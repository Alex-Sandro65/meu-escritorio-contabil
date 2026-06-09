"""
Classificador automático de natureza e grupo contábil com base em código e descrição.
Combina regras determinísticas com fallback para IA.
"""
import re
from dataclasses import dataclass
from app.models.plano_contas import NaturezaConta, GrupoContabil, TipoConta


@dataclass
class ClassificacaoConta:
    natureza: NaturezaConta
    grupo: GrupoContabil
    tipo: TipoConta
    aceita_lancamento: bool
    dre: bool
    balanco: bool
    confianca: float  # 0.0 a 1.0
    motivo: str


# Regras baseadas em prefixo de código (CFC padrão BR)
_PREFIXO_NATUREZA: list[tuple[str, NaturezaConta, GrupoContabil]] = [
    ("1.1", NaturezaConta.ATIVO, GrupoContabil.ATIVO_CIRCULANTE),
    ("1.2", NaturezaConta.ATIVO, GrupoContabil.ATIVO_NAO_CIRCULANTE),
    ("1.3", NaturezaConta.ATIVO, GrupoContabil.ATIVO_REALIZAVEL),
    ("1.4", NaturezaConta.ATIVO, GrupoContabil.ATIVO_IMOBILIZADO),
    ("1.5", NaturezaConta.ATIVO, GrupoContabil.ATIVO_INTANGIVEL),
    ("1.", NaturezaConta.ATIVO, GrupoContabil.ATIVO_CIRCULANTE),
    ("2.1", NaturezaConta.PASSIVO, GrupoContabil.PASSIVO_CIRCULANTE),
    ("2.2", NaturezaConta.PASSIVO, GrupoContabil.PASSIVO_NAO_CIRCULANTE),
    ("2.3", NaturezaConta.PATRIMONIO_LIQUIDO, GrupoContabil.PATRIMONIO_LIQUIDO),
    ("2.", NaturezaConta.PASSIVO, GrupoContabil.PASSIVO_CIRCULANTE),
    ("3.", NaturezaConta.RECEITA, GrupoContabil.RECEITA_BRUTA),
    ("4.", NaturezaConta.CUSTO, GrupoContabil.CMV),
    ("5.", NaturezaConta.DESPESA, GrupoContabil.DESPESA_OPERACIONAL),
    ("6.", NaturezaConta.RESULTADO, GrupoContabil.RESULTADO),
    ("7.", NaturezaConta.RECEITA, GrupoContabil.RECEITA_FINANCEIRA),
    ("8.", NaturezaConta.DESPESA, GrupoContabil.DESPESA_FINANCEIRA),
    ("9.", NaturezaConta.RESULTADO, GrupoContabil.RESULTADO),
]

