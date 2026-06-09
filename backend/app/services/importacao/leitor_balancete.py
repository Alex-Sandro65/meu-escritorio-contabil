"""
Leitor universal de balancetes contábeis.
Suporta Excel (.xls/.xlsx), CSV, TXT (SPED) e PDF via OCR.
"""
import re
import io
from decimal import Decimal, InvalidOperation
from typing import Optional
import pandas as pd
import pdfplumber
from dataclasses import dataclass, field


@dataclass
class ContaImportada:
    codigo: str
    descricao: str
    nivel: int
    saldo_anterior: Decimal = Decimal("0")
    debitos: Decimal = Decimal("0")
    creditos: Decimal = Decimal("0")
    saldo_atual: Decimal = Decimal("0")
    natureza_raw: str = ""


@dataclass
class ResultadoImportacao:
    sucesso: bool
    contas: list[ContaImportada] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    formato_detectado: str = ""
    total_linhas: int = 0
    metadados: dict = field(default_factory=dict)


COLUNAS_BALANCETE = {
    "codigo": ["codigo", "cod", "conta", "code", "cód", "código"],
    "descricao": ["descricao", "desc", "historico", "nome", "description", "descrição"],
    "saldo_anterior": ["saldo_anterior", "saldo ant", "sd anterior", "sal ant", "saldo_ini"],
    "debitos": ["debitos", "débitos", "debit", "debito", "déb"],
    "creditos": ["creditos", "créditos", "credit", "credito", "créd"],
    "saldo_atual": ["saldo_atual", "saldo atual", "saldo", "balance", "sd atual", "saldo_fin"],
}


def _parse_valor(v) -> Decimal:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return Decimal("0")
    s = str(v).strip()
    s = re.sub(r"[^\d,.\-]", "", s)
    # Normaliza separadores: 1.234.567,89 → 1234567.89
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s) if s else Decimal("0")
    except InvalidOperation:
        return Decimal("0")


def _detectar_nivel(codigo: str) -> int:
    partes = re.split(r"[.\-_]", codigo.strip())
    return len([p for p in partes if p])


def _mapear_coluna(colunas_df: list[str], candidatos: list[str]) -> Optional[str]:
    for col in colunas_df:
        col_lower = col.lower().strip()
        if col_lower in candidatos:
            return col
    for col in colunas_df:
        col_lower = col.lower().strip()
        for c in candidatos:
            if c in col_lower:
                return col
    return None


def importar_balancete_excel(conteudo: bytes, nome_arquivo: str) -> ResultadoImportacao:
    try:
        df = pd.read_excel(io.BytesIO(conteudo), dtype=str)
    except Exception as e:
        return ResultadoImportacao(sucesso=False, erros=[f"Erro ao abrir Excel: {e}"])

    return _processar_dataframe(df, "excel")


def importar_balancete_csv(conteudo: bytes) -> ResultadoImportacao:
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        for sep in (";", ",", "\t", "|"):
            try:
                df = pd.read_csv(io.BytesIO(conteudo), sep=sep, dtype=str, encoding=encoding)
                if len(df.columns) >= 3:
                    return _processar_dataframe(df, "csv")
            except Exception:
                continue
    return ResultadoImportacao(sucesso=False, erros=["Não foi possível interpretar o CSV."])


def importar_balancete_sped(conteudo: bytes) -> ResultadoImportacao:
    """Lê o bloco I do SPED ECD (registros I050, I052, I150, I155)."""
    contas: list[ContaImportada] = []
    erros: list[str] = []
    linhas = conteudo.decode("latin-1", errors="replace").splitlines()

    plano: dict[str, dict] = {}
    saldos: dict[str, dict] = {}

    for linha in linhas:
        campos = linha.strip().strip("|").split("|")
        if not campos:
            continue
        reg = campos[0] if campos else ""

        if reg == "I050" and len(campos) >= 6:
            cod = campos[3].strip()
            plano[cod] = {
                "codigo": cod,
                "descricao": campos[5].strip() if len(campos) > 5 else cod,
                "nivel": int(campos[2]) if campos[2].isdigit() else 1,
            }

        elif reg == "I150" and len(campos) >= 4:
            cod = campos[1].strip()
            saldos[cod] = {
                "saldo_anterior": _parse_valor(campos[2]) if len(campos) > 2 else Decimal("0"),
                "saldo_atual": _parse_valor(campos[3]) if len(campos) > 3 else Decimal("0"),
            }

        elif reg == "I155" and len(campos) >= 4:
            cod = campos[1].strip()
            if cod not in saldos:
                saldos[cod] = {}
            saldos[cod]["debitos"] = _parse_valor(campos[2]) if len(campos) > 2 else Decimal("0")
            saldos[cod]["creditos"] = _parse_valor(campos[3]) if len(campos) > 3 else Decimal("0")

    for cod, info in plano.items():
        sal = saldos.get(cod, {})
        contas.append(ContaImportada(
            codigo=info["codigo"],
            descricao=info["descricao"],
            nivel=info["nivel"],
            saldo_anterior=sal.get("saldo_anterior", Decimal("0")),
            debitos=sal.get("debitos", Decimal("0")),
            creditos=sal.get("creditos", Decimal("0")),
            saldo_atual=sal.get("saldo_atual", Decimal("0")),
        ))

    return ResultadoImportacao(
        sucesso=True,
        contas=contas,
        formato_detectado="sped_ecd",
        total_linhas=len(linhas),
        metadados={"total_contas_plano": len(plano)},
    )


