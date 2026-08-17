"""Trava de ESCALA da renda: o artefato materializado bate com o IBGE?

Por que este arquivo existe
---------------------------
Em 2026-08-13 uma auditoria achou seis defeitos na cadeia da renda. Dois deles eram de ESCALA e
atravessaram os ~2.000 testes da suite sem encostar em nada:

  - a renda domiciliar exibida saia 23,35% ACIMA da referencia do IBGE (o `k` era aplicado por
    cima de um uplift que ja fazia a mesma conversao);
  - a renda per capita exibida saia 19,62% ABAIXO (usava o `k`, 1,2335, no lugar do uplift, 1,632).

Nenhum teste pegou, porque todos os testes de renda eram sobre a FORMA do resultado ou sobre a
FORMULA em fixture sintetico. Fixture sintetico nao tem escala: ele confirma que `a x b x c` foi
calculado, nunca que o numero final corresponde a alguma coisa no mundo.

Este teste e o unico que olha o dado REAL contra uma referencia EXTERNA. E o que pega o proximo
erro de escala vindo do pipeline.

A ancora
--------
A identidade e definicional, nao empirica: `uplift_composicao` foi DEFINIDO em
`pipelines/derivar_uplift_renda_domiciliar.py` como

    uplift_municipio = (renda domiciliar per capita do SIDRA x moradores) / V06004_bruta

logo `V06004 x uplift / moradores` reproduz a renda domiciliar per capita do SIDRA por
construcao, e `V06004 x uplift` reproduz a renda do domicilio. O raking do uplift SETORIAL
(`derivar_uplift_composicao_setor.py`) preserva a media municipal ponderada por domicilios, entao
a identidade sobrevive a descida para o setor — medido: razao 0,999 (p05 0,991 / p95 1,009).

Por que uma AMOSTRA basta
-------------------------
Erro de escala e multiplicativo e uniforme por natureza — foi exatamente assim que os dois
defeitos se apresentaram (dispersao ZERO: p05 = p95 = 1,2335 nos 5.551 municipios). Uma amostra
estratificada por UF pega isso com folga, e mantem o teste em segundos em vez de minutos. A
tolerancia de 2% e larga o suficiente para o ruido de amostragem e apertada o suficiente para
barrar qualquer fator espurio real: o menor dos dois defeitos era de 19,62%.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dashboard.constants import uplift_composicao_por_setor

_RAIZ = Path(__file__).resolve().parents[2]
GEO_DIR = _RAIZ / "data" / "outputs" / "setores_censitarios_2022_geo"
UPLIFT_MUNICIPIO = _RAIZ / "data" / "staging" / "uplift_renda_domiciliar_municipio.parquet"

MUNICIPIOS_POR_UF = 3          # amostra estratificada: ~81 particoes
TOLERANCIA = 0.02              # 2%

_COLUNAS = [
    "cod_setor",
    "cod_municipio",
    "renda_responsavel_media_setor_2022",
    "avg_moradores_domicilio_setor_2022",
    "domicilios_particulares_ocupados_setor_2022",
]

pytestmark = pytest.mark.skipif(
    not GEO_DIR.exists() or not UPLIFT_MUNICIPIO.exists(),
    reason="artefato geo e/ou uplift municipal nao materializados neste checkout",
)


def _amostra_estratificada() -> pd.DataFrame:
    """Ate `MUNICIPIOS_POR_UF` municipios de cada UF, deterministico (ordem do disco)."""
    partes: list[pd.DataFrame] = []
    for uf_dir in sorted(GEO_DIR.glob("uf=*")):
        for mun_dir in sorted(uf_dir.glob("cod_municipio=*"))[:MUNICIPIOS_POR_UF]:
            try:
                partes.append(pd.read_parquet(mun_dir, columns=_COLUNAS))
            except (KeyError, OSError, ValueError):
                continue
    assert partes, "nenhuma particao legivel no artefato geo"
    df = pd.concat(partes, ignore_index=True)
    df["resp"] = pd.to_numeric(df["renda_responsavel_media_setor_2022"], errors="coerce")
    df["mor"] = pd.to_numeric(df["avg_moradores_domicilio_setor_2022"], errors="coerce")
    df["dom"] = pd.to_numeric(df["domicilios_particulares_ocupados_setor_2022"], errors="coerce")
    df["cod_municipio"] = df["cod_municipio"].astype(str)
    return df[df["resp"].gt(0) & df["mor"].gt(0) & df["dom"].gt(0)].reset_index(drop=True)


@pytest.fixture(scope="module")
def amostra() -> pd.DataFrame:
    return _amostra_estratificada()


@pytest.fixture(scope="module")
def referencia_sidra() -> pd.DataFrame:
    ref = pd.read_parquet(
        UPLIFT_MUNICIPIO,
        columns=["cod_municipio", "renda_domiciliar_per_capita_ibge", "renda_domiciliar_total_ibge"],
    )
    ref["cod_municipio"] = ref["cod_municipio"].astype(str)
    return ref


def test_amostra_cobre_o_pais(amostra: pd.DataFrame) -> None:
    """Guarda da propria amostra: sem cobertura, os asserts de escala nao valem nada."""
    assert amostra["cod_municipio"].nunique() >= 60
    assert len(amostra) >= 5_000


def test_renda_domiciliar_do_artefato_bate_com_o_sidra(
    amostra: pd.DataFrame, referencia_sidra: pd.DataFrame
) -> None:
    """`V06004 x uplift_setor` tem de reproduzir a renda domiciliar do IBGE, dentro de 2%.

    Este e o assert que teria pego o defeito de +23,35%: com o `k` sobrando na conta, a razao
    daria 1,2335 e o teste falharia por 12 vezes a tolerancia.
    """
    up = np.array(
        [uplift_composicao_por_setor(c, None, m) for c, m in
         zip(amostra["cod_setor"], amostra["cod_municipio"], strict=False)],
        dtype=float,
    )
    dom_setor = amostra["resp"].to_numpy(dtype=float) * up
    peso = amostra["dom"].to_numpy(dtype=float)

    # Referencia: a renda domiciliar do IBGE dos MESMOS municipios, no mesmo peso.
    por_mun = (
        pd.DataFrame({"cod_municipio": amostra["cod_municipio"], "dom": peso})
        .groupby("cod_municipio", as_index=False)["dom"].sum()
        .merge(referencia_sidra, on="cod_municipio", how="inner")
    )
    alvo = float(
        np.average(por_mun["renda_domiciliar_total_ibge"], weights=por_mun["dom"].to_numpy())
    )
    medido = float(np.average(dom_setor, weights=peso))

    razao = medido / alvo
    assert razao == pytest.approx(1.0, abs=TOLERANCIA), (
        f"escala da renda DOMICILIAR fora do IBGE: medido R$ {medido:,.2f} contra "
        f"R$ {alvo:,.2f} (razao {razao:.4f}). Um fator espurio entrou na cadeia — o suspeito "
        f"historico e o `k` da calibragem (1,2335) aplicado por cima do uplift."
    )


def test_renda_per_capita_do_artefato_bate_com_o_sidra(
    amostra: pd.DataFrame, referencia_sidra: pd.DataFrame
) -> None:
    """`V06004 x uplift_setor / moradores` tem de reproduzir a renda per capita do IBGE.

    Este e o assert que teria pego o defeito de -19,62%: exibindo `V06004/moradores x k`, a razao
    daria ~0,80.

    RAZAO DE SOMAS, nao media de razoes. Renda per capita e, por definicao, renda total dividida
    por gente total — e `media(x/y) != soma(x)/soma(y)`. Ponderar por domicilios uma razao ja
    per capita superestima em ~4,8% aqui, porque domicilio menor tende a ser mais rico. O erro
    seria do teste, nao do dado, e faria a trava acusar defeito onde nao ha.
    """
    up = np.array(
        [uplift_composicao_por_setor(c, None, m) for c, m in
         zip(amostra["cod_setor"], amostra["cod_municipio"], strict=False)],
        dtype=float,
    )
    dom = amostra["dom"].to_numpy(dtype=float)
    mor = amostra["mor"].to_numpy(dtype=float)
    renda_total = float(np.sum(amostra["resp"].to_numpy(dtype=float) * up * dom))
    pessoas_total = float(np.sum(mor * dom))
    medido = renda_total / pessoas_total

    por_mun = (
        pd.DataFrame(
            {"cod_municipio": amostra["cod_municipio"], "dom": dom, "pessoas": mor * dom}
        )
        .groupby("cod_municipio", as_index=False)[["dom", "pessoas"]].sum()
        .merge(referencia_sidra, on="cod_municipio", how="inner")
    )
    alvo = float(
        (por_mun["renda_domiciliar_total_ibge"] * por_mun["dom"]).sum()
        / por_mun["pessoas"].sum()
    )

    razao = medido / alvo
    assert razao == pytest.approx(1.0, abs=TOLERANCIA), (
        f"escala da renda PER CAPITA fora do IBGE: medido R$ {medido:,.2f} contra "
        f"R$ {alvo:,.2f} (razao {razao:.4f}). Se a razao estiver perto de 1/1,632 = 0,61, a conta "
        f"perdeu o uplift; se estiver perto de 0,80, esta usando o `k` no lugar dele."
    )


def test_motor_nao_introduz_fator_sobre_o_artefato() -> None:
    """A outra metade da trava: o CODIGO nao pode acrescentar escala que o artefato nao tem.

    Os testes acima ancoram o ARTEFATO no IBGE. Sozinhos, nao veem `censo_point.py`: alguem podia
    reintroduzir o `k` na exibicao e eles continuariam verdes. Aqui o motor real roda sobre uma
    particao real e se exige que a base da renda domiciliar caia DENTRO da faixa das rendas do
    responsavel dos setores que ele mesmo devolveu — o que qualquer media ponderada satisfaz, e
    que um fator multiplicativo espurio de 23% quebra assim que a faixa for mais estreita que ele.
    """
    from motor_expansao.dashboard.censo_point import analisar_ponto_censitario_setores
    from motor_expansao.dashboard.constants import FATOR_TEMPORAL_RENDA

    # Marilia/SP: ponto real, usado como referencia em toda a investigacao de 2026-08-13.
    part = GEO_DIR / "uf=SP" / "cod_municipio=3529005"
    if not part.exists():
        pytest.skip("particao de Marilia/SP indisponivel")

    particao = pd.read_parquet(part)
    res = analisar_ponto_censitario_setores(-22.213451, -49.949359, particao, raio_km=1.0)
    base = res["renda_media_domiciliar_raio"]
    total = res["renda_domiciliar_total_raio"]
    pc = res["renda_per_capita_media_raio"]
    assert base and total and pc, "o motor nao devolveu renda neste ponto"

    # `setores_intersectados` nao expoe a renda do responsavel (fora do schema de exibicao),
    # entao a faixa vem da PARTICAO, restrita aos setores que o motor de fato usou.
    usados = set(res["setores_intersectados"]["cod_setor"].astype(str))
    resp = pd.to_numeric(
        particao.loc[
            particao["cod_setor"].astype(str).isin(usados), "renda_responsavel_media_setor_2022"
        ],
        errors="coerce",
    ).dropna()
    if resp.empty:
        pytest.skip("nenhum setor do raio tem renda do responsavel")

    # Reproduz a cadeia DOCUMENTADA a partir das colunas cruas da particao, com os pesos que o
    # proprio motor devolveu. Faixas ("esta entre o min e o max") sao frouxas demais: medido, um
    # fator de 1,2335 na base ainda cai dentro da faixa deste raio e passa despercebido.
    inter = res["setores_intersectados"].set_index(
        res["setores_intersectados"]["cod_setor"].astype(str)
    )
    crus = particao.set_index(particao["cod_setor"].astype(str)).loc[list(inter.index)]
    peso_area = pd.to_numeric(inter["peso_area_setor"], errors="coerce").to_numpy(dtype=float)
    resp_v = pd.to_numeric(crus["renda_responsavel_media_setor_2022"], errors="coerce").to_numpy(float)
    mor_v = pd.to_numeric(crus["avg_moradores_domicilio_setor_2022"], errors="coerce").to_numpy(float)
    dom_v = pd.to_numeric(
        crus["domicilios_particulares_ocupados_setor_2022"], errors="coerce"
    ).to_numpy(float) * peso_area
    pop_v = pd.to_numeric(crus["pop_total_setor_2022"], errors="coerce").to_numpy(float) * peso_area
    up_v = np.array(
        [uplift_composicao_por_setor(c, "SP", "3529005") for c in inter.index], dtype=float
    )

    def _pond(valores: np.ndarray, pesos: np.ndarray) -> float:
        ok = np.isfinite(valores) & np.isfinite(pesos) & (pesos > 0)
        return float(np.average(valores[ok], weights=pesos[ok]))

    base_esperada = _pond(resp_v, dom_v)
    total_esperado = _pond(resp_v * up_v * float(FATOR_TEMPORAL_RENDA), dom_v)
    pc_esperada = _pond(resp_v * up_v * float(FATOR_TEMPORAL_RENDA) / mor_v, pop_v)

    assert base == pytest.approx(base_esperada, rel=0.005), (
        f"a base da renda domiciliar do motor (R$ {base:,.2f}) nao reproduz a media ponderada por "
        f"domicilios da V06004 dos setores do raio (R$ {base_esperada:,.2f}); razao "
        f"{base / base_esperada:.4f}. Um fator espurio entrou — o suspeito historico e o `k`."
    )
    assert total == pytest.approx(total_esperado, rel=0.005), (
        f"a renda domiciliar do motor (R$ {total:,.2f}) diverge da cadeia documentada "
        f"V06004 x uplift x fator temporal (R$ {total_esperado:,.2f})."
    )
    assert pc == pytest.approx(pc_esperada, rel=0.005), (
        f"a renda per capita do motor (R$ {pc:,.2f}) nao e a renda domiciliar per capita "
        f"(R$ {pc_esperada:,.2f}); razao {pc / pc_esperada:.4f}. Perto de 0,80 significa que ela "
        "voltou a usar o `k` no lugar do uplift."
    )


def test_a_calibrada_NAO_serve_de_base_para_renda_exibida(amostra: pd.DataFrame) -> None:
    """Trava do caminho errado, nao so do certo.

    `renda_per_capita_setor_2022_calibrada x moradores` NAO pode ser usada como renda do
    domicilio: ela devolve `V06004 x k`. Aqui so se afirma que as duas bases sao mesmo distintas
    no artefato real — se um dia o `k` virar 1,0 e elas coincidirem, este teste avisa que a trava
    de escala perdeu o poder de discriminar.
    """
    uma_uf = sorted(GEO_DIR.glob("uf=SP/cod_municipio=*"))[:1]
    if not uma_uf:
        pytest.skip("particao de SP indisponivel")
    df = pd.read_parquet(
        uma_uf[0],
        columns=[
            "renda_responsavel_media_setor_2022",
            "renda_per_capita_setor_2022_calibrada",
            "avg_moradores_domicilio_setor_2022",
        ],
    ).dropna()
    if df.empty:
        pytest.skip("particao sem renda")
    razao = (
        df["renda_per_capita_setor_2022_calibrada"] * df["avg_moradores_domicilio_setor_2022"]
    ) / df["renda_responsavel_media_setor_2022"]
    k = float(razao.median())
    assert abs(k - 1.0) > 0.05, (
        f"a base calibrada e a bruta coincidem (k = {k:.4f}): esta trava deixou de discriminar "
        "os dois caminhos e precisa ser revista junto com o papel do `k`."
    )
