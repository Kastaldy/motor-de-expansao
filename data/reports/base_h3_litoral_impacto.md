# BLK-FIX-06 — Impacto do criterio HIBRIDO no litoral (Fase A, medicao em scratch)

- Data: 2026-06-03 09:43:58
- Resolucao H3: 7; criterio: centroide-dentro OU fracao_terra >= L
- Limiar default candidato (config): 0.2
- Total de hexes OFICIAL (criterio centroide atual): 1537950
- Fracao de terra: razao de areas em graus (EPSG:4674), interseccao calculada 1x por hex hoje-descartado.
- NENHUM artefato oficial foi escrito. Tudo em scratch (ver caminhos no fim).

## Tabela do LEQUE de limiares {0.15, 0.20, 0.25, 0.30}

> CAVEAT IMPORTANTE (massa demografica do leque): as colunas `soma_pop_total` /
> `soma_populacao_proxy` aqui sao SUPER-ESTIMADAS e NAO representam a populacao real
> dos hexes recuperados. Motivo: a `populacao_proxy` do M1 distribui a populacao do
> municipio pelos hexes do municipio (`populacao_proxy = pop_total_municipio /
> total_hex_municipio`); ao enriquecer SO os hexes recuperados (em isolamento, sem o
> conjunto completo de hexes do municipio), o denominador colapsa e cada hex recebe
> ~a populacao do municipio inteiro (ex.: hex do litoral do Rio recebe ~6,2 M = pop do
> municipio). Use estas colunas apenas como ORDENACAO RELATIVA entre limiares
> (monotonicidade), nao como massa absoluta. A massa/efeito REAL e capturada no DELTA
> CARO abaixo (enriquecimento na base nacional COMPLETA), que e o numero confiavel
> para a DEC. `renda_media_entram` (per capita) nao sofre esse vies e e confiavel.

| limiar_L | hexes_entram_total | hexes_por_uf | soma_pop_total (SUPERESTIMADA, ver caveat) | soma_populacao_proxy (SUPERESTIMADA) | renda_media_entram |
|---|---|---|---|---|---|
| 0.15 | 494 | AC:24, AL:1, AM:57, AP:14, BA:11, CE:13, ES:2, GO:1, MA:36, MS:32, MT:11, PA:46, PB:1, PE:5, PI:1, PR:10, RJ:25, RN:6, RO:36, RR:51, RS:75, SC:18, SE:2, SP:16 | 72807538.0 | 72807538.0 | 1080.72 |
| 0.2 | 474 | AC:24, AL:1, AM:57, AP:14, BA:10, CE:13, ES:2, GO:1, MA:33, MS:31, MT:11, PA:43, PB:1, PE:4, PI:1, PR:10, RJ:23, RN:6, RO:35, RR:49, RS:73, SC:16, SE:2, SP:14 | 71583581.0 | 71583581.0 | 1070.26 |
| 0.25 | 428 | AC:22, AL:1, AM:51, AP:14, BA:10, CE:12, ES:2, GO:1, MA:32, MS:30, MT:9, PA:40, PB:1, PE:3, PI:1, PR:8, RJ:18, RN:6, RO:34, RR:43, RS:62, SC:14, SE:2, SP:12 | 54063352.0 | 54063352.0 | 1048.34 |
| 0.3 | 383 | AC:22, AL:1, AM:43, AP:13, BA:10, CE:12, ES:2, GO:1, MA:25, MS:30, MT:7, PA:35, PB:1, PE:2, PI:1, PR:8, RJ:16, RN:6, RO:30, RR:40, RS:54, SC:11, SE:2, SP:11 | 50132280.0 | 50132280.0 | 1041.86 |

## Total de hexes antes vs. depois

| limiar L | total_apos | recuperados |
|---|---|---|
| 0.15 | 1538444 | 494 |
| 0.2 | 1538424 | 474 |
| 0.25 | 1538378 | 428 |
| 0.3 | 1538333 | 383 |

## Distribuicao (quartis) de fracao_terra dos hexes que entram

- Geral (>= 0.15): {'n': 494, 'min': 0.1533, 'q25': 0.3214, 'mediana': 0.399, 'q75': 0.4588, 'max': 0.8649}
- >= 0.2: {'n': 474, 'min': 0.2004, 'q25': 0.333, 'mediana': 0.4019, 'q75': 0.4598, 'max': 0.8649}
- >= 0.3: {'n': 383, 'min': 0.3006, 'q25': 0.3729, 'mediana': 0.4242, 'q75': 0.4717, 'max': 0.8649}

## DELTA CARO — percentis nacionais e score_priorizacao dos hexes EXISTENTES (0.20 e 0.30)

