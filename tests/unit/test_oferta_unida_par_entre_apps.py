"""DEC-066 x DEC-046: a academia que esta' no WellHub E no TotalPass conta UMA vez no ponto.

O artefato nomeado tem uma linha por (app, academia). O carimbo `fontes_da_academia` ROTULA o par
("totalpass,wellhub") mas nao o colapsa, e a uniao de oferta do Relatorio Pontual somava as duas
linhas: em Santana/SP (-23,4852 / -46,6177) eram 24 linhas para 21 academias, e o PDF dizia
"Academias no raio (todas) 24" e "(25 no total)". Aqui tudo e' hermetico (fixtures em `tmp_path`).
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.api import service as sv
from motor_expansao.dashboard.censo_point import (
    _empty_setores_frame,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.competitors import CHAVE_AMBOS, chave_agregador_da_fonte

LAT, LNG = -23.48516, -46.61771
# ~30 m em latitude: dentro dos 100 m da regua (RAIO_MESMA_ACADEMIA_ENTRE_APPS_M)
D30 = 0.00027


def _escrever(staging, nome, df):
    staging.mkdir(parents=True, exist_ok=True)
    df.to_parquet(staging / f"{nome}.parquet", index=False)


@pytest.fixture(autouse=True)
def _sem_cache():
    sv._oferta_unida.cache_clear()
    yield
    sv._oferta_unida.cache_clear()


def _staging(tmp_path, indep: pd.DataFrame, com_cadeia_colada: bool = False):
    base = tmp_path / "staging"
    lat_cadeia = [LAT + 0.02]
    lng_cadeia = [LNG + 0.02]
    if com_cadeia_colada:
        # cadeia a ~10 m da copia TotalPass do par
        lat_cadeia.append(LAT + 0.004 + D30 + 0.00009)
        lng_cadeia.append(LNG)
    _escrever(base, sv.FONTE_MAPEADOS, pd.DataFrame({
        "rede": ["smart_fit"] * len(lat_cadeia),
        "nome_unidade": [f"SF {i}" for i in range(len(lat_cadeia))],
        "lat": lat_cadeia,
        "lng": lng_cadeia,
        "status_registro": ["valido"] * len(lat_cadeia),
    }))
    _escrever(base, sv.FONTE_INDEPENDENTES, indep)
    return base


def _par_e_isolada() -> pd.DataFrame:
    """Black Fitness nos dois apps (30 m, mesmo nome) + uma academia so' do TotalPass."""
    return pd.DataFrame({
        "nome": ["Black Fitness Club", "Black fitness Club", "Nitrobox"],
        "fonte": ["totalpass", "wellhub", "totalpass"],
        "fontes_da_academia": ["totalpass,wellhub", "totalpass,wellhub", "totalpass"],
        "lat": [LAT + 0.004 + D30, LAT + 0.004, LAT - 0.004],
        "lng": [LNG, LNG, LNG],
    })


def test_par_wellhub_totalpass_no_mesmo_ponto_conta_uma_vez(tmp_path):
    df, _ = sv._oferta_unida(str(_staging(tmp_path, _par_e_isolada())))
    indep = df[df["classe"] == sv.CLASSE_INDEPENDENTE]
    assert len(indep) == 2
    black = indep[indep["nome"].str.lower() == "black fitness club"]
    assert len(black) == 1
    # o representante e' o do WellHub (nome exibido igual ao de antes da DEC-066)...
    assert black["fonte"].iloc[0] == "wellhub"
    # ...e continua carregando a marca dos DOIS apps, para o pino do terceiro estado
    linha = black.iloc[0]
    assert chave_agregador_da_fonte(linha["fonte"], linha["fontes_da_academia"]) == CHAVE_AMBOS


def test_contagem_do_ponto_le_a_academia_do_par_uma_vez(tmp_path):
    """O numero do PDF/ficha (`n_academias_total`) sai daqui: 1 cadeia longe + 2 academias."""
    df, _ = sv._oferta_unida(str(_staging(tmp_path, _par_e_isolada())))
    res = analisar_ponto_censitario_setores(
        LAT, LNG, _empty_setores_frame(), raio_km=1.0, competitors_df=df
    )
    assert res["n_academias_total"] == 2
    assert res["n_concorrentes"] == 2
    assert res["n_concorrentes_cadeia"] == 0


def test_nome_diferente_nao_colapsa_mesmo_colado(tmp_path):
    """A regua e' a da DEC-066 (100 m E nome). Distancia sozinha nao basta."""
    indep = pd.DataFrame({
        "nome": ["CPN Academia - Agua Fria", "Cpn - Santana"],
        "fonte": ["totalpass", "wellhub"],
        "fontes_da_academia": ["totalpass", "wellhub"],
        "lat": [LAT, LAT + 0.00005],
        "lng": [LNG, LNG],
    })
    df, _ = sv._oferta_unida(str(_staging(tmp_path, indep)))
    assert (df["classe"] == sv.CLASSE_INDEPENDENTE).sum() == 2


def test_artefato_sem_carimbo_ainda_colapsa_pela_regua(tmp_path):
    """Artefato anterior ao v8 (sem `fontes_da_academia`): o par sai da regua, nao do carimbo."""
    indep = _par_e_isolada().drop(columns=["fontes_da_academia"])
    df, _ = sv._oferta_unida(str(_staging(tmp_path, indep)))
    indep_df = df[df["classe"] == sv.CLASSE_INDEPENDENTE]
    assert len(indep_df) == 2
    black = indep_df[indep_df["nome"].str.lower() == "black fitness club"].iloc[0]
    assert black["fontes_da_academia"] == "totalpass,wellhub"


def test_sem_totalpass_nao_ha_par_e_nada_muda(tmp_path):
    indep = pd.DataFrame({
        "nome": ["Academia A", "Academia B"],
        "fonte": ["wellhub", "wellhub"],
        "fontes_da_academia": ["wellhub", "wellhub"],
        "lat": [LAT, LAT + D30],
        "lng": [LNG, LNG],
    })
    df, _ = sv._oferta_unida(str(_staging(tmp_path, indep)))
    assert (df["classe"] == sv.CLASSE_INDEPENDENTE).sum() == 2


def test_sem_coluna_fonte_degrada_sem_quebrar(tmp_path):
    indep = _par_e_isolada().drop(columns=["fonte", "fontes_da_academia"])
    df, _ = sv._oferta_unida(str(_staging(tmp_path, indep)))
    # sem saber o app, nao ha' como afirmar par: conta como antes
    assert (df["classe"] == sv.CLASSE_INDEPENDENTE).sum() == 3


def test_par_com_um_membro_colado_numa_cadeia_sai_inteiro(tmp_path):
    """A copia TotalPass colapsa contra a cadeia (<= 50 m): a academia E' a cadeia, e manter a
    copia WellHub a contaria de novo."""
    df, _ = sv._oferta_unida(str(_staging(tmp_path, _par_e_isolada(), com_cadeia_colada=True)))
    indep = df[df["classe"] == sv.CLASSE_INDEPENDENTE]
    assert list(indep["nome"]) == ["Nitrobox"]
