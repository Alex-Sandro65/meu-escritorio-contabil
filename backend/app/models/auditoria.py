from sqlalchemy import Column, String, Enum as SAEnum, ForeignKey, Numeric, Date, JSON, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class TipoPapel(str, enum.Enum):
    COMPOSICAO_SALDO = "composicao_saldo"
    CONCILIACAO = "conciliacao"
    CIRCULARIZACAO = "circularizacao"
    MEMORIA_CALCULO = "memoria_calculo"
    ANALISE_HORIZONTAL = "analise_horizontal"
    ANALISE_VERTICAL = "analise_vertical"
    INDICE_FINANCEIRO = "indice_financeiro"
    MATERIALIDADE = "materialidade"
    TESTE_AUDITORIA = "teste_auditoria"


class StatusPapel(str, enum.Enum):
    RASCUNHO = "rascunho"
    EM_REVISAO = "em_revisao"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"


class PapelTrabalho(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "papeis_trabalho"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    balancete_id = Column(UUID(as_uuid=True), ForeignKey("balancetes.id"), nullable=True)
    tipo = Column(SAEnum(TipoPapel), nullable=False)
    competencia = Column(String(7), nullable=False)
    titulo = Column(String(300), nullable=False)
    referencia = Column(String(50), nullable=True)  # Ex: PT-1.01, PT-2.03
    status = Column(SAEnum(StatusPapel), default=StatusPapel.RASCUNHO, nullable=False)
    conteudo = Column(JSON, default=dict)
    conclusao = Column(Text, nullable=True)
    responsavel_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revisor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    materialidade = Column(Numeric(18, 2), nullable=True)
    risco = Column(String(20), nullable=True)  # alto, medio, baixo
    arquivo_pdf = Column(String(500), nullable=True)


class TestAuditoria(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "testes_auditoria"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    papel_trabalho_id = Column(UUID(as_uuid=True), ForeignKey("papeis_trabalho.id"), nullable=True)
    conta_id = Column(UUID(as_uuid=True), ForeignKey("contas_contabeis.id"), nullable=True)
    competencia = Column(String(7), nullable=False)
    descricao = Column(String(500), nullable=False)
    procedimento = Column(Text, nullable=True)
    resultado = Column(Text, nullable=True)
    conclusao = Column(String(200), nullable=True)
    passou = Column(Boolean, nullable=True)
    divergencia_encontrada = Column(Boolean, default=False)
    valor_divergencia = Column(Numeric(18, 2), nullable=True)
    evidencias = Column(JSON, default=list)
    risco = Column(String(20), nullable=True)
