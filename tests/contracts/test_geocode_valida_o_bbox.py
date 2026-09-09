"""Bloco A / commit A4 — `/api/geocode` valida o retorno contra o bbox do país.

**O defeito que isto fecha é real e está em produção hoje.** A rota devolvia o `top-1`
CRU do Nominatim, e o parâmetro `countrycodes` do Nominatim é uma **dica**, não uma
garantia: buscar `"Buenos Aires"` com `countrycodes=br` resolve para o município
homônimo de Pernambuco e volta com `found: true`. Um pin errado com cara de certo é
pior do que não achar — o operador não tem como saber que a barra de busca do Mapa o
levou para o lugar errado.

Compare com as outras rotas de coordenada: `resolve_endereco_http` e `resolve_plus_code`
(`maps_geocoder.py`) já validavam contra o bbox. `/api/geocode` era a única que não — e
é justamente a que a barra de busca do Mapa consome (`MapScreen.tsx` → `api.ts` →
`aplicarPonto`), a única das quatro que sobrevive ao gate de superfície do Bloco C no
dia 1 da Argentina.

Decisão de 2026-09-02 (Felipe, pendência **BR-P2**): ligar nos **dois** países. O campo
`geocode.validar_contra_bbox` saiu dos dois perfis — um campo que só poderia valer
`true` é o "campo sem leitor" que a spec §1.4 recusa.

Spec: `docs/spec_bloco_a_perfil.md` §2.3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

# Buenos Aires de verdade. Fora do bbox brasileiro (lat_min = -34,0), dentro do argentino.
BA_LAT, BA_LNG = -34.6037, -58.3816
# O municipio HOMONIMO em Pernambuco — o que o Nominatim devolve hoje para
# "Buenos Aires" com `countrycodes=br`. Dentro do bbox brasileiro.
BA_PE_LAT, BA_PE_LNG = -7.7261, -35.3181


class _RespostaFalsa:
    """Dublê de `requests.Response` com o mínimo que a rota consome."""

    ok = True

    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self._payload = payload

    def json(self) -> list[dict[str, Any]]:
        return self._payload


@pytest.fixture
def cache_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O cache de `/api/geocode` é por hash do TERMO e mora em disco.

    Sem isolar, um teste contamina o outro — e, o que é pior, contaminaria o worktree
    de quem rodar a suíte.
    """
    destino = tmp_path / "geocode"
    monkeypatch.setattr(pilot, "GEOCODE_CACHE_DIR", destino)
    return destino


def _mockar_nominatim(
    monkeypatch: pytest.MonkeyPatch, lat: float, lng: float, nome: str
) -> dict[str, Any]:
    """Substitui a ida à rede e devolve o dict de parâmetros que a rota mandaria."""
    capturado: dict[str, Any] = {}

    def _get(url: str, **kwargs: Any) -> _RespostaFalsa:
        capturado["url"] = url
        capturado["params"] = kwargs.get("params", {})
        capturado["headers"] = kwargs.get("headers", {})
        return _RespostaFalsa([{"lat": str(lat), "lon": str(lng), "display_name": nome}])

    import requests

    monkeypatch.setattr(requests, "get", _get)
    return capturado


# --------------------------------------------------------------------------------
# O defeito, e o conserto
# --------------------------------------------------------------------------------


def test_homonimo_brasileiro_de_buenos_aires_ainda_resolve(
    monkeypatch: pytest.MonkeyPatch, cache_isolado: Path
) -> None:
    """Guarda de precisão: o município de Buenos Aires/PE **existe** e está no Brasil.

    A validação não pode recusar por causa do NOME — ela olha a coordenada. Se este
    teste falhar junto com o próximo, a implementação está filtrando texto, não bbox.
    """
    _mockar_nominatim(monkeypatch, BA_PE_LAT, BA_PE_LNG, "Buenos Aires, Pernambuco")
    r = pilot.geocode(q="Buenos Aires PE")
    assert r["found"] is True
    assert r["lat"] == pytest.approx(BA_PE_LAT)


def test_coordenada_fora_do_bbox_vira_found_false_com_motivo(
    monkeypatch: pytest.MonkeyPatch, cache_isolado: Path
) -> None:
    """Buenos Aires DE VERDADE, sob perfil BR: recusada, e o motivo é nomeado.

    `{"found": false}` sozinho seria indistinguível de "o Nominatim não achou". O
    `motivo` é o que permite ao front dizer a coisa certa ao operador.
    """
    _mockar_nominatim(monkeypatch, BA_LAT, BA_LNG, "Buenos Aires, Argentina")
    r = pilot.geocode(q="Buenos Aires Argentina")
    assert r["found"] is False
    assert r["motivo"] == "fora_do_pais"


