"""BLK-MA-17-FU4: identidade de estabelecimento por NOME.

Todos os casos deste arquivo saem de PARES REAIS medidos em 2026-08-18 entre o feed do WellHub e
`concorrentes_mapeados` — nenhum é inventado. É o que separa um matcher que funciona no papel de um
que funciona no insumo.

O que se protege:

  1. **A duplicata longe.** `SKYFIT ACADEMIA - BACABAL` e `Bacabal (MA)` são a mesma academia a
     **940 m** de distância. A dedup por distância (150 m) não tinha chance.
  2. **A irmã perto.** `Carpina` e `Carpina 2` estão a 582 m e são DUAS academias. O discriminante
     das duas é idêntico (Jaccard `1,00`) — só o ordinal as separa, e é por isso que a regra de
     ordinal é uma NEGAÇÃO avaliada ANTES do Jaccard.
  3. **O nome sem lugar.** `Performance Academia` não diz onde fica; afirmar identidade a partir
     dele colapsaria academias distintas em massa.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import pytest

from motor_expansao.vulnerabilidade.identidade import (
    JACCARD_MIN_NOME,
    discriminante,
    mesma_unidade,
    ordinal_da_unidade,
    similaridade_nome,
)


# --------------------------------------------------------------------------- #
# O discriminante: nome MENOS rede, ruído e ordinal                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("nome", "rede", "esperado"),
    [
        ("Panobianco Extrema", "panobianco", {"extrema"}),
        ("SkyFit Academia - DIC Campinas", "skyfit", {"dic", "campinas"}),
        ("Alpha Fitness - Vila Laura", "alpha_fitness", {"vila", "laura"}),
        ("Uplay Express Joinville", "uplay", {"joinville"}),
        # o slug da rede sai mesmo quando escrito por extenso e com underscore
        ("Contorno do Corpo Jardim Riacho", "contorno_do_corpo", {"jardim", "riacho"}),
        # nome sem parte geográfica -> discriminante VAZIO, e isso é o correto
        ("Performance Academia", "performance", set()),
    ],
)
def test_discriminante_isola_o_lugar(nome: str, rede: str, esperado: set[str]) -> None:
    assert discriminante(nome, rede) == esperado


def test_ordinal_ausente_vale_um() -> None:
    """A primeira unidade de um bairro não se numera — tratá-la como `1` é o que permite
    comparar `Carpina` com `Carpina 2`."""
    assert ordinal_da_unidade("Carpina") == 1
    assert ordinal_da_unidade("Carpina 2") == 2
    assert ordinal_da_unidade("Águas Claras II") == 2
    assert ordinal_da_unidade("Itaim Paulista I - SP") == 1
    assert ordinal_da_unidade("BAIRRO-DE-FATIMA-II") == 2


# --------------------------------------------------------------------------- #
# 1. Duplicatas reais que a distância pura não pegava                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("feed", "mapeado", "rede", "distancia_real_m"),
    [
        ("Panobianco Extrema", "EXTREMA", "panobianco", 188),
        ("Alpha Fitness - Vila Laura", "VILA-LAURA", "alpha_fitness", 237),
        ("Pratique Pedra Branca", "PEDRA BRANCA", "pratique", 224),
        ("Bodytech Uberlândia - NV Boulevard", "Bodytech Uberlândia - NV Boulevard", "bodytech", 299),
        ("Power Fit Parque Cuiabá", "POWER FIT PARQUE CUIABÁ", "power_fit", 430),
        ("SKYFIT ACADEMIA - BACABAL", "Bacabal (MA)", "skyfit", 940),
        ("Redfit - Shopping Jardim Oriente (SJC)", "Shopping Jardim Oriente - SJC", "redfit", 257),
        ("Match Fit Camaragibe 2", "Camaragibe 2", "match_fit", 703),
    ],
)
def test_par_real_de_duplicata_casa(feed: str, mapeado: str, rede: str, distancia_real_m: int) -> None:
    """Pares medidos no insumo. O `distancia_real_m` está aqui para documentar que TODOS estão
    além dos 150 m do limiar antigo — nenhum era alcançável por distância."""
    assert distancia_real_m > 150, "o caso perderia o sentido se estivesse dentro do limiar antigo"
    assert mesma_unidade(feed, mapeado, rede), (
        f"{feed!r} x {mapeado!r} deveria casar (J={similaridade_nome(feed, mapeado, rede):.2f})"
    )


# --------------------------------------------------------------------------- #
# 2. Irmãs reais que NÃO podem colapsar                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("a", "b", "rede"),
    [
        ("Carpina", "Carpina 2", "match_fit"),
        ("Águas Claras", "Águas Claras II", "bluefit"),
        ("CAMPO GRANDE", "CAMPO GRANDE 2", "panobianco"),
        ("BAIRRO-DE-FATIMA", "BAIRRO-DE-FATIMA-II", "selfit"),
        ("Itaim Paulista I - SP", "Itaim Paulista II - SP", "allp_fit"),
        ("EVOLVE - AGUAS CLARAS", "EVOLVE - AGUAS CLARAS 2", "evolve"),
        ("SANTA INÊS", "SANTA INÊS II", "pratique"),
    ],
)
def test_unidade_numerada_NAO_colapsa(a: str, b: str, rede: str) -> None:
    """O caso que quebrava o matcher v1: discriminante IDÊNTICO, unidades diferentes.

    Estes pares têm Jaccard `1,00` — nenhum limiar de similaridade os separaria. Só a regra de
    ordinal, e ela tem de ser avaliada ANTES.
    """
    assert similaridade_nome(a, b, rede) >= JACCARD_MIN_NOME, (
        "premissa do teste: sem a regra de ordinal, o Jaccard casaria"
    )
    assert not mesma_unidade(a, b, rede)


def test_sufixo_diferente_no_mesmo_bairro_nao_colapsa() -> None:
    """`AD3 - Tubarão - Humaitá` x `- Premium`: compartilham a cidade, diferem no bairro.

    Aqui quem resolve é o Jaccard (`0,50 < 0,67`), não o ordinal — os dois são unidade `1`.
    """
    a, b, rede = "AD3 - Tubarão - Humaitá", "AD3 - Tubarão - Premium", "ad3"
    assert ordinal_da_unidade(a) == ordinal_da_unidade(b) == 1
    assert similaridade_nome(a, b, rede) < JACCARD_MIN_NOME
    assert not mesma_unidade(a, b, rede)


def test_nome_sem_lugar_nunca_afirma_identidade() -> None:
    """Discriminante vazio -> similaridade `0`. Conservador de propósito."""
    assert similaridade_nome("Performance Academia", "Academia Performance", "performance") == 0.0
    assert not mesma_unidade("Performance Academia", "Academia Performance", "performance")


def test_o_modulo_nao_checa_rede_mas_o_slug_alheio_protege() -> None:
    """`mesma_unidade` NÃO valida rede — quem chama garante isso
    (`dedup_cadeias_do_feed`: `if redes[i] != rede_m[j]: continue`).

    Mas há uma proteção de segunda ordem que vale documentar, porque foi medida ao escrever o
    teste: só o slug da rede PASSADA sai do discriminante. Chamando com `"bluefit"`, o token
    `selfit` do outro nome SOBREVIVE e vira discriminante — o Jaccard cai para `0,50` e o par não
    casa. Ou seja, mesmo um chamador descuidado erra para o lado seguro.
    """
    a, b = "Bluefit Centro Cívico", "Selfit Centro Cívico"
    assert discriminante(a, "bluefit") == {"civico"}
    assert discriminante(b, "bluefit") == {"selfit", "civico"}, "o slug alheio tem de sobrar"
    assert similaridade_nome(a, b, "bluefit") == pytest.approx(0.5)
    assert not mesma_unidade(a, b, "bluefit")


# --------------------------------------------------------------------------- #
# Simetria e limiar                                                            #
# --------------------------------------------------------------------------- #
def test_o_casamento_e_simetrico() -> None:
    """Sem isto, o resultado da dedup dependeria de quem é o lado esquerdo."""
    pares = [
        ("Panobianco Extrema", "EXTREMA", "panobianco"),
        ("Carpina", "Carpina 2", "match_fit"),
        ("AD3 - Tubarão - Humaitá", "AD3 - Tubarão - Premium", "ad3"),
    ]
    for a, b, r in pares:
        assert mesma_unidade(a, b, r) == mesma_unidade(b, a, r)
        assert similaridade_nome(a, b, r) == pytest.approx(similaridade_nome(b, a, r))


def test_o_limiar_vem_do_contrato_e_nao_do_corpo() -> None:
    """Molde do `test_13` do BLK-MA-17: número mágico no corpo da função é regressão."""
    assert 0.5 < JACCARD_MIN_NOME <= 1.0
    # `0,67` é o ponto de inflexão medido: com `0,50` o custo dobra (31 -> 64 academias reais
    # apagadas a 500 m) sem ganho equivalente.
    assert JACCARD_MIN_NOME == pytest.approx(0.67)


def test_o_limiar_e_ESTRITAMENTE_maior_que_dois_tercos_de_proposito() -> None:
    """A trava contra o "conserto" que parece óbvio e piora o resultado.

    `0,67 > 2/3 = 0,6666...`, então `{a,b}` × `{a,b,c}` NÃO casa. Isso parece arredondamento
    descuidado e foi auditado como tal em 2026-08-19. A medição mandou manter: baixar para `2/3`
    ganha 27 duplicatas e **dobra** o custo (12 -> 27 academias reais apagadas), razão `1,8:1`
    contra os `26,7:1` do critério como está.

    A razão é estrutural, não numérica: o sufixo que distingue uma unidade da irmã é quase sempre
    UM token (`OURO PRETO` × `OURO PRETO PRIME`, `AD3 - Tubarão - Humaitá` × `- Premium`), e é
    exatamente esse caso que `2/3` passa a aceitar.
    """
    assert JACCARD_MIN_NOME > 2 / 3, "baixar para 2/3 dobra o custo — ver a tabela em identidade.py"

    # O par de um token a mais fica logo ABAIXO do limiar, e isso é o comportamento correto.
    a, b, rede = "OURO PRETO", "OURO PRETO PRIME", "pratique"
    assert similaridade_nome(a, b, rede) == pytest.approx(2 / 3)
    assert not mesma_unidade(a, b, rede), "unidade `PRIME` colapsou na irmã"
