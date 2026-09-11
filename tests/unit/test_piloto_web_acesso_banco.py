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


@pytest.fixture(autouse=True)
def _sem_producao(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.delenv("MOTOR_CADASTRO_DIR", raising=False)
    monkeypatch.delenv("MOTOR_ACESSO_FAIL_CLOSED", raising=False)
    yield


def _identidade(monkeypatch: pytest.MonkeyPatch, permissoes: set[str] | None) -> None:
    """Dubla `rbac.identidade`: `None` = usuário desconhecido/negado."""
    def falsa(_remote_user: object) -> rbac.Identidade | None:
        if permissoes is None:
            return None
        return rbac.Identidade(
            id_usuario=1, login="alguem", perfil="teste", permissoes=frozenset(permissoes)
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
    """Uma ida ao banco a menos por abertura de app, no ramo em que ela seria inutil."""
    import app as pilot_app

    from motor_expansao.db import usuarios as db_usuarios

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: False)
    monkeypatch.setattr(acesso, "abas_do_usuario", lambda _u: ["mapa"])

    def _nao_deveria(_login: str) -> None:
        raise AssertionError("consultou o banco com `banco_no_comando()` falso")

    monkeypatch.setattr(db_usuarios, "estado_da_senha", _nao_deveria)
    assert "senha" not in pilot_app.me(remote_user="ana")
