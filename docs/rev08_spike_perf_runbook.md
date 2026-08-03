> **[HISTORICO — 2026-08-03, DEC-022]** O dashboard Streamlit medido aqui foi aposentado e os
> artefatos do spike (`ui_spike_deckgl.py`, `scripts/rev08_spike_app.py`,
> `scripts/rev08_spike_playwright.py`) sairam do repo com o corte. O runbook fica preservado como
> registro da medicao que embasou o mapa client-side (deck.gl) do piloto web — os comandos abaixo
> nao sao mais executaveis neste repo.

> **[SPIKE]** Artefato de medicao descartavel do BLK-REV-08 (tabelas propositalmente em branco).

# Runbook de medição — Spike deck.gl (BLK-REV-08)

> Spike **descartável** de teto de performance do mapa client-side (deck.gl
> `H3HexagonLayer`) no volume real do cap (18–35k hexes). Este runbook cobre a
> **MEDIÇÃO EMPÍRICA**, que é **passo HUMANO** — a esteira autônoma entrega o
> código (módulo `ui_spike_deckgl.py` + harness `rev08_spike_playwright.py`),
> mas **não** gera tráfego contra produção nem executa comandos na VPS.
>
> READ-ONLY sobre o M1: nada aqui recalcula ou altera
> `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/artefatos
> oficiais. As tabelas abaixo estão **em branco de propósito** — preencha com
> os números reais que você medir. **Não invente métricas.**

## Contexto rápido

- **Motor do spike:** deck.gl `H3HexagonLayer` via bundle UMD por CDN, basemap
  raster CARTO dark via `TileLayer`. O payload usa `hex_id` cru (tesselação na
  GPU) — sem geometria, sem lat/lng por hex.
- **Cap espelhando produção:** SP (47.389 hexes) > `MAP_POINT_LIMIT` (35000) →
  cap `MAP_POINT_LIMIT_LARGE` (18000). UFs de 18k–35k → cap 35000. `mode_stress`
  desliga o cap (renderiza o recorte inteiro — achar o teto).
- **Marcadores de perf** expostos pelo spike (via `performance.now()`):
  `window.__spikeFirstPaintMs`, `window.__spikeRecolorMs`,
  `window.__spikeAddHexMs`.

## Pré-requisitos (ambiente local do humano)

Playwright já está no extra `[scraping]` do `pyproject.toml` (sem dep nova). Os
browsers do Playwright são passo de ambiente, **não** da esteira:

```bash
pip install -e '.[scraping]'
python -m playwright install chromium
```

Para servir o spike localmente (opt-in, sem tocar produção), use o **lançador
standalone descartável** `scripts/rev08_spike_app.py` (serve APENAS a página
`render_spike_page()`; não é importado por `pages.py`/`streamlit_app.py`):

```bash
python -m streamlit run scripts/rev08_spike_app.py
```

> O lançador já define `ULTRA_SPIKE_DECKGL=1` internamente. O dashboard de
> produção (`streamlit_app.py`) NÃO é tocado e roda idêntico sem a env var.
>
> **Nota de render (fix pós-gate):** o protótipo desenha os hexágonos com o
> `PolygonLayer` do deck.gl 8.9.36 tesselando a célula no cliente via
> `h3-js@4` (`cellToBoundary`) a partir do `hex_id` cru — o payload continua
> sem geometria. O motivo de não usar `H3HexagonLayer` é que o h3 embutido no
> bundle standalone era incompatível (API v3 x v4). O deck cria o próprio
> canvas dentro do `<div id="container">` (necessário para o controlador de
> zoom/pan/clique funcionar dentro do iframe do Streamlit).

---

## Sub-entregável (i) — DevTools contra produção (leitura no browser humano)

Medição manual no navegador do humano, **sem automação**. Abra
`https://dashboard.ultra-expansao.tech` e use as abas do DevTools:

1. **Network → WS:** observe o tamanho dos frames WebSocket a cada rerun do
   Streamlit (trocar modo de cor, aplicar filtro, selecionar hex). Anote o
   tamanho do maior frame por interação.
2. **Performance:** grave um trace curto de cada interação de dor e leia o
   intervalo clique → primeiro paint do mapa.

| Interação (produção)            | Frame WS (KB) | Clique→paint (ms) | Observação |
|---------------------------------|---------------|-------------------|------------|
| Carga inicial do Mapa (UF=SP)   |               |                   |            |
| Trocar modo de cor (M1↔Residual)|               |                   |            |
| Selecionar/adicionar hex        |               |                   |            |
| Gerar relatório (PDF)           |               |                   |            |

> Só leitura no browser do humano — não requer VPS nem automação.

---

## Sub-entregável (ii) — Playwright contra produção (ação HUMANA)

O harness `scripts/rev08_spike_playwright.py` cronometra os 4 fluxos. Contra
**produção** ele exige confirmação humana explícita (guarda anti-produção):

```bash
python scripts/rev08_spike_playwright.py \
  --url https://dashboard.ultra-expansao.tech \
  --target production --flow all --runs 5 \
  --i-confirm-production \
  --out data/reports/scratch/rev08_producao.json
```

