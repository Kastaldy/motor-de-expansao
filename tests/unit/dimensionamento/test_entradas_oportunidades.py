"""Lote noturno das entradas do modelo de praca por imovel (DEC-086).

A calculadora de producao (Valhalla + malha de setores) e' trocada por uma FALSA: aqui se
trava o CONTRATO do lote -- incremental, falha permanente gravada, falha do servico nunca
gravada, parada com o servico fora sem perder o que ja' foi feito, e o arquivo de saida.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dimensionamento import entradas_oportunidades as eo


def _lista(tmp_path: Path, coords, *, status=None, nome="viaveis.parquet") -> Path:
    linhas = []
    for i, (lat, lng) in enumerate(coords):
        linhas.append({
            "imovel_id": f"im_{i}",
            "latitude": lat,
            "longitude": lng,
            "status": (status or {}).get(i, "ativo"),
        })
    caminho = tmp_path / nome
    pd.DataFrame(linhas).to_parquet(caminho)
    return caminho


class Calc:
    """Calculadora falsa: conta as chamadas e responde por coordenada."""

    def __init__(self, permanentes=(), servico=(), inesperados=()):
        self.chamadas: list[tuple[float, float]] = []
        self.permanentes = set(permanentes)
        self.servico = set(servico)
        self.inesperados = set(inesperados)

    def __call__(self, lat, lng):
        self.chamadas.append((lat, lng))
        if (lat, lng) in self.servico:
            raise eo.FalhaDoServico("timeout")
        if (lat, lng) in self.permanentes:
            raise eo.FalhaPermanente(eo.STATUS_SEM_ISOCRONA, "Sem via a menos de 300 m.")
        if (lat, lng) in self.inesperados:
            raise RuntimeError("geometria estranha")
        return {
            "pop_c10": 100_000.0 + abs(lat),
            "dom_c10": 35_000.0,
            "renda_pc_c10": 2_000.0,
            "n_setores": 120,
            "renda_fonte": "calibrada",
            "area_km2": 18.5,
            "versao_rotas": "2026-11-01T00:00:00+00:00",
        }


def _rodar(lista, saida, calc, **kw):
    return eo.rodar(lista, saida, calc, relogio=lambda: "2026-11-14T03:00:00+00:00",
                    log=lambda _m: None, **kw)


A, B, C = (-23.55001, -46.63002), (-22.90001, -43.17002), (-19.91001, -43.93002)


def test_primeira_rodada_calcula_cada_coordenada_uma_vez(tmp_path):
    # Dois imoveis no MESMO ponto (a 5 casas) viram UMA conta.
    lista = _lista(tmp_path, [A, (A[0] + 1e-7, A[1]), B])
    saida = tmp_path / "entradas_c10.parquet"
    calc = Calc()
    r = _rodar(lista, saida, calc)
    assert r.imoveis_vivos == 3 and r.coordenadas_unicas == 2 and r.pendentes == 2
    assert sorted(calc.chamadas) == sorted([eo.chave_coordenada(*A), eo.chave_coordenada(*B)])
    df = pd.read_parquet(saida)
    assert list(df.columns) == list(eo.COLUNAS)
    assert set(df["status"]) == {eo.STATUS_OK}
    assert str(df["n_setores"].dtype) == "Int64"


def test_segunda_rodada_so_calcula_o_que_e_novo_e_nao_regrava_sem_novidade(tmp_path):
    saida = tmp_path / "entradas_c10.parquet"
    _rodar(_lista(tmp_path, [A, B]), saida, Calc())
    antes = os.stat(saida).st_mtime_ns

    calc = Calc()
    r = _rodar(_lista(tmp_path, [A, B]), saida, calc)
    assert calc.chamadas == [] and r.pendentes == 0 and r.gravou is False
    assert os.stat(saida).st_mtime_ns == antes, "sem novidade o site nao pode reler a lista"

    calc = Calc()
    r = _rodar(_lista(tmp_path, [A, B, C]), saida, calc)
    assert calc.chamadas == [eo.chave_coordenada(*C)]
    assert r.ja_calculadas == 2 and len(pd.read_parquet(saida)) == 3


def test_falha_permanente_fica_gravada_com_o_motivo_e_nao_se_repete(tmp_path):
    saida = tmp_path / "entradas_c10.parquet"
    kb = eo.chave_coordenada(*B)
    _rodar(_lista(tmp_path, [A, B]), saida, Calc(permanentes={kb}))
    df = pd.read_parquet(saida).set_index(["lat5", "lng5"])
    assert df.loc[kb, "status"] == eo.STATUS_SEM_ISOCRONA
    assert "300 m" in df.loc[kb, "motivo"] and pd.isna(df.loc[kb, "pop_c10"])

    calc = Calc()
    _rodar(_lista(tmp_path, [A, B]), saida, calc)
    assert calc.chamadas == [], "falha permanente nao e' tentada de novo"


def test_falha_do_servico_nao_grava_nada_e_o_ponto_volta_na_proxima(tmp_path):
    saida = tmp_path / "entradas_c10.parquet"
    kb = eo.chave_coordenada(*B)
    r = _rodar(_lista(tmp_path, [A, B]), saida, Calc(servico={kb}))
    assert r.falhas_do_servico == 1 and r.abortou_por_servico is False
    assert kb not in set(zip(*pd.read_parquet(saida)[["lat5", "lng5"]].T.values, strict=True))

    calc = Calc()
    _rodar(_lista(tmp_path, [A, B]), saida, calc)
    assert calc.chamadas == [kb]


def test_servico_fora_para_o_lote_e_guarda_o_que_ja_foi_feito(tmp_path):
    coords = [(-23.0 - i / 100, -46.0) for i in range(10)]
    chaves = [eo.chave_coordenada(*c) for c in coords]
    saida = tmp_path / "entradas_c10.parquet"
    # As 3 primeiras dao certo; dali em diante o Valhalla caiu.
    calc = Calc(servico=set(chaves[3:]))
    r = _rodar(_lista(tmp_path, coords), saida, calc, max_falhas_seguidas=4)
    assert r.abortou_por_servico is True
    assert len(calc.chamadas) == 3 + 4, "para na 4a falha seguida, sem varrer o resto"
    assert len(pd.read_parquet(saida)) == 3


def test_erro_inesperado_e_contado_e_nao_grava(tmp_path):
    kb = eo.chave_coordenada(*B)
    saida = tmp_path / "entradas_c10.parquet"
    r = _rodar(_lista(tmp_path, [A, B]), saida, Calc(inesperados={kb}))
    assert r.erros_inesperados == {"RuntimeError": 1}
    assert len(pd.read_parquet(saida)) == 1


def test_removido_e_coordenada_vazia_ficam_fora(tmp_path):
    lista = _lista(tmp_path, [A, B, (float("nan"), -46.0)], status={1: "Removido"})
    calc = Calc()
    r = _rodar(lista, tmp_path / "entradas_c10.parquet", calc)
    assert r.imoveis_vivos == 2 and calc.chamadas == [eo.chave_coordenada(*A)]


def test_grava_no_meio_do_lote(tmp_path):
    """A primeira rodada leva ~1,2 h: o progresso vai ao disco a cada N pontos."""
    coords = [(-23.0 - i / 100, -46.0) for i in range(5)]
    saida = tmp_path / "entradas_c10.parquet"
    vistos: list[int] = []

    def calc(lat, lng):
        vistos.append(len(pd.read_parquet(saida)) if saida.exists() else 0)
        return Calc()(lat, lng)

    _rodar(_lista(tmp_path, coords), saida, calc, gravar_a_cada=2)
    assert vistos == [0, 0, 2, 2, 4]
    assert len(pd.read_parquet(saida)) == 5


def test_recalcular_tudo_substitui_mas_nao_apaga_o_que_nao_refez(tmp_path):
    saida = tmp_path / "entradas_c10.parquet"
    _rodar(_lista(tmp_path, [A, B, C]), saida, Calc())
    kb, kc = eo.chave_coordenada(*B), eo.chave_coordenada(*C)
    # Refaz tudo, mas o Valhalla cai depois do primeiro ponto.
    calc = Calc(servico={kb, kc})
    r = _rodar(_lista(tmp_path, [A, B, C]), saida, calc, recalcular_tudo=True,
               max_falhas_seguidas=2)
    assert r.abortou_por_servico is True and r.ja_calculadas == 0
    df = pd.read_parquet(saida)
    assert len(df) == 3, "o que nao foi refeito segue no arquivo"


def test_limite_corta_as_novas(tmp_path):
    coords = [(-23.0 - i / 100, -46.0) for i in range(6)]
    calc = Calc()
    r = _rodar(_lista(tmp_path, coords), tmp_path / "entradas_c10.parquet", calc, limite=2)
    assert len(calc.chamadas) == 2 and r.pendentes == 2


def test_lista_sem_coordenada_e_entrada_invalida(tmp_path):
    caminho = tmp_path / "viaveis.parquet"
    pd.DataFrame({"imovel_id": ["x"]}).to_parquet(caminho)
    with pytest.raises(ValueError, match="latitude"):
        _rodar(caminho, tmp_path / "entradas_c10.parquet", Calc())


def test_main_usa_os_caminhos_do_site_e_devolve_o_codigo(tmp_path, monkeypatch, capsys):
    import motor_expansao.perfil as perfil_mod

    (tmp_path / "oportunidades").mkdir()
    lista = _lista(tmp_path / "oportunidades", [A, B])
    monkeypatch.delenv(eo.ENV_OPORTUNIDADES, raising=False)
    monkeypatch.delenv(eo.ENV_SAIDA, raising=False)
    monkeypatch.setattr(perfil_mod, "resolver_perfil", lambda: type("P", (), {"raiz": tmp_path})())
    monkeypatch.setattr(eo, "calculadora_de_producao", lambda raiz, perfil: Calc())
    assert eo.main([]) == eo.CODIGO_OK
    resumo = json.loads(capsys.readouterr().out)
    assert resumo["calculadas_agora"] == {"ok": 2}
    assert Path(resumo["saida"]) == lista.with_name(eo.ARQUIVO_SAIDA)

    monkeypatch.setattr(eo, "calculadora_de_producao", lambda raiz, perfil: Calc(servico={
        eo.chave_coordenada(*C)}))
    _lista(tmp_path / "oportunidades", [A, B, C])
    assert eo.main(["--max-falhas-seguidas", "1"]) == eo.CODIGO_SERVICO_FORA
    capsys.readouterr()

    assert eo.main(["--oportunidades", str(tmp_path / "nao-existe.parquet")]) == (
        eo.CODIGO_ENTRADA_INVALIDA
    )
