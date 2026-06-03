# BLK-FIX-06-B — Leque de limiares de recuperacao costeira (medicao, scratch)

- Data: 2026-06-03 12:26:34
- Geracao de candidatos por OVERLAP (corrigida). Vetor de fracao-de-terra dos hexes de mar.
- Universo oficial atual: 1.538.424 (limiar 0.20 = +2229 sobre os candidatos overlap).
- NENHUM artefato oficial tocado.

## Recuperados por limiar (re-filtragem do vetor)

| limiar_L | recuperados_total | quartis_fracao | por_uf |
|---|---|---|---|
| 0.05 | 3890 | {'n': 3890, 'min': 0.05, 'q25': 0.127, 'mediana': 0.232, 'q75': 0.353, 'max': 0.865} | AC:254, AL:40, AM:488, AP:204, BA:151, CE:83, ES:81, MA:242, MS:232, MT:140, PA:278, PB:23, PE:30, PI:9, PR:93, RJ:146, RN:70, RO:174, RR:296, RS:635, SC:105, SE:23, SP:93 |
| 0.1 | 3234 | {'n': 3234, 'min': 0.1, 'q25': 0.178, 'mediana': 0.27, 'q75': 0.378, 'max': 0.865} | AC:209, AL:29, AM:413, AP:168, BA:130, CE:70, ES:64, MA:191, MS:198, MT:117, PA:224, PB:19, PE:25, PI:6, PR:73, RJ:131, RN:59, RO:143, RR:248, RS:528, SC:93, SE:17, SP:79 |
| 0.15 | 2692 | {'n': 2692, 'min': 0.15, 'q25': 0.224, 'mediana': 0.304, 'q75': 0.396, 'max': 0.865} | AC:180, AL:24, AM:353, AP:137, BA:108, CE:60, ES:51, MA:161, MS:160, MT:98, PA:179, PB:14, PE:20, PI:6, PR:63, RJ:105, RN:49, RO:120, RR:216, RS:438, SC:79, SE:16, SP:55 |
| 0.2 | 2229 | {'n': 2229, 'min': 0.2, 'q25': 0.264, 'mediana': 0.335, 'q75': 0.415, 'max': 0.865} | AC:150, AL:19, AM:284, AP:117, BA:89, CE:50, ES:47, MA:130, MS:141, MT:82, PA:151, PB:12, PE:16, PI:5, PR:50, RJ:87, RN:42, RO:99, RR:183, RS:350, SC:67, SE:13, SP:45 |
| 0.25 | 1790 | {'n': 1790, 'min': 0.25, 'q25': 0.305, 'mediana': 0.365, 'q75': 0.432, 'max': 0.865} | AC:119, AL:16, AM:231, AP:95, BA:73, CE:38, ES:42, MA:95, MS:114, MT:69, PA:117, PB:8, PE:13, PI:4, PR:41, RJ:69, RN:35, RO:83, RR:141, RS:284, SC:57, SE:10, SP:36 |

## Repro dos hexes da orla apontados pelo usuario

| alvo | hex_id | fracao_terra | entra_a_partir_de |
|---|---|---|---|
| Orla Mongagua (SP) | 87a810998ffffff | 0.218 | 0.05 |
| Orla PG-Mongagua (SP) | 87a810d4cffffff | 0.104 | 0.05 |
| Orla Itanhaem (SP) | 87a810903ffffff | 0.035 | nan |

## Leitura

- Limiar MENOR => mais orla fina entra, mas tambem mais hex majoritariamente oceanico
  (baixa pop; no mapa cairia no corte cinza <5k, mas passa a EXISTIR em vez de ausente).
- Impacto no score dos hexes existentes ja medido ~nulo em 0.20 (+2.446); limiares menores
  adicionam hexes de pop ainda menor => impacto esperado igualmente desprezivel.

