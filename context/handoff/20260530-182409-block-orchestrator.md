# Handoff — Block Orchestrator
## Skill que gerou este handoff
Block Orchestrator
## Próxima Skill recomendada
Planner
## Bloco refinado
**BLK-SCORE-01 — Dataset rotulado de validação (Ultra + Skyfit + Engenharia do Corpo).**
Montar `data/analysis/dataset_validacao.parquet`: uma linha por unidade existente (Ultra própria +
concorrentes Skyfit e Engenharia do Corpo), ligando cada unidade ao hex H3 res.7 (e, quando possível,
ao `cod_municipio`/setor IBGE) onde ela cai, aos scores existentes (M1, censitário, residual, domínio)
e aos desfechos observados (alunos / faturamento / sinal Wellhub-Gympass). Insumo do backtest
(BLK-SCORE-02). Read-only sobre o M1: só leitura e join, nenhuma escrita em artefato M1.

**Achados de mapeamento (verificados em disco — números reais):**

1. Conversão lat/lng→H3 é inline; NÃO há módulo `geo/`/`data_sources/`/geocoder. Padrão canônico:
   `h3.latlng_to_cell(lat, lng, 7)` (fallback `h3.geo_to_h3`), em
   `src/motor_expansao/pipelines/normalizar_unidades_ultra.py` (`_latlng_to_h3`, ~linha 166) e
   `normalizar_concorrentes.py` (~linha 90). NÃO há geocodificação de endereço (string→coord) =
   BLK-PROD-05 (pendente). As três redes JÁ têm lat/lng, então este bloco NÃO depende de BLK-PROD-05.

2. Unidades Ultra (performance + hex + scores já resolvidos):
   `data/staging/unidades_ultra_performance_hex.parquet` — 54 linhas, 57 colunas (gitignored).
   Contém `hex_id_res7`, `hex_id`, `score_priorizacao`, `score_oficial`, `score_expansao_hibrido`,
   ranks, e desfechos: `alunos_total`, `ativos_pag`, `alunos_gympass` (=Wellhub), `alunos_totalpass`,
   `agregadores`, `faturamento`, `ticket_medio_aluno`, `metragem`, `alunos_por_m2`, `penetracao_ultra_*`.
   Cobertura do join: 49/54 com `hex_id` + `score_priorizacao` + `score_expansao_hibrido` (5 sem
   coordenada casada). NÃO tem coluna `rede`, NÃO tem `cod_municipio`, NÃO tem
   `score_setor_2022_calibrado`/`score_oportunidade_residual`/`score_dominio_hibrido` nem
   `data_abertura`. Gerado por `normalizar_unidades_ultra.py` → `calcular_penetracao_ultra_hex.py`.

3. Concorrentes mapeados: `data/staging/concorrentes_mapeados.parquet` (11 colunas; gitignored).
   `rede="engenharia_do_corpo"` → 63 unidades válidas, todas com `hex_id_res7`.
   ATENÇÃO — Skyfit NÃO está neste parquet (0 linhas de `rede="skyfit"`). A fonte
   `concorrentes/unidades_skyfit.csv` existe (482 linhas) mas o snapshot normalizado não a incluiu.
   Existem também `concorrentes/SkyFit_unidades_geocodificado.csv` e
   `concorrentes/Sky_Fit_Unidades_geocoded.xlsx`. DECISÃO NECESSÁRIA: o Planner decide se re-roda
   `normalizar_concorrentes.py` (regrava `concorrentes_mapeados.parquet` — STAGING, NÃO oficial M1)
   para incluir Skyfit, ou lê o CSV Skyfit direto no script e resolve hex via `h3.latlng_to_cell`.
   Sem isso, Skyfit fica de fora do dataset.

4. Fonte dos scores por hex (chave de join = `hex_id` = H3 res.7):
   `data/staging/hexagonos_mercado_mapeado.parquet` — 131 colunas (gitignored). Confirmado conter:
   `score_priorizacao` (M1), `score_setor_2022_calibrado` (censitário),
   `score_oportunidade_residual` (residual), `score_expansao_hibrido`, mais `cod_municipio`,
   `nome_municipio`, `cod_municipio_censo`. NÃO contém `score_dominio_hibrido` nem `cod_setor_2022`.
   - 4º score (domínio): `score_dominio_hibrido` existe SÓ em
     `data/outputs/plano_expansao_dominio.parquet` (500 linhas, por `hex_id`). Cobertura restrita aos
     500 hexes do plano — a maioria das unidades ficará com domínio NULO (esperado; marcar, não falhar).
   - Setor IBGE: este parquet resolve `cod_municipio`/`nome_municipio`, não `cod_setor`. Resolução de
     setor real (geometria) viria de
     `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet` via
     `resolve_cod_municipio_from_geo_dir` (dashboard/data.py, ~linha 88) — pesado. RECOMENDAÇÃO: anexar
     `cod_municipio` + `score_setor_2022_calibrado` do parquet de mercado e deixar o setor censitário
     detalhado como opcional/decisão do gate.

