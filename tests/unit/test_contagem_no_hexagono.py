"""A ficha do hexagono conta unidades DENTRO do hexagono — nao o modelo de 2 km.

Regressao de 2026-08-13. O bloco "Quem ja disputa o aluno" do `FichaHex` promete
"unidades mapeadas dentro do hexagono" e mostrava outra coisa:

* `conc` era `n_concorrentes_est` = `oferta_consumida_mercado_estimada / 2.500` —
  CAPACIDADE do modelo de 2 km ponderado por distancia, nao contagem. Uma concorrente a
  1,8 km do centroide entrava ali sem estar dentro do hexagono;
* `ultra` era `n_unidades_ultra_performance_hex`, da camada de performance.

O mesmo defeito de redacao ja tinha sido corrigido no texto do funil (docstring
"RAIO, NAO HEXAGONO" em `_texto_passo3`); a ficha ficou para tras. Nada travava isso.

Estes testes travam as tres coisas que a correcao precisa manter verdadeiras:
1. a contagem e por CELULA H3 res-7, sobre os MESMOS pontos que viram pin no mapa;
2. hexagono coberto pela base e sem unidade da `0` — afirmacao legitima;
3. base de pontos AUSENTE da `None`, nunca `0` — ausencia nao afirma.

HERMETICO: os parquets de pontos sao sinteticos em `tmp_path`; nenhum `data/` real e
lido. READ-ONLY sobre o M1 — nada aqui toca score, pesos ou artefato oficial.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

h3 = pytest.importorskip("h3")

# Dois pontos vizinhos na Paulista e um longe. As celulas sao DERIVADAS pelo h3 no
# proprio teste, nunca hardcoded: um id de celula colado a mao envelhece em silencio se
# a resolucao mudar, e o teste passaria medindo a coisa errada.
_LAT_A, _LNG_A = -23.5613, -46.6560  # Av. Paulista
_LAT_B, _LNG_B = -23.5620, -46.6555  # ~90 m de A -> MESMA celula res-7
_LAT_C, _LNG_C = -23.4800, -46.4000  # ~28 km de A -> outra celula

CELULA_A = h3.latlng_to_cell(_LAT_A, _LNG_A, 7)
CELULA_C = h3.latlng_to_cell(_LAT_C, _LNG_C, 7)
CELULA_VAZIA = h3.latlng_to_cell(-23.9600, -46.3300, 7)  # Santos: coberta, sem ponto


def _escrever_bases(tmp_path: Path, *, com_concorrentes: bool, com_ultra: bool) -> None:
    """Materializa os parquets de PONTO que o backend le, em tmp_path."""
    if com_concorrentes:
        pd.DataFrame(
            {
                "rede": ["Smart Fit", "Bluefit", "Panobianco"],
                "nome_unidade": ["Paulista 1", "Paulista 2", "Longe"],
                "lat": [_LAT_A, _LAT_B, _LAT_C],
                "lng": [_LNG_A, _LNG_B, _LNG_C],
                "hex_id_res7": [CELULA_A, CELULA_A, CELULA_C],
                "flag_coord_valida": [True, True, True],
            }
        ).to_parquet(tmp_path / "concorrentes_mapeados.parquet")

    if com_ultra:
        pd.DataFrame(
            {
                "unidade": ["Ultra Paulista"],
                "lat": [_LAT_B],
                "lng": [_LNG_B],
            }
        ).to_parquet(tmp_path / "unidades_ultra_performance_hex.parquet")


@pytest.fixture
def bases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reaponta as bases de ponto para tmp_path e zera TODAS as caches envolvidas.

    As caches sao `lru_cache` de modulo: sem limpar antes E depois, a primeira leitura
    real de `data/staging` vazaria para os testes seguintes (e vice-versa).
    """

    def _aplicar(*, com_concorrentes: bool = True, com_ultra: bool = True) -> None:
        _escrever_bases(tmp_path, com_concorrentes=com_concorrentes, com_ultra=com_ultra)
        monkeypatch.setattr(pilot, "CONCORRENTES_PARQUET", tmp_path / "concorrentes_mapeados.parquet")
        # Mesmo arquivo por outro nome: `_derivar` usa este para o prototipo de 1 km.
        monkeypatch.setattr(pilot, "CONCORRENTES_PATH", tmp_path / "concorrentes_mapeados.parquet")
        monkeypatch.setattr(
            pilot, "ULTRA_PERF_PARQUET", tmp_path / "unidades_ultra_performance_hex.parquet"
        )
        monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", tmp_path / "unidades_ultra_mapeadas.parquet")
        _limpar_caches()

    _limpar_caches()
    yield _aplicar
    _limpar_caches()


