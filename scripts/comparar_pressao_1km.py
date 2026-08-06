"""Comparativo: pressao concorrencial 2 km do centroide (atual) vs 1 km por area (novo).

Insumo da decisao pendente — se o residual deve ou nao migrar para a base de 1 km por
area (colunas `*_1km_area` de `pipelines/pressao_concorrencial_1km.py`). Nao escreve em
nenhum artefato: so' le, compara e imprime/salva o relatorio. READ-ONLY sobre o M1.

MODO REAL vs MODO DEMO
----------------------
Se os parquets de producao existirem, o script usa os DADOS REAIS:
    data/staging/hexagonos_mercado_mapeado.parquet
    data/staging/concorrentes_mapeados.parquet

Se nao existirem (o caso de uma estacao de trabalho recem-clonada — ambos sao
gitignored), ele cai num CENARIO SINTETICO com a mesma geometria H3 res-7 real e
concorrentes distribuidos com adensamento radial, so' para demonstrar o COMPORTAMENTO
dos dois modelos. O cabecalho do relatorio diz sempre em qual modo rodou — um numero de
modo DEMO nao vale como evidencia para virar a chave do residual.

Uso:
    python scripts/comparar_pressao_1km.py
    python scripts/comparar_pressao_1km.py --uf SP --csv data/reports/comparativo_1km.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from motor_expansao.pipelines.pressao_concorrencial_1km import (  # noqa: E402
    CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS,
    H3_RESOLUTION,
    comparar_modelos,
)

HEX_PATH = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
CONC_PATH = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"

# Centro do cenario sintetico: Sao Paulo (Se). Raio de ~8 km cobre uma mancha urbana
# densa o suficiente para o comportamento dos dois modelos aparecer.
DEMO_CENTRO = (-23.5505, -46.6333)
DEMO_RAIO_HEX_K = 5      # aneis H3 res-7 em volta do centro -> 91 hexes, ~475 km2
DEMO_N_CONCORRENTES = 120
DEMO_SEED = 20260805


def _carregar_real(uf: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    # `oferta_efetiva_mapeada_2km` entra de PROPOSITO: com ela, `comparar_modelos` usa o
    # valor que o Bloco 3 materializou em producao em vez de recalcular. Sem ela, o
    # comparativo mediria o modelo novo contra uma REIMPLEMENTACAO do antigo — e uma
    # divergencia entre as duas (filtro de concorrente, snapshot da coleta) passaria
    # despercebida bem no numero que decide a virada do residual. Se a coluna nao existir
    # no parquet, o fallback recalcula e o relatorio avisa.
    colunas = ["hex_id", "lat", "lng", "uf"]
    disponiveis = set(pq.read_schema(HEX_PATH).names)
    if "oferta_efetiva_mapeada_2km" in disponiveis:
        colunas.append("oferta_efetiva_mapeada_2km")
    hexes = pd.read_parquet(HEX_PATH, columns=colunas)
    conc = pd.read_parquet(CONC_PATH)
    conc = conc[conc["status_registro"] == "valido"]
    if uf:
        hexes = hexes[hexes["uf"] == uf]
        # Concorrentes NAO sao filtrados por UF: um concorrente do outro lado da divisa
        # ainda pressiona hexes desta UF. Recortar por UF aqui criaria borda artificial.
    return hexes.reset_index(drop=True), conc.reset_index(drop=True)


def _gerar_demo(n_concorrentes: int = DEMO_N_CONCORRENTES) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cenario sintetico sobre a malha H3 REAL, com adensamento radial de concorrentes.

    `n_concorrentes` controla a DENSIDADE, que muda qualitativamente o comparativo:
    num cenario denso praticamente todo hex pressionado a 2 km tambem e' coberto por
    algum disco de 1 km, entao ninguem perde pressao. Num cenario ESPARSO aparecem os
    hexes que ficam entre 1 e 2 km de todo concorrente — esses zeram a pressao no
    modelo novo e sao os que GANHAM residual.
    """
    rng = np.random.default_rng(DEMO_SEED)
    centro_hex = h3.latlng_to_cell(*DEMO_CENTRO, H3_RESOLUTION)
    hex_ids = list(h3.grid_disk(centro_hex, DEMO_RAIO_HEX_K))
    hexes = pd.DataFrame(
        [
            {"hex_id": h, "lat": h3.cell_to_latlng(h)[0], "lng": h3.cell_to_latlng(h)[1]}
            for h in hex_ids
        ]
    )

    # Concorrentes: gaussiana em volta do centro (sigma ~3 km) -> denso no miolo, ralo na
    # borda, como uma mancha urbana real. Nenhum PII: sao pontos sinteticos.
    sigma_graus = 3_000.0 / 111_000.0
    lats = DEMO_CENTRO[0] + rng.normal(0.0, sigma_graus, n_concorrentes)
    lngs = DEMO_CENTRO[1] + rng.normal(0.0, sigma_graus, n_concorrentes)
    conc = pd.DataFrame({"lat": lats, "lng": lngs})

    # So' concorrentes que caem sobre a malha modelada (fora dela nao ha hex para receber).
    dentro = [h3.latlng_to_cell(la, ln, H3_RESOLUTION) in set(hex_ids) for la, ln in zip(lats, lngs, strict=True)]
    return hexes, conc[dentro].reset_index(drop=True)


