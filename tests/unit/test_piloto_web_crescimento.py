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

# O que a API ENVIA (rotulo de exibicao). O identificador no parquet e ASCII —
# `CLASSES_BRUTAS` abaixo — e a traducao mora em `_ROTULO_CLASSE`. A paridade dos
# dois com o `colors.ts` e travada em `test_paridade_classe_crescimento_web.py`.
CLASSES_HEX = {"Em alta", "Estável", "Sem obra nova"}
CLASSES_BRUTAS = {"Em alta", "Estavel", "Sem obra nova"}


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
            # Sem acento, como o gerador grava (08_populacao_e_hex.py, CORTES). Se a
            # fixture gravasse o rotulo pronto, o teste de acentuacao passaria de graca.
            "cres_hex_classe": ["Estavel", "Em alta", "Sem obra nova", "Em alta"]
            * (len(enr) // 4)
            + ["Estavel"] * (len(enr) % 4),
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
# O chip do ranking — posicao relativa, nao corte absoluto
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "mediana", "etiqueta", "tom"),
    [
        # Queda de verdade: unica leitura ABSOLUTA que sobrevive, e nomeia a metrica
        # ("emprego") para nao ser confundida com a classe do hexagono no mapa.
        (-3.0, 6.0, "emprego em queda", "red"),
        (-0.1, 6.0, "emprego em queda", "red"),
        # Multiplos da mediana da UF.
        (18.0, 6.0, "3× a mediana do estado", "green"),
        (12.0, 6.0, "2× a mediana do estado", "green"),
        (11.9, 6.0, "acima da mediana do estado", "green"),
        (6.0, 6.0, "na mediana do estado", "gray"),
        # Sem casos EXATOS na fronteira: 4.8/6.0 da 0.7999999999999999 em float, e o
        # teste passaria a medir o binario em vez da regra.
        (5.0, 6.0, "na mediana do estado", "gray"),
        (4.5, 6.0, "abaixo da mediana do estado", "amber"),
        # Sem valor: chip vazio, e nao um chip errado.
        (None, 6.0, "", None),
    ],
)
def test_chip_de_crescimento_por_ramo(valor, mediana, etiqueta, tom) -> None:
    """Cada ramo de `_etiqueta_crescimento`, direto — sem passar pelo funil.

    O ramo anterior era um corte absoluto (>=15 "Em alta", >=2 "Estável", senao "Em
    queda") com tres defeitos: colidia com o vocabulario que pinta o mapa, era
    CONSTANTE no top-10 (a lista ja e o topo, entao um corte nacional nunca varia
    dentro dela) e dava chip VERMELHO para cidade que cresceu +1%.
    """
    assert pilot._etiqueta_crescimento(valor, mediana) == (etiqueta, tom)


def test_chip_nunca_repete_o_vocabulario_do_mapa() -> None:
    """A colisao que motivou a mudanca: chip e mapa mediam coisas diferentes com as
    MESMAS palavras — emprego formal (CAGED, municipal) contra area construida
    (satelite, por hexagono). Uma cidade podia sair verde "Em alta" com todos os
    hexagonos cinza "Sem obra nova"."""
    saidas = {
        pilot._etiqueta_crescimento(v, m)[0]
        for v in (-5.0, 0.5, 3.0, 7.0, 13.0, 40.0)
        for m in (2.8, 6.0, 12.7)  # amplitude real da mediana por UF no artefato
    }
    assert not (saidas & CLASSES_HEX), f"o chip fala o idioma do mapa: {saidas & CLASSES_HEX}"
    assert not (saidas & CLASSES_BRUTAS)


def test_chip_varia_dentro_de_um_top_10() -> None:
    """Um chip que nao varia no unico lugar onde aparece nao informa nada.

    Top-10 plausivel de uma UF com mediana +6,0%: pelo corte antigo (>=15) os dez
    sairiam "Em alta"; pela regua relativa eles se separam.
    """
    top10 = [31.0, 25.0, 25.0, 21.0, 20.0, 19.0, 19.0, 16.0, 16.0, 15.0]
    etiquetas = [pilot._etiqueta_crescimento(v, 6.0)[0] for v in top10]
    assert len(set(etiquetas)) >= 3, f"chip quase constante no top-10: {set(etiquetas)}"


def test_chip_atravessa_o_funil_de_verdade(com_crescimento: Path) -> None:
    """Mesma checagem, mas POR `montar_funil_uf` — nao chamando a funcao direto.

    `docs/contrato_api_metodologia.md` registra o modo de falha: um contrato de
    etiqueta validado so por chamada direta passa verde sobre vocabulario que o funil
    nunca emite (o caso citado la usa `n_concorrentes_est` = 2 e 99 quando a base do
    passo e' `white`, com n == 0). Entao alem dos ramos, o chip tem que ser conferido
    no caminho que a tela realmente percorre.
    """
    itens = _uf()["passos"][3]["itens"]
    assert itens, "o passo 4 da UF saiu sem ranking — o teste nao provaria nada"
    tags = {it["tag"] for it in itens}
    assert all(tags), "item do ranking sem chip"
    assert not (tags & CLASSES_HEX), f"o chip fala o idioma do mapa: {tags & CLASSES_HEX}"
    assert not (tags & CLASSES_BRUTAS)
    # E o chip tem que citar a regua que usa, senao o numero fica sem escala.
    assert all("estado" in t or "média" in t for t in tags), tags


