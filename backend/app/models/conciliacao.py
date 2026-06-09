from sqlalchemy import Column, String, Enum as SAEnum, ForeignKey, Numeric, Date, Boolean, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class TipoConciliacao(str, enum.Enum):
    BANCARIA = "bancaria"
    CLIENTES = "clientes"
    FORNECEDORES = "fornecedores"
    TRIBUTOS = "tributos"
    FOLHA = "folha"
    EMPRESTIMOS = "emprestimos"
    APLICACOES = "aplicacoes"
    IMOBILIZADO = "imobilizado"
    ESTOQUES = "estoques"
    INTERCOMPANY = "intercompany"


class StatusConciliacao(str, enum.Enum):
    PENDENTE = "pendente"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDA = "concluida"
    COM_DIVERGENCIA = "com_divergencia"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"


class Conciliacao(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conciliacoes"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    balancete_id = Column(UUID(as_uuid=True), ForeignKey("balancetes.id"), nullable=True)
    conta_id = Column(UUID(as_uuid=True), ForeignKey("contas_contabeis.id"), nullable=True)

    tipo = Column(SAEnum(TipoConciliacao), nullable=False)
    competencia = Column(String(7), nullable=False)
    status = Column(SAEnum(StatusConciliacao), default=StatusConciliacao.PENDENTE, nullable=False)

    saldo_contabil = Column(Numeric(18, 2), nullable=True)
    saldo_externo = Column(Numeric(18, 2), nullable=True)
    diferenca = Column(Numeric(18, 2), nullable=True)
    score = Column(Numeric(5, 2), nullable=True)

    total_itens = Column(Integer, default=0)
    itens_conciliados = Column(Integer, default=0)
    itens_pendentes = Column(Integer, default=0)
    itens_divergentes = Column(Integer, default=0)

    responsavel_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    aprovador_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    observacoes = Column(String(2000), nullable=True)
    alertas_ia = Column(JSON, default=list)
    evidencias = Column(JSON, default=list)

    empresa = relationship("Empresa", back_populates="conciliacoes")
    itens = relationship("ConciliacaoItem", back_populates="conciliacao",
                         cascade="all, delete-orphan")


class ConciliacaoItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conciliacao_items"

    conciliacao_id = Column(UUID(as_uuid=True), ForeignKey("conciliacoes.id"), nullable=False)
    lancamento_id = Column(UUID(as_uuid=True), ForeignKey("lancamentos.id"), nullable=True)
    extrato_item_id = Column(UUID(as_uuid=True), ForeignKey("extrato_items.id"), nullable=True)

    data = Column(Date, nullable=True)
    valor = Column(Numeric(18, 2), nullable=False)
    descricao = Column(String(500), nullable=True)
    documento = Column(String(100), nullable=True)
    status = Column(String(30), default="pendente")
    score = Column(Numeric(5, 2), nullable=True)
    motivo_divergencia = Column(String(500), nullable=True)
    conciliado_manualmente = Column(Boolean, default=False)
    metadados = Column(JSON, default=dict)

    conciliacao = relationship("Conciliacao", back_populates="itens")
