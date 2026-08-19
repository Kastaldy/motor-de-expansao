"""Relatório de acessos por usuário (trilha DEC-027) — módulo + comando do bot.

Pedido de Felipe (2026-08-18): agregado "quem logou e quais abas" puxável pelo
Telegram (`/acessos`, só no chat de ops) e enviado 3/3h pelo cron. Cobre: a
agregação (filtro de curl, mapeamento rota→aba, janela BRT), o contrato de
consistência com as `REGRAS_DE_ACESSO` do piloto, o formato do texto e a
autorização do comando no bot.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from motor_expansao.api import relatorio_acessos
from motor_expansao.api import telegram_bot as bot
from motor_expansao.api.settings import Settings

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402  (controle por aba do piloto; web/server no sys.path acima)


def _linha(usuario: str, rota: str, quando: str = "2026-08-18T13:00:00+00:00",
           agente: str = "Mozilla/5.0") -> str:
    return json.dumps(
        {"quando": quando, "usuario": usuario, "ip": "1.2.3.4", "metodo": "GET",
         "rota": rota, "status": 200, "duracao_ms": 5, "agente": agente},
        ensure_ascii=False,
    )


# --- agregação --------------------------------------------------------------


def test_agrega_por_usuario_com_janela_brt_e_abas() -> None:
    linhas = [
        _linha("ana", "/api/ufs", "2026-08-18T12:00:00+00:00"),
        _linha("ana", "/api/rede/carteira", "2026-08-18T12:30:00+00:00"),
        _linha("ana", "/api/viabilidade", "2026-08-18T14:15:00+00:00"),
        _linha("bia", "/api/municipios/SP"),
    ]
    agregado = relatorio_acessos.agregar_acessos(linhas)
    # Janela ja em BRT (UTC-3): 12:00 UTC -> 09:00.
    assert agregado["ana"]["ini"] == "09:00" and agregado["ana"]["fim"] == "11:15"
    assert agregado["ana"]["abas"] == {"executiva", "viabilidade"}  # /api/ufs não é aba
    assert agregado["ana"]["acoes"] == 3
    assert agregado["bia"]["abas"] == {"mapa"}


def test_ignora_diagnostico_curl_linha_ilegivel_e_nao_dict() -> None:
    linhas = [
        _linha("deploy-check", "/api/ufs", agente="curl/8.14.1"),
        "{nao é json}",
        '["json valido mas nao e objeto"]',
        "42",
        _linha("ana", "/api/ponto"),
    ]
    agregado = relatorio_acessos.agregar_acessos(linhas)
    assert set(agregado) == {"ana"}


def test_agrega_filtra_pelo_dia_brt() -> None:
    """Linha de 01:00 UTC do dia 19 é 22:00 BRT do dia 18 — pertence ao dia 18."""
    from datetime import date

    linhas = [
        _linha("ana", "/api/ponto", "2026-08-18T12:00:00+00:00"),   # 09:00 BRT dia 18
        _linha("ana", "/api/ponto", "2026-08-19T01:00:00+00:00"),   # 22:00 BRT dia 18
        _linha("bia", "/api/ponto", "2026-08-18T02:00:00+00:00"),   # 23:00 BRT dia 17!
    ]
    agregado = relatorio_acessos.agregar_acessos(linhas, dia_brt=date(2026, 8, 18))
    assert set(agregado) == {"ana"}, "bia agiu no dia BRT 17; fica fora do dia 18"
    assert agregado["ana"]["ini"] == "09:00" and agregado["ana"]["fim"] == "22:00"


def test_agrupamento_cobre_as_regras_de_acesso() -> None:
    """Contrato anti-drift: toda rota controlada em `web/server/acesso.py` tem de
    estar no agrupamento do relatório, atribuída a uma aba que a LIBERA lá."""
    espelho = dict(relatorio_acessos.AGRUPAMENTO_ABAS)
    for prefixo, abas_que_liberam in acesso.REGRAS_DE_ACESSO:
        assert prefixo in espelho, (
            f"rota controlada {prefixo!r} sem aba no relatório — "
            "atualize AGRUPAMENTO_ABAS em relatorio_acessos.py"
        )
        assert espelho[prefixo] in abas_que_liberam, (
            f"{prefixo!r}: relatório atribui {espelho[prefixo]!r}, "
            f"que não libera a rota ({sorted(abas_que_liberam)})"
        )
    assert set(espelho.values()) <= set(relatorio_acessos.LABEL_ABA), (
        "aba sem label de exibição acentuado"
    )


# --- geração do texto -------------------------------------------------------

_AGORA = datetime(2026, 8, 18, 15, 0, tzinfo=UTC)  # 12:00 BRT


def _trilha(tmp_path: Path, linhas: list[str]) -> Path:
    dia_brt = (_AGORA + relatorio_acessos._FUSO_BRT).date()
    arquivo = relatorio_acessos.arquivos_do_dia_brt(tmp_path, dia_brt)[0]
    arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return tmp_path


def _trilha_agora(tmp_path: Path, usuario: str = "ana", rota: str = "/api/ponto") -> Path:
    """Trilha ancorada no relógio REAL, para quem não aceita `agora_utc`.

    A CLI (`main`) e o bot (`/acessos`) resolvem o dia com `datetime.now(UTC)` lá dentro — não
    há por onde injetar. Um `_trilha` cravado em `_AGORA` (18/08) grava no arquivo daquele dia
    e o leitor procura no de HOJE: o relatório sai vazio e o assert cai.

    Isso não era hipótese — os três testes que usam este helper passavam **só em 2026-08-18** e
    falharam em todos os dias seguintes, deixando a `main` vermelha (`BLK-FIX-ACESSOS-01`).

    A margem de 2 h para trás cobre a borda: rodando entre 00:00 e 02:00 BRT, "agora" cru
    cairia no arquivo UTC do dia seguinte enquanto o dia BRT ainda é o anterior.
    """
    agora = datetime.now(UTC) - timedelta(hours=2)
    dia_brt = (agora + relatorio_acessos._FUSO_BRT).date()
    arquivo = relatorio_acessos.arquivos_do_dia_brt(tmp_path, dia_brt)[0]
    arquivo.write_text(_linha(usuario, rota, agora.isoformat()) + chr(10), encoding="utf-8")
    return tmp_path


def test_relatorio_formata_em_brt_com_labels(tmp_path: Path) -> None:
    base = _trilha(tmp_path, [
        _linha("ana", "/api/rede/carteira", "2026-08-18T12:00:00+00:00"),
        _linha("ana", "/api/viabilidade", "2026-08-18T14:15:00+00:00"),
    ])
    texto = relatorio_acessos.gerar_relatorio(base, _AGORA)
    assert "1 usuário hoje" in texto
    assert "• ana — 09:00–11:15 · Executiva, Viabilidade" in texto  # UTC-3 + labels
    assert "12:00 BRT" in texto
    assert "/api/" not in texto, "o relatório é agregado: rota nunca aparece"
    assert "*" not in texto, "texto puro: sem Markdown (nome de usuário quebraria o parse)"


def test_relatorio_no_fim_da_noite_brt_le_o_arquivo_utc_seguinte(tmp_path: Path) -> None:
    """22:30 BRT do dia 18 = 01:30 UTC do dia 19: a trilha já está no ARQUIVO do
    dia 19, mas o relatório do dia BRT 18 tem de enxergar o dia inteiro (defeito
    da revisão: entre 21h e meia-noite BRT ele negava o dia todo)."""
    agora = datetime(2026, 8, 19, 1, 40, tzinfo=UTC)  # 22:40 BRT do dia 18
    arquivo_d19 = tmp_path / "acesso-2026-08-19.jsonl"
    arquivo_d18 = tmp_path / "acesso-2026-08-18.jsonl"
    arquivo_d18.write_text(
        _linha("ana", "/api/ponto", "2026-08-18T12:00:00+00:00") + "\n", encoding="utf-8"
    )
    arquivo_d19.write_text(
        _linha("bia", "/api/ponto", "2026-08-19T01:30:00+00:00") + "\n", encoding="utf-8"
    )
    texto = relatorio_acessos.gerar_relatorio(tmp_path, agora)
    assert "2 usuários hoje" in texto and "18/08" in texto
    assert "ana" in texto and "bia" in texto
    assert "22:30" in texto  # a bia aparece na hora BRT coerente do MESMO dia


def test_relatorio_sem_arquivo_ou_vazio(tmp_path: Path) -> None:
    texto = relatorio_acessos.gerar_relatorio(tmp_path, _AGORA)
    assert "Nenhum acesso" in texto and relatorio_acessos.relatorio_vazio(texto)
    _trilha(tmp_path, [_linha("x", "/api/ufs", agente="curl/1")])
    assert "Nenhum acesso" in relatorio_acessos.gerar_relatorio(tmp_path, _AGORA)


def test_enviar_telegram_nao_vaza_token_e_particiona(monkeypatch: pytest.MonkeyPatch) -> None:
    """Erro do Telegram vira RuntimeError SEM a URL (o HTTPError do requests embute
    o token); texto longo sai em blocos abaixo do teto de 4096."""
    import requests

    chamadas: list[dict] = []

    class _Resp:
        def __init__(self, ok: bool):
            self.ok = ok
            self.status_code = 200 if ok else 400

        def json(self) -> dict:
            return {"description": "Bad Request: can't parse"}

    def _post(url: str, json: dict, timeout: int) -> _Resp:  # noqa: A002
        chamadas.append(json)
        return _Resp(ok=True)

    monkeypatch.setattr(requests, "post", _post)
    texto_longo = "\n".join(f"• usuario_{i:03d} — 09:00–10:00 · Mapa" for i in range(200))
    relatorio_acessos.enviar_telegram(texto_longo, "tok-secreto", "777")
    assert len(chamadas) >= 2, "acima do teto tem de particionar"
    assert all(len(c["text"]) <= 4096 for c in chamadas)
    assert all("parse_mode" not in c for c in chamadas), "texto puro, sem Markdown"

    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(ok=False))
    with pytest.raises(RuntimeError) as erro:
        relatorio_acessos.enviar_telegram("oi", "tok-secreto", "777")
    assert "tok-secreto" not in str(erro.value), "token JAMAIS na mensagem de erro"
    assert "400" in str(erro.value)


def test_cli_imprime_sem_enviar(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _trilha_agora(tmp_path)
    codigo = relatorio_acessos.main(["--dir", str(tmp_path)])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "ana" in saida and "enviado" not in saida


def test_cli_enviar_exige_credenciais(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _trilha(tmp_path, [_linha("ana", "/api/ponto", "2026-08-18T12:00:00+00:00")])
    monkeypatch.delenv("API_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("MONITOR_TELEGRAM_CHAT_ID", raising=False)
    assert relatorio_acessos.main(["--dir", str(tmp_path), "--enviar"]) == 1


def test_cli_pular_vazio_nao_envia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    def _explode(*_a: object, **_k: object) -> None:
        raise AssertionError("não pode enviar relatório vazio")

    monkeypatch.setattr(relatorio_acessos, "enviar_telegram", _explode)
    codigo = relatorio_acessos.main(["--dir", str(tmp_path), "--enviar", "--pular-vazio"])
    assert codigo == 0
    assert "pulado" in capsys.readouterr().out


def test_settings_env_vazia_desliga_o_acesso_log_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`API_ACESSO_LOG_DIR=` (vazio) tem de virar None — Path('.') truthy furaria o
    guard de 'não configurado' do bot (revisão de 2026-08-18)."""
    monkeypatch.setenv("API_ACESSO_LOG_DIR", "")
    assert Settings(bot_senha="x", telegram_token="x").acesso_log_dir is None


