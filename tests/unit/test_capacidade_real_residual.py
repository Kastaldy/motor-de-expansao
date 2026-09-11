"""Capacidade REAL por unidade no residual (BLK-CAPACIDADE-01).

Ate' aqui toda academia do pais consumia os mesmos **2.500 alunos** — um proxy, e o
proprio nome da constante dizia isso. O crosswalk do BLK-ALUNOS-01 casou 1.202 unidades
com o numero que a rede informou; onde ele existe, nao ha' motivo para usar o proxy.

**A armadilha que estes testes existem para travar.** Quando a capacidade varia por
unidade, `oferta_consumida / 2.500` DEIXA DE SER UMA CONTAGEM. Um Smart Fit de 5.000
alunos apareceria como "2 concorrentes" e mandaria o hexagono de `Adensar` para
`Disputa` por ser GRANDE, nao por ter vizinho. Por isso as duas grandezas se separam:

  * `oferta_efetiva_1km_area`      -> unidades-equivalentes (quem me cerca)
  * `consumo_concorrentes_1km_area`-> alunos de verdade (o que sai do mercado)
  * `n_concorrentes_influencia_1km`-> a contagem, e e' ela que a tela passa a ler
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import (
    anexar_capacidade_real,
    unir_cadeias,
)
from motor_expansao.pipelines.pressao_concorrencial_1km import repartir_concorrentes

CAP_PADRAO = 2_500.0


def _uma(lat: float = -23.55, lng: float = -46.63, **extra) -> pd.DataFrame:
    return pd.DataFrame([{"lat": lat, "lng": lng, **extra}])


# --------------------------------------------------------------------------- #
# O modelo de 1 km com capacidade por unidade                                  #
# --------------------------------------------------------------------------- #


def test_sem_a_coluna_o_consumo_e_o_proxy_vezes_a_oferta() -> None:
    """Compatibilidade com artefato antigo -- e a ressalva honesta sobre ela.

    NAO e' bit a bit. Antes o consumo era `soma(shares) * 2.500`, uma multiplicacao no
    fim; agora e' `soma(share * capacidade)`, acumulada unidade a unidade. A ORDEM das
    operacoes em ponto flutuante mudou, e um caso de uma academia so' devolve
    2499,999999999998 no lugar de 2500. E' erro relativo de ~1e-12 e nao muda decisao
    nenhuma, mas esta escrito aqui para ninguem concluir, mais tarde, que uma diferenca
    na ultima casa entre duas regeneracoes e' sintoma de outra coisa.
    """
    out = repartir_concorrentes(_uma())
    assert out["consumo_concorrentes_1km_area"].sum() == pytest.approx(CAP_PADRAO, rel=1e-9)
    assert round(float(out["oferta_efetiva_1km_area"].sum()), 6) == 1.0


def test_com_a_coluna_o_consumo_e_a_capacidade_da_unidade() -> None:
    out = repartir_concorrentes(
        _uma(capacidade_alunos=5000.0), coluna_capacidade="capacidade_alunos"
    )
    assert round(float(out["consumo_concorrentes_1km_area"].sum()), 3) == 5000.0
    # A oferta em UNIDADES nao se move: continua uma academia.
    assert round(float(out["oferta_efetiva_1km_area"].sum()), 6) == 1.0


def test_unidade_sem_capacidade_cai_no_proxy() -> None:
    """A rede sem planilha continua valendo 2.500 -- ausencia nao vira zero."""
    df = pd.DataFrame(
        [
            {"lat": -23.55, "lng": -46.63, "capacidade_alunos": 4000.0},
            {"lat": -23.55, "lng": -46.63, "capacidade_alunos": None},
        ]
    )
    out = repartir_concorrentes(df, coluna_capacidade="capacidade_alunos")
    assert round(float(out["consumo_concorrentes_1km_area"].sum()), 3) == 6500.0


def test_oferta_e_consumo_deixam_de_ser_proporcionais() -> None:
    """E' o ponto do bloco, e o motivo de a contagem ter de mudar de fonte.

    Enquanto a capacidade era uniforme, consumo/2500 devolvia a contagem. Com capacidade
    real isso vira uma razao sem significado -- e quem dividir vai ler academia GRANDE
    como DUAS academias.
    """
    out = repartir_concorrentes(
        _uma(capacidade_alunos=7500.0), coluna_capacidade="capacidade_alunos"
    )
    oferta = float(out["oferta_efetiva_1km_area"].sum())
    consumo = float(out["consumo_concorrentes_1km_area"].sum())
    assert round(consumo / CAP_PADRAO, 1) == 3.0, "a divisao daria 3 concorrentes..."
    assert round(oferta, 6) == 1.0, "...mas ha UMA academia"
    assert int(out["n_concorrentes_influencia_1km"].max()) == 1


def test_massa_conservada_com_capacidade_variavel() -> None:
    """O share continua fechando em 1,0 por unidade; so' o peso muda."""
    df = pd.DataFrame(
        [
            {"lat": -23.55, "lng": -46.63, "capacidade_alunos": 1000.0},
            {"lat": -23.60, "lng": -46.70, "capacidade_alunos": 3000.0},
        ]
    )
    out = repartir_concorrentes(df, coluna_capacidade="capacidade_alunos")
    assert round(float(out["consumo_concorrentes_1km_area"].sum()), 3) == 4000.0
    assert round(float(out["oferta_efetiva_1km_area"].sum()), 6) == 2.0


