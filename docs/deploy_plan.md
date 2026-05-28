# Deploy — Motor de Expansão Dashboard

## Infraestrutura

- Servidor: Hostinger KVM4 (4 vCPU, 16 GB RAM, 200 GB NVMe, ~R$ 780/ano)
- Stack: Docker + Caddy (reverse proxy + TLS) + Authelia (autenticação) + Streamlit
- Autenticação: Authelia com tela de login própria; senhas individuais por usuário Ultra
- Domínio: incluso no plano Hostinger (substituir SEU_DOMINIO.COM.BR nos arquivos de config)

## Pré-condições

- [ ] Pagamento KVM4 realizado e servidor provisionado
- [ ] IP público anotado
- [ ] DNS: registros A `dashboard.SEU_DOMINIO.COM.BR` e `auth.SEU_DOMINIO.COM.BR` apontando para o IP
- [ ] Acesso SSH com chave pública configurada
- [ ] Lista de usuários Ultra e senhas definida (fora do repositório)

## Arquivos de configuração a personalizar antes do deploy

| Arquivo | O que substituir |
|---|---|
| `Caddyfile` | `SEU_DOMINIO.COM.BR` pelo domínio real |
| `authelia/configuration.yml` | `SEU_DOMINIO.COM.BR` pelo domínio real |
| `authelia/users_database.yml` | Usuários e hashes reais (não commitar) |
| `.env` (criado a partir de `.env.example`) | Segredos reais gerados com `openssl rand -hex 32` |

## Sequência de deploy (executar após contratação)

1. **Contratar o KVM4 na Hostinger.** Acessar hostinger.com.br, contratar plano KVM4 com cartão de crédito nacional. Anotar o IP público do servidor e o nome do domínio incluso.

2. **Apontar DNS do domínio para o IP do servidor.** No painel Hostinger → Domínios → DNS → criar dois registros A:
   - `dashboard.SEU_DOMINIO.COM.BR` → IP do servidor
   - `auth.SEU_DOMINIO.COM.BR` → IP do servidor
   Aguardar propagação (~5–30 min) e verificar com `nslookup dashboard.SEU_DOMINIO.COM.BR`.

3. **Acessar o servidor via SSH e instalar Docker.**
   ```bash
   ssh root@IP_DO_SERVIDOR
   apt-get update && apt-get install -y docker.io docker-compose-plugin curl
   systemctl enable --now docker
   ```

4. **Criar estrutura de diretórios no servidor.**
   ```bash
   mkdir -p /opt/motor-expansao/data/outputs
   mkdir -p /opt/motor-expansao/data/ultra
   mkdir -p /opt/motor-expansao/app
   ```

5. **Configurar swap de 4 GB no servidor (camada extra de segurança).**
   ```bash
   fallocate -l 4G /swapfile && chmod 600 /swapfile
   mkswap /swapfile && swapon /swapfile
   echo '/swapfile none swap sw 0 0' >> /etc/fstab
   ```

6. **Abrir portas 80 e 443 no firewall do provedor.** No painel Hostinger → Servidor → Firewall: abrir TCP 80 e TCP 443. Fechar porta 8501 se aberta. Manter porta 22 restrita a IPs conhecidos se possível.

7. **Verificar que `data/outputs/` existe localmente antes da transferência.**
   ```bash
   du -sh data/outputs/   # esperado: ~1,55–1,58 GB
   ```

8. **Transferir dados estáticos com rsync (máquina local → servidor).**
   ```bash
   rsync -avz --progress data/outputs/ root@IP_DO_SERVIDOR:/opt/motor-expansao/data/outputs/
   rsync -avz --progress data/ultra/ root@IP_DO_SERVIDOR:/opt/motor-expansao/data/ultra/
   ```
   Verificar no servidor: `du -sh /opt/motor-expansao/data/outputs/` (esperado: ~1,55–1,58 GB)

9. **Personalizar os arquivos de configuração localmente.**
   - Em `Caddyfile`: substituir `SEU_DOMINIO.COM.BR` pelo domínio real
   - Em `authelia/configuration.yml`: substituir `SEU_DOMINIO.COM.BR` pelo domínio real
   - Em `authelia/users_database.yml`: substituir usuários placeholder pelos reais (ver seção "Como adicionar usuário")
   - Copiar `.env.example` para `.env` e preencher `AUTHELIA_JWT_SECRET`, `AUTHELIA_SESSION_SECRET`, `AUTHELIA_STORAGE_ENCRYPTION_KEY` com saída de `openssl rand -hex 32`

10. **Transferir o código-fonte para o servidor (sem dados).**
    ```bash
    rsync -avz --progress --exclude='.git' --exclude='data/' \
      ./ root@IP_DO_SERVIDOR:/opt/motor-expansao/app/
    ```

