"""Normalizacion de valores heterogeneos a un vocabulario canonico."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from .modelo import TipoDocumento

#: Catalogo de alias. Solo contiene los que aparecen en el dataset y los que el
#: enunciado nombra explicitamente; no se anticipan sinonimos hipoteticos. Dar de
#: alta uno nuevo es anyadir una linea, y hasta entonces un tipo no reconocido se
#: descarta de forma ruidosa (motivo `tipo_desconocido`) para que alguien decida.
#:
#: La clave se compara ya normalizada (mayusculas, sin acentos ni separadores),
#: de modo que "CERTIFICADO ORIGEN", "certificado-origen" y "CERTORIGEN" colapsan
#: en la misma entrada.
ALIAS_TIPO: dict[str, TipoDocumento] = {
    "DUA": TipoDocumento.DUA,
    # FACTURA
    "FACTURA": TipoDocumento.FACTURA,
    "FRA": TipoDocumento.FACTURA,
    # PACKING LIST
    "PACKING": TipoDocumento.PACKING,
    "PACKINGLIST": TipoDocumento.PACKING,
    "PLIST": TipoDocumento.PACKING,
    # TRANSPORTE: el enunciado enumera CMR, B/L y AWB como las formas del
    # documento de transporte, luego las tres son alias del mismo tipo logico.
    "TRANSPORTE": TipoDocumento.TRANSPORTE,
    "CMR": TipoDocumento.TRANSPORTE,
    "BL": TipoDocumento.TRANSPORTE,
    "AWB": TipoDocumento.TRANSPORTE,
    # CERTIFICADO DE ORIGEN
    "CERTORIGEN": TipoDocumento.CERTORIGEN,
    "CERTIFICADOORIGEN": TipoDocumento.CERTORIGEN,
}

_NO_ALFANUM = re.compile(r"[^A-Z0-9]+")


def normalizar_tipo(bruto: str | None) -> TipoDocumento | None:
    """Traduce una etiqueta de tipo a su tipo canonico, o None si no se reconoce."""
    if not bruto:
        return None
    clave = _NO_ALFANUM.sub("", quitar_acentos(bruto).upper())
    return ALIAS_TIPO.get(clave)


def quitar_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def slug(texto: str) -> str:
    """Convierte una razon social en un fragmento de ruta seguro y estable.

    'Congelados Atlantico, S.A.' -> 'congelados-atlantico-s-a'
    """
    limpio = quitar_acentos(texto).lower()
    limpio = re.sub(r"[^a-z0-9]+", "-", limpio)
    return limpio.strip("-") or "sin-nombre"


#: Formatos de fecha vistos en nombres de fichero y contenidos.
_FORMATOS_FECHA = ("%Y-%m-%d", "%Y%m%d", "%d-%m-%Y", "%d/%m/%Y")


def parsear_fecha(bruto: str | None) -> date | None:
    """Interpreta una fecha en cualquiera de los formatos aceptados.

    Devuelve None si el valor es sintacticamente reconocible pero no corresponde
    a un dia real (p.ej. 2026-02-30), caso que el llamante reporta como aviso.
    """
    if not bruto:
        return None
    texto = bruto.strip()
    from datetime import datetime

    for formato in _FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None
