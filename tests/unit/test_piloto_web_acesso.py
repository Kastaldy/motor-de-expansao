"""Controle temporario de acesso por aba do piloto (web/server/acesso.py + /api/me).

Segue o padrao da suite do piloto (test_piloto_web_api.py): chama as funcoes DIRETO,
sem TestClient/httpx. O middleware do app e' um embrulho fino de `motivo_bloqueio`;
a logica inteira vive nas funcoes puras testadas aqui, e o teste de cobertura de
rotas garante que rota nova nao nasce fora do controle sem decisao explicita.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402  (modulo do piloto; web/server no sys.path acima)
import app as pilot_app  # noqa: E402

TODAS = acesso.ABAS_VALIDAS


@pytest.fixture()
def escrever_mapa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Grava um JSON de mapa e aponta o modulo para ele, zerando o cache global."""

    def _escrever(conteudo: object) -> Path:
        p = tmp_path / "acesso_abas.json"
        texto = conteudo if isinstance(conteudo, str) else json.dumps(conteudo)
        p.write_text(texto, encoding="utf-8")
        monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", str(p))
        acesso._cache = None
        return p

    yield _escrever
    acesso._cache = None  # nao vazar cache de um teste para o outro


# --- degradacao (fail-open) --------------------------------------------------


def test_sem_arquivo_todas_as_abas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev local e mount ausente nao podem trancar o piloto: controle desligado."""
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", str(Path("Z:/nao/existe/acesso.json")))
    acesso._cache = None
    assert acesso.abas_do_usuario("qualquer_um") == TODAS
    assert acesso.motivo_bloqueio("/api/rede/carteira", "qualquer_um") is None


def test_json_invalido_e_fail_open(escrever_mapa) -> None:
    """Um typo no JSON devolve acesso cheio (com warning), nunca um piloto morto."""
    escrever_mapa("{ isto nao e json")
    assert acesso.abas_do_usuario("x") == TODAS


def test_raiz_nao_objeto_e_fail_open(escrever_mapa) -> None:
    escrever_mapa(["mapa"])
    assert acesso.abas_do_usuario("x") == TODAS


# --- leitura do mapa ----------------------------------------------------------


def test_usuario_no_mapa_recebe_suas_abas(escrever_mapa) -> None:
    escrever_mapa({"ana": ["mapa", "viabilidade"]})
    assert acesso.abas_do_usuario("ana") == frozenset({"mapa", "viabilidade"})


def test_aba_desconhecida_e_descartada(escrever_mapa) -> None:
    """Valor de aba fora do vocabulario nao vira permissao fantasma."""
    escrever_mapa({"ana": ["mapa", "dominio", "EXECUTIVA"]})
    assert acesso.abas_do_usuario("ana") == frozenset({"mapa"})


def test_usuario_fora_do_mapa_cai_no_default(escrever_mapa) -> None:
    escrever_mapa({"ana": ["mapa"], "*": ["executiva"]})
    assert acesso.abas_do_usuario("novato") == frozenset({"executiva"})


def test_usuario_fora_do_mapa_sem_default_nao_tem_nada(escrever_mapa) -> None:
    escrever_mapa({"ana": ["mapa"]})
    assert acesso.abas_do_usuario("novato") == frozenset()
    assert acesso.abas_do_usuario(None) == frozenset()


def test_chave_de_comentario_e_ignorada(escrever_mapa) -> None:
    escrever_mapa({"_comentario": ["isto", "nao", "e", "usuario"], "ana": ["mapa"]})
    assert acesso.abas_do_usuario("_comentario") == frozenset()


def test_edicao_do_arquivo_vale_sem_restart(escrever_mapa) -> None:
    """O cache e' por mtime: editar o JSON em producao muda a resposta seguinte."""
    p = escrever_mapa({"ana": ["mapa"]})
    assert acesso.abas_do_usuario("ana") == frozenset({"mapa"})

    p.write_text(json.dumps({"ana": ["executiva"]}), encoding="utf-8")
    # mtime pode ter a mesma resolucao do relogio; forca um valor estritamente maior.
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    assert acesso.abas_do_usuario("ana") == frozenset({"executiva"})


# --- regras rota -> abas -------------------------------------------------------


