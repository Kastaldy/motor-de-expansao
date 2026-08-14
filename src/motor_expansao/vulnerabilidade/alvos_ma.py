"""BLK-MA-05: lista priorizada de alvos de M&A — hexágono quente (D5) + entregável (D6).

É o último elo do epic: os quatro blocos anteriores produzem insumo, e este é o único que **sai do
repositório** e vai para a mesa do comercial. Recebe a saída do `score.py` (grão ACADEMIA, 22
colunas) e a carteira de mercado (grão HEX), cruza as duas e materializa os dois artefatos do D6.

A INVERSÃO DO §2, que é a razão de este bloco existir e o erro mais fácil de cometer nele:
**comprar não é abrir.** Abrir quer residual ALTO (mercado com capacidade não atendida); comprar
quer o OPOSTO — demanda ALTA + residual BAIXO, mercado **saturado**, onde já não cabe abrir mas
cabe adquirir quem já opera. Por isso o hex quente **não** reusa `tese_entrada == "abrir_agora"`:
ele é `sam_fitness_potencial` no top quartil **AND** `score_oportunidade_residual < 25`.

GRÃO DA SAÍDA, e por que são dois:
  - `vulnerabilidade_ma_academias.parquet` — uma linha por ACADEMIA (`(fonte, chave_snapshot)`),
    que é o grão do score, com o hotness do hex propagado por join.
  - `alvos_ma_priorizados.csv` — uma linha por **(HEX, REGIME DE SINAIS)**, hex-level e sem
    identidade (D1 Opção A / DEC-012).

O REGIME NA CHAVE DO CSV NÃO É ZELO EXCESSIVO — é a emenda `BLK-MA-04-FU1` aplicada à AGREGAÇÃO.
Linhas de regimes diferentes não estão na mesma régua: um `{s3}` com `sumiu_recente` sai com
`score_vulnerabilidade = 100,0` e bate qualquer `{s1,s3,s4}` com os três sinais medidos. Uma média
por hex que atravesse regimes mistura as réguas **antes** de qualquer `sort` — não devolve `NaN`,
não levanta, e o erro só aparece na shortlist. E segmentar pelo CONTADOR não basta: `{s1,s3}` e
`{s3,s4}` têm ambos `n = 2` e renormalizações diferentes. A chave é a **composição**
(`sinais_disponiveis`); o contador viaja junto por legibilidade e para ser a chave primária da
ordenação.

READ-ONLY, e aqui isso é executável, não promessa: a carteira entra por parâmetro, é copiada antes
de qualquer coisa, e o join carrega os asserts de invariância do molde
`enriquecer_dataframe_com_residual` (`pipelines/enriquecer_outputs_residual_mercado.py`, ancorado
pelo NOME porque o ponteiro de linha já apodreceu uma vez). Se o merge alterar a cardinalidade, o
`score_priorizacao` ou qualquer um dos 4 ranks, o assert derruba. **Nada aqui escreve em carteira,
mercado, plano ou artefato oficial do M1.**

CORTE SOBRE NOTA/CONTAGEM — DECLARAÇÃO EXIGIDA PELA DEC-026: **este entregável não faz nenhum.**
A nota e a contagem viajam como FATOS agregados (`n_com_nota_wellhub`, `nota_wellhub_mediana`) e
**não entram em filtro, em ordenação nem em qualquer critério de seleção**. A ordenação é por
`n_sinais_disponiveis` e depois pelo score. É deliberado, e a razão é medida: a ausência de nota
não é aleatória — 8.443 independentes do próprio WellHub (14,9% do universo) não têm nota, todos
com `qtd_avaliacoes = 0`, e são academias novas ou de baixíssimo tráfego, exatamente o perfil que o
funil de M&A mais quer olhar. Cortar por nota aqui montaria, fora do contrato versionado, um
ranking de um sinal só sobre 60% do universo, com os outros 40% invisíveis por construção. Se um
consumidor futuro quiser esse corte, a obrigação de documentá-lo é dele — e as duas colunas andam
juntas de propósito, porque nota sem contagem ao lado põe no topo academias cujo sinal são três
avaliações (das 158 abaixo de 4,0, a mediana é de 10,5 avaliações).

ANTI-PII (DEC-012): a entrada já é anti-PII por construção (chaves opacas, geometria só por
`hex_id_res7`), e o CSV é agregado sem identidade. A variante NOMEADA segue deferida (D1-B); se um
dia existir, nasce `gitignored`.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable, Sequence
from pathlib import Path

import h3
import pandas as pd

from .contrato import (
    ADJACENCIA_HEX_QUENTE_K,
    COLUNAS_HOTNESS_CARTEIRA,
    COLUNAS_M1_INVARIANTES,
    CONTRATO_COLUNAS_ACADEMIAS_MA,
    CONTRATO_COLUNAS_ALVOS_MA,
    CONTRATO_COLUNAS_SCORE,
    H3_RES_CONTRATO,
    LIMIAR_RESIDUAL_SATURADO,
    QUANTIL_SAM_QUENTE,
    VERSAO_CONTRATO_ALVOS_MA,
)

_logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CARTEIRA_PATH_DEFAULT = ROOT / "data" / "outputs" / "carteira_expansao_acionavel.parquet"
ACADEMIAS_PATH_DEFAULT = ROOT / "data" / "staging" / "vulnerabilidade_ma_academias.parquet"
ALVOS_CSV_DEFAULT = ROOT / "data" / "outputs" / "alvos_ma_priorizados.csv"

# A chave de join tem nome diferente dos dois lados: `hex_id` na carteira, `hex_id_res7` na
# academia. Mesmo conteúdo, e a diferença é herdada — renomear qualquer um dos dois seria mudança
# em artefato alheio.
_COL_HEX_CARTEIRA = "hex_id"
_COL_HEX_ACADEMIA = "hex_id_res7"

_MSG_FONTE = "informe `score` e `carteira`, ou os caminhos correspondentes"


def _frame_vazio(contrato: dict[str, str]) -> pd.DataFrame:
    """Frame vazio bem-formado, no schema exato do contrato (inclusive dtypes)."""
    return pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in contrato.items()})


def _projetar(df: pd.DataFrame, contrato: dict[str, str]) -> pd.DataFrame:
    """Projeta exatamente as colunas do contrato, na ordem, com os dtypes declarados."""
    out = df[list(contrato.keys())].copy()
    for coluna, dtype in contrato.items():
        out[coluna] = out[coluna].astype(dtype)
    return out


# --------------------------------------------------------------------------- #
# D5 — hexágono quente
# --------------------------------------------------------------------------- #
def marcar_hex_quente(
    carteira: pd.DataFrame,
    *,
    quantil_sam: float = QUANTIL_SAM_QUENTE,
    limiar_residual: float = LIMIAR_RESIDUAL_SATURADO,
) -> pd.DataFrame:
    """Carteira -> `[hex_id, hex_quente, <hotness>, <invariantes do M1>]`. Não muta a entrada.

    A conjunção do D5 (gate de 2026-07-23, reabrir exige DEC): `sam_fitness_potencial` no top
    quartil **do universo** E `score_oportunidade_residual < 25`.

    **O quartil é do universo, não do subconjunto com SAM positivo** — e a diferença importa:
    63% da carteira tem `sam_fitness_potencial == 0`, o que faz o `q75` cair em ~7,5, um número que
    não se parece com "SAM alto". É deliberado e é o que o gate ratificou: o corte seleciona o
    quartil superior, e quem quiser mudá-lo mede **sobre o top quartil**, nunca sobre o universo (a
    razão entre as duas leituras é de 4x) e abre DEC.
    """
    if _COL_HEX_CARTEIRA not in carteira.columns:
        raise AssertionError(f"carteira sem `{_COL_HEX_CARTEIRA}` para o join de hotness")
    for coluna in ("sam_fitness_potencial", "score_oportunidade_residual"):
        if coluna not in carteira.columns:
            raise AssertionError(f"carteira sem `{coluna}`: o D5 nao e' calculavel")

    base = carteira.copy()
    sam = pd.to_numeric(base["sam_fitness_potencial"], errors="coerce")
    residual = pd.to_numeric(base["score_oportunidade_residual"], errors="coerce")

    if base.empty:
        corte_sam = float("nan")
        quente = pd.Series(dtype="bool")
    else:
        corte_sam = float(sam.quantile(quantil_sam))
        # GUARDA CONTRA DEGENERAÇÃO DO QUARTIL, e ela não é hipotética: 63% da carteira tem
        # `sam_fitness_potencial == 0`. Em qualquer recorte onde os zeros passem de 75% (medido:
        # 12 das 27 UFs, SP entre elas), `corte_sam` vira `0.0` — e `sam >= 0` é verdade para o
        # universo INTEIRO. A metade "demanda alta" do D5 desapareceria em silêncio e `hex_quente`
        # colapsaria em `residual < 25`: em SP isso marcaria 354 hexes de SAM ZERO como quentes,
        # na lista que vai para a mesa do comercial.
        #
        # Exigir SAM estritamente positivo **não reabre o D5** nem muda o resultado nacional (lá o
        # corte é 7,53 e já exclui os zeros; 836 quentes antes e depois) — apenas impede que "top
        # quartil" signifique "tudo" quando o quartil é zero.
        if corte_sam <= 0.0:
            _logger.warning(
                "quartil de `sam_fitness_potencial` degenerado (q%.0f = %.4f): o recorte tem "
                "zeros demais. Mantendo apenas SAM > 0 como demanda alta.",
                quantil_sam * 100,
                corte_sam,
            )
        quente = (sam >= corte_sam) & (sam > 0.0) & (residual < float(limiar_residual))

    out = pd.DataFrame({_COL_HEX_CARTEIRA: base[_COL_HEX_CARTEIRA].astype("string")})
    out["hex_quente"] = quente.fillna(False).astype(bool) if not base.empty else quente
    for coluna in (*COLUNAS_HOTNESS_CARTEIRA, *COLUNAS_M1_INVARIANTES):
        if coluna in base.columns:
            out[coluna] = base[coluna].to_numpy()
    out.attrs["corte_sam"] = corte_sam
    return out


def _vizinhanca_quente(hexes_quentes: Iterable[str], k: int = ADJACENCIA_HEX_QUENTE_K) -> set[str]:
    """Hexes quentes -> conjunto dos hexes ADJACENTES a eles (o centro **não** entra).

    Devolver só o anel é o que permite ao chamador distinguir `hex_quente` de `hex_quente_vizinho`
    — a disjunção do §9 é montada depois, e as duas metades ficam auditáveis em separado.

    `h3.grid_disk` **levanta** `H3CellInvalidError` para célula inválida (não devolve vazio), e a
    lista de hexes vem de artefato externo: por isso a validação é explícita, e o hex inválido é
    ignorado com aviso em vez de derrubar a materialização inteira por um dado sujo de terceiro.
    """
    anel: set[str] = set()
    centros: set[str] = set()
    invalidos = 0
    for hex_id in hexes_quentes:
        texto = str(hex_id)
        if not texto or not h3.is_valid_cell(texto):
            invalidos += 1
            continue
        centros.add(texto)
        anel.update(str(v) for v in h3.grid_disk(texto, k))
    if invalidos:
        _logger.warning("hex quente ignorado por `hex_id` invalido: %d", invalidos)
    return anel - centros


# --------------------------------------------------------------------------- #
# Join READ-ONLY do hotness na lista de academias
# --------------------------------------------------------------------------- #
def _assert_invariancia_m1(
    academias: pd.DataFrame,
    enriquecido: pd.DataFrame,
    referencia: pd.DataFrame,
) -> None:
    """Molde de `enriquecer_dataframe_com_residual`: cardinalidade + invariantes intocadas.

    Duas diferenças em relação ao molde, ambas por o lado esquerdo aqui ser a ACADEMIA (que não
    possui as colunas do M1) e não um output do M1:

    1. a comparação é contra a CARTEIRA de origem, casada por hex — o que o assert prova é que o
       join **transportou** `score_priorizacao` e os 4 ranks sem alterá-los, não que eles
       sobreviveram a si mesmos;
    2. `NaN` é esperado nas linhas cujo hex não existe na carteira, então a igualdade é comparada
       com os nulos alinhados (`.equals` trata `NaN == NaN` como igual, que é o que queremos).
    """
    if len(enriquecido) != len(academias):
        raise AssertionError(
            f"join de hotness alterou cardinalidade: {len(academias)} -> {len(enriquecido)}"
        )

    mapa = referencia.drop_duplicates(subset=[_COL_HEX_CARTEIRA]).set_index(_COL_HEX_CARTEIRA)
    chave = enriquecido[_COL_HEX_ACADEMIA].astype("string")
    for coluna in COLUNAS_M1_INVARIANTES:
        if coluna not in referencia.columns or coluna not in enriquecido.columns:
            continue
        # `.astype("float64")` nos DOIS lados, e não só `pd.to_numeric`: `Series.equals` compara
        # DTYPE além de valor, e `to_numeric` PRESERVA o nulável. Ler a carteira com
        # `dtype_backend="numpy_nullable"` ou `"pyarrow"` (opções suportadas, sobre o mesmo arquivo
        # de produção) traz `score_priorizacao` como `Float64`/`double[pyarrow]`, enquanto o lado
        # do join já saiu como `float64` numpy — valores idênticos, dtypes diferentes, e o assert
        # acusaria "o M1 foi alterado" sem que um único valor tivesse mudado. Falso alarme de
        # violação de guardrail é pior que nenhum alarme: manda o leitor caçar corrupção de
        # artefato oficial que não existe.
        esperado = (
            pd.to_numeric(chave.map(mapa[coluna]), errors="coerce")
            .astype("float64")
            .reset_index(drop=True)
        )
        atual = (
            pd.to_numeric(enriquecido[coluna], errors="coerce")
            .astype("float64")
            .reset_index(drop=True)
        )
        if not esperado.equals(atual):
            raise AssertionError(f"`{coluna}` foi alterado pelo join de hotness")


def academias_com_hotness(
    score: pd.DataFrame,
    carteira: pd.DataFrame,
    *,
    quantil_sam: float = QUANTIL_SAM_QUENTE,
    limiar_residual: float = LIMIAR_RESIDUAL_SATURADO,
) -> pd.DataFrame:
    """Saída do score (academia) + carteira (hex) -> camada scored do D6. Função **pura**.

    Left join `validate="many_to_one"` do hotness NA lista de academias — a direção importa: a
    academia é o grão que sobrevive, a carteira é consultada. Hex de academia que não existe na
    carteira **não é erro**: fica com hotness nulo e `hex_quente = False`, porque a carteira é o
    universo onde "quente" está definido. Ausência de evidência de calor não é calor.
    """
    if _COL_HEX_ACADEMIA not in score.columns:
        raise AssertionError(f"frame de score sem `{_COL_HEX_ACADEMIA}`")
    faltando = [c for c in CONTRATO_COLUNAS_SCORE if c not in score.columns]
    if faltando:
        raise AssertionError(f"frame de score fora do contrato do BLK-MA-04: faltam {faltando}")

    carteira_antes = carteira.copy()
    if score.empty:
        vazio = _frame_vazio(CONTRATO_COLUNAS_ACADEMIAS_MA)
        _assert_schema_academias(vazio)
        return vazio

    hotness = marcar_hex_quente(carteira, quantil_sam=quantil_sam, limiar_residual=limiar_residual)
    if hotness[_COL_HEX_CARTEIRA].duplicated().any():
        raise AssertionError("carteira com `hex_id` duplicado: o join `many_to_one` seria ambiguo")

    academias = score.copy()
    academias[_COL_HEX_ACADEMIA] = academias[_COL_HEX_ACADEMIA].astype("string")

    enriquecido = academias.merge(
        hotness.rename(columns={_COL_HEX_CARTEIRA: _COL_HEX_ACADEMIA}),
        on=_COL_HEX_ACADEMIA,
        how="left",
        validate="many_to_one",
    )
    _assert_invariancia_m1(academias, enriquecido, carteira_antes)
    if not carteira.equals(carteira_antes):
        raise AssertionError("a carteira foi MUTADA: esta camada e' READ-ONLY sobre o mercado/M1")

    quentes = hotness.loc[hotness["hex_quente"].astype(bool), _COL_HEX_CARTEIRA]
    anel = _vizinhanca_quente(quentes.tolist())

    # `astype("boolean")` antes do `fillna`: o left join promove a coluna a `object` com `NaN`, e
    # `fillna` sobre `object` cai no downcast silencioso que o pandas vai remover.
    enriquecido["hex_quente"] = (
        enriquecido["hex_quente"].astype("boolean").fillna(False).astype(bool)
    )
    enriquecido["hex_quente_vizinho"] = (
        enriquecido[_COL_HEX_ACADEMIA].astype(str).isin(anel).astype(bool)
    )
    enriquecido["proximo_de_hex_quente"] = (
        enriquecido["hex_quente"] | enriquecido["hex_quente_vizinho"]
    )
    for coluna in (*COLUNAS_HOTNESS_CARTEIRA, *COLUNAS_M1_INVARIANTES):
        if coluna not in enriquecido.columns:
            # `float("nan")`, NUNCA `pd.NA`: este ramo existe para tolerar carteira incompleta, e
            # `pd.Series([pd.NA]).astype("float64")` LEVANTA `TypeError` (não há conversão de
            # `NAType` para float nativo). Com `pd.NA` a defesa derrubava exatamente o caso que
            # ela foi escrita para salvar — uma defesa que não defende é pior que nenhuma, porque
            # some da revisão. `NaN` converte para todos os dtypes do contrato, texto inclusive.
            enriquecido[coluna] = float("nan")
    enriquecido["versao_contrato"] = VERSAO_CONTRATO_ALVOS_MA

    out = _projetar(enriquecido, CONTRATO_COLUNAS_ACADEMIAS_MA)
    out = out.sort_values(["fonte", "chave_snapshot"], kind="mergesort").reset_index(drop=True)
    _assert_schema_academias(out)
    return out


def _assert_schema_academias(df: pd.DataFrame) -> None:
    """Falha alto se a camada scored não é exatamente o contrato."""
    esperado = list(CONTRATO_COLUNAS_ACADEMIAS_MA.keys())
    if list(df.columns) != esperado:
        raise AssertionError(f"camada scored fora do contrato: {list(df.columns)}")
    if df.empty:
        return
    if bool(df.duplicated(subset=["fonte", "chave_snapshot"]).any()):
        raise AssertionError("camada scored com `(fonte, chave_snapshot)` duplicada")
    # O `[:5]` corta a AMOSTRA DA MENSAGEM, nunca a varredura. Cortar o input (que é o erro fácil
    # aqui) faria o guard olhar só os 5 primeiros hexes únicos: com dezenas de milhares de
    # academias, a chance de um hex sujo cair nessa janela é ~0, e este é o ÚNICO guard de
    # geometria da camada — ele passaria a nunca disparar.
    invalidos = [
        h
        for h in df[_COL_HEX_ACADEMIA].astype(str).unique()
        if not h3.is_valid_cell(h) or h3.get_resolution(h) != H3_RES_CONTRATO
    ]
    if invalidos:
        raise AssertionError(
            f"`hex_id_res7` fora de res-{H3_RES_CONTRATO}: {len(invalidos)} distinto(s), "
            f"amostra {invalidos[:5]}"
        )
    # A disjunção do §9 tem de ser reconstituível a partir da própria saída.
    disjuncao = df["hex_quente"].astype(bool) | df["hex_quente_vizinho"].astype(bool)
    if not disjuncao.equals(df["proximo_de_hex_quente"].astype(bool)):
        raise AssertionError("`proximo_de_hex_quente` nao e' a disjuncao das duas metades")
    if bool((df["hex_quente"].astype(bool) & df["hex_quente_vizinho"].astype(bool)).any()):
        raise AssertionError("hex nao pode ser quente E vizinho de quente: o anel exclui o centro")


# --------------------------------------------------------------------------- #
# D6 — agregação hex-level (a lista curada)
# --------------------------------------------------------------------------- #
def agregar_alvos_por_hex(academias: pd.DataFrame) -> pd.DataFrame:
    """Camada scored -> lista curada, uma linha por **(hex, regime)**, ordenada para o comercial.

    Só entram linhas com `score_vulnerabilidade` preenchido: `n_sinais_disponiveis == 0` significa
    ausência de evidência, e uma média sobre ausência é invenção.

    A ordenação usa `n_sinais_disponiveis` como chave **primária** (descendente) e o score como
    secundária. Isso é a obrigação dura do FU1 na prática: hexes medidos por mais sinais aparecem
    antes, e um `{s3}` de score 100 nunca encabeça a lista por cima de um `{s1,s3,s4}` medido —
    ele lidera o **seu** bloco, que é onde a comparação é legítima.
    """
    _assert_schema_academias(academias)
    if academias.empty:
        vazio = _frame_vazio(CONTRATO_COLUNAS_ALVOS_MA)
        _assert_schema_alvos(vazio)
        return vazio

    com_score = academias[academias["score_vulnerabilidade"].notna()].copy()
    if com_score.empty:
        vazio = _frame_vazio(CONTRATO_COLUNAS_ALVOS_MA)
        _assert_schema_alvos(vazio)
        return vazio

    com_score["_tem_nota"] = com_score["nota_wellhub"].notna().astype("int64")
    agrupado = com_score.groupby([_COL_HEX_ACADEMIA, "sinais_disponiveis"], dropna=False, sort=True)
    out = agrupado.agg(
        uf=("uf", "first"),
        n_sinais_disponiveis=("n_sinais_disponiveis", "first"),
        n_independentes_vulneraveis=("chave_snapshot", "size"),
        score_vulnerabilidade_medio=("score_vulnerabilidade", "mean"),
        score_vulnerabilidade_max=("score_vulnerabilidade", "max"),
        sam_fitness_potencial=("sam_fitness_potencial", "first"),
        score_oportunidade_residual=("score_oportunidade_residual", "first"),
        hex_quente=("hex_quente", "first"),
        proximo_de_hex_quente=("proximo_de_hex_quente", "first"),
        flag_serie_imatura=("flag_serie_imatura", "any"),
        n_com_nota_wellhub=("_tem_nota", "sum"),
        nota_wellhub_mediana=("nota_wellhub", "median"),
        # MÉDIA e MÁXIMO, não `first` — e a troca é obrigatória desde o BLK-MA-14, não estética.
        # Enquanto a pressão vinha do centroide do hexágono ela era CONSTANTE dentro do grupo, e
        # `first` era a leitura honesta ("agregar fingiria variância que não existe"). Com o grão
        # ACADEMIA a variância passa a existir — amplitude média medida de 14,89 pontos dentro do
        # mesmo hex, máxima de 73,82 —, e `first` devolveria a linha que o `groupby` viu primeiro
        # como se representasse o hexágono inteiro. O par média+máximo é o mínimo honesto: a média
        # descreve o hex, o máximo diz se há UMA academia muito espremida escondida numa média
        # baixa, que é justamente o alvo que o entregável procura.
        pressao_competitiva_media=("pressao_competitiva", "mean"),
        pressao_competitiva_max=("pressao_competitiva", "max"),
        v6_medio=("v6", "mean"),
    ).reset_index()
    out["versao_contrato"] = VERSAO_CONTRATO_ALVOS_MA

    out = _projetar(out, CONTRATO_COLUNAS_ALVOS_MA)
    out = out.sort_values(
        ["n_sinais_disponiveis", "score_vulnerabilidade_medio", _COL_HEX_ACADEMIA],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    _assert_schema_alvos(out)
    return out


def _assert_schema_alvos(df: pd.DataFrame) -> None:
    """Falha alto se a lista curada não é exatamente o contrato, e se ela carregar identidade."""
    esperado = list(CONTRATO_COLUNAS_ALVOS_MA.keys())
    if list(df.columns) != esperado:
        raise AssertionError(f"lista curada fora do contrato: {list(df.columns)}")
    # D1 Opção A / DEC-012: o MVP é hex-level e SEM identidade. `chave_snapshot` é opaca, mas
    # mesmo ela não entra — uma linha por chave seria a variante nomeada por outro nome.
    proibidas = {"chave_snapshot", "fonte", "rede", "nome", "latitude", "longitude"}
    vazando = sorted(set(df.columns) & proibidas)
    if vazando:
        raise AssertionError(f"lista curada com identidade (D1-A/DEC-012): {vazando}")
    if df.empty:
        return
    if bool(df.duplicated(subset=[_COL_HEX_ACADEMIA, "sinais_disponiveis"]).any()):
        raise AssertionError("lista curada com `(hex, regime)` duplicado")
    if bool((df["n_independentes_vulneraveis"].astype("int64") < 1).any()):
        raise AssertionError("`n_independentes_vulneraveis` menor que 1 numa linha agregada")
    medio = pd.to_numeric(df["score_vulnerabilidade_medio"], errors="coerce")
    maximo = pd.to_numeric(df["score_vulnerabilidade_max"], errors="coerce")
    if bool(((medio < 0.0) | (medio > 100.0)).any()):
        raise AssertionError("`score_vulnerabilidade_medio` fora de [0, 100]")
    if bool((medio > maximo + 1e-9).any()):
        raise AssertionError("media maior que o maximo no mesmo grupo")


# --------------------------------------------------------------------------- #
# Materialização
# --------------------------------------------------------------------------- #
def materializar_alvos_ma(
    score: pd.DataFrame | None = None,
    carteira: pd.DataFrame | None = None,
    *,
    carteira_path: Path | None = None,
    academias_path: Path = ACADEMIAS_PATH_DEFAULT,
    alvos_csv_path: Path = ALVOS_CSV_DEFAULT,
    dry_run: bool = False,
) -> dict[str, object]:
    """Compõe as duas camadas e grava os dois artefatos do D6. Devolve auditoria só com escalares.

    Com `score`/`carteira` injetados a função é **pura até a escrita** — é assim que os testes
    rodam sem tocar em `data/`. Com `carteira_path`, lê a carteira do disco (nunca a reescreve).
    """
    if score is None:
        raise ValueError(_MSG_FONTE)
    if carteira is None:
        if carteira_path is None:
            raise ValueError(_MSG_FONTE)
        carteira = pd.read_parquet(carteira_path)

    academias = academias_com_hotness(score, carteira)
    alvos = agregar_alvos_por_hex(academias)

    auditoria: dict[str, object] = {
        "academias": int(len(academias)),
        "hexes_no_csv": int(alvos[_COL_HEX_ACADEMIA].nunique()) if not alvos.empty else 0,
        "linhas_csv": int(len(alvos)),
        "regimes": int(alvos["sinais_disponiveis"].nunique()) if not alvos.empty else 0,
        "academias_proximas_de_hex_quente": int(
            academias["proximo_de_hex_quente"].astype(bool).sum()
        )
        if not academias.empty
        else 0,
        "dry_run": bool(dry_run),
    }
    if dry_run:
        _logger.info("dry-run: nada gravado. %s", auditoria)
        return auditoria

    academias_path.parent.mkdir(parents=True, exist_ok=True)
    academias.to_parquet(academias_path, index=False)
    alvos_csv_path.parent.mkdir(parents=True, exist_ok=True)
    alvos.to_csv(alvos_csv_path, index=False, sep=";", encoding="utf-8-sig")
    _logger.info("camada scored: %s | lista curada: %s", academias_path, alvos_csv_path)
    return auditoria


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """CLI do entregável. Sem ela, `python -m ...alvos_ma` gravaria sem argumento."""
    p = argparse.ArgumentParser(
        prog="python -m motor_expansao.vulnerabilidade.alvos_ma",
        description=(
            "Materializa a lista priorizada de alvos de M&A (BLK-MA-05): cruza o score de "
            "vulnerabilidade com o hexágono quente e grava os dois artefatos do D6. "
            "READ-ONLY sobre o M1 e sobre a carteira."
        ),
    )
    p.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="raiz das partições `semana=AAAA-SS` do snapshot; deriva o score a partir dela",
    )
    p.add_argument(
        "--carteira",
        type=Path,
        default=CARTEIRA_PATH_DEFAULT,
        help="carteira de mercado, lida somente para o hotness (nunca reescrita)",
    )
    p.add_argument("--saida-academias", type=Path, default=ACADEMIAS_PATH_DEFAULT)
    p.add_argument("--saida-csv", type=Path, default=ALVOS_CSV_DEFAULT)
    p.add_argument(
        "--concorrentes",
        type=Path,
        default=None,
        help=(
            "pontos de concorrentes para o SINAL 6 (pressao competitiva POR ACADEMIA). "
            "Default: o parquet padrao, quando existir."
        ),
    )
    p.add_argument(
        "--sem-pressao",
        action="store_true",
        help="ignora o insumo de pressao e devolve o score sem o s6 (DEC-027)",
    )
    p.add_argument(
        "--oferta-com-independentes",
        action="store_true",
        help=(
            "as independentes tambem contam como concorrencia no s6, com metade do peso de uma "
            "unidade de rede (BLK-MA-16). DESLIGADO por default: muda o numero de quase toda "
            "linha e a virada do default e' decisao de gate"
        ),
    )
    p.add_argument(
        "--saida-nomeadas",
        type=Path,
        default=None,
        help=(
            "artefato NOMEADO (D1-B): score + identidade + coordenada, para os pins do piloto "
            "(BLK-MA-15). Sem este argumento, nada nomeado e' gravado. So' aceita caminho sob "
            "`data/staging/` — o artefato nasce gitignored."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="compõe tudo e reporta a auditoria, sem gravar arquivo algum",
    )
    return p.parse_args(argv)


def _pressao_por_academia(
    caminho: Path | None,
    academias: pd.DataFrame | None = None,
    *,
    com_independentes: bool = False,
) -> tuple[pd.DataFrame | None, str]:
    """Pressão POR ACADEMIA a partir do feed cru, ou `(None, motivo)`. Nunca derruba o lote.

    A coordenada é lida do feed, usada para medir distância e **descartada dentro da função** — o
    que sai é `(fonte, chave_snapshot, pressao)`. É a rota B da DEC-029: sem persistir coordenada,
    logo sem bump de série.

    `com_independentes` liga o universo de oferta do BLK-MA-16: as independentes do MESMO feed
    entram como concorrência, com metade do peso de uma unidade de rede. **Desligado por default**,
    porque virar o universo padrão é decisão de gate — o número muda para quase todo mundo (em SP,
    a fração com pressão zero cai de 29,2% para 3,9%).
    """
    from .contrato import CATEGORIA_INDEPENDENTE
    from .pressao_competitiva import (
        CONCORRENTES_PATH_DEFAULT,
        calcular_pressao_por_academia,
        ler_concorrentes,
    )
    from .snapshots import coordenadas_por_chave

    alvo = caminho or CONCORRENTES_PATH_DEFAULT
    if not alvo.exists():
        return None, f"insumo de pressao ausente ({alvo}); score sem o s6"
    if academias is None:
        academias = coordenadas_por_chave()
    if academias.empty:
        return None, "feed cru vazio ou ausente; score sem o s6"
    pontos = ler_concorrentes(alvo)

    independentes = None
    sufixo = "universo `cadeias`"
    if com_independentes:
        if "rede" not in academias.columns:
            return None, "feed sem a coluna `rede`; nao da' para separar independente de cadeia"
        independentes = academias[academias["rede"].astype(str) == CATEGORIA_INDEPENDENTE]
        sufixo = f"universo `cadeias_e_independentes` (+{len(independentes)} independente(s))"

    pressao = calcular_pressao_por_academia(academias, pontos, independentes=independentes)
    return pressao, f"pressao POR ACADEMIA sobre {len(pressao)} unidade(s), {sufixo}"


def main(argv: Sequence[str] | None = None) -> int:
    """Entrada do `python -m`. Devolve 0 em sucesso — código de saída importa para o cron."""
    from .score import calcular_score_vulnerabilidade

    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    if args.base_dir is None:
        raise SystemExit("informe `--base-dir` com a raiz das particoes do snapshot")

    from .snapshots import coordenadas_por_chave

    # UMA leitura do feed cru serve aos dois consumidores (pressao e artefato nomeado). Ler duas
    # vezes custaria o dobro e abriria a chance de os dois verem feeds diferentes.
    coordenadas = coordenadas_por_chave()

    if args.sem_pressao:
        pressao, motivo = None, "`--sem-pressao`: score sem o s6, por pedido explicito"
    else:
        pressao, motivo = _pressao_por_academia(
            args.concorrentes, coordenadas, com_independentes=args.oferta_com_independentes
        )
    _logger.info("sinal 6: %s", motivo)

    score = calcular_score_vulnerabilidade(args.base_dir, pressao=pressao)
    auditoria = materializar_alvos_ma(
        score,
        carteira_path=args.carteira,
        academias_path=args.saida_academias,
        alvos_csv_path=args.saida_csv,
        dry_run=args.dry_run,
    )
    auditoria["sinal_6"] = motivo

    # Artefato NOMEADO (BLK-MA-15): so' quando pedido explicitamente. Default `None` porque ele
    # carrega identidade — materializa-lo tem de ser um ato, nunca um efeito colateral.
    if args.saida_nomeadas is not None:
        from .alvos_nomeados import materializar_alvos_nomeados

        auditoria["nomeadas"] = materializar_alvos_nomeados(
            score, coordenadas, saida=args.saida_nomeadas, dry_run=args.dry_run
        )
    print(auditoria)
    return 0


__all__ = [
    "ACADEMIAS_PATH_DEFAULT",
    "ALVOS_CSV_DEFAULT",
    "CARTEIRA_PATH_DEFAULT",
    "academias_com_hotness",
    "agregar_alvos_por_hex",
    "main",
    "marcar_hex_quente",
    "materializar_alvos_ma",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
