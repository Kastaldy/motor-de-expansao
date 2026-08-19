"""A cobertura de 1 km sobrevive a um hexagono SEM leitura — e nao leva a UF junto.

POR QUE ESTE ARQUIVO EXISTE. `cobertura_1km.cobertura` fazia

    sem_conc = float(sem_conc_por_hex.get(hid, 0.0))
    if sem_conc != sem_conc:  # NaN
        continue

O guard estava certo e NUNCA era alcancado. O `.get(hid, 0.0)` so' usa o padrao quando
falta a CHAVE; com a chave presente e valor ausente ele devolve o proprio ausente — e a
serie chega em dtype anulavel (`Float32`), cujo ausente e' `pd.NA`, nao `float('nan')`.
`float(pd.NA)` levanta `TypeError`, entao a rota morria antes do teste de NaN.

Efeito medido em 2026-08-12, local e em producao: `/api/cobertura/{uf}` respondia HTTP 500
em 17 das 27 UFs — todas as densas (SP, RJ, MG, PR, RS, SC, DF, ES, BA, PE...). No mapa,
os raios e o mapa de calor da pressao concorrencial simplesmente nao apareciam: sobrava a
recoloracao dos hexagonos, que nao depende da geometria. Bastava UM hexagono com
concorrente a menos de 1 km e valor ausente para derrubar a UF inteira.

Nao roda com parquet: monta o DataFrame na mao.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import cobertura_1km  # noqa: E402

# Hexagonos res-7 reais e vizinhos, para a geometria nao ser degenerada.
HEXES = ["87a8100a0ffffff", "87a8100a1ffffff", "87a8100a2ffffff"]


def _frame(ofertas: list[float], dtype: str = "Float32") -> pd.DataFrame:
    """Frame de hexes no contrato que a cobertura consome.

    `oferta_efetiva_disponivel == 0` marca o hexagono SATURADO; como o frame NAO traz as
    colunas de consumo Ultra (que e' o estado do artefato em producao),
    `disponivel_sem_concorrente` devolve o ausente exatamente nesses. Oferta > 0 sai com
    residual real. `n_concorrentes_influencia_1km` > 0 e' o portao de entrada da rota —
    sem ele o laco nem roda.

    `dtype` escolhe entre o anulavel (`Float32` -> ausente e' `pd.NA`, o caso de producao)
    e o classico (`float64` -> ausente e' `float('nan')`). Os dois tem de sair da leitura.
    """
    import h3

    centros = [h3.cell_to_latlng(h) for h in HEXES]
    return pd.DataFrame(
        {
            "hex_id": HEXES,
            "lat": [c[0] for c in centros],
            "lng": [c[1] for c in centros],
            "n_concorrentes_influencia_1km": [1] * len(HEXES),
            "oferta_efetiva_disponivel": pd.array(ofertas, dtype=dtype),
            "oferta_consumida_mercado_estimada": pd.array([200.0] * len(HEXES), dtype=dtype),
            "sam_fitness_potencial": pd.array([1000.0] * len(HEXES), dtype=dtype),
            "consumo_concorrentes_1km": pd.array([10.0] * len(HEXES), dtype=dtype),
        }
    )


def _concorrentes(tmp_path: Path) -> Path:
    """Uma concorrente no centro de cada hexagono — garante disco tocando os tres."""
    import h3

    linhas = []
    for i, h in enumerate(HEXES):
        lat, lng = h3.cell_to_latlng(h)
        linhas.append(
            {"nome": f"C{i}", "lat": lat, "lng": lng, "rede": "TESTE", "status_registro": "valido"}
        )
    caminho = tmp_path / "conc.parquet"
    pd.DataFrame(linhas).to_parquet(caminho)
    return caminho


def test_hexagono_sem_leitura_nao_derruba_a_uf(tmp_path: Path) -> None:
    """Um saturado no meio da serie: aquele sai, os outros continuam desenhando."""
    conc = _concorrentes(tmp_path)
    quadro = _frame([500.0, 0.0, 500.0])

    saida = cobertura_1km.cobertura(quadro, conc, com_sombras=True, apenas_dentro=False)

    assert saida["pecas"], "os hexagonos com leitura tem de continuar desenhando"
    hexes_desenhados = {p["hex"] for p in saida["pecas"]}
    assert HEXES[1] not in hexes_desenhados, "o hexagono sem leitura sai, em vez de estourar"
    assert hexes_desenhados <= set(HEXES)


def test_serie_inteira_sem_leitura_devolve_vazio_em_vez_de_500(tmp_path: Path) -> None:
    """O caso de producao: TODO hexagono saturado sem leitura. Vazio, nunca excecao."""
    conc = _concorrentes(tmp_path)
    quadro = _frame([0.0] * len(HEXES))

    saida = cobertura_1km.cobertura(quadro, conc, com_sombras=True, apenas_dentro=False)

    assert saida["pecas"] == []
    # O contorno do alcance NAO depende da leitura do hexagono: ele e' a fronteira dos
    # discos, um fato geografico. Continua saindo — e e' o que desenha os raios no mapa.
    assert saida["contorno"], "o alcance das concorrentes independe do residual"


def test_dtype_classico_tambem_e_tratado(tmp_path: Path) -> None:
    """Com `float64` o ausente e' `float('nan')`, nao `pd.NA` — os dois tem de sair.

    Era a unica forma que o guard antigo (`x != x`) cobria, e por isso o defeito passou:
    todo teste sintetico que montava o frame em `float64` passava verde.
    """
    conc = _concorrentes(tmp_path)
    quadro = _frame([500.0, 0.0, 500.0], dtype="float64")

    saida = cobertura_1km.cobertura(quadro, conc, com_sombras=False, apenas_dentro=False)

    assert saida["pecas"]
    assert HEXES[1] not in {p["hex"] for p in saida["pecas"]}


class TestReporUnidadesUltra2km:
    """A OUTRA metade do defeito: a coluna que faz o hexagono saturado ter leitura.

    `pressao_1km._consumo_ultra` precisa de `oferta_consumida_ultra_estimada` OU do par
    `oferta_consumida_ultra_real` + `n_unidades_ultra_2km`. O artefato enriquecido (82
    colunas) traz so' a primeira do par, entao `_consumo_ultra` devolvia `None` e TODO
    hexagono saturado saia como ausente — 94,6% de SP. Consertar so' o guard de `pd.NA`
    devolveria a camada em 17% dos hexes; e' esta reposicao que enche o mapa.
    """

    @staticmethod
    def _app():
        import sys as _sys

        _sys.path.insert(0, str(_SERVER))
        import app  # noqa: PLC0415

        app._unidades_ultra_2km.cache_clear()
        return app

    def test_coluna_presente_e_preservada(self, tmp_path: Path) -> None:
        """Quando a particao MATERIALIZAR a coluna, este caminho nao roda."""
        app = self._app()
        quadro = pd.DataFrame({"hex_id": HEXES, "n_unidades_ultra_2km": [7, 7, 7]})
        saida = app._completar_unidades_ultra_2km(quadro)
        assert list(saida["n_unidades_ultra_2km"]) == [7, 7, 7]

    def test_repoe_do_parquet_de_mercado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app = self._app()
        mercado = tmp_path / "mercado.parquet"
        pd.DataFrame(
            {"hex_id": [HEXES[0], HEXES[1], "outro"], "n_unidades_ultra_2km": [3, 0, 9]}
        ).to_parquet(mercado)
        monkeypatch.setattr(app, "MERCADO_PARQUET", mercado)
        app._unidades_ultra_2km.cache_clear()

        saida = app._completar_unidades_ultra_2km(pd.DataFrame({"hex_id": HEXES}))

        # O hexagono com unidade recebe a contagem; o de valor zero e o ausente do parquet
        # caem em 0 — que e' o mesmo numero, e o que `_consumo_ultra` espera.
        assert list(saida["n_unidades_ultra_2km"]) == [3, 0, 0]
        assert str(saida["n_unidades_ultra_2km"].dtype) == "int32"

    def test_mapa_guarda_so_os_nao_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """299 de 1,54 milhao tem valor: guardar o resto custaria 117 MB por nada."""
        app = self._app()
        mercado = tmp_path / "mercado.parquet"
        pd.DataFrame(
            {"hex_id": [f"h{i}" for i in range(100)], "n_unidades_ultra_2km": [0] * 98 + [1, 2]}
        ).to_parquet(mercado)
        monkeypatch.setattr(app, "MERCADO_PARQUET", mercado)
        app._unidades_ultra_2km.cache_clear()

        assert app._unidades_ultra_2km() == {"h98": 1, "h99": 2}

    def test_sem_o_parquet_degrada_sem_quebrar(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sem a fonte, o frame passa intacto: o mapa perde a camada, nao a tela."""
        app = self._app()
        monkeypatch.setattr(app, "MERCADO_PARQUET", tmp_path / "nao-existe.parquet")
        app._unidades_ultra_2km.cache_clear()

        saida = app._completar_unidades_ultra_2km(pd.DataFrame({"hex_id": HEXES}))
        assert "n_unidades_ultra_2km" not in saida.columns

    def test_a_coluna_reposta_faz_o_saturado_ter_leitura(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O elo inteiro: com a coluna, `_consumo_ultra` sai de `None` e o saturado vive."""
        import pressao_1km

        app = self._app()
        mercado = tmp_path / "mercado.parquet"
        pd.DataFrame({"hex_id": HEXES, "n_unidades_ultra_2km": [1, 1, 1]}).to_parquet(mercado)
        monkeypatch.setattr(app, "MERCADO_PARQUET", mercado)
        app._unidades_ultra_2km.cache_clear()

        saturado = _frame([0.0] * len(HEXES))
        saturado["oferta_consumida_ultra_real"] = pd.array([0.0] * len(HEXES), dtype="Float32")

        assert pressao_1km._consumo_ultra(saturado) is None, "sem a coluna, nao ha leitura"
        assert pressao_1km.disponivel_sem_concorrente(saturado).isna().all()

        com_coluna = app._completar_unidades_ultra_2km(saturado)
        assert pressao_1km._consumo_ultra(com_coluna) is not None
        assert not pressao_1km.disponivel_sem_concorrente(com_coluna).isna().any()


@pytest.mark.parametrize("ausente", [pd.NA, float("nan"), None])
def test_float_do_ausente_estouraria_sem_o_guard(ausente: object) -> None:
    """Fixa a razao do guard: o `float()` cru falha ou mente, conforme o tipo do ausente.

    `pd.NA` levanta TypeError (era o 500); `None` levanta TypeError; `float('nan')` passa e
    so' entao o teste `x != x` funcionaria. Um `.get(chave, 0.0)` nao protege nenhum dos
    tres, porque a chave EXISTE.
    """
    if ausente is not None and ausente is not pd.NA:
        assert float(ausente) != float(ausente)  # NaN passa pelo float
    else:
        with pytest.raises(TypeError):
            float(ausente)  # type: ignore[arg-type]
    assert pd.isna(ausente), "`pd.isna` e' o unico teste que cobre os tres"