> ⚠️ **NOTA:** este comando gera **tráfego real** contra produção. É
> **decisão/execução HUMANA** — a esteira autônoma **não** o roda (sem a flag
> `--i-confirm-production`, uma URL `ultra-expansao.tech` **aborta**). Só o
> `--target production` habilita o fluxo `pdf`; no `--target spike` o `pdf` é
> **pulado com aviso** (não se inventa número server-side).

Para medir o **spike local** (sem tocar produção):

```bash
python scripts/rev08_spike_playwright.py \
  --url http://localhost:8501 --uf SP --flow all --runs 5 \
  --out data/reports/scratch/rev08_spike_local.json
```

> **Limitação conhecida do harness:** o `--url`/`--flow` funcionam, mas o
> harness clica "Gerar recorte" com a UF **default** do seletor — ele NÃO
> seleciona a `--uf` na página. Para medir um volume específico, use a medição
> determinística por volume abaixo (mais limpa: isola o deck.gl do iframe do
> Streamlit).

### Curva de escala (medição determinística por volume — laptop, 2026-07-16)

Método: para cada volume, gera-se o recorte → monta-se o HTML do spike →
abre-se o arquivo direto no Chromium (Playwright, `file://`) e lê-se
`window.__spike*`. Isola o custo puro de render do deck.gl (sem o iframe do
Streamlit). 3 runs por caso (mediana). **Laptop local, SEM rede VPS.**

| Caso                    | hexes  | payload inline | render (1º paint) | recolor | cenário (add hex) |
|-------------------------|--------|----------------|-------------------|---------|-------------------|
| SP cap 18k (produção)   | 18.000 | 1,46 MB        | 478 ms            | 38 ms   | 57 ms             |
| AC full 29k             | 29.004 | 2,41 MB        | 640 ms            | 34 ms   | 90 ms             |
| SP stress 47k           | 47.389 | 3,86 MB        | 497 ms            | 71 ms   | 64 ms             |
| MG stress 104k          | 104.078| 8,46 MB        | ~1038 ms ⚠️       | 30 ms   | 177 ms            |

⚠️ No 104k, 2 de 3 runs estouraram o timeout de 45 s no 1º paint → a partir de
~100k hexes o render fica pesado/instável (payload 8,5 MB inline). A faixa
OPERACIONAL de produção é o cap 18k–35k, onde render ~0,5–0,65 s e interação
< 100 ms.

**Leitura para o REV-12:** o diferencial do client-side é a **interação**
(recolor 30–71 ms, cenário 57–177 ms) — client-side/GPU, SEM round-trip ao
servidor, praticamente **plana com o volume**; é a ordem de grandeza que o
REV-04/REV-05 querem comparar contra o rerun server-side do Streamlit atual. O
`render` (1º paint) escala com o volume (payload + tesselação h3 + paint WebGL)
e vira o gargalo só perto de ~100k. Os números de **produção/A-B na VPS seguem
passo humano** (rede real + §6) — é o que valida se o payload inline (1,5–8,5 MB)
sobrevive ao link real.

> **Nota:** os markers `window.__spike*` existem SÓ no spike. O
> `rev08_spike_playwright.py` NÃO mede o app atual. Para o baseline do app atual,
> usou-se uma medição AUTOMATIZADA independente por **frames de WebSocket** (a
> seguir), já que cada interação no Streamlit re-serializa o mapa e trafega pelo
> WS — o tempo até o maior frame chegar é um proxy fiel do custo do rerun.

### Comparação AUTOMATIZADA — app atual (pydeck/Streamlit) x spike (deck.gl)

Método (app atual): Playwright dirige o dashboard real local (`:8502`, UF=SP,
aba Mapa), captura os frames do WebSocket do Streamlit e mede, por interação, a
**latência clique → chegada do maior frame WS** (mapa re-serializado) e o
**tamanho desse frame**. 5 runs, mediana. **Laptop local, SEM rede VPS** — na
mesma máquina que mediu o spike. (Script throwaway de scratchpad; reprodutível.)

| Fluxo                         | App atual (Streamlit/pydeck) | Spike (deck.gl client-side) | Ganho    |
|-------------------------------|------------------------------|-----------------------------|----------|
| render (atualizar/1º mapa)    | **791 ms**                   | 478 ms                      | ~1,7×    |
| recolor (trocar modo de cor)  | **3282 ms** (~3,3 s)         | 38 ms                       | **~86×** |
| payload por INTERAÇÃO          | ~239 KB por rerun (a CADA clique) | 1,46 MB **uma vez** (0/clique) | break-even ~6 cliques |

**Leitura:** o `render` (desenhar o mapa do zero) é comparável — o app atual até
segura bem (791 ms). O abismo é a **interação**: trocar o modo de cor custa
**~3,3 s no app atual** (rerun completo: recomputa cores + re-serializa + repaint)
vs **38 ms no spike** (recolor client-side por `updateTriggers`, sem tráfego).
O trade-off de payload: o app atual manda ~239 KB **a cada** interação; o spike
paga 1,46 MB **uma vez** e depois ~0 — o ponto de equilíbrio é ~6 interações por
sessão (bem abaixo do uso real). Caveats: `scenario` (add hex) não foi
automatizado (exige clique no hexágono do mapa pydeck por pixel) — mas incorre no
MESMO rerun do recolor; `239 KB` é o maior frame WS único (o total do rerun pode
ser maior); tudo LOCAL — a **perna VPS** (rede real) segue passo humano (§6).

