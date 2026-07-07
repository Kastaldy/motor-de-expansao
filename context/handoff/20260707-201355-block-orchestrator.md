# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-VIAB-01 — Validação/limpeza da base de imóveis candidatos

## Objetivo
Ler `data/ultra/Imoveis_16-06-2026_150117.xlsx`, aplicar as 4 regras de limpeza PRÉ-FIXADAS e materializar `data/staging/imoveis_candidatos_limpos.parquet` + `data/analysis/imoveis_qualidade.md`.

## Inspeção real do arquivo (confirmada pelo BO)

Arquivo: `data/ultra/Imoveis_16-06-2026_150117.xlsx`
- Sheet única: `Imóveis`
- Linha 0: título "RELATÓRIO DE IMÓVEIS (16/05/2026 à 16/06/2026)"
- Linha 1: vazia
- **Linha 2: cabeçalho real** — usar `header=2` ao chamar `pd.read_excel`
- 28 linhas de dados (IDs 424–452)

**Colunas confirmadas (19 no total):**
`ID`, `NOME`, `ÁREA`, `VAGAS`, `ALUGUEL`, `LOGRADOURO`, `NÚMERO`, `COMPLEMENTO`, `BAIRRO`, `CIDADE`, `ESTADO`, `CEP`, `LATITUDE`, `LONGITUDE`, `DATA CADASTRO`, `DATA ATUALIZAÇÃO`, `STATUS`, `ATIVO`, `DESCRIÇÃO`

**Observações críticas:**
- `ÁREA`: todos 28 preenchidos. Valores problemáticos confirmados: `14.9` (ID 430), `25.63` (ID 443), `190.0` (ID 432), `200.0` (ID 435) — abaixo de 500 m². Faixa válida restante: `991.0` a `4000.0` m².
- `ALUGUEL`: todos 28 preenchidos. Placeholder `11111.11` presente em ID 452. Demais valores entre `10.000` e `151.000` — todos dentro do range `[10.000, 500.000]`.
- `LATITUDE`/`LONGITUDE`: **ZERO registros com coordenada** (28/28 NaN). Todos ganham `flag_sem_coord=True`.
- `STATUS`: `PROSPECÇÃO` (25), `APROVADOS` (2), `HISTÓRICO COMITÊ` (1). Manter todos.
- **Estimativa limpo:** 28 - 4 (área < 500) - 1 (placeholder aluguel, ID 452 com área 2100) = **23 registros limpos**, todos com `flag_sem_coord=True`.

## Escopo permitido
- Criar `src/motor_expansao/dimensionamento/imoveis_candidatos.py` com funções puras: `ler_imoveis_xlsx(path)`, `validar_e_limpar(df)`, `materializar(df, staging_dir, analysis_dir)`.
- Criar `tests/unit/dimensionamento/test_imoveis_candidatos.py` com fixture sintética (não usa o xlsx real).
- Materializar `data/staging/imoveis_candidatos_limpos.parquet` (gitignored, paralela).
- Materializar `data/analysis/imoveis_qualidade.md` com tabela contagem entrou/descartado por regra (área/placeholder/aluguel-fora-de-range), total limpo, % sem coordenada.

## Fora de escopo
- Geocoding ao vivo ou enriquecimento de coordenadas (blocos humanos BLK-VIAB-03 e seguintes; DEC-010/013).
- Alteração de `config.py` raiz do M1 (`src/motor_expansao/config.py`). Parâmetros de limpeza são locais ao novo módulo.
- Qualquer escrita em `pipelines/m1/`, `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais.
- Alteração do `dimensionamento/config.py` existente (não é necessária).
- Deploy, VPS, Docker, CI externo.

## Arquivos que devem ser lidos
- `/repo/data/ultra/Imoveis_16-06-2026_150117.xlsx` (insumo real; `header=2`)
- `/repo/src/motor_expansao/dimensionamento/config.py` (padrões anti-PII e diretórios do módulo)
- `/repo/src/motor_expansao/dimensionamento/__init__.py` (verificar exportações existentes)
- `/repo/tasks/backlog.md` linhas 892–921 (decisões PRÉ-FIXADAS)
- `/repo/CLAUDE.md` §2/§5/§6.1 (guardrails, loop_guard, acento)

## Arquivos que podem ser alterados
- `src/motor_expansao/dimensionamento/imoveis_candidatos.py` (NOVO)
- `tests/unit/dimensionamento/test_imoveis_candidatos.py` (NOVO)
- `data/staging/imoveis_candidatos_limpos.parquet` (gitignored, gerado, não commitado)
- `data/analysis/imoveis_qualidade.md` (gitignored, gerado, não commitado)
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (fechamento do ciclo)
- `context/handoff.md`, `context/handoff/` (handoffs do ciclo)

## Critérios de aceite
- `data/staging/imoveis_candidatos_limpos.parquet` materializado com colunas originais + `flag_sem_coord` (bool).
- Registros com `ÁREA < 500` ausentes do parquet limpo.
- Registros com `ALUGUEL == 11111.11` (placeholder) ou fora de `[10.000, 500.000]` ausentes do parquet limpo.
- Coluna `STATUS` preservada com todos os valores originais dos sobreviventes.
- Todos os registros do parquet limpo têm `flag_sem_coord=True` (snapshot atual: 0/28 com coordenada).
- `data/analysis/imoveis_qualidade.md` com contagem entrou/descartado por regra.
- Determinístico: mesmas entradas → mesma saída.
- Testes com fixture sintética passam (`pytest tests/unit/dimensionamento/test_imoveis_candidatos.py`).
- `ruff` e `mypy` limpos no módulo novo.
- Suite completa verde (`pytest -q`, sem regressão).
- `loop_guard.py` não dispara (zero toque em `config.py` raiz / `pipelines/m1` / artefatos oficiais).

## Criticidade classificada
Média — camada paralela de dados de entrada; READ-ONLY sobre o M1.

## Esteira recomendada
Block Orchestrator (este) → **Planner** → Builder → QA

## Riscos identificados
- **Cabeçalho na linha 2** (0-indexado): ler com `header=2`; se usar `header=0` os dados ficam corrompidos.
- **ÁREA é float**: comparar `< 500.0` (não inteiro). Valores como `14.9` e `25.63` precisam de float.
- **Placeholder 11111.11**: no xlsx já é `float 11111.11`; comparar com tolerância `abs(val - 11111.11) < 0.01` para evitar erro de ponto flutuante em leituras com locale alternativo.
- **Zero coordenadas no snapshot atual**: `flag_sem_coord` será `True` para todos os sobreviventes; o relatório deve explicitar esse fato.
- **Crescimento da base**: o módulo deve aceitar qualquer snapshot `Imoveis_*.xlsx` com o mesmo schema, sem hardcodar o nome do arquivo.

## Guardrails ativos
- §5 READ-ONLY M1: nenhuma escrita em `config.py` raiz / `pipelines/m1` / artefatos oficiais.
- §6.1 loop-safe: `loop_guard.py` aborta se diff tocar `config.py`/`pipelines/m1`/`*scoring*`/artefatos M1/deploy/Docker/compose/Caddy/authelia/`.env`/`secrets/`/CI.
- DEC-009: demanda NUNCA prevista pela geografia; este bloco não toca demanda.
- DEC-010/013: geocoding é passo humano separado; NÃO fazer fetch HTTP neste bloco.
- §2: sem dependência de API ao vivo; leitura local do xlsx apenas.
- Saída em `data/staging/` e `data/analysis/` (ambos gitignored); zero commit de dados.
