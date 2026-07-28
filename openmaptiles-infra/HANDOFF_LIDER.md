# Handoff — subir o basemap self-host (OpenMapTiles) no VPS

**Para quem tem acesso ao servidor** (`root@2.25.137.241`, Hostinger KVM, Ubuntu, rede
`app_net`). Tempo: ~15–30 min. Não roda em domingo 2h (janela do job pesado do motor).

## Contexto (1 parágrafo)
Vamos adicionar um **seletor de mapa de fundo** (Escuro/Claro/Satélite) no dashboard. Para
os modos Claro/Satélite, subimos um **tileserver OpenMapTiles próprio** na MESMA VPS, na
rede `app_net`, servido **sob o domínio do dashboard** em `/tiles` e atrás do MESMO login
(Authelia). **Não abre porta nova, não cria DNS novo.** Não toca em nenhum dado do motor.

## O que você precisa ter em mãos
- Acesso ao servidor (SSH ou Browser terminal do Hostinger).
- Esta pasta `openmaptiles-infra/` no servidor (passo 1).
- A **chave `age` do SOPS** (para editar o Caddyfile no passo 6).

---

## Passo a passo

### 1) Colocar a stack no servidor
Se tiver SSH da sua máquina:
```bash
scp -r openmaptiles-infra root@2.25.137.241:/opt/openmaptiles-infra
```
(Ou suba a pasta pelo File Manager do Hostinger para `/opt/openmaptiles-infra`.)

Depois, no servidor:
```bash
ssh root@2.25.137.241
cd /opt/openmaptiles-infra
```

### 2) Confirmar a rede do motor
```bash
docker network ls | grep app
```
Espera-se `app_app_net`. Se o nome for OUTRO, ajuste em `docker-compose.yml` (campo
`networks.app_net.name`).

### 3) Java para o gerador de tiles (se faltar)
```bash
java -version 2>/dev/null || apt update && apt install -y openjdk-17-jre-headless
```

### 4) Gerar os tiles do Brasil (~3–6 GB) — passo mais longo
```bash
bash scripts/generate-brazil.sh
```
- Baixa o OSM do Brasil e gera `data/mbtiles/brazil.mbtiles`. Pode levar alguns minutos.
- RAM baixa: `JAVA_XMX=4g bash scripts/generate-brazil.sh`.
- **Alternativa sem gerar:** se já houver um `.mbtiles` OpenMapTiles do Brasil, salve como
  `data/mbtiles/brazil.mbtiles` e pule este passo.

### 5) Subir o tileserver
```bash
docker compose up -d
docker compose ps
docker exec motor_expansao_tileserver wget -qO- http://127.0.0.1:8080/data/brazil.json | head
```
O container fica interno (sem porta no host), com cap 1.5 GB / 1 vCPU — não compete com o motor.

### 6) Publicar a rota no Caddy (precisa da chave age/SOPS)
Adicione o bloco de `caddy/tiles.Caddyfile` **DENTRO do bloco
`dashboard.ultra-expansao.tech { ... }`** do Caddyfile do motor (gerenciado via SOPS em
`secrets/Caddyfile.enc` no repo do motor), antes do `reverse_proxy` do streamlit:
```
    handle_path /tiles/* {
        reverse_proxy motor_expansao_tileserver:8080
        header Cache-Control "public, max-age=604800"
    }
```
Aplique o Caddyfile conforme o fluxo de secrets do projeto e recarregue:
```bash
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml restart caddy
```

### 7) Monitoramento
No `scripts/healthcheck_vps.sh` do motor, subir a contagem esperada de containers de **5 → 6**.

---

## Verificação final
Logado no dashboard, no navegador:
```
https://dashboard.ultra-expansao.tech/tiles/styles/ultra-maptiler/style.json
```
Deve retornar o JSON do estilo (não erro/redirect). Se aparecer, a Fase 1 está pronta.

## Reportar de volta
Diga se: (a) `docker compose ps` mostra o tileserver `Up`; (b) o `brazil.json` respondeu;
(c) a URL `/tiles/styles/ultra-maptiler/style.json` abriu logado. Com isso confirmamos e
seguimos para o deploy do dashboard (Fase 2).

> Detalhes e racional completos: `README.md` (nesta pasta) e, no repo do motor,
> `docs/deploy_basemap_selfhost.md`.
