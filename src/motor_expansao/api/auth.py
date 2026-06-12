"""Autenticacao por token de portador (Decisao 2 / BLK-API-02).

Valida o header ``Authorization: Bearer <token>`` e resolve o **consumidor**
(ex.: ``bot-telegram``) pelo mapa estatico em `Settings`. O consumidor e
carimbado no JSON de resposta para rastreio (LGPD / BLK-EST-01).

Aplicada como dependencia em todas as rotas exceto `GET /health`:
- token ausente/invalido -> ``401`` ``nao_autenticado``;
- token valido sem permissao -> ``403`` ``sem_permissao`` (reservado para quando
  houver escopos por consumidor; no MVP todo token valido tem acesso).
"""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from motor_expansao.api.errors import APIError
from motor_expansao.api.settings import Settings, get_settings

# auto_error=False: nos mesmos devolvemos o corpo padrao {detail, codigo}.
_bearer = HTTPBearer(auto_error=False, description="Token de portador por consumidor.")


def resolver_consumidor(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> str:
    """Resolve o consumidor a partir do Bearer token. Levanta `APIError` 401."""
    token = credentials.credentials if credentials else None
    if not token:
        raise APIError(401, "Token invalido", "nao_autenticado")

    consumidor = settings.tokens.get(token)
    if consumidor is None:
        raise APIError(401, "Token invalido", "nao_autenticado")

    return consumidor
