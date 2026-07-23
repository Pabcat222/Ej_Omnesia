"""Materializacion en disco, idempotencia y proteccion del destino."""

from __future__ import annotations

import json

import pytest

from expedientes.clasificador import clasificar
from expedientes.escritura import (
    CENTINELA,
    DestinoNoSeguroError,
    comprobar_rutas,
    escribir_salida,
)
from expedientes.lectura import leer_inbox

from .conftest import MRN_A, NIF_A, cuerpo, huella_arbol


@pytest.fixture
def poblado(crear):
    for tipo in ("DUA", "FACTURA", "PACKING"):
        crear(f"{tipo}_{MRN_A}_20260315_{NIF_A}.txt", cuerpo(tipo=tipo))
    crear("PACKING_copia.txt", cuerpo(tipo="PACKING"))
    crear("vacio.txt", "")


def ejecutar(inbox, salida, **kwargs):
    documentos, descartes = leer_inbox(inbox)
    resultado = clasificar(documentos, descartes)
    escribir_salida(salida, resultado, **kwargs)
    return resultado


class TestLayout:
    def test_estructura_cliente_expediente(self, inbox, tmp_path, poblado):
        salida = tmp_path / "salida"
        ejecutar(inbox, salida)
        destino = salida / "archivo" / f"{NIF_A}_maderas-soria-sl" / MRN_A
        assert destino.is_dir()
        assert {p.name for p in destino.iterdir()} == {
            "DUA.txt",
            "FACTURA.txt",
            "PACKING.txt",
        }

    def test_el_documento_se_copia_intacto(self, inbox, tmp_path, poblado):
        salida = tmp_path / "salida"
        ejecutar(inbox, salida)
        copiado = salida / "archivo" / f"{NIF_A}_maderas-soria-sl" / MRN_A / "DUA.txt"
        assert copiado.read_text(encoding="utf-8") == cuerpo(tipo="DUA")

    def test_el_inbox_no_se_modifica(self, inbox, tmp_path, poblado):
        """Requisito explicito del enunciado: el inbox es de solo lectura."""
        antes = huella_arbol(inbox)
        ejecutar(inbox, tmp_path / "salida")
        assert huella_arbol(inbox) == antes


class TestDescartes:
    def test_cada_descarte_va_a_la_carpeta_de_su_motivo(self, inbox, tmp_path, poblado):
        salida = tmp_path / "salida"
        ejecutar(inbox, salida)
        assert (salida / "_descartes" / "fichero_vacio" / "vacio.txt").exists()
        assert (
            salida / "_descartes" / "duplicado_exacto" / "PACKING_copia.txt"
        ).exists()

    def test_sidecar_explica_el_motivo(self, inbox, tmp_path, poblado):
        salida = tmp_path / "salida"
        ejecutar(inbox, salida)
        sidecar = salida / "_descartes" / "fichero_vacio" / "vacio.txt.motivo.json"
        datos = json.loads(sidecar.read_text(encoding="utf-8"))
        assert datos["motivo"] == "fichero_vacio"
        assert datos["problema"] and datos["decision"]

    def test_nombres_colisionantes_no_se_pisan(self, inbox, tmp_path, crear):
        """Dos ficheros distintos podrian compartir nombre tras el sufijado."""
        crear("a.txt", cuerpo(bultos=1))
        crear("b.txt", cuerpo(bultos=2))  # conflicto de version: ambos descartados
        salida = tmp_path / "salida"
        ejecutar(inbox, salida)
        carpeta = salida / "_descartes" / "conflicto_version"
        assert len([p for p in carpeta.iterdir() if p.suffix == ".txt"]) == 2


class TestIdempotencia:
    def test_dos_ejecuciones_producen_el_mismo_arbol(self, inbox, tmp_path, poblado):
        salida = tmp_path / "salida"
        ejecutar(inbox, salida)
        primera = huella_arbol(salida)
        ejecutar(inbox, salida)
        assert huella_arbol(salida) == primera

    def test_no_quedan_restos_de_ejecuciones_previas(self, inbox, tmp_path, poblado):
        salida = tmp_path / "salida"
        ejecutar(inbox, salida)
        basura = salida / "archivo" / "cliente-fantasma"
        basura.mkdir(parents=True)
        (basura / "viejo.txt").write_text("resto", encoding="utf-8")
        ejecutar(inbox, salida)
        assert not basura.exists()


class TestProteccionDelDestino:
    def test_rechaza_directorio_ajeno_no_vacio(self, inbox, tmp_path, poblado):
        salida = tmp_path / "importante"
        salida.mkdir()
        (salida / "tesis.txt").write_text("no me borres", encoding="utf-8")
        with pytest.raises(DestinoNoSeguroError):
            ejecutar(inbox, salida)
        assert (salida / "tesis.txt").exists()

    def test_forzar_permite_sobrescribir(self, inbox, tmp_path, poblado):
        salida = tmp_path / "importante"
        salida.mkdir()
        (salida / "tesis.txt").write_text("adios", encoding="utf-8")
        ejecutar(inbox, salida, forzar=True)
        assert not (salida / "tesis.txt").exists()

    def test_acepta_directorio_vacio(self, inbox, tmp_path, poblado):
        salida = tmp_path / "vacia"
        salida.mkdir()
        ejecutar(inbox, salida)
        assert (salida / CENTINELA).exists()

    def test_reutiliza_su_propio_destino_sin_forzar(self, inbox, tmp_path, poblado):
        salida = tmp_path / "salida"
        ejecutar(inbox, salida)
        ejecutar(inbox, salida)  # el centinela lo identifica como propio

    def test_rechaza_destino_que_es_un_fichero(self, inbox, tmp_path, poblado):
        salida = tmp_path / "archivo.txt"
        salida.write_text("soy un fichero", encoding="utf-8")
        with pytest.raises(DestinoNoSeguroError):
            ejecutar(inbox, salida)


class TestSolapamientoEntreEntradaYDestino:
    """El destino se borra entero: jamas puede contener al inbox."""

    def test_rechaza_inbox_y_destino_iguales(self, inbox, tmp_path):
        with pytest.raises(DestinoNoSeguroError, match="mismo directorio"):
            comprobar_rutas(inbox, inbox)

    def test_rechaza_inbox_dentro_del_destino(self, inbox, tmp_path):
        with pytest.raises(DestinoNoSeguroError, match="dentro del destino"):
            comprobar_rutas(inbox, inbox.parent)

    def test_rechaza_destino_dentro_del_inbox(self, inbox, tmp_path):
        with pytest.raises(DestinoNoSeguroError, match="dentro del inbox"):
            comprobar_rutas(inbox, inbox / "salida")

    def test_acepta_rutas_hermanas(self, inbox, tmp_path):
        comprobar_rutas(inbox, tmp_path / "salida")

    def test_resuelve_rutas_relativas_y_enlaces(self, inbox, tmp_path):
        """'inbox/../inbox' es el mismo directorio aunque no lo parezca."""
        with pytest.raises(DestinoNoSeguroError):
            comprobar_rutas(inbox, inbox / ".." / inbox.name)

    def test_escribir_salida_protege_aunque_se_salte_el_cli(
        self, inbox, tmp_path, poblado
    ):
        """Red de seguridad para el uso programatico: no se borra nada."""
        with pytest.raises(DestinoNoSeguroError, match="fichero de origen"):
            ejecutar(inbox, inbox.parent, forzar=True)
        assert len(list(inbox.iterdir())) == 5  # el inbox sigue intacto
