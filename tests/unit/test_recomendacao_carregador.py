"""Regua versionada da recomendacao unica (`regra/<PAIS>/<versao>.json` + `VIGENTE`).

Teste 13 da spec da Fase 2: VIGENTE -> arquivo; arquivo/JSON/chave/tipo/faixa invalidos ->
`RegraRecomendacaoInvalida` NOMEANDO o campo; pais sem diretorio -> None; fixacao por env com
WARNING; checagem de subida (regua invalida sempre erro; sem k so e erro em producao).
O contrato da BR v1 ancorado (numeros aprovados no GATE 2) fica em
`tests/contracts/test_recomendacao_contrato.py`.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from motor_expansao.recomendacao import (
    ENV_VERSAO,
    RegraRecomendacaoInvalida,
    carregar_regra,
    limpar_cache,
)
from motor_expansao.recomendacao import carregador as carregador_mod
from motor_expansao.recomendacao import subida as subida_mod
from motor_expansao.renda.hex import CENSO_MALHA_PARQUET, InsumoRendaInvalido

_V1: dict[str, Any] = json.loads(
    (carregador_mod.DIR_REGRA / "BR" / "2026-10_v1.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def _cache_limpo(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_VERSAO, raising=False)
    limpar_cache()
    yield
    limpar_cache()


def _gravar(raiz: Path, dados: Any, *, versao: str = "2026-10_v1", vigente: str | None = None):
    d = raiz / "BR"
    d.mkdir(parents=True, exist_ok=True)
    texto = dados if isinstance(dados, str) else json.dumps(dados)
    (d / f"{versao}.json").write_text(texto, encoding="utf-8")
    (d / "VIGENTE").write_text(vigente if vigente is not None else versao, encoding="utf-8")
    return d


def _carregar(raiz: Path):
    return carregar_regra("BR", raiz=raiz)


def test_vigente_aponta_o_arquivo(tmp_path: Path) -> None:
    v2 = copy.deepcopy(_V1) | {"versao": "2026-11_v2", "vagas_por_segmento": 3}
    d = _gravar(tmp_path, _V1)
    (d / "2026-11_v2.json").write_text(json.dumps(v2), encoding="utf-8")
    assert _carregar(tmp_path).versao == "2026-10_v1"
    (d / "VIGENTE").write_text("2026-11_v2\r\n", encoding="utf-8")  # CRLF do checkout Windows
    limpar_cache()
    r = _carregar(tmp_path)
    assert (r.versao, r.vagas_por_segmento, r.fixada_por_env) == ("2026-11_v2", 3, False)
    assert r.caminho == d / "2026-11_v2.json"


def test_cache_devolve_a_mesma_instancia(tmp_path: Path) -> None:
    _gravar(tmp_path, _V1)
    assert _carregar(tmp_path) is _carregar(tmp_path)
    assert hash(_carregar(tmp_path)) == hash(_carregar(tmp_path))


def test_pais_sem_diretorio_devolve_none(tmp_path: Path) -> None:
    assert carregar_regra("AR", raiz=tmp_path) is None


def test_argentina_real_nao_tem_regua() -> None:
    assert carregar_regra("AR") is None


def test_pais_padrao_vem_do_perfil_da_instancia(monkeypatch: pytest.MonkeyPatch) -> None:
    """`carregar_regra()` sem argumento (o caminho de `montar_recomendacao(regra=None)`): o pais
    e o do PERFIL. BR embarcado -> regua BR; instancia AR -> None (a tela segue o legado)."""
    from motor_expansao import perfil as perfil_mod

    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    real = perfil_mod.resolver_perfil
    real.cache_clear()
    try:
        r = carregar_regra()
        assert r is not None and r.pais == "BR"
        perfil_ar = perfil_mod.carregar_perfil(
            perfil_mod.PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json"
        )
        assert perfil_ar.pais == "AR"
        monkeypatch.setattr(perfil_mod, "resolver_perfil", lambda: perfil_ar)
        limpar_cache()
        assert carregar_regra() is None
    finally:
        real.cache_clear()


def test_pais_invalido(tmp_path: Path) -> None:
    with pytest.raises(RegraRecomendacaoInvalida, match="pais invalido"):
        carregar_regra("../x", raiz=tmp_path)


def test_fixacao_por_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    d = _gravar(tmp_path, _V1)
    v0 = copy.deepcopy(_V1) | {"versao": "2026-09_v0"}
    (d / "2026-09_v0.json").write_text(json.dumps(v0), encoding="utf-8")
    monkeypatch.setenv(ENV_VERSAO, "2026-09_v0")
    with caplog.at_level(logging.WARNING, logger="motor_expansao.recomendacao"):
        r = _carregar(tmp_path)
    assert r.versao == "2026-09_v0" and r.fixada_por_env is True
    assert ENV_VERSAO in caplog.text


def test_fixacao_por_env_de_versao_inexistente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(tmp_path, _V1)
    monkeypatch.setenv(ENV_VERSAO, "2099-01_vX")
    with pytest.raises(RegraRecomendacaoInvalida, match=ENV_VERSAO):
        _carregar(tmp_path)


def test_vigente_ausente(tmp_path: Path) -> None:
    d = _gravar(tmp_path, _V1)
    (d / "VIGENTE").unlink()
    with pytest.raises(RegraRecomendacaoInvalida, match="VIGENTE"):
        _carregar(tmp_path)


def test_vigente_vazio(tmp_path: Path) -> None:
    _gravar(tmp_path, _V1, vigente="  \n")
    with pytest.raises(RegraRecomendacaoInvalida, match="vazio"):
        _carregar(tmp_path)


def test_vigente_aponta_arquivo_inexistente(tmp_path: Path) -> None:
    _gravar(tmp_path, _V1, vigente="2026-12_v9")
    with pytest.raises(RegraRecomendacaoInvalida, match="2026-12_v9"):
        _carregar(tmp_path)


@pytest.mark.parametrize("arquivo", ["json", "VIGENTE"])
def test_arquivo_fora_de_utf8_e_regua_invalida(tmp_path: Path, arquivo: str) -> None:
    """Salvo em cp1252 (editor do Windows): erro DA REGUA nomeando o arquivo, nunca um
    `UnicodeDecodeError` cru no boot."""
    d = _gravar(tmp_path, _V1)
    alvo = d / ("2026-10_v1.json" if arquivo == "json" else "VIGENTE")
    if arquivo == "json":
        dados = copy.deepcopy(_V1) | {"aprovado_por": "Felipe Silva (aprovação)"}
        alvo.write_bytes(json.dumps(dados, ensure_ascii=False).encode("cp1252"))
    else:
        alvo.write_bytes("2026-10_v1çã".encode("cp1252"))
    with pytest.raises(RegraRecomendacaoInvalida, match="ilegivel") as exc:
        _carregar(tmp_path)
    assert alvo.name in str(exc.value)


def test_json_invalido(tmp_path: Path) -> None:
    _gravar(tmp_path, "{nao e json")
    with pytest.raises(RegraRecomendacaoInvalida, match="JSON invalido"):
        _carregar(tmp_path)


def _com(caminho: str, valor: Any) -> dict[str, Any]:
    dados = copy.deepcopy(_V1)
    alvo = dados
    partes = caminho.split(".")
    for p in partes[:-1]:
        alvo = alvo[p]
    if valor is _APAGAR:
        del alvo[partes[-1]]
    else:
        alvo[partes[-1]] = valor
    return dados


_APAGAR = object()


@pytest.mark.parametrize(
    ("campo", "valor", "nomeado"),
    [
        ("versao", "2026-10_v2", "versao"),
        ("pais", "AR", "pais"),
        ("dec", _APAGAR, "dec"),
        ("dec", "", "dec"),
        ("aprovado_por", None, "aprovado_por"),
        ("vagas_por_segmento", _APAGAR, "vagas_por_segmento"),
        ("vagas_por_segmento", 0, "vagas_por_segmento"),
        ("vagas_por_segmento", 11, "vagas_por_segmento"),
        ("vagas_por_segmento", 5.0, "vagas_por_segmento"),
        ("vagas_por_segmento", True, "vagas_por_segmento"),
        ("mata_virgem", [], "mata_virgem"),
        ("mata_virgem.renda_domiciliar_min", _APAGAR, "mata_virgem.renda_domiciliar_min"),
        ("mata_virgem.renda_domiciliar_min", 0, "mata_virgem.renda_domiciliar_min"),
        ("mata_virgem.renda_domiciliar_min", "4500", "mata_virgem.renda_domiciliar_min"),
        ("mata_virgem.renda_domiciliar_min", True, "mata_virgem.renda_domiciliar_min"),
        ("mata_virgem.residual_min", -1.0, "mata_virgem.residual_min"),
        ("mata_virgem.residual_min", None, "mata_virgem.residual_min"),
        ("mata_virgem.populacao_min", -5, "mata_virgem.populacao_min"),
        ("mata_virgem.populacao_min", False, "mata_virgem.populacao_min"),
        ("mata_virgem.exige_residual_medido", 1, "mata_virgem.exige_residual_medido"),
        ("mata_virgem.exige_residual_medido", _APAGAR, "mata_virgem.exige_residual_medido"),
        ("mata_virgem.residual_mini", 2000.0, "mata_virgem.residual_mini"),
        ("premium.score_min", 0, "premium.score_min"),
        ("premium.score_min", 100.01, "premium.score_min"),
        ("premium.score_min", True, "premium.score_min"),
        ("premium.score_min", _APAGAR, "premium.score_min"),
        ("premium.populacao_min", "10 mil", "premium.populacao_min"),
        ("premium.exige_residual_medido", "false", "premium.exige_residual_medido"),
        ("chave_nova", 1, "chave_nova"),
    ],
)
def test_regua_invalida_nomeia_o_campo(
    tmp_path: Path, campo: str, valor: Any, nomeado: str
) -> None:
    _gravar(tmp_path, _com(campo, valor))
    with pytest.raises(RegraRecomendacaoInvalida) as exc:
        _carregar(tmp_path)
    assert nomeado in str(exc.value)


def test_score_100_e_populacao_null_sao_validos(tmp_path: Path) -> None:
    dados = _com("premium.score_min", 100)
    dados["premium"]["populacao_min"] = None
    _gravar(tmp_path, dados)
    r = _carregar(tmp_path)
    assert r.premium.score_min == 100.0 and r.premium.populacao_min is None


def test_chaves_de_comentario_sao_ignoradas(tmp_path: Path) -> None:
    dados = copy.deepcopy(_V1)
    dados["mata_virgem"]["_obs"] = "comentario"
    _gravar(tmp_path, dados)
    assert _carregar(tmp_path).mata_virgem.renda_domiciliar_min == 4500.0


# ===========================================================================
# Subida
# ===========================================================================


def test_subida_regua_invalida_e_sempre_erro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(tmp_path, _com("premium.score_min", 0))
    monkeypatch.setattr(carregador_mod, "DIR_REGRA", tmp_path)
    monkeypatch.setattr(carregador_mod, "_pais_padrao", lambda: "BR")
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    with pytest.raises(RegraRecomendacaoInvalida, match="premium.score_min"):
        subida_mod.validar_na_subida(tmp_path)


def test_subida_sem_k_em_producao_e_erro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subida_mod, "carregar_regra", lambda: carregar_regra("BR"))
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    with pytest.raises(InsumoRendaInvalido, match="k da malha"):
        subida_mod.validar_na_subida(tmp_path)


def test_subida_sem_k_em_dev_so_avisa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(subida_mod, "carregar_regra", lambda: carregar_regra("BR"))
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    with caplog.at_level(logging.WARNING):
        r = subida_mod.validar_na_subida(tmp_path)
    assert r is not None and r.versao == "2026-10_v1"
    assert "Top 10" in caplog.text


def test_subida_com_k_em_producao_passa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pd.DataFrame({"metodo_calibracao_renda_malha": ["multiplicativo_global_k=1.2335"]}).to_parquet(
        tmp_path / CENSO_MALHA_PARQUET
    )
    monkeypatch.setattr(subida_mod, "carregar_regra", lambda: carregar_regra("BR"))
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    assert subida_mod.validar_na_subida(tmp_path) is not None


def test_subida_pais_sem_regua(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subida_mod, "carregar_regra", lambda: None)
    monkeypatch.setenv("MOTOR_DATA_DIR", "/nao/existe")
    assert subida_mod.validar_na_subida() is None
