"""Mediana da renda da cidade PONDERADA PELA POPULACAO na pagina "Onde crescer" (DEC-072).

Com a renda do hexagono rateada por area (DEC-072), hexagonos rurais quase vazios passaram a ter
renda -- muitas vezes alta. Na mediana sem peso cada um deles valia um hexagono urbano inteiro,
a regua subia e a pagina esvaziava em 87 municipios (Trindade/GO, Pontalina/GO...). O dono
escolheu em 2026-10-16 a opcao (b): mediana ponderada pela populacao do hexagono (a MESMA
`pop_leitura` da linha da tabela).
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from motor_expansao.dashboard import relatorio_praca as rp


def _hexes(linhas: list[tuple[str, float, float, float, float | None]]) -> pd.DataFrame:
    return pd.DataFrame(
        linhas,
        columns=["hex_id", "oferta_efetiva_disponivel", "renda_domiciliar", "indice_praca", "pop_leitura"],
    )


# --- a funcao --------------------------------------------------------------------------------


def test_menor_renda_cuja_populacao_acumulada_atinge_metade():
    renda = pd.Series([1_000.0, 2_000.0, 3_000.0, 4_000.0])
    pop = pd.Series([10.0, 10.0, 10.0, 70.0])
    # acumulado 10, 20, 30, 100: 2*30 = 60 < 100; 2*100 >= 100 -> 4.000
    assert rp.mediana_renda_da_cidade(renda, pop) == (4_000.0, True)
    # exatamente 50%: entra o valor onde o acumulado TOCA a metade (>=), nao o seguinte
    assert rp.mediana_renda_da_cidade(renda, pd.Series([25.0, 25.0, 25.0, 25.0])) == (2_000.0, True)


def test_ordem_de_entrada_nao_muda_o_resultado():
    renda = pd.Series([3_000.0, 1_000.0, 4_000.0, 2_000.0])
    pop = pd.Series([10.0, 10.0, 70.0, 10.0])
    assert rp.mediana_renda_da_cidade(renda, pop) == (4_000.0, True)


def test_populacao_nula_ou_zero_fica_fora_do_peso():
    renda = pd.Series([1_000.0, 2_000.0, 9_000.0, 9_500.0])
    pop = pd.Series([100.0, 100.0, 0.0, None])
    # so' os dois primeiros pesam: acumulado 100, 200 -> 2*100 >= 200 -> 1.000
    assert rp.mediana_renda_da_cidade(renda, pop) == (1_000.0, True)


def test_sem_peso_cai_na_mediana_simples_e_declara():
    renda = pd.Series([1_000.0, 2_000.0, 3_000.0, 4_000.0])
    assert rp.mediana_renda_da_cidade(renda, None) == (2_500.0, False)
    assert rp.mediana_renda_da_cidade(renda, pd.Series([0.0, None, 0.0, None])) == (2_500.0, False)
    assert rp.mediana_renda_da_cidade(pd.Series([None, 0.0]), pd.Series([10.0, 10.0])) == (None, False)


# --- a selecao -------------------------------------------------------------------------------


def _cidade_com_borda_rural() -> pd.DataFrame:
    """4 hexagonos urbanos de 10 mil habitantes e 6 rurais de 5 habitantes com renda ALTA."""
    urbanos = [
        ("u1", 3_000.0, 2_000.0, 50.0, 10_000.0),
        ("u2", 3_000.0, 2_500.0, 55.0, 10_000.0),
        ("u3", 3_000.0, 3_000.0, 60.0, 10_000.0),
        ("u4", 3_000.0, 3_500.0, 65.0, 10_000.0),
    ]
    rurais = [(f"r{i}", 0.0, 8_000.0 + 200.0 * i, 10.0, 5.0) for i in range(6)]
    return _hexes(urbanos + rurais)


def test_hexagonos_rurais_quase_vazios_e_ricos_nao_puxam_a_mediana():
    df = _cidade_com_borda_rural()
    sel = rp.selecionar_onde_crescer(df)
    assert sel.mediana_ponderada is True
    assert sel.mediana_renda == 3_000.0  # o morador mediano mora em u3
    assert sel.hexagonos["hex_id"].tolist() == ["u4", "u3"]
    assert sel.n_elegiveis == 2

    # Com a regua antiga (sem peso), a mediana era 8.100 e a pagina saia VAZIA.
    simples, _ = rp.mediana_renda_da_cidade(df["renda_domiciliar"], None)
    assert simples == 8_100.0
    assert int(((df["oferta_efetiva_disponivel"] > 0) & (df["renda_domiciliar"] >= simples)).sum()) == 0


def test_renda_exibida_do_hexagono_fica_intacta():
    df = _cidade_com_borda_rural()
    sel = rp.selecionar_onde_crescer(df)
    esperado = df.set_index("hex_id").loc[sel.hexagonos["hex_id"], "renda_domiciliar"].tolist()
    assert sel.hexagonos["renda_domiciliar"].tolist() == esperado


def test_sem_populacao_na_base_cai_na_simples_e_o_pdf_diz():
    from motor_expansao.dashboard import relatorio_municipal as rm

    df = _cidade_com_borda_rural().drop(columns=["pop_leitura"])
    sel = rp.selecionar_onde_crescer(df)
    assert sel.mediana_ponderada is False
    assert sel.mediana_renda == 8_100.0

    import inspect

    fonte = inspect.getsource(rm._praca_onde_crescer_page)
    assert "mediana da cidade ponderada pela população" in fonte
    assert "simples: a base não traz população por hexágono" in fonte


# --- regressao com dado real -----------------------------------------------------------------


def _data_dir() -> Path:
    base = os.environ.get("MOTOR_DATA_DIR")
    candidatos = [Path(base)] if base else []
    candidatos.append(Path(__file__).resolve().parents[2] / "data")
    for raiz in candidatos:
        geo = raiz / "outputs" / "setores_censitarios_2022_geo" / "uf=GO"
        enr = raiz / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=GO"
        malha = raiz / "ibge"
        if (
            (geo / "cod_municipio=5221403").is_dir()
            and (geo / "cod_municipio=5217708").is_dir()
            and enr.is_dir()
            and malha.is_dir()
        ):
            return raiz
    pytest.skip("dado real de GO ausente (enriquecido, setores geo e malha IBGE)")


@pytest.mark.parametrize(("cod", "nome"), [("5221403", "Trindade"), ("5217708", "Pontalina")])
def test_trindade_e_pontalina_voltam_a_ter_lista(cod, nome):
    """Medido em 2026-10-16: com o rateio por area e a mediana SEM peso as duas listas saiam
    vazias (Trindade 4.031,84 contra 3.654,61 ponderada; Pontalina 6.781,45 contra 4.954,87)."""
    import pyarrow.dataset as ds

    from motor_expansao.api import service
    from motor_expansao.dashboard.relatorio_municipal import carregar_renda_domiciliar_por_hex

    raiz = _data_dir()
    settings = SimpleNamespace(
        ibge_dir=raiz / "ibge", censo_geo_dir=raiz / "outputs" / "setores_censitarios_2022_geo"
    )
    dset = ds.dataset(sorted((raiz / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=GO").glob("*.parquet")))
    tipo = str(dset.schema.field("cod_municipio").type)
    valor = int(cod) if "int" in tipo else (float(cod) if "double" in tipo else cod)
    df = dset.to_table(filter=ds.field("cod_municipio") == valor).to_pandas()
    if df.empty:
        pytest.skip(f"{nome}/GO ausente do enriquecido local")

    hex_ids = sorted(df["hex_id"].astype(str))
    vizinhos = service._municipios_vizinhos_dos_hexes(hex_ids, "GO", cod, settings)
    renda = carregar_renda_domiciliar_por_hex(
        "GO", cod, settings.censo_geo_dir, hexes=hex_ids, vizinhos=vizinhos
    )
    hexes = rp.preparar_hexes_da_cidade(df, renda)
    sel = rp.selecionar_onde_crescer(hexes)

    assert sel.mediana_ponderada is True
    assert len(sel.hexagonos) >= 1, f"{nome}: 'Onde crescer' vazia com a mediana ponderada"
    simples, _ = rp.mediana_renda_da_cidade(hexes["renda_domiciliar"], None)
    assert sel.mediana_renda < simples  # a borda rural rica puxava a regua para cima
