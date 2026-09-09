"""PROTOTIPO — serve a pressao concorrencial de 1 km por area ao lado da de 2 km.

STATUS: EXPERIMENTO. Existe para o Felipe VER no mapa como ficaria a troca do raio de
atuacao das concorrentes; nao e' caminho de producao. O piloto abre no modelo de 2 km
(comportamento identico ao de hoje) e o operador liga o de 1 km numa chave — nenhum
numero muda sem alguem clicar.

Trocar o padrao para 1 km exige DEC: mexe no residual do passo 2 ("Demanda nao
atendida") e na contagem de white space do passo 3 ("Pressao concorrencial"), que
alimentam carteira e plano.

COMO O RESIDUAL NOVO E' DERIVADO
--------------------------------
O Bloco 5 define, com CLIP em zero:

    oferta_efetiva_disponivel = max(sam - consumo_mercado_2km - consumo_ultra, 0)

A parcela Ultra nao muda com o raio das CONCORRENTES, entao o alvo e':

    oferta_1km = max( (sam - consumo_ultra) - consumo_mercado_1km , 0 )

CUIDADO COM A INVERSAO INGENUA. A primeira versao deste modulo reconstruia
`sam - consumo_ultra` como `oferta_efetiva_disponivel + consumo_mercado_2km`. Isso so'
vale enquanto a oferta NAO bateu no clip. Em hexagono saturado a soma devolve
`consumo_mercado_2km`, um numero sem relacao com o residual — e INFLA o resultado
exatamente onde a disputa e' maior, que e' o caso que a chave existe para mostrar.
Ver `disponivel_sem_concorrente`, que trata os dois regimes e devolve NaN quando o
consumo Ultra nao puder ser reproduzido.

CUSTO: a reparticao roda UMA vez por processo (~8 s para os 3.179 concorrentes validos
do Brasil) e fica em cache. Sem isso, cada request de UF pagaria a conta de novo.

RENORMALIZACAO CONTRA A BASE NACIONAL (mesmo fix de
`pipelines/pressao_concorrencial_1km.py`, aplicado aqui em 2026-09-08). Sem isso, um
concorrente cujo disco cai parcialmente fora do universo valido de hexagonos (litoral,
fronteira, hexagono podado por `M1_HEX_LAND_FRACTION_MIN`) perdia parte da conta em
silencio quando `anexar` fazia merge contra o `df` da UF — o mesmo defeito medido no
modulo de pipeline (3,7% dos concorrentes, ~68 mil alunos, vies de SUPERESTIMAR residual
em metropoles costeiras). `_reparticao` agora renormaliza contra o universo NACIONAL de
hexagonos (nao contra o `df` da UF em exibicao): um concorrente perto da divisa pressiona
hexes de outra UF, e restringir a renormalizacao a UF isolada inflaria artificialmente a
pressao so' porque o vizinho nao esta na tela.
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

# Espelha CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS do Bloco 5. Usada so' para REPRODUZIR
# `oferta_consumida_ultra_estimada`, nunca para inventar capacidade nova.
CAPACIDADE_ULTRA_PROXY = 2_500.0


def _num(df: pd.DataFrame, nome: str) -> pd.Series:
    if nome not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[nome], errors="coerce").fillna(0.0)


def _consumo_ultra(df: pd.DataFrame) -> pd.Series | None:
    """Reproduz `oferta_consumida_ultra_estimada` do Bloco 5. `None` se nao der.

    `calcular_colunas_mercado.py:369` define
        ultra_est = where(ultra_real > 0, ultra_real, n_unidades_ultra_2km * CAP)
    Como `ultra_real` ja vem no artefato enriquecido, o unico insumo extra e'
    `n_unidades_ultra_2km` — pedido em `_COLS_DESEJADAS` (app.py) de forma defensiva.
    """
    if "oferta_consumida_ultra_estimada" in df.columns:
        return _num(df, "oferta_consumida_ultra_estimada")
    if "oferta_consumida_ultra_real" not in df.columns:
        return None
    if "n_unidades_ultra_2km" not in df.columns:
        return None
    ultra_real = _num(df, "oferta_consumida_ultra_real")
    n_2km = _num(df, "n_unidades_ultra_2km").clip(lower=0)
    return ultra_real.where(ultra_real > 0, n_2km * CAPACIDADE_ULTRA_PROXY)


def disponivel_sem_concorrente(df: pd.DataFrame) -> pd.Series:
    """Residual que existiria sem NENHUMA concorrente: `max(sam - consumo_ultra, 0)`.

    NAO basta somar `oferta_efetiva_disponivel + oferta_consumida_mercado_estimada`.
    Aquela coluna ja nasce CLIPADA em zero (`calcular_colunas_mercado.py:379`):

        oferta_efetiva_disponivel = max(sam - merc_2km - ultra, 0)

    Em hexagono NAO saturado a inversao e' exata — some `merc_2km` de volta e sobra
    `sam - ultra`. Em hexagono SATURADO (a oferta bateu no zero) o clip destruiu o
    excedente, e somar de volta devolve `merc_2km`, que nao tem relacao com o residual
    real. Media medida do estrago: com sam=1000, ultra=800, merc_2km=1000, a soma dava
    1000 onde o certo eram 200 — e o erro aparece EXATAMENTE nos hexes mais disputados,
    que sao a razao de ser da chave de 1 km.

    Onde o consumo Ultra nao puder ser reproduzido, devolve NaN em vez de um numero
    errado: o hexagono some da leitura, e some de forma visivel.
    """
    sam = _num(df, "sam_fitness_potencial")
    merc2k = _num(df, "oferta_consumida_mercado_estimada")
    oferta = _num(df, "oferta_efetiva_disponivel")

    sem_conc = oferta + merc2k
    saturado = oferta <= 0
    if not bool(saturado.any()):
        return sem_conc

    ultra = _consumo_ultra(df)
    if ultra is None:
        return sem_conc.where(~saturado, float("nan"))
    return sem_conc.where(~saturado, (sam - ultra).clip(lower=0.0))


@functools.lru_cache(maxsize=1)
def _universo_hex_valido(caminho_dashboard: str) -> frozenset[str]:
    """Universo NACIONAL de hexagonos validos do M1. Cache por processo, so' `hex_id`.

    Usado para renormalizar a massa do disco de 1 km que cai fora da base (ver
    docstring do modulo). Sem o parquet (caminho ausente), devolve conjunto vazio e
    `_reparticao` cai de volta no comportamento sem renormalizacao (nenhum hex e'
    "valido" -> `repartir_concorrentes` trataria tudo como fora da base). Por isso
    `disponivel()` exige os DOIS parquets antes de a chave aparecer no piloto.
    """
    caminho = Path(caminho_dashboard)
    if not caminho.exists():
        return frozenset()
    ids = pd.read_parquet(caminho, columns=["hex_id"])["hex_id"]
    return frozenset(ids.astype(str))


@functools.lru_cache(maxsize=1)
def _reparticao(caminho_conc: str, caminho_dashboard: str) -> pd.DataFrame:
    """Reparte TODOS os concorrentes validos do Brasil entre hexagonos. Cache por processo.

    Nacional de proposito: um concorrente do outro lado da divisa pressiona hexes desta
    UF, entao recortar por UF antes de repartir criaria uma borda artificial de pressao
    exatamente onde ela costuma importar (regioes metropolitanas que cruzam divisa). Pela
    mesma razao a renormalizacao (ver docstring do modulo) usa o universo NACIONAL, nao o
    `df` da UF em exibicao.
    """
    conc = pd.read_parquet(caminho_conc)
    if "status_registro" in conc.columns:
        conc = conc[conc["status_registro"] == "valido"]
    universo = _universo_hex_valido(caminho_dashboard)
    return repartir_concorrentes(conc.reset_index(drop=True), hex_ids_validos=universo)


def disponivel(caminho_conc: Path, caminho_dashboard: Path) -> bool:
    """True se da' para servir o modelo novo. Sem os parquets, o piloto segue so' com 2 km."""
    return Path(caminho_conc).exists() and Path(caminho_dashboard).exists()


def anexar(df: pd.DataFrame, caminho_conc: Path, caminho_dashboard: Path) -> pd.DataFrame:
    """Anexa ao frame de hexes as duas colunas do modelo de 1 km + o residual derivado.

    Colunas adicionadas:
      - `n_concorrentes_influencia_1km`  quantas concorrentes alcancam o hex (colore o mapa)
      - `consumo_concorrentes_1km`       alunos que o hex perde p/ concorrentes (colore o mapa)
      - `oferta_efetiva_disponivel_1km`  residual sob o modelo novo (identidade do docstring)

    Preserva cardinalidade e nao toca nenhuma coluna existente: o modelo de 2 km continua
    intacto no mesmo frame, que e' o que permite a chave alternar sem recarregar.

    `caminho_dashboard`: parquet nacional do M1 (so' `hex_id` e' lido) usado para
    renormalizar a massa perdida na borda da base — ver `_universo_hex_valido`.
    """
    n_orig = len(df)
    agregado = _reparticao(str(caminho_conc), str(caminho_dashboard))

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

    # Residual sob o modelo novo = (residual que existiria sem concorrente) - (consumo
    # rateado por area em 1 km). O primeiro termo NAO pode ser reconstruido somando a
    # coluna clipada; ver `disponivel_sem_concorrente`.
    sem_conc = disponivel_sem_concorrente(out)
    out["oferta_efetiva_disponivel_1km"] = (sem_conc - consumo_1km).clip(lower=0.0)

    assert len(out) == n_orig, "Cardinalidade alterada ao anexar o modelo de 1 km"
    return out