| limiar | hexes_existentes_comparados | delta_renda_pct_nacional_min | delta_renda_pct_nacional_mediana | delta_renda_pct_nacional_max | delta_pop_pct_nacional_min | delta_pop_pct_nacional_mediana | delta_pop_pct_nacional_max | delta_score_priorizacao_min | delta_score_priorizacao_mediana | delta_score_priorizacao_max | score_n_muda_alem_0p5 | score_pct_muda_alem_0p5 | score_maior_deslocamento_abs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.2 | 1537950.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.01 | 0.0 | 0.0 | 0.01 |
| 0.3 | 1537950.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.01 | 0.0 | 0.0 | 0.01 |

## DELTA CARO — recorte top-20%/UF (brasil_priorizados) (0.20 e 0.30)

| limiar | top20_oficial | top20_novo | entram_no_recorte | saem_do_recorte |
|---|---|---|---|---|
| 0.2 | 307579.0 | 307674.0 | 136.0 | 41.0 |
| 0.3 | 307579.0 | 307655.0 | 104.0 | 28.0 |

> Nota: `top20_oficial` (307.579) e lido do `brasil_priorizados.parquet` oficial em
> disco (gerado em 2026-05-26). `top20_novo` e regerado em scratch com a base ampliada.
> A floor(20% por UF) muda quando o total de hexes da UF cresce, por isso o tamanho do
> recorte difere ligeiramente. `entram_no_recorte` inclui os proprios hexes costeiros
> recuperados (quando entram no top-20% da UF) mais alguns hexes de borda que mudam de
> lado pela leve mudanca de contagem; `saem_do_recorte` sao hexes de borda deslocados.

## Interpretacao (insumo direto da DEC-002)

- **Impacto nos hexes EXISTENTES e desprezivel** em 0.20 E 0.30: mediana de delta = 0.0
  em `renda_pct_nacional`, `pop_pct_nacional` e `score_priorizacao`; deslocamento maximo
  de `score_priorizacao` = 0.01; ZERO hexes mudam alem de +-0.5. Razao: 474 (0.20) /
  383 (0.30) hexes novos sobre 1.537.950 existentes nao movem percentis nacionais
  praticamente nada. O risco ALTO levantado no plano (deslocamento de percentis) NAO se
  materializou nesta escala de recuperacao.
- **0.20 vs 0.30:** 0.20 recupera 474 hexes (incl. orla de Praia Grande e mais do litoral
  RJ/NE/Norte); 0.30 recupera 383 (perde 91, sobretudo costeiros com 0.20<=frac<0.30,
  ex.: Praia Grande `87a810c02ffffff` frac=0.231 SAI em 0.30). Ambos com impacto nulo no
  score dos existentes. A escolha entre 0.20 e 0.30 e essencialmente quanto litoral
  povoado incluir vs. quao conservador ser contra borda oceanica — decisao da DEC.
- **Candidato 0.20 (ajuste humano):** inclui Praia Grande; quartis de frac dos que entram
  em 0.20 = [min 0.20, q25 0.33, mediana 0.40, q75 0.46, max 0.86] — ou seja, a maioria
  dos recuperados tem fracao de terra bem acima do piso, nao sao "esquinas" oceanicas.

## Repro do litoral (hexes hoje ausentes que reaparecem)

| alvo | hex_recuperado | fracao_terra | ausente_hoje | reaparece_a_partir_de | n_vizinhos_recuperados |
|---|---|---|---|---|---|
| Praia Grande (SP) | 87a810c02ffffff | 0.2312 | True | 0.15 | 1 |
| Litoral RJ (Rio) | 87a8a078cffffff | 0.4008 | True | 0.15 | 4 |

## Caminhos de SCRATCH gerados (prova de nao-escrita em oficiais)

- base scratch (piso 0.15): data\staging\brasil_litoral_tmp/uf=XX/hexagonos.parquet
- vetor fracao_terra: data\staging\brasil_litoral_tmp\fracao_terra_descartados.parquet
- bases por limiar caro: data/staging/brasil_litoral_tmp_020/ , .../brasil_litoral_tmp_030/
- estrutural/priorizados scratch: data/staging/brasil_estrutural.0NN.tmp.parquet , brasil_priorizados.0NN.tmp.parquet
- CSV auxiliar do leque: data\reports\base_h3_litoral_leque.csv

## Nota de honestidade (delta caro)

- Delta caro medido em 0.20 E 0.30 (enriquecimento estrutural+priorizacao+camada de oportunidade em scratch).
- 0.15 e 0.25 reportados apenas com contagem/massa (leque), por design do plano v2.

