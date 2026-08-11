"""
Valida presenca dos artefatos minimos para o piloto web e os relatorios.
Apenas leitura de metadados — nao modifica nenhum arquivo.

Uso: python scripts/check_artifacts.py
Retorna exit code 1 se algum artefato critico estiver ausente.

RAIZ: le `MOTOR_DATA_DIR`, a MESMA variavel que `web/server/app.py` e
`data/reports/crescimento/_raizes.py` usam. Ate aqui este script olhava sempre
`<repo>/data`, entao numa maquina que aponta `MOTOR_DATA_DIR` para outro lugar ele
respondia sobre uma pasta que o app nao le — dava [FALTA] com o piloto funcionando, ou
[OK] com o piloto vazio. Um verificador que discorda do programa verificado e' pior que
nenhum: manda procurar o problema no lugar errado.

O QUE ELE NAO ALCANCA: o ambiente PUBLICADO. Aqui so' se ve o disco local. Para o VPS,
`GET /api/health` devolve os mesmos artefatos em `artefatos_faltando`.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("MOTOR_DATA_DIR", str(REPO / "data")))

# Sem estes, os pipelines e o piloto web nao tem insumo (DEC-022)
CRITICOS = [
    ("outputs/hexagonos_brasil_dashboard.parquet",
     "Mapa executivo principal — gerado por fase1_bi_exports.py"),
    ("outputs/oportunidades_expansao_hibrido.parquet",
     "Oportunidades M1+Hibrido — gerado por jobs/pipelines/modelo_hibrido_expansao.py"),
    ("outputs/carteira_expansao_acionavel.parquet",
     "Carteira de expansao — gerado por jobs/pipelines/gerar_carteira_acionavel.py"),
    ("outputs/plano_expansao_curto_prazo.parquet",
     "Plano de curto prazo — gerado por jobs/pipelines/gerar_plano_expansao_curto_prazo.py"),
]

# Ausentes degradam abas Censitario/Hibrido, mas nao travam o dashboard
STAGING_OPCIONAL = [
    ("staging/censo2022_setores_calibrado.parquet",
     "Aba Censitario — core (DF/GO/MG/RJ/RS/SP)"),
    ("staging/censo2022_setores_calibrado_piloto_expandido.parquet",
     "Aba Censitario — piloto expandido"),
    ("staging/censo2022_setores_validado_v2.parquet",
     "Aba Censitario — validado v2"),
]

# Grupo PROPRIO, e nao mais junto do staging das abas Censitario/Hibrido. Os dois moram
# em `staging/` e tambem nao travam nada, mas a semelhanca acaba ai: quem some com eles
# apaga o passo 4 do PILOTO, que nao tem relacao nenhuma com aquelas abas. Enquanto
# dividiam a mesma linha de aviso, o script terminava dizendo "abas Censitario/Hibrido
# podem falhar ao carregar" para quem tinha acabado de perder a camada de crescimento —
# a mensagem mandava investigar o lugar errado.
PILOTO_CRESCIMENTO = [
    ("staging/crescimento_municipal.parquet",
     "Passo 4 do piloto: emprego/empresas por cidade (CAGED, Receita)"),
    ("staging/crescimento_hex.parquet",
     "Passo 4 do piloto: cor do mapa por hexagono (satelite 2016-2023)"),
]


def _check_group(artifacts: list) -> list[str]:
    missing = []
    for rel, desc in artifacts:
        path = DATA_DIR / rel
        if path.exists():
            mb = path.stat().st_size / (1024 * 1024)
            print(f"  [OK]    {rel}  ({mb:.1f} MB)")
        else:
            print(f"  [FALTA] {rel}")
            print(f"          {desc}")
            missing.append(rel)
    return missing


def main() -> None:
    print(f"check_artifacts | data: {DATA_DIR}")
    if "MOTOR_DATA_DIR" not in os.environ:
        print("  (MOTOR_DATA_DIR nao definida — usando <repo>/data, o mesmo default do app)")
    print()

    print("Criticos (piloto/pipelines nao sobem sem eles):")
    faltando_criticos = _check_group(CRITICOS)

    print("\nStaging opcional (abas Censitario/Hibrido):")
    faltando_staging = _check_group(STAGING_OPCIONAL)

    print("\nCrescimento — passo 4 do piloto web (BLK-TRAJ-01):")
    faltando_cresc = _check_group(PILOTO_CRESCIMENTO)

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

    # Cada aviso diz o que APAGA da tela, nao so' que um arquivo falta. Sem isso o
    # operador ve "artefato de staging ausente" e nao liga o recado a' camada em branco
    # que esta olhando.
    if faltando_staging:
        print(f"AVISO: {len(faltando_staging)} artefato(s) de staging ausente(s).")
        print("  -> Abas Censitario/Hibrido podem falhar ao carregar.")
    if faltando_cresc:
        print(f"AVISO: {len(faltando_cresc)} artefato(s) de crescimento ausente(s).")
        print("  -> O passo 4 do piloto ('Como as cidades estao indo') sai VAZIO e sem")
        print("     cor no mapa, sem erro nenhum na tela. Os passos 1, 2, 3 e 5 seguem.")
        print("  -> Eles NAO vem do git nem da imagem Docker (`.gitignore`:")
        print("     `data/staging/*`; `.dockerignore` corta `data/`). Sao gerados por")
        print("     `data/reports/crescimento/` a partir de insumos que nao estao no")
        print("     repo, e chegam em producao so' pelo bind mount do compose.")
        print("  -> No ar, conferir com: curl -fsS <host>/api/health")
    if not (faltando_staging or faltando_cresc):
        print("OK: todos os artefatos criticos e de staging presentes.")


if __name__ == "__main__":
    main()