11. **Verificar que os arquivos de configuração chegaram ao servidor.**
    ```bash
    ls /opt/motor-expansao/app/Caddyfile
    ls /opt/motor-expansao/app/authelia/configuration.yml
    ls /opt/motor-expansao/app/authelia/users_database.yml
    ls /opt/motor-expansao/app/.env
    ```

12. **Confirmar que o volume de dados aponta para o caminho absoluto correto.** O `docker-compose.prod.yml` já usa `/opt/motor-expansao/data/outputs` como caminho absoluto — nenhum ajuste adicional necessário.

13. **Buildar e subir os containers no servidor.**
    ```bash
    cd /opt/motor-expansao/app
    docker compose -f docker-compose.prod.yml up -d --build
    ```

14. **Aguardar o Streamlit ficar healthy (~45 segundos).**
    ```bash
    docker inspect motor_expansao_streamlit --format='{{.State.Health.Status}}'
    # Esperado: "healthy"
    docker compose -f docker-compose.prod.yml logs --tail=50 streamlit
    ```

15. **Verificar health do Caddy e Authelia.**
    ```bash
    docker compose -f docker-compose.prod.yml ps
    # Todos os 3 serviços devem estar Up
    docker compose -f docker-compose.prod.yml logs --tail=30 caddy
    docker compose -f docker-compose.prod.yml logs --tail=30 authelia
    ```

16. **Verificar acesso autenticado via browser.** Acessar `https://dashboard.SEU_DOMINIO.COM.BR` — deve redirecionar para `https://auth.SEU_DOMINIO.COM.BR` com formulário de login. Após autenticação, o dashboard deve carregar sem erros em todas as 4 abas.

17. **Verificar que a porta 8501 não está acessível diretamente.**
    ```bash
    curl -I http://IP_DO_SERVIDOR:8501
    # Esperado: Connection refused (ou timeout)
    ```

## Como adicionar/revogar usuário

### Adicionar
1. Gerar hash: `docker run authelia/authelia:latest authelia crypto hash generate argon2 --password 'SenhaDoUsuario'`
2. Adicionar entrada em `authelia/users_database.yml` no servidor com o hash gerado
3. Reiniciar: `docker compose -f docker-compose.prod.yml restart authelia`

### Revogar
1. Remover entrada de `authelia/users_database.yml` no servidor
2. Reiniciar: `docker compose -f docker-compose.prod.yml restart authelia`

## Validações pós-deploy

```bash
# 1. Health do Streamlit (dentro do container)
docker exec motor_expansao_streamlit curl -fsS http://127.0.0.1:8501/_stcore/health
# Esperado: HTTP 200

# 2. Portal Authelia acessível
curl -I https://auth.SEU_DOMINIO.COM.BR
# Esperado: HTTP/2 200 (página de login)

# 3. Dashboard redireciona para login quando sem sessão
curl -I https://dashboard.SEU_DOMINIO.COM.BR
# Esperado: HTTP/2 302 redirecionando para auth.SEU_DOMINIO.COM.BR

# 4. Porta 8501 fechada no host
curl -I http://IP_DO_SERVIDOR:8501
# Esperado: Connection refused

# 5. Dados presentes no volume
docker exec motor_expansao_streamlit du -sh /app/data/outputs/
# Esperado: ~1.5–1.6G

# 6. Uso de memória em idle
docker stats motor_expansao_streamlit --no-stream
# Esperado: abaixo de 1 GB em idle (antes de usuários ativos)

# 7. Swap configurado
ssh root@IP_DO_SERVIDOR "free -h"
# Esperado: Swap de 4 GB configurado

# 8. Logs sem erro de import
docker compose -f docker-compose.prod.yml logs streamlit | grep -i "error\|exception" | head -20
# Esperado: nenhuma linha de erro crítico no startup
```

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Caddy não emite certificado TLS porque DNS ainda não propagou | Verificar `nslookup` antes do `docker compose up`; se necessário, aguardar e reiniciar Caddy |
| Volume `/opt/motor-expansao/data/outputs` vazio no primeiro up | Verificar `du -sh` no servidor antes de subir (passo 8) |
| Authelia não sobe por segredo não preenchido no `.env` | Verificar `.env` com `cat .env` antes do `docker compose up` |
| Build lento por falta de `.dockerignore` | `.dockerignore` já criado — exclui `data/`, `tests/`, `docs/` e outros |
| OOM com múltiplos usuários simultâneos | `mem_limit: 10g` definido; swap de 4 GB configurado como camada extra |
| Concorrência com fases futuras (PostgreSQL + scrapers) | Scrapers M2/M3 devem ser agendados em janela noturna (2h–5h BRT) |
