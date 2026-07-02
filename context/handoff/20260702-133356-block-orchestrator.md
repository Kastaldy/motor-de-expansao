# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-TP-06 — Calibração/validação do `score_oportunidade_residual` com demanda revelada observada.**
Bloco de MODELAGEM, **READ-ONLY sobre o M1**, na camada PARALELA de mercado/residual. Mede,
**fora-de-amostra (out-of-fold)**, quanto o `score_oportunidade_residual` (e/ou seu componente
`oferta_efetiva_disponivel`) prevê a **demanda OBSERVADA** da camada Demanda Revelada
(`data/staging/demanda_revelada_h3.parquet`), casada por `hex_id`. Quantifica de forma honesta
(DEC-008) o **+0,52 exploratório/in-sample** da DEC-012, emite veredito **GO/NO-GO**, e — se GO —
**propõe (sem aplicar em produção)** como recalibrar os componentes do residual para melhorar o
alinhamento com a demanda observada. Recalibrar a FÓRMULA do residual em produção é FOLLOW-UP com
gate próprio, **não** este bloco.

## Objetivo
Validar out-of-fold (LOO/k-fold vs baseline, IC95 bootstrap seed-fixa, sem R² in-sample) o poder do
`score_oportunidade_residual` de prever a demanda observada por hex e propor — sem aplicar — uma
calibração melhor, mantendo o M1 e a fórmula de produção do residual intocados.

## Escopo permitido
- Módulo/script novo em pacote DISJUNTO (`src/motor_expansao/demanda_revelada/` e/ou `scripts/`), que
  IMPORTA (nunca edita) o parquet da demanda revelada e o `score_oportunidade_residual`/
  `oferta_efetiva_disponivel` de `data/staging/hexagonos_mercado_mapeado.parquet`, casa por `hex_id`.
- **Alvo de modelagem = demanda OBSERVADA** (`membros` da Demanda Revelada; documentar explicitamente
  qual das duas noções de "aluno/ativo" é o alvo — ver Inventário abaixo). **Preditor/score existente =
  `score_oportunidade_residual`** (e opcionalmente seus componentes). A validação mede se o PREDITOR
  alinha com o ALVO, out-of-fold.
- Validação honesta (DEC-008): LOO/k-fold vs **baseline da média**; **R² in-sample BANIDO** dos outputs;
  IC95 por bootstrap com **seed fixa**; predições com intervalo + **flag de extrapolação**.
- Métricas de alinhamento: Spearman rho_oof + IC95, R²_oof (contra baseline), reportadas com caveat de
  cobertura do join (~1,06% do universo do Motor; concentração SP — DEC-012).
- Se GO: **proposta escrita** (não aplicada) de recalibração dos componentes do residual, em relatório
  `data/analysis/*.md` (gitignored). Se NO-GO: veredito honesto documentado (sem gerar score).
- Fixtures sintéticas para os testes (nunca o dump/planilhas reais de `NAO_ABRA/`).
- Documentar a diferença entre os DOIS tipos de "aluno/ativo" e travar qual é o alvo de validação.
- Registrar como sub-escopo/risco (para decisão Planner+gate) se a inclusão das academias menores
  WellHub/TotalPass exigir NOVA ingestão a partir das planilhas de `NAO_ABRA/` (ver risco R4).

## Fora de escopo
- **QUALQUER** recálculo/alteração de `score_priorizacao`, `hex_score_estrutural`, pesos (renda 0.40/pop
  0.60), carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 (§5 — CRÍTICO se
  tocado).
- **Aplicar** a recalibração da fórmula do `score_oportunidade_residual` em produção / regenerar
  `hexagonos_mercado_mapeado.parquet` ou os parquets derivados — isso é follow-up com gate próprio.
- Usar a demanda revelada (`membros`/qualquer coluna) como **preditor geográfico de magnitude** ou como
  ajuste do `score_priorizacao`/residual — PROIBIDO por DEC-009 (ela é alvo/insumo observado).
