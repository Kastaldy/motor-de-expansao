# Consultas úteis — banco e operação

> Registro dos **comandos reutilizáveis** para puxar informação relevante do sistema em produção.
> Duas partes: **A) Banco de dados** (SELECT sobre `banco_de_reservas`) e **B) Operação** (estado
> da infra: migrations aplicadas, imagem no ar, saúde). Tudo aqui é **read-only**. A execução na
> VPS é manual (CLAUDE.md §6): confirme cada comando.
>
> Mapa de schema por trás das queries: as migrations em `src/motor_expansao/db/migracoes/` (os
> produtores de evento estão em `src/motor_expansao/db/eventos.py` e `.../usuarios.py`).

---

## Pré-requisito — acesso à VPS

Os comandos abaixo assumem acesso SSH à VPS de produção como o usuário `deploy` — cada operador
com a **sua própria** chave (onboarding e política em
[acesso_deploy_colaborador.md](acesso_deploy_colaborador.md)). Para não repetir a chave em cada
linha, defina um alias uma vez no seu `~/.ssh/config`:

```
Host motor-vps
    HostName 2.25.137.241
    User deploy
    IdentityFile ~/.ssh/SUA-CHAVE-DE-DEPLOY
```

Assim todos os comandos usam `ssh motor-vps`. (Sem o alias, troque cada `ssh motor-vps` por
`ssh -i ~/.ssh/SUA-CHAVE deploy@2.25.137.241`.) Cada comando na VPS exige a **sua** confirmação
(CLAUDE.md §6).

---

# A. Banco de dados

## O que está no banco — e o que não está

- O banco guarda: **eventos de negócio e de conta** (`eventos`), **sessões** (`sessoes`),
  **usuários/perfis/permissões** e o **histórico de permissões** (`perfil_permissoes_historico`).
- A **navegação fina da aba "Acessos"** (heatmap, abas visitadas, rota + latência, IP por
  requisição) **não está no banco** — vive em arquivos JSONL de 90 dias (ver a seção da trilha).
  No banco, "acesso" = os eventos `login` / `logout` / `login.recusado`.
- Senha nunca aparece em claro: só hashes (`senha_hash`, `token_hash_sessao`, `token_hash_ticket`).

## O runner (`motorq`)

Defina uma vez por terminal. Cada consulta vai pela entrada-padrão (heredoc). Roda `psql`
**dentro** do container `postgres` (socket local, sem senha), como `reservas_owner`, sobre
`banco_de_reservas`:

```bash
motorq() {
  ssh motor-vps \
    'cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml exec -T postgres psql -U reservas_owner -d banco_de_reservas -P pager=off -v ON_ERROR_STOP=1'
}
```

Uso:

```bash
motorq <<'SQL'
SELECT tipo, count(*) FROM eventos GROUP BY tipo ORDER BY 2 DESC;
SQL
```

- **Linhas largas:** comece a consulta com `\x on` (formato vertical).
- **Exportar CSV:** troque `-P pager=off` por `--csv` na definição do `motorq`, ou use
  `\copy (SELECT ...) to stdout csv header` dentro do heredoc.
- **Segurança:** só cole `SELECT` (e `\x` / `\copy ... to stdout`). O `reservas_owner` é **dono**
  do schema — um `UPDATE`/`DELETE` colado aqui escreve de verdade. Para só ler, não há risco.

## A1. Acessos (login / logout)

**Logins e logouts num período (linha a linha).** Ajuste as datas:

```sql
SELECT e.criado_em_evento AS quando,
       coalesce(u.login_usuario, '(conta removida/inexistente)') AS usuario,
       e.tipo
FROM eventos e
LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
WHERE e.tipo IN ('login','logout')
  AND e.criado_em_evento >= '2026-11-01'
  AND e.criado_em_evento <  '2026-12-01'
ORDER BY e.criado_em_evento DESC;
```

**Logins por pessoa nos últimos 30 dias (contagem + último):**

