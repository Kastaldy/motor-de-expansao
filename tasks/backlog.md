# Backlog

## Priorização atual

Próximo ciclo recomendado: **bugs de produção do dashboard** (BLK-FIX-03..06 abaixo) —
reportados por Felipe em 2026-06-01; **topo de prioridade**. Atenção: BLK-FIX-06 (hexes do
litoral) é **Crítica + DEC** (toca a base do M1 e regenera artefatos oficiais).

> Blocos BLK-OPS-02/03/04, BLK-ARCH-01 e BLK-SCORE-01/02/03 originados do "Programa de
> Melhorias — Referência do Master Orchestrator" (PRD.md), migrados em 2026-05-29.
> Mapa de dependências e ordem recomendada do programa: ver §3 do PRD.md original.
> Ordem deste backlog: arquitetura (BLK-ARCH-01) à frente da trilha de score (BLK-SCORE-*).

---

## Bugs de produção do dashboard — TOPO DE PRIORIDADE (2026-06-01)

> Reportados por Felipe a partir do dashboard em produção (`dashboard.ultra-expansao.tech`).
> Cada bug é um bloco BLK-FIX próprio. Nenhum toca M1/score, **exceto BLK-FIX-06** (litoral),
> que altera a base de hexes do M1 e regenera artefatos oficiais → **Crítica + DEC**.
> Causas-raiz abaixo são **hipóteses** ancoradas no código (file:line) a confirmar pelo Planner.

- BLK-FIX-03 (concluído 2026-06-01) — ver tasks/completed.md

### BLK-FIX-03-FU1 — Caption "capped" do Mapa Territorial pode dar falso positivo (follow-up opcional)

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (cosmético de UX; não toca M1/score) |
| **Prioridade** | **Baixa** |
| **Esteira** | Block Orchestrator → Builder |
| **Depende de** | BLK-FIX-03 (concluído) |
| **Status** | Pendente |
| **Origem** | Ressalva do QA no fechamento do BLK-FIX-03 (2026-06-01) |

**Contexto / gap:** após o BLK-FIX-03, o gatilho do caption "capped" em
`dashboard/pages.py` (`render_mapa_pydeck_fragment`) infere o corte por heurística
`capped = n_points >= MAP_POINT_LIMIT_LARGE` (18.000). Logo um recorte com **18.000–34.999 hexes
distintos** — que é renderizado **sem corte** (cap cheio de 35k não foi atingido) — exibiria
falsamente a mensagem "amostrado / recorte maior que o limite". É um falso positivo cosmético; o
render e os dados estão corretos.

**Objetivo:** o caption só indica "amostrado" quando houve corte de fato.

**Escopo permitido:** propagar o cap efetivo aplicado (ou o nº de candidatos pré-cap) do builder ao
fragmento, em vez de inferir por `n_points`, para que `capped`/`effective_cap` reflitam o corte real.
Sem tocar M1/score/regra de cor.

**Fora de escopo:** M1/artefatos; mudar o cap dinâmico do BLK-FIX-03.

**Arquivos prováveis:** `dashboard/components.py` (retorno dos builders quantitativos),
`dashboard/pages.py` (`render_mapa_pydeck_fragment`/`render_mapa_territorial`), testes do caption.

**Critérios de aceite:** recorte de 18k–35k hexes não exibe o caption "amostrado"; recorte que satura
(≥35k) continua exibindo o caption com o cap efetivo (18.000); suíte verde; zero M1.

**Risco:** baixo (UX/caption).

---

### BLK-FIX-04 — Seleção de hex por clique não funciona no Mapa Territorial

| Campo | Valor |
|---|---|
| **Criticidade** | **Média-Alta** (interação central da aba quebrada; não toca M1/score) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |
| **Origem** | Felipe, 2026-06-01 |

