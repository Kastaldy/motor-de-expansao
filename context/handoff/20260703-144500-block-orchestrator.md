# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade **Alta** → esteira com REVISÃO HUMANA de modelagem antes do Builder)

## Bloco refinado
**BLK-TP-07 — Huff/gravitacional de captura de concorrentes com demanda observada (reabertura da Camada 2 do BLK-DIM).**

Modelar a **captura/share gravitacional (Huff)** de um ponto/hex candidato — atratividade dos concorrentes × distância, com saturação e canibalização da rede Ultra — e **validá-la out-of-fold contra a demanda OBSERVADA** (`membros` / `alunos_parceiras` da camada Demanda Revelada, casada por `hex_id`), sob a disciplina DEC-008. Emite **veredito honesto GO/NO-GO** em `data/analysis/` (gitignored). É a reabertura destravada pelo BLK-TP-05 (GO demanda→captura).

**Precedente crítico que o Planner DEVE ler:** já existe `src/motor_expansao/dimensionamento/huff.py` (BLK-DIM-02R). Ele implementa o Huff PURO (`share_huff`), calibra β por LOO honesto e valida — mas contra o **alvo interno `alunos_reais` das ~56 unidades Ultra** (deu NO-GO). O BLK-TP-07 é diferente pelo **ALVO**: agora a validação é contra a **demanda observada por hex** (`membros`), um universo maior (16.575 hexes) e georreferenciado à demanda, não às unidades Ultra. O Planner decide se ESTENDE/REUSA `huff.py` (funções puras `share_huff`/`_haversine_vec`) ou cria módulo novo em `demanda_revelada/` — mas o núcleo Huff PURO já existe e NÃO deve ser reimplementado do zero.

## Objetivo
Emitir veredito GO/NO-GO honesto (out-of-fold vs baseline, IC95) sobre se o share de captura Huff alinha com a demanda paga observada por hex, READ-ONLY sobre o M1, sem integrar nada ao residual/carteira/plano.

## Escopo permitido
- Módulo de análise ISOLADO na camada paralela, em `src/motor_expansao/demanda_revelada/` (ou reuso das funções puras de `dimensionamento/huff.py`, que já é camada paralela irmã e já é importado por `calibracao_residual.py`/`backtest_tp05.py`).
- Função de Huff **parametrizável**: β de distância, atratividade por concorrente, janela de catchment, tratamento de canibalização Ultra.
- **Calibração/validação out-of-fold vs baseline da média** (k-fold repetido ou LOO conforme N), IC95 bootstrap **seed=42**, **R² in-sample BANIDO do veredito** (só campo de auditoria rotulado), intervalos + **flag de extrapolação** (DEC-008).
- **Alvo = demanda OBSERVADA** casada por `hex_id`: `membros` (principal) e/ou `alunos_parceiras`; agregação do share ao nível do hex para casar com o alvo.
- Baseline honesto explícito (ex.: contagem de concorrentes no raio sem β / média), reportado ao lado do Huff — se o Huff não bate o baseline, a geometria de distância não agrega.
- **Relatório GO/NO-GO gitignored** em `data/analysis/` (markdown, sem PII, só métricas agregadas), com o caveat de cobertura DEC-012 explícito.
- Testes unitários em `tests/unit/` com **fixtures sintéticas** (zero dado real, zero PII).

## Fora de escopo
- **Integrar o resultado ao `score_oportunidade_residual`, à carteira, ao plano ou a qualquer artefato** — isso é o **BLK-TP-09** (follow-up com DEC + gate próprio). Este bloco só MODELA e VALIDA.
- Recalcular/alterar QUALQUER artefato oficial M1 (`score_priorizacao`, `hex_score_estrutural`, carteira, plano, os 4 parquets oficiais) — mtime deve ficar inalterado.
- Usar `membros`/`alunos_parceiras`/qualquer coluna da Demanda Revelada como **preditor geográfico de magnitude** — proibido por DEC-009 (é ALVO de validação, nunca feature de previsão de demanda).
- Regenerar qualquer parquet de staging (mercado/residual/híbrido).
- Ler PII: nenhuma coluna de `COLUNAS_PII_PROIBIDAS`; `nome_unidade` de concorrentes NUNCA lido para saída/log; fonte real (`NAO_ABRA/`) nunca tocada; `data/validacao/*.xlsx` só via fronteira anti-PII já existente (`capacidade_clube_validacao.py`) SE o gate escolher atratividade por capacidade real.
- Dependência nova de rede/base pesada; import de `pipelines/m1`, `dashboard`, `censo_*`, `api`, `config.py` raiz.
- **Nota de isolamento importante:** o `current_task.md` cita `analisar_entorno_ponto` como dependência, mas ela vive em `src/motor_expansao/dashboard/data.py` — **IMPORTÁ-LA VIOLA o isolamento** (`dashboard/`). Use a geometria de catchment vetorizada já existente em `dimensionamento/huff.py` (`_haversine_vec`, `share_huff`, `JANELA_CATCHMENT_KM`), não o helper do dashboard. Registrar esta tradução no plano.

