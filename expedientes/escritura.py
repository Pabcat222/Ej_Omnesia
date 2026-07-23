"""Materializacion del resultado en el sistema de ficheros.

Idempotencia: el arbol de salida se reconstruye entero en cada ejecucion. Misma
entrada produce el mismo arbol byte a byte, sin restos de ejecuciones previas ni
acumulacion de basura. La alternativa (sincronizar incrementalmente) exigiria
detectar borrados y no aporta nada aqui.

Seguridad: para no borrar un directorio ajeno por un error de argumento, solo se
reconstruye un destino inexistente, vacio, o previamente creado por esta
herramienta (marcado con un fichero centinela).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .modelo import Descarte, Expediente, Resultado
from .normalizacion import slug

CENTINELA = ".omnesia-salida"

DIR_ARCHIVO = "archivo"
DIR_DESCARTES = "_descartes"
DIR_INFORMES = "informes"


class DestinoNoSeguroError(RuntimeError):
    """El destino no puede reconstruirse sin riesgo de destruir datos ajenos."""


def comprobar_rutas(inbox: Path, salida: Path) -> None:
    """Rechaza cualquier solapamiento entre la entrada y el destino.

    El destino se borra entero en cada ejecucion (ver `preparar_destino`), asi
    que si el inbox cuelga de el la herramienta destruiria su propia entrada. Y
    al reves: escribir dentro del inbox lo modificaria, cuando el enunciado lo
    define como de solo lectura. Se comprueba antes de leer nada, para fallar
    sin haber tocado el disco.
    """
    origen = inbox.resolve()
    destino = salida.resolve()

    if origen == destino:
        raise DestinoNoSeguroError(
            f"El inbox y el destino son el mismo directorio ({origen}); "
            "reconstruir el destino borraria la entrada."
        )
    if origen.is_relative_to(destino):
        raise DestinoNoSeguroError(
            f"El inbox {origen} esta dentro del destino {destino}: al reconstruir "
            "el destino se borraria la entrada."
        )
    if destino.is_relative_to(origen):
        raise DestinoNoSeguroError(
            f"El destino {destino} esta dentro del inbox {origen}: escribir ahi "
            "modificaria el inbox, que es de solo lectura."
        )


def _comprobar_origenes_fuera_del_destino(salida: Path, resultado: Resultado) -> None:
    """Ultima red de seguridad, valida para cualquier llamante de la libreria.

    `comprobar_rutas` cubre el caso normal, pero un uso programatico podria
    construir un Resultado con documentos de varios directorios. Antes de borrar
    nada se verifica que ningun fichero de origen viva bajo el destino.
    """
    destino = salida.resolve()
    origenes = [d.origen for e in resultado.expedientes for d in e.documentos.values()]
    origenes += [d.origen for d in resultado.descartes]
    for ruta in origenes:
        if ruta.resolve().is_relative_to(destino):
            raise DestinoNoSeguroError(
                f"El fichero de origen {ruta} esta dentro del destino {destino}: "
                "reconstruir el destino lo destruiria."
            )


def preparar_destino(salida: Path, forzar: bool = False) -> None:
    if salida.exists():
        if not salida.is_dir():
            raise DestinoNoSeguroError(f"{salida} existe y no es un directorio.")
        contenido = list(salida.iterdir())
        es_nuestro = (salida / CENTINELA).exists()
        if contenido and not es_nuestro and not forzar:
            raise DestinoNoSeguroError(
                f"{salida} no esta vacio y no fue generado por esta herramienta "
                f"(falta {CENTINELA}). Use otro destino o --forzar."
            )
        shutil.rmtree(salida)

    salida.mkdir(parents=True)
    (salida / CENTINELA).write_text(
        "Directorio generado automaticamente. Se borra y reescribe en cada "
        "ejecucion del clasificador.\n",
        encoding="utf-8",
    )


def _volcar_json(ruta: Path, dato: object) -> None:
    ruta.write_text(
        json.dumps(dato, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def carpeta_cliente(expediente: Expediente) -> str:
    """Nombre de la carpeta de cliente: NIF canonico + razon social legible.

    El NIF es la clave estable y unica; el slug solo aporta legibilidad al
    navegar el arbol.
    """
    return f"{expediente.nif}_{slug(expediente.cliente)}"


def escribir_archivo(salida: Path, expedientes: list[Expediente]) -> None:
    raiz = salida / DIR_ARCHIVO
    for expediente in expedientes:
        destino = raiz / carpeta_cliente(expediente) / expediente.mrn
        destino.mkdir(parents=True, exist_ok=True)
        for tipo in expediente.tipos_presentes:
            documento = expediente.documentos[tipo]
            # Nombre canonico por tipo: el expediente admite un documento de
            # cada tipo, asi que el tipo basta como identificador dentro de el.
            shutil.copy2(documento.origen, destino / f"{tipo.value}.txt")


def escribir_descartes(salida: Path, descartes: list[Descarte]) -> None:
    """Copia cada descarte a su carpeta de motivo con un sidecar que lo explica."""
    raiz = salida / DIR_DESCARTES
    raiz.mkdir(parents=True, exist_ok=True)

    for descarte in descartes:
        destino = raiz / descarte.motivo.value
        destino.mkdir(parents=True, exist_ok=True)

        copia = destino / descarte.origen.name
        # Dos ficheros distintos del inbox no pueden compartir nombre, pero un
        # mismo nombre podria repetirse entre motivos; el sufijo lo evita.
        sufijo = 1
        while copia.exists():
            sufijo += 1
            copia = destino / f"{descarte.origen.stem}~{sufijo}{descarte.origen.suffix}"
        shutil.copy2(descarte.origen, copia)

        _volcar_json(copia.with_suffix(copia.suffix + ".motivo.json"), descarte.a_dict())


def escribir_salida(salida: Path, resultado: Resultado, forzar: bool = False) -> None:
    _comprobar_origenes_fuera_del_destino(salida, resultado)
    preparar_destino(salida, forzar=forzar)
    escribir_archivo(salida, resultado.expedientes)
    escribir_descartes(salida, resultado.descartes)
    (salida / DIR_INFORMES).mkdir(parents=True, exist_ok=True)
