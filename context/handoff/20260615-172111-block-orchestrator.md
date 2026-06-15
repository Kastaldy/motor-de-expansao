# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (design UX detalhado) → [APROVAÇÃO HUMANA — Felipe/Vini] → Builder → QA

## Bloco refinado
**BLK-DIM-12 — UI da esteira property-first: ferramenta de viabilidade do imóvel no dashboard**

Nova função `render_viabilidade_ponto` em `src/motor_expansao/dashboard/pages.py`, plugada como
**expander adicional na aba Mapa Territorial** (imediatamente após o expander
`"Relatorio Pontual Censitario"`, linha ~2956 de `pages.py`), consumindo exclusivamente o engine
`analisar_viabilidade_ponto` do BLK-DIM-11 (já concluído). A escolha final entre expander no Mapa
Territorial vs nova aba fica para o Planner / gate humano — o padrão preferido do backlog é expander,
mas a alternativa de aba é explicitamente permitida.

## Objetivo
Permitir que o operador insira um imóvel real (lat/lng + m² + aluguel + demanda como premissa
explícita) e obtenha a viabilidade financeira completa (break-even, aluguel-teto, ROI/payback/ROIC,
grade de sensibilidade, faixa de alunos, contexto de entorno, flag de zona morta), sem nunca derivar
demanda de coordenadas geográficas.

## Contrato do engine (leitura obrigatória para Builder e Planner)

### Função pública principal
```python
# src/motor_expansao/dimensionamento/viabilidade_ponto.py
def analisar_viabilidade_ponto(
    lat: float,
    lng: float,
    m2: float,
    aluguel_pedido: float,
    demanda_premissa: float,          # ENTRADA EXPLÍCITA — nunca derivada de lat/lng
    *,
    ticket_medio: float = SIM_MENSALIDADE_BALCAO,
    margem_alvo: float = 0.10,
    raio_km: float = RAIO_CATCHMENT_KM,
    base_calibracao_df: pd.DataFrame | None = None,   # comparáveis; None = modo degradado
    setores_df: pd.DataFrame | None = None,           # setores censo; None = sem catchment
    alunos_range: tuple[float, ...] = ALUNOS_RANGE_DEFAULT,
    aluguel_range_fator: tuple[float, ...] = ALUGUEL_RANGE_FATOR,
    **kwargs,
) -> ViabilidadePontoResult
```

### Campos do resultado `ViabilidadePontoResult`
- **Inputs ecoados:** `lat`, `lng`, `m2`, `aluguel_pedido`, `demanda_premissa`
- **Faixa por densidade (curva m²→densidade, NÃO geográfica):** `faixa_alunos_p10/p50/p90`, `n_comparaveis`
- **Zona morta (contexto, NÃO predição de demanda):** `flag_zona_morta`, `motivo_zona_morta`
- **Catchment:** `pop_captacao`, `renda_per_capita_captacao` (None se `setores_df` ausente)
- **Cenário pedido:** `viabilidade` (`ViabilidadeResult` com `faturamento_mensal_steady`,
  `ebitda_mensal`, `margem_ebitda_pct`, `payback_meses`, `roic_anual`, `lucro_liquido_mensal`,
  `flag_viavel`); `aluguel_teto_calculado`; `alunos_breakeven`
- **Sensibilidade:** `grade_sensibilidade` (DataFrame com colunas `alunos`, `aluguel`,
  `fator_aluguel`, `margem_liq`, `viavel`, `payback` — shape `len(alunos_range) × len(aluguel_range_fator)`)
- **Guardrail:** `demanda_fonte = "premissa_explicita"` (sempre; a UI DEVE exibir isso)

### Modos degradados (o engine os suporta, a UI deve comunicá-los)
- `setores_df=None` → sem catchment, `flag_zona_morta=None`, `pop_captacao=None`
- `base_calibracao_df=None` → sem faixa p10/p50/p90, `n_comparaveis=None`

## DataFrames a injetar (lazy, com cache — padrão idêntico ao censo report)

