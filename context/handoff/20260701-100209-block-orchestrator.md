# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (override -1: fallback único totalmente especificado; design mínimo, sem ambiguidade de produto)

## Bloco refinado
BLK-DIM-18 — Fix: faixa de alunos pela metragem ausente em produção (fallback para parquet de unidades)

## Objetivo
Adicionar, em `load_base_calibracao()` (streamlit_app.py), um caminho de fallback que lê `data/staging/unidades_ultra_performance_hex.parquet` quando `BASE_CALIBRACAO_PATH` não existe, permitindo que a faixa p10/p50/p90 seja exibida no dashboard em produção onde o multirede não foi regenerado.

## Escopo permitido
- `streamlit_app.py`, função `load_base_calibracao()` (linhas 344–359): inserir bloco de fallback entre `return pd.DataFrame()` (linha 354) e o `return df` final — lê `STAGING_DIR / "unidades_ultra_performance_hex.parquet"` e entrega o DataFrame já com `alunos_por_m2` preenchida.
- `STAGING_DIR` não existe como constante nomeada: o path do fallback deve ser construído por derivação de `BASE_CALIBRACAO_PATH.parent` (que é `data/staging/`).
- `alunos_por_m2` JÁ EXISTE pré-computada no parquet de fallback (0 NaNs em 54 linhas); o Builder PODE simplesmente usar a coluna existente. Mas, para consistência com a lógica da função principal (e com `calcular_penetracao_ultra_hex.py:174`), a opção recomendada é RE-DERIVAR via `alunos_total / metragem` com o mesmo guard `(alunos > 0) & (metragem > 0)` — idêntico ao bloco das linhas 356–358 mas trocando `alunos_reais` por `alunos_total`. Qualquer das duas abordagens é válida; o Planner decide e documenta.
- 1 teste novo em `tests/integration/test_streamlit_app.py` cobrindo o caminho de fallback (multirede ausente, parquet de unidades presente → `alunos_por_m2` no retorno).

