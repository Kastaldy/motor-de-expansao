# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-UI-04** — Destaque do seletor de telas: aba ATIVA ciano sólido, maior espaçamento entre botões, fundos dos botões distintos dos cartões de valores.

## Objetivo
Refinar exclusivamente o bloco CSS do `stSegmentedControl` em `inject_styles()` (`pages.py`) para que o seletor de abas seja visualmente distinto e legível: aba ativa com ciano sólido (decisão capturada), botões com espaçamento maior, fundos dos botões distintos dos cartões ao redor.

## Decisão de produto capturada (inviolável)
- **Aba ATIVA = ciano SÓLIDO preenchido**: fundo `#19B7FF` (= `brand_alt`) cheio, texto escuro (ex.: `#0A0C18` ou `#0F172A`), bold. Não usar `rgba(...)` com transparência para a ativa.
- As 3 mudanças são CSS-only; `render_tab_selector` e toda a lógica do Bloco 5 são INTOCÁVEIS.

## Diagnóstico ancorando file:line reais

### Fundos dos cartões de valores (referência de camuflagem)
| Seletor | Arquivo:linha | Valor atual |
|---|---|---|
| `[data-testid="stMetric"]` | `pages.py:159-160` | `linear-gradient(180deg, rgba(18,23,42,0.96) 0%, rgba(14,19,36,0.96) 100%)` |
| `.section-card` | `pages.py:214-215` | `linear-gradient(180deg, rgba(18,23,42,0.96) 0%, rgba(14,19,36,0.96) 100%)` |
| `.model-card` | `pages.py:236-237` | `linear-gradient(180deg, rgba(18,23,42,0.96) 0%, rgba(14,19,36,0.96) 100%)` |

### Bloco CSS do stSegmentedControl atual (pages.py:304-328)
| Seletor | Linha(s) | Valor atual | Problema |
|---|---|---|---|
| `[data-testid="stSegmentedControl"] button` (inativo) | 304-314 | `background: rgba(18,23,42,0.92)` | Quase idêntico aos cartões → camuflagem |
| `[data-testid="stSegmentedControl"] button[aria-checked="true"]` (ativo) | 320-328 | `background: rgba(25,183,255,0.22)` (fraco) | Pouco contraste vs inativos |
| Container para `gap` (espaçamento) | ausente | nenhum `gap` no container `stSegmentedControl` | Botões sem espaçamento entre si |

### `render_tab_selector` — INTOCÁVEL
- Localização: `pages.py:435-459`
- Contém `st.segmented_control` + lógica `session_state` do Bloco 5 (render lazy de abas).
- **Nenhuma linha desta função pode ser alterada.**

### COLORS relevante
- `COLORS["brand_alt"]` = `"#19B7FF"` → `rgb(25,183,255)` (`constants.py:280`)
- `COLORS["bg"]` = `"#0A0C18"` — candidato para cor de texto escuro na ativa

## Escopo permitido
- `src/motor_expansao/dashboard/pages.py` — **somente o bloco CSS do `stSegmentedControl` dentro de `inject_styles()`** (~linhas 304-328); podendo adicionar uma regra de container acima (ex.: `div[data-testid="stSegmentedControl"]` para `gap`).
- `tests/integration/test_streamlit_app.py` — somente se necessário para atualizar/estender `test_inject_styles_cobre_componentes_baseweb` (ex.: adicionar assert de `background: #19B7FF` ou `background-color: #19B7FF` para a ativa sólida).

## Fora de escopo
- `render_tab_selector` (`pages.py:435-459`) — lógica Bloco 5, byte-idêntico; **INTOCÁVEL**.
- Qualquer outro seletor CSS além do bloco `stSegmentedControl` em `inject_styles()`.
- Recalcular `score_priorizacao`, `hex_score_estrutural`, qualquer artefato M1 ou parquet oficial.
- Tocar `components.py`, `constants.py`, `data.py`, pipelines, `streamlit_app.py` (app principal).
- Criar dependência de API ao vivo.
- Alterar os paths pré-sujos: `data/outputs/setores_censitarios_2022_geo/_metadata.json` e `data/reports/relatorio_pontual_censitario_base_geo.md`.

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/pages.py` (bloco `inject_styles`, linhas ~132-360; e `render_tab_selector`, linhas ~435-459)
- `src/motor_expansao/dashboard/constants.py` (dict `COLORS`, linhas ~270-287)
- `tests/integration/test_streamlit_app.py` (teste `test_inject_styles_cobre_componentes_baseweb`, linhas ~4466-4481)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` — SÓ o bloco CSS `stSegmentedControl` em `inject_styles()` (~304-328 + eventual regra de container acima)
- `tests/integration/test_streamlit_app.py` — somente `test_inject_styles_cobre_componentes_baseweb`, se necessário