- R² in-sample, `fit(X,y)→predict(X)`, ou reproduzir o +0,52 sem out-of-fold como veredito.
- Ingerir/persistir/logar PII (employee_id, company_id, coordenadas residenciais, e-mails, nomes) —
  DEC-012. Nova ingestão das academias menores, se aprovada, entra só como camada agregada anti-PII.
- Tocar `dashboard/`, `censo_*`, `api/`, `pipelines/m1/`.

## Arquivos que devem ser lidos
- `CLAUDE.md` (§1 low-cost/Smart Fit; §4 camada mercado/residual + `score_oportunidade_residual`; §5
  guardrails; DEC-008, DEC-009, DEC-012)
- `tasks/current_task.md` (Contexto adicional do usuário — 2 tipos de aluno/ativo; planilhas; WellHub/TotalPass)
- `tasks/backlog.md` (bloco `### BLK-TP-06`, linha 919; cabeçalho do epic BLK-TP, linha 851)
- `docs/modelo_mercado_hexagonos.md` (§5.6 — definição exata de `score_oportunidade_residual` e
  `oferta_efetiva_disponivel`; linhas 299–327; ordem de cálculo §6, linhas 341–354)
- `src/motor_expansao/demanda_revelada/contrato.py` (contrato de 9 colunas + `COLUNAS_PII_PROIBIDAS`)
- `src/motor_expansao/demanda_revelada/ingestao.py` (o que já é lido/produzido; anti-PII na fronteira)
- `data/staging/demanda_revelada_h3.parquet` (schema/agregados; NUNCA linhas individuais)
- `data/staging/hexagonos_mercado_mapeado.parquet` (colunas `hex_id`, `score_oportunidade_residual`,
  `oferta_efetiva_disponivel`; NUNCA imprimir PII — não há PII aqui, mas manter só agregados)
- `context/handoff/README.md` (convenção de snapshot append-only)

## Arquivos que podem ser alterados
- `src/motor_expansao/demanda_revelada/*.py` (módulo/script novo de validação; NÃO alterar o M1)
- `scripts/*.py` (script de execução da validação, se preferido)
- `tests/unit/*` e/ou `tests/integration/*` (fixtures sintéticas + testes anti-PII e de validação)
- `data/analysis/*.md` (relatório de veredito GO/NO-GO — gitignored)
- `docs/*.md` (contrato/caveats da validação, se necessário)
- `tasks/backlog.md` (bloco BLK-TP-06), `tasks/current_task.md`, `tasks/completed.md`
- `context/handoff.md`, `context/handoff/`

## Critérios de aceite
- Módulo READ-ONLY na camada paralela: **não importa** de `pipelines/m1`, `dashboard`, `censo_*`, `api`.
- Validação por LOO/k-fold vs **baseline da média** com **IC95 bootstrap (seed fixa)**; **R² in-sample
  banido** dos outputs; predições com intervalo + **flag de extrapolação** (DEC-008).
- Join por `hex_id` demanda×residual com **caveat de cobertura** reportado (~16.411 hexes ≈ 1,06% do
  universo do Motor; concentração SP — DEC-012).
- **Alvo de validação explicitamente documentado** e travado (`membros` = demanda paga observada, NÃO
  `alunos_parceiras`); diferença entre os 2 tipos de aluno/ativo escrita no relatório.
- Veredito **GO/NO-GO** documentado em `data/analysis/*.md` (gitignored). Se GO, **proposta** de
  calibração (não aplicada). Nenhuma escrita em `hexagonos_mercado_mapeado.parquet` nem derivados.
- Anti-PII: só camada agregada; **fixtures sintéticas** nos testes; zero coluna de
  `COLUNAS_PII_PROIBIDAS` em qualquer artefato/log/teste.
- **mtime dos 4 artefatos oficiais do M1 inalterado**; suíte verde; `import streamlit_app` ok.

## Inventário do NAO_ABRA (anti-PII)
Listagem SÓ de nomes de arquivo, schemas (cabeçalhos) e contagens agregadas — nenhuma linha individual,
e-mail, coordenada residencial, `employee_id`/`company_id` foi lida/impressa.

