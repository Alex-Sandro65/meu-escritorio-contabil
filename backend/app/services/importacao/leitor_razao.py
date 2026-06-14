"""
Leitor de Razão Contábil (Livro Razão / General Ledger).

Importa lançamentos individuais a partir de Excel (.xlsx/.xls) ou CSV.

Formatos suportados:
  - Exportações genéricas: colunas Data, Conta, Débito, Crédito, Histórico, Documento
  - SCI Único, Omie, Conta Azul (auto-detectado pelas colunas)
  - SPED ECD registros I100/I150 (simplificado)

Resultado: lista de LancamentoRazao prontos para persistir como Lancamento.
"""
import re
import io
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LancamentoRazao:
    data: date
    conta: str           # código da conta ex: 1.1.01.001
    tipo: str            # "D" ou "C"
    valor: Decimal
    historico: str = ""
    documento: Optional[str] = None
    complemento: Optional[str] = None


@dataclass
class ResultadoRazao:
    sucesso: bool
    lancamentos: list[LancamentoRazao] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    total_debitos: Decimal = Decimal("0")
    total_creditos: Decimal = Decimal("0")
    formato_detectado: str = ""
    empresa_nome: Optional[str] = None
    competencia: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def _parse_valor(v) -> Decimal:
    """Converte strings como '1.234,56' ou '1234.56' para Decimal."""
    if v is None or str(v).strip() in ("", "nan", "NaN", "None", "-"):
        return Decimal("0")
    s = str(v).strip()
    # Remove símbolos comuns
    s = s.replace("R$", "").replace(" ", "").replace("\xa0", "")
    # Detecta formato brasileiro: 1.234,56
    if re.match(r"^\d{1,3}(\.\d{3})*(,\d+)?$", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        # Remove pontos de milhar americano (1,234.56)
        s = re.sub(r",(?=\d{3}(\.|$))", "", s)
        s = s.replace(",", ".")
    # Remove parênteses (valor negativo)
    negativo = s.startswith("(") and s.endswith(")")
    s = s.replace("(", "").replace(")", "")
    try:
        v = Decimal(s) if s else Decimal("0")
        return -v if negativo else v
    except InvalidOperation:
        return Decimal("0")


def _parse_data(v) -> Optional[date]:
    """Tenta vários formatos de data."""
    if v is None or str(v).strip() in ("", "nan", "NaN", "None"):
        return None
    if isinstance(v, (date, datetime)):
        return v if isinstance(v, date) else v.date()
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _normalizar_conta(v) -> str:
    if not v:
        return ""
    s = str(v).strip()
    # Remove zeros à esquerda dentro dos segmentos ex: 01.001 → 1.001 (opcional)
    return s


# ─────────────────────────────────────────────────────────────────────────────
# MAPEAMENTO FLEXÍVEL DE COLUNAS
# ─────────────────────────────────────────────────────────────────────────────

# Alias → nome canônico
_ALIAS_COLUNAS = {
    # Data
    "data": "data", "date": "data", "dt": "data", "data lançamento": "data",
    "data_lancamento": "data", "data mov": "data", "data movimento": "data",
    # Conta
    "conta": "conta", "cód. conta": "conta", "cod conta": "conta",
    "código": "conta", "codigo": "conta", "account": "conta",
    "conta contábil": "conta", "conta_contabil": "conta",
    # Débito
    "débito": "debito", "debito": "debito", "debit": "debito",
    "db": "debito", "d": "debito", "valor débito": "debito",
    "valor_debito": "debito", "vl debito": "debito",
    # Crédito
    "crédito": "credito", "credito": "credito", "credit": "credito",
    "cr": "credito", "c": "credito", "valor crédito": "credito",
    "valor_credito": "credito", "vl credito": "credito",
    # Histórico
    "histórico": "historico", "historico": "historico", "history": "historico",
    "descrição": "historico", "descricao": "historico", "description": "historico",
    "memo": "historico", "complemento": "historico", "obs": "historico",
    "observação": "historico", "observacao": "historico",
    # Documento
    "documento": "documento", "doc": "documento", "document": "documento",
    "nf": "documento", "nota fiscal": "documento", "núm. doc": "documento",
    "num doc": "documento", "número documento": "documento",
    # Tipo (D/C em coluna separada)
    "tipo": "tipo", "type": "tipo", "dc": "tipo", "d/c": "tipo",
    # Valor único (quando há só uma coluna de valor + tipo)
    "valor": "valor", "value": "valor", "vl": "valor", "amount": "valor",
}


def _mapear_colunas(cols: list[str]) -> dict:
    """Retorna {canonico: indice_original} para as colunas encontradas."""
    mapa = {}
    for i, c in enumerate(cols):
        chave = str(c).strip().lower()
        canonico = _ALIAS_COLUNAS.get(chave)
        if canonico and canonico not in mapa:
            mapa[canonico] = i
    return mapa


# ─────────────────────────────────────────────────────────────────────────────
# PARSERS
# ─────────────────────────────────────────────────────────────────────────────

def _parse_dataframe(df: pd.DataFrame) -> ResultadoRazao:
    """Converte um DataFrame em ResultadoRazao."""
    # Limpeza
    df = df.dropna(how="all").reset_index(drop=True)
    cols = list(df.columns)
    mapa = _mapear_colunas(cols)

    erros = []
    avisos = []

    # Colunas obrigatórias mínimas
    if "data" not in mapa:
        erros.append("Coluna de data não encontrada. Esperado: 'Data', 'Date' ou 'Dt'.")
    if "conta" not in mapa:
        erros.append("Coluna de conta não encontrada. Esperado: 'Conta', 'Código' ou 'Account'.")
    if "debito" not in mapa and "credito" not in mapa and "valor" not in mapa:
        erros.append("Nenhuma coluna de valor encontrada. Esperado: 'Débito'/'Crédito' ou 'Valor'.")

    if erros:
        return ResultadoRazao(sucesso=False, erros=erros)

    lancamentos = []
    total_deb = Decimal("0")
    total_cred = Decimal("0")
    skipped = 0

    for idx, row in df.iterrows():
        vals = list(row)

        data = _parse_data(vals[mapa["data"]] if "data" in mapa else None)
        if data is None:
            skipped += 1
            continue

        conta = _normalizar_conta(vals[mapa["conta"]] if "conta" in mapa else "")
        if not conta:
            skipped += 1
            continue

        historico = str(vals[mapa["historico"]]).strip() if "historico" in mapa else ""
        historico = "" if historico in ("nan", "None", "NaN") else historico

        documento = str(vals[mapa["documento"]]).strip() if "documento" in mapa else None
        documento = None if documento in ("nan", "None", "NaN", "") else documento

        # Determina tipo e valor
        if "debito" in mapa and "credito" in mapa:
            deb = _parse_valor(vals[mapa["debito"]])
            cred = _parse_valor(vals[mapa["credito"]])
            if deb > 0 and cred == 0:
                tipo, valor = "D", deb
            elif cred > 0 and deb == 0:
                tipo, valor = "C", cred
            elif deb > 0 and cred > 0:
                # Ambos preenchidos — usa diferença
                if deb >= cred:
                    tipo, valor = "D", deb - cred
                else:
                    tipo, valor = "C", cred - deb
            else:
                skipped += 1
                continue
        elif "valor" in mapa:
            val_bruto = _parse_valor(vals[mapa["valor"]])
            if "tipo" in mapa:
                t = str(vals[mapa["tipo"]]).strip().upper()
                tipo = "D" if t in ("D", "DÉBITO", "DEBITO", "DEBIT") else "C"
                valor = abs(val_bruto)
            else:
                # Valor negativo = crédito, positivo = débito (ou inverso)
                if val_bruto >= 0:
                    tipo, valor = "D", val_bruto
                else:
                    tipo, valor = "C", abs(val_bruto)
        else:
            skipped += 1
            continue

        if valor == 0:
            skipped += 1
            continue

        lancamentos.append(LancamentoRazao(
            data=data,
            conta=conta,
            tipo=tipo,
            valor=valor,
            historico=historico,
            documento=documento,
        ))

        if tipo == "D":
            total_deb += valor
        else:
            total_cred += valor

    if skipped > 0:
        avisos.append(f"{skipped} linha(s) ignoradas (sem data, conta ou valor válidos).")

    if not lancamentos:
        return ResultadoRazao(
            sucesso=False,
            erros=["Nenhum lançamento válido encontrado no arquivo."],
            avisos=avisos,
        )

    return ResultadoRazao(
        sucesso=True,
        lancamentos=lancamentos,
        avisos=avisos,
        total_debitos=total_deb,
        total_creditos=total_cred,
        formato_detectado="excel/csv",
    )


def importar_razao_excel(conteudo: bytes, nome_arquivo: str = "") -> ResultadoRazao:
    """Importa Razão Contábil de arquivo Excel (.xlsx / .xls)."""
    try:
        buf = io.BytesIO(conteudo)
        engine = "xlrd" if nome_arquivo.endswith(".xls") else "openpyxl"
        # Tenta várias abas: primeira não vazia
        xl = pd.ExcelFile(buf, engine=engine)
        df = None
        for sheet in xl.sheet_names:
            _df = xl.parse(sheet, header=None)
            _df = _df.dropna(how="all")
            if len(_df) >= 2:
                # Usa primeira linha como header se parece texto
                first_row = _df.iloc[0].fillna("").astype(str).tolist()
                if any(len(c.strip()) > 0 for c in first_row):
                    _df.columns = first_row
                    _df = _df.iloc[1:].reset_index(drop=True)
                df = _df
                break
        if df is None:
            return ResultadoRazao(sucesso=False, erros=["Arquivo Excel vazio ou sem planilhas."])
        return _parse_dataframe(df)
    except Exception as e:
        return ResultadoRazao(sucesso=False, erros=[f"Erro ao ler Excel: {str(e)}"])


def importar_razao_csv(conteudo: bytes) -> ResultadoRazao:
    """Importa Razão Contábil de arquivo CSV."""
    try:
        # Detecta encoding
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                texto = conteudo.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            return ResultadoRazao(sucesso=False, erros=["Encoding do arquivo CSV não reconhecido."])

        # Detecta separador
        primeira = texto.split("\n")[0]
        sep = ";" if primeira.count(";") >= primeira.count(",") else ","

        df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str, encoding_errors="replace")
        return _parse_dataframe(df)
    except Exception as e:
        return ResultadoRazao(sucesso=False, erros=[f"Erro ao ler CSV: {str(e)}"])


