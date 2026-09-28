"""Senha de verdade (D26) — politica sem dependencia, hash com `importorskip`.

O arquivo tem duas metades de proposito.

A PRIMEIRA nao precisa de `argon2-cffi`: a politica de forca e a leitura da env sao Python puro,
e devem ser exercitadas em todo lugar -- inclusive na estacao do Vinicius, onde o extra `auth`
pode nao estar instalado, e no CI antes de o lockfile ser regerado.

A SEGUNDA precisa, e por isso usa `pytest.importorskip`. O molde e' o do `test_migracoes.py`, que
faz o mesmo com o `pglast`: dependencia de ambiente ausente vira SKIP legivel, nunca suite
vermelha por motivo que nao e' defeito do codigo. Se estes testes estiverem SKIPADOS na sua
maquina, o hash nao foi verificado ali -- rode-os onde o extra exista antes de confiar no corte
do P19.
"""

from __future__ import annotations

import pytest

from motor_expansao.db import senhas

# ======================================================================================
# Politica — roda sempre, sem dependencia
# ======================================================================================


def test_a_senha_inicial_nao_tem_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ausente significa "criacao recusada", nunca "use esta".

    Mesmo raciocinio do `MOTOR_DATABASE_URL` (ver `tests/contracts/test_sem_credencial_morta.py`):
    um default no fonte deixa de ser ruido no dia em que ha banco real no ar e vira caminho.
    """
    monkeypatch.delenv(senhas.ENV_SENHA_INICIAL, raising=False)
    with pytest.raises(senhas.SenhaInicialNaoConfigurada):
        senhas.senha_inicial()


@pytest.mark.parametrize("valor", ["", "   ", "\t\n"])
def test_senha_inicial_em_branco_conta_como_ausente(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    """`MOTOR_SENHA_INICIAL=` no `.env` e' o erro mais facil de cometer, e nao pode passar."""
    monkeypatch.setenv(senhas.ENV_SENHA_INICIAL, valor)
    with pytest.raises(senhas.SenhaInicialNaoConfigurada):
        senhas.senha_inicial()


def test_o_modulo_nao_carrega_senha_nenhuma_no_fonte() -> None:
    """Contrato, nao faxina: nenhuma senha literal aqui, em nenhuma forma.

    Uma "senha de exemplo" no fonte e' exatamente o movimento que o
    `test_sem_credencial_morta.py` existe para impedir em `config.py` — e este modulo e' o
    proximo lugar obvio para ela reaparecer.
    """
    from pathlib import Path

    fonte = Path(senhas.__file__).read_text(encoding="utf-8")
    assert 'os.environ.get(ENV_SENHA_INICIAL, "")' in fonte, (
        "a leitura da env mudou; garanta que a ausencia continua sem default"
    )
    # Inclui `Senha@` de proposito: um "exemplo de senha ruim" na prosa e' o caminho mais curto
    # para um literal com forma de credencial virar default de verdade depois.
    for suspeita in ("ultra123", "dev-secret-key", "senha123", "Senha@", "123456"):
        assert suspeita not in fonte, f"literal com forma de credencial no fonte: {suspeita!r}"


@pytest.mark.parametrize(
    "curta",
    ["", "abc", "a" * (senhas.MINIMO_DE_CARACTERES - 1)],
    ids=["vazia", "tres", "uma_abaixo_do_piso"],
)
def test_senha_curta_e_reprovada(curta: str) -> None:
    """Comprimento e' a unica exigencia que sustenta evidencia (NIST SP 800-63B).

    O caso de borda DERIVA da constante, e isso e' conserto de um defeito real: ate' 25/09/2026
    o literal era `"12345678901"` (11 caracteres, escolhido quando o piso era 12). Quando o dono
    baixou o piso para 8, aqueles 11 passaram a ser senha VALIDA e o teste reprovaria -- um
    numero cravado num teste envelhece em silencio junto com a politica que ele guarda.
    """
    with pytest.raises(senhas.SenhaFraca):
        senhas.validar(curta)


def test_senha_no_limite_passa() -> None:
    """Exatamente `MINIMO_DE_CARACTERES` tem de passar — o piso e' inclusivo."""
    senhas.validar("a" * senhas.MINIMO_DE_CARACTERES)


def test_senha_absurdamente_longa_e_reprovada() -> None:
    """Teto e' defesa, nao usabilidade: Argon2 com custo fixo processa entrada arbitraria, e
    aceitar megabytes num endpoint e' negacao de servico de graca."""
    with pytest.raises(senhas.SenhaFraca):
        senhas.validar("a" * (senhas.MAXIMO_DE_CARACTERES + 1))


