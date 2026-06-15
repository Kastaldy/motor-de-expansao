# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco
BLK-DIM-11 — Esteira property-first: motor de viabilidade do imóvel

## Análise do escopo

O BLK-DIM-11 materializa o "Caminho A" decidido pelo BLK-DIM-10: após 4 NO-GOs honestos
(DIM-01R/05/08 + spike de densidade) que provaram que **a geografia não prevê demanda nem
densidade**, a esteira inverte — em vez de prever o melhor lugar, o operador traz um imóvel
real e a ferramenta stress-testa a viabilidade.

### O que existe e será orquestrado (quase tudo já existe)

Três peças validadas cobrem o núcleo:

1. **`simulador.py` (DIM-03R):** `viabilidade()`, `aluguel_teto()`, `alunos_minimos_viaveis()`,
   `m2_otimo()` e `ViabilidadeResult`. Toda a aritmética do DRE + goal-seek já está aqui.
   A função `viabilidade()` aceita `alunos_maturidade` como **premissa explícita** — exatamente
   o contrato exigido pelo BLK-DIM-11 (demanda entra pelo operador, nunca pela geografia).

2. **`catchment_batch.py` (DIM-07):** `calcular_catchment_unidade(lat, lng, setores_df, raio_km)`
   retorna `pop_captacao`, `renda_per_capita_captacao`, `n_setores_captacao`. Fornece o
   **contexto do entorno** (pop/renda) e a base para sinalizar "zona sem demanda". O módulo
   já está parametrizado com `RAIO_CATCHMENT_KM=1.5` do `dimensionamento/config.py`.

3. **`base_multirede.py` (DIM-07):** `haversine_km()`, `_conc_por_km2()`, `raio_variavel_km()`
   e o parquet `concorrentes_mapeados.parquet`. Fornece o **consumo concorrente do entorno**
   e a métrica de saturação do mercado.

### O que é lógica nova (a criar em `viabilidade_ponto.py`)

A. **Faixa de plausibilidade de alunos por densidade (curva tamanho→densidade):**
   O único sinal usável (corr −0.37, confirmado em DIM-03R) é `alunos_por_m2` em função do
   tamanho. A base `unidades_ultra_performance_hex.parquet` já tem `alunos_por_m2` e `metragem`
   (54 unidades). A lógica nova é: dado `m²` do imóvel candidato, derivar percentis
   (p10/p50/p90) de `alunos_por_m2` da amostra de comparáveis Ultra por faixa de m²,
   multiplicar por `m²` para obter a **faixa de alunos** (`alunos_min`/`alunos_mediana`/
   `alunos_max`). Isso **não é previsão geográfica** — é uma distribuição empírica de
   referência dos comparáveis internos por tamanho.

B. **Flag de zona morta:**
   Condição exógena (não preditiva) que sinaliza risco de demanda insuficiente baseada em
   thresholds de pop/renda do entorno e de saturação concorrente — NÃO uma previsão de alunos.
   Exemplo: `pop_captacao < POP_ZONA_MORTA_MIN` OU `renda_per_capita_captacao < RENDA_ZONA_MORTA_MIN`
   → `flag_zona_morta=True`. Thresholds parametrizados em constantes locais do módulo.

C. **Grade de sensibilidade demanda × aluguel:**
   Varrer uma grade discreta de `alunos_premissa` × `aluguel_mes` e para cada célula chamar
   `viabilidade()`. Retornar a grade como lista de dicts (sem plotagem — UI é BLK-DIM-12).
   Lógica de iteração simples sobre as peças existentes.

D. **Orquestrador `analisar_viabilidade_ponto()`:**
   Função pura que conecta os três componentes existentes com as três lógicas novas:
   1. Catchment do ponto → contexto (pop/renda/consumo concorrente) + flag_zona_morta
   2. Faixa de alunos por comparáveis de densidade (nova)
   3. `aluguel_teto()` + `alunos_minimos_viaveis()` + `viabilidade()` para o cenário pedido
   4. Grade de sensibilidade (nova)
   Retorna dict estruturado.

### O que ESTÁ FORA DE ESCOPO (inviolável)

- UI/plotagem no dashboard (BLK-DIM-12)
- Prever demanda/alunos pela geografia (4 NO-GOs)
- Qualquer escrita em artefatos M1 (score, pesos, carteira, plano)
- Ingesta ao vivo de dados externos
- PII em disco

