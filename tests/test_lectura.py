"""Lectura del inbox: que es procesable, que no, y que avisos se emiten."""

from __future__ import annotations

from expedientes.lectura import analizar_nombre, leer_fichero, leer_inbox, parsear_campos
from expedientes.modelo import Motivo, TipoDocumento

from .conftest import MRN_A, NIF_A, NIF_A_MALA, cuerpo


def codigos(documento) -> set[str]:
    return {a.codigo for a in documento.avisos}


class TestParseo:
    def test_campos_basicos(self):
        campos = parsear_campos(cuerpo())
        assert campos["TIPO"] == "DUA"
        assert campos["MRN"] == MRN_A
        assert campos["PESO-KG"] == "1000"

    def test_ignora_decoracion_y_lineas_sueltas(self):
        campos = parsear_campos("=== CABECERA ===\nlinea suelta\nTIPO: DUA\n")
        assert campos == {"TIPO": "DUA"}

    def test_claves_a_mayusculas_y_primera_aparicion_gana(self):
        campos = parsear_campos("tipo: DUA\nTIPO: FACTURA\n")
        assert campos == {"TIPO": "DUA"}

    def test_valor_con_dos_puntos(self):
        assert parsear_campos("NOTA: ver: aqui")["NOTA"] == "ver: aqui"


class TestAnalizarNombre:
    def test_nombre_canonico(self, tmp_path):
        pistas = analizar_nombre(tmp_path / f"FACTURA_{MRN_A}_20260315_{NIF_A}.txt")
        assert pistas.tipo is TipoDocumento.FACTURA
        assert pistas.mrn == MRN_A
        assert not pistas.es_copia

    def test_detecta_sufijos_de_copia(self, tmp_path):
        for nombre in ("doc_copia", "doc (1)", "doc_copy"):
            assert analizar_nombre(tmp_path / f"{nombre}.txt").es_copia

    def test_nombre_no_canonico_no_rompe(self, tmp_path):
        pistas = analizar_nombre(tmp_path / "notas_reunion.txt")
        assert pistas.tipo is None and pistas.mrn is None

    def test_tipo_con_espacios(self, tmp_path):
        pistas = analizar_nombre(tmp_path / f"CERTIFICADO ORIGEN_{MRN_A}_20260315_{NIF_A}.txt")
        assert pistas.tipo is TipoDocumento.CERTORIGEN


class TestDescartes:
    def test_fichero_vacio(self, crear):
        _, descarte = leer_fichero(crear("vacio.txt", ""))
        assert descarte.motivo is Motivo.FICHERO_VACIO

    def test_solo_espacios_tambien_es_vacio(self, crear):
        _, descarte = leer_fichero(crear("blanco.txt", "\n\n   \n"))
        assert descarte.motivo is Motivo.FICHERO_VACIO

    def test_no_decodificable(self, crear):
        _, descarte = leer_fichero(crear("raro.txt", b"\xff\xfe\x00binario"))
        assert descarte.motivo is Motivo.NO_DECODIFICABLE

    def test_artefactos_del_sistema(self, crear):
        for nombre in (".DS_Store", "~$factura.tmp", "Thumbs.db"):
            _, descarte = leer_fichero(crear(nombre, "lo que sea"))
            assert descarte.motivo is Motivo.ARTEFACTO_SISTEMA, nombre

    def test_texto_libre_sin_estructura(self, crear):
        ruta = crear("notas_reunion.txt", "llamar al transitario\npedir el certificado\n")
        _, descarte = leer_fichero(ruta)
        assert descarte.motivo is Motivo.SIN_ESTRUCTURA

    def test_falta_mrn(self, crear):
        _, descarte = leer_fichero(crear("x.txt", "TIPO: DUA\nCLIENTE: X\n"))
        assert descarte.motivo is Motivo.SIN_ESTRUCTURA

    def test_falta_nif_no_se_puede_archivar_por_cliente(self, crear):
        contenido = cuerpo().replace(f"NIF-CLIENTE: {NIF_A}\n", "")
        _, descarte = leer_fichero(crear("x.txt", contenido))
        assert descarte.motivo is Motivo.SIN_ESTRUCTURA
        assert "NIF-CLIENTE" in descarte.problema

    def test_nif_presente_pero_vacio(self, crear):
        contenido = cuerpo().replace(f"NIF-CLIENTE: {NIF_A}", "NIF-CLIENTE:")
        _, descarte = leer_fichero(crear("x.txt", contenido))
        assert descarte.motivo is Motivo.SIN_ESTRUCTURA

    def test_el_descarte_nombra_solo_los_campos_que_faltan(self, crear):
        _, descarte = leer_fichero(crear("x.txt", "TIPO: DUA\n"))
        assert "MRN" in descarte.problema and "NIF-CLIENTE" in descarte.problema
        assert "TIPO," not in descarte.problema

    def test_tipo_desconocido(self, crear):
        _, descarte = leer_fichero(crear("x.txt", cuerpo(tipo="SEGURO")))
        assert descarte.motivo is Motivo.TIPO_DESCONOCIDO

    def test_mrn_invalido_no_se_corrige(self, crear):
        ruta = crear("x.txt", cuerpo(mrn="26ESAAAAAAAAAAAAA"))
        documento, descarte = leer_fichero(ruta)
        assert documento is None
        assert descarte.motivo is Motivo.MRN_INVALIDO
        assert descarte.tipo is TipoDocumento.DUA  # se conserva lo que si se sabe


