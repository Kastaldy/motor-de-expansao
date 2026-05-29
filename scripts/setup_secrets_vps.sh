#!/usr/bin/env bash
# scripts/setup_secrets_vps.sh
# Setup idempotente dos segredos SOPS+age no VPS Ultra Academia.
# Pre-condicao: rodado no VPS em /opt/motor-expansao/app/, como root.
# Cenario A: chave age e gerada pelo proprio script (este arquivo).
# Cenario B (recomendado): chave age foi gerada na maquina local (ver docs/backup_restore.md §7-bis)
#   e copiada via SCP para /root/.config/sops/age/keys.txt antes de rodar este script —
#   nesse caso o script detecta a chave existente e aborta o passo de geracao (esperado).
# O passo 3 do runbook (cofre offline da chave privada) e MANUAL e inerentemente humano.
#
# NAO faz git commit. Humano revisa diff e comita manualmente apos o script.

set -euo pipefail

SOPS_VERSION="3.8.1"
AGE_VERSION="1.1.1"
KEY_DIR="/root/.config/sops/age"
KEY_FILE="${KEY_DIR}/keys.txt"
APP_DIR="/opt/motor-expansao/app"

echo "=== Motor de Expansao Ultra Academia — setup_secrets_vps.sh ==="
echo "Pre-condicao: rodar como root em ${APP_DIR}"
echo

# ------------------------------------------------------------------------------
# Passo 1 — Instalar sops + age se ausentes
# ------------------------------------------------------------------------------
echo "[1/7] Verificando tooling..."

install_sops() {
  echo "  -> Instalando sops ${SOPS_VERSION}..."
  curl -fsSL \
    "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64" \
    -o /usr/local/bin/sops
  chmod +x /usr/local/bin/sops
}

install_age() {
  echo "  -> Instalando age ${AGE_VERSION}..."
  local tmpdir
  tmpdir="$(mktemp -d)"
  curl -fsSL \
    "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-amd64.tar.gz" \
    -o "${tmpdir}/age.tar.gz"
  tar -xzf "${tmpdir}/age.tar.gz" -C "${tmpdir}"
  mv "${tmpdir}/age/age" /usr/local/bin/age
  mv "${tmpdir}/age/age-keygen" /usr/local/bin/age-keygen
  chmod +x /usr/local/bin/age /usr/local/bin/age-keygen
  rm -rf "${tmpdir}"
}

if ! command -v sops >/dev/null 2>&1; then
  install_sops
else
  echo "  sops ja instalado: $(sops --version | head -n1)"
fi

if ! command -v age >/dev/null 2>&1 || ! command -v age-keygen >/dev/null 2>&1; then
  install_age
else
  echo "  age ja instalado: $(age --version 2>&1 | head -n1)"
fi

sops --version >/dev/null
age --version >/dev/null
echo "  Tooling OK."
echo

# ------------------------------------------------------------------------------
# Passo 2 — Verificar/gerar chave age
# ------------------------------------------------------------------------------
echo "[2/7] Verificando chave age em ${KEY_FILE}..."

if [[ -f "${KEY_FILE}" ]]; then
  echo "  Chave existente detectada (Cenario B — chave veio do operador via SCP)."
  echo "  Nao sobrescrevendo. Continuando para encriptacao."
else
  echo "  Chave ausente — gerando agora (Cenario A)."
  mkdir -p "${KEY_DIR}"
  age-keygen -o "${KEY_FILE}"
  chmod 600 "${KEY_FILE}"
  echo "  Chave gerada: ${KEY_FILE}"
fi

RECIPIENT="$(grep '# public key:' "${KEY_FILE}" | awk '{print $4}')"
if [[ -z "${RECIPIENT}" ]]; then
  echo "ERRO: nao consegui extrair recipient publico de ${KEY_FILE}. Saindo." >&2
  exit 1
fi
echo

# ------------------------------------------------------------------------------
# Passo 3 — Imprimir recipient e pausar para humano atualizar .sops.yaml
# ------------------------------------------------------------------------------
echo "[3/7] Recipient publico age:"
echo "  ${RECIPIENT}"
echo
echo "  >>> Cole este valor no .sops.yaml (raiz do repo) substituindo"
echo "      age1REPLACE_WITH_REAL_RECIPIENT em todas as 4 regras."
echo "      Em seguida: git add .sops.yaml && git commit && git push."
echo
read -r -p "Pressione ENTER apos commit do .sops.yaml com recipient real..."
echo