def _linha(rotulo: str, valor: str) -> str:
    return f"  {rotulo:<44} {valor}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uf", default=None, help="Recorta os hexes por UF (modo real).")
    parser.add_argument("--csv", default=None, help="Salva a tabela hex a hex neste caminho.")
    parser.add_argument(
        "--demo-concorrentes",
        type=int,
        default=DEMO_N_CONCORRENTES,
        help="So' no modo demo: quantos concorrentes sortear (controla a densidade).",
    )
    args = parser.parse_args()

    modo_real = HEX_PATH.exists() and CONC_PATH.exists()
    if modo_real:
        hexes, conc = _carregar_real(args.uf)
        cabecalho = f"MODO REAL — {HEX_PATH.name} + {CONC_PATH.name}"
    else:
        hexes, conc = _gerar_demo(args.demo_concorrentes)
        # ASCII no cabecalho: o console do Windows (cp1252) imprime travessao como "?".
        cabecalho = (
            "MODO DEMO - parquets de producao ausentes (gitignored nesta maquina).\n"
            "  Numeros ILUSTRAM o comportamento dos modelos; NAO servem de evidencia\n"
            "  para virar a chave do residual."
        )

    print("=" * 78)
    print("Comparativo de pressao concorrencial: 2 km centroide (atual) vs 1 km area")
    print("=" * 78)
    print(cabecalho)
    print(_linha("Hexagonos analisados:", f"{len(hexes):,}"))
    print(_linha("Concorrentes:", f"{len(conc):,}"))
    print(_linha("Capacidade por concorrente (alunos):", f"{CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS:,.0f}"))
    print()

    comp = comparar_modelos(hexes, conc)

    # De onde veio o lado ESQUERDO da comparacao. "recalculado" significa que o parquet
    # nao trazia a coluna de producao e o script reimplementou o Bloco 3 — o numero ainda
    # serve para ler o COMPORTAMENTO, mas nao e' o valor oficial.
    fonte = str(comp["fonte_2km"].iloc[0]) if len(comp) else "n/d"
    print("LADO DE COMPARACAO (modelo atual 2 km)")
    if fonte == "producao":
        print(_linha("Fonte:", "coluna oferta_efetiva_mapeada_2km do parquet (PRODUCAO)"))
    else:
        print(_linha("Fonte:", "RECALCULADO aqui - o parquet nao trazia a coluna"))
        print(_linha("", "compara comportamento, nao o valor oficial do Bloco 3"))
    print()

    massa_2km = float(comp["oferta_efetiva_mapeada_2km"].sum())
    massa_1km = float(comp["oferta_efetiva_1km_area"].sum())
    n_conc = len(conc)

    # O desvio e' mostrado como DELTA (`x/esperado - 1`), nao como razao: escrever
    # "+80,2% vs esperado" para 96,24 de 120 le-se como "80% ACIMA do esperado", quando
    # e' 19,8% ABAIXO. O sinal tem de dizer a direcao certa.
    def _desvio(x: float) -> str:
        d = x / n_conc - 1.0 if n_conc else float("nan")
        # Zera residuo de ponto flutuante: o modelo novo conserva massa por construcao,
        # mas a soma de floats devolve -8e-15, que formatado vira "-0.0%" e sugere um
        # deficit que nao existe.
        if abs(d) < 1e-9:
            d = 0.0
        return f"{d:+.1%}"
    print("CONSERVACAO DE MASSA (unidades-equivalentes de concorrente no sistema)")
    print(_linha("Esperado (1 por concorrente):", f"{n_conc:,.2f}"))
    print(
        _linha(
            "Modelo atual 2 km centroide:",
            f"{massa_2km:,.2f}  ({_desvio(massa_2km)} vs esperado)",
        )
    )
    print(
        _linha(
            "Modelo novo 1 km area:",
            f"{massa_1km:,.2f}  ({_desvio(massa_1km)} vs esperado)",
        )
    )
    print()

    consumo_2km = float(comp["consumo_concorrentes_2km"].sum())
    consumo_1km = float(comp["consumo_concorrentes_1km_area"].sum())
    print("CONSUMO ATRIBUIDO A CONCORRENTES (alunos)")
    print(_linha("Modelo atual 2 km:", f"{consumo_2km:,.0f}"))
    print(_linha("Modelo novo 1 km area:", f"{consumo_1km:,.0f}"))
    delta_pct = (consumo_1km / consumo_2km - 1.0) if consumo_2km else float("nan")
    print(_linha("Variacao:", f"{delta_pct:+.1%}  (consumo maior => residual MENOR)"))
    print()

    tocados_2km = int((comp["oferta_efetiva_mapeada_2km"] > 0).sum())
    tocados_1km = int((comp["oferta_efetiva_1km_area"] > 0).sum())
    print("ALCANCE (hexagonos com alguma pressao)")
    print(_linha("Modelo atual 2 km:", f"{tocados_2km:,}  ({tocados_2km / len(comp):.1%} da malha)"))
    print(_linha("Modelo novo 1 km area:", f"{tocados_1km:,}  ({tocados_1km / len(comp):.1%} da malha)"))
    print()

    sobe = int((comp["delta_consumo"] > 1.0).sum())
    desce = int((comp["delta_consumo"] < -1.0).sum())
    igual = len(comp) - sobe - desce
    print("EFEITO POR HEXAGONO (delta de consumo; >0 = residual do hex CAI)")
    print(_linha("Hexes que ganham pressao (residual cai):", f"{sobe:,}  ({sobe / len(comp):.1%})"))
    print(_linha("Hexes que perdem pressao (residual sobe):", f"{desce:,}  ({desce / len(comp):.1%})"))
    print(_linha("Praticamente sem mudanca (|delta| <= 1):", f"{igual:,}  ({igual / len(comp):.1%})"))
    print(_linha("Delta mediano (alunos):", f"{comp['delta_consumo'].median():+,.0f}"))
    print(_linha("Delta p95 / p05 (alunos):",
                 f"{comp['delta_consumo'].quantile(0.95):+,.0f} / {comp['delta_consumo'].quantile(0.05):+,.0f}"))
    print()

    print("MAIORES ALTAS DE PRESSAO (residual cai mais)")
    topo = comp.nlargest(5, "delta_consumo")[
        ["hex_id", "consumo_concorrentes_2km", "consumo_concorrentes_1km_area", "delta_consumo"]
    ]
    print(topo.to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
    print()
    print("MAIORES QUEDAS DE PRESSAO (residual sobe mais)")
    fundo = comp.nsmallest(5, "delta_consumo")[
        ["hex_id", "consumo_concorrentes_2km", "consumo_concorrentes_1km_area", "delta_consumo"]
    ]
    print(fundo.to_string(index=False, float_format=lambda v: f"{v:,.0f}"))

    if args.csv:
        destino = Path(args.csv)
        destino.parent.mkdir(parents=True, exist_ok=True)
        comp.to_csv(destino, sep=";", encoding="utf-8-sig", index=False)
        print(f"\nTabela hex a hex salva em: {destino}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
