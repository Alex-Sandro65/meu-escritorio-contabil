from sqlalchemy import Column, String, Enum as SAEnum, ForeignKey, Integer, Numeric, Date, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class StatusBalancete(str, enum.Enum):
    IMPORTANDO = "importando"
    PROCESSANDO = "processando"
    CONCILIANDO = "conciliando"
    CONCLUIDO = "concluido"
    ERRO = "erro"


class Balancete(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "balancetes"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    plano_contas_id = Column(UUID(as_uuid=True), ForeignKey("planos_contas.id"), nullable=True)
    competencia = Column(String(7), nullable=False)  # YYYY-MM
    data_inicial = Column(Date, nullable=False)
    data_final = Column(Date, nullable=False)
    status = Column(SAEnum(StatusBalancete), default=StatusBalancete.IMPORTANDO, nullable=False)
    arquivo_origem = Column(String(500), nullable=True)
    total_debitos = Column(Numeric(18, 2), default=0)
    total_creditos = Column(Numeric(18, 2), default=0)
    total_contas = Column(Integer, default=0)
    percentual_conciliado = Column(Numeric(5, 2), default=0)
    metadados = Column(JSON, default=dict)
    observacoes = Column(String(2000), nullable=True)

    empresa = relationship("Empresa", back_populates="balancetes")
    itens = relationship("BalanceteItem", back_populates="balancete",
                         cascade="all, delete-orphan")


class BalanceteItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "balancete_items"

    balancete_id = Column(UUID(as_uuid=True), ForeignKey("balancetes.id"), nullable=False)
    conta_id = Column(UUID(as_uuid=True), ForeignKey("contas_contabeis.id"), nullable=True)

    codigo_conta = Column(String(30), nullable=False)
    descricao_conta = Column(String(300), nullable=False)
    nivel = Column(Integer, default=1)

    saldo_anterior = Column(Numeric(18, 2), default=0)
    debitos_periodo = Column(Numeric(18, 2), default=0)
    creditos_periodo = Column(Numeric(18, 2), default=0)
    saldo_atual = Column(Numeric(18, 2), default=0)

    saldo_conciliado = Column(Numeric(18, 2), nullable=True)
    diferenca = Column(Numeric(18, 2), nullable=True)
    score_conciliacao = Column(Numeric(5, 2), nullable=True)
    status_conciliacao = Column(String(30), default="pendente")

    alertas_ia = Column(JSON, default=list)
    composicao = Column(JSON, default=list)
    responsavel = Column(String(200), nullable=True)
    observacao = Column(String(2000), nullable=True)

    balancete = relationship("Balancete", back_populates="itens")
    conta = relationship("ContaContabil", back_populates="balancete_items")
