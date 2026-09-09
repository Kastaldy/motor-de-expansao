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
    # Curinga so' concede aba NAO-sensivel (pentest Onda B #14); usa "mapa" no default.
    escrever_mapa({"ana": ["executiva"], "*": ["mapa"]})
    assert acesso.abas_do_usuario("novato") == frozenset({"mapa"})


def test_curinga_nao_concede_abas_sensiveis(escrever_mapa) -> None:
    """Pentest Onda B #14: o curinga "*" NUNCA libera aba sensivel.

    Um typo `{"*": ["executiva"]}` liberaria financeiro/PII/escrita a TODO autenticado.
    Sensiveis (executiva/imobiliaria/viabilidade) exigem concessao NOMINAL no JSON; o
    curinga so' carrega as nao-sensiveis (espelha o fail-closed).
    """
    escrever_mapa({"ana": ["executiva"], "*": ["executiva", "imobiliaria", "mapa"]})
    # novato herda so' a nao-sensivel do curinga; sensiveis somem.
    assert acesso.abas_do_usuario("novato") == frozenset({"mapa"})
    # concessao NOMINAL segue intacta.
    assert acesso.abas_do_usuario("ana") == frozenset({"executiva"})


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


def test_ciencia_confidencialidade_existe_e_e_livre() -> None:
    """O OK do pop-up de confidencialidade vira linha da trilha via POST proprio.

    Livre de proposito: TODO usuario autenticado ve o pop-up — restringir por aba
    deixaria usuario sem aba nenhuma fora do registro de ciencia (2026-08-19)."""
    assert "/api/ciencia-confidencialidade" in acesso.ROTAS_LIVRES
    rotas_api = {r.path for r in pilot_app.app.routes if getattr(r, "path", "").startswith("/api/")}
    assert "/api/ciencia-confidencialidade" in rotas_api


def test_toda_rota_do_app_tem_regra_ou_e_livre_declarada() -> None:
    """Rota /api/* nova SEM regra e fora de ROTAS_LIVRES = decisao que faltou tomar.

    E' o guardrail contra o esquecimento classico: alguem cria a rota, a SPA esconde a
    aba, e o dado continua servido a qualquer usuario logado que chame a URL na mao.
    """
    rotas_api = {r.path for r in pilot_app.app.routes if getattr(r, "path", "").startswith("/api/")}
    assert rotas_api, "o app deveria registrar rotas /api/*"
    sem_decisao = {
        p
        for p in rotas_api
        if acesso.abas_necessarias(p) is None
        and p not in acesso.ROTAS_LIVRES
        # Painel de acessos (emenda DEC-027): controle PROPRIO, mais forte que o
        # de abas — allowlist de env checada no middleware (bloqueio_acessos).
        and not p.startswith(acesso.PREFIXO_ROTAS_ACESSOS)
    }
    assert not sem_decisao, (
        f"rotas sem regra de acesso nem declaracao de rota livre: {sorted(sem_decisao)} "
        "— adicione em REGRAS_DE_ACESSO ou, se for deliberadamente livre, em ROTAS_LIVRES "
        "(web/server/acesso.py)"
    )


def test_toda_rota_do_app_tem_superficie_ou_exige_malha_ou_e_livre() -> None:
    """A MESMA garantia acima, para o gate de PAIS (Bloco C).

    Rota nova em `REGRAS_DE_ACESSO` sem entrada em `SUPERFICIE_DA_ROTA` (nem em
    `ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL`) passaria despercebida em qualquer instancia
    que nao declare a superficie dela — o mesmo esquecimento classico, um nivel acima.
    """
    rotas_api = {r.path for r in pilot_app.app.routes if getattr(r, "path", "").startswith("/api/")}
    sem_decisao = {
        p
        for p in rotas_api
        if acesso.superficie_necessaria(p) is None
        and not acesso.rota_exige_malha_municipal(p)
        and p not in acesso.ROTAS_LIVRES
        and not p.startswith(acesso.PREFIXO_ROTAS_ACESSOS)
    }
    assert not sem_decisao, (
        f"rotas sem gate de pais nem declaracao de rota livre: {sorted(sem_decisao)} — "
        "adicione em SUPERFICIE_DA_ROTA, ROTAS_QUE_EXIGEM_MALHA_MUNICIPAL ou, se for "
        "deliberadamente livre, em ROTAS_LIVRES (web/server/acesso.py)"
    )