def test_regras_por_prefixo() -> None:
    assert acesso.abas_necessarias("/api/rede/carteira") == frozenset({"executiva"})
    assert acesso.abas_necessarias("/api/rede/unidade/u1.pdf") == frozenset({"executiva"})
    assert acesso.abas_necessarias("/api/executiva/SP") == frozenset({"executiva"})
    assert acesso.abas_necessarias("/api/viabilidade") == frozenset({"mapa", "viabilidade"})
    assert acesso.abas_necessarias("/api/relatorio/pontual") == frozenset({"mapa", "viabilidade"})
    assert acesso.abas_necessarias("/api/simulador/xlsx") == frozenset({"viabilidade"})
    # `/api/municipios/` NAO pode cair na regra de `/api/municipio/` por acidente de
    # prefixo — as duas existem de proposito e apontam para o mesmo conjunto.
    assert acesso.abas_necessarias("/api/municipios/SP") == frozenset({"mapa", "oportunidades"})
    assert acesso.abas_necessarias("/api/municipio/SP/Campinas") == frozenset(
        {"mapa", "oportunidades"}
    )
    # Rotas livres nao tem regra.
    for livre in sorted(acesso.ROTAS_LIVRES):
        assert acesso.abas_necessarias(livre) is None, livre


def test_toda_rota_do_app_tem_regra_ou_e_livre_declarada() -> None:
    """Rota /api/* nova SEM regra e fora de ROTAS_LIVRES = decisao que faltou tomar.

    E' o guardrail contra o esquecimento classico: alguem cria a rota, a SPA esconde a
    aba, e o dado continua servido a qualquer usuario logado que chame a URL na mao.
    """
    rotas_api = {r.path for r in pilot_app.app.routes if getattr(r, "path", "").startswith("/api/")}
    assert rotas_api, "o app deveria registrar rotas /api/*"
    sem_decisao = {
        p for p in rotas_api if acesso.abas_necessarias(p) is None and p not in acesso.ROTAS_LIVRES
    }
    assert not sem_decisao, (
        f"rotas sem regra de acesso nem declaracao de rota livre: {sorted(sem_decisao)} "
        "— adicione em REGRAS_DE_ACESSO ou, se for deliberadamente livre, em ROTAS_LIVRES "
        "(web/server/acesso.py)"
    )


# --- motivo_bloqueio (o que o middleware devolve) ------------------------------


def test_bloqueia_rota_de_aba_que_o_usuario_nao_tem(escrever_mapa) -> None:
    escrever_mapa({"ana": ["mapa"]})
    detalhe = acesso.motivo_bloqueio("/api/rede/carteira", "ana")
    assert detalhe is not None and "não tem acesso" in detalhe


def test_permite_rota_de_aba_que_o_usuario_tem(escrever_mapa) -> None:
    escrever_mapa({"ana": ["executiva"]})
    assert acesso.motivo_bloqueio("/api/rede/carteira", "ana") is None


def test_basta_uma_das_abas_da_regra(escrever_mapa) -> None:
    """/api/viabilidade aceita mapa OU viabilidade (BlocoViabilidadePonto)."""
    escrever_mapa({"ana": ["mapa"]})
    assert acesso.motivo_bloqueio("/api/viabilidade", "ana") is None


def test_rota_livre_passa_mesmo_sem_aba_nenhuma(escrever_mapa) -> None:
    escrever_mapa({"ana": []})
    assert acesso.motivo_bloqueio("/api/health", "ana") is None
    assert acesso.motivo_bloqueio("/api/me", "ana") is None
    # E o SPA em si (fora de /api) nunca e' barrado — quem recorta e' a propria tela.
    assert acesso.motivo_bloqueio("/", "ana") is None


def test_header_ausente_com_controle_ativo_bloqueia(escrever_mapa) -> None:
    """Sem Remote-User (chamada por fora do Caddy) nao ha usuario -> sem abas."""
    escrever_mapa({"ana": ["mapa"]})
    assert acesso.motivo_bloqueio("/api/uf/SP", None) is not None


# --- /api/me -------------------------------------------------------------------


def test_me_sem_header_devolve_anonimo_e_fail_open() -> None:
    """Chamada direta (suite sem TestClient): o default do Header nao vira usuario."""
    acesso._cache = None
    os.environ.pop("MOTOR_ACESSO_ABAS_PATH", None)
    payload = pilot_app.me()
    assert payload["usuario"] is None
    assert isinstance(payload["abas"], list)


def test_me_com_usuario_lista_as_abas_do_mapa(escrever_mapa) -> None:
    escrever_mapa({"rodrigo_oliveira": ["mapa", "oportunidades", "viabilidade"]})
    payload = pilot_app.me(remote_user="rodrigo_oliveira")
    assert payload["usuario"] == "rodrigo_oliveira"
    assert payload["abas"] == ["mapa", "oportunidades", "viabilidade"]
