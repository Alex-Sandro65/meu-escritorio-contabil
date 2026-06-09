from sqlalchemy import Column, String, Enum as SAEnum, ForeignKey, Numeric, Date, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class TipoMovimento(str, enum.Enum):
    CREDITO = "C"
    DEBITO = "D"


class OrigemExtrato(str, enum.Enum):
    OFX = "ofx"
    PDF = "pdf"
    CSV = "csv"
    MANUAL = "manual"
    API_BANCO = "api_banco"


class ExtratoItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "extrato_items"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    conta_bancaria = Column(String(50), nullable=False)
    banco = Column(String(100), nullable=True)
    agencia = Column(String(10), nullable=True)
    numero_conta = Column(String(20), nullable=True)

    data_movimento = Column(Date, nullable=False)
    data_compensacao = Column(Date, nullable=True)
    tipo = Column(SAEnum(TipoMovimento), nullable=False)
    valor = Column(Numeric(18, 2), nullable=False)
    descricao = Column(String(500), nullable=True)
    numero_documento = Column(String(100), nullable=True)
    tipo_transacao = Column(String(50), nullable=True)  # PIX, TED, DOC, BOLETO etc.
    nome_favorecido = Column(String(200), nullable=True)
    cpf_cnpj_favorecido = Column(String(18), nullable=True)
    origem = Column(SAEnum(OrigemExtrato), default=OrigemExtrato.OFX, nullable=False)
    conciliado = Column(Boolean, default=False)
    lancamento_id = Column(UUID(as_uuid=True), ForeignKey("lancamentos.id"), nullable=True)
    score_conciliacao = Column(Numeric(5, 2), nullable=True)
    metadados = Column(JSON, default=dict)

    lancamento = relationship("Lancamento")
