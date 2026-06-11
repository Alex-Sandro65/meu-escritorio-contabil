from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.empresa import Empresa, RegimeTributario, NaturezaJuridica

router = APIRouter(prefix="/empresas", tags=["empresa"])


class EmpresaCreate(BaseModel):
    razao_social: str
    nome_fantasia: Optional[str] = None
    cnpj: str
    regime_tributario: RegimeTributario
    natureza_juridica: Optional[NaturezaJuridica] = None
    cnae_principal: Optional[str] = None


@router.get("/")
async def listar_empresas(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Empresa)
        .where(
            Empresa.tenant_id == current_user.tenant_id,
            Empresa.is_active == True,
        )
        .order_by(Empresa.razao_social)
    )
    empresas = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "razao_social": e.razao_social,
            "nome_fantasia": e.nome_fantasia,
            "cnpj": e.cnpj,
            "regime_tributario": e.regime_tributario,
        }
        for e in empresas
    ]


@router.post("/", status_code=201)
async def criar_empresa(
    data: EmpresaCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Empresa).where(
            Empresa.tenant_id == current_user.tenant_id,
            Empresa.cnpj == data.cnpj,
            Empresa.is_active == True,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="CNPJ já cadastrado neste escritório")

    empresa = Empresa(
        tenant_id=current_user.tenant_id,
        razao_social=data.razao_social,
        nome_fantasia=data.nome_fantasia,
        cnpj=data.cnpj,
        regime_tributario=data.regime_tributario,
        natureza_juridica=data.natureza_juridica,
        cnae_principal=data.cnae_principal,
    )
    db.add(empresa)
    await db.commit()
    await db.refresh(empresa)

    return {
        "id": str(empresa.id),
        "razao_social": empresa.razao_social,
        "nome_fantasia": empresa.nome_fantasia,
        "cnpj": empresa.cnpj,
        "regime_tributario": empresa.regime_tributario,
    }


@router.get("/{empresa_id}")
async def get_empresa(
    empresa_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Empresa).where(
            Empresa.id == empresa_id,
            Empresa.tenant_id == current_user.tenant_id,
            Empresa.is_active == True,
        )
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return {
        "id": str(empresa.id),
        "razao_social": empresa.razao_social,
        "nome_fantasia": empresa.nome_fantasia,
        "cnpj": empresa.cnpj,
        "regime_tributario": empresa.regime_tributario,
    }


@router.delete("/{empresa_id}")
async def desativar_empresa(
    empresa_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Empresa).where(
            Empresa.id == empresa_id,
            Empresa.tenant_id == current_user.tenant_id,
        )
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    empresa.is_active = False
    await db.commit()
    return {"message": "Empresa desativada com sucesso"}
