"""Regras do cadastro das unidades Ultra numa fonte só (DEC-085): inclusão pelo site e composição de domingo.

O script da conta `deploy` (`scripts/incluir_unidade_ultra.py`) e o site importam
`motor_expansao.cadastro_ultra`; aqui ficam as regras e a composição que o cron de domingo usa
para levar ao parquet as unidades do site que passaram do prazo de alteração.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import h3
import pandas as pd
import pytest

from motor_expansao import cadastro_ultra as cu

BBOX_BR = {"lat_min": -34.0, "lat_max": 5.5, "lng_min": -74.0, "lng_max": -28.0}
AGORA = datetime(2026, 11, 15, 6, 0, tzinfo=UTC)


def _base() -> pd.DataFrame:
    linhas = [
        ("a" * 40, "Cabo Frio / RJ", "RJ", "Cabo Frio", -22.88242, -42.02299),
        ("b" * 40, "Maricá / RJ", "RJ", "Maricá", -22.922484, -42.817391),
    ]
    return pd.DataFrame(
        [
            {
                "ultra_id": i, "unidade": u, "uf": uf, "cidade": c, "lat": la, "lng": ln,
                "flag_coord_valida": True, "hex_id_res7": h3.latlng_to_cell(la, ln, 7),
            }
            for i, u, uf, c, la, ln in linhas
        ],
        columns=list(cu.COLUNAS_CADASTRO),
    )


def _site(
    ident: int,
    horas: float,
    *,
    pais: str = "BR",
    removida: bool = False,
    nome: str | None = None,
    lat: float = -22.407291,
    lng: float = -42.965760,
) -> cu.UnidadeDoSite:
    criada = AGORA - timedelta(hours=horas)
    return cu.UnidadeDoSite(
        id_unidade_site=ident,
        pais=pais,
        unidade=nome or f"Unidade {ident}",
        uf="RJ",
        cidade="Teresópolis",
        lat=lat,
        lng=lng,
        hex_id_res7=h3.latlng_to_cell(lat, lng, 7),
        criada_em=criada,
        id_usuario_criou=7,
        removida_em=criada + timedelta(hours=1) if removida else None,
    )


# ---------------------------------------------------------------------------------------
# Conferência da inclusão
# ---------------------------------------------------------------------------------------


def test_inclusao_limpa_os_campos_e_acha_a_unidade_mais_perto() -> None:
    inc = cu.conferir_inclusao(
        unidade="  Teresópolis ", uf="rj", cidade=" Teresópolis", lat="-22.407291", lng=-42.96576,
        cadastro=_base(), bbox=BBOX_BR,
    )
    assert (inc.unidade, inc.uf, inc.cidade) == ("Teresópolis", "RJ", "Teresópolis")
    assert inc.hex_id_res7 == h3.latlng_to_cell(-22.407291, -42.96576, 7)
    assert inc.mais_perto is not None and inc.mais_perto.unidade == "Maricá / RJ"
    assert 50_000 < inc.mais_perto.distancia_m < 100_000


def test_nome_repetido_e_recusado_sem_olhar_caixa_nem_espaco() -> None:
    with pytest.raises(cu.Recusa, match="Já existe"):
        cu.conferir_inclusao(
            unidade=" cabo frio / rj ", uf="RJ", cidade="Cabo Frio", lat=-22.5, lng=-42.5,
            cadastro=_base(), bbox=BBOX_BR,
        )


def test_unidade_a_menos_de_200_m_de_outra_e_recusada() -> None:
    # ~110 m ao norte de Cabo Frio
    with pytest.raises(cu.Recusa, match="pode ser a mesma"):
        cu.conferir_inclusao(
            unidade="Cabo Frio II", uf="RJ", cidade="Cabo Frio", lat=-22.88142, lng=-42.02299,
            cadastro=_base(), bbox=BBOX_BR,
        )


def test_coordenada_fora_da_caixa_do_pais_e_recusada() -> None:
    # latitude e longitude trocadas: o erro mais comum ao copiar do mapa
    with pytest.raises(cu.Recusa, match="fora do país"):
        cu.conferir_inclusao(
            unidade="Teresópolis", uf="RJ", cidade="Teresópolis", lat=-42.96576, lng=-22.407291,
            cadastro=_base(), bbox=BBOX_BR,
        )


@pytest.mark.parametrize("campo", ["unidade", "uf", "cidade"])
def test_campo_vazio_e_recusado(campo: str) -> None:
    valores = {"unidade": "Teresópolis", "uf": "RJ", "cidade": "Teresópolis"} | {campo: "   "}
    with pytest.raises(cu.Recusa, match="Preencha"):
        cu.conferir_inclusao(**valores, lat=-22.4, lng=-42.9, cadastro=_base(), bbox=BBOX_BR)


@pytest.mark.parametrize("lat", ["abc", None, float("nan"), float("inf")])
def test_coordenada_que_nao_e_numero_e_recusada(lat: object) -> None:
    with pytest.raises(cu.Recusa, match="Coordenada inválida"):
        cu.conferir_inclusao(
            unidade="X Teste", uf="RJ", cidade="Rio", lat=lat, lng=-42.9, cadastro=_base(), bbox=BBOX_BR,
        )


def test_alteracao_nao_se_recusa_por_estar_perto_de_si_mesma() -> None:
    cadastro = cu.unir_ao_cadastro(_base(), [_site(5, 2)])
    assert cadastro is not None
    inc = cu.conferir_inclusao(
        unidade="Unidade 5", uf="RJ", cidade="Teresópolis", lat=-22.4074, lng=-42.9657,
        cadastro=cadastro, bbox=BBOX_BR, ignorar_ultra_id="site-5",
    )
    assert inc.unidade == "Unidade 5"


# ---------------------------------------------------------------------------------------
# O prazo de alteração
# ---------------------------------------------------------------------------------------


def test_prazo_e_de_24_horas() -> None:
    assert cu.PRAZO_ALTERACAO == timedelta(hours=24)
    assert _site(1, 23.99).no_prazo(AGORA)
    assert not _site(1, 24.01).no_prazo(AGORA)
    assert not _site(1, 2, removida=True).no_prazo(AGORA)


# ---------------------------------------------------------------------------------------
# Leitura no site: o parquet + as vivas do site, sem duplicar
# ---------------------------------------------------------------------------------------


def test_unir_ao_cadastro_soma_as_vivas_e_nao_duplica_a_ja_levada_ao_parquet() -> None:
    base = _base()
    ja_no_parquet = _site(3, 30)
    base_com_3 = pd.concat([base, cu.cadastro_do_site([ja_no_parquet])], ignore_index=True)
    unido = cu.unir_ao_cadastro(base_com_3, [ja_no_parquet, _site(4, 2), _site(6, 2, removida=True)])
    assert unido is not None
    assert list(unido["ultra_id"]) == ["a" * 40, "b" * 40, "site-3", "site-4"]


def test_unir_ao_cadastro_sem_parquet_mostra_so_as_do_site() -> None:
    unido = cu.unir_ao_cadastro(None, [_site(4, 2)])
    assert unido is not None and list(unido["ultra_id"]) == ["site-4"]
    assert cu.unir_ao_cadastro(None, []) is None


# ---------------------------------------------------------------------------------------
# A composição de domingo
# ---------------------------------------------------------------------------------------


def test_compor_leva_so_as_consolidadas_do_pais_e_nao_duplica() -> None:
    base = _base()
    ja = _site(1, 200, lat=-22.95, lng=-43.2)
    base_com_ja = pd.concat([base, cu.cadastro_do_site([ja])], ignore_index=True).astype(base.dtypes.to_dict())
    unidades = [
        ja,  # já está no parquet: não duplica
        _site(2, 25),  # passou do prazo: entra
        _site(3, 2, lat=-22.5, lng=-43.0),  # ainda no prazo: não entra
        _site(4, 30, removida=True, lat=-22.6, lng=-43.1),  # removida: não entra
        _site(5, 30, pais="AR", lat=-22.7, lng=-43.3),  # de outro país: não entra
    ]
    novo, levadas = cu.compor_cadastro(base_com_ja, unidades, pais="BR", agora=AGORA)
    assert [u.id_unidade_site for u in levadas] == [2]
    assert list(novo["ultra_id"]) == ["a" * 40, "b" * 40, "site-1", "site-2"]
    # as linhas que já estavam ficam idênticas, e os tipos também
    pd.testing.assert_frame_equal(novo.iloc[: len(base_com_ja)], base_com_ja)
    assert novo.dtypes.to_dict() == base_com_ja.dtypes.to_dict()
    linha = novo.iloc[-1]
    assert (linha["unidade"], bool(linha["flag_coord_valida"])) == ("Unidade 2", True)


def test_compor_sem_nada_novo_devolve_a_mesma_base() -> None:
    base = _base()
    novo, levadas = cu.compor_cadastro(base, [_site(3, 2)], pais="BR", agora=AGORA)
    assert levadas == [] and novo is base


def test_compor_recusa_parquet_com_colunas_inesperadas() -> None:
    with pytest.raises(cu.Recusa, match="colunas inesperadas"):
        cu.compor_cadastro(_base().drop(columns=["hex_id_res7"]), [], pais="BR", agora=AGORA)


# ---------------------------------------------------------------------------------------
# O subcomando que o cron de domingo chama (`python -m motor_expansao.db.cli compor-unidades-ultra`)
# ---------------------------------------------------------------------------------------


def test_subcomando_do_cron_compoe_o_parquet_do_rascunho_sem_duplicar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import motor_expansao.perfil as perfil_mod
    from motor_expansao.db import cli, unidades_site

    arquivo = tmp_path / cu.ARQ_CADASTRO
    _base().to_parquet(arquivo, index=False)
    monkeypatch.setattr(
        unidades_site,
        "listar_vivas",
        lambda pais: [_site(2, 25), _site(3, 2, lat=-22.5, lng=-43.0)] if pais == "BR" else [],
    )
    monkeypatch.setattr(unidades_site, "agora_do_banco", lambda: AGORA)
    monkeypatch.setattr(perfil_mod, "resolver_perfil", lambda: SimpleNamespace(pais="BR"))

    assert cli.main(["compor-unidades-ultra", "--arquivo", str(arquivo)]) == 0
    novo = pd.read_parquet(arquivo)
    assert list(novo["ultra_id"]) == ["a" * 40, "b" * 40, "site-2"]
    pd.testing.assert_frame_equal(novo.iloc[:2], _base())
    assert not list(tmp_path.glob("*.compondo")), "o temporario nao pode sobrar"

    # A rodada seguinte (ou a mesma, repetida) nao duplica.
    assert cli.main(["compor-unidades-ultra", "--arquivo", str(arquivo)]) == 0
    assert len(pd.read_parquet(arquivo)) == 3


def test_subcomando_do_cron_com_o_banco_fora_falha_sem_tocar_o_arquivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import motor_expansao.perfil as perfil_mod
    from motor_expansao.db import BancoIndisponivel, cli, unidades_site

    arquivo = tmp_path / cu.ARQ_CADASTRO
    _base().to_parquet(arquivo, index=False)
    antes = arquivo.read_bytes()

    def _fora(_pais: str) -> list[cu.UnidadeDoSite]:
        raise BancoIndisponivel("fora")

    monkeypatch.setattr(unidades_site, "listar_vivas", _fora)
    monkeypatch.setattr(perfil_mod, "resolver_perfil", lambda: SimpleNamespace(pais="BR"))
    with pytest.raises(BancoIndisponivel):
        cli.main(["compor-unidades-ultra", "--arquivo", str(arquivo)])
    assert arquivo.read_bytes() == antes