**Contexto / gap:** clicar num hexágono no Mapa Territorial não dispara a seleção / Análise Pontual.
O fluxo usa `st.pydeck_chart(..., on_select="rerun")` e `_extract_click_coord_from_selection`
(`pages.py:2294`), que tenta extrair **lat/lng** do evento de seleção; mas o `H3HexagonLayer` do pydeck
não emite lat/lng no objeto selecionado (retorna propriedades do hex / `hex_id`) → extração falha →
`click_coord` fica `None` → `lookup_hex_by_coord` (`data.py:1072`) não roda. CLAUDE.md §5 registra que
o clique usa o centroide do hex via pydeck; **confirmar se o contrato do evento mudou** com a versão de
Streamlit/pydeck.

**Objetivo:** restaurar captura de clique → seleção de hex → Análise Pontual, mantendo o fallback de
`lat,lng` na sidebar.

**Escopo permitido:** corrigir a extração para ler o identificador efetivamente retornado pelo evento
(índice / `hex_id` / objeto) em vez de assumir lat/lng; mapear de volta ao hex no `df`; garantir
`pickable=True` na camada. Sem recalcular score.

**Fora de escopo:** M1/score/artefatos; trocar o componente de mapa (decisão do Bloco 12 mantém pydeck).

**Arquivos prováveis:** `dashboard/pages.py` (`_extract_click_coord_from_selection≈2294`, render do Mapa
Territorial, `st.pydeck_chart`), `dashboard/components.py` (`build_map_figure` / `pickable` da camada),
`dashboard/data.py` (`lookup_hex_by_coord≈1072`).

**Critérios de aceite:** clique num hex seleciona e dispara a Análise Pontual (repro manual + teste do
parser de evento com payload representativo); fallback `lat,lng` preservado; zero M1; suíte verde.

**Risco:** baixo-médio (depende do contrato de evento do pydeck/Streamlit).

---

### BLK-FIX-05 — Cores da UI ficam claras em tema claro do SO (botões de aba e caixas de filtro)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (legibilidade/usabilidade; não toca M1/score) |
| **Prioridade** | **Alta** |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | — |
| **Status** | Pendente |
| **Origem** | Felipe, 2026-06-01 |

**Contexto / gap:** em máquinas com **tema claro** do SO/navegador, os botões das abas
(`render_tab_selector` / `st.segmented_control`) e as caixas de seleção dos filtros (selectbox/
multiselect) ficam **brancos**, perdendo o fundo escuro do design. Causa provável: `.streamlit/config.toml`
**não tem bloco `[theme]`** (confirmado — só `[server]`/`[browser]`/`[client]`), então o app segue o
tema do SO (auto), enquanto o CSS de `inject_styles` (`pages.py:121`) assume fundo escuro → em tema
claro, componentes baseweb (`[data-baseweb="tab"]`, `[data-baseweb="select"]`) caem no estilo claro do
Streamlit e/ou o CSS escuro não cobre todos os estados.

**Objetivo:** UI mantém o tema escuro consistente independentemente do tema do SO/navegador.

**Escopo permitido:** fixar o tema escuro no `.streamlit/config.toml` (`[theme] base="dark"` + paleta)
e/ou endurecer o CSS de `inject_styles` para garantir contraste dos seletores de aba e filtros;
verificar em tema claro **e** escuro do SO.

**Fora de escopo:** M1/score; redesenho de identidade visual; mexer nas faixas de cor de score
(`RESIDUAL_SCORE_BANDS` / `score_band_to_color`).

**Arquivos prováveis:** `.streamlit/config.toml` (sem `[theme]`), `dashboard/pages.py`
(`inject_styles≈121`, `render_tab_selector≈359`), `dashboard/constants.py` (`COLORS`).

**Critérios de aceite:** abas e caixas de filtro mantêm fundo escuro/contraste em SO tema claro
(evidência visual antes/depois) e seguem ok no escuro; zero M1; suíte verde.

**Risco:** baixo (CSS/config).

---

### BLK-FIX-06 — Hexágonos do litoral recortados pelo pipeline ⚠ (toca base M1 → Crítica + DEC)