5. Rótulos de desfecho dos concorrentes (parte frágil) — planilhas em `data/validacao/` (gitignored):
   - `Sky Fit dados.xlsx` → sheet `Sell Out` (~347 linhas; HEADER NA LINHA 4, linhas 1-3 vazias).
     Colunas: `ID SKY | NOMENCLATURA UNIDADE | ENDERECO | CIDADE | ESTADO | Alunos EVO | Alunos Gympass |
     Alunos TotalPass`. É a fonte MAIS rica dos concorrentes: tem `ID SKY` (id estável), endereço/cidade/
     estado, `Alunos EVO` (alunos reais do sistema da rede), `Alunos Gympass` (=Wellhub) e
     `Alunos TotalPass` (3 sinais de demanda). Ler com `skiprows`/header na linha 4.
   - `academias_engenharia_do_corpo.xlsx` → sheets ricos: `Academias` (62 linhas:
     `ID | Unidade | Tipo de Imóvel | Metragem M² | Vagas | Total Alunos Ativos | Total Alunos Gympass |
     Alunos Totais | Observações`), `Base_Calculo` (alunos/m²), `Estacionamento`, `Fontes`. EngCorpo TEM
     alunos absolutos (`Alunos Totais`, `Total Alunos Ativos`) e Gympass — melhor que o README sugeria
     (não é só alunos/m²).
   - Join unidade-mapeada ↔ planilha é por NOME (Skyfit tem `ID SKY` interno mas o parquet mapeado não o
     carrega) — maior fonte de erro de rótulo.

6. Sinal Wellhub/Totalpass disponível para as TRÊS redes (Gympass=Wellhub), com nomes diferentes:
   Ultra → `alunos_gympass`+`alunos_totalpass`; Skyfit → `Alunos Gympass`+`Alunos TotalPass`;
   EngCorpo → `Total Alunos Gympass`. Unificar como coluna proxy de demanda por agregador.

7. `data_abertura`/maturação: NÃO ENCONTRADO como data explícita em nenhuma fonte (Ultra, concorrentes,
   validação). Sem fonte canônica de data de abertura → flag de maturação fica majoritariamente
   indisponível. Decisão do gate.
## Objetivo
Gerar `data/analysis/dataset_validacao.parquet` ligando cada unidade (Ultra/Skyfit/EngCorpo) ao hex H3
res.7 + `cod_municipio`, aos scores existentes e ao desfecho observado, por join read-only sobre o M1.
## Escopo permitido
- Ler Ultra de `unidades_ultra_performance_hex.parquet` (hex + scores M1/híbrido já presentes).
- Obter EngCorpo de `concorrentes_mapeados.parquet` (`rede=="engenharia_do_corpo"`,
  `status_registro=="valido"`) e Skyfit por uma das vias decididas pelo Planner (re-rodar
  `normalizar_concorrentes.py` OU ler `concorrentes/unidades_skyfit.csv` e resolver hex via H3).
- Anexar `score_priorizacao`, `score_setor_2022_calibrado`, `score_oportunidade_residual`,
  `cod_municipio`/`nome_municipio` por `hex_id` de `hexagonos_mercado_mapeado.parquet` (read-only).
- Anexar `score_dominio_hibrido` por `hex_id` de `plano_expansao_dominio.parquet` (cobertura parcial,
  500 hexes) — read-only.
