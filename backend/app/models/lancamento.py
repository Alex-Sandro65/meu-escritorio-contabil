from sqlalchemy import Column, String, Enum as SAEnum, ForeignKey, Numeric, Date, Boolean, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class TipoLancamento(str, enum.Enum):
    DEBITO = "D"
    CREDITO = "C"


class OrigemLancamento(str, enum.Enum):
    BALANCETE = "balancete"
    RAZAO = "razao"
    EXTRATO = "extrato"
    NF = "nf"
    FOLHA = "folha"
    MANUAL = "manual"
    IMPORTACAO = "importacao"


class Lancamento(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "lancamentos"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    conta_id = Column(UUID(as_uuid=True), ForeignKey("contas_contabeis.id"), nullable=True)

    data_lancamento = Column(Date, nullable=False)
    data_competencia = Column(Date, nullable=True)
    tipo = Column(SAEnum(TipoLancamento), nullable=False)
    valor = Column(Numeric(18, 2), nullable=False)
    historico = Column(String(500), nullable=True)
    documento = Column(String(100), nullable=True)
    numero_lancamento = Column(String(30), nullable=True)
    lote = Column(String(30), nullable=True)
    origem = Column(SAEnum(OrigemLancamento), default=OrigemLancamento.IMPORTACAO, nullable=False)
    conciliado = Column(Boolean, default=False)
    score_conciliacao = Column(Numeric(5, 2), nullable=True)
    atipico = Column(Boolean, default=False)
    alerta_ia = Column(String(500), nullable=True)
    metadados = Column(JSON, default=dict)
    partida_dobrada_id = Column(UUID(as_uuid=True), ForeignKey("lancamentos.id"), nullable=True)

    conta = relationship("ContaContabil")
