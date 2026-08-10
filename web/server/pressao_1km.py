"""PROTOTIPO — serve a pressao concorrencial de 1 km por area ao lado da de 2 km.

STATUS: EXPERIMENTO. Existe para o Felipe VER no mapa como ficaria a troca do raio de
atuacao das concorrentes; nao e' caminho de producao. O piloto abre no modelo de 2 km
(comportamento identico ao de hoje) e o operador liga o de 1 km numa chave — nenhum
numero muda sem alguem clicar.

Trocar o padrao para 1 km exige DEC: mexe no residual do passo 2 ("Demanda nao
atendida") e na contagem de white space do passo 3 ("Pressao concorrencial"), que
alimentam carteira e plano.

COMO O RESIDUAL NOVO E' DERIVADO (identidade exata, sem coluna nova)
--------------------------------------------------------------------
O Bloco 5 define:

    oferta_efetiva_disponivel = max(sam - consumo_mercado - consumo_ultra, 0)

A parcela Ultra nao muda com o raio das CONCORRENTES. Entao, isolando-a:

    oferta_1km = max(oferta_atual + consumo_mercado_2km - consumo_mercado_1km, 0)

Ambas as parcelas do lado direito ja vem no parquet enriquecido
(`oferta_efetiva_disponivel` e `oferta_consumida_mercado_estimada`), o que dispensa
carregar `oferta_consumida_ultra_estimada` (que nem existe naquele artefato) e evita
reimplementar a formula do Bloco 5 aqui — reimplementar abriria espaco para divergir
dela em silencio.

CUSTO: a reparticao roda UMA vez por processo (~8 s para os 3.179 concorrentes validos
do Brasil) e fica em cache. Sem isso, cada request de UF pagaria a conta de novo.
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path

import pandas as pd

# O pacote `motor_expansao` vive em src/ do repo; o backend roda de web/server/.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from motor_expansao.pipelines.pressao_concorrencial_1km import (  # noqa: E402
    repartir_concorrentes,
)

COLUNAS_SERVIDAS = ["oferta_efetiva_1km_area", "n_concorrentes_influencia_1km"]


@functools.lru_cache(maxsize=1)
def _reparticao(caminho_conc: str) -> pd.DataFrame:
    """Reparte TODOS os concorrentes validos do Brasil entre hexagonos. Cache por processo.

    Nacional de proposito: um concorrente do outro lado da divisa pressiona hexes desta
    UF, entao recortar por UF antes de repartir criaria uma borda artificial de pressao
    exatamente onde ela costuma importar (regioes metropolitanas que cruzam divisa).
    """
    conc = pd.read_parquet(caminho_conc)
    if "status_registro" in conc.columns:
        conc = conc[conc["status_registro"] == "valido"]
    return repartir_concorrentes(conc.reset_index(drop=True))


def disponivel(caminho_conc: Path) -> bool:
    """True se da' para servir o modelo novo. Sem o parquet, o piloto segue so' com 2 km."""
    return Path(caminho_conc).exists()


def anexar(df: pd.DataFrame, caminho_conc: Path) -> pd.DataFrame:
    """Anexa ao frame de hexes as duas colunas do modelo de 1 km + o residual derivado.

    Colunas adicionadas:
      - `n_concorrentes_influencia_1km`  quantas concorrentes alcancam o hex (colore o mapa)
      - `consumo_concorrentes_1km`       alunos que o hex perde p/ concorrentes (colore o mapa)
      - `oferta_efetiva_disponivel_1km`  residual sob o modelo novo (identidade do docstring)

    Preserva cardinalidade e nao toca nenhuma coluna existente: o modelo de 2 km continua
    intacto no mesmo frame, que e' o que permite a chave alternar sem recarregar.
    """
    n_orig = len(df)
    agregado = _reparticao(str(caminho_conc))

    out = df.drop(
        columns=[c for c in COLUNAS_SERVIDAS if c in df.columns], errors="ignore"
    ).merge(
        agregado[["hex_id", "oferta_efetiva_1km_area", "n_concorrentes_influencia_1km"]],
        on="hex_id",
        how="left",
    )
    out["oferta_efetiva_1km_area"] = pd.to_numeric(
        out["oferta_efetiva_1km_area"], errors="coerce"
    ).fillna(0.0)
    out["n_concorrentes_influencia_1km"] = (
        pd.to_numeric(out["n_concorrentes_influencia_1km"], errors="coerce")
        .fillna(0)
        .astype("int64")
    )

    capacidade = pd.to_numeric(
        out.get("capacidade_default_concorrente_alunos"), errors="coerce"
    ).fillna(2_500.0)
    consumo_1km = out["oferta_efetiva_1km_area"] * capacidade
    # Guardado como COLUNA porque e' o numero que a tela precisa mostrar: quantos alunos
    # cada hexagono perde para as concorrentes sob o rateio por area. E' isso que torna o
    # split visivel — a concorrente na borda tira 1.750 do hexagono dela e 750 do vizinho,
    # em vez dos 2.500 inteiros de um so'.
    out["consumo_concorrentes_1km"] = consumo_1km
    consumo_2km = pd.to_numeric(
        out.get("oferta_consumida_mercado_estimada"), errors="coerce"
    ).fillna(0.0)
    oferta_atual = pd.to_numeric(
        out.get("oferta_efetiva_disponivel"), errors="coerce"
    ).fillna(0.0)

    out["oferta_efetiva_disponivel_1km"] = (
        oferta_atual + consumo_2km - consumo_1km
    ).clip(lower=0.0)

    assert len(out) == n_orig, "Cardinalidade alterada ao anexar o modelo de 1 km"
    return out