def test_mediana_perto_de_zero_cai_no_ramo_de_pontos_percentuais() -> None:
    """Defesa: com mediana ~0 a razao explode e "10× a mediana" elogiaria um municipio
    que cresceu 5% num estado parado. Nenhuma UF do artefato atual chega la (a mediana
    vai de +2,8% a +12,7%), mas um recorte novo pode."""
    assert pilot._etiqueta_crescimento(5.0, 0.2) == ("acima do estado", "green")
    assert pilot._etiqueta_crescimento(15.0, 0.2) == ("muito acima do estado", "green")
    assert pilot._etiqueta_crescimento(1.0, 0.2) == ("na média do estado", "gray")
    assert pilot._etiqueta_crescimento(5.0, None) == ("acima do estado", "green")


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


def test_hex_nao_carrega_nada_de_municipal(com_crescimento: Path) -> None:
    """NENHUM valor broadcast municipal pode viajar por hexagono.

    Duas rodadas do mesmo erro: primeiro `cres_dims`/`cres_series` (3,6 -> 19,45 MB em
    /api/uf/SP), depois os seis campos do tooltip, que ficaram com a desculpa de serem
    "curtos o bastante" — eram 1,87 MB em SP (6,58 -> 4,71). O hex so pode carregar o
    que varia POR hexagono, mais a chave da cidade.
    """
    hexes = _muni()["hexes"]
    assert hexes, "fixture sem hexagonos"
    proibidos = (
        "cres_dims", "cres_series", "cres_serie",          # strings longas
        "cres_tend", "cres_emp", "cres_empresas",          # tooltip municipal
        "cres_salario", "cres_setor", "cres_uf_mediana",
        "cres_confiab",                                     # so server-side
    )
    for proibido in proibidos:
        assert proibido not in hexes[0], f"{proibido} voltou para o payload por hexagono"
    # E o que SOBRA tem que continuar la, senao o mapa perde a cor da camada.
    assert "cres_hex_classe" in hexes[0] and "cres_hex_taxa" in hexes[0]
    assert "mun" in hexes[0], "sem a chave da cidade o tooltip nao acha o bloco municipal"


def test_bloco_municipal_vem_uma_vez_por_cidade(com_crescimento: Path) -> None:
    """O que saiu do hexagono tem que CHEGAR em algum lugar — senao a economia de
    payload e so perda de informacao."""
    for payload in (_muni(), _uf()):
        blocos = payload["cres_mun"]
        assert blocos, "nenhuma cidade com leitura no bloco municipal"
        # Chaveado pelo mesmo nome que o hexagono carrega.
        muns = {h["mun"] for h in payload["hexes"] if h.get("mun")}
        assert set(blocos) & muns, "as chaves do bloco nao casam com nenhum `Hex.mun`"
        um = next(iter(blocos.values()))
        assert set(um) == {"tend", "emp", "empresas", "salario", "setor", "uf_mediana"}
    # Uma entrada por cidade, nao por hexagono.
    uf = _uf()
    assert len(uf["cres_mun"]) <= len({h["mun"] for h in uf["hexes"] if h.get("mun")})


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


def test_classe_do_hexagono_sai_acentuada(com_crescimento: Path) -> None:
    """Gemeo de `test_tendencia_sai_acentuada`, para a outra coluna do mesmo balao.

    O parquet guarda o identificador ASCII; a tela mostra texto acentuado. Antes as
    duas colunas apareciam no mesmo tooltip escritas de formas diferentes, e o
    identificador acentuado era comparado por literal no `colors.ts` — regerar o
    artefato normalizado pintava a camada inteira de cinza, em silencio.
    """
    hexes = _muni()["hexes"]
    classes = {h.get("cres_hex_classe") for h in hexes if h.get("cres_hex_classe")}
    assert classes, "fixture sem classe de hexagono"
    assert "Estavel" not in classes, "a API vazou o identificador cru para a tela"
    assert classes <= CLASSES_HEX, f"classe fora do vocabulario do front: {classes - CLASSES_HEX}"


def test_payload_e_json_valido_sem_nan(com_crescimento: Path) -> None:
    """NaN quebra o JSON.parse do cliente; `_num`/`_texto` existem para isso."""
    import json

    for payload in (_muni(), _uf()):
        json.dumps(payload, allow_nan=False)
