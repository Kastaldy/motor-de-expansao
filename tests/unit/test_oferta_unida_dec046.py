"""DEC-046 — a oferta do Relatorio Pontual passa a unir 3 fontes, com `classe` por linha.

POR QUE ESTE ARQUIVO EXISTE. Antes da DEC-046 NENHUM teste exercitava `_competitors_ultra`:
as unicas 3 mencoes em `tests/` eram dois `monkeypatch.setattr(..., lambda cfg: (None, None))`
— que DESLIGAM a funcao — e uma citacao em docstring. Todo o resto do corpus injeta
`competitors_df=` sintetico direto no motor. Ou seja: o carregador que alimenta as 3 rotas de
producao nao tinha rede nenhuma embaixo, e a troca de universo entraria sem que a suite a
enxergasse.

Os parquets reais sao gitignored (`.gitignore:38 *.parquet`) e nao existem no CI nem no
container do loop. Por isso aqui tudo e' HERMETICO: fixtures sinteticas escritas em
`tmp_path`, sem depender de artefato de producao.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.api import service as sv
from motor_expansao.api.settings import Settings
from motor_expansao.dashboard.censo_point import (
    CLASSE_CADEIA_OFERTA,
    CLASSE_INDEPENDENTE_OFERTA,
    _contar_classe,
)

# Ponto de referencia das fixtures (centro de Londrina, o caso que originou a DEC-046).
LAT, LNG = -23.31896, -51.15666


def _settings(staging) -> Settings:
    return Settings(staging_dir=staging)


def _escrever(staging, nome: str, df: pd.DataFrame) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    df.to_parquet(staging / f"{nome}.parquet", index=False)


@pytest.fixture
def staging(tmp_path):
    """Tres fontes sinteticas, cada uma com uma armadilha propria embutida."""
    base = tmp_path / "staging"

    # cadeias mapeadas: 2 validas + 1 descartada + 1 com flag de coordenada invalida
    _escrever(base, sv.FONTE_MAPEADOS, pd.DataFrame({
        "rede": ["smart_fit", "bluefit", "bodytech", "pratique"],
        "nome_unidade": ["SF Centro", "BF Centro", "BT fantasma", "PR Miami"],
        "lat": [LAT + 0.001, LAT + 0.002, LAT + 0.003, 25.96],
        "lng": [LNG + 0.001, LNG + 0.002, LNG + 0.003, -80.14],
        "status_registro": ["valido", "valido", "descartado_duplicado", "descartado_coord"],
        "flag_coord_valida": [True, True, True, False],
    }))

    # cadeias do agregador: 1 com pin proprio + 1 que ja' colapsou contra um mapeado
    _escrever(base, sv.FONTE_REDES_AGREGADOR, pd.DataFrame({
        "rede": ["force_one", "smart_fit"],
        "nome": ["Force One Londrina", "SF duplicada"],
        "lat": [LAT + 0.004, LAT + 0.001],
        "lng": [LNG + 0.004, LNG + 0.001],
        "tem_pin_proprio": [True, False],
    }))

    # independentes: 1 distante de tudo + 1 praticamente em cima de uma cadeia (dedup <= 50 m)
    _escrever(base, sv.FONTE_INDEPENDENTES, pd.DataFrame({
        "nome": ["Academia Pura Vida", "Colada na Smart Fit"],
        "lat": [LAT + 0.006, LAT + 0.0010005],
        "lng": [LNG + 0.006, LNG + 0.0010005],
    }))
    return base


@pytest.fixture(autouse=True)
def _sem_cache():
    """`_oferta_unida` e' `lru_cache` — limpar entre testes evita vazamento de fixture."""
    sv._oferta_unida.cache_clear()
    yield
    sv._oferta_unida.cache_clear()


# --- uniao e classe ---------------------------------------------------------

