"""Analytics da aba Acessos do piloto — agregações da trilha + rollup sem dado pessoal.

Camada de LEITURA da trilha de acesso (DEC-027, emenda de 2026-08-19) que alimenta a
aba `Acessos` do piloto — restrita por allowlist de usuário (env
`MOTOR_ACESSOS_ADMIN_USUARIOS`; o guard vive em `web/server/acesso.py`).

O que este módulo entrega (e o corte deliberado do que NÃO entrega):
  - agregados (série diária, heatmap hora×dia, distribuição por aba, saúde);
  - por usuário: janelas de atividade, abas e contagem de ações por FEATURE
    ("rodou simulador 4x") — nunca a query/conteúdo (o endereço pesquisado, os
    parâmetros da simulação). O detalhe fino continua só na trilha bruta.

ROLLUP DIÁRIO SEM DADO PESSOAL (`uso-diario.json`, no mesmo diretório da trilha):
a trilha se poda em 90 dias (DEC-027); para tendência longa, cada dia BRT FECHADO é
consolidado UMA vez em `{dia: {acoes, usuarios, por_aba}}` — contagens apenas, sem
nome, sem IP, sem rota — e nunca recalculado (fica estável mesmo depois da poda).
A consolidação roda no startup do app e a cada abertura da aba; o nome do arquivo
NÃO casa com o padrão de poda `acesso-*.jsonl` de propósito.

Consistência com o relatório do Telegram: o filtro de evento (`evento_valido`) e o
mapa rota->aba são IMPORTADOS de `motor_expansao.api.relatorio_acessos` — os acessos
do próprio painel (`/api/acessos/*`) ficam fora das métricas NOS DOIS, pelo mesmo
código (auditados na trilha, invisíveis nas contagens).

READ-ONLY sobre o M1: lê a trilha e escreve APENAS o rollup, no diretório próprio da
trilha (fora do MOTOR_DATA_DIR). O app.py continua sem escritor de FS (guardrail AST).
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from motor_expansao.api.relatorio_acessos import (
    _FUSO_BRT,
    LABEL_ABA,
    _aba_da_rota,
    _quando_brt,
    evento_valido,
)
from motor_expansao.dashboard import acesso_log
from motor_expansao.dashboard.acesso_log import (
    PREFIXO_ARQUIVO,
    SUFIXO_ARQUIVO,
    acesso_log_dir,
)

ROLLUP_ARQUIVO = "uso-diario.json"
ROLLUP_VERSAO = 1

#: Janela padrão e teto das agregações detalhadas (a trilha só guarda 90 dias).
JANELA_DIAS_DEFAULT = 30
JANELA_DIAS_MAX = 90

#: Rota -> rótulo de FEATURE exibido na ficha do usuário ("o quê", sem o conteúdo).
#: Prefixos mais específicos primeiro (`/api/rede/unidade/` antes de `/api/rede/`).
#: Método só quando distingue leitura de escrita (PUT do cadastro).
FEATURES_ROTULOS: tuple[tuple[str | None, str, str], ...] = (
    ("PUT", "/api/rede/cadastro/", "Editou cadastro de unidade"),
    (None, "/api/rede/unidade/", "Abriu ficha de unidade"),
    (None, "/api/rede/carteira", "Consultou carteira da rede"),
    (None, "/api/rede/", "Visão executiva da rede"),
    (None, "/api/executiva/", "Visão executiva da rede"),
    (None, "/api/relatorio/pontual", "Gerou relatório pontual"),
    (None, "/api/relatorio/municipal", "Gerou relatório municipal"),
    (None, "/api/simulador/", "Exportou simulador (XLSX)"),
    (None, "/api/viabilidade", "Rodou simulação de viabilidade"),
    (None, "/api/faixa-alunos", "Consultou faixa de alunos"),
    (None, "/api/geocode", "Buscou endereço"),
    (None, "/api/resolver-ponto", "Buscou endereço"),
    (None, "/api/ponto", "Analisou ponto no mapa"),
    (None, "/api/cobertura/", "Ligou camada de cobertura"),
    (None, "/api/uf/", "Navegou pelo mapa"),
    (None, "/api/municipio/", "Explorou município"),
    (None, "/api/municipios/", "Explorou município"),
    (None, "/api/estados", "Ranking de estados"),
    (None, "/api/metodologia", "Leu a metodologia"),
)
_FEATURE_OUTRAS = "Outras ações"

#: Pausa que fecha uma sessão na ficha do usuário (leitura de "sentou para usar").
_GAP_SESSAO = timedelta(minutes=30)
#: Teto de eventos da linha do tempo da ficha (os mais recentes).
_TETO_LINHA_DO_TEMPO = 80
#: Dias da mini-série de atividade por usuário na tabela do resumo (sparkline).
_DIAS_SPARKLINE = 14

_LOCK_ROLLUP = threading.Lock()


# ---------------------------------------------------------------------------
# Leitura e normalização de eventos da trilha
# ---------------------------------------------------------------------------


def _arquivo_do_dia_utc(diretorio: Path, dia: date) -> Path:
    return diretorio / f"{PREFIXO_ARQUIVO}{dia.isoformat()}{SUFIXO_ARQUIVO}"


def _dias_utc_para_janela_brt(primeiro_brt: date, ultimo_brt: date) -> list[date]:
    """Dias UTC cujos arquivos podem conter eventos da janela BRT [primeiro..ultimo].

    O dia BRT D vive nos arquivos UTC D e D+1 (BRT = UTC-3); a união da janela é
    [primeiro .. ultimo+1] em dias UTC.
    """
    n = (ultimo_brt - primeiro_brt).days + 2
    return [primeiro_brt + timedelta(days=i) for i in range(n)]


def _eventos_da_janela(
    diretorio: Path, primeiro_brt: date, ultimo_brt: date
) -> tuple[list[dict[str, Any]], bool]:
    """Eventos válidos da janela BRT (com `momento` BRT e `aba`) + flag de confiança.

    Linha ilegível é ignorada (a trilha é rastro, não transação). O filtro de
    validade (`evento_valido`) é o MESMO do relatório do Telegram. O segundo item
    é `False` quando algum arquivo da janela EXISTE mas não pôde ser lido (IO/
    permissão) — a janela está incompleta e a consolidação write-once não deve
    congelar uma subcontagem (defeito da revisão adversarial de 2026-08-19).
    Arquivo simplesmente ausente é normal (dia sem tráfego) e não derruba a flag.
    """
    eventos: list[dict[str, Any]] = []
    confiavel = True
    for dia_utc in _dias_utc_para_janela_brt(primeiro_brt, ultimo_brt):
        arquivo = _arquivo_do_dia_utc(diretorio, dia_utc)
        try:
            linhas = arquivo.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            continue
        except OSError:
            confiavel = False
            continue
        for bruta in linhas:
            try:
                r = json.loads(bruta)
            except (ValueError, TypeError):
                continue
            if not evento_valido(r):
                continue
            momento = _quando_brt(r.get("quando"))
            if momento is None or not (primeiro_brt <= momento.date() <= ultimo_brt):
                continue
            r["momento"] = momento
            r["aba"] = _aba_da_rota(str(r.get("rota", "")))
            eventos.append(r)
    return eventos, confiavel


def _feature_do_evento(r: dict[str, Any]) -> str:
    metodo = str(r.get("metodo") or "").upper()
    rota = str(r.get("rota") or "")
    for metodo_regra, prefixo, rotulo in FEATURES_ROTULOS:
        if metodo_regra is not None and metodo != metodo_regra:
            continue
        if rota.startswith(prefixo):
            return rotulo
    return _FEATURE_OUTRAS


def _hhmm(momento: object) -> str | None:
    return momento.strftime("%H:%M") if isinstance(momento, datetime) else None


# ---------------------------------------------------------------------------
# Rollup diário sem dado pessoal (tendência além dos 90 dias da trilha)
# ---------------------------------------------------------------------------


def caminho_rollup(diretorio: Path | None = None) -> Path:
    return (diretorio or acesso_log_dir()) / ROLLUP_ARQUIVO


#: Um aviso por processo quando o rollup for quarentenado (mesmo padrão da trilha).
_avisou_rollup_corrompido = False


def _carregar_rollup(diretorio: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    """`('ok'|'ausente'|'ilegivel'|'corrompido', dias)`.

    A distinção importa (revisão adversarial de 2026-08-19): tratar QUALQUER falha
    como "vazio" fazia a consolidação REESCREVER o arquivo só com os dias que ainda
    sobrevivem na trilha de 90 dias — destruindo o histórico longo em silêncio.
    `ilegivel` = OSError com o arquivo existindo (soluço de IO: não tocar, tentar
    depois); `corrompido` = conteúdo inválido (quarentenar, nunca sobrescrever).
    """
    caminho = caminho_rollup(diretorio)
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "ausente", {}
    except OSError:
        return "ilegivel", {}
    except ValueError:
        return "corrompido", {}
    dias = bruto.get("dias") if isinstance(bruto, dict) else None
    if not isinstance(dias, dict):
        return "corrompido", {}
    return "ok", dias


def _entradas_validas(dias: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Só entradas com chave-data ISO e valor dict — entrada estranha (edição manual)
    não pode derrubar a série com 500; na regravação ela é PRESERVADA (só se soma)."""
    validas: dict[str, dict[str, Any]] = {}
    for chave, info in dias.items():
        if not isinstance(info, dict):
            continue
        try:
            date.fromisoformat(str(chave))
        except (TypeError, ValueError):
            continue
        validas[str(chave)] = info
    return validas


