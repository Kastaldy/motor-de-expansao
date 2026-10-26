# Backup Encriptado de Segredos e Restore Ponta a Ponta

> Runbook canonico para sobreviver a perda total do VPS Hostinger KVM4.
> Cobre: tooling SOPS+age, geracao de chave, encriptacao inicial, restore em
> servidor zerado, regeneracao dos Parquets oficiais do M1, rotacao de chaves
> e validacao anti-vazamento.
>
> Quem mantem: Felipe Silva (Estrategia / Growth — Ultra Academia).
> Atualizado em: 2026-05-28 (ciclo BLK-OPS-01); revisado em 2026-08-03 (DEC-022 —
> Streamlit aposentado, app de producao passa a ser o piloto web); revisado em
> 2026-10-24 (o restore do servidor zerado passa a incluir o banco Postgres — §10.7-bis).

---

## 1. Escopo e premissas

**Cobre:**
- Encriptar 5 arquivos que hoje vivem apenas no VPS (`.env`, `Caddyfile`,
  `authelia/configuration.yml`, `authelia/users_database.yml`,
  `authelia/db.sqlite3`).
- Restore de servidor zerado (Ubuntu 22.04) com Docker + Compose plugin.
- Regeneracao completa dos Parquets oficiais do M1 a partir das fontes brutas.
- Rotacao de chave age e de segredos individuais.

**NAO cobre:**
- Backup remoto automatizado (rclone, S3, Backblaze). Anexo opcional, nao
  implementado neste ciclo. **Ressalva (2026-10-24):** isto vale para os segredos,
  cuja copia fora do servidor e' o proprio git (cifrado). O banco Postgres (§2) tem
  copia off-box prevista no `scripts/cron/run_backup_banco.sh` (restic), e ela esta'
  DESLIGADA em producao: destino e custo sao decisao pendente do Felipe. O BLK-SEC-04
  aceitou o risco em 2026-07-13 porque quase tudo era regeneravel, e o gatilho de
  reabertura dele inclui o crescimento de dado NAO regeneravel — que e' o banco. Ate'
  la', os dumps ficam no MESMO disco do banco; a unica copia externa e' o snapshot
  semanal da Hostinger (servidor inteiro, mesmo provedor), se ainda estiver ativo.
- Alteracoes em `docker-compose.prod.yml`, `Dockerfile.web`, pipeline
  M1, `config.py` ou parametros canonicos (`score_priorizacao`,
  `hex_score_estrutural`).
- Snapshot binario do VPS (Hostinger oferece backup proprio — fora de escopo).

**Premissas:**
- Operador tem acesso ssh `root@2.25.137.241` com `~/.ssh/id_ultra`.
- Maquina local roda Windows 11 com PowerShell 5.1+ ou 7+.
- Cofre offline (gestor de senhas ou pen drive criptografado) disponivel.

---

## 2. Inventario do que existe so no servidor

| Arquivo no VPS                                          | Tipo       | Descricao                                                   |
| ------------------------------------------------------- | ---------- | ----------------------------------------------------------- |
| `/opt/motor-expansao/app/.env`                          | dotenv     | Segredos Authelia (`AUTHELIA_JWT_SECRET` etc.)              |
| `/opt/motor-expansao/app/Caddyfile`                     | texto      | Reverse proxy com dominios reais e config TLS               |
| `/opt/motor-expansao/app/authelia/configuration.yml`    | YAML       | Configuracao Authelia (dominio, regras)                     |
| `/opt/motor-expansao/app/authelia/users_database.yml`   | YAML       | Usuarios + hashes argon2 das senhas                         |
| `/opt/motor-expansao/app/authelia/db.sqlite3`           | binario    | Sessoes Authelia (muda a cada login — drift esperado)       |
| `/opt/motor-expansao/cadastro/` (`cadastro_unidades.json`, `cadastro_log.jsonl`, `acesso_abas.json`, `bot_allowlist.json`) | JSON | Cadastro operacional (DEC-023), abas do piloto e allowlist do bot — editados em producao, SEM copia cifrada |
| volume `postgres_data` (`motor_expansao_postgres`) | Postgres | Usuarios, RBAC, sessoes e eventos — nenhum pipeline regenera; backup por `scripts/cron/run_backup_banco.sh`, que em producao roda no crontab da conta `deploy` com os dumps em `/home/deploy/backups/banco` (restore: §10.7-bis e `docs/banco_deploy.md` §10) |

> Esses arquivos estao no `.gitignore` da raiz do repo (linhas 135-139 atuais).
> Nenhuma versao em claro pode entrar no git.

### 2.1 Instancia AR (Bloco E / BLK-INTL-08)

A stack AR (`docker-compose.ar.yml`) **nao cria segredo novo**: Caddy, Authelia e o
`.env` sao os MESMOS da stack BR (compartilhados — o que muda neles e' so o bloco/regra
do host `piloto-ar`, ja coberto pelos backups cifrados acima). O que a AR acrescenta:

