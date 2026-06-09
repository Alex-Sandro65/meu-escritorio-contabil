"""
Motor de Conciliação — coração do sistema.

Score de confiança:
  100% → valor + data + documento idênticos
   95% → valor + documento
   90% → valor + histórico similar
   70% → valor semelhante (±0.05)
  <70% → encaminha para análise manual
"""
from decimal import Decimal
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional
import re


SCORE_PLENO = Decimal("100")
SCORE_DOC = Decimal("95")
SCORE_HISTORICO = Decimal("90")
SCORE_VALOR = Decimal("70")
SCORE_MANUAL = Decimal("50")

LIMIAR_AUTO = Decimal("70")


@dataclass
class ItemConciliavel:
    id: str
    data: Optional[date]
    valor: Decimal
    tipo: str          # D ou C
    descricao: str
    documento: Optional[str] = None
    origem: str = ""


@dataclass
class ParesConciliacao:
    item_contabil: ItemConciliavel
    item_externo: ItemConciliavel
    score: Decimal
    motivo: str
    manual: bool = False


@dataclass
class ResultadoConciliacao:
    pares: list[ParesConciliacao] = field(default_factory=list)
    nao_conciliados_contabil: list[ItemConciliavel] = field(default_factory=list)
    nao_conciliados_externos: list[ItemConciliavel] = field(default_factory=list)
    total_conciliado: Decimal = Decimal("0")
    total_divergente: Decimal = Decimal("0")
    score_geral: Decimal = Decimal("0")
    alertas: list[str] = field(default_factory=list)


def _normalizar_doc(doc: Optional[str]) -> str:
    if not doc:
        return ""
    return re.sub(r"[^0-9a-zA-Z]", "", doc).upper()


def _similar_historico(a: str, b: str) -> float:
    """Jaccard sobre tokens."""
    ta = set(re.findall(r"\w{3,}", a.lower()))
    tb = set(re.findall(r"\w{3,}", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _score_par(contabil: ItemConciliavel, externo: ItemConciliavel) -> tuple[Decimal, str]:
    if contabil.valor != externo.valor:
        diff = abs(contabil.valor - externo.valor)
        pct = diff / contabil.valor if contabil.valor else Decimal("1")
        if pct > Decimal("0.05"):
            return Decimal("0"), "valores muito diferentes"
        return SCORE_VALOR, "valor semelhante (±5%)"

    # Valores iguais — checar data e documento
    doc_a = _normalizar_doc(contabil.documento)
    doc_b = _normalizar_doc(externo.documento)

    if doc_a and doc_b and doc_a == doc_b:
        if contabil.data and externo.data and contabil.data == externo.data:
            return SCORE_PLENO, "valor + data + documento"
        return SCORE_DOC, "valor + documento"

    # Testa similaridade de histórico
    sim = _similar_historico(contabil.descricao, externo.descricao)
    if sim >= 0.5:
        score = SCORE_HISTORICO + Decimal(str(round(sim * 5, 2)))
        return min(score, Decimal("95")), f"valor + histórico ({sim:.0%} similar)"

    # Apenas valor
    return SCORE_VALOR, "somente valor"


def conciliar(
    contabeis: list[ItemConciliavel],
    externos: list[ItemConciliavel],
    janela_dias: int = 5,
) -> ResultadoConciliacao:
    """
    Algoritmo greedy de conciliação:
    1. Ordena candidatos por score decrescente.
    2. Associa o melhor par e remove da pool.
    3. Itens sem par → não conciliados.
    """
    resultado = ResultadoConciliacao()
    usados_externos: set[str] = set()
    usados_contabeis: set[str] = set()

    # Pré-computar candidatos com score
    candidatos: list[tuple[Decimal, str, ItemConciliavel, ItemConciliavel]] = []

    for c in contabeis:
        for e in externos:
            # Filtro rápido por janela de data
            if c.data and e.data:
                delta = abs((c.data - e.data).days)
                if delta > janela_dias:
                    continue
            score, motivo = _score_par(c, e)
            if score > Decimal("0"):
                candidatos.append((score, motivo, c, e))

    # Ordena por score decrescente
    candidatos.sort(key=lambda x: x[0], reverse=True)

    for score, motivo, c, e in candidatos:
        if c.id in usados_contabeis or e.id in usados_externos:
            continue
        par = ParesConciliacao(
            item_contabil=c,
            item_externo=e,
            score=score,
            motivo=motivo,
            manual=score < LIMIAR_AUTO,
        )
        resultado.pares.append(par)
        usados_contabeis.add(c.id)
        usados_externos.add(e.id)

        if score >= LIMIAR_AUTO:
            resultado.total_conciliado += c.valor
        else:
            resultado.total_divergente += c.valor

    resultado.nao_conciliados_contabil = [c for c in contabeis if c.id not in usados_contabeis]
    resultado.nao_conciliados_externos = [e for e in externos if e.id not in usados_externos]

    # Diferenças não identificadas
    for item in resultado.nao_conciliados_contabil:
        resultado.alertas.append(
            f"Lançamento contábil sem correspondência: {item.descricao} | "
            f"R$ {item.valor:,.2f} | {item.data}"
        )
    for item in resultado.nao_conciliados_externos:
        resultado.alertas.append(
            f"Movimento externo sem lançamento: {item.descricao} | "
            f"R$ {item.valor:,.2f} | {item.data}"
        )

    # Score geral
    total = resultado.total_conciliado + resultado.total_divergente + sum(
        i.valor for i in resultado.nao_conciliados_contabil
    )
    if total > 0:
        resultado.score_geral = (resultado.total_conciliado / total * 100).quantize(Decimal("0.01"))

    return resultado


def conciliar_bancario(
    lancamentos_contabeis: list[ItemConciliavel],
    movimentos_extrato: list[ItemConciliavel],
) -> ResultadoConciliacao:
    return conciliar(lancamentos_contabeis, movimentos_extrato, janela_dias=3)


def conciliar_clientes(
    lancamentos: list[ItemConciliavel],
    contas_receber: list[ItemConciliavel],
) -> ResultadoConciliacao:
    return conciliar(lancamentos, contas_receber, janela_dias=10)


def conciliar_fornecedores(
    lancamentos: list[ItemConciliavel],
    contas_pagar: list[ItemConciliavel],
) -> ResultadoConciliacao:
    return conciliar(lancamentos, contas_pagar, janela_dias=10)


def conciliar_tributos(
    lancamentos: list[ItemConciliavel],
    guias: list[ItemConciliavel],
) -> ResultadoConciliacao:
    return conciliar(lancamentos, guias, janela_dias=5)
