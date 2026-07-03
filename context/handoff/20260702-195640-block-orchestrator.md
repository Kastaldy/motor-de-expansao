# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-TP-06-FU2 — Candidato C do residual: decay ~2 km nas academias de bairro (k-ring H3) + capacidade de CLUBE real por rede (data/validacao/)**

Estende `revalidacao_residual_candidatos.py` com um NOVO vetor `residual_cand_C` que corrige as 2 crudezas do Candidato A (NO-GO): (1) aplica um decay de proximidade (~2 km) também às academias de bairro, em vez de somar contagem crua flat por hex; (2) pondera a oferta consumida pela **capacidade de CLUBE real por rede**, lida anti-PII de `data/validacao/`, no lugar do 2500 flat e das medianas ~340 de bairro. Valida OUT-OF-FOLD vs baseline (+0,3119) com o MESMO harness/seed/recortes do FU1 e decide honestamente (DEC-008) se o C vence e sobrevive fora de SP/MG/RJ. READ-ONLY sobre o M1; só em memória/relatório.

## Objetivo
Rodar o Candidato C bem-feito (decay ~2 km nas bairro via k-ring H3 + capacidade de clube real por rede) e decidir, out-of-fold vs baseline, se ele supera o residual atual e generaliza fora do metropolitano — distinguindo "hipótese errada" de "execução crua" do Candidato A.

## Escopo permitido
- ESTENDER `src/motor_expansao/demanda_revelada/revalidacao_residual_candidatos.py` adicionando `residual_cand_C` e sua validação/comparação, SEM tocar as funções do baseline nem do Candidato A (estrutura já extensível: dedup fino isolado em `alunos_menores_add_por_hex`, construção em `construir_residuais_candidatos`).
- ADICIONAR um passo de fronteira anti-PII que lê `data/validacao/` (3 xlsx) e extrai APENAS a **capacidade de clube (mediana de alunos/unidade) POR REDE** — nenhum nome/endereço/coord/linha individual atravessa a fronteira; só sai o dicionário `rede → mediana_alunos`.
- Aplicar o decay de ~2 km às academias de bairro por **aproximação de vizinhança H3 (k-ring)** — coords das bairro estão dropadas (só `hex_id`). Os concorrentes têm `lat/lng` point-level (decay 2 km exato já materializado em produção como `oferta_efetiva_mapeada_2km`).
- Recompor `oferta_consumida_C` = (concorrentes ponderados pela capacidade real por rede, com o mesmo decay 2 km point-level do baseline) + (bairro decaídas por k-ring, ponderadas por capacidade/dedup fino) e `residual_cand_C = clip(100·max(sam_fitness_potencial − oferta_consumida_C, 0)/2500, 0, 100)` (denominador do clip = `CAP_REF=2500` INTOCADO).
- Validar `residual_cand_C` out-of-fold (k-fold 5×5, seed=42, IC95 bootstrap, R² in-sample banido, Δ pareado vs baseline, 3 recortes completo/metro/fora), estender o veredito e o relatório markdown (gitignored, sem PII).
- Fixtures sintéticas para a nova capacidade por rede e para o k-ring; testes unitários do novo caminho.

## Fora de escopo
- QUALQUER escrita em artefato M1 oficial ou na fórmula do `score_oportunidade_residual` em produção; NÃO regenerar `hexagonos_mercado_mapeado.parquet` nem derivados. Candidato C só EM MEMÓRIA/relatório.
- Alterar `preparar_dados`/harness de `calibracao_residual.py` (API estável do irmão — só reusar).
- Alterar baseline ou Candidato A (reproduzir idênticos ao FU1).
- Usar `capacidade_media_por_rede.parquet` (medianas ~340 de bairro) como proxy de capacidade de CLUBE — é justamente o erro que o FU2 corrige.
- Versionar/copiar/logar a fonte real de `data/validacao/` ou qualquer PII; tocar `NAO_ABRA/`.
- Importar de `pipelines/m1`, `dashboard`, `censo_*`, `api`, `config.py` raiz, `pipelines.calcular_colunas_mercado`, `pipelines.enriquecimento_espacial_hexagonos`.
- res-8, ticket/receita, Huff completo, dedup grosseiro, integração ao dashboard/produção (são BLK-TP-09/futuros sob gate).