| DataFrame | Fonte em disco | Como carregar | Cache key |
|---|---|---|---|
| `base_calibracao_df` | `data/staging/base_calibracao_multirede.parquet` | `pd.read_parquet(...)` com `@st.cache_data` | caminho fixo (sem UF) |
| `setores_df` | `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=N/` | `censo_geo_loader(uf, cod_municipio)` — já existe como `load_censo_geo_setores` em `streamlit_app.py` linha 334 | `(uf, cod_municipio)` |

- `base_calibracao_df` deve ser lida **uma vez** com `@st.cache_data` e passada injetada.
- `setores_df` segue o padrão de `render_relatorio_pontual_censitario`: recebe `censo_geo_loader`
  como callable + `censo_geo_dir: Path | None` para fallback via `resolve_cod_municipio_from_geo_dir`.
- Resolução de `(uf, cod_municipio)` a partir de `(lat, lng)`: usar `_resolve_censo_context` (já
  existe em `pages.py`, chamada na linha ~2552) — mesma lógica do censo report.

## Ponto de plugagem exato no dashboard

**Arquivo:** `src/motor_expansao/dashboard/pages.py`

**Onde adicionar o expander** (opção preferida do backlog):
```python
# Após linha ~2967 (após o expander "Relatorio Pontual Censitario"):
with st.expander(
    "Viabilidade do Imóvel (property-first)",
    expanded=effective_pin is not None,
):
    render_viabilidade_ponto(
        effective_pin,
        df,
        censo_geo_loader=censo_geo_loader,
        censo_geo_dir=censo_geo_dir,
        base_calibracao_df=base_calibracao_df,  # novo parâmetro a propagar
    )
```

**Assinatura proposta de `render_viabilidade_ponto`** (Planner pode ajustar UX):
```python
def render_viabilidade_ponto(
    search_pin: tuple[float, float] | None,
    df: pd.DataFrame,
    *,
    censo_geo_loader: Callable[[str, str | None], pd.DataFrame] | None = None,
    censo_geo_dir: Path | None = None,
    base_calibracao_df: pd.DataFrame | None = None,
) -> None
```

**`render_mapa_territorial` precisa receber `base_calibracao_df`** como novo parâmetro opcional e
propagá-lo internamente até o expander. A chamada em `streamlit_app.py` (linha ~528) deve passar
`base_calibracao_df` carregado com `@st.cache_data`. Nenhuma outra lógica de `render_mapa_territorial`
é alterada.

**Alternativa de nova aba:** adicionar `"Viabilidade do Imóvel"` à lista `DASHBOARD_TAB_LABELS`
(linha 441 de `pages.py`) e criar o `elif active_tab == "Viabilidade do Imóvel":` em
`streamlit_app.py`. Esta opção preserva o render lazy de abas (Bloco 5) de forma mais limpa, mas
aumenta de 4 para 5 abas — decisão de produto no gate humano.

## Escopo permitido
- Nova função `render_viabilidade_ponto` em `src/motor_expansao/dashboard/pages.py`
- Propagação de `base_calibracao_df` como novo parâmetro opcional de `render_mapa_territorial` (ou alternativa: aba nova)
- Ajuste em `streamlit_app.py`: carregar `base_calibracao_multirede.parquet` com `@st.cache_data` e passar ao render
- Inputs do formulário: `lat/lng` (campo numérico OU parser puro de link do Google Maps — string, sem geocoding ao vivo) + `m²` + `aluguel_pedido` + `demanda_premissa` (número explícito obrigatório) + toggle "usar p50 dos comparáveis" como atalho (preenche o campo `demanda_premissa` com `faixa_alunos_p50`, mas o número SEMPRE fica visível e editável pelo operador antes de submeter — nunca silencioso)
- Render dos resultados: cards de métricas (`alunos_breakeven`, `aluguel_teto_calculado`, `margem_ebitda_pct`, `payback_meses`, `roic_anual`); heatmap ou tabela de `grade_sensibilidade`; faixa p10/p50/p90; aviso de zona morta (`flag_zona_morta=True` → alerta visível); pop/renda do entorno; pin do imóvel no mapa pydeck (reusar componente existente); exibição explícita de `demanda_fonte = "premissa_explicita"`
- Carga lazy/cache por `(uf, cod_municipio)` para `setores_df`; `base_calibracao_df` em cache fixo
- Mensagem clara quando base geo não existe (padrão do censo report)
- Testes: teste que verifica que a UI NUNCA passa `demanda_premissa` derivada de lat/lng; smoke em `test_streamlit_app.py` cobrindo a nova função; teste de carga lazy

