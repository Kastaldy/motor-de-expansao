"""Controle TEMPORARIO de acesso por aba do piloto web (pedido do Felipe, 2026-08-13).

O Authelia AUTENTICA (quem entra no piloto); este modulo AUTORIZA (que aba cada
usuario pode usar). O usuario chega no header `Remote-User`, que o Caddy ja repassa
atras do Authelia — nao ha sessao propria nem banco. A solucao definitiva e' o banco
de identidade (plano de 2026-08-07); este modulo existe para morrer quando ele chegar.

O mapa `usuario -> [abas]` vive num JSON EDITAVEL EM PRODUCAO, no volume `:rw` do
cadastro (DEC-023) — trocar o acesso de alguem nao exige rebuild nem deploy, so'
editar o arquivo (relido a cada mudanca de mtime).

Regras de degradacao (fail-open DE PROPOSITO):
  - SEM arquivo (dev local, mount ausente)  -> todas as abas para todos.
  - Arquivo ilegivel / JSON invalido        -> todas as abas para todos + warning.
    Um typo no JSON nao pode trancar o piloto inteiro para o time; o preco e' que o
    typo tambem devolve acesso cheio — por isso o passo de deploy VALIDA o JSON.
  - Arquivo ok e usuario fora do mapa       -> entrada "*" se existir; senao NENHUMA.

READ-ONLY sobre o M1: este modulo so' le um JSON de configuracao; nao toca dado.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

_LOG = logging.getLogger("piloto.acesso")

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]

# Valores brutos de aba — identificadores SEM acento (regra do CLAUDE.md §2). A SPA
# usa exatamente estes nomes em `web/src/lib/acesso.ts`; mudou aqui, muda la' junto.
ABAS_VALIDAS = frozenset({"executiva", "mapa", "oportunidades", "viabilidade"})

# Que abas LIBERAM cada rota (basta ter UMA delas). Casamento por PREFIXO do path.
# Rota sem regra = livre para qualquer usuario autenticado (health, catalogos, /api/me);
# o teste de cobertura em tests/unit/test_piloto_web_acesso.py obriga toda rota nova
# do app a aparecer aqui OU na lista explicita de rotas livres.
#
# A aba "mapa" cobre tambem o modo de PONTO (tela 'ponto' = Explorar + ficha por cima).
# `/api/viabilidade` aceita mapa OU viabilidade porque o BlocoViabilidadePonto (modo de
# ponto) chama a mesma rota que a tela de Viabilidade. `/api/relatorio/pontual` idem:
# e' disparado pela tela de Viabilidade, alcancavel a partir do mapa.
REGRAS_DE_ACESSO: tuple[tuple[str, frozenset[str]], ...] = (
    ("/api/rede/", frozenset({"executiva"})),
    ("/api/executiva/", frozenset({"executiva"})),
    ("/api/geocode", frozenset({"mapa"})),
    ("/api/resolver-ponto", frozenset({"mapa"})),
    ("/api/ponto", frozenset({"mapa"})),
    ("/api/cobertura/", frozenset({"mapa"})),
    ("/api/relatorio/municipal", frozenset({"mapa"})),
    ("/api/relatorio/pontual", frozenset({"mapa", "viabilidade"})),
    ("/api/viabilidade", frozenset({"mapa", "viabilidade"})),
    ("/api/faixa-alunos", frozenset({"viabilidade"})),
    ("/api/simulador/", frozenset({"viabilidade"})),
    ("/api/uf/", frozenset({"mapa", "oportunidades"})),
    ("/api/municipio/", frozenset({"mapa", "oportunidades"})),
    ("/api/municipios/", frozenset({"mapa", "oportunidades"})),
    ("/api/estados", frozenset({"oportunidades"})),
)

# Rotas /api/* deliberadamente livres (qualquer usuario autenticado):
#   /api/health      — healthcheck do container (curl interno, sem Remote-User)
#   /api/ufs         — catalogo de UFs, carregado pelo App antes de saber a tela
#   /api/metodologia — manual do funil, conteudo explicativo sem dado sensivel
#   /api/me          — e' a rota que DIZ a SPA o que esconder
ROTAS_LIVRES = frozenset({"/api/health", "/api/ufs", "/api/metodologia", "/api/me"})


def caminho_do_mapa() -> Path:
    """Onde mora o JSON `usuario -> [abas]`.

    Default: `acesso_abas.json` dentro do MESMO volume `:rw` do cadastro (DEC-023) —
    em producao, `/opt/motor-expansao/cadastro/acesso_abas.json`. Override por env
    `MOTOR_ACESSO_ABAS_PATH` (testes e casos especiais).
    """
    explicito = os.environ.get("MOTOR_ACESSO_ABAS_PATH")
    if explicito:
        return Path(explicito)
    cadastro = Path(os.environ.get("MOTOR_CADASTRO_DIR", str(_REPO_ROOT / "data" / "cadastro")))
    return cadastro / "acesso_abas.json"


# Cache do parse, invalidado por (caminho, mtime): editar o arquivo em producao vale
# na requisicao seguinte, sem restart e sem custo de reparse a cada request.
_cache: tuple[str, int, dict[str, frozenset[str]]] | None = None


def _ler_mapa() -> dict[str, frozenset[str]] | None:
    """`None` = controle DESLIGADO (fail-open); dict = controle ativo."""
    global _cache
    path = caminho_do_mapa()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        _cache = None
        return None

    if _cache is not None and _cache[0] == str(path) and _cache[1] == mtime:
        return _cache[2]

    try:
        bruto = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(bruto, dict):
            raise ValueError("a raiz do JSON deve ser um objeto usuario -> [abas]")
        mapa: dict[str, frozenset[str]] = {}
        for usuario, abas in bruto.items():
            if usuario.startswith("_"):
                continue  # chave de comentario ("_comentario": "...")
            if not isinstance(abas, list):
                raise ValueError(f"as abas de {usuario!r} devem ser uma lista")
            # Aba desconhecida e' descartada em silencio aqui, mas o deploy valida.
            mapa[usuario] = frozenset(a for a in abas if a in ABAS_VALIDAS)
    except (OSError, ValueError) as erro:
        _LOG.warning(
            "acesso_abas.json ilegivel (%s) — controle de abas DESLIGADO (fail-open)",
            erro,
        )
        _cache = None
        return None

    _cache = (str(path), mtime, mapa)
    return mapa


def normalizar_usuario(valor: object) -> str | None:
    """Primeiro valor string nao vazio, ou None.

    Mesmo racional do `_autor` do app: chamada direta da rota (suite sem TestClient)
    entrega o proprio objeto `Header` como default, e ele nao pode virar um usuario.
    """
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    return None


def abas_do_usuario(usuario: str | None) -> frozenset[str]:
    """Abas que este usuario pode usar, segundo o JSON vigente."""
    mapa = _ler_mapa()
    if mapa is None:
        return ABAS_VALIDAS
    if usuario is not None and usuario in mapa:
        return mapa[usuario]
    return mapa.get("*", frozenset())


def abas_necessarias(path: str) -> frozenset[str] | None:
    """Abas que liberam esta rota; `None` = rota sem controle."""
    for prefixo, abas in REGRAS_DE_ACESSO:
        if path.startswith(prefixo):
            return abas
    return None


def motivo_bloqueio(path: str, usuario: object) -> str | None:
    """`None` = pode passar; string = detail do 403 que o middleware devolve."""
    necessarias = abas_necessarias(path)
    if necessarias is None:
        return None
    if necessarias & abas_do_usuario(normalizar_usuario(usuario)):
        return None
    return "Seu usuário não tem acesso a esta área do piloto. Fale com o Felipe."