class TestCodificacion:
    def test_bom_utf8_no_impide_leer_el_documento(self, crear):
        """Las herramientas de Windows anteponen BOM; no debe romper el parseo."""
        documento, descarte = leer_fichero(
            crear("bom.txt", "﻿".encode() + cuerpo().encode())
        )
        assert documento is not None, descarte and descarte.problema
        assert documento.mrn == MRN_A

    def test_bom_con_el_primer_campo_en_la_primera_linea(self, crear):
        """Sin utf-8-sig la clave se leeria como '﻿TIPO' y se rechazaria."""
        crudo = f"TIPO: DUA\nMRN: {MRN_A}\nNIF-CLIENTE: {NIF_A}\nCLIENTE: X\n"
        documento, _ = leer_fichero(crear("bom2.txt", "﻿".encode() + crudo.encode()))
        assert documento is not None and documento.tipo is TipoDocumento.DUA

    def test_saltos_de_linea_windows(self, crear):
        crudo = cuerpo().replace("\n", "\r\n")
        documento, _ = leer_fichero(crear("crlf.txt", crudo))
        assert documento is not None and documento.mrn == MRN_A


class TestPrecedenciaDelContenido:
    def test_el_contenido_manda_sobre_el_nombre(self, crear):
        """Nombre dice FACTURA y MRN_B; el contenido dice DUA y MRN_A."""
        from .conftest import MRN_B

        ruta = crear(f"FACTURA_{MRN_B}_20260101_{NIF_A}.txt", cuerpo(tipo="DUA", mrn=MRN_A))
        documento, _ = leer_fichero(ruta)
        assert documento.tipo is TipoDocumento.DUA
        assert documento.mrn == MRN_A
        assert {"TIPO_DIVERGENTE", "MRN_DIVERGENTE"} <= codigos(documento)

    def test_alias_en_el_nombre_genera_aviso_informativo(self, crear):
        ruta = crear(f"FRA_{MRN_A}_20260315_{NIF_A}.txt", cuerpo(tipo="FACTURA"))
        documento, _ = leer_fichero(ruta)
        assert documento.tipo is TipoDocumento.FACTURA
        assert "ALIAS_TIPO" in codigos(documento)

    def test_fecha_divergente(self, crear):
        ruta = crear(f"DUA_{MRN_A}_20260101_{NIF_A}.txt", cuerpo(fecha="2026-03-15"))
        documento, _ = leer_fichero(ruta)
        assert documento.fecha.isoformat() == "2026-03-15"
        assert "FECHA_DIVERGENTE" in codigos(documento)

    def test_nombre_sin_pistas_no_genera_avisos(self, crear):
        documento, _ = leer_fichero(crear("cualquiercosa.txt", cuerpo()))
        assert documento.avisos == []


class TestAvisos:
    def test_nif_con_letra_mala_se_normaliza(self, crear):
        documento, _ = leer_fichero(crear("x.txt", cuerpo(nif=NIF_A_MALA)))
        assert documento.nif == NIF_A
        assert "NIF_CORREGIDO" in codigos(documento)

    def test_fecha_inexistente_no_bloquea(self, crear):
        documento, _ = leer_fichero(crear("x.txt", cuerpo(fecha="2026-02-30")))
        assert documento is not None and documento.fecha is None
        assert "FECHA_INVALIDA" in codigos(documento)

    def test_rectificacion_detectada(self, crear):
        documento, _ = leer_fichero(
            crear("x.txt", cuerpo(nota="RECTIFICACION: bultos corregidos"))
        )
        assert documento.es_rectificacion

    def test_cliente_ausente(self, crear):
        documento, _ = leer_fichero(crear("x.txt", cuerpo(cliente="")))
        assert documento.cliente == "DESCONOCIDO"


class TestLeerInbox:
    def test_orden_determinista_y_separacion(self, inbox, crear):
        crear(f"DUA_{MRN_A}_20260315_{NIF_A}.txt")
        crear("vacio.txt", "")
        crear("notas.txt", "texto libre")
        documentos, descartes = leer_inbox(inbox)
        assert len(documentos) == 1 and len(descartes) == 2
        assert [d.origen.name for d in descartes] == sorted(
            d.origen.name for d in descartes
        )

    def test_inbox_inexistente(self, tmp_path):
        import pytest

        with pytest.raises(NotADirectoryError):
            leer_inbox(tmp_path / "no-existe")

    def test_ignora_subdirectorios(self, inbox, crear):
        (inbox / "sub").mkdir()
        crear(f"DUA_{MRN_A}_20260315_{NIF_A}.txt")
        documentos, descartes = leer_inbox(inbox)
        assert len(documentos) == 1 and descartes == []
