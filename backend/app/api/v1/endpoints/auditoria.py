from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.balancete import Balancete, BalanceteItem
from app.models.auditoria import PapelTrabalho, TipoPapel, StatusPapel
from app.services.auditoria.gerador_papeis import (
    calcular_materialidade, calcular_analise_horizontal,
    calcular_analise_vertical, calcular_indices
)
from app.services.ai.motor_ia import gerar_analise_balancete

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


class MaterialidadeRequest(BaseModel):
    empresa_id: UUID
    balancete_id: UUID
    receita_bruta: Optional[float] = None
    ativo_total: Optional[float] = None
    lucro_antes_ir: Optional[float] = None
    patrimonio_liquido: Optional[float] = None


@router.post("/materialidade")
async def calcular_mat(
    data: MaterialidadeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mat = calcular_materialidade(
        receita_bruta=Decimal(str(data.receita_bruta)) if data.receita_bruta else None,
        ativo_total=Decimal(str(data.ativo_total)) if data.ativo_total else None,
        lucro_antes_ir=Decimal(str(data.lucro_antes_ir)) if data.lucro_antes_ir else None,
        patrimonio_liquido=Decimal(str(data.patrimonio_liquido)) if data.patrimonio_liquido else None,
    )
    return {
        "base_calculo": mat.base_calculo,
        "valor_base": float(mat.valor_base),
        "percentual_aplicado": float(mat.percentual_aplicado),
        "materialidade_geral": float(mat.materialidade_geral),
        "materialidade_execucao": float(mat.materialidade_execucao),
        "materialidade_trivial": float(mat.materialidade_trivial),
    }


@router.post("/analise-horizontal")
async def analise_horizontal(
    balancete_atual_id: UUID,
    balancete_anterior_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def get_contas(bal_id):
        r = await db.execute(
            select(BalanceteItem).where(BalanceteItem.balancete_id == bal_id)
        )
        return [
            {"codigo": i.codigo_conta, "descricao": i.descricao_conta,
             "saldo_atual": float(i.saldo_atual or 0)}
            for i in r.scalars().all()
        ]

    contas_atual = await get_contas(balancete_atual_id)
    contas_anterior = await get_contas(balancete_anterior_id)

    analise = calcular_analise_horizontal(contas_atual, contas_anterior)
    alertas = [a for a in analise if a.alerta]

    return {
        "total_contas": len(analise),
        "contas_com_alerta": len(alertas),
        "analise": [
            {
                "conta": a.conta,
                "descricao": a.descricao,
                "valor_atual": float(a.valor_atual),
                "valor_anterior": float(a.valor_anterior),
                "variacao_absoluta": float(a.variacao_absoluta),
                "variacao_percentual": float(a.variacao_percentual),
                "alerta": a.alerta,
            }
            for a in analise
        ],
        "alertas": [
            {
                "conta": a.conta,
                "descricao": a.descricao,
                "variacao": f"{a.variacao_percentual:+.1f}%",
                "valor": float(a.variacao_absoluta),
            }
            for a in alertas
        ],
    }


@router.post("/indices/{balancete_id}")
async def calcular_indices_financeiros(
    balancete_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(BalanceteItem).where(BalanceteItem.balancete_id == balancete_id)
    )
    itens = r.scalars().all()

    def soma_grupo(prefixos: list[str]) -> Decimal:
        total = Decimal("0")
        for i in itens:
            for p in prefixos:
                if i.codigo_conta.startswith(p):
                    total += Decimal(str(i.saldo_atual or 0))
                    break
        return total

    ativo_circ = soma_grupo(["1.1"])
    passivo_circ = soma_grupo(["2.1"])
    ativo_total = soma_grupo(["1"])
    passivo_total = soma_grupo(["2"])
    pl = soma_grupo(["2.3", "3"])
    receita = soma_grupo(["3"])
    cmv = soma_grupo(["4"])
    lucro_bruto = receita - cmv
    despesas = soma_grupo(["5", "8"])
    lucro_liq = lucro_bruto - despesas
    disponivel = soma_grupo(["1.1.01"])

    indices = calcular_indices(
        ativo_circulante=ativo_circ,
        passivo_circulante=passivo_circ,
        ativo_total=ativo_total,
        passivo_total=passivo_total,
        patrimonio_liquido=pl,
        receita_liquida=receita,
        lucro_bruto=lucro_bruto,
        lucro_liquido=lucro_liq,
        disponivel=disponivel,
    )

    return {
        "indices": [
            {
                "nome": i.nome,
                "formula": i.formula,
                "valor": float(i.valor),
                "referencia": i.referencia,
                "status": i.status,
                "interpretacao": i.interpretacao,
            }
            for i in indices
        ]
    }


@router.post("/analise-ia/{balancete_id}")
async def analise_ia(
    balancete_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r_bal = await db.execute(select(Balancete).where(Balancete.id == balancete_id))
    balancete = r_bal.scalar_one_or_none()
    if not balancete:
        raise HTTPException(status_code=404, detail="Balancete não encontrado")

    r_itens = await db.execute(
        select(BalanceteItem).where(
            BalanceteItem.balancete_id == balancete_id,
            BalanceteItem.diferenca != 0,
        ).limit(10)
    )
    top_div = [
        {
            "conta": i.codigo_conta,
            "descricao": i.descricao_conta,
            "diferenca": float(i.diferenca or 0),
        }
        for i in r_itens.scalars().all()
    ]

    dados = {
        "competencia": balancete.competencia,
        "total_contas": balancete.total_contas,
        "contas_conciliadas": 0,
        "pct_conciliado": float(balancete.percentual_conciliado or 0),
        "total_diferencas": float(balancete.total_debitos or 0) - float(balancete.total_creditos or 0),
        "contas_alerta": len(top_div),
        "top_divergencias": top_div,
    }

    analise = await gerar_analise_balancete(dados)
    return {"analise": analise, "competencia": balancete.competencia}
