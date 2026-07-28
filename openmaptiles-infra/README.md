# OpenMapTiles self-host — basemap do motor

Sobe um servidor de **tiles vector OpenMapTiles** na **mesma VPS do motor**, com o
**visual MapTiler soft** (autoral) e um **satélite + overlay claro**. É a **Fase 1**:
montar a infra. A Fase 2 (seletor de basemap no motor) vem depois, apontando o
`map_style` do pydeck para as URLs deste servidor.

> **Alinhado à infra de produção do motor** (`docs/infra_producao.md`): stack separada
> (padrão dos `-infra`), na rede `app_net`, atrás do **Caddy** existente. Servido **sob
> o domínio do dashboard e o MESMO login (Authelia)** — igual ao antigo. **Sem porta
> nova** (ufw só libera 22/80/443) e **sem subdomínio/DNS novo**.

> **Muda / não muda:** muda só *de onde vêm os tiles de fundo*. Os dados do motor
> (hexágonos, scores, pins) **não mudam**. Esta infra **não toca no código do motor**.

---

## Como encaixa na produção (topologia)

```
https://dashboard.ultra-expansao.tech/          -> dashboard (Streamlit)
https://dashboard.ultra-expansao.tech/tiles/... -> tiles (MESMO login Authelia)
                          │
          [Caddy motor_expansao_caddy] :443  (TLS + Authelia forward_auth)
                          │  handle_path /tiles/*  (rede app_net)
          [motor_expansao_tileserver] :8080  (interno, cap 1.5G/1cpu)
                          │  lê  data/mbtiles/brazil.mbtiles
                          ▼
          /tiles/styles/ultra-maptiler/style.json
          /tiles/styles/sat-overlay/style.json
```

- **Login:** herda o Authelia do dashboard (same-origin) — sem cookie cross-origin.
- **Edge:** o Caddy do motor (não subo outro proxy). Um `handle_path /tiles/*` roteia.
- **Rede:** `app_net` (externa) — a mesma do `docker-compose.prod.yml` do motor.
- **Porta / DNS:** nada novo. Acesso pelo domínio do dashboard já existente.
- **Servidor:** `/opt/openmaptiles-infra` (padrão dos outros `-infra`).

---

## Estrutura

```
openmaptiles-infra/
├─ docker-compose.yml            # tileserver (capado) na rede app_net externa
├─ caddy/tiles.Caddyfile         # handle_path /tiles/* p/ o bloco do dashboard (SOPS)
├─ scripts/generate-brazil.sh    # gera o brazil.mbtiles com planetiler
└─ data/
   ├─ config.json                # tileserver -> mbtiles + styles + publicUrl (/tiles/)
   ├─ mbtiles/                   # brazil.mbtiles vai aqui (gerado; gitignored)
   └─ styles/
      └─ ultra-maptiler/style.json   # visual MapTiler soft (autoral)
```

> **`sat-overlay` NAO foi versionado (2026-07-28).** O estilo buscava a imagem de satelite em
> `server.arcgisonline.com` **sem chave** — exatamente o endpoint anonimo que a **DEC-018**
> proibiu ao regularizar a licenca (`censo_map.py:1611-1617`: a vista aerea vem de
> `ibasemaps-api.arcgis.com` autenticada por `API_ARCGIS_API_KEY`, e **sem** chave a pagina e
> OMITIDA, nunca se cai no anonimo). Como um `style.json` versionado e servido ao cliente, nao da
> para injetar a chave nele sem expo-la. O estilo nao e consumido por nada hoje e esta **fora do
> escopo** do basemap de ruas do PDF — entra quando houver um caminho compativel com a DEC-018.
> A entrada correspondente foi removida do `data/config.json` (o tileserver nao sobe apontando
> para um `style.json` inexistente).

---

## Passo a passo (na VPS)

1. **Copie a stack** pro servidor (padrão dos `-infra`):
   ```bash
   scp -r openmaptiles-infra root@2.25.137.241:/opt/openmaptiles-infra
   ssh root@2.25.137.241
   cd /opt/openmaptiles-infra
   ```

2. **Confirme o nome da rede** do motor e ajuste `docker-compose.yml` se preciso:
   ```bash
   docker network ls | grep app      # espera-se 'app_app_net'
   ```

