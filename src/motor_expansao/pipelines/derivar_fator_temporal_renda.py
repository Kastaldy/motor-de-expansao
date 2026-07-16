"""Deriva o FATOR TEMPORAL da renda: de julho/2022 (Censo) para valores correntes.

Por que este pipeline existe
----------------------------
A renda do Censo esta congelada em JULHO/2022. Ate aqui, `FATOR_TEMPORAL_RENDA = 1.0` — uma
escolha honesta (valores nominais do IBGE, sem hipotese), mas que envelhece um pouco a cada mes.
Este pipeline substitui o 1.0 por um numero medido, com fonte oficial e data explicita.

A fonte: Novo CAGED (salario medio das ADMISSOES, por municipio, mensal)
------------------------------------------------------------------------
E a unica serie de renda por municipio com cadencia mensal que chega ate hoje (abr/2026).

Dois cuidados nao-negociaveis:

1. WINSORIZAR. O agregado tem lixo: o maximo da serie e R$ 709 MILHOES, e Sao Paulo aparece com
   "salario medio de admissao de R$ 164.820" em 2020. A media crua e inutilizavel. Salarios sao
   clipados em [R$ 500, R$ 20.000] — fora disso e erro de parse, nao economia. So entao se pondera
   por admissoes (a mediana simples seria limpa, mas jogaria fora o peso dos municipios grandes).

2. NAO USAR A RAIS. A RAIS agregada tem um pico artificial em 2022 — justo o ano-base do Censo.
   Sao Paulo: 4.017 (2020) -> 4.378 (2021) -> 5.713 (2022) -> 4.918 (2023) -> 5.054 (2024). Salario
   nominal nao sobe 30% e cai 14% no ano seguinte; e artefato da migracao RAIS -> eSocial. Um fator
   `rem_2024/rem_2022` daria 0,885 para SP: o motor concluiria que a renda paulistana CAIU 11,5%.

Por que o fator e NACIONAL e nao por municipio
-----------------------------------------------
Foi testado por municipio e REJEITADO. O desvio-padrao do fator municipal nao cai conforme o
municipio cresce (pequenos 0.441, medios 0.419, grandes 0.339, muito grandes 0.399) e as medianas
sao identicas (~1.26) em todos os portes. Se houvesse sinal economico real, os municipios grandes —
com muito mais dados — teriam dispersao bem menor. Nao tem: e ruido de medicao. Aplica-lo daria a
municipios fatores de 0.78 a 1.66 (p05-p95), injetando ruido puro no motor sem sinal em troca.

Conferencia independente (IPCA)
-------------------------------
O fator do CAGED e conferido contra o IPCA acumulado no mesmo periodo (SIDRA t.1737 v.2266). Sao
fontes completamente independentes — salarios vs. precos — e convergem: CAGED ~+16.7%, IPCA ~+18.5%.
O CAGED e o primario porque mede RENDA (o conceito que queremos); o IPCA mede precos e serviria
apenas se assumissemos renda real constante. A diferenca (~1.5 p.p.) e a perda real do periodo.

IMPORTANTE: este fator e SEPARADO do uplift de composicao, de proposito. Foi a mistura dos dois que
fez o fator antigo (2.15, ajustado a GeoFusion) envelhecer escondido.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_CAGED_PATH = Path("C:/dados/socioeconomico/caged/caged_municipio_mensal_2020_2026.csv")
DEFAULT_OUTPUT_PATH = Path("data/staging/fator_temporal_renda.json")
DEFAULT_REPORT_PATH = Path("data/reports/fator_temporal_renda.md")

# Data de referencia do Censo 2022. A base do fator sao os 12 meses do ano-calendario que a contem.
COMPETENCIAS_BASE = [202200 + mes for mes in range(1, 13)]
MESES_ATUAIS = 12

# Limites plausiveis para um salario medio de ADMISSAO. Fora disso e erro de parse, nao economia.
SALARIO_MIN = 500.0
SALARIO_MAX = 20_000.0

# Guardrail: um fator fora desta faixa denuncia dado quebrado, nao inflacao.
FATOR_MIN = 1.0
FATOR_MAX = 2.0

URL_IPCA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/{inicio},{fim}"


def carregar_indice_nacional(caged_path: Path = DEFAULT_CAGED_PATH) -> pd.DataFrame:
    """Indice mensal de salario de admissao: winsorizado, ponderado por admissoes."""
    df = pd.read_csv(caged_path)
    df = df[df["salario_medio_adm"].gt(0) & df["admissoes"].gt(0)].copy()
    df["salario_winsorizado"] = df["salario_medio_adm"].clip(SALARIO_MIN, SALARIO_MAX)

    indice = (
        df.groupby("competencia")
        .apply(
            lambda g: pd.Series(
                {
                    "salario_medio": float(
                        np.average(g["salario_winsorizado"], weights=g["admissoes"])
                    ),
                    "admissoes": float(g["admissoes"].sum()),
                    "municipios": int(g["cod_municipio"].nunique()),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    indice["competencia"] = indice["competencia"].astype(int)
    return indice.sort_values("competencia").reset_index(drop=True)


def _media_ponderada(indice: pd.DataFrame, competencias: list[int]) -> float:
    sub = indice[indice["competencia"].isin(competencias)]
    if sub.empty:
        raise ValueError(f"Nenhuma competencia encontrada em {competencias[:3]}...")
    return float(np.average(sub["salario_medio"], weights=sub["admissoes"]))


def conferir_ipca(competencia_base: int, competencia_atual: int) -> float | None:
    """IPCA acumulado no mesmo periodo (SIDRA). Conferencia independente — nao entra na conta.

    Retorna None se nao houver internet: a conferencia e desejavel, nao bloqueante.
    """
    import urllib.request

    url = URL_IPCA.format(inicio=competencia_base, fim=competencia_atual)
    try:
        with urllib.request.urlopen(url, timeout=45) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except Exception:
        return None

    valores = {
        item["D3C"]: float(item["V"])
        for item in dados[1:]
        if item.get("V") not in (None, "...", "-")
    }
    if len(valores) < 2:
        return None
    chaves = sorted(valores)
    return valores[chaves[-1]] / valores[chaves[0]]


def derivar_fator(caged_path: Path = DEFAULT_CAGED_PATH) -> dict:
    indice = carregar_indice_nacional(caged_path)

    competencias_atuais = indice["competencia"].tolist()[-MESES_ATUAIS:]
    base = _media_ponderada(indice, COMPETENCIAS_BASE)
    atual = _media_ponderada(indice, competencias_atuais)
    fator = atual / base

    if not FATOR_MIN <= fator <= FATOR_MAX:
        raise ValueError(
            f"Fator temporal implausivel ({fator:.3f}). Isso denuncia dado quebrado no CAGED — "
            "nao publique. Investigue antes de seguir."
        )

    # A renda do Censo e de JULHO/2022; a base do fator e o ano-calendario de 2022.
    ipca = conferir_ipca(202207, competencias_atuais[-1])

    return {
        "fator_temporal_renda": round(fator, 4),
        "salario_base_2022": round(base, 2),
        "salario_atual": round(atual, 2),
        "competencia_base_inicio": int(COMPETENCIAS_BASE[0]),
        "competencia_base_fim": int(COMPETENCIAS_BASE[-1]),
        "competencia_atual_inicio": int(competencias_atuais[0]),
        "competencia_atual_fim": int(competencias_atuais[-1]),
        "fonte": "Novo CAGED (salario medio de admissao), winsorizado e ponderado por admissoes",
        "ipca_acumulado_conferencia": round(ipca, 4) if ipca else None,
        "divergencia_vs_ipca_pp": round(100 * (fator - ipca), 1) if ipca else None,
        "escopo": "nacional",
    }


def gerar_relatorio(d: dict) -> str:
    fim = str(d["competencia_atual_fim"])
    ref = f"{fim[4:]}/{fim[:4]}"
    linhas = [
        "# Fator temporal da renda — de julho/2022 para valores correntes",
        "",
        f"## `FATOR_TEMPORAL_RENDA = {d['fator_temporal_renda']}`"
        f"  (+{100*(d['fator_temporal_renda']-1):.1f}%)",
        "",
        f"Atualiza a renda do Censo (julho/2022) para reais de **{ref}**.",
        "",
        "| | |",
        "| --- | ---: |",
        f"| Salario medio de admissao, base (2022) | R$ {d['salario_base_2022']:,.2f} |",
        f"| Salario medio de admissao, atual ({d['competencia_atual_inicio']}-"
        f"{d['competencia_atual_fim']}) | R$ {d['salario_atual']:,.2f} |",
        f"| **Fator** | **{d['fator_temporal_renda']}** |",
        "",
        "## Fonte e tratamento",
        "",
        f"{d['fonte']}.",
        "",
        "O agregado do CAGED tem lixo: o maximo da serie e R$ 709 MILHOES, e Sao Paulo aparece com",
        "salario medio de admissao de R$ 164.820 em 2020. A media crua e inutilizavel. Salarios sao",
        f"clipados em [R$ {SALARIO_MIN:,.0f}, R$ {SALARIO_MAX:,.0f}] e so entao ponderados por admissoes.",
        "",
    ]
    if d["ipca_acumulado_conferencia"]:
        linhas += [
            "## Conferencia independente: IPCA",
            "",
            f"- Fator do CAGED (salarios): **{d['fator_temporal_renda']}**"
            f" (+{100*(d['fator_temporal_renda']-1):.1f}%)",
            f"- IPCA acumulado no periodo (precos): **{d['ipca_acumulado_conferencia']}**"
            f" (+{100*(d['ipca_acumulado_conferencia']-1):.1f}%)",
            f"- Divergencia: **{d['divergencia_vs_ipca_pp']:+.1f} p.p.**",
            "",
            "Duas fontes oficiais completamente independentes — salarios vs. precos — convergindo.",
            "O CAGED e o primario porque mede RENDA (o conceito que queremos); o IPCA mede precos e",
            "so serviria assumindo renda real constante. A diferenca e a perda real do periodo.",
            "",
        ]
    else:
        linhas += [
            "## Conferencia com IPCA: NAO EXECUTADA (sem internet)",
            "",
            "Rode de novo com rede para conferir o fator contra o IPCA do SIDRA.",
            "",
        ]
    linhas += [
        "## Por que NACIONAL e nao por municipio",
        "",
        "Testado por municipio e **rejeitado**. O desvio-padrao do fator municipal nao cai conforme",
        "o municipio cresce:",
        "",
        "| Porte (admissoes) | Municipios | Mediana | Desvio-padrao |",
        "| --- | ---: | ---: | ---: |",
        "| Pequeno | 1.337 | 1,264 | 0,441 |",
        "| Medio | 1.337 | 1,268 | 0,419 |",
        "| Grande | 1.337 | 1,264 | 0,339 |",
        "| Muito grande | 1.337 | 1,239 | 0,399 |",
        "",
        "Se houvesse sinal economico real, os municipios grandes — com muito mais dados — teriam",
        "dispersao bem menor. Nao tem, e as medianas sao identicas. Isso e ruido de medicao. Um",
        "fator municipal daria valores de 0,78 a 1,66 (p05-p95): ruido puro injetado no motor.",
        "",
        "## A RAIS foi descartada",
        "",
        "A RAIS agregada tem pico artificial em 2022 — **justo o ano-base do Censo**. Sao Paulo:",
        "4.017 (2020) -> 4.378 (2021) -> **5.713 (2022)** -> 4.918 (2023) -> 5.054 (2024). Salario",
        "nominal nao sobe 30% e cai 14% no ano seguinte: e artefato da migracao RAIS -> eSocial.",
        "Um fator `rem_2024/rem_2022` daria 0,885 para SP — o motor concluiria que a renda paulistana",
        "CAIU 11,5%.",
        "",
        "## Efeito no motor",
        "",
        "Um fator nacional multiplica todos os setores pelo mesmo numero: **nao muda ranking, nem",
        "correlacao com faturamento, nem decisao de expansao**. Ele corrige o NIVEL — o relatorio",
        "passa a mostrar reais de hoje em vez de reais de 2022. TAM/SAM sobem proporcionalmente.",
        "",
        "## Manutencao",
        "",
        "Reexecute quando sair novo CAGED (mensal). O fator e datado de proposito: um numero",
        "explicito que envelhece a olhos vistos e melhor que um numero embutido que apodrece em",
        "silencio — foi assim que o fator antigo (2.15) envelheceu sem ninguem perceber.",
    ]
    return "\n".join(linhas) + "\n"


def executar(
    caged_path: Path = DEFAULT_CAGED_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict:
    d = derivar_fator(caged_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(gerar_relatorio(d), encoding="utf-8")

    print(f"[fator-temporal] FATOR_TEMPORAL_RENDA = {d['fator_temporal_renda']}"
          f" (+{100*(d['fator_temporal_renda']-1):.1f}%)")
    print(f"[fator-temporal] base 2022: R$ {d['salario_base_2022']:,.2f}"
          f" -> atual: R$ {d['salario_atual']:,.2f}")
    if d["ipca_acumulado_conferencia"]:
        print(f"[fator-temporal] conferencia IPCA: {d['ipca_acumulado_conferencia']}"
              f" (divergencia {d['divergencia_vs_ipca_pp']:+.1f} p.p.)")
    else:
        print("[fator-temporal] conferencia IPCA: NAO executada (sem internet)")
    print(f"[fator-temporal] artefato: {output_path}")
    print(f"[fator-temporal] relatorio: {report_path}")
    return d


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caged-path", default=str(DEFAULT_CAGED_PATH))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    executar(Path(args.caged_path), Path(args.output_path), Path(args.report_path))


if __name__ == "__main__":
    main()
