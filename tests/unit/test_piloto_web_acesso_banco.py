"""Gate de acesso pelo BANCO (F4.2) — a camada que substitui o mapa `usuario -> [abas]`.

Nenhum banco é tocado: a identidade é dublada. O que se prova aqui é a fronteira — quais
rotas exigem qual capacidade, o que o método HTTP muda, e como o gate degrada quando o
banco cai. As regras de segurança que o modelo por aba acumulou (fail-closed nas sensíveis,
o painel de acessos fora do mecanismo, first-match por prefixo) têm de sobreviver à troca:
cada uma delas é resposta a um achado de pentest ou a uma emenda de DEC.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402

from motor_expansao.db import rbac  # noqa: E402
from motor_expansao.db import sessoes as db_sessoes  # noqa: E402


@pytest.fixture(autouse=True)
def _sem_producao(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.delenv("MOTOR_CADASTRO_DIR", raising=False)
    monkeypatch.delenv("MOTOR_ACESSO_FAIL_CLOSED", raising=False)
    # Login proprio DESLIGADO por padrao: e' o estado de producao ate' o corte do P19, e um
    # `MOTOR_AUTENTICACAO_PROPRIA` exportado na maquina de quem roda mudaria os testes de senha.
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    yield


def _identidade(monkeypatch: pytest.MonkeyPatch, permissoes: set[str] | None) -> None:
    """Dubla `rbac.identidade`: `None` = usuário desconhecido/negado."""
    def falsa(_remote_user: object) -> rbac.Identidade | None:
        if permissoes is None:
            return None
        return rbac.Identidade(
            id_usuario=1,
            login="alguem",
            perfil="teste",
            permissoes=frozenset(permissoes),
            # DEC-081: campo obrigatorio. Este duble alimenta o gate de CAPACIDADE (e o
            # `/api/me`), nao o gate de PAIS -- o valor nao muda as assercoes aqui.
            paises=frozenset({"BR"}),
        )

    monkeypatch.setattr(rbac, "identidade", falsa)


# --------------------------------------------------------------------------------------
# O mapa rota -> capacidade
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "metodo", "esperada"),
    [
        ("/api/uf/SP", "GET", "territorio.explorar"),
        ("/api/estados", "GET", "territorio.ranking_nacional"),
        ("/api/ponto", "GET", "ponto.analisar"),
        ("/api/relatorio/pontual", "POST", "relatorio.pontual"),
        ("/api/simulador/xlsx", "GET", "viabilidade.simular"),
        ("/api/executiva/carteira", "GET", "rede.ver"),
        ("/api/acessos/resumo", "GET", "acesso.painel_ver"),
        ("/api/imobiliaria/evento/visita", "POST", "imovel.registrar_gesto"),
    ],
)
def test_cada_rota_exige_a_capacidade_certa(path: str, metodo: str, esperada: str) -> None:
    assert acesso.capacidade_necessaria(path, metodo) == esperada


def test_o_dossie_e_a_lista_sao_capacidades_DIFERENTES() -> None:
    """O recorte mais fino do sistema, e o motivo de a DEC-037 existir: a barra final separa
    o dossiê (com contato de corretor) da lista agregada, que alimenta os pins do Mapa.
    Modelar por aba apagava isso — e foi exatamente o problema que aquela decisão resolveu."""
    assert acesso.capacidade_necessaria("/api/oportunidades/42/dossie", "GET") == "imovel.dossie_ver"
    assert acesso.capacidade_necessaria("/api/oportunidades", "GET") == "imovel.listar"


def test_o_metodo_separa_ver_a_carteira_de_editar_o_cadastro() -> None:
    """O ganho que o modelo por aba NAO expressa. Com `/api/rede/` liberando os dois pela
    mesma chave, era impossível ter quem lê sem ter quem escreve."""
    assert acesso.capacidade_necessaria("/api/rede/cadastro/123", "GET") == "rede.ver"
    assert acesso.capacidade_necessaria("/api/rede/cadastro/123", "PUT") == "rede.cadastro_editar"
    assert acesso.capacidade_necessaria("/api/rede/carteira", "GET") == "rede.ver"


def test_rota_sem_regra_nao_e_controlada() -> None:
    """Health, catálogos e `/api/me` seguem livres — quem diz à SPA o que esconder não pode
    depender de permissão para responder."""
    for livre in ("/api/health", "/api/ufs", "/api/me", "/api/metodologia"):
        assert acesso.capacidade_necessaria(livre, "GET") is None


def _capacidades_semeadas() -> set[str]:
    """As chaves que as migrations realmente inserem em `permissoes`.

    LIDAS dos arquivos, e não copiadas para cá: a lista à mão já ficou para trás uma vez —
    a 015 acrescentou `acesso.usuario_gerir` e o teste acusou uma capacidade "sem seed" que
    o seed tinha. Derivar mantém os dois lados casados sozinhos.
    """
    import re
    from pathlib import Path

    migracoes = Path(__file__).resolve().parents[2] / "src/motor_expansao/db/migracoes"
    chaves: set[str] = set()
    for sql in sorted(migracoes.glob("*.sql")):
        texto = sql.read_text(encoding="utf-8")
        for bloco in re.findall(r"INSERT INTO permissoes\b.*?;", texto, re.DOTALL):
            chaves.update(re.findall(r"\(\s*'([a-z][a-z_]*\.[a-z_]+)'\s*,", bloco))
    return chaves


def test_toda_capacidade_do_mapa_existe_no_seed() -> None:
    """Se o mapa citar uma capacidade que nenhuma migration cria, a rota fica INALCANÇÁVEL
    para todos — e em silêncio, porque ninguém teria a chave."""
    do_seed = _capacidades_semeadas()
    assert do_seed, "nenhuma capacidade lida das migrations — o parser quebrou"
    do_mapa = {capacidade for _, _, capacidade in acesso.REGRAS_POR_CAPACIDADE}
    assert do_mapa <= do_seed, f"capacidades sem seed: {sorted(do_mapa - do_seed)}"
    assert acesso.CAPACIDADES_SENSIVEIS <= do_seed


def test_gerir_usuario_e_capacidade_propria_e_vem_antes_da_generica() -> None:
    """Ver o painel é leitura; mudar quem entra é escrita (D25).

    Duas coisas travadas aqui. A capacidade das ESCRITAS não pode ser `acesso.painel_ver` —
    senão uma chave de leitura autoriza desativar gente. E a ordem importa: o mapa casa por
    prefixo com `first-match`, então a regra específica tem de vir antes de `/api/acessos/`.
    """
    assert acesso.capacidade_necessaria("/api/acessos/usuarios", "GET") == "acesso.painel_ver"
    assert acesso.capacidade_necessaria("/api/acessos/usuarios/7", "PATCH") == (
        "acesso.usuario_gerir"
    )
    # POST tambem, desde a D26 (criar usuario). A regra ja' listava o metodo antes de a
    # rota existir, mas NENHUM teste fixava isso — uma reordenacao da tupla passaria
    # calada, deixando CRIAR gente sob a chave de LEITURA do painel.
    assert acesso.capacidade_necessaria("/api/acessos/usuarios", "POST") == (
        "acesso.usuario_gerir"
    )
    assert acesso.capacidade_necessaria("/api/acessos/resumo", "GET") == "acesso.painel_ver"
    # Mudar quem entra é tão sensível quanto o financeiro da rede: fail-closed nega em produção.
    assert "acesso.usuario_gerir" in acesso.CAPACIDADES_SENSIVEIS


# --------------------------------------------------------------------------------------
# A decisão
# --------------------------------------------------------------------------------------


def test_quem_tem_a_capacidade_passa(monkeypatch: pytest.MonkeyPatch) -> None:
    _identidade(monkeypatch, {"territorio.explorar"})
    assert acesso.motivo_bloqueio_por_banco("/api/uf/SP", "GET", "alguem") is None


def test_quem_nao_tem_e_barrado(monkeypatch: pytest.MonkeyPatch) -> None:
    _identidade(monkeypatch, {"territorio.explorar"})
    detalhe = acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "alguem")
    assert detalhe is not None and "não tem acesso" in detalhe


def test_usuario_desconhecido_e_barrado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deny-by-default: autenticado no Authelia não é autorizado no piloto."""
    _identidade(monkeypatch, None)
    assert acesso.motivo_bloqueio_por_banco("/api/uf/SP", "GET", "fantasma") is not None


