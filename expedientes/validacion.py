"""Validaciones de identificadores del dominio: MRN y NIF.

Ambas son reglas objetivas y verificables, no heuristicas: permiten decidir
entre valores contradictorios sin recurrir a "el primero que llegue".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: MRN (Movement Reference Number): 18 caracteres.
#:   2 digitos de anyo + 2 letras de pais + 14 alfanumericos.
#: No se fija "26ES" a fuego: el lote actual es de 2026/Espanya, pero el formato
#: es el general de la UE y el clasificador debe seguir sirviendo en 2027.
PATRON_MRN = re.compile(r"^\d{2}[A-Z]{2}[A-Z0-9]{14}$")

LONGITUD_MRN = 18


def mrn_valido(mrn: str) -> bool:
    return bool(PATRON_MRN.fullmatch(mrn or ""))


# --------------------------------------------------------------------------- #
# NIF
# --------------------------------------------------------------------------- #

_LETRAS_NIF = "TRWAGMYFPDXBNJZSQVHLCKE"
_PREFIJO_NIE = {"X": "0", "Y": "1", "Z": "2"}

_PATRON_DNI = re.compile(r"^(\d{8})([A-Z])$")
_PATRON_NIE = re.compile(r"^([XYZ])(\d{7})([A-Z])$")


@dataclass(frozen=True)
class ResultadoNIF:
    """Diagnostico de un NIF.

    - ``valido``    : la letra de control cuadra con el numero.
    - ``canonico``  : el NIF con la letra correcta (igual al original si es valido).
    - ``validable`` : False para formatos que este validador no cubre (p.ej. CIF
                      de persona juridica), donde no se corrige nada.
    """

    original: str
    valido: bool
    canonico: str
    validable: bool


def validar_nif(bruto: str | None) -> ResultadoNIF:
    """Comprueba la letra de control de un DNI o NIE y devuelve su forma canonica.

    La letra de control es un digito verificador (modulo 23) sobre la parte
    numerica. Si la letra no cuadra, lo probable es un error de transcripcion en
    la letra, no en los 8 digitos: por eso el canonico conserva el numero y
    recalcula la letra. Esta asuncion queda documentada en el README.
    """
    texto = (bruto or "").strip().upper().replace("-", "").replace(" ", "")

    if m := _PATRON_DNI.fullmatch(texto):
        numero, letra = m.group(1), m.group(2)
        esperada = _LETRAS_NIF[int(numero) % 23]
        return ResultadoNIF(texto, letra == esperada, numero + esperada, True)

    if m := _PATRON_NIE.fullmatch(texto):
        prefijo, numero, letra = m.groups()
        equivalente = _PREFIJO_NIE[prefijo] + numero
        esperada = _LETRAS_NIF[int(equivalente) % 23]
        return ResultadoNIF(texto, letra == esperada, prefijo + numero + esperada, True)

    # CIF u otro formato: no se valida ni se corrige, se acepta tal cual.
    return ResultadoNIF(texto, True, texto, False)


# --------------------------------------------------------------------------- #
# Distancia de edicion (solo para sugerir, nunca para corregir)
# --------------------------------------------------------------------------- #


def distancia_edicion(a: str, b: str, maximo: int = 2) -> int:
    """Distancia de Levenshtein acotada.

    Se usa exclusivamente para proponer al operador un MRN candidato en el
    informe cuando aparece un MRN mal formado. Nunca se aplica la correccion de
    forma automatica (decision de diseno D3).
    """
    if abs(len(a) - len(b)) > maximo:
        return maximo + 1
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        actual = [i]
        for j, cb in enumerate(b, start=1):
            actual.append(
                min(
                    previa[j] + 1,
                    actual[j - 1] + 1,
                    previa[j - 1] + (ca != cb),
                )
            )
        previa = actual
        if min(previa) > maximo:
            return maximo + 1
    return previa[-1]


def sugerir_mrn(mrn_roto: str, candidatos: set[str], umbral: int = 1) -> str | None:
    """Devuelve el unico MRN valido a distancia <= umbral, o None si hay ambiguedad."""
    cercanos = sorted(
        c for c in candidatos if distancia_edicion(mrn_roto, c, umbral) <= umbral
    )
    return cercanos[0] if len(cercanos) == 1 else None