## Critérios de aceite
1. **Ativa ciano sólido:** `button[aria-checked="true"]` e `button[aria-selected="true"]` têm `background: #19B7FF` (ou `rgb(25,183,255)`) sólido (sem `rgba` com transparência), texto escuro legível (ex.: `#0A0C18`), `font-weight: 700`.
2. **Espaçamento:** existe regra CSS `gap` no container do `stSegmentedControl` (ex.: `div[data-testid="stSegmentedControl"]` ou seletor filho `> div`) com valor > 0 (sugestão: `0.4rem`–`0.6rem`).
3. **Botões inativos distintos:** `background` dos botões inativos é visivelmente diferente de `rgba(18,23,42,0.96)` dos cartões — ex.: slate mais claro como `rgba(30,38,65,0.88)` ou `rgba(22,30,58,0.80)` — e a borda visível permanece.
4. **Seletores preservados:** `stSegmentedControl`, `aria-checked="true"`, `aria-selected="true"` continuam presentes no CSS (o teste `test_inject_styles_cobre_componentes_baseweb` passa sem modificações ou com adições compatíveis).
5. **Contraste verificado:** texto da aba ativa escuro sobre ciano `#19B7FF` (razão de contraste ≥ 4.5:1 visualmente; ex.: `#0A0C18` sobre `#19B7FF` é ~7:1).
6. **`render_tab_selector` byte-idêntico:** zero diferença em `pages.py` nas linhas 435-459.
7. **Suíte alvo verde:** `pytest tests/integration/test_streamlit_app.py -q` passa sem regressão.
8. **M1 intocado:** nenhum score, peso, fórmula, artefato M1 ou parquet oficial alterado.

## Criticidade classificada
**Média** — CSS localizado em `inject_styles()`; sem gate humano; READ-ONLY sobre o M1; Bloco 5 intocável.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → Builder (sonnet) → QA (opus 4.8)

## Tiering de modelo (Passo 4 — Média)
- Block Orchestrator: sonnet (concluído)
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Riscos identificados
1. **Seletor de container para `gap`:** o `st.segmented_control` pode renderizar botões em `div[data-testid="stSegmentedControl"] > div` (wrapper flex interno) ou diretamente em `[data-baseweb="button-group"]`. O Planner deve confirmar o seletor correto (estender os já presentes no bloco CSS, ex.: `[data-baseweb="button-group"]`). Se o seletor não casar, o gap simplesmente não aplica (sem regressão visual).
2. **Seletor de ativa não casando:** caso a versão do Streamlit use `aria-pressed` em vez de `aria-checked`/`aria-selected`, o ciano sólido pode não aparecer. Mitigação: manter os 3 seletores atuais e adicionar `[data-baseweb="button-group"] button[aria-pressed="true"]` como fallback sem remover nenhum existente.
3. **Contraste texto ativo:** texto claro (`#F3F7FF`) sobre ciano sólido `#19B7FF` tem contraste insuficiente (~1.5:1). **Obrigatório usar texto escuro** (ex.: `#0A0C18`, `#0F172A` ou `#1a1a2e`) na aba ativa.
4. **`test_inject_styles_cobre_componentes_baseweb` já verifica** `aria-checked="true"` OR `aria-selected="true"` — se a implementação mantiver esses seletores (obrigatório), o teste passa sem alteração. Só precisará de update se o Builder quiser adicionar assert do valor de background sólido.
5. **Paths pré-sujos:** `_metadata.json` e `relatorio_pontual_censitario_base_geo.md` estão modificados no working tree; não podem ser commitados neste ciclo.

## Guardrails ativos
- Guardrail permanente (CLAUDE.md §5): visualizações, análise radial e interações de mapa **não podem** recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- Bloco 5 (CLAUDE.md §4): `render_tab_selector` e `st.segmented_control`/`session_state` são lógica intocável; só o bloco CSS em `inject_styles()` pode mudar.
- READ-ONLY M1: `renda=0.40`/`pop=0.60`, `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais — INALTERADOS.
- Paths pré-sujos não devem ser commitados: `data/outputs/setores_censitarios_2022_geo/_metadata.json`, `data/reports/relatorio_pontual_censitario_base_geo.md`.