**Arquivos em `NAO_ABRA/`:**
- `totalpass_final (72) (1).html` (~19 MB) — dump HTML bruto; fonte da ingestão atual
  (`ingestao.py`/`FONTE_DEFAULT`); vars JS `CELLS`/`GYMS_PTS`/`SF`/`BANDS` (já agregadas) são as únicas lidas.
- **Planilhas (.xlsx) — extraídas do HTML, com dados importantes que o usuário destacou:**
  - `00_Resumo_Executivo.xlsx` — 1 aba `Resumo`, 6 linhas (métricas agregadas).
  - `01_SmartFit.xlsx` — aba `Smart Fit`, **970 linhas** [`ID, Nome, Latitude, Longitude`] = unidades do
    concorrente low-cost (SF).
  - `02_Oportunidades_Expansão.xlsx` — 15 linhas [`Rank, Bairro, Cidade, UF, Lat, Lng,
    Alunos_Potenciais, Distância_SF_km, Score`] = extrato das 15 sugestões (NÃO o universo; cuidado com
    o caveat "89% a >5km" do RELATORIO, que é este extrato, não o universo).
  - `03_Competidores.xlsx` — **24.045 linhas** [`Lat, Lng, Cluster_ID, Total_Academias,
    Total_Alunos_Cluster, Nome_Academia, Plano, Alunos_Academia, Município`] = academias parceiras/
    concorrentes menores (WellHub/TotalPass), com **`Alunos_Academia`** por unidade.
  - `04_Grid_Geográfico.xlsx` — **18.377 linhas** [`ID, Lat, Lng, Cell_ID, Distância_SF_km, População,
    Nome_Região`] = grade de células res-8 (bate com as 18.377 células res-8 do RELATORIO).
- `RELATORIO_demanda_revelada.md`, `SPEC_BLK-TP-01.md` — docs internos (gitignored).
- `_agg_e_cruzamento.py`, `_analise_totalpass.py` — scripts do protótipo exploratório.
- `out/` — `cruzamento_res7.parquet` (~24,8 MB), `demanda_h3_res7.parquet`, `demanda_h3_res8.parquet`
  (saídas exploratórias gitignored do protótipo).

**De onde a ingestão atual lê e o que produz:** `ingestao.py` lê SOMENTE o HTML (vars
`CELLS`/`GYMS_PTS`/`SF`/`BANDS`), agrega para H3 res-7 e produz
`data/staging/demanda_revelada_h3.parquet` (**16.575 hexes**, 9 colunas do contrato). **As planilhas
.xlsx NÃO são consumidas pela ingestão atual** — em especial `03_Competidores.xlsx` (24.045 academias
menores WellHub/TotalPass com `Alunos_Academia`) e `04_Grid_Geográfico.xlsx`.

**Os DOIS tipos de "aluno/ativo" (ambiguidade central — TRAVAR no Planner):**
1. **`membros`** (contrato) = beneficiários pagantes do benefício corporativo (TotalPass/WellHub),
   georreferenciados e agregados por hex. É a **DEMANDA OBSERVADA / "ativos" do benefício** — presente em
   **todos os 16.575 hexes** (soma 1.960.742). **Este é o ALVO de validação do BLK-TP-06.**
2. **`alunos_parceiras`** (contrato) / `Alunos_Academia` (planilha `03_Competidores`) = matrículas reais
   nas academias parceiras/menores (lado da OFERTA/captura), presente em só **5.341 hexes** (soma
   1.957.629). É denominador DIFERENTE — mistura oferta instalada, não demanda revelada.
   **RISCO:** confundir (1) com (2) como métrica de validação inverteria a semântica (validar residual
   contra oferta instalada, não contra demanda). O Planner DEVE fixar `membros` como alvo e documentar a
   distinção; usar `alunos_parceiras` só como covariável/cross-check, nunca como alvo principal.