3. **Gere os tiles do Brasil** (~3–6 GB; precisa de Java 17+: `apt install -y openjdk-17-jre-headless`):
   ```bash
   bash scripts/generate-brazil.sh
   ```
   > ⚠️ **Não rode no domingo 2h** (janela do job pesado do motor). Melhor: gerar em
   > **outra máquina** e copiar só `data/mbtiles/brazil.mbtiles` — impacto zero no motor.
   > RAM: `JAVA_XMX=4g bash scripts/generate-brazil.sh` se precisar.

4. **Suba o tileserver** (entra na rede app_net; sem porta no host):
   ```bash
   docker compose up -d
   ```

5. **Adicione a rota no Caddy** — cole o `handle_path /tiles/*` de `caddy/tiles.Caddyfile`
   **dentro do bloco `dashboard.ultra-expansao.tech { ... }`** do Caddyfile do motor
   (gerenciado por SOPS: `secrets/Caddyfile.enc` no repo do motor). Assim os tiles
   herdam o `forward_auth` do Authelia que já protege o dashboard. Recarregue:
   ```bash
   cd /opt/motor-expansao/app
   docker compose -f docker-compose.prod.yml restart caddy
   ```

6. **Pronto.** Estilos disponíveis (exigem estar logado no dashboard):
   - `https://dashboard.ultra-expansao.tech/tiles/styles/ultra-maptiler/style.json`
   - `https://dashboard.ultra-expansao.tech/tiles/styles/sat-overlay/style.json`

---

## Verificação

```bash
# --- interno (na VPS, sem passar pelo login) ---
docker compose ps                                   # tileserver de pé
docker exec motor_expansao_tileserver \
  wget -qO- http://127.0.0.1:8080/data/brazil.json | head   # dataset responde
docker stats --no-stream motor_expansao_tileserver  # < 1.5 GB / ~0% CPU

# --- externo (via Caddy; precisa do cookie de sessão do Authelia) ---
# Sem login, o Caddy/Authelia redireciona p/ auth.ultra-expansao.tech (esperado).
# Logado no navegador, abrir:
#   https://dashboard.ultra-expansao.tech/tiles/data/brazil.json
```

**Verificação visual:** logado no dashboard, aponte um MapLibre para
`https://dashboard.ultra-expansao.tech/tiles/styles/ultra-maptiler/style.json`. No zoom
das casas os prédios devem bater **melhor** com o MapTiler que na demo com CARTO — agora
a fonte é OpenMapTiles, a mesma família do MapTiler Basic.

---

## Checklist de integração (não esquecer)

- [ ] `docker network ls` confirma o nome da rede em `docker-compose.yml`.
- [ ] `handle_path /tiles/*` adicionado ao bloco **dashboard** do Caddyfile (via SOPS) e Caddy recarregado.
- [ ] `ufw` **permanece** só 22/80/443 (nada a abrir). **Sem DNS novo.**
- [ ] **Monitoramento:** `scripts/healthcheck_vps.sh` conta "5 containers" — subir p/ **6** (o tileserver).
- [ ] `publicUrl` no `data/config.json` = `https://dashboard.ultra-expansao.tech/tiles/` (ajuste se o domínio mudar).

---

## Notas

- **Login (igual ao antigo):** os tiles ficam atrás do Authelia porque são servidos no
  domínio do dashboard. Como é same-origin, o cookie de sessão já vale — por isso **não**
  usamos subdomínio separado (lá o MapLibre não mandaria o cookie e quebraria).
- **Fontes (glyphs):** os estilos usam `Open Sans Italic`/`Semibold` (`serveAllFonts: true`).
  Se algum rótulo sumir, troque no `style.json` por `Open Sans Regular`/`Bold`.
- **Sem segredos:** OpenMapTiles é keyless — nada entra no SOPS além do trecho do Caddyfile.
- **Atualizar OSM:** re-rode `scripts/generate-brazil.sh` (trimestral basta) e
  `docker compose restart tileserver`. Opcional.
- **Encolher:** `AREA=sao-paulo bash scripts/generate-brazil.sh` gera só uma UF. Default: `brazil`.
- **Fase 2 (motor):** trocar os 7 `pdk.Deck(map_style=CARTO_DARK)` de `components.py` por
  um `map_style` resolvido de `st.session_state["basemap_choice"]`, com o seletor no
  `render_uf_selectbox` (`pages.py`), apontando para os estilos deste servidor.
```