def test_capacidade_negativa_e_saneada() -> None:
    out = repartir_concorrentes(
        _uma(capacidade_alunos=-500.0), coluna_capacidade="capacidade_alunos"
    )
    assert float(out["consumo_concorrentes_1km_area"].sum()) == 0.0


# --------------------------------------------------------------------------- #
# O join da capacidade real                                                    #
# --------------------------------------------------------------------------- #


def _crosswalk(tmp_path, linhas: list[dict]):
    caminho = tmp_path / "alunos.parquet"
    pd.DataFrame(linhas).to_parquet(caminho)
    return caminho


def _cadeias() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rede": ["smart_fit", "bluefit"],
            "lat": [-23.55, -23.60],
            "lng": [-46.63, -46.70],
            "status_registro": ["valido", "valido"],
            "concorrente_id": ["c1", "c2"],
        }
    )


def test_capacidade_real_chega_a_unidade_casada(tmp_path) -> None:
    cw = _crosswalk(
        tmp_path,
        [{"concorrente_id": "c1", "alunos_total": 4200.0, "confianca_match": "alta"}],
    )
    out = anexar_capacidade_real(_cadeias(), crosswalk_path=cw)
    assert out.set_index("concorrente_id").loc["c1", "capacidade_alunos"] == 4200.0


def test_unidade_sem_crosswalk_fica_NULA_e_nao_2500(tmp_path) -> None:
    """Preencher aqui esconderia do artefato quantas sao medidas e quantas estimadas.

    Quem consome decide o default -- e' o `repartir_concorrentes` que aplica o proxy.
    """
    cw = _crosswalk(
        tmp_path,
        [{"concorrente_id": "c1", "alunos_total": 4200.0, "confianca_match": "alta"}],
    )
    out = anexar_capacidade_real(_cadeias(), crosswalk_path=cw)
    assert pd.isna(out.set_index("concorrente_id").loc["c2", "capacidade_alunos"])


def test_confianca_media_nao_vira_capacidade(tmp_path) -> None:
    """A rota de contencao e' inferencia, e capacidade mexe no residual DE TODOS em volta.

    Um numero inferido no tooltip afeta uma linha; virando capacidade, ele desloca a
    oferta de todo hexagono que aquele disco de 1 km alcanca.
    """
    cw = _crosswalk(
        tmp_path,
        [{"concorrente_id": "c1", "alunos_total": 9999.0, "confianca_match": "media"}],
    )
    out = anexar_capacidade_real(_cadeias(), crosswalk_path=cw)
    assert out["capacidade_alunos"].isna().all()


