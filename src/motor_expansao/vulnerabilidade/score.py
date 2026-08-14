"""BLK-MA-04: score de vulnerabilidade (D4) — composição ponderada de S1/S3/S4.

Módulo **PURO QUANDO OS FRAMES SÃO INJETADOS** — e essa ressalva não é preciosismo `[precisão
BLK-MA-04-FU1]`: pelo modo de conveniência `base_dir=` ele lê disco **transitivamente**, delegando
aos dois extratores, que chamam `ler_snapshots`. O que vale em QUALQUER modo é a metade forte: o
módulo **nunca ESCREVE** (travado por `test_modulo_nao_escreve_em_disco`) e nada aqui depende do
universo do lote (travado por `test_v4_nao_depende_do_universo`). Recebe (ou deriva, por
conveniência) os dois insumos já entregues —
`presenca_agregador_v1` (sinal 1, hex-level, BLK-MA-03) e `churn_staleness_v2` (sinais 3 e 4, por
academia, BLK-MA-02) — e devolve o contrato de coluna `score_vulnerabilidade_v2` (22 colunas), com
`score_vulnerabilidade ∈ [0,100]`, os componentes `vi` para auditoria e as flags de qualidade do
§8.4. Materializar artefato, cruzar com hexágono quente e montar a lista comercial são do
**BLK-MA-05**; a flag de staleness do cron é do **BLK-MA-06**.

GRÃO DA LINHA = ACADEMIA, e "academia" aqui é uma CHAVE DE SNAPSHOT, não um estabelecimento
nomeado (universo NOMEADO / D1-B deferido): a mesma academia listada em TotalPass e WellHub são
**duas linhas**, porque a chave embute a `fonte`. É comportamento intencional, travado por
`test_churn_staleness.py::test_mesma_academia_em_duas_fontes_sao_duas_linhas`, e é a razão de o
sinal 1 ser medido por hex (emenda BLK-MA-03 ao §8.1).

O ERRO MAIS CARO DESTE EPIC, e onde ele é barrado: **pontuar uma CADEIA como alvo de aquisição.**
O frame de churn é genérico e traz o feed `unidades` (um CSV por rede de cadeia) e também marcas
conhecidas listadas dentro do TotalPass/WellHub. Sem filtro, a Smart Fit entraria na lista de
alvos de M&A. O universo é fechado aqui, no passo 2, reusando `_filtrar_universo_sinal_1` do sinal
1 (não duplicado: pelo §3/D1 o universo do sinal 1 e o universo de M&A são o MESMO conjunto por
definição), e é travado de novo na fronteira de saída pelo `_assert_schema_score`.

LEITURA HONESTA DO RAMP-UP (registrar antes de qualquer uso comercial): enquanto S3 e S4
estiverem imaturos (~8-12 meses na cadência real, §6/§12 do contrato), o §8.4 os renormaliza para
fora e S1 fica sendo o único sinal — peso renormalizado `1,00` e domínio `{0.0, 0.5}`, logo o
score vive em `{0, 50}`. E **esse `0` NÃO significa "não vulnerável"**: significa apenas "o hex
tem os dois agregadores". É uma afirmação de solidez que ninguém mediu. Por isso a saída traz
`score_vulnerabilidade` (o número auditável do D4, sempre preenchido quando há >= 1 sinal) **e**
`score_vulnerabilidade_ordenavel`, que nasce NULA enquanto `flag_score_provisorio` estiver ligada:
a proibição de ordenar carteira por um score de dois valores vira o TIPO da saída, não uma frase
num handoff arquivado.

EMENDA DA DEC-028: `flag_score_provisorio` é `(~s3) & (~s4) & (~s6)`. Com o insumo de pressão, o
score deixa de ter dois valores e volta a ser ordenável — mas o que ele ordena, nesse regime, é
PRESSÃO COMPETITIVA (`30 + 40·v6`, porque `v1 ≡ 0,5` enquanto só um agregador existe em disco). A
emenda libera o `sort`; a honestidade do rótulo é obrigação de quem exibe.

AUSÊNCIA NUNCA É ZERO: linha sem sinal algum (`n_sinais_disponiveis == 0`) recebe score **NULO**.
`0` é uma afirmação; nulo é ausência de evidência.

O QUE ESTA CAMADA NÃO PROPAGA, POR DECISÃO (achado A7, verificado no código em 2026-07-30): as
colunas `flag_troca_chave_na_serie` (ressalva do `BLK-MA-02-FU1`) e
`n_academias_independentes_totalpass`/`n_academias_independentes_wellhub` (ressalva do
`BLK-MA-03-FU1`) **não entram em componente `vi` algum e não são repassadas**. É o que
desbloqueia este bloco sem esperar os dois FU1 — e a não-propagação é trava executável no
`_assert_schema_score`, não prosa: se um bloco futuro quiser exibi-las, o teste quebra e as
ressalvas voltam a ser bloqueantes em voz alta.

GUARDRAILS: **READ-ONLY sobre o M1** — `score_vulnerabilidade` é PARALELO, não é
`score_priorizacao` nem `hex_score_estrutural`, e a saída rejeita colunas do M1 por schema;
pacote DISJUNTO (nunca importa `pipelines/m1/`, `dashboard/`, `api`, `censo_*`, `config.py` raiz,
`normalizar_concorrentes.py` nem `demanda_revelada`); anti-PII por construção (DEC-012: só chaves
opacas e agregados por hex); não persiste nada em disco; fixtures 100% sintéticas nos testes.
"""