def _quarentenar_rollup(diretorio: Path) -> None:
    """Renomeia o rollup corrompido para `.corrompido` (bytes preservados para
    recuperação manual) e avisa uma vez no stderr. A próxima consolidação parte de
    'ausente' e reconstrói o que a trilha ainda tem — nada é sobrescrito às cegas."""
    global _avisou_rollup_corrompido
    destino = caminho_rollup(diretorio)
    try:
        os.replace(destino, destino.with_name(destino.name + ".corrompido"))
    except OSError:
        return  # não conseguiu nem quarentenar: não toca em nada, tenta depois
    if not _avisou_rollup_corrompido:
        print(
            f"[acesso_analytics] rollup corrompido movido para {destino.name}.corrompido — "
            "a série longa será reconstruída a partir da trilha vigente",
            file=sys.stderr,
        )
        _avisou_rollup_corrompido = True


def _gravar_rollup(diretorio: Path, dias: dict[str, dict[str, Any]]) -> None:
    """Escrita atômica (tmp + replace), modo 0600 — mesmo tratamento da trilha."""
    destino = caminho_rollup(diretorio)
    conteudo = json.dumps(
        {"_versao": ROLLUP_VERSAO, "dias": dict(sorted(dias.items()))},
        ensure_ascii=False,
        indent=1,
    )
    tmp = destino.with_name(destino.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(conteudo + "\n")
    os.replace(tmp, destino)


def _dia_de_rollup(eventos: list[dict[str, Any]]) -> dict[str, Any]:
    por_aba = Counter(str(r["aba"]) for r in eventos if r.get("aba"))
    return {
        "acoes": len(eventos),
        "usuarios": len({str(r.get("usuario") or "desconhecido") for r in eventos}),
        "por_aba": dict(sorted(por_aba.items())),
    }


def consolidar_rollup(diretorio: Path | None = None, agora_utc: datetime | None = None) -> int:
    """Consolida no rollup todo dia BRT FECHADO presente na trilha e ainda ausente.

    Idempotente e write-once por dia: dia já consolidado nunca é recalculado — o
    número histórico fica estável mesmo depois de a trilha ser podada. Devolve
    quantos dias novos entraram.
    """
    base = diretorio or acesso_log_dir()
    hoje_brt = ((agora_utc or datetime.now(UTC)) + _FUSO_BRT).date()

    # Um dia BRT só é candidato se o SEU arquivo UTC existir. O arquivo do dia
    # seguinte (que carrega 21h-24h BRT) é lido junto quando presente; mas
    # consolidar um dia só pelo transbordo do vizinho congelaria uma contagem
    # parcial de 3h no write-once (ex.: o arquivo próprio já podado na borda da
    # retenção) — defeito da revisão adversarial de 2026-08-19.
    candidatos: set[date] = set()
    try:
        arquivos = list(base.glob(f"{PREFIXO_ARQUIVO}*{SUFIXO_ARQUIVO}"))
    except OSError:
        return 0
    for arquivo in arquivos:
        try:
            candidatos.add(
                date.fromisoformat(arquivo.name[len(PREFIXO_ARQUIVO) : -len(SUFIXO_ARQUIVO)])
            )
        except ValueError:
            continue

    with _LOCK_ROLLUP:
        status, dias = _carregar_rollup(base)
        if status == "ilegivel":
            return 0  # soluço de IO com o arquivo lá: não sobrescrever histórico
        if status == "corrompido":
            _quarentenar_rollup(base)
            return 0  # a próxima rodada parte de 'ausente' e reconstrói
        novos = 0
        for dia in sorted(candidatos):
            if dia >= hoje_brt or dia.isoformat() in dias:
                continue  # dia aberto (ainda muda) ou já consolidado (write-once)
            eventos, confiavel = _eventos_da_janela(base, dia, dia)
            if not confiavel:
                continue  # arquivo existente mas ilegível: não congelar subcontagem
            dias[dia.isoformat()] = _dia_de_rollup(eventos)
            novos += 1
        if novos:
            _gravar_rollup(base, dias)
    return novos


def consolidar_rollup_seguro(
    diretorio: Path | None = None, agora_utc: datetime | None = None
) -> int:
    """Como `consolidar_rollup`, mas nunca levanta (startup, rota e virada de dia)."""
    try:
        return consolidar_rollup(diretorio, agora_utc=agora_utc)
    except Exception:  # noqa: BLE001 — analytics é rastro, não pode derrubar o app
        return 0


# A poda da trilha (90 dias) roda na virada de dia dentro de `acesso_log.registrar`;
# a consolidação PRECISA acontecer antes que ela alcance um dia ainda não rollupado
# (app 90+ dias sem restart e sem abertura da aba perderia dias — revisão adversarial
# de 2026-08-19). O hook amarra as duas cadências sem import circular.
acesso_log.registrar_hook_virada_de_dia(consolidar_rollup_seguro)


# ---------------------------------------------------------------------------
# Payloads da aba
# ---------------------------------------------------------------------------


def _label(aba: object) -> str:
    return LABEL_ABA.get(str(aba), str(aba))


def _p95(valores: list[int]) -> int | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[int(0.95 * (len(ordenados) - 1))]


def _saude(eventos: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(eventos)
    e4 = sum(1 for r in eventos if isinstance(r.get("status"), int) and 400 <= r["status"] < 500)
    e5 = sum(1 for r in eventos if isinstance(r.get("status"), int) and r["status"] >= 500)
    por_rota: dict[str, list[int]] = {}
    for r in eventos:
        if isinstance(r.get("duracao_ms"), int):
            por_rota.setdefault(str(r.get("rota") or "?"), []).append(int(r["duracao_ms"]))
    lentas: list[dict[str, Any]] = [
        {"rota": rota, "n": len(ds), "p95_ms": _p95(ds)}
        for rota, ds in por_rota.items()
        if len(ds) >= 5
    ]
    lentas.sort(key=lambda x: -(x["p95_ms"] or 0))
    return {
        "total": total,
        "erros_4xx": e4,
        "erros_5xx": e5,
        "taxa_erro_pct": round(100.0 * (e4 + e5) / total, 1) if total else 0.0,
        "lentas": lentas[:5],
    }


def _linhas_usuarios(
    eventos: list[dict[str, Any]], hoje: date, dias: int = _DIAS_SPARKLINE
) -> list[dict[str, Any]]:
    por_usuario: dict[str, list[dict[str, Any]]] = {}
    for r in eventos:
        por_usuario.setdefault(str(r.get("usuario") or "desconhecido"), []).append(r)
    largura_spark = min(int(dias), _DIAS_SPARKLINE)
    eixo_spark = [hoje - timedelta(days=i) for i in range(largura_spark - 1, -1, -1)]
    linhas: list[dict[str, Any]] = []
    for nome, evs in por_usuario.items():
        momentos = [r["momento"] for r in evs if isinstance(r.get("momento"), datetime)]
        ultimo = max(momentos) if momentos else None
        contagem_dias = Counter(m.date() for m in momentos)
        linhas.append(
            {
                "nome": nome,
                "ultimo_dia": ultimo.date().isoformat() if ultimo else None,
                "ultimo_hora": _hhmm(ultimo),
                "dias_ativos": len({m.date() for m in momentos}),
                "acoes": len(evs),
                "abas": sorted({_label(r["aba"]) for r in evs if r.get("aba")}),
                "ips": len({str(r.get("ip")) for r in evs if r.get("ip")}),
                # Mini-série dos últimos 14 dias (sparkline da tabela) — só contagens.
                "serie14": [contagem_dias.get(d, 0) for d in eixo_spark],
            }
        )
    linhas.sort(key=lambda x: (-(x["acoes"] or 0), x["nome"]))
    return linhas


def resumo(
    diretorio: Path | None = None,
    dias: int = JANELA_DIAS_DEFAULT,
    agora_utc: datetime | None = None,
) -> dict[str, Any]:
    """Payload completo da aba: big numbers, série, heatmap, abas, usuários, saúde."""
    base = diretorio or acesso_log_dir()
    dias = max(1, min(int(dias), JANELA_DIAS_MAX))
    agora_brt = (agora_utc or datetime.now(UTC)) + _FUSO_BRT
    hoje = agora_brt.date()
    primeiro = hoje - timedelta(days=dias - 1)

    consolidar_rollup_seguro(base, agora_utc)
    eventos, _confiavel = _eventos_da_janela(base, primeiro, hoje)
    de_hoje = [r for r in eventos if r["momento"].date() == hoje]

    # Contagens AO VIVO por dia BRT da janela: alimentam o "hoje" da série e o
    # fallback dos dias fechados que o rollup não tem (ex.: escrita indisponível) —
    # sem isso a série mostraria zero para um dia com atividade visível logo abaixo.
    vivos: dict[str, dict[str, Any]] = {}
    for r in eventos:
        d = r["momento"].date().isoformat()
        v = vivos.setdefault(d, {"acoes": 0, "usuarios": set()})
        v["acoes"] += 1
        v["usuarios"].add(str(r.get("usuario") or "desconhecido"))

    # Série longa: dias fechados vêm do rollup (sobrevivem à poda); hoje entra ao
    # vivo. Dias sem arquivo (container parado = nenhum acesso servível) entram
    # como zero para o gráfico não pular datas. Entrada estranha no rollup (edição
    # manual) é ignorada aqui — nunca um 500 (revisão adversarial de 2026-08-19).
    rollup = _entradas_validas(_carregar_rollup(base)[1])
    inicios = [date.fromisoformat(d) for d in (*rollup, *vivos)]
    serie: list[dict[str, Any]] = []
    if inicios:
        cursor = min(inicios)
        while cursor < hoje:
            chave = cursor.isoformat()
            info = rollup.get(chave)
            if info is None and chave in vivos:
                info = {"acoes": vivos[chave]["acoes"], "usuarios": len(vivos[chave]["usuarios"])}
            info = info or {}
            serie.append(
                {
                    "dia": chave,
                    "acoes": info.get("acoes", 0),
                    "usuarios": info.get("usuarios", 0),
                }
            )
            cursor += timedelta(days=1)
    serie.append(
        {
            "dia": hoje.isoformat(),
            "acoes": len(de_hoje),
            "usuarios": len({str(r.get("usuario") or "desconhecido") for r in de_hoje}),
        }
    )

    heatmap = [[0] * 24 for _ in range(7)]  # [dia da semana 0=segunda][hora BRT]
    for r in eventos:
        m = r["momento"]
        heatmap[m.weekday()][m.hour] += 1

    contagem_abas = Counter(str(r["aba"]) for r in eventos if r.get("aba"))
    usuarios_por_aba: dict[str, set[str]] = {}
    for r in eventos:
        if r.get("aba"):
            usuarios_por_aba.setdefault(str(r["aba"]), set()).add(
                str(r.get("usuario") or "desconhecido")
            )
    por_aba = [
        {"aba": _label(aba), "acoes": n, "usuarios": len(usuarios_por_aba.get(aba, ()))}
        for aba, n in contagem_abas.most_common()
    ]

    ultimo = max(
        (r for r in de_hoje), key=lambda r: r["momento"], default=None
    )
    aba_top_hoje = Counter(str(r["aba"]) for r in de_hoje if r.get("aba")).most_common(1)

    return {
        "gerado_em": agora_brt.strftime("%d/%m %H:%M"),
        "janela_dias": dias,
        "hoje": {
            "usuarios": len({str(r.get("usuario") or "desconhecido") for r in de_hoje}),
            "acoes": len(de_hoje),
            "aba_top": _label(aba_top_hoje[0][0]) if aba_top_hoje else None,
            "ultimo": (
                {"usuario": str(ultimo.get("usuario") or "desconhecido"), "hora": _hhmm(ultimo["momento"])}
                if ultimo
                else None
            ),
        },
        "serie": serie,
        "heatmap": heatmap,
        "por_aba": por_aba,
        "usuarios": _linhas_usuarios(eventos, hoje, dias),
        "saude": _saude(eventos),
    }


def ficha_usuario(
    nome: str,
    diretorio: Path | None = None,
    dias: int = JANELA_DIAS_DEFAULT,
    agora_utc: datetime | None = None,
) -> dict[str, Any] | None:
    """Drill-down de UM usuário: janelas por dia + contagem por feature.

    Nunca expõe query/conteúdo — só o rótulo da feature. `None` = sem atividade
    na janela (a rota devolve 404).
    """
    base = diretorio or acesso_log_dir()
    dias = max(1, min(int(dias), JANELA_DIAS_MAX))
    hoje = ((agora_utc or datetime.now(UTC)) + _FUSO_BRT).date()
    primeiro = hoje - timedelta(days=dias - 1)

    da_janela, _confiavel = _eventos_da_janela(base, primeiro, hoje)
    eventos = [r for r in da_janela if str(r.get("usuario") or "desconhecido") == nome]
    if not eventos:
        return None
    eventos.sort(key=lambda r: r["momento"])

    por_dia: dict[str, list[datetime]] = {}
    for r in eventos:
        por_dia.setdefault(r["momento"].date().isoformat(), []).append(r["momento"])
    linhas_dias = [
        {
            "dia": d,
            "ini": min(ms).strftime("%H:%M"),
            "fim": max(ms).strftime("%H:%M"),
            "acoes": len(ms),
        }
        for d, ms in sorted(por_dia.items(), reverse=True)
    ]

    # Sessões: sequência de ações sem pausa maior que o gap (ou virada de dia).
    # É a leitura "quando a pessoa realmente sentou para usar" — mais fiel que a
    # janela ini–fim do dia, que dilui manhã e noite numa faixa só.
    sessoes: list[dict[str, Any]] = []
    fim_anterior: datetime | None = None
    for r in eventos:
        m = r["momento"]
        nova = (
            fim_anterior is None
            or (m - fim_anterior) > _GAP_SESSAO
            or m.date() != fim_anterior.date()
        )
        if nova:
            sessoes.append(
                {"dia": m.date().isoformat(), "ini": _hhmm(m), "fim": _hhmm(m),
                 "acoes": 0, "abas": set()}
            )
        sessao = sessoes[-1]
        sessao["fim"] = _hhmm(m)
        sessao["acoes"] += 1
        if r.get("aba"):
            sessao["abas"].add(_label(r["aba"]))
        fim_anterior = m
    for sessao in sessoes:
        sessao["abas"] = sorted(sessao["abas"])
    sessoes.reverse()  # mais recente primeiro

    # Linha do tempo: os últimos N eventos como FEATURE + hora + status — o "log"
    # legível da emenda, sem rota/query/conteúdo (o corte da DEC-027 permanece).
    linha_do_tempo = [
        {
            "dia": r["momento"].date().isoformat(),
            "hora": _hhmm(r["momento"]),
            "feature": _feature_do_evento(r),
            "aba": _label(r["aba"]) if r.get("aba") else None,
            "erro": isinstance(r.get("status"), int) and r["status"] >= 400,
        }
        for r in eventos[-_TETO_LINHA_DO_TEMPO:]
    ]
    linha_do_tempo.reverse()

    heatmap = [[0] * 24 for _ in range(7)]
    for r in eventos:
        heatmap[r["momento"].weekday()][r["momento"].hour] += 1

    contagem_abas = Counter(str(r["aba"]) for r in eventos if r.get("aba"))
    erros = sum(1 for r in eventos if isinstance(r.get("status"), int) and r["status"] >= 400)

    features = Counter(_feature_do_evento(r) for r in eventos)
    ultimo = eventos[-1]["momento"]
    return {
        "nome": nome,
        "janela_dias": dias,
        "acoes": len(eventos),
        "dias_ativos": len(por_dia),
        "ultimo_dia": ultimo.date().isoformat(),
        "ultimo_hora": _hhmm(ultimo),
        "abas": sorted({_label(r["aba"]) for r in eventos if r.get("aba")}),
        "ips": len({str(r.get("ip")) for r in eventos if r.get("ip")}),
        "erros": erros,
        "dias": linhas_dias,
        "sessoes": sessoes,
        "features": [{"feature": f, "n": n} for f, n in features.most_common()],
        "por_aba": [{"aba": _label(a), "acoes": n} for a, n in contagem_abas.most_common()],
        "heatmap": heatmap,
        "linha_do_tempo": linha_do_tempo,
    }
