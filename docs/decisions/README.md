# Decisões registradas (DEC)

Corpo completo de cada decisão do projeto — **um arquivo por DEC**, com todas as suas emendas.

O **índice canônico** (data · criticidade · status) fica no `CLAUDE.md` §8. Esta pasta guarda o corpo;
o índice guarda a linha. Ao criar uma nova DEC: crie `DEC-0XX.md` aqui **e** adicione 1 linha no índice
do `CLAUDE.md` §8 — **não** cole o corpo no CLAUDE.md (regra "manter curto", topo do CLAUDE.md).
Emendas entram no próprio arquivo da DEC, não no índice.

> Nota de EOL: `docs/*.md` é normalizado para LF (`.gitattributes`, DEC-017).

## Índice

- [DEC-001](DEC-001.md) — Manter pesos/fórmula do `score_priorizacao` (M1) após backtest BLK-SCORE-02
- [DEC-002](DEC-002.md) — Critério geométrico híbrido no litoral (M1) e regeneração dos artefatos oficiais (BLK-FIX-06)
- [DEC-003](DEC-003.md) — Geração de candidatos por OVERLAP + limiar 0.05 (correção do BLK-FIX-06; BLK-FIX-06-B)
- [DEC-004](DEC-004.md) — Fundo de ruas por tiles online no Relatório Pontual Censitário (BLK-CENSO-01)
- [DEC-005](DEC-005.md) — Arquitetura e contrato da API GeoEspacial on-demand (BLK-API-01 / G1)
- [DEC-006](DEC-006.md) — Redefinição do gate do SAM: Faixa M1 elegível AND população ≥ 5000 (BLK-SAM-01)
- [DEC-007](DEC-007.md) — Afrouxar o gate do SAM: apenas Faixa M1 elegível AND população ≥ 5000 (reverte 2 sub-decisões da DEC-006; BLK-SAM-02)
- [DEC-008](DEC-008.md) — Supersessão do BLK-SCORE-05 pela epic BLK-DIM (Motor de Dimensionamento e Viabilidade)
- [DEC-009](DEC-009.md) — Pivô da epic BLK-DIM para "property-first" (viabilidade/break-even)
- [DEC-010](DEC-010.md) — Resolução de endereço por fetch HTTP na barra de busca do dashboard (BLK-UI-08)
- [DEC-011](DEC-011.md) — Fundo de ruas por tiles online no Relatório Municipal (BLK-RELMUN-01); critério dos hexágonos destacados
- [DEC-012](DEC-012.md) — Adoção da camada paralela de Demanda Revelada (H3 res-7, sem PII; BLK-TP-01)
- [DEC-013](DEC-013.md) — Coleta recorrente de concorrentes (GymScraping) automatizada na VPS + integração ao residual
- [DEC-014](DEC-014.md) — Score de retenção territorial (camada paralela M2 READ-ONLY sobre o M1; BLK-LTV-04)
- DEC-015 — *reservado* (a numeração pulou de 014 para 016)
- [DEC-016](DEC-016.md) — Portão da `main` por checks de CI (0 aprovações) e auto-merge de blocos Baixa/Média
- [DEC-017](DEC-017.md) — Normalização de EOL (`tasks/`+`docs/` em LF) + enxugamento do CODEOWNERS
- [DEC-018](DEC-018.md) — Vista aérea por tiles de satélite (Esri) no Relatório Pontual Censitário (BLK-SAT-01) — **APROVADA** (2026-07-23)
- [DEC-019](DEC-019.md) — Segundo dono autorizado a liberar merge Crítico (`@VinhoAbencoado`); emenda a blindagem #3 da DEC-016
- [DEC-020](DEC-020.md) — Escopo do corte do Streamlit pelo piloto web (BLK-WEB-11); emendada pela DEC-022
- [DEC-021](DEC-021.md) — Raio do Relatório Pontual Censitário passa de 1,5 km para 1,0 km; emenda a decisão-chave 5 da DEC-005
- [DEC-022](DEC-022.md) — Substituição total do Streamlit pelo piloto web: corte imediato, `dashboard.` vira host só de `/tiles/` + 301
- [DEC-023](DEC-023.md) — Visão Executiva 2.0: de mapa territorial a dashboard acionável da rede, com a primeira escrita do piloto; emenda a DEC-020 e a consequência (iii) da DEC-022
- [DEC-024](DEC-024.md) — Extensão do escopo de coleta do GymScraping: nota in-app do WellHub (`partnerRating`) como agregado numérico (BLK-MA-08); emenda as partes 2 e 3 da DEC-013
- [DEC-025](DEC-025.md) — Critério de universo do coletor WellHub (vocabulário "V2") + taxonomia fora do hash de staleness, com bump para `snapshots_concorrentes_v2` (BLK-MA-11); emenda a parte 3 da DEC-013
- [DEC-026](DEC-026.md) — Gate do BLK-MA-09: rating como coluna-fato **sem peso** (molde do G-D2); o `v2` não é reativado e D-A/D-C ficam sem objeto (BLK-MA-09)