## Componentes existentes a orquestrar

| Arquivo | Função/classe | O que fornece ao BLK-DIM-11 |
|---|---|---|
| `simulador.py` | `viabilidade(alunos_maturidade, m2, aluguel_mes, ticket_medio, **kwargs)` | DRE completo: faturamento, ebitda, margem, payback, ROIC, flag_viavel |
| `simulador.py` | `aluguel_teto(alunos_maturidade, m2, ticket_medio, margem_alvo, **kwargs)` | Aluguel máximo para a margem-alvo (goal-seek) |
| `simulador.py` | `alunos_minimos_viaveis(m2, aluguel_mes, ticket_medio, margem_alvo, **kwargs)` | Break-even em alunos |
| `simulador.py` | `ViabilidadeResult` (dataclass) | Tipagem do resultado financeiro |
| `catchment_batch.py` | `calcular_catchment_unidade(lat, lng, setores_df, raio_km)` | pop/renda/n_setores do entorno do imóvel |
| `base_multirede.py` | `haversine_km()`, `_conc_por_km2()` | Distância e saturação concorrente no entorno |
| `base_multirede.py` | `raio_variavel_km(densidade_hab_km2, n_concorrentes_km2)` | Raio adaptado ao contexto urbano |
| `dimensionamento/config.py` | `RAIO_CATCHMENT_KM`, `SIM_*`, `PII_COLUNAS_PROIBIDAS` | Constantes canônicas do módulo |

**Parquet de comparáveis (para faixa de densidade):**
`data/staging/unidades_ultra_performance_hex.parquet` — tem `metragem` e `alunos_por_m2`
das 54 unidades Ultra maduras. Leitura sob demanda (lazy), não persiste nada.

**Parquet de concorrentes (para saturação):**
`data/staging/concorrentes_mapeados.parquet` — já lido em `base_multirede.py`.

## Lógica nova necessária

### 1. `faixa_alunos_por_densidade(m2, comparaveis_df) -> dict`
- Filtra `comparaveis_df` por faixa de m² (±20% do `m2` candidato, ou toda a base se N < 5)
- Computa p10/p50/p90 de `alunos_por_m2` nos comparáveis
- Multiplica por `m2` → `alunos_min`, `alunos_mediana`, `alunos_max`
- Retorna dict com os 3 valores + `n_comparaveis` + `nota_honesta` (interpolação ou extrapolação)
- **Sem escrita em disco, sem PII**

### 2. `flag_zona_morta(pop_captacao, renda_per_capita, n_concorrentes_km2) -> dict`
- Thresholds: `POP_ZONA_MORTA_MIN` (sugerido: 5_000 hab, alinhado com `POP_MIN_ACIONAVEL`)
  e `RENDA_ZONA_MORTA_MIN` (alinhado com `RENDA_MIN = 4500.0` do M1 canônico)
- Retorna `flag_zona_morta: bool` + `motivos: list[str]` (quais thresholds dispararam)
- Thresholds como constantes locais em `viabilidade_ponto.py`; não alteram M1

### 3. `grade_sensibilidade(m2, aluguel_pedido, ticket_medio, alunos_range, aluguel_range, **kwargs) -> list[dict]`
- Itera produto cartesiano de `alunos_range × aluguel_range` (grades discretas, ex. 5×5 = 25 pontos)
- Cada ponto: chama `viabilidade()` e extrai `flag_viavel`, `margem_ebitda_pct`, `payback_meses`
- Retorna lista de dicts (sem plotagem)

### 4. `analisar_viabilidade_ponto(lat, lng, m2, aluguel_pedido, demanda_premissa, ticket_medio, *, ...) -> dict`
- Função pública principal: orquestra os 3 existentes + 3 novos
- `demanda_premissa` é obrigatório (float > 0 ou None para indicar que o operador não forneceu)
- Se `demanda_premissa is None`: usa `alunos_mediana` da curva de densidade como fallback com aviso
- NUNCA deriva demanda da geografia

## Interface esperada

