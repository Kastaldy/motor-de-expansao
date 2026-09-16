"""Acesso ao banco PostgreSQL/PostGIS do motor — fundacao da inclusao do banco.

Este pacote e' a UNICA porta do motor para o banco. Ele existe antes de o banco
existir: sem a env `MOTOR_DATABASE_URL`, tudo aqui reporta "nao configurado" e
NENHUMA conexao e' tentada -- o motor sobe e funciona exatamente como antes.
Esse e' o requisito que permite preparar o codigo hoje e ligar o banco depois,
sem um deploy que dependa do outro.

Molde do `rede_cadastro`/`acesso_log`: degradacao graciosa e explicita. La', sem
o volume montado, a leitura degrada e a escrita devolve 503; aqui, sem a env (ou
sem o driver instalado), o mesmo -- e o `/api/health` diz qual dos dois falta.

Duas portas, e a diferenca entre elas e' imposta pelo BANCO, nao por convencao:

* `conexao()`     -- leitura. Abre a transacao com `SET TRANSACTION READ ONLY`,
                     entao um INSERT ali dentro e' recusado pelo servidor.
* `transacao()`   -- escrita. EXIGE `id_usuario` (que pode ser `None` para acao
                     de sistema, mas tem de ser passado) e emite o
                     `set_config('app.id_usuario', ..., true)` que as triggers de
                     auditoria do banco leem. Sem esse passo, toda concessao e
                     revogacao de permissao seria registrada com autor nulo --
                     exatamente o dado pelo qual a auditoria existe.

O submodulo se chama `postgres`, e nao `conexao`, de proposito: `conexao` e' o nome
da FUNCAO publica acima, e um submodulo homonimo seria sombreado por ela neste
namespace -- `from motor_expansao.db import conexao` devolveria a funcao, e o modulo
ficaria inalcancavel por esse caminho.

O contrato do `app.id_usuario` e' de todo caminho de escrita que age EM NOME DE ALGUEM,
nao de uma funcao; por isso ele mora no gerenciador de contexto, e nao numa chamada que
alguem possa esquecer de fazer. Contrato completo: `esquema-do-banco.md` §3.7 (D28).

A EXCECAO TEM NOME, e ate' 16/09/2026 esta frase dizia "TODO caminho de escrita" sem
menciona-la -- ou seja, nascia falsa. `db/cli.py` abre conexao propria e escreve sem
carimbo, de proposito: ele roda como DONO (runner de migration e verificador de
privilegio), e migration nao e' ato de RBAC de um usuario -- nao ha' autor a carimbar.
Qualquer OUTRA conexao fora deste modulo e' defeito, e ha' teste de contrato que a recusa
(`tests/contracts/test_conexao_por_uma_porta_so.py`).
"""

from __future__ import annotations

from .postgres import (
    AutocommitProibido,
    BancoIndisponivel,
    BancoNaoConfigurado,
    conexao,
    configurado,
    fechar_pool,
    motivo_indisponivel,
    saude,
    transacao,
    url_configurada,
)

__all__ = [
    "AutocommitProibido",
    "BancoIndisponivel",
    "BancoNaoConfigurado",
    "conexao",
    "configurado",
    "fechar_pool",
    "motivo_indisponivel",
    "saude",
    "transacao",
    "url_configurada",
]
