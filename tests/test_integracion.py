"""Integracion extremo a extremo contra el dataset real de la prueba.

Estos tests fijan el comportamiento observado sobre `dataset/inbox`. Si el
dataset no esta presente se omiten, de modo que la suite sigue siendo ejecutable
de forma aislada.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from expedientes.cli import CODIGO_ERROR, CODIGO_INCIDENCIAS, CODIGO_OK, main
from expedientes.modelo import Motivo

from .conftest import cuerpo, huella_arbol

DATASET = Path(__file__).resolve().parent.parent / "dataset" / "inbox"

pytestmark = pytest.mark.skipif(
    not DATASET.is_dir(), reason="dataset/inbox no disponible"
)


@pytest.fixture(scope="module")
def salida(tmp_path_factory) -> Path:
    destino = tmp_path_factory.mktemp("salida")
    assert main(["--inbox", str(DATASET), "--salida", str(destino), "-q"]) == CODIGO_OK
    return destino


@pytest.fixture(scope="module")
def informe(salida: Path) -> dict:
    return json.loads((salida / "informes" / "informe.json").read_text(encoding="utf-8"))


class TestCifras:
    def test_resumen_global(self, informe):
        resumen = informe["resumen"]
        assert resumen["ficheros_leidos"] == 96
        assert resumen["expedientes"] == 20
        assert resumen["clientes"] == 8
        assert resumen["expedientes_completos"] == 18
        assert resumen["expedientes_incompletos"] == 2

    def test_ningun_fichero_se_pierde(self, informe):
        resumen = informe["resumen"]
        assert (
            resumen["documentos_archivados"] + resumen["ficheros_descartados"]
            == resumen["ficheros_leidos"]
        )

    def test_incidencias_por_motivo(self, informe):
        assert informe["incidencias_por_motivo"] == {
            Motivo.ARTEFACTO_SISTEMA.value: 2,
            Motivo.CONFLICTO_CLIENTE.value: 1,
            Motivo.DUPLICADO_EXACTO.value: 3,
            Motivo.FICHERO_VACIO.value: 1,
            Motivo.MRN_INVALIDO.value: 3,
            Motivo.SIN_ESTRUCTURA.value: 1,
            Motivo.VERSION_SUPERADA.value: 2,
        }


class TestCasosConcretosDelDataset:
    def _expediente(self, informe, mrn):
        return next(e for e in informe["expedientes"] if e["mrn"] == mrn)

    def test_los_tres_nif_ambiguos_se_unifican(self, informe):
        """20989659W, 55464039R y 75502037D no generan clientes fantasma."""
        nifs = {e["nif"] for e in informe["expedientes"]}
        assert {"20989659W", "55464039R", "75502037D"}.isdisjoint(nifs)
        assert {"20989659C", "55464039E", "75502037Y"} <= nifs

    def test_expedientes_incompletos_esperados(self, informe):
        incompletos = {
            e["mrn"]: e["documentos_ausentes"]["obligatorios"]
            for e in informe["expedientes"]
            if e["estado"] == "INCOMPLETO"
        }
        assert incompletos == {
            "26ESZ73E9EAR21SU35": ["FACTURA"],
            "26ESTZK6P9UDW63M0N": ["DUA"],
        }

    def test_el_certorigen_cruzado_no_contamina_a_electro_import(self, informe):
        expediente = self._expediente(informe, "26ESDX26CENWCZ1R5N")
        assert expediente["nif"] == "50693756P"
        intruso = next(
            i
            for i in informe["incidencias"]
            if i["fichero"].startswith("CERTORIGEN_26ES13YWB77MXATXKP")
        )
        assert intruso["motivo"] == Motivo.CONFLICTO_CLIENTE.value

    def test_los_mrn_corruptos_llevan_candidato(self, informe):
        rotos = {
            i["mrn"]: i["sugerencia"]
            for i in informe["incidencias"]
            if i["motivo"] == Motivo.MRN_INVALIDO.value
        }
        assert rotos == {
            "26ESA70XSGJHX8HA9WZ": "26ESA70XSGJHX8HA9W",
            "26ESDX26CENWCZ1R5": "26ESDX26CENWCZ1R5N",
            "26ESHGDB-XVL72JJAP": "26ESHGDBTXVL72JJAP",
        }

    def test_las_rectificaciones_ganan(self, salida):
        factura = (
            salida
            / "archivo"
            / "46490500W_frutas-levante-sl"
            / "26ESSD385Y6CJ6F92R"
            / "FACTURA.txt"
        ).read_text(encoding="utf-8")
        assert "BULTOS: 59" in factura
        assert "RECTIFICACION" in factura

    def test_la_version_superada_sigue_disponible(self, salida):
        superadas = salida / "_descartes" / "version_superada"
        nombres = {p.name for p in superadas.iterdir() if p.suffix == ".txt"}
        assert nombres == {
            "DUA_26ES1XMXPFFDZN97KD_20260521_12898185S.txt",
            "FACTURA_26ESSD385Y6CJ6F92R_20260123_46490500W.txt",
        }

    def test_los_alias_de_tipo_se_archivan_con_nombre_canonico(self, salida):
        # CMR_... se archiva como TRANSPORTE.txt
        destino = (
            salida
            / "archivo"
            / "44582623K_congelados-atlantico-sa"
            / "26ESZ73E9EAR21SU35"
        )
        assert (destino / "TRANSPORTE.txt").exists()

    def test_cada_descarte_tiene_sidecar(self, salida):
        raiz = salida / "_descartes"
        for motivo in raiz.iterdir():
            if not motivo.is_dir():
                continue
            for fichero in motivo.iterdir():
                if fichero.name.endswith(".motivo.json"):
                    continue
                sidecar = fichero.with_suffix(fichero.suffix + ".motivo.json")
                assert sidecar.exists(), f"falta sidecar de {fichero}"


class TestCLI:
    def test_idempotencia_sobre_el_dataset(self, tmp_path):
        destino = tmp_path / "salida"
        argumentos = ["--inbox", str(DATASET), "--salida", str(destino), "-q"]
        main(argumentos)
        primera = [
            (nombre, digest)
            for nombre, digest in huella_arbol(destino)
            if "informe" not in nombre  # el informe lleva sello temporal
        ]
        main(argumentos)
        segunda = [
            (nombre, digest)
            for nombre, digest in huella_arbol(destino)
            if "informe" not in nombre
        ]
        assert primera == segunda

    def test_el_dataset_no_se_modifica(self, tmp_path):
        antes = huella_arbol(DATASET)
        main(["--inbox", str(DATASET), "--salida", str(tmp_path / "s"), "-q"])
        assert huella_arbol(DATASET) == antes

    def test_inbox_inexistente_devuelve_error(self, tmp_path, capsys):
        codigo = main(["--inbox", str(tmp_path / "no"), "--salida", str(tmp_path / "s")])
        assert codigo == CODIGO_ERROR
        assert "error:" in capsys.readouterr().err


class TestInformePorStdout:
    def test_vuelca_el_informe_markdown(self, tmp_path, capsys):
        main(
            [
                "--inbox",
                str(DATASET),
                "--salida",
                str(tmp_path / "s"),
                "-q",
                "--informe-stdout",
            ]
        )
        salida = capsys.readouterr()
        assert "# Informe de clasificacion documental" in salida.out
        assert "## Expedientes" in salida.out and "## Incidencias" in salida.out

    def test_stdout_solo_lleva_el_informe(self, tmp_path, capsys):
        """El resumen va por stderr para poder redirigir stdout a un fichero."""
        main(
            [
                "--inbox",
                str(DATASET),
                "--salida",
                str(tmp_path / "s"),
                "--informe-stdout",
            ]
        )
        capturado = capsys.readouterr()
        assert capturado.out.startswith("# Informe")
        assert "Leidos" in capturado.err
        assert "Leidos" not in capturado.out

    def test_sin_la_bandera_stdout_queda_vacio(self, tmp_path, capsys):
        main(["--inbox", str(DATASET), "--salida", str(tmp_path / "s"), "-q"])
        assert capsys.readouterr().out == ""


class TestIntegracionConCI:
    """El codigo de salida permite detener una tuberia ante un lote sucio."""

    def test_por_defecto_las_incidencias_no_hacen_fallar(self, tmp_path):
        argumentos = ["--inbox", str(DATASET), "--salida", str(tmp_path / "s"), "-q"]
        assert main(argumentos) == CODIGO_OK

    def test_con_la_bandera_un_lote_con_incidencias_devuelve_2(self, tmp_path):
        codigo = main(
            [
                "--inbox",
                str(DATASET),
                "--salida",
                str(tmp_path / "s"),
                "-q",
                "--fallar-si-incidencias",
            ]
        )
        assert codigo == CODIGO_INCIDENCIAS

    def test_un_lote_limpio_devuelve_0_aunque_se_pida_fallar(
        self, inbox, crear, tmp_path
    ):
        for tipo in ("DUA", "FACTURA", "PACKING"):
            crear(f"{tipo}.txt", cuerpo(tipo=tipo))
        codigo = main(
            [
                "--inbox",
                str(inbox),
                "--salida",
                str(tmp_path / "s"),
                "-q",
                "--fallar-si-incidencias",
            ]
        )
        assert codigo == CODIGO_OK

    def test_un_error_de_ejecucion_no_se_confunde_con_incidencias(self, tmp_path):
        """El inbox inexistente da 1, no 2, aunque se pida fallar."""
        codigo = main(
            [
                "--inbox",
                str(tmp_path / "no-existe"),
                "--salida",
                str(tmp_path / "s"),
                "-q",
                "--fallar-si-incidencias",
            ]
        )
        assert codigo == CODIGO_ERROR