@pytest.mark.parametrize("com_espaco", [" uma frase longa", "uma frase longa "])
def test_senha_com_espaco_na_borda_e_reprovada(com_espaco: str) -> None:
    """Impossivel de conferir na tela e quebra ao digitar de novo."""
    with pytest.raises(senhas.SenhaFraca):
        senhas.validar(com_espaco)


def test_a_senha_inicial_nao_pode_ser_escolhida_como_a_propria(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E' a regra que faz a troca significar alguma coisa.

    Sem ela, "trocar" pela mesma string deixaria todo mundo com a senha compartilhada E a coluna
    `senha_definida_em_usuario` afirmando que a pessoa definiu a propria. Seria pior que nao ter
    troca nenhuma, porque a trilha passaria a mentir.
    """
    monkeypatch.setenv(senhas.ENV_SENHA_INICIAL, "a-senha-inicial-do-piloto")
    with pytest.raises(senhas.SenhaFraca):
        senhas.validar("a-senha-inicial-do-piloto")
    senhas.validar("outra frase bem diferente")


def test_sem_env_configurada_a_politica_ainda_funciona(monkeypatch: pytest.MonkeyPatch) -> None:
    """A comparacao com a inicial e' condicional: sem env, a politica nao pode explodir."""
    monkeypatch.delenv(senhas.ENV_SENHA_INICIAL, raising=False)
    senhas.validar("uma frase bem longa")


def test_os_parametros_sao_os_do_authelia() -> None:
    """Travados por teste, porque a compatibilidade e' o que viabiliza o corte do P19.

    O `users_database.yml` do Authelia guarda `argon2id` com estes valores (4.37+). Mantendo-os,
    o dia da virada pode IMPORTAR os hashes existentes em vez de obrigar todo mundo a redefinir
    senha de uma vez. Mudar um numero aqui e' decisao, nao ajuste — e cobra a nota no D26.
    """
    assert senhas.MEMORIA_KIB == 65536
    assert senhas.ITERACOES == 3
    assert senhas.PARALELISMO == 4
    assert senhas.BYTES_DE_SAL == 16
    assert senhas.BYTES_DE_CHAVE == 32
    assert senhas.PREFIXO_PHC == "$argon2id$"


# ======================================================================================
# Hash de verdade — SKIP sem o extra `auth`
# ======================================================================================


@pytest.fixture
def _argon2() -> None:
    pytest.importorskip(
        "argon2",
        reason="extra `auth` (argon2-cffi) nao instalado; instale com pip install '.[auth]'",
    )


def test_gerar_devolve_phc_argon2id(_argon2: None) -> None:
    """O formato importa: e' o prefixo que distingue hash de verdade dos `hash_de_teste_*`."""
    phc = senhas.gerar("uma frase bem longa")
    assert phc.startswith(senhas.PREFIXO_PHC)
    assert "uma frase bem longa" not in phc


def test_o_mesmo_texto_gera_hashes_DIFERENTES(_argon2: None) -> None:
    """Sal por linha. Sem ele, dois hashes iguais anunciariam no dump quem tem a mesma senha —
    e com senha inicial compartilhada isso seria a lista de quem ainda nao trocou."""
    assert senhas.gerar("uma frase bem longa") != senhas.gerar("uma frase bem longa")


def test_verificar_aceita_a_senha_certa_e_recusa_a_errada(_argon2: None) -> None:
    phc = senhas.gerar("uma frase bem longa")
    assert senhas.verificar("uma frase bem longa", phc) is True
    assert senhas.verificar("uma frase bem longo", phc) is False


def test_gerar_aplica_a_politica(_argon2: None) -> None:
    """`gerar` e' o unico produtor legitimo do hash, e nao confia em quem o chama."""
    with pytest.raises(senhas.SenhaFraca):
        senhas.gerar("curta")


@pytest.mark.parametrize("lixo", [None, "", "hash_de_teste_1", "$2b$12$algumacoisa", "nao-e-phc"])
def test_verificar_recusa_hash_que_nao_e_phc(_argon2: None, lixo: str | None) -> None:
    """As quatro fixtures `hash_de_teste_*` do banco de ensaio caem exatamente aqui.

    Antes da 016 a coluna aceitava qualquer string, e e' esse o estado do
    `banco_de_reservas_ensaio` hoje: as pessoas fictícias nao conseguem "acertar" a senha, o que
    e' o comportamento certo.
    """
    assert senhas.verificar("qualquer coisa", lixo) is False


def test_verificar_nunca_levanta_por_senha_errada(_argon2: None) -> None:
    """Devolve `False`. Levantar transformaria senha errada em 500 no dia do P19."""
    phc = senhas.gerar("uma frase bem longa")
    for tentativa in ("", " ", "x" * 200, "uma frase bem long"):
        assert senhas.verificar(tentativa, phc) is False


def test_precisa_rehash_e_falso_para_hash_recem_feito(_argon2: None) -> None:
    assert senhas.precisa_rehash(senhas.gerar("uma frase bem longa")) is False


@pytest.mark.parametrize("velho", ["", "hash_de_teste_1", "$2b$12$algumacoisa"])
def test_precisa_rehash_e_verdadeiro_para_hash_estranho(_argon2: None, velho: str) -> None:
    """Hash ilegivel e' hash a refazer — inclusive os `hash_de_teste_*` do ensaio."""
    assert senhas.precisa_rehash(velho) is True


def test_hash_da_senha_inicial_usa_a_env(monkeypatch: pytest.MonkeyPatch, _argon2: None) -> None:
    monkeypatch.setenv(senhas.ENV_SENHA_INICIAL, "a-senha-inicial-do-piloto")
    phc = senhas.hash_da_senha_inicial()
    assert senhas.verificar("a-senha-inicial-do-piloto", phc) is True
    assert senhas.verificar("outra coisa", phc) is False


def test_a_senha_inicial_nao_passa_pela_politica(
    monkeypatch: pytest.MonkeyPatch, _argon2: None
) -> None:
    """Quem a define e' o operador no `.env`.

    Reprova-la em tempo de execucao transformaria uma escolha de deploy num erro para quem
    clicou em "Criar" — e a pessoa na tela nao tem como consertar o `.env`.
    """
    monkeypatch.setenv(senhas.ENV_SENHA_INICIAL, "curta")
    assert senhas.hash_da_senha_inicial().startswith(senhas.PREFIXO_PHC)


def test_disponivel_diz_a_verdade(_argon2: None) -> None:
    """Com o extra instalado, `disponivel()` e' verdadeiro — a tela usa isto para nao oferecer
    o que vai falhar com 503."""
    assert senhas.disponivel() is True


# --------------------------------------------------------------------------------------
# A senha TEMPORARIA (D31) — o que a redefinicao por administrador entrega
# --------------------------------------------------------------------------------------


def test_a_temporaria_passa_na_propria_politica() -> None:
    """Ela e' uma senha como outra qualquer: se `validar` a reprovasse, `gerar` levantaria
    `SenhaFraca` no meio da redefinicao -- e o admin veria erro ao clicar num botao correto."""
    senhas.validar(senhas.gerar_temporaria())


def test_duas_temporarias_nunca_sao_iguais() -> None:
    """O contrario disto e' exatamente o defeito que a D31 corrige: senha compartilhada."""
    assert len({senhas.gerar_temporaria() for _ in range(200)}) == 200


def test_a_temporaria_nao_tem_caractere_ambiguo() -> None:
    """Ela nasce para ser DITADA por telefone. `O`/`0` e `I`/`l`/`1` sao as confusoes caras --
    e o custo delas nao e' erro de digitacao: e' a pessoa achar que foi barrada por outra coisa.
    """
    amostra = "".join(senhas.gerar_temporaria() for _ in range(200))
    for ambiguo in ("o", "O", "0", "I", "l", "1"):
        assert ambiguo not in amostra, f"caractere ambiguo na senha ditada: {ambiguo!r}"


def test_a_temporaria_usa_secrets_e_nao_random() -> None:
    """`random` e' Mersenne Twister: previsivel a partir de saidas anteriores. Aqui a saida e'
    uma credencial, entao a fonte tem de ser a criptografica."""
    from pathlib import Path

    fonte = Path(senhas.__file__).read_text(encoding="utf-8")
    assert "import secrets" in fonte
    assert "import random" not in fonte
    assert "random.choice" not in fonte


def test_a_temporaria_tem_entropia_declarada() -> None:
    """Tamanho e' a unica exigencia que o modulo sustenta (NIST SP 800-63B), entao ele precisa
    SOBRAR: 12 caracteres de um alfabeto de 31 dao ~59 bits."""
    import math

    bits = (
        senhas.GRUPOS_DA_TEMPORARIA
        * senhas.CARACTERES_POR_GRUPO
        * math.log2(len(senhas.ALFABETO_TEMPORARIA))
    )
    assert bits > 50, f"entropia caiu para {bits:.1f} bits"
    assert len(senhas.gerar_temporaria()) >= senhas.MINIMO_DE_CARACTERES