```sql
SELECT u.login_usuario, count(*) AS logins, max(e.criado_em_evento) AS ultimo
FROM eventos e JOIN usuarios u ON u.id_usuario = e.id_usuario
WHERE e.tipo = 'login' AND e.criado_em_evento >= now() - interval '30 days'
GROUP BY u.login_usuario ORDER BY logins DESC;
```

**Tentativas de login recusadas (contas sob pressão), últimos 7 dias:**

```sql
SELECT coalesce(u.login_usuario, '(usuario inexistente)') AS conta,
       count(*) AS recusas, max(e.criado_em_evento) AS ultima
FROM eventos e LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
WHERE e.tipo = 'login.recusado' AND e.criado_em_evento >= now() - interval '7 days'
GROUP BY u.login_usuario ORDER BY recusas DESC;
```

> Tentativa contra usuário **inexistente** grava `id_usuario` NULL; o login digitado e o IP **não**
> são gravados no banco (só na trilha JSONL).

**Último login de cada usuário ativo** (deriva de `eventos` — não existe coluna `ultimo_login`):

```sql
SELECT u.login_usuario, max(e.criado_em_evento) AS ultimo_login
FROM usuarios u
LEFT JOIN eventos e ON e.id_usuario = u.id_usuario AND e.tipo = 'login'
WHERE u.ativo
GROUP BY u.login_usuario ORDER BY ultimo_login DESC NULLS LAST;
```

## A2. Extração de documentos — quem extraiu e qual

**Relatórios/PDFs gerados — quem, qual tipo, id do PDF** (últimos 30 dias):

```sql
SELECT e.criado_em_evento AS quando,
       coalesce(u.login_usuario, '(sem sessao)') AS usuario,
       e.metadados->>'relatorio' AS relatorio,
       e.metadados->>'formato'   AS formato,
       e.metadados->>'report_id' AS report_id
FROM eventos e LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
WHERE e.tipo = 'relatorio.gerado' AND e.criado_em_evento >= now() - interval '30 days'
ORDER BY e.criado_em_evento DESC;
```

- `relatorio` ∈ {`municipal`, `pontual`, `simulador`, `comparacao`}; `formato` ∈ {`pdf`, `xlsx`}.
- O `report_id` (UUID) também é **carimbado no próprio PDF** — permite rastrear um PDF vazado de
  volta ao evento e à pessoa.

**Rastrear um PDF específico pelo `report_id` impresso nele:**

```sql
SELECT e.criado_em_evento, u.login_usuario, e.metadados
FROM eventos e LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
WHERE e.tipo = 'relatorio.gerado'
  AND e.metadados->>'report_id' = 'COLE-O-UUID-DO-PDF';
```

**Dossiês imobiliários baixados — quem baixou qual imóvel:**

```sql
SELECT e.criado_em_evento AS quando,
       coalesce(u.login_usuario, '(sem sessao)') AS usuario,
       e.metadados->>'imovel_id' AS imovel
FROM eventos e LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
WHERE e.tipo = 'dossie.baixado'
ORDER BY e.criado_em_evento DESC;
```

> Só o **download do PDF** do dossiê vira evento no banco. Abrir o dossiê na tela (sem baixar),
> filtrar, ver no mapa etc. ficam só na trilha JSONL de 90 dias.

**Simulações de viabilidade rodadas (com as premissas):**

```sql
SELECT e.criado_em_evento AS quando, coalesce(u.login_usuario,'(sem sessao)') AS usuario,
       e.metadados->>'m2'      AS m2,
       e.metadados->>'aluguel' AS aluguel,
       e.metadados->>'demanda' AS demanda
FROM eventos e LEFT JOIN usuarios u ON u.id_usuario = e.id_usuario
WHERE e.tipo = 'viabilidade.calculada' AND e.criado_em_evento >= now() - interval '30 days'
ORDER BY e.criado_em_evento DESC;
```

## A3. Movimentação de perfil e ações sobre contas

**Histórico de permissões de um perfil** (concedida/revogada/alterada/truncada):

