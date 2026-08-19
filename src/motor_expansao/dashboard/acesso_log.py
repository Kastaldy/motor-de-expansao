"""Trilha de acesso do piloto web — gravador JSONL (DEC-027).

Uma linha JSON por requisicao RELEVANTE do backend do piloto, com o autor real
(`Remote-User`, que o Caddy injeta atras do Authelia), IP de origem
(`X-Forwarded-For`), rota+query, status e latencia. E' o par de leitura do
`cadastro_log.jsonl` (DEC-023): la se audita a unica escrita; aqui, quem leu o que.

GUARDRAIS (mesmo desenho do rede_cadastro):
  - READ-ONLY sobre o M1: escreve APENAS no diretorio proprio
    (`MOTOR_ACESSO_LOG_DIR`, fora do `MOTOR_DATA_DIR`), nunca em artefato.
  - Rastro, nao transacao: falha de escrita NUNCA derruba a requisicao.

Formato: `acesso-AAAA-MM-DD.jsonl` (um arquivo por dia UTC), append-only.
Retencao: na primeira escrita de cada dia (por processo), remove arquivos com o
padrao proprio mais antigos que `MOTOR_ACESSO_RETENCAO_DIAS` (default 90). A poda
casa SOMENTE `acesso-*.jsonl` com data valida no nome — nunca outro arquivo.

Sem inflar: `relevante()` filtra o que nao diz nada sobre uso — assets estaticos
do SPA e o `/api/health` (healthcheck interno a cada 30s). Todo o resto entra.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PREFIXO_ARQUIVO = "acesso-"
SUFIXO_ARQUIVO = ".jsonl"
RETENCAO_DIAS_DEFAULT = 90

#: Tetos de tamanho por campo — trilha de acesso, nao dump de payload.
_TETO_USUARIO = 120  # mesmo teto do `autor` no cadastro_log
_TETO_IP = 64
_TETO_ROTA = 300
_TETO_QUERY = 2000  # o Relatorio Pontual manda os inputs de viabilidade na query
_TETO_AGENTE = 200

#: Rotas que nao dizem nada sobre uso humano. O `/api/health` bate a cada 30s
#: (healthcheck do compose) e afogaria a trilha com ruido de maquina.
_ROTAS_IGNORADAS = {"/api/health"}
_PREFIXOS_IGNORADOS = ("/assets/",)
#: Estaticos do SPA servidos pelo mount de raiz (js/fontes/imagens/sourcemaps).
_EXTENSOES_IGNORADAS = re.compile(
    r"\.(?:js|mjs|css|map|woff2?|ttf|otf|eot|png|jpe?g|svg|gif|ico|webp|txt)$",
    re.IGNORECASE,
)
_PADRAO_NOME = re.compile(
    rf"^{re.escape(PREFIXO_ARQUIVO)}(\d{{4}}-\d{{2}}-\d{{2}}){re.escape(SUFIXO_ARQUIVO)}$"
)

_LOCK = threading.Lock()
_ultimo_dia_podado: date | None = None
_avisou_falha = False


def acesso_log_dir() -> Path:
    """Diretorio da trilha. `MOTOR_ACESSO_LOG_DIR` manda; default = `<repo>/data/acesso_log`."""
    bruto = os.environ.get("MOTOR_ACESSO_LOG_DIR")
    if bruto:
        return Path(bruto)
    return Path(__file__).resolve().parents[3] / "data" / "acesso_log"


def retencao_dias() -> int:
    """Dias de retencao. `MOTOR_ACESSO_RETENCAO_DIAS` manda; valor invalido cai no default."""
    bruto = os.environ.get("MOTOR_ACESSO_RETENCAO_DIAS", "")
    try:
        dias = int(bruto)
    except ValueError:
        return RETENCAO_DIAS_DEFAULT
    return dias if dias > 0 else RETENCAO_DIAS_DEFAULT


def relevante(caminho: str) -> bool:
    """Se a rota merece linha na trilha (filtra estatico do SPA e healthcheck)."""
    if caminho in _ROTAS_IGNORADAS:
        return False
    if caminho.startswith(_PREFIXOS_IGNORADOS):
        return False
    return not _EXTENSOES_IGNORADAS.search(caminho)


def _texto(valor: object, teto: int) -> str | None:
    if not isinstance(valor, str):
        return None
    aparado = valor.strip()
    return aparado[:teto] if aparado else None


def _inteiro(valor: object) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return round(valor)
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def montar_evento(
    *,
    usuario: object = None,
    ip: object = None,
    metodo: object = None,
    rota: object = None,
    query: object = None,
    status: object = None,
    duracao_ms: object = None,
    agente: object = None,
    tamanho: object = None,
) -> dict[str, object]:
    """Normaliza os campos de uma requisicao numa linha da trilha (sem gravar).

    Framework-agnostico de proposito: recebe primitivos, nao Request/Response —
    testavel sem FastAPI, e o middleware fica com meia duzia de `headers.get`.
    """
    evento: dict[str, object] = {
        "usuario": _texto(usuario, _TETO_USUARIO) or "desconhecido",
        "ip": _texto(ip, _TETO_IP),
        "metodo": _texto(metodo, 16),
        "rota": _texto(rota, _TETO_ROTA),
        "status": _inteiro(status),
        "duracao_ms": _inteiro(duracao_ms),
    }
    consulta = _texto(query, _TETO_QUERY)
    if consulta:
        evento["query"] = consulta
    agente_norm = _texto(agente, _TETO_AGENTE)
    if agente_norm:
        evento["agente"] = agente_norm
    bytes_resposta = _inteiro(tamanho)
    if bytes_resposta is not None:
        evento["bytes"] = bytes_resposta
    return evento


def registrar(evento: dict[str, object], base: Path | None = None) -> None:
    """Anexa uma linha JSON a trilha do dia e, na virada de dia, poda a retencao.

    Nunca levanta: a trilha e' rastro, nao transacao — se o volume nao estiver
    montado/escrevivel, a requisicao segue e um unico aviso sai no stderr.
    """
    global _ultimo_dia_podado, _avisou_falha
    diretorio = base or acesso_log_dir()
    agora = datetime.now(UTC)
    linha = json.dumps(
        {"quando": agora.isoformat(timespec="seconds"), **evento},
        ensure_ascii=False,
        default=str,
    )
    try:
        with _LOCK:
            diretorio.mkdir(mode=0o700, parents=True, exist_ok=True)
            arquivo = diretorio / f"{PREFIXO_ARQUIVO}{agora.date().isoformat()}{SUFIXO_ARQUIVO}"
            with _abrir_para_anexar(arquivo) as fh:
                fh.write(linha + "\n")
            if _ultimo_dia_podado != agora.date():
                _podar(diretorio, agora.date())
                _ultimo_dia_podado = agora.date()
    except OSError as erro:
        if not _avisou_falha:  # um aviso por processo; depois, silencio (e' rastro)
            print(f"[acesso_log] trilha indisponivel em {diretorio}: {erro}", file=sys.stderr)
            _avisou_falha = True


def _abrir_para_anexar(arquivo: Path):
    """Append com modo 0600 na criacao: a trilha e' dado pessoal, so' dono le.

    O modo de `os.open` vale apenas quando o arquivo NASCE (depois, e' ignorado), e
    0600 sobrevive a qualquer umask usual — diferente de confiar no default 0644.
    """
    fd = os.open(arquivo, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    return os.fdopen(fd, "a", encoding="utf-8")


def _podar(diretorio: Path, hoje: date) -> None:
    """Remove APENAS `acesso-AAAA-MM-DD.jsonl` mais antigos que a retencao."""
    limite = hoje - timedelta(days=retencao_dias())
    for arquivo in diretorio.glob(f"{PREFIXO_ARQUIVO}*{SUFIXO_ARQUIVO}"):
        casamento = _PADRAO_NOME.match(arquivo.name)
        if not casamento:
            continue
        try:
            dia = date.fromisoformat(casamento.group(1))
        except ValueError:
            continue
        if dia < limite:
            try:
                arquivo.unlink()
            except OSError:
                pass  # poda e' melhor esforco; tenta de novo na proxima virada de dia
