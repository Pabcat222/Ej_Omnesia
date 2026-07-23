"""Contenido y determinismo del informe."""

from __future__ import annotations

import json

from expedientes.clasificador import clasificar
from expedientes.informe import construir_json, construir_markdown, escribir_informes
from expedientes.lectura import leer_inbox

from .conftest import MRN_A, NIF_A, cuerpo

SELLO = "2026-07-21T00:00:00+00:00"


def resultado_de(inbox):
    documentos, descartes = leer_inbox(inbox)
    return clasificar(documentos, descartes)


class TestJSON:
    def test_resumen(self, inbox, crear):
        for tipo in ("DUA", "FACTURA", "PACKING"):
            crear(f"{tipo}.txt", cuerpo(tipo=tipo))
        crear("vacio.txt", "")
        datos = construir_json(resultado_de(inbox), SELLO)
        assert datos["resumen"] == {
            "ficheros_leidos": 4,
            "expedientes": 1,
            "expedientes_completos": 1,
            "expedientes_incompletos": 0,
            "documentos_archivados": 3,
            "ficheros_descartados": 1,
            "avisos": 0,
            "clientes": 1,
        }

    def test_expediente_expone_ausentes_por_obligatoriedad(self, inbox, crear):
        crear("DUA.txt", cuerpo(tipo="DUA"))
        expediente = construir_json(resultado_de(inbox), SELLO)["expedientes"][0]
        assert expediente["estado"] == "INCOMPLETO"
        assert expediente["documentos_ausentes"]["obligatorios"] == ["FACTURA", "PACKING"]
        assert expediente["documentos_ausentes"]["opcionales"] == [
            "TRANSPORTE",
            "CERTORIGEN",
        ]

    def test_incidencia_lleva_fichero_problema_y_decision(self, inbox, crear):
        crear("vacio.txt", "")
        incidencia = construir_json(resultado_de(inbox), SELLO)["incidencias"][0]
        assert incidencia["fichero"] == "vacio.txt"
        assert incidencia["problema"] and incidencia["decision"]

    def test_es_serializable(self, inbox, crear):
        crear("DUA.txt", cuerpo())
        json.dumps(construir_json(resultado_de(inbox), SELLO))


class TestMarkdown:
    def test_incluye_expedientes_e_incidencias(self, inbox, crear):
        crear(f"DUA_{MRN_A}_20260315_{NIF_A}.txt", cuerpo(tipo="DUA"))
        crear("vacio.txt", "")
        texto = construir_markdown(resultado_de(inbox), SELLO)
        assert MRN_A in texto
        assert "INCOMPLETO" in texto
        assert "vacio.txt" in texto
        assert "## Incidencias" in texto

    def test_secciones_vacias_no_rompen(self, inbox, crear):
        crear("DUA.txt", cuerpo())
        texto = construir_markdown(resultado_de(inbox), SELLO)
        assert "_Sin incidencias._" in texto
        assert "_Sin avisos._" in texto

    def test_los_avisos_se_listan(self, inbox, crear):
        crear("DUA.txt", cuerpo(fecha="2026-02-30"))
        assert "FECHA_INVALIDA" in construir_markdown(resultado_de(inbox), SELLO)


class TestDeterminismo:
    def test_mismo_sello_mismo_informe(self, inbox, crear):
        for tipo in ("DUA", "FACTURA", "PACKING"):
            crear(f"{tipo}.txt", cuerpo(tipo=tipo))
        primera = construir_markdown(resultado_de(inbox), SELLO)
        segunda = construir_markdown(resultado_de(inbox), SELLO)
        assert primera == segunda

    def test_se_escriben_ambos_formatos(self, inbox, tmp_path, crear):
        crear("DUA.txt", cuerpo())
        ruta_md, ruta_json = escribir_informes(tmp_path, resultado_de(inbox), SELLO)
        assert ruta_md.exists() and ruta_json.exists()
        assert json.loads(ruta_json.read_text(encoding="utf-8"))["generado_en"] == SELLO
