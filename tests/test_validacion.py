"""Validacion de identificadores: son las reglas que desambiguan sin heuristicas."""

from __future__ import annotations

import pytest

from expedientes.validacion import (
    distancia_edicion,
    mrn_valido,
    sugerir_mrn,
    validar_nif,
)


class TestMRN:
    @pytest.mark.parametrize(
        "mrn",
        [
            "26ESWVVCU6XUX2LFAK",
            "26ESA70XSGJHX8HA9W",
            "27FR0123456789ABCD",  # otro anyo y otro pais: el formato es el general
        ],
    )
    def test_acepta_formato_valido(self, mrn):
        assert mrn_valido(mrn)

    @pytest.mark.parametrize(
        ("mrn", "porque"),
        [
            ("26ESA70XSGJHX8HA9WZ", "un caracter de mas"),
            ("26ESDX26CENWCZ1R5", "truncado"),
            ("26ESHGDB-XVL72JJAP", "caracter no alfanumerico"),
            ("ESES0123456789ABCD", "anyo no numerico"),
            ("2612WVVCU6XUX2LFAK", "pais no alfabetico"),
            ("", "vacio"),
        ],
    )
    def test_rechaza_formato_invalido(self, mrn, porque):
        assert not mrn_valido(mrn), porque

    def test_no_acepta_minusculas(self):
        # El MRN se normaliza a mayusculas antes de validar; el validador es estricto.
        assert not mrn_valido("26eswvvcu6xux2lfak")


class TestNIF:
    @pytest.mark.parametrize(
        "nif", ["20989659C", "46490500W", "55464039E", "12898185S", "75502037Y"]
    )
    def test_letra_correcta(self, nif):
        resultado = validar_nif(nif)
        assert resultado.valido
        assert resultado.canonico == nif

    @pytest.mark.parametrize(
        ("erroneo", "esperado"),
        [
            ("20989659W", "20989659C"),
            ("55464039R", "55464039E"),
            ("75502037D", "75502037Y"),
        ],
    )
    def test_letra_incorrecta_se_normaliza(self, erroneo, esperado):
        """Los tres pares ambiguos del dataset: uno valido y uno no, sin empate."""
        resultado = validar_nif(erroneo)
        assert not resultado.valido
        assert resultado.canonico == esperado

    def test_nie(self):
        # X0000000 -> 00000000 % 23 = 0 -> 'T'
        assert validar_nif("X0000000T").valido
        assert validar_nif("X0000000A").canonico == "X0000000T"

    def test_cif_no_se_valida_ni_se_corrige(self):
        resultado = validar_nif("B12345678")
        assert not resultado.validable
        assert resultado.valido  # se acepta tal cual
        assert resultado.canonico == "B12345678"

    def test_normaliza_espacios_y_guiones(self):
        assert validar_nif(" 20989659-c ").canonico == "20989659C"

    def test_vacio(self):
        assert validar_nif(None).canonico == ""


class TestSugerencias:
    def test_distancia_acotada(self):
        assert distancia_edicion("abc", "abc") == 0
        assert distancia_edicion("abc", "abd") == 1
        assert distancia_edicion("abc", "xyz", maximo=1) == 2  # corta al superar

    def test_sugiere_unico_candidato(self):
        validos = {"26ESDX26CENWCZ1R5N", "26ESAAAAAAAAAAAAAA"}
        assert sugerir_mrn("26ESDX26CENWCZ1R5", validos) == "26ESDX26CENWCZ1R5N"

    def test_no_sugiere_si_hay_ambiguedad(self):
        """Con dos candidatos igual de cercanos no se propone ninguno."""
        validos = {"26ESAAAAAAAAAAAAAA", "26ESAAAAAAAAAAAAAB"}
        assert sugerir_mrn("26ESAAAAAAAAAAAAAX", validos) is None

    def test_no_sugiere_si_nada_esta_cerca(self):
        assert sugerir_mrn("26ESZZZZZZZZZZZZZZ", {"26ESAAAAAAAAAAAAAA"}) is None