def test_a_rejeicao_nao_e_cacheada(
    monkeypatch: pytest.MonkeyPatch, cache_isolado: Path
) -> None:
    """**O detalhe que mais importa.** O cache é por hash do TERMO e sobrevive a uma
    troca de perfil: um "Buenos Aires" recusado sob perfil BR não pode voltar recusado
    depois de a instância virar AR. Gravar a rejeição em disco criaria um envenenamento
    silencioso que só se descobre no dia da subida da Argentina."""
    _mockar_nominatim(monkeypatch, BA_LAT, BA_LNG, "Buenos Aires, Argentina")
    pilot.geocode(q="Buenos Aires Argentina")
    gravados = list(cache_isolado.glob("*.json")) if cache_isolado.exists() else []
    assert gravados == [], f"a rejeicao foi cacheada em {gravados}"


def test_o_sucesso_continua_sendo_cacheado(
    monkeypatch: pytest.MonkeyPatch, cache_isolado: Path
) -> None:
    """A contrapartida: o cache da DEC-010 não pode ter morrido junto."""
    _mockar_nominatim(monkeypatch, BA_PE_LAT, BA_PE_LNG, "Buenos Aires, Pernambuco")
    pilot.geocode(q="Buenos Aires PE")
    gravados = list(cache_isolado.glob("*.json"))
    assert len(gravados) == 1
    assert json.loads(gravados[0].read_text(encoding="utf-8"))["found"] is True


# --------------------------------------------------------------------------------
# Os dois parâmetros que passam a sair do perfil
# --------------------------------------------------------------------------------


def test_countrycodes_e_idioma_saem_do_perfil(
    monkeypatch: pytest.MonkeyPatch, cache_isolado: Path
) -> None:
    """`countrycodes` era o literal `"br"` e `Accept-Language` **não era enviado**.

    A ausência do header não é cosmética: sem ele o Nominatim responde no idioma que
    quiser, e o `display_name` que vai para a tela vem em qualquer língua.
    """
    capturado = _mockar_nominatim(monkeypatch, BA_PE_LAT, BA_PE_LNG, "qualquer")
    pilot.geocode(q="Avenida Paulista 1000")
    assert capturado["params"]["countrycodes"] == pilot.PERFIL.geocode.countrycodes
    assert capturado["headers"]["Accept-Language"] == pilot.PERFIL.geocode.idioma
    # No perfil brasileiro, os valores de sempre.
    assert capturado["params"]["countrycodes"] == "br"


# --------------------------------------------------------------------------------
# A prova de que é o PERFIL que manda, e não um literal novo
# --------------------------------------------------------------------------------


def test_sob_perfil_argentino_buenos_aires_passa(
    monkeypatch: pytest.MonkeyPatch, cache_isolado: Path
) -> None:
    """O mesmo ponto que o perfil BR recusa, o perfil AR aceita.

    Exercita o bbox do `data/perfis/AR/perfil.json` REAL, não uma caixa inventada no
    teste — se alguém estreitar a caixa argentina e deixar Buenos Aires de fora, é aqui
    que aparece. O perfil é injetado direto no módulo porque a rota lê `PERFIL` do
    escopo de módulo (resolvido no import, DEC-047): não há troca de país em runtime,
    e é justamente isso que o monkeypatch simula para um processo que subiu como AR.
    """
    from motor_expansao.perfil import carregar_perfil

    perfil_ar = carregar_perfil(_REPO / "data" / "perfis" / "AR" / "perfil.json")
    assert perfil_ar.pais == "AR"
    monkeypatch.setattr(pilot, "PERFIL", perfil_ar)

    capturado = _mockar_nominatim(monkeypatch, BA_LAT, BA_LNG, "Buenos Aires, Argentina")
    r = pilot.geocode(q="Buenos Aires")

    assert r["found"] is True, "instancia AR tem de aceitar Buenos Aires"
    assert r["lat"] == pytest.approx(BA_LAT)
    assert capturado["params"]["countrycodes"] == "ar"
    assert capturado["headers"]["Accept-Language"] == perfil_ar.geocode.idioma


def test_sob_perfil_argentino_sao_paulo_e_recusada(
    monkeypatch: pytest.MonkeyPatch, cache_isolado: Path
) -> None:
    """A simetria. Sem ela, o teste acima passaria com uma caixa que aceita tudo."""
    from motor_expansao.perfil import carregar_perfil

    perfil_ar = carregar_perfil(_REPO / "data" / "perfis" / "AR" / "perfil.json")
    monkeypatch.setattr(pilot, "PERFIL", perfil_ar)

    _mockar_nominatim(monkeypatch, -23.5613, -46.6565, "Sao Paulo, Brasil")
    r = pilot.geocode(q="Avenida Paulista")
    assert r["found"] is False
    assert r["motivo"] == "fora_do_pais"