| Caminho no VPS                                     | O que e'                                                                     |
| -------------------------------------------------- | ---------------------------------------------------------------------------- |
| `/opt/motor-expansao-ar/data/perfil.json`          | Copia de `data/perfis/AR/perfil.json` (versionado — restore = scp do repo)   |
| `/opt/motor-expansao-ar/cadastro/acesso_abas.json` | Concessoes de aba da AR (editado em producao, so existe no servidor); molde em `docs/acesso_abas_ar.exemplo.json` |

A trilha de acesso AR (`/opt/motor-expansao-ar/logs/acesso/`) segue o regime da trilha
BR (sem prazo de retencao desde a emenda 2 da DEC-027, 20/10/2026; era 90 dias), porque
e' o mesmo codigo. Nenhum backup deste runbook cobre as trilhas (BR ou AR): se o disco
for perdido, o historico inteiro vai junto. Artefatos de dados AR
(`/opt/motor-expansao-ar/data/{outputs,staging}`) seguem a MESMA politica dos BR (§3):
nao entram no git nem no backup cifrado — sao reproduziveis a partir do pacote
Motor-Argentina e sobem por `scp`.

---

## 3. Inventario do que existe so localmente (dados brutos)

| Caminho local                                  | Tamanho | Descricao                                              |
| ---------------------------------------------- | ------- | ------------------------------------------------------ |
| `data/ultra/Ultra.csv`                         | ~50 KB  | Base operacional Ultra. Encoding `latin-1`, sep `;`, 1 linha de metadado inicial. **Legado: nao alterar contrato.** |
| `data/raw/ibge/`                               | varia   | Cache de malhas IBGE Censo 2022 baixadas (acelera regen) |
| `data/outputs/*.parquet`                       | ~1.6 GB | Artefatos M1 ja materializados — regeneraveis em ~45-75 min |

**Por que `data/outputs/` nao entra no git:** 1.6 GB violaria limites do
GitHub e do clone normal. Tudo ali e reproducao deterministica de
`data/ultra/Ultra.csv` + IBGE Censo 2022, via 3 scripts em
`src/motor_expansao/pipelines/m1/`. Documentado em §13.

**O que precisa ser preservado fora do servidor:**
- `data/ultra/Ultra.csv` — backup pessoal (drive, gestor de senhas).
- Cache `data/raw/ibge/` — opcional, so acelera regen. Nao critico.

---

## 4. Tooling: SOPS + age

**Versoes minimas:**
- `sops` >= 3.8 (testado: 3.8.1)
- `age` >= 1.1 (testado: 1.1.1)

**Releases oficiais:**
- SOPS: https://github.com/getsops/sops/releases
- age:  https://github.com/FiloSottile/age/releases

**Por que SOPS+age (vs git-crypt):**
- Granularidade por arquivo: SOPS criptografa apenas valores em YAML/JSON,
  preservando estrutura legivel em diffs.
- Binarios estaticos em Linux e Windows — sem GPG, sem `git config filter.*`.
- Rotacao de chave por re-encriptacao por arquivo (`sops updatekeys`).

---

## 5. Setup do tooling — Windows (PowerShell)

> Nao usa winget/choco para nao exigir privilegio administrativo. Instala em
> `C:\tools\sops\` e adiciona ao PATH do usuario.

```powershell
# 1. Criar pasta
$ToolsDir = "C:\tools\sops"
New-Item -ItemType Directory -Force $ToolsDir | Out-Null

# 2. Baixar sops.exe
Invoke-WebRequest `
  -Uri "https://github.com/getsops/sops/releases/download/v3.8.1/sops-v3.8.1.exe" `
  -OutFile "$ToolsDir\sops.exe"

# 3. Baixar age (zip contendo age.exe + age-keygen.exe)
Invoke-WebRequest `
  -Uri "https://github.com/FiloSottile/age/releases/download/v1.1.1/age-v1.1.1-windows-amd64.zip" `
  -OutFile "$env:TEMP\age.zip"
Expand-Archive -Path "$env:TEMP\age.zip" -DestinationPath $env:TEMP -Force
Copy-Item "$env:TEMP\age\age.exe" "$ToolsDir\age.exe"
Copy-Item "$env:TEMP\age\age-keygen.exe" "$ToolsDir\age-keygen.exe"

# 4. Adicionar ao PATH do usuario (persistente)
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$ToolsDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$ToolsDir", "User")
}
$env:Path = "$env:Path;$ToolsDir"

# 5. Validar
sops --version
age --version
```

---

## 6. Setup do tooling — Linux (VPS Ubuntu 22.04)

> Pode ser substituido pelo script idempotente `bash scripts/setup_secrets_vps.sh`
> (passos 1, 2, 4 e 5 da acao humana). O passo 3 — cofre offline — fica
> sempre manual.

```bash
# 1. SOPS
curl -L https://github.com/getsops/sops/releases/download/v3.8.1/sops-v3.8.1.linux.amd64 \
  -o /usr/local/bin/sops
