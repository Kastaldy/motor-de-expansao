"""A regua da DEC-061 LIGADA no entregavel -- o unico chamador da dedup de cadeias.

Ate' a DEC-061 as duas reguas (trava de municipio e raio ampliado) existiam so' como opt-in na funcao
pura, e NENHUM chamador as ligava: aprovar a DEC nao mudaria um pin. `alvos_ma.py` e' quem grava
`vulnerabilidade_ma_redes.parquet` (o pin e, por `unir_cadeias`, a oferta de mercado) e quem calcula
a pressao por academia (a oferta do s6). Estes testes protegem:

  1. **Ligada por padrao, reversivel por flag** -- `--sem-dedup-dec061` volta a regua anterior.
  2. **A chave do mapa e' o CODIGO IBGE, nao o nome** -- 232 nomes de municipio existem em mais de
     uma UF, e com o nome como chave a propria trava fundiria homonimos de estados diferentes.
  3. **Sem o insumo, a trava desliga e AVISA** -- o raio segue ligado e o motivo diz que as
     sobreviventes sairao acima das 714 medidas.
  4. **A MESMA regua chega a pressao** -- pin e oferta nao podem ver reguas diferentes.
  5. **A auditoria do `main` diz qual regua valeu** -- de ponta a ponta, sem simular.

READ-ONLY sobre o M1: o `brasil_estrutural.parquet` e' lido, nunca escrito.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import alvos_ma as m
from motor_expansao.vulnerabilidade import pressao_competitiva as pc
from motor_expansao.vulnerabilidade.contrato import (
    CATEGORIA_INDEPENDENTE,
    DEDUP_CADEIA_FEED_RAIO_AMPLIADO_M,
)
from motor_expansao.vulnerabilidade.pressao_competitiva import dedup_cadeias_do_feed

from .test_alvos_ma import _carteira, _serie_de_duas_fontes
from .test_dedup_cadeias_por_municipio import _feed, _mapa, _mapeados


def _estrutural(caminho: Path, linhas: list[tuple[str, str | None, str]]) -> Path:
    """`(hex_id, cod_municipio, nome_municipio)` -> parquet no molde do artefato oficial do M1."""
    pd.DataFrame(
        {
            "hex_id": [h for h, _, _ in linhas],
            "uf": ["XX"] * len(linhas),
            "cod_municipio": [cod for _, cod, _ in linhas],
            "nome_municipio": [nome for _, _, nome in linhas],
        }
    ).to_parquet(caminho, index=False)
    return caminho


# --------------------------------------------------------------------------- #
# 1. Ligada por padrao, reversivel por flag                                    #
# --------------------------------------------------------------------------- #
def test_cli_liga_a_regua_por_padrao() -> None:
    """Omitir o flag e' LIGAR: e' o que a DEC decide, e o que a receita copiavel do runbook roda."""
    args = m._parse_args(["--base-dir", "x"])
    assert args.sem_dedup_dec061 is False
    assert args.estrutural is None


def test_a_flag_volta_a_regua_anterior_nas_duas_passagens() -> None:
    regua = m.resolver_regua_dedup_cadeias(
        m._parse_args(["--base-dir", "x", "--sem-dedup-dec061"])
    )
    assert regua.municipio_por_hex is None
    assert regua.raio_ampliado_m is None
    assert "ANTERIOR" in regua.motivo


def test_com_o_insumo_as_duas_passagens_ligam(tmp_path: Path) -> None:
    est = _estrutural(tmp_path / "e.parquet", [("hex-rio", "3304557", "Rio de Janeiro")])
    regua = m.resolver_regua_dedup_cadeias(
        m._parse_args(["--base-dir", "x", "--estrutural", str(est)])
    )
    assert regua.municipio_por_hex == {"hex-rio": "3304557"}
    assert regua.raio_ampliado_m == DEDUP_CADEIA_FEED_RAIO_AMPLIADO_M == 300.0
    assert regua.motivo.startswith("DEC-061:")


# --------------------------------------------------------------------------- #
# 2. A chave e' o CODIGO, nao o nome                                           #
# --------------------------------------------------------------------------- #
def test_o_mapa_carrega_o_codigo_e_nao_o_nome(tmp_path: Path) -> None:
    """Dois municipios HOMONIMOS de UFs diferentes tem de sair com valores DIFERENTES no mapa."""
    est = _estrutural(
        tmp_path / "e.parquet",
        [
            ("hex-a", "cod-uf-a", "Itabaiana"),
            ("hex-b", "cod-uf-b", "Itabaiana"),
            ("hex-c", None, "Sem codigo"),
        ],
    )
    assert m.mapa_municipio_por_hex(est) == {"hex-a": "cod-uf-a", "hex-b": "cod-uf-b"}, (
        "o valor tem de ser o codigo, e hex sem codigo nao pode entrar no mapa"
    )


def test_com_o_NOME_como_chave_a_trava_fundiria_homonimos_e_com_o_codigo_nao() -> None:
    """Por que a chave nao pode ser o nome: o `ITABAIANA` entrando pela porta da propria trava.

    Mesma rede, nome que casa, 50 km de distancia -- so' a trava de municipio alcancaria o par. Com o
    NOME como valor do mapa, os dois lados viram "Itabaiana" e a trava funde academias REAIS de
    estados diferentes. Com o CODIGO, sao municipios diferentes e nada colapsa.
    """
    feed = _feed([("k1", "selfit", 50_000.0, "Selfit Itabaiana")])
    mapeados = _mapeados([("selfit", 0.0, "ITABAIANA")])
    por_nome = _mapa((50_000.0, "Itabaiana"), (0.0, "Itabaiana"))
    por_codigo = _mapa((50_000.0, "cod-uf-a"), (0.0, "cod-uf-b"))

    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=por_nome)[0]) == 0, (
        "premissa do teste: com o nome como chave, os homonimos colapsam"
    )
    assert len(dedup_cadeias_do_feed(feed, mapeados, municipio_por_hex=por_codigo)[0]) == 1, (
        "com o codigo como chave, homonimos de UFs diferentes nao podem colapsar"
    )


# --------------------------------------------------------------------------- #
# 3. Sem o insumo, a trava desliga e AVISA                                     #
# --------------------------------------------------------------------------- #
def test_sem_o_insumo_a_trava_desliga_o_raio_segue_e_o_motivo_avisa(tmp_path: Path) -> None:
    ausente = tmp_path / "nao_existe.parquet"
    regua = m.resolver_regua_dedup_cadeias(
        m._parse_args(["--base-dir", "x", "--estrutural", str(ausente)])
    )
    assert m.mapa_municipio_por_hex(ausente) is None
    assert regua.municipio_por_hex is None
    assert regua.raio_ampliado_m == 300.0, "sem o mapa, o raio NAO pode desligar junto"
    assert "PARCIAL" in regua.motivo and "714" in regua.motivo


# --------------------------------------------------------------------------- #
# 4. A MESMA regua chega a pressao                                             #
# --------------------------------------------------------------------------- #
def test_a_pressao_recebe_a_regua_e_sem_ela_segue_o_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capturado: dict[str, object] = {}

    def falso_calcular(
        academias: pd.DataFrame, pontos: pd.DataFrame, **kwargs: object
    ) -> pd.DataFrame:
        capturado.clear()
        capturado.update(kwargs)
        return pd.DataFrame({"fonte": [], "chave_snapshot": []})

    monkeypatch.setattr(pc, "calcular_pressao_por_academia", falso_calcular)
    monkeypatch.setattr(pc, "ler_concorrentes", lambda _caminho: pd.DataFrame())
    insumo = tmp_path / "concorrentes.parquet"
    insumo.write_bytes(b"")
    academias = pd.DataFrame(
        {
            "fonte": ["wellhub", "wellhub"],
            "chave_snapshot": ["a", "b"],
            "lat": [0.0, 0.0],
            "lng": [0.0, 0.0],
            "rede": [CATEGORIA_INDEPENDENTE, "selfit"],
        }
    )

    regua = m.ReguaDedupCadeias({"hex": "cod"}, 300.0, "teste")
    m._pressao_por_academia(insumo, academias, regua=regua)
    assert capturado["dedup_cadeia_feed_municipio_por_hex"] == {"hex": "cod"}
    assert capturado["dedup_cadeia_feed_raio_ampliado_m"] == 300.0

    m._pressao_por_academia(insumo, academias)
    assert capturado["dedup_cadeia_feed_municipio_por_hex"] is None
    assert capturado["dedup_cadeia_feed_raio_ampliado_m"] is None


# --------------------------------------------------------------------------- #
# 5. A auditoria do `main` diz qual regua valeu                                #
# --------------------------------------------------------------------------- #
def test_a_auditoria_do_main_diz_qual_regua_valeu(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    base = tmp_path / "serie"
    _serie_de_duas_fontes(base)
    carteira = tmp_path / "carteira.parquet"
    _carteira().to_parquet(carteira, index=False)
    comum = [
        "--base-dir", str(base),
        "--carteira", str(carteira),
        "--sem-pressao",
        "--dry-run",
    ]  # fmt: skip

    ausente = tmp_path / "nao_existe.parquet"
    with caplog.at_level(logging.WARNING):
        assert m.main([*comum, "--estrutural", str(ausente)]) == 0
    saida = capsys.readouterr().out
    assert "'dedup_cadeias'" in saida and "PARCIAL" in saida, saida
    assert any(
        "PARCIAL" in r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    ), "a regua parcial tem de sair em WARNING, nao so' na auditoria"

    assert m.main([*comum, "--sem-dedup-dec061"]) == 0
    assert "ANTERIOR" in capsys.readouterr().out


def test_o_main_passa_a_MESMA_regua_ao_pin_proprio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metade do `main` que o teste anterior nao exercita: a regua chega ao PIN, nao so' a pressao.

    Sem isto, apagar os dois kwargs da chamada de `chaves_com_pin_proprio` deixaria a suite verde e o
    artefato de redes com a regua ANTERIOR -- pin e oferta divergindo em 137 unidades, que e' o
    defeito "a duplicata visivel e a oferta fantasma por duas portas".
    """
    from motor_expansao.vulnerabilidade import redes_nomeadas as rn
    from motor_expansao.vulnerabilidade import snapshots as msnap

    capturado: dict[str, object] = {}

    def falso_pin(
        cadeias: pd.DataFrame, pontos: pd.DataFrame, **kwargs: object
    ) -> set[tuple[str, str]]:
        capturado.update(kwargs)
        return set()

    feed = pd.DataFrame(
        {
            "fonte": ["wellhub"],
            "chave_snapshot": ["k1"],
            "lat": [-22.98],
            "lng": [-43.40],
            "rede": ["selfit"],
            "nome": ["Selfit Recreio"],
        }
    )
    monkeypatch.setattr(msnap, "coordenadas_por_chave", lambda **_kw: feed)
    monkeypatch.setattr(rn, "chaves_com_pin_proprio", falso_pin)
    monkeypatch.setattr(rn, "materializar_redes_nomeadas", lambda *_a, **_k: {"redes": "dry"})
    monkeypatch.setattr(pc, "ler_concorrentes", lambda _caminho: pd.DataFrame())
    monkeypatch.setattr(pc, "_pontos_validos_frame", lambda frame: frame)

    base = tmp_path / "serie"
    _serie_de_duas_fontes(base)
    carteira = tmp_path / "carteira.parquet"
    _carteira().to_parquet(carteira, index=False)
    concorrentes = tmp_path / "concorrentes.parquet"
    concorrentes.write_bytes(b"")
    est = _estrutural(tmp_path / "e.parquet", [("hex-rio", "3304557", "Rio de Janeiro")])

    argv = [
        "--base-dir", str(base),
        "--carteira", str(carteira),
        "--sem-pressao",
        "--dry-run",
        "--concorrentes", str(concorrentes),
        "--estrutural", str(est),
        "--saida-redes", str(tmp_path / "redes.parquet"),
    ]  # fmt: skip
    assert m.main(argv) == 0
    assert capturado["municipio_por_hex"] == {"hex-rio": "3304557"}, "a trava nao chegou ao pin"
    assert capturado["raio_ampliado_m"] == 300.0, "o raio nao chegou ao pin"
