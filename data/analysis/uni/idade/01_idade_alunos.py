# -*- coding: utf-8 -*-
"""Idade REAL dos alunos (pedido do Felipe, 2026-10-01: conferir o publico-alvo no dado antes de assumir).
Fonte: Growth API GET /alunos-frequencia (doc Growth_API_Ultra_v1_0_0.pdf §8.8): base de alunos filtrada pela DATA DE
VENCIMENTO do plano, com data_nascimento e sexo.

LGPD (doc §10.3 + regras da casa): a resposta fica so' em memoria; cod_aluno e data_nascimento sao descartados logo depois
de calcular a idade; so' AGREGADOS por unidade sao gravados (assert_sem_pii antes de gravar). Sem cache em disco. Sem
retry em 429: uma tentativa; se vier 429, para. Uso: 01_idade_alunos.py <data_inicio> <data_fim> <rotulo>
.venv, PYTHONPATH=src."""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.growth_api_client import GrowthAPIClient, assert_sem_pii

AQUI = Path(__file__).resolve().parent
_P = Path(__file__).resolve().parents
REPO = _P[3] if len(_P) > 3 else None
OUT = Path(os.environ.get("IDADE_OUT", str(AQUI)))
REF = pd.Timestamp("2026-10-01")
CENSO = [(0, 4, "0_4"), (5, 9, "5_9"), (10, 14, "10_14"), (15, 19, "15_19"), (20, 24, "20_24"), (25, 29, "25_29"), (30, 39, "30_39"),
         (40, 49, "40_49"), (50, 59, "50_59"), (60, 69, "60_69"), (70, 130, "70_mais")]  # grupos do Censo 2022 por setor (item 3)
FAIXAS = [(0, 15, "<16"), (16, 17, "16-17"), (18, 24, "18-24"), (25, 29, "25-29"), (30, 34, "30-34"), (35, 39, "35-39"),
          (40, 44, "40-44"), (45, 49, "45-49"), (50, 54, "50-54"), (55, 64, "55-64"), (65, 130, "65+")]


def carregar_env():
    if REPO is None or not (REPO / ".env").exists():
        return  # na VPS as credenciais vem do --env-file do container efemero
    for linha in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if linha.startswith(("GROWTH_API_USUARIO=", "GROWTH_API_SENHA=")):
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ini, fim, rot = sys.argv[1], sys.argv[2], sys.argv[3]
    carregar_env()
    cli = GrowthAPIClient()
    cli.login()
    cli._throttle()
    resp = cli._session.request("GET", f"{cli.base_url}/alunos-frequencia", params={"data_inicio": ini, "data_fim": fim},
                                headers=cli._headers(), timeout=600)
    if resp.status_code == 429:
        print("HTTP 429 — parado sem nova tentativa."); return
    dados = cli._parse_response(resp)
    df = pd.DataFrame(dados or [])
    del dados, resp
    n_bruto = len(df)
    if df.empty:
        print("resposta vazia"); return
    cols_resp = sorted(df.columns)
    nasc = pd.to_datetime(df["data_nascimento"].where(df["data_nascimento"].astype(str) != "False"), errors="coerce")
    idade = ((REF - nasc).dt.days / 365.25).astype(float)
    canc = df["data_cancelamento"].astype(str).ne("False") & df["data_cancelamento"].notna()
    A = pd.DataFrame({"unidade": df["unidade"].astype(str), "idade": idade.where((idade >= 5) & (idade <= 100)),
                      "sexo": df["sexo"].astype(str).str.upper().str[:1], "tipo": df["tipo"].astype(str), "cancelado": canc})
    del df, nasc, idade  # descarta cod_aluno, data_nascimento e o resto da resposta
    A["faixa"] = pd.cut(A.idade, [a - 0.001 for a, _, _ in FAIXAS] + [130.999], labels=[r for _, _, r in FAIXAS])
    ativos = A[~A.cancelado]
    g = ativos.groupby("unidade")
    U = pd.DataFrame({"n_alunos": g.size(), "n_com_idade": g.idade.count(), "idade_mediana": g.idade.median(),
                      "idade_p25": g.idade.quantile(.25), "idade_p75": g.idade.quantile(.75),
                      "pct_feminino": g.sexo.apply(lambda s: float((s == "F").mean()))})
    fx = pd.crosstab(ativos.unidade, ativos.faixa, normalize="index").add_prefix("pct_")
    U = U.join(fx)
    ativos = ativos.assign(censo=pd.cut(ativos.idade, [a - 0.001 for a, _, _ in CENSO] + [130.999], labels=[r for _, _, r in CENSO]))
    U = U.join(pd.crosstab(ativos.unidade, ativos.censo).reindex(columns=[r for _, _, r in CENSO], fill_value=0).add_prefix("n_censo_"))
    U = U[U.n_alunos >= 30]
    assert_sem_pii(U.reset_index())
    out = OUT / f"idade_alunos_por_unidade_{rot}.parquet"
    U.reset_index().to_parquet(out, index=False)
    rede = ativos.faixa.value_counts(normalize=True).reindex([r for _, _, r in FAIXAS])
    L = [f"# Idade real dos alunos — Growth /alunos-frequencia (vencimento {ini} a {fim}; referência {REF:%Y-%m-%d})", "",
         f"Campos na resposta: {', '.join(cols_resp)}.",
         f"Registros: {n_bruto:,}; não cancelados: {len(ativos):,}; unidades: {ativos.unidade.nunique()} (≥ 30 alunos: {len(U)}); "
         f"com data de nascimento válida: {100 * ativos.idade.notna().mean():.1f}%.",
         f"Tipos: {ativos.tipo.value_counts().head(8).to_dict()}.", "",
         f"**Rede:** idade mediana {ativos.idade.median():.1f} (p10 {ativos.idade.quantile(.1):.0f}, p25 {ativos.idade.quantile(.25):.0f}, "
         f"p75 {ativos.idade.quantile(.75):.0f}, p90 {ativos.idade.quantile(.9):.0f}); feminino {100 * (ativos.sexo == 'F').mean():.0f}%.", "",
         "| faixa | % dos alunos |", "|---|---|"] + [f"| {k} | {100 * v:.1f}% |" for k, v in rede.items()] + ["",
         f"Faixa que concentra 80% dos alunos (p10–p90): {ativos.idade.quantile(.1):.0f} a {ativos.idade.quantile(.9):.0f} anos. "
         f"Entre 18 e 45 (dos alunos COM idade): {100 * ativos.idade.dropna().between(18, 45.999).mean():.0f}%.",
         f"Cobertura da data de nascimento por unidade (≥ 30 alunos): p10 {(U.n_com_idade / U.n_alunos).quantile(.1):.0%}, "
         f"mediana {(U.n_com_idade / U.n_alunos).median():.0%}, p90 {(U.n_com_idade / U.n_alunos).quantile(.9):.0%}; "
         f"unidades com < 20%: {int((U.n_com_idade / U.n_alunos < .2).sum())}; por tipo: "
         f"{ativos.assign(c=ativos.idade.notna()).groupby('tipo').c.mean().round(2).to_dict()}.",
         f"Entre unidades: idade mediana de {U.idade_mediana.min():.1f} a {U.idade_mediana.max():.1f} (mediana {U.idade_mediana.median():.1f}).", ""]
    (OUT / f"resultado_idade_{rot}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
