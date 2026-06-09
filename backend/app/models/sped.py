from sqlalchemy import Column, String, Enum as SAEnum, ForeignKey, Numeric, Date, JSON, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class StatusSped(str, enum.Enum):
    IMPORTADO = "importado"
    VALIDANDO = "validando"
    VALIDO = "valido"
    COM_ERROS = "com_erros"
    TRANSMITIDO = "transmitido"


class SpedEcd(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sped_ecd"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    ano_calendario = Column(Integer, nullable=False)
    data_inicial = Column(Date, nullable=False)
    data_final = Column(Date, nullable=False)
    status = Column(SAEnum(StatusSped), default=StatusSped.IMPORTADO, nullable=False)
    arquivo_path = Column(String(500), nullable=True)
    hash_arquivo = Column(String(64), nullable=True)
    versao_leiaute = Column(String(10), nullable=True)
    total_registros = Column(Integer, default=0)
    erros = Column(JSON, default=list)
    alertas = Column(JSON, default=list)
    blocos = Column(JSON, default=dict)
    divergencias_balancete = Column(JSON, default=list)


class SpedEcf(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sped_ecf"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    ano_calendario = Column(Integer, nullable=False)
    situacao_especial = Column(String(10), nullable=True)
    status = Column(SAEnum(StatusSped), default=StatusSped.IMPORTADO, nullable=False)
    arquivo_path = Column(String(500), nullable=True)
    hash_arquivo = Column(String(64), nullable=True)
    versao_leiaute = Column(String(10), nullable=True)
    total_registros = Column(Integer, default=0)
    erros = Column(JSON, default=list)
    alertas = Column(JSON, default=list)
    blocos = Column(JSON, default=dict)
    irpj_apurado = Column(Numeric(18, 2), nullable=True)
    csll_apurado = Column(Numeric(18, 2), nullable=True)
