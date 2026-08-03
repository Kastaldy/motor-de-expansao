"""
Valida presenca dos artefatos minimos para o piloto web e os relatorios.
Apenas leitura de metadados — nao modifica nenhum arquivo.

Uso: python scripts/check_artifacts.py
Retorna exit code 1 se algum artefato critico estiver ausente.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Sem estes, os pipelines e o piloto web nao tem insumo (DEC-022)
CRITICOS = [
    ("data/outputs/hexagonos_brasil_dashboard.parquet",
     "Mapa executivo principal — gerado por fase1_bi_exports.py"),
    ("data/outputs/oportunidades_expansao_hibrido.parquet",
     "Oportunidades M1+Hibrido — gerado por jobs/pipelines/modelo_hibrido_expansao.py"),
    ("data/outputs/carteira_expansao_acionavel.parquet",
     "Carteira de expansao — gerado por jobs/pipelines/gerar_carteira_acionavel.py"),
    ("data/outputs/plano_expansao_curto_prazo.parquet",
     "Plano de curto prazo — gerado por jobs/pipelines/gerar_plano_expansao_curto_prazo.py"),
]

# Ausentes degradam abas Censitario/Hibrido, mas nao travam o dashboard
STAGING_OPCIONAL = [
    ("data/staging/censo2022_setores_calibrado.parquet",
     "Aba Censitario — core (DF/GO/MG/RJ/RS/SP)"),
    ("data/staging/censo2022_setores_calibrado_piloto_expandido.parquet",
     "Aba Censitario — piloto expandido"),
    ("data/staging/censo2022_setores_validado_v2.parquet",
     "Aba Censitario — validado v2"),
]


def _check_group(artifacts: list) -> list[str]:
    missing = []
    for rel, desc in artifacts:
        path = ROOT / rel
        if path.exists():
            mb = path.stat().st_size / (1024 * 1024)
            print(f"  [OK]    {rel}  ({mb:.0f} MB)")
        else:
            print(f"  [FALTA] {rel}")
            print(f"          {desc}")
            missing.append(rel)
    return missing


def main() -> None:
    print(f"check_artifacts | raiz: {ROOT}\n")

    print("Criticos (piloto/pipelines nao sobem sem eles):")
    faltando_criticos = _check_group(CRITICOS)

    print("\nStaging opcional (abas Censitario/Hibrido):")
    faltando_staging = _check_group(STAGING_OPCIONAL)

    print()
    if faltando_criticos:
        print(f"BLOQUEIO: {len(faltando_criticos)} artefato(s) critico(s) ausente(s).")
        print("Para gerar:")
        print("  python hex_enrichment.py")
        print("  python fase1_bi_exports.py")
        print("  python jobs/pipelines/modelo_hibrido_expansao.py")
        print("  python jobs/pipelines/gerar_carteira_acionavel.py")
        print("  python jobs/pipelines/gerar_plano_expansao_curto_prazo.py")
        sys.exit(1)
    elif faltando_staging:
        print(f"AVISO: {len(faltando_staging)} artefato(s) de staging ausente(s).")
        print("Abas Censitario/Hibrido podem falhar ao carregar.")
    else:
        print("OK: todos os artefatos criticos e de staging presentes.")


if __name__ == "__main__":
    main()
