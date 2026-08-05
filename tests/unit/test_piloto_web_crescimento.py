"""Passo 4 do funil do piloto — "Como a cidade esta indo" (BLK-TRAJ-01).

Cobre o que o resto da suite nao alcanca: a renumeracao do funil (4 -> 5 passos),
o fallback de join por nome — de que 21 UFs dependem, porque o M1 deixa
`cod_municipio` nulo nelas — e a degradacao quando os artefatos nao existem, que
e o estado do CI e o estado de producao ate o proximo deploy de dados.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

# Reusa a montagem da suite do piloto: `pilot` (o modulo app com web/server no
# sys.path) e as duas fixtures de data_dir. Importar a fixture pelo nome a torna
# visivel para o pytest neste modulo.
from tests.unit.test_piloto_web_endpoints import (  # noqa: F401
    empty_data,
    pilot,
    synth_data,
)


def _muni(nome: str = "Sao Paulo") -> dict:
    """A rota do municipio, chamada direto — sem cliente HTTP.

    O CI nao instala httpx, e `starlette.testclient` estoura na importacao sem ele;
    a suite do piloto ja resolvia isso chamando a funcao de rota (ver o cabecalho do
    modulo vizinho). Como bonus, o payload chega como dict cru: `test_payload_e_json_
    valido_sem_nan` passa a testar o dado que o FastAPI vai serializar, e nao o JSON
    ja saneado por ele."""
    return pilot.municipio("SP", nome)


def _uf() -> dict:
    return pilot.uf_view("SP")

CLASSES_HEX = {"Em alta", "Estável", "Sem obra nova"}


def _crescimento_municipal() -> pd.DataFrame:
    """Artefato municipal minimo. `cod6` de Sao Paulo e Campinas (fixture do piloto)."""
    return pd.DataFrame(
        [
            {
                "cod6": "355030",
                "cres_chave_nome": "SP|SAO PAULO",
                "cres_tendencia": "Estavel",
                "cres_emp_pct": 8.8,
                "cres_saldo_empresas": 61553.0,
                "cres_confiab": "alta",
                "cres_salario": 2501.0,
                "cres_salario_var": 3.7,
                "cres_setor": "Transporte e logística",
                "cres_uf_mediana": 9.0,
                "cres_dims": "Renda:25.8:%:25:2020→2024;Emprego:8.8:%:59:2022→jun/2026",
                "cres_series": "Renda|R$|2020|2024|3243,3500,3900,4200,4643",
                "v_frase": "São Paulo cresceu em empresas e emprego.",
            },
            {
                # Confiabilidade muito baixa zera a tendencia DE PROPOSITO, mas o
                # veredito existe. E o caso de 39% dos municipios do pais.
                "cod6": "350950",
                "cres_chave_nome": "SP|CAMPINAS",
                "cres_tendencia": None,
                "cres_emp_pct": 4.2,
                "cres_saldo_empresas": 900.0,
                "cres_confiab": "muito_baixa",
                "cres_salario": 1900.0,
                "cres_salario_var": 1.1,
                "cres_setor": "Comércio",
                "cres_uf_mediana": 9.0,
                "cres_dims": "Renda:12.0:%:30:2020→2024",
                "cres_series": "Renda|R$|2020|2024|2000,2100,2200,2300,2400",
                "v_frase": "Campinas cresceu em renda.",
            },
        ]
    )


@pytest.fixture
def com_crescimento(synth_data: Path) -> Path:  # noqa: F811
    """Fixture do piloto + os dois artefatos do passo 4."""
    staging = synth_data / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    _crescimento_municipal().to_parquet(staging / "crescimento_municipal.parquet", index=False)
    enr = pd.read_parquet(synth_data / "outputs" / "hexagonos_dashboard_enriquecido")
    pd.DataFrame(
        {
            "hex_id": enr["hex_id"].astype(str),
            "cres_hex_taxa": [12.0, 45.0, -3.0, 200.0] * (len(enr) // 4) + [0.0] * (len(enr) % 4),
            "cres_hex_classe": ["Estável", "Em alta", "Sem obra nova", "Em alta"]
            * (len(enr) // 4)
            + ["Estável"] * (len(enr) % 4),
        }
    ).to_parquet(staging / "crescimento_hex.parquet", index=False)
    pilot.carregar_crescimento.cache_clear()
    pilot.carregar_crescimento_hex.cache_clear()
    pilot.carregar_uf.cache_clear()
    return synth_data


# ---------------------------------------------------------------------------
# Estrutura do funil — pina a renumeracao
# ---------------------------------------------------------------------------


def test_funil_do_municipio_tem_cinco_passos_em_ordem(com_crescimento: Path) -> None:
    passos = _muni()["passos"]
    assert [p["n"] for p in passos] == [1, 2, 3, 4, 5]
    assert passos[3]["titulo"] == "Como a cidade está indo"
    assert passos[4]["titulo"] == "Para onde crescer"


def test_funil_da_uf_tem_cinco_passos_em_ordem(com_crescimento: Path) -> None:
    passos = _uf()["passos"]
    assert [p["n"] for p in passos] == [1, 2, 3, 4, 5]
    assert passos[3]["titulo"] == "Como as cidades estão indo"


def test_todo_passo_tem_os_campos_do_contrato(com_crescimento: Path) -> None:
    obrigatorios = {
        "n", "mode", "titulo", "narrativa",
        "funil_big", "funil_unit", "funil_from", "metrica", "itens", "hexes",
    }
    for nome, payload in (("municipio", _muni()), ("uf", _uf())):
        for p in payload["passos"]:
            assert obrigatorios <= set(p), f"{nome} passo {p.get('n')}"


# ---------------------------------------------------------------------------
# O veredito e a degradacao
# ---------------------------------------------------------------------------


def test_veredito_aparece_mesmo_sem_tendencia(com_crescimento: Path) -> None:
    """Campinas tem confiabilidade muito baixa (tendencia nula) e veredito presente.

    Testar a tendencia primeiro escondia o veredito em 39% dos municipios do pais.
    """
    passos = _muni("Campinas")["passos"]
    narrativa = passos[3]["narrativa"]
    assert "Campinas cresceu em renda." in narrativa
    assert "Sem leitura de crescimento" not in narrativa
    assert "Confiabilidade baixa" in narrativa


def test_degrada_sem_artefato(synth_data: Path) -> None:  # noqa: F811
    """Sem os parquets o passo 4 existe, avisa, e nao derruba nada."""
    for payload in (_muni(), _uf()):
        p4 = payload["passos"][3]
        assert p4["n"] == 4
        assert p4["funil_big"] == 0
        assert "Sem leitura" in p4["narrativa"] or "não está disponível" in p4["narrativa"]


# ---------------------------------------------------------------------------
# O join: por codigo e pelo fallback de nome
# ---------------------------------------------------------------------------


def test_fallback_por_nome_quando_cod_municipio_e_nulo(com_crescimento: Path) -> None:
    """O M1 deixa `cod_municipio` 100% nulo em 21 UFs; sem o fallback elas ficam vazias."""
    cres = pilot.carregar_crescimento()
    assert cres is not None
    # `carregar_uf` ja juntou; parte-se do df CRU para exercitar o join de verdade.
    cru = pilot.carregar_uf("SP").drop(columns=[c for c in cres.columns if c != "cod6"], errors="ignore")
    sem_cod = cru.assign(cod_municipio=pd.NA)
    juntado = pilot._juntar_crescimento(sem_cod, cres, "SP")
    assert juntado["v_frase"].notna().any(), "fallback por nome nao casou nenhuma linha"
    assert len(juntado) == len(sem_cod), "o merge inflou linhas"


def test_join_nao_infla_linhas(com_crescimento: Path) -> None:
    df = pilot.carregar_uf("SP")
    assert len(df) == len(df.drop_duplicates("hex_id"))


def test_join_falha_alto_com_cod6_duplicado(com_crescimento: Path) -> None:
    """`validate="m:1"`: artefato duplicado deve estourar, nao duplicar hexagono."""
    cres = pd.concat([pilot.carregar_crescimento()] * 2, ignore_index=True)
    with pytest.raises(pd.errors.MergeError):
        pilot._juntar_crescimento(pilot.carregar_uf("SP"), cres, "SP")


# ---------------------------------------------------------------------------
# Contrato de saida
# ---------------------------------------------------------------------------


def test_hex_nao_carrega_as_strings_municipais(com_crescimento: Path) -> None:
    """`cres_dims`/`cres_series` sao municipais: repetidos por hexagono levavam
    /api/uf/SP de 3,6 para 19,45 MB. Vao no passo e no item do ranking."""
    hexes = _muni()["hexes"]
    assert hexes, "fixture sem hexagonos"
    for proibido in ("cres_dims", "cres_series", "cres_serie"):
        assert proibido not in hexes[0], f"{proibido} voltou para o payload por hexagono"


def test_dims_e_series_vem_uma_vez_no_passo(com_crescimento: Path) -> None:
    p4 = _muni()["passos"][3]
    assert p4["dims"] and "Renda:" in p4["dims"]
    assert p4["series"] and "Renda|" in p4["series"]


def test_tendencia_sai_acentuada(com_crescimento: Path) -> None:
    """O artefato guarda o identificador sem acento; a tela mostra texto acentuado."""
    hexes = _muni()["hexes"]
    tends = {h.get("cres_tend") for h in hexes if h.get("cres_tend")}
    assert "Estavel" not in tends
    assert tends <= {"Em alta", "Estável", "Em queda"}


def test_classe_do_hexagono_esta_no_vocabulario_do_front(com_crescimento: Path) -> None:
    """`crescClasseToColor` compara string literal: classe fora do conjunto vira
    "sem medicao" em silencio."""
    hexes = _muni()["hexes"]
    classes = {h.get("cres_hex_classe") for h in hexes if h.get("cres_hex_classe")}
    assert classes <= CLASSES_HEX, f"classe fora do vocabulario do front: {classes - CLASSES_HEX}"


def test_payload_e_json_valido_sem_nan(com_crescimento: Path) -> None:
    """NaN quebra o JSON.parse do cliente; `_num`/`_texto` existem para isso."""
    import json

    for payload in (_muni(), _uf()):
        json.dumps(payload, allow_nan=False)
