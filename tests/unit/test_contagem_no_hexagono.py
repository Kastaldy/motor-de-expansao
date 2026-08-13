"""A ficha do hexagono conta ENDERECOS mapeados dentro do hexagono.

Regressao de 2026-08-13. O bloco "Quem ja disputa o aluno" do `FichaHex` promete
"unidades mapeadas dentro do hexagono" e mostrava outra coisa: `hex.conc` era
`n_concorrentes_est` = `oferta_consumida_mercado_estimada / 2.500` — CAPACIDADE do
modelo de 2 km ponderado por distancia, nao contagem; uma concorrente a 1,8 km do
centroide entrava ali sem estar dentro do hexagono. E `hex.ultra` vinha da camada de
performance. O mesmo defeito de redacao ja tinha sido corrigido no texto do funil
(docstring "RAIO, NAO HEXAGONO" em `_texto_passo3`); a ficha ficou para tras.

A primeira correcao contava LINHA e ainda discordava da tela: o Juan viu 8 pins onde a
ficha dizia 11. Duas causas, as duas travadas aqui:

* **Empilhamento.** Sobram 3.179 unidades validas em 3.111 coordenadas — 68 linhas caem
  sobre um ponto ja' ocupado, com redes DIFERENTES (o trio `aera_pilates`+`tonus_gym`+
  `vidya_studio` junto em 4 coordenadas), sem que a coleta as marque como duplicadas. Os
  pins empilham no mesmo pixel, entao a tela mostra menos marcadores do que linhas.
  Conta-se ENDERECO.
* **Descarte da coleta ignorado.** `status_registro` separa `valido` de
  `descartado_duplicado` (90) e `descartado_coord` (27), e o carregador nao olhava para
  ele. Passava despercebido porque as 90 duplicadas vem com `hex_id_res7` NULO e
  `_montar_pins` filtra por essa coluna — perdia-as por acidente. A chave nula NAO e'
  defeito do artefato: e' como a coleta marca o descarte. Derivar a celula do ponto para
  "consertar" o nulo ressuscitaria justamente o que ela jogou fora.

HERMETICO: os parquets de pontos sao sinteticos em `tmp_path`; nenhum `data/` real e
lido. READ-ONLY sobre o M1 — nada aqui toca score, pesos ou artefato oficial.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

h3 = pytest.importorskip("h3")

# As celulas sao DERIVADAS pelo h3 no proprio teste, nunca hardcoded: um id colado a mao
# envelhece em silencio se a resolucao mudar, e o teste passaria medindo outra coisa.
_LAT_A, _LNG_A = -23.5613, -46.6560  # Av. Paulista
_LAT_B, _LNG_B = -23.5620, -46.6555  # ~90 m de A -> MESMA celula, OUTRO endereco
_LAT_C, _LNG_C = -23.4800, -46.4000  # ~28 km de A -> outra celula

CELULA_A = h3.latlng_to_cell(_LAT_A, _LNG_A, 7)
CELULA_C = h3.latlng_to_cell(_LAT_C, _LNG_C, 7)
CELULA_VAZIA = h3.latlng_to_cell(-23.9600, -46.3300, 7)  # Santos: coberta, sem ponto

# Segundo endereco DENTRO da celula C, para a linha de chave nula. Sai do centroide da
# propria celula: assim esta' dentro por construcao, sem depender de eu acertar no olho.
_LAT_D, _LNG_D = h3.cell_to_latlng(CELULA_C)


def _escrever_bases(tmp_path: Path, *, com_concorrentes: bool, com_ultra: bool) -> None:
    """Materializa os parquets de PONTO que o backend le, em tmp_path.

    O cenario embute os dois casos reais da base: `Vidya` divide a coordenada EXATA da
    `Smart Fit` (endereco repetido sob outra rede, e a coleta NAO marca como duplicado) e
    `Bodytech` chega `descartado_duplicado` com `hex_id_res7` nulo — como as 90 reais.
    """
    if com_concorrentes:
        pd.DataFrame(
            {
                "rede": ["Smart Fit", "Bluefit", "Vidya", "Panobianco", "Bodytech"],
                "nome_unidade": [
                    "Paulista 1",
                    "Paulista 2",
                    "Mesmo endereco da Smart",
                    "Longe",
                    "Descartada pela coleta",
                ],
                "lat": [_LAT_A, _LAT_B, _LAT_A, _LAT_C, _LAT_D],
                "lng": [_LNG_A, _LNG_B, _LNG_A, _LNG_C, _LNG_D],
                "hex_id_res7": [CELULA_A, CELULA_A, CELULA_A, CELULA_C, None],
                "flag_coord_valida": [True, True, True, True, True],
                "status_registro": [
                    "valido",
                    "valido",
                    "valido",
                    "valido",
                    "descartado_duplicado",
                ],
            }
        ).to_parquet(tmp_path / "concorrentes_mapeados.parquet")

    if com_ultra:
        pd.DataFrame(
            {"unidade": ["Ultra Paulista"], "lat": [_LAT_B], "lng": [_LNG_B]}
        ).to_parquet(tmp_path / "unidades_ultra_performance_hex.parquet")


@pytest.fixture
def bases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reaponta as bases de ponto para tmp_path e zera TODAS as caches envolvidas.

    As caches sao `lru_cache` de modulo: sem limpar antes E depois, a primeira leitura
    real de `data/staging` vazaria para os testes seguintes (e vice-versa).
    """

    def _aplicar(*, com_concorrentes: bool = True, com_ultra: bool = True) -> None:
        _escrever_bases(tmp_path, com_concorrentes=com_concorrentes, com_ultra=com_ultra)
        monkeypatch.setattr(pilot, "CONCORRENTES_PARQUET", tmp_path / "concorrentes_mapeados.parquet")
        # Mesmo arquivo por outro nome: `_derivar` usa este para o prototipo de 1 km.
        monkeypatch.setattr(pilot, "CONCORRENTES_PATH", tmp_path / "concorrentes_mapeados.parquet")
        monkeypatch.setattr(
            pilot, "ULTRA_PERF_PARQUET", tmp_path / "unidades_ultra_performance_hex.parquet"
        )
        monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", tmp_path / "unidades_ultra_mapeadas.parquet")
        _limpar_caches()

    _limpar_caches()
    yield _aplicar
    _limpar_caches()