- Anexar desfechos: Ultra direto; Skyfit/EngCorpo via join por nome com `data/validacao/*.xlsx`.
- Unificar sinal Wellhub/Gympass das três redes numa coluna de demanda por agregador.
- Marcar qualidade de rótulo (medido/estimado, nulos, outliers) e flag de maturação conforme o gate.
- Gravar `data/analysis/dataset_validacao.parquet` (criar `data/analysis/`).
- Criar script de montagem e teste unitário com fixtures sintéticas.
## Fora de escopo
- QUALQUER escrita em artefato M1 ou alteração de score/fórmula/pesos/carteira/plano/domínio.
  ALERTA EXPLÍCITO: read-only sobre o M1; não tocar `hexagonos_brasil_*`, `brasil_*`, `carteira_*`,
  `plano_expansao_*` (consumir como leitura), `hexagonos_mercado_mapeado.parquet`, `core/scoring.py`,
  `core/constants.py`. (Re-rodar `normalizar_concorrentes.py` regrava SÓ
  `data/staging/concorrentes_mapeados.parquet`, staging paralelo, NÃO artefato oficial M1 — admissível
  se o Planner optar, mas é decisão a registrar.)
- Geocodificação de endereço (string→coord) = BLK-PROD-05.
- Backtest / correlação score×desfecho = BLK-SCORE-02.
## Arquivos que devem ser lidos
- `CLAUDE.md` (§2, §3, §5) · `tasks/backlog.md` (BLK-SCORE-01) · `tasks/current_task.md`.
- `data/validacao/README.md`.
- `src/motor_expansao/pipelines/normalizar_unidades_ultra.py`.
- `src/motor_expansao/pipelines/normalizar_concorrentes.py`.
- `src/motor_expansao/pipelines/calcular_penetracao_ultra_hex.py`.
- `src/motor_expansao/core/scoring.py` (entender scores — NÃO alterar).
- `docs/modelo_mercado_hexagonos.md` · `docs/expansao_dominio.md`.
- Schemas (gitignored, locais): `data/staging/hexagonos_mercado_mapeado.parquet`,
  `data/staging/unidades_ultra_performance_hex.parquet`, `data/staging/concorrentes_mapeados.parquet`,
  `data/outputs/plano_expansao_dominio.parquet`.
- Planilhas `data/validacao/Sky Fit dados.xlsx` (sheet `Sell Out`, header na linha 4) e
  `data/validacao/academias_engenharia_do_corpo.xlsx` (sheets `Academias`/`Base_Calculo`) — LER só
  estrutura, não despejar PII no handoff/log.
- `concorrentes/unidades_skyfit.csv` (482 linhas, `nome_unidade,latitude,longitude,data_coleta`) caso o
  Planner opte por ler Skyfit direto.
- NÃO ENCONTRADO (sinalizar): fonte de `data_abertura`/maturação; `score_dominio_hibrido` por hex fora
  dos 500 do plano; `cod_setor_2022` no parquet de mercado; módulo geo central.
## Arquivos que podem ser alterados
- `analysis/build_validation_dataset.py` (script de montagem — nome final a confirmar pelo Planner).
- `tests/unit/test_validation_dataset.py` (teste novo, com fixtures sintéticas).
- `data/analysis/dataset_validacao.parquet` (artefato gerado — gitignored, NÃO versionar).
- (Opcional) `data/analysis/relatorio_auditoria_rotulo.md` (gitignored).
- `tasks/current_task.md` · `tasks/backlog.md` · `tasks/completed.md`.
- `context/handoff.md` · `context/handoff/` (snapshots append-only).
- (Decisão do Planner) re-rodar `normalizar_concorrentes.py` → regrava
  `data/staging/concorrentes_mapeados.parquet` (staging, gitignored, não oficial M1).
- NÃO tocar `CLAUDE.md` (já `M` no worktree por mudança pré-existente do usuário). Commit só por path.
## Critérios de aceite
- Coluna `rede` distinguindo Ultra / Skyfit / Engenharia do Corpo; Skyfit presente (não silenciosamente
  ausente — se ficar fora, justificar explicitamente).
- Cada unidade tem `hex_id_res7` resolvido e os scores disponíveis anexados
  (`score_priorizacao`, `score_setor_2022_calibrado`, `score_oportunidade_residual`,
  `score_dominio_hibrido`); ausência por falta de cobertura (domínio 500 hexes; unidades sem coordenada)
  fica MARCADA em coluna de status, não descartada.
- Flag de maturação presente: se sem fonte, valor explícito `maturacao_indisponivel` (não inventar).
- Sinal Wellhub/Gympass unificado para as três redes (quando disponível).
- Auditoria de rótulo: relatório curto de nulos/outliers em alunos, com nota de confiabilidade
  (Skyfit `Alunos EVO` real vs Gympass/TotalPass; EngCorpo `Alunos Totais` vs `Alunos/m²`).
