"""Allowlist de chats do bot (2026-09-24).

O que estes testes protegem, em ordem de importancia:

1. que o gate rode ANTES do estado de sessao — e' isso que faz a revogacao valer
   para quem JA' estava autorizado, sem apagar sessao de ninguem;
2. que a ausencia do arquivo seja FAIL-CLOSED — um controle de revogacao que se
   abre sozinho quando o arquivo some tem o modo de falha exatamente igual ao
   cenario que ele deveria impedir;
3. que nem o `/acessos` escape do gate;
4. que a lista seja relida por MTIME, porque a promessa operacional e' "edita na
   VPS e vale na hora, sem restart".
"""

from __future__ import annotations

import json
import os
import time

import pytest

from motor_expansao.api import telegram_bot as bot
from motor_expansao.api.settings import Settings


@pytest.fixture(autouse=True)
def _limpa():
    bot._sessoes.clear()
    bot._allow_cache = None
    yield
    bot._sessoes.clear()
    bot._allow_cache = None


def _textos(acoes) -> str:
    return " || ".join(a.get("text", "<pdf>") for a in acoes)


def _cfg(tmp_path, chats, *, formato="objeto") -> Settings:
    alvo = tmp_path / "bot_allowlist.json"
    corpo = {"_comentario": "teste", "chats": chats} if formato == "objeto" else chats
    alvo.write_text(json.dumps(corpo), encoding="utf-8")
    return Settings(bot_senha="abre", telegram_token="x", bot_allowlist_path=alvo)


# ── o gate ──────────────────────────────────────────────────────────────────
def test_chat_da_lista_passa(tmp_path) -> None:
    s = _cfg(tmp_path, [7])
    assert "nao tem acesso" not in _textos(bot.processar(7, "oi", s)).lower()


def test_chat_fora_da_lista_e_barrado(tmp_path) -> None:
    s = _cfg(tmp_path, [7])
    assert "nao tem acesso" in _textos(bot.processar(999, "oi", s)).lower()


def test_senha_certa_nao_salva_quem_esta_fora(tmp_path) -> None:
    """A senha e' COMPARTILHADA: sem isto, o ex-funcionario que a conhece entra."""
    s = _cfg(tmp_path, [7])
    assert "nao tem acesso" in _textos(bot.processar(999, "abre", s)).lower()
    assert bot._sessoes.get(999, {}).get("autorizado") is not True


def test_revoga_quem_ja_estava_autorizado(tmp_path) -> None:
    """O caso que motivou o bloco: sessao persistida com `autorizado: true`.

    Trocar a senha NAO resolveria isso — a sessao sobrevive em disco. O gate roda
    antes do estado, entao a revogacao vale na proxima mensagem.
    """
    s = _cfg(tmp_path, [7])
    bot.processar(7, "abre", s)
    bot.processar(7, "Fulano", s)
    assert bot._sessoes[7]["autorizado"] is True

    # Reescreve o MESMO arquivo tirando o 7 — e' o gesto real na VPS (editar a lista),
    # nao trocar de arquivo. `utime` garante mtime distinto num teste de milissegundos.
    alvo = tmp_path / "bot_allowlist.json"
    alvo.write_text(json.dumps({"chats": []}), encoding="utf-8")
    futuro = time.time() + 2
    os.utime(alvo, (futuro, futuro))
    assert "nao tem acesso" in _textos(bot.processar(7, "menu", s)).lower()
    # A sessao continua no disco; quem barra e' a lista, nao o estado.
    assert bot._sessoes[7]["autorizado"] is True


def test_acessos_tambem_passa_pelo_gate(tmp_path) -> None:
    """`/acessos` vinha ANTES do gate de senha; nao pode vir antes deste."""
    s = _cfg(tmp_path, [7])
    object.__setattr__(s, "acessos_admin_chat_id", "999")
    assert "nao tem acesso" in _textos(bot.processar(999, "/acessos", s)).lower()


