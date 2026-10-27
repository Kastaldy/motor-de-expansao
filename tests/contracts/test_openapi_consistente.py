"""A spec OpenAPI nao pode referenciar o que nao existe.

Motivo de existir, medido: o PR #362 entrou com os SEIS checks verdes declarando
`security: [{bearerAuth: []}]` numa rota nova — e `bearerAuth` nao existe nesta spec.
O unico esquema definido e `tokenConsumidor`, aplicado na raiz. Nada reprovou, porque
nada olhava o arquivo: ruff nao le YAML, mypy nao le YAML, e a suite so' exercitava a app
FastAPI, que gera o proprio schema em runtime e nunca abre este documento.

Por que isso e' pior que cosmetico: parte das ferramentas de OpenAPI trata requisito de
seguranca com esquema INDEFINIDO como "sem requisito". Uma rota autenticada passaria a ser
documentada como publica — e quem gera cliente a partir da spec faria chamadas sem token.

`docs/api_geoespacial_openapi.yaml` e' a fonte de contrato para quem consome de fora (em
producao o `/docs` fica desligado, entao este arquivo e' o UNICO lugar onde o contrato se
le). Documento que envelhece calado e' a familia de defeito que mais custa aqui.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

SPEC = Path(__file__).resolve().parents[2] / "docs" / "api_geoespacial_openapi.yaml"


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


def _requisitos_de_seguranca(spec: dict[str, Any]) -> list[tuple[str, str]]:
    """(onde, nome do esquema) de cada requisito declarado — raiz e operacoes."""
    achados: list[tuple[str, str]] = []
    for req in spec.get("security") or []:
        achados.extend(("raiz", nome) for nome in req)
    for rota, operacoes in (spec.get("paths") or {}).items():
        for verbo, op in operacoes.items():
            if not isinstance(op, dict):
                continue
            for req in op.get("security") or []:
                achados.extend((f"{verbo.upper()} {rota}", nome) for nome in req)
    return achados


def test_todo_esquema_de_seguranca_citado_existe(spec: dict[str, Any]) -> None:
    definidos = set((spec.get("components") or {}).get("securitySchemes") or {})
    assert definidos, "a spec nao define nenhum securityScheme"

    pendentes = [(onde, nome) for onde, nome in _requisitos_de_seguranca(spec) if nome not in definidos]
    assert not pendentes, (
        "requisito de seguranca aponta para esquema inexistente: "
        + "; ".join(f"{onde} -> {nome!r}" for onde, nome in pendentes)
        + f". Definidos: {sorted(definidos)}"
    )


def test_toda_rota_autenticada_ou_declara_que_e_publica(spec: dict[str, Any]) -> None:
    """`security: []` e' a UNICA forma de dizer "esta rota e publica".

    Rota sem nenhuma mencao herda a raiz — e a raiz desta spec exige token. O que este
    teste impede e' a rota que se declara publica por ACIDENTE, com uma lista vazia
    escrita sem intencao. Hoje so' `/health` pode.
    """
    publicas = {
        rota
        for rota, operacoes in (spec.get("paths") or {}).items()
        for op in operacoes.values()
        if isinstance(op, dict) and op.get("security") == []
    }
    assert publicas == {"/health"}, f"rotas declaradas publicas: {sorted(publicas)}"


def test_todo_ref_de_schema_resolve(spec: dict[str, Any]) -> None:
    """`$ref` para schema que nao existe quebra qualquer gerador de cliente."""
    definidos = set((spec.get("components") or {}).get("schemas") or {})
    quebrados: list[str] = []

    def andar(no: Any) -> None:
        if isinstance(no, dict):
            alvo = no.get("$ref")
            if isinstance(alvo, str) and alvo.startswith("#/components/schemas/"):
                nome = alvo.rsplit("/", 1)[-1]
                if nome not in definidos:
                    quebrados.append(alvo)
            for valor in no.values():
                andar(valor)
        elif isinstance(no, list):
            for item in no:
                andar(item)

    andar(spec.get("paths"))
    andar((spec.get("components") or {}).get("schemas"))
    assert not quebrados, f"$ref sem destino: {sorted(set(quebrados))}"


def test_alcance_do_documento_e_o_do_motor(spec: dict[str, Any]) -> None:
    """O enum de `alcance` no documento e' o do motor (DEC-074, Emenda 3).

    Quem consome de fora le' SO' este arquivo. Se o motor ganhar um alcance e o documento
    nao, o cliente nunca pede; se o documento listar um que o motor nao tem, o cliente
    recebe 422 sem entender por que.
    """
    from motor_expansao.dashboard.alcance_ponto import ALCANCES

    campo = spec["components"]["schemas"]["AnalisarRequest"]["properties"]["alcance"]
    assert tuple(v for v in campo["enum"] if v is not None) == ALCANCES
    respostas = spec["paths"]["/analisar"]["post"]["responses"]
    assert "503" in respostas, "o 503 do servico de rotas nao esta documentado"
