"""Analytics da aba Acessos (emenda DEC-027) — agregações + rollup sem dado pessoal.

Cobre os contratos que a emenda promete:
  - o filtro de métrica é o MESMO do relatório do Telegram (`evento_valido`), e o
    painel (`/api/acessos/*`) fica fora das contagens nas DUAS superfícies;
  - o rollup diário é write-once (número histórico estável mesmo após a poda),
    idempotente, atômico e SEM dado pessoal (contagens, nunca nome/IP/rota);
  - a ficha por usuário para no nível de FEATURE — nunca expõe query/conteúdo;
  - o dia de agrupamento é o dia BRT (UTC-3), lendo os dois arquivos UTC.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from motor_expansao.api import relatorio_acessos as rel
from motor_expansao.dashboard import acesso_analytics as aa
from motor_expansao.dashboard import acesso_log

AGORA = datetime(2026, 8, 19, 15, 0, tzinfo=UTC)  # 12:00 BRT de 2026-08-19


def _gravar(base: Path, quando: datetime, **campos: object) -> None:
    linha = {
        "quando": quando.isoformat(timespec="seconds"),
        "usuario": "felipe",
        "rota": "/api/uf/SP",
        "metodo": "GET",
        "status": 200,
        "duracao_ms": 100,
        "ip": "10.0.0.1",
        **campos,
    }
    base.mkdir(parents=True, exist_ok=True)
    arquivo = base / f"acesso-{quando.date().isoformat()}.jsonl"
    with arquivo.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")


# --- filtro compartilhado com o relatório do Telegram --------------------------


def test_painel_fora_das_metricas_nas_duas_superficies(tmp_path: Path) -> None:
    """/api/acessos/* é auditado na trilha mas invisível no resumo E no Telegram."""
    _gravar(tmp_path, AGORA, rota="/api/acessos/resumo")
    _gravar(tmp_path, AGORA, rota="/api/acessos/usuario/ana")
    _gravar(tmp_path, AGORA, rota="/api/ponto")

    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    assert r["hoje"]["acoes"] == 1  # só o /api/ponto

    linhas = (tmp_path / f"acesso-{AGORA.date().isoformat()}.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    agregado = rel.agregar_acessos(linhas, dia_brt=(AGORA + rel._FUSO_BRT).date())
    assert agregado["felipe"]["acoes"] == 1  # o gerador do bot usa o MESMO filtro


def test_curl_de_diagnostico_fora_das_metricas(tmp_path: Path) -> None:
    _gravar(tmp_path, AGORA, agente="curl/8.5.0")
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    assert r["hoje"]["acoes"] == 0


def test_prefixo_do_painel_bate_com_o_filtro() -> None:
    """Anti-drift REAL: o prefixo do guard (acesso.py) deriva do filtro de métrica —
    se um dos dois mudar sozinho, este teste aponta (não compara literal consigo)."""
    import sys

    server = Path(__file__).resolve().parents[2] / "web" / "server"
    if str(server) not in sys.path:
        sys.path.insert(0, str(server))
    import acesso  # noqa: PLC0415

    assert acesso.PREFIXO_ROTAS_ACESSOS.startswith(rel.ROTAS_FORA_DA_METRICA), (
        "toda rota que o guard protege tem de estar fora das métricas"
    )
    assert not rel.evento_valido({"rota": acesso.PREFIXO_ROTAS_ACESSOS + "resumo"})
    assert not rel.evento_valido({"rota": "/api/acessos/usuario/ana"})
    assert rel.evento_valido({"rota": "/api/ponto"})


# --- dia BRT -------------------------------------------------------------------


def test_evento_da_madrugada_utc_pertence_ao_dia_brt_anterior(tmp_path: Path) -> None:
    """01:00 UTC do dia 19 = 22:00 BRT do dia 18 — vive no arquivo do 19, conta no 18."""
    _gravar(tmp_path, datetime(2026, 8, 19, 1, 0, tzinfo=UTC), usuario="ana")
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    assert r["hoje"]["acoes"] == 0  # nada no dia 19 BRT
    ontem = [d for d in r["serie"] if d["dia"] == "2026-08-18"]
    assert ontem and ontem[0]["acoes"] == 1


def test_heatmap_usa_hora_e_dia_da_semana_brt(tmp_path: Path) -> None:
    # 2026-08-19 é quarta-feira; 15:00 UTC = 12:00 BRT -> heatmap[2][12].
    _gravar(tmp_path, AGORA)
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    assert r["heatmap"][2][12] == 1
    assert sum(sum(linha) for linha in r["heatmap"]) == 1


# --- rollup sem dado pessoal ---------------------------------------------------


def test_rollup_consolida_so_dias_fechados_e_e_idempotente(tmp_path: Path) -> None:
    _gravar(tmp_path, AGORA - timedelta(days=1), usuario="ana")
    _gravar(tmp_path, AGORA)  # hoje: dia ABERTO, não entra no rollup
    novos = aa.consolidar_rollup(tmp_path, agora_utc=AGORA)
    assert novos >= 1
    dias = json.loads(aa.caminho_rollup(tmp_path).read_text(encoding="utf-8"))["dias"]
    assert "2026-08-18" in dias
    assert AGORA.date().isoformat() not in dias
    assert aa.consolidar_rollup(tmp_path, agora_utc=AGORA) == 0  # idempotente


def test_rollup_nao_carrega_dado_pessoal(tmp_path: Path) -> None:
    _gravar(tmp_path, AGORA - timedelta(days=1), usuario="ana_souza", ip="200.1.2.3")
    aa.consolidar_rollup(tmp_path, agora_utc=AGORA)
    bruto = aa.caminho_rollup(tmp_path).read_text(encoding="utf-8")
    assert "ana_souza" not in bruto
    assert "200.1.2.3" not in bruto
    assert "/api/" not in bruto  # nem rota: só contagens por aba
    info = json.loads(bruto)["dias"]["2026-08-18"]
    assert info["acoes"] == 1 and info["usuarios"] == 1 and info["por_aba"] == {"mapa": 1}


def test_rollup_e_write_once_o_historico_sobrevive_a_poda(tmp_path: Path) -> None:
    """Dia consolidado não é recalculado: apagar a trilha (poda) não zera o número."""
    _gravar(tmp_path, AGORA - timedelta(days=1), usuario="ana")
    aa.consolidar_rollup(tmp_path, agora_utc=AGORA)
    # A poda leva o arquivo embora...
    (tmp_path / "acesso-2026-08-18.jsonl").unlink()
    (tmp_path / "acesso-2026-08-19.jsonl").unlink(missing_ok=True)
    _gravar(tmp_path, AGORA)  # trilha nova só com hoje
    aa.consolidar_rollup(tmp_path, agora_utc=AGORA)
    dias = json.loads(aa.caminho_rollup(tmp_path).read_text(encoding="utf-8"))["dias"]
    assert dias["2026-08-18"]["acoes"] == 1  # ...e o histórico fica de pé


def test_arquivo_do_rollup_escapa_da_poda_da_trilha(tmp_path: Path) -> None:
    """O nome `uso-diario.json` NÃO casa com o padrão `acesso-*.jsonl` da poda."""
    _gravar(tmp_path, AGORA - timedelta(days=1))
    aa.consolidar_rollup(tmp_path, agora_utc=AGORA)
    assert aa.caminho_rollup(tmp_path).exists()
    acesso_log._podar(tmp_path, AGORA.date() + timedelta(days=400))
    assert aa.caminho_rollup(tmp_path).exists()  # poda levou os jsonl, não o rollup
    assert not list(tmp_path.glob("acesso-*.jsonl"))


def test_rollup_corrompido_e_quarentenado_nunca_sobrescrito(tmp_path: Path) -> None:
    """Conteúdo inválido NÃO vira '{}' silencioso (isso reescreveria o arquivo e
    destruiria o histórico além dos 90 dias — defeito da revisão adversarial):
    o arquivo vai para quarentena com os bytes preservados e a rodada não grava."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    aa.caminho_rollup(tmp_path).write_text("{ nao e json", encoding="utf-8")
    _gravar(tmp_path, AGORA - timedelta(days=1))
    assert aa.consolidar_rollup(tmp_path, agora_utc=AGORA) == 0  # rodada aborta
    quarentena = tmp_path / (aa.ROLLUP_ARQUIVO + ".corrompido")
    assert quarentena.read_text(encoding="utf-8") == "{ nao e json"
    assert not aa.caminho_rollup(tmp_path).exists()
    # A rodada SEGUINTE parte de 'ausente' e reconstrói o que a trilha ainda tem.
    assert aa.consolidar_rollup(tmp_path, agora_utc=AGORA) >= 1
    assert aa.caminho_rollup(tmp_path).exists()


def test_rollup_ilegivel_por_io_nao_e_tocado(tmp_path: Path, monkeypatch) -> None:
    """OSError de leitura com o arquivo VÁLIDO no disco (soluço de volume) não pode
    quarentenar nem sobrescrever nada — só abortar e tentar na próxima."""
    _gravar(tmp_path, AGORA - timedelta(days=2), usuario="ana")
    aa.consolidar_rollup(tmp_path, agora_utc=AGORA)
    conteudo_original = aa.caminho_rollup(tmp_path).read_text(encoding="utf-8")

    original = Path.read_text

    def _falha_no_rollup(self: Path, *args, **kwargs):
        if self.name == aa.ROLLUP_ARQUIVO:
            raise PermissionError("soluço de IO")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _falha_no_rollup)
    _gravar(tmp_path, AGORA - timedelta(days=1), usuario="bia")
    assert aa.consolidar_rollup(tmp_path, agora_utc=AGORA) == 0
    monkeypatch.undo()
    assert aa.caminho_rollup(tmp_path).read_text(encoding="utf-8") == conteudo_original
    assert not (tmp_path / (aa.ROLLUP_ARQUIVO + ".corrompido")).exists()


def test_entrada_estranha_no_rollup_nao_derruba_o_resumo_e_e_preservada(
    tmp_path: Path,
) -> None:
    """JSON válido com entrada lixo (edição manual): a série ignora a entrada em vez
    de explodir em date.fromisoformat, e a consolidação NÃO a apaga (só soma dias)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    aa.caminho_rollup(tmp_path).write_text(
        json.dumps({"_versao": 1, "dias": {"nota-do-felipe": "lembrete", "2026-08-17": {"acoes": 3, "usuarios": 1, "por_aba": {}}, "2026-08-18": "quebrado"}}),
        encoding="utf-8",
    )
    _gravar(tmp_path, AGORA)
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)  # não pode levantar
    assert any(d["dia"] == "2026-08-17" and d["acoes"] == 3 for d in r["serie"])
    persistido = json.loads(aa.caminho_rollup(tmp_path).read_text(encoding="utf-8"))
    assert persistido["dias"]["nota-do-felipe"] == "lembrete"  # preservada


def test_trilha_ilegivel_nao_congela_subcontagem_no_write_once(tmp_path: Path) -> None:
    """Arquivo da trilha EXISTENTE mas ilegível (aqui: um diretório com o nome do
    jsonl) torna a janela não-confiável: o dia é PULADO e consolidado depois,
    completo — nunca um número parcial congelado para sempre."""
    _gravar(tmp_path, AGORA - timedelta(days=1), usuario="ana")  # evento real do dia 18
    intruso = tmp_path / "acesso-2026-08-18.jsonl"
    conteudo = intruso.read_text(encoding="utf-8")
    intruso.unlink()
    intruso.mkdir()  # read_text -> OSError (existe, mas não é legível como arquivo)
    assert aa.consolidar_rollup(tmp_path, agora_utc=AGORA) == 0
    intruso.rmdir()
    intruso.write_text(conteudo, encoding="utf-8")
    assert aa.consolidar_rollup(tmp_path, agora_utc=AGORA) == 1
    dias = json.loads(aa.caminho_rollup(tmp_path).read_text(encoding="utf-8"))["dias"]
    assert dias["2026-08-18"]["acoes"] == 1


def test_dia_sem_arquivo_proprio_nao_e_consolidado_pelo_transbordo(tmp_path: Path) -> None:
    """Só o arquivo do dia SEGUINTE presente (o próprio já podado, na borda da
    retenção): consolidar o dia D só com as 3h de transbordo congelaria uma
    subcontagem — D fica fora do rollup (a série o zera por gap-fill)."""
    # Evento de 01:00 UTC do dia 18 = 22:00 BRT do dia 17; arquivo do dia 17 não existe.
    _gravar(tmp_path, datetime(2026, 8, 18, 1, 0, tzinfo=UTC), usuario="ana")
    aa.consolidar_rollup(tmp_path, agora_utc=AGORA)
    dias = json.loads(aa.caminho_rollup(tmp_path).read_text(encoding="utf-8"))["dias"]
    assert "2026-08-17" not in dias  # sem arquivo próprio, não congela parcial
    assert "2026-08-18" in dias


def test_resumo_propaga_o_relogio_injetado_para_a_consolidacao(tmp_path: Path) -> None:
    """`resumo(agora_utc=passado)` não pode consolidar (write-once!) um dia que,
    para o chamador, ainda está aberto."""
    _gravar(tmp_path, AGORA, usuario="ana")  # dia 19: aberto segundo AGORA
    aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    if aa.caminho_rollup(tmp_path).exists():
        dias = json.loads(aa.caminho_rollup(tmp_path).read_text(encoding="utf-8"))["dias"]
        assert AGORA.date().isoformat() not in dias


def test_serie_cai_para_contagem_viva_quando_o_rollup_nao_grava(
    tmp_path: Path, monkeypatch,
) -> None:
    """Volume sem escrita: a série não pode mostrar zero num dia fechado cuja
    atividade está visível na própria janela — cai para a contagem ao vivo."""
    monkeypatch.setattr(aa, "_gravar_rollup", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    _gravar(tmp_path, AGORA - timedelta(days=1), usuario="ana")
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    ontem = next(d for d in r["serie"] if d["dia"] == "2026-08-18")
    assert ontem["acoes"] == 1 and ontem["usuarios"] == 1


def test_virada_de_dia_da_trilha_consolida_antes_da_poda(tmp_path: Path, monkeypatch) -> None:
    """O hook registrado em acesso_log dispara a consolidação na MESMA cadência da
    poda — app 90 dias de pé sem abertura da aba não perde dia (defeito da revisão)."""
    monkeypatch.setattr(acesso_log, "_ultimo_dia_podado", None)
    _gravar(tmp_path, AGORA - timedelta(days=1), usuario="ana")
    acesso_log.registrar({"usuario": "ana", "rota": "/api/ponto"}, base=tmp_path)
    assert aa.caminho_rollup(tmp_path).exists(), (
        "a virada de dia do registrar() deveria ter consolidado o rollup via hook"
    )
    assert aa.consolidar_rollup_seguro in acesso_log._hooks_virada_de_dia


def test_consolidar_seguro_nunca_levanta(monkeypatch) -> None:
    monkeypatch.setattr(aa, "consolidar_rollup", lambda *a, **k: 1 / 0)
    assert aa.consolidar_rollup_seguro() == 0


def test_serie_preenche_dia_sem_arquivo_com_zero(tmp_path: Path) -> None:
    _gravar(tmp_path, AGORA - timedelta(days=3), usuario="ana")
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    dias_da_serie = [d["dia"] for d in r["serie"]]
    assert dias_da_serie == sorted(dias_da_serie)
    # Entre o dia consolidado e hoje não pode haver buraco de datas.
    assert "2026-08-17" in dias_da_serie and "2026-08-18" in dias_da_serie
    zerado = next(d for d in r["serie"] if d["dia"] == "2026-08-17")
    assert zerado["acoes"] == 0


# --- resumo e ficha ------------------------------------------------------------


def test_resumo_agrupa_por_usuario_e_aba(tmp_path: Path) -> None:
    _gravar(tmp_path, AGORA, usuario="felipe", rota="/api/simulador/xlsx")
    _gravar(tmp_path, AGORA, usuario="felipe", rota="/api/ponto", query="lat=-8.1&lng=-34.9")
    _gravar(tmp_path, AGORA, usuario="ana", rota="/api/rede/carteira", ip="10.0.0.2")
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    assert r["hoje"]["usuarios"] == 2
    linhas = {u["nome"]: u for u in r["usuarios"]}
    assert linhas["felipe"]["acoes"] == 2
    assert linhas["felipe"]["abas"] == ["Mapa", "Viabilidade"]
    assert linhas["ana"]["abas"] == ["Executiva"]
    assert linhas["ana"]["ips"] == 1
    # Promessa (b) da emenda, no payload INTEIRO: IP bruto e query nunca saem.
    bruto = json.dumps(r, ensure_ascii=False, default=str)
    assert "10.0.0.1" not in bruto and "10.0.0.2" not in bruto
    assert "lat=-8.1" not in bruto


def test_janela_e_limitada_ao_teto_da_trilha(tmp_path: Path) -> None:
    r = aa.resumo(tmp_path, dias=5000, agora_utc=AGORA)
    assert r["janela_dias"] == aa.JANELA_DIAS_MAX


def test_ficha_traz_features_e_nunca_a_query(tmp_path: Path) -> None:
    _gravar(
        tmp_path,
        AGORA,
        rota="/api/geocode",
        query="q=Rua+Sigilosa+123+Recife",  # o CONTEÚDO que a emenda promete esconder
    )
    _gravar(tmp_path, AGORA, rota="/api/relatorio/pontual", metodo="POST")
    ficha = aa.ficha_usuario("felipe", tmp_path, dias=7, agora_utc=AGORA)
    assert ficha is not None
    features = {f["feature"] for f in ficha["features"]}
    assert features == {"Buscou endereço", "Gerou relatório pontual"}
    bruto = json.dumps(ficha, ensure_ascii=False, default=str)
    assert "Sigilosa" not in bruto
    assert "10.0.0.1" not in bruto  # IP bruto nunca sai — só a contagem `ips`
    assert ficha["dias"][0]["ini"] == "12:00" and ficha["dias"][0]["acoes"] == 2


def test_ficha_de_usuario_sem_atividade_e_none(tmp_path: Path) -> None:
    _gravar(tmp_path, AGORA, usuario="ana")
    assert aa.ficha_usuario("zeca", tmp_path, dias=7, agora_utc=AGORA) is None


def test_put_do_cadastro_e_feature_propria() -> None:
    assert (
        aa._feature_do_evento({"metodo": "PUT", "rota": "/api/rede/cadastro/u1"})
        == "Editou cadastro de unidade"
    )
    assert (
        aa._feature_do_evento({"metodo": "GET", "rota": "/api/rede/carteira"})
        == "Consultou carteira da rede"
    )


def test_toda_rota_com_regra_de_acesso_tem_rotulo_de_feature() -> None:
    """Anti-drift: rota nova em REGRAS_DE_ACESSO sem rótulo cairia em 'Outras ações'
    em silêncio — este teste obriga a decisão."""
    import sys

    server = Path(__file__).resolve().parents[2] / "web" / "server"
    if str(server) not in sys.path:
        sys.path.insert(0, str(server))
    import acesso  # noqa: PLC0415

    for prefixo, _abas in acesso.REGRAS_DE_ACESSO:
        rotulo = aa._feature_do_evento({"metodo": "GET", "rota": prefixo + "x"})
        assert rotulo != "Outras ações", f"prefixo sem rótulo de feature: {prefixo}"


def test_saude_conta_erros_e_p95(tmp_path: Path) -> None:
    for i in range(6):
        _gravar(tmp_path, AGORA, rota="/api/ponto", duracao_ms=100 + i * 100)
    _gravar(tmp_path, AGORA, rota="/api/uf/SP", status=500)
    _gravar(tmp_path, AGORA, rota="/api/rede/carteira", status=403)
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    assert r["saude"]["erros_5xx"] == 1
    assert r["saude"]["erros_4xx"] == 1
    lentas = {item["rota"]: item for item in r["saude"]["lentas"]}
    assert "/api/ponto" in lentas and lentas["/api/ponto"]["n"] == 6


def test_linha_ilegivel_e_ignorada(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    arq = tmp_path / f"acesso-{AGORA.date().isoformat()}.jsonl"
    arq.write_text('{"quando": corrompido\n[1,2,3]\n', encoding="utf-8")
    _gravar(tmp_path, AGORA)
    r = aa.resumo(tmp_path, dias=7, agora_utc=AGORA)
    assert r["hoje"]["acoes"] == 1


def test_diretorio_inexistente_devolve_resumo_vazio(tmp_path: Path) -> None:
    r = aa.resumo(tmp_path / "nao_existe", dias=7, agora_utc=AGORA)
    assert r["hoje"]["acoes"] == 0 and r["usuarios"] == []


def test_dias_utc_da_janela_cobrem_o_transbordo() -> None:
    dias = aa._dias_utc_para_janela_brt(date(2026, 8, 18), date(2026, 8, 19))
    assert dias == [date(2026, 8, 18), date(2026, 8, 19), date(2026, 8, 20)]
