# Repasse — logout por inatividade de 30 min para 2 h (Authelia da VPS)

> **Para quem vai executar.** Runbook curto e auto-contido. Cada comando roda **um de cada vez**,
> com confirmação explícita do Felipe ou do Vinicius antes de cada um (§6 do `CLAUDE.md`). Se
> qualquer saída vier diferente do previsto, **pare e chame quem repassou**.

**Estado:** executado na VPS em 17/10/2026; o backup cifrado (R1/R2) entrou no #461. **Origem:** emenda da DEC-067 (D2) de 14/10/2026, decidida por Vinicius — inatividade 30 min -> 2 h;
o teto absoluto de 8 h e a trava de toque de 5 min ficam como estão.

## Por que existe um passo manual

O código (`src/motor_expansao/db/sessoes.py`, `INATIVIDADE_MIN = 120`) só vale para a **sessão
própria** do P19, que só é consultada com `MOTOR_AUTENTICACAO_PROPRIA` ligada. **Hoje quem desloga
em produção é o Authelia**, e a configuração dele vive só na VPS
(`/opt/motor-expansao/app/authelia/configuration.yml`, gitignored). Sem este runbook, o merge do
código não muda nada para quem usa o piloto.

`secrets/authelia.configuration.enc.yaml` é só **cópia de backup** cifrada (SOPS). Nenhum deploy a
aplica — editá-la achando que resolve é falso positivo. Ela é atualizada **depois** (seção
"Depois: atualizar o backup cifrado", passos R1 e R2, após o passo 7b), senão um restore traz os
30 min de volta.

## Antes de começar — leia

- **O restart do Authelia DESLOGA TODO MUNDO**: BR, AR e o host `dashboard.`. O serviço é
  compartilhado, e as 2 h passam a valer **também para a instância AR** (não há como separar sem
  dividir o Authelia). Faça fora do horário de uso e avise a equipe antes.
- **Nunca `inactivity: 0`.** No Authelia 4.38 qualquer valor `<= 0` é coagido para **5 minutos**.
  Foi o incidente de 06/08/2026: ~4 h de rede deslogando a cada 5 min. O valor é `2h`, explícito.
- Com "lembrar de mim" marcado, o Authelia não aplica `inactivity` — isso não muda.
- Se o corte do P19 já tiver acontecido (BR autenticando pelo motor), o BR passa a seguir a
  constante do código, que entra na imagem `web` no próximo deploy por digest; o Authelia segue
  valendo para a AR. Este runbook continua necessário nos dois casos.

## Passos (um comando por vez)

Cada bloco abaixo tem **um** comando — é a unidade de cada confirmação do §6. Nenhum é encadeado
com `&&` ou `;`.

```bash
# 1. Entrar na pasta da aplicação
cd /opt/motor-expansao/app/
```

```bash
# 2. Conferir o valor atual (esperado: a linha `inactivity: 30m`, uma única ocorrência)
grep -n 'inactivity:' authelia/configuration.yml
```

```bash
# 3. Backup datado da configuração viva (anote o nome do arquivo criado: o 5b e o
#    restore usam a data dele)
cp -p authelia/configuration.yml authelia/configuration.yml.bak-$(date +%Y%m%d-%H%M%S)
```

```bash
# 4. Trocar 30m por 2h (só a chave `inactivity`; `expiration: 8h` e `remember_me: 8h` ficam)
sed -i 's/^\(\s*inactivity:\s*\)30m\s*$/\12h/' authelia/configuration.yml
```

```bash
# 5a. Conferir: tem de mostrar `inactivity: 2h`, com `expiration: 8h` e `remember_me: 8h` intactos
grep -n 'inactivity:\|expiration:\|remember_me:' authelia/configuration.yml
```

```bash
# 5b. Conferir: o diff contra o backup do passo 3 mostra SÓ a linha do `inactivity`
diff authelia/configuration.yml.bak-<data-do-passo-3> authelia/configuration.yml
```

```bash
# 6. Reiniciar o Authelia (DESLOGA TODOS, BR + AR + dashboard.)
docker compose -f docker-compose.prod.yml restart authelia
```

```bash
# 7a. Conferir que o container está de pé (estado `running`/`healthy`, sem `restarting`)
docker compose -f docker-compose.prod.yml ps authelia
```

```bash
# 7b. Conferir que subiu sem erro de configuração (nenhuma linha `level=error`/`fatal`)
docker compose -f docker-compose.prod.yml logs --tail=50 authelia
```

**Se o 7a ou o 7b mostrarem erro de configuração ou o container reiniciando:** restaurar o
backup do passo 3 (`cp -p authelia/configuration.yml.bak-<data> authelia/configuration.yml`, um
comando, com confirmação) e repetir o passo 6. Ninguém fica sem login por mais que o tempo de um
restart.

## Depois: atualizar o backup cifrado

Mesmo procedimento do `docs/backup_restore.md` (item 3 de "Comandos exatos por arquivo"), em dois
comandos separados; `sops -e` só precisa do recipient público do `.sops.yaml`:

```bash
# R1. Copiar a configuração viva para o caminho do backup (ainda EM CLARO; o R2 cifra no lugar)
cp authelia/configuration.yml secrets/authelia.configuration.enc.yaml
```

```bash
# R2. Cifrar no lugar (esperado: o arquivo passa a ter o bloco `sops:` e nenhum valor legível)
sops -e -i secrets/authelia.configuration.enc.yaml
```

Não pare entre o R1 e o R2: até o R2 rodar, o arquivo com nome de cifrado está em claro.

Levar o `secrets/authelia.configuration.enc.yaml` novo para o repositório (commit + PR), como nos
demais backups cifrados. Sem isso, um restore traz `inactivity: 30m` de volta.

## Verificação

1. Entrar no piloto, deixar a aba parada por ~45-60 min e voltar: a sessão continua.
2. Depois de ~2 h parado, qualquer ação mostra o pop-up "sessão encerrada" (`AvisoSessao`).