def _limpar_caches() -> None:
    for fn in (
        pilot._carregar_concorrentes,
        pilot._carregar_ultra_pontos,
        pilot._carregar_ultra_mapeadas,
        pilot._ultra_pontos_mapa,
        pilot._contagem_no_hexagono,
    ):
        fn.cache_clear()


def test_o_cenario_esta_montado_como_o_teste_supoe() -> None:
    """Guardas do proprio fixture. Sem elas um cenario mal montado faria os testes
    abaixo passarem por acidente — A e B em celulas diferentes dariam 1+1=2 sem que a
    deduplicacao por endereco estivesse funcionando."""
    assert h3.latlng_to_cell(_LAT_A, _LNG_A, 7) == h3.latlng_to_cell(_LAT_B, _LNG_B, 7)
    assert CELULA_A != CELULA_C
    # O endereco do `Bodytech` (chave nula) cai na celula C e NAO repete a do Panobianco.
    assert h3.latlng_to_cell(_LAT_D, _LNG_D, 7) == CELULA_C
    assert (_LAT_D, _LNG_D) != (_LAT_C, _LNG_C)


def test_conta_por_celula_e_nao_pelo_modelo_de_2km(bases) -> None:
    bases()

    n_conc, n_ultra = pilot._contagem_no_hexagono()

    assert n_conc is not None and n_ultra is not None
    assert int(n_conc[CELULA_A]) == 2  # 3 linhas, 2 enderecos
    assert int(n_conc[CELULA_C]) == 1  # so' o Panobianco: a Bodytech foi descartada
    assert int(n_ultra[CELULA_A]) == 1


