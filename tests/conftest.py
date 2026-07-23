from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

PLANTILLA = """=== DOCUMENTO SIMULADO - PRUEBA TECNICA ===
TIPO: {tipo}
MRN: {mrn}
FECHA: {fecha}
NIF-CLIENTE: {nif}
CLIENTE: {cliente}
MERCANCIA: {mercancia}
BULTOS: {bultos}
PESO-KG: {peso}
"""

MRN_A = "26ESAAAAAAAAAAAAAA"
MRN_B = "26ESBBBBBBBBBBBBBB"
NIF_A = "20989659C"  # letra de control valida
NIF_A_MALA = "20989659W"  # mismo numero, letra incorrecta
NIF_B = "46490500W"


def cuerpo(
    tipo: str = "DUA",
    mrn: str = MRN_A,
    fecha: str = "2026-03-15",
    nif: str = NIF_A,
    cliente: str = "Maderas Soria SL",
    mercancia: str = "tablero contrachapado",
    bultos: int = 10,
    peso: int = 1000,
    nota: str | None = None,
) -> str:
    texto = PLANTILLA.format(
        tipo=tipo,
        mrn=mrn,
        fecha=fecha,
        nif=nif,
        cliente=cliente,
        mercancia=mercancia,
        bultos=bultos,
        peso=peso,
    )
    if nota:
        texto += f"NOTA: {nota}\n"
    return texto


@pytest.fixture
def inbox(tmp_path: Path) -> Path:
    destino = tmp_path / "inbox"
    destino.mkdir()
    return destino


@pytest.fixture
def crear(inbox: Path):
    """Crea un fichero en el inbox de pruebas y devuelve su ruta."""

    def _crear(nombre: str, contenido: str | bytes = None, **kwargs) -> Path:
        ruta = inbox / nombre
        if contenido is None:
            contenido = cuerpo(**kwargs)
        if isinstance(contenido, bytes):
            ruta.write_bytes(contenido)
        else:
            ruta.write_text(contenido, encoding="utf-8")
        return ruta

    return _crear


def huella_arbol(raiz: Path) -> list[tuple[str, str]]:
    """Huella determinista de un arbol: rutas relativas + hash de contenido."""
    entradas = []
    for ruta in sorted(raiz.rglob("*")):
        rel = ruta.relative_to(raiz).as_posix()
        if ruta.is_dir():
            entradas.append((rel + "/", ""))
        else:
            entradas.append((rel, hashlib.sha256(ruta.read_bytes()).hexdigest()))
    return entradas
