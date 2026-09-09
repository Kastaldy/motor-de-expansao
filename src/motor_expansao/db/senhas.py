"""Senha de verdade: hash Argon2id, politica de forca, e a senha inicial compartilhada.

O que esta camada resolve
-------------------------
`usuarios.senha_hash` existe desde a migration 003 e, ate' a 016, nunca teve consumidor: quem
autentica e' o Authelia, e o que estava gravado ali eram as strings `hash_de_teste_1..4`. Este
modulo e' o produtor e o verificador que faltavam -- ele NAO coloca a senha no caminho do login
(isso e' a execucao do P19, que segue aberta), mas faz com que o valor da coluna passe a significar
alguma coisa.

Por que Argon2id, e nao bcrypt
------------------------------
Forca a parte, ha um motivo pratico que decide: o `authelia/users_database.yml` JA' guarda
`argon2id`. Usando o mesmo algoritmo com parametros compativeis, o dia da virada do P19 pode
IMPORTAR os hashes que ja existem, em vez de obrigar todo mundo a redefinir senha de uma vez.
Escolher bcrypt aqui custaria exatamente isso, e o custo apareceria no pior momento.

Os parametros abaixo sao os defaults do Authelia 4.37+ de proposito -- nao os do `argon2-cffi`, que
sao mais fracos em memoria. Mudar qualquer um deles NAO invalida hash antigo: o PHC carrega os
proprios parametros, e `precisa_rehash` avisa quando um hash foi feito com parametros velhos.

Por que o import e' tardio
--------------------------
`argon2-cffi` entra pelo extra novo `auth` do `pyproject.toml`, e o lockfile do projeto e' gerado
com `uv pip compile`. Enquanto o extra nao estiver instalado em todo lugar, um import no topo deste
arquivo derrubaria o piloto INTEIRO no import de `web/server/app.py` -- e o piloto tem de continuar
servindo sem senha, que e' o estado de hoje. A disciplina e' a mesma do modulo de banco: dependencia
ausente vira estado explicavel (`HashIndisponivel`), nunca traceback no boot.

Por que a senha inicial nao tem default
---------------------------------------
Mesma razao do `MOTOR_DATABASE_URL` (ver `tests/contracts/test_sem_credencial_morta.py`): um default
no fonte deixa de ser ruido no dia em que ha banco real no ar e vira caminho de entrada. Sem
`MOTOR_SENHA_INICIAL` definida, criar usuario e' RECUSADO com mensagem clara -- nunca "criei com uma
senha que voce nao sabe qual e'".
"""

from __future__ import annotations

import os
from typing import Any

#: Env da senha inicial compartilhada, entregue a quem e' criado pela tela. SEM default.
ENV_SENHA_INICIAL = "MOTOR_SENHA_INICIAL"

#: Todo hash escrito por este modulo comeca assim. E' o que distingue hash de verdade dos
#: `hash_de_teste_*` que as fixtures gravaram, e o que a rota de troca confere antes de aceitar.
PREFIXO_PHC = "$argon2id$"

# Defaults do Authelia 4.37+ (`authentication_backend.file.password`), para o hash deste modulo e o
# do `users_database.yml` serem intercambiaveis quando o P19 acontecer.
MEMORIA_KIB = 65536
ITERACOES = 3
PARALELISMO = 4
BYTES_DE_SAL = 16
BYTES_DE_CHAVE = 32

#: Piso de tamanho. Comprimento e' a unica exigencia que sustenta evidencia (NIST SP 800-63B):
#: regra de composicao -- "uma maiuscula, um digito, um simbolo" -- produz a palavra obvia com
#: uma letra trocada e um ano no fim, o que da' sensacao de rigor sem ganho mensuravel. Por isso
#: aqui ha piso de tamanho e nada mais. (Nenhum exemplo literal neste arquivo, de proposito: ver
#: `test_o_modulo_nao_carrega_senha_nenhuma_no_fonte`.)
MINIMO_DE_CARACTERES = 12

#: Teto, e ele e' defesa e nao usabilidade: Argon2 com custo de memoria fixo processa entrada
#: arbitrariamente longa, entao aceitar megabytes num endpoint publico e' negacao de servico de
#: graca. 128 nao aperta ninguem -- uma frase-senha longa cabe folgada.
MAXIMO_DE_CARACTERES = 128


class HashIndisponivel(RuntimeError):
    """`argon2-cffi` nao esta instalado neste ambiente.

    Traduzida para 503 na rota, como `BancoIndisponivel`: e' falta de dependencia de ambiente,
    nao erro de quem clicou.
    """


class SenhaFraca(ValueError):
    """Senha reprovada pela politica. A mensagem vai para a tela -- escreva-a para a pessoa."""


class SenhaInicialNaoConfigurada(RuntimeError):
    """`MOTOR_SENHA_INICIAL` ausente ou vazia. Criar usuario fica RECUSADO enquanto for assim."""


