"""Interfaz de linea de comandos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .clasificador import clasificar
from .escritura import DestinoNoSeguroError, comprobar_rutas, escribir_salida
from .informe import construir_markdown, escribir_informes
from .lectura import leer_inbox
from .modelo import EstadoExpediente, Resultado

CODIGO_OK = 0
CODIGO_ERROR = 1
CODIGO_INCIDENCIAS = 2


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expedientes",
        description=(
            "Clasifica los documentos de un inbox en expedientes aduaneros por "
            "cliente y MRN, y emite un informe de estado e incidencias. "
            "El inbox se trata como de solo lectura."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Codigos de salida:\n"
            "  0  ejecucion correcta\n"
            "  1  error de ejecucion\n"
            "  2  hubo incidencias (solo con --fallar-si-incidencias)\n"
        ),
    )
    parser.add_argument(
        "--inbox",
        type=Path,
        default=Path("dataset/inbox"),
        help="Directorio de entrada (por defecto: dataset/inbox).",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path("salida"),
        help="Directorio de salida; se reconstruye en cada ejecucion (por defecto: salida).",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Permite reconstruir un destino no vacio no generado por esta herramienta.",
    )
    parser.add_argument(
        "--informe-stdout",
        action="store_true",
        help=(
            "Escribe ademas el informe Markdown por la salida estandar, para "
            "leerlo o encadenarlo sin abrir el fichero."
        ),
    )
    parser.add_argument(
        "--fallar-si-incidencias",
        action="store_true",
        help=(
            "Devuelve codigo 2 si algun fichero no ha podido procesarse, para que "
            "un orquestador o una tuberia de CI puedan detenerse."
        ),
    )
    parser.add_argument(
        "-q",
        "--silencioso",
        action="store_true",
        help="Suprime el resumen por consola.",
    )
    return parser


def _resumir(resultado: Resultado, salida: Path) -> str:
    completos = sum(
        1 for e in resultado.expedientes if e.estado is EstadoExpediente.COMPLETO
    )
    return (
        f"Leidos {resultado.ficheros_leidos} ficheros de inbox.\n"
        f"Expedientes: {len(resultado.expedientes)} "
        f"({completos} completos, {len(resultado.expedientes) - completos} incompletos).\n"
        f"Descartados: {len(resultado.descartes)} ficheros.\n"
        f"Salida en: {salida}"
    )


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    try:
        comprobar_rutas(args.inbox, args.salida)
        documentos, descartes = leer_inbox(args.inbox)
        resultado = clasificar(documentos, descartes)
        escribir_salida(args.salida, resultado, forzar=args.forzar)
        escribir_informes(args.salida, resultado)
    except (NotADirectoryError, DestinoNoSeguroError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return CODIGO_ERROR

    # El informe va por stdout y el resumen por stderr, de modo que
    # `expedientes --informe-stdout -q > informe.md` produzca un fichero limpio.
    if args.informe_stdout:
        print(construir_markdown(resultado))
    if not args.silencioso:
        print(_resumir(resultado, args.salida), file=sys.stderr)

    # El fallo es opcional y no por defecto: un lote con incidencias sigue siendo
    # una ejecucion correcta del clasificador, no un error de la herramienta.
    if args.fallar_si_incidencias and resultado.descartes:
        return CODIGO_INCIDENCIAS
    return CODIGO_OK


if __name__ == "__main__":
    raise SystemExit(main())
