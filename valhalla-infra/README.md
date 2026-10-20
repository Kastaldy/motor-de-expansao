# Valhalla self-host — serviço de rotas do motor (DEC-074)

Sobe um **Valhalla 3.9.0** na **mesma VPS do motor**, numa stack separada, para responder
uma pergunta só: **até onde se chega em 10 minutos de carro, sem trânsito, a partir de um
ponto**. É o alcance "10 min de carro" da ficha do ponto e do Estudo (DEC-074). Raio de
1 km e raio de 2 km **não** passam por aqui.

> **Muda / não muda:** muda só a disponibilidade da opção "10 min de carro". Score, funil,
> M1 e artefatos **não mudam**. A isócrona **não é gate nem peso** de nada (alinhado ao
> relatório de isócronas de 25/09/2026): é o recorte em que o motor lê população, renda e
> concorrência, como o raio.

> **Opcional por construção.** Sem `MOTOR_ROTAS_URL` no `.env` do motor, a opção some da
> tela e a rota responde 503 com mensagem. Nunca há queda silenciosa para o raio de 1 km.

---

## Como encaixa na produção (topologia)

```
[navegador] --(HTTPS, login)--> [Caddy] --> [motor_expansao_web]
                                                  |  POST /isochrone (app_net, interno)
                                                  v
                                   [motor_expansao_valhalla] :8002
                                                  |  lê custom_files/valhalla_tiles.tar
```

- **Quem chama:** só o **servidor** do piloto (`MOTOR_ROTAS_URL=http://motor_expansao_valhalla:8002`).
  O navegador nunca fala com o Valhalla.
- **Sem porta no host e sem rota no Caddy.** Diferente do tileserver (que o navegador busca),
  aqui não há motivo para sair da `app_net`: o Valhalla não tem autenticação, e porta exposta
  seria serviço aberto na internet. Travado por teste (`tests/contracts/test_compose_rotas.py`).
- **Rede:** `app_net` externa (`app_app_net`), a mesma do `docker-compose.prod.yml`.
- **Servidor:** `/opt/valhalla-infra` (padrão dos outros `-infra`).

---

## Estrutura

```
valhalla-infra/
├─ docker-compose.yml          # valhalla (só serve; teto de memória obrigatório) na app_net externa
├─ scripts/build-brazil.sh     # build FORA da VPS + publicação atômica NA VPS
└─ custom_files/               # valhalla_tiles.tar + valhalla.json + VERSAO_TILES (gerado; gitignored)
```

---

## Por que o build é fora da VPS

O build dos tiles do Brasil inteiro disputa RAM e CPU com o motor, e a KVM4 já tem tetos
declarados acima dos 16 GB físicos (`docs/infra_producao.md`). RAM, tempo e tamanho do build
**ainda não foram medidos** — são itens da seção "Números a medir antes de aprovar" da
DEC-074. Mesma regra do `openmaptiles-infra`: gerar em outra máquina e copiar só o resultado.

O container de produção **só serve**: `use_tiles_ignore_pbf=True` + `force_rebuild=False`
impedem que ele decida rebuildar o Brasil no boot, dentro da caixa de produção.

---

## Passo a passo

> Cada comando **na VPS** exige confirmação explícita do Felipe, um a um (CLAUDE.md §6).

1. **Build (na estação, fora da VPS).** Precisa de Docker, `curl`, `md5sum` e Python:
   ```bash
   cd valhalla-infra
   bash scripts/build-brazil.sh build          # BUILD_MEM=12g para limitar a RAM do build
   ```
   O script baixa o extrato da Geofabrik, confere o `.md5`, gera os tiles num rascunho, sobe um
   Valhalla temporário em `127.0.0.1:8012`, roda o **smoke** (isócrona de 10 min na Av. Paulista)
   e só então empacota `valhalla-tiles-brazil-AAAAMMDD.tar.gz`. **Anote** o que ele imprime
   (duração, tamanho, `docker stats`): são números da DEC-074.

2. **Copiar a stack e o pacote** para `/opt/valhalla-infra/` na VPS.

3. **Definir o teto de memória medido** no `.env` da stack (`/opt/valhalla-infra/.env`):
   ```bash
   VALHALLA_MEM_LIMIT=<valor medido>   # ex.: 2g — SÓ depois de medir (ver "Verificação")
   ```
   O compose **aborta** sem essa variável, de propósito: um serviço novo sem teto, numa caixa
   cujos tetos já somam mais que a RAM física, é o que derrubaria o motor.

4. **Publicar** (na VPS):
   ```bash
   cd /opt/valhalla-infra
   docker network ls | grep app                # espera-se 'app_app_net'
   bash scripts/build-brazil.sh publicar valhalla-tiles-brazil-AAAAMMDD.tar.gz
   ```
   Rascunho → rename atômico (o vivo vira `custom_files.anterior`) → `docker compose up -d` →
   smoke **de dentro** do `motor_expansao_web`. Smoke reprovado = volta o anterior sozinho.

5. **Ligar no motor** — só depois do smoke verde. No `.env` do motor:
   ```bash
   MOTOR_ROTAS_URL=http://motor_expansao_valhalla:8002
   ```
   e recriar o `web` (`docker compose -f docker-compose.prod.yml up -d web`). A partir daí o
   healthcheck passa a vigiar `motor_expansao_valhalla`.

**Desligar:** esvaziar `MOTOR_ROTAS_URL` e recriar o `web`. A opção some da tela; nada mais muda.

---

## Verificação

```bash
docker compose ps                                       # valhalla de pé
docker exec motor_expansao_web python -c \
  "import urllib.request;print(urllib.request.urlopen('http://motor_expansao_valhalla:8002/status').read()[:300])"
docker stats --no-stream motor_expansao_valhalla        # memória em repouso
```

**Medir o teto de memória:** com o serviço de pé, rodar uma série de isócronas reais (várias
capitais, pela tela ou pelo smoke) e observar `docker stats` durante a série. O
`VALHALLA_MEM_LIMIT` é o pico observado com folga — e o número entra na DEC-074.

**Versão dos tiles:** `custom_files/VERSAO_TILES` (extrato, md5, data do OSM, imagem, data do
build) e o `/status` do serviço (`tileset_last_modified`). O motor carimba a versão no
resultado de cada isócrona (auditoria, DEC-074).

---

## Notas

- **Imagem pinada por tag e digest** (`valhalla-scripted:3.9.0@sha256:...`), no compose e no
  script, com paridade travada por teste: tiles gerados por uma versão e servidos por outra
  quebram o serviço. Trocar de versão = rebuild dos tiles + reconferir o nome das envs.
- **Usuário da imagem:** ela roda sem root. O script descobre o UID pela própria imagem
  (`id -u`) e ajusta o dono do volume; não cravar o número.
- **Atualizar a malha:** repetir o build e o `publicar`. A malha viária muda devagar —
  cadência manual (mensal a trimestral). **Não** rodar na janela de domingo (lote semanal,
  CLAUDE.md §6) nem no sábado 03:00 UTC (WellHub, DEC-039).
- **Tempo sem trânsito:** o motor não manda `date_time`; o tempo é de rua livre, e a tela diz
  "sem trânsito".