## Fora de escopo (invioláveis)
- Regenerar `base_calibracao_multirede.parquet` (pipeline `base_multirede.py` — outro ciclo).
- Tocar `viabilidade_ponto.py`, `simulador.py` ou qualquer engine de dimensionamento.
- Alterar qualquer campo M1 (`score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais).
- Expandir para outros arquivos além de `streamlit_app.py` e o arquivo de teste.

## Arquivos que devem ser lidos
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\streamlit_app.py` — linhas 207–212 (constantes de path) e linhas 344–359 (função `load_base_calibracao` completa)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tests\integration\test_streamlit_app.py` — linhas 5333–5350 (teste existente `test_load_base_calibracao_deriva_alunos_por_m2`, modelo para o novo teste)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\src\motor_expansao\dimensionamento\viabilidade_ponto.py` — linhas 106–155 (assinatura e consumo de `alunos_por_m2` pelo engine)

## Arquivos que podem ser alterados
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\streamlit_app.py` (apenas `load_base_calibracao`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tests\integration\test_streamlit_app.py` (adicionar 1 teste)

## Evidências do código (para o Planner/Builder não precisar re-investigar)

### 1. Assinatura e lógica atual de `load_base_calibracao()` (linhas 344–359)
```python
@st.cache_data(show_spinner=False)
def load_base_calibracao() -> pd.DataFrame:
    if not BASE_CALIBRACAO_PATH.exists():
        return pd.DataFrame()           # <-- fallback entra AQUI, antes deste return
    df = pd.read_parquet(BASE_CALIBRACAO_PATH)
    alunos = pd.to_numeric(df.get("alunos_reais"), errors="coerce")
    metragem = pd.to_numeric(df.get("metragem"), errors="coerce")
    df["alunos_por_m2"] = (alunos / metragem).where((alunos > 0) & (metragem > 0))
    return df
```
`BASE_CALIBRACAO_PATH` = `Path(__file__).resolve().parent / "data" / "staging" / "base_calibracao_multirede.parquet"` (linha 207–209). Não há `STAGING_DIR` nomeado; o diretório pai é `BASE_CALIBRACAO_PATH.parent`.

### 2. Colunas do parquet de fallback `unidades_ultra_performance_hex.parquet`
Confirmado por inspeção real do arquivo (`data/staging/unidades_ultra_performance_hex.parquet`, 54 linhas, 57 colunas):
- `metragem` — int64, presente, sem NaN.
- `alunos_total` — int64, presente (é o campo "alunos" operacional; NÃO existe `alunos_reais`).
- `alunos_por_m2` — float64, já pré-computada por `calcular_penetracao_ultra_hex.py:174` como `alunos_total / metragem`, 0 NaNs.
- **ATENÇÃO:** `alunos_reais` NÃO existe neste parquet. O bloco principal da função usa `df.get("alunos_reais")` — no fallback, o campo equivalente é `alunos_total`.

### 3. Como `alunos_por_m2` é derivado em `calcular_penetracao_ultra_hex.py` (linha 174)
```python
out["alunos_por_m2"] = _safe_div(out["alunos_total"], out["metragem"])
```
Para o fallback, a mesma lógica manual fica:
```python
alunos = pd.to_numeric(df.get("alunos_total"), errors="coerce")
metragem = pd.to_numeric(df.get("metragem"), errors="coerce")
df["alunos_por_m2"] = (alunos / metragem).where((alunos > 0) & (metragem > 0))
```
Alternativa válida (mais simples): a coluna `alunos_por_m2` já existe e está correta — o fallback pode retornar o parquet diretamente sem re-derivar, bastando garantir que a coluna está presente. O Planner escolhe; documentar a decisão no handoff do Planner.

### 4. O engine `faixa_alunos_por_densidade` (viabilidade_ponto.py:140)
Só exige `alunos_por_m2` e, opcionalmente, `metragem` para filtrar a janela. Não requer `alunos_reais`. O parquet de fallback tem ambas as colunas — o engine funcionará corretamente sem nenhuma alteração.

### 5. Teste existente (modelo para o novo)
`test_load_base_calibracao_deriva_alunos_por_m2` (linha 5333) cria um parquet sintético, monkeypatcha `BASE_CALIBRACAO_PATH` e valida `alunos_por_m2`. O novo teste deve monkeypatchar também `BASE_CALIBRACAO_PATH` para um path inexistente e um segundo atributo com o path do fallback (ou derivado do `BASE_CALIBRACAO_PATH.parent`), validando que `alunos_por_m2` aparece no retorno quando só o fallback existe.

## Critérios de aceite
- Com apenas `data/staging/unidades_ultra_performance_hex.parquet` presente (e `base_calibracao_multirede.parquet` ausente), `load_base_calibracao()` retorna um DataFrame não-vazio com a coluna `alunos_por_m2` sem NaNs nos registros válidos.
- O caminho principal (multirede presente) não é alterado — teste existente `test_load_base_calibracao_deriva_alunos_por_m2` continua verde sem modificação.
- Suíte completa verde (`pytest -q`): zero falhas, zero erros de coleta.
- `ruff check` e `mypy src/` limpos.
- Nenhuma coluna M1 (`score_priorizacao`, `hex_score_estrutural`, etc.) foi alterada ou regravada.
- O campo "Faixa de alunos plausível pela metragem" exibe p10/p50/p90 no dashboard quando apenas o parquet de unidades está presente.

## Criticidade classificada
Alta (toca `streamlit_app.py` de produção; READ-ONLY sobre o M1; não envolve `score_priorizacao`/artefatos oficiais)

## Esteira recomendada
Block Orchestrator (concluído) → Planner → [aprovação humana] → Builder (Opus) → QA (Opus 4.8)

## Tiering de modelo
- Block Orchestrator: Sonnet (concluído)
- Planner: Sonnet (override −1: fallback único especificado; design mínimo)
- Builder: Opus (código de produção em streamlit_app.py)
- QA: Opus 4.8 (sempre)

## Riscos identificados
- `alunos_reais` não existe no parquet de fallback: o Builder deve usar `alunos_total` (confirmado por inspeção) — se usar `df.get("alunos_reais")` copypaste do bloco principal, a coluna `alunos_por_m2` ficará toda NaN e a faixa continuará "n/d". Este é o risco principal do copy-paste cego.
- O cache `@st.cache_data` de `load_base_calibracao()` pode entregar o DataFrame vazio antigo após o deploy; o operador precisará restartar o Streamlit (ou o cache expirará naturalmente). Nenhuma ação de código necessária — registrar no runbook de deploy.
- O parquet de fallback `unidades_ultra_performance_hex.parquet` pode não existir no ambiente de CI nos testes se não for criado como fixture sintética — o teste novo deve usar `tmp_path` + fixture sintética, NÃO o arquivo real.

## Guardrails ativos
- §5 (READ-ONLY M1): visualizações, análise radial e interações de mapa não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- DEC-009: a demanda entra como premissa explícita (input do operador), NUNCA prevista pela geografia. O fallback não muda essa semântica.
- DEC-001: pesos `renda=0.40`/`pop=0.60` e fórmula do score INALTERADOS.