chmod +x /usr/local/bin/sops

# 2. age
curl -L https://github.com/FiloSottile/age/releases/download/v1.1.1/age-v1.1.1-linux-amd64.tar.gz \
  -o /tmp/age.tar.gz
tar -xzf /tmp/age.tar.gz -C /tmp/
mv /tmp/age/age /tmp/age/age-keygen /usr/local/bin/
chmod +x /usr/local/bin/age /usr/local/bin/age-keygen
rm -rf /tmp/age /tmp/age.tar.gz

# 3. Validar
sops --version
age --version
age-keygen --version 2>/dev/null || true   # age-keygen pode nao ter --version
```

---

## 7. Geracao da chave age no VPS (Plano A — fallback)

> Use **Plano A** apenas se SCP nao estiver disponivel. Em geral prefira o
> **Plano B** (§7-bis). O Plano A continua valido e suportado.

```bash
mkdir -p /root/.config/sops/age/
age-keygen -o /root/.config/sops/age/keys.txt
chmod 600 /root/.config/sops/age/keys.txt

# Extrair recipient publico (linha "# public key: age1...")
grep "# public key:" /root/.config/sops/age/keys.txt | awk '{print $4}'
```

Anote o `age1...` exibido — vai para o `.sops.yaml` (§8).

**Cofre offline da chave privada:**
```bash
cat /root/.config/sops/age/keys.txt
```
Copie o conteudo completo (inclui linha `AGE-SECRET-KEY-1...`) para seu
gestor de senhas ou pen drive criptografado. **Sem essa copia nao ha restore
possivel** se o VPS for perdido.

---

## 7-bis. Plano B — Geracao da chave age na maquina local (Windows)

> **OPCAO RECOMENDADA.** Reduz a superficie de exposicao da chave privada:
> ela nunca toca disco do VPS alem do `keys.txt` que VOCE copia
> deliberadamente. Trade-off: exige SCP funcionando e **higiene local
> rigorosa** (apagar `keys.txt` local apos backup no cofre — senao anula
> o ganho).

### Procedimento

1. **Gerar a chave em PowerShell local:**
   ```powershell
   New-Item -ItemType Directory -Force "$env:USERPROFILE\.sops\age" | Out-Null
   age-keygen -o "$env:USERPROFILE\.sops\age\keys.txt"
   ```

2. **Extrair recipient publico e atualizar `.sops.yaml`:**
   ```powershell
   Get-Content "$env:USERPROFILE\.sops\age\keys.txt" | Select-String "# public key:"
   # Saida: "# public key: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```
   Edite `.sops.yaml` substituindo `age1REPLACE_WITH_REAL_RECIPIENT` pelo
   valor real em **todas as 4 regras**. Commit e push:
   ```powershell
   git add .sops.yaml
   git commit -m "chore: definir recipient age real para SOPS"
   git push
   ```

3. **Mover IMEDIATAMENTE `keys.txt` para o cofre offline.** Abra o arquivo,
   copie o conteudo completo (inclui `AGE-SECRET-KEY-1...`), cole no gestor
   de senhas / pen drive criptografado. **Apague do disco local apos
   confirmacao visual de que o cofre tem a copia:**
   ```powershell
   Remove-Item "$env:USERPROFILE\.sops\age\keys.txt" -Force
   ```
   **NEGRITO: nao deixe `keys.txt` no disco local indefinidamente — senao
   o Plano B perde sentido.**

4. **(Opcional) Copiar a chave privada para o VPS via SCP**, somente se
   precisar desencriptar no proprio servidor (ex.: setup inicial):
   ```powershell
   # Recuperar do cofre temporariamente, copiar, apagar de novo
   ssh -i "$env:USERPROFILE\.ssh\id_ultra" root@2.25.137.241 "mkdir -p /root/.config/sops/age/"
   scp -i "$env:USERPROFILE\.ssh\id_ultra" "$env:USERPROFILE\.sops\age\keys.txt" `
     root@2.25.137.241:/root/.config/sops/age/keys.txt
   ssh -i "$env:USERPROFILE\.ssh\id_ultra" root@2.25.137.241 "chmod 600 /root/.config/sops/age/keys.txt"
   Remove-Item "$env:USERPROFILE\.sops\age\keys.txt" -Force
   ```
   Se a desencriptacao for feita sempre via Docker secrets ou no proprio
   deploy automatizado, pule este passo.

5. **Continuar do §8** (atualizacao do `.sops.yaml`) e §9 (encriptacao
   inicial). Se executou o passo 4, pode rodar `bash scripts/setup_secrets_vps.sh`
   no VPS — ele detectara a chave existente e ira direto para o passo de
   encriptacao.

### Trade-off documentado

| Vantagem                                        | Custo                                    |
| ----------------------------------------------- | ---------------------------------------- |
| Chave privada nunca em disco no VPS (se passo 4 nao for executado) | Exige SCP + cuidado para apagar local |
| Operador controla totalmente onde a chave vive  | Higiene local rigorosa obrigatoria       |

---

## 8. Atualizacao do `.sops.yaml` com o recipient real

```bash
# Edite .sops.yaml na raiz e substitua:
#   age1REPLACE_WITH_REAL_RECIPIENT  ->  age1xxxxxxxx... (o recipient real)
# em todas as 4 regras (creation_rules).

