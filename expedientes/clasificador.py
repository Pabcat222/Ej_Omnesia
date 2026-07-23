"""Agrupacion de documentos en expedientes y resolucion de conflictos.

Orden del pipeline (importa, y esta razonado en el README):

  1. Agrupar por MRN.
  2. Fijar el titular de cada expediente y expulsar a los intrusos.
  3. Resolver duplicados y versiones dentro de cada (MRN, TIPO).
  4. Sugerir MRN candidatos para los ficheros con MRN corrupto.

Se resuelve la identidad ANTES que las versiones para no elegir como "buena" la
version de un documento que ni siquiera pertenece al expediente.
"""

from __future__ import annotations

import collections
from pathlib import Path

from .modelo import (
    Aviso,
    Descarte,
    Documento,
    Expediente,
    Motivo,
    Resultado,
    Severidad,
    TipoDocumento,
)
from .validacion import sugerir_mrn


def _orden_estable(documento: Documento) -> tuple:
    """Orden total y reproducible entre documentos equivalentes.

    Ante un empate real (dos ficheros indistinguibles salvo por el nombre) se
    escoge siempre el mismo para que dos ejecuciones den el mismo arbol.
    """
    return (
        not documento.es_rectificacion,  # las rectificaciones primero
        documento.fecha is None,  # las fechas validas antes que las ausentes
        documento.fecha.toordinal() if documento.fecha else 0,
        documento.origen.name,
    )


def _resolver_titular(
    mrn: str, documentos: list[Documento]
) -> tuple[str | None, str | None, list[Aviso]]:
    """Determina a que cliente pertenece un expediente.

      1. Si todos los documentos declaran el mismo NIF, ese es el titular.
      2. Si discrepan, manda el NIF del DUA: es la declaracion que la aduana
         asocia al MRN, luego es la fuente autorizada sobre la identidad de la
         operacion.
      3. Sin un DUA que arbitre, no se decide: el expediente entero va a
         cuarentena.

    No hay desempate por mayoria ni por ningun otro criterio. Una heuristica de
    ese tipo no tiene respaldo en los datos observados y solo servira para elegir
    un titular equivocado con aparente seguridad. Se prefiere no responder.
    """
    avisos: list[Aviso] = []
    nifs = {d.nif for d in documentos}
    if len(nifs) == 1:
        unico = documentos[0]
        return unico.nif, unico.cliente, avisos

    nifs_dua = {d.nif for d in documentos if d.tipo is TipoDocumento.DUA}
    if len(nifs_dua) != 1:
        avisos.append(
            Aviso(
                "TITULAR_INDETERMINADO",
                f"Los documentos declaran {len(nifs)} NIF distintos "
                f"({', '.join(sorted(nifs))}) y no hay un unico DUA que arbitre.",
            )
        )
        return None, None, avisos

    titular = next(d for d in documentos if d.tipo is TipoDocumento.DUA)
    avisos.append(
        Aviso(
            "TITULAR_POR_DUA",
            f"Documentos con {len(nifs)} NIF distintos; el titular se fija por "
            f"el DUA ({titular.nif}).",
        )
    )
    return titular.nif, titular.cliente, avisos


def _resolver_versiones(
    documentos: list[Documento],
) -> tuple[Documento | None, list[Descarte]]:
    """Elige un unico documento entre varios del mismo (MRN, TIPO).

      - Contenido identico (mismo sha256): duplicado material, se conserva uno.
      - Contenidos distintos y exactamente uno marcado RECTIFICACION: manda ese.
      - Contenidos distintos sin marca que arbitre: no se elige ninguno. Se
        prefiere un hueco visible en el expediente a un dato elegido al azar.
    """
    descartes: list[Descarte] = []
    if len(documentos) == 1:
        return documentos[0], descartes

    ordenados = sorted(documentos, key=_orden_estable)
    por_hash: dict[str, list[Documento]] = collections.defaultdict(list)
    for documento in ordenados:
        por_hash[documento.hash_sha256].append(documento)

    representantes: list[Documento] = []
    for copias in por_hash.values():
        representantes.append(copias[0])
        for duplicado in copias[1:]:
            descartes.append(
                Descarte(
                    origen=duplicado.origen,
                    motivo=Motivo.DUPLICADO_EXACTO,
                    problema=(
                        f"Contenido byte a byte identico a {copias[0].origen.name} "
                        f"(sha256 {duplicado.hash_sha256[:12]}...)."
                    ),
                    decision=f"Se conserva {copias[0].origen.name} y se aparta esta copia.",
                    mrn=duplicado.mrn,
                    tipo=duplicado.tipo,
                )
            )

    if len(representantes) == 1:
        return representantes[0], descartes

    rectificaciones = [d for d in representantes if d.es_rectificacion]
    if len(rectificaciones) == 1:
        ganador = rectificaciones[0]
        for superado in representantes:
            if superado is ganador:
                continue
            descartes.append(
                Descarte(
                    origen=superado.origen,
                    motivo=Motivo.VERSION_SUPERADA,
                    problema=(
                        f"Existe una version posterior del mismo {superado.tipo.value} "
                        f"marcada como rectificacion: {ganador.origen.name}."
                    ),
                    decision=(
                        "Se archiva la version rectificada y esta se conserva en "
                        "descartes como historico."
                    ),
                    mrn=superado.mrn,
                    tipo=superado.tipo,
                )
            )
        ganador.avisos.append(
            Aviso(
                "RECTIFICACION_APLICADA",
                "Sustituye a "
                + ", ".join(
                    sorted(d.origen.name for d in representantes if d is not ganador)
                )
                + ".",
            )
        )
        return ganador, descartes

    nombres = sorted(d.origen.name for d in representantes)
    for conflictivo in representantes:
        descartes.append(
            Descarte(
                origen=conflictivo.origen,
                motivo=Motivo.CONFLICTO_VERSION,
                problema=(
                    f"{len(representantes)} versiones distintas del mismo "
                    f"{conflictivo.tipo.value} sin marca de rectificacion que arbitre: "
                    + ", ".join(nombres)
                    + "."
                ),
                decision=(
                    "No se elige ninguna; el tipo queda como ausente en el "
                    "expediente y requiere revision manual."
                ),
                mrn=conflictivo.mrn,
                tipo=conflictivo.tipo,
            )
        )
    return None, descartes


