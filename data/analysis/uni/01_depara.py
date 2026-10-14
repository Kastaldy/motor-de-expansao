# -*- coding: utf-8 -*-
"""BLK-UNI-00, passo 1: de-para de identidade entre as fontes do painel (unidade_id = slug da Growth).

Liga, por unidade_id: catalogo Growth (inclui excluidas, com flag) | cod_unidade do Financeiro (pelo MESMO join de nome
de rede_metricas.aplicar_faturamento_financeiro) | cod_unidade do cadastro (conferencia) | COD_UNIDADE do Lifetime
(via cod do Financeiro) | LOCALIZACAO do dados_academias.xlsx (chave_unidade + UF, 1:1) | pino das isocronas.
Divergencia entre caminhos e' ERRO REGISTRADO, nao resolvido no chute.
Saidas: data/analysis/uni/depara_unidade.parquet (+ .csv) e depara_divergencias.md
"""
import importlib.util
import json
from pathlib import Path

import pandas as pd

from motor_expansao.dashboard import rede_faturamento_financeiro as rf
from motor_expansao.dashboard import rede_metricas as rm

UNI = Path(__file__).parent
s_aj = importlib.util.spec_from_file_location("ajustes", Path(__file__).parent / "_ajustes.py"); ajustes = importlib.util.module_from_spec(s_aj); s_aj.loader.exec_module(ajustes)
VPS, LOC = UNI / "insumos_vps", UNI / "insumos_locais"
ISO = UNI.parent / "isocronas"


# Alias declarado (o join de nome do motor nao casa): cod 91 e' "SÃO CARLOS - SP" no Financeiro e "SAO CARLOS - CENTRO - SP"
# na Growth e no Lifetime (mesmo cod 91); unica Sao Carlos da rede. Lacuna do motor registrada no relatorio do UNI-00.
ALIAS_FINANCEIRO = {"SÃO CARLOS - SP": "SAO CARLOS - CENTRO - SP"}


