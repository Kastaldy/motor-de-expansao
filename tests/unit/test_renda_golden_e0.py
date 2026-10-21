"""Golden da E0: a migracao para `motor_expansao.renda` NAO muda nenhum numero exibido.

Regra-mae da E0 (plano de correcao da renda, secao 10.4): com a versao 0 dos fatores
(BR `2026-08_caged_v0`, F = 1,1641 -- o mesmo float que a VPS aplicava), toda superficie que
exibe renda tem de sair IGUAL bit a bit ao que saia antes da migracao.

Desde a E2 (DEC-075) o `VIGENTE` aponta para a versao da PNAD, entao este golden FIXA a v0 por
`MOTOR_FATORES_RENDA_VERSAO` -- o mesmo mecanismo do rollback de producao. Ele continua provando
que a migracao nao mudou numero e, de quebra, que o rollback para a v0 devolve a escala de antes. Igualdade EXATA (`==`),
nunca `approx`: uma troca na ORDEM das operacoes (`v x (u x F)` no lugar de `(v x u) x F`)
muda o ultimo bit e `approx` deixaria passar.

Como a comparacao e feita
-------------------------
"Antes" e uma reimplementacao CONGELADA das formulas de `origin/main` anteriores a E0, copiada
do codigo (as linhas de origem estao citadas em cada uma). Nada aqui le o codigo antigo do git
em tempo de teste: o CI clona raso, e o que se trava e o NUMERO, nao a existencia do arquivo.

  - motor do ponto (`censo_point`), mapas do PDF pontual (`censo_map`) e setores da ficha da
    rede (`app._rede_setores_entorno`): a MESMA funcao roda duas vezes, uma com o modulo da
    renda e outra com as expressoes antigas no lugar dele (`_RENDA_ANTIGA`) -- todo o resto
    do caminho e identico, entao qualquer diferenca e da formula;
  - hexagono do card (`app._hex_dict`), renda da rede (`app._rede_renda_domiciliar`) e o
    mapa do PDF municipal (`renda_domiciliar_por_hex`): copia congelada das funcoes antigas;
  - insumos (uplift municipal/UF/setor, moradores): copia congelada da cascata antiga de
    `dashboard/constants.py`, lendo o MESMO staging.

O fator antigo nao e digitado: sai de `_carregar_fator_temporal_antigo` (copia de
`constants.py:566-579`) aplicada ao JSON que a VPS servia (medido nos containers em 2026-10-20).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from motor_expansao.dashboard import censo_map, censo_point
from motor_expansao.renda import (
    ENV_VERSAO,
    carregar_fatores,
    insumos,
    renda_domiciliar_por_hex,
)
from motor_expansao.renda.hex import serie_renda
from tests.unit.renda_fixtures import apontar_staging_renda
from tests.unit.test_relatorio_pontual_censitario_motor import LAT_C, LNG_C, _sector_record

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))
import app as pilot  # noqa: E402

# --------------------------------------------------------------------------------
# O fator de antes da E0, derivado como a producao derivava
# --------------------------------------------------------------------------------

#: `data/staging/fator_temporal_renda.json` da VPS (containers api e web, 2026-10-20).
_JSON_VPS = {
    "fator_temporal_renda": 1.1641,
    "salario_base_2022": 2195.21,
    "salario_atual": 2555.41,
    "competencia_base_inicio": 202201,
    "competencia_base_fim": 202212,
    "competencia_atual_inicio": 202507,
    "competencia_atual_fim": 202606,
    "fonte": "Novo CAGED (salario medio de admissao), winsorizado e ponderado por admissoes",
    "ipca_acumulado_conferencia": 1.1935,
    "divergencia_vs_ipca_pp": -2.9,
    "escopo": "nacional",
}


def _carregar_fator_temporal_antigo(d: dict) -> tuple[float, str]:
    """Copia de `dashboard/constants.py:566-579` (origin/main antes da E0), sem o disco."""
    try:
        fator = float(d["fator_temporal_renda"])
        fim = str(d["competencia_atual_fim"])
        if 1.0 <= fator <= 2.0:
            return fator, f"{fim[4:]}/{fim[:4]} (CAGED; Censo jul/2022 x {fator})"
    except (KeyError, ValueError, TypeError):
        pass
    return 1.0, "julho/2022 (Censo IBGE)"


F_ANTIGO, ROTULO_ANTIGO = _carregar_fator_temporal_antigo(_JSON_VPS)
#: A versao que reproduz producao de antes da E0 (fixada por env: o VIGENTE e a da E2).
VERSAO_V0 = "2026-08_caged_v0"

def _v06004_antiga(v, pc, m):
    """A reconstrucao da V06004 de antes da E0, nos tres consumidores (so chamada sem V06004)."""
    if isinstance(v, pd.Series):  # censo_point.py:536-537
        return v.where(v.notna(), pc * m)
    if pc is None or m is None:  # app.py (_rede_setores_entorno): guarda de None
        return None
    return pc * m  # censo_map.py:2017-2019 / app.py


#: As expressoes de antes da E0, no lugar do modulo da renda (mesma assinatura).
_RENDA_ANTIGA = SimpleNamespace(
    v06004_de_fallback=_v06004_antiga,
    # censo_point.py:564 / censo_map.py:2029-2031 / app.py:10304
    renda_domiciliar=lambda v, u, uf: v * u * float(F_ANTIGO),
    # censo_point.py:577 / censo_map.py:2039-2043 (= renda_domiciliar_total / moradores)
    renda_per_capita=lambda v, u, m, uf: (v * u * float(F_ANTIGO)) / m,
    # censo_point.py:733-735 (o round fica no chamador)
    fator_composto_domiciliar=lambda u, uf: u * F_ANTIGO,
    # censo_point.py:374-375
    campos_referencia_ponto=lambda uf=None: {
        "fator_temporal_renda": F_ANTIGO,
        "data_referencia_renda": ROTULO_ANTIGO,
    },
)

# --------------------------------------------------------------------------------
# Staging sintetico, com numeros "feios" de proposito
# --------------------------------------------------------------------------------

_COD_SP, _COD_SP2, _COD_RJ = "3550308", "3509502", "3304557"
_TABELA_MUNICIPIOS = pd.DataFrame(
    {
        "uf": ["SP", "SP", "SP", "RJ"],
        "cod_municipio": [_COD_SP, _COD_SP2, "3501608", _COD_RJ],
        "uplift_composicao_final": [1.43119, 1.6327771, 1.517, 1.71913],
        "uplift_confiavel": [True, True, False, True],
        "moradores_por_domicilio_municipio": [2.83917, 2.6101, 3.0213, 2.71],
    }
)
_SETORES_UPLIFT = pd.DataFrame(
    {
        "cod_setor": ["355030801000001", "355030801000002", "355030801000003"],
        "uplift_composicao_setor": [1.38211947, 1.7134002, 1.5555557],
        "flag_extrapolacao": [False, True, False],
    }
)
#: k do carimbo do staging hex: o da safra 2026-08 do artefato GEO, 10 casas.
_K = 1.2334632197


@pytest.fixture
def staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    st = tmp_path / "staging"
    st.mkdir()
    _TABELA_MUNICIPIOS.to_parquet(st / "uplift_renda_domiciliar_municipio.parquet")
    _SETORES_UPLIFT.to_parquet(st / "uplift_composicao_setor.parquet")
    pd.DataFrame({"metodo_calibracao_renda": [f"multiplicativo_global_k={_K}"]}).to_parquet(
        st / "censo2022_setores_calibrado.parquet"
    )
    # A v0 do pacote FIXADA por env (o caminho do rollback), sem fator sintetico.
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    monkeypatch.setenv(ENV_VERSAO, VERSAO_V0)
    carregar_fatores.cache_clear()
    monkeypatch.setattr(pilot, "STAGING_DIR", st)
    apontar_staging_renda(monkeypatch, st)
    pilot._renda_staging_configurado.cache_clear()
    pilot._k_calibracao_renda.cache_clear()
    yield st
    pilot._renda_staging_configurado.cache_clear()
    pilot._k_calibracao_renda.cache_clear()
    carregar_fatores.cache_clear()


def test_a_v0_e_o_fator_que_a_producao_aplicava(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VERSAO, VERSAO_V0)
    carregar_fatores.cache_clear()
    f = carregar_fatores("BR")
    assert f.versao == VERSAO_V0 and f.fixada_por_env is True
    assert f.nacional.domiciliar == F_ANTIGO
    assert f.nacional.per_capita == F_ANTIGO
    assert f.rotulo_referencia == ROTULO_ANTIGO
    carregar_fatores.cache_clear()


# --------------------------------------------------------------------------------
# Cascata antiga dos insumos (copia de dashboard/constants.py:588-730, origin/main)
# --------------------------------------------------------------------------------


class _InsumosAntigos:
    """Os lookups de `constants.py` antes da E0, apontados para o mesmo staging."""

    def __init__(self, staging: Path) -> None:
        from motor_expansao.dashboard import constants as _c

        self.uplift_nacional = _c.UPLIFT_COMPOSICAO_NACIONAL
        self.moradores_nacional = _c.MORADORES_DOMICILIO_NACIONAL
        df = pd.read_parquet(staging / "uplift_renda_domiciliar_municipio.parquet")
        self.uplift_mun = dict(
            zip(
                df["cod_municipio"].astype(str),
                pd.to_numeric(df["uplift_composicao_final"], errors="coerce"),
                strict=False,
            )
        )
        confiavel = df[df["uplift_confiavel"].astype(bool)]
        self.uplift_uf = confiavel.groupby("uf")["uplift_composicao_final"].median().to_dict()
        valores = pd.to_numeric(df["moradores_por_domicilio_municipio"], errors="coerce")
        self.mor_mun = dict(zip(df["cod_municipio"].astype(str), valores, strict=False))
        self.mor_uf = df.assign(_m=valores).groupby("uf")["_m"].median().to_dict()
        ds = pd.read_parquet(staging / "uplift_composicao_setor.parquet")
        self.uplift_set = dict(
            zip(
                ds["cod_setor"].astype(str),
                pd.to_numeric(ds["uplift_composicao_setor"], errors="coerce"),
                strict=False,
            )
        )

    def uplift_renda_domiciliar(self, uf, cod_municipio=None) -> float:
        if cod_municipio:
            valor = self.uplift_mun.get(str(cod_municipio).strip())
            if valor is not None and valor == valor:
                return float(valor)
        if uf:
            valor = self.uplift_uf.get(str(uf).strip().upper())
            if valor is not None and valor == valor:
                return float(valor)
        return self.uplift_nacional

    def moradores_por_domicilio(self, uf, cod_municipio=None) -> float:
        if cod_municipio:
            valor = self.mor_mun.get(str(cod_municipio).strip())
            if valor is not None and valor == valor:
                return float(valor)
        if uf:
            valor = self.mor_uf.get(str(uf).strip().upper())
            if valor is not None and valor == valor:
                return float(valor)
        return self.moradores_nacional

    def uplift_composicao_por_setor(self, cod_setor, uf=None, cod_municipio=None) -> float:
        if cod_setor is not None and cod_setor == cod_setor:
            valor = self.uplift_set.get(str(cod_setor).strip())
            if valor is not None and valor == valor:
                return float(valor)
        return self.uplift_renda_domiciliar(uf, cod_municipio)

    # renda_hex.py:136-158 (origin/main): (m x u) x F, um escalar por municipio.
    def fator_domiciliar(self, uf, cod_municipio, fator_temporal) -> float:
        return (
            self.moradores_por_domicilio(uf, cod_municipio)
            * self.uplift_renda_domiciliar(uf, cod_municipio)
            * fator_temporal
        )

    # renda_hex.py:161-188 (origin/main)
    def base_renda_domiciliar(self, valor, origem, uf, cod, k) -> float | None:
        if valor is None or pd.isna(valor):
            return None
        if origem == "renda_per_capita_setor_2022_calibrada":
            return float(valor) / k()
        if origem == "renda_per_capita":
            uplift = self.uplift_renda_domiciliar(uf, cod)
            return float(valor) / uplift if uplift else None
        return float(valor)


_CHAVES_INSUMO = [
    ("SP", _COD_SP),  # municipio na tabela
    ("SP", _COD_SP2),
    ("SP", "3501608"),  # municipio com uplift NAO confiavel (ainda e lido por municipio)
    ("SP", "3599999"),  # fora da tabela -> mediana da UF
    ("sp", " 3599999 "),  # caixa e espaco
    ("RJ", _COD_RJ),
    ("ZZ", "9999999"),  # UF fora -> nacional do perfil
    (None, None),
]


def test_insumos_iguais_a_cascata_antiga(staging: Path) -> None:
    antigo = _InsumosAntigos(staging)
    for uf, cod in _CHAVES_INSUMO:
        assert insumos.uplift_municipio(uf, cod) == antigo.uplift_renda_domiciliar(uf, cod)
        assert insumos.moradores_por_domicilio(uf, cod) == antigo.moradores_por_domicilio(uf, cod)
    for cod_setor in [*_SETORES_UPLIFT["cod_setor"], "355030899999999", None, float("nan")]:
        for uf, cod in _CHAVES_INSUMO:
            assert insumos.uplift_setor(cod_setor, uf, cod) == antigo.uplift_composicao_por_setor(
                cod_setor, uf, cod
            )


# --------------------------------------------------------------------------------
# Motor do ponto (censo_point) e mapas do PDF pontual (censo_map)
# --------------------------------------------------------------------------------


def _setores_ponto() -> pd.DataFrame:
    """Setores com V06004, moradores e uplift distintos; um sem V06004 (fallback pela bruta)."""
    registros = [
        _sector_record("355030801000001", box(-400, -400, 0, 400), pop=811, renda=1494.49,
                       moradores=2.8, domicilios=290.0),
        _sector_record("355030801000002", box(0, -400, 400, 400), pop=1307, renda=2711.07,
                       moradores=3.13, domicilios=417.0),
        _sector_record("355030801000003", box(-400, 400, 400, 900), pop=533, renda=987.651,
                       moradores=2.4111, domicilios=221.0),
        # cod_setor fora da tabela setorial: cai no uplift do municipio.
        _sector_record("355030801000004", box(-900, -400, -400, 400), pop=702, renda=3333.33,
                       moradores=3.7, domicilios=189.0),
        # Sem V06004: a renda domiciliar e reconstruida por per capita BRUTA x moradores.
        _sector_record("355030801000005", box(400, -400, 900, 400), pop=455, renda=1999.995,
                       moradores=2.9, domicilios=157.0),
    ]
    df = pd.DataFrame(registros)
    df.loc[4, "renda_responsavel_media_setor_2022"] = np.nan
    return df


def _iguais(a: object, b: object) -> bool:
    """Igualdade EXATA, com NaN == NaN e frames comparados celula a celula."""
    if isinstance(a, pd.DataFrame) or isinstance(b, pd.DataFrame):
        try:
            pd.testing.assert_frame_equal(a, b, check_exact=True)  # type: ignore[arg-type]
        except AssertionError:
            return False
        return True
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return type(a) is type(b) and a == b


def _rodar_ponto(monkeypatch: pytest.MonkeyPatch, *, antigo: bool, **kw) -> dict:
    with monkeypatch.context() as m:
        if antigo:
            m.setattr(censo_point, "_renda", _RENDA_ANTIGA)
        return censo_point.analisar_ponto_censitario_setores(LAT_C, LNG_C, _setores_ponto(), **kw)


@pytest.mark.parametrize("raio_km", [None, 0.35])
def test_motor_do_ponto_igual_ao_de_antes(
    staging: Path, monkeypatch: pytest.MonkeyPatch, raio_km: float | None
) -> None:
    kw = {} if raio_km is None else {"raio_km": raio_km}
    novo = _rodar_ponto(monkeypatch, antigo=False, **kw)
    velho = _rodar_ponto(monkeypatch, antigo=True, **kw)
    assert set(novo) == set(velho)
    diferentes = [k for k in novo if not _iguais(novo[k], velho[k])]
    assert diferentes == [], diferentes
    # E o caso nao e trivial: ha renda, com o fator e o rotulo de producao.
    assert novo["renda_per_capita_media_raio"] and novo["renda_domiciliar_total_raio"]
    assert novo["fator_temporal_renda"] == F_ANTIGO
    assert novo["data_referencia_renda"] == "06/2026 (CAGED; Censo jul/2022 x 1.1641)"
    setores = novo["setores_intersectados"]
    assert setores["renda_per_capita_domiciliar_setor"].notna().any()


def test_motor_do_ponto_vazio_igual_ao_de_antes(
    staging: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O resultado sem setor tambem carrega `fator_temporal_renda`/`data_referencia_renda`."""
    vazio = _setores_ponto().iloc[0:0]
    novo = censo_point.analisar_ponto_censitario_setores(LAT_C, LNG_C, vazio)
    with monkeypatch.context() as m:
        m.setattr(censo_point, "_renda", _RENDA_ANTIGA)
        velho = censo_point.analisar_ponto_censitario_setores(LAT_C, LNG_C, vazio)
    assert [k for k in novo if not _iguais(novo[k], velho[k])] == []


