"""Contratos da camada censitaria no grao do HEXAGONO agregada da malha de setores.

Todos os testes aqui sao de FORMA, nao de VALOR. A licao do defeito que originou este
modulo e' que nenhum teste de valor o teria pego: a formula estava certa, a cobertura
estava certa, os totais nacionais estavam certos, o k estava carimbado -- so' a
ALOCACAO ESPACIAL da renda estava errada, e o artefato continuava plausivel linha a
linha. Um golden com numero congelado fica falsamente verde diante disso.

Os dois grupos:
- puros (fixture sintetico): idempotencia, cobertura, unicidade do `k`, reescala.
- com artefato (pulam quando os parquets nao estao materializados): concordancia com a
  malha e AUTOCORRELACAO ESPACIAL -- a propriedade que pega permutacao sem conhecer
  nenhum numero.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.pipelines.agregar_censo_hex_da_malha import (
    COL_CARIMBO,
    COL_FONTE,
    COL_RENDA,
    COL_SCORE,
    FONTE_MALHA,
    k_exato,
    sobrepor_renda_da_malha,
)

MALHA_PATH = Path("data/staging/censo2022_hex_da_malha.parquet")
MERCADO_PATH = Path("data/staging/hexagonos_mercado_mapeado.parquet")

K_MALHA = 1.2334632197  # DEC-032, k nacional unico da renda setorial
K_HEX_ANTIGO = 1.0239   # o k que o caminho da Fase A gravava no grao do hexagono


# ---------------------------------------------------------------------------
# Puros
# ---------------------------------------------------------------------------


@pytest.fixture
def malha_sintetica(tmp_path: Path) -> Path:
    """Malha minima: 3 hexagonos com renda, um deles fora do censo de entrada."""
    caminho = tmp_path / "malha.parquet"
    pd.DataFrame(
        {
            "hex_id": ["a", "b", "z"],
            "renda_malha": [1000.0, 2000.0, 3000.0],
            "score_malha": [30.0, 60.0, 90.0],
            "k_malha": [K_MALHA] * 3,
        }
    ).to_parquet(caminho, index=False)
    return caminho


@pytest.fixture
def censo_sintetico() -> pd.DataFrame:
    """Censo de hexagono no `k` antigo: 'a' e 'b' cobertos pela malha, 'c' nao."""
    return pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            COL_RENDA: [500.0, 700.0, 900.0],
            COL_SCORE: [10.0, 20.0, 25.0],
            COL_CARIMBO: [f"multiplicativo_global_k={K_HEX_ANTIGO}"] * 3,
        }
    )


def test_sobreposicao_e_idempotente(censo_sintetico, malha_sintetica):
    """Aplicar duas vezes tem de ser igual a aplicar uma.

    `calcular_colunas_mercado` le o PROPRIO artefato como entrada, entao esta funcao
    roda sobre um frame que ela mesma ja pode ter reescalado. Sem idempotencia a segunda
    passada multiplicaria o residuo por 1,2047 outra vez -- e nada quebraria, porque o
    numero continuaria plausivel.
    """
    uma = sobrepor_renda_da_malha(censo_sintetico, malha_path=malha_sintetica)
    duas = sobrepor_renda_da_malha(uma, malha_path=malha_sintetica)
    pd.testing.assert_series_equal(uma[COL_RENDA], duas[COL_RENDA])
    pd.testing.assert_series_equal(uma[COL_SCORE], duas[COL_SCORE])


def test_sobreposicao_nao_reduz_cobertura(censo_sintetico, malha_sintetica):
    """Onde a malha nao alcanca, o valor antigo permanece (reescalado), nunca vira nulo.

    Cobertura e mais perigosa que valor: some por `has_censo_signal` ->
    `confianca_geografica` -> `populacao_corte_hex` -> `flag_sam` (DEC-006/007).
    """
    antes = censo_sintetico[COL_RENDA].notna().sum()
    depois = sobrepor_renda_da_malha(censo_sintetico, malha_path=malha_sintetica)
    assert depois[COL_RENDA].notna().sum() >= antes
    assert depois[COL_SCORE].notna().sum() >= censo_sintetico[COL_SCORE].notna().sum()


def test_hexagono_sem_malha_e_reescalado_e_nao_copiado(censo_sintetico, malha_sintetica):
    """O residuo troca de escala junto: senao a coluna sai com DOIS `k`."""
    out = sobrepor_renda_da_malha(censo_sintetico, malha_path=malha_sintetica)
    linha_c = out.loc[out.hex_id == "c"].iloc[0]
    esperado = 900.0 * (K_MALHA / K_HEX_ANTIGO)
    assert linha_c[COL_RENDA] == pytest.approx(esperado, rel=1e-6)
    assert linha_c[COL_FONTE] != FONTE_MALHA


def test_um_unico_carimbo_de_k_apos_a_sobreposicao(censo_sintetico, malha_sintetica):
    """A coluna homonima nao pode sair com dois `k`.

    Antes deste modulo ela saia com k=1,0239 no grao do hexagono e k=1,2335 no grao do
    setor -- 20,5% de diferenca entre o Mapa e o Relatorio Pontual para o MESMO endereco,
    sem nada quebrar, porque os dois numeros eram plausiveis isolados.
    """
    out = sobrepor_renda_da_malha(censo_sintetico, malha_path=malha_sintetica)
    carimbos = set(out[COL_CARIMBO].dropna().unique())
    assert len(carimbos) == 1, carimbos
    assert f"k={K_MALHA}"[:10] in carimbos.pop()


def test_sem_malha_o_censo_sai_intacto(censo_sintetico, tmp_path):
    """Ausencia do artefato da malha nao pode alterar nada — degrada, nao corrompe."""
    out = sobrepor_renda_da_malha(censo_sintetico, malha_path=tmp_path / "nao_existe.parquet")
    pd.testing.assert_frame_equal(out, censo_sintetico)


def test_k_exato_recusa_calibracao_nao_multiplicativa():
    """`k_exato` mede, e levanta quando a razao nao e constante.

    Um `k` que varia por linha significa que a coluna nao passou por um multiplicativo
    global — reescalar por uma media ali seria inventar numero. E' o defeito que a
    DEC-032 corrigiu (um `k` por UF), com sinal trocado.
    """
    bruta = pd.Series([100.0, 200.0, 300.0])
    with pytest.raises(ValueError, match="k nao e constante"):
        k_exato(bruta, pd.Series([110.0, 240.0, 300.0]))
    assert k_exato(bruta, bruta * 1.5) == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# Com artefato materializado
# ---------------------------------------------------------------------------

com_artefato = pytest.mark.skipif(
    not MALHA_PATH.exists() or not MERCADO_PATH.exists(),
    reason="artefatos de censo/mercado nao materializados neste checkout",
)


@com_artefato
def test_renda_servida_reproduz_a_malha():
    """Onde a malha cobre, o artefato servido tem de carregar o valor DELA.

    Compara CHAVE a CHAVE, nao distribuicao: distribuicao parecida foi exatamente o que
    deixou o defeito invisivel por meses (mediana batendo, ordem embaralhada).
    """
    malha = pd.read_parquet(MALHA_PATH, columns=["hex_id", "renda_malha"]).dropna()
    servido = pd.read_parquet(MERCADO_PATH, columns=["hex_id", COL_RENDA, COL_FONTE])
    j = servido[servido[COL_FONTE] == FONTE_MALHA].merge(malha, on="hex_id", how="inner")
    assert len(j) > 1000, f"amostra pequena demais para o contrato valer: {len(j)}"
    erro = (j[COL_RENDA] - j["renda_malha"]).abs()
    assert erro.max() < 1e-6, f"maior divergencia: {erro.max()}"


@com_artefato
def test_um_unico_k_no_artefato_servido():
    servido = pd.read_parquet(MERCADO_PATH, columns=[COL_CARIMBO])
    carimbos = set(servido[COL_CARIMBO].dropna().unique())
    assert len(carimbos) == 1, f"a coluna servida carrega {len(carimbos)} calibracoes: {carimbos}"


MORAN_MINIMO = 0.70
# Cidades onde a renda e' um gradiente ESPACIAL forte, medido na malha reparada em
# 2026-08-31: Sao Paulo +0,905 e Goiania +0,878. Com o artefato defeituoso Sao Paulo dava
# +0,425 -- o piso de 0,70 separa os dois casos com folga dos dois lados.
#
# RIO DE JANEIRO E BELO HORIZONTE FICAM DE FORA, e o motivo e' geografico, nao tecnico:
# medidos na MALHA PURA dao +0,435 e +0,579. No Rio favela e bairro rico sao vizinhos
# (Rocinha/Sao Conrado, Vidigal/Leblon, Complexo do Alemao), entao a renda tem
# descontinuidade real entre hexagonos adjacentes. Um piso global nao consegue separar
# "Rio de verdade" (+0,435) de "Sao Paulo embaralhado" (+0,425) -- por isso o contrato
# escolhe as cidades onde a propriedade vale, em vez de afrouxar o piso ate' passar.
CIDADES_GRADIENTE = [("SP", "Paulo"), ("GO", "Goi")]


@com_artefato
@pytest.mark.parametrize("uf,fragmento", CIDADES_GRADIENTE)
def test_autocorrelacao_espacial_da_renda(uf: str, fragmento: str):
    """Renda urbana e um GRADIENTE: hexagonos vizinhos se parecem.

    Este e o teste que teria pego o defeito sem conhecer numero nenhum. Permutar a renda
    entre setores preserva media, mediana, desvio e total -- e DESTROI a vizinhanca.
    Medido em 2026-08-31 nos mesmos hexagonos de Sao Paulo: Moran I +0,905 na malha
    contra +0,425 no artefato defeituoso.

    Nao e' calibracao, e' deteccao de embaralhamento -- e cobre um buraco que
    `test_renda_servida_reproduz_a_malha` nao cobre: se um dia a PROPRIA malha for
    embaralhada, comparar o servido com ela passaria verde.
    """
    import h3

    df = pd.read_parquet(
        MERCADO_PATH, columns=["hex_id", "uf", "nome_municipio", COL_RENDA, "pop_total_setor_2022"]
    )
    df = df[(df.uf == uf) & df.nome_municipio.astype(str).str.contains(fragmento, case=False, na=False)]
    df = df[(df.pop_total_setor_2022 > 1000) & df[COL_RENDA].notna()]
    if len(df) < 50:
        pytest.skip(f"{fragmento}/{uf} com poucos hexagonos povoados: {len(df)}")

    valor = dict(zip(df.hex_id, df[COL_RENDA].astype(float), strict=True))
    x = np.array([valor[h] for h in df.hex_id])
    media = x.mean()
    vizinhos = [[v for v in h3.grid_disk(h, 1) if v != h and v in valor] for h in df.hex_id]

    num = sum(
        (x[i] - media) * (valor[v] - media)
        for i, vs in enumerate(vizinhos)
        for v in vs
    )
    n_pares = sum(len(vs) for vs in vizinhos)
    if n_pares == 0:
        pytest.skip("sem pares de vizinhos no recorte")
    den = float(((x - media) ** 2).sum())
    moran = (len(x) / n_pares) * (num / den)
    assert moran >= MORAN_MINIMO, (
        f"Moran I da renda em {fragmento}/{uf} = {moran:.3f} - abaixo do piso de {MORAN_MINIMO}. "
        "Renda urbana e um gradiente suave; valor baixo aqui indica renda colada no "
        "hexagono errado, nao cidade heterogenea."
    )
