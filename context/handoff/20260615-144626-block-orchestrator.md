# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Builder

## Bloco refinado
**BLK-FIX-13 — Data-drift em `test_csvs_concorrentes_legiveis` (2 falhas pré-existentes na suíte full)**

Reconciliar o teste parametrizado de contagem exata de CSVs de concorrentes com os dados reais regenerados, deixando a suíte full 100% verde sem mascarar regressão.

## Objetivo
Restaurar a suíte full 100% verde (0 failed) reconciliando `test_csvs_concorrentes_legiveis` com os CSVs de concorrentes atuais, sem perder capacidade de detecção de regressão real.

## Escopo permitido
- Alteração do teste `test_csvs_concorrentes_legiveis` em `tests/integration/test_modelo_mercado_hexagonos.py` (linhas 147-153) para implementar a abordagem escolhida.
- Documentação em comentário/docstring da mudança justificando por que contagem exata em dado gitignored é friável e a abordagem escolhida preserva sanidade.

## Fora de escopo
- Regenerar CSVs de concorrentes em `concorrentes/` (dados locais reais, GITIGNORED).
- Alterar `CSV_REQUIRED_COLS` (colunas obrigatórias permanecem o guardrail correto).
- Score, pesos, artefatos M1 (READ-ONLY; DEC-001); nenhuma alteração em componentes de cálculo de demanda/oferta/residual do motor.

## Arquivos que devem ser lidos
- `tests/integration/test_modelo_mercado_hexagonos.py` (linhas ~26-29: `CSV_SOURCES`; linhas ~147-153: função do teste)
- `concorrentes/*.csv` (para confirmação de contagens atuais, se necessário verificar na árvore local)

## Arquivos que podem ser alterados
- `tests/integration/test_modelo_mercado_hexagonos.py`

## Critérios de aceite
- Suite full roda com `pytest -q` (ou `pytest -n auto`) e retorna **0 failed, N passed, 1 skipped** (zero falhas do BLK-FIX-13).
- O teste mantém verificação de `CSV_REQUIRED_COLS` (schema) e parseabilidade (sem exceção).
- Documentação em código (comentário/docstring) explica a mudança: "Dado real gitignored é friável a regenerações; snapshot de contagem exata é anti-padrão. Mantém piso de sanidade para detectar regressão séria (CSV truncado/vazio) sem rebote a cada refresh legítimo."
- Nenhum artefato M1 alterado; READ-ONLY preservado.

## Criticidade classificada
**Baixa** (teste de dados desatualizado vs CSVs reais regenerados; READ-ONLY sobre M1)

## Esteira recomendada
**Block Orchestrator → Builder** (sem Planner/QA; Builder DEVE rodar suíte full para confirmar 0 falhas)

## Abordagem recomendada (decisão central)
**(B) Tornar o teste robusto a drift.**

Justificativa (2 frases):
O teste tem intenção "CSV parseável com colunas corretas" (demonstrado pelo nome `...legiveis` e pela verificação de `CSV_REQUIRED_COLS`), não "contagem exata de dado regenerado". Dado real gitignored é friável a regenerações; manter piso de sanidade (ex.: `len(df) >= 100`) preserva detecção de regressão séria (CSV vazio/truncado) sem rebote a cada refresh legítimo do pipeline.

**Implementação sugerida:** trocar `assert len(df) == expected_rows` por `assert len(df) >= piso`, onde o piso é um valor conservador (ex.: 100-200) que protege contra CSV não-vazio/parseável mas permite regenerações. Alternativamente, remover o `expected_rows` de `CSV_SOURCES` e substituir por um dicionário de pisos (ex.: `{path: piso_minimo}`).

## Riscos identificados
- **Risco baixo:** remover snapshot exato perde "early warning" de regressão silenciosa em contagem (ex., código que trunca CSV), porém pytest.skip em CI e piso razoável (>=100) ainda detectam CSV vazio/quebrado.
- **Risco de escopo:** se a mudança for interpretada como "robustecer TODO o teste", risco de expandir para outras verificações não-necessárias. Manter foco: só contagem exata → piso.

## Guardrails ativos
- **READ-ONLY M1 (DEC-001, §2, §5):** nenhuma alteração em `config.py`, score, pesos, artefatos M1 (brasil_estrutural.parquet, brasil_priorizados.parquet, etc.), carteira, plano, cálculos de mercado/residual.
- **Dados gitignored (§2):** CSVs em `concorrentes/` são dados reais locais, não artefatos versionados; nenhuma regeneração deles neste ciclo.
- **CI intacto:** pytest.skip mantém o teste verde em CI (arquivo não existe); vermelho é só local (DEV com arquivo real).

## Contexto adicional
- CSVs reais: smart_fit=1000 (estável), bluefit=226 (drift +3 vs 223), panobianco=455 (drift −17 vs 472).
- Origem da mudança: pipelines de mapeamento de concorrentes regeneram dados reais periodicamente; contagens variam conforme atualização de fonte e filtros de coleta.
- Comprovação: falhas independentes de BLK-EST-03 (reproduzem com BLK-EST-03 em stash), nada a ver com API/marca d'água.
- Builder: rodar `pytest -n auto` ou `pytest -q` (full suite) antes de fechar o bloco para confirmar 0 falhas (critério único de aceite).