## Insumos reais disponíveis vs faltantes (para o gate de modelagem resolver)
**Disponíveis (verificados):**
- `data/staging/concorrentes_mapeados.parquet` (3.296 linhas): `concorrente_id, rede, nome_unidade, lat, lng, flag_coord_valida, flag_duplicado_rede_coord, hex_id_res7`. **Tem `rede` + coords; NÃO tem metragem nem capacidade.**
- `data/staging/demanda_revelada_h3.parquet` (16.575 linhas, contrato de 9 col): `hex_id, membros, membros_gt5km_concorrente_lc, dist_concorrente_lc_min_m, n_celulas_agregadas, n_acad_parceiras, alunos_parceiras, n_concorrente_lc, versao_contrato`.
- `data/staging/hexagonos_mercado_mapeado.parquet` (1.542.531 × 135): já traz por hex `lat, lng, n_concorrentes_mapeados_1km/2km, n_smart_fit_2km, dist_concorrente_mais_proximo_m, dist_smart_fit_mais_proximo_m, n_unidades_ultra_1km/2km, dist_ultra_mais_proxima_m, flag_canibalizacao_ultra_1km, oferta_efetiva_disponivel, score_oportunidade_residual`. (READ-ONLY; nenhuma coluna oficial M1 pode ser reescrita.)
- Capacidade de clube por rede ANTI-PII (opcional para atratividade): `data/validacao/` via `demanda_revelada/capacidade_clube_validacao.py` (Smart ~2.363–2.370 / Engenharia ~3.106; fallback 2.500). Já usado no BLK-TP-06-FU2.

**Faltante / ausente:** **não há metragem nem capacidade instalada por unidade** em `concorrentes_mapeados` → a atratividade não pode ser "por m²". O DIM-02R resolveu com **atratividade unitária (1.0)**; alternativa é **capacidade mediana por rede** (anti-PII). É decisão do gate.

**Decisões de modelagem que o gate humano precisará resolver (Planner deve enumerá-las):**
1. **Fonte de atratividade:** unitária (precedente DIM-02R) vs capacidade mediana por rede (`capacidade_clube_validacao.py`) vs contagem/densidade de concorrentes no raio.
2. **Unidade de agregação:** share por PONTO/hex candidato agregado ao `hex_id` para casar com `membros` — definir como agregar o share ao hex (centroide do hex? média dos concorrentes?).
3. **β de distância:** grade/otimização (o DIM-02R re-otimiza β por LOO; aqui o alvo é `membros`).
4. **Canibalização Ultra:** incluir unidades Ultra no denominador (via `n_unidades_ultra_1km`/`dist_ultra_mais_proxima_m`/`flag_canibalizacao_ultra_1km`) ou não.
5. **Alvo:** `membros` (log1p, precedente) como principal; `alunos_parceiras` como secundário/cross-check (é OFERTA instalada — cuidado circular, ver TP-05/TP-06).
6. **Baseline:** qual baseline honesto (contagem no raio sem β / média).

## Arquivos que devem ser lidos
- `CLAUDE.md` (§1, §2, §4, §5; DEC-008, DEC-009, DEC-012).
- `src/motor_expansao/dimensionamento/huff.py` (precedente Huff PURO + LOO honesto — REUSAR o núcleo).
- `src/motor_expansao/dimensionamento/base_multirede.py` (`CONCORRENTES_PATH`, `PISO_VIABILIDADE_ALUNOS`, `haversine_km`).
- `src/motor_expansao/demanda_revelada/contrato.py` (schema + `COLUNAS_PII_PROIBIDAS`).
- `src/motor_expansao/demanda_revelada/backtest_tp05.py` e `calibracao_residual.py` (padrão de join por `hex_id`, k-fold/IC/seed, alvo demanda observada, guardrails anti-PII e anti-circular já codificados).
- `src/motor_expansao/demanda_revelada/capacidade_clube_validacao.py` (fronteira anti-PII de capacidade por rede — só se o gate escolher atratividade por capacidade).
- `src/motor_expansao/dimensionamento/aderencia.py` (`ALPHA_GRID`, `LIMIAR_R2_GO`, `_r2_loo_para_alpha`) e `backtest_dim.py` (`_r2`, `_rmse`) — infra de validação já reutilizada pela camada.
- `data/staging/{demanda_revelada_h3, hexagonos_mercado_mapeado, concorrentes_mapeados}.parquet` (só leitura; NÃO reescrever).

