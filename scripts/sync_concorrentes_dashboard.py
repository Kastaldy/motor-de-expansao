"""
Sincroniza o diretorio de concorrentes que o dashboard/PDFs leem, a partir do
checkout do coletor semanal (VinhoAbencoado/GymScraping).

PROBLEMA QUE ESTE SCRIPT RESOLVE
--------------------------------
O ciclo semanal (`/opt/gymscraping-infra/run_weekly_90.sh`) monta
`GymScraping/Unidades` como `/app/concorrentes:ro` SO dentro do container de regen,
para o `normalizar_concorrentes` gerar `data/staging/concorrentes_mapeados.parquet`.
O diretorio `/opt/motor-expansao/concorrentes` -- que os servicos `streamlit`, `api`
e `web` montam em `/app/concorrentes` -- nunca era tocado por esse ciclo. Resultado
medido em 2026-07-29: o parquet tinha 106 redes, mas o diretorio estava congelado em
39 CSVs e 39 logos de 2026-05-28. Efeitos visiveis em producao:
  - Streamlit: `load_competitor_points` le os CSVs -> 68 das 107 redes sumiam do mapa;
  - piloto web e PDFs: os pontos vinham do parquet (apareciam), mas sem
    `logo_<slug>.png` o pin caia no fallback de sigla -- as logos "nao apareciam".

O QUE ELE FAZ
-------------
1. LOGOS: o GymScraping guarda parte das artes fora do padrao (`AD3_logo.png`,
   `Malibu_logo.png`, `companhiafit_logo.png`, ...). O nome canonico e sempre
   `logo_<slug>.png`, definido por `COMPETITOR_LOGO_FILES`. O casamento e por chave
   compacta (minusculas, sem separadores, sem o token "logo"), com desempate por
   prefixo. Rede sem arte em lugar nenhum fica sem logo de proposito -- o pin cai no
   fallback de sigla, que e o comportamento projetado.
2. CSVs: por rede, escolhe a fonte com MAIS unidades validas entre o que ja esta no
   destino e o que veio do coletor, contando com o MESMO parser do app
   (`_normalize_frame`). Isso e deliberado: uma coleta parcial (o coletor ja falhou
   em 45/106 redes num domingo) nao pode reduzir o que ja estava visivel.

Camada VISUAL de apoio (CLAUDE.md secao 2): nao altera score, ranking, carteira nem
artefatos oficiais do M1. Nao acessa a rede -- as duas pontas sao diretorios locais.

Uso:
    python scripts/sync_concorrentes_dashboard.py \
        --gymscraping /opt/gymscraping --destino /opt/motor-expansao/concorrentes
    # dry-run por padrao; acrescente --aplicar para escrever

Exit code 1 se o destino ficar sem nenhum CSV (situacao que quebraria o mapa).
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from motor_expansao.dashboard.competitors import (  # noqa: E402
    COMPETITOR_LOGO_FILES,
    COMPETITOR_SPECS,
    _normalize_frame,
)


def _compacta(texto: str) -> str:
    """Chave de comparacao: minusculas, so alfanumericos."""
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def _chave_arquivo(nome: str) -> str:
    """Chave compacta do arquivo, descartando o token 'logo' em qualquer posicao.

    `AD3_logo.png` -> `ad3`; `logo_smart_fit.png` -> `smartfit`.
    """
    base = nome.rsplit(".", 1)[0]
    partes = [p for p in re.split(r"[_\-\s]+", base) if p.lower() != "logo"]
    return _compacta("".join(partes))


def indexar_logos(dir_logos: Path) -> dict[str, str]:
    """{chave compacta: nome do arquivo} para os PNGs disponiveis."""
    indice: dict[str, str] = {}
    for caminho in sorted(dir_logos.glob("*.png")):
        indice.setdefault(_chave_arquivo(caminho.name), caminho.name)
    return indice


def resolver_logo(slug: str, indice: dict[str, str]) -> str | None:
    """Nome do PNG de origem para `slug`, ou None se nao houver arte.

    Casa por chave exata; se nao houver, aceita UM unico candidato por prefixo
    (`malibu` <-> `malibu_fitness`), exigindo pelo menos 4 caracteres para nao
    casar siglas curtas por acidente.
    """
    chave = _compacta(slug)
    if chave in indice:
        return indice[chave]
    candidatos = [
        arquivo
        for chave_arq, arquivo in indice.items()
        if len(chave_arq) >= 4 and (chave.startswith(chave_arq) or chave_arq.startswith(chave))
    ]
    return candidatos[0] if len(candidatos) == 1 else None


def contar_unidades(caminho: Path, spec: dict[str, str]) -> int:
    """Unidades validas no CSV pelo parser do app; -1 se ausente ou ilegivel."""
    if not caminho.is_file():
        return -1
    try:
        return len(_normalize_frame(caminho, spec))
    except Exception as exc:  # noqa: BLE001 — CSV corrompido nao pode derrubar o sync
        print(f"  [AVISO] {caminho.name} ilegivel: {exc}")
        return -1


def sincronizar(gymscraping: Path, destino: Path, aplicar: bool) -> int:
    dir_logos = gymscraping / "Logos"
    dir_unidades = gymscraping / "Unidades"
    if not dir_unidades.is_dir():
        print(f"[ERRO] {dir_unidades} nao existe")
        return 1
    destino.mkdir(parents=True, exist_ok=True)

    # ── logos ────────────────────────────────────────────────────────────────
    indice = indexar_logos(dir_logos) if dir_logos.is_dir() else {}
    logos_copiadas: list[str] = []
    logos_preservadas: list[str] = []
    logos_ausentes: list[str] = []
    for slug, nome_canonico in COMPETITOR_LOGO_FILES.items():
        origem_nome = resolver_logo(slug, indice)
        alvo = destino / nome_canonico
        if origem_nome is None:
            # sem arte no coletor: preserva a que ja estiver no destino
            (logos_preservadas if alvo.is_file() else logos_ausentes).append(slug)
            continue
        origem = dir_logos / origem_nome
        if alvo.is_file() and alvo.read_bytes() == origem.read_bytes():
            continue
        if aplicar:
            shutil.copyfile(origem, alvo)
        logos_copiadas.append(f"{origem_nome} -> {nome_canonico}")

    # ── CSVs de unidades ─────────────────────────────────────────────────────
    copiados: list[tuple[str, int, int]] = []  # (arquivo, antes, depois)
    mantidos: list[tuple[str, int, int]] = []  # destino ja tinha mais unidades
    sem_fonte: list[str] = []
    total = 0
    for nome_csv, spec in COMPETITOR_SPECS.items():
        n_destino = contar_unidades(destino / nome_csv, spec)
        n_origem = contar_unidades(dir_unidades / nome_csv, spec)
        if n_origem < 0 and n_destino < 0:
            sem_fonte.append(spec["rede"])
            continue
        # Empate de contagem TAMBEM propaga (desde que o conteudo mude): uma coleta que
        # so corrige coordenada ou nome de unidade nao altera o total e, com `>`, ficaria
        # presa fora de producao para sempre. O que a regra proibe e REDUZIR.
        origem_csv = dir_unidades / nome_csv
        alvo_csv = destino / nome_csv
        empate_com_mudanca = (
            n_origem == n_destino
            and n_origem >= 0
            and origem_csv.is_file()
            and (not alvo_csv.is_file() or alvo_csv.read_bytes() != origem_csv.read_bytes())
        )
        if n_origem > n_destino or empate_com_mudanca:
            if aplicar:
                shutil.copyfile(origem_csv, alvo_csv)
            copiados.append((nome_csv, max(n_destino, 0), n_origem))
            total += n_origem
        else:
            if 0 <= n_origem < n_destino:
                mantidos.append((nome_csv, n_destino, n_origem))
            total += max(n_destino, 0)

    # ── relatorio ────────────────────────────────────────────────────────────
    print(f"redes cadastradas ............ {len(COMPETITOR_SPECS)}")
    print(f"logos atualizadas ............ {len(logos_copiadas)}")
    print(f"logos preservadas do destino . {len(logos_preservadas)} {sorted(logos_preservadas)}")
    print(f"redes sem logo (fallback) .... {len(logos_ausentes)} {sorted(logos_ausentes)}")
    print(f"CSVs atualizados ............. {len(copiados)}")
    print(f"CSVs mantidos (destino maior)  {len(mantidos)}")
    print(f"redes sem CSV em lugar nenhum  {len(sem_fonte)} {sorted(sem_fonte)}")
    print(f"total de unidades no destino . {total}")
    if copiados:
        print("\nmaiores ganhos:")
        for nome, antes, depois in sorted(copiados, key=lambda r: r[2] - r[1], reverse=True)[:10]:
            print(f"  {nome:40s} {antes:5d} -> {depois:5d}  (+{depois - antes})")
    if mantidos:
        print("\nmantidos (a coleta traria MENOS unidades):")
        for nome, no_destino, na_origem in mantidos:
            print(f"  {nome:40s} destino={no_destino:5d}  coleta={na_origem:5d}")
    if not aplicar:
        print("\n(dry-run — nada foi escrito; use --aplicar)")

    n_csv_final = len(list(destino.glob("unidades_*.csv")))
    if aplicar and n_csv_final == 0:
        print("[ERRO] destino ficou sem nenhum CSV de unidades")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--gymscraping",
        type=Path,
        default=Path("/opt/gymscraping"),
        help="raiz do checkout do coletor (espera Logos/ e Unidades/)",
    )
    parser.add_argument(
        "--destino",
        type=Path,
        default=Path("/opt/motor-expansao/concorrentes"),
        help="diretorio que os containers montam em /app/concorrentes",
    )
    parser.add_argument("--aplicar", action="store_true", help="escreve de fato (default: dry-run)")
    args = parser.parse_args()
    return sincronizar(args.gymscraping, args.destino, args.aplicar)


if __name__ == "__main__":
    raise SystemExit(main())