# Local (Windows):
notepad .sops.yaml

# Linux:
nano .sops.yaml

# Commit + push:
git add .sops.yaml
git commit -m "chore: definir recipient age real para SOPS"
git push
```

O recipient publico (`age1...`) **PODE** ser commitado — e equivalente a
uma chave publica GPG. A chave privada (`AGE-SECRET-KEY-1...`) **NUNCA**
pode entrar no git.

---

## 9. Encriptacao inicial dos segredos no VPS

> Atalho idempotente: `bash scripts/setup_secrets_vps.sh` no VPS automatiza
> os passos 1, 2, 4 e 5 da acao humana (instalacao do tooling, geracao da
> chave se ausente, encriptacao dos 5 arquivos e pausa para git commit
> manual). O passo 3 (cofre offline) continua manual.

> **NOTA TECNICA — sufixo `.enc.env` e path_regex sem `/`:** o `.env` produz
> `secrets/env.enc.env` (sufixo duplo), nao `secrets/env.enc`. Isso e
> necessario para que a regra dotenv do `.sops.yaml` case (`.*\.enc\.env$`)
> e cada KEY=VALUE seja encriptado em vez de tratar o arquivo como blob
> opaco. Adicionalmente, o `.sops.yaml` usa `path_regex` sem prefixo de
> diretorio (`.*\.enc\.env$`, nao `secrets/.*\.enc\.env$`) por conta de uma
> quirk do SOPS 3.8.1 que nao casa `path_regex` contendo `/`. A convencao
> de manter os encriptados em `secrets/` fica como disciplina humana,
> reforcada por este runbook e pelo `secrets/README.md`.

### Comandos exatos por arquivo (manual)

```bash
cd /opt/motor-expansao/app/

# 1. .env -> secrets/env.enc.env
cp .env secrets/env.enc.env && sops --input-type dotenv --output-type dotenv -e -i secrets/env.enc.env

# 2. Caddyfile -> secrets/Caddyfile.enc
cp Caddyfile secrets/Caddyfile.enc && sops --input-type binary --output-type binary -e -i secrets/Caddyfile.enc

# 3. authelia/configuration.yml -> secrets/authelia.configuration.enc.yaml
cp authelia/configuration.yml secrets/authelia.configuration.enc.yaml && sops -e -i secrets/authelia.configuration.enc.yaml

# 4. authelia/users_database.yml -> secrets/authelia.users_database.enc.yaml
cp authelia/users_database.yml secrets/authelia.users_database.enc.yaml && sops -e -i secrets/authelia.users_database.enc.yaml

# 5. authelia/db.sqlite3 -> secrets/authelia.db.sqlite3.enc
cp authelia/db.sqlite3 secrets/authelia.db.sqlite3.enc && sops --input-type binary --output-type binary -e -i secrets/authelia.db.sqlite3.enc