def test_brasil_e_inerte_sob_o_gate_de_pais_para_TODA_rota_real() -> None:
    """A garantia mais forte possivel: nao contra a tabela declarada, contra as rotas
    que o `FastAPI` REGISTROU de fato. Se um dia uma rota nascer com prefixo que bate
    em `SUPERFICIE_DA_ROTA` mas o Brasil nao tiver aquela superficie, e' aqui que
    acende — antes de qualquer instancia real notar."""
    rotas_api = {r.path for r in pilot_app.app.routes if getattr(r, "path", "").startswith("/api/")}
    bloqueadas = {p: acesso.motivo_bloqueio_pais(p, pilot_app.PERFIL) for p in rotas_api}
    bloqueadas = {p: d for p, d in bloqueadas.items() if d is not None}
    assert not bloqueadas, f"o gate de pais bloqueou o Brasil: {bloqueadas}"


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


def test_me_nao_concede_aba_que_a_INSTANCIA_nao_oferece(
    escrever_mapa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bloco C: o cadastro de abas e' arquivo OPERACIONAL, separado do perfil — nada
    o impede de conceder "oportunidades" a um usuario argentino por copia-e-cola do
    cadastro brasileiro. Sem a interseccao, a SPA mostraria um card cujo clique
    morreria em 404 no gate de pais; com ela, o card simplesmente nao aparece.
    """
    from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil

    perfil_ar = carregar_perfil(PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json")
    monkeypatch.setattr(pilot_app, "PERFIL", perfil_ar)
    # Cadastro concede as CINCO abas — como se fosse copiado do Brasil por engano.
    escrever_mapa({"ana": ["mapa", "oportunidades", "imobiliaria", "executiva", "viabilidade"]})
    payload = pilot_app.me(remote_user="ana")
    # So' o que a Argentina de fato oferece (perfil.superficies = mapa, viabilidade).
    assert payload["abas"] == ["mapa", "viabilidade"]


# --- fail-CLOSED em producao (BLK-SEC-05) ------------------------------------
# Quando o controle CAI (arquivo ausente/typo/mount sumiu), producao NEGA as abas
# sensiveis (financeiro/PII/escrita); dev preserva o fail-open historico.
_NAO_EXISTE = str(Path("Z:/nao/existe/acesso_abas.json"))
_NAO_SENSIVEIS = acesso.ABAS_VALIDAS - acesso.ABAS_SENSIVEIS


def _forcar_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    acesso._cache = None
    acesso._fail_closed_logado = False


def test_prod_sem_arquivo_nega_abas_sensiveis(monkeypatch: pytest.MonkeyPatch) -> None:
    _forcar_prod(monkeypatch)
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", _NAO_EXISTE)
    abas = acesso.abas_do_usuario("qualquer")
    assert abas == _NAO_SENSIVEIS
    assert "executiva" not in abas and "viabilidade" not in abas
    assert "mapa" in abas  # nao-sensivel segue liberada


def test_prod_json_invalido_nega_abas_sensiveis(escrever_mapa, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    acesso._fail_closed_logado = False
    escrever_mapa("{ isto nao e json valido")
    assert acesso.abas_do_usuario("x") == _NAO_SENSIVEIS


def test_prod_bloqueia_rota_sensivel_e_permite_analitica(monkeypatch: pytest.MonkeyPatch) -> None:
    _forcar_prod(monkeypatch)
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", _NAO_EXISTE)
    # Sensivel (financeiro da rede + escrita + simulador) -> BLOQUEADO.
    assert acesso.motivo_bloqueio("/api/rede/carteira", "alguem") is not None
    assert acesso.motivo_bloqueio("/api/executiva/SP", "alguem") is not None
    assert acesso.motivo_bloqueio("/api/simulador/xlsx", "alguem") is not None
    # Analitico (mapa/oportunidades) -> LIBERADO.
    assert acesso.motivo_bloqueio("/api/ponto", "alguem") is None
    assert acesso.motivo_bloqueio("/api/estados", "alguem") is None


def test_cadastro_dir_ativa_fail_closed_sem_override(monkeypatch: pytest.MonkeyPatch) -> None:
    # Sem override, MOTOR_CADASTRO_DIR setado (sinal de prod pelo compose) ativa o fail-closed.
    monkeypatch.delenv("MOTOR_ACESSO_FAIL_CLOSED", raising=False)
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", str(Path("Z:/prod/cadastro")))
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", _NAO_EXISTE)
    acesso._cache = None
    acesso._fail_closed_logado = False
    assert acesso.abas_do_usuario("x") == _NAO_SENSIVEIS


def test_dev_sem_sinais_e_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    # Carve-out do dev: sem FAIL_CLOSED e sem CADASTRO_DIR -> fail-open (todas as abas).
    monkeypatch.delenv("MOTOR_ACESSO_FAIL_CLOSED", raising=False)
    monkeypatch.delenv("MOTOR_CADASTRO_DIR", raising=False)
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", _NAO_EXISTE)
    acesso._cache = None
    assert acesso.abas_do_usuario("x") == acesso.ABAS_VALIDAS


def test_prod_com_mapa_valido_respeita_o_mapa(escrever_mapa, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail-closed so vale quando o controle CAI; com mapa valido, respeita o mapa.
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    escrever_mapa({"ana": ["executiva"]})
    assert acesso.abas_do_usuario("ana") == frozenset({"executiva"})


# --- Aba Acessos (emenda DEC-027): guard por allowlist de env -------------------
# Controle PROPRIO, mais forte que o de abas: sem curinga "*", sem fail-open, 404
# (nao 403) para quem nao pode — a existencia do painel nao e' anunciada.


def _com_allowlist(monkeypatch: pytest.MonkeyPatch, valor: str | None) -> None:
    if valor is None:
        monkeypatch.delenv(acesso.ENV_ADMIN_ACESSOS, raising=False)
    else:
        monkeypatch.setenv(acesso.ENV_ADMIN_ACESSOS, valor)


def test_sem_env_o_painel_esta_desligado_para_todos(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_allowlist(monkeypatch, None)
    assert acesso.bloqueio_acessos("/api/acessos/resumo", "felipe") is True
    _com_allowlist(monkeypatch, "   ")
    assert acesso.bloqueio_acessos("/api/acessos/resumo", "felipe") is True


def test_allowlist_libera_so_quem_esta_nela(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_allowlist(monkeypatch, "felipe, vinicius")
    assert acesso.bloqueio_acessos("/api/acessos/resumo", "felipe") is False
    assert acesso.bloqueio_acessos("/api/acessos/resumo", "vinicius") is False
    assert acesso.bloqueio_acessos("/api/acessos/resumo", "ana") is True
    assert acesso.bloqueio_acessos("/api/acessos/resumo", None) is True
    assert acesso.bloqueio_acessos("/api/acessos/resumo", "  ") is True


def test_comparacao_e_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Authelia normaliza usuario minusculo; a env nao pode falhar por caixa."""
    _com_allowlist(monkeypatch, "Felipe")
    assert acesso.bloqueio_acessos("/api/acessos/resumo", "felipe") is False
    assert acesso.pode_ver_acessos("FELIPE") is True


def test_rota_fora_do_painel_nunca_e_bloqueada_por_este_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _com_allowlist(monkeypatch, None)
    assert acesso.bloqueio_acessos("/api/ponto", "ana") is False
    assert acesso.bloqueio_acessos("/api/me", None) is False


def test_aba_acessos_nao_pode_vir_do_json_de_abas(escrever_mapa) -> None:
    """`acessos` fora de ABAS_VALIDAS: concedida no JSON (ate' pelo curinga), e'
    descartada como qualquer valor desconhecido — permissao fantasma impossivel."""
    assert acesso.ABA_ACESSOS not in acesso.ABAS_VALIDAS
    escrever_mapa({"ana": ["mapa", "acessos"], "*": ["acessos"]})
    assert acesso.abas_do_usuario("ana") == frozenset({"mapa"})
    assert acesso.abas_do_usuario("novato") == frozenset()


def test_me_lista_acessos_so_para_a_allowlist(
    escrever_mapa, monkeypatch: pytest.MonkeyPatch
) -> None:
    escrever_mapa({"felipe": ["mapa"], "ana": ["mapa"]})
    _com_allowlist(monkeypatch, "felipe")
    assert pilot_app.me(remote_user="felipe")["abas"] == ["acessos", "mapa"]
    assert pilot_app.me(remote_user="ana")["abas"] == ["mapa"]


def test_rotas_do_painel_devolvem_404_para_quem_nao_pode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException

    _com_allowlist(monkeypatch, "felipe")
    for chamada in (
        lambda u: pilot_app.acessos_resumo(remote_user=u),
        lambda u: pilot_app.acessos_usuario("alguem", remote_user=u),
        # Inventario diagnostico (pentest Onda B #8): mesma barreira das demais /acessos.
        lambda u: pilot_app.acessos_saude_artefatos(remote_user=u),
    ):
        with pytest.raises(HTTPException) as exc:
            chamada("ana")
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            chamada(None)
        assert exc.value.status_code == 404


def test_resumo_responde_para_quem_esta_na_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _com_allowlist(monkeypatch, "felipe")
    payload = pilot_app.acessos_resumo(remote_user="felipe")
    assert "serie" in payload and "usuarios" in payload and "saude" in payload


def test_saude_artefatos_responde_inventario_para_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pentest Onda B #8: o inventario (data_dir + caminhos + descricao) so' sai para
    a allowlist de admin — saiu do /api/health publico."""
    _com_allowlist(monkeypatch, "felipe")
    payload = pilot_app.acessos_saude_artefatos(remote_user="felipe")
    assert payload["status"] == "ok"
    assert "data_dir" in payload and "artefatos" in payload


def test_ficha_inexistente_devolve_404_mesmo_para_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException

    _com_allowlist(monkeypatch, "felipe")
    with pytest.raises(HTTPException) as exc:
        pilot_app.acessos_usuario("ninguem_com_esse_nome", remote_user="felipe")
    assert exc.value.status_code == 404


# --- o APP de verdade aplica o guard (anti falso-verde, revisao 2026-08-19) ------
# As funcoes puras acima poderiam existir sem ninguem chama-las; estes testes
# travam o registro do middleware, o comportamento dele, o startup do rollup e o
# vazamento de existencia via OpenAPI.

import asyncio  # noqa: E402


class _UrlFake:
    def __init__(self, caminho: str):
        self.path = caminho


class _CabecalhosFake(dict):
    def get(self, chave: str, default=None):  # type: ignore[override]
        for k, v in self.items():
            if k.lower() == str(chave).lower():
                return v
        return default


class _RequisicaoFake:
    def __init__(self, caminho: str, usuario: str | None = None):
        self.url = _UrlFake(caminho)
        self.headers = _CabecalhosFake(
            {"Remote-User": usuario} if usuario is not None else {}
        )


def _rodar_controle(caminho: str, usuario: str | None):
    chamado = {"handler": False}

    async def _proximo(_req):
        chamado["handler"] = True

        class _R:
            status_code = 200

        return _R()

    resposta = asyncio.run(
        pilot_app._controle_de_acesso_por_aba(_RequisicaoFake(caminho, usuario), _proximo)
    )
    return resposta, chamado["handler"]


def test_middleware_de_controle_esta_registrado_no_app() -> None:
    dispatches = [
        getattr(m, "kwargs", {}).get("dispatch") for m in pilot_app.app.user_middleware
    ]
    assert pilot_app._controle_de_acesso_por_aba in dispatches


def test_middleware_devolve_404_do_painel_sem_chamar_o_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _com_allowlist(monkeypatch, "felipe")
    resposta, handler_rodou = _rodar_controle("/api/acessos/resumo", "ana")
    assert resposta.status_code == 404 and handler_rodou is False
    resposta, handler_rodou = _rodar_controle("/api/acessos/resumo", None)
    assert resposta.status_code == 404 and handler_rodou is False


def test_middleware_deixa_o_admin_passar_ate_o_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _com_allowlist(monkeypatch, "felipe")
    resposta, handler_rodou = _rodar_controle("/api/acessos/resumo", "felipe")
    assert handler_rodou is True and resposta.status_code == 200


def test_rota_futura_sob_o_prefixo_ja_nasce_guardada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O guard vive no middleware por prefixo: rota nova /api/acessos/* nao depende
    de ninguem lembrar da dependencia por rota."""
    _com_allowlist(monkeypatch, "felipe")
    resposta, handler_rodou = _rodar_controle("/api/acessos/rota-que-nem-existe", "ana")
    assert resposta.status_code == 404 and handler_rodou is False


def test_openapi_nao_anuncia_o_painel() -> None:
    """/openapi.json e /docs sao livres para qualquer autenticado; os paths do
    painel ficam FORA do schema (include_in_schema=False), senao o 404 'nao
    anunciado' seria anulado pelos metadados (revisao adversarial 2026-08-19)."""
    pilot_app.app.openapi_schema = None  # limpa cache de schema de outros testes
    paths = pilot_app.app.openapi().get("paths", {})
    vazados = [p for p in paths if p.startswith("/api/acessos")]
    assert not vazados, f"rotas do painel anunciadas no OpenAPI: {vazados}"


def test_startup_consolida_o_rollup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O hook de startup existe, esta registrado e produz o rollup de verdade."""
    assert pilot_app._consolidar_rollup_de_uso in pilot_app.app.router.on_startup
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    from motor_expansao.dashboard import acesso_analytics as _aa

    trilha = tmp_path / "trilha"
    trilha.mkdir()
    # D-2 e' um dia BRT ja fechado em qualquer fuso; o de hoje nao consolidaria.
    dia = (_dt.now(_UTC).date() - _td(days=2)).isoformat()
    (trilha / f"acesso-{dia}.jsonl").write_text(
        _json.dumps({"quando": f"{dia}T12:00:00+00:00", "usuario": "ana", "rota": "/api/ponto"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MOTOR_ACESSO_LOG_DIR", str(trilha))
    pilot_app._consolidar_rollup_de_uso()
    assert _aa.caminho_rollup(trilha).exists()


# --- Aba imobiliaria (2026-08-24): dossie restrito, lista/pins seguem o mapa -----
# A camada de imoveis ganhou aba PROPRIA porque antes reusava o gate de
# `oportunidades` — nao dava para restringir os imoveis sem tirar o funil de expansao
# de quem o usa. O recorte fino e' entre as DUAS rotas de oportunidades: o DOSSIE (PDF
# do coletor, com contato de corretor) fica so' na aba nova; a LISTA agregada tambem
# alimenta os pins do Mapa Territorial, entao "mapa" a libera (decisao do Felipe).

_DOSSIE = "/api/oportunidades/im_x/dossie"
_LISTA = "/api/oportunidades"
_EVENTO = "/api/imobiliaria/evento/abrir-imovel"


def test_imobiliaria_e_aba_valida_e_sensivel() -> None:
    """Valida (pode ser concedida no JSON) e sensivel (cai no fail-closed de prod)."""
    assert "imobiliaria" in acesso.ABAS_VALIDAS
    assert "imobiliaria" in acesso.ABAS_SENSIVEIS


def test_regras_separam_dossie_de_lista() -> None:
    """O prefixo com barra vem ANTES no first-match: `/api/oportunidades/` (dossie)
    nao pode ser engolido pela regra mais curta da lista."""
    assert acesso.abas_necessarias(_DOSSIE) == frozenset({"imobiliaria"})
    assert acesso.abas_necessarias(_LISTA) == frozenset({"mapa", "imobiliaria"})
    assert acesso.abas_necessarias(_EVENTO) == frozenset({"mapa", "imobiliaria"})


def test_so_mapa_ve_a_lista_mas_nao_baixa_dossie(escrever_mapa) -> None:
    """Cerne da decisao: quem tem o Mapa Territorial ve os imoveis (pins e ficha do
    hexagono vem da lista agregada), mas o PDF com contato de corretor fica fora."""
    escrever_mapa({"ana": ["mapa"]})
    assert acesso.motivo_bloqueio(_LISTA, "ana") is None
    detalhe = acesso.motivo_bloqueio(_DOSSIE, "ana")
    assert detalhe is not None and "não tem acesso" in detalhe


def test_so_imobiliaria_passa_nas_duas(escrever_mapa) -> None:
    escrever_mapa({"ana": ["imobiliaria"]})
    assert acesso.motivo_bloqueio(_LISTA, "ana") is None
    assert acesso.motivo_bloqueio(_DOSSIE, "ana") is None


def test_sem_mapa_nem_imobiliaria_nada_passa(escrever_mapa) -> None:
    escrever_mapa({"ana": ["executiva", "viabilidade", "oportunidades"]})
    assert acesso.motivo_bloqueio(_LISTA, "ana") is not None
    assert acesso.motivo_bloqueio(_DOSSIE, "ana") is not None


def test_evento_de_imobiliaria_segue_o_gate_da_lista(escrever_mapa) -> None:
    """O pin do Mapa Territorial tambem abre ficha de imovel, entao o evento aceita
    "mapa"; quem nao tem nenhuma das duas nao consegue nem sujar a trilha."""
    escrever_mapa({"do_mapa": ["mapa"], "da_imob": ["imobiliaria"], "nenhuma": ["executiva"]})
    assert acesso.motivo_bloqueio(_EVENTO, "do_mapa") is None
    assert acesso.motivo_bloqueio(_EVENTO, "da_imob") is None
    assert acesso.motivo_bloqueio(_EVENTO, "nenhuma") is not None


def test_prod_com_controle_caido_nega_dossie_e_mantem_a_lista(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-closed (BLK-SEC-05) aplicado a decisao: com o JSON fora do ar ninguem
    baixa dossie, mas os pins do mapa continuam — quem perde `imobiliaria` no
    fail-closed ainda tem `mapa`, e a lista aceita as duas."""
    _forcar_prod(monkeypatch)
    monkeypatch.setenv("MOTOR_ACESSO_ABAS_PATH", _NAO_EXISTE)
    abas = acesso.abas_do_usuario("alguem")
    assert "imobiliaria" not in abas
    assert "mapa" in abas
    assert acesso.motivo_bloqueio(_DOSSIE, "alguem") is not None
    assert acesso.motivo_bloqueio(_LISTA, "alguem") is None
    assert acesso.motivo_bloqueio(_EVENTO, "alguem") is None


def test_rota_de_evento_existe_no_app_e_esta_coberta() -> None:
    """A rota nova nasce dentro do controle: aparece no app E casa com uma regra —
    e' o mesmo criterio que `test_toda_rota_do_app_tem_regra_ou_e_livre_declarada`
    aplica ao path TEMPLATE registrado pelo FastAPI."""
    rotas_api = {r.path for r in pilot_app.app.routes if getattr(r, "path", "").startswith("/api/")}
    template = "/api/imobiliaria/evento/{acao}"
    assert template in rotas_api
    assert acesso.abas_necessarias(template) == frozenset({"mapa", "imobiliaria"})
    assert template not in acesso.ROTAS_LIVRES


def test_acao_desconhecida_e_404_mesmo_para_quem_pode(escrever_mapa) -> None:
    """404 do VOCABULARIO, nao do gate: o usuario passa no controle de aba e ainda
    assim leva 404 — senao a trilha viraria lixo com acao inventada pelo front."""
    from fastapi import HTTPException

    escrever_mapa({"ana": ["imobiliaria"]})
    assert acesso.motivo_bloqueio("/api/imobiliaria/evento/inventada", "ana") is None
    with pytest.raises(HTTPException) as exc:
        pilot_app.api_imobiliaria_evento("inventada")
    assert exc.value.status_code == 404
    # E a acao do vocabulario responde normalmente.
    assert pilot_app.api_imobiliaria_evento("abrir-imovel") == {"ok": True}