- Sanidade do join: nº de unidades de entrada == nº com score anexado, OU diferença explicada.
- `pytest -q tests/unit/test_validation_dataset.py` verde; `pytest -q` sem regressão
  (baseline 532 passed, 1 skipped — números maiores recentes citados em handoffs antigos são daqueles
  ciclos).
- Artefato em `data/analysis/`, nunca em `data/outputs/`.
## Criticidade classificada
alta
## Esteira recomendada
Block Orchestrator → Planner → [revisão humana] → Builder → QA
## Riscos identificados
- Skyfit ausente do staging (alto): sem ação explícita, uma das três redes-alvo fica fora. Decidir via
  de inclusão.
- Join de rótulo por nome (alto): planilhas/CSV mapeado não compartilham id estável exposto; casamento
  fuzzy por nome. Cardinalidades não batem (EngCorpo 63 mapeadas vs 62 na planilha `Academias`; Skyfit
  482 no CSV vs ~347 na planilha vs 0 no staging). Exige reconciliação e relatório de não-casados.
- Maturação sem fonte (alto): não há `data_abertura` em nenhuma fonte.
- Cobertura parcial do score de domínio (médio): só 500 hexes no plano; maioria fica nulo.
- Cobertura parcial de hex (médio): 5/54 Ultra sem hex; unidades em hex fora do mercado mapeado ficam
  sem scores censitário/residual.
- Header não-padrão na planilha Skyfit (médio): header na linha 4; ler com skiprows.
- Fontes gitignored (operacional): CI não tem os parquets/.xlsx reais — o teste deve usar fixtures
  sintéticas, nunca os dados reais.
## Guardrails ativos
- READ-ONLY sobre o M1: nada recalcula nem altera `score_priorizacao`, `hex_score_estrutural`,
  carteira, plano curto prazo, plano de domínio ou artefato oficial (CLAUDE.md §3/§5). Escrita em
  artefato M1 = FORA DE ESCOPO.
- Dados sensíveis (Ultra/Skyfit/EngCorpo/Wellhub) NÃO entram em logs/handoff em texto agregável a PII
  (nomes de unidade, endereços, contagens nominais). Descrever por caminho/schema.
- Artefato em `data/analysis/`, nunca `data/outputs/`. CSVs derivados `sep=";"`, `utf-8-sig`;
  `data/ultra/Ultra.csv` permanece `sep=";"`, `latin-1`, 1 linha de metadado.
- Preservar 100% das linhas/colunas oficiais do M1.
- Commit SÓ por path; NUNCA `git add -A`; `CLAUDE.md` (já `M`) NÃO entra no commit deste ciclo.
- Branch isolado `ciclo/BLK-SCORE-01`; gate humano APÓS Planner, ANTES do Builder.
- H3 res.7 canônico (`H3_RESOLUTION=7`); preferir os `hex_id_res7` já materializados.
## Lacunas / decisões pendentes para o gate humano
1. Skyfit: aprovar a via de inclusão — (a) re-rodar `normalizar_concorrentes.py` para regravar o staging
   com Skyfit, ou (b) o script ler `concorrentes/unidades_skyfit.csv` e resolver hex via H3.
2. Maturação: sem `data_abertura`. Aceitar `maturacao_indisponivel` nesta entrega (tratar maturação em
   BLK-SCORE-02 quando houver fonte) OU fornecer planilha de datas de abertura.
3. Rótulo canônico de "alunos": definir a coluna única (Ultra `alunos_total`/`ativos_pag`; Skyfit
   `Alunos EVO`; EngCorpo `Alunos Totais`/`Total Alunos Ativos`) e como sinalizar medido vs estimado.
4. Setor censitário: confirmar que basta `cod_municipio`+`score_setor_2022_calibrado` (do mercado) e
   que NÃO é preciso resolver geometria de setor via `setores_censitarios_2022_geo`.
5. Score de domínio com cobertura parcial: confirmar que anexar só nos 500 hexes do plano e marcar nulo
   no resto é aceitável.
6. Versionamento: `data/analysis/dataset_validacao.parquet` está gitignored (verificado) — manter fora
   do git (contém dados sensíveis de concorrentes). Confirmar.
7. Nome/local do script (`analysis/build_validation_dataset.py`) e forma de execução (CLI/módulo).
