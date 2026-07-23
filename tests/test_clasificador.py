"""Agrupacion en expedientes y resolucion de conflictos."""

from __future__ import annotations

from expedientes.clasificador import clasificar
from expedientes.lectura import leer_inbox
from expedientes.modelo import EstadoExpediente, Motivo, TipoDocumento

from .conftest import MRN_A, MRN_B, NIF_A, NIF_A_MALA, NIF_B, cuerpo


def procesar(inbox):
    documentos, descartes = leer_inbox(inbox)
    return clasificar(documentos, descartes)


def descartes_por_motivo(resultado, motivo):
    return [d for d in resultado.descartes if d.motivo is motivo]


class TestCompletitud:
    def test_expediente_completo_con_los_tres_obligatorios(self, inbox, crear):
        for tipo in ("DUA", "FACTURA", "PACKING"):
            crear(f"{tipo}.txt", cuerpo(tipo=tipo))
        expediente = procesar(inbox).expedientes[0]
        assert expediente.estado is EstadoExpediente.COMPLETO
        assert expediente.obligatorios_ausentes == []

    def test_los_opcionales_no_alteran_el_estado(self, inbox, crear):
        for tipo in ("DUA", "FACTURA", "PACKING"):
            crear(f"{tipo}.txt", cuerpo(tipo=tipo))
        expediente = procesar(inbox).expedientes[0]
        assert expediente.estado is EstadoExpediente.COMPLETO
        assert set(expediente.opcionales_ausentes) == {
            TipoDocumento.TRANSPORTE,
            TipoDocumento.CERTORIGEN,
        }

    def test_incompleto_lista_lo_que_falta(self, inbox, crear):
        crear("DUA.txt", cuerpo(tipo="DUA"))
        crear("CMR.txt", cuerpo(tipo="TRANSPORTE"))
        expediente = procesar(inbox).expedientes[0]
        assert expediente.estado is EstadoExpediente.INCOMPLETO
        assert expediente.obligatorios_ausentes == [
            TipoDocumento.FACTURA,
            TipoDocumento.PACKING,
        ]

    def test_expedientes_ordenados_por_mrn(self, inbox, crear):
        crear("b.txt", cuerpo(mrn=MRN_B))
        crear("a.txt", cuerpo(mrn=MRN_A))
        assert [e.mrn for e in procesar(inbox).expedientes] == [MRN_A, MRN_B]


class TestDuplicados:
    def test_copia_identica_se_descarta_conservando_una(self, inbox, crear):
        crear("PACKING.txt", cuerpo(tipo="PACKING"))
        crear("PACKING_copia.txt", cuerpo(tipo="PACKING"))
        resultado = procesar(inbox)
        assert len(resultado.expedientes[0].documentos) == 1
        duplicados = descartes_por_motivo(resultado, Motivo.DUPLICADO_EXACTO)
        assert len(duplicados) == 1
        assert "identico" in duplicados[0].problema

    def test_eleccion_estable_entre_copias_identicas(self, inbox, crear):
        crear("PACKING_copia.txt", cuerpo(tipo="PACKING"))
        crear("PACKING.txt", cuerpo(tipo="PACKING"))
        elegido = procesar(inbox).expedientes[0].documentos[TipoDocumento.PACKING]
        assert elegido.origen.name == "PACKING.txt"


