"""As camadas de leitura do pacote ARGENTINO na fronteira de leitura do piloto.

O pacote argentino ganhou, nas fases 12-17 do `motor-argentina`, cinco camadas que ja
viajavam nas particoes `uf=*` e que o backend nao lia: obra autorizada (INDEC), sociedades
novas (IGJ), emprego e empresas (OEDE) e fluxo de transporte (SUBE). Este modulo trava as
quatro formas de essa travessia dar errado SEM erro nenhum:

- **virar cartao no Brasil.** O binario e um so (`docs/plano_multipais.md` — "um binario,
  N containers, um pais por processo"), entao o MESMO codigo roda na instancia brasileira,
  onde nenhuma dessas colunas existe. Se a secao aparecer la, aparece vazia;
- **NaN virando zero.** Vazio aqui e partido sem pesquisa do INDEC, celula suprimida por
  sigilo ou fonte que nao alcanca o lugar. Zero e medicao (La Paz autorizou 84 m2 em 2022
  e 0 em 2025). Confundir os dois inventa dado, e nenhum tipo reclama;
- **viajar por hexagono.** Sao todos atributo do PARTIDO/DEPARTAMENTO. O repositorio ja
  pagou essa conta uma vez e a mediu (`_bloco_municipal`: SP 6,58 -> 4,71 MB ao tirar seis
  campos municipais do payload por hexagono). Doze campos repetidos em 15.000 hexes
  refariam o mesmo defeito com dado novo;
- **numero sem periodo.** As cinco fontes tem janelas diferentes; m2 sem intervalo nao diz
  se descreve o ultimo ano ou 2019.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tests.unit.test_piloto_web_endpoints import (  # noqa: F401
    _point_app_at,
    _synthetic_enriched,
    pilot,
    synth_data,
)

#: O que `_CAMADAS_AR` promete entregar. Escrito aqui a mao DE PROPOSITO: derivar do
#: proprio `_CAMADAS_AR` faria o teste concordar com qualquer renomeacao futura.
CHAVES = {
    "obras_m2",
    "obras_var",
    "obras_periodo",
    "soc_n",
    "soc_var",
    "soc_janela",
    "emp_estoque",
    "emp_salario",
    "emp_constr",
    "emp_periodo",
    "fluxo_dia",
    "fluxo_periodo",
}

#: cidade -> (obras, obras_var, soc, soc_var, estoque, salario, constr, fluxo)
#: Sao Paulo tem tudo; Campinas so as camadas de alcance NACIONAL (o caso comum fora da
#: RMBA); Santos, nada.
#:
#: `constr` vai em FRACAO (0..1), que e como o produtor a escreve — e e por isso que o
#: valor de Campinas e 0,0457, a mediana real do pacote: com `casas=1` e sem a conversao
#: de `_CAMADAS_AR`, ele arredondaria para `0,0` e o teste abaixo veria "0,0 %" onde sao
#: 4,6 %. Escrever 4,57 aqui esconderia exatamente o defeito que o teste procura.
POR_CIDADE = {
    "Sao Paulo": (34_900.0, 12.4, 1_485.0, 8.1, 52_300.0, 1_180.0, 0.074, 61_200.0),
    "Campinas": (None, None, None, None, 9_820.0, 940.0, 0.0457, None),
    "Santos": (None, None, None, None, None, None, None, None),
}

COLS_NUMERO = [
    "mun_permisos_m2_12m",
    "mun_permisos_cresc_pct",
    "soc_hex_n_3a",
    "soc_hex_cresc_partido_pct",
    "oede_emp_estoque",
    "oede_sal_medio_usd",
    "oede_constr_share",
    "sube_usos_dia",
]


def _com_camadas() -> pd.DataFrame:
    """O enriquecido sintetico com as camadas argentinas por cima."""
    df = _synthetic_enriched()
    santos = pd.DataFrame(
        {
            "hex_id": ["87a2000000000ffff"],
            "lat": [-23.96],
            "lng": [-46.33],
            "nome_municipio": ["Santos"],
            "cod_municipio": ["3548500"],
        }
    )
    df = pd.concat([df, santos], ignore_index=True)

    nomes = df["nome_municipio"]
    for i, col in enumerate(COLS_NUMERO):
        df[col] = [POR_CIDADE[n][i] for n in nomes]
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # O periodo acompanha o numero: existe so onde ha numero.
    for col_num, col_per, rotulo in (
        ("mun_permisos_m2_12m", "mun_permisos_periodo", "2025-07..2026-06"),
        ("soc_hex_n_3a", "soc_hex_janela_3a", "2023..2025"),
        ("oede_emp_estoque", "oede_periodo", "2019-11..2025-11"),
        ("sube_usos_dia", "sube_periodo", "2026-01-01..2026-09-08"),
    ):
        df[col_per] = [rotulo if pd.notna(v) else None for v in df[col_num]]

    # Existem no pacote e NAO devem atravessar — ver `_CAMADAS_AR`.
    df["viirs_luz_media"] = 2.4
    df["viirs_periodo"] = "2023"
    return df


@pytest.fixture
def dados_ar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """App apontado para um enriquecido sintetico COM as camadas argentinas."""
    part = tmp_path / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=SP"
    part.mkdir(parents=True)
    _com_camadas().to_parquet(part / "part-0.parquet")  # escrita do TESTE, nao do app
    _point_app_at(monkeypatch, tmp_path)
    yield tmp_path
    pilot.carregar_uf.cache_clear()


def _uf() -> dict:
    return pilot.uf_view("SP")


# ---------------------------------------------------------------------------
# 1) O Brasil nao ganha a secao
# ---------------------------------------------------------------------------


def test_pacote_sem_as_colunas_devolve_bloco_vazio(synth_data: Path) -> None:  # noqa: F811
    """O caso BRASILEIRO, que e o que roda hoje no outro container.

    `carregar_uf` descarta as colunas na intersecao, o bloco sai `{}` e a ficha nao
    desenha a secao. Nenhum `if (pais)` em lugar nenhum do caminho.
    """
    assert _uf()["ctx_mun"] == {}


def test_a_rota_de_municipio_tambem_devolve_o_bloco(synth_data: Path) -> None:  # noqa: F811
    """As duas rotas servem a MESMA ficha; uma so com o bloco e meia travessia."""
    assert pilot.municipio("SP", "Sao Paulo")["ctx_mun"] == {}


# ---------------------------------------------------------------------------
# 2) Com as colunas: uma vez por cidade, chaveado pelo que o hexagono carrega
# ---------------------------------------------------------------------------


def test_bloco_vem_uma_vez_por_cidade_e_casa_com_o_hexagono(dados_ar: Path) -> None:
    payload = _uf()
    blocos = payload["ctx_mun"]
    assert blocos, "nenhuma cidade com leitura"
    muns = {h["mun"] for h in payload["hexes"] if h.get("mun")}
    assert set(blocos) <= muns, "chave do bloco que nenhum hexagono sabe procurar"
    assert len(blocos) <= len(muns), "uma entrada por hexagono, nao por cidade"


def test_os_numeros_nao_viajam_no_hexagono(dados_ar: Path) -> None:
    """A economia de payload que `_bloco_municipal` mediu vale para estas tambem."""
    hexagono = _uf()["hexes"][0]
    assert not (CHAVES & set(hexagono)), "campo municipal repetido em cada hexagono"
    crus = ("mun_permisos", "soc_hex", "oede_", "sube_", "viirs")
    assert not [k for k in hexagono if k.startswith(crus)]


# ---------------------------------------------------------------------------
# 3) NaN nao e zero, e zero nao e NaN
# ---------------------------------------------------------------------------


def test_cidade_sem_nenhuma_leitura_nao_entra(dados_ar: Path) -> None:
    assert "Santos" not in _uf()["ctx_mun"]


def test_cidade_com_leitura_parcial_entra_com_os_ausentes_nulos(dados_ar: Path) -> None:
    """Campinas tem OEDE (nacional) e nao tem INDEC nem SUBE. E o caso COMUM."""
    c = _uf()["ctx_mun"]["Campinas"]
    assert c["emp_estoque"] == 9820
    assert c["obras_m2"] is None and c["fluxo_dia"] is None
    assert c["obras_periodo"] is None, "periodo sobreviveu ao numero que o justificava"


def test_zero_medido_sobrevive_e_nao_some() -> None:
    """O contrario do caso acima, e o mais facil de quebrar sem perceber.

    La Paz (Mendoza) autorizou 84 m2 em 2022 e 0 em 2025: o zero E o dado. Uma guarda
    escrita como `if valor:` em vez de `is not None` apagaria exatamente a medicao que
    diz "a obra parou aqui".
    """
    bloco = pilot._bloco_camadas_leitura(
        pd.DataFrame({"nome_municipio": ["La Paz"], "mun_permisos_m2_12m": [0.0]})
    )
    assert bloco["La Paz"]["obras_m2"] == 0, "zero medido virou ausencia"


def test_nan_nao_vira_zero() -> None:
    bloco = pilot._bloco_camadas_leitura(
        pd.DataFrame(
            {
                "nome_municipio": ["Cego"],
                "mun_permisos_m2_12m": [float("nan")],
                "oede_emp_estoque": [10.0],
            }
        )
    )
    assert bloco["Cego"]["obras_m2"] is None, "NaN virou numero"


def test_sem_a_coluna_de_nome_nao_ha_o_que_chavear() -> None:
    """Sem `nome_municipio` o bloco nao teria chave — devolver `{}` e a saida honesta."""
    assert pilot._bloco_camadas_leitura(pd.DataFrame({"mun_permisos_m2_12m": [1.0]})) == {}


# ---------------------------------------------------------------------------
# 4) Periodo e as exclusoes declaradas
# ---------------------------------------------------------------------------


def test_todo_numero_chega_com_o_seu_periodo(dados_ar: Path) -> None:
    sp = _uf()["ctx_mun"]["Sao Paulo"]
    assert set(sp) == CHAVES
    for numero, periodo in (
        ("obras_m2", "obras_periodo"),
        ("soc_n", "soc_janela"),
        ("emp_estoque", "emp_periodo"),
        ("fluxo_dia", "fluxo_periodo"),
    ):
        assert sp[numero] is not None and sp[periodo], f"{numero} chegou sem data"


def test_fracao_vira_ponto_percentual_na_fronteira(dados_ar: Path) -> None:
    """A unica coluna do bloco que NAO vem em pontos percentuais.

    `oede_constr_share` e fracao (mediana 0,0457; maximo 0,6209 em Anelo/NQ, que e 62 %
    de construcao no emprego local, nao 0,6 %). As outras duas colunas de percentual do
    bloco ja vem em pontos. Sem converter, o arredondamento de `casas=1` publicaria
    "0,0 %" — errado, silencioso, e sem tipo nenhum para reclamar.
    """
    ctx = _uf()["ctx_mun"]
    assert ctx["Sao Paulo"]["emp_constr"] == pytest.approx(7.4)
    assert ctx["Campinas"]["emp_constr"] == pytest.approx(4.6), "fracao arredondada a zero"


def test_escala_nao_transforma_ausencia_em_numero(dados_ar: Path) -> None:
    """Multiplicar por 100 nao pode ser o caminho por onde o NaN vira 0."""
    bloco = pilot._bloco_camadas_leitura(
        pd.DataFrame({"nome_municipio": ["Cego"], "oede_constr_share": [float("nan")],
                      "oede_emp_estoque": [10.0]})
    )
    assert bloco["Cego"]["emp_constr"] is None


def test_viirs_fica_de_fora_de_proposito(dados_ar: Path) -> None:
    """Exclusao ESCOLHIDA, nao esquecimento — e por isso tem teste.

    A coluna existe no pacote com 100 % de cobertura, mas radiancia crua nao tem regua
    publicada que o operador saiba ler, e o backtest do produtor mediu +0,0030 de AUC
    sobre o score, abaixo do piso de 0,01 que ele mesmo declarou. Entra no dia em que
    houver regua — e este teste e que deve ser reescrito primeiro.
    """
    assert not any("viirs" in c for c in pilot._COLS_CAMADAS_AR)
    assert not any("viirs" in k for k in _uf()["ctx_mun"]["Sao Paulo"])
