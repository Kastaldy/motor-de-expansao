"""BLK-VIAB-04-FU: backtest do motor de viabilidade com N MAIOR (Ultra 54 + Eng Corpo 58 = 112).

LEAVE-ONE-OUT sobre as 112 unidades reais, com quebra por rede, para responder:
o motor GENERALIZA entre redes de porte diferente (Eng Corpo vai acima de 3.500 m²)?

READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009): `viabilidade_ponto.py` INTOCADO; demanda entra
SO como premissa explicita (`alunos_total` real); nenhum score/artefato oficial tocado. Relatorio
gitignored em `data/analysis/`. Anti-PII: so contagens/metricas + rotulo de unidade (nao-PII).
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from motor_expansao.dimensionamento.backtest_viabilidade import (  # noqa: E402
    calcular_metricas_agregadas,
    carregar_eng_corpo,
    carregar_ultra,
    rodar_backtest,
)

ULTRA_PARQUET = Path("data/staging/unidades_ultra_performance_hex.parquet")
OUT = Path("data/analysis/viabilidade_backtest_multirede.md")


def _linha(nome: str, m: dict) -> str:
    return (
        f"| {nome} | {m['n']} | {m['mae']:.1f} | {m['mape'] * 100:.1f}% | "
        f"{m['vies']:+.1f} | {m['r2']:.3f} | {m['cobertura_intervalo'] * 100:.1f}% |"
    )


def main() -> None:
    ultra = carregar_ultra(ULTRA_PARQUET)
    ultra["unidade"] = "[Ultra] " + ultra["unidade"].astype(str)
    eng = carregar_eng_corpo()
    eng["unidade"] = "[Eng] " + eng["unidade"].astype(str)

    combinado = pd.concat([ultra, eng], ignore_index=True)
    assert combinado["unidade"].is_unique, "colisao de rotulo de unidade no combinado"

    # Backtest LOO sobre os 112 (cada unidade predita a partir das outras 111).
    res = rodar_backtest(combinado)
    res["rede"] = res["unidade"].str.startswith("[Ultra]").map(
        {True: "ultra", False: "eng_corpo"}
    )
    met_all = calcular_metricas_agregadas(res)
    met_u = calcular_metricas_agregadas(
        res[res["rede"] == "ultra"].reset_index(drop=True)
    )
    met_e = calcular_metricas_agregadas(
        res[res["rede"] == "eng_corpo"].reset_index(drop=True)
    )

    # Referencia: VIAB-04 original = Ultra-only (base=54, LOO sobre 54).
    res_u54 = rodar_backtest(ultra)
    met_u54 = calcular_metricas_agregadas(res_u54)

    # Sub-recorte Eng dentro/fora do envelope Ultra (<=2.800 m²) — teste de extrapolacao.
    eng_res = res[res["rede"] == "eng_corpo"].copy()
    eng_dentro = eng_res[eng_res["metragem"] <= 2800].reset_index(drop=True)
    eng_fora = eng_res[eng_res["metragem"] > 2800].reset_index(drop=True)

    linhas = [
        "# Backtest multi-rede do motor de viabilidade (N=112) — BLK-VIAB-04-FU",
        "",
        f"Data de geração: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Base LOO = Ultra (54) + Engenharia do Corpo (58) = **112 unidades reais** com metragem e "
        "alunos totais. Cada unidade é predita a partir das outras 111 (LEAVE-ONE-OUT). Demanda = "
        "premissa explícita `alunos_total` real (DEC-009); modo coordless; motor INTOCADO.",
        "",
        "## Métricas agregadas (p50 vs real)",
        "",
        "| Recorte | N | MAE | MAPE | Viés | R² | Cobertura [p10,p90] |",
        "|---|--:|--:|--:|--:|--:|--:|",
        _linha("**Todas (112, base 112)**", met_all),
        _linha("Ultra (dentro dos 112)", met_u),
        _linha("Eng Corpo (dentro dos 112)", met_e),
        _linha("_ref:_ Ultra-only (54, base 54)", met_u54),
        "",
        "### Eng Corpo: dentro vs fora do envelope Ultra (<= 2.800 m²)",
        "",
        "| Recorte Eng | N | MAE | MAPE | Viés | R² | Cobertura |",
        "|---|--:|--:|--:|--:|--:|--:|",
        _linha("Eng <= 2.800 m² (interpolação)", calcular_metricas_agregadas(eng_dentro))
        if len(eng_dentro)
        else "| Eng <= 2.800 m² | 0 | n/d | n/d | n/d | n/d | n/d |",
        _linha("Eng > 2.800 m² (extrapolação)", calcular_metricas_agregadas(eng_fora))
        if len(eng_fora)
        else "| Eng > 2.800 m² | 0 | n/d | n/d | n/d | n/d | n/d |",
        "",
        "## Leitura",
        "",
        f"- **N de validação {met_u54['n']} → {met_all['n']}** (mais que dobra ao incluir Eng Corpo).",
        f"- **Generalização cross-rede:** o motor prevê a Eng Corpo com MAPE {met_e['mape'] * 100:.1f}% "
        f"(vs {met_u['mape'] * 100:.1f}% na Ultra dentro dos 112). "
        + (
            "Erro parecido entre redes → generaliza razoavelmente."
            if abs(met_e["mape"] - met_u["mape"]) < 0.10
            else "Erro materialmente pior na Eng → generalização limitada (porte/rede diferente)."
        ),
        f"- **Efeito de ampliar a base na Ultra:** MAPE Ultra {met_u54['mape'] * 100:.1f}% (base 54) "
        f"→ {met_u['mape'] * 100:.1f}% (base 112). "
        + (
            "Incluir Eng ajudou/neutro."
            if met_u["mape"] <= met_u54["mape"] + 0.02
            else "Incluir Eng PIOROU a predição da Ultra (porte diferente contamina a curva)."
        ),
        "",
        "## Caveats honestos",
        "",
        "- **Eng Corpo tem porte diferente** (vai acima de 3.500 m²; Ultra max ~2.800). O recorte "
        "'> 2.800 m²' é extrapolação pura da curva calibrada majoritariamente em porte Ultra.",
        "- **Ticket placeholder** para Eng Corpo (ausente na fonte) — NÃO afeta a métrica de alunos "
        "(vem da curva de densidade); só o aluguel-teto, que já é capacidade interna não validada "
        "contra mercado.",
        "- **N=112 ainda modesto** e demanda revelada em unidades JÁ operando (sobrevivência; DEC-009).",
        "- **READ-ONLY M1:** nenhum score/peso/artefato oficial tocado; `viabilidade_ponto.py` INTOCADO.",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"OK: {OUT}")
    print(
        f"N={met_all['n']} MAPE_all={met_all['mape'] * 100:.1f}% "
        f"MAPE_ultra={met_u['mape'] * 100:.1f}% MAPE_eng={met_e['mape'] * 100:.1f}% "
        f"R2_all={met_all['r2']:.3f}"
    )


if __name__ == "__main__":
    main()