```sql
SELECT h.registrado_em, h.acao, h.chave_permissao,
       coalesce(quem.login_usuario,'(sistema/seed)') AS registrado_por
FROM perfil_permissoes_historico h
LEFT JOIN usuarios quem ON quem.id_usuario = h.registrado_por
WHERE h.id_perfil = (SELECT id_perfil FROM perfis WHERE nome_perfil = 'COLE-O-NOME-DO-PERFIL')
ORDER BY h.registrado_em DESC;
```

**Quem trocou o perfil de quem (de → para):**

```sql
SELECT e.criado_em_evento AS quando,
       feito.login_usuario AS feito_por,
       alvo.login_usuario  AS alvo,
       e.metadados->>'de'   AS de,
       e.metadados->>'para' AS para
FROM eventos e
LEFT JOIN usuarios feito ON feito.id_usuario = e.id_usuario
LEFT JOIN usuarios alvo  ON alvo.id_usuario  = e.entidade_id
WHERE e.tipo = 'usuario.perfil_alterado'
ORDER BY e.criado_em_evento DESC;
```

**Todas as ações administrativas sobre contas** (criação, desativação/reativação, senha, país):

```sql
SELECT e.criado_em_evento AS quando, e.tipo,
       feito.login_usuario AS feito_por,
       alvo.login_usuario  AS alvo,
       e.metadados
FROM eventos e
LEFT JOIN usuarios feito ON feito.id_usuario = e.id_usuario
LEFT JOIN usuarios alvo  ON alvo.id_usuario  = e.entidade_id
WHERE e.tipo LIKE 'usuario.%'
ORDER BY e.criado_em_evento DESC;
```

> Nos eventos `usuario.*`: `id_usuario` (coluna) = **quem fez**; `entidade_id` = **quem sofreu**.

## A4. Sessões — quem logou, de onde, o que está vivo

**Sessões dos últimos 30 dias — quando logou, de onde, vivas vs encerradas:**

```sql
SELECT u.login_usuario,
       s.criado_em_sessao        AS logou_em,
       s.ultimo_acesso_em_sessao AS ultimo_uso,
       host(s.ip_sessao)         AS ip,
       s.user_agent_sessao       AS dispositivo,
       CASE WHEN s.revogada_em_sessao IS NULL AND s.expira_em_sessao > now()
            THEN 'viva' ELSE 'encerrada' END AS estado
FROM sessoes s JOIN usuarios u ON u.id_usuario = s.id_usuario
WHERE s.criado_em_sessao >= now() - interval '30 days'
ORDER BY s.criado_em_sessao DESC;
```

> IP e dispositivo são **anonimizados após 90 dias** (a linha fica; os campos viram NULL).

**Sessões vivas agora (quem está logado):**

```sql
SELECT u.login_usuario, s.criado_em_sessao AS logou_em, s.ultimo_acesso_em_sessao
FROM sessoes s JOIN usuarios u ON u.id_usuario = s.id_usuario
WHERE s.revogada_em_sessao IS NULL AND s.expira_em_sessao > now()
ORDER BY s.ultimo_acesso_em_sessao DESC;
```

## A5. Permissões e países

**Quem tem qual permissão hoje** (via perfil):

```sql
SELECT u.login_usuario, p.nome_perfil, pe.chave AS permissao
FROM usuarios u
JOIN perfis p             ON p.id_perfil    = u.id_perfil
JOIN perfil_permissoes pp ON pp.id_perfil   = p.id_perfil
JOIN permissoes pe        ON pe.id_permissao = pp.id_permissao
WHERE u.ativo
ORDER BY u.login_usuario, pe.chave;
```

**Permissões de um perfil só:**

```sql
SELECT pe.chave, pe.descricao_permissao
FROM perfil_permissoes pp
JOIN permissoes pe ON pe.id_permissao = pp.id_permissao
WHERE pp.id_perfil = (SELECT id_perfil FROM perfis WHERE nome_perfil = 'COLE-O-NOME-DO-PERFIL')
ORDER BY pe.chave;
```