def cod2(x):
    """'6' / '06' / 'A0' -> '06' / '06' / 'A0'. Nunca o _cod() do modulo do Financeiro (tira o zero)."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().upper()
    return s.zfill(2) if s.isdigit() else s


def main():
    div = []
    raw = pd.read_parquet(VPS / "growth_api_historico.parquet")
    t = rm._com_colunas_de_identidade(raw)
    t["_data"] = pd.to_datetime(t["data"], format="%d/%m/%Y", errors="coerce")
    t = t.dropna(subset=["_data"])
    _, cat = rm.resolver_identidade(t)
    D = pd.DataFrame([{"unidade_id": u.id, "nome": u.nome, "uf": u.uf, "master": u.master, "inauguracao": u.inauguracao,
                       "nomes_crus": " | ".join(u.nomes_crus), "excluida_rede": u.excluida} for u in cat.values()])
    # ---- Financeiro: mesmo join de nome do motor
    fin = ajustes.financeiro()  # planilha de 2026-09-28 (a copia da VPS tinha o Guaruja ago/26 velho)
    fin["unidade_ux"] = fin["unidade_ux"].replace(ALIAS_FINANCEIRO)
    ativos = {uid: u for uid, u in cat.items() if not u.excluida}
    por_nome = {rm._sem_acento(n): uid for uid, u in ativos.items() for n in u.nomes_crus}
    resg = rm._resgate_por_aperto(por_nome, fin["unidade_ux"])
    fin["unidade_id"] = fin["unidade_ux"].map(lambda n: por_nome.get(rm._sem_acento(n)) or resg.get(n))
    fin["cod2"] = fin.cod_unidade.map(cod2)
    fc = fin[fin.cod2.notna() & fin.unidade_id.notna()]
    cods = fc.groupby("unidade_id").cod2.agg(lambda s: ",".join(sorted(set(s))))
    D["cod_financeiro"] = D.unidade_id.map(cods)
    sem_par = sorted(set(fin.loc[fin.unidade_id.isna() & fin.faturamento.fillna(0).gt(0), "unidade_ux"].dropna()) - {n for n in fin.unidade_ux.dropna() if rm.eh_excluida(n)})
    if sem_par:
        div.append(f"- Financeiro sem par na Growth (faturamento > 0; ficam fora do painel mensal): {sem_par}")
    multi = cods[cods.str.contains(",")]
    if len(multi):
        div.append(f"- unidade_id com MAIS DE UM cod do Financeiro (valores somam): {multi.to_dict()}")
    # dois codigos no mesmo mes (checagem do Guaruja ago/26)
    dup = fin[fin.unidade_id.notna() & fin.faturamento.notna()].groupby(["unidade_id", "competencia"]).size()
    dup = dup[dup > 1]
    if len(dup):
        div.append(f"- unidade-mes com 2+ LINHAS somadas no Financeiro (qualquer codigo, inclusive nulo): {dup.reset_index().to_dict('records')[:20]}")
    else:
        div.append("- nenhuma unidade-mes com 2+ linhas no Financeiro. Guaruja ago/26: a planilha atual traz R$ 217.525,74; a copia da VPS (ingerida em 2026-09-08) ainda tem R$ 547.745,05 — unica celula divergente em 6.528; o painel usa a planilha de 2026-09-28 (reingerir na VPS)")
    div.append(f"- ALIAS DECLARADO (o join de nome do motor nao casa; lacuna do motor): {ALIAS_FINANCEIRO} — a Visao Executiva nao ve o faturamento de Sao Carlos pelo Financeiro")
    por_nome_sem_cod = sorted(set(fin.loc[fin.unidade_id.notna() & fin.faturamento.fillna(0).gt(0), "unidade_id"]) - set(fc.unidade_id))
    if por_nome_sem_cod:
        div.append(f"- unidades com Financeiro casado so' por NOME (bloco do layout sem codigo): {por_nome_sem_cod}")
    # ---- cadastro
    cad = json.load(open(VPS / "cadastro_unidades_campos_usados.json", encoding="utf-8"))["unidades"]
    D["cod_cadastro"] = D.unidade_id.map(lambda u: cod2(cad.get(u, {}).get("cod_unidade")))
    D["cidade_cadastro"] = D.unidade_id.map(lambda u: cad.get(u, {}).get("cidade"))
    x = D[D.cod_cadastro.notna() & D.cod_financeiro.notna()]
    bate = x.apply(lambda r: r.cod_cadastro in r.cod_financeiro.split(","), axis=1)
    if (~bate).any():
        div.append(f"- cod do cadastro DIVERGE do cod do Financeiro: {x.loc[~bate, ['unidade_id', 'cod_cadastro', 'cod_financeiro']].to_dict('records')}")
    fora_cat = sorted(set(cad) - set(D.unidade_id))
    if fora_cat:
        div.append(f"- ids do cadastro que nao existem no catalogo Growth: {fora_cat}")
    # ---- Lifetime (cadastro ja lido acima)
    lt = pd.read_parquet(LOC / "unidade_para_motor.parquet")
    assert lt.FONTE_SCORES.dropna().str.startswith("vintage:").all(), "Lifetime com escala RAW (fallback)"
    lt["cod2"] = lt.COD_UNIDADE.map(cod2)
    cod2uid = fc.sort_values("competencia").drop_duplicates("cod2", keep="last").set_index("cod2")
    lt["unidade_id"] = lt.cod2.map(cod2uid.unidade_id)
    # 2o caminho: cod do cadastro (concorda com o Financeiro onde os dois existem; medido)
    cad2uid = {}
    for uid, c in cad.items():
        if c.get("cod_unidade") is not None and uid in ativos:
            cad2uid.setdefault(cod2(c["cod_unidade"]), set()).add(uid)
    via_cad = lt.unidade_id.isna() & lt.cod2.map(lambda c: len(cad2uid.get(c, ())) == 1)
    lt.loc[via_cad, "unidade_id"] = lt.loc[via_cad, "cod2"].map(lambda c: next(iter(cad2uid[c])))
    lt["via"] = "financeiro"; lt.loc[via_cad, "via"] = "cadastro"
    lt["unidade_ux_fin"] = lt.cod2.map(cod2uid.unidade_ux)
    nome_bate = [rm._apertar(a) == rm._apertar(b) if isinstance(b, str) else None for a, b in zip(lt.UNIDADE, lt.unidade_ux_fin)]
    lt["nome_bate"] = nome_bate
    D["cod_lifetime"] = D.unidade_id.map(lt.dropna(subset=["unidade_id"]).groupby("unidade_id").cod2.agg(lambda s: ",".join(sorted(s))))
    sem = lt[lt.unidade_id.isna()]
    if len(sem):
        div.append(f"- COD do Lifetime sem unidade_id (cod ausente no Financeiro): {sem[['COD_UNIDADE', 'UNIDADE']].to_dict('records')}")
    nb = lt[lt.nome_bate.eq(False)]
    if len(nb):
        div.append(f"- COD do Lifetime casou, mas o NOME difere do Financeiro (conferir): {nb[['COD_UNIDADE', 'UNIDADE', 'unidade_ux_fin', 'unidade_id']].to_dict('records')}")
    # ---- dados_academias.xlsx (metragem/vagas)
    xl = pd.read_excel(LOC / "dados_academias.xlsx", sheet_name="Plan1")
    xl["uf_x"] = xl.LOCALIZACAO.str.rsplit("-", n=1).str[-1].str.strip()
    xl["nome_x"] = xl.LOCALIZACAO.str.rsplit("-", n=1).str[0].str.strip()
    xl["k"] = xl.nome_x.map(rm.chave_unidade) + "|" + xl.uf_x
    kcat = {}
    for u in ativos.values():
        for n in u.nomes_crus:
            kcat.setdefault(rm.chave_unidade(n) + "|" + u.uf, set()).add(u.id)
    xl["unidade_id"] = xl.k.map(lambda k: next(iter(kcat[k])) if len(kcat.get(k, ())) == 1 else None)
    # linhas sem sufixo ' - UF' (AUGUSTA, ACLIMACAO...): casa pela chave sem UF se ela for UNICA entre as nao excluidas
    ksem = {}
    for u in ativos.values():
        for n in u.nomes_crus:
            ksem.setdefault(rm.chave_unidade(n), set()).add(u.id)
    sem_uf = xl.unidade_id.isna() & ~xl.LOCALIZACAO.str.contains("-")
    xl.loc[sem_uf, "unidade_id"] = xl.loc[sem_uf, "LOCALIZACAO"].map(lambda n: next(iter(ksem[rm.chave_unidade(n)])) if len(ksem.get(rm.chave_unidade(n), ())) == 1 else None)
    naocasou = xl[xl.unidade_id.isna()]
    if len(naocasou):
        div.append(f"- dados_academias.xlsx sem par 1:1 no catalogo: {naocasou.LOCALIZACAO.tolist()}")
    assert not xl.unidade_id.dropna().duplicated().any(), "xlsx casou 2 linhas na mesma unidade"
    D["localizacao_xlsx"] = D.unidade_id.map(xl.dropna(subset=["unidade_id"]).set_index("unidade_id").LOCALIZACAO)
    # ---- pinos das isocronas
    up = pd.read_parquet(ISO / "ultra_pontos.parquet")
    D["tem_pino_iso"] = D.unidade_id.isin(set(up.unidade_id))
    fora = sorted(set(up.unidade_id) - set(D.unidade_id))
    if fora:
        div.append(f"- unidade_id das isocronas que nao existe no catalogo atual: {fora}")
    D = D.sort_values(["excluida_rede", "uf", "unidade_id"]).reset_index(drop=True)
    D.to_parquet(UNI / "depara_unidade.parquet", index=False)
    D.to_csv(UNI / "depara_unidade.csv", sep=";", encoding="utf-8-sig", index=False)
    lt[["COD_UNIDADE", "cod2", "UNIDADE", "unidade_ux_fin", "unidade_id", "nome_bate"]].to_csv(UNI / "depara_lifetime.csv", sep=";", encoding="utf-8-sig", index=False)
    nat = D[~D.excluida_rede]
    res = [f"# De-para de identidade — BLK-UNI-00\n", f"Catálogo Growth: {len(D)} unidades ({int(D.excluida_rede.sum())} excluídas da rede comparável).\n",
           "| fonte | unidades (fora as excluídas) |", "|---|---|",
           f"| Financeiro (cod) | {nat.cod_financeiro.notna().sum()} |", f"| Cadastro (cod) | {nat.cod_cadastro.notna().sum()} |",
           f"| Lifetime (COD) | {nat.cod_lifetime.notna().sum()} |", f"| dados_academias.xlsx (metragem) | {nat.localizacao_xlsx.notna().sum()} |",
           f"| Pino das isócronas | {int(nat.tem_pino_iso.sum())} |", "\n## Divergências (registradas, não resolvidas no chute)\n"] + (div or ["- nenhuma"])
    (UNI / "depara_divergencias.md").write_text("\n".join(res), encoding="utf-8")
    print("\n".join(res))


if __name__ == "__main__":
    main()
