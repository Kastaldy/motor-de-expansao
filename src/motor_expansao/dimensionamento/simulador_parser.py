"""Parser da estrutura parametrica do simulador financeiro Ultra (BLK-DIM).

Le SO metadado (mapeamento celula->driver, valores default de premissa, ratios %)
do `.xlsx` real e serializa em `data/staging/simulador_estrutura.json` (D2:
COMMITABLE). NAO ha PII de aluno nem dado financeiro real de unidade. Celulas que
sao formula (J9, R9) tem a string registrada em `formula` e `valor_default=None`.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl

XLSX_DEFAULT = Path("data/ultra/ULTRA padrão   - Simulador Financeiro (1).xlsx")

# Drivers da aba `Simulador` (celula -> metadado), verificados celula a celula
# contra o arquivo real (handoff §C).
_DRIVERS_SIMULADOR: list[dict[str, Any]] = [
    {"driver": "alunos_inicial", "celula": "E9", "unidade": "alunos", "natureza": "demanda"},
    {"driver": "alunos_balcao_maturidade", "celula": "E10", "unidade": "alunos", "natureza": "demanda"},
    {"driver": "alunos_agregadores_maturidade", "celula": "E11", "unidade": "alunos", "natureza": "demanda"},
    {"driver": "churn", "celula": "E12", "unidade": "fracao", "natureza": "premissa"},
    {"driver": "maturacao_meses", "celula": "E13", "unidade": "meses", "natureza": "premissa"},
    {"driver": "mensalidade", "celula": "J9", "unidade": "reais", "natureza": "premissa"},
    {"driver": "manutencao_anuidade", "celula": "J10", "unidade": "reais", "natureza": "premissa"},
    {"driver": "matricula", "celula": "J11", "unidade": "reais", "natureza": "premissa"},
    {"driver": "mes_inicio_cobranca_taxas", "celula": "J12", "unidade": "mes", "natureza": "premissa"},
    {"driver": "aluguel_mes", "celula": "N9", "unidade": "reais", "natureza": "fisico"},
    {"driver": "carencia_aluguel_meses", "celula": "N10", "unidade": "meses", "natureza": "premissa"},
    {"driver": "royalties_pct", "celula": "N11", "unidade": "fracao", "natureza": "contrato"},
    {"driver": "cenario_estudios", "celula": "N12", "unidade": "indice", "natureza": "premissa"},
    {"driver": "capex_total", "celula": "R9", "unidade": "reais", "natureza": "fisico"},
    {"driver": "taxa_franquia", "celula": "R10", "unidade": "reais", "natureza": "contrato"},
    {"driver": "multiplo_valuation", "celula": "R11", "unidade": "multiplo", "natureza": "premissa"},
    {"driver": "regime_tributario", "celula": "R12", "unidade": "texto", "natureza": "premissa"},
    {"driver": "escolha_cenario", "celula": "G7", "unidade": "indice", "natureza": "toggle"},
    {"driver": "toggle_financiamento", "celula": "I7", "unidade": "indice", "natureza": "toggle"},
]

# Ratios de custo (aba DRE): % na celula F da linha imediatamente abaixo do rotulo.
_RATIOS_DRE: list[dict[str, Any]] = [
    {"driver": "devolucoes_pct_receita", "celula": "F30", "natureza": "ratio"},
    {"driver": "royalties_pct_receita", "celula": "F61", "natureza": "ratio"},
    {"driver": "marketing_pct_receita", "celula": "F63", "natureza": "ratio"},
    {"driver": "manutencao_pct_receita", "celula": "F67", "natureza": "ratio"},
    {"driver": "cartoes_pct_receita", "celula": "F79", "natureza": "ratio"},
]

# Impostos do regime LUCRO PRESUMIDO (aba Tributos).
_IMPOSTOS_PRESUMIDO: list[dict[str, Any]] = [
    {"driver": "pis", "celula": "E38", "natureza": "imposto"},
    {"driver": "cofins", "celula": "E40", "natureza": "imposto"},
    {"driver": "iss", "celula": "E42", "natureza": "imposto"},
    {"driver": "ir_aliquota", "celula": "E44", "natureza": "imposto"},
    {"driver": "csll_aliquota", "celula": "E46", "natureza": "imposto"},
]


def _ler_celula(ws, celula: str) -> tuple[Any, str | None]:
    """Retorna `(valor_default, formula)`. Se for formula, valor_default=None."""
    raw = ws[celula].value
    if isinstance(raw, str) and raw.startswith("="):
        return None, raw
    return raw, None


def _entradas(ws, specs: list[dict[str, Any]], aba: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for spec in specs:
        valor, formula = _ler_celula(ws, spec["celula"])
        out[spec["driver"]] = {
            "aba": aba,
            "celula": spec["celula"],
            "valor_default": valor,
            "formula": formula,
            "unidade": spec.get("unidade"),
            "natureza": spec["natureza"],
        }
    return out


def parse_simulador(xlsx_path: str | Path = XLSX_DEFAULT) -> dict:
    """Parseia o `.xlsx` e retorna a estrutura parametrica (metadado, sem PII)."""
    wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=False)
    try:
        sim = wb["Simulador"]
        dre = wb["DRE"]
        trib = wb["Tributos"]
        estrutura: dict[str, Any] = {
            "fonte": Path(xlsx_path).name,
            "regime_tributario": "presumido",
            "drivers": _entradas(sim, _DRIVERS_SIMULADOR, "Simulador"),
            "ratios_dre": _entradas(dre, _RATIOS_DRE, "DRE"),
            "impostos_presumido": _entradas(trib, _IMPOSTOS_PRESUMIDO, "Tributos"),
        }
    finally:
        wb.close()
    return estrutura