```python
# viabilidade_ponto.py

@dataclass
class ViabilidadePontoResult:
    # Contexto do entorno
    pop_captacao: float
    renda_per_capita_captacao: float
    n_concorrentes_km2: float
    raio_usado_km: float
    flag_zona_morta: bool
    motivos_zona_morta: list[str]
    # Faixa de alunos por comparáveis de densidade (NOT previsão geográfica)
    alunos_min_densidade: float          # p10 da curva tamanho→densidade
    alunos_mediana_densidade: float      # p50
    alunos_max_densidade: float          # p90
    n_comparaveis_densidade: int
    nota_densidade: str                  # "interpolacao" | "extrapolacao"
    # Resultado financeiro no cenário pedido (demanda = premissa explícita)
    demanda_premissa: float              # SEMPRE o input do operador
    viabilidade_pedido: ViabilidadeResult   # saída de simulador.viabilidade()
    aluguel_teto_calculado: float
    alunos_breakeven: float
    # Grade de sensibilidade
    grade: list[dict]                    # [{alunos, aluguel, flag_viavel, margem, payback}, ...]


def analisar_viabilidade_ponto(
    lat: float,
    lng: float,
    m2: float,
    aluguel_pedido: float,
    demanda_premissa: float,             # alunos balcão na maturidade — PREMISSA DO OPERADOR
    ticket_medio: float = SIM_MENSALIDADE_BALCAO,
    *,
    margem_alvo: float = 0.10,
    raio_catchment_km: float = RAIO_CATCHMENT_KM,
    setores_df: pd.DataFrame | None = None,    # None = sem censo geo (catchment retorna NaN)
    conc_lat: np.ndarray | None = None,
    conc_lng: np.ndarray | None = None,
    alunos_grade: tuple[float, ...] = (500, 700, 938, 1100, 1400),
    aluguel_grade: tuple[float, ...] = (10_000, 15_000, 20_000, 25_000, 30_000),
    **kwargs,  # repassados para viabilidade()
) -> ViabilidadePontoResult: ...


def faixa_alunos_por_densidade(
    m2: float,
    comparaveis_df: pd.DataFrame,        # deve ter 'metragem' e 'alunos_por_m2'
    banda_pct: float = 0.20,             # ±20% do m2 candidato para filtro de comparáveis
    n_min_comparaveis: int = 5,
) -> dict: ...


def flag_zona_morta(
    pop_captacao: float,
    renda_per_capita: float,
    n_concorrentes_km2: float,
) -> dict: ...    # {flag_zona_morta: bool, motivos: list[str]}


def grade_sensibilidade(
    m2: float,
    ticket_medio: float,
    alunos_range: tuple[float, ...],
    aluguel_range: tuple[float, ...],
    **kwargs,
) -> list[dict]: ...
```

## Guardrails verificados

- **READ-ONLY sobre M1:** nenhum toque em `config.py` raiz, `pipelines/m1/`, `score_priorizacao`,
  `hex_score_estrutural`, `brasil_estrutural.parquet`, `brasil_priorizados.parquet` ou qualquer
  artefato oficial. O módulo fica em `src/motor_expansao/dimensionamento/viabilidade_ponto.py`
  (camada paralela isolada). DEC-001 e DEC-008 intactas.

- **Demanda SEMPRE premissa explícita:** `demanda_premissa` é parâmetro obrigatório de
  `analisar_viabilidade_ponto()`. Se `None`, usa fallback da curva de comparáveis com aviso
  explícito no resultado — nunca deriva alunos da lat/lng. Teste garante que a saída não
  contém derivação geográfica de demanda.

- **Anti-PII:** o módulo lê apenas lat/lng, metragem e alunos_por_m2 dos parquets. Sem
  `nome`, `cpf`, `email` etc. `assert_sem_pii` já disponível em `growth_api_client.py` e
  deve ser invocado se qualquer saída for persistida (mas a função pública retorna dict em
  memória, sem escrita).

- **Sem ingestão ao vivo:** lê apenas `data/staging/unidades_ultra_performance_hex.parquet`
  e `data/staging/concorrentes_mapeados.parquet` (Parquets locais pré-existentes). O
  `setores_df` para o catchment é injetado como parâmetro — o módulo não faz I/O de censo
  por conta própria (responsabilidade do chamador ou do teste).

- **Sem UI:** retorna dict/dataclass. Plotagem é BLK-DIM-12 (gate humano, não loop-safe).

