# -*- coding: utf-8 -*-
"""Fachada x residuo SEM Botafogo — exclusao por DECISAO DO FELIPE (2026-09-29): "fachada ridicula e totalmente fora da
curva, o maior outlier da rede". Pos-hoc e declarado (a regra 4 do epic proibe excluir para ganhar metrica; a exclusao
fica registrada como decisao do dono e as duas versoes sao reportadas). Reusa 05_fachada_ampliada.py."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
s_ = importlib.util.spec_from_file_location("fa", AQUI / "05_fachada_ampliada.py"); fa = importlib.util.module_from_spec(s_); s_.loader.exec_module(fa)

# reconstroi a tabela do 05 sem regravar o resultado dele
import io, contextlib  # noqa: E402
buf = io.StringIO()
orig_write = Path.write_text
Path.write_text = lambda self, *a, **k: None  # nao sobrescreve resultado_fachada_ampliada.md
with contextlib.redirect_stdout(buf):
    fa.main()
Path.write_text = orig_write
linhas = [l for l in buf.getvalue().splitlines() if l.startswith("| ") and "%" in l and l.count("|") == 5 and not l.startswith("| amostra") and not l.startswith("| principal") and not l.startswith("| ampliada")]
D = pd.DataFrame([[c.strip() for c in l.strip("|").split("|")] for l in linhas], columns=["unidade", "origem", "nota", "vs"])
D["nota"] = D.nota.astype(float); D["residuo"] = np.log1p(D.vs.str.rstrip("%").astype(float) / 100)
rng = np.random.default_rng(20261008)
L = ["# Fachada × desempenho sem Botafogo (decisão do Felipe, 2026-09-29)", "",
     "Exclusão pós-hoc por decisão do dono: Botafogo tem \"fachada ridícula e é totalmente fora da curva, o maior outlier da rede\". "
     "A regra 4 do epic não permite excluir unidade para ganhar métrica; por isso a exclusão fica registrada como decisão dele e as duas versões aparecem.", "",
     "| amostra | N | Spearman nota × resíduo | IC 90% | inclinação | leitura |", "|---|---|---|---|---|---|"]
for nome, Dx in (("principal, com Botafogo", D[D.origem.isin(["treino (LOO)", "teste UNI-02"])]), ("principal, sem Botafogo", D[D.origem.isin(["treino (LOO)", "teste UNI-02"]) & (D.unidade != "botafogo-rj")]),
                 ("ampliada, com Botafogo", D), ("ampliada, sem Botafogo", D[D.unidade != "botafogo-rj"])):
    n = len(Dx); rho = stats.spearmanr(Dx.nota, Dx.residuo)[0]
    bs = [stats.spearmanr(Dx.nota.to_numpy()[i], Dx.residuo.to_numpy()[i])[0] for i in (rng.integers(0, n, n) for _ in range(2000))]
    lo, hi = np.nanquantile(bs, [0.05, 0.95]); sl = np.polyfit(Dx.nota, Dx.residuo, 1)[0]
    L.append(f"| {nome} | {n} | {rho:+.2f} | [{lo:+.2f}; {hi:+.2f}] | {100 * (np.exp(sl) - 1):+.0f}% por ponto | {'sinal' if lo > 0 else 'contrário' if hi < 0 else 'inconclusivo'} |")
(AQUI / "resultado_fachada_sem_botafogo.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