# ------------------------------------------------------------------------------
# Passo 4 — git pull no repo
# ------------------------------------------------------------------------------
echo "[4/7] Atualizando ${APP_DIR}..."
cd "${APP_DIR}"
git pull
echo

# Sanity check do .sops.yaml
if grep -q "age1REPLACE_WITH_REAL_RECIPIENT" .sops.yaml; then
  echo "ERRO: .sops.yaml ainda contem age1REPLACE_WITH_REAL_RECIPIENT." >&2
  echo "      Atualize, comite, faca push e rode este script novamente." >&2
  exit 1
fi
echo "  .sops.yaml OK (placeholder substituido)."
echo

# ------------------------------------------------------------------------------
# Passo 5 — Encriptar os 5 arquivos
# ------------------------------------------------------------------------------
echo "[5/7] Encriptando segredos para secrets/*.enc*..."
mkdir -p secrets/

encrypt_one() {
  local src="$1"
  local dst="$2"
  local mode="$3"  # dotenv | binary | yaml

  if [[ ! -f "${src}" ]]; then
    echo "  AVISO: ${src} nao existe, pulando."
    return 0
  fi

  case "${mode}" in
    dotenv)
      cp "${src}" "${dst}"
      if ! sops --input-type dotenv --output-type dotenv -e -i "${dst}"; then
        rm -f "${dst}"
        echo "ERRO: falha ao encriptar ${dst} (dotenv); DST removido." >&2
        return 1
      fi
      ;;
    binary)
      cp "${src}" "${dst}"
      if ! sops --input-type binary --output-type binary -e -i "${dst}"; then
        rm -f "${dst}"
        echo "ERRO: falha ao encriptar ${dst} (binary); DST removido." >&2
        return 1
      fi
      ;;
    yaml)
      cp "${src}" "${dst}"
      if ! sops -e -i "${dst}"; then
        rm -f "${dst}"
        echo "ERRO: falha ao encriptar ${dst} (yaml); DST removido." >&2
        return 1
      fi
      ;;
    *)
      echo "ERRO: modo desconhecido ${mode}." >&2
      exit 1
      ;;
  esac
  echo "  OK: ${src} -> ${dst}"
}

encrypt_one ".env"                          "secrets/env.enc.env"                          dotenv
encrypt_one "Caddyfile"                     "secrets/Caddyfile.enc"                        binary
encrypt_one "authelia/configuration.yml"    "secrets/authelia.configuration.enc.yaml"      yaml
encrypt_one "authelia/users_database.yml"   "secrets/authelia.users_database.enc.yaml"     yaml
encrypt_one "authelia/db.sqlite3"           "secrets/authelia.db.sqlite3.enc"              binary
echo

# ------------------------------------------------------------------------------
# Passo 6 — Stage + status + pausa para commit manual
# ------------------------------------------------------------------------------
echo "[6/7] Preparando staging area..."
git add secrets/*.enc* 2>/dev/null || true
echo
git status
echo
echo "  >>> Revise o diff acima cuidadosamente."
echo "      Confirme que NENHUM valor em claro vazou."
echo "      Depois execute MANUALMENTE (fora deste script):"
echo "        git commit -m \"chore: encriptar segredos iniciais (SOPS+age)\""
echo "        git push"
echo
read -r -p "Pressione ENTER apos git commit && git push manualmente..."
echo

# ------------------------------------------------------------------------------
# Passo 7 — Lembrete final do cofre offline
# ------------------------------------------------------------------------------
echo "[7/7] LEMBRETE FINAL — passo manual inerentemente humano:"
echo
echo "  Copie ${KEY_FILE} para cofre offline:"
echo "    - Gestor de senhas pessoal (Bitwarden, 1Password, etc.) E"
echo "    - Pen drive criptografado (VeraCrypt, LUKS) — duas copias independentes."
echo
echo "  Sem essa copia NAO HA RESTORE possivel se o VPS for perdido."
echo "  Conteudo a copiar:"
echo "    cat ${KEY_FILE}"
echo
echo "OK"
exit 0
