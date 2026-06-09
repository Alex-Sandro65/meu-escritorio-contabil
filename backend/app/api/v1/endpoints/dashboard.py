from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from uuid import UUID
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.empresa import Empresa
from app.models.balancete import Balancete, BalanceteItem, StatusBalancete
from app.models.conciliacao import Conciliacao, StatusConciliacao
from app.models.sped import SpedEcd, SpedEcf

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/resumo")
async def resumo_geral(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = current_user.tenant_id

    # Total de empresas
    r_emp = await db.execute(
        select(func.count(Empresa.id)).where(
            Empresa.tenant_id == tenant_id, Empresa.is_active == True
        )
    )
    total_empresas = r_emp.scalar() or 0

    # Balancetes por status
    r_bal = await db.execute(
        select(Balancete.status, func.count(Balancete.id))
        .join(Empresa, Empresa.id == Balancete.empresa_id)
        .where(Empresa.tenant_id == tenant_id)
        .group_by(Balancete.status)
    )
    bal_status = {row[0]: row[1] for row in r_bal.all()}

    # Conciliações
    r_conc = await db.execute(
        select(Conciliacao.status, func.count(Conciliacao.id))
        .join(Empresa, Empresa.id == Conciliacao.empresa_id)
        .where(Empresa.tenant_id == tenant_id)
        .group_by(Conciliacao.status)
    )
    conc_status = {row[0]: row[1] for row in r_conc.all()}

    # Score médio de conciliações
    r_score = await db.execute(
        select(func.avg(Conciliacao.score))
        .join(Empresa, Empresa.id == Conciliacao.empresa_id)
        .where(Empresa.tenant_id == tenant_id)
    )
    score_medio = float(r_score.scalar() or 0)

    # Diferenças totais
    r_diff = await db.execute(
        select(func.sum(Conciliacao.diferenca))
        .join(Empresa, Empresa.id == Conciliacao.empresa_id)
        .where(Empresa.tenant_id == tenant_id)
    )
    total_diferencas = float(r_diff.scalar() or 0)

    return {
        "total_empresas": total_empresas,
        "balancetes": {
            "total": sum(bal_status.values()),
            "concluidos": bal_status.get(StatusBalancete.CONCLUIDO, 0),
            "em_andamento": bal_status.get(StatusBalancete.CONCILIANDO, 0) + bal_status.get(StatusBalancete.PROCESSANDO, 0),
            "com_erro": bal_status.get(StatusBalancete.ERRO, 0),
        },
        "conciliacoes": {
            "total": sum(conc_status.values()),
            "aprovadas": conc_status.get(StatusConciliacao.APROVADA, 0),
            "concluidas": conc_status.get(StatusConciliacao.CONCLUIDA, 0),
            "com_divergencia": conc_status.get(StatusConciliacao.COM_DIVERGENCIA, 0),
            "pendentes": conc_status.get(StatusConciliacao.PENDENTE, 0),
        },
        "score_medio_conciliacao": round(score_medio, 2),
        "total_diferencas": total_diferencas,
    }


@router.get("/empresa/{empresa_id}")
async def resumo_empresa(
    empresa_id: UUID,
    competencia: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filtro_bal = [Balancete.empresa_id == empresa_id]
    filtro_conc = [Conciliacao.empresa_id == empresa_id]
    if competencia:
        filtro_bal.append(Balancete.competencia == competencia)
        filtro_conc.append(Conciliacao.competencia == competencia)

    r_bal = await db.execute(
        select(Balancete).where(*filtro_bal).order_by(Balancete.competencia.desc()).limit(1)
    )
    ultimo_balancete = r_bal.scalar_one_or_none()

    r_contas = await db.execute(
        select(
            func.count(BalanceteItem.id).label("total"),
            func.sum(
                func.case((BalanceteItem.status_conciliacao == "conciliado", 1), else_=0)
            ).label("conciliadas"),
            func.sum(
                func.case((BalanceteItem.status_conciliacao == "divergente", 1), else_=0)
            ).label("divergentes"),
            func.sum(BalanceteItem.diferenca).label("total_diferencas"),
        )
        .where(BalanceteItem.balancete_id == ultimo_balancete.id if ultimo_balancete else False)
    )
    stats = r_contas.one()

    r_conc = await db.execute(
        select(Conciliacao).where(*filtro_conc).order_by(Conciliacao.created_at.desc()).limit(10)
    )
    conciliacoes = r_conc.scalars().all()

    return {
        "empresa_id": str(empresa_id),
        "competencia": competencia,
        "ultimo_balancete": {
            "id": str(ultimo_balancete.id) if ultimo_balancete else None,
            "status": ultimo_balancete.status if ultimo_balancete else None,
            "percentual_conciliado": float(ultimo_balancete.percentual_conciliado or 0) if ultimo_balancete else 0,
        } if ultimo_balancete else None,
        "contas": {
            "total": stats.total or 0,
            "conciliadas": stats.conciliadas or 0,
            "divergentes": stats.divergentes or 0,
            "pendentes": (stats.total or 0) - (stats.conciliadas or 0) - (stats.divergentes or 0),
            "total_diferencas": float(stats.total_diferencas or 0),
        },
        "conciliacoes_recentes": [
            {
                "id": str(c.id),
                "tipo": c.tipo,
                "status": c.status,
                "score": float(c.score or 0),
                "diferenca": float(c.diferenca or 0),
            }
            for c in conciliacoes
        ],
    }
