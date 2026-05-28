# Infraestrutura de Produção — Motor de Expansão Ultra Academia

## Visão geral

| Componente | Valor |
|---|---|
| Provedor | Hostinger KVM4 |
| IP | 2.25.137.241 |
| Domínio | ultra-expansao.tech |
| Dashboard | https://dashboard.ultra-expansao.tech |
| Portal de login | https://auth.ultra-expansao.tech |
| SO | Ubuntu 22.04 LTS |
| Recursos | 4 vCPU, 16 GB RAM, 200 GB NVMe, 4 GB swap |

## Stack

- **Streamlit** — dashboard Python, container `motor_expansao_streamlit`
- **Caddy** — reverse proxy com TLS automático (Let's Encrypt), container `motor_expansao_caddy`
- **Authelia 4.38** — autenticação self-hosted (login + 2FA opcional), container `motor_expansao_authelia`

Todos os containers sobem com `docker compose -f docker-compose.prod.yml`.

## Acesso SSH

```bash
ssh -i ~/.ssh/id_ultra root@2.25.137.241
```

Chave privada local: `~/.ssh/id_ultra` (Windows: `C:\Users\Felipe Silva\.ssh\id_ultra`)

---

## Atualizar o código do dashboard

Quando houver commits novos no GitHub (`main`):

```bash
cd /opt/motor-expansao/app
git pull
docker compose -f docker-compose.prod.yml up -d --build streamlit
```

- `git pull` puxa as mudanças do repositório
- `--build streamlit` reconstrói só o container Streamlit (~1–2 min)
- Caddy e Authelia **não precisam reiniciar**
- Dados em `/opt/motor-expansao/data/outputs/` são preservados (bind mount read-only)

---

## Atualizar parquets de dados

Os parquets não estão no git. Para atualizar no servidor após rodar o pipeline localmente:

### Arquivo específico

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/ARQUIVO.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
```

### Diretório particionado (ex: enriquecido por UF)

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ultra" -r data/outputs/hexagonos_dashboard_enriquecido root@2.25.137.241:/opt/motor-expansao/data/outputs/
```

### Todos os outputs de uma vez

```powershell
# Atenção: rodar de dentro do diretório do projeto
cd "C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao"
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/brasil_estrutural.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/brasil_priorizados.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/hexagonos_brasil_dashboard.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/outputs/hexagonos_mapa_sample.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
scp -i "$env:USERPROFILE\.ssh\id_ultra" -r data/outputs/hexagonos_dashboard_enriquecido root@2.25.137.241:/opt/motor-expansao/data/outputs/
```

O Streamlit lê do volume na próxima requisição — **não é necessário reiniciar o container**.

---

## Integração com gymscraping (repo separado)

Quando o pipeline de gymscraping gerar novos parquets de concorrentes:

### Opção A — transferir do Windows (pipeline roda localmente)

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ultra" CAMINHO\DO\ARQUIVO.parquet root@2.25.137.241:/opt/motor-expansao/data/outputs/
```

### Opção B — pipeline roda direto no servidor (recomendado a longo prazo)

Instalar o repo de gymscraping em `/opt/gymscraping/` no mesmo servidor. O pipeline grava diretamente em `/opt/motor-expansao/data/outputs/`. Agendar via cron para rodadas noturnas (2h–5h BRT):

```bash
# Exemplo de cron (crontab -e no servidor)
0 2 * * * cd /opt/gymscraping && python scraper.py >> /var/log/gymscraping.log 2>&1
```

Verificar logs: `tail -f /var/log/gymscraping.log`

### Transferir data/ultra (base Ultra)

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ultra" -r data/ultra/ root@2.25.137.241:/opt/motor-expansao/data/ultra/
```

---

## Gerenciar usuários do dashboard

### Adicionar usuário

1. Gerar hash da senha no servidor:
   ```bash
   docker run --rm authelia/authelia:4.38 authelia crypto hash generate argon2 --password 'SenhaNova'
   ```
2. Editar o arquivo de usuários:
   ```bash
   nano /opt/motor-expansao/app/authelia/users_database.yml
   ```
3. Adicionar bloco:
   ```yaml
   novousuario:
     displayname: "Nome Completo"
     password: "$argon2id$v=19$... (hash gerado)"
     email: email@ultraacademia.com.br
     groups:
       - ultra_team
   ```
4. Reiniciar Authelia:
   ```bash
   cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml restart authelia
   ```

### Revogar usuário

1. Editar `authelia/users_database.yml` e remover o bloco do usuário
2. `docker compose -f docker-compose.prod.yml restart authelia`

### Trocar senha de usuário

1. Gerar novo hash (passo 1 acima)
2. Substituir o campo `password:` do usuário em `users_database.yml`
3. Reiniciar Authelia

---

## Monitoramento e manutenção

### Ver status dos containers

```bash
cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml ps
```

### Ver logs em tempo real

```bash
docker compose -f docker-compose.prod.yml logs -f streamlit
docker compose -f docker-compose.prod.yml logs -f caddy
docker compose -f docker-compose.prod.yml logs -f authelia
```

### Verificar uso de memória

```bash
docker stats --no-stream
free -h
```

### Reiniciar um serviço específico

```bash
docker compose -f docker-compose.prod.yml restart streamlit
docker compose -f docker-compose.prod.yml restart authelia
docker compose -f docker-compose.prod.yml restart caddy
```

### Reiniciar tudo

```bash
cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d
```

### Verificar espaço em disco

```bash
df -h /
du -sh /opt/motor-expansao/data/outputs/
```

---

## Renovação de certificados TLS

Caddy renova os certificados Let's Encrypt automaticamente. Nenhuma ação manual necessária. Para verificar:

```bash
docker compose -f docker-compose.prod.yml logs caddy | grep -i "certificate\|tls"
```

---

## Estrutura de diretórios no servidor

```
/opt/motor-expansao/
├── app/                          # Código-fonte (git clone)
│   ├── docker-compose.prod.yml
│   ├── Dockerfile.streamlit
│   ├── Caddyfile                 # NÃO está no git
│   ├── .env                      # NÃO está no git
│   ├── authelia/
│   │   ├── configuration.yml     # NÃO está no git
│   │   ├── users_database.yml    # NÃO está no git
│   │   └── db.sqlite3            # banco de sessões Authelia
│   ├── streamlit_app.py
│   ├── src/
│   └── dashboard/
└── data/
    ├── outputs/                  # Parquets do M1 (~1,6 GB)
    │   ├── hexagonos_brasil_dashboard.parquet
    │   ├── hexagonos_dashboard_enriquecido/
    │   │   └── uf=XX/
    │   └── ...
    └── ultra/                    # Base Ultra (CSV legado)
```

### Arquivos que NÃO estão no git (existem apenas no servidor)

| Arquivo | Conteúdo |
|---|---|
| `app/Caddyfile` | Configuração do Caddy com domínio real |
| `app/.env` | Segredos Authelia |
| `app/authelia/configuration.yml` | Configuração Authelia com domínio real |
| `app/authelia/users_database.yml` | Usuários e hashes de senhas |
| `data/outputs/` | Todos os parquets (~1,6 GB) |
| `data/ultra/` | Base Ultra.csv |

**Importante:** antes de qualquer `git pull`, confirme que esses arquivos não foram sobrescritos.

---

## Cuidados e boas práticas

- **Nunca commitar** `.env`, `Caddyfile`, `authelia/users_database.yml` ou `authelia/configuration.yml` com dados reais
- **Backup dos parquets:** manter cópia local em `data/outputs/` na máquina de desenvolvimento
- **Scrapers M2/M3:** agendar em janela noturna 2h–5h BRT para não competir com usuários ativos
- **Memória:** limite de 10 GB no container Streamlit + 4 GB swap; monitorar com `docker stats` se houver lentidão
- **Atualizações de sistema:** rodar mensalmente `apt-get update && apt-get upgrade -y` no servidor