def test_uniao_traz_as_tres_fontes_e_carimba_a_classe(staging):
    df, fontes = sv._oferta_unida(str(staging))
    assert set(fontes) == set(sv.FONTES_OFERTA)
    # 2 cadeias mapeadas validas + 1 do agregador com pin proprio + 1 independente
    assert len(df) == 4
    assert df["classe"].value_counts().to_dict() == {
        CLASSE_CADEIA_OFERTA: 3,
        CLASSE_INDEPENDENTE_OFERTA: 1,
    }


def test_independente_nunca_carrega_rede(staging):
    """A `classe` sai da ORIGEM, nao de heuristica de nome: independente nao tem `rede`."""
    df, _ = sv._oferta_unida(str(staging))
    indep = df[df["classe"] == CLASSE_INDEPENDENTE_OFERTA]
    assert indep["rede"].isna().all()
    assert (indep["nome"] == "Academia Pura Vida").all()


# --- os descartes que a coleta ja' marcou (D4) ------------------------------

def test_status_registro_derruba_o_fantasma_e_a_coordenada_lixo(staging):
    """Sem este filtro, 64 `bodytech` empilhadas numa coordenada do Rio viravam 64 pins."""
    df, _ = sv._oferta_unida(str(staging))
    assert "bodytech" not in set(df["rede"].dropna())
    # `descartado_coord` com coordenada NAO-nula era desenhada em Miami
    assert "pratique" not in set(df["rede"].dropna())


def test_tem_pin_proprio_impede_o_pin_duplicado_da_dec034(staging):
    """A unidade do agregador que colapsa contra um mapeado NAO pode ganhar pin proprio."""
    df, _ = sv._oferta_unida(str(staging))
    assert "SF duplicada" not in set(df["nome"].dropna())
    assert "Force One Londrina" in set(df["nome"].dropna())


# --- dedup das independentes (D5) -------------------------------------------

def test_independente_a_menos_de_50m_de_uma_cadeia_colapsa(staging):
    df, _ = sv._oferta_unida(str(staging))
    assert "Colada na Smart Fit" not in set(df["nome"].dropna())


def test_independente_longe_de_cadeia_sobrevive(staging):
    df, _ = sv._oferta_unida(str(staging))
    assert "Academia Pura Vida" in set(df["nome"].dropna())


# --- procedencia: o D7 depende disto ----------------------------------------

def test_fonte_ausente_e_declarada_e_nao_some_em_silencio(staging):
    (staging / f"{sv.FONTE_INDEPENDENTES}.parquet").unlink()
    sv._oferta_unida.cache_clear()
    df, fontes = sv._oferta_unida(str(staging))
    assert sv.FONTE_INDEPENDENTES not in fontes
    assert set(fontes) == {sv.FONTE_MAPEADOS, sv.FONTE_REDES_AGREGADOR}
    assert (df["classe"] == CLASSE_CADEIA_OFERTA).all()


def test_sem_nenhuma_fonte_devolve_none_e_lista_vazia(tmp_path):
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    df, fontes = sv._oferta_unida(str(vazio))
    assert df is None
    assert fontes == ()


def test_coluna_opcional_ausente_nao_derruba_a_fonte_inteira(tmp_path):
    """A forma do defeito da DEC-038: a coluna existe no codigo e nao no artefato."""
    base = tmp_path / "staging"
    _escrever(base, sv.FONTE_MAPEADOS, pd.DataFrame({
        "rede": ["smart_fit"], "lat": [LAT], "lng": [LNG],
    }))  # sem `status_registro`, sem `nome_unidade`, sem `flag_coord_valida`
    df, fontes = sv._oferta_unida(str(base))
    assert sv.FONTE_MAPEADOS in fontes
    assert len(df) == 1


def test_coluna_obrigatoria_ausente_marca_a_fonte_como_nao_lida(tmp_path):
    base = tmp_path / "staging"
    _escrever(base, sv.FONTE_MAPEADOS, pd.DataFrame({"rede": ["x"], "lat": [LAT]}))  # sem lng
    _df, fontes = sv._oferta_unida(str(base))
    assert sv.FONTE_MAPEADOS not in fontes