## Arquivos que devem ser lidos
- `CLAUDE.md` (§1, §2, §4, §5; DEC-008, DEC-009, DEC-012, DEC-013)
- `tasks/current_task.md`
- `src/motor_expansao/demanda_revelada/revalidacao_residual_candidatos.py`
- `src/motor_expansao/demanda_revelada/calibracao_residual.py` (harness: `_selecionar_alpha_e_oof`, `_metodo_validacao`, `_ic_bootstrap_r2`, `_ic_bootstrap_rho`, `_rho_oof`, `SEED`, `N_BOOTSTRAP`)
- `src/motor_expansao/demanda_revelada/contrato.py` (`COLUNAS_PII_PROIBIDAS`)
- `docs/modelo_mercado_hexagonos.md` (§5.3 pesos de proximidade `peso_2km`/`oferta_efetiva_mapeada_2km`; §5.6 composição de `oferta_consumida_*`/`oferta_efetiva_disponivel`)
- `data/validacao/README.md`
- `tests/unit/test_demanda_revelada_revalidacao_candidatos.py` (padrão de fixtures/teste do FU1, se existir)

## Arquivos que podem ser alterados
- `src/motor_expansao/demanda_revelada/revalidacao_residual_candidatos.py` (ESTENDER — não reescrever baseline/A)
- `tests/unit/test_demanda_revelada_revalidacao_candidatos.py` (novos testes do Candidato C + fixtures sintéticas)
- (relatório gerado em runtime) `data/analysis/revalidacao_residual_candidatos.md` — gitignored, sem PII (não é código-fonte a commitar como artefato de teste)

## Capacidade de clube por rede (validacao, anti-PII, só agregados)
Medido nesta sessão — SÓ nomes de coluna, contagens e a **mediana agregada de alunos/unidade por rede** (nenhuma linha/nome/endereço/coord reportado ou persistido):

| Rede (validacao) | Arquivo | Coluna de alunos/unidade | N unidades | **Mediana alunos/clube** |
|---|---|---|---:|---:|
| **Smart Fit** | `KPIs_Smart_2025_02 (1).xlsx` (sheet `Base`, painel 37 meses × unidade; usar o mês mais recente por unidade) | `Alunos Totais SF` | 952 (últ. mês) | **~2.370** (média ~2.374; p25 1.839 / p75 2.871) |
| **Sky Fit** | `Sky Fit dados.xlsx` (sheet `Sell Out`, header na linha 3) | `Alunos EVO`+`Alunos Gympass`+`Alunos TotalPass` (total do clube) | 315 | **~2.191** (EVO-only ~944) |
| **Engenharia do Corpo** | `academias_engenharia_do_corpo.xlsx` (sheet `Academias`) | `Alunos Totais` | 58 | **~3.106** (p25 2.432 / p75 3.870) |

- **Ordem de grandeza vs ~340 de bairro:** capacidade de clube real ≈ **2.200–3.100 alunos/unidade = ~7–9× as medianas ~340** de `capacidade_media_por_rede.parquet` (footprint de bairro). Isso CONFIRMA que as medianas de bairro são inadequadas como proxy de capacidade de clube (motivo do FU2). Notavelmente, a capacidade real é **próxima do 2500 flat atual** — a correção de capacidade por rede é mais um refino do que uma virada; o Planner deve dimensionar expectativa (o ganho maior tende a vir do decay das bairro, não da re-capacidade das grandes).
- **Cobertura vs fallback:** das 28 redes de `concorrentes_mapeados`, só **smart_fit (999 pontos) e engenharia_do_corpo (63)** casam diretamente com validacao = **1.062 de 3.179 pontos válidos (33,4%)**. **`skyfit` NÃO é rede mapeada** em `concorrentes_mapeados` → a capacidade Sky serve como **âncora/prior de capacidade low-cost**, não como peso direto. Restam **~26 redes (~66,6% dos pontos) SEM capacidade de clube em validacao → fallback obrigatório declarado.** Fallback recomendado a decidir no gate: `2.500` (§4, atual) OU a mediana das capacidades de clube reais (~2.200–2.500, coerente com o segmento low-cost); NÃO usar as medianas ~340 de bairro para as grandes.
- **Anti-PII confirmado:** os 3 xlsx são gitignored (`*.xlsx` no `.gitignore`; `git check-ignore` = IGNORED nos 3). A extração ocorre na FRONTEIRA: lê o xlsx, agrega a mediana POR REDE, descarta o DataFrame com PII; só o dicionário `rede → capacidade` (e opcionalmente contagem N) segue adiante. `COLUNAS_PII_PROIBIDAS` + assert no relatório permanecem como rede de segurança.

