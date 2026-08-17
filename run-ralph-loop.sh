#!/usr/bin/env bash
# Ralph loop — /run-cycle AUTONOMO para blocos "loop-safe" do Motor de Expansao.
# Roda DENTRO do container isolado (Dockerfile.loop). SEM humano no loop.
#
# Rede de seguranca (substitui o humano):
#   1) aborta se houver credencial sensivel no ambiente (VPS/Growth API/ClickUp-write/deploy);
#   2) GUARD de M1/VPS apos cada iteracao (scripts/loop_guard.py) -> aborta se um commit do loop
#      tocou caminho proibido (config.py/score/pesos/pipelines m1/VPS/deploy/segredo/.env);
#   3) os testes (ruff + pytest) sao o gate de correcao, sem bypass (o QA re-roda);
#   4) o container nao tem chave de VPS/ClickUp -> nao consegue deployar nem escrever em producao.
# O loop commita por path no branch atual e NUNCA faz merge/push/deploy dentro do container. O PR
# resultante auto-mergeia (Baixa/Media, 4 checks de CI verdes) ou segue por label humana (Alta/Critica)
# depois, fora do container — ver DEC-016 / docs/portao_merge_orq21.md. Deploy segue sempre manual.
set -uo pipefail

MAX_ITERS="${MAX_ITERS:-10}"
BASE_REF="$(git rev-parse HEAD)"   # ponto de partida para o guard de M1/VPS

# --- Rede de seguranca 1: nenhuma credencial sensivel no container -----------------------------
# BLK-SEC-05: alem de VPS/deploy, tambem barra segredos de CI (GH_TOKEN/AUTO_MERGE_PAT)
# e de producao da API/Authelia (o loop e credential-free; so CLAUDE_CODE_OAUTH_TOKEN).
# Nomes ESPECIFICOS de proposito: um `API_` cru pegaria config benigna (API_ENVIRONMENT).
if env | grep -Eiq 'VPS_|SSH_PRIVATE_KEY|CLICKUP_WRITE|DEPLOY_KEY|GROWTH_API_|_TOKEN_PROD|GH_TOKEN|GITHUB_TOKEN|AUTO_MERGE_PAT|AUTHELIA_|API_TELEGRAM_TOKEN|API_BOT_SENHA|API_TOKENS|API_API_CALL_TOKEN'; then
  echo "ABORT: credencial sensivel detectada no container (VPS/Growth API/ClickUp/deploy/CI/API prod)."
  echo "       O loop e credential-free: remova-a do ambiente antes de rodar."
  exit 1
fi

# --- Auth: assinatura via CLAUDE_CODE_OAUTH_TOKEN ('claude setup-token' no host). NAO API key. --
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "AVISO: ANTHROPIC_API_KEY esta setada e TEM PRECEDENCIA — isso cobraria via API, nao pela"
  echo "       assinatura. Para usar o plano: 'unset ANTHROPIC_API_KEY' e use CLAUDE_CODE_OAUTH_TOKEN."
fi
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ABORT: sem autenticacao. Gere um token no host com 'claude setup-token' e passe como"
  echo "       CLAUDE_CODE_OAUTH_TOKEN ao 'docker run'."
  exit 1
fi

# Garante o pacote editavel apontando para o volume montado (deps ja estao na imagem).
pip install -e . --no-deps >/dev/null 2>&1 || true

# Limpa sinais de RODADAS ANTERIORES antes de comecar. LOOP_DONE e RELATORIO-BLOQUEIO.md sao
# gitignored e persistem no volume entre rodadas; sem isso, um sinal velho faz a nova rodada
# encerrar na iteracao 1 (bug observado em 2026-06-13).
rm -f LOOP_DONE RELATORIO-BLOQUEIO.md
echo "Sinais de rodada anterior limpos (LOOP_DONE / RELATORIO-BLOQUEIO.md)."