| Campo | Valor |
|---|---|
| **Criticidade** | **CRÍTICA** — a correção altera a base de hexes do M1 e **regenera artefatos oficiais** → aprovação obrigatória + **DEC** (CLAUDE.md §2 e §8) |
| **Prioridade** | **Alta** (cobertura de mercado costeiro), **mas bloqueada por decisão humana** |
| **Esteira** | Block Orchestrator → Planner → **[REVISÃO/APROVAÇÃO HUMANA + DEC]** → Builder → QA |
| **Depende de** | decisão humana (DEC) antes de qualquer execução |
| **Status** | Pendente (bloqueado em decisão) |
| **Origem** | Felipe, 2026-06-01 (litoral: Praia Grande, Rio de Janeiro etc. sem hexes; print de exemplo) |

**Contexto / gap:** hexágonos sobre faixas litorâneas povoadas (Praia Grande, litoral do RJ, etc.)
**não aparecem** no mapa. Causa provável: `base_h3_brasil.py` filtra hexes **só por centróide dentro do
polígono do Brasil** (`shapely.intersects(brasil_geom, chunk_centroids)`, ~linha 189; remoção logada
como "centroide em mar/fronteira", ~linha 361). Hexes costeiros cujo centróide cai na água — mesmo com
a maior parte sobre terra povoada — são descartados **na geração da base, antes de qualquer score**.

⚠ **Atenção de criticidade:** corrigir isso **adiciona hexes ao universo do M1**, mudando contagens,
**percentis nacionais** e, portanto, **regenera os artefatos oficiais** (`brasil_estrutural`,
`brasil_priorizados`, `hexagonos_*`). Pela regra §2 do CLAUDE.md isso é **ALTERAÇÃO de artefato M1 →
Crítica (aprovação obrigatória + DEC)**. **Não é** um fix de dashboard trivial e **não pode** ser
executado pelo Builder sem DEC registrada.

**Objetivo:** incluir hexes litorâneos que sobreponham terra/população real, sem distorcer o M1,
mediante decisão registrada.

**Escopo permitido (somente APÓS DEC):** trocar o critério de centróide por **interseção do polígono do
hex com o polígono do Brasil** (ou critério híbrido centróide-ou-interseção com limiar de área);
**quantificar** quantos hexes entram e o impacto em percentis/score ANTES de aplicar; regenerar
artefatos de forma auditável e reprodutível.

**Fora de escopo (sem DEC):** qualquer regeneração de artefato M1; mudar pesos/fórmula
(renda=0.40/pop=0.60); parâmetros canônicos.

**Arquivos prováveis:** `src/motor_expansao/pipelines/m1/base_h3_brasil.py` (filtro de centróide
~181-194, log ~356-364), `config.py` (`M1_POP_MINIMA_PROXY`), artefatos M1 (regeneração controlada).

**Critérios de aceite:** critério geométrico revisado cobre o litoral povoado (repro: Praia Grande/RJ
voltam a aparecer); **impacto no M1 quantificado e aprovado em DEC**; artefatos regenerados de forma
reprodutível; testes do pipeline verdes.

**Risco:** **alto** (mexe na base do M1 e em artefatos oficiais; exige DEC e validação de não-regressão
do score). Mitigação: decisão humana + DEC antes de qualquer execução; medir delta de hexes/percentis.

---

- BLK-FIX-07 (concluído 2026-06-01) — ver tasks/completed.md

### BLK-FIX-07-B — Clustering server-side por recorte das IconLayers (Fase B, refino de UX)

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (refino de UX da camada de pins; não toca M1/score) |
| **Prioridade** | **Média** (o bound de 40k já está garantido pela Fase A / cap duro) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | BLK-FIX-07 (Fase A, concluído 2026-06-01) |
| **Status** | Pendente |
| **Origem** | Decisão de faseamento do Planner no BLK-FIX-07 (2026-06-01); recomendado pelo QA |

**Contexto / gap:** o BLK-FIX-07 (Fase A) já eliminou o OOM e garantiu o bound de ~40k via cap de
segurança duro (`COMPETITOR_PIN_LIMIT=6000`) + atlas de ícones + payload enxuto. Quando o recorte excede
o cap, a Fase A **corta** pins (com caption "amostrado" honesta). A Fase B substitui "cortar" por
"mostrar densidade": agregar pins em clusters por grid/hex na visão de UF inteira e expandir para pins
individuais com logo quando o recorte é município/filtro.