def test_crosswalk_ausente_e_caminho_normal(tmp_path) -> None:
    """O parquet nao e' versionado: sem ele, todo mundo cai no proxy, como antes."""
    out = anexar_capacidade_real(_cadeias(), crosswalk_path=tmp_path / "nao_existe.parquet")
    assert "capacidade_alunos" not in out.columns


def test_unir_cadeias_carrega_o_concorrente_id() -> None:
    """Sem ele a capacidade nao teria por onde casar -- depois so' ha agregado por hex."""
    comp = pd.DataFrame(
        {
            "rede": ["smart_fit"],
            "lat": [-23.55],
            "lng": [-46.63],
            "status_registro": ["valido"],
            "concorrente_id": ["c1"],
        }
    )
    feed = pd.DataFrame(
        {"rede": ["bluefit"], "lat": [-23.60], "lng": [-46.70], "tem_pin_proprio": [True]}
    )
    unido = unir_cadeias(comp, feed)
    assert "concorrente_id" in unido.columns
    assert set(unido["concorrente_id"].dropna()) == {"c1"}
    # A do agregador entra sem id -- ela nao tem, e fingir que tem casaria errado.
    assert unido["concorrente_id"].isna().sum() == 1


# --------------------------------------------------------------------------- #
# A coluna tem de CHEGAR — as duas projeções                                   #
# --------------------------------------------------------------------------- #


def test_a_contagem_esta_nas_DUAS_listas_de_projecao() -> None:
    """O defeito da família DEC-038 na forma mais pura, e ele aconteceu neste bloco.

    `n_concorrentes_influencia_1km` nasce em `hexagonos_mercado_mapeado`, precisa ser
    materializada no enriquecido (`RESIDUAL_MERCADO_COLS`) e depois LIDA pelo piloto
    (`_COLS_DESEJADAS`). Esquecer o nome em qualquer uma das duas devolve campo vazio sem
    erro: o pipeline roda verde, o artefato sai sem a coluna e a tela cai no ramo antigo
    (`oferta_consumida / capacidade`) — que, com capacidade real por unidade, deixa de
    contar academias.

    Na primeira regeneração deste bloco a coluna faltou na primeira lista, e só apareceu
    ao conferir o schema do enriquecido à mão antes do deploy. Este teste existe para essa
    conferência não depender de alguém lembrar de fazê-la.
    """
    from motor_expansao.dashboard.constants import RESIDUAL_MERCADO_COLS

    assert "n_concorrentes_influencia_1km" in RESIDUAL_MERCADO_COLS

    app_py = (
        Path(__file__).resolve().parents[2] / "web" / "server" / "app.py"
    ).read_text(encoding="utf-8")
    inicio = app_py.index("_COLS_DESEJADAS = [")
    bloco = app_py[inicio : app_py.index("]", inicio)]
    assert '"n_concorrentes_influencia_1km"' in bloco, (
        "a coluna sumiu da projecao que o piloto le"
    )


