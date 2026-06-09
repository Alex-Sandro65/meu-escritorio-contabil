from sqlalchemy import Column, String, Boolean, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class PerfilUsuario(str, enum.Enum):
    ADMIN = "admin"
    CONTADOR = "contador"
    ANALISTA = "analista"
    AUDITOR = "auditor"
    VISUALIZADOR = "visualizador"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    hashed_password = Column(String(200), nullable=False)
    perfil = Column(SAEnum(PerfilUsuario), default=PerfilUsuario.ANALISTA, nullable=False)
    mfa_secret = Column(String(64), nullable=True)
    mfa_ativo = Column(Boolean, default=False)
    creci = Column(String(20), nullable=True)

    tenant = relationship("Tenant", back_populates="usuarios")