def importar_razao_sped(conteudo: bytes) -> ResultadoRazao:
    """
    Importa lançamentos do SPED ECD (registros I100 e I150).
    I100 = Identificação da conta do plano de contas referencial
    I150 = Identificação dos lançamentos
    """
    try:
        texto = conteudo.decode("latin-1", errors="replace")
        linhas = texto.splitlines()

        # Mapa de contas do plano referencial
        plano: dict[str, str] = {}
        lancamentos = []
        total_deb = Decimal("0")
        total_cred = Decimal("0")

        for linha in linhas:
            campos = linha.split("|")
            if len(campos) < 2:
                continue
            registro = campos[1].strip()

            if registro == "I050":
                # |I050|REFERENCIA|IND_CTA|NÍVEL|CÓDIGO|NOME|
                if len(campos) > 5:
                    plano[campos[5].strip()] = campos[6].strip() if len(campos) > 6 else ""

            elif registro == "I150":
                # |I150|DT_INI|DT_FIN|NUM_LCT|DT_LCT|VL_LCT|IND_LCT|...|
                if len(campos) < 8:
                    continue
                try:
                    data_str = campos[4].strip()
                    data = _parse_data(data_str) or _parse_data(campos[2].strip())
                    valor = _parse_valor(campos[6].strip())
                    tipo_raw = campos[7].strip()
                    tipo = "D" if tipo_raw in ("D", "1") else "C"
                    conta = campos[3].strip() if len(campos) > 3 else ""
                    historico = campos[8].strip() if len(campos) > 8 else ""
                    documento = campos[9].strip() if len(campos) > 9 else None
                    if data and conta and valor > 0:
                        lancamentos.append(LancamentoRazao(
                            data=data,
                            conta=conta,
                            tipo=tipo,
                            valor=valor,
                            historico=historico,
                            documento=documento or None,
                        ))
                        if tipo == "D":
                            total_deb += valor
                        else:
                            total_cred += valor
                except Exception:
                    continue

        if not lancamentos:
            return ResultadoRazao(
                sucesso=False,
                erros=["Nenhum lançamento (registro I150) encontrado no SPED ECD."],
            )

        return ResultadoRazao(
            sucesso=True,
            lancamentos=lancamentos,
            total_debitos=total_deb,
            total_creditos=total_cred,
            formato_detectado="SPED ECD",
        )
    except Exception as e:
        return ResultadoRazao(sucesso=False, erros=[f"Erro ao ler SPED ECD: {str(e)}"])
