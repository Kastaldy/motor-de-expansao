# -*- coding: utf-8 -*-
"""Coleta de vendas por unidade x mes na Growth (/relatorio-vendas-operacoes) com a agregacao do 01_coletar_vendas.py, mas SEM
repeticao em 429 (regra do estudo: uma tentativa so'). Respeita a janela de 10 chamadas / 5 min do cliente (throttle) e para de vez
no primeiro 429. LGPD: nome, cod_aluno e usuario sao descartados na agregacao, antes de qualquer gravacao; nada da resposta crua vai
para disco. Retoma de onde parou (pula meses ja' gravados). Uso: 02_coletar_sem_repeticao.py [ini] [fim]  (.venv, PYTHONPATH=src)."""
import importlib.util
import sys
import types
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import pandas as pd  # noqa: E402

from motor_expansao.dimensionamento.growth_api_client import GrowthAPIClient  # noqa: E402

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "vendas_unidade_mes.parquet"
LOG = AQUI / "coleta_log.txt"


def main():
    s = importlib.util.spec_from_file_location("c1", AQUI / "01_coletar_vendas.py"); c1 = importlib.util.module_from_spec(s); s.loader.exec_module(c1)
    ini = sys.argv[1] if len(sys.argv) > 1 else "2023-01"
    fim = sys.argv[2] if len(sys.argv) > 2 else "2026-08"
    feitos = set(pd.read_parquet(SAIDA).competencia) if SAIDA.exists() else set()
    partes = [pd.read_parquet(SAIDA)] if SAIDA.exists() else []
    from motor_expansao.dimensionamento import growth_api_client as gac
    gac.config.RATE_LIMIT_REQS = 8          # o servidor conta o login: 8 por janela deixa folga (o 10o pedido deu 429 em 06/10)
    c = GrowthAPIClient()
    log = LOG.read_text(encoding="utf-8").splitlines() if LOG.exists() else []
    for p in pd.period_range(ini, fim, freq="M"):
        if str(p) in feitos:
            continue
        di, df = p.start_time.strftime("%Y-%m-%d"), p.end_time.strftime("%Y-%m-%d")
        c._throttle()
        resp = c._session.request("GET", f"{c.base_url}/relatorio-vendas-operacoes", params={"data_inicio": di, "data_fim": df}, headers=c._headers())
        if resp.status_code == 429:
            log.append(f"{p}: HTTP 429 — coleta interrompida (uma tentativa so')"); print(log[-1], flush=True); break
        if resp.status_code >= 400:
            log.append(f"{p}: HTTP {resp.status_code} — mes pulado"); print(log[-1], flush=True); continue
        d = pd.DataFrame(c._parse_response(resp) or [])
        if d.empty:
            log.append(f"{p}: vazio"); print(log[-1], flush=True); continue
        if not feitos and not partes:
            print("colunas da resposta:", [x for x in d.columns if x not in c1.PII], flush=True)
        a, n, fora = c1.agregar(d, str(p))
        del d
        partes.append(a)
        pd.concat(partes, ignore_index=True).to_parquet(SAIDA, index=False)
        log.append(f"{p}: {n} vendas, {a.unidade.nunique()} unidades, fora da janela {fora}"); print(log[-1], flush=True)
    LOG.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("fim", flush=True)


if __name__ == "__main__":
    main()
