from sqlalchemy import Column, String, Boolean, Enum as SAEnum, ForeignKey, Date, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class RegimeTributario(str, enum.Enum):
    SIMPLES_NACIONAL = "simples_nacional"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"
    IMUNE = "imune"


class NaturezaJuridica(str, enum.Enum):
    LTDA = "ltda"
    SA = "sa"
    MEI = "mei"
    EIRELI = "eireli"
    SLU = "slu"
    ASSOCIACAO = "associacao"
    FUNDACAO = "fundacao"


class Empresa(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "empresas"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    razao_social = Column(String(300), nullable=False)
    nome_fantasia = Column(String(200), nullable=True)
    cnpj = Column(String(18), nullable=False)
    ie = Column(String(20), nullable=True)
    im = Column(String(20), nullable=True)
    regime_tributario = Column(SAEnum(RegimeTributario), nullable=False)
    natureza_juridica = Column(SAEnum(NaturezaJuridica), nullable=True)
    cnae_principal = Column(String(10), nullable=True)
    data_abertura = Column(Date, nullable=True)
    endereco = Column(JSON, default=dict)
    configuracoes = Column(JSON, default=dict)
    integracoes = Column(JSON, default=dict)

    tenant = relationship("Tenant", back_populates="empresas")
    planos_contas = relationship("PlanoContas", back_populates="empresa")
    balancetes = relationship("Balancete", back_populates="empresa")
    conciliacoes = relationship("Conciliacao", back_populates="empresa")