**Objetivo:** preservar a leitura de densidade concorrencial em recortes grandes (UF inteira) sem cortar
pins arbitrariamente, mantendo o bound de payload.

**Escopo permitido:** clustering server-side por recorte com gate **determinístico por recorte/filtro
selecionado** (NÃO por zoom — `st.pydeck_chart` não round-trippa zoom/pan ao servidor): UF inteira sem
filtro ⇒ clusters agregados (contagem por grid/hex); município/filtro selecionado ⇒ pins individuais com
logo (caminho atual da Fase A). Tooltip de cluster (contagem por rede/total). Reusar o atlas e o payload
enxuto da Fase A.

**Fora de escopo:** M1/score/artefatos/universo de hexes; trocar o componente de mapa (Bloco 12 mantém
`st.pydeck_chart`); culling por zoom client-side ao vivo (exigiria componente React custom); refazer o cap
de hexes do BLK-FIX-03 ou o atlas/cap da Fase A; mexer na regra de cor de score.

**Arquivos prováveis:** `dashboard/components.py` (`_build_competitor_icon_layer`, builders de mapa, novo
helper de clustering), `dashboard/constants.py` (limites de cluster/grid), `dashboard/pages.py` (gate por
recorte + caption de cluster), `tests/integration/test_streamlit_app.py`.

**Critérios de aceite:** UF inteira renderiza clusters agregados (sem cortar pins) com payload ≤ limite;
município/filtro renderiza pins individuais com logo (Fase A); gate determinístico testado; logos e
`pickable` preservados; zero M1; suíte verde.

**Risco:** médio (novo modelo de dados/UX de cluster). Mitigação: bound já garantido pela Fase A; Fase B é
melhoria incremental, não correção de bug.

---

## Tarefas pendentes