# ── fail-closed ─────────────────────────────────────────────────────────────
def test_arquivo_ausente_nega_todos(tmp_path) -> None:
    s = Settings(bot_senha="abre", telegram_token="x",
                 bot_allowlist_path=tmp_path / "nao-existe.json")
    assert "nao tem acesso" in _textos(bot.processar(7, "oi", s)).lower()


def test_json_quebrado_nega_todos(tmp_path) -> None:
    alvo = tmp_path / "bot_allowlist.json"
    alvo.write_text("{isto nao e json", encoding="utf-8")
    s = Settings(bot_senha="abre", telegram_token="x", bot_allowlist_path=alvo)
    assert "nao tem acesso" in _textos(bot.processar(7, "oi", s)).lower()


def test_arquivo_consertado_volta_a_valer_sem_restart(tmp_path) -> None:
    """O erro NAO e' cacheado: quem conserta o arquivo nao precisa reiniciar o bot."""
    alvo = tmp_path / "bot_allowlist.json"
    alvo.write_text("{quebrado", encoding="utf-8")
    s = Settings(bot_senha="abre", telegram_token="x", bot_allowlist_path=alvo)
    assert "nao tem acesso" in _textos(bot.processar(7, "oi", s)).lower()

    alvo.write_text(json.dumps({"chats": [7]}), encoding="utf-8")
    assert "nao tem acesso" not in _textos(bot.processar(7, "oi", s)).lower()


def test_sem_caminho_configurado_o_controle_fica_desligado(tmp_path) -> None:
    """Dev/teste sem a env: o bot segue como antes, sem allowlist."""
    s = Settings(bot_senha="abre", telegram_token="x")
    assert "nao tem acesso" not in _textos(bot.processar(7, "oi", s)).lower()


# ── releitura por mtime ─────────────────────────────────────────────────────
def test_relido_por_mtime_sem_restart(tmp_path) -> None:
    alvo = tmp_path / "bot_allowlist.json"
    alvo.write_text(json.dumps({"chats": [7]}), encoding="utf-8")
    s = Settings(bot_senha="abre", telegram_token="x", bot_allowlist_path=alvo)
    assert "nao tem acesso" not in _textos(bot.processar(7, "oi", s)).lower()

    # Reescreve TIRANDO o 7, e forca um mtime distinto (o teste roda em ms).
    alvo.write_text(json.dumps({"chats": [8]}), encoding="utf-8")
    futuro = time.time() + 2
    os.utime(alvo, (futuro, futuro))
    assert "nao tem acesso" in _textos(bot.processar(7, "menu", s)).lower()


def test_aceita_lista_crua_alem_do_objeto(tmp_path) -> None:
    """O objeto permite `_comentario` no arquivo; a lista crua e' o formato minimo."""
    s = _cfg(tmp_path, [7], formato="lista")
    assert "nao tem acesso" not in _textos(bot.processar(7, "oi", s)).lower()


def test_chat_id_em_texto_tambem_vale(tmp_path) -> None:
    """Quem edita a mao pode escrever com aspas; nao e' motivo para trancar todos."""
    s = _cfg(tmp_path, ["7", 8])
    assert "nao tem acesso" not in _textos(bot.processar(7, "oi", s)).lower()


def test_grupo_de_ops_com_id_negativo(tmp_path) -> None:
    """Chat de GRUPO tem id negativo — o parse nao pode perder o sinal."""
    s = _cfg(tmp_path, [-5300865540])
    assert "nao tem acesso" not in _textos(bot.processar(-5300865540, "oi", s)).lower()


# ── trilha persistente ──────────────────────────────────────────────────────
def _linhas(dir_trilha):
    saida = []
    for arq in sorted(dir_trilha.glob("*.jsonl")):
        saida += [json.loads(x) for x in arq.read_text(encoding="utf-8").splitlines() if x]
    return saida


