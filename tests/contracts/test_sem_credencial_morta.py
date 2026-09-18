"""Nenhuma credencial default sobrevive no fonte — contrato, nao faxina pontual.

O `config.py` e o `conftest.py` carregavam `DATABASE_URL = postgresql+asyncpg://ultra:ultra123@...`
e `SECRET_KEY = dev-secret-key-change-in-production` desde o PostGIS de maio
(`fora_primeira_fase/api_postgis/`), que nunca subiu. Nenhuma linha de codigo os lia.

Removidos em 01/09/2026, junto com a entrada do banco de verdade. Este teste existe porque a
remocao sozinha nao segura: o esqueleto legado continua no repositorio, e reintroduzir a chave
"para o caso de precisar" e' o movimento natural de quem o encontrar. Com um banco REAL no ar,
um default apontando para credencial fraca deixa de ser ruido e vira caminho.

A porta legitima e' `MOTOR_DATABASE_URL` (`motor_expansao/db/postgres.py`): sem default, sem
segredo no fonte, e ausente significa "sem banco" em vez de "conecte em qualquer coisa".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: Arquivos que o motor carrega em producao ou no CI. O `fora_primeira_fase/` fica FORA
#: de proposito: e' arquivo morto, declarado como tal, e nao entra em import nenhum.
VIGIADOS = ("src/motor_expansao/config.py", "conftest.py", "tests/conftest.py")

#: Credencial embutida em qualquer forma reconhecivel.
PADROES = (
    re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s\"']*:[^\s\"'@]+@", re.IGNORECASE),
    re.compile(r"ultra123"),
    re.compile(r"dev-secret-key"),
)


@pytest.mark.parametrize("relativo", VIGIADOS)
def test_config_sem_credencial_morta(relativo: str) -> None:
    caminho = RAIZ / relativo
    if not caminho.exists():
        pytest.skip(f"{relativo} nao existe neste checkout")
    texto = caminho.read_text(encoding="utf-8")
    for padrao in PADROES:
        achado = padrao.search(texto)
        assert achado is None, (
            f"{relativo} voltou a carregar credencial embutida ({achado.group()!r}). "
            "Use MOTOR_DATABASE_URL, que nao tem default."
        )


def test_a_porta_do_banco_nao_tem_default() -> None:
    """`MOTOR_DATABASE_URL` ausente tem de significar 'sem banco', nunca 'conecte aqui'.

    Um default aqui reintroduziria o defeito por outro nome: o motor tentaria conectar
    sozinho, e o estado 'nao configurado' -- que e' o que permite a imagem ir para producao
    antes do banco existir -- deixaria de ser alcancavel.
    """
    from motor_expansao.db import postgres

    fonte = Path(postgres.__file__).read_text(encoding="utf-8")
    for padrao in PADROES:
        assert padrao.search(fonte) is None, "credencial embutida no modulo de conexao"
    assert 'os.environ.get(ENV_URL, "")' in fonte, (
        "a leitura da env mudou; garanta que a ausencia continua devolvendo None"
    )
