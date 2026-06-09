from sqlalchemy import Column, String, Enum as SAEnum, ForeignKey, Numeric, Date, JSON, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class TipoDocumento(str, enum.Enum):
    NF_ENTRADA = "nf_entrada"
    NF_SAIDA = "nf_saida"
    BOLETO = "boleto"
    GUIA_TRIBUTO = "guia_tributo"
    EXTRATO = "extrato"
    CONTRATO = "contrato"
    FOLHA = "folha"
    OUTROS = "outros"


class Documento(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documentos"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    tipo = Column(SAEnum(TipoDocumento), nullable=False)
    numero = Column(String(50), nullable=True)
    serie = Column(String(10), nullable=True)
    chave_acesso = Column(String(50), nullable=True, unique=True)
    data_emissao = Column(Date, nullable=True)
    data_vencimento = Column(Date, nullable=True)
    data_pagamento = Column(Date, nullable=True)

    cnpj_emitente = Column(String(18), nullable=True)
    nome_emitente = Column(String(300), nullable=True)
    cnpj_destinatario = Column(String(18), nullable=True)
    nome_destinatario = Column(String(300), nullable=True)

    valor_total = Column(Numeric(18, 2), nullable=True)
    valor_pago = Column(Numeric(18, 2), nullable=True)
    valor_desconto = Column(Numeric(18, 2), nullable=True)

    arquivo_path = Column(String(500), nullable=True)
    arquivo_original = Column(String(200), nullable=True)
    dados_xml = Column(JSON, default=dict)
    dados_ocr = Column(JSON, default=dict)
    conciliado = Column(Boolean, default=False)
    lancamento_id = Column(UUID(as_uuid=True), ForeignKey("lancamentos.id"), nullable=True)
    metadados = Column(JSON, default=dict)
