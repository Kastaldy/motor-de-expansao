# BLK-FIX-06-B — Impacto da geracao de candidatos por OVERLAP (medicao, scratch)

- Data: 2026-06-03 12:36:15
- Limiar M1_HEX_LAND_FRACTION_MIN (DEC-002, inalterado): 0.05
- Fix: candidatos por containment OVERLAP (antes: centro). Filtro de fracao-de-terra inalterado.
- NENHUM artefato oficial escrito. Tudo em scratch.

## Universo de hexes

- Oficial atual (BLK-FIX-06, +474): **1538424**
- Novo (06-B, overlap): **1542531**
- Recuperados pelo 06-B: **+4107**  | perdidos: -0
- Recuperados por UF: AC:259, AL:40, AM:503, AP:207, BA:152, CE:83, ES:83, MA:276, MS:238, MT:142, PA:303, PB:27, PE:31, PI:9, PR:98, RJ:174, RN:70, RO:191, RR:312, RS:665, SC:118, SE:23, SP:103

## Delta nos hexes EXISTENTES (percentis nacionais + score_priorizacao)

- {'hexes_existentes_comparados': 1538424, 'delta_renda_pct_nacional_mediana': 0.0, 'delta_renda_pct_nacional_max': 0.0002, 'delta_pop_pct_nacional_mediana': 0.0001, 'delta_pop_pct_nacional_max': 0.0002, 'delta_score_priorizacao_mediana': 0.01, 'delta_score_priorizacao_max': 0.02, 'score_n_muda_alem_0p5': 0, 'score_maior_deslocamento_abs': 0.02}

## Recorte top-20%/UF (brasil_priorizados)

- {'top20_oficial': 307674, 'top20_novo': 308494, 'entram': 1148, 'saem': 328}

## Repro dos hexes da orla (apontados pelo usuario)

| alvo | hex_id | no_oficial_atual | no_novo_06b | recuperado_por_06b |
|---|---|---|---|---|
| Orla Mongagua (SP) | 87a810998ffffff | False | True | True |
| Orla PG-Mongagua (SP) | 87a810d4cffffff | False | True | True |
| Orla Itanhaem (SP) | 87a810903ffffff | False | False | False |
| Orla Praia Grande recuperada (06) | 87a810c02ffffff | True | True | False |

## Scratch gerado (prova de nao-escrita em oficiais)

- base: data\staging\brasil_litoral06b_tmp/uf=XX/hexagonos.parquet
- estrutural/priorizados: data/staging/*.06b.tmp.parquet

