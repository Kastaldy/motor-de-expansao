"""Pontos de patch da renda exibida para a suite (E0 do plano de correcao da renda).

Antes da E0 os testes trocavam o fator temporal reatribuindo `constants.FATOR_TEMPORAL_RENDA`
e trocavam o uplift patchando o NOME importado em cada consumidor (`censo_point`,
`censo_map`). Os dois pontos sumiram: o fator vem de um arquivo de versao lido por
`motor_expansao.renda.carregador`, e os insumos sao lidos como atributo do modulo
`motor_expansao.renda.insumos`. Os pontos de patch novos ficam aqui, num lugar so.

Tudo e desfeito pelo proprio `monkeypatch` -- nada de cache global que vaze entre testes:
  - `fixar_fatores` grava uma versao SINTETICA, carrega-a pelo loader REAL (raiz alternativa,
    com toda a validacao de schema) e a serve no lugar do `carregar_fatores` da formula;
  - `fixar_uplift_setor` troca o lookup de uplift por setor no modulo dos insumos;
  - `apontar_staging_renda` aponta os insumos para um staging de teste e zera os caches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from motor_expansao.renda import carregador, formula, insumos

#: Fator da versao 0 brasileira (`fatores/BR/2026-08_caged_v0.json`): o que producao exibe.
F_V0_BR = 1.1641

_CACHES_INSUMOS = (
    "_uplift_cache",
    "_uplift_uf_cache",
    "_moradores_cache",
    "_moradores_uf_cache",
    "_uplift_setor_cache",
    "_uplift_setor_extrapolado_cache",
)


def versao_sintetica(
    *,
    per_capita: float,
    domiciliar: float | None = None,
    pais: str = "BR",
    versao: str = "2026-10_teste_v1",
    rotulo_referencia: str = "teste (fatores sinteticos)",
) -> dict:
    """Dicionario de versao valido (schema completo) com os fatores pedidos."""
    dom = per_capita if domiciliar is None else domiciliar
    return {
        "versao": versao,
        "pais": pais,
        "ano_base_renda": 2022,
        "data_referencia_base": "2022-07",
        "ano_alvo": 2026,
        "fonte": {"pesquisa": "sintetica (teste)"},
        "data_extracao": "2026-10-20",
        "metodo": "sintetico",
        # moradores implicito pela coerencia interna: per_capita x moradores = domiciliar.
        "nacional": {"per_capita": per_capita, "domiciliar": dom, "moradores": dom / per_capita},
        "regra_excecao": None,
        "candidatas_regra": [],
        "excecoes_aprovadas": {},
        "ponte_ipca": None,
        "dec": None,
        "aprovado_por": None,
        "relatorio": None,
        "rotulo_referencia": rotulo_referencia,
        "rotulo_pdf": "Renda: teste - fatores sinteticos",
        "artefatos_obrigatorios": [],
        "artefato_k_obrigatorio": False,
    }


def fixar_fatores(
    monkeypatch: pytest.MonkeyPatch,
    raiz: Path,
    *,
    per_capita: float,
    domiciliar: float | None = None,
    pais: str = "BR",
    rotulo_referencia: str = "teste (fatores sinteticos)",
) -> carregador.FatoresRenda:
    """Serve uma versao SINTETICA de fatores a `fator()`/`renda_*()` durante o teste.

    A versao e gravada em `raiz/fatores/<pais>/` e carregada pelo loader REAL (sem cache), entao
    um schema invalido falha aqui como falharia em producao. A troca e no `carregar_fatores`
    que a formula usa -- o lru_cache do loader nao e tocado e nada vaza para o teste seguinte.
    """
    dados = versao_sintetica(
        per_capita=per_capita,
        domiciliar=domiciliar,
        pais=pais,
        rotulo_referencia=rotulo_referencia,
    )
    dir_fatores = Path(raiz) / "fatores"
    dir_pais = dir_fatores / pais
    dir_pais.mkdir(parents=True, exist_ok=True)
    (dir_pais / f"{dados['versao']}.json").write_text(json.dumps(dados), encoding="utf-8")
    (dir_pais / carregador.ARQUIVO_VIGENTE).write_text(dados["versao"], encoding="utf-8")
    fatores = carregador.carregar_fatores.__wrapped__(pais, raiz=dir_fatores)
    monkeypatch.setattr(formula, "carregar_fatores", lambda *_a, **_k: fatores)
    return fatores


def fixar_uplift_setor(monkeypatch: pytest.MonkeyPatch, uplift: float) -> None:
    """Uplift de composicao constante para todo setor (substitui o patch por nome de antes)."""
    monkeypatch.setattr(insumos, "uplift_setor", lambda *_a, **_k: uplift)


def apontar_staging_renda(monkeypatch: pytest.MonkeyPatch, staging: Path | None) -> None:
    """Aponta os insumos da renda para `staging` e zera os caches, com restauracao pos-teste.

    Registra no `monkeypatch` o apontamento e os seis caches ANTES de muda-los: quem chamar
    `configurar_staging` depois (o piloto faz isso no `_renda_staging_configurado`) tambem e
    desfeito no fim do teste.
    """
    monkeypatch.setattr(insumos, "_staging_configurado", insumos._staging_configurado)
    for cache in _CACHES_INSUMOS:
        monkeypatch.setattr(insumos, cache, None)
    insumos.configurar_staging(staging)
