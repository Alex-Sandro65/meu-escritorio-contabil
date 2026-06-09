"""
Leitor de extratos bancários: OFX, CSV, PDF.
"""
import re
import io
from decimal import Decimal
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

try:
    from ofxparse import OfxParser
    HAS_OFX = True
except ImportError:
    HAS_OFX = False

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


@dataclass
class MovimentoExtrato:
    data: date
    tipo: str  # D ou C
    valor: Decimal
    descricao: str
    documento: Optional[str] = None
    tipo_transacao: Optional[str] = None
    nome_favorecido: Optional[str] = None
    banco: Optional[str] = None
    agencia: Optional[str] = None
    conta: Optional[str] = None


@dataclass
class ResultadoExtrato:
    sucesso: bool
    movimentos: list[MovimentoExtrato] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    banco: Optional[str] = None
    agencia: Optional[str] = None
    conta: Optional[str] = None
    saldo_inicial: Optional[Decimal] = None
    saldo_final: Optional[Decimal] = None
    formato: str = ""


def importar_extrato_ofx(conteudo: bytes) -> ResultadoExtrato:
    if not HAS_OFX:
        return ResultadoExtrato(sucesso=False, erros=["ofxparse não instalado."])
    try:
        ofx = OfxParser.parse(io.BytesIO(conteudo))
        movimentos = []
        banco = agencia = conta = None

        for account in ofx.account if hasattr(ofx, "account") else [ofx.account]:
            if account is None:
                continue
            banco = getattr(account, "institution", None)
            if banco:
                banco = str(banco.organization) if hasattr(banco, "organization") else None
            agencia = getattr(account, "branch_id", None)
            conta = getattr(account, "account_id", None)

            stmt = getattr(account, "statement", None)
            if not stmt:
                continue

            for t in stmt.transactions:
                tipo = "C" if t.amount >= 0 else "D"
                movimentos.append(MovimentoExtrato(
                    data=t.date.date() if hasattr(t.date, "date") else t.date,
                    tipo=tipo,
                    valor=abs(Decimal(str(t.amount))),
                    descricao=str(t.memo or t.payee or ""),
                    documento=str(t.id or ""),
                    tipo_transacao=str(t.type or ""),
                    banco=banco,
                    agencia=agencia,
                    conta=conta,
                ))

        return ResultadoExtrato(
            sucesso=True,
            movimentos=movimentos,
            banco=banco,
            agencia=agencia,
            conta=conta,
            formato="ofx",
        )
    except Exception as e:
        return ResultadoExtrato(sucesso=False, erros=[f"Erro OFX: {e}"])


def importar_extrato_csv(conteudo: bytes) -> ResultadoExtrato:
    movimentos: list[MovimentoExtrato] = []

    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        for sep in (";", ",", "\t"):
            try:
                df = pd.read_csv(io.BytesIO(conteudo), sep=sep, dtype=str, encoding=encoding)
                if len(df.columns) < 3:
                    continue

                cols = [c.lower().strip() for c in df.columns]

                def find_col(*names):
                    for n in names:
                        for i, c in enumerate(cols):
                            if n in c:
                                return df.columns[i]
                    return None

                col_data = find_col("data", "date", "dt")
                col_desc = find_col("descricao", "desc", "historico", "memo", "detail")
                col_valor = find_col("valor", "value", "amount", "vlr")
                col_tipo = find_col("tipo", "type", "dc", "natureza")

                if not col_data or not col_valor:
                    continue

                for _, row in df.iterrows():
                    try:
                        data_str = str(row[col_data]).strip()
                        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
                            try:
                                dt = datetime.strptime(data_str, fmt).date()
                                break
                            except ValueError:
                                continue
                        else:
                            continue

                        valor_str = str(row[col_valor]).strip().replace(".", "").replace(",", ".")
                        valor = abs(Decimal(valor_str)) if valor_str else Decimal("0")

                        if col_tipo:
                            tipo_raw = str(row[col_tipo]).upper().strip()
                            tipo = "C" if tipo_raw in ("C", "CR", "CREDITO", "CRÉDITO", "+") else "D"
                        else:
                            valor_original = Decimal(valor_str) if valor_str else Decimal("0")
                            tipo = "C" if valor_original >= 0 else "D"

                        desc = str(row[col_desc]).strip() if col_desc else ""
                        movimentos.append(MovimentoExtrato(
                            data=dt,
                            tipo=tipo,
                            valor=valor,
                            descricao=desc,
                        ))
                    except Exception:
                        continue

                if movimentos:
                    return ResultadoExtrato(sucesso=True, movimentos=movimentos, formato="csv")
            except Exception:
                continue

    return ResultadoExtrato(sucesso=False, erros=["Não foi possível interpretar o CSV do extrato."])


def importar_extrato_pdf(conteudo: bytes) -> ResultadoExtrato:
    if not HAS_PDF:
        return ResultadoExtrato(sucesso=False, erros=["pdfplumber não instalado."])

    movimentos: list[MovimentoExtrato] = []
    pattern_data = re.compile(r"\b(\d{2}/\d{2}/\d{4}|\d{2}/\d{2}/\d{2})\b")
    pattern_valor = re.compile(r"-?\d{1,3}(?:\.\d{3})*(?:,\d{2})")

    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            for page in pdf.pages:
                lines = (page.extract_text() or "").splitlines()
                for line in lines:
                    datas = pattern_data.findall(line)
                    valores = pattern_valor.findall(line)
                    if datas and valores:
                        try:
                            for fmt in ("%d/%m/%Y", "%d/%m/%y"):
                                try:
                                    dt = datetime.strptime(datas[0], fmt).date()
                                    break
                                except ValueError:
                                    continue
                            else:
                                continue
                            valor_str = valores[-1].replace(".", "").replace(",", ".")
                            valor = Decimal(valor_str)
                            tipo = "D" if valor < 0 else "C"
                            movimentos.append(MovimentoExtrato(
                                data=dt,
                                tipo=tipo,
                                valor=abs(valor),
                                descricao=line.strip(),
                            ))
                        except Exception:
                            continue
    except Exception as e:
        return ResultadoExtrato(sucesso=False, erros=[f"Erro PDF: {e}"])

    return ResultadoExtrato(sucesso=True, movimentos=movimentos, formato="pdf")
