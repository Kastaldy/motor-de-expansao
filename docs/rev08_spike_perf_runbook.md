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

| Fluxo (harness)      | Alvo        | Mediana (ms) | p95 (ms) | Runs | Observação |
|----------------------|-------------|--------------|----------|------|------------|
| render (REV-03)      | spike local | 463          | 525      | 3    | 1ª leitura local 2026-07-16 (18k hexes SP; inclui build do payload + tesselação h3 + 1º paint WebGL) |
| recolor (REV-04)     | spike local | 46           | 101      | 3    | recolor M1↔Residual client-side (updateTriggers GPU, sem re-serializar) |
| scenario (REV-05)    | spike local | 32           | 33       | 3    | add hex ao cenário (client-side, sem rerun) |
| render (REV-03)      | produção    |              |          |      | (humano — A/B na VPS) |
| recolor (REV-04)     | produção    |              |          |      | (humano — A/B na VPS) |
| scenario (REV-05)    | produção    |              |          |      | (humano — A/B na VPS) |
| pdf (REV-06)         | produção    |              |          |      | (humano — só `--target production`) |

> **Leitura local preliminar (2026-07-16, laptop, sem rede VPS):** o custo de
> interação do spike (recolor ~46 ms, cenário ~32 ms) é client-side/GPU — a
> ordem de grandeza que o REV-04/REV-05 queriam comparar contra o rerun
> server-side do Streamlit. O `render` (~463 ms) inclui montar o payload de
> ~1,45 MB, tesselar 18k células (h3-js) e o 1º paint WebGL. Os números de
> **produção/A-B na VPS seguem sendo passo humano** (rede real + §6).

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
| SP   | 18000            | 1483 (~1,45 MB)             | cap 18k|
| SP   |                  |                             | stress |
|      |                  |                             |        |

---

## Decisão (fica para o BLK-REV-12, não aqui)

Este bloco **não** decide o rumo (Streamlit+otimizar vs SPA vs Dash/Panel vs
deck.gl custom). Ele entrega o número real de teto para o **BLK-REV-12** decidir
com evidência. Ao concluir a medição, anexe os JSONs de
`data/reports/scratch/` e resuma os achados para o REV-12.
