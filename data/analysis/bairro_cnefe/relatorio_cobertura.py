"""BLK-BAIRRO-01 fase 1 -- consolida os agregados do CNEFE em metricas de cobertura.

Metricas (todas por UF e Brasil):
  dom_bairro   % dos domicilios cujo endereco tem localidade da classe BAIRRO
  setores      % dos setores censitarios (com >= 1 endereco) cuja localidade DOMINANTE
               (maioria dos enderecos do setor) e' BAIRRO
  munis_2      % dos municipios com >= 2 bairros distintos (o nome DISTINGUE partes da cidade)
  hex_pop      % dos hexagonos H3 res-7 com >= 1 domicilio cujo bairro dominante e' BAIRRO
  hex_pop_dom  o mesmo, ponderado por domicilios
SP: cruza com o NM_BAIRRO da malha do IBGE (dados-vps-local) por municipio.
Uso: python -I relatorio_cobertura.py <out> <municipios_nomes.parquet> [geo_sp_dir]
"""
import glob
import json
import os
import sys

import h3
import pandas as pd

OUT, NOMES = sys.argv[1], sys.argv[2]
GEO_SP = sys.argv[3] if len(sys.argv) > 3 else None
nomes = pd.read_parquet(NOMES).assign(cod_municipio=lambda d: d.cod_municipio.astype(str))

linhas, munis_todos, classes_br = [], [], []
for f in sorted(glob.glob(os.path.join(OUT, 'setor_*.parquet'))):
    uf = f[-10:-8]
    s = pd.read_parquet(f)
    g = pd.read_parquet(os.path.join(OUT, f'grade_{uf}.parquet'))
    classes_br.append(s.groupby('classe')[['n_end', 'n_dom']].sum().assign(uf=uf))

    dom_total = s.n_dom.sum()
    dom_bairro = s.loc[s.classe == 'BAIRRO', 'n_dom'].sum()

    dominante = s.sort_values('n_end', ascending=False).drop_duplicates('cod_setor')
    set_ok = (dominante.classe == 'BAIRRO').mean()

    b = s[s.classe == 'BAIRRO']
    nb = b.groupby('cod_municipio')['loc'].nunique()
    munis = pd.DataFrame({'cod_municipio': s.cod_municipio.unique()})
    munis['n_bairros'] = munis.cod_municipio.map(nb).fillna(0).astype(int)
    munis['dom'] = munis.cod_municipio.map(s.groupby('cod_municipio').n_dom.sum())
    munis['uf'] = uf
    munis_todos.append(munis)
    m2 = (munis.n_bairros >= 2).mean()
    m2_dom = munis.loc[munis.n_bairros >= 2, 'dom'].sum() / munis.dom.sum()

    cel = g[['lat3', 'lon3']].drop_duplicates()
    cel['hex'] = [h3.latlng_to_cell(a / 1000, o / 1000, 7) for a, o in zip(cel.lat3, cel.lon3)]
    g = g.merge(cel, on=['lat3', 'lon3'])
    por_hex_loc = g.groupby(['hex', 'loc', 'classe'], observed=True).n_dom.sum().reset_index()
    dom_hex = por_hex_loc.sort_values('n_dom', ascending=False).drop_duplicates('hex')
    tot_hex = por_hex_loc.groupby('hex').n_dom.sum()
    dom_hex = dom_hex.assign(tot=dom_hex.hex.map(tot_hex))
    hex_ok = (dom_hex.classe == 'BAIRRO').mean()
    hex_ok_dom = dom_hex.loc[dom_hex.classe == 'BAIRRO', 'tot'].sum() / dom_hex.tot.sum()

    linhas.append(dict(uf=uf, municipios=len(munis), domicilios=int(dom_total),
                       dom_bairro=dom_bairro / dom_total, setores=len(dominante), set_bairro=set_ok,
                       munis_2bairros=m2, munis_2bairros_dom=m2_dom, hexes_pop=len(dom_hex),
                       hex_bairro=hex_ok, hex_bairro_dom=hex_ok_dom))
    print(uf, 'ok', flush=True)