def _rodar_mapas(monkeypatch: pytest.MonkeyPatch, *, antigo: bool) -> dict[str, dict]:
    capturado: dict[str, dict] = {}
    original = censo_map._render_camada

    def _spy(*, titulo, **kwargs):
        capturado[titulo] = {
            "source_values": kwargs.get("source_values"),
            "valor_ponto": kwargs.get("valor_ponto"),
        }
        return original(titulo=titulo, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(censo_map, "_render_camada", _spy)
        if antigo:
            m.setattr(censo_map, "_renda", _RENDA_ANTIGA)
            m.setattr(censo_point, "_renda", _RENDA_ANTIGA)
        censo_map.render_mapas_censitarios_combinados(
            LAT_C, LNG_C, _setores_ponto(), width=800, height=600, basemap=False
        )
    return capturado


def test_mapas_do_pdf_pontual_iguais_aos_de_antes(
    staging: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    novo = _rodar_mapas(monkeypatch, antigo=False)
    velho = _rodar_mapas(monkeypatch, antigo=True)
    for titulo in ("Renda per capita", "Renda media domiciliar"):
        pd.testing.assert_series_equal(
            novo[titulo]["source_values"], velho[titulo]["source_values"], check_exact=True
        )
        assert novo[titulo]["valor_ponto"] == velho[titulo]["valor_ponto"]
        assert novo[titulo]["source_values"].notna().sum() >= 4, titulo


# --------------------------------------------------------------------------------
# Hexagono do card (app._hex_dict), rede (app._rede_renda_domiciliar) e PDF municipal
# --------------------------------------------------------------------------------

_num = pilot._num


def _frame_hex() -> pd.DataFrame:
    """Hexagonos dos dois ramos da base (calibrada / SIDRA), com bordas de arredondamento."""
    antigo_fator = (2.83917 * 1.43119) * F_ANTIGO  # SP/3550308
    bordas = [(n + 0.5) / antigo_fator * _K for n in (3123, 4567, 9998)]
    calibradas = [1500.0, 2017.3311, 987.65, None, 2400.0, *bordas, 1.0, 0.0]
    n = len(calibradas)
    cods = [_COD_SP] * n
    cods[1], cods[2], cods[4] = _COD_SP2, _COD_RJ, "3599999"
    ufs = ["RJ" if c == _COD_RJ else "SP" for c in cods]
    return pd.DataFrame(
        {
            "hex_id": [f"h{i}" for i in range(n)],
            "lat": [-23.55] * n,
            "lng": [-46.63] * n,
            "uf": ufs,
            "cod_municipio": cods,
            "renda_per_capita_setor_2022_calibrada": calibradas,
            "renda_per_capita": [1800.0, 1777.77, 2100.5, 1650.25, 1999.99, *[1900.0] * 3, 2.0, 3.0],
            "pop_total_setor_2022": [1200, 830, 4410, 77, 1503, 990, 610, 2875, 5, 0],
        }
    )


def _hex_antigo(r: pd.Series, antigo: _InsumosAntigos) -> tuple[float | None, float | None]:
    """app.py:1855-1893 + renda_hex.py:136-188 (origin/main): (renda_dom, renda pc) do hex."""
    cod = r.get("cod_municipio")
    if cod is None or pd.isna(cod):
        return None, None
    uf = r.get("uf")
    fator = antigo.fator_domiciliar(uf, str(cod), F_ANTIGO)
    base = antigo.base_renda_domiciliar(
        r.get("renda_leitura", float("nan")), r.get("renda_origem"), uf, str(cod), lambda: _K
    )
    if base is None:
        return None, None
    dom = _num(base * fator)
    if dom is None:
        return None, None
    moradores = antigo.moradores_por_domicilio(uf, str(cod))
    return dom, (_num(dom / moradores) if moradores else None)


def test_hexagono_do_card_igual_ao_de_antes(staging: Path) -> None:
    antigo = _InsumosAntigos(staging)
    derivado = pilot._derivar(_frame_hex())
    vistos = 0
    for _, r in derivado.iterrows():
        dom_velho, pc_velho = _hex_antigo(r, antigo)
        payload = pilot._hex_dict(r)
        assert payload["renda_dom"] == dom_velho, r["hex_id"]
        assert payload["renda"] == pc_velho, r["hex_id"]
        assert type(payload["renda_dom"]) is type(dom_velho)
        assert type(payload["renda"]) is type(pc_velho)
        vistos += dom_velho is not None
    assert vistos >= 8


def _rede_renda_domiciliar_antigo(
    bloco: pd.DataFrame, pesos: dict | None, antigo: _InsumosAntigos
) -> float | None:
    """app.py:10137-10164 (origin/main), com o `_renda_domiciliar_hex` antigo por linha."""
    if not len(bloco):
        return None
    trabalho = bloco.copy()
    trabalho["renda_leitura"], trabalho["renda_origem"] = serie_renda(trabalho)
    soma = peso = 0.0
    for _, linha in trabalho.iterrows():
        cod = linha.get("cod_municipio")
        if cod is None or pd.isna(cod):
            continue
        cod_txt = str(cod).strip()
        if cod_txt.endswith(".0"):
            cod_txt = cod_txt[:-2]
        linha = linha.copy()
        linha["cod_municipio"] = cod_txt
        dom, _ = _hex_antigo(linha, antigo)
        pop = (pilot._numf(linha.get("pop_total_setor_2022")) or 0.0) * (pesos or {}).get(
            linha.name, 1.0
        )
        if dom is not None and pop > 0:
            soma += dom * pop
            peso += pop
    return _num(soma / peso, 0) if peso else None


def test_renda_da_rede_igual_a_de_antes(staging: Path) -> None:
    antigo = _InsumosAntigos(staging)
    bloco = _frame_hex()
    # cod_municipio como float, que a rotina da rede normaliza (".0").
    bloco["cod_municipio"] = bloco["cod_municipio"].astype(float)
    pesos = dict(zip(bloco.index, [1.0, 0.37, 0.5, 1.0, 0.913, 0.25, 1.0, 0.61, 1, 1], strict=True))
    for p in (None, pesos):
        novo = pilot._rede_renda_domiciliar(bloco, p)
        velho = _rede_renda_domiciliar_antigo(bloco, p, antigo)
        assert novo == velho and novo is not None
        assert type(novo) is type(velho)


def _renda_domiciliar_por_hex_antigo(df, *, uf, cod_municipio, antigo) -> dict[str, float]:
    """renda_hex.py:190-226 (origin/main), com F = o fator de producao."""
    if df is None or df.empty or "hex_id" not in df.columns or not cod_municipio:
        return {}
    fator = antigo.fator_domiciliar(uf, cod_municipio, float(F_ANTIGO))
    valor, origem = serie_renda(df)
    out: dict[str, float] = {}
    for hex_id, v, o in zip(df["hex_id"].astype(str), valor, origem, strict=True):
        base = antigo.base_renda_domiciliar(v, o, uf, cod_municipio, lambda: _K)
        if base is not None:
            out[hex_id] = base * fator
    return out


@pytest.mark.parametrize(("uf", "cod"), [("SP", _COD_SP), ("SP", "3599999"), ("ZZ", "9999999")])
def test_mapa_do_pdf_municipal_igual_ao_de_antes(staging: Path, uf: str, cod: str) -> None:
    antigo = _InsumosAntigos(staging)
    df = _frame_hex()
    novo = renda_domiciliar_por_hex(df, uf=uf, cod_municipio=cod, staging_dir=staging)
    velho = _renda_domiciliar_por_hex_antigo(df, uf=uf, cod_municipio=cod, antigo=antigo)
    assert novo == velho
    assert len(novo) >= 8


# --------------------------------------------------------------------------------
# Setores da ficha da rede (app._rede_setores_entorno)
# --------------------------------------------------------------------------------


def test_setores_da_ficha_da_rede_iguais_aos_de_antes(
    staging: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import h3

    geo = tmp_path / "geo"
    part = geo / "uf=SP" / f"cod_municipio={_COD_SP}"
    part.mkdir(parents=True)
    _setores_ponto().to_parquet(part / "part-000.parquet")
    celula = h3.latlng_to_cell(LAT_C, LNG_C, 7)
    pd.DataFrame({"hex_id": [celula], "uf": ["SP"], "cod_municipio": [_COD_SP]}).to_parquet(
        staging / "hexagonos_mercado_mapeado.parquet"
    )
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", geo)
    monkeypatch.setattr(
        pilot,
        "_rede_pontos",
        lambda: pd.DataFrame({"unidade_id": ["u1"], "lat": [LAT_C], "lng": [LNG_C]}),
    )

    pilot._renda_staging_configurado()  # aponta os insumos ANTES das duas rodadas

    def _rodar(antigo: bool) -> dict:
        pilot._rede_setores_entorno.cache_clear()
        with monkeypatch.context() as m:
            if antigo:
                m.setattr(pilot, "_renda", _RENDA_ANTIGA)
            saida = json.loads(pilot._rede_setores_entorno("u1"))
        pilot._rede_setores_entorno.cache_clear()
        return saida

    novo, velho = _rodar(False), _rodar(True)
    assert novo == velho
    rendas = [s["renda_domiciliar"] for s in novo["setores"]]
    assert novo["disponivel"] and sum(r is not None for r in rendas) >= 4