def importar_balancete_pdf(conteudo: bytes) -> ResultadoImportacao:
    """Extrai tabelas de balancete de PDF via pdfplumber."""
    contas: list[ContaImportada] = []
    erros: list[str] = []

    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header = [str(c).lower().strip() if c else "" for c in table[0]]
                    for row in table[1:]:
                        if not row or not row[0]:
                            continue
                        cod = str(row[0]).strip()
                        if not re.match(r"^\d", cod):
                            continue
                        desc = str(row[1]).strip() if len(row) > 1 else ""
                        vals = [_parse_valor(row[i]) if i < len(row) else Decimal("0") for i in range(2, 6)]
                        contas.append(ContaImportada(
                            codigo=cod,
                            descricao=desc,
                            nivel=_detectar_nivel(cod),
                            saldo_anterior=vals[0] if vals else Decimal("0"),
                            debitos=vals[1] if len(vals) > 1 else Decimal("0"),
                            creditos=vals[2] if len(vals) > 2 else Decimal("0"),
                            saldo_atual=vals[3] if len(vals) > 3 else Decimal("0"),
                        ))
    except Exception as e:
        return ResultadoImportacao(sucesso=False, erros=[f"Erro ao ler PDF: {e}"])

    return ResultadoImportacao(
        sucesso=True,
        contas=contas,
        formato_detectado="pdf",
        total_linhas=len(contas),
    )


def _processar_dataframe(df: pd.DataFrame, formato: str) -> ResultadoImportacao:
    contas: list[ContaImportada] = []
    erros: list[str] = []
    avisos: list[str] = []

    cols = list(df.columns)

    col_codigo = _mapear_coluna(cols, COLUNAS_BALANCETE["codigo"])
    col_descricao = _mapear_coluna(cols, COLUNAS_BALANCETE["descricao"])
    col_saldo_ant = _mapear_coluna(cols, COLUNAS_BALANCETE["saldo_anterior"])
    col_debitos = _mapear_coluna(cols, COLUNAS_BALANCETE["debitos"])
    col_creditos = _mapear_coluna(cols, COLUNAS_BALANCETE["creditos"])
    col_saldo_atual = _mapear_coluna(cols, COLUNAS_BALANCETE["saldo_atual"])

    if not col_codigo:
        return ResultadoImportacao(
            sucesso=False,
            erros=["Coluna de código contábil não encontrada."],
            metadados={"colunas_encontradas": cols},
        )

    for idx, row in df.iterrows():
        codigo = str(row.get(col_codigo, "")).strip()
        if not codigo or not re.match(r"^\d", codigo):
            continue

        descricao = str(row.get(col_descricao, codigo)).strip() if col_descricao else codigo
        conta = ContaImportada(
            codigo=codigo,
            descricao=descricao,
            nivel=_detectar_nivel(codigo),
            saldo_anterior=_parse_valor(row.get(col_saldo_ant)) if col_saldo_ant else Decimal("0"),
            debitos=_parse_valor(row.get(col_debitos)) if col_debitos else Decimal("0"),
            creditos=_parse_valor(row.get(col_creditos)) if col_creditos else Decimal("0"),
            saldo_atual=_parse_valor(row.get(col_saldo_atual)) if col_saldo_atual else Decimal("0"),
        )
        contas.append(conta)

    return ResultadoImportacao(
        sucesso=True,
        contas=contas,
        erros=erros,
        avisos=avisos,
        formato_detectado=formato,
        total_linhas=len(df),
        metadados={"colunas_mapeadas": {
            "codigo": col_codigo,
            "descricao": col_descricao,
            "debitos": col_debitos,
            "creditos": col_creditos,
            "saldo_atual": col_saldo_atual,
        }},
    )