def clasificar(
    documentos: list[Documento], descartes_previos: list[Descarte]
) -> Resultado:
    """Construye los expedientes a partir de los documentos ya validados."""
    descartes = list(descartes_previos)
    expedientes: list[Expediente] = []

    por_mrn: dict[str, list[Documento]] = collections.defaultdict(list)
    for documento in documentos:
        por_mrn[documento.mrn].append(documento)

    for mrn in sorted(por_mrn):
        del_mrn = por_mrn[mrn]
        nif, cliente, avisos = _resolver_titular(mrn, del_mrn)

        if nif is None:
            for huerfano in del_mrn:
                descartes.append(
                    Descarte(
                        origen=huerfano.origen,
                        motivo=Motivo.CONFLICTO_CLIENTE,
                        problema=(
                            f"El expediente {mrn} tiene titular indeterminado: sus "
                            "documentos declaran NIF distintos y no hay un unico "
                            "DUA que arbitre."
                        ),
                        decision="Expediente completo a cuarentena; requiere revision manual.",
                        mrn=mrn,
                        tipo=huerfano.tipo,
                    )
                )
            continue

        propios: list[Documento] = []
        for documento in del_mrn:
            if documento.nif == nif:
                propios.append(documento)
                continue
            descartes.append(
                Descarte(
                    origen=documento.origen,
                    motivo=Motivo.CONFLICTO_CLIENTE,
                    problema=(
                        f"Declara el MRN {mrn}, cuyo titular es {nif} ({cliente}), "
                        f"pero identifica como cliente a {documento.nif} "
                        f"({documento.cliente})."
                    ),
                    decision=(
                        "No se incorpora al expediente: mezclar documentos de dos "
                        "clientes es un fallo mas grave que un expediente incompleto."
                    ),
                    mrn=mrn,
                    tipo=documento.tipo,
                )
            )

        expediente = Expediente(mrn=mrn, nif=nif, cliente=cliente, avisos=avisos)
        por_tipo: dict[TipoDocumento, list[Documento]] = collections.defaultdict(list)
        for documento in propios:
            por_tipo[documento.tipo].append(documento)

        for tipo in sorted(por_tipo, key=lambda t: t.value):
            elegido, nuevos = _resolver_versiones(por_tipo[tipo])
            descartes.extend(nuevos)
            if elegido is not None:
                expediente.documentos[tipo] = elegido

        expedientes.append(expediente)

    _unificar_razon_social(expedientes)
    _anotar_sugerencias(expedientes, descartes)

    return Resultado(
        expedientes=expedientes,
        descartes=sorted(descartes, key=lambda d: (d.motivo.value, d.origen.name)),
        ficheros_leidos=len(documentos) + len(descartes_previos),
    )


def _unificar_razon_social(expedientes: list[Expediente]) -> None:
    """Garantiza una unica carpeta por NIF aunque la razon social varie.

    El NIF es la clave del cliente (D9) y el nombre solo aporta legibilidad, pero
    la carpeta combina ambos: si el mismo NIF aparece como "Maderas Soria SL" y
    "MADERAS SORIA, S.L.", el archivo partiria un cliente en dos directorios.

    Se elige el nombre mas frecuente, medido en documentos, y se desempata
    alfabeticamente para que el resultado sea reproducible. La regla afecta solo
    a como se presenta el cliente; la identidad la sigue fijando el NIF.
    """
    nombres_por_nif: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for expediente in expedientes:
        peso = max(len(expediente.documentos), 1)
        nombres_por_nif[expediente.nif][expediente.cliente] += peso

    for expediente in expedientes:
        variantes = nombres_por_nif[expediente.nif]
        if len(variantes) == 1:
            continue
        canonico = min(variantes.items(), key=lambda par: (-par[1], par[0]))[0]
        if canonico == expediente.cliente:
            continue
        expediente.avisos.append(
            Aviso(
                "RAZON_SOCIAL_UNIFICADA",
                f"El NIF {expediente.nif} aparece como {expediente.cliente!r} y como "
                f"{canonico!r}; se archiva bajo {canonico!r} para no partir el cliente.",
            )
        )
        expediente.cliente = canonico


def _anotar_sugerencias(
    expedientes: list[Expediente], descartes: list[Descarte]
) -> None:
    """Propone un MRN candidato para cada fichero con MRN corrupto.

    Es una pista para el operador que tiene que arreglarlo a mano, no una
    correccion: el documento sigue descartado.
    """
    validos = {e.mrn for e in expedientes}
    for descarte in descartes:
        if descarte.motivo is not Motivo.MRN_INVALIDO or not descarte.mrn:
            continue
        candidato = sugerir_mrn(descarte.mrn, validos)
        if candidato:
            descarte.sugerencia = candidato
            descarte.decision += (
                f" Candidato mas proximo para revision manual: {candidato}."
            )