def test_ler_a_carteira_nao_da_direito_de_editar(monkeypatch: pytest.MonkeyPatch) -> None:
    """A separação só vale se o gate olhar o método — este teste é o que a prova."""
    _identidade(monkeypatch, {"rede.ver"})
    assert acesso.motivo_bloqueio_por_banco("/api/rede/cadastro/1", "GET", "x") is None
    assert acesso.motivo_bloqueio_por_banco("/api/rede/cadastro/1", "PUT", "x") is not None


# --------------------------------------------------------------------------------------
# Degradação — as regras que não podem se perder na troca
# --------------------------------------------------------------------------------------


def test_banco_fora_em_producao_nega_so_as_sensiveis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mesma política do JSON (BLK-SEC-05): um incidente de infraestrutura não pode trancar
    o piloto inteiro, mas também não pode liberar financeiro, PII e escrita."""
    from motor_expansao import db

    def explode(_remote_user: object) -> Any:
        raise db.BancoIndisponivel("connection refused")

    monkeypatch.setattr(rbac, "identidade", explode)
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")  # sinal de produção

    assert acesso.motivo_bloqueio_por_banco("/api/uf/SP", "GET", "x") is None
    assert acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "x") is not None
    assert acesso.motivo_bloqueio_por_banco("/api/oportunidades/1/dossie", "GET", "x") is not None


def test_banco_fora_em_dev_e_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-open histórico em dev, para não atrapalhar quem desenvolve — igual ao JSON."""
    from motor_expansao import db

    def explode(_remote_user: object) -> Any:
        raise db.BancoIndisponivel("connection refused")

    monkeypatch.setattr(rbac, "identidade", explode)
    assert acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "x") is None


def test_o_painel_de_acessos_continua_fora_do_mecanismo() -> None:
    """Emenda da DEC-027: allowlist de env, 404 em vez de 403, e NUNCA concedível pelo
    mecanismo de permissões. O middleware chama `bloqueio_acessos` ANTES e por cima — se um
    dia a capacidade `acesso.painel_ver` bastasse, a existência do painel seria anunciada."""
    assert acesso.bloqueio_acessos("/api/acessos/resumo", "quem_quer_que_seja") is True
    assert "acessos" not in acesso.ABAS_VALIDAS


def test_o_mecanismo_de_abas_continua_intacto() -> None:
    """A troca é por env, e é reversível: sem `MOTOR_DATABASE_URL`, nada muda. As regras
    antigas seguem no módulo, e o middleware escolhe entre os dois caminhos."""
    assert acesso.REGRAS_DE_ACESSO
    assert acesso.abas_necessarias("/api/rede/") == frozenset({"executiva"})


