"""BLK-BAIRRO-01: bairro DOMINANTE por setor censitario, do CNEFE 2022 (agregado, sem endereco).

Uma linha por setor: cod_setor, cod_municipio, uf, bairro_cnefe (nome cru do IBGE, MAIUSCULO e
sem acento), classe (BAIRRO/MUNICIPIO/RURAL/CODIGO/SEM_NOME/VAZIO, regua da fase 1),
participacao (fracao dos enderecos do setor no bairro dominante), n_enderecos, n_domicilios.
Particionado por UF: <saida>/uf=XX/part-000.parquet
Entrada: os `setor_<UF>.parquet` de `cobertura_cnefe.py` (fase 1). Saida em producao (DEC-076):
<MOTOR_DATA_DIR>/staging/bairro_cnefe_setor/. Uso: python -I artefato_bairro_setor.py <entrada> <saida>
"""
import glob, os, sys
import pandas as pd
ENTRADA, SAIDA = sys.argv[1], sys.argv[2]
total = 0
for f in sorted(glob.glob(os.path.join(ENTRADA, 'setor_*.parquet'))):
    uf = f[-10:-8]
    s = pd.read_parquet(f)
    tot = s.groupby('cod_setor').agg(n_enderecos=('n_end', 'sum'), n_domicilios=('n_dom', 'sum'))
    dom = (s.sort_values(['cod_setor', 'n_end', 'loc'], ascending=[True, False, True])
             .drop_duplicates('cod_setor').set_index('cod_setor'))
    out = tot.join(dom[['cod_municipio', 'loc', 'classe', 'n_end']])
    out['participacao'] = (out.pop('n_end') / out['n_enderecos']).round(4)
    out = out.rename(columns={'loc': 'bairro_cnefe'}).reset_index()
    out.insert(2, 'uf', uf)
    out = out[['cod_setor', 'cod_municipio', 'uf', 'bairro_cnefe', 'classe', 'participacao', 'n_enderecos', 'n_domicilios']]
    os.makedirs(os.path.join(SAIDA, f'uf={uf}'), exist_ok=True)
    out.to_parquet(os.path.join(SAIDA, f'uf={uf}', 'part-000.parquet'), index=False)
    total += len(out)
print('setores', total)