---

## Sub-entregável (iii) — A/B via Caddy na VPS (ação HUMANA, §6)

Servir o spike atrás do Caddy e rodar o **mesmo** harness contra o Streamlit de
produção vs o spike, na **mesma rede**, para um A/B justo. A topologia real
(REV-07) é multi-container: `motor_expansao_streamlit` + `motor_expansao_api` +
`motor_expansao_caddy` + `authelia`, com os dados em volume `:ro`, orquestrados
por `docker-compose.prod.yml`. Deploy é **manual por digest**.

> ⚠️ **§6 — GUARDRAIL ABSOLUTO:** cada comando abaixo toca a VPS de produção e
> **exige confirmação humana INDIVIDUAL por comando**. **NÃO encadear.** A
> esteira autônoma **nunca** executa nada disto.

1. Atualizar o checkout do motor na VPS (traz o spike):

   ```bash
   # ⚠️ §6 — exige confirmação humana individual por comando; não encadear
   git -C /opt/motor-expansao/app pull
   ```

2. Rebuild da imagem do serviço do spike (por digest; não subir automático):

   ```bash
   # ⚠️ §6 — exige confirmação humana individual por comando; não encadear
   docker build -f Dockerfile.streamlit -t motor-expansao-spike:rev08 /opt/motor-expansao/app
   ```

3. Adicionar uma rota temporária no Caddyfile para o spike (ex.: subdomínio ou
   path `/spike`), atrás do Authelia como o resto:

   ```bash
   # ⚠️ §6 — exige confirmação humana individual por comando; não encadear
   nano /opt/motor-expansao/infra/Caddyfile
   ```

4. Recarregar o Caddy (sem derrubar produção):

   ```bash
   # ⚠️ §6 — exige confirmação humana individual por comando; não encadear
   docker compose -f /opt/motor-expansao/infra/docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
   ```

5. Subir o container do spike (opt-in via `ULTRA_SPIKE_DECKGL=1`):

   ```bash
   # ⚠️ §6 — exige confirmação humana individual por comando; não encadear
   docker compose -f /opt/motor-expansao/infra/docker-compose.prod.yml up -d spike
   ```

6. Rodar o A/B (do laptop do humano, contra os dois endpoints da MESMA VPS):

   ```bash
   # produção (Streamlit atual) — requer confirmação humana
   python scripts/rev08_spike_playwright.py --url https://dashboard.ultra-expansao.tech \
     --target production --flow all --runs 10 --i-confirm-production \
     --out data/reports/scratch/rev08_ab_streamlit.json
   # spike (deck.gl) — requer confirmação humana
   python scripts/rev08_spike_playwright.py --url https://spike.ultra-expansao.tech \
     --target spike --flow render,recolor,scenario --runs 10 --i-confirm-production \
     --out data/reports/scratch/rev08_ab_spike.json
   ```

7. Derrubar a rota/container do spike ao terminar (limpeza):

   ```bash
   # ⚠️ §6 — exige confirmação humana individual por comando; não encadear
   docker compose -f /opt/motor-expansao/infra/docker-compose.prod.yml stop spike
   ```

| Métrica (A/B, mesma VPS)     | Streamlit (produção) | Spike (deck.gl) | Δ | Observação |
|------------------------------|----------------------|-----------------|---|------------|
| render — mediana (ms)        |                      |                 |   |            |
| render — p95 (ms)            |                      |                 |   |            |
| recolor — mediana (ms)       |                      |                 |   |            |
| scenario — mediana (ms)      |                      |                 |   |            |
| payload por interação (KB)   |                      |                 |   |            |
| FPS de pan/zoom (aprox.)     |                      |                 |   |            |

---

## Registro do payload embutido (medição humana)

O JSON embutido no HTML é justamente o custo que o spike expõe (18–35k × 7
chaves curtas). Meça e anote — **não** otimize prematuramente no spike:

| UF   | Hexes no recorte | Tamanho do JSON inline (KB) | Modo   |
|------|------------------|-----------------------------|--------|
| SP   | 18000            | 1483 (~1,46 MB)             | cap 18k|
| SP   | 47389            | ~3950 (~3,86 MB)            | stress |
| AC   | 29004            | ~2470 (~2,41 MB)            | full   |
| MG   | 104078           | ~8660 (~8,46 MB)            | stress |

---

## Decisão (fica para o BLK-REV-12, não aqui)

Este bloco **não** decide o rumo (Streamlit+otimizar vs SPA vs Dash/Panel vs
deck.gl custom). Ele entrega o número real de teto para o **BLK-REV-12** decidir
com evidência. Ao concluir a medição, anexe os JSONs de
`data/reports/scratch/` e resuma os achados para o REV-12.