**Academias menores (WellHub/TotalPass) — já ingeridas?** PARCIALMENTE. O contrato já tem
`n_acad_parceiras`/`alunos_parceiras` derivados da var `GYMS_PTS` do HTML (5.919 hexes com parceira). A
planilha `03_Competidores.xlsx` (24.045 linhas, mais rica — `Plano`/`Cluster`/`Município`) está **fora
da ingestão atual**. Incorporá-la exigiria **NOVA ingestão anti-PII** (drop Lat/Lng/Nome_Academia na
fronteira; agregar por hex) — potencialmente grande. **Recomendação BO:** tratar essa nova ingestão como
**sub-escopo condicional/risco** (R4) a ser decidido pelo Planner + gate humano — pode virar sucessor
(BLK-TP-08) para não inchar este bloco de validação.

## Criticidade classificada
**Alta.** READ-ONLY sobre o M1: valida/propõe (não aplica) calibração de um campo ATIVO da camada
PARALELA de mercado/residual (`score_oportunidade_residual`), que **não** é `score_priorizacao`/
`hex_score_estrutural`/artefato oficial do M1 → NÃO é Crítica. Exige revisão humana por ser modelagem
que pode propor recalibração de um score ativo.

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA — modelagem]** → Builder → QA.

## Riscos identificados
- **R1 (semântico, central):** confundir os 2 tipos de aluno/ativo (`membros` = demanda vs
  `alunos_parceiras`/`Alunos_Academia` = oferta instalada). Travar `membros` como alvo; documentar.
- **R2 (cobertura/viés):** join casa só ~1,06% do universo do Motor (16.411 hexes), fortemente enviesado
  para SP (~66%). Veredito vale para metrópoles, não é validação nacional — reportar como caveat forte.
- **R3 (metodologia):** tentação de reportar o +0,52 in-sample como veredito. DEC-008 exige out-of-fold
  vs baseline, IC95 seed-fixa, R² in-sample banido. Sem isso o bloco falha o gate.
- **R4 (escopo/PII):** incorporar as academias menores de `03_Competidores.xlsx` exige nova ingestão
  anti-PII (drop Lat/Lng/Nome na fronteira). Pode ser grande — Planner deve decidir se entra aqui ou vira
  sucessor. Se entrar, cobrir por teste anti-PII e fixture sintética.
- **R5 (ruído de join):** coords das células arredondadas (~1 km) introduzem ruído no join res-7 —
  aceitável para densidade, não para ponto exato; declarar no relatório.
- **R6 (escopo criativo/guardrail):** proposta de calibração NÃO pode virar aplicação em produção nem
  tocar a fórmula do residual/artefatos — só relatório. Recalibrar em prod = follow-up com gate próprio.
- **R7 (extrato ≠ universo):** `02_Oportunidades_Expansão.xlsx` (15 linhas) e o "89% a >5km" são o
  extrato das sugestões, NÃO o universo — não usar como base de validação.

## Guardrails ativos
- **§5 (guardrail permanente / READ-ONLY M1):** visualizações, análises e camadas paralelas **não podem
  recalcular ou alterar** `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano
  de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- **DEC-008:** LOO/k-fold repetido **sempre contra baseline da média**; **BANIR R² in-sample** e
  `fit(X,y)→predict(X)`; começar simples (linear regularizado/GLM); toda saída com intervalo de predição
  + flag de extrapolação.
- **DEC-009:** a demanda entra como **PREMISSA/ALVO OBSERVADO**, **NUNCA prevista/usada como preditor
  geográfico de magnitude**. Proibido reintroduzir demanda como ajuste do `score_priorizacao`/residual.
- **DEC-012 (anti-PII):** consumir só a camada agregada; `employee_id`/`company_id`/coordenadas
  residenciais nunca lidos/persistidos/logados; artefato e testes com **zero PII**
  (`COLUNAS_PII_PROIBIDAS`); fonte real nunca versionada (`NAO_ABRA/` gitignored); **fixtures sintéticas**
  nos testes.
- **§1:** Ultra é low-cost/massa; Smart Fit (`concorrente_lc`/SF) é o concorrente low-cost de referência.
