# Acesso de deploy para colaborador (usuário `deploy` na VPS)

Runbook do acesso SSH **por pessoa** que permite a um colaborador deployar o Motor (BR e AR) e
atualizar os dados de produção do PC dele, sem usar a chave do Felipe e sem virar `root` nominal.

Aplicado em **2026-10-09** para o **Vini** (`@VinhoAbencoado`), no modelo decidido em 2026-07-23
(usuário dedicado, não "a chave dele no `root`"), para ter **log e revogação por pessoa**.

> **Guardrail CLAUDE.md §6 continua valendo:** execução na VPS é passo humano, comando a comando.
> O acesso dá *capacidade*; não dá *autorização* para rodar o que não foi combinado.
> Deploy segue **manual, por digest imutável** (`docs/deploy_piloto_web.md`, `docs/deploy_api_bot.md`).

---

## 1. O que o usuário `deploy` pode

| Capacidade | Como | Caminho |
|---|---|---|
| Subir/reiniciar containers, puxar imagem por digest | grupo `docker` (socket) | `/var/run/docker.sock` |
| Trocar o digest do deploy (`WEB_IMAGE` / `API_IMAGE`) | grupo `motor-ops`, `.env` em `660` | `/opt/motor-expansao/app/.env` |
| `scp` de parquets / `perfil.json` — **BR** | grupo `motor-ops`, `g+rwX` + `setgid` | `/opt/motor-expansao/data/**`, `/opt/motor-expansao/concorrentes` |
| `scp` de parquets / `perfil.json` — **AR** | idem | `/opt/motor-expansao-ar/data/**`, `/opt/motor-expansao-ar/concorrentes` |

Validado por teste real no dia da criação (`sudo -u deploy`): lê o `.env`, fala com o `docker`,
escreve em BR e AR, e arquivo novo nasce `deploy:motor-ops` (efeito do `setgid`).

**Não tem `sudo`** (`/etc/sudoers` intocado) e **não tem senha** (`passwd -l`; o sshd já está com
`PasswordAuthentication no`). Entra só pela chave pública instalada.

### O que ele NÃO deve tocar (não liberado de propósito)

- `/opt/motor-expansao/cadastro/` e `/opt/motor-expansao-ar/cadastro/` — `ubuntu:ubuntu`, arquivos `0600`.
  É onde vive o `acesso_abas.json` (controle de abas, **fail-closed**): sobrescrever por `scp` com
  outro dono derruba o controle de abas inteiro, **sem erro visível**.
- `/opt/motor-expansao/logs/acesso/` — `ubuntu`, `0700`, trilha de acesso (DEC-027), escrita do app.
- `authelia/`, `secrets/`, `Caddyfile` — ficam dentro de `/opt/motor-expansao/app/`, com permissão própria.

### Limites honestos deste modelo

- **`docker` ≡ `root` na prática** (quem fala com o socket monta `/` num container). A segmentação de
  arquivos acima **não** é contenção contra alguém mal-intencionado; o ganho real é **auditoria**
  (login próprio no `journalctl`/`lastlog`) e **revogação por pessoa** (§4).
- O `.env` de produção tem segredos (tokens do bot, etc.) e o `deploy` **lê**. Isso não amplia a
  exposição material — com o grupo `docker` dá para ler o ambiente de qualquer container —, mas é
  consequência aceita: quem recebe deploy recebe os segredos do deploy.
- O diretório `/opt/motor-expansao/app` ficou `2775` (group-write) porque editar o `.env` in-place
  cria arquivo temporário no diretório.

---

## 2. Onboarding (o que o Felipe roda, como `root`)

Já executado para o Vini, menos a chave. Sequência completa, para repetir com outra pessoa:

