"""Lectura del inbox: de fichero en bruto a documento parseado o descarte.

Esta capa no decide nada sobre expedientes; solo responde a "que es este
fichero y puedo confiar en el". El inbox se trata como estrictamente de solo
lectura: aqui no se escribe, renombra ni mueve nada.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .modelo import Aviso, Descarte, Documento, Motivo, Severidad, TipoDocumento
from .normalizacion import normalizar_tipo, parsear_fecha
from .validacion import mrn_valido, validar_nif

#: Ficheros que ningun sistema documental deberia intentar interpretar.
_PATRONES_ARTEFACTO = (
    re.compile(r"^\.DS_Store$"),
    re.compile(r"^Thumbs\.db$", re.IGNORECASE),
    re.compile(r"^~\$"),  # temporales de Microsoft Office
    re.compile(r"\.tmp$", re.IGNORECASE),
    re.compile(r"^\._"),  # forks de recurso de macOS
)

#: Nombre canonico esperado: TIPO_MRN_FECHA_NIF.txt
_PATRON_NOMBRE = re.compile(r"^(?P<tipo>.+?)_(?P<mrn>[^_]+)_(?P<fecha>[^_]+)_(?P<nif>[^_]+)$")

#: Sufijos que anyaden los gestores de ficheros al copiar; son ruido, no identidad.
_SUFIJOS_COPIA = re.compile(r"(\s*\(\d+\)|_copia|_copy|\s*-\s*copia)$", re.IGNORECASE)

#: Campos sin los cuales el documento no puede archivarse por cliente y expediente.
CAMPOS_MINIMOS = ("TIPO", "MRN", "NIF-CLIENTE")


@dataclass(frozen=True)
class PistasNombre:
    """Lo que sugiere el nombre del fichero. Nunca es fuente de verdad (D1)."""

    tipo: TipoDocumento | None = None
    tipo_bruto: str | None = None
    mrn: str | None = None
    fecha: str | None = None
    nif: str | None = None
    es_copia: bool = False


def analizar_nombre(ruta: Path) -> PistasNombre:
    tallo = ruta.stem
    sin_sufijo = _SUFIJOS_COPIA.sub("", tallo)
    es_copia = sin_sufijo != tallo

    m = _PATRON_NOMBRE.fullmatch(sin_sufijo)
    if not m:
        return PistasNombre(es_copia=es_copia)
    return PistasNombre(
        tipo=normalizar_tipo(m.group("tipo")),
        tipo_bruto=m.group("tipo"),
        mrn=m.group("mrn"),
        fecha=m.group("fecha"),
        nif=m.group("nif"),
        es_copia=es_copia,
    )


def parsear_campos(texto: str) -> dict[str, str]:
    """Extrae los pares CLAVE: VALOR del cuerpo del documento.

    Se ignoran lineas decorativas (=== ... ===) y lineas sin separador. Las
    claves se normalizan a mayusculas para tolerar variaciones de estilo.
    """
    campos: dict[str, str] = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("==="):
            continue
        clave, sep, valor = linea.partition(":")
        if not sep:
            continue
        clave = clave.strip().upper()
        if clave and clave not in campos:  # la primera aparicion manda
            campos[clave] = valor.strip()
    return campos


def leer_fichero(ruta: Path) -> tuple[Documento | None, Descarte | None]:
    """Convierte un fichero del inbox en un Documento o en un Descarte motivado."""
    nombre = ruta.name

    for patron in _PATRONES_ARTEFACTO:
        if patron.search(nombre):
            return None, Descarte(
                origen=ruta,
                motivo=Motivo.ARTEFACTO_SISTEMA,
                problema="Artefacto del sistema de ficheros o temporal de ofimatica.",
                decision="No se intenta interpretar; se aparta sin analizar.",
            )

    datos = ruta.read_bytes()
    if not datos.strip():
        return None, Descarte(
            origen=ruta,
            motivo=Motivo.FICHERO_VACIO,
            problema=f"El fichero no tiene contenido ({len(datos)} bytes).",
            decision="Se aparta: no hay nada que clasificar.",
        )

    try:
        # utf-8-sig descarta la marca BOM que anteponen muchas herramientas de
        # Windows. Sin ella, la primera clave del documento se leeria como
        # "﻿TIPO" y el fichero se rechazaria por falta de estructura.
        texto = datos.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return None, Descarte(
            origen=ruta,
            motivo=Motivo.NO_DECODIFICABLE,
            problema=f"No es texto UTF-8 valido: {exc.reason} en el byte {exc.start}.",
            decision="Se aparta: el contenido no es legible como documento de texto.",
        )

    campos = parsear_campos(texto)
    pistas = analizar_nombre(ruta)

    # Campos minimos: sin tipo no se clasifica, sin MRN no hay expediente y sin
    # NIF no se puede archivar por cliente, que es lo que se pide.
    ausentes = [c for c in CAMPOS_MINIMOS if not campos.get(c, "").strip()]
    if ausentes:
        return None, Descarte(
            origen=ruta,
            motivo=Motivo.SIN_ESTRUCTURA,
            problema=(
                f"El contenido no expone los campos minimos {', '.join(ausentes)} "
                f"(claves encontradas: {sorted(campos) or 'ninguna'})."
            ),
            decision="Se aparta: no es un documento del expediente clasificable.",
        )

    avisos: list[Aviso] = []

    # --- Tipo: manda el contenido; el nombre solo genera aviso si diverge ---
    tipo = normalizar_tipo(campos["TIPO"])
    if tipo is None:
        return None, Descarte(
            origen=ruta,
            motivo=Motivo.TIPO_DESCONOCIDO,
            problema=f"Tipo documental no reconocido: {campos['TIPO']!r}.",
            decision="Se aparta: anyadir el alias al catalogo si es un tipo legitimo.",
            mrn=campos.get("MRN"),
        )
    if pistas.tipo is not None and pistas.tipo is not tipo:
        avisos.append(
            Aviso(
                "TIPO_DIVERGENTE",
                f"El nombre sugiere {pistas.tipo.value} y el contenido declara "
                f"{tipo.value}; prevalece el contenido.",
            )
        )
    elif pistas.tipo_bruto and normalizar_tipo(pistas.tipo_bruto) is tipo:
        if pistas.tipo_bruto.upper().replace(" ", "") != tipo.value:
            avisos.append(
                Aviso(
                    "ALIAS_TIPO",
                    f"El nombre usa el alias {pistas.tipo_bruto!r} para {tipo.value}.",
                    Severidad.INFO,
                )
            )

    # --- MRN: identidad del expediente, no se corrige nunca (D3) ---
    mrn = campos["MRN"].strip().upper()
    if not mrn_valido(mrn):
        return None, Descarte(
            origen=ruta,
            motivo=Motivo.MRN_INVALIDO,
            problema=(
                f"El MRN {mrn!r} ({len(mrn)} caracteres) no cumple el formato "
                "de 18 caracteres AAPP + 14 alfanumericos."
            ),
            decision=(
                "Se aparta sin reasignar: el MRN identifica el expediente y una "
                "fusion erronea contaminaria un expediente ajeno."
            ),
            mrn=mrn,
            tipo=tipo,
        )
    if pistas.mrn and pistas.mrn.upper() != mrn:
        avisos.append(
            Aviso(
                "MRN_DIVERGENTE",
                f"El nombre indica el MRN {pistas.mrn} y el contenido {mrn}; "
                "prevalece el contenido.",
            )
        )

    # --- NIF: la letra de control desambigua sin heuristicas ---
    diagnostico = validar_nif(campos.get("NIF-CLIENTE"))
    nif = diagnostico.canonico
    if diagnostico.validable and not diagnostico.valido:
        avisos.append(
            Aviso(
                "NIF_CORREGIDO",
                f"El NIF {diagnostico.original} tiene letra de control incorrecta; "
                f"se normaliza a {nif}.",
            )
        )
    if not diagnostico.validable and nif:
        avisos.append(
            Aviso(
                "NIF_NO_VALIDABLE",
                f"El identificador {nif} no es un DNI/NIE; se acepta sin validar.",
                Severidad.INFO,
            )
        )

    # --- Fecha: informativa, nunca bloqueante ---
    fecha = parsear_fecha(campos.get("FECHA"))
    if campos.get("FECHA") and fecha is None:
        avisos.append(
            Aviso(
                "FECHA_INVALIDA",
                f"La fecha {campos['FECHA']!r} no corresponde a un dia real; "
                "el documento se clasifica igualmente.",
            )
        )
    if pistas.fecha and fecha is not None:
        fecha_nombre = parsear_fecha(pistas.fecha)
        if fecha_nombre is not None and fecha_nombre != fecha:
            avisos.append(
                Aviso(
                    "FECHA_DIVERGENTE",
                    f"El nombre fecha el documento el {fecha_nombre.isoformat()} y el "
                    f"contenido el {fecha.isoformat()}; prevalece el contenido.",
                )
            )

    documento = Documento(
        origen=ruta,
        hash_sha256=hashlib.sha256(datos).hexdigest(),
        tipo=tipo,
        mrn=mrn,
        nif=nif,
        cliente=campos.get("CLIENTE", "").strip() or "DESCONOCIDO",
        fecha=fecha,
        campos=campos,
        avisos=avisos,
    )
    return documento, None


def leer_inbox(inbox: Path) -> tuple[list[Documento], list[Descarte]]:
    """Lee todos los ficheros del inbox en orden determinista."""
    if not inbox.is_dir():
        raise NotADirectoryError(f"El inbox {inbox} no existe o no es un directorio.")

    documentos: list[Documento] = []
    descartes: list[Descarte] = []
    for ruta in sorted(p for p in inbox.iterdir() if p.is_file()):
        documento, descarte = leer_fichero(ruta)
        if documento is not None:
            documentos.append(documento)
        if descarte is not None:
            descartes.append(descarte)
    return documentos, descartes