PROMPT='/run-cycle [MODO LOOP AUTONOMO — sem humano no loop]
Trabalhe UM bloco BLK-* por vez do tasks/backlog.md, SOMENTE blocos marcados "Autonomia: loop-safe".
Ignore TOTALMENTE qualquer bloco SEM esse marcador (sao trabalho futuro/manual — nao entram no loop).
SELECAO por completed.md (BLK-ORQ-24): tasks/completed.md e a FONTE UNICA de conclusao. Antes de
escolher um bloco, cheque a conclusao de forma ESTRUTURAL, nao por substring:
"python scripts/housekeeping_move_block.py <BLK-ID> --is-done" sai 0 se o bloco JA esta concluido
(heading "### <BLK-ID>" em completed.md, com fronteira de palavra) -> nesse caso PULE o bloco, MESMO
que ele ainda apareca integro (com heading e marcador loop-safe) em tasks/backlog.md (no modo
auto-merge o stub do backlog e DIFERIDO ate o PR de housekeeping em lote). NAO decida conclusao por
grep de mencao: completed.md cita blocos AINDA ABERTOS em prosa ("Sucessor: BLK-X", "Proximo
recomendado: BLK-Y") e um teste de substring PULARIA para sempre um bloco loop-safe aberto. Reia o
completed.md do checkout ATUAL antes de cada selecao (a routine clona fresco a cada run; NUNCA use
cache de sessao anterior).
Respeite "Depende de": so inicie um bloco cujas dependencias JA estao em tasks/completed.md; se uma
dependencia ainda nao fechou, pule esse bloco nesta passada. Esteira Planner->Builder->QA.
NESTE MODO o gate de APROVACAO HUMANA dos blocos Alta e SUBSTITUIDO pelo guard automatico:
o bloco SO pode ser READ-ONLY sobre o M1 e NAO pode tocar VPS/deploy/segredos nem persistir PII.
Se o plano exigir alterar M1 (config.py/score/pesos/artefatos oficiais/pipelines/m1), VPS/SSH/deploy,
.env/segredos ou gravar PII em disco -> NAO execute: pule o bloco e registre o motivo em
RELATORIO-BLOQUEIO.md. Consuma os parquets ja existentes em data/staging (NAO faca ingestao ao vivo
na Growth API — o container nao tem credencial). Rode "ruff check ." e "pytest -q" (gate unico no QA,
SEM bypass); NAO avance com teste vermelho. Commit POR PATH no branch atual.
HOUSEKEEPING no modo auto-merge (BLK-ORQ-24): NAO edite tasks/backlog.md ao fechar o bloco (NAO rode
o housekeeping_move_block.py). O PR do ciclo leva SO codigo + testes + o append em tasks/completed.md
(que o guard trata como LIMPO -> auto-mergeia). backlog.md e GOVERNANCA no guard: inclui-lo forcaria
label humana e o PR nao auto-mergearia. A remocao do bloco do backlog fica para o PR de housekeeping
em lote (humano). NUNCA merge/push/deploy; NUNCA escreva no ClickUp ou na VPS. Quando TODOS os blocos
loop-safe ainda NAO concluidos estiverem cobertos (nada novo a fazer) e a suite estiver verde, crie o
arquivo LOOP_DONE na raiz e pare. Se o MESMO erro persistir por 3 tentativas, pare e escreva
RELATORIO-BLOQUEIO.md.'

for i in $(seq 1 "$MAX_ITERS"); do
  if [ -f LOOP_DONE ]; then echo "LOOP_DONE presente — encerrando."; break; fi
  if [ -f RELATORIO-BLOQUEIO.md ]; then echo "RELATORIO-BLOQUEIO.md presente — encerrando."; break; fi
  echo "================ Ralph loop — iteracao $i/$MAX_ITERS ================"

  claude --dangerously-skip-permissions -p "$PROMPT" \
    || echo "(iteracao $i retornou codigo de erro; o loop segue)"

  # --- Rede de seguranca 2: guard de M1/VPS sobre o que o loop commitou nesta branch ----------
  if ! python scripts/loop_guard.py --base "$BASE_REF"; then
    echo "ABORT: guard detectou alteracao PROIBIDA (M1/score/config/VPS/segredo). Encerrando."
    {
      echo "# RELATORIO DE BLOQUEIO — guard de M1/VPS (iteracao $i)"
      echo ""
      echo "O loop tentou alterar um caminho proibido para o modo autonomo."
      echo "Revise antes de qualquer merge:  git diff $BASE_REF...HEAD"
      echo "Caminhos proibidos: config.py, src/motor_expansao/pipelines/m1/, *scoring*,"
      echo "artefatos M1 (brasil_*, hexagonos_brasil*), deploy/, Dockerfile.{web,api},"
      echo "docker-compose*, Caddyfile*, authelia/, .env*, secrets/, .github/workflows/."
    } >> RELATORIO-BLOQUEIO.md
    break
  fi
done

echo "Ralph loop finalizado apos $i iteracao(oes). REVISE o branch ANTES de qualquer merge/deploy."
