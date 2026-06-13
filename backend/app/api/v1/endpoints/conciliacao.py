from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.conciliacao import Conciliacao, ConciliacaoItem, TipoConciliacao, StatusConciliacao
from app.models.balancete import Balancete, BalanceteItem
from app.models.lancamento import Lancamento, TipoLancamento
from app.models.extrato import ExtratoItem
from app.services.importacao.leitor_extrato import (
    importar_extrato_ofx, importar_extrato_csv, importar_extrato_pdf
)
from app.services.conciliacao.motor_conciliacao import (
    ItemConciliavel, conciliar_bancario, conciliar_clientes,
    conciliar_fornecedores, conciliar_tributos
)

router = APIRouter(prefix="/conciliacoes", tags=["conciliacao"])


@router.post("/extrato/processar")
async def processar_extrato(
    empresa_id: UUID = Form(...),
    extrato: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Importa extrato bancário (OFX/CSV/PDF) e tenta conciliar com lançamentos
    contábeis da empresa. Se não houver lançamentos, retorna os movimentos
    do extrato para visualização.
    """
    conteudo = await extrato.read()
    nome = (extrato.filename or "").lower()

    if nome.endswith(".ofx"):
        res_extrato = importar_extrato_ofx(conteudo)
    elif nome.endswith(".csv"):
        res_extrato = importar_extrato_csv(conteudo)
    elif nome.endswith(".pdf"):
        res_extrato = importar_extrato_pdf(conteudo)
    else:
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Use OFX, CSV ou PDF."
        )

    if not res_extrato.sucesso or not res_extrato.movimentos:
        raise HTTPException(
            status_code=422,
            detail={
                "mensagem": "Não foi possível processar o arquivo.",
                "erros": res_extrato.erros,
            }
        )

    movimentos = res_extrato.movimentos

    total_credito = sum(float(m.valor) for m in movimentos if m.tipo == "C")
    total_debito  = sum(float(m.valor) for m in movimentos if m.tipo == "D")

    # Busca lançamentos contábeis não conciliados da empresa
    result = await db.execute(
        select(Lancamento).where(
            Lancamento.empresa_id == empresa_id,
            Lancamento.conciliado == False,
        ).limit(500)
    )
    lancamentos_db = result.scalars().all()

    itens_externos = [
        ItemConciliavel(
            id=f"ext_{i}",
            data=m.data,
            valor=m.valor,
            tipo=m.tipo,
            descricao=m.descricao,
            documento=m.documento,
            origem="extrato",
        )
        for i, m in enumerate(movimentos)
    ]

    conciliacao_result = None

    if lancamentos_db:
        itens_contabeis = [
            ItemConciliavel(
                id=str(l.id),
                data=l.data_lancamento,
                valor=abs(l.valor),
                tipo=l.tipo.value if hasattr(l.tipo, "value") else l.tipo,
                descricao=l.historico or "",
                documento=l.documento,
                origem="contabil",
            )
            for l in lancamentos_db
        ]
        resultado = conciliar_bancario(itens_contabeis, itens_externos)
        conciliacao_result = {
            "score_geral": float(resultado.score_geral),
            "total_pares": len(resultado.pares),
            "conciliados_auto": sum(1 for p in resultado.pares if not p.manual),
            "revisao_manual": sum(1 for p in resultado.pares if p.manual),
            "nao_conciliados_contabil": len(resultado.nao_conciliados_contabil),
            "nao_conciliados_extrato": len(resultado.nao_conciliados_externos),
            "alertas": resultado.alertas[:20],
            "pares": [
                {
                    "contabil": {
                        "data": str(p.item_contabil.data),
                        "valor": float(p.item_contabil.valor),
                        "descricao": p.item_contabil.descricao,
                        "documento": p.item_contabil.documento or "",
                    },
                    "extrato": {
                        "data": str(p.item_externo.data),
                        "valor": float(p.item_externo.valor),
                        "descricao": p.item_externo.descricao,
                    },
                    "score": float(p.score),
                    "motivo": p.motivo,
                    "manual": p.manual,
                }
                for p in resultado.pares[:100]
            ],
        }

    return {
        "banco": res_extrato.banco or "Banco não identificado",
        "agencia": res_extrato.agencia or "",
        "conta": res_extrato.conta or "",
        "total_movimentos": len(movimentos),
        "total_credito": round(total_credito, 2),
        "total_debito": round(total_debito, 2),
        "saldo_periodo": round(total_credito - total_debito, 2),
        "tem_lancamentos": len(lancamentos_db) > 0,
        "total_lancamentos": len(lancamentos_db),
        "movimentos": [
            {
                "data": str(m.data),
                "tipo": m.tipo,
                "valor": float(m.valor),
                "descricao": m.descricao,
                "documento": m.documento or "",
            }
            for m in movimentos[:300]
        ],
        "conciliacao": conciliacao_result,
    }


@router.post("/bancaria")
async def iniciar_conciliacao_bancaria(
    balancete_id: UUID = Form(...),
    conta_id: UUID = Form(...),
    extrato: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Importa extrato
    conteudo = await extrato.read()
    nome = extrato.filename.lower()

    if nome.endswith(".ofx"):
        res_extrato = importar_extrato_ofx(conteudo)
    elif nome.endswith(".csv"):
        res_extrato = importar_extrato_csv(conteudo)
    elif nome.endswith(".pdf"):
        res_extrato = importar_extrato_pdf(conteudo)
    else:
        raise HTTPException(status_code=400, detail="Formato não suportado. Use OFX, CSV ou PDF.")

    if not res_extrato.sucesso:
        raise HTTPException(status_code=422, detail={"erros": res_extrato.erros})

    # Busca lançamentos contábeis da conta
    result = await db.execute(
        select(Lancamento).where(
            Lancamento.conta_id == conta_id,
            Lancamento.conciliado == False,
        )
    )
    lancamentos_db = result.scalars().all()

    # Converte para ItemConciliavel
    itens_contabeis = [
        ItemConciliavel(
            id=str(l.id),
            data=l.data_lancamento,
            valor=abs(l.valor),
            tipo=l.tipo,
            descricao=l.historico or "",
            documento=l.documento,
            origem="contabil",
        )
        for l in lancamentos_db
    ]

    itens_externos = [
        ItemConciliavel(
            id=f"ext_{i}",
            data=m.data,
            valor=m.valor,
            tipo=m.tipo,
            descricao=m.descricao,
            documento=m.documento,
            origem="extrato",
        )
        for i, m in enumerate(res_extrato.movimentos)
    ]

    # Executa conciliação
    resultado = conciliar_bancario(itens_contabeis, itens_externos)

    # Persiste extrato no banco
    balancete_result = await db.execute(select(Balancete).where(Balancete.id == balancete_id))
    balancete = balancete_result.scalar_one_or_none()

    for m in res_extrato.movimentos:
        item_extrato = ExtratoItem(
            empresa_id=balancete.empresa_id if balancete else None,
            conta_bancaria=str(conta_id),
            banco=res_extrato.banco,
            agencia=res_extrato.agencia,
            numero_conta=res_extrato.conta,
            data_movimento=m.data,
            tipo=m.tipo,
            valor=m.valor,
            descricao=m.descricao,
            numero_documento=m.documento,
            tipo_transacao=m.tipo_transacao,
            conciliado=False,
        )
        db.add(item_extrato)

    # Cria registro de conciliação
    total_contabil = sum(float(c.valor) for c in itens_contabeis)
    total_extrato = sum(float(e.valor) for e in itens_externos)

    conciliacao = Conciliacao(
        empresa_id=balancete.empresa_id if balancete else None,
        balancete_id=balancete_id,
        conta_id=conta_id,
        tipo=TipoConciliacao.BANCARIA,
        competencia=balancete.competencia if balancete else "",
        status=StatusConciliacao.CONCLUIDA if resultado.score_geral >= 95 else StatusConciliacao.COM_DIVERGENCIA,
        saldo_contabil=Decimal(str(total_contabil)),
        saldo_externo=Decimal(str(total_extrato)),
        diferenca=Decimal(str(abs(total_contabil - total_extrato))),
        score=resultado.score_geral,
        total_itens=len(resultado.pares),
        itens_conciliados=sum(1 for p in resultado.pares if not p.manual),
        itens_pendentes=len(resultado.nao_conciliados_contabil),
        itens_divergentes=sum(1 for p in resultado.pares if p.manual),
        alertas_ia=resultado.alertas,
        responsavel_id=current_user.id,
    )
    db.add(conciliacao)
    await db.commit()

    return {
        "conciliacao_id": str(conciliacao.id),
        "score_geral": float(resultado.score_geral),
        "total_pares": len(resultado.pares),
        "conciliados_automaticamente": sum(1 for p in resultado.pares if not p.manual),
        "requerem_revisao_manual": sum(1 for p in resultado.pares if p.manual),
        "nao_conciliados_contabil": len(resultado.nao_conciliados_contabil),
        "nao_conciliados_extrato": len(resultado.nao_conciliados_externos),
        "alertas": resultado.alertas[:20],
        "pares": [
            {
                "contabil": {
                    "id": p.item_contabil.id,
                    "data": str(p.item_contabil.data),
                    "valor": float(p.item_contabil.valor),
                    "descricao": p.item_contabil.descricao,
                    "documento": p.item_contabil.documento,
                },
                "extrato": {
                    "data": str(p.item_externo.data),
                    "valor": float(p.item_externo.valor),
                    "descricao": p.item_externo.descricao,
                },
                "score": float(p.score),
                "motivo": p.motivo,
                "manual": p.manual,
            }
            for p in resultado.pares[:100]
        ],
    }


@router.get("/{conciliacao_id}")
async def get_conciliacao(
    conciliacao_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Conciliacao).where(Conciliacao.id == conciliacao_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Conciliação não encontrada")

    return {
        "id": str(c.id),
        "tipo": c.tipo,
        "competencia": c.competencia,
        "status": c.status,
        "score": float(c.score or 0),
        "saldo_contabil": float(c.saldo_contabil or 0),
        "saldo_externo": float(c.saldo_externo or 0),
        "diferenca": float(c.diferenca or 0),
        "total_itens": c.total_itens,
        "itens_conciliados": c.itens_conciliados,
        "itens_pendentes": c.itens_pendentes,
        "itens_divergentes": c.itens_divergentes,
        "alertas_ia": c.alertas_ia or [],
    }