- **Testes determinísticos:** fixtures sintéticas (sem leitura de staging real). A função
  `analisar_viabilidade_ponto()` aceita `setores_df=None` e arrays de concorrentes vazios —
  modos degradados para teste.

- **Sem dependência de API ao vivo:** nenhuma chamada HTTP.

- **CI:** ruff + mypy + pytest devem passar; nenhum arquivo de M1 tocado.

## Arquivos-alvo para o Planner

O Planner deve ler:

1. `/repo/src/motor_expansao/dimensionamento/simulador.py` — funções `viabilidade()`,
   `aluguel_teto()`, `alunos_minimos_viaveis()` e `ViabilidadeResult`
2. `/repo/src/motor_expansao/dimensionamento/catchment_batch.py` — `calcular_catchment_unidade()`
3. `/repo/src/motor_expansao/dimensionamento/base_multirede.py` — `haversine_km()`,
   `_conc_por_km2()`, `raio_variavel_km()`
4. `/repo/src/motor_expansao/dimensionamento/config.py` — todas as constantes `SIM_*` e
   `RAIO_CATCHMENT_KM`
5. `/repo/tasks/backlog.md` (linhas 456–500) — spec completo do BLK-DIM-11
6. `/repo/tasks/current_task.md` — contexto da tarefa ativa
7. `/repo/CLAUDE.md` — guardrails canônicos (§2, §3, §6.1)
8. `/repo/src/motor_expansao/dimensionamento/growth_api_client.py` — `assert_sem_pii()`

Arquivos de contexto secundário (se necessário):
- `/repo/src/motor_expansao/dimensionamento/calibracao_maduras.py` — para ver como
  `alunos_por_m2` flui do performance parquet
- `/repo/src/motor_expansao/dimensionamento/backtest_dim.py` — padrão de orquestração
  (como o backtest chama `viabilidade()`)

## Alertas / riscos

1. **Faixa de comparáveis por densidade:** A base de Ultra tem apenas 54 unidades. Com
   filtro ±20% de m², o N de comparáveis pode ser < 5 em extremos. O Planner deve especificar
   o fallback: usar a base inteira se N < `n_min_comparaveis`. Emitir `nota_densidade = "extrapolacao"`
   se o `m2` candidato cair fora do range observado [metragem_min, metragem_max].

2. **`setores_df` ausente em produção:** `calcular_catchment_unidade()` requer o DataFrame
   de setores censitários carregado. Em produção, o chamador precisa carregar via
   `read_censo_geo_partition(geo_dir, uf)`. O módulo `viabilidade_ponto.py` **não** deve
   carregar I/O de censo internamente (violaria o guardrail de staging); deve aceitar
   `setores_df: pd.DataFrame | None = None` com degradação graciosa (pop/renda → NaN,
   flag_zona_morta → False por padrão quando sem dado).

3. **`conc_lat`/`conc_lng` para saturação:** para calcular `n_concorrentes_km2`, o módulo
   precisa das coordenadas do `concorrentes_mapeados.parquet`. O Planner deve decidir se
   o módulo carrega internamente (simples mas viola injeção) ou se o chamador injeta (testável).
   Recomendação do BO: injetar como `conc_lat: np.ndarray | None = None` — se None, o módulo
   carrega internamente com path padrão (facilita uso em produção sem sacrificar testabilidade).

4. **Grade de sensibilidade e performance:** 5×5 = 25 chamadas a `viabilidade()` são
   instantâneas (aritmética pura). Se o Planner optar por grades maiores (ex.: 10×10 = 100),
   ainda é trivial, mas deve parametrizar os ranges.

5. **Demanda premissa obrigatória vs. None:** o backlog diz "demanda SEMPRE premissa explícita".
   O Planner deve definir se `demanda_premissa=None` é erro (ValueError) ou fallback com aviso.
   Recomendação do BO: aceitar None com fallback na mediana da curva de comparáveis + flag
   `demanda_eh_estimativa=True` no resultado — o operador ainda vê a conta, mas sabe que não
   inseriu a premissa.

6. **Guardrail de teste anti-previsão geográfica:** o teste deve garantir que a função não
   varia o campo `demanda_premissa` ao mudar lat/lng (mantendo m2, aluguel, ticket fixos).
   Isso prova que a latitude/longitude só afeta contexto (pop/renda), não a demanda inferida.