def test_RESIDUAL_MERCADO_COLS_e_UM_OBJETO_SO() -> None:
    """Identidade, nao igualdade — e a diferenca e o bloco inteiro.

    Ate' 2026-09-10 existiam DUAS listas com esse nome, uma em `dashboard/constants.py` e
    outra em `gerar_carteira_acionavel.py`, e elas nao se enxergavam: acrescentar coluna
    numa so' era no-op SILENCIOSO. O teste que existia aqui comparava
    `set(A) == set(B)` — e um teste de conjunto continua PASSANDO com duas copias, entao
    ele travava a divergencia de hoje sem impedir que a divergencia de amanha nascesse.

    Agora ha' uma fonte unica em `constants.py` e o pipeline RE-EXPORTA o nome. `is` e' o
    unico assert que constata isso: se alguem redigitar o literal, o conteudo pode ate'
    coincidir, mas o objeto nao.
    """
    from motor_expansao.dashboard import constants
    from motor_expansao.pipelines import gerar_carteira_acionavel

    assert constants.RESIDUAL_MERCADO_COLS is gerar_carteira_acionavel.RESIDUAL_MERCADO_COLS, (
        "o pipeline deixou de RE-EXPORTAR a fonte unica e voltou a ter lista propria"
    )

    # O terceiro consumidor importa o nome do pipeline (e nao de `constants`); a cadeia
    # inteira tem de pousar no mesmo objeto, senao a unificacao vale so' para dois tercos.
    from motor_expansao.pipelines import enriquecer_outputs_residual_mercado as enriquecer

    assert enriquecer.RESIDUAL_MERCADO_COLS is constants.RESIDUAL_MERCADO_COLS


# --------------------------------------------------------------------------- #
# Injecao: a fonte unica realmente MANDA nas projecoes derivadas               #
# --------------------------------------------------------------------------- #


COLUNA_SINTETICA = "coluna_sintetica_so_de_teste"


def test_injetar_coluna_na_fonte_unica_chega_a_LOAD_COLS() -> None:
    """Injecao de verdade: mexer na fonte unica muda a projecao do pipeline.

    Containment (`set(fonte) <= set(LOAD_COLS)`) passaria mesmo se alguem trocasse o
    `*RESIDUAL_MERCADO_COLS` por uma copia literal dos 18 nomes. Este teste falsifica isso:
    poe uma coluna que NAO existe em lugar nenhum e exige que ela apareca.

    `LOAD_COLS` e' montada por unpacking no IMPORT, entao a injecao precisa do `reload` —
    e' a arquitetura, nao uma escolha do teste. Sem monkeypatch de proposito: o `finally`
    tem de rodar DEPOIS do reload de restauracao, e a ordem de teardown do monkeypatch nao
    garante isso.
    """
    import importlib

    from motor_expansao.dashboard import constants
    from motor_expansao.pipelines import gerar_carteira_acionavel

    original = constants.RESIDUAL_MERCADO_COLS
    try:
        constants.RESIDUAL_MERCADO_COLS = [*original, COLUNA_SINTETICA]
        recarregado = importlib.reload(gerar_carteira_acionavel)
        assert COLUNA_SINTETICA in recarregado.RESIDUAL_MERCADO_COLS
        assert COLUNA_SINTETICA in recarregado.LOAD_COLS, (
            "LOAD_COLS parou de derivar da fonte unica"
        )
    finally:
        constants.RESIDUAL_MERCADO_COLS = original
        importlib.reload(gerar_carteira_acionavel)

    assert COLUNA_SINTETICA not in gerar_carteira_acionavel.LOAD_COLS


def test_injetar_coluna_na_fonte_unica_chega_a_carregar_colunas_residual_mercado(
    tmp_path, monkeypatch
) -> None:
    """A leitura do parquet de mercado pede as colunas pela lista, em tempo de CHAMADA.

    Aqui o monkeypatch basta (a funcao le' o global a cada chamada), entao da' para provar
    o caminho ponta a ponta: coluna sintetica na lista -> coluna sintetica no frame lido.
    """
    from motor_expansao.pipelines import gerar_carteira_acionavel as gca

    mercado = tmp_path / "mercado.parquet"
    pd.DataFrame(
        {
            "hex_id": ["87a8100efffffff", "87a8100e0ffffff"],
            "oferta_efetiva_disponivel": [10.0, 20.0],
            COLUNA_SINTETICA: [1, 2],
        }
    ).to_parquet(mercado)

    monkeypatch.setattr(
        gca,
        "RESIDUAL_MERCADO_COLS",
        [*gca.RESIDUAL_MERCADO_COLS, COLUNA_SINTETICA],
    )
    lido = gca.carregar_colunas_residual_mercado(mercado)
    assert COLUNA_SINTETICA in lido.columns, (
        "a projecao de leitura do mercado nao pergunta a fonte unica"
    )


