from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
import uuid
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.balancete import Balancete, BalanceteItem, StatusBalancete
from app.models.plano_contas import ContaContabil, PlanoContas
from app.services.importacao.leitor_balancete import (
    importar_balancete_excel, importar_balancete_csv,
    importar_balancete_sped, importar_balancete_pdf
)
from app.services.importacao.classificador_conta import classificar_conta
from pydantic import BaseModel
from datetime import date

router = APIRouter(prefix="/balancetes", tags=["balancete"])


class BalanceteCreate(BaseModel):
    empresa_id: UUID
    competencia: str  # YYYY-MM
    data_inicial: date
    data_final: date


@router.post("/importar")
async def importar_balancete(
    background_tasks: BackgroundTasks,
    empresa_id: UUID = Form(...),
    competencia: str = Form(...),
    data_inicial: date = Form(...),
    data_final: date = Form(...),
    arquivo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conteudo = await arquivo.read()
    nome = arquivo.filename.lower()

    if nome.endswith((".xlsx", ".xls")):
        resultado = importar_balancete_excel(conteudo, nome)
    elif nome.endswith(".csv"):
        resultado = importar_balancete_csv(conteudo)
    elif nome.endswith(".txt") or nome.endswith(".sped"):
        resultado = importar_balancete_sped(conteudo)
    elif nome.endswith(".pdf"):
        resultado = importar_balancete_pdf(conteudo)
    else:
        raise HTTPException(status_code=400, detail=f"Formato não suportado: {nome}")

    if not resultado.sucesso:
        raise HTTPException(status_code=422, detail={"erros": resultado.erros})

    # Cria registro do balancete
    balancete = Balancete(
        empresa_id=empresa_id,
        competencia=competencia,
        data_inicial=data_inicial,
        data_final=data_final,
        status=StatusBalancete.PROCESSANDO,
        arquivo_origem=arquivo.filename,
        total_contas=len(resultado.contas),
        metadados=resultado.metadados,
    )
    db.add(balancete)
    await db.flush()

    # Persiste itens
    total_debitos = total_creditos = 0
    for conta_imp in resultado.contas:
        classificacao = classificar_conta(conta_imp.codigo, conta_imp.descricao)
        item = BalanceteItem(
            balancete_id=balancete.id,
            codigo_conta=conta_imp.codigo,
            descricao_conta=conta_imp.descricao,
            nivel=conta_imp.nivel,
            saldo_anterior=conta_imp.saldo_anterior,
            debitos_periodo=conta_imp.debitos,
            creditos_periodo=conta_imp.creditos,
            saldo_atual=conta_imp.saldo_atual,
            status_conciliacao="pendente",
        )
        db.add(item)
        total_debitos += float(conta_imp.debitos)
        total_creditos += float(conta_imp.creditos)

    balancete.total_debitos = total_debitos
    balancete.total_creditos = total_creditos
    balancete.status = StatusBalancete.CONCLUIDO

    await db.commit()

    return {
        "balancete_id": str(balancete.id),
        "total_contas": len(resultado.contas),
        "formato_detectado": resultado.formato_detectado,
        "erros": resultado.erros,
        "avisos": resultado.avisos,
        "metadados": resultado.metadados,
    }


@router.get("/{balancete_id}")
async def get_balancete(
    balancete_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Balancete).where(Balancete.id == balancete_id)
    )
    balancete = result.scalar_one_or_none()
    if not balancete:
        raise HTTPException(status_code=404, detail="Balancete não encontrado")

    result_itens = await db.execute(
        select(BalanceteItem).where(BalanceteItem.balancete_id == balancete_id)
        .order_by(BalanceteItem.codigo_conta)
    )
    itens = result_itens.scalars().all()

    return {
        "id": str(balancete.id),
        "empresa_id": str(balancete.empresa_id),
        "competencia": balancete.competencia,
        "status": balancete.status,
        "total_contas": balancete.total_contas,
        "percentual_conciliado": float(balancete.percentual_conciliado or 0),
        "itens": [
            {
                "id": str(i.id),
                "codigo": i.codigo_conta,
                "descricao": i.descricao_conta,
                "nivel": i.nivel,
                "saldo_anterior": float(i.saldo_anterior or 0),
                "debitos": float(i.debitos_periodo or 0),
                "creditos": float(i.creditos_periodo or 0),
                "saldo_atual": float(i.saldo_atual or 0),
                "saldo_conciliado": float(i.saldo_conciliado or 0) if i.saldo_conciliado else None,
                "diferenca": float(i.diferenca or 0) if i.diferenca else None,
                "score": float(i.score_conciliacao or 0) if i.score_conciliacao else None,
                "status": i.status_conciliacao,
                "alertas_ia": i.alertas_ia or [],
                "composicao": i.composicao or [],
                "responsavel": i.responsavel,
            }
            for i in itens
        ],
    }


@router.get("/empresa/{empresa_id}")
async def listar_balancetes(
    empresa_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Balancete).where(Balancete.empresa_id == empresa_id)
        .order_by(Balancete.competencia.desc())
    )
    balancetes = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "competencia": b.competencia,
            "status": b.status,
            "total_contas": b.total_contas,
            "percentual_conciliado": float(b.percentual_conciliado or 0),
            "created_at": b.created_at.isoformat(),
        }
        for b in balancetes
    ]