class TestRectificaciones:
    def test_la_rectificacion_prevalece(self, inbox, crear):
        crear("FACTURA.txt", cuerpo(tipo="FACTURA", bultos=58))
        crear(
            "FACTURA (1).txt",
            cuerpo(tipo="FACTURA", bultos=59, nota="RECTIFICACION: bultos corregidos"),
        )
        resultado = procesar(inbox)
        elegido = resultado.expedientes[0].documentos[TipoDocumento.FACTURA]
        assert elegido.campos["BULTOS"] == "59"
        assert {a.codigo for a in elegido.avisos} >= {"RECTIFICACION_APLICADA"}

    def test_la_version_superada_se_conserva_como_historico(self, inbox, crear):
        crear("FACTURA.txt", cuerpo(tipo="FACTURA", bultos=58))
        crear("FACTURA (1).txt", cuerpo(tipo="FACTURA", bultos=59, nota="RECTIFICACION"))
        superadas = descartes_por_motivo(procesar(inbox), Motivo.VERSION_SUPERADA)
        assert [d.origen.name for d in superadas] == ["FACTURA.txt"]

    def test_versiones_en_conflicto_sin_arbitro_no_se_eligen(self, inbox, crear):
        """Dos DUA distintos sin marca de rectificacion: mejor hueco que azar."""
        crear("DUA_a.txt", cuerpo(bultos=1))
        crear("DUA_b.txt", cuerpo(bultos=2))
        resultado = procesar(inbox)
        expediente = resultado.expedientes[0]
        assert TipoDocumento.DUA not in expediente.documentos
        assert expediente.estado is EstadoExpediente.INCOMPLETO
        assert len(descartes_por_motivo(resultado, Motivo.CONFLICTO_VERSION)) == 2

    def test_dos_rectificaciones_simultaneas_son_conflicto(self, inbox, crear):
        crear("DUA_a.txt", cuerpo(bultos=1, nota="RECTIFICACION"))
        crear("DUA_b.txt", cuerpo(bultos=2, nota="RECTIFICACION"))
        resultado = procesar(inbox)
        assert TipoDocumento.DUA not in resultado.expedientes[0].documentos
        assert len(descartes_por_motivo(resultado, Motivo.CONFLICTO_VERSION)) == 2


class TestTitularDelExpediente:
    def test_el_dua_fija_el_titular(self, inbox, crear):
        crear("DUA.txt", cuerpo(tipo="DUA", nif=NIF_A, cliente="Maderas Soria SL"))
        crear("FACTURA.txt", cuerpo(tipo="FACTURA", nif=NIF_A, cliente="Maderas Soria SL"))
        crear("CERT.txt", cuerpo(tipo="CERTORIGEN", nif=NIF_B, cliente="Frutas Levante SL"))
        resultado = procesar(inbox)
        expediente = resultado.expedientes[0]
        assert expediente.nif == NIF_A
        assert TipoDocumento.CERTORIGEN not in expediente.documentos
        intrusos = descartes_por_motivo(resultado, Motivo.CONFLICTO_CLIENTE)
        assert [d.origen.name for d in intrusos] == ["CERT.txt"]
        assert "TITULAR_POR_DUA" in {a.codigo for a in expediente.avisos}

    def test_sin_dua_no_se_decide_aunque_haya_mayoria(self, inbox, crear):
        """No hay desempate por mayoria: sin DUA que arbitre, no se responde."""
        crear("FACTURA.txt", cuerpo(tipo="FACTURA", nif=NIF_A))
        crear("PACKING.txt", cuerpo(tipo="PACKING", nif=NIF_A))
        crear("CERT.txt", cuerpo(tipo="CERTORIGEN", nif=NIF_B, cliente="Frutas Levante SL"))
        resultado = procesar(inbox)
        assert resultado.expedientes == []
        assert len(descartes_por_motivo(resultado, Motivo.CONFLICTO_CLIENTE)) == 3

    def test_empate_sin_dua_manda_todo_a_cuarentena(self, inbox, crear):
        crear("FACTURA.txt", cuerpo(tipo="FACTURA", nif=NIF_A))
        crear("CERT.txt", cuerpo(tipo="CERTORIGEN", nif=NIF_B, cliente="Frutas Levante SL"))
        resultado = procesar(inbox)
        assert resultado.expedientes == []
        assert len(descartes_por_motivo(resultado, Motivo.CONFLICTO_CLIENTE)) == 2

    def test_dos_dua_discrepantes_no_arbitran(self, inbox, crear):
        crear("DUA_a.txt", cuerpo(tipo="DUA", nif=NIF_A))
        crear("DUA_b.txt", cuerpo(tipo="DUA", nif=NIF_B, cliente="Frutas Levante SL"))
        assert procesar(inbox).expedientes == []

    def test_nif_con_letra_mala_no_parte_el_expediente(self, inbox, crear):
        """El mismo cliente escrito con letra de control erronea no es otro cliente."""
        crear("DUA.txt", cuerpo(tipo="DUA", nif=NIF_A_MALA))
        crear("FACTURA.txt", cuerpo(tipo="FACTURA", nif=NIF_A))
        crear("PACKING.txt", cuerpo(tipo="PACKING", nif=NIF_A))
        resultado = procesar(inbox)
        assert len(resultado.expedientes) == 1
        assert resultado.expedientes[0].nif == NIF_A
        assert resultado.expedientes[0].estado is EstadoExpediente.COMPLETO
        assert descartes_por_motivo(resultado, Motivo.CONFLICTO_CLIENTE) == []