# --- comando /acessos no bot ------------------------------------------------


@pytest.fixture(autouse=True)
def _limpa_sessoes():
    bot._sessoes.clear()
    yield
    bot._sessoes.clear()


def _settings(tmp_path: Path | None = None, admin: str = "777") -> Settings:
    return Settings(
        bot_senha="abre",
        telegram_token="x",
        acessos_admin_chat_id=admin,
        acesso_log_dir=tmp_path,
    )


def _texto(acoes: list[dict]) -> str:
    return " || ".join(a.get("text", "") for a in acoes)


def test_acessos_no_chat_de_ops_sem_senha(tmp_path: Path) -> None:
    """O chat de ops puxa o relatório DIRETO — sem passar pela senha do bot."""
    _trilha_agora(tmp_path)
    saida = _texto(bot.processar(777, "/acessos", _settings(tmp_path)))
    assert "ana" in saida and "Acessos do piloto" in saida


def test_acessos_cobre_forma_de_grupo(tmp_path: Path) -> None:
    _trilha_agora(tmp_path)
    saida = _texto(bot.processar(777, "/acessos@MotorBot", _settings(tmp_path)))
    assert "ana" in saida


def test_acessos_negado_fora_do_chat_de_ops(tmp_path: Path) -> None:
    """Outro chat — mesmo AUTENTICADO — recebe resposta neutra, sem dado nenhum."""
    settings = _settings(tmp_path)
    bot.processar(1, "abre", settings)
    bot.processar(1, "Tester", settings)
    saida = _texto(bot.processar(1, "/acessos", settings))
    assert "restrito" in saida.lower()
    assert "ana" not in saida


def test_acessos_desligado_sem_admin_configurado(tmp_path: Path) -> None:
    saida = _texto(bot.processar(777, "/acessos", _settings(tmp_path, admin="")))
    assert "restrito" in saida.lower()


def test_acessos_sem_trilha_configurada() -> None:
    saida = _texto(bot.processar(777, "/acessos", _settings(None)))
    assert "indisponível" in saida.lower()


def test_acessos_erro_no_gerador_nao_derruba(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        relatorio_acessos, "gerar_relatorio",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    saida = _texto(bot.processar(777, "/acessos", _settings(tmp_path)))
    assert "não consegui" in saida.lower()