def test_HYBRID_LOAD_COLS_deriva_da_fonte_unica() -> None:
    """O mais proximo possivel para `HYBRID_LOAD_COLS` — e por que nao da' para mais.

    Ela vive no MESMO modulo que a fonte unica e e' montada por unpacking no import.
    Injetar exigiria recarregar `constants`, o que reconstroi a propria lista a partir do
    literal e apaga a injecao — circular por construcao. O que resta e' containment: se
    alguem acrescentar a 19a coluna a fonte unica e `HYBRID_LOAD_COLS` tiver virado copia
    literal, este assert fica vermelho, que e' exatamente o cenario do incidente.
    """
    from motor_expansao.dashboard.constants import (
        HYBRID_LOAD_COLS,
        RESIDUAL_MERCADO_COLS,
    )

    faltam = [c for c in RESIDUAL_MERCADO_COLS if c not in HYBRID_LOAD_COLS]
    assert not faltam, f"HYBRID_LOAD_COLS parou de derivar da fonte unica: {faltam}"


# --------------------------------------------------------------------------- #
# Tipagem declarada dos dois lados                                             #
# --------------------------------------------------------------------------- #


#: Colunas de `RESIDUAL_MERCADO_COLS` que NAO recebem tipagem no lado do dashboard, com a
#: razao medida. Lista de excecoes e' divida declarada, nao permissao: qualquer nome novo
#: aqui precisa vir com a medicao ao lado.
SEM_TIPAGEM_NO_DASHBOARD = {
    # E' uma CONTAGEM inteira. `FLOAT_COLUMNS` coage com `.astype("Float32")` e mudaria o
    # schema do artefato enriquecido -- medido em `uf=SP/parte-0.parquet` (2026-09-10):
    # a coluna sai `int64` hoje e viraria `float`. Nao existe lista de inteiros no
    # dashboard; criar uma mexe em `_prepare_dataframe` e no schema, e isso e' PR proprio.
    "n_concorrentes_influencia_1km": "contagem int64; Float32 mudaria o schema do artefato",
}

#: Do lado do PIPELINE nao existe coercao de texto -- `_coerce_types` so' tem
#: NUMERIC_COLUMNS e BOOL_COLUMNS. As colunas de texto sao declaradas so' no dashboard, e
#: isso e' desenho, nao esquecimento.
SEM_TIPAGEM_NO_PIPELINE = {"fonte_pop_hex_base", "quartil_oportunidade_residual",
                           "prioridade_mercado_mapeado", "tese_entrada"}


def test_toda_coluna_de_mercado_tem_tipagem_declarada_no_dashboard() -> None:
    """Coluna sem tipagem chega ao piloto com o dtype que o parquet der — inclusive `object`.

    Foi assim que a familia DEC-038 machucou: o valor existe, o tipo esta errado e nada
    grita. Este teste exige declaracao EXPLICITA (uma lista, exatamente uma) ou entrada na
    lista de excecoes com a razao escrita.
    """
    from motor_expansao.dashboard.constants import (
        BOOL_COLUMNS,
        FLOAT_COLUMNS,
        RESIDUAL_MERCADO_COLS,
        TEXT_COLUMNS,
    )

    listas = {"FLOAT_COLUMNS": FLOAT_COLUMNS, "BOOL_COLUMNS": BOOL_COLUMNS,
              "TEXT_COLUMNS": TEXT_COLUMNS}
    for coluna in RESIDUAL_MERCADO_COLS:
        onde = [nome for nome, lista in listas.items() if coluna in lista]
        if coluna in SEM_TIPAGEM_NO_DASHBOARD:
            assert not onde, (
                f"{coluna} esta' na excecao de tipagem mas foi declarada em {onde}; "
                "tirar da excecao e medir o efeito no schema"
            )
            continue
        assert len(onde) == 1, f"{coluna} deveria estar em UMA lista de tipagem, esta' em {onde}"


