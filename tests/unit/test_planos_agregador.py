"""Planos dos agregadores (`motor_expansao.dashboard.planos_agregador`).

Trava a forma: preço de teste não vira preço, a Ultra não concorre com ela mesma, e
academia fora do TotalPass não ganha plano por aproximação larga.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dashboard import planos_agregador as pa


def _bruto(linhas):
    base = {
        "slug": "s", "nome": "x", "latitude": "-23.0", "longitude": "-46.0", "cidade": "SP", "uf": "sp",
        "cep": "", "endereco_formatado": "", "modalidades": "Musculação", "plano_totalpass": "TP 1",
        "preco_plano_totalpass": "109.90", "data_coleta": "2026-09-10",
    }
    return pd.DataFrame([{**base, **linha} for linha in linhas])


def test_normalizar_zera_preco_de_teste_e_descarta_sem_coordenada():
    bruto = _bruto(
        [
            {"slug": "a"},
            {"slug": "b", "plano_totalpass": "TP Free", "preco_plano_totalpass": "1.00"},
            {"slug": "c", "latitude": "abc"},
            {"slug": "a"},
            {"slug": "d", "modalidades": "Pilates,Yoga"},
        ]
    )
    q = pa.normalizar(bruto)
    assert list(q["slug"]) == ["a", "b", "d"]
    assert q.loc[q.slug == "b", "preco"].isna().all() and q.loc[q.slug == "b", "plano"].item() == "TP Free"
    assert q.loc[q.slug == "a", "uf"].item() == "SP"
    assert q.loc[q.slug == "d", "musculacao"].item() is False or not q.loc[q.slug == "d", "musculacao"].item()


def test_normalizar_recusa_csv_sem_coluna_do_contrato():
    with pytest.raises(ValueError, match="plano_totalpass"):
        pa.normalizar(_bruto([{}]).drop(columns=["plano_totalpass"]))


def _planos():
    return pa.normalizar(
        _bruto(
            [
                {"slug": "u", "nome": "ULTRA ACADEMIA ACLIMAÇÃO", "latitude": "-23.00005", "plano_totalpass": "TP 2", "preco_plano_totalpass": "199.90"},
                {"slug": "u2", "nome": "Ultra Academia Cambuci", "latitude": "-23.009", "plano_totalpass": "TP 2", "preco_plano_totalpass": "199.90"},
                {"slug": "b", "nome": "Barata", "latitude": "-23.004", "plano_totalpass": "TP 1", "preco_plano_totalpass": "109.90"},
                {"slug": "m", "nome": "Mesmo", "latitude": "-23.005", "plano_totalpass": "TP 2", "preco_plano_totalpass": "199.90"},
                {"slug": "c", "nome": "Cara", "latitude": "-23.006", "plano_totalpass": "TP 4", "preco_plano_totalpass": "499.90"},
                {"slug": "f", "nome": "Teste", "latitude": "-23.007", "plano_totalpass": "TP Free", "preco_plano_totalpass": "1.00"},
                {"slug": "l", "nome": "Longe", "latitude": "-23.5", "plano_totalpass": "TP 1", "preco_plano_totalpass": "109.90"},
            ]
        )
    )


def test_entorno_acha_a_propria_ultra_e_compara_so_com_concorrentes_com_preco():
    r = pa.planos_no_entorno(-23.0, -46.0, _planos())
    assert r["ultra"] == {"nome": "ULTRA ACADEMIA ACLIMAÇÃO", "plano": "TP 2", "preco": 199.9}
    # a outra Ultra sai da concorrência; o TP Free entra na lista mas não na comparação
    assert r["total"] == 4
    assert (r["mais_baratas"], r["mesmo_nivel"], r["mais_caras"]) == (1, 1, 1)
    assert [x["plano"] for x in r["distribuicao"]] == ["TP 1", "TP 2", "TP 4"]
    assert r["academias"][0]["nome"] == "Barata"


def test_sem_ultra_no_feed_nao_inventa_comparacao():
    planos = _planos()
    r = pa.planos_no_entorno(-23.0, -46.0, planos[~planos["nome"].str.contains("ULTRA", case=False)])
    assert r["ultra"] is None and r["mais_baratas"] is None
    assert r["total"] == 4


def test_pino_so_ganha_plano_no_mesmo_ponto():
    pinos = [{"lat": -23.004, "lng": -46.0}, {"lat": -23.3, "lng": -46.0}]
    pa.anexar_planos(pinos, _planos())
    assert pinos[0]["plano"] == "TP 1" and pinos[0]["preco_plano"] == 109.9
    assert pinos[1]["plano"] is None and pinos[1]["preco_plano"] is None
    assert pa.anexar_planos([{"lat": 1.0, "lng": 1.0}], None)[0]["plano"] is None


def _bruto_wellhub(linhas):
    base = {
        "slug": "s", "nome": "x", "latitude": "-23.0", "longitude": "-46.0", "cidade": "SP", "uf": "sp",
        "cep": "", "endereco_formatado": "", "atividades": "Musculação", "nota_wellhub": "4.7",
        "qtd_avaliacoes_wellhub": "10", "tier_wellhub": "Silver", "preco_tier_wellhub": "149.99",
        "data_coleta": "2026-09-14",
    }
    return pd.DataFrame([{**base, **linha} for linha in linhas])


def test_wellhub_normaliza_pela_regua_propria_e_zera_o_digital():
    q = pa.normalizar(
        _bruto_wellhub([{"slug": "a"}, {"slug": "b", "tier_wellhub": "Digital", "preco_tier_wellhub": "0"}]),
        "wellhub",
    )
    assert q.loc[q.slug == "a", ["plano", "preco"]].values.tolist() == [["Silver", 149.99]]
    assert q.loc[q.slug == "b", "preco"].isna().all() and q.loc[q.slug == "a", "musculacao"].item()
    with pytest.raises(ValueError, match="tier_wellhub"):
        pa.normalizar(_bruto_wellhub([{}]).drop(columns=["tier_wellhub"]), "wellhub")
    with pytest.raises(ValueError, match="desconhecida"):
        pa.normalizar(_bruto_wellhub([{}]), "gympass")


def test_pino_recebe_as_duas_fontes_sem_uma_apagar_a_outra():
    wellhub = pa.normalizar(_bruto_wellhub([{"slug": "w", "latitude": "-23.004"}]), "wellhub")
    pinos = [{"lat": -23.004, "lng": -46.0}]
    pa.anexar_planos(pinos, _planos(), fonte="totalpass")
    pa.anexar_planos(pinos, wellhub, fonte="wellhub")
    assert (pinos[0]["plano"], pinos[0]["plano_wellhub"], pinos[0]["preco_plano_wellhub"]) == ("TP 1", "Silver", 149.99)
    assert pa.arquivo_staging("wellhub") == "planos_wellhub.parquet"


def test_entorno_tira_estudio_e_quem_nao_tem_musculacao_e_da_a_media():
    planos = pa.normalizar(
        _bruto(
            [
                {"slug": "b", "nome": "Barata", "latitude": "-23.004", "plano_totalpass": "TP 1", "preco_plano_totalpass": "100"},
                {"slug": "c", "nome": "Cara", "latitude": "-23.005", "plano_totalpass": "TP 3", "preco_plano_totalpass": "300"},
                {"slug": "v", "nome": "Tonus Gym / Vidya Studio - Asa Sul", "latitude": "-23.006", "preco_plano_totalpass": "900"},
                {"slug": "y", "nome": "Yoga da Esquina", "latitude": "-23.007", "modalidades": "Yoga", "preco_plano_totalpass": "900"},
            ]
        )
    )
    padrao = pa.padrao_de_redes({"vidya_studio", "jab_house"})
    r = pa.planos_no_entorno(-23.0, -46.0, planos, excluir_nomes=padrao, somente_musculacao=True)
    assert [a["nome"] for a in r["academias"]] == ["Barata", "Cara"]
    assert (r["media_preco"], r["n_com_preco"]) == (200.0, 2)
    assert pa.planos_no_entorno(-23.0, -46.0, planos)["n_com_preco"] == 4
    assert pa.padrao_de_redes([]) is None
