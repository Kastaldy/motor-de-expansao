"""
scripts/setup.py — Script de setup inicial do ambiente

Uso:
    python scripts/setup.py --check    # Verifica dependências
    python scripts/setup.py --init-db  # Inicializa banco com PostGIS
    python scripts/setup.py --all      # Tudo
"""

import subprocess
import sys
import argparse
from pathlib import Path


def check_dependencias():
    print("\n🔍 Verificando dependências...\n")

    checks = [
        ("Python 3.11+", lambda: sys.version_info >= (3, 11)),
        ("Docker",       lambda: subprocess.run(["docker", "--version"], capture_output=True).returncode == 0),
        ("PostgreSQL",   lambda: subprocess.run(["psql", "--version"], capture_output=True).returncode == 0),
    ]

    ok = True
    for nome, check in checks:
        try:
            status = "✅" if check() else "❌"
            if status == "❌":
                ok = False
        except Exception:
            status = "❌"
            ok = False
        print(f"  {status} {nome}")

    # Verificar .env
    env_ok = Path(".env").exists()
    print(f"\n  {'✅' if env_ok else '⚠️ '} Arquivo .env {'encontrado' if env_ok else 'NÃO encontrado — copiar .env.example'}")

    return ok


def init_dirs():
    print("\n📁 Criando diretórios de dados...\n")
    dirs = [
        "data/staging",
        "data/snapshots/wellhub",
        "data/snapshots/totalpass",
        "data/snapshots/zap",
        "data/snapshots/vivareal",
        "data/models",
        "data/reports",
        "tests/contracts/fixtures",
        "logs",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {d}")


def print_proximos_passos():
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Motor de Expansão Ultra Academia — Setup Concluído
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Próximos passos:

  1. Copiar variáveis de ambiente:
     cp .env.example .env
     # Editar .env com suas chaves

  2. Subir banco de dados:
     docker-compose up -d db

  3. Instalar dependências Python:
     pip install -e ".[dev]"

  4. Instalar browsers do Playwright:
     playwright install chromium

  5. Criar tabelas do banco:
     alembic upgrade head

  6. Rodar testes:
     pytest tests/unit -v

  7. Iniciar API:
     uvicorn api.main:app --reload

  📖 Documentação completa: CLAUDE.md
  🗂️  Blueprint executiva: docs/blueprint_executiva.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup do Motor de Expansão")
    parser.add_argument("--check", action="store_true", help="Verificar dependências")
    parser.add_argument("--init-dirs", action="store_true", help="Criar diretórios de dados")
    parser.add_argument("--all", action="store_true", help="Executar tudo")
    args = parser.parse_args()

    if args.all or args.check:
        check_dependencias()

    if args.all or args.init_dirs:
        init_dirs()

    print_proximos_passos()