def test_toda_coluna_de_mercado_tem_tipagem_coerente_no_pipeline() -> None:
    """As duas coercoes tem de concordar: float la', numerico aqui; bool la', bool aqui.

    Uma coluna declarada FLOAT no dashboard e ausente do `NUMERIC_COLUMNS` do pipeline sai
    do `gerar_carteira_acionavel` com o dtype cru do parquet e so' e' consertada na leitura
    — quem consumir o CSV/parquet da carteira le' o tipo errado.
    """
    from motor_expansao.dashboard.constants import (
        BOOL_COLUMNS as DASH_BOOL,
    )
    from motor_expansao.dashboard.constants import (
        FLOAT_COLUMNS as DASH_FLOAT,
    )
    from motor_expansao.dashboard.constants import (
        RESIDUAL_MERCADO_COLS,
    )
    from motor_expansao.pipelines.gerar_carteira_acionavel import (
        BOOL_COLUMNS as PIPE_BOOL,
    )
    from motor_expansao.pipelines.gerar_carteira_acionavel import (
        NUMERIC_COLUMNS as PIPE_NUMERIC,
    )

    for coluna in RESIDUAL_MERCADO_COLS:
        if coluna in SEM_TIPAGEM_NO_PIPELINE:
            assert coluna not in PIPE_NUMERIC and coluna not in PIPE_BOOL
            continue
        if coluna in DASH_FLOAT:
            assert coluna in PIPE_NUMERIC, f"{coluna} e' FLOAT no dashboard e nao e' numerica no pipeline"
            assert coluna not in PIPE_BOOL
        elif coluna in DASH_BOOL:
            assert coluna in PIPE_BOOL, f"{coluna} e' BOOL no dashboard e nao e' bool no pipeline"
            assert coluna not in PIPE_NUMERIC
        else:
            # Sobra so' a excecao do dashboard; ela ainda precisa de tipagem no pipeline,
            # onde `pd.to_numeric` preserva o int64 e nao mexe no schema.
            assert coluna in SEM_TIPAGEM_NO_DASHBOARD
            assert coluna in PIPE_NUMERIC, f"{coluna} nao tem tipagem em nenhum dos dois lados"


def test_a_contagem_esta_na_rede_que_recusa_artefato_mutilado() -> None:
    """`COLUNAS_CRITICAS_ENRIQUECIDO` e' a rede que RECUSA escrever o enriquecido sem a coluna.

    Ela existia e nao cobria justamente a coluna do incidente: o pipeline rodou verde tres
    vezes e o artefato saiu mutilado. Sem ela, `n_concorrentes_est` cai no ramo legado
    (`oferta_consumida / capacidade`) que, com capacidade REAL por unidade (DEC-057), le'
    academia GRANDE como DUAS.
    """
    from motor_expansao.pipelines.m1.fase1_bi_exports import (
        COLUNAS_CRITICAS_ENRIQUECIDO,
        verificar_colunas_criticas,
    )

    assert "n_concorrentes_influencia_1km" in COLUNAS_CRITICAS_ENRIQUECIDO

    frame = pd.DataFrame({c: [1.0] for c in COLUNAS_CRITICAS_ENRIQUECIDO})
    verificar_colunas_criticas(frame)  # completo: nao levanta

    with pytest.raises(ValueError) as erro:
        verificar_colunas_criticas(frame.drop(columns=["n_concorrentes_influencia_1km"]))
    # A dica tem de apontar o passo que faltou rodar -- antes ela so' disparava para
    # colunas com prefixo `oferta_`, e esta nao tem.
    assert "enriquecer_outputs_residual_mercado" in str(erro.value)
