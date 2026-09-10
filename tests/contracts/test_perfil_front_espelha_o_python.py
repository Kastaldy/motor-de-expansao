"""Bloco A / commit A9 — o perfil do FRONT espelha o do Python, campo a campo.

Há duas cópias do perfil brasileiro do lado do cliente, e as duas podem envelhecer:

1. **`web/src/lib/perfil-br.ts`** — o default compilado. É ele que mantém `coord.ts`,
   `format.ts`, `faixas.ts`, `colors.ts` e `mapa-ponto.ts` testáveis pelo Vitest **sem
   servidor**; sem ele os testes desses módulos quebrariam por `undefined`, não por
   régua. Como não passa por requisição nenhuma, nada o obrigaria a bater com
   `data/perfis/BR/perfil.json` — e um default divergente é pior que ausente, porque
   responde com um número plausível.

2. **O payload de `/api/me`** — o perfil que a instância de fato serve. Se ele deixar de
   trazer um campo que o front lê, `definirPerfil` **rejeita o payload inteiro** (é
   fail-safe de propósito) e o front fica no default brasileiro, em silêncio, numa
   instância argentina.

Mesmo padrão de `tests/contracts/test_faixas_mapa_espelho.py`.

Spec: `docs/spec_bloco_a_perfil.md` §3.5 e §5.9 item 5.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[2]
_PERFIL_BR_JSON = _REPO / "data" / "perfis" / "BR" / "perfil.json"
_PERFIL_BR_TS = _REPO / "web" / "src" / "lib" / "perfil-br.ts"


@pytest.fixture(scope="module")
def json_br() -> dict[str, Any]:
    return json.loads(_PERFIL_BR_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ts_br() -> dict[str, Any]:
    """Extrai o objeto literal do `perfil-br.ts`.

    O arquivo é GERADO com `json.dumps`, então o corpo entre a primeira `{` e a última
    `}` é JSON válido — não é preciso um parser de TypeScript aqui.
    """
    texto = _PERFIL_BR_TS.read_text(encoding="utf-8")
    m = re.search(r"export const PERFIL_BR: PerfilCliente = (\{.*\})\s*$", texto, re.S)
    assert m, "objeto PERFIL_BR nao encontrado em web/src/lib/perfil-br.ts"
    return json.loads(m.group(1))


#: Caminho pontilhado de TODO campo que o front consome. É a mesma lista que
#: `_perfil_do_cliente()` monta em `web/server/app.py` — se as duas divergirem, um dos
#: dois testes abaixo falha nomeando o campo.
CAMPOS_DO_FRONT = [
    "pais",
    "nome",
    "locale",
    "moeda.codigo",
    "moeda.simbolo",
    "moeda.indicadores_renda",
    "bbox.lat_min",
    "bbox.lat_max",
    "bbox.lng_min",
    "bbox.lng_max",
    "vista_padrao.lat",
    "vista_padrao.lng",
    "vista_padrao.zoom",
    "reguas.pop_min_acionavel",
    "reguas.capacidade_unidade_alunos",
]

#: Campos que o payload SERVE mas que não são transcrição de campo do perfil: são
#: RESOLVIDOS pelo Python antes de sair (`_bandas_para_o_cliente` sobre
#: `RENDA_PER_CAPITA_BANDS` / `DENSIDADE_POP_BANDS`). Ficam FORA de `CAMPOS_DO_FRONT`
#: por construção, e não por esquecimento: `perfil.json` declara `reguas.faixas_renda`
#: e `reguas.faixas_densidade` — cortes e rótulos, sem cor —, e a cor vem da rampa da
#: plataforma. Comparar um contra o outro campo a campo compararia coisas diferentes.
#: Quem trava o VALOR deles é `tests/unit/test_paridade_paleta_web.py`, contra as
#: constantes do núcleo, nos dois perfis.
#: O `perfil-br.ts` compilado ainda NÃO os traz, e é por isso que eles ficam fora do
#: espelho TS↔JSON acima: quem os lê no front é `colors.ts`, no PR seguinte. Até lá o
#: campo viaja e ninguém o consome — o inverso do "campo sem leitor", e um estado
#: transitório declarado, não uma lacuna.
CAMPOS_RESOLVIDOS_NO_PAYLOAD = [
    "reguas.bandas_renda_setor",
    "reguas.bandas_densidade_setor",
]


def _ler(dados: dict[str, Any], caminho: str) -> Any:
    alvo: Any = dados
    for parte in caminho.split("."):
        assert isinstance(alvo, dict) and parte in alvo, f"`{caminho}` ausente"
        alvo = alvo[parte]
    return alvo


@pytest.mark.parametrize("campo", CAMPOS_DO_FRONT)
def test_perfil_br_ts_bate_com_o_json(
    json_br: dict[str, Any], ts_br: dict[str, Any], campo: str
) -> None:
    assert _ler(ts_br, campo) == _ler(json_br, campo), (
        f"`{campo}` divergiu entre web/src/lib/perfil-br.ts e "
        f"data/perfis/BR/perfil.json. O TS e GERADO do JSON: regenere, nao edite a mao."
    )


def test_o_ts_nao_traz_campo_ALEM_do_que_o_front_le(ts_br: dict[str, Any]) -> None:
    """Campo a mais no default é campo sem leitor — a mesma regra da spec §1.1, e o que
    impede o `perfil-br.ts` de virar uma segunda cópia do perfil inteiro."""
    achados: list[str] = []

    def _andar(d: Any, prefixo: str = "") -> None:
        if isinstance(d, dict):
            for k, v in d.items():
                _andar(v, f"{prefixo}{k}.")
        else:
            achados.append(prefixo.rstrip("."))

    _andar(ts_br)
    assert sorted(achados) == sorted(CAMPOS_DO_FRONT)


def test_o_payload_de_api_me_traz_exatamente_esses_campos() -> None:
    """O que a instância SERVE tem de ter a mesma forma do default compilado.

    Se `/api/me` parar de mandar um campo, `definirPerfil` rejeita o payload inteiro
    (fail-safe) e o front fica no default BRASILEIRO em silêncio — numa instância
    argentina, isso é o mapa nascendo no país errado sem nenhum erro na tela.
    """
    servidor = _REPO / "web" / "server"
    if str(servidor) not in sys.path:
        sys.path.insert(0, str(servidor))
    import app as pilot  # noqa: PLC0415

    payload = pilot._perfil_do_cliente()
    for campo in CAMPOS_DO_FRONT + CAMPOS_RESOLVIDOS_NO_PAYLOAD:
        _ler(payload, campo)  # levanta nomeando o campo se faltar

    achados: list[str] = []

    def _andar(d: Any, prefixo: str = "") -> None:
        if isinstance(d, dict):
            for k, v in d.items():
                _andar(v, f"{prefixo}{k}.")
        else:
            achados.append(prefixo.rstrip("."))

    _andar(payload)
    assert sorted(achados) == sorted(CAMPOS_DO_FRONT + CAMPOS_RESOLVIDOS_NO_PAYLOAD), (
        "o payload de /api/me divergiu da lista que o front consome"
    )


def test_o_payload_bate_com_o_perfil_carregado() -> None:
    """Prova que o payload é DERIVADO do perfil, e não uma terceira transcrição."""
    servidor = _REPO / "web" / "server"
    if str(servidor) not in sys.path:
        sys.path.insert(0, str(servidor))
    import app as pilot  # noqa: PLC0415

    payload = pilot._perfil_do_cliente()
    assert payload["nome"] == pilot.PERFIL.nome
    assert payload["locale"] == pilot.PERFIL.locale
    assert payload["moeda"]["simbolo"] == pilot.PERFIL.moeda.simbolo
    assert payload["moeda"]["indicadores_renda"] == pilot.PERFIL.moeda.indicadores_renda
    assert payload["bbox"]["lat_min"] == pilot.PERFIL.bbox.lat_min
    assert payload["vista_padrao"]["zoom"] == pilot.PERFIL.vista_padrao.zoom
    assert (
        payload["reguas"]["pop_min_acionavel"] == pilot.PERFIL.reguas.pop_min_acionavel
    )