class TestRazonSocial:
    """Un NIF debe producir siempre una unica carpeta de cliente."""

    def _clientes(self, resultado):
        return {e.cliente for e in resultado.expedientes}

    def test_variantes_del_nombre_no_parten_al_cliente(self, inbox, crear):
        crear("a.txt", cuerpo(mrn=MRN_A, cliente="Maderas Soria SL"))
        crear("b1.txt", cuerpo(mrn=MRN_B, tipo="DUA", cliente="MADERAS SORIA, S.L."))
        crear("b2.txt", cuerpo(mrn=MRN_B, tipo="FACTURA", cliente="MADERAS SORIA, S.L."))
        resultado = procesar(inbox)
        assert len(self._clientes(resultado)) == 1

    def test_gana_el_nombre_con_mas_documentos(self, inbox, crear):
        crear("a.txt", cuerpo(mrn=MRN_A, cliente="Variante Rara SL"))
        crear("b1.txt", cuerpo(mrn=MRN_B, tipo="DUA", cliente="Maderas Soria SL"))
        crear("b2.txt", cuerpo(mrn=MRN_B, tipo="FACTURA", cliente="Maderas Soria SL"))
        resultado = procesar(inbox)
        assert self._clientes(resultado) == {"Maderas Soria SL"}

    def test_se_deja_constancia_del_cambio(self, inbox, crear):
        crear("a.txt", cuerpo(mrn=MRN_A, cliente="Variante Rara SL"))
        crear("b1.txt", cuerpo(mrn=MRN_B, tipo="DUA", cliente="Maderas Soria SL"))
        crear("b2.txt", cuerpo(mrn=MRN_B, tipo="FACTURA", cliente="Maderas Soria SL"))
        resultado = procesar(inbox)
        codigos = {a.codigo for e in resultado.expedientes for a in e.avisos}
        assert "RAZON_SOCIAL_UNIFICADA" in codigos

    def test_empate_se_resuelve_alfabeticamente(self, inbox, crear):
        crear("a.txt", cuerpo(mrn=MRN_A, cliente="Zeta SL"))
        crear("b.txt", cuerpo(mrn=MRN_B, cliente="Alfa SL"))
        assert self._clientes(procesar(inbox)) == {"Alfa SL"}

    def test_nifs_distintos_no_se_mezclan(self, inbox, crear):
        crear("a.txt", cuerpo(mrn=MRN_A, nif=NIF_A, cliente="Maderas Soria SL"))
        crear("b.txt", cuerpo(mrn=MRN_B, nif=NIF_B, cliente="Frutas Levante SL"))
        assert self._clientes(procesar(inbox)) == {
            "Maderas Soria SL",
            "Frutas Levante SL",
        }


class TestSugerenciaDeMRN:
    def test_se_sugiere_el_expediente_cercano_sin_fusionar(self, inbox, crear):
        for tipo in ("DUA", "FACTURA", "PACKING"):
            crear(f"{tipo}.txt", cuerpo(tipo=tipo, mrn=MRN_A))
        crear("CERT.txt", cuerpo(tipo="CERTORIGEN", mrn=MRN_A + "Z"))
        resultado = procesar(inbox)
        roto = descartes_por_motivo(resultado, Motivo.MRN_INVALIDO)[0]
        assert roto.sugerencia == MRN_A
        assert MRN_A in roto.decision
        # sigue descartado: no se ha incorporado al expediente
        assert TipoDocumento.CERTORIGEN not in resultado.expedientes[0].documentos


class TestRecuento:
    def test_todo_fichero_acaba_clasificado_o_descartado(self, inbox, crear):
        crear("DUA.txt", cuerpo(tipo="DUA"))
        crear("FACTURA.txt", cuerpo(tipo="FACTURA"))
        crear("FACTURA_copia.txt", cuerpo(tipo="FACTURA"))
        crear("vacio.txt", "")
        crear("roto.txt", cuerpo(mrn="XX"))
        resultado = procesar(inbox)
        archivados = sum(len(e.documentos) for e in resultado.expedientes)
        assert archivados + len(resultado.descartes) == 5
