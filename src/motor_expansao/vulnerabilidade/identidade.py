"""Identidade de estabelecimento por NOME — a primitiva que o dedup por distância não dá.

**O defeito que este módulo fecha, medido em 2026-08-18.** A dedup entre o feed do agregador e
`concorrentes_mapeados` casava por distância pura (`DEDUP_CADEIA_FEED_M = 150 m`). Mas as duas
fontes geocodificam o mesmo endereço com desvio muito maior que isso: entre 150 m e 1 km há **438
pares** de mesma rede, e **407 deles (92,9%) têm o nome batendo** — é a mesma academia contada duas
vezes. Casos reais: `Bodytech Uberlândia - NV Boulevard` contra nome idêntico a **299 m**;
`SKYFIT ACADEMIA - BACABAL` contra `Bacabal (MA)` a **940 m**.

Distância sozinha não resolve: subir o limiar para 1 km apagaria academia real. Quem separa os dois
casos é o **nome**.

## Como o nome discrimina

O nome de uma unidade é, quase sempre, `REDE + LUGAR` — "Panobianco Extrema", "SkyFit Academia -
Bacabal". Tirando o slug da rede (que é igual nos dois lados por construção, já que só comparamos
dentro da mesma rede) e as palavras genéricas, sobra o **discriminante geográfico**. Se ele coincide,
é a mesma unidade.

A medida é **Jaccard** e não "compartilha ao menos um token", porque o falso positivo medido era
`AD3 - Tubarão - Humaitá` contra `AD3 - Tubarão - Premium`: compartilham "tubarão", mas diferem
justamente no que distingue. Jaccard põe isso em número — `1/3 = 0,33` contra `1,00` de
`Panobianco Extrema` × `EXTREMA`.

## A regra de negação, que é o que torna o matcher utilizável

Jaccard alto ainda confundia **unidades numeradas** da mesma rede no mesmo bairro: `Águas Claras` ×
`Águas Claras II`, `Carpina` × `Carpina 2`, `CAMPO GRANDE` × `CAMPO GRANDE 2`. A causa era boba — o
filtro de token curto descartava justamente o sufixo `2`/`II` que distingue.

Mexer no limiar de Jaccard **não** resolve, e a razão é mais forte do que "casaria mesmo assim":
`discriminante` já exclui os romanos, então no código real esse par tem Jaccard **exatamente
`1,00`** — nenhum limiar o separa. A regra certa é de **negação**: ordinais diferentes ⇒ unidades
diferentes, por mais parecido que seja o resto.

Efeito medido dessa única regra, a `800 m`: o custo cai de **59 para 10** academias reais, com o
ganho praticamente intacto (292 -> 285). A razão ganho/custo sai de `4,9:1` para `28,5:1`.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import re
import unicodedata

# Palavras que aparecem em toda parte e não discriminam UNIDADE nenhuma. Note `centro`,
# `premium` e `shopping`: elas são ruído na maioria dos nomes, e o custo de mantê-las aqui são
# os 3 pares residuais medidos (`Itapevi Centro` × `Itapevi`, `Shopping Cidade Tiradentes` ×
# `Cidade Tiradentes`, `AD3 - Florianópolis - Centro` × `... - Premium`). Tirá-las da lista
# separaria esses três, mas faria a MESMA unidade deixar de casar quando só uma das fontes usa a
# palavra — que é o caso mais comum. Fica o ruído, e o resíduo é declarado.
RUIDO_NOME: frozenset[str] = frozenset(
    {
        "academia", "academias", "fit", "fitness", "unidade", "gym", "ct", "studio",
        "shopping", "shop", "loja", "the", "com", "das", "dos", "sao", "santa", "santo",
        "centro", "premium", "express", "smart", "club", "clube", "sport", "sports",
    }
)

_ROMANOS: dict[str, int] = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}

# Limiar de similaridade do discriminante.
#
# **`0,67` é ESTRITAMENTE MAIOR que `2/3 = 0,6666...`, e isso é deliberado.** A consequência é que o
# par `{a,b}` × `{a,b,c}` — dois tokens em comum, um lado com um extra — NÃO casa. Parece um
# descuido de arredondamento e foi auditado como tal em 2026-08-19; a medição mandou manter:
#
#   | limiar  | duplicatas a mais | academias REAIS apagadas |
#   |---------|-------------------|--------------------------|
#   | `0,67`  | (referência)      | **12** de 4.366 (0,27%)  |
#   | `2/3`   | +27               | **27** de 4.366 (0,62%)  |
#
# Baixar para `2/3` DOBRA o custo para ganhar 27 — razão `1,8:1`, contra os `26,7:1` do critério
# como está. E os falsos positivos novos são exatamente o padrão que este limiar existe para
# recusar: `OURO PRETO` × `OURO PRETO PRIME` a 142 m, irmã do `AD3 - Tubarão - Humaitá` ×
# `- Premium`. O sufixo que distingue uma unidade da outra é, quase sempre, UM token — que é
# precisamente o que `2/3` passa a ignorar.
#
# Custo aceito: 27 duplicatas reais sobrevivem por este motivo (ex.: `SKYFIT ACADEMIA CAMPO BELO` ×
# `Campo Belo - Campinas (SP)` a 162 m). Estão declaradas no `BLK-MA-17-FU5`.
JACCARD_MIN_NOME = 0.67

# Até onde a MESMA academia pode aparecer deslocada entre as duas fontes. Não é uma distância
# geográfica "real" — é a divergência de geocodificação entre o feed do agregador e o site da
# rede, medida: 27,3% dos pares de duplicata estão além de 1 km.
DIST_MAX_MESMO_NOME_M = 1200.0


def _tokens(texto: str) -> list[str]:
    """Minúsculo, sem acento, só alfanumérico."""
    s = unicodedata.normalize("NFKD", str(texto or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else " " for c in s).split()


def ordinal_da_unidade(nome: str) -> int:
    """Número da unidade dentro do bairro. Ausência = `1` — a primeira não se numera.

    É isto que separa `Carpina` de `Carpina 2`. Sem esta função o matcher colapsa unidades irmãs
    reais, que foi o modo de falha medido em 31 pares.
    """
    for t in _tokens(nome):
        if t in _ROMANOS:
            return _ROMANOS[t]
        if re.fullmatch(r"[2-9]", t):
            return int(t)
    return 1


def discriminante(nome: str, rede: str) -> set[str]:
    """Tokens do nome MENOS o slug da rede, o ruído genérico e os ordinais: sobra o LUGAR.

    O slug da rede sai porque só comparamos dentro da mesma rede — mantê-lo inflaria o Jaccard de
    todo par igualmente, que é o mesmo que não medir nada.
    """
    da_rede = set(_tokens(str(rede).replace("_", " ")))
    return {
        t
        for t in _tokens(nome)
        if len(t) > 2 and t not in RUIDO_NOME and t not in da_rede and t not in _ROMANOS
    }


def similaridade_nome(nome_a: str, nome_b: str, rede: str) -> float:
    """Jaccard dos discriminantes, em `[0, 1]`. `0` quando algum lado não tem discriminante.

    Devolver `0` no caso vazio é deliberado e conservador: um nome sem parte geográfica (ex.:
    `"Performance Academia"`, cujo discriminante é vazio depois de tirar rede e ruído) não afirma
    nada sobre identidade, e afirmar casamento ali colapsaria academias distintas em massa.
    """
    a, b = discriminante(nome_a, rede), discriminante(nome_b, rede)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def mesma_unidade(
    nome_a: str,
    nome_b: str,
    rede: str,
    *,
    limiar_jaccard: float = JACCARD_MIN_NOME,
) -> bool:
    """`True` se os dois nomes descrevem a MESMA unidade da rede. Não olha distância.

    A ordem das duas checagens importa: o ordinal é uma NEGAÇÃO e vem primeiro. `Carpina` e
    `Carpina 2` têm discriminante idêntico (Jaccard `1,00`) e mesmo assim são unidades diferentes —
    se o Jaccard decidisse antes, elas colapsariam.
    """
    if ordinal_da_unidade(nome_a) != ordinal_da_unidade(nome_b):
        return False
    return similaridade_nome(nome_a, nome_b, rede) >= float(limiar_jaccard)


__all__ = [
    "DIST_MAX_MESMO_NOME_M",
    "JACCARD_MIN_NOME",
    "RUIDO_NOME",
    "discriminante",
    "mesma_unidade",
    "ordinal_da_unidade",
    "similaridade_nome",
]
