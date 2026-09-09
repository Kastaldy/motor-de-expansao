"""Renormalizacao da chave '1km' do piloto web contra a base NACIONAL de hexagonos.

Regressao (Bloco F, 2026-09-08): `pressao_1km._reparticao` chamava
`repartir_concorrentes` sem `hex_ids_validos`, entao `anexar` perdia em silencio a massa
de um concorrente cujo disco caisse fora da base -- o mesmo defeito corrigido em
`pipelines/pressao_concorrencial_1km.py` (~68 mil alunos perdidos nacionalmente, vies de
SUPERESTIMAR residual em hexagonos costeiros/fronteira). A base de renormalizacao aqui e'
o universo NACIONAL (`DASHBOARD_NACIONAL_PATH`), nao o `df` da UF em exibicao -- um
concorrente perto da divisa deve continuar pressionando o vizinho, mesmo que a UF
consultada nao inclua o hex dele.

HERMETICO: parquets sinteticos em `tmp_path`. READ-ONLY sobre o M1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import h3
import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import pressao_1km  # noqa: E402

H3_RES = 7
SP_CENTROIDE = h3.latlng_to_cell(-23.55, -46.63, H3_RES)


def _limpar_caches():
    pressao_1km._reparticao.cache_clear()
    pressao_1km._universo_hex_valido.cache_clear()


@pytest.fixture(autouse=True)
def _cache_isolado():
    _limpar_caches()
    yield
    _limpar_caches()


def _escrever_concorrente(tmp_path: Path, lat: float, lng: float) -> Path:
    caminho = tmp_path / "concorrentes.parquet"
    pd.DataFrame(
        {
            "lat": [lat],
            "lng": [lng],
            "status_registro": ["valido"],
        }
    ).to_parquet(caminho, index=False)
    return caminho


def _escrever_universo(tmp_path: Path, *hex_ids: str) -> Path:
    caminho = tmp_path / "dashboard_nacional.parquet"
    pd.DataFrame({"hex_id": list(hex_ids)}).to_parquet(caminho, index=False)
    return caminho


def test_disponivel_exige_os_dois_parquets(tmp_path):
    conc = _escrever_concorrente(tmp_path, -23.55, -46.63)
    dash = _escrever_universo(tmp_path, SP_CENTROIDE)
    ausente = tmp_path / "nao_existe.parquet"

    assert pressao_1km.disponivel(conc, dash) is True
    assert pressao_1km.disponivel(ausente, dash) is False
    assert pressao_1km.disponivel(conc, ausente) is False


def test_anexar_concentra_toda_a_massa_quando_so_um_hex_e_valido(tmp_path):
    """O bug original: base com 1 unico hexagono valido, concorrente perto mas nao
    exatamente no centroide -- antes do fix, a massa fora do unico hex valido era
    descartada; depois, toda ela pousa no unico hex valido (soma = 1,0)."""
    lat, lng = -23.55, -46.63  # nao e' o centroide exato do hex -> reparte por natureza
    conc = _escrever_concorrente(tmp_path, lat, lng)
    dash = _escrever_universo(tmp_path, SP_CENTROIDE)  # universo restrito a 1 hex

    df = pd.DataFrame(
        {
            "hex_id": [SP_CENTROIDE],
            "lat": [lat],
            "lng": [lng],
            "capacidade_default_concorrente_alunos": [2500.0],
        }
    )
    out = pressao_1km.anexar(df, conc, dash)

    assert out["oferta_efetiva_1km_area"].iloc[0] == pytest.approx(1.0, abs=1e-6)


def test_anexar_nao_inventa_massa_quando_universo_vazio(tmp_path):
    """Sem universo nacional acessivel, nao ha' hex 'valido' -> nenhuma massa e'
    atribuida (fallback seguro, nao um numero fantasma)."""
    conc = _escrever_concorrente(tmp_path, -23.55, -46.63)
    dash = tmp_path / "nao_existe.parquet"  # _universo_hex_valido -> frozenset vazio

    df = pd.DataFrame(
        {
            "hex_id": [SP_CENTROIDE],
            "lat": [-23.55],
            "lng": [-46.63],
            "capacidade_default_concorrente_alunos": [2500.0],
        }
    )
    out = pressao_1km.anexar(df, conc, dash)

    assert out["oferta_efetiva_1km_area"].iloc[0] == 0.0


def test_renormalizacao_usa_universo_nacional_nao_o_df_da_uf(tmp_path):
    """Um concorrente perto da divisa continua pressionando o vizinho de OUTRA UF,
    mesmo que o `df` em exibicao seja so' da UF consultada -- a renormalizacao usa o
    universo NACIONAL (dash), nao os hex_id do `df`."""
    lat, lng = -23.55, -46.63
    vizinhos = list(h3.grid_disk(SP_CENTROIDE, 1))
    conc = _escrever_concorrente(tmp_path, lat, lng)
    # Universo nacional inclui os vizinhos (outra UF); o `df` exibido so' traz o
    # hex central (a UF consultada).
    dash = _escrever_universo(tmp_path, *vizinhos)

    df_uf_atual = pd.DataFrame(
        {
            "hex_id": [SP_CENTROIDE],
            "lat": [lat],
            "lng": [lng],
            "capacidade_default_concorrente_alunos": [2500.0],
        }
    )
    out = pressao_1km.anexar(df_uf_atual, conc, dash)

    # A massa que pousaria nos vizinhos (fora do `df` exibido) NAO deve ser realocada
    # para o hex central so' porque a tela nao mostra os vizinhos -- o valor deve ser
    # igual ao share bruto (sem renormalizacao adicional), nao 1,0.
    from motor_expansao.pipelines.pressao_concorrencial_1km import shares_por_hex

    share_bruto_central = shares_por_hex(lat, lng).get(SP_CENTROIDE, 0.0)
    assert out["oferta_efetiva_1km_area"].iloc[0] == pytest.approx(
        share_bruto_central, abs=1e-6
    )
    assert share_bruto_central < 1.0, "escolher um ponto que realmente reparte"
