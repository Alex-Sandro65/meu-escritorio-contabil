from sqlalchemy import Column, String, Integer, JSON, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class PlanoTenant(str, enum.Enum):
    STARTER = "starter"       # até 5 empresas
    PROFISSIONAL = "profissional"  # até 20 empresas
    ENTERPRISE = "enterprise"  # ilimitado


class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    nome = Column(String(200), nullable=False)
    cnpj = Column(String(18), nullable=True, unique=True)
    plano = Column(SAEnum(PlanoTenant), default=PlanoTenant.STARTER, nullable=False)
    limite_empresas = Column(Integer, default=5)
    configuracoes = Column(JSON, default=dict)

    usuarios = relationship("User", back_populates="tenant")
    empresas = relationship("Empresa", back_populates="tenant")