from __future__ import annotations

from pathlib import Path

import h3
import pandas as pd

# `_assert_schema_churn` e `_assert_schema_presenca_agregador` são REUSADOS dos irmãos: validar o
# insumo pelo contrato de origem custa zero e evita que um frame malformado vire score errado.
from .churn_staleness import _assert_schema_churn, extrair_churn_staleness
from .contrato import (
    CATEGORIA_INDEPENDENTE,
    CONTRATO_COLUNAS_SCORE,
    FONTES_AGREGADORES,
    H3_RES_CONTRATO,
    PESOS_ALVO_SINAIS,
    PRESSAO_GRAO_ACADEMIA,
    PRESSAO_GRAO_HEX,
    PRESSAO_GRAOS,
    SINAIS_INATIVOS,
    SINAIS_ORDEM,
    STALE_SEMANAS,
    STATUS_CHURN_VALIDOS,
    V3_POR_STATUS_CHURN,
    VERSAO_CONTRATO_SCORE,
    renormalizar_pesos,
)

# `_filtrar_universo_sinal_1` é IMPORTADO, nunca recriado: o nome diz "sinal 1" e o uso aqui é
# "universo de M&A" porque, pelo §3/D1 do contrato, os dois são o MESMO conjunto por definição
# (academias independentes observadas em TotalPass/WellHub). Duas cópias do predicado criariam
# dois lugares para o universo divergir — que é exatamente o modo de falha do achado A3.
from .presenca_agregador import (
    _assert_schema_presenca_agregador,
    _filtrar_universo_sinal_1,
    extrair_presenca_agregador,
)

# --------------------------------------------------------------------------- #
# Travas executáveis de escopo (o READ-ONLY e o anti-vazamento viram schema)
# --------------------------------------------------------------------------- #
# M1: torna o READ-ONLY do §5 EXECUTÁVEL. Mesmo espírito das travas
# `_COLUNAS_DE_SCORE_PROIBIDAS` dos dois irmãos, mas apontando para FORA do pacote.
_COLUNAS_PROIBIDAS_M1: frozenset[str] = frozenset(
    {
        "score_priorizacao",
        "hex_score_estrutural",
        "score_oficial",
        "renda_pct_nacional",
        "pop_pct_nacional",
    }
)

# BLK-MA-05: impede vazamento de escopo para o bloco seguinte, do mesmo jeito que os irmãos
# impediram o vazamento do score PARA CÁ.
_COLUNAS_PROIBIDAS_MA05: frozenset[str] = frozenset(
    {
        "sam_fitness_potencial",
        "score_oportunidade_residual",
        "hex_quente",
        "tese_entrada",
        "oferta_efetiva_disponivel",
    }
)

# Ressalvas abertas nos FU1: a decisão de "não consumir, não propagar" (A7) vira trava.
_COLUNAS_PROIBIDAS_RESSALVADAS: frozenset[str] = frozenset(
    {
        "flag_troca_chave_na_serie",
        "n_academias_independentes_totalpass",
        "n_academias_independentes_wellhub",
    }
)

# Componente de cada sinal. `s2` aponta para `v2`, que NÃO existe no Plano B (D3): enquanto `s2`
# estiver em `SINAIS_INATIVOS` ele nunca fica disponível, e o BLK-MA-08 reativa o sinal
# acrescentando a coluna e removendo a entrada daquela tupla.
_COLUNA_POR_SINAL: dict[str, str] = {
    "s1": "v1",
    "s2": "v2",
    "s3": "v3",
    "s4": "v4",
    "s6": "v6",
}

# `v1` é CATEGÓRICO (emenda G1 ao §8.1, ratificada em 2026-07-29): mapa literal, NUNCA
# normalização por posição no universo. O domínio de entrada `{1, 2}` é travado pelo contrato do
# sinal 1; o ramo `0 -> 1.0` do §8.1 é inalcançável nesta granularidade e não é implementado.
_V1_POR_N_AGREGADORES: dict[int, float] = {2: 0.0, 1: 0.5}

# Colunas trazidas do sinal 1 pelo join. A projeção é o que mantém as colunas ressalvadas do
# `BLK-MA-03-FU1` fora da saída POR CONSTRUÇÃO, e não por remoção posterior.
_COLUNAS_DO_SINAL_1: tuple[str, ...] = (
    "hex_id_res7",
    "n_agregadores_no_hex",
    "fontes_presentes_no_hex",
)