t = pd.DataFrame(linhas)
br = dict(uf='BR', municipios=int(t.municipios.sum()), domicilios=int(t.domicilios.sum()),
          dom_bairro=(t.dom_bairro * t.domicilios).sum() / t.domicilios.sum(),
          setores=int(t.setores.sum()), set_bairro=(t.set_bairro * t.setores).sum() / t.setores.sum(),
          munis_2bairros=(t.munis_2bairros * t.municipios).sum() / t.municipios.sum(),
          munis_2bairros_dom=None, hexes_pop=int(t.hexes_pop.sum()),
          hex_bairro=(t.hex_bairro * t.hexes_pop).sum() / t.hexes_pop.sum(), hex_bairro_dom=None)
m = pd.concat(munis_todos)
br['munis_2bairros_dom'] = m.loc[m.n_bairros >= 2, 'dom'].sum() / m.dom.sum()
t = pd.concat([t, pd.DataFrame([br])], ignore_index=True)
pd.set_option('display.width', 250)
print(t.round(4).to_string(index=False))

cls = pd.concat(classes_br).groupby(level=0)[['n_end', 'n_dom']].sum()
print('\nclasses (Brasil):\n', (cls / cls.sum()).round(4))

# distribuicao do n de bairros por municipio, por porte
m = m.merge(nomes, on=['cod_municipio'], how='left', suffixes=('', '_n'))
m['porte'] = pd.cut(m.dom, [0, 5_000, 20_000, 100_000, 1e9], labels=['<5k dom', '5-20k', '20-100k', '>100k'])
print('\nmunicipios com >=2 bairros por porte:\n',
      m.groupby('porte', observed=True).apply(lambda d: pd.Series({'n': len(d), 'pct_2b': (d.n_bairros >= 2).mean(),
                                                                    'mediana_bairros': d.n_bairros.median()})).round(3))
sem = m[m.n_bairros < 2].sort_values('dom', ascending=False).head(15)[['uf', 'nome_municipio', 'dom', 'n_bairros']]
print('\nmaiores municipios SEM bairro no CNEFE:\n', sem.to_string(index=False))
m.to_parquet(os.path.join(OUT, 'municipios.parquet'), index=False)

if GEO_SP:
    import pyarrow.parquet as pq
    reg = []
    for p in glob.glob(os.path.join(GEO_SP, 'cod_municipio=*', '*.parquet')):
        cod = p.split('cod_municipio=')[1].split(os.sep)[0].split('/')[0]
        nb = pq.ParquetFile(p).read(columns=['nome_bairro']).to_pandas()['nome_bairro'].dropna().astype(str).str.strip()
        nb = nb[nb != '']
        reg.append(dict(cod_municipio=cod, ibge_n=nb.nunique()))
    ibge = pd.DataFrame(reg)
    x = ibge.merge(m[m.uf == 'SP'][['cod_municipio', 'n_bairros', 'dom']], on='cod_municipio', how='left')
    x['ibge'] = x.ibge_n.map(lambda n: 'sem bairro' if n == 0 else 'com bairro')
    x['cnefe'] = x.n_bairros.map(lambda n: '>=2 bairros' if n >= 2 else '<2')
    print('\nSP: IBGE NM_BAIRRO x CNEFE (municipios):\n', pd.crosstab(x.ibge, x.cnefe, margins=True))
    print('SP: mediana de bairros IBGE vs CNEFE nos que TEM IBGE:',
          x.loc[x.ibge_n > 0, 'ibge_n'].median(), x.loc[x.ibge_n > 0, 'n_bairros'].median())

t.to_json(os.path.join(OUT, 'cobertura_uf.json'), orient='records', force_ascii=False, indent=1)
print('FIM')