## Arquivos que podem ser alterados
- `src/motor_expansao/demanda_revelada/` — módulo novo do Huff (ou extensão de reuso). NÃO importar `pipelines/m1`, `dashboard`, `censo_*`, `api`, `config.py` raiz.
- `tests/unit/` (e/ou `tests/unit/demanda_revelada/`) — testes com fixtures sintéticas.
- `data/analysis/` — relatório GO/NO-GO gitignored (não versionado).
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (fechamento).
- `context/handoff.md`, `context/handoff/`.

## Critérios de aceite
- Módulo READ-ONLY isolado: **zero import** de `pipelines/m1`, `dashboard`, `censo_*`, `api`, `config.py` raiz (verificável por grep/AST).
- Função de Huff parametrizável (β, atratividade, catchment, canibalização) validada **out-of-fold vs baseline** com **IC95 bootstrap seed=42**; **R² in-sample nunca no veredito** (só auditoria rotulada); intervalos + **flag de extrapolação** presentes.
- Validação contra demanda observada por `hex_id`; **caveat de cobertura DEC-012 (~1%, viés Sudeste) explícito** no relatório.
- **Veredito GO/NO-GO** materializado em `data/analysis/` (gitignored) — **NO-GO é resultado VÁLIDO** (DEC-008), não forçar GO.
- Anti-PII verificável: nenhuma coluna de `COLUNAS_PII_PROIBIDAS` em qualquer frame/saída/log; teste `test_zero_pii`/equivalente; testes só com fixtures sintéticas; `nome_unidade` nunca em saída.
- **mtime dos 4 artefatos oficiais M1 inalterado**; nenhum parquet de staging regenerado.
- Sem dependência nova de rede/base pesada; suíte verde (`pytest -n auto` no subconjunto impactado; suíte full no QA); `import streamlit_app` ok.

## Criticidade classificada
**Alta** (READ-ONLY sobre o M1). **Não é Crítica** porque não toca `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos oficiais — só emite veredito em `data/analysis/`. **ALERTA de vigilância:** se durante o planejamento/execução surgir QUALQUER escrita em artefato M1 ou alteração da fórmula do `score_oportunidade_residual`/carteira/plano → **reclassificar para CRÍTICA e parar** (isso seria escopo do BLK-TP-09, com DEC + gate).

## Esteira recomendada
Block Orchestrator → **Planner** → `[REVISÃO HUMANA — modelagem: as 6 decisões acima]` → Builder → QA (Opus 4.8).

## Riscos identificados
- **Violação DEC-009:** usar `membros`/demanda como preditor de magnitude (em vez de ALVO de validação) = proibido. O share Huff PURO NÃO pode receber o alvo (vazamento) — o precedente `huff.py` já garante isso estruturalmente; manter.
- **Violação DEC-012 (PII):** ler `nome_unidade`, coords residenciais individuais, `NAO_ABRA/`, ou vazar coluna proibida no artefato/log/teste. `data/validacao/*.xlsx` só via fronteira anti-PII existente.
- **Generalização:** join cobre ~1% do universo (16.575 hexes), concentrado no Sudeste (DEC-012) → um GO não é cobertura nacional; o relatório deve declarar isso. Precedente DIM-02R deu NO-GO contra alvo interno; NO-GO honesto aqui é plausível e aceitável.
- **Circularidade / colinearidade:** `alunos_parceiras`↔`n_acad_parceiras` (rho ~+0,94) e `alunos_parceiras` como OFERTA instalada — o TP-05/TP-06 já mapearam; se usar `alunos_parceiras`, tratar como cross-check, não alvo principal ingênuo.
- **Isolamento:** importar `analisar_entorno_ponto` (de `dashboard/data.py`) quebra o isolamento — usar a geometria de `dimensionamento/`.
- **Reinvenção:** reimplementar Huff do zero em vez de reusar `dimensionamento/huff.py` = risco de divergência e de reintroduzir vazamento.

## Guardrails ativos (de CLAUDE.md)
- **§5 (guardrail permanente):** visualizações/análises READ-ONLY não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita.
- **§2:** tratar `config.py`, `CLAUDE.md`, `PRD.md` como fontes canônicas; toda mudança relevante entra com teste; nenhum PR com CI quebrado; preservar 100% das linhas/colunas oficiais do M1.
- **DEC-008:** LOO/k-fold vs baseline SEMPRE; R² in-sample BANIDO do veredito; IC obrigatório; flag de extrapolação; começar simples; NO-GO é resultado válido.
- **DEC-009:** demanda entra como PREMISSA/ALVO OBSERVADO, NUNCA prevista pela geografia nem usada como preditor de magnitude.
- **DEC-012 (anti-PII):** camada `demanda_revelada/` disjunta; agregação na fronteira; zero PII em artefato/log/teste; fonte real nunca versionada; fixtures sintéticas.
