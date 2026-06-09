"""
Gerador automático de Papéis de Trabalho de Auditoria.
Produz: composição de saldos, análise horizontal/vertical, índices, materialidade.
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ComposicaoSaldo:
    conta: str
    descricao: str
    saldo: Decimal
    itens: list[dict] = field(default_factory=list)
    diferenca: Decimal = Decimal("0")
    score: Decimal = Decimal("0")
    responsavel: str = ""
    status: str = "pendente"


@dataclass
class AnaliseHorizontal:
    conta: str
    descricao: str
    valor_atual: Decimal
    valor_anterior: Decimal
    variacao_absoluta: Decimal
    variacao_percentual: Decimal
    alerta: bool = False


@dataclass
class AnaliseVertical:
    conta: str
    descricao: str
    valor: Decimal
    base: Decimal
    percentual: Decimal
    grupo: str = ""


@dataclass
class IndiceFinanceiro:
    nome: str
    formula: str
    valor: Decimal
    referencia: str
    status: str  # bom, atencao, critico
    interpretacao: str


@dataclass
class Materialidade:
    base_calculo: str
    valor_base: Decimal
    percentual_aplicado: Decimal
    materialidade_geral: Decimal
    materialidade_execucao: Decimal
    materialidade_trivial: Decimal


def calcular_materialidade(
    receita_bruta: Optional[Decimal] = None,
    ativo_total: Optional[Decimal] = None,
    lucro_antes_ir: Optional[Decimal] = None,
    patrimonio_liquido: Optional[Decimal] = None,
) -> Materialidade:
    """NBC TA 320 — materialidade baseada em benchmarks."""
    candidatos = []
    if receita_bruta and receita_bruta > 0:
        candidatos.append(("Receita Bruta", receita_bruta, Decimal("0.005")))
    if ativo_total and ativo_total > 0:
        candidatos.append(("Ativo Total", ativo_total, Decimal("0.01")))
    if patrimonio_liquido and patrimonio_liquido > 0:
        candidatos.append(("Patrimônio Líquido", patrimonio_liquido, Decimal("0.05")))
    if lucro_antes_ir and lucro_antes_ir > 0:
        candidatos.append(("Lucro Antes do IR", lucro_antes_ir, Decimal("0.05")))

    if not candidatos:
        return Materialidade(
            base_calculo="N/A",
            valor_base=Decimal("0"),
            percentual_aplicado=Decimal("0"),
            materialidade_geral=Decimal("0"),
            materialidade_execucao=Decimal("0"),
            materialidade_trivial=Decimal("0"),
        )

    # Escolhe a base com maior materialidade calculada
    melhor = max(candidatos, key=lambda x: x[1] * x[2])
    base_nome, valor_base, pct = melhor
    mat_geral = (valor_base * pct).quantize(Decimal("0.01"))

    return Materialidade(
        base_calculo=base_nome,
        valor_base=valor_base,
        percentual_aplicado=pct * 100,
        materialidade_geral=mat_geral,
        materialidade_execucao=(mat_geral * Decimal("0.75")).quantize(Decimal("0.01")),
        materialidade_trivial=(mat_geral * Decimal("0.05")).quantize(Decimal("0.01")),
    )


def calcular_analise_horizontal(
    contas_atual: list[dict],
    contas_anterior: list[dict],
) -> list[AnaliseHorizontal]:
    """Compara dois períodos e calcula variações."""
    mapa_anterior = {c["codigo"]: Decimal(str(c.get("saldo_atual", 0))) for c in contas_anterior}
    resultado = []

    for conta in contas_atual:
        codigo = conta["codigo"]
        valor_atual = Decimal(str(conta.get("saldo_atual", 0)))
        valor_anterior = mapa_anterior.get(codigo, Decimal("0"))
        variacao_abs = valor_atual - valor_anterior
        variacao_pct = (
            (variacao_abs / valor_anterior * 100).quantize(Decimal("0.01"))
            if valor_anterior != 0 else Decimal("0")
        )

        resultado.append(AnaliseHorizontal(
            conta=codigo,
            descricao=conta.get("descricao", ""),
            valor_atual=valor_atual,
            valor_anterior=valor_anterior,
            variacao_absoluta=variacao_abs,
            variacao_percentual=variacao_pct,
            alerta=abs(variacao_pct) > 50 and abs(variacao_abs) > 10000,
        ))

    return resultado


def calcular_analise_vertical(
    contas: list[dict],
    base_ativo: Decimal,
    base_receita: Decimal,
) -> list[AnaliseVertical]:
    """Percentual de cada conta sobre a base (ativo total ou receita)."""
    resultado = []
    for conta in contas:
        codigo = conta["codigo"]
        valor = Decimal(str(conta.get("saldo_atual", 0)))
        natureza = conta.get("natureza", "")

        if natureza in ("receita", "custo", "despesa", "resultado") and base_receita > 0:
            base = base_receita
            grupo = "dre"
        elif base_ativo > 0:
            base = base_ativo
            grupo = "balanco"
        else:
            continue

        pct = (valor / base * 100).quantize(Decimal("0.01")) if base else Decimal("0")
        resultado.append(AnaliseVertical(
            conta=codigo,
            descricao=conta.get("descricao", ""),
            valor=valor,
            base=base,
            percentual=pct,
            grupo=grupo,
        ))

    return resultado


def calcular_indices(
    ativo_circulante: Decimal,
    passivo_circulante: Decimal,
    ativo_total: Decimal,
    passivo_total: Decimal,
    patrimonio_liquido: Decimal,
    receita_liquida: Decimal,
    lucro_bruto: Decimal,
    lucro_liquido: Decimal,
    estoque: Decimal = Decimal("0"),
    disponivel: Decimal = Decimal("0"),
) -> list[IndiceFinanceiro]:
    def safe_div(a: Decimal, b: Decimal) -> Decimal:
        return (a / b).quantize(Decimal("0.0001")) if b != 0 else Decimal("0")

    indices = []

    # Liquidez
    lc = safe_div(ativo_circulante, passivo_circulante)
    indices.append(IndiceFinanceiro(
        nome="Liquidez Corrente",
        formula="AC / PC",
        valor=lc,
        referencia="≥ 1,50",
        status="bom" if lc >= Decimal("1.5") else "atencao" if lc >= Decimal("1.0") else "critico",
        interpretacao=f"Para cada R$ 1,00 de dívida circulante, há R$ {lc:,.2f} de ativo circulante.",
    ))

    ls = safe_div(ativo_circulante - estoque, passivo_circulante)
    indices.append(IndiceFinanceiro(
        nome="Liquidez Seca",
        formula="(AC - Estoques) / PC",
        valor=ls,
        referencia="≥ 1,00",
        status="bom" if ls >= Decimal("1.0") else "atencao" if ls >= Decimal("0.8") else "critico",
        interpretacao=f"Liquidez sem dependência de estoque: R$ {ls:,.2f}.",
    ))

    li = safe_div(disponivel, passivo_circulante)
    indices.append(IndiceFinanceiro(
        nome="Liquidez Imediata",
        formula="Disponível / PC",
        valor=li,
        referencia="≥ 0,20",
        status="bom" if li >= Decimal("0.2") else "atencao" if li >= Decimal("0.1") else "critico",
        interpretacao=f"Caixa imediato representa {li * 100:,.1f}% das obrigações circulantes.",
    ))

    # Endividamento
    et = safe_div(passivo_total, ativo_total)
    indices.append(IndiceFinanceiro(
        nome="Endividamento Total",
        formula="PT / AT",
        valor=et,
        referencia="≤ 0,60",
        status="bom" if et <= Decimal("0.5") else "atencao" if et <= Decimal("0.7") else "critico",
        interpretacao=f"{et * 100:,.1f}% dos ativos são financiados por terceiros.",
    ))

    # Rentabilidade
    mbr = safe_div(lucro_bruto, receita_liquida)
    indices.append(IndiceFinanceiro(
        nome="Margem Bruta",
        formula="Lucro Bruto / Receita Líquida",
        valor=mbr,
        referencia="Depende do setor",
        status="bom" if mbr >= Decimal("0.3") else "atencao" if mbr >= Decimal("0.15") else "critico",
        interpretacao=f"Margem bruta de {mbr * 100:,.1f}%.",
    ))

    ml = safe_div(lucro_liquido, receita_liquida)
    indices.append(IndiceFinanceiro(
        nome="Margem Líquida",
        formula="Lucro Líquido / Receita Líquida",
        valor=ml,
        referencia="Depende do setor",
        status="bom" if ml >= Decimal("0.1") else "atencao" if ml >= Decimal("0.05") else "critico",
        interpretacao=f"Margem líquida de {ml * 100:,.1f}%.",
    ))

    roe = safe_div(lucro_liquido, patrimonio_liquido)
    indices.append(IndiceFinanceiro(
        nome="Retorno sobre PL (ROE)",
        formula="Lucro Líquido / PL",
        valor=roe,
        referencia="≥ 15% a.a.",
        status="bom" if roe >= Decimal("0.15") else "atencao" if roe >= Decimal("0.08") else "critico",
        interpretacao=f"Retorno de {roe * 100:,.1f}% sobre o capital dos sócios.",
    ))

    return indices