_MSG_FONTE = "informe `base_dir` ou o par (`churn`, `presenca`)"


def _frame_score_vazio() -> pd.DataFrame:
    """Frame vazio bem-formado, no schema exato do contrato (inclusive dtypes)."""
    return pd.DataFrame(
        {col: pd.Series(dtype=dtype) for col, dtype in CONTRATO_COLUNAS_SCORE.items()}
    )


def _preparar_universo(churn: pd.DataFrame) -> pd.DataFrame:
    """Frame de churn -> universo de M&A (TotalPass/WellHub x `independente`). Não muta a entrada.

    É o passo que impede o erro mais caro do epic (ver docstring do módulo). A `rede` do frame de
    churn é a da ÚLTIMA observação presente (`churn_staleness.py:184`), então o filtro herda de
    graça o P2 do BLK-MA-03: a classificação mais recente vence.
    """
    return _filtrar_universo_sinal_1(churn.copy())


def _juntar_presenca(universo: pd.DataFrame, presenca: pd.DataFrame) -> pd.DataFrame:
    """Left join do sinal 1 (hex-level) no universo (por academia), `validate="many_to_one"`.

    `many_to_one` é obrigatório (molde do §9/D5 e da emenda G1): muitas academias por hex, um hex
    por linha de presença — e ele levanta se a presença trouxer `hex_id_res7` duplicado.

    **Nenhum `raise` por linha sem par.** Hex sem par no sinal 1 é caso previsto pelo §8.4: `v1`
    fica ausente, S1 é renormalizado para fora e o score sai pelos sinais restantes. O miss não
    fica escondido — ele é auditável pela própria saída, pelo biconditional
    `v1` nulo <-> `n_agregadores_no_hex` nulo <-> `"s1"` fora de `sinais_disponiveis`.
    """
    df = universo.merge(
        presenca[list(_COLUNAS_DO_SINAL_1)],
        on="hex_id_res7",
        how="left",
        validate="many_to_one",
    )
    # P1: no miss o pandas promove a coluna a `float64` + `NaN`; o `int64` nativo não carrega
    # nulo. A coluna da SAÍDA é `Int64` (nulável) por causa disso.
    df["n_agregadores_no_hex"] = df["n_agregadores_no_hex"].astype("Int64")
    df["fontes_presentes_no_hex"] = df["fontes_presentes_no_hex"].astype("string")
    return df


def _juntar_pressao(df: pd.DataFrame, pressao: pd.DataFrame | None) -> pd.DataFrame:
    """Left join da pressão no universo, nos DOIS grãos possíveis. `None` -> colunas NULAS.

    O grão é decidido pelo FORMATO do frame, não por um parâmetro — quem produziu o insumo já sabe
    o que mediu, e um parâmetro criaria a chance de declarar um grão e passar o outro:

    | frame tem | grão | join |
    |---|---|---|
    | `fonte` + `chave_snapshot` | `academia` (BLK-MA-14, o default do pipeline) | `1:1` pela chave primária |
    | `hex_id_res7` | `hex` (o grão antigo, do centroide) | `many_to_one` |

    O carimbo `pressao_grao` viaja até a saída porque **duas linhas com grãos diferentes não estão
    na mesma régua** — a pressão de academia varia dentro do hexágono (amplitude média medida:
    14,89 pontos) e a de hex, não. Sem o carimbo, um consumidor compararia as duas sem saber.

    Nulo, jamais `0`: na régua do §8.1 `v6 = 0` afirma "ninguém espremendo", a leitura mais
    otimista possível. "Não recebi o insumo" tem de ser distinguível de "medi e não há" — é a mesma
    regra que vale para o `v1` no miss do join do sinal 1.
    """
    out = df.copy()
    if pressao is None or pressao.empty:
        out["pressao_competitiva"] = pd.Series(float("nan"), index=out.index, dtype="float64")
        out["pressao_grao"] = pd.Series(pd.NA, index=out.index, dtype="string")
        return out

    por_academia = {"fonte", "chave_snapshot"} <= set(pressao.columns)
    por_hex = "hex_id_res7" in pressao.columns
    if not (por_academia or por_hex):
        raise ValueError(
            "frame de pressao fora do contrato: exige `(fonte, chave_snapshot)` (grao academia) "
            "ou `hex_id_res7` (grao hex)"
        )

    if por_academia:
        chaves = ["fonte", "chave_snapshot"]
        # Cada grão carrega o NOME de coluna do seu próprio contrato: `pressao_competitiva` no de
        # academia, `pressao_competitiva_no_hex` no de hex (que mantém o sufixo porque é a
        # grandeza comparável com o `pressao_concorrencial_score_2km` da camada de mercado).
        # Uniformizar aqui, na leitura, é mais barato que renomear um contrato já publicado.
        coluna = "pressao_competitiva"
        if bool(pressao.duplicated(subset=chaves).any()):
            raise ValueError("frame de pressao com `(fonte, chave_snapshot)` duplicado")
        grao = PRESSAO_GRAO_ACADEMIA
    else:
        chaves = ["hex_id_res7"]
        coluna = "pressao_competitiva_no_hex"
        if bool(pressao["hex_id_res7"].duplicated().any()):
            raise ValueError("frame de pressao com `hex_id_res7` duplicado: o join seria ambiguo")
        grao = PRESSAO_GRAO_HEX
    if coluna not in pressao.columns:
        raise ValueError(f"frame de pressao (grao {grao}) sem a coluna `{coluna}`")

    # `many_to_one` nos dois casos: o universo de M&A é um SUBCONJUNTO do insumo (o filtro de
    # cadeia já rodou), então sobram linhas de pressão sem par à esquerda — esperado. O que não
    # pode haver é duplicata à direita, e os guards acima já barraram.
    projecao = pressao[[*chaves, coluna]].copy().rename(columns={coluna: "pressao_competitiva"})
    for chave in chaves:
        projecao[chave] = projecao[chave].astype("string")
        out[chave] = out[chave].astype("string")
    out = out.merge(projecao, on=chaves, how="left", validate="many_to_one")
    out["pressao_competitiva"] = pd.to_numeric(
        out["pressao_competitiva"], errors="coerce"
    ).astype("float64")
    # O carimbo acompanha o VALOR: linha sem par no join fica sem pressão E sem grão. Carimbar o
    # grão numa linha sem medição afirmaria uma procedência que não existe.
    out["pressao_grao"] = (
        pd.Series(grao, index=out.index, dtype="string")
        .where(out["pressao_competitiva"].notna())
        .astype("string")
    )
    return out


