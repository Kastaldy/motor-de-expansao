# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-OPS-01-FU4 — Corrigir `encrypt_one` no `scripts/setup_secrets_vps.sh`.**

A função `encrypt_one` (linhas 128-154) encripta com `sops -e "${src}" > "${dst}"` (e variantes `--input-type/--output-type ... -e "${src}" > "${dst}"`), ou seja, lê o SRC fora de `secrets/` e redireciona para o DST. No SOPS 3.8.1 isso falha com "no matching creation rules found", pelo mesmo defeito 3 já documentado: o SOPS casa `path_regex` contra o **caminho do arquivo de entrada (SRC)**, e as regras do `.sops.yaml` casam apenas por sufixo `*.enc.*`/`*.enc` — que os SRCs (`.env`, `Caddyfile`, `authelia/configuration.yml`, etc.) não possuem. O workaround manual usado no fechamento real de 2026-05-29 foi `cp SRC DST && sops -e -i DST` (encriptação in-place: o nome do DST já carrega o sufixo que casa a regra). A correção deste bloco é trocar o padrão de cada um dos 3 ramos do `case` por `cp SRC DST && sops [flags] -e -i DST`, com guarda de erro que remove o DST se a encriptação falhar (para nunca deixar plaintext em `secrets/`).

## Objetivo
Reescrever `encrypt_one` para encriptar in-place (`cp SRC DST && sops -e -i DST`) com guarda que apaga o DST em caso de falha, eliminando o erro "no matching creation rules found" no SOPS 3.8.1.

## Escopo permitido
- Editar apenas a função `encrypt_one` (linhas ~128-154) de `scripts/setup_secrets_vps.sh`, trocando o padrão de redirecionamento pelo padrão in-place com `cp` + `sops -e -i` + guarda de erro.
- Decidir (Planner) se cada modo (`dotenv`/`binary`/`yaml`) ainda precisa de `--input-type/--output-type` explícitos no comando `-i`, ou se a inferência por extensão do DST basta. Ver "Pontos a resolver pelo Planner" abaixo.
- Ajuste paralelo no `docs/backup_restore.md` (bloco "Comandos exatos por arquivo (manual)", linhas ~291-318): os comandos 3 e 4 (e potencialmente 1, 2, 5) ainda mostram `sops -e SRC > DST`, padrão quebrado idêntico. Atualizar para refletir o padrão correto (`cp` + `sops -e -i`) e/ou registrar a nota da quirk. Manter o doc consistente com o script.
- Não alterar as 5 chamadas a `encrypt_one` (linhas 156-160): os SRC/DST/modo permanecem; só muda a implementação interna.

## Fora de escopo
- Não tocar `.sops.yaml` (as `creation_rules` já estão corretas — casam por sufixo; defeitos 3-5 já corrigidos).
- Não tocar M1, `score_priorizacao`, `hex_score_estrutural`, carteira, plano, ou qualquer artefato oficial. Esta tarefa não os toca.
- Não executar o script no VPS. Não rodar `sops`/`age`. Não manipular nenhum segredo real. A correção é só texto do script (e do doc).
- Não alterar os passos 1-4, 6, 7 do script (instalação, geração de chave, pausas, staging, lembrete).
- Não mudar os nomes de DST nem a ordem das 5 chamadas.
- Não expandir para outros scripts (`secrets_roundtrip_test.*`) — fora deste bloco.

