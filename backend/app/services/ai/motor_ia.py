"""
Motor de IA Contábil — OpenAI GPT-4o especializado em contabilidade brasileira.

Funções:
- Detectar lançamentos atípicos
- Sugerir classificações
- Alertar divergências
- Detectar possíveis fraudes
- Gerar análises narrativas
"""
from typing import Optional
from decimal import Decimal
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """Você é um especialista em contabilidade brasileira com 20 anos de experiência.
Seu papel é analisar dados contábeis, identificar inconsistências, sugerir classificações e detectar possíveis irregularidades.

Conhecimentos especializados:
- NBC TG (normas contábeis brasileiras)
- SPED ECD e ECF
- Regime tributário: Simples Nacional, Lucro Presumido, Lucro Real
- Auditoria independente (NBC TA)
- Análise de balanço patrimonial, DRE, DFC, DMPL
- Conciliação contábil e bancária

Sempre responda em português do Brasil. Seja direto, técnico e objetivo.
Quando identificar algo suspeito, explique claramente o motivo."""


async def analisar_lancamento_atipico(
    conta: str,
    descricao_conta: str,
    valor: Decimal,
    historico: str,
    media_lancamentos: Decimal,
    desvio_padrao: Decimal,
) -> dict:
    """Analisa se um lançamento é atípico e explica o motivo."""
    desvios = float((valor - media_lancamentos) / desvio_padrao) if desvio_padrao else 0

    prompt = f"""Analise o seguinte lançamento contábil:

Conta: {conta} — {descricao_conta}
Valor: R$ {valor:,.2f}
Histórico: {historico}
Média da conta: R$ {media_lancamentos:,.2f}
Desvio padrão: R$ {desvio_padrao:,.2f}
Desvios da média: {desvios:.1f}σ

Este lançamento é atípico? Quais são os riscos? Existe indício de erro ou fraude?
Responda em JSON: {{"atipico": bool, "nivel_risco": "baixo|medio|alto", "motivo": "...", "recomendacao": "..."}}"""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300,
        )
        import json
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "atipico": abs(desvios) > 3,
            "nivel_risco": "alto" if abs(desvios) > 3 else "baixo",
            "motivo": f"Análise automática: {desvios:.1f}σ acima da média",
            "recomendacao": "Verificar documentação de suporte",
        }


async def analisar_diferenca_bancaria(
    conta: str,
    banco: str,
    saldo_contabil: Decimal,
    saldo_extrato: Decimal,
    diferenca: Decimal,
    movimentos_nao_conciliados: list[dict],
) -> str:
    """Gera análise narrativa de diferença bancária."""
    prompt = f"""Analise a seguinte diferença de conciliação bancária:

Conta contábil: {conta}
Banco: {banco}
Saldo contábil: R$ {saldo_contabil:,.2f}
Saldo do extrato: R$ {saldo_extrato:,.2f}
Diferença: R$ {diferenca:,.2f}

Movimentos não conciliados ({len(movimentos_nao_conciliados)}):
{_formatar_movimentos(movimentos_nao_conciliados[:10])}

Explique as possíveis causas desta diferença e sugira os próximos passos para resolução.
Use no máximo 3 parágrafos."""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception as e:
        return (
            f"Diferença de R$ {diferenca:,.2f} identificada entre saldo contábil e extrato bancário. "
            f"Existem {len(movimentos_nao_conciliados)} movimentos não conciliados. "
            "Recomenda-se verificar depósitos em trânsito, cheques emitidos e não compensados."
        )


async def sugerir_classificacao_conta(
    codigo: str,
    descricao: str,
    historico_lancamentos: list[str],
) -> dict:
    """Sugere natureza e grupo contábil com base em IA."""
    prompt = f"""Classifique a conta contábil abaixo conforme as normas brasileiras (CFC/CVM):

Código: {codigo}
Descrição: {descricao}
Exemplos de históricos:
{chr(10).join(f'- {h}' for h in historico_lancamentos[:5])}

Responda em JSON:
{{"natureza": "ativo|passivo|patrimonio_liquido|receita|custo|despesa|resultado",
  "grupo": "ativo_circulante|ativo_nao_circulante|...",
  "dre": bool,
  "balanco": bool,
  "confianca": 0.0-1.0,
  "justificativa": "..."}}"""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300,
        )
        import json
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"natureza": "ativo", "grupo": "ativo_circulante", "confianca": 0.3,
                "justificativa": "Classificação padrão (IA indisponível)"}


async def gerar_analise_balancete(dados_resumo: dict) -> str:
    """Gera análise executiva do balancete."""
    prompt = f"""Analise o seguinte balancete consolidado e gere um parecer executivo:

Competência: {dados_resumo.get('competencia')}
Total de contas: {dados_resumo.get('total_contas')}
Contas conciliadas: {dados_resumo.get('contas_conciliadas')} ({dados_resumo.get('pct_conciliado', 0):.1f}%)
Diferenças encontradas: R$ {dados_resumo.get('total_diferencas', 0):,.2f}
Contas com alerta: {dados_resumo.get('contas_alerta')}

Top divergências:
{_formatar_divergencias(dados_resumo.get('top_divergencias', []))}

Gere um relatório executivo de 3 parágrafos: situação geral, pontos de atenção e recomendações."""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content
    except Exception as e:
        return "Análise indisponível. Verifique a chave de API da OpenAI."


async def detectar_fraude(lancamentos: list[dict]) -> list[dict]:
    """Analisa lote de lançamentos em busca de padrões suspeitos."""
    alertas = []

    # Regras determinísticas rápidas
    valores_vistos: dict[str, int] = {}
    for l in lancamentos:
        v = str(l.get("valor", ""))
        valores_vistos[v] = valores_vistos.get(v, 0) + 1

    for l in lancamentos:
        alertas_item = []
        valor = Decimal(str(l.get("valor", 0)))

        # Valores redondos suspeitos acima de 10k
        if valor > 10000 and valor % 1000 == 0:
            alertas_item.append("Valor redondo acima de R$ 10.000")

        # Valor abaixo do limiar de comunicação ao COAF (R$ 2.000 caixa)
        if l.get("conta", "").startswith("1.1.01") and valor == Decimal("1999"):
            alertas_item.append("Possível fracionamento — valor próximo ao limite COAF (R$ 2.000)")

        # Duplicidade exata
        if valores_vistos.get(str(valor), 0) > 3:
            alertas_item.append(f"Valor R$ {valor:,.2f} repetido {valores_vistos[str(valor)]}x")

        if alertas_item:
            alertas.append({**l, "alertas_fraude": alertas_item, "nivel_risco": "alto"})

    return alertas


def _formatar_movimentos(movimentos: list[dict]) -> str:
    linhas = []
    for m in movimentos:
        linhas.append(f"  {m.get('data')} | {m.get('descricao')} | R$ {m.get('valor', 0):,.2f}")
    return "\n".join(linhas) or "  (nenhum)"


def _formatar_divergencias(divergencias: list[dict]) -> str:
    linhas = []
    for d in divergencias:
        linhas.append(f"  {d.get('conta')} {d.get('descricao')} — R$ {d.get('diferenca', 0):,.2f}")
    return "\n".join(linhas) or "  (nenhuma)"