def test_mesmo_endereco_com_redes_diferentes_conta_UMA_vez(bases) -> None:
    """`Vidya` divide a coordenada exata da `Smart Fit`. Sao 3 linhas na celula A e 2
    enderecos — e o mapa desenha os 3 pins empilhados em 2 pixels. Contar linha era o que
    fazia a ficha dizer 11 onde a tela mostra 8."""
    bases()
    n_conc, _ = pilot._contagem_no_hexagono()

    linhas_na_celula = 3
    assert int(n_conc[CELULA_A]) == 2 < linhas_na_celula


def test_descartado_pela_coleta_nao_entra_na_ficha_nem_nos_pins(bases) -> None:
    """`status_registro` e a fonte da verdade sobre o descarte — nao o `hex_id_res7` nulo.

    O filtro mora no CARREGADOR, que serve as DUAS pontas: `_montar_pins` (pins) e
    `_contagem_no_hexagono` (ficha). Filtrar so' na contagem deixaria a duplicata virar
    pin no mapa; e confiar no nulo faria o descarte depender de um detalhe que a coleta
    nunca prometeu manter — bastaria ela passar a gravar a celula para as 90 voltarem.
    """
    bases()
    conc = pilot._carregar_concorrentes()

    assert "Descartada pela coleta" not in set(conc["nome_unidade"].astype(str))
    assert len(conc) == 4  # 5 linhas no parquet, 1 descartada

    n_conc, _ = pilot._contagem_no_hexagono()
    assert int(n_conc[CELULA_C]) == 1


def test_hexagono_coberto_e_sem_unidade_da_zero_e_nao_ausencia(bases) -> None:
    """`0` aqui e AFIRMACAO: a base esta montada e nao ha unidade nesta celula."""
    bases()
    df = pilot._derivar(pd.DataFrame({"hex_id": [CELULA_A, CELULA_C, CELULA_VAZIA]}))

    assert df["n_conc_no_hex"].tolist() == [2, 1, 0]
    assert df["n_ultra_no_hex"].tolist() == [1, 0, 0]


def test_base_de_pontos_ausente_vira_None_e_NUNCA_zero(bases) -> None:
    """A regra da casa, escrita no cabecalho do FichaHex: zero afirma "nao ha
    concorrente", e ausencia nao afirma. Sem os parquets, o payload diz "nao sei"."""
    bases(com_concorrentes=False, com_ultra=False)

    n_conc, n_ultra = pilot._contagem_no_hexagono()
    assert n_conc is None and n_ultra is None

    # lat/lng entram porque `_hex_dict` os le direto (`r["lat"]`), sem `.get`.
    df = pilot._derivar(pd.DataFrame({"hex_id": [CELULA_A], "lat": [_LAT_A], "lng": [_LNG_A]}))
    assert df["n_conc_no_hex"].isna().all()
    assert df["n_ultra_no_hex"].isna().all()

    payload = pilot._hex_dict(df.iloc[0], None)
    assert payload["conc_hex"] is None
    assert payload["ultra_hex"] is None


def test_payload_separa_a_contagem_do_hexagono_do_modelo_de_2km(bases) -> None:
    """`conc` (2 km / 2.500) e `conc_hex` (enderecos) sao campos DISTINTOS e podem
    divergir — era exatamente essa divergencia que a ficha exibia como se fosse
    contagem. O de 2 km continua servindo mapa, funil e ranking."""
    bases()
    bruto = pd.DataFrame(
        {
            "hex_id": [CELULA_A],
            "lat": [_LAT_A],
            "lng": [_LNG_A],
            # 12.500 alunos consumidos / 2.500 = 5 "concorrentes" do modelo de 2 km,
            # contra os 2 enderecos realmente dentro do hexagono.
            "oferta_consumida_mercado_estimada": [12_500.0],
            "n_unidades_ultra_performance_hex": [7],
        }
    )
    linha = pilot._derivar(bruto).iloc[0]
    payload = pilot._hex_dict(linha, None)

    assert payload["conc"] == 5  # modelo de 2 km, inalterado
    assert payload["conc_hex"] == 2  # enderecos dentro do hexagono
    assert payload["ultra"] == 7  # camada de performance, inalterada
    assert payload["ultra_hex"] == 1  # ponto dentro do hexagono
    assert isinstance(payload["conc_hex"], int)  # contagem nao sai como 3.0 no JSON