## Fora de escopo (invioláveis)
- Derivar `demanda_premissa` automaticamente de `lat`, `lng` ou de qualquer coluna do `df` M1/mercado — PROIBIDO; a UI não pode burlar o guardrail do engine
- Recalcular ou ler `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano curto prazo, artefatos oficiais do M1 (DEC-001, DEC-008, DEC-009)
- Geocoding de endereço ao vivo (converter texto → coordenadas via API externa)
- Quebrar otimizações de performance: carga lazy por UF (Bloco 4), render lazy de abas (Bloco 5), fonte de mapa enxuta (Bloco 6)
- Alterar `_resolve_censo_context`, `setor_censitario_intersecao_area_1p5km`, raio 1.5 km, método de interseção do censo
- Alterar artefatos oficiais: `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`, `top_oportunidades_resumo.csv`, `resumo_por_uf.csv`
- PostGIS, API ao vivo, geocoding externo, deploy no VPS
- Alterar `calcular_catchment_unidade`, `faixa_alunos_por_densidade`, `grade_sensibilidade` (engine é READ-ONLY)

## Arquivos que devem ser lidos
- `src/motor_expansao/dimensionamento/viabilidade_ponto.py` — contrato completo do engine
- `src/motor_expansao/dimensionamento/simulador.py` — campos de `ViabilidadeResult`
- `src/motor_expansao/dimensionamento/config.py` — defaults de `SIM_MENSALIDADE_BALCAO`, `RAIO_CATCHMENT_KM`
- `src/motor_expansao/dashboard/pages.py` linhas 441–470 — `DASHBOARD_TAB_LABELS` e `render_tab_selector`
- `src/motor_expansao/dashboard/pages.py` linhas 2525–2967 — padrão do censo report e ponto de plugagem exato
- `src/motor_expansao/dashboard/pages.py` linhas 2728–2755 — assinatura atual de `render_mapa_territorial`
- `src/motor_expansao/dashboard/data.py` linhas 143–179 — `read_censo_geo_partition`
- `streamlit_app.py` linhas 200–210 (`CENSO_GEO_DIR`) e linhas 527–542 (chamada de `render_mapa_territorial`)
- `data/staging/base_calibracao_multirede.parquet` — inspecionar colunas (`metragem`, `alunos_por_m2`) para confirmar compatibilidade com `faixa_alunos_por_densidade`

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` — adicionar `render_viabilidade_ponto`; adicionar `base_calibracao_df` a `render_mapa_territorial` e ao expander de plugagem
- `streamlit_app.py` — carregar `base_calibracao_multirede.parquet` com `@st.cache_data`; passar `base_calibracao_df` em `render_mapa_territorial`; (se aba nova) adicionar `elif active_tab` e atualizar `DASHBOARD_TAB_LABELS`
- `tests/integration/test_streamlit_app.py` — testes de smoke da nova função
- `tests/unit/dimensionamento/test_viabilidade_ponto_ui.py` (novo, se necessário) — testes de guardrail e render

## Arquivos que NÃO podem ser alterados
- `src/motor_expansao/dimensionamento/viabilidade_ponto.py` — engine READ-ONLY
- `src/motor_expansao/dimensionamento/simulador.py` — engine READ-ONLY
- `src/motor_expansao/dimensionamento/catchment_batch.py` — engine READ-ONLY
- `src/motor_expansao/pipelines/m1/` — qualquer arquivo
- `config.py` — parâmetros canônicos M1
- `data/staging/brasil_*.parquet`, `data/outputs/hexagonos_*.parquet` — artefatos oficiais
- `src/motor_expansao/censo/censo_point.py`, `censo_map.py`, `censo_report.py` — intocados neste bloco