def test_toda_rota_controlada_por_aba_tem_capacidade_correspondente() -> None:
    """O teste que o número mágico não fazia.

    Enquanto os dois mecanismos coexistem, uma rota nova entra primeiro no modelo por aba
    (é lá que o `test_piloto_web_acesso` obriga). Se ela não ganhar capacidade aqui, fica
    SEM CONTROLE com o banco no comando -- passa livre, em silêncio, para quem quer que
    seja. Foi o que aconteceu na sincronia com a main de 01/09, que trouxe `/api/hexagonos`,
    `/api/foto-concorrente/` e `/api/pin-concorrente/`: contar regras pegou o sintoma pelo
    número; isto pega a causa, e continua pegando na próxima vez.
    """
    sem_capacidade = [
        prefixo
        for prefixo, _abas in acesso.REGRAS_DE_ACESSO
        if acesso.capacidade_necessaria(prefixo, "GET") is None
    ]
    assert not sem_capacidade, (
        f"rotas controladas por aba e SEM capacidade no RBAC: {sem_capacidade}. "
        "Acrescente-as a REGRAS_POR_CAPACIDADE e a migration de seed correspondente."
    )


# --------------------------------------------------------------------------------------
# /api/me — a interface tem de contar a mesma história que o gate
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("perfil", "capacidades", "abas_esperadas"),
    [
        (
            "expansao",
            {
                "territorio.explorar", "territorio.ranking_nacional", "ponto.analisar",
                "relatorio.comparacao", "relatorio.municipal", "relatorio.pontual",
                "viabilidade.calcular", "viabilidade.simular", "imovel.listar",
                "imovel.dossie_ver", "imovel.registrar_gesto",
            },
            {"mapa", "oportunidades", "imobiliaria", "viabilidade"},
        ),
        ("consultoria", {"rede.ver", "rede.cadastro_editar"}, {"executiva"}),
    ],
)
def test_as_abas_derivadas_reproduzem_os_perfis_do_acesso_abas_json(
    monkeypatch: pytest.MonkeyPatch,
    perfil: str,
    capacidades: set[str],
    abas_esperadas: set[str],
) -> None:
    """A prova de que a migração não mudou o que cada pessoa vê: as abas derivadas das
    capacidades da D22 batem com as que o `acesso_abas.json` da VPS concedia."""
    _identidade(monkeypatch, capacidades)
    assert set(acesso.abas_do_usuario_por_banco("alguem")) == abas_esperadas


def test_usuario_desconhecido_nao_ve_aba_nenhuma(monkeypatch: pytest.MonkeyPatch) -> None:
    _identidade(monkeypatch, None)
    assert acesso.abas_do_usuario_por_banco("fantasma") == frozenset()


