"""Normalizacion de tipos, nombres de cliente y fechas."""

from __future__ import annotations

import datetime

import pytest

from expedientes.modelo import TipoDocumento
from expedientes.normalizacion import normalizar_tipo, parsear_fecha, slug


class TestTipos:
    @pytest.mark.parametrize(
        ("bruto", "esperado"),
        [
            ("DUA", TipoDocumento.DUA),
            ("FACTURA", TipoDocumento.FACTURA),
            ("FRA", TipoDocumento.FACTURA),
            ("fra", TipoDocumento.FACTURA),
            ("PACKING", TipoDocumento.PACKING),
            ("PACKINGLIST", TipoDocumento.PACKING),
            ("PLIST", TipoDocumento.PACKING),
            ("CMR", TipoDocumento.TRANSPORTE),
            ("B/L", TipoDocumento.TRANSPORTE),
            ("AWB", TipoDocumento.TRANSPORTE),
            ("CERTORIGEN", TipoDocumento.CERTORIGEN),
            ("CERTIFICADO ORIGEN", TipoDocumento.CERTORIGEN),
            ("Certificado_Origen", TipoDocumento.CERTORIGEN),
        ],
    )
    def test_alias_conocidos(self, bruto, esperado):
        assert normalizar_tipo(bruto) is esperado

    @pytest.mark.parametrize("bruto", ["", None, "SEGURO", "ALBARAN"])
    def test_desconocidos(self, bruto):
        assert normalizar_tipo(bruto) is None


class TestSlug:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("Maderas Soria SL", "maderas-soria-sl"),
            ("Congelados Atlantico, S.A.", "congelados-atlantico-s-a"),
            ("Quimicas Ebro  SL ", "quimicas-ebro-sl"),
            ("Aceites del Sur SL", "aceites-del-sur-sl"),
            ("Almacenes Peña & Hijos", "almacenes-pena-hijos"),
        ],
    )
    def test_slug(self, entrada, esperado):
        assert slug(entrada) == esperado

    def test_nombre_sin_caracteres_utiles(self):
        assert slug("///") == "sin-nombre"


class TestFechas:
    @pytest.mark.parametrize(
        ("bruto", "esperado"),
        [
            ("2026-04-09", datetime.date(2026, 4, 9)),
            ("20260409", datetime.date(2026, 4, 9)),
            ("09-04-2026", datetime.date(2026, 4, 9)),
            ("09/04/2026", datetime.date(2026, 4, 9)),
        ],
    )
    def test_formatos_admitidos(self, bruto, esperado):
        assert parsear_fecha(bruto) == esperado

    @pytest.mark.parametrize("bruto", ["2026-02-30", "20260230", "no es fecha", "", None])
    def test_fechas_no_reales(self, bruto):
        """Una fecha inexistente devuelve None para que el llamante avise."""
        assert parsear_fecha(bruto) is None