# --- contagem separada (D2/D3) ----------------------------------------------

def test_contar_classe_separa_cadeia_de_independente():
    pontos = pd.DataFrame({"classe": ["cadeia", "cadeia", "independente"]})
    assert _contar_classe(pontos, CLASSE_CADEIA_OFERTA) == 2
    assert _contar_classe(pontos, CLASSE_INDEPENDENTE_OFERTA) == 1


def test_df_sem_coluna_classe_conta_tudo_como_cadeia():
    """RETROCOMPATIVEL: e' o que dezenas de fixtures do corpus injetam, e e' o que elas eram.

    Tratar a ausencia como ZERO faria `n_concorrentes_cadeia` nascer 0 em todo o corpus e o
    criterio da ficha APROVARIA tudo — a falha silenciosa que o D7 veio impedir.
    """
    pontos = pd.DataFrame({"rede": ["smart_fit", "bluefit"], "lat": [0, 0], "lng": [0, 0]})
    assert _contar_classe(pontos, CLASSE_CADEIA_OFERTA) == 2
    assert _contar_classe(pontos, CLASSE_INDEPENDENTE_OFERTA) == 0


def test_contar_classe_e_indiferente_a_vazio():
    assert _contar_classe(None, CLASSE_CADEIA_OFERTA) == 0
    assert _contar_classe(pd.DataFrame(), CLASSE_CADEIA_OFERTA) == 0


# --- vocabulario duplicado nao pode driftar ---------------------------------

def test_classe_da_oferta_casa_com_o_vocabulario_do_motor():
    """`api.service` repete os literais em vez de importar (o import do motor e' lazy)."""
    assert sv.CLASSE_CADEIA == CLASSE_CADEIA_OFERTA
    assert sv.CLASSE_INDEPENDENTE == CLASSE_INDEPENDENTE_OFERTA


# --- o marcador do independente (D6) ----------------------------------------

def test_pin_sem_rede_vira_marcador_do_agregador_e_menor_que_a_bandeira():
    from motor_expansao.dashboard import censo_map as cm
    from motor_expansao.dashboard.competitors import CHAVE_AGREGADOR, PIN_INDEPENDENTE_PX

    assert PIN_INDEPENDENTE_PX < cm._PIN_LOGO_PX
    vistos: list[tuple[str, int]] = []
    original = cm._render_square_logo_tile

    class _TileFalso:
        def __init__(self, size: int) -> None:
            self.size = (size, size)

    def _espiao(key, size, **kwargs):
        vistos.append((key, size))
        return _TileFalso(size)

    class _ImagemFalsa:
        def paste(self, *_a, **_k) -> None:
            return None

    cm._render_square_logo_tile = _espiao
    try:
        cm._paste_logo_pin(_ImagemFalsa(), 10, 10, "")            # independente
        cm._paste_logo_pin(_ImagemFalsa(), 10, 10, "smart_fit")   # cadeia
    finally:
        cm._render_square_logo_tile = original

    assert vistos[0] == (CHAVE_AGREGADOR, PIN_INDEPENDENTE_PX)
    assert vistos[1] == ("smart_fit", cm._PIN_LOGO_PX)


def test_independente_e_desenhada_ANTES_da_cadeia():
    """Precedencia do Mapa Territorial: a bandeira da rede instalada fica POR CIMA."""
    from motor_expansao.dashboard import censo_map as cm

    pontos = pd.DataFrame({
        "rede": ["smart_fit", None, "bluefit", None],
        "lat": [LAT, LAT + 0.001, LAT + 0.002, LAT + 0.003],
        "lng": [LNG, LNG + 0.001, LNG + 0.002, LNG + 0.003],
    })
    chaves = [chave for _x, _y, chave in cm._project_points(pontos, LAT, LNG)]
    assert chaves[:2] == ["", ""], "independentes primeiro"
    assert all(chaves[2:]), "cadeias por ultimo"