## Viabilidade do decay (point-level vs H3 k-ring)
- **Concorrentes = point-level EXATO.** `concorrentes_mapeados.parquet` (3.296 linhas) TEM `lat`/`lng` → o decay de 2 km é o mesmo do baseline em produção: `peso_2km = max(0, 1 − dist_m/2000)` e `oferta_efetiva_mapeada_2km = Σ peso_2km` (já materializado no parquet de mercado). **Para o Candidato C ser comparável ao baseline, a oferta de concorrentes deve reproduzir esse mesmo decay 2 km point-level**, só trocando o peso de capacidade de `2500` flat por `capacidade_por_rede[rede]` (com fallback). Recomenda-se reaproveitar `oferta_efetiva_mapeada_2km`/`n_*_2km` do parquet quando possível para não re-derivar distâncias (o módulo é disjunto; se precisar de distância por rede, é Haversine local, sem importar pipeline).
- **Bairro = SÓ k-ring H3 (coords dropadas no anti-PII do TP-08).** `oferta_academias_menores_rede_h3.parquet` tem apenas `hex_id` (sem lat/lng) → point-level impossível; usar vizinhança H3 `grid_disk(hex, k)` como proxy do raio de 2 km.
- **Geometria res-7 MEDIDA (corrige a suposição da tarefa):** aresta média **~1,406 km**, área ~5,16 km², espaçamento centro-a-centro **~2,436 km** (a tarefa dizia "1,2 km/hex, k=1 ≈ 2,5 km" — **impreciso**). Portanto:
  - **k=0** (1 célula): cobertura ~raio 1,4 km → **subestima** 2 km.
  - **k=1** (7 células): alcance centro-externo ~2,44 km, cobertura ~raio 3,8 km → **superestima** 2 km (é o mais próximo de um "vizinho de 2 km", mas espalha demais).
  - **k=2** (19 células) ~raio 6,3 km → longe demais.
  - **Recomendação: k=1 como aproximação do raio de 2 km, com peso decrescente por anel** (ex.: hex central peso 1,0; anel k=1 peso ~0,5, análogo ao `peso_2km` linear), em vez de k=1 flat — assim o overshoot de ~3,8 km é atenuado e o decay fica na mesma família do point-level. **Trade-off explícito:** k=1 flat espalha oferta por ~3,8 km (superconsumo, empurra o residual para baixo demais e pode replicar o viés de co-localização que matou o Candidato A); k=0 ignora vizinhança (subconsumo). O peso por anel é o meio-termo honesto; o Planner deve travar a escolha (k=1 ponderado vs k=1 flat vs k=0) como decisão de produto no gate, e o Builder deve rodar ao menos k=1-ponderado. As coords das bairro têm arredondamento ~1 km na origem, o que já adiciona ruído ao join res-7 — mais um argumento contra precisão excessiva.
- **Comparabilidade com o baseline:** o baseline em produção compõe `oferta_consumida_total_estimada = oferta_efetiva_mapeada_2km·2500 (concorrentes, decay 2 km real) + oferta_consumida_ultra_estimada`. O Candidato C deve partir EXATAMENTE dessa base e (a) trocar o `·2500` por capacidade real por rede no termo de concorrentes, e (b) SOMAR o termo novo de bairro decaídas por k-ring (com dedup fino já isolado em `alunos_menores_add_por_hex` — mas agora decaído, não flat). Assim a diferença medida isola as 2 correções, não muda o denominador do clip.

## Critérios de aceite
- `residual_cand_C` construído EM MEMÓRIA; baseline e Candidato A reproduzem os números do FU1 byte-a-byte (N=16.411; baseline R²_oof ~+0,3119, rho_oof ~+0,4615).
- Capacidade de clube por rede lida de `data/validacao/` na FRONTEIRA anti-PII: nenhum nome/endereço/coord/linha individual persistido em artefato/log/teste; só `rede → capacidade` agregada sai; teste garante que a fonte não é versionada e que nenhuma coluna de `COLUNAS_PII_PROIBIDAS` vaza no relatório.
- Fallback de capacidade para as ~26 redes sem dado em validacao é DECLARADO e testado (valor travado no gate: 2500 ou mediana das reais).
- Concorrentes usam decay 2 km point-level (mesmo do baseline); bairro usam k-ring H3 com a escolha de `k`/peso travada e justificada; geometria res-7 documentada (aresta ~1,4 km, espaçamento ~2,44 km).
- Validação out-of-fold: k-fold 5×5, seed=42, IC95 bootstrap, R² in-sample BANIDO do veredito, Δ pareado vs baseline (mesmos folds), 3 recortes (completo/metro SP-MG-RJ/fora). `vence_candidato_c` ⇔ Δ pareado > 0 (IC95 não cruza zero) NO COMPLETO **E** FORA de SP/MG/RJ.
- Veredito honesto emitido (APLICAR_C / NAO_APLICAR); **NO-GO é resultado VÁLIDO** e deve ser aceito sem forçar recalibração.
- Relatório markdown gitignored atualizado (baseline + A + C + Δ pareado + recortes + nota honesta/confounds), sem PII (`_assert_sem_pii_no_relatorio` passa).
- Suite unitária verde (`pytest -q`); ruff + mypy limpos; nenhum import de m1/dashboard/censo/api/config; nenhum artefato M1 alterado (mtime dos oficiais inalterado).
- `tasks/backlog.md` (BLK-TP-09) atualizado conforme o veredito de C no fechamento (passo pós-QA, não requisito de teste).

