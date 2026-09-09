#!/usr/bin/env bash
# BLK-INTL-13 — Aceite da METADE NAO-VERSIONADA do portal de selecao de pais.
# Spec: docs/spec_portal_selecao_pais.md §7.4.2 (asserts 1-6, 9 e 10).
#
# ONDE RODA: /opt/motor-expansao/app na VPS — o unico lugar onde `Caddyfile` e
# `authelia/users_database.yml` existem (os dois sao GITIGNORED; e' por isso que
# estes asserts NAO estao em tests/ — la eles reprovariam o CI de todo mundo, §7.4).
# Nao e' pytest, nao e' chamado por workflow nenhum. Molde do healthcheck_vps.sh.
#
#     cd /opt/motor-expansao/app
#     bash scripts/aceite_portal_paises.sh ; echo "exit=$?"
#     # esperado: 8 linhas comecando com OK, e exit=0
#
# A SAIDA INTEIRA (8 linhas + o exit=) E' COLADA NO PR — e' a unica evidencia
# revisavel da metade que o guard e o CI nao enxergam (§7.3). Rodar ANTES do
# `up -d caddy` (le o arquivo do repo, nao o do container) e DE NOVO depois.
#
# CONTRATO (§7.4.2): uma linha por assert — `OK <n> — o que checou` ou
# `FALHA <n> — <arquivo>:<linha>, o que esperava` (so a PRIMEIRA falha de cada
# assert) — e exit 1 se qualquer um falhar. NUNCA imprime conteudo dos arquivos:
# nome de usuario e nome de grupo JAMAIS vao para a saida — os asserts 6 e 10
# relatam QUANTOS grupos leram e QUAL INDICE reprovou, nao qual grupo.
#
# Para exercitar fora da VPS (fixtures sinteticas, nao versionadas):
#     ACEITE_CADDYFILE=/tmp/Caddyfile ACEITE_USERS_DB=/tmp/users.yml bash scripts/aceite_portal_paises.sh
set -euo pipefail

CADDYFILE="${ACEITE_CADDYFILE:-Caddyfile}"
USERS_DB="${ACEITE_USERS_DB:-authelia/users_database.yml}"

if [[ ! -f "$CADDYFILE" || ! -f "$USERS_DB" ]]; then
    echo "FALHA — arquivos nao encontrados (rodar em /opt/motor-expansao/app): $CADDYFILE / $USERS_DB" >&2
    exit 1
fi

FALHOU=0
ok()    { printf 'OK %s — %s\n' "$1" "$2"; }
falha() { printf 'FALHA %s — %s\n' "$1" "$2"; FALHOU=1; }

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# ── Bloco raiz do Caddyfile, com numero de linha original ("N<TAB>texto") ─────────
# RAIZ tem todas as linhas (a contagem de chaves precisa delas); RAIZ_DIR descarta
# comentarios — os comentarios do bloco §2.3 citam `permanent`, `templates` e
# `forward_auth` de proposito, e um grep ingenuo casaria neles.
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

# Extrai um bloco aninhado de um arquivo "N<TAB>texto": da primeira linha cujo TEXTO
# casa a ERE ate' a chave que fecha (uma linha so', se a definicao nao abre chave).
extrair_bloco() { # $1=arquivo "N<TAB>texto"  $2=ERE sobre o texto
    awk -v re="$2" '
        {
            texto = substr($0, index($0, "\t") + 1)
            if (!dentro) {
                if (texto !~ re) next
                dentro = 1; prof = 0; viu = 0
            }
            print
            n = gsub(/\{/, "{", texto); m = gsub(/\}/, "}", texto)
            prof += n - m
            if (n > 0) viu = 1
            if (!viu || prof <= 0) exit
        }
    ' "$1"
}

primeira_linha_num() { head -n 1 | cut -f1; }