def test_trilha_registra_autorizacao_e_negativa(tmp_path) -> None:
    trilha = tmp_path / "trilha"
    alvo = tmp_path / "bot_allowlist.json"
    alvo.write_text(json.dumps({"chats": [7]}), encoding="utf-8")
    s = Settings(bot_senha="abre", telegram_token="x",
                 bot_allowlist_path=alvo, bot_trilha_dir=trilha)

    bot.processar(7, "abre", s)      # autorizado
    bot.processar(999, "oi", s)      # negado pela allowlist

    assert [e["evento"] for e in _linhas(trilha)] == ["autorizado", "negado_allowlist"]


def test_trilha_nao_guarda_chat_id_cru_nem_nome_nem_texto(tmp_path) -> None:
    """Anti-PII, e o NOME e' o ponto.

    A 1a versao gravava o `login` auto-declarado — nome de pessoa em texto puro,
    retido 90 dias. A revisao automatica reprovou: a DEC-027 tratou trilha analoga
    como mudanca de postura de auditoria e excluiu o bot do escopo de proposito.
    O nome era dispensavel — a referencia opaca ja' agrupa por pessoa.
    """
    trilha = tmp_path / "trilha"
    s = Settings(bot_senha="abre", telegram_token="x", bot_trilha_dir=trilha)
    bot.processar(424242, "abre", s)
    bot.processar(424242, "Fulano de Tal", s)  # etapa de login: o nome passa por aqui

    bruto = "".join(a.read_text(encoding="utf-8") for a in trilha.glob("*.jsonl"))
    assert "424242" not in bruto          # chat_id cru
    assert "Fulano" not in bruto          # nome auto-declarado
    for linha in _linhas(trilha):
        assert linha["chat"].startswith("#") and len(linha["chat"]) == 9
        assert set(linha) == {"ts", "chat", "evento", "detalhe"}


def test_senha_incorreta_deixa_rastro(tmp_path) -> None:
    """Vocabulario sem emissor e' promessa vazia — era o 2o achado da revisao.

    Tentativa contra a senha COMPARTILHADA e' o sinal de forca bruta que o log
    efemero perdia a cada deploy; tem de sobreviver.
    """
    trilha = tmp_path / "trilha"
    s = Settings(bot_senha="abre", telegram_token="x", bot_trilha_dir=trilha)
    bot.processar(7, "oi", s)        # 1a msg = saudacao, nao conta como tentativa
    bot.processar(7, "chutando", s)  # agora sim

    eventos = [(e["evento"], e["detalhe"]) for e in _linhas(trilha)]
    assert ("senha_incorreta", "tentativa 1") in eventos


def test_todo_evento_declarado_tem_emissor() -> None:
    """Trava a classe do achado: vocabulario declarado e nunca usado.

    Le o FONTE porque o defeito e' de ausencia — nao ha execucao que o revele.
    """
    import pathlib

    fonte = pathlib.Path(bot.__file__).read_text(encoding="utf-8")
    for evento in bot.EVENTOS_TRILHA:
        # Pelo menos DUAS aparicoes: a declaracao em `EVENTOS_TRILHA` e a chamada de
        # `_registrar` que o emite. Contar e' mais robusto que recortar o arquivo por
        # posicao — nao quebra quando alguem move o bloco de lugar.
        assert fonte.count(f'"{evento}"') >= 2, (
            f"evento {evento!r} declarado mas nunca emitido por `_registrar`"
        )


def test_trilha_desligada_sem_diretorio_configurado() -> None:
    s = Settings(bot_senha="abre", telegram_token="x")
    bot.processar(7, "abre", s)  # nao pode levantar


def test_trilha_recusa_evento_fora_do_vocabulario(tmp_path) -> None:
    """Vocabulario FECHADO: evento novo se declara em EVENTOS_TRILHA."""
    s = Settings(bot_senha="abre", telegram_token="x", bot_trilha_dir=tmp_path / "t")
    with pytest.raises(ValueError):
        bot._registrar(7, s, "inventado")