def test_o_painel_de_acessos_nao_sai_do_rbac(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mesmo quem tem `acesso.painel_ver` no banco não recebe a aba por aqui: ela vem da
    allowlist de env, e a rota a soma depois. As duas camadas são independentes (DEC-027) —
    o banco governa a ROTA, a env decide se o painel é anunciado."""
    _identidade(monkeypatch, {"rede.ver", "acesso.painel_ver"})
    assert acesso.ABA_ACESSOS not in acesso.abas_do_usuario_por_banco("growth")


def test_toda_aba_valida_tem_capacidade_que_a_sustenta() -> None:
    """Aba sem capacidade mapeada nunca apareceria para ninguém — some da interface em
    silêncio, sem que nada falhe."""
    assert set(acesso.CAPACIDADE_QUE_SUSTENTA_A_ABA) == set(acesso.ABAS_VALIDAS)


def test_banco_fora_em_producao_esconde_as_abas_sensiveis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mesma degradação do gate: a interface não pode oferecer o que o middleware nega."""
    from motor_expansao import db

    def explode(_remote_user: object) -> Any:
        raise db.BancoIndisponivel("connection refused")

    monkeypatch.setattr(rbac, "identidade", explode)
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")
    abas = acesso.abas_do_usuario_por_banco("x")
    assert abas == acesso.ABAS_VALIDAS - acesso.ABAS_SENSIVEIS


# --------------------------------------------------------------------------------------
# O painel na máquina de quem desenvolve
# --------------------------------------------------------------------------------------


def test_painel_alcancavel_com_identidade_de_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem Authelia local não há `Remote-User`, e a allowlist não via a identidade de dev.

    O RBAC já honrava o `MOTOR_DEV_USUARIO` (as abas apareciam), mas a allowlist não —
    então as duas camadas liam a MESMA pessoa de fontes diferentes e o painel devolvia
    404 na própria máquina, incluindo a tela de administração de usuários.
    """
    from motor_expansao.db import rbac

    monkeypatch.delenv(rbac.ENV_SINAL_PRODUCAO, raising=False)
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius.teste")
    monkeypatch.setenv(acesso.ENV_ADMIN_ACESSOS, "vinicius.teste")
    assert acesso.pode_ver_acessos(None) is True


def test_identidade_de_dev_nao_vale_em_producao(monkeypatch: pytest.MonkeyPatch) -> None:
    """O sinal de produção manda: com ele, a env de dev é ignorada e sobra o header."""
    from motor_expansao.db import rbac

    monkeypatch.setenv(rbac.ENV_SINAL_PRODUCAO, "/app/cadastro")
    monkeypatch.delenv(rbac.ENV_DEV_IDENTIDADE, raising=False)
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius.teste")
    monkeypatch.setenv(acesso.ENV_ADMIN_ACESSOS, "vinicius.teste")
    assert acesso.pode_ver_acessos(None) is False


def test_header_sempre_vence_a_env_de_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """Havendo header, ele decide — a env nunca sobrescreve quem o Authelia autenticou."""
    from motor_expansao.db import rbac

    monkeypatch.delenv(rbac.ENV_SINAL_PRODUCAO, raising=False)
    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius.teste")
    monkeypatch.setenv(acesso.ENV_ADMIN_ACESSOS, "vinicius.teste")
    assert acesso.pode_ver_acessos("outra_pessoa") is False


# --------------------------------------------------------------------------------------
# O teto da INSTANCIA vale tambem quando as abas vem do banco
# --------------------------------------------------------------------------------------


def test_me_pelo_banco_tambem_respeita_o_teto_da_instancia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Espelho, no ramo do RBAC, do teste que a main escreveu para o ramo do JSON.

    O `test_me_nao_concede_aba_que_a_INSTANCIA_nao_oferece` (test_piloto_web_acesso.py)
    guarda a interseccao com `PERFIL.superficies` — mas roda SEM `MOTOR_DATABASE_URL`,
    entao cai no ramo do `acesso_abas.json` e passaria verde mesmo que o ramo do banco
    perdesse a interseccao. Era o ponto cego exato do merge de 09/09: o `me()` tem DUAS
    fontes de aba, e so' uma delas estava coberta.

    O RBAC do banco NAO tem eixo de pais — `territorio.ranking_nacional` e' a mesma
    capacidade no Brasil e na Argentina. Quem decide o que a instancia serve e' o perfil.
    """
    # `app` entra aqui dentro de proposito: este arquivo testa o `acesso` em isolamento, e
    # importa-lo no topo puxaria a arvore inteira do FastAPI para todos os casos.
    import app as pilot_app

    from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil

    perfil_ar = carregar_perfil(PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json")
    monkeypatch.setattr(pilot_app, "PERFIL", perfil_ar)
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    _identidade(
        monkeypatch,
        {"territorio.explorar", "territorio.ranking_nacional", "viabilidade.simular"},
    )

    payload = pilot_app.me(remote_user="ana")

    # `oportunidades` cai: a Argentina nao a oferece (`superficies` = mapa, viabilidade).
    assert payload["abas"] == ["mapa", "viabilidade"]


def test_a_tela_nao_oferece_o_que_o_gate_de_pais_nega(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Os dois lados tem de contar a MESMA historia sobre a mesma pessoa.

    Sem a interseccao, o `/api/me` anunciaria `oportunidades`, a SPA desenharia o card, e
    o clique morreria em 404 no `motivo_bloqueio_pais`. Aqui se afirma a concordancia, e
    nao so' o valor: a rota que aquela aba serviria e' justamente a que o gate nega.
    """
    import app as pilot_app

    from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil

    perfil_ar = carregar_perfil(PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json")
    monkeypatch.setattr(pilot_app, "PERFIL", perfil_ar)
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    _identidade(
        monkeypatch,
        {"territorio.explorar", "territorio.ranking_nacional", "viabilidade.simular"},
    )

    abas = set(pilot_app.me(remote_user="ana")["abas"])
    assert acesso.motivo_bloqueio_pais("/api/estados", perfil_ar) is not None
    assert "oportunidades" not in abas


# --------------------------------------------------------------------------------------
# O estado da senha no payload de /api/me (D26, 11/09)
# --------------------------------------------------------------------------------------


def test_me_leva_o_estado_da_senha_quando_o_banco_responde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem este campo a tela nao tem como saber a quem OFERECER a troca.

    Ate' 11/09 o payload trazia usuario, abas e perfil -- e nada dizia que a pessoa ainda
    esta' na senha inicial COMPARTILHADA. A coluna `deve_trocar_senha_usuario` da migration
    016 existia desde entao sem nenhum leitor.
    """
    import app as pilot_app

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(acesso, "abas_do_usuario_por_banco", lambda _u: ["mapa"])
    monkeypatch.setattr(
        pilot_app, "_estado_da_minha_senha", lambda _u: {"deve_trocar": True, "propria": False}
    )
    payload = pilot_app.me(remote_user="ana")
    assert payload["senha"] == {"deve_trocar": True, "propria": False}


def test_me_OMITE_a_chave_quando_nao_da_para_saber(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUSENTE, e nao `false`. A distincao e' o contrato inteiro deste campo.

    `false` significaria "nao precisa trocar" e esconderia a oferta de todo mundo no dia em
    que o banco piscasse. Ausente significa "nao sei", e o front (`estadoDaSenhaDoPayload`)
    devolve `null` -- que nao oferece nada, mas tambem nao afirma nada.
    """
    import app as pilot_app

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(acesso, "abas_do_usuario_por_banco", lambda _u: ["mapa"])
    monkeypatch.setattr(pilot_app, "_estado_da_minha_senha", lambda _u: None)
    assert "senha" not in pilot_app.me(remote_user="ana")


def test_o_estado_da_senha_NUNCA_derruba_o_me(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/api/me` e' a PRIMEIRA chamada da SPA: dela saem as abas e o perfil do pais.

    Deixar uma consulta acessoria derrubar essa rota apagaria o piloto inteiro por causa de
    um campo que so' serve para oferecer a troca de senha. O `except Exception` do helper
    cobre tres casos com a mesma resposta: banco fora, banco nao configurado, e banco que
    respondeu mas ainda nao tem a coluna da 016.
    """
    import app as pilot_app

    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(acesso, "abas_do_usuario_por_banco", lambda _u: ["mapa"])
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")

    for explosao in (
        RuntimeError("banco fora"),
        Exception('column "deve_trocar_senha_usuario" does not exist'),
    ):

        def _explode(_login: str, _erro: Exception = explosao) -> None:
            raise _erro

        monkeypatch.setattr(db_usuarios, "estado_da_senha", _explode)
        payload = pilot_app.me(remote_user="ana")
        assert "senha" not in payload
        assert payload["abas"] == ["mapa"], "as abas tem de sair intactas"


def test_sem_banco_no_comando_nem_consulta_o_estado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma ida ao banco a menos por abertura de app, no ramo em que ela seria inutil.

    O duble REGISTRA a chamada em vez de levantar, e a diferenca decide se este teste vale
    alguma coisa. Ate' 16/09 ele levantava `AssertionError` -- que e' subclasse de `Exception`
    e portanto cai no `except Exception` do `_estado_da_minha_senha`, que existe para a
    consulta acessoria nunca derrubar o `/api/me`. Com a guarda removida, a chamada
    aconteceria, a excecao seria engolida, o helper devolveria `None` e a chave `senha`
    continuaria ausente: o teste passava exatamente no caso que ele deveria denunciar.
    """
    import app as pilot_app

    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: False)
    monkeypatch.setattr(acesso, "abas_do_usuario", lambda _u: ["mapa"])
    # Chave LIGADA de proposito: o que este teste isola e' a guarda do banco, e com a chave
    # desligada a outra guarda pararia a consulta antes -- o teste passaria pela razao errada.
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")

    consultas: list[str] = []
    monkeypatch.setattr(db_usuarios, "estado_da_senha", lambda login: consultas.append(login))

    assert "senha" not in pilot_app.me(remote_user="ana")
    assert consultas == [], "consultou o banco com `banco_no_comando()` falso"


def test_em_DEV_o_estado_da_senha_sai_sem_Remote_User(monkeypatch: pytest.MonkeyPatch) -> None:
    """O defeito que manteve a tela invisivel por tres dias (14/09).

    Na maquina de quem desenvolve nao ha Authelia, entao nao ha `Remote-User` -- e o campo
    `senha` saia do header CRU, enquanto a rota de ESCRITA (`PATCH /api/me/senha`) resolvia
    por `rbac.identidade`, que honra o `MOTOR_DEV_USUARIO`. As duas camadas liam a MESMA
    pessoa de fontes diferentes: o endpoint funcionava e a tela que o chama nunca aparecia.
    """
    import app as pilot_app

    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius.teste")
    monkeypatch.delenv(rbac.ENV_SINAL_PRODUCAO, raising=False)
    monkeypatch.delenv(rbac.ENV_DEV_IDENTIDADE, raising=False)
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(acesso, "abas_do_usuario_por_banco", lambda _u: ["mapa"])
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")
    vistos: list[str] = []

    def _estado(login: str) -> dict[str, bool]:
        vistos.append(login)
        return {"deve_trocar": True, "propria": False}

    monkeypatch.setattr(db_usuarios, "estado_da_senha", _estado)

    payload = pilot_app.me(remote_user=None)
    assert payload["senha"] == {"deve_trocar": True, "propria": False}
    assert vistos == ["vinicius.teste"], "consultou o banco por outra identidade"


def test_o_header_VENCE_a_env_de_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """A env so' preenche o VAZIO. Havendo header, e' ele -- em dev tambem.

    Inverter isto seria deixar uma env de desenvolvimento decidir de quem e' a senha que a
    tela oferece trocar, mesmo com uma identidade real na requisicao.
    """
    import app as pilot_app

    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setenv(rbac.ENV_DEV_USUARIO, "vinicius.teste")
    monkeypatch.delenv(rbac.ENV_SINAL_PRODUCAO, raising=False)
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(acesso, "abas_do_usuario_por_banco", lambda _u: ["mapa"])
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")
    vistos: list[str] = []

    def _estado(login: str) -> None:
        vistos.append(login)

    monkeypatch.setattr(db_usuarios, "estado_da_senha", _estado)

    pilot_app.me(remote_user="will.lindo")
    assert vistos == ["will.lindo"]


# --------------------------------------------------------------------------------------
# O estado da senha so' com o login proprio LIGADO (decisao do dono, 24/10/2026)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("banco", "chave", "manda"),
    [(True, True, True), (True, False, False), (False, True, False), (False, False, False)],
)
def test_o_estado_da_senha_so_sai_com_o_banco_no_comando_E_o_login_proprio_ligado(
    monkeypatch: pytest.MonkeyPatch, banco: bool, chave: bool, manda: bool
) -> None:
    """O cadeado do Dock e o convite de troca nascem desta chave -- e com o login proprio
    desligado eles mentiam: quem confere a senha e' o Authelia, e o cadeado pedia a senha
    INICIAL do banco, que em producao foi SORTEADA. Recusava todo mundo.

    O duble REGISTRA as consultas: sem a chave, o banco nem e' perguntado (uma ida a menos por
    abertura de app, no ramo em que ela seria inutil).
    """
    import app as pilot_app

    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: banco)
    monkeypatch.setattr(acesso, "abas_do_usuario_por_banco", lambda _u: ["mapa"])
    monkeypatch.setattr(acesso, "abas_do_usuario", lambda _u: ["mapa"])
    if chave:
        monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")
    consultas: list[str] = []

    def _estado(login: str) -> dict[str, bool]:
        consultas.append(login)
        return {"deve_trocar": True, "propria": False}

    monkeypatch.setattr(db_usuarios, "estado_da_senha", _estado)

    payload = pilot_app.me(remote_user="ana")
    assert ("senha" in payload) is manda
    assert consultas == (["ana"] if manda else [])


# --------------------------------------------------------------------------------------
# /api/me SEM PROVA DE QUEDA: a regua do gate (#463, follow-up A)
# --------------------------------------------------------------------------------------


def _sem_prova(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rbac.identidade` com o banco VIVO e ocupado: pool saturado, sem recusa de conexao."""
    from motor_expansao import db

    def ocupado(_remote_user: object) -> Any:
        raise db.BancoSemProvaDeQueda("PoolTimeout: couldn't get a connection after 5.00 sec")

    monkeypatch.setattr(rbac, "identidade", ocupado)


def _fora(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rbac.identidade` com o banco FORA, e a queda provada."""
    from motor_expansao import db

    def fora(_remote_user: object) -> Any:
        raise db.BancoIndisponivel("connection refused")

    monkeypatch.setattr(rbac, "identidade", fora)


@pytest.mark.parametrize("producao", [True, False])
def test_sem_prova_de_queda_o_me_nao_esconde_aba_nenhuma(
    monkeypatch: pytest.MonkeyPatch, producao: bool
) -> None:
    """O defeito: `BancoSemProvaDeQueda` e' SUBCLASSE de `BancoIndisponivel`, e o `except`
    generico pegava as duas como "banco fora". Com o banco VIVO e ocupado, o `/api/me` escondia
    executiva, imobiliaria e viabilidade de quem as tem -- e a SPA tirava a pessoa da tela dela.
    A regra agora e' a do gate, nos dois ambientes: sem prova, levanta; quem chama responde 503.
    """
    _sem_prova(monkeypatch)
    if producao:
        monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")
    monkeypatch.setattr(acesso, "banco_em_falha", lambda: False)
    with pytest.raises(acesso.RbacSemProvaDeQueda):
        acesso.abas_do_usuario_por_banco("ana")


def test_sem_prova_nesta_chamada_mas_com_a_queda_ja_provada_o_me_degrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mesma excecao do gate: se OUTRA chamada ja' provou a queda (e nenhuma terminou bem
    desde entao), o `PoolTimeout` seguinte nao precisa provar de novo -- degradacao de sempre."""
    _sem_prova(monkeypatch)
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")
    monkeypatch.setattr(acesso, "banco_em_falha", lambda: True)
    assert acesso.abas_do_usuario_por_banco("ana") == acesso.ABAS_VALIDAS - acesso.ABAS_SENSIVEIS


def test_a_interface_e_o_portao_contam_a_MESMA_historia(monkeypatch: pytest.MonkeyPatch) -> None:
    """A razao de existir do follow-up A. Para a mesma falha e a mesma pessoa, o gate e o
    `/api/me` decidem igual: sem prova, os dois levantam; com a queda provada, os dois degradam."""
    _sem_prova(monkeypatch)
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")

    monkeypatch.setattr(acesso, "banco_em_falha", lambda: False)
    with pytest.raises(acesso.RbacSemProvaDeQueda):
        acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "ana")
    with pytest.raises(acesso.RbacSemProvaDeQueda):
        acesso.abas_do_usuario_por_banco("ana")

    monkeypatch.setattr(acesso, "banco_em_falha", lambda: True)
    assert acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "ana") is not None
    assert "executiva" not in acesso.abas_do_usuario_por_banco("ana")


def test_o_me_responde_o_MESMO_503_do_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mesmo status, mesma frase, mesmo `Retry-After` -- a SPA mostra a mesma coisa venha a
    resposta de onde vier, e e' pelo `Retry-After` que ela sabe quanto esperar para tentar."""
    import json

    import app as pilot_app
    from fastapi import HTTPException

    _sem_prova(monkeypatch)
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(acesso, "banco_em_falha", lambda: False)
    with pytest.raises(HTTPException) as caiu:
        pilot_app.me(remote_user="ana")
    gate = pilot_app._piloto_ocupado()
    assert caiu.value.status_code == gate.status_code == 503
    assert caiu.value.detail == json.loads(bytes(gate.body))["detail"]
    assert caiu.value.headers == {"Retry-After": gate.headers["retry-after"]}


def test_o_log_do_me_e_UMA_linha_por_episodio(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Antes, um ERROR a cada abertura de SPA durante o incidente. Agora: uma linha por CASO no
    episodio -- outra so' se ele muda de caso, porque ai' muda o que a pessoa recebe (503 x abas
    escondidas) -- e o episodio acaba quando o RBAC responde de novo."""
    import logging

    import app as pilot_app
    from fastapi import HTTPException

    monkeypatch.setattr(acesso, "_episodio_rbac_no_me", None)
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    for nome in ("piloto.acesso", "piloto.falha"):
        caplog.set_level(logging.WARNING, logger=nome)

    def linhas(trecho: str) -> int:
        return sum(1 for r in caplog.records if trecho in r.getMessage())

    # Banco ocupado, sem prova: 503 a cada pedido, UMA linha.
    _sem_prova(monkeypatch)
    monkeypatch.setattr(acesso, "banco_em_falha", lambda: False)
    for _ in range(20):
        with pytest.raises(HTTPException):
            pilot_app.me(remote_user="ana")
    assert linhas("/api/me: o RBAC nao respondeu") == 1

    # A queda fica provada: a resposta MUDA (degradacao), e isso vale UMA linha a mais.
    _fora(monkeypatch)
    for _ in range(20):
        pilot_app.me(remote_user="ana")
    assert linhas("RBAC indisponivel no /api/me") == 1

    # O banco volta e cai de novo: novo episodio, nova linha.
    _identidade(monkeypatch, {"territorio.explorar"})
    pilot_app.me(remote_user="ana")
    _fora(monkeypatch)
    pilot_app.me(remote_user="ana")
    assert linhas("RBAC indisponivel no /api/me") == 2
    assert linhas("/api/me: o RBAC nao respondeu") == 1


def test_o_episodio_do_me_fecha_tambem_quando_o_GATE_ve_o_banco_voltar(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Quem navega sem recarregar a SPA so' toca o gate. Se so' o `/api/me` fechasse o episodio
    dele, o banco voltaria, cairia de novo, e a nova queda chegaria MUDA ao log do `/api/me`."""
    import logging

    monkeypatch.setattr(acesso, "_episodio_rbac_no_me", None)
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")
    caplog.set_level(logging.ERROR, logger="piloto.acesso")

    def linhas() -> int:
        return sum(1 for r in caplog.records if "RBAC indisponivel no /api/me" in r.getMessage())

    _fora(monkeypatch)
    acesso.abas_do_usuario_por_banco("ana")
    assert linhas() == 1

    _identidade(monkeypatch, {"territorio.explorar"})
    assert acesso.motivo_bloqueio_por_banco("/api/uf/SP", "GET", "ana") is None  # o gate ve' a volta

    _fora(monkeypatch)
    acesso.abas_do_usuario_por_banco("ana")
    assert linhas() == 2


# --------------------------------------------------------------------------------------
# O perfil `master` (migration 025, DEC-087): a Visão Executiva só das próprias unidades
# --------------------------------------------------------------------------------------

#: As leituras que o master alcança — a allowlist FECHADA de `acesso.rota_da_rede_propria`. O
#: recorte às unidades dele é da rota (`_recorte_da_rede`); aqui se prova só que ele CHEGA nelas.
_LEITURAS_DO_MASTER = (
    "/api/rede/filtros",
    "/api/rede/carteira",
    "/api/rede/inteligencia",
    "/api/rede/unidade/dalmo-centro-sp",
    "/api/rede/unidade/dalmo-centro-sp/inteligencia",
    "/api/rede/unidade/dalmo-centro-sp/setores",
)

#: O que o master NÃO alcança: exports, escrita do cadastro, unidades fora da rede, a Executiva
#: legada e tudo fora de `/api/rede/` (mapa, oportunidades, viabilidade, anotações, acessos).
_FORA_DO_MASTER = (
    ("PUT", "/api/rede/cadastro/dalmo-centro-sp"),
    ("GET", "/api/rede/carteira.csv"),
    ("GET", "/api/rede/carteira.xlsx"),
    ("GET", "/api/rede/carteira.pdf"),
    ("GET", "/api/rede/unidade/dalmo-centro-sp.pdf"),
    ("GET", "/api/rede/unidade/dalmo-centro-sp/concorrencia.pdf"),
    ("GET", "/api/rede/unidades-sem-rede"),
    ("GET", "/api/rede/unidade-sem-rede/x"),
    ("GET", "/api/executiva/SP"),
    ("GET", "/api/uf/SP"),
    ("GET", "/api/mapa/unidades"),
    ("GET", "/api/oportunidades"),
    ("POST", "/api/viabilidade"),
    ("GET", "/api/concorrente/observacoes"),
    ("POST", "/api/concorrente/observacoes"),
    ("POST", "/api/acessos/usuarios"),
)


@pytest.mark.parametrize("path", _LEITURAS_DO_MASTER)
def test_o_master_passa_nas_leituras_da_executiva(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    _identidade(monkeypatch, {acesso.CAPACIDADE_REDE_PROPRIA})
    assert acesso.motivo_bloqueio_por_banco(path, "GET", "dalmo_ribeiro") is None


@pytest.mark.parametrize(("metodo", "path"), _FORA_DO_MASTER)
def test_o_master_e_barrado_fora_da_allowlist(
    monkeypatch: pytest.MonkeyPatch, metodo: str, path: str
) -> None:
    _identidade(monkeypatch, {acesso.CAPACIDADE_REDE_PROPRIA})
    detalhe = acesso.motivo_bloqueio_por_banco(path, metodo, "dalmo_ribeiro")
    assert detalhe is not None and "não tem acesso" in detalhe


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE", "HEAD"])
def test_o_master_so_le(monkeypatch: pytest.MonkeyPatch, metodo: str) -> None:
    """A allowlist é de LEITURA: o mesmo caminho com outro método não passa — nem HEAD, que o
    servidor responderia com a mesma consulta e que não entra sem decisão."""
    _identidade(monkeypatch, {acesso.CAPACIDADE_REDE_PROPRIA})
    for path in _LEITURAS_DO_MASTER:
        assert acesso.motivo_bloqueio_por_banco(path, metodo, "dalmo_ribeiro") is not None


@pytest.mark.parametrize(
    "path",
    [
        "/api/rede/carteira/",  # barra a mais: não é a rota da allowlist
        "/api/rede/unidade/",  # id vazio
        "/api/rede/unidade/a/b",  # segmento a mais
        "/api/rede/unidade/x.pdf",  # o ponto separa a ficha do PDF dela
        "/api/rede/unidade/x.csv",
        "/api/rede/unidade/x/setores.csv",
        "/api/rede/unidade/x/concorrencia.pdf",
        "/api/rede/CARTEIRA",  # caixa diferente não é a mesma rota
        "/api/rede/carteira\n",  # fullmatch, e não a âncora de fim, que aceitaria a quebra de linha
        "/api/rede/cadastro/x",  # GET no cadastro cai em `rede.ver`, e não está na lista
        "/api/rede/unidades",
    ],
)
def test_a_allowlist_do_master_e_fechada(path: str) -> None:
    assert acesso.rota_da_rede_propria(path, "GET") is False


def test_a_allowlist_do_master_aceita_exatamente_as_seis_leituras() -> None:
    for path in _LEITURAS_DO_MASTER:
        assert acesso.rota_da_rede_propria(path, "GET") is True
        assert acesso.rota_da_rede_propria(path, "get") is True
    assert len(acesso.ROTAS_DA_REDE_PROPRIA) == len(_LEITURAS_DO_MASTER)


def test_a_allowlist_nao_aceita_entrada_que_nao_e_texto() -> None:
    assert acesso.rota_da_rede_propria(None, "GET") is False  # type: ignore[arg-type]
    assert acesso.rota_da_rede_propria("/api/rede/carteira", None) is False  # type: ignore[arg-type]


def test_rede_ver_propria_so_substitui_rede_ver(monkeypatch: pytest.MonkeyPatch) -> None:
    """A troca vale só no lugar de `rede.ver`. Se o gate aceitasse `rede.ver_propria` no lugar de
    qualquer capacidade de uma rota da allowlist, um remapeamento futuro (ex.: a ficha passar a
    exigir outra chave) abriria a rota ao master por acidente."""
    _identidade(monkeypatch, {acesso.CAPACIDADE_REDE_PROPRIA})
    monkeypatch.setattr(acesso, "capacidade_necessaria", lambda _p, _m: "territorio.explorar")
    assert acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "x") is not None


def test_as_abas_do_master_sao_so_a_executiva(monkeypatch: pytest.MonkeyPatch) -> None:
    """A interface conta a mesma história que o gate: a aba Executiva aparece, e nenhuma outra."""
    _identidade(monkeypatch, {acesso.CAPACIDADE_REDE_PROPRIA})
    assert acesso.abas_do_usuario_por_banco("dalmo_ribeiro") == frozenset({"executiva"})


def test_quem_tem_rede_ver_continua_igual(monkeypatch: pytest.MonkeyPatch) -> None:
    """Consultoria, líderes e growth: a rede inteira, os exports e a Executiva legada seguem
    abertos, e a escrita do cadastro segue dependendo de `rede.cadastro_editar`."""
    _identidade(monkeypatch, {"rede.ver"})
    for metodo, path in [
        ("GET", "/api/rede/carteira"),
        ("GET", "/api/rede/carteira.csv"),
        ("GET", "/api/rede/carteira.xlsx"),
        ("GET", "/api/rede/carteira.pdf"),
        ("GET", "/api/rede/unidade/x.pdf"),
        ("GET", "/api/rede/unidade/x/concorrencia.pdf"),
        ("GET", "/api/rede/unidades-sem-rede"),
        ("GET", "/api/executiva/SP"),
    ]:
        assert acesso.motivo_bloqueio_por_banco(path, metodo, "x") is None, path
    assert acesso.motivo_bloqueio_por_banco("/api/rede/cadastro/x", "PUT", "x") is not None
    assert acesso.abas_do_usuario_por_banco("x") == frozenset({"executiva"})


def test_ter_as_duas_chaves_nao_estreita_ninguem(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rede.ver` responde antes: quem tem as duas segue com a rede inteira e os exports."""
    _identidade(monkeypatch, {"rede.ver", acesso.CAPACIDADE_REDE_PROPRIA})
    assert acesso.motivo_bloqueio_por_banco("/api/rede/carteira.csv", "GET", "x") is None


def test_rede_ver_propria_tem_seed_e_e_sensivel() -> None:
    """Sem seed, o perfil master nunca teria a chave; fora das sensíveis, uma rota que um dia a
    exija direto nasceria aberta na degradação com o banco fora."""
    do_seed = _capacidades_semeadas()
    assert acesso.CAPACIDADE_REDE_PROPRIA == "rede.ver_propria"
    assert acesso.CAPACIDADE_REDE_PROPRIA in do_seed
    assert acesso.CAPACIDADE_REDE_PROPRIA in acesso.CAPACIDADES_SENSIVEIS
    for aba, alternativas in acesso.CAPACIDADES_ALTERNATIVAS_DA_ABA.items():
        assert aba in acesso.ABAS_VALIDAS, aba
        assert alternativas <= do_seed, sorted(alternativas - do_seed)


def test_banco_fora_em_producao_nega_o_master(monkeypatch: pytest.MonkeyPatch) -> None:
    """A degradação não sabe QUEM pede: as rotas da allowlist exigem `rede.ver`, que é sensível,
    e por isso ficam negadas para todo mundo — o master não ganha a rede por um incidente."""
    from motor_expansao import db

    def explode(_remote_user: object) -> Any:
        raise db.BancoIndisponivel("connection refused")

    monkeypatch.setattr(rbac, "identidade", explode)
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")  # sinal de produção
    for path in _LEITURAS_DO_MASTER:
        assert acesso.motivo_bloqueio_por_banco(path, "GET", "dalmo_ribeiro") is not None
    assert "executiva" not in acesso.abas_do_usuario_por_banco("dalmo_ribeiro")


def test_banco_ocupado_sem_prova_da_503_tambem_ao_master(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem prova de queda o gate responde 503 (`RbacSemProvaDeQueda`), e não a degradação."""
    from motor_expansao import db

    def ocupado(_remote_user: object) -> Any:
        raise db.BancoSemProvaDeQueda("pool saturado")

    monkeypatch.setattr(rbac, "identidade", ocupado)
    monkeypatch.setattr(acesso, "banco_em_falha", lambda: False)
    with pytest.raises(acesso.RbacSemProvaDeQueda):
        acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "dalmo_ribeiro")