**Países que cada pessoa pode acessar** (gate da DEC-081):

```sql
SELECT u.login_usuario,
       coalesce(string_agg(up.pais, ', ' ORDER BY up.pais), '(nenhum)') AS paises
FROM usuarios u
LEFT JOIN usuario_paises up ON up.id_usuario = u.id_usuario
WHERE u.ativo
GROUP BY u.login_usuario ORDER BY u.login_usuario;
```

## Trilha de acessos (arquivo JSONL — não é banco)

A aba **"Acessos"** do piloto (DEC-027) lê arquivos `acesso-AAAA-MM-DD.jsonl` (um por dia UTC,
retenção 90 dias), **não** o banco. Lá estão os detalhes que o banco não tem: rota, feature
("Gerou relatório pontual"), IP por requisição, latência, status HTTP, user-agent. A identidade
ali é o **texto do login** (`Remote-User`), não o `id_usuario`.

- **Jeito recomendado:** a própria aba **Acessos** no piloto (já faz os agregados, sem expor a
  query/conteúdo).
- **Arquivos crus** (volume de log do serviço `web`, env `MOTOR_ACESSO_LOG_DIR`). Para localizá-los:

```bash
ssh motor-vps \
  'cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml exec -T web sh -lc "echo DIR=\$MOTOR_ACESSO_LOG_DIR; find / -name \"acesso-*.jsonl\" 2>/dev/null | sort | tail"'
```

Com o caminho em mãos, um dia específico (ex. filtrando por usuário com `grep`):

```bash
ssh motor-vps \
  'cd /opt/motor-expansao/app && docker compose -f docker-compose.prod.yml exec -T web sh -lc "cat \$MOTOR_ACESSO_LOG_DIR/acesso-2026-11-09.jsonl"'
```

## Referência — os tipos de evento em `eventos`

`id_usuario` = quem fez a ação (pode ser NULL = sem sessão / sistema). O alvo, quando existe, vai
em `metadados` (chaves abaixo) — exceto nos `usuario.*`, onde o alvo é `entidade_id`.

| `tipo` | o que é | `metadados` (chaves) |
|---|---|---|
| `login` | login bem-sucedido | `origem` |
| `logout` | logout explícito | (NULL) |
| `login.recusado` | tentativa recusada | `origem`, `usuario_conhecido` |
| `relatorio.gerado` | gerou relatório/PDF | `report_id`, `relatorio`, `formato`, `origem` |
| `dossie.baixado` | baixou PDF do dossiê | `imovel_id`, `origem` |
| `imovel.visita_marcada` | marcou visita | `imovel_id`, `origem` |
| `imovel.visita_desmarcada` | desmarcou visita | `imovel_id`, `origem` |
| `viabilidade.calculada` | rodou o simulador | `m2`, `aluguel`, `demanda`, `origem` |
| `usuario.criado` | criou conta | `perfil` |
| `usuario.perfil_alterado` | trocou perfil de alguém | `de`, `para` |
| `usuario.desativado` / `usuario.reativado` | (des)ativou conta | (NULL) |
| `usuario.senha_definida` | a pessoa definiu a própria senha | `primeira_vez` |
| `usuario.senha_redefinida` | admin redefiniu senha de alguém | `tinha_senha_propria`, `validade_horas` |
| `usuario.troca_exigida` | admin forçou troca de senha | (NULL) |
| `usuario.pais_atribuido` / `usuario.pais_removido` | (des)atribuiu país | `pais` |

## O que o banco **não** responde (está só em arquivo/log, ou não é gravado)

- **Navegação fina da aba Acessos** (heatmap, abas visitadas, rota + query + latência + status):
  só na trilha JSONL (90 dias).
- **IP de quem logou/tentou logar nos eventos**: a coluna `eventos.ip` não é preenchida pelos
  produtores de login. IP só existe na trilha JSONL e em `sessoes.ip_sessao` (anonimizado após 90 dias).