## Critérios de aceite
1. `render_viabilidade_ponto` renderiza o resultado completo (cards + grade + faixa + mapa + zona morta) quando `search_pin` está presente e as bases estão disponíveis
2. A UI exibe sempre `demanda_fonte = "premissa_explicita"` — nunca omite
3. Teste automatizado confirma que `demanda_premissa` passada ao engine é sempre o valor digitado pelo operador, nunca derivado de `lat`/`lng` ou colunas do `df`
4. Carga de `setores_df` é lazy e cacheada por `(uf, cod_municipio)` (mesmo padrão do censo report); carga de `base_calibracao_df` é cacheada uma vez
5. Quando `setores_df` não existe para o município: mensagem informativa clara, sem exceção
6. Quando `base_calibracao_df` é None ou vazio: faixa p10/p50/p90 exibe "n/d" sem travar
7. Performance: `render_mapa_territorial` não regride — nova chamada só executa dentro do expander/aba ativa (render lazy preservado)
8. `pytest -q` (suite completa) verde + ruff + mypy limpos
9. `test_streamlit_app.py` cobre import e smoke da nova função
10. UX validada por Felipe/Vini antes do Builder iniciar (gate humano obrigatório)
11. Score M1 (`score_priorizacao`, pesos, artefatos) inalterado — nenhum artefato oficial regravado

## Criticidade classificada
**Alta** — toca o dashboard de produção; READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009); guardrail de demanda como premissa explícita é inviolável.

## Esteira recomendada
1. Planner (design UX detalhado: layout inputs, cards, heatmap sensibilidade, escolha expander vs aba, assinatura final)
2. [APROVAÇÃO HUMANA — Felipe/Vini] (validar UX antes de qualquer código)
3. Builder (implementação em `pages.py` + `streamlit_app.py` + testes)
4. QA (suite completa em Opus 4.8; guardrail anti-geográfico + perf + mypy)

## Riscos identificados
- **Médio — regressão de performance:** `render_mapa_territorial` já é pesada; `base_calibracao_df` deve ser carregado fora da função (no `main()` de `streamlit_app.py`, com `@st.cache_data`), não relido a cada rerun. O Builder deve garantir que o carregamento só ocorre uma vez.
- **Médio — UX do toggle "usar p50":** o toggle deve preencher o campo `demanda_premissa` como valor visível e editável, nunca silencioso; caso contrário viola DEC-009. O Planner deve especificar o comportamento exato (ex.: preenche o `st.number_input`, operador confirma antes de rodar).
- **Baixo — `_resolve_censo_context` pode retornar None:** mesmo comportamento do censo report; comunicar claramente ao operador.
- **Baixo — `base_calibracao_multirede.parquet` sem colunas `metragem`/`alunos_por_m2`:** o engine degrada graciosamente (`n_comparaveis=0`); a UI deve tratar e exibir "n/d".
- **Baixo — colisão de session_state keys:** o Builder deve usar prefixo distinto (ex.: `viabilidade_ponto_*`) para não colidir com keys do censo report ou do mapa.

## Guardrails ativos
- **§5 (CLAUDE.md):** visualizações não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano ou artefatos oficiais do M1.
- **DEC-009:** a demanda entra como PREMISSA EXPLÍCITA (input do operador), NUNCA prevista pela geografia. Proibido reintroduzir "20% fixo" ou regressão geográfica como preditor.
- **DEC-001:** `renda=0.40`/`pop=0.60`, `score_priorizacao` e artefatos M1: INALTERADOS.
- **DEC-008:** epic BLK-DIM é camada paralela, READ-ONLY sobre o M1.
- **§2 (CLAUDE.md):** "Não criar dependência de API ao vivo no dashboard de produção." (parser de link Maps é puro — sem chamada de rede.)
- **Blocos 4–6 (performance):** carga lazy por UF, render lazy de abas, fonte de mapa enxuta — PRESERVADOS.