# Palavras-chave na descrição → natureza / grupo
_KEYWORDS: list[tuple[list[str], NaturezaConta, GrupoContabil]] = [
    (["banco", "caixa", "poupança", "aplicação", "investimento", "cdb", "lca", "lci"],
     NaturezaConta.ATIVO, GrupoContabil.ATIVO_CIRCULANTE),
    (["cliente", "duplicata", "contas a receber", "receber"],
     NaturezaConta.ATIVO, GrupoContabil.ATIVO_CIRCULANTE),
    (["estoque", "mercadoria", "produto"],
     NaturezaConta.ATIVO, GrupoContabil.ATIVO_CIRCULANTE),
    (["pis", "cofins", "irpj", "csll", "icms", "iss", "inss", "fgts", "imposto a recuperar",
      "imposto a compensar", "tributo a recuperar"],
     NaturezaConta.ATIVO, GrupoContabil.ATIVO_CIRCULANTE),
    (["imobilizado", "máquina", "equipamento", "veículo", "imóvel", "terreno", "edificação"],
     NaturezaConta.ATIVO, GrupoContabil.ATIVO_IMOBILIZADO),
    (["intangível", "software", "marca", "patente", "goodwill"],
     NaturezaConta.ATIVO, GrupoContabil.ATIVO_INTANGIVEL),
    (["fornecedor", "contas a pagar", "pagar", "duplicata a pagar"],
     NaturezaConta.PASSIVO, GrupoContabil.PASSIVO_CIRCULANTE),
    (["empréstimo", "financiamento", "mútuo"],
     NaturezaConta.PASSIVO, GrupoContabil.PASSIVO_CIRCULANTE),
    (["salário", "folha", "pro-labore", "pró-labore", "férias", "13", "trabalhista", "rescisão"],
     NaturezaConta.PASSIVO, GrupoContabil.PASSIVO_CIRCULANTE),
    (["parcelamento", "refis", "parcelamento fiscal"],
     NaturezaConta.PASSIVO, GrupoContabil.PASSIVO_NAO_CIRCULANTE),
    (["capital", "patrimônio", "reserva", "resultado acumulado", "lucro acumulado",
      "prejuízo acumulado", "ações"],
     NaturezaConta.PATRIMONIO_LIQUIDO, GrupoContabil.PATRIMONIO_LIQUIDO),
    (["receita", "venda", "faturamento", "serviço prestado"],
     NaturezaConta.RECEITA, GrupoContabil.RECEITA_BRUTA),
    (["custo", "cmv", "cpm", "cst"],
     NaturezaConta.CUSTO, GrupoContabil.CMV),
    (["despesa", "gasto", "despesa administrativa", "despesa comercial", "despesa operacional"],
     NaturezaConta.DESPESA, GrupoContabil.DESPESA_OPERACIONAL),
    (["juros", "mora", "multa financeira", "receita financeira"],
     NaturezaConta.RECEITA, GrupoContabil.RECEITA_FINANCEIRA),
    (["juros pagos", "despesa financeira", "variação cambial passiva"],
     NaturezaConta.DESPESA, GrupoContabil.DESPESA_FINANCEIRA),
]

_GRUPOS_DRE = {
    GrupoContabil.RECEITA_BRUTA,
    GrupoContabil.DEDUCOES,
    GrupoContabil.CMV,
    GrupoContabil.DESPESA_OPERACIONAL,
    GrupoContabil.DESPESA_FINANCEIRA,
    GrupoContabil.RECEITA_FINANCEIRA,
    GrupoContabil.RESULTADO,
}


def classificar_conta(codigo: str, descricao: str) -> ClassificacaoConta:
    desc_lower = descricao.lower()
    codigo_norm = codigo.strip()

    # 1. Tenta prefixo de código
    for prefixo, natureza, grupo in _PREFIXO_NATUREZA:
        if codigo_norm.startswith(prefixo):
            return ClassificacaoConta(
                natureza=natureza,
                grupo=grupo,
                tipo=_inferir_tipo(codigo_norm),
                aceita_lancamento=_inferir_tipo(codigo_norm) == TipoConta.ANALITICA,
                dre=grupo in _GRUPOS_DRE,
                balanco=grupo not in _GRUPOS_DRE,
                confianca=0.90,
                motivo=f"Prefixo '{prefixo}' reconhecido",
            )

    # 2. Tenta palavras-chave na descrição
    for keywords, natureza, grupo in _KEYWORDS:
        for kw in keywords:
            if kw in desc_lower:
                return ClassificacaoConta(
                    natureza=natureza,
                    grupo=grupo,
                    tipo=_inferir_tipo(codigo_norm),
                    aceita_lancamento=True,
                    dre=grupo in _GRUPOS_DRE,
                    balanco=grupo not in _GRUPOS_DRE,
                    confianca=0.75,
                    motivo=f"Palavra-chave '{kw}' na descrição",
                )

    # 3. Fallback — ATIVO com baixa confiança
    return ClassificacaoConta(
        natureza=NaturezaConta.ATIVO,
        grupo=GrupoContabil.ATIVO_CIRCULANTE,
        tipo=TipoConta.ANALITICA,
        aceita_lancamento=True,
        dre=False,
        balanco=True,
        confianca=0.30,
        motivo="Classificação padrão (requer revisão)",
    )


def _inferir_tipo(codigo: str) -> TipoConta:
    """Contas com menos pontuações/níveis tendem a ser sintéticas."""
    nivel = len([p for p in re.split(r"[.\-_]", codigo) if p])
    return TipoConta.SINTETICA if nivel <= 2 else TipoConta.ANALITICA
