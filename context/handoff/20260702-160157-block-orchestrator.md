# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-TP-08-FU — Re-ingestão das academias menores COM rótulo de rede (`rede_menor`) classificado na fronteira anti-PII.**

Estende o BLK-TP-08 (`src/motor_expansao/demanda_revelada/oferta_academias_menores.py`, contrato `oferta_menores_v1`): re-ingere `NAO_ABRA/03_Competidores.xlsx` (24.045 academias menores WellHub/TotalPass) e, ANTES do drop-PII do `Nome_Academia`, deriva uma CATEGORIA de rede (`rede_menor`) por matching de tokens contra o vocabulário de redes já mapeadas em `concorrentes_mapeados.parquet`. Produz duas saídas anti-PII (gitignored, NÃO oficiais): (a) oferta por hex COM quebra por rede (habilita dedup FINO por rede vs `concorrentes_mapeados`); (b) tabela de MÉDIA de alunos/unidade por rede. Fecha as 2 lacunas de dado que pausaram o BLK-TP-06-FU1. READ-ONLY sobre o M1.

## Objetivo
Re-ingerir as academias menores classificando cada uma numa CATEGORIA de rede (`rede_menor`) na fronteira anti-PII, gerando oferta por hex×rede (dedup fino) + tabela de média de alunos/unidade por rede — sem tocar em nada do M1.

## Escopo permitido
- **Classificação de rede na fronteira:** derivar `rede_menor` do `Nome_Academia` por normalização (lower, remoção de acentos/pontuação, colapso de espaços) + matching de token contra o vocabulário curado das redes de `concorrentes_mapeados.parquet` (28 redes); atribuir a categoria e **DESCARTAR** `Nome_Academia`/`Latitude`/`Longitude`/`Cluster_ID` IMEDIATAMENTE após (mesmo padrão do TP-08). Não classificáveis → categoria genérica `independente`.
- **Saída (a) — oferta por hex×rede:** novo parquet gitignored em `data/staging/` no formato LONGO `hex_id` × `rede_menor` × `n_academias_menores` × `alunos_academias_menores` (Σ `Alunos_Academia`, NUNCA `Total_Alunos_Cluster`), carimbo `versao_contrato`. Formato longo (vs largo) recomendado ao Planner por robustez a novas redes (o gate decide).
- **Saída (b) — média de alunos/unidade por rede:** tabela/parquet `rede_menor` → `media_alunos` + `mediana_alunos` + `n_filiais` (de `Alunos_Academia` das filiais classificadas), com **flag de confiabilidade** por N mínimo (candidato N≥10; o gate confirma o limiar).
- Estender/duplicar padrão do módulo `oferta_academias_menores.py` (novo helper/função na MESMA camada `demanda_revelada/`) para a classificação + as 2 saídas; blindagens anti-PII (`_assert_sem_pii`, `test_zero_pii`) estendidas ao novo contrato.
- Relatório de qualidade (só agregados/contagens) documentando cobertura de classificação e o N por rede.
- Testes com **fixtures sintéticas** (nomes fake, jamais reais).
- Registrar bloco AD-HOC BLK-TP-08-FU em `tasks/backlog.md`.

## Fora de escopo
- **Qualquer escrita/recálculo no M1** (score_priorizacao, hex_score_estrutural, carteira, plano, artefatos oficiais). READ-ONLY.
- **Recompor o residual** (`score_oportunidade_residual`/`oferta_efetiva_disponivel`) ou integrar a capacidade por rede ao pipeline de mercado — isso é o BLK-TP-06-FU1 (retomável) / BLK-TP-09, sob gate próprio.
- **Aplicar o dedup fino** (subtrair oferta): este bloco só HABILITA (produz o rótulo); a subtração é follow-up.
- Alterar o contrato/artefato existente `oferta_menores_v1` de forma que quebre o TP-08 (preferir novo contrato/arquivo, ou aditivo compatível — o Planner decide).
- Persistir/logar QUALQUER PII: `Nome_Academia`, `Latitude`, `Longitude`, `Cluster_ID`, `Total_Alunos_Cluster`.
- Versionar a fonte real (`NAO_ABRA/`).
- Importar de `pipelines/m1/`, `dashboard/`, `censo_*` ou `api` (isolamento da camada paralela).
- Res-8 / novas cadências de coleta / integração WellHub-TotalPass ao residual.

