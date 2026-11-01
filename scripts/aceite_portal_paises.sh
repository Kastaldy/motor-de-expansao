#!/usr/bin/env bash
# DEC-081 — Aceite do bloco do APEX no Caddyfile real da VPS (metade NAO-versionada).
# Spec: docs/spec_portal_selecao_pais.md (secao "Atualizacao DEC-081").
#
# O QUE MUDOU. Ate' a DEC-081 este aceite validava o portal template-Go atras do Authelia:
# a escada de matchers `@so_<pais>`, os grupos `expansao_<pais>` do `authelia/users_database.yml`
# e a diretiva `templates`. A DEC-081 aposentou tudo isso -- o apex virou uma TELA REACT servida
# pelo `web` -- e o bloco do apex ficou simples (ver `deploy/caddy/apex.Caddyfile.template`, que
# e' a METADE VERSIONADA). Este arquivo passa a conferir que o `Caddyfile` REAL da VPS bate com
# aquele template e que NENHUM vestigio do modelo Authelia sobrou no bloco do apex.
#
# ONDE RODA: /opt/motor-expansao/app na VPS -- o unico lugar onde o `Caddyfile` existe (ele e'
# gitignored; por isso este assert NAO esta' em tests/, onde reprovaria o CI de todo mundo). Nao
# e' pytest, nao e' chamado por workflow nenhum. Molde do healthcheck_vps.sh.
#
#     cd /opt/motor-expansao/app
#     bash scripts/aceite_portal_paises.sh ; echo "exit=$?"
#     # esperado: 6 linhas comecando com OK, e exit=0
#
# A SAIDA INTEIRA (6 linhas + o exit=) E' COLADA NO PR do corte -- a unica evidencia revisavel
# da metade que o guard e o CI nao enxergam. Rodar ANTES do `up -d caddy`/`reload` (le o arquivo
# do repo/host, nao o do container) e DE NOVO depois.
#
# CONTRATO: uma linha por assert -- `OK <n> — o que checou` ou `FALHA <n> — <arquivo>:<linha>,
# o que esperava` -- e exit 1 se qualquer um falhar. NUNCA imprime conteudo do arquivo.
#
# Para exercitar fora da VPS (fixture sintetica, nao versionada):
#     ACEITE_CADDYFILE=/tmp/Caddyfile bash scripts/aceite_portal_paises.sh
set -euo pipefail

CADDYFILE="${ACEITE_CADDYFILE:-Caddyfile}"

if [[ ! -f "$CADDYFILE" ]]; then
    echo "FALHA — Caddyfile nao encontrado (rodar em /opt/motor-expansao/app): $CADDYFILE" >&2
    exit 1
fi

