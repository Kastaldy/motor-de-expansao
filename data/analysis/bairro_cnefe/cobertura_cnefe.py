"""BLK-BAIRRO-01 fase 1 -- cobertura de bairro do CNEFE 2022 (DSC_LOCALIDADE), por UF.

Le cada CSV oficial em blocos (so 6 colunas), classifica a localidade pela REGUA abaixo
(declarada antes de medir) e grava, por UF, dois agregados retomaveis:
  <out>/setor_<UF>.parquet : (cod_municipio, cod_setor, loc, classe, n_end, n_dom)
  <out>/grade_<UF>.parquet : (cod_municipio, loc, classe, lat3, lon3, n_dom)  -- grade de 0,001 grau
Nao grava endereco, numero, logradouro nem coordenada individual: so contagens.

REGUA (classe da localidade):
  VAZIO     nulo/vazio
  SEM_NOME  'SEM DENOMINACAO', 'NAO INFORMADO', 'S/N', 'IGNORADO'...
  CODIGO    so digitos/simbolos, ou '<SETOR|ZONA|AREA|REGIAO|QUADRA|GLEBA|BAIRRO|RP|AP|UR> <numero>'
  RURAL     qualquer nome com a palavra RURAL (ZONA RURAL, RORAINOPOLIS RURAL) ou INTERIOR
  MUNICIPIO igual ao nome do municipio (sem acento) ou 'SEDE'/'SEDE MUNICIPAL'
  BAIRRO    todo o resto (inclui CENTRO: e' bairro de verdade)
Uso: python -I cobertura_cnefe.py <dir_cnefe> <municipios_nomes.parquet> <out> [UF ...]
"""
import glob
import os
import re
import sys
import time
import unicodedata

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv

RAW, NOMES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
UFS = set(sys.argv[4:])
os.makedirs(OUT, exist_ok=True)


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.upper()).strip()


nomes = pd.read_parquet(NOMES)
NOME_MUNI = {str(c): norm(n) for c, n in zip(nomes['cod_municipio'], nomes['nome_municipio'])}

RE_SEM_NOME = re.compile(r'^(SEM DENOMINACAO|SEM NOME|NAO INFORMADO|NAO DECLARADO|IGNORADO|S/N|SN|S N|NI|NA|-+)$')
RE_CODIGO = re.compile(
    r'^[\d\W_]+$|^(SETOR|ZONA|AREA|REGIAO|QUADRA|GLEBA|BAIRRO|RP|AP|UR|UNIDADE|DISTRITO)\s*[-.:]?\s*[\dIVX]+[A-Z]?$'
)
RE_RURAL = re.compile(r'\bRURAL\b|^INTERIOR$')


def classe(loc: str, muni: str) -> str:
    if not loc:
        return 'VAZIO'
    if RE_SEM_NOME.match(loc):
        return 'SEM_NOME'
    if RE_CODIGO.match(loc):
        return 'CODIGO'
    if RE_RURAL.search(loc):
        return 'RURAL'
    if loc in ('SEDE', 'SEDE MUNICIPAL') or loc == NOME_MUNI.get(muni, '\0'):
        return 'MUNICIPIO'
    return 'BAIRRO'


COLS = ['COD_MUNICIPIO', 'COD_SETOR', 'DSC_LOCALIDADE', 'LATITUDE', 'LONGITUDE', 'COD_ESPECIE']
TIPOS = {c: pa.string() for c in COLS} | {'LATITUDE': pa.float64(), 'LONGITUDE': pa.float64()}

for caminho in sorted(glob.glob(os.path.join(RAW, '*.csv'))):
    uf = os.path.basename(caminho)[3:5]
    if UFS and uf not in UFS:
        continue
    alvo_s, alvo_g = os.path.join(OUT, f'setor_{uf}.parquet'), os.path.join(OUT, f'grade_{uf}.parquet')
    if os.path.exists(alvo_s) and os.path.exists(alvo_g):
        print(uf, 'ja feito', flush=True)
        continue
    t0 = time.time()
    leitor = pacsv.open_csv(
        caminho,
        read_options=pacsv.ReadOptions(block_size=64 << 20, encoding='latin-1'),
        parse_options=pacsv.ParseOptions(delimiter=';', quote_char=False),
        convert_options=pacsv.ConvertOptions(include_columns=COLS, column_types=TIPOS),
    )
    partes_s, partes_g, cache = [], [], {}
    for lote in leitor:
        df = lote.to_pandas()
        df['loc'] = df['DSC_LOCALIDADE'].fillna('').map(lambda x: cache.setdefault(x, norm(x)))
        chave = df['COD_MUNICIPIO'] + '|' + df['loc']
        unicos = pd.unique(chave)
        mapa = {k: classe(k.split('|', 1)[1], k.split('|', 1)[0]) for k in unicos}
        df['classe'] = chave.map(mapa)
        df['dom'] = (df['COD_ESPECIE'] == '1').astype('int32')
        df['cod_setor'] = df['COD_SETOR'].str.rstrip('P')
        partes_s.append(
            df.groupby(['COD_MUNICIPIO', 'cod_setor', 'loc', 'classe'], observed=True)
            .agg(n_end=('dom', 'size'), n_dom=('dom', 'sum')).reset_index()
        )
        g = df[(df['dom'] == 1) & df['LATITUDE'].notna()]
        partes_g.append(
            g.assign(lat3=(g['LATITUDE'] * 1000).round().astype('int32'),
                     lon3=(g['LONGITUDE'] * 1000).round().astype('int32'))
            .groupby(['COD_MUNICIPIO', 'loc', 'classe', 'lat3', 'lon3'], observed=True)
            .size().rename('n_dom').reset_index()
        )
    s = pd.concat(partes_s).groupby(['COD_MUNICIPIO', 'cod_setor', 'loc', 'classe'], observed=True)[['n_end', 'n_dom']].sum().reset_index()
    g = pd.concat(partes_g).groupby(['COD_MUNICIPIO', 'loc', 'classe', 'lat3', 'lon3'], observed=True)['n_dom'].sum().reset_index()
    s.rename(columns={'COD_MUNICIPIO': 'cod_municipio'}).to_parquet(alvo_s, index=False)
    g.rename(columns={'COD_MUNICIPIO': 'cod_municipio'}).to_parquet(alvo_g, index=False)
    print(uf, f'{s.n_end.sum():,} enderecos', f'{time.time() - t0:.0f}s', flush=True)
print('FIM', flush=True)
