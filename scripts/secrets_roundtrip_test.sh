#!/usr/bin/env bash
# Roundtrip dummy de SOPS+age. NAO usa segredo real.
# Gera chave dummy temporaria, encripta tests/fixtures/dummy_secret.yaml,
# desencripta, compara e limpa. Imprime ROUNDTRIP OK / ROUNDTRIP FAIL.
#
# Exit code 0 em sucesso, 1 em falha.
# Sempre limpa temporarios, inclusive em caso de falha.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="${REPO_ROOT}/tests/fixtures/dummy_secret.yaml"
ENC="${REPO_ROOT}/tests/fixtures/dummy_secret.enc.yaml"
ROUNDTRIP="${REPO_ROOT}/tests/fixtures/dummy_secret.roundtrip.yaml"
KEY_FILE="${HOME}/.sops/age/dummy-test-key.txt"

cleanup() {
  rm -f "${ENC}" "${ROUNDTRIP}" "${KEY_FILE}" 2>/dev/null || true
}
trap cleanup EXIT

# Pre-checks
if ! command -v sops >/dev/null 2>&1; then
  echo "ROUNDTRIP FAIL: sops nao instalado." >&2
  exit 1
fi
if ! command -v age-keygen >/dev/null 2>&1; then
  echo "ROUNDTRIP FAIL: age-keygen nao instalado." >&2
  exit 1
fi
if [[ ! -f "${FIXTURE}" ]]; then
  echo "ROUNDTRIP FAIL: fixture ausente em ${FIXTURE}." >&2
  exit 1
fi

# Estado limpo
mkdir -p "$(dirname "${KEY_FILE}")"
rm -f "${KEY_FILE}"

# Gerar chave dummy
if ! age-keygen -o "${KEY_FILE}" >/dev/null 2>&1; then
  echo "ROUNDTRIP FAIL: age-keygen falhou." >&2
  exit 1
fi
chmod 600 "${KEY_FILE}"

export SOPS_AGE_KEY_FILE="${KEY_FILE}"

DUMMY_RECIPIENT="$(grep '# public key:' "${KEY_FILE}" | awk '{print $4}')"
if [[ -z "${DUMMY_RECIPIENT}" ]]; then
  echo "ROUNDTRIP FAIL: nao consegui extrair recipient publico." >&2
  exit 1
fi

# Encriptar (--config /dev/null: ignora .sops.yaml do projeto, cujas creation_rules
# casam apenas com secrets/**; o teste vive em tests/fixtures/).
if ! sops --config /dev/null --age "${DUMMY_RECIPIENT}" -e "${FIXTURE}" > "${ENC}" 2>/dev/null; then
  echo "ROUNDTRIP FAIL: sops -e falhou." >&2
  exit 1
fi

# Desencriptar
if ! sops --config /dev/null -d "${ENC}" > "${ROUNDTRIP}" 2>/dev/null; then
  echo "ROUNDTRIP FAIL: sops -d falhou." >&2
  exit 1
fi

# Comparar via parse YAML semantico (sops normaliza aspas e indentacao na
# desencriptacao; o conteudo logico e identico, o byte-a-byte nao).
if ! command -v python >/dev/null 2>&1; then
  echo "ROUNDTRIP FAIL: python ausente para comparacao YAML." >&2
  exit 1
fi
if python -c '
import sys, yaml
with open(sys.argv[1], encoding="utf-8") as fa, open(sys.argv[2], encoding="utf-8") as fb:
    sys.exit(0 if yaml.safe_load(fa) == yaml.safe_load(fb) else 1)
' "${FIXTURE}" "${ROUNDTRIP}"; then
  echo "ROUNDTRIP OK"
  exit 0
else
  echo "ROUNDTRIP FAIL: estrutura YAML do roundtrip diverge do original." >&2
  exit 1
fi