def _limpar_caches() -> None:
    for fn in (
        pilot._carregar_concorrentes,
        pilot._carregar_ultra_pontos,
        pilot._carregar_ultra_mapeadas,
        pilot._ultra_pontos_mapa,
        pilot._contagem_no_hexagono,
    ):
        fn.cache_clear()


def test_o_fixture_poe_dois_concorrentes_na_MESMA_celula() -> None:
    """Guarda do proprio cenario: se A e B cairem em celulas diferentes, o teste de
    contagem abaixo mediria 1+1 e passaria por acidente."""
    assert h3.latlng_to_cell(_LAT_A, _LNG_A, 7) == h3.latlng_to_cell(_LAT_B, _LNG_B, 7)
    assert CELULA_A != CELULA_C


def test_conta_por_celula_e_nao_pelo_modelo_de_2km(bases) -> None:
    bases()

    n_conc, n_ultra = pilot._contagem_no_hexagono()

    assert n_conc is not None and n_ultra is not None
    assert int(n_conc[CELULA_A]) == 2  # os dois da Paulista
    assert int(n_conc[CELULA_C]) == 1  # o de longe, na propria celula
    assert int(n_ultra[CELULA_A]) == 1


def test_hexagono_coberto_e_sem_unidade_da_zero_e_nao_ausencia(bases) -> None:
    """`0` aqui e AFIRMACAO: a base esta montada e nao ha unidade nesta celula."""
    bases()
    df = pilot._derivar(pd.DataFrame({"hex_id": [CELULA_A, CELULA_C, CELULA_VAZIA]}))

    assert df["n_conc_no_hex"].tolist() == [2, 1, 0]
    assert df["n_ultra_no_hex"].tolist() == [1, 0, 0]


def test_base_de_pontos_ausente_vira_None_e_NUNCA_zero(bases) -> None:
    """A regra da casa, escrita no cabecalho do FichaHex: zero afirma "nao ha
    concorrente", e ausencia nao afirma. Sem os parquets, o payload diz "nao sei"."""
    bases(com_concorrentes=False, com_ultra=False)

    n_conc, n_ultra = pilot._contagem_no_hexagono()
    assert n_conc is None and n_ultra is None

    # lat/lng entram porque `_hex_dict` os le direto (`r["lat"]`), sem `.get`.
    df = pilot._derivar(pd.DataFrame({"hex_id": [CELULA_A], "lat": [_LAT_A], "lng": [_LNG_A]}))
    assert df["n_conc_no_hex"].isna().all()
    assert df["n_ultra_no_hex"].isna().all()

    payload = pilot._hex_dict(df.iloc[0], None)
    assert payload["conc_hex"] is None
    assert payload["ultra_hex"] is None


def test_payload_separa_a_contagem_do_hexagono_do_modelo_de_2km(bases) -> None:
    """`conc` (2 km / 2.500) e `conc_hex` (contagem) sao campos DISTINTOS e podem
    divergir — era exatamente essa divergencia que a ficha exibia como se fosse
    contagem. O de 2 km continua servindo mapa, funil e ranking."""
    bases()
    bruto = pd.DataFrame(
        {
            "hex_id": [CELULA_A],
            "lat": [_LAT_A],
            "lng": [_LNG_A],
            # 12.500 alunos consumidos / 2.500 = 5 "concorrentes" do modelo de 2 km,
            # contra as 2 unidades realmente dentro do hexagono.
            "oferta_consumida_mercado_estimada": [12_500.0],
            "n_unidades_ultra_performance_hex": [7],
        }
    )
    linha = pilot._derivar(bruto).iloc[0]
    payload = pilot._hex_dict(linha, None)

    assert payload["conc"] == 5  # modelo de 2 km, inalterado
    assert payload["conc_hex"] == 2  # contagem dentro do hexagono
    assert payload["ultra"] == 7  # camada de performance, inalterada
    assert payload["ultra_hex"] == 1  # ponto dentro do hexagono
    assert isinstance(payload["conc_hex"], int)  # contagem nao sai como 3.0 no JSON
