"""Modelo de dominio: tipos documentales, incidencias y expedientes.

Todo el vocabulario del problema vive aqui. El resto de modulos importa de este
para que no existan cadenas magicas repartidas por el codigo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path


class TipoDocumento(str, Enum):
    """Tipos documentales que componen un expediente aduanero."""

    DUA = "DUA"
    FACTURA = "FACTURA"
    PACKING = "PACKING"
    TRANSPORTE = "TRANSPORTE"
    CERTORIGEN = "CERTORIGEN"


#: Un expediente esta completo si contiene, al menos, estos tres tipos.
TIPOS_OBLIGATORIOS: tuple[TipoDocumento, ...] = (
    TipoDocumento.DUA,
    TipoDocumento.FACTURA,
    TipoDocumento.PACKING,
)

#: Deseables pero no exigibles: su ausencia no impide considerar completo.
TIPOS_OPCIONALES: tuple[TipoDocumento, ...] = (
    TipoDocumento.TRANSPORTE,
    TipoDocumento.CERTORIGEN,
)


class Motivo(str, Enum):
    """Motivo por el que un fichero no llega al archivo.

    El valor se usa tal cual como nombre de subdirectorio dentro de
    ``_descartes/``, de modo que la razon del descarte es legible sin abrir
    ningun informe.
    """

    ARTEFACTO_SISTEMA = "artefacto_sistema"
    FICHERO_VACIO = "fichero_vacio"
    NO_DECODIFICABLE = "no_decodificable"
    SIN_ESTRUCTURA = "sin_estructura"
    TIPO_DESCONOCIDO = "tipo_desconocido"
    MRN_INVALIDO = "mrn_invalido"
    DUPLICADO_EXACTO = "duplicado_exacto"
    VERSION_SUPERADA = "version_superada"
    CONFLICTO_VERSION = "conflicto_version"
    CONFLICTO_CLIENTE = "conflicto_cliente"


class Severidad(str, Enum):
    """Gravedad de un aviso que NO impide clasificar el documento."""

    INFO = "info"
    ADVERTENCIA = "advertencia"


class EstadoExpediente(str, Enum):
    COMPLETO = "COMPLETO"
    INCOMPLETO = "INCOMPLETO"


@dataclass(frozen=True)
class Aviso:
    """Anomalia detectada que se reporta pero no bloquea la clasificacion."""

    codigo: str
    detalle: str
    severidad: Severidad = Severidad.ADVERTENCIA

    def a_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "detalle": self.detalle,
            "severidad": self.severidad.value,
        }


@dataclass
class Documento:
    """Un fichero del inbox que ha superado el parseo y la validacion.

    Los campos provienen SIEMPRE del contenido (decision de diseno D1). Lo que
    dice el nombre del fichero se conserva solo para poder reportar divergencias.
    """

    origen: Path
    hash_sha256: str
    tipo: TipoDocumento
    mrn: str
    nif: str
    cliente: str
    fecha: date | None
    campos: dict[str, str]
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def es_rectificacion(self) -> bool:
        """Un documento marcado como rectificacion sustituye a su version previa."""
        nota = self.campos.get("NOTA", "")
        return "RECTIFICACION" in nota.upper()

    def a_dict(self) -> dict:
        return {
            "origen": self.origen.name,
            "tipo": self.tipo.value,
            "mrn": self.mrn,
            "nif": self.nif,
            "cliente": self.cliente,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "sha256": self.hash_sha256,
            "es_rectificacion": self.es_rectificacion,
            "avisos": [a.a_dict() for a in self.avisos],
        }


@dataclass
class Descarte:
    """Fichero que no entra en el archivo, con la razon y la decision adoptada."""

    origen: Path
    motivo: Motivo
    problema: str
    decision: str
    mrn: str | None = None
    tipo: TipoDocumento | None = None
    sugerencia: str | None = None

    def a_dict(self) -> dict:
        return {
            "fichero": self.origen.name,
            "motivo": self.motivo.value,
            "problema": self.problema,
            "decision": self.decision,
            "mrn": self.mrn,
            "tipo": self.tipo.value if self.tipo else None,
            "sugerencia": self.sugerencia,
        }


@dataclass
class Expediente:
    """Agrupacion de documentos bajo un mismo MRN."""

    mrn: str
    nif: str
    cliente: str
    documentos: dict[TipoDocumento, Documento] = field(default_factory=dict)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def tipos_presentes(self) -> list[TipoDocumento]:
        return sorted(self.documentos, key=lambda t: t.value)

    @property
    def obligatorios_ausentes(self) -> list[TipoDocumento]:
        return [t for t in TIPOS_OBLIGATORIOS if t not in self.documentos]

    @property
    def opcionales_ausentes(self) -> list[TipoDocumento]:
        return [t for t in TIPOS_OPCIONALES if t not in self.documentos]

    @property
    def estado(self) -> EstadoExpediente:
        return (
            EstadoExpediente.COMPLETO
            if not self.obligatorios_ausentes
            else EstadoExpediente.INCOMPLETO
        )

    def a_dict(self) -> dict:
        return {
            "mrn": self.mrn,
            "nif": self.nif,
            "cliente": self.cliente,
            "estado": self.estado.value,
            "documentos_encontrados": [t.value for t in self.tipos_presentes],
            "documentos_ausentes": {
                "obligatorios": [t.value for t in self.obligatorios_ausentes],
                "opcionales": [t.value for t in self.opcionales_ausentes],
            },
            "documentos": [
                self.documentos[t].a_dict() for t in self.tipos_presentes
            ],
            "avisos": [a.a_dict() for a in self.avisos],
        }


@dataclass
class Resultado:
    """Salida completa de una ejecucion: lo clasificado y lo descartado."""

    expedientes: list[Expediente] = field(default_factory=list)
    descartes: list[Descarte] = field(default_factory=list)
    ficheros_leidos: int = 0