FALHOU=0
ok()    { printf 'OK %s — %s\n' "$1" "$2"; }
falha() { printf 'FALHA %s — %s\n' "$1" "$2"; FALHOU=1; }

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# ── Bloco do apex, com numero de linha original ("N<TAB>texto") ───────────────────
# RAIZ tem todas as linhas; RAIZ_DIR descarta comentarios (os comentarios deste bloco citam
# `authelia`, `templates` e `/srv/portal` de proposito, ao explicar o que SAIU -- um grep
# ingenuo casaria neles e reprovaria os asserts de ausencia).
RAIZ="$TMP_DIR/raiz"
RAIZ_DIR="$TMP_DIR/raiz_dir"
awk '
    !dentro && /^ultra-expansao\.tech/ && /\{[[:space:]]*$/ { dentro = 1; prof = 0 }
    dentro {
        printf "%d\t%s\n", NR, $0
        t = $0
        n = gsub(/\{/, "{", t); m = gsub(/\}/, "}", t)
        prof += n - m
        if (prof <= 0) exit
    }
' "$CADDYFILE" > "$RAIZ"
awk -F'\t' 'substr($0, index($0, "\t") + 1) !~ /^[[:space:]]*#/' "$RAIZ" > "$RAIZ_DIR"

tem() { # $1=ERE sobre o texto (sem numero de linha)
    cut -f2- "$RAIZ_DIR" | grep -qE "$1"
}
linha_de() { # $1=ERE -> primeiro numero de linha que casa, ou vazio
    awk -F'\t' -v re="$1" 'substr($0, index($0, "\t") + 1) ~ re { print $1; exit }' "$RAIZ_DIR"
}

# ── Assert 1 — o bloco do apex existe ────────────────────────────────────────────
if [[ ! -s "$RAIZ_DIR" ]]; then
    falha 1 "$CADDYFILE:0, bloco 'ultra-expansao.tech { ... }' nao encontrado"
else
    ok 1 "bloco 'ultra-expansao.tech' encontrado ($(wc -l < "$RAIZ" | tr -d '[:space:]') linhas)"
fi

# ── Assert 2 — forward_auth PAIS-NEUTRO: aponta para /api/verify-sessao ───────────
if tem '(^|[[:space:]])uri[[:space:]]+/api/verify-sessao([[:space:]]|$)'; then
    ok 2 "forward_auth usa /api/verify-sessao (pais-neutro, DEC-081)"
else
    falha 2 "$CADDYFILE:$(linha_de 'forward_auth'), forward_auth do apex deve usar 'uri /api/verify-sessao' (nao /api/verify, que gateia pais)"
fi

# ── Assert 3 — serve pelo `web` (reverse_proxy), nao de /srv/portal ───────────────
if tem '(^|[[:space:]])reverse_proxy[[:space:]]+web:8899([[:space:]]|$)'; then
    ok 3 "reverse_proxy web:8899 — o apex e' servido pelo backend, nao de /srv/portal"
else
    falha 3 "$CADDYFILE:0, esperava 'reverse_proxy web:8899' no bloco do apex (DEC-081)"
fi

# ── Assert 4 — a raiz vira a tela React: rewrite para /portal.html ────────────────
if tem '(^|[[:space:]])rewrite[[:space:]].*/portal\.html([[:space:]]|$)'; then
    ok 4 "a raiz reescreve para /portal.html (a tela React de selecao)"
else
    falha 4 "$CADDYFILE:0, esperava 'rewrite ... /portal.html' (senao '/' cairia na SPA do piloto BR)"
fi

# ── Assert 5 — as rotas publicas ficam fora do @protegido ─────────────────────────
if tem 'not[[:space:]]+path[[:space:]].*/api/verify-sessao'; then
    ok 5 "matcher @protegido deixa as rotas publicas (login/logout/health/verify/verify-sessao) de fora"
else
    falha 5 "$CADDYFILE:$(linha_de '@protegido'), o matcher @protegido deve excluir /api/login /api/logout /api/health /api/verify /api/verify-sessao"
fi

# ── Assert 6 — nenhum vestigio do modelo Authelia no bloco do apex ────────────────
# Procura nas linhas NAO-comentadas (RAIZ_DIR): authelia, /srv/portal, templates, @so_<pais>,
# Remote-Groups *expansao*. Qualquer um e' DEC-081 aplicada pela metade.
VESTIGIO=""
for padrao in 'authelia' '/srv/portal' '(^|[[:space:]])templates([[:space:]]|$)' '@so_[a-z0-9]+' 'Remote-Groups[[:space:]]+\*expansao'; do
    if tem "$padrao"; then
        n="$(linha_de "$padrao")"
        VESTIGIO="$CADDYFILE:${n}, vestigio do modelo Authelia no bloco do apex (padrao: ${padrao})"
        break
    fi
done
if [[ -z "$VESTIGIO" ]]; then
    ok 6 "nenhum vestigio Authelia no bloco do apex (sem authelia/srv/portal/templates/@so_/Remote-Groups expansao)"
else
    falha 6 "$VESTIGIO"
fi

exit "$FALHOU"