# Verificar diff antes de committar:
git add secrets/*.enc*
git status
git diff --cached --stat

# Commit (manual, fora do script):
git commit -m "chore: encriptar segredos iniciais (SOPS+age)"
git push
```

> **NOTA TECNICA — `cp` + `sops -e -i` (in-place):** o SOPS 3.8.1 casa
> `creation_rules.path_regex` contra o caminho do arquivo de **entrada**.
> Como os SRCs (`.env`, `Caddyfile`, etc.) nao tem sufixo `.enc.*`, o
> padrao antigo `sops -e SRC > DST` falhava com "no matching creation
> rules found". A correcao e copiar o SRC para o DST (que ja carrega o
> sufixo que casa a regra) e encriptar in-place com `-i`. O modo binary
> exige `--input-type/--output-type binary` porque a extensao `.enc` nao e
> reconhecida por SOPS; sem isso o conteudo seria tratado como JSON/YAML e
> corrompido.

> **Importante:** o `setup_secrets_vps.sh` faz tudo isso e pausa antes do
> commit para voce revisar o diff. O script **NAO** comita por seguranca.

---

## 10. Restore ponta a ponta em servidor zerado

> Cenario: VPS perdido. Voce tem `keys.txt` no cofre offline e acesso ao
> GitHub.

### 10.1. Provisionar servidor

1. Contratar VPS Ubuntu 22.04 (recomendado: Hostinger KVM4 ou equivalente,
   4 vCPU, 16 GB RAM, 200 GB NVMe).
2. Login como root: `ssh root@<novo-ip>`.

### 10.2. Instalar Docker e Compose plugin

```bash
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker --version
docker compose version
```

### 10.3. Instalar SOPS e age (§6)

### 10.4. Recuperar `keys.txt` do cofre offline

```bash
mkdir -p /root/.config/sops/age/
# Cole o conteudo do cofre no arquivo:
nano /root/.config/sops/age/keys.txt
chmod 600 /root/.config/sops/age/keys.txt
```

### 10.5. Clonar o repo

```bash
mkdir -p /opt/motor-expansao/
cd /opt/motor-expansao/
git clone https://github.com/<org>/motor-de-expansao.git app
cd app/
```

### 10.6. Desencriptar segredos para os destinos certos

```bash
cd /opt/motor-expansao/app/

# 1. .env
sops --input-type dotenv --output-type dotenv -d secrets/env.enc.env > .env
chmod 600 .env

# 2. Caddyfile
sops --input-type binary --output-type binary -d secrets/Caddyfile.enc > Caddyfile

# 3. Authelia configuration
sops -d secrets/authelia.configuration.enc.yaml > authelia/configuration.yml

# 4. Authelia users database
sops -d secrets/authelia.users_database.enc.yaml > authelia/users_database.yml

# 5. Authelia DB sqlite
sops --input-type binary --output-type binary -d secrets/authelia.db.sqlite3.enc \
  > authelia/db.sqlite3
```

> **O `secrets/env.enc.env` e' de 2026-10-25, ja' com a linha `MOTOR_DATABASE_URL`** (o banco foi
> ligado no site em 2026-10-23; ate' 2026-10-25 o cifrado era o de 2026-10-17, sem ela, e
> restaurado subia o web com o banco DESLIGADO, sem nada acusar). Ele fica velho de novo a cada
> mudanca do `.env`: no corte do P19 entram a nova `MOTOR_SENHA_INICIAL` e a
> `MOTOR_AUTENTICACAO_PROPRIA` (BLK-BANCO-04). Os pins `WEB_IMAGE`/`API_IMAGE` dele sao os de
> 2026-10-25: confira o digest vigente antes do `pull` (§10.8).

### 10.7. Recolocar dados de parquets

Opcoes:
- **Rapido:** SCP da maquina local: `scp -r data/outputs/ root@<novo-ip>:/opt/motor-expansao/data/outputs/`
- **Limpo:** regenerar conforme §13.
- **Obrigatorio antes do `up` (DEC-047):** `scp` de `data/perfis/BR/perfil.json` para `/opt/motor-expansao/data/perfil.json` (bind de ARQUIVO em `web`/`api`/`telegram-bot`: ausente, o Docker cria um diretorio e os containers falham com `"is a directory"`), e os diretorios dos outros mounts — `data/{staging,ibge,oportunidades}`, `cadastro/` e `logs/{acesso,caddy}` (`cadastro` e `logs/acesso` com `chown 1000:1000`).

```bash
mkdir -p /opt/motor-expansao/data/outputs/ /opt/motor-expansao/data/ultra/ /opt/motor-expansao/concorrentes/
# (Transferir conteudo via SCP ou regenerar — §13)
```

### 10.7-bis. Restaurar o banco (Postgres) ANTES de subir o resto

O volume do Postgres nao existe num servidor novo, e nenhum pipeline regenera o que mora
nele (usuarios, perfis e RBAC, sessoes, eventos): ele volta do **dump**. O passo a passo e'
o §10 do `docs/banco_deploy.md`, secao "Restaurar num servidor novo" — nao repetido aqui.
Em resumo, nesta ordem:

1. **O dump mais novo** (`banco_de_reservas_<carimbo>.dump` e o `.sha256` ao lado, conferido com
   `sha256sum -c` dentro da pasta, porque o `.sha256` guarda so' o nome): de
   `/home/deploy/backups/banco/diario/` do servidor antigo, se o disco sobreviveu, ou da
   copia off-box quando ela existir. **Em 2026-10-24, com a copia off-box desligada (§1), perder o
   disco e' perder os dumps junto** — sobra o snapshot semanal da Hostinger, que restaura o
   servidor inteiro, se ainda estiver ativo.
2. `docker compose -f docker-compose.prod.yml up -d postgres` — so' ele. O `.env`
   restaurado precisa dos `POSTGRES_*`, e a senha do dono e' gravada no primeiro boot.
3. **D20 secao 1** (os papeis `app`, `auditoria` e `etl`; as senhas dos dois primeiros sao
   `MOTOR_APP_DB_PASSWORD` e `MOTOR_AUDITORIA_DB_PASSWORD` no `.env`), depois o
   `pg_restore --no-owner` direto no `banco_de_reservas`, depois a **D20 secao 2**, e por fim
   `conferir` e `privilegios` com os dois OK e as contagens batendo com as de origem. O D20
   vive no repositorio `banco-de-reservas` (`sql/papeis-e-privilegios.md`), fora deste:
   tenha-o em maos.

Sem dump nenhum, o banco recomeca vazio pelos §5 a §7 do `docs/banco_deploy.md`
(migrations, D20 e os usuarios semeados de novo), e cada pessoa precisa de perfil outra vez.

### 10.8. Subir o stack

O compose nao builda nada no servidor (modo PULL por digest — DEC-022): o `.env`
restaurado precisa ter `WEB_IMAGE` e `API_IMAGE` pinados por digest do GHCR
(ver `docs/deploy_piloto_web.md` e `docs/deploy_api_bot.md`; se o pacote GHCR
for privado, `docker login ghcr.io` antes).

```bash
cd /opt/motor-expansao/app/
docker compose -f docker-compose.prod.yml pull
unset MOTOR_DATABASE_URL   # a do shell, mesmo vazia, venceria a do .env (o postgres ja' subiu no §10.7-bis)
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

Esperado: 6 containers `healthy`/`running` em ate 2 min (web, api, telegram-bot, postgres, caddy, authelia) — o `.env`
restaurado precisa dos `POSTGRES_*` (o compose aborta sem eles). Stack AR (`docker-compose.ar.yml`), tileserver
(`/opt/openmaptiles-infra`) e Valhalla (`/opt/valhalla-infra`) tem compose proprio e sobem a parte.

### 10.9. Validar (vai para §14)

---

## 11. Rotacao de chave age

> Quando rotacionar: suspeita de vazamento, troca de operador, politica
> periodica (ex.: anual).

### 11.1. Gerar nova chave

```bash
age-keygen -o /tmp/new-keys.txt
NEW_RECIPIENT=$(grep "# public key:" /tmp/new-keys.txt | awk '{print $4}')
echo "Novo recipient: $NEW_RECIPIENT"
```

### 11.2. Adicionar como recipient adicional no `.sops.yaml`

Edite `.sops.yaml` e adicione o novo `age:` em cada `creation_rule`:
```yaml
creation_rules:
  - path_regex: '.*\.enc\.yaml$'   # sem `/`: o SOPS 3.8.1 nao casa path_regex com barra (§9)
    age: >-
      age1OLD_RECIPIENT,
      age1NEW_RECIPIENT
  # ... (idem para as outras regras)
```

> Multiplos recipients separados por virgula no campo `age:` — ambos
> conseguem desencriptar.

### 11.3. Re-encriptar todos os arquivos

```bash
sops updatekeys secrets/env.enc.env
sops updatekeys secrets/Caddyfile.enc
sops updatekeys secrets/authelia.configuration.enc.yaml
sops updatekeys secrets/authelia.users_database.enc.yaml
sops updatekeys secrets/authelia.db.sqlite3.enc
git add .sops.yaml secrets/*.enc*
git commit -m "chore: rotacionar chave age (adicionar novo recipient)"
git push
```

### 11.4. Mover nova chave para cofre offline

Coloque `/tmp/new-keys.txt` no cofre e apague o original:
```bash
shred -u /tmp/new-keys.txt
```

### 11.5. Remover recipient antigo (apos confirmacao)

Apos confirmar que todos os colaboradores autorizados tem a nova chave,
edite `.sops.yaml`, remova o `age1OLD_RECIPIENT`, e rode novamente
`sops updatekeys secrets/*.enc*`. Commit, push.

---

## 12. Rotacao de segredos individuais

```bash
# Editar um segredo (abre editor com plaintext em memoria):
sops secrets/env.enc.env

# Salvar e sair re-encripta automaticamente.
git add secrets/env.enc.env
git commit -m "chore: rotacionar AUTHELIA_JWT_SECRET"
git push

# No VPS, regenerar o .env (o checkout /opt/motor-expansao/app esta parado: levar secrets/env.enc.env por scp em vez de git pull):
ssh root@2.25.137.241
cd /opt/motor-expansao/app/
sops --input-type dotenv --output-type dotenv -d secrets/env.enc.env > .env
docker compose -f docker-compose.prod.yml up -d authelia   # restart NAO rele o .env; so' o up -d aplica o segredo novo
```

> **Ressalva (2026-10-24): a metade do VPS nao funciona na producao de hoje.** O `sops -d` no VPS
> exige a chave age NO VPS, e ela nao esta' la' (o sops e a chave ficam na estacao do Vinicius). O
> fluxo vigente e' o inverso: trocar o valor direto no `.env` do VPS, sem imprimi-lo; `up -d` do
> servico que o le'; e, por ultimo, refazer o `secrets/env.enc.env` na estacao, lendo o `.env` do
> VPS por `ssh` direto para o `sops` (nunca em claro no disco nem na tela). Senha de papel do banco:
> secao "Trocar a senha de um papel" do `docs/banco_deploy.md`.

> **NUNCA** edite `secrets/*.enc*` com editor de texto direto — quebra o
> envelope SOPS. Sempre `sops <arquivo>`.

---

## 13. Regeneracao completa dos Parquets oficiais do M1

### 13.1. Pre-requisitos

- `data/ultra/Ultra.csv` presente (encoding `latin-1`, sep `;`).
- Python 3.11 + dependencias do `pyproject.toml` instaladas com o lock:
  `pip install -e . -c constraints.txt` (nao existe `requirements.txt`).
- Conexao com IBGE (download de malhas Censo 2022) — cache em
  `data/raw/ibge/` acelera reexecucao.

### 13.2. Sequencia canonica

```powershell
# 1. Base H3 res 7 — todas as UFs
python -m motor_expansao.pipelines.m1.base_h3_brasil
# Output: data/staging/brasil/uf=XX/hexagonos.parquet (27 particoes)
# Tempo esperado: ~25-40 min (depende de latencia IBGE)

# 2. Enriquecimento + score oficial
python -m motor_expansao.pipelines.m1.hex_enrichment
# Outputs:
#   data/staging/brasil_estrutural.parquet
#   data/staging/brasil_priorizados.parquet
#   data/staging/hexagonos_brasil_oportunidades.parquet
# Tempo esperado: ~15-25 min

# 3. Exports BI executivos
python -m motor_expansao.pipelines.m1.fase1_bi_exports
# Outputs:
#   data/outputs/hexagonos_brasil_dashboard.parquet
#   data/outputs/hexagonos_mapa_sample.parquet
#   data/outputs/top_oportunidades_resumo.csv
#   data/outputs/resumo_por_uf.csv
#   data/outputs/hexagonos_dashboard_enriquecido/uf=XX/parte-*.parquet (derivado)
# Tempo esperado: ~5-10 min
```

**Tempo total esperado:** ~45-75 min (rede IBGE como gargalo).

### 13.3. Validacao dos artefatos

```powershell
python scripts/check_artifacts.py
# Verifica presenca + shape minimo dos artefatos oficiais.
# Esperado: exit code 0, mensagens "OK" para cada arquivo.
```

### 13.4. (Opcional) Carteira e Plano — fora do M1 oficial

Se a carteira de mercado tambem precisar ser regenerada:
```powershell
python -m motor_expansao.pipelines.gerar_carteira_acionavel
python -m motor_expansao.pipelines.gerar_plano_expansao_curto_prazo
```
**Nao** faz parte do escopo oficial M1; rode somente se necessario.

### 13.5. Transferir para o VPS

Ver `docs/infra_producao.md` — secao "Atualizar parquets de dados".

---

## 14. Validacao pos-restore

Checklist apos `docker compose up -d`:

```bash
# 1. Containers
docker compose -f docker-compose.prod.yml ps
# Esperado: web, api, telegram-bot, postgres, caddy, authelia todos 'healthy' ou 'running'

# 2. Healthcheck do piloto web — POR DENTRO do container (este e' o caminho bom)
docker compose -f docker-compose.prod.yml exec web curl -fsS http://127.0.0.1:8899/api/health
# Esperado: HTTP 200 + {"status":"ok", "renda_fatores": {...}} — e SO' isso (a versao dos fatores entrou na E0 da renda). O /api/health foi EMUDECIDO pelo
# pentest Onda B #8: ele prova que o container responde, NAO que o dado chegou.
# O inventario de artefatos mora em /api/acessos/saude-artefatos (so' admin).
#
# NAO usar `curl -fsS https://piloto.ultra-expansao.tech/api/health` como verificacao: o
# `forward_auth` do Caddy vale para o SITE INTEIRO (ver o bloco do Caddyfile em
# docs/deploy_piloto_web.md §3) e nao ha matcher que isente `/api/health`, entao um curl
# anonimo recebe o redirect do Authelia — e como `-f` nao falha em 3xx, o comando sai com
# exit 0 e corpo VAZIO, que le como sucesso. Por fora, so' no navegador ja logado.

# 3. Login Authelia
# Abrir em navegador: https://auth.ultra-expansao.tech
# Esperado: tela de login do Authelia

# 4. Login no piloto (cookie via Authelia)
# Abrir em navegador: https://piloto.ultra-expansao.tech
# Esperado: redirect para Authelia, login, retorno ao SPA do piloto

# 5. Logs sem erro
docker compose -f docker-compose.prod.yml logs --tail=50 web
docker compose -f docker-compose.prod.yml logs --tail=50 api
docker compose -f docker-compose.prod.yml logs --tail=50 caddy
docker compose -f docker-compose.prod.yml logs --tail=50 authelia

# 6. Banco ligado no web, com a URL do papel `app` (o .env restaurado pode ter vindo sem ela —
#    §10.6). Conta a linha sem imprimir a senha: tem de dar 1. NUNCA tire o -c.
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' motor_expansao_web | grep -c '^MOTOR_DATABASE_URL=postgresql://app:'
```

### 14.1. Validacao de dados M1

```powershell
# Maquina local apos sincronizar parquets:
python scripts/check_artifacts.py
```

Contagens esperadas (baseline 2026-05-22):
- `hexagonos_brasil_dashboard.parquet`: ~500k linhas
- 27 particoes UF em `hexagonos_dashboard_enriquecido/`

---

## 15. Anti-vazamento — politica e verificacao

### 15.1. Regras canonicas

- `secrets/*.enc*` rastreados no git (versao encriptada).
- `secrets/*.dec`, `secrets/*.plain.*`, `*.age.key`, `key.txt`, `keys.txt`
  **gitignored** — `.gitignore` enforce.
- `.sops.yaml` com `encrypted_regex: ^.*$` em dotenv garante que **todos**
  os valores sao encriptados, nao apenas alguns.
- Recipient publico (`age1...`) pode entrar no git; chave privada
  (`AGE-SECRET-KEY-1...`) **nunca**.

### 15.2. Varredura gitleaks

O repo inclui `.gitleaks.toml` (allowlist de paths sem segredos: `data/`, `.venv/`,
`*.parquet`, `*.csv`, `*.png` etc.) e `.gitleaksignore` (fingerprints de falsos
positivos confirmados — placeholders de `.env.example` e nomes de coluna de
DataFrame). Use sempre essas duas configs para evitar runs de 2h em `data/`.

```powershell
# PowerShell, gitleaks binario nativo (release oficial):
gitleaks detect --no-git --source . --config .gitleaks.toml --gitleaks-ignore-path .gitleaksignore
# Exit code 0 = sem findings nao-ignorados.
```

```bash
# Bash, gitleaks binario nativo:
gitleaks detect --no-git --source . --config .gitleaks.toml --gitleaks-ignore-path .gitleaksignore
```

Alternativa via Docker (sem instalar gitleaks no host):

```bash
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect \
  --no-git --source /repo \
  --config /repo/.gitleaks.toml \
  --gitleaks-ignore-path /repo/.gitleaksignore
```

> Instalar `gitleaks.exe` no Windows: baixar release oficial em
> `https://github.com/gitleaks/gitleaks/releases/latest` (asset
> `gitleaks_X.Y.Z_windows_x64.zip`), extrair `gitleaks.exe` para
> `$env:USERPROFILE\tools\` e garantir que esta no `$env:PATH`.

### 15.3. Verificar gitignore

```bash
git check-ignore -v secrets/env.enc.env      # esperado: NAO ignorado (exit 1, nada)
git check-ignore -v secrets/env.dec      # esperado: ignorado
git check-ignore -v secrets/keys.txt     # esperado: ignorado (regra keys.txt cobre)
git check-ignore -v .sops.yaml           # esperado: NAO ignorado
```

---

## 16. Riscos conhecidos e cuidados

| Risco                                                              | Mitigacao                                         |
| ------------------------------------------------------------------ | ------------------------------------------------- |
| Chave privada age commitada acidentalmente                         | `.gitignore` cobre `*.age.key`, `key.txt`, `keys.txt`; gitleaks na pre-merge |
| Recipient publico placeholder em producao                          | Aprovacao humana antes do Builder; QA confere antes do merge |
| `authelia/db.sqlite3` muda a cada login (drift do encriptado)      | Aceitar drift; re-encriptar manualmente apos mudancas de usuarios |
| Editar `.enc.env` com editor errado (quebra envelope)              | SEMPRE usar `sops <arquivo>`; nunca `nano` direto |
| Tempo de regen Parquets dependente de IBGE (~45-75 min)            | Cache em `data/raw/ibge/`; rodar em janela de baixa latencia |
| **Plano B com `keys.txt` esquecido no disco local**                | **NEGRITO: apos copiar para cofre, executar `Remove-Item` imediatamente. Se ficar no disco, anula todo o ganho de seguranca do Plano B.** |
| Perda do unico recipient (sem rotacao multi-recipient)             | Manter copias da chave privada em 2 cofres distintos (gestor + pen drive offline) |
| Dumps do banco no MESMO disco do banco (copia off-box desligada)   | Decisao pendente do Felipe (destino e custo do restic); ate' la', o snapshot semanal da Hostinger. O monitor `banco` do healthcheck, quando instalado, lembra toda semana (`banco_offbox`) |

---

## Apendice — referencias internas

- `CLAUDE.md` §6 — Guardrails de VPS.
- `docs/infra_producao.md` — Acesso, monitoramento, atualizacao de codigo/parquets.
- `docs/banco_deploy.md` §10 — Backup e restore do banco, inclusive num servidor novo.
- `docs/m1_outputs_oficiais.md` — Contrato dos artefatos oficiais do M1.
- `scripts/setup_secrets_vps.sh` — Setup idempotente do tooling no VPS.
- `scripts/secrets_roundtrip_test.{sh,ps1}` — Validacao de roundtrip dummy.
- `.sops.yaml` — Regras de criptografia.
- `secrets/README.md` — Convencao de nomes no diretorio.