## Cobertura de classificação de rede (anti-PII, só contagens)
Inspeção do `03_Competidores.xlsx` (24.045 linhas) por CONTAGEM contra o vocabulário das 28 redes de `concorrentes_mapeados.parquet` (normalização + token whole-word), método candidato do bloco:
- **Redes distintas no vocabulário:** **28** (smart_fit, panobianco, bluefit, selfit, pratique, bodytech, phd_sports, gavioes, velocity, allp_fit, 26fit, engenharia_do_corpo, vidya_studio, contorno_do_corpo, evoque, live, tonus_gym, bio_ritmo, aera_pilates, race_bootcamp, alpha_fitness, greenlife, xprime, kore, cia_athletica, world_gym, red_fitness, jab_house).
- **Classificáveis como rede conhecida:** **713 de 24.045 (~3,0%)** — casam em **20 das 28 redes**. Maiores: panobianco 149, velocity 114, gavioes 91, 26fit 67, evoque 48, vidya_studio 46, kore 37, bio_ritmo 33, smart_fit 29, live 25 (bate a estimativa do BO do TP-08: panobianco 149, smart 29, bio ritmo 33).
- **`independente`/desconhecida:** **23.332 (~97,0%)** — o dump é dominado por academias de bairro/independentes (esperado p/ agregador TotalPass).
- **N por rede p/ média confiável:** N≥5 em 16 redes, **N≥10 em 13 redes**, N≥20 em 11 redes → a tabela de média por rede é confiável só para ~13 redes; o restante entra com flag de baixa confiabilidade. Isso fecha a lacuna 2 do FU1 (média por rede além de SkyFit/Engenharia) para as redes com N suficiente.
- **Média real pré-existente:** `base_calibracao_multirede.parquet` (`marca`) só tem 2 concorrentes (skyfit 311, engenharia_do_corpo 61) + ultra 54 — confirma a lacuna que este bloco fecha.

> NOTA de fidelidade: token bruto pode gerar falsos positivos (ex.: `live ` / `race ` / `jab ` casam substrings comuns); o Planner deve especificar tokens com boundary e curar a lista final (regra: precisão > recall — falso `independente` é aceitável, falso rótulo de rede não). Contagens acima são estimativa de ordem de grandeza.

