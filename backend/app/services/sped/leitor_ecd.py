"""
Leitor e validador do SPED ECD (Escrituração Contábil Digital).
Suporta leiautes 10, 11, 12 e 13.
"""
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from decimal import Decimal


@dataclass
class ErroSped:
    registro: str
    linha: int
    campo: str
    mensagem: str
    nivel: str  # erro, aviso


@dataclass
class ResultadoEcd:
    sucesso: bool
    cnpj: str = ""
    razao_social: str = ""
    ano_calendario: int = 0
    data_inicial: str = ""
    data_final: str = ""
    versao_leiaute: str = ""
    total_registros: int = 0
    plano_contas: list[dict] = field(default_factory=list)
    saldos: list[dict] = field(default_factory=list)
    diarios: list[dict] = field(default_factory=list)
    erros: list[ErroSped] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    hash_arquivo: str = ""
    blocos: dict = field(default_factory=dict)


def ler_ecd(conteudo: bytes) -> ResultadoEcd:
    resultado = ResultadoEcd(sucesso=False)
    resultado.hash_arquivo = hashlib.sha256(conteudo).hexdigest()

    try:
        texto = conteudo.decode("latin-1", errors="replace")
    except Exception as e:
        resultado.erros.append(ErroSped("0000", 0, "arquivo", f"Erro de encoding: {e}", "erro"))
        return resultado

    linhas = texto.splitlines()
    resultado.total_registros = len(linhas)
    blocos: dict[str, int] = {}

    for i, linha in enumerate(linhas, 1):
        linha = linha.strip()
        if not linha.startswith("|"):
            continue
        campos = linha.strip("|").split("|")
        if not campos:
            continue
        reg = campos[0]

        # Conta blocos
        bloco = reg[0] if reg else "?"
        blocos[bloco] = blocos.get(bloco, 0) + 1

        # Registro 0000 — abertura
        if reg == "0000" and len(campos) >= 12:
            resultado.versao_leiaute = campos[3]
            resultado.cnpj = campos[7]
            resultado.razao_social = campos[8]
            resultado.data_inicial = campos[4]
            resultado.data_final = campos[5]
            resultado.ano_calendario = int(campos[4][:4]) if len(campos[4]) >= 4 else 0

        # I050 — Plano de contas
        elif reg == "I050" and len(campos) >= 8:
            resultado.plano_contas.append({
                "linha": i,
                "codigo": campos[3],
                "nome": campos[7] if len(campos) > 7 else "",
                "nivel": int(campos[2]) if campos[2].isdigit() else 0,
                "natureza": campos[4] if len(campos) > 4 else "",
                "tipo": campos[6] if len(campos) > 6 else "",
            })

        # I150 — Saldos periódicos
        elif reg == "I150" and len(campos) >= 4:
            resultado.saldos.append({
                "linha": i,
                "codigo_conta": campos[1],
                "saldo_inicial": _parse_valor(campos[2]) if len(campos) > 2 else Decimal("0"),
                "saldo_final": _parse_valor(campos[3]) if len(campos) > 3 else Decimal("0"),
            })

        # I155 — Movimentos
        elif reg == "I155" and len(campos) >= 4:
            resultado.diarios.append({
                "linha": i,
                "codigo_conta": campos[1],
                "debitos": _parse_valor(campos[2]) if len(campos) > 2 else Decimal("0"),
                "creditos": _parse_valor(campos[3]) if len(campos) > 3 else Decimal("0"),
            })

    resultado.blocos = blocos
    resultado.sucesso = True

    # Validações básicas
    _validar_ecd(resultado)

    return resultado


def _validar_ecd(resultado: ResultadoEcd) -> None:
    if not resultado.cnpj:
        resultado.erros.append(ErroSped("0000", 0, "CNPJ", "CNPJ não encontrado no arquivo", "erro"))

    if not resultado.plano_contas:
        resultado.alertas.append("Plano de contas não encontrado (bloco I050)")

    if not resultado.saldos:
        resultado.alertas.append("Saldos iniciais/finais não encontrados (bloco I150)")

    # Verifica equilíbrio débito/crédito
    total_debitos = sum(d["debitos"] for d in resultado.diarios)
    total_creditos = sum(d["creditos"] for d in resultado.diarios)
    diferenca = abs(total_debitos - total_creditos)

    if diferenca > Decimal("0.01"):
        resultado.erros.append(ErroSped(
            "I155", 0, "movimentos",
            f"Partida dobrada desequilibrada: Débitos R$ {total_debitos:,.2f} | "
            f"Créditos R$ {total_creditos:,.2f} | Diferença R$ {diferenca:,.2f}",
            "erro"
        ))

    # Verifica se blocos obrigatórios existem
    blocos_obrigatorios = ["0", "I", "J", "K", "9"]
    for bloco in blocos_obrigatorios:
        if bloco not in resultado.blocos:
            resultado.alertas.append(f"Bloco {bloco} ausente no arquivo ECD")


def _parse_valor(v: str) -> Decimal:
    try:
        return Decimal(v.replace(",", "."))
    except Exception:
        return Decimal("0")