```bash
# 1. grupo + usuário (sem senha, sem sudo)
groupadd -f motor-ops
useradd -m -s /bin/bash -G docker,motor-ops <pessoa>
passwd -l <pessoa>

# 2. .env legível/gravável pelo grupo + setgid no dir do compose
chgrp motor-ops /opt/motor-expansao/app/.env && chmod 660 /opt/motor-expansao/app/.env
chgrp motor-ops /opt/motor-expansao/app     && chmod 2775 /opt/motor-expansao/app

# 3. dados BR + AR graváveis pelo grupo, com setgid para herdar o grupo
for D in /opt/motor-expansao/data /opt/motor-expansao/concorrentes \
         /opt/motor-expansao-ar/data /opt/motor-expansao-ar/concorrentes; do
  chgrp -R motor-ops "$D" && chmod -R g+rwX "$D" && find "$D" -type d -exec chmod g+s {} +
done

# 4. ~/.ssh pronto
install -d  -m 700 -o <pessoa> -g <pessoa> /home/<pessoa>/.ssh
install -m 600 -o <pessoa> -g <pessoa> /dev/null /home/<pessoa>/.ssh/authorized_keys

# 5. instalar a chave PÚBLICA que a pessoa enviou (só o .pub; privada NUNCA trafega)
printf '%s\n' 'ssh-ed25519 AAAA... comentario' >> /home/<pessoa>/.ssh/authorized_keys

# 6. conferir
id <pessoa>; ls -l /home/<pessoa>/.ssh/authorized_keys
```

O `sshd` não tem `AllowUsers`/`AllowGroups` — usuário novo loga sem mexer em config de SSH.

---

## 3. Setup no PC do colaborador

1. **Gerar o par de chaves** (sem passphrase — o servidor MCP não tem como responder prompt):
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ultra_deploy -N "" -C "<pessoa>@<maquina>"
   ```
   Enviar ao Felipe **apenas** o conteúdo de `~/.ssh/id_ultra_deploy.pub`.

2. **Bloco MCP** no `~/.claude.json` dele (mesmo servidor que o Felipe usa, com a chave e o
   usuário dele). Ajustar o caminho ao SO:
   ```json
   "mcpServers": {
     "ssh-vps-ultra": {
       "type": "stdio",
       "command": "npx",
       "args": ["-y", "@idletoaster/ssh-mcp-server"],
       "env": {
         "SSH_PRIVATE_KEY": "C:\Users\<usuario>\.ssh\id_ultra_deploy",
         "SSH_HOST": "2.25.137.241",
         "SSH_USER": "deploy"
       }
     }
   }
   ```

3. **Teste de fumaça** (fora do MCP, direto no terminal):
   ```bash
   ssh -i ~/.ssh/id_ultra_deploy deploy@2.25.137.241 \
     'cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml ps'
   ```

4. **GHCR não precisa de PAT**: as imagens `ghcr.io/kastaldy/motor-de-expansao/motor-expansao-{web,api}`
   são **públicas** (verificado em 2026-10-09 com token anônimo), então `docker compose pull` funciona
   sem `docker login`. Se a visibilidade do pacote virar privada, aí sim cada pessoa precisa de um PAT
   com `read:packages`.

5. **Deploy e dados**: seguir `docs/deploy_piloto_web.md` (web), `docs/deploy_api_bot.md` (api/bot) e
   `docs/infra_producao.md` (dados/manutenção), trocando `root@` por `deploy@` e `id_ultra_mcp` pela
   chave dele. O `perfil.json` continua sendo o único arquivo cuja ausência **derruba** o container
   (DEC-047).

---

## 4. Offboarding (revogação)

Ordem crescente de dureza — qualquer um dos dois primeiros já tira o acesso:

```bash
# tira só o login (mantém o usuário e os arquivos dele)
truncate -s 0 /home/<pessoa>/.ssh/authorized_keys

# tira a capacidade de deploy (sai do docker e do grupo de dados)
gpasswd -d <pessoa> docker; gpasswd -d <pessoa> motor-ops

# remove o usuário e o home
userdel -r <pessoa>
```

As permissões de grupo em `/opt/...` podem ficar — sem ninguém em `motor-ops`, elas não concedem nada.
Depois de revogar, considerar **rotacionar os segredos do `.env`** se a saída não foi amigável.
