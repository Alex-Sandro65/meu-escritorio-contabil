from sqlalchemy import Column, String, Enum as SAEnum, ForeignKey, Integer, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class NaturezaConta(str, enum.Enum):
    ATIVO = "ativo"
    PASSIVO = "passivo"
    PATRIMONIO_LIQUIDO = "patrimonio_liquido"
    RECEITA = "receita"
    CUSTO = "custo"
    DESPESA = "despesa"
    RESULTADO = "resultado"


class TipoConta(str, enum.Enum):
    SINTETICA = "sintetica"    # Grupo — não recebe lançamentos
    ANALITICA = "analitica"    # Recebe lançamentos


class GrupoContabil(str, enum.Enum):
    ATIVO_CIRCULANTE = "ativo_circulante"
    ATIVO_NAO_CIRCULANTE = "ativo_nao_circulante"
    ATIVO_REALIZAVEL = "ativo_realizavel"
    ATIVO_IMOBILIZADO = "ativo_imobilizado"
    ATIVO_INTANGIVEL = "ativo_intangivel"
    PASSIVO_CIRCULANTE = "passivo_circulante"
    PASSIVO_NAO_CIRCULANTE = "passivo_nao_circulante"
    PATRIMONIO_LIQUIDO = "patrimonio_liquido"
    RECEITA_BRUTA = "receita_bruta"
    DEDUCOES = "deducoes"
    CMV = "cmv"
    DESPESA_OPERACIONAL = "despesa_operacional"
    DESPESA_FINANCEIRA = "despesa_financeira"
    RECEITA_FINANCEIRA = "receita_financeira"
    RESULTADO = "resultado"


class PlanoContas(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "planos_contas"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    descricao = Column(String(500), nullable=True)
    versao = Column(String(20), default="1.0")
    padrao = Column(Boolean, default=False)

    empresa = relationship("Empresa", back_populates="planos_contas")
    contas = relationship("ContaContabil", back_populates="plano_contas",
                          cascade="all, delete-orphan")


class ContaContabil(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contas_contabeis"

    plano_contas_id = Column(UUID(as_uuid=True), ForeignKey("planos_contas.id"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("contas_contabeis.id"), nullable=True)

    codigo = Column(String(30), nullable=False)
    descricao = Column(String(300), nullable=False)
    nivel = Column(Integer, nullable=False, default=1)
    natureza = Column(SAEnum(NaturezaConta), nullable=False)
    tipo = Column(SAEnum(TipoConta), default=TipoConta.ANALITICA, nullable=False)
    grupo = Column(SAEnum(GrupoContabil), nullable=True)
    aceita_lancamento = Column(Boolean, default=True)
    dre = Column(Boolean, default=False)
    balanco = Column(Boolean, default=True)
    cosif = Column(String(20), nullable=True)
    referencia_ecd = Column(String(20), nullable=True)
    referencia_ecf = Column(String(20), nullable=True)

    plano_contas = relationship("PlanoContas", back_populates="contas")
    filhos = relationship("ContaContabil", backref="parent", remote_side="ContaContabil.id")
    balancete_items = relationship("BalanceteItem", back_populates="conta")
