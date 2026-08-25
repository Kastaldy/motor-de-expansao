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
- [DEC-023](DEC-023.md) — Visão Executiva 2.0: de mapa territorial a dashboard acionável da rede, com a primeira escrita do piloto; emenda a DEC-020 e a consequência (iii) da DEC-022; emendada pela DEC-027
- [DEC-024](DEC-024.md) — Extensão do escopo de coleta do GymScraping: nota in-app do WellHub (`partnerRating`) como agregado numérico (BLK-MA-08); emenda as partes 2 e 3 da DEC-013
- [DEC-025](DEC-025.md) — Critério de universo do coletor WellHub (vocabulário "V2") + taxonomia fora do hash de staleness, com bump para `snapshots_concorrentes_v2` (BLK-MA-11); emenda a parte 3 da DEC-013
- [DEC-026](DEC-026.md) — Gate do BLK-MA-09: rating como coluna-fato **sem peso** (molde do G-D2); o `v2` não é reativado e D-A/D-C ficam sem objeto (BLK-MA-09)
- [DEC-027](DEC-027.md) — Trilha de acesso do piloto web (quem fez o quê, retenção 90 dias): middleware com identidade Authelia + segundo volume `:rw` + Caddy access log + Authelia `info`; emenda o "único mount de escrita" da DEC-023
- [DEC-028](DEC-028.md) — A camada de M&A entra no piloto como **overlay de pressão competitiva** (não vulnerabilidade); emenda o §10 (overlay sai de "futuro") e o G-D1 (`flag_score_provisorio` passa a olhar o S6) — BLK-MA-13
- [DEC-029](DEC-029.md) — O sinal 6 passa a ser medido **por academia** (rota B, sem bump de série); emenda o §8.1, agregação do entregável deixa de ser `first` e o score vai a `v4` — BLK-MA-14
- [DEC-030](DEC-030.md) — A Conclusão do Relatório Pontual carimba **dois selos** independentes (demográfico e financeiro) e deixa de emitir veredito único; emenda 1: o gate E5 passa a valer nos dois modos
- [DEC-031](DEC-031.md) — Régua do percentil de renda setorial: MANTER a referência do M1 (a troca por régua setorial foi medida e refutada) — **PROPOSTA**
- [DEC-032](DEC-032.md) — O `k` de calibração da renda setorial é NACIONAL e único (`1,2334632197`): o cálculo dentro do laço por UF dava um `k` por estado — **PROPOSTA**
- [DEC-033](DEC-033.md) — As **independentes entram na oferta** do sinal 6, com metade do peso de uma unidade de rede; o insumo só tinha cadeias, então 37,8% do universo marcava `0` e **32,3% tinha sinal invisível**. Carimbo `universo_oferta`, auto-exclusão e dedup entre fontes; score vai a `v5` — BLK-MA-16 *(renumerada de DEC-030 em 2026-08-15: o número colidia com uma DEC-030 já existente na `main`)*
- [DEC-034](DEC-034.md) — As **unidades de REDE listadas pelo agregador** entram na oferta do sinal 6, com peso `1,0`; é a outra metade da DEC-033. Dedup própria contra `concorrentes_mapeados` (`rede` igual a 150 m **ou** qualquer rede a 50 m), auto-exclusão nos dois casos e decomposição por procedência. **A ordem muda** (Spearman `0,9912`; 12 trocas no top-100 do CSV) e três réguas visíveis no pin se movem — quatro bumps de série — BLK-MA-17 (metade 2)
- [DEC-035](DEC-035.md) — **Metade 1 do BLK-MA-17**: as unidades de REDE ganham diagnóstico visível com **fato e sem score** (S6 + fatos sem peso; nada de `score_vulnerabilidade`, porque S1/S3 medem outra coisa numa rede). Universo do sinal 1 intacto, precedência de pin herdada da dedup da DEC-034, e a auditoria do pin corrigida na causa — BLK-MA-17 (metade 1)
- [DEC-036](DEC-036.md) — Sinal 6 (pressão competitiva) entra no score com peso `0,10`, **condicionado ao insumo**; pesos do D4 seguem congelados e a soma-alvo vai a 1,10 (BLK-MA-12)
- [DEC-037](DEC-037.md) — Aba `imobiliaria` com **gate próprio** para a tela de imóveis (antes ela reusava o de `oportunidades`, o que tornava impossível restringir os imóveis sem tirar o funil de expansão de quem o usa): o **dossiê** do coletor fica só em `{imobiliaria}` e a **lista** agregada em `{mapa, imobiliaria}`, porque também alimenta os pins do Mapa Territorial; `imobiliaria` entra em `ABAS_SENSIVEIS` (fail-closed) e ganha trilha própria por GESTO, com mount `:ro` do artefato do coletor. **Emenda 1 (mesmo dia):** o ALCANCE da aba — filtro de UF server-side, desempate estável e `total_recorte` no payload; `m1_residual_fitness` SATURA (1.752 de 4.003 empatam em 100,0) e o corte caía DENTRO do empate, deixando 3 UFs de 6 e 18 dos 203 dossiês visíveis — **APROVADA** (2026-08-24)
- [DEC-038](DEC-038.md) — A **renda setorial não chegava a 21 UFs**: descartada em duas listas de colunas (`keep_cols` do híbrido e as fontes do trace censitário em `fase1_bi_exports`), com falha silenciosa porque a coluna existia e estava nula. Cobertura no que o piloto web serve: **18,1% (6 UFs) → 84,4% (27 UFs)**; Curitiba vai de 0 para 93 de 93 hexágonos com renda. M1 intacto, verificado por hash. Destrava o gate socioeconômico e a curva de penetração × renda — e **não** melhora previsão de desempenho
- [DEC-039](DEC-039.md) — **Cron MENSAL dos agregadores** (BLK-MA-21): 1a terca do mes 02:00 UTC; particao de DUAS chaves (`semana=X/fonte=Y`), porque duas cadencias escrevem na mesma semana ISO e `delete_matching` fazia a segunda apagar a primeira; retencao `26` -> **`78`** (com 26 um feed mensal para em 5,98 observacoes e NUNCA alcanca `MIN_SEMANAS = 8`); curadoria versionada com escolha de diretorio e **guarda de frescor**; `fontes_lidas` no parquet com bump `snapshots_concorrentes_v3` -> **`v4`** (1o bump COM serie viva); `--migrar-layout` explicito; e a fronteira com o BLK-MA-20 imposta POR CODIGO. **Emenda 1 (2026-08-25, painel adversarial):** rotação do consolidado (`--no-resume` só apaga o checkpoint, e o feed anexava safra sobre safra — o desempate por menor hash congelava a linha VELHA de quem mudou); `--no-resume` também no TotalPass, que **nunca recoletava**, e a régua de frescor sai do `mtime` para a coluna `data_coleta` (85 dias reportados como `0`); e a fronteira D9 vira **FAIL-CLOSED** — omitir `--fontes` aplica `("wellhub",)`, abrir exige `--todas-as-fontes`
