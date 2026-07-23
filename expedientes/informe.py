"""Generacion del informe en dos formatos con la misma informacion.

  - JSON: contrato estable para integrar el clasificador aguas abajo.
  - Markdown: lectura humana, que es lo que necesita el operador que tiene que
    resolver las incidencias.

Determinismo: salvo el sello temporal ``generado_en``, dos ejecuciones sobre la
misma entrada producen informes identicos. El sello se puede inyectar para que
los tests comparen byte a byte.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .escritura import DIR_INFORMES, carpeta_cliente
from .modelo import EstadoExpediente, Resultado, Severidad

VERSION_INFORME = "1.0"


def _resumen(resultado: Resultado) -> dict:
    completos = sum(
        1 for e in resultado.expedientes if e.estado is EstadoExpediente.COMPLETO
    )
    avisos = sum(
        len(d.avisos) for e in resultado.expedientes for d in e.documentos.values()
    ) + sum(len(e.avisos) for e in resultado.expedientes)
    return {
        "ficheros_leidos": resultado.ficheros_leidos,
        "expedientes": len(resultado.expedientes),
        "expedientes_completos": completos,
        "expedientes_incompletos": len(resultado.expedientes) - completos,
        "documentos_archivados": sum(
            len(e.documentos) for e in resultado.expedientes
        ),
        "ficheros_descartados": len(resultado.descartes),
        "avisos": avisos,
        "clientes": len({carpeta_cliente(e) for e in resultado.expedientes}),
    }


def _por_motivo(resultado: Resultado) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for descarte in resultado.descartes:
        conteo[descarte.motivo.value] = conteo.get(descarte.motivo.value, 0) + 1
    return dict(sorted(conteo.items()))


def construir_json(resultado: Resultado, generado_en: str | None = None) -> dict:
    sello = generado_en or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "version_informe": VERSION_INFORME,
        "generado_en": sello,
        "resumen": _resumen(resultado),
        "incidencias_por_motivo": _por_motivo(resultado),
        "expedientes": [e.a_dict() for e in resultado.expedientes],
        "incidencias": [d.a_dict() for d in resultado.descartes],
    }


def _tabla(cabeceras: list[str], filas: list[list[str]]) -> list[str]:
    if not filas:
        return ["_Sin registros._", ""]
    lineas = ["| " + " | ".join(cabeceras) + " |"]
    lineas.append("|" + "|".join(["---"] * len(cabeceras)) + "|")
    for fila in filas:
        lineas.append("| " + " | ".join(fila) + " |")
    lineas.append("")
    return lineas


def construir_markdown(resultado: Resultado, generado_en: str | None = None) -> str:
    datos = construir_json(resultado, generado_en)
    r = datos["resumen"]

    lineas: list[str] = [
        "# Informe de clasificacion documental",
        "",
        f"Generado: {datos['generado_en']}",
        "",
        "## Resumen",
        "",
        f"- Ficheros leidos del inbox: **{r['ficheros_leidos']}**",
        f"- Expedientes identificados: **{r['expedientes']}** "
        f"({r['clientes']} clientes)",
        f"- Completos: **{r['expedientes_completos']}** / "
        f"Incompletos: **{r['expedientes_incompletos']}**",
        f"- Documentos archivados: **{r['documentos_archivados']}**",
        f"- Ficheros descartados: **{r['ficheros_descartados']}**",
        f"- Avisos no bloqueantes: **{r['avisos']}**",
        "",
        "Un expediente es **COMPLETO** cuando contiene DUA, FACTURA y PACKING.",
        "TRANSPORTE y CERTORIGEN son opcionales y no alteran el estado.",
        "",
        "## Expedientes",
        "",
    ]

    filas = []
    for expediente in sorted(
        resultado.expedientes, key=lambda e: (e.cliente, e.mrn)
    ):
        ausentes = expediente.obligatorios_ausentes
        opcionales = expediente.opcionales_ausentes
        filas.append(
            [
                expediente.cliente,
                expediente.nif,
                f"`{expediente.mrn}`",
                expediente.estado.value,
                ", ".join(t.value for t in expediente.tipos_presentes) or "-",
                ", ".join(t.value for t in ausentes) or "-",
                ", ".join(t.value for t in opcionales) or "-",
            ]
        )
    lineas += _tabla(
        [
            "Cliente",
            "NIF",
            "MRN",
            "Estado",
            "Documentos encontrados",
            "Obligatorios ausentes",
            "Opcionales ausentes",
        ],
        filas,
    )

    lineas += ["## Incidencias", ""]
    if resultado.descartes:
        lineas += [
            "Ficheros que no han podido incorporarse al archivo. Cada uno se "
            f"conserva en `_descartes/<motivo>/` junto a un sidecar "
            "`.motivo.json` con este mismo detalle.",
            "",
        ]
        lineas += _tabla(
            ["Motivo", "Nº"],
            [[m, str(n)] for m, n in datos["incidencias_por_motivo"].items()],
        )
        lineas += _tabla(
            ["Fichero", "Problema detectado", "Decision adoptada"],
            [
                [
                    f"`{d.origen.name}`",
                    d.problema,
                    d.decision,
                ]
                for d in resultado.descartes
            ],
        )
    else:
        lineas += ["_Sin incidencias._", ""]

    lineas += ["## Avisos", ""]
    avisos = []
    for expediente in sorted(resultado.expedientes, key=lambda e: e.mrn):
        for aviso in expediente.avisos:
            avisos.append([f"`{expediente.mrn}`", "(expediente)", aviso.codigo, aviso.detalle])
        for tipo in expediente.tipos_presentes:
            documento = expediente.documentos[tipo]
            for aviso in documento.avisos:
                avisos.append(
                    [
                        f"`{expediente.mrn}`",
                        f"`{documento.origen.name}`",
                        aviso.codigo,
                        aviso.detalle,
                    ]
                )
    if avisos:
        lineas += [
            "Anomalias detectadas que **no** han impedido clasificar el documento.",
            "",
        ]
        lineas += _tabla(["MRN", "Fichero", "Codigo", "Detalle"], avisos)
    else:
        lineas += ["_Sin avisos._", ""]

    return "\n".join(lineas).rstrip() + "\n"


def escribir_informes(
    salida: Path, resultado: Resultado, generado_en: str | None = None
) -> tuple[Path, Path]:
    destino = salida / DIR_INFORMES
    destino.mkdir(parents=True, exist_ok=True)

    ruta_json = destino / "informe.json"
    ruta_json.write_text(
        json.dumps(construir_json(resultado, generado_en), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    ruta_md = destino / "informe.md"
    ruta_md.write_text(construir_markdown(resultado, generado_en), encoding="utf-8")
    return ruta_md, ruta_json