# ── Grupos do users_database.yml ("N<TAB>grupo"), estilo bloco E flow ─────────────
GRUPOS="$TMP_DIR/grupos"
awk '
    function emitir(nome, nr) {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", nome)
        gsub(/["'\''\[\]]/, "", nome)
        if (nome != "") printf "%d\t%s\n", nr, nome
    }
    /^[[:space:]]*groups:[[:space:]]*\[/ {
        linha = $0
        sub(/^[[:space:]]*groups:[[:space:]]*\[/, "", linha)
        sub(/\].*$/, "", linha)
        ncampos = split(linha, itens, ",")
        for (i = 1; i <= ncampos; i++) emitir(itens[i], NR)
        next
    }
    /^[[:space:]]*groups:[[:space:]]*$/ { em_grupos = 1; next }
    em_grupos {
        if ($0 ~ /^[[:space:]]*-[[:space:]]*/) {
            item = $0
            sub(/^[[:space:]]*-[[:space:]]*/, "", item)
            sub(/[[:space:]]*#.*$/, "", item)
            emitir(item, NR)
        } else if ($0 ~ /[^[:space:]]/) {
            em_grupos = 0
        }
    }
' "$USERS_DB" > "$GRUPOS"

# ── Paises declarados: os sufixos dos matchers @so_<pais> do bloco raiz ───────────
PAISES=()
while IFS= read -r p; do PAISES+=("$p"); done < <(
    cut -f2- "$RAIZ_DIR" | grep -oE '@so_[a-z0-9]+' | sed 's/@so_//' | sort -u
)

# ── Assert 1 — a escada nunca fica pela metade (§2.2/§3) ─────────────────────────
if [[ ${#PAISES[@]} -eq 0 ]]; then
    falha 1 "$CADDYFILE:0, esperava ao menos um matcher @so_<pais> no bloco raiz"
else
    msg_1=""
    for p in "${PAISES[@]}"; do
        bloco="$(extrair_bloco "$RAIZ_DIR" "^[[:space:]]*@so_${p}([^a-z0-9]|\$)")"
        if [[ -z "$bloco" ]]; then
            [[ -n "$msg_1" ]] || msg_1="$CADDYFILE:0, matcher @so_${p} usado mas nao definido"
            continue
        fi
        n_ini="$(printf '%s\n' "$bloco" | primeira_linha_num)"
        for q in "${PAISES[@]}"; do
            [[ "$q" == "$p" ]] && continue
            if ! printf '%s\n' "$bloco" | cut -f2- \
                | grep -qE "^[[:space:]]*not[[:space:]]+header[[:space:]]+Remote-Groups[[:space:]]+\*expansao_${q}\*[[:space:]]*\$"; then
                [[ -n "$msg_1" ]] || msg_1="$CADDYFILE:${n_ini}, @so_${p} nao nega o grupo do pais '${q}' — escada pela metade"
            fi
        done
    done
    if [[ -z "$msg_1" ]]; then
        ok 1 "escada completa: ${#PAISES[@]} matcher(es) @so_<pais>, cada um nega todos os outros paises"
    else
        falha 1 "$msg_1"
    fi
fi

# ── Assert 2 — nenhum `permanent` (301) no bloco raiz (§4.1) ─────────────────────
n_perm="$(awk -F'\t' 'substr($0, index($0, "\t") + 1) ~ /(^|[[:space:]])permanent([[:space:]]|$)/ { print $1; exit }' "$RAIZ_DIR")"
if [[ -n "$n_perm" ]]; then
    falha 2 "$CADDYFILE:${n_perm}, o bloco raiz nao pode conter 'permanent' — todo redirect desta origem e' 302"
else
    ok 2 "bloco raiz sem 'permanent' — nenhum 301 nesta origem"
fi

# ── Assert 3 — cada `handle @so_<pais>` redireciona com 302 explicito ────────────
if [[ ${#PAISES[@]} -eq 0 ]]; then
    falha 3 "$CADDYFILE:0, sem matchers @so_<pais> nao ha handles de pais para conferir"
else
    msg_3=""
    for p in "${PAISES[@]}"; do
        hbloco="$(extrair_bloco "$RAIZ_DIR" "^[[:space:]]*handle[[:space:]]+@so_${p}([^a-z0-9]|\$)")"
        if [[ -z "$hbloco" ]]; then
            [[ -n "$msg_3" ]] || msg_3="$CADDYFILE:0, esperava um 'handle @so_${p}' no bloco raiz"
            continue
        fi
        n_ini="$(printf '%s\n' "$hbloco" | primeira_linha_num)"
        if ! printf '%s\n' "$hbloco" | cut -f2- | grep -qE "redir[[:space:]].*[[:space:]]302([^0-9]|\$)"; then
            [[ -n "$msg_3" ]] || msg_3="$CADDYFILE:${n_ini}, handle @so_${p} sem 'redir ... 302' explicito"
        fi
    done
    if [[ -z "$msg_3" ]]; then
        ok 3 "cada um dos ${#PAISES[@]} handle(s) @so_<pais> redireciona com 302 explicito"
    else
        falha 3 "$msg_3"
    fi
fi

# ── Blocos route/handle para os asserts 4, 5 e 9 ─────────────────────────────────
ROTA="$TMP_DIR/rota"
extrair_bloco "$RAIZ_DIR" "^[[:space:]]*route[[:space:]]*[{]" > "$ROTA"

# ── Assert 4 — `handle @escolher` e' o PRIMEIRO handle do route (§2.2/§4.2) ──────
if [[ ! -s "$ROTA" ]]; then
    falha 4 "$CADDYFILE:0, bloco 'route { ... }' nao encontrado no bloco raiz (§2.1)"
else
    primeiro_handle="$(awk -F'\t' 'substr($0, index($0, "\t") + 1) ~ /^[[:space:]]*handle([[:space:]]|\{|$)/ { print; exit }' "$ROTA")"
    if [[ -z "$primeiro_handle" ]]; then
        falha 4 "$CADDYFILE:0, nenhum 'handle' dentro do route"
    elif printf '%s\n' "$primeiro_handle" | cut -f2- | grep -q "@escolher"; then
        ok 4 "handle @escolher e' o primeiro handle do route — a unica ordem que importa"
    else
        n_h="$(printf '%s\n' "$primeiro_handle" | primeira_linha_num)"
        falha 4 "$CADDYFILE:${n_h}, o primeiro handle do route tem de ser 'handle @escolher'"
    fi
fi

# ── Assert 5 — `forward_auth` vem antes de qualquer handle (§2.1) ────────────────
if [[ ! -s "$ROTA" ]]; then
    falha 5 "$CADDYFILE:0, bloco 'route { ... }' nao encontrado no bloco raiz (§2.1)"
else
    n_fa="$(awk -F'\t' 'substr($0, index($0, "\t") + 1) ~ /(^|[[:space:]])forward_auth([[:space:]]|$)/ { print $1; exit }' "$ROTA")"
    n_h1="$(awk -F'\t' 'substr($0, index($0, "\t") + 1) ~ /^[[:space:]]*handle([[:space:]]|\{|$)/ { print $1; exit }' "$ROTA")"
    if [[ -z "$n_fa" ]]; then
        falha 5 "$CADDYFILE:0, sem 'forward_auth' dentro do route — Remote-Groups nunca chegaria"
    elif [[ -n "$n_h1" && "$n_fa" -ge "$n_h1" ]]; then
        falha 5 "$CADDYFILE:${n_fa}, 'forward_auth' tem de vir ANTES do primeiro handle (esta depois da linha ${n_h1})"
    else
        ok 5 "forward_auth vem antes de qualquer handle dentro do route"
    fi
fi

# ── Assert 6 — nenhum grupo expansao_* e' substring de outro (curinga, §2.2) ─────
EXP="$TMP_DIR/expansao"
awk -F'\t' '$2 ~ /^expansao_/ { if (!(($2) in v)) { v[$2] = 1; print } }' "$GRUPOS" > "$EXP"
n_exp="$(wc -l < "$EXP" | tr -d '[:space:]')"
if [[ "$n_exp" -eq 0 ]]; then
    falha 6 "$USERS_DB:0, nenhum grupo expansao_* encontrado — grupos nao aplicados ou parse falhou"
else
    msg_6="$(awk -F'\t' '
        { nr[NR] = $1; g[NR] = $2 }
        END {
            for (i = 1; i <= NR; i++)
                for (j = 1; j <= NR; j++)
                    if (i != j && index(g[j], g[i]) > 0) {
                        printf "grupo expansao_* #%d e substring do grupo #%d (linha %d)", i, j, nr[j]
                        exit
                    }
        }
    ' "$EXP")"
    if [[ -z "$msg_6" ]]; then
        ok 6 "${n_exp} grupo(s) expansao_* unicos lidos do users_database.yml; nenhum e' substring de outro"
    else
        falha 6 "$USERS_DB, ${msg_6} — o curinga *expansao_<pais>* casaria os dois (§2.2)"
    fi
fi

# ── Assert 9 — `templates` nos DOIS handle do index, e SO' neles (§5.4) ──────────
# Enumera cada bloco `handle` do bloco raiz: inicio, e o que contem.
HANDLES="$TMP_DIR/handles"
awk '
    {
        texto = substr($0, index($0, "\t") + 1)
        nlin = substr($0, 1, index($0, "\t") - 1)
        if (!dentro && texto ~ /^[[:space:]]*handle([[:space:]]|\{|$)/) {
            dentro = 1; prof = 0; viu = 0
            ini = nlin; idx = 0; tpl = 0; sem = 0; rp = 0
            if (texto ~ /@sem_pais/) sem = 1
        }
        if (dentro) {
            if (texto ~ /\/index\.html/) idx = 1
            if (texto ~ /^[[:space:]]*templates[[:space:]]*$/) tpl = 1
            if (texto ~ /(^|[[:space:]])reverse_proxy([[:space:]]|$)/) rp = 1
            n = gsub(/\{/, "{", texto); m = gsub(/\}/, "}", texto)
            prof += n - m
            if (n > 0) viu = 1
            if (!viu || prof <= 0) {
                dentro = 0
                printf "%d\t%d\t%d\t%d\t%d\n", ini, idx, tpl, sem, rp
            }
        }
    }
' "$RAIZ_DIR" > "$HANDLES"
msg_9=""
n_idx="$(awk -F'\t' '$2 == 1' "$HANDLES" | wc -l | tr -d '[:space:]')"
if [[ "$n_idx" -ne 2 ]]; then
    msg_9="$CADDYFILE:0, esperava exatamente 2 handles servindo /index.html (@escolher e o fallback), achei ${n_idx}"
fi
n_sem_tpl="$(awk -F'\t' '$2 == 1 && $3 == 0 { print $1; exit }' "$HANDLES")"
if [[ -z "$msg_9" && -n "$n_sem_tpl" ]]; then
    msg_9="$CADDYFILE:${n_sem_tpl}, handle serve /index.html SEM a diretiva 'templates' — a pagina sairia crua (§5.4)"
fi
n_sempais_tpl="$(awk -F'\t' '$4 == 1 && $3 == 1 { print $1; exit }' "$HANDLES")"
if [[ -z "$msg_9" && -n "$n_sempais_tpl" ]]; then
    msg_9="$CADDYFILE:${n_sempais_tpl}, handle @sem_pais NAO pode ter 'templates' (§5.4 — garantia a menos para revisar)"
fi
# Nenhum handle com reverse_proxy pode ter `templates` — no ARQUIVO INTEIRO, nao so'
# na raiz (ali ele executaria a RESPOSTA do upstream como template, §5.4).
TODOS="$TMP_DIR/todos_handles"
awk '{ printf "%d\t%s\n", NR, $0 }' "$CADDYFILE" \
    | awk -F'\t' 'substr($0, index($0, "\t") + 1) !~ /^[[:space:]]*#/' > "$TMP_DIR/caddy_dir"
awk '
    {
        texto = substr($0, index($0, "\t") + 1)
        nlin = substr($0, 1, index($0, "\t") - 1)
        if (!dentro && texto ~ /^[[:space:]]*handle([[:space:]]|\{|$)/) {
            dentro = 1; prof = 0; viu = 0; ini = nlin; tpl = 0; rp = 0
        }
        if (dentro) {
            if (texto ~ /^[[:space:]]*templates[[:space:]]*$/) tpl = 1
            if (texto ~ /(^|[[:space:]])reverse_proxy([[:space:]]|$)/) rp = 1
            n = gsub(/\{/, "{", texto); m = gsub(/\}/, "}", texto)
            prof += n - m
            if (n > 0) viu = 1
            if (!viu || prof <= 0) {
                dentro = 0
                if (tpl && rp) { printf "%d\n", ini; exit }
            }
        }
    }
' "$TMP_DIR/caddy_dir" > "$TODOS"
n_rp_tpl="$(head -n 1 "$TODOS")"
if [[ -z "$msg_9" && -n "$n_rp_tpl" ]]; then
    msg_9="$CADDYFILE:${n_rp_tpl}, handle com reverse_proxy E templates — executaria a resposta do upstream como template"
fi
if [[ -z "$msg_9" ]]; then
    ok 9 "templates nos 2 handles do /index.html; ausente do @sem_pais e de todo handle com reverse_proxy"
else
    falha 9 "$msg_9"
fi

# ── Assert 10 — todo grupo casa ^[a-z0-9_]+$ (§2.2/§5.4) ─────────────────────────
n_grp="$(wc -l < "$GRUPOS" | tr -d '[:space:]')"
if [[ "$n_grp" -eq 0 ]]; then
    falha 10 "$USERS_DB:0, nenhum grupo lido — parse falhou ou arquivo vazio"
else
    msg_10="$(awk -F'\t' '$2 !~ /^[a-z0-9_]+$/ { printf "grupo #%d (linha %d) nao casa ^[a-z0-9_]+$", NR, $1; exit }' "$GRUPOS")"
    if [[ -z "$msg_10" ]]; then
        ok 10 "${n_grp} entrada(s) de grupo lidas do users_database.yml; todas casam ^[a-z0-9_]+\$"
    else
        falha 10 "$USERS_DB, ${msg_10} — nomes fora disso reabrem as duas armadilhas do §2.2"
    fi
fi

exit "$FALHOU"