- BLK-OPS-06 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-07 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-PRD-01 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02b (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-08 (concluído 2026-05-29) — ver tasks/completed.md

---

- BLK-OPS-03 (concluído 2026-05-30) — ver tasks/completed.md


---

- BLK-OPS-04 (concluído 2026-05-30) — ver tasks/completed.md



- BLK-FIX-01 (concluído 2026-05-30) — ver tasks/completed.md



- BLK-FIX-02 (concluído 2026-05-30) — ver tasks/completed.md


---

- BLK-SCORE-01 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-01a (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-02 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-03 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-04 (concluído 2026-05-31) — ver tasks/completed.md


---

### BLK-SCORE-05 — Viabilidade de proxy exógeno de demanda (pré-requisito de modelagem)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (LEITURA/ANÁLISE + engenharia de dados; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-SCORE-02**, **BLK-SCORE-03 (DEC-001)**, **BLK-SCORE-04** |
| **Status** | Pendente |
| **Origem** | pergunta do usuário "dá para modelar demanda potencial por hex?" (2026-05-31) |

**Contexto / por que existe:** BLK-SCORE-02/04 mostraram que NÃO é possível, hoje, treinar um modelo
preditivo confiável de demanda. Três bloqueios estruturais: (1) **viés de seleção** — o único
desfecho (`alunos_recorrentes`) só existe onde JÁ há unidade; não há observação de demanda em hexes
vazios (sem contrafactual); (2) **alvo enviesado/ruidoso** — desfecho pós-seleção e pós-maturação,
sem `maturacao_status` real, heterogêneo entre redes; (3) **sinal exógeno ≈ nulo** — features de
mercado/competição com IC cruzando zero, OLS conjunto R²≈0.034; o sinal que sobra é endógeno (rede
própria). Conclusão: o gargalo é de DADOS, não de algoritmo. Este bloco é o **pré-requisito de
engenharia de dados ANTES de qualquer modelagem** — NÃO é um bloco de ML.

**Objetivo:** avaliar, read-only, a VIABILIDADE de obter (a) um sinal de **maturação** por unidade
(data de abertura ou proxy auditável) e (b) ao menos um **proxy de demanda EXÓGENO** — independente
da existência de academia no hex. Entregar um diagnóstico de disponibilidade/qualidade de fontes +
recomendação GO/NO-GO para um futuro bloco de modelagem, SEM construir modelo nem alterar score.

**Escopo permitido (read-only, diagnóstico):**
- Inventariar fontes candidatas de demanda exógena e checar cobertura/granularidade por hex/município:
  - **Penetração Wellhub/Gympass** (já há `sinal_wellhub`, `n_parcerias_wellhub` no dataset de
    validação — medir cobertura e se é exógeno ou colado a unidades existentes);
  - dados de **mobilidade/fluxo** ou **busca/intenção** (avaliar se há fonte acessível offline/legal,
    sem criar dependência de API ao vivo — guardrail do projeto);
  - sinais demográfico-comportamentais já no censo/IBGE não usados (faixa etária, vínculo formal,
    renda do trabalho) que correlacionem com propensão a academia.
- Avaliar viabilidade de **maturação**: existe data de abertura por unidade (Ultra real; concorrentes
  via mapeamento)? Que proxy auditável (ex.: primeira aparição em snapshot) seria aceitável?
- Estimar, com o que houver, se algum proxy exógeno tem correlação não-trivial com `alunos_recorrentes`
  CONTROLANDO maturação (reusar `analysis/score_backtest.py`/`feature_backtest_mercado.py`).
- Produzir relatório `data/analysis/viabilidade_demanda.md` (gitignored) com: matriz de fontes ×
  (cobertura, granularidade, exógena S/N, custo/risco de obtenção), achado de correlação controlada
  (se viável), e **recomendação GO/NO-GO** para um eventual `BLK-SCORE-06 — modelo de demanda`.

**Fora de escopo (invioláveis):**
- Construir/treinar qualquer modelo preditivo (isso seria o BLK-SCORE-06, só com GO + seu gate).
- Qualquer escrita/recálculo de M1 (`scoring.py`/`constants.py`/pesos/artefatos) — DEC-001 vigente.
- Criar dependência de API ao vivo no dashboard de produção (guardrail do CLAUDE.md).
- Inventar proxy de maturação/idade sem base auditável (lição do BLK-SCORE-02 §5).
- Saída fora de `data/analysis/`; qualquer PII (`nome_unidade`) no relatório.

**Arquivos a ler:** `data/analysis/relatorio_backtest.md`, `data/analysis/relatorio_backtest_mercado.md`,
`data/analysis/dataset_validacao.parquet` (colunas `sinal_wellhub`/`n_parcerias_wellhub`/`maturacao_status`),
`CLAUDE.md` §8 (DEC-001) e §4 (camadas), `analysis/feature_backtest_mercado.py` (reuso).
**Arquivos a alterar (read-only sobre M1):** novo script de diagnóstico em `analysis/` + testes
sintéticos; relatório em `data/analysis/` (gitignored). NENHUM artefato M1.

**Critérios de aceite:**
- Relatório `data/analysis/viabilidade_demanda.md` com matriz de fontes + veredito GO/NO-GO fundamentado.
- Diagnóstico explícito de maturação (disponível? proxy aceitável?) e de pelo menos 1 proxy exógeno.
- Se houver correlação controlada, reportada com incerteza (IC, N, confounds); sem forçar significância.
- ZERO escrita em M1/artefatos oficiais; ZERO PII; reprodutível (seed fixo; script versionado).

**Guardrails específicos:** READ-ONLY sobre M1; diagnóstico de viabilidade, NÃO modelagem; sem
dependência de API ao vivo; alimenta a decisão sobre os gates G1/G2/+contrafactual da DEC-001.

**Risco:** baixo (read-only). O valor é evitar investir em ML sobre dados que não identificam demanda;
o entregável é um GO/NO-GO honesto, não um modelo.

---

- BLK-OPS-11 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SEC-01 (concluído 2026-06-01) — ver tasks/completed.md


---

### BLK-SEC-02 — Varredura de vulnerabilidades (deps + imagem) e gitleaks como gate de CI

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (supply-chain; não toca M1/score) |
| **Prioridade** | **Média-Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-OPS-11** (deps pinadas) e idealmente **BLK-SEC-01** |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 |

**Contexto / gap:** não há varredura automatizada de vulnerabilidades de dependências nem da imagem
de produção; o `gitleaks` (com `.gitleaks.toml`/`.gitleaksignore` do BLK-OPS-01) existe mas **não roda
como gate no CI**. Combinado com deps não-pinadas (BLK-OPS-11), o risco de supply-chain é real.

**Objetivo:** detectar dependências/imagens vulneráveis e segredos vazados ANTES do merge/deploy.

**Escopo permitido:**
- `pip-audit` (ou Dependabot/`safety`) sobre as deps pinadas, como step do CI.
- Scan da imagem GHCR (Trivy/Grype) no pipeline de publish.
- `gitleaks` como **step bloqueante** do CI (reusa a config existente do BLK-OPS-01).
- Definir política de severidade (o que bloqueia vs. o que só alerta) para evitar CI ruidoso.
- **Pinar as GitHub Actions por SHA** (hoje usam tags móveis, ex.: `actions/checkout@v5`,
  `actions/setup-python@v6`) — endurece a supply-chain do próprio pipeline de CI/CD.
- **Resolver de uma vez o aviso de Node 20 nas `docker/*-action`** (AUTORIZADO explicitamente por
  Felipe em 2026-06-01): o BLK-OPS-08 (concluído 2026-05-29) subiu `actions/checkout@v4→v5` e
  `actions/setup-python@v5→v6` (zerou o aviso no job `test`), mas **deixou** `docker/login-action@v3`,
  `docker/metadata-action@v5`, `docker/setup-buildx-action@v3` e `docker/build-push-action@v6` (job
  `publish` de `ci.yml`), que **ainda rodam em Node 20** — aviso de descontinuação persiste no `publish`
  (GitHub força Node 24 em 16-jun-2026). Ao pinar por SHA, escolher SHAs de versões dessas actions que
  já rodem em **Node 24**, eliminando o aviso de vez. Validar com um run verde do `publish` sem o aviso.

**Fora de escopo:** remediar toda CVE histórica de uma vez (priorizar por severidade); assinatura de
imagem (cosign) — follow-up.

**Arquivos prováveis:** `.github/workflows/ci.yml` (jobs `test`/`publish`/`build-sanity` —
o antigo `docker-publish.yml` foi consolidado em `ci.yml` no BLK-SEC-01), `pyproject.toml`/lock,
`.gitleaks.toml`.

**Critérios de aceite:**
- CI roda `pip-audit` + `gitleaks` (bloqueantes por severidade definida) e scan de imagem no publish.
- Um segredo de teste plantado é pego pelo gitleaks (prova do gate); removido depois.
- Política de severidade documentada; zero mudança em M1/artefatos.

**Risco:** baixo-médio (ferramental/CI). Cuidado para não tornar o CI instável por CVEs de baixa
severidade — calibrar o gate.

---

### BLK-SEC-03 — Hardening do VPS (firewall, fail2ban, updates, SSH, 2FA)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (exposição do servidor de produção) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 (acesso root SSH; sem hardening documentado) |

**Contexto / gap:** o `docs/infra_producao.md` mostra acesso como `root` via SSH e atualização de
sistema **manual mensal**; não há menção a firewall (ufw), fail2ban, `unattended-upgrades`, política de
SSH (desabilitar login por senha / limitar root) nem 2FA obrigatório no Authelia (hoje "opcional").

**Objetivo:** reduzir a superfície de ataque do VPS de produção sem quebrar o deploy atual.

**Escopo permitido (cada passo via MCP com confirmação individual — guardrail do projeto):**
- `ufw` liberando só 22/80/443; `fail2ban` no SSH; `unattended-upgrades` para patches de segurança.
- SSH: desabilitar autenticação por senha (manter chave), avaliar usuário não-root para operação.
- Authelia: avaliar **forçar 2FA** para o grupo `ultra_team`.
- **Revisão de acesso (least-privilege):** auditar quem está no `ultra_team` em
  `authelia/users_database.yml`, remover acessos obsoletos e definir processo de offboarding
  (revogar usuário ao sair). Documentar a periodicidade da revisão.
- Documentar tudo em `docs/infra_producao.md` (seção de hardening) com rollback de cada item.

**Fora de escopo:** trocar provedor/arquitetura; mudar M1/dashboard.

**Critérios de aceite:**
- Firewall ativo (regras mínimas), fail2ban e unattended-upgrades rodando; SSH sem senha.
- Dashboard e deploy continuam funcionando (smoke + login OK após cada mudança).
- Cada alteração no VPS feita com confirmação individual; documentada com rollback.

**Risco:** médio-alto (mexer em SSH/firewall pode trancar o acesso). Mitigação: alterar um item por vez,
manter sessão aberta de teste, ter rollback pronto ANTES de aplicar regras de SSH/ufw.

---

### BLK-SEC-04 — Backup automatizado dos dados de produção (parquets) + restore testado

| Campo | Valor |
|---|---|
| **Criticidade** | **Média** (continuidade de dados; não toca M1/score) |
| **Prioridade** | **Média** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 (BLK-OPS-01 cobre segredos, não dados) |

**Contexto / gap:** o BLK-OPS-01 entregou backup/DR dos **segredos**, mas os **dados** de produção
(`/opt/motor-expansao/data/outputs/`, ~1.6 GB de parquets do M1) hoje só têm "manter cópia local na
máquina de dev" como backup — manual e frágil. Não há snapshot periódico nem restore testado.

**Objetivo:** garantir recuperação dos parquets de produção após perda/corrupção, com restore provado.

**Escopo permitido:**
- Definir destino de backup (snapshot do provedor, bucket S3-compatível, ou cópia versionada off-box).
- Job agendado (cron na janela 2h–5h BRT, fora do pico) que faz snapshot dos `data/outputs/`.
- Política de retenção (ex.: diários 7d / semanais 4w) e verificação de integridade (checksum).
- **Restore testado** em pasta limpa (igual ao rigor do BLK-OPS-01) + runbook em `docs/`.

**Fora de escopo:** versionar parquets no git (são grandes/gerados); recalcular M1.

**Critérios de aceite:**
- Backup automatizado rodando com retenção definida; checksums conferem.
- Restore validado end-to-end (arquivos íntegros) e documentado.
- Sem PII em logs; sem dependência de API ao vivo no dashboard.

**Risco:** baixo. Atenção a custo/espaço do destino e a não competir com usuários (janela noturna).

---

### BLK-SEC-05 — Observabilidade: monitoramento, alertas e runbook de incidente

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (contraparte detectiva dos controles preventivos; não toca M1/score) |
| **Prioridade** | **Média-Alta** |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Status** | Pendente |
| **Origem** | revisão de robustez 2026-05-31 (ponto cego de detecção identificado) |

**Contexto / gap:** os blocos BLK-SEC-01..04 são **preventivos**; falta o lado **detectivo**. Hoje não
há como saber quando algo dá errado: sem alerta de uptime (queda do dashboard só é vista por
`docker logs` manual), sem alerta de segurança (tentativas de login no Authelia, disparos do
fail2ban — ver BLK-SEC-03, uso anômalo de CPU/memória/disco), e sem runbook de resposta a incidente
geral (o BLK-OPS-01 cobre só regeneração de segredos). Controle preventivo sem detecção é
meia-segurança: portas trancadas, mas sem alarme.

**Objetivo:** detectar e ser notificado de falhas e eventos de segurança em tempo hábil, e ter um
plano claro de resposta — proporcional a um dashboard interno (nada de SIEM/enterprise).

**Escopo permitido (leve, sem stack pesada):**
- **Uptime/health externo** do dashboard (ex.: monitor HTTP simples/UptimeRobot-like ou cron + alerta)
  com notificação (e-mail/webhook) quando cair.
- **Alertas de host:** disco cheio, memória/swap saturada, container reiniciando (reusa `docker stats`,
  `df -h` do runbook; transformar em check agendado com alerta).
- **Sinais de segurança:** expor/alertar disparos do fail2ban e falhas de login do Authelia
  (logs já existem; falta o alerta).
- **Retenção/rotação de logs** dos containers (evitar disco cheio por log infinito).
- **Runbook de incidente** em `docs/` (VPS comprometido / vazamento / indisponibilidade): passos de
  contenção, quem aciona, como isolar, e ligação com o DR de segredos (BLK-OPS-01) e o backup de
  dados (BLK-SEC-04).

**Fora de escopo:** SIEM, APM completo, tracing distribuído, on-call formal — exagero para o contexto.

**Arquivos prováveis:** `docs/infra_producao.md` (seção de monitoramento + runbook de incidente),
`docker-compose.prod.yml` (logging/retention), eventual script de health-check agendado.

**Critérios de aceite:**
- Queda do dashboard gera notificação comprovada (teste: derrubar o container num horário combinado).
- Alertas de disco/memória e de eventos de segurança (fail2ban/Authelia) configurados e testados.
- Rotação de logs ativa (sem crescimento ilimitado).
- Runbook de incidente documentado e revisado; zero mudança em M1/artefatos.

**Risco:** baixo. Cuidado para não gerar alarme ruidoso (calibrar limiares) nem expor segredos nos
canais de alerta.

---

### BLK-ORQ-02 — Implementar estrutura Fase 2

Status: pendente (depende de BLK-ORQ-01 validado)
Criticidade: alta
Prioridade: média
Tipo: estrutura
Skill recomendada: /run-cycle
Resumo: Criar DECISIONS.md com migração das decisões do CLAUDE.md (DEC-001 a DEC-003),
context/active_context.md, tasks/blocked.md e 5 prompts adicionais
(master_orchestrator, approver, documenter, data_agent, metrics_agent).
Dependências: BLK-ORQ-01
Observações: CLAUDE.md não deve ser reescrito, apenas estendido com seção ## Skills.

---

### BLK-PROD-03 — Avaliar hex_id como category com benchmark

Status: pendente
Criticidade: média
Prioridade: baixa
Tipo: performance
Skill recomendada: /run-cycle
Resumo: hex_id é chave de join; avaliar se category ajuda ou prejudica performance.
Requer benchmark antes de qualquer mudança.
Dependências: nenhuma

---

### BLK-PROD-02 — Limpar leftovers de staging

Status: pendente
Criticidade: baixa
Prioridade: baixa
Tipo: manutenção
Skill recomendada: /run-cycle
Resumo: Remover data/outputs/*.tmp.parquet e diretório tmp_codex_runtime/.
Dependências: aprovação explícita do usuário para remoção de arquivos.
Observações: não executar sem confirmação explícita. Risco de remoção indevida.

---

### BLK-PROD-01 — Refatoração completa do repositório

Status: pendente
Criticidade: estratégica
Prioridade: média
Tipo: refatoração
Skill recomendada: /run-cycle (fluxo estratégico)
Resumo: Migrado do PRD.md. Próxima etapa de planejamento estrutural do repositório.
Dependências: nenhuma bloqueadora
Observações: requer planejamento detalhado antes de execução. Não iniciar sem aprovação.

---

### BLK-PROD-05 — Geocodificação offline/online de endereço

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Implementar geocodificação de endereço apenas se dependência externa for
aprovada ou base local viável identificada.
Dependências: aprovação de dependência externa ou base local.

---

### BLK-PROD-06 — Relatório semanal de movimentação concorrencial

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature / analytics
Skill recomendada: /run-cycle
Resumo: Snapshots, deltas por rede/cidade e impacto nas oportunidades.
Dependências: definição de fonte de dados concorrencial automatizável.

---

### BLK-PROD-07 — Cenários salvos por usuário e histórico de decisão

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Apenas se o dashboard evoluir para produto web interno com múltiplos usuários.
Dependências: decisão de produto sobre evolução para web interno.

---