## Arquivos que devem ser lidos
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\scripts\setup_secrets_vps.sh`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\.sops.yaml`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\docs\backup_restore.md` (foco no bloco "Comandos exatos por arquivo (manual)", linhas ~289-318)

## Arquivos que podem ser alterados
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\scripts\setup_secrets_vps.sh` (somente a função `encrypt_one`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\docs\backup_restore.md` (somente o bloco de comandos manuais e, se necessário, nota explicativa adjacente)

## Critérios de aceite
- `encrypt_one` usa o padrão `cp "${src}" "${dst}" && sops [flags] -e -i "${dst}"` em todos os 3 modos (`dotenv`, `binary`, `yaml`), nunca mais `sops -e "${src}" > "${dst}"`.
- Existe guarda de erro: se `sops -e -i "${dst}"` falhar, o script faz `rm -f "${dst}"` (não deixa plaintext copiado em `secrets/`) e em seguida sinaliza falha. Com `set -euo pipefail` ativo, definir explicitamente que o script deve **abortar limpando o DST** — ex.: `if ! sops ... -e -i "${dst}"; then rm -f "${dst}"; echo "ERRO ..." >&2; return 1; fi` (ou padrão equivalente que não deixe lixo nem aborte antes do `rm`). O `cp` também deve ser protegido: se `cp` falhar, não tentar `sops`.
- O comportamento de tipo é preservado: o conteúdo encriptado de cada DST mantém o tipo esperado (dotenv KEY=VALUE encriptado valor-a-valor para `env.enc.env`; YAML estruturado para `*.enc.yaml`; binário opaco para `Caddyfile.enc` e `authelia.db.sqlite3.enc`).
- As 5 chamadas (linhas 156-160) permanecem inalteradas e continuam coerentes com a nova implementação.
- O bloco de comandos manuais em `docs/backup_restore.md` reflete o mesmo padrão correto (sem `sops -e SRC > DST`).
- Nenhum segredo em texto puro aparece no script, no doc, no diff ou em qualquer log.
- O script continua válido em bash (`bash -n scripts/setup_secrets_vps.sh` passa) e respeita `set -euo pipefail`.

## Criticidade classificada
média

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA

## Riscos identificados
- **Inferência de tipo com `-i` (PONTO A RESOLVER PELO PLANNER, não pelo Orchestrator):** com `sops -e -i DST`, o SOPS infere o tipo pela extensão do DST. Verificar caso a caso se ainda é necessário passar `--input-type/--output-type` explícitos:
  - `env.enc.env` termina em `.env` → SOPS pode inferir dotenv automaticamente; a regra `.*\.enc\.env$` tem `encrypted_regex: '^.*$'`. Avaliar se manter `--input-type dotenv --output-type dotenv` no `-i` é necessário/seguro.
  - `Caddyfile.enc` e `authelia.db.sqlite3.enc` terminam em `.enc` → SOPS trata como binário? Avaliar se ainda precisa `--input-type binary --output-type binary` no `-i` para não corromper conteúdo.
  - `*.enc.yaml` → inferência yaml deve bastar (modo `yaml` hoje não passa flags).
  Decisão sobre essas flags é do Planner/Builder; documentar a escolha.
- `set -euo pipefail` está ativo: um `sops` que falhe abortaria o script. A guarda precisa capturar a falha (`if ! sops ...; then ...`) ANTES que o `set -e` mate o script, garantindo que o `rm -f "${dst}"` rode e que então o script termine com erro limpo (sem DST plaintext órfão em `secrets/`).
- `cp` pode falhar (permissão, disco): proteger também o `cp` para não chamar `sops` sobre um DST inexistente/parcial.
- Idempotência: rodar o script duas vezes faz `cp` sobre um DST já encriptado, sobrescrevendo com a versão em claro do SRC antes do `sops -e -i` — isso é o comportamento esperado (re-encripta do SRC original), mas confirmar que não há corrida onde o DST encriptado anterior seja lido como SRC.
- Doc e script podem divergir se só um for corrigido; manter ambos no mesmo padrão (escopo já inclui o doc).

## Guardrails ativos
- Builder NÃO toca o VPS e NÃO manipula segredos reais; este script roda no VPS por humano. A correção é apenas no texto do script e do doc.
- Nenhum segredo em texto puro entra em handoff/log/commit.
- Não tocar M1/score/artefatos oficiais — esta tarefa não os toca (CLAUDE.md §5, guardrail permanente).
- GUARDRAIL ABSOLUTO (CLAUDE.md §6): nunca executar comando no VPS via MCP/SSH sem confirmação explícita por comando. Não aplicável a esta correção textual, mas reforçado.
- NÃO atualizar `tasks/current_task.md` (o orquestrador faz isso).