def test_poda_apaga_so_o_que_saiu_da_retencao(tmp_path) -> None:
    import datetime as _dt

    trilha = tmp_path / "trilha"
    trilha.mkdir()
    hoje = _dt.datetime.now(_dt.UTC)
    velho = (hoje - _dt.timedelta(days=bot.TRILHA_RETENCAO_DIAS + 5)).strftime("%Y-%m-%d")
    novo = (hoje - _dt.timedelta(days=3)).strftime("%Y-%m-%d")
    (trilha / f"{velho}.jsonl").write_text("{}\n", encoding="utf-8")
    (trilha / f"{novo}.jsonl").write_text("{}\n", encoding="utf-8")

    bot._trilha_podada_em = ""
    s = Settings(bot_senha="abre", telegram_token="x", bot_trilha_dir=trilha)
    bot._registrar(7, s, "autorizado")

    restantes = {a.stem for a in trilha.glob("*.jsonl")}
    assert velho not in restantes
    assert novo in restantes


# ── o estado do controle na PARTIDA (2026-09-25) ────────────────────────────
#
# O gate era fail-CLOSED por ARQUIVO (ilegivel nega a todos) e fail-OPEN por
# CONFIGURACAO (caminho ausente libera a todos) — e nao dizia qual das duas metades
# estava valendo. O unico print de estado saia de dentro de `_allowlist`, so' com o
# controle LIGADO e so' na PRIMEIRA mensagem processada: o estado que mais precisava
# aparecer era justamente o que nunca imprimia nada. Bot no ar com a revogacao
# desligada era indistinguivel de bot no ar com ela valendo.
#
# Importa porque a allowlist existe para revogar acesso de quem saiu da empresa: uma
# env que some numa edicao do compose devolvia esse acesso sem uma linha de log.
def test_producao_sem_allowlist_recusa_subir() -> None:
    s = Settings(bot_senha="abre", telegram_token="x", environment="production")
    with pytest.raises(SystemExit) as erro:
        bot.verificar_controle_de_acesso(s)
    assert "API_BOT_ALLOWLIST_PATH" in str(erro.value)


def test_producao_com_allowlist_sobe_e_diz_quantos(tmp_path, capsys) -> None:
    alvo = tmp_path / "bot_allowlist.json"
    alvo.write_text(json.dumps({"chats": [7, 8, 9]}), encoding="utf-8")
    s = Settings(
        bot_senha="abre",
        telegram_token="x",
        environment="production",
        bot_allowlist_path=alvo,
    )
    bot.verificar_controle_de_acesso(s)
    saida = capsys.readouterr().out
    assert "LIGADA" in saida
    assert "3 chats" in saida


def test_fora_de_producao_sobe_avisando_que_esta_desligada(capsys) -> None:
    """Desenvolvimento segue usavel sem arquivo nenhum — mas o log diz o que vale."""
    s = Settings(bot_senha="abre", telegram_token="x")
    bot.verificar_controle_de_acesso(s)  # nao levanta
    assert "DESLIGADA" in capsys.readouterr().out


def test_arquivo_quebrado_grita_na_partida_e_nao_na_1a_mensagem(tmp_path, capsys) -> None:
    """Fail-closed por arquivo continua valendo — o que muda e' QUANDO se descobre."""
    alvo = tmp_path / "bot_allowlist.json"
    alvo.write_text("{isto nao e json", encoding="utf-8")
    s = Settings(
        bot_senha="abre",
        telegram_token="x",
        environment="production",
        bot_allowlist_path=alvo,
    )
    bot.verificar_controle_de_acesso(s)  # sobe: o arquivo pode ser consertado sem restart
    saida = capsys.readouterr().out
    assert "FAIL-CLOSED" in saida
    assert "0 chats" in saida


def test_env_vazia_cai_na_mesma_recusa_que_env_ausente() -> None:
    """`API_BOT_ALLOWLIST_PATH=` vira None pelo validador — e nao pode virar brecha."""
    s = Settings(
        bot_senha="abre", telegram_token="x", environment="production", bot_allowlist_path=""
    )
    assert s.bot_allowlist_path is None
    with pytest.raises(SystemExit):
        bot.verificar_controle_de_acesso(s)