## Arquivos que devem ser lidos
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\demanda_revelada\oferta_academias_menores.py`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\demanda_revelada\contrato.py`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tests\unit\test_demanda_revelada_ingestao.py` (padrão de fixture sintética + `test_zero_pii`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\data\staging\concorrentes_mapeados.parquet` (coluna `rede` = vocabulário; `hex_id_res7` = chave de dedup)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\data\staging\base_calibracao_multirede.parquet` (redes com média real pré-existente; coluna `marca`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\docs\modelo_mercado_hexagonos.md` (join por `hex_id` / capacidade por unidade)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\CLAUDE.md` (§1 redes low-cost; §4/§5; DEC-012; DEC-013 parte 3)

## Arquivos que podem ser alterados
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\demanda_revelada\oferta_academias_menores.py` (ou NOVO módulo irmão em `demanda_revelada/`, ex.: `oferta_por_rede.py` — Planner decide)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\demanda_revelada\contrato.py` (aditivo — novo contrato/constantes de rede, sem quebrar `oferta_menores_v1`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tests\unit\` (testes novos com fixtures sintéticas)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tests\fixtures\` (fixture sintética com nomes fake de rede, se necessária)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\data\reports\scratch\` (relatório de qualidade/cobertura, gitignored)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\docs\modelo_mercado_hexagonos.md` (documentar o novo contrato, se aprovado)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tasks\backlog.md` / `tasks\current_task.md` / `tasks\completed.md`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\context\handoff.md` e `context\handoff\`

## Critérios de aceite
- `rede_menor` é derivada do `Nome_Academia` e o `Nome_Academia`/`Latitude`/`Longitude`/`Cluster_ID` são **dropados na fronteira** (mesmo ponto do TP-08); nenhum deles aparece em parquet/relatório/log/teste.
- `test_zero_pii` (ou equivalente) FALHA se qualquer coluna de `_COLUNAS_PII_LOCAIS`/`COLUNAS_PII_PROIBIDAS` (incl. `nome_academia`, `latitude`, `longitude`, `cluster_id`, `total_alunos_cluster`) surgir nas novas saídas.
- Saída (a): parquet gitignored em `data/staging/` com `hex_id` (res-7 válido) × `rede_menor` × `n_academias_menores` × `alunos_academias_menores` (Σ `Alunos_Academia`, jamais `Total_Alunos_Cluster`) + `versao_contrato`; join por `hex_id` com o universo do Motor reproduzível.
- Saída (b): tabela/parquet gitignored `rede_menor` → `media_alunos`, `mediana_alunos`, `n_filiais` + flag de confiabilidade por N mínimo aprovado; cobre as redes conhecidas com N suficiente (≥ ~13 redes).
- Não classificáveis caem em `independente`; a categoria não reidentifica nenhum estabelecimento individual.
- Nenhum artefato oficial do M1 alterado (mtime dos 4 oficiais inalterado); nenhum import de `pipelines/m1`/`dashboard`/`censo_*`/`api`.
- Testes usam fixtures sintéticas; a fonte real (`NAO_ABRA/`) não é versionada.
- Suíte verde (ruff + mypy + pytest do escopo tocado) sem CI vermelho.

## Criticidade classificada
**Alta** — re-ingestão com classificação de rede derivada de nome cru sob anti-PII (DEC-012); exige revisão humana do vocabulário/matching e da não-reidentificação. NÃO é crítica: READ-ONLY sobre o M1, zero escrita em score/pesos/carteira/plano/artefatos oficiais (nenhum gatilho do guardrail de criticidade do prompt do BO).

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA OBRIGATÓRIA — anti-PII + classificação/vocabulário de rede]** → Builder → QA (Opus 4.8). Bloco AD-HOC (adicionar BLK-TP-08-FU ao backlog durante o ciclo; ao fechar, desbloquear BLK-TP-06-FU1).

## Riscos identificados
- **Reidentificação por categoria (anti-PII):** uma `rede_menor` de baixíssima cardinalidade (ex.: rede com 1 filial no dump) poderia, combinada ao hex, aproximar a identidade do estabelecimento. Mitigação a definir no gate: colapsar redes com N muito baixo em `independente` e/ou não expor média por rede abaixo do N mínimo.
- **Falsos positivos de matching por token:** tokens curtos/comuns (`live `, `race `, `jab `) casam substrings genéricas → risco de rotular indevidamente. Regra: precisão > recall; boundary de palavra + lista curada; falso `independente` é aceitável.
- **Cobertura baixa (~3%):** 97% caem em `independente` — a tabela de média por rede só ajuda o FU1 para as ~13 redes com N≥10; para as demais o dado permanece raso (registrar como caveat, não como falha).
- **Chave de dedup divergente:** `concorrentes_mapeados` usa `hex_id_res7`; o TP-08 usa `hex_id` — garantir join consistente res-7.
- **Ambiguidade de precedência de matching:** nome com dois tokens (raro) precisa de ordem determinística (first-match) documentada.
- **Escopo:** tentação de já integrar ao residual/aplicar dedup — proibido neste bloco.

## Ambiguidades para o gate (decisões de produto a fechar antes do Builder)
- **(a) Vocabulário/método de matching:** lista curada das 28 redes de `concorrentes_mapeados` como alvo? Token exato vs normalizado+boundary? Curadoria manual dos tokens ambíguos?
- **(b) Não-classificáveis:** categoria única `independente` (recomendado)? Colapsar também redes de N muito baixo em `independente` por anti-PII?
- **(c) Formato do parquet (a):** LONGO `hex_id×rede_menor` (recomendado — robusto a novas redes) vs LARGO (uma coluna por rede)?
- **(d) Média por rede (b):** usar média, mediana ou ambas? **N mínimo** para a média ser confiável (candidato N≥10, cobre 13 redes; N≥20 cobre 11)? Redes abaixo do N entram com flag ou ficam de fora?

## Guardrails ativos
- **§5 (READ-ONLY M1):** zero recálculo de score/pesos/carteira/plano/artefatos oficiais; NÃO recompor o residual; pesos `renda=0.40`/`pop=0.60` e `score_priorizacao` INALTERADOS.
- **DEC-012 (anti-PII POR CONSTRUÇÃO):** rede classificada na FRONTEIRA; `Nome_Academia`/Lat/Lng/`Cluster_ID`/`Total_Alunos_Cluster` descartados na entrada, nunca persistidos/logados; `rede_menor` é CATEGORIA (não o nome) e não pode reidentificar; zero PII em artefato/log/teste (rede de segurança automatizada); fonte real em `NAO_ABRA/` (gitignored, nunca versionada); fixtures sintéticas.
- **DEC-013 (parte 3):** dedup + capacidade por tipo é exatamente o que este bloco HABILITA (rótulo de rede + média por rede); a integração ao residual permanece follow-up sob gate.
- **DEC-009:** oferta é insumo OBSERVADO, NUNCA preditor geográfico de magnitude.
- **Isolamento:** pacote `demanda_revelada/` NÃO importa de `pipelines/m1/`, `dashboard/`, `censo_*` nem `api`.