def _hasher() -> Any:
    """O `PasswordHasher` configurado. Levanta `HashIndisponivel` se o extra `auth` faltar."""
    try:
        from argon2 import PasswordHasher
    except ModuleNotFoundError as erro:  # pragma: no cover - depende do ambiente
        raise HashIndisponivel(
            "argon2-cffi nao esta instalado. Instale o extra `auth`: "
            'python -m pip install ".[auth]" -c constraints.txt'
        ) from erro

    return PasswordHasher(
        time_cost=ITERACOES,
        memory_cost=MEMORIA_KIB,
        parallelism=PARALELISMO,
        hash_len=BYTES_DE_CHAVE,
        salt_len=BYTES_DE_SAL,
    )


def disponivel() -> bool:
    """Se este ambiente sabe hashear. A tela usa isto para nao oferecer o que vai falhar."""
    try:
        _hasher()
    except HashIndisponivel:
        return False
    return True


def validar(senha: str) -> None:
    """Aplica a politica. Levanta `SenhaFraca` com a mensagem que a pessoa vai ler.

    A comparacao com a senha inicial e' parte da politica, e nao detalhe: uma senha inicial
    COMPARTILHADA que a pessoa "troca" pela mesma string deixa todo mundo com a mesma senha e a
    coluna `senha_definida_em_usuario` afirmando que ela definiu a propria. Seria pior que nao ter
    troca nenhuma, porque a trilha passaria a mentir.
    """
    if len(senha) < MINIMO_DE_CARACTERES:
        raise SenhaFraca(
            f"A senha precisa de pelo menos {MINIMO_DE_CARACTERES} caracteres. "
            "Uma frase curta e fácil de lembrar funciona melhor que letra trocada por símbolo."
        )
    if len(senha) > MAXIMO_DE_CARACTERES:
        raise SenhaFraca(f"A senha não pode passar de {MAXIMO_DE_CARACTERES} caracteres.")
    if senha.strip() != senha:
        raise SenhaFraca(
            "A senha não pode começar nem terminar com espaço — é impossível de conferir na tela "
            "e quebra na hora de digitar de novo."
        )

    inicial = os.environ.get(ENV_SENHA_INICIAL, "")
    if inicial and senha == inicial:
        raise SenhaFraca(
            "Essa é a senha inicial, que é a mesma para todo mundo. Escolha uma que só você saiba."
        )


def gerar(senha: str) -> str:
    """Valida e devolve o PHC do Argon2id. Unico produtor legitimo de `usuarios.senha_hash`."""
    validar(senha)
    return str(_hasher().hash(senha))


def senha_inicial() -> str:
    """A senha inicial compartilhada, da env. Levanta se ela nao estiver configurada.

    NAO tem default (ver o cabecalho do modulo). Ela nao passa pela `validar`: quem a define e'
    o operador no `.env`, e reprova-la em tempo de execucao transformaria uma escolha de deploy
    num erro de quem clicou em "Criar".
    """
    valor = os.environ.get(ENV_SENHA_INICIAL, "").strip()
    if not valor:
        raise SenhaInicialNaoConfigurada(
            f"{ENV_SENHA_INICIAL} não está definida. Sem ela não há senha para entregar a quem "
            "é criado — defina no `.env` antes de criar usuários."
        )
    return valor


def hash_da_senha_inicial() -> str:
    """O hash a gravar em quem nasce pela tela. Cada pessoa recebe um SAL diferente.

    Sal por linha importa mesmo com senha compartilhada: sem ele, duas linhas com o mesmo hash
    anunciariam no dump quem ainda nao trocou a senha -- e a coluna
    `deve_trocar_senha_usuario` ja' responde isso de forma honesta, para quem tem direito de ver.

    A env e' conferida ANTES da biblioteca, de proposito. Se as duas faltarem, o operador precisa
    saber das duas -- mas a env e' o que ele controla no `.env` e a causa muito mais provavel;
    deixar `HashIndisponivel` na frente mandaria investigar o lockfile por um `.env` incompleto.
    """
    inicial = senha_inicial()
    return str(_hasher().hash(inicial))


def verificar(senha: str, hash_guardado: str | None) -> bool:
    """Se a senha casa com o hash. Nunca levanta por senha errada -- devolve `False`.

    `hash_guardado` nulo ou fora do formato PHC devolve `False` DEPOIS de pagar o custo de um
    hash descartavel. Isso e' proposital: sem o trabalho falso, o tempo de resposta diria quem
    tem cadastro e quem nao tem, e um endpoint de login publico entregaria a lista de usuarios
    por cronometro. As fixtures `hash_de_teste_*` caem exatamente aqui.
    """
    from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

    ph = _hasher()

    if not hash_guardado or not hash_guardado.startswith(PREFIXO_PHC):
        ph.hash(senha)  # trabalho falso, tempo comparavel
        return False

    try:
        return bool(ph.verify(hash_guardado, senha))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def precisa_rehash(hash_guardado: str) -> bool:
    """Se o hash foi feito com parametros mais fracos que os de agora.

    Chamar depois de uma verificacao BEM-SUCEDIDA e regravar: e' assim que o custo sobe com o
    hardware sem pedir nada a ninguem. Um hash importado do Authelia com parametros diferentes
    dos daqui aparece por este caminho.
    """
    if not hash_guardado or not hash_guardado.startswith(PREFIXO_PHC):
        return True
    try:
        return bool(_hasher().check_needs_rehash(hash_guardado))
    except Exception:  # noqa: BLE001 - hash ilegivel e' hash a refazer
        return True