def _regra_de_disponibilidade(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Regra do §8.4 por linha, ANTES de olhar o componente.

    | sinal | disponível quando |
    |---|---|
    | `s1` | a linha casou no join com o sinal 1 (`n_agregadores_no_hex` não nulo) |
    | `s2` | nunca — está em `SINAIS_INATIVOS` (rating é `n/d` permanente, D3) |
    | `s3` | `flag_serie_imatura == False` |
    | `s4` | `flag_staleness_interpretavel == True` |

    `s1` **não** é renormalizado para fora por meia-faixa (emenda G1): `v1 = 0.5` é observado e
    maduro, não ausente. E `s4` disponível IMPLICA `s3` disponível, porque
    `STALE_SEMANAS > MIN_SEMANAS` — mas isso é consequência das constantes, não regra: nada aqui
    depende disso, e a implicação é travada por teste.
    """
    indice = df.index
    regras: dict[str, pd.Series] = {
        "s1": df["n_agregadores_no_hex"].notna(),
        "s2": pd.Series(False, index=indice),
        "s3": ~df["flag_serie_imatura"].astype(bool),
        "s4": df["flag_staleness_interpretavel"].astype(bool),
        # `s6` disponível SE E SOMENTE SE o insumo de pressão foi fornecido na chamada — o mesmo
        # princípio do `s1` (casou no join). NÃO é "sempre disponível", e a diferença é estrutural:
        # um S6 sempre presente extinguiria o regime `n_sinais_disponiveis == 0` e tornaria
        # INALCANÇÁVEL a invariante "ausência nunca é zero", que é o guardrail mais antigo desta
        # camada. Aqui, quem não passa pressão obtém exatamente o score de antes — os pesos
        # efetivos do Plano B inclusive, porque `renormalizar_pesos` divide pelos PRESENTES.
        "s6": (
            df["pressao_competitiva"].notna()
            if "pressao_competitiva" in df.columns
            else pd.Series(False, index=indice)
        ),
    }
    for sinal in SINAIS_INATIVOS:
        regras[sinal] = pd.Series(False, index=indice)
    return regras


def _derivar_componentes(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta `v1`, `v3` e `v4`, já mascarados para `NaN` onde o sinal está indisponível.

    Cada `vi` é calculado para TODAS as linhas e só então mascarado — é mais simples e mais
    testável que calcular-só-onde-disponível, e o mascaramento passa a ser a única fonte de `NaN`
    nos componentes.

    A disponibilidade efetiva é a regra do §8.4 **e** o componente bruto ser não-nulo. A segunda
    metade só morde no estado `novo` do `status_churn` (achado A5: `V3_POR_STATUS_CHURN["novo"]`
    é ausente de propósito, nunca `0.0`), que por construção já é sempre `flag_serie_imatura`.
    Escrever assim mantém o biconditional "sinal disponível <-> componente não nulo" verdadeiro
    por CONSTRUÇÃO, inclusive para um frame forjado à mão.
    """
    out = df.copy()

    v1_bruto = out["n_agregadores_no_hex"].map(_V1_POR_N_AGREGADORES).astype("float64")
    v3_bruto = out["status_churn"].astype(str).map(V3_POR_STATUS_CHURN).astype("float64")
    # `v4` é RAZÃO ABSOLUTA (§8.1 literal; §8.2 emendado pelo G-D3 em 2026-07-30), jamais uma
    # posição relativa dentro do universo: esta linha é o que torna o score monotônico no sinal
    # que ele diz medir, reprodutível fora do lote e calculável linha a linha.
    v4_bruto = (out["semanas_sem_mudanca"].astype("float64") / float(STALE_SEMANAS)).clip(
        lower=0.0, upper=1.0
    )
    # `v6` já vem em [0,1) do `pressao_competitiva`; aqui é só leitura, não normalização — a régua
    # é ABSOLUTA como a do `v4` (G-D3), nunca percentil do lote.
    v6_bruto = (
        out["pressao_competitiva"].astype("float64") / 100.0
        if "pressao_competitiva" in out.columns
        else pd.Series(float("nan"), index=out.index, dtype="float64")
    )

    regras = _regra_de_disponibilidade(out)
    for sinal, bruto in (
        ("s1", v1_bruto),
        ("s3", v3_bruto),
        ("s4", v4_bruto),
        ("s6", v6_bruto),
    ):
        out[_COLUNA_POR_SINAL[sinal]] = bruto.where(regras[sinal] & bruto.notna())
    return out


def _disponibilidade_efetiva(df: pd.DataFrame) -> dict[str, pd.Series]:
    """`{sinal: máscara}` lida dos COMPONENTES já mascarados — o biconditional por construção."""
    disponivel: dict[str, pd.Series] = {}
    for sinal in SINAIS_ORDEM:
        coluna = _COLUNA_POR_SINAL[sinal]
        if sinal in SINAIS_INATIVOS or coluna not in df.columns:
            disponivel[sinal] = pd.Series(False, index=df.index)
        else:
            disponivel[sinal] = df[coluna].notna()
    return disponivel


def _string_canonica(disponivel: dict[str, pd.Series], indice: pd.Index) -> pd.Series:
    """`sinais_disponiveis` iterando `SINAIS_ORDEM` — nunca um `set`, nunca chaves de dict."""
    acc = pd.Series("", index=indice, dtype="object")
    for sinal in SINAIS_ORDEM:
        marca = disponivel[sinal]
        concatenado = acc.where(acc.eq(""), acc + ",") + sinal
        acc = concatenado.where(marca, acc)
    return acc.astype("string")


def _compor_score(df: pd.DataFrame) -> pd.DataFrame:
    """Renormaliza, soma, aplica as flags e projeta exatamente as 22 colunas do contrato.

    A renormalização é GENÉRICA (`renormalizar_pesos` sobre `PESOS_ALVO_SINAIS`): os pesos
    efetivos do Plano B são consequência de S2 estar inativo, e nenhum deles é digitado. Há no
    máximo `2^3 = 8` padrões de disponibilidade (na prática <= 6), então o agrupamento por
    `sinais_disponiveis` resolve o frame inteiro com <= 6 chamadas e soma vetorizada — sem
    `.apply(axis=1)`.
    """
    out = df.copy()
    disponivel = _disponibilidade_efetiva(out)
    out["sinais_disponiveis"] = _string_canonica(disponivel, out.index)

    n_sinais = pd.Series(0, index=out.index, dtype="int64")
    for sinal in SINAIS_ORDEM:
        n_sinais = n_sinais + disponivel[sinal].astype("int64")

    score = pd.Series(float("nan"), index=out.index, dtype="float64")
    for padrao, bloco in out.groupby("sinais_disponiveis", sort=True):
        tokens = [t for t in str(padrao).split(",") if t]
        pesos = renormalizar_pesos(tokens)
        if not pesos:
            # Nenhum sinal disponível -> score AUSENTE. Jamais `0`: `0` afirmaria solidez.
            continue
        parcial = pd.Series(0.0, index=bloco.index)
        for sinal, peso in pesos.items():
            parcial = parcial + peso * bloco[_COLUNA_POR_SINAL[sinal]].astype("float64")
        score.loc[bloco.index] = (100.0 * parcial).clip(lower=0.0, upper=100.0)

    # Escrita como a CONJUNÇÃO do §8.4, fiel ao texto, embora a parte S3/S4 seja redutível a
    # "S3 indisponível" por `STALE_SEMANAS > MIN_SEMANAS`. A redução é testada, não assumida.
    #
    # `& (~s6)` é a EMENDA DA DEC-028, e ela tem um motivo medido: sem o S6 na conjunção,
    # `score_vulnerabilidade_ordenavel` saía **NULA em 19.329 de 19.329** academias reais, e um
    # `sort_values` devolvia `NaN` em tudo. O G-D1 virou o TIPO da saída para impedir ranking sobre
    # o ramp-up **só-S1 de DOIS valores** (`{0, 50}`); o S6 é contínuo, então o objeto que o G-D1
    # protegia deixa de existir assim que a pressão entra. A emenda libera a ORDENAÇÃO e **não**
    # conserta o SIGNIFICADO — quem carrega a honestidade do rótulo é a superfície.
    provisorio = (~disponivel["s3"]) & (~disponivel["s4"]) & (~disponivel["s6"])

    out["n_sinais_disponiveis"] = n_sinais
    out["score_vulnerabilidade"] = score
    out["flag_score_provisorio"] = provisorio
    out["score_vulnerabilidade_ordenavel"] = score.where(~provisorio)
    out["versao_contrato"] = VERSAO_CONTRATO_SCORE

    out = out[list(CONTRATO_COLUNAS_SCORE.keys())].copy()
    for coluna, dtype in CONTRATO_COLUNAS_SCORE.items():
        out[coluna] = out[coluna].astype(dtype)
    return out.sort_values(["fonte", "chave_snapshot"], kind="mergesort").reset_index(drop=True)


def _assert_schema_score(df: pd.DataFrame) -> None:
    """Falha alto se o frame não é exatamente o contrato `VERSAO_CONTRATO_SCORE`.

    A versão vive na constante, não neste texto — cravá-la aqui já ficou stale no bump
    `v1` -> `v2` do BLK-MA-09 (mesma armadilha corrigida em `snapshots.py`).
    """
    esperado = list(CONTRATO_COLUNAS_SCORE.keys())
    presentes = set(df.columns)

    # A ordem das três primeiras checagens importa: a mensagem genérica de "coluna fora do
    # contrato" venceria e o motivo REAL da rejeição se perderia.
    do_m1 = sorted(presentes & _COLUNAS_PROIBIDAS_M1)
    if do_m1:
        raise ValueError(
            f"coluna do M1 na saida do score (camada PARALELA, READ-ONLY sobre o M1): {do_m1}"
        )
    do_ma05 = sorted(presentes & _COLUNAS_PROIBIDAS_MA05)
    if do_ma05:
        raise ValueError(f"coluna de escopo do BLK-MA-05 na saida do score: {do_ma05}")
    ressalvadas = sorted(presentes & _COLUNAS_PROIBIDAS_RESSALVADAS)
    if ressalvadas:
        raise ValueError(
            f"coluna com ressalva aberta nos FU1, nao consumida nem propagada: {ressalvadas}"
        )
    extras = presentes - set(esperado)
    if extras:
        raise ValueError(f"colunas fora do contrato: {sorted(extras)}")
    faltando = set(esperado) - presentes
    if faltando:
        raise ValueError(f"colunas do contrato ausentes: {sorted(faltando)}")
    if list(df.columns) != esperado:
        raise ValueError(f"ordem de colunas fora do contrato: {list(df.columns)}")
    if df.empty:
        return

    invalidos: list[str] = []
    for hid in df["hex_id_res7"].astype(str).unique():
        if not h3.is_valid_cell(hid) or h3.get_resolution(hid) != H3_RES_CONTRATO:
            invalidos.append(hid)
            if len(invalidos) >= 5:
                break
    if invalidos:
        raise ValueError(f"hex_id_res7 fora de res-{H3_RES_CONTRATO}: amostra {invalidos}")

    dup = int(df.duplicated(subset=["fonte", "chave_snapshot"]).sum())
    if dup > 0:
        raise ValueError(f"chave (fonte, chave_snapshot) duplicada: {dup} linha(s)")

    # Universo de M&A travado na fronteira de SAÍDA, além do filtro na entrada (achado A3).
    fontes_fora = sorted(set(df["fonte"].astype(str)) - set(FONTES_AGREGADORES))
    if fontes_fora:
        raise ValueError(
            f"universo de M&A violado; `fonte` fora dos agregadores: {fontes_fora}"
        )
    redes_fora = sorted(set(df["rede"].astype(str)) - {CATEGORIA_INDEPENDENTE})
    if redes_fora:
        raise ValueError(f"universo de M&A violado; `rede` nao independente: {redes_fora}")

    status_fora = sorted(set(df["status_churn"].astype(str)) - set(STATUS_CHURN_VALIDOS))
    if status_fora:
        raise ValueError(f"status_churn fora do contrato: {status_fora}")

    v1 = df["v1"].astype("float64")
    v3 = df["v3"].astype("float64")
    v4 = df["v4"].astype("float64")
    score = df["score_vulnerabilidade"].astype("float64")

    fora_v1 = sorted({float(v) for v in v1.dropna()} - set(_V1_POR_N_AGREGADORES.values()))
    if fora_v1:
        raise ValueError(f"`v1` fora do dominio categorico {{0.0, 0.5}}: {fora_v1}")
    dominio_v3 = {float(v) for v in V3_POR_STATUS_CHURN.values() if v is not None}
    fora_v3 = sorted({float(v) for v in v3.dropna()} - dominio_v3)
    if fora_v3:
        raise ValueError(f"`v3` fora do dominio categorico {sorted(dominio_v3)}: {fora_v3}")
    if bool(((v4 < 0.0) | (v4 > 1.0)).any()):
        raise ValueError("`v4` fora do dominio [0, 1]")
    v6 = df["v6"].astype("float64")
    if bool(((v6 < 0.0) | (v6 >= 1.0)).any()):
        raise ValueError("`v6` fora do dominio [0, 1)")
    if bool((v6.isna() != df["pressao_competitiva"].isna()).any()):
        raise ValueError(
            "biconditional do S6 violado: `v6` nulo deve equivaler a `pressao_competitiva` nulo"
        )
    # O carimbo de GRAO acompanha o valor: presente exatamente onde ha pressao. Um grao sem
    # pressao afirmaria procedencia inexistente; pressao sem grao esconderia a regua usada, e e'
    # justamente a regua que nao pode ser comparada entre linhas (BLK-MA-14).
    if bool((df["pressao_grao"].isna() != df["pressao_competitiva"].isna()).any()):
        raise ValueError(
            "`pressao_grao` deve estar preenchido exatamente onde `pressao_competitiva` esta"
        )
    graos = sorted(set(df["pressao_grao"].dropna().astype(str)) - set(PRESSAO_GRAOS))
    if graos:
        raise ValueError(f"`pressao_grao` fora do dominio {list(PRESSAO_GRAOS)}: {graos}")
    if bool(((score < 0.0) | (score > 100.0)).any()):
        raise ValueError("`score_vulnerabilidade` fora do dominio [0, 100]")

    texto = df["sinais_disponiveis"].astype(str)
    for valor in sorted(set(texto)):
        tokens = [t for t in valor.split(",") if t]
        desconhecidos = sorted(set(tokens) - set(SINAIS_ORDEM))
        if desconhecidos:
            raise ValueError(f"`sinais_disponiveis` com token desconhecido: {desconhecidos}")
        if len(set(tokens)) != len(tokens):
            raise ValueError(f"`sinais_disponiveis` com token repetido: {valor!r}")
        if tokens != [s for s in SINAIS_ORDEM if s in set(tokens)]:
            raise ValueError(f"`sinais_disponiveis` fora da ordem canonica: {valor!r}")
        inativos = sorted(set(tokens) & set(SINAIS_INATIVOS))
        if inativos:
            raise ValueError(f"sinal INATIVO em `sinais_disponiveis`: {inativos}")

    n_tokens = texto.map(lambda v: len([t for t in v.split(",") if t])).astype("int64")
    n_sinais = df["n_sinais_disponiveis"].astype("int64")
    if bool((n_tokens != n_sinais).any()):
        raise ValueError("`n_sinais_disponiveis` incoerente com `sinais_disponiveis`")

    tem: dict[str, pd.Series] = {
        sinal: texto.map(lambda v, s=sinal: s in v.split(",")) for sinal in ("s1", "s3", "s4", "s6")
    }
    for sinal in ("s1", "s3", "s4", "s6"):
        coluna = _COLUNA_POR_SINAL[sinal]
        if bool((tem[sinal] != df[coluna].notna()).any()):
            raise ValueError(
                f"biconditional violado: `{sinal}` em `sinais_disponiveis` "
                f"deve equivaler a `{coluna}` nao nulo"
            )

    if bool((v1.isna() != df["n_agregadores_no_hex"].isna()).any()):
        raise ValueError(
            "biconditional do join violado: `v1` nulo deve equivaler a "
            "`n_agregadores_no_hex` nulo"
        )
    if bool((df["n_agregadores_no_hex"].isna() != df["fontes_presentes_no_hex"].isna()).any()):
        raise ValueError(
            "biconditional do join violado: `n_agregadores_no_hex` nulo deve equivaler a "
            "`fontes_presentes_no_hex` nulo"
        )

    sem_sinal = n_sinais == 0
    if bool((sem_sinal & (score.fillna(-1.0) == 0.0)).any()):
        raise ValueError(
            "linha sem sinal algum com `score_vulnerabilidade` 0.0: ausencia nunca e zero"
        )
    if bool((sem_sinal != score.isna()).any()):
        raise ValueError(
            "`n_sinais_disponiveis == 0` deve equivaler a `score_vulnerabilidade` NULO"
        )

    provisorio = df["flag_score_provisorio"].astype(bool)
    # A conjunção inclui o `s6` desde a DEC-028 — ver o comentário longo em `_compor_score`.
    if bool((provisorio != ((~tem["s3"]) & (~tem["s4"]) & (~tem["s6"]))).any()):
        raise ValueError(
            "`flag_score_provisorio` incoerente com `sinais_disponiveis` (S3, S4 e S6 fora)"
        )
    ordenavel = df["score_vulnerabilidade_ordenavel"].astype("float64")
    nulo_esperado = provisorio | score.isna()
    if bool((ordenavel.isna() != nulo_esperado).any()):
        raise ValueError(
            "`score_vulnerabilidade_ordenavel` deve ser NULO exatamente quando o score e "
            "provisorio ou ausente"
        )
    comparaveis = ~nulo_esperado
    if bool((ordenavel[comparaveis] != score[comparaveis]).any()):
        raise ValueError(
            "`score_vulnerabilidade_ordenavel` difere do score fora do regime provisorio"
        )

    versoes = sorted(set(df["versao_contrato"].astype(str)) - {VERSAO_CONTRATO_SCORE})
    if versoes:
        raise ValueError(f"versao_contrato inesperada: {versoes}")


def calcular_score_vulnerabilidade(
    base_dir: Path | None = None,
    *,
    churn: pd.DataFrame | None = None,
    presenca: pd.DataFrame | None = None,
    pressao: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Insumos -> frame `score_vulnerabilidade_v3` (24 colunas), 1 linha por academia.

    Informe `base_dir` (conveniência: deriva os DOIS frames da MESMA série, numa só chamada) **ou**
    o par (`churn`, `presenca`) já pronto. Com o par injetado a função é **pura** — é assim que os
    testes rodam sem I/O — e o chamador passa a ser o dono da consistência entre os dois frames.

    `pressao` (BLK-MA-12) é **OPCIONAL e ortogonal** aos outros dois, e vale para os dois modos: é
    o frame de `pressao_competitiva.calcular_pressao_por_hex`, com uma linha por `hex_id_res7`.
    Ele não sai da `base_dir` de propósito — a pressão vem do parquet de PONTOS de concorrentes,
    que não vive junto dos snapshots.

    **Omitir `pressao` devolve exatamente o score de antes**, bit a bit: o `s6` fica indisponível,
    `renormalizar_pesos` normaliza só pelos presentes e os pesos efetivos do Plano B seguem
    `0,20 / 0,4667 / 0,3333`. Isso é o que permite o S6 existir sem repesar S1..S4 e sem extinguir
    o regime `n_sinais_disponiveis == 0` — a invariante "ausência nunca é zero" continua alcançável
    e continua travada.

    Algoritmo, em passos:

    | # | passo | por quê |
    |---|---|---|
    | 1 | validar os insumos pelos contratos de origem | frame malformado não vira score errado |
    | 2 | **filtrar o universo de M&A** (TP/WH x independente) | sem isto uma CADEIA vira alvo |
    | 3 | join `many_to_one` do sinal 1 (hex) no universo (academia) | S1 é por hex, S3/S4 por academia |
    | 3b | join `many_to_one` da pressão (hex), se fornecida | S6 é por hex, como o S1 |
    | 4 | componentes `v1`/`v3`/`v4`/`v6`, mascarados por disponibilidade | §8.1 |
    | 5 | renormalizar os pesos-alvo e somar | §8.3/§8.4, genérico |
    | 6 | flags de qualidade e schema de saída | §8.4/§8.5 |

    `score_vulnerabilidade = 100 · Σ(wi · vi)` sobre os sinais DISPONÍVEIS, com os pesos-alvo
    reescalados para somar `1`. Nenhum `NaN` entra na soma (as parcelas são exatamente as dos
    sinais disponíveis) e em nenhum momento um componente ausente é tratado como `0` — que é
    precisamente o defeito que o §8.4 existe para evitar.
    """
    if base_dir is None:
        if churn is None or presenca is None:
            raise ValueError(_MSG_FONTE)
    elif churn is not None or presenca is not None:
        raise ValueError(_MSG_FONTE)

    if base_dir is not None:
        # Os dois extratores na MESMA `base_dir` e na mesma chamada: é isto que garante que os
        # frames venham da MESMA série (a invariância que torna o join sem `left_only`).
        churn = extrair_churn_staleness(Path(base_dir))
        presenca = extrair_presenca_agregador(Path(base_dir))

    if churn is None or presenca is None:  # pragma: no cover - a regra acima já garantiu
        raise ValueError(_MSG_FONTE)

    _assert_schema_churn(churn)
    if churn.empty:
        vazio = _frame_score_vazio()
        _assert_schema_score(vazio)
        return vazio
    _assert_schema_presenca_agregador(presenca)

    universo = _preparar_universo(churn)
    if universo.empty:
        vazio = _frame_score_vazio()
        _assert_schema_score(vazio)
        return vazio

    df = _juntar_presenca(universo, presenca)
    df = _juntar_pressao(df, pressao)
    df = _derivar_componentes(df)
    out = _compor_score(df)
    _assert_schema_score(out)
    return out


__all__ = [
    "calcular_score_vulnerabilidade",
    "CONTRATO_COLUNAS_SCORE",
    "VERSAO_CONTRATO_SCORE",
    "PESOS_ALVO_SINAIS",
    "SINAIS_ORDEM",
    "SINAIS_INATIVOS",
    "V3_POR_STATUS_CHURN",
    "renormalizar_pesos",
]