## Criticidade classificada
**Alta** (modelagem/validação READ-ONLY sobre o M1, mas com ingestão de dados REAIS com PII na origem — `data/validacao/` — exigindo gate humano de anti-PII + modelagem). NÃO toca `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos oficiais do M1 → não é Crítica; a fronteira anti-PII e a decisão de fallback/`k` justificam a revisão humana.

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA — modelagem + anti-PII de data/validacao + escolha de `k`/fallback]** → Builder → QA (Opus 4.8)

## Riscos identificados
- **k-ring não bate 2 km exato** (res-7 espaça ~2,44 km): k=1 cobre ~3,8 km (overshoot), k=0 ~1,4 km (undershoot). Risco de o k=1 flat re-espalhar oferta e reproduzir o viés de co-localização bairro↔demanda que causou o NO-GO do Candidato A → recomendar k=1 PONDERADO por anel; travar no gate.
- **Capacidade real ≈ 2500 flat** (Smart ~2370, Sky ~2191, Eng ~3106): a re-capacidade das grandes tende a mover pouco o residual; o sinal do C virá majoritariamente do termo de bairro. Expectativa de ganho modesto — NO-GO plausível e aceitável (DEC-008).
- **Cobertura de capacidade real baixa (33,4% dos pontos; só smart_fit + engenharia)**: ~66,6% dependem de fallback → o "peso por rede" é parcialmente uniforme na prática; o fallback escolhido domina o resultado. Documentar sensibilidade ao fallback.
- **Sky Fit não é rede mapeada** em `concorrentes_mapeados` → sua capacidade não vira peso direto; só prior/âncora. Não inventar um join Sky↔concorrentes.
- **PII na origem** (nomes/endereços/coords nos 3 xlsx, e coords/nome_unidade em `concorrentes_mapeados`): risco de vazamento em log/relatório/teste → agregação na fronteira + `_assert_sem_pii_no_relatorio` + fixtures sintéticas obrigatórios.
- **Viés metropolitano** (SP/MG/RJ ~metade do join; cobertura ~1% do universo — DEC-012): qualquer ganho só conta se sobrevive FORA de SP/MG/RJ.
- **DEC-009:** `membros` é ALVO OBSERVADO; proibido virar preditor geográfico de magnitude.

## Guardrails ativos
- **§5 (READ-ONLY M1):** zero recálculo de score/pesos/carteira/plano/artefatos oficiais; NÃO alterar a fórmula do residual em produção nem regenerar `hexagonos_mercado_mapeado.parquet`. Candidato C só EM MEMÓRIA/relatório.
- **DEC-001:** pesos `renda=0.40`/`pop=0.60` e fórmula do `score_priorizacao` INALTERADOS.
- **DEC-008:** out-of-fold vs baseline da média; R² in-sample BANIDO; IC95 seed=42; Δ pareado; NO-GO é resultado válido.
- **DEC-009:** demanda (`membros`) é ALVO OBSERVADO; nunca preditor geográfico de magnitude.
- **DEC-012 (anti-PII):** `data/validacao/` são DADOS REAIS gitignored — agregar capacidade POR REDE na fronteira e DESCARTAR qualquer PII (nome/endereço/coord); zero PII em artefato/log/teste; fixtures sintéticas; nunca versionar a fonte real.
- **DEC-013:** oferta das academias menores entra só na camada de mercado/residual (candidata), COM dedup fino por rede; READ-ONLY sobre M1 e censitário.
- **Isolamento (DEC-012):** módulo `demanda_revelada/` NÃO importa de `pipelines/m1`, `dashboard`, `censo_*`, `api`, `config.py` raiz, `pipelines.calcular_colunas_mercado`, `pipelines.enriquecimento_espacial_hexagonos`.
