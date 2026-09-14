"""A viabilidade no contrato PUBLICO da API — e a regua unica que a sustenta.

Ate' aqui `POST /api/v1/analisar` so' sabia devolver as 7 paginas base: o gerador tinha
os kwargs de viabilidade, mas nao havia por onde receber os insumos. A montagem do
payload vivia dentro do `web/server/app.py`, e a API nao podia usa-la sem importar uma
app FastAPI inteira.

O que estes testes protegem, na ordem em que o defeito voltaria:

1. **Uma regua so'** (FIN-VIAB-01). O piloto e a API tem que produzir o MESMO dict para
   o mesmo cenario. Foi a divergencia entre duas montagens que fez o mesmo caso sair com
   payback 35 e 33 e aluguel-teto de R$55,5 mil e R$105,8 mil.
2. **A coordenada nao se repete.** `ViabilidadeInputs` NAO tem lat/lng: na API o ponto ja'
   vem no corpo do request, e dois lugares para a mesma coordenada e' um lugar para eles
   discordarem.
3. **Ausencia continua sendo ausencia** (DEC-009). Sem o objeto de viabilidade, nada e'
   inventado — nem demanda, nem paginas.

Sem PII e sem dado real: o motor financeiro nao depende de parquet (sem base de
calibracao a faixa de alunos volta vazia, com a fonte declarada).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from motor_expansao.api.schemas import AnalisarRequest
from motor_expansao.dimensionamento.payload_viabilidade import (
    ViabilidadeIn,
    ViabilidadeInputs,
    montar_payload_viabilidade,
)

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

_CENARIO = {"lat": -23.55, "lng": -46.63, "m2": 1500, "aluguel": 30000, "demanda": 1600}


def test_payload_do_piloto_e_da_api_e_o_mesmo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prova da regua unica: mesmo cenario, dicts iguais campo a campo.

    O catchment e' NEUTRALIZADO nos dois lados (`setores_df=None`) de proposito: o que
    se compara aqui e' a MONTAGEM, e deixar o piloto ler a malha do disco compararia
    tambem a disponibilidade de dado da maquina — o teste passaria ou falharia por um
    motivo que nao e' o dele.
    """
    monkeypatch.setattr(pilot, "_setores_para_catchment", lambda lat, lng: None)

    do_piloto = pilot._payload_viabilidade(ViabilidadeIn(**_CENARIO))
    da_api = montar_payload_viabilidade(
        ViabilidadeIn(**_CENARIO), staging_dir=pilot.STAGING_DIR, setores_df=None
    )

    assert do_piloto == da_api
    assert do_piloto["versao"] == "viabilidade_payload_v1"


def test_viabilidade_inputs_nao_repete_a_coordenada() -> None:
    campos_inputs = set(ViabilidadeInputs.model_fields)
    campos_cenario = set(ViabilidadeIn.model_fields)

    assert {"lat", "lng"}.isdisjoint(campos_inputs)
    assert {"lat", "lng"} <= campos_cenario
    # O cenario completo e' os inputs MAIS o ponto: nenhum campo financeiro se perdeu
    # no caminho, o que uma redeclaracao a mao deixaria acontecer em silencio.
    assert campos_cenario == campos_inputs | {"lat", "lng"}


def test_analisar_request_aceita_o_cenario_e_os_dados_do_imovel() -> None:
    req = AnalisarRequest.model_validate(
        {
            "lat": -23.55,
            "lng": -46.63,
            "formato": "pdf",
            "viabilidade": {"m2": 1500, "aluguel": 30000, "demanda": 1600},
            "info_imovel": {"endereco": "Av. Paulista, 1500", "vagas": 12},
            "solicitante": "Juan",
        }
    )

    assert req.viabilidade is not None
    assert req.viabilidade.m2 == 1500
    assert req.info_imovel == {"endereco": "Av. Paulista, 1500", "vagas": 12}
    assert req.solicitante == "Juan"


def test_analisar_request_sem_viabilidade_continua_valido() -> None:
    """DEC-009: sem o objeto, o relatorio sai como sempre saiu. O que NAO pode existir
    e' um caminho em que a API invente demanda para preencher a pagina."""
    req = AnalisarRequest.model_validate({"lat": -23.55, "lng": -46.63})

    assert req.viabilidade is None
    assert req.info_imovel is None
    assert req.solicitante is None


def test_demanda_continua_obrigatoria_dentro_do_cenario() -> None:
    """Se alguem mandar viabilidade PELA METADE, o 422 e' a resposta certa — melhor que
    um DRE montado sobre demanda default, que sairia com cara de numero apurado."""
    with pytest.raises(ValueError):
        AnalisarRequest.model_validate(
            {"lat": -23.55, "lng": -46.63, "viabilidade": {"m2": 1500, "aluguel": 30000}}
        )