- **Endereço/coordenada/parâmetro específico** de uma análise: fica fora de `eventos` por política;
  a query bruta só na trilha JSONL.
- **Gestos imobiliários** além de marcar/desmarcar visita (abrir aba, abrir imóvel, abrir dossiê,
  ver no mapa, filtrar): só na trilha JSONL.
- **Quem tentou logar com usuário inexistente**: grava `id_usuario` NULL; o login digitado e o IP
  não entram no banco.
- **Senhas em claro**: nunca — só hashes.

---

# B. Operação (estado do sistema)

Leituras reutilizáveis do estado da infra — não do conteúdo do banco. Todas read-only.

## B1. Estado das migrations (o que o banco já aplicou)

Lista cada migration aplicada vs o manifesto da imagem, e quantas estão registradas. Roda num
container efêmero da **imagem `web` que está no ar** (detectada na hora — sem digest fixo), na rede
do compose, com a credencial de **dono** montada do `.env`:

```bash
ssh motor-vps 'bash -s' <<'OPS'
cd /opt/motor-expansao/app
IMG="$(docker inspect motor_expansao_web --format '{{.Config.Image}}')"
NET="$(docker network ls --format '{{.Name}}' | grep -E '(^|_)app_net$' | head -1)"
docker run --rm --network "$NET" --env-file .env --entrypoint sh "$IMG" -c '
  export PGPASSWORD="${POSTGRES_OWNER_PASSWORD}"
  export MOTOR_DATABASE_URL_ADMIN="postgresql://${POSTGRES_OWNER_USER}@motor_expansao_postgres:5432/${POSTGRES_DB}"
  exec python -m motor_expansao.db estado'
OPS
```

> A senha de dono é **`POSTGRES_OWNER_PASSWORD`** (não o `POSTGRES_PASSWORD` legado do `.env`), e vai
> por `PGPASSWORD` (fora da URL — imune a `@ : / #`). Para **aplicar** uma migration pendente, troque
> `estado` por `aplicar --simular` → `aplicar` → `conferir` (isso **escreve** — ver `banco_deploy.md`).

## B2. O que está de fato no ar (revisão da imagem)

`success` no CI **não** garante imagem publicada (lição de 2026-09-11). Para confirmar qual commit
está rodando em cada serviço e comparar com a `main`:

```bash
ssh motor-vps 'bash -s' <<'OPS'
for c in motor_expansao_web motor_expansao_web_ar motor_expansao_api motor_expansao_telegram_bot; do
  rev=$(docker inspect "$c" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' 2>/dev/null)
  printf '%-30s %s\n' "$c" "${rev:0:12}"
done
OPS
```

Compare com o esperado: `git rev-parse origin/main` (os 12 primeiros dígitos). Divergência = a
imagem no ar é mais velha que a `main`.

## B3. Saúde e monitores

**Liveness (público, sem VPS)** — status + versão dos fatores de renda:

```bash
curl -s https://piloto.ultra-expansao.tech/api/health
curl -s https://piloto-ar.ultra-expansao.tech/api/health
```

**Inventário de artefatos / frescor dos monitores** (geoip, crescimento, mercado, banco, pins...):
está em `/api/acessos/saude-artefatos`, que é **autenticado** (401 sem sessão). A forma de ver é
pela aba **Acessos** do piloto.

**Verificador on-demand na VPS:** `/opt/motor-monitoring/healthcheck_vps.sh <sub>`, com `<sub>` ∈
{`containers`, `host`, `authelia`, `coleta`, `agregadores`, `crescimento`, `geoip`, `mercado`,
`pins`, `banco`, `test`}.

> **Atenção — não é leitura passiva:** o `healthcheck_vps.sh` **alerta via Telegram** na transição
> OK→FAIL (e avisa a recuperação em FAIL→OK). Rodar um subcomando pode disparar aviso no chat de
> ops. Cadências e runbook em `docs/infra_producao.md` ("Alertas automáticos").
