"""Comodidades das concorrentes (`motor_expansao.dashboard.comodidades_concorrentes`).

Trava a forma: vazio na coleta nunca vira "não oferece", linha de coordenada reprovada não
casa com pino nenhum, e a comodidade de uma rede não é emprestada à academia vizinha de outra.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dashboard import comodidades_concorrentes as cc


def _bruto(linhas):
    base = {
        "canal": "agregador", "fonte": "wellhub", "marca": "bluefit", "nome": "Academia Bluefit - Centro",
        "cidade": "São Paulo", "uf": "sp", "latitude": "-23.0", "longitude": "-46.0",
        "musculacao": "sim", "luta": "", "armario": "sim", "chuveiro": "", "vestiario": "sim",
        "massagem": "", "cadeira_massagem": "", "declarou_comodidades": "sim",
        "comodidades": "Armários, Vestiário, Wi-Fi", "atividades": "Musculação, Yoga",
        "slug": "s", "data_coleta": "2026-09-29", "csv": "oficial",
    }
    return pd.DataFrame([{**base, **linha} for linha in linhas])


def test_normalizar_vira_booleano_e_descarta_o_que_nao_serve_para_casar():
    q = cc.normalizar(
        _bruto(
            [
                {"slug": "a"},
                {"slug": "b", "latitude": "abc"},
                # coordenada reprovada na auditoria do coletor: casar por distância seria chute
                {"slug": "c", "csv": "pendente"},
                {"slug": "d", "canal": "recorrente", "fonte": "site", "nome": "Centro - SP"},
            ]
        )
    )
    assert list(q["slug"]) == ["a", "d"]
    a = q.iloc[0]
    assert bool(a["musculacao"]) and bool(a["armario"]) and bool(a["vestiario"])
    assert not bool(a["luta"]) and not bool(a["chuveiro"])
    assert a["uf"] == "SP" and a["marca"] == "bluefit"


def test_normalizar_recusa_csv_sem_coluna_do_contrato():
    with pytest.raises(ValueError, match="canal"):
        cc.normalizar(_bruto([{}]).drop(columns=["canal"]))


def test_canal_fora_do_vocabulario_e_recusado():
    with pytest.raises(ValueError, match="canal"):
        cc.normalizar(_bruto([{"canal": "boato"}]))


def _base():
    return cc.normalizar(
        _bruto(
            [
                {"slug": "ag", "latitude": "-23.00010"},
                {
                    "slug": "site", "canal": "recorrente", "fonte": "site", "nome": "Centro - SP",
                    "latitude": "-23.00012", "luta": "sim", "comodidades": "sala de lutas, armarios",
                    "atividades": "",
                },
                {"slug": "outra", "marca": "smart_fit", "nome": "Smart Fit - Centro", "latitude": "-23.00020"},
                # mesma rede, pino divergente do agregador (até 300 m ainda é a mesma unidade)
                {"slug": "longe", "marca": "selfit", "nome": "Selfit - Sul", "latitude": "-23.0520"},
                {"slug": "sem", "marca": "", "nome": "Academia do Bairro", "latitude": "-23.1000"},
            ]
        )
    )


def _pino(**campos):
    return {"lat": -23.0, "lng": -46.0, "nome": "Bluefit Centro", "rede": "bluefit", "classe": "cadeia", **campos}


def test_pino_ganha_os_dois_canais_separados():
    (p,) = cc.anexar_comodidades([_pino()], _base())
    ag, site = p["comodidades"]["agregador"], p["comodidades"]["recorrente"]
    assert ag["fonte"] == "wellhub" and site["fonte"] == "site"
    assert ag["itens"]["armario"] is True and site["itens"]["luta"] is True
    assert ag["lista"] == ["Armários", "Vestiário", "Wi-Fi"]
    assert ag["atividades"] == ["Musculação", "Yoga"] and site["atividades"] == []
    assert ag["data_coleta"] == "2026-09-29"


def test_vazio_na_coleta_nao_vira_nao_oferece():
    (p,) = cc.anexar_comodidades([_pino()], _base())
    itens = p["comodidades"]["agregador"]["itens"]
    # só existe "sim" e "não declarado": a fonte nunca afirma a ausência
    assert itens["luta"] is None and itens["chuveiro"] is None
    assert False not in itens.values()
    assert set(itens) == set(cc.ITENS)


def test_comodidade_de_outra_rede_nao_e_emprestada():
    # a 22 m existe uma Smart Fit; o pino é Bluefit e fica com a linha da Bluefit a 11 m
    (p,) = cc.anexar_comodidades([_pino()], _base())
    assert p["comodidades"]["agregador"]["nome"] == "Academia Bluefit - Centro"
    # e pino de uma terceira rede, no mesmo ponto, não herda de nenhuma das duas
    (q,) = cc.anexar_comodidades([_pino(rede="skyfit", nome="Skyfit Centro")], _base())
    assert q["comodidades"] == {"recorrente": None, "agregador": None}


def test_mesma_rede_casa_com_o_pino_divergente_do_agregador():
    # 220 m: fora do raio curto, dentro do raio de mesma rede
    perto = _pino(lat=-23.0540, rede="selfit", nome="Selfit Sul")
    longe = _pino(lat=-23.0560, rede="selfit", nome="Selfit Sul")
    p, q = cc.anexar_comodidades([perto, longe], _base())
    assert p["comodidades"]["agregador"]["nome"] == "Selfit - Sul"
    assert q["comodidades"]["agregador"] is None


def test_independente_so_casa_no_mesmo_ponto():
    no_ponto = {"lat": -23.1000, "lng": -46.0, "nome": "Academia do Bairro", "rede": None, "classe": "independente"}
    ao_lado = {**no_ponto, "lat": -23.1012}
    p, q = cc.anexar_comodidades([no_ponto, ao_lado], _base())
    assert p["comodidades"]["agregador"]["nome"] == "Academia do Bairro"
    assert q["comodidades"]["agregador"] is None


@pytest.mark.parametrize("base", [None, pd.DataFrame()])
def test_sem_base_a_chave_nasce_nula_em_todo_pino(base):
    # `None` no pino = base ausente ("indisponível"); o par de canais nulos = academia não coletada
    pinos = cc.anexar_comodidades([_pino(), {"lat": None, "lng": None}], base)
    assert [p["comodidades"] for p in pinos] == [None, None]


def test_pino_sem_coordenada_nao_quebra_e_fica_sem_canal():
    (p,) = cc.anexar_comodidades([{"lat": None, "lng": None, "rede": "bluefit"}], _base())
    assert p["comodidades"] == {"recorrente": None, "agregador": None}


# ---------------------------------------------------------------------------
# Em que agregadores a academia está (plano e preço)
# ---------------------------------------------------------------------------


def _planos():
    return {
        "wellhub": pd.DataFrame([{"slug": "ag", "plano": "Basic", "preco": 69.99}]),
        "totalpass": pd.DataFrame([{"slug": "tp", "plano": "TP 1", "preco": 109.9}]),
    }


def test_plano_casado_no_ponto_e_mantido_e_as_chaves_antigas_nao_mudam():
    pino = _pino(plano="TP 2", preco_plano=199.9, plano_wellhub=None, preco_plano_wellhub=None)
    (p,) = cc.anexar_agregadores([pino], None, _planos())
    assert p["agregadores"]["totalpass"] == {"plano": "TP 2", "preco": 199.9, "casado_por": "ponto"}
    assert p["agregadores"]["wellhub"] is None  # sem base de comodidades não há segundo caminho
    assert (p["plano"], p["preco_plano"], p["plano_wellhub"]) == ("TP 2", 199.9, None)


def test_pino_sem_plano_no_ponto_acha_o_plano_pela_linha_da_mesma_rede():
    # a linha `ag` (Bluefit, wellhub) casa com o pino; o plano vem do slug dela
    pino = _pino(plano=None, preco_plano=None, plano_wellhub=None, preco_plano_wellhub=None)
    (p,) = cc.anexar_agregadores([pino], _base(), _planos())
    assert p["agregadores"]["wellhub"] == {"plano": "Basic", "preco": 69.99, "casado_por": "rede"}
    # não há linha do TotalPass para esta academia: "não identificado", nunca "não aceita"
    assert p["agregadores"]["totalpass"] is None
    assert p["plano_wellhub"] is None  # a chave que a Executiva lê fica como estava


def test_plano_de_outra_rede_nao_e_emprestado_e_fonte_sem_tabela_fica_nula():
    pino = _pino(rede="skyfit", nome="Skyfit Centro")
    (p,) = cc.anexar_agregadores([pino], _base(), {"wellhub": None, "totalpass": None})
    assert p["agregadores"] == {"totalpass": None, "wellhub": None}
    (q,) = cc.anexar_agregadores([_pino(rede="skyfit")], _base(), _planos())
    assert q["agregadores"] == {"totalpass": None, "wellhub": None}
