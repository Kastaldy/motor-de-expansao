"""Nota de cobertura censitaria por MUNICIPIO (BLK-JOINUF-01).

POR QUE ESTE MODULO EXISTE. A nota que decide se um hexagono le dado de setor
(`qualidade_join_uf`) e' UM UNICO VALOR POR ESTADO: `fase_a_nacional_completo.py:322-325`
grava um escalar em `df_uf` inteiro. Pior, esse escalar vem de
`mismatch_renda_total_pct = abs(len(basico_uf) - len(renda_uf)) / len(basico_uf) * 100`
(`validar_fase_a_censo2022.py:215-217`) -- uma diferenca de CONTAGEM DE LINHAS entre dois
CSVs do IBGE, que nunca casa um codigo de setor com outro. O proprio repo ja' chamou essa
comparacao de obsoleta em `materializar_setores_censitarios_geo.py:638-639` ("nada dizia
sobre o acerto do join").

Consequencia medida contra o artefato de producao: AM (10,50% de deficit de linhas) e RR
(9,59%) sao as duas unicas UFs classe C do pais, e por isso 100% dos seus hexagonos leem
populacao municipal. Manaus perdia 2.038 dos 2.139 -- exibindo os 2.063.689 habitantes do
municipio inteiro repetidos em cada hexagono -- embora 97,50% dos seus 3.281 setores
tenham renda publicada.

O QUE A NOTA MEDE, COM PRECISAO. E' a fracao da POPULACAO do municipio que mora em setor
com renda publicada (`flag_renda_disponivel = renda_per_capita_setor_2022.notna()`,
`materializar_setores_censitarios_geo.py:637`), ponderada por `pop_total_setor_2022`.
Isso e' COBERTURA, nao CORRECAO de join: ela responde "o IBGE publicou renda para onde
essa gente mora?" e NAO "a renda foi colada no setor certo?" -- distincao que este repo
pagou caro para aprender na DEC-045 (cobertura cheia com a renda no setor errado). A chave
`cod_setor` do artefato GEO, alem disso, e' recuperada POSICIONALMENTE de um agregado
irmao (`materializar_setores_censitarios_geo.py:196-300`), entao nem a cobertura e' imune
ao mesmo modo de falha.

POR QUE O DENOMINADOR E' POPULACAO E NAO CONTAGEM DE SETORES (DEC-058, emenda a DEC-054).
Ate' 2026-09-10 a nota era `flag_renda_disponivel.mean()` -- um setor de 3 moradores
pesava o mesmo que um de 3.000. Isso REPROVAVA cidade de praia inteira, porque o litoral
tem uma cauda longa de setores de veraneio quase vazios sem renda publicada, e a populacao
mora concentrada em poucos setores urbanos QUE TEM renda. Medido no artefato de producao:
Angra dos Reis 0,84392 (classe C) na contagem e 0,998752 (classe A) na populacao; Paraty
0,805714 -> 0,997038; Bertioga 0,816993 -> 0,997710; Ilhabela 0,846154 -> 0,998368;
Ubatuba 0,880184 -> 0,998311; Sao Sebastiao 0,888136 -> 0,999706; Imbituba 0,881119 ->
0,997585; Buzios 0,879310 -> 0,998500; Ilha Comprida 0,892308 -> 0,998361. As nove eram
classe C pela contagem e sao classe A pela populacao. A DEC-054 nao viu isso porque mediu
o denominador so' contra Manaus e Boa Vista, que EMPATAM nas duas reguas.

A nota nova NAO e' so' mais generosa: 13 municipios CAEM de A/B para C, e a queda e'
honesta -- neles a renda falta exatamente onde a populacao esta' (Ilha de Itamaraca/PE:
0,932692 na contagem, 0,880399 na populacao).

Por que ela ainda serve, apesar disso: o que ela LIBERA e' a leitura de POPULACAO do setor
(`pop_total_setor_2022`), que vem do Basico com contagem validada exata e mede Pearson
>= 0,99954 contra a malha por chave -- com AM e RR entre as MAIS fieis do pais. A RENDA
exibida nao passa por este gate: desde a DEC-045 ela vem da malha, agregada por chave.

O QUE ELE NAO FAZ. Nao rebaixa ninguem. A nota entra como DISJUNCAO em
`pop_corte.derive_confianca_geografica` -- ver a nota la'. Substituir a nota de UF pela
municipal (em vez de somar) seria regressao liquida de 231.891 hexagonos.

READ-ONLY sobre o M1: nao toca `score_priorizacao`, `hex_score_estrutural` nem nenhum dos
7 artefatos oficiais do §3.
"""

from __future__ import annotations

import glob
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

#: Mesmos cortes de `materializar_setores_censitarios_geo.py:641`, de proposito: a regua
#: fina nao inventa criterio novo, so' aplica num grao mais fino o que o repo ja' usa.
CORTE_CLASSE_A = 0.95
CORTE_CLASSE_B = 0.90

#: Carimbo de procedencia. Sem ele, "nota ausente" e "nota calculada como C" ficariam
#: indistinguiveis a jusante -- exatamente a familia de defeito do "valor legitimo no
#: lugar errado" que ja' custou a DEC-038 e a DEC-045 a este repo.
FONTE_CALCULADA = "geo_setor_cobertura"
FONTE_AUSENTE = "ausente"
FONTE_PRESERVADA = "preservada"

#: Contrato de SAIDA de `calcular_notas`.
#: `pop_municipio_malha` e `n_setores_municipio` sao AUDITORIA: com as duas lado a lado da'
#: para separar municipio promovido porque a populacao esta' concentrada em setor coberto
#: (pop alta, poucos setores descobertos) de municipio promovido por RUIDO (malha de dois
#: setores, um deles com um morador). Sem o par, a nota nova seria um numero sem recurso.
COLUNAS_NOTA = (
    "cod_municipio",
    "classe_join_municipio",
    "taxa_match_municipio",
    "n_setores_municipio",
    "pop_municipio_malha",
)

#: O que `anexar_nota_municipal` de fato CONSOME. Deliberadamente menor que `COLUNAS_NOTA`:
#: exigir a coluna de auditoria aqui faria um produtor desatualizado virar no-op SILENCIOSO
#: -- promocao que nao acontece, sem erro nenhum, que e' o defeito que este modulo existe
#: para consertar. Frame sem estas colunas e' tratado como ausencia, em vez de estourar
#: KeyError no meio de um pipeline de 4 horas.
COLUNAS_ANEXACAO = (
    "cod_municipio",
    "classe_join_municipio",
    "taxa_match_municipio",
)


def _normalizar_cod_municipio(serie: pd.Series) -> pd.Series:
    """Extrai os 7 digitos do codigo IBGE, a convencao ja usada no repo.

    Sem isso, um `cod_municipio` que chegue como float (`1302603.0`), com espaco ou como
    int casaria ZERO linhas e a promocao viraria no-op SILENCIOSO -- o mesmo modo de falha
    que este bloco existe para consertar. `ibge_censo.py:709` usa este mesmo extract.
    """
    return serie.astype(str).str.extract(r"(\d{7})")[0]


def classificar_taxa(taxa: float | None) -> str | None:
    """Taxa de cobertura de renda (ponderada por populacao) -> classe {A,B,C}.

    NA entra e NA sai. Sem esta guarda, `NaN >= 0.95` e' `False` e o municipio sem
    populacao na malha viraria classe "C" -- afirmando "medi e o join e' ruim" onde a
    verdade e' "nao ha o que medir". Distinguir nota AUSENTE de nota RUIM e' o mesmo
    cuidado que os carimbos `FONTE_*` abaixo existem para dar.
    """
    if taxa is None or pd.isna(taxa):
        return None
    if taxa >= CORTE_CLASSE_A:
        return "A"
    if taxa >= CORTE_CLASSE_B:
        return "B"
    return "C"


def _frame_vazio() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cod_municipio": pd.Series(dtype="object"),
            "classe_join_municipio": pd.Series(dtype="object"),
            "taxa_match_municipio": pd.Series(dtype="float64"),
            "n_setores_municipio": pd.Series(dtype="int64"),
            "pop_municipio_malha": pd.Series(dtype="float64"),
        }
    )


def calcular_notas(geo_root: Path) -> pd.DataFrame:
    """Le o artefato GEO e devolve a nota por municipio.

    Colunas: ver `COLUNAS_NOTA`. Devolve frame VAZIO quando o artefato nao esta' no disco
    -- e' o caso do CI e de qualquer maquina sem o 1,17 GB da malha. Frame vazio faz a
    promocao virar no-op, nunca um rebaixamento.
    """
    if not Path(geo_root).exists():
        return _frame_vazio()

    arquivos = glob.glob(str(Path(geo_root) / "uf=*" / "cod_municipio=*" / "*.parquet"))
    if not arquivos:
        return _frame_vazio()

    partes = []
    ilegiveis = 0
    for caminho in arquivos:
        try:
            partes.append(
                pd.read_parquet(
                    caminho,
                    columns=["cod_municipio", "flag_renda_disponivel", "pop_total_setor_2022"],
                )
            )
        except Exception:
            # Particao corrompida/sem alguma das colunas nao pode derrubar a nota do pais
            # inteiro -- o custo de pular e' so' nao promover aquele municipio, e a direcao
            # e' segura (a nota so' entra como perna de OR). Mas CONTA, porque pular 5.000
            # em silencio e pular 1 sao problemas diferentes.
            ilegiveis += 1
    if ilegiveis:
        log.warning(
            "classe_join_municipio: %d de %d particoes ilegiveis (faltam "
            "cod_municipio/flag_renda_disponivel/pop_total_setor_2022?), ignoradas",
            ilegiveis,
            len(arquivos),
        )
    if not partes:
        return _frame_vazio()

    setores = pd.concat(partes, ignore_index=True)
    setores["flag_renda_disponivel"] = setores["flag_renda_disponivel"].fillna(False).astype(bool)
    setores["cod_municipio"] = _normalizar_cod_municipio(setores["cod_municipio"])
    # `.copy()` porque abaixo se ESCREVEM colunas neste frame, e ele acabou de virar uma
    # fatia. Sob copy-on-write a escrita numa fatia nao levanta erro: ela nao acontece --
    # e a nota do pais inteiro sairia de colunas que nunca existiram.
    setores = setores[setores["cod_municipio"].notna()].copy()
    if setores.empty:
        return _frame_vazio()

    # PESO = populacao do setor. `fillna(0)` e `clip(lower=0)` porque um setor sem
    # populacao publicada (ou com valor absurdo) nao pode inventar peso: ele conta zero nos
    # DOIS lados da fracao, o que e' o mesmo que nao existir para a nota.
    pop = (
        pd.to_numeric(setores["pop_total_setor_2022"], errors="coerce")
        .fillna(0.0)
        .clip(lower=0.0)
    )
    setores["_pop_setor"] = pop
    setores["_pop_com_renda"] = pop.where(setores["flag_renda_disponivel"], 0.0)

    agregado = setores.groupby("cod_municipio").agg(
        pop_municipio_malha=("_pop_setor", "sum"),
        _pop_com_renda=("_pop_com_renda", "sum"),
        n_setores_municipio=("_pop_setor", "size"),
    )
    # GUARDA DE DENOMINADOR ZERO: municipio cuja malha soma 0 habitante devolve NA, NUNCA
    # 0,0. Com 0,0 a divisao daria 0,0, `classificar_taxa` responderia "C" e o municipio
    # seria REPROVADO em silencio por uma medicao que nunca existiu -- a familia de defeito
    # do "valor legitimo no lugar errado" (DEC-038/DEC-042).
    denominador = agregado["pop_municipio_malha"].where(agregado["pop_municipio_malha"] > 0)
    agregado["taxa_match_municipio"] = agregado["_pop_com_renda"] / denominador

    notas = agregado.reset_index()
    notas["classe_join_municipio"] = notas["taxa_match_municipio"].map(classificar_taxa)
    return notas[list(COLUNAS_NOTA)]


def _notas_utilizaveis(notas: pd.DataFrame | None) -> bool:
    return (
        notas is not None
        and not notas.empty
        and all(coluna in notas.columns for coluna in COLUNAS_ANEXACAO)
    )


def anexar_nota_municipal(df: pd.DataFrame, notas: pd.DataFrame) -> pd.DataFrame:
    """Anexa `classe_join_municipio` (+ taxa e procedencia) ao frame de hexagonos.

    PRESERVA o que ja' existe quando nao ha nota nova. Isso importa porque
    `calcular_colunas_mercado` LE O PROPRIO OUTPUT (`MERCADO_PATH == OUT_PATH`): uma
    re-execucao numa maquina sem a malha sobrescreveria a nota ja' gravada com NA e
    deixaria o artefato com hexagono `granular` sem nenhuma coluna explicando por que --
    granular por causa do termo `base` de `derive_confianca_geografica`, e inexplicavel
    para quem auditasse depois.
    """
    out = df.copy()
    tem_nota_previa = "classe_join_municipio" in out.columns

    if "cod_municipio" not in out.columns or not _notas_utilizaveis(notas):
        if tem_nota_previa:
            # Preserva; so' carimba a procedencia para o leitor saber que esta rodada nao
            # recalculou nada.
            out["fonte_classe_join_municipio"] = FONTE_PRESERVADA
            return out
        out["classe_join_municipio"] = pd.Series(pd.NA, index=out.index, dtype="object")
        out["taxa_match_municipio"] = pd.Series(pd.NA, index=out.index, dtype="Float64")
        out["fonte_classe_join_municipio"] = FONTE_AUSENTE
        return out

    chave = _normalizar_cod_municipio(out["cod_municipio"])
    notas_indexadas = notas.drop_duplicates(subset=["cod_municipio"]).set_index("cod_municipio")
    out["classe_join_municipio"] = chave.map(notas_indexadas["classe_join_municipio"]).astype(
        "object"
    )
    out["taxa_match_municipio"] = pd.to_numeric(
        chave.map(notas_indexadas["taxa_match_municipio"]), errors="coerce"
    ).astype("Float64")
    out["fonte_classe_join_municipio"] = out["classe_join_municipio"].notna().map(
        {True: FONTE_CALCULADA, False: FONTE_AUSENTE}
    )

    # TRIPWIRE: nota disponivel e casamento ZERO e' drift de formato de chave, nao dado
    # legitimo -- e sem este aviso viraria um no-op silencioso, que e' o defeito que o
    # bloco inteiro existe para consertar.
    casados = int(out["classe_join_municipio"].notna().sum())
    if casados == 0 and len(out):
        log.warning(
            "classe_join_municipio: %d notas disponiveis mas ZERO hexagonos casaram -- "
            "provavel divergencia de formato em cod_municipio",
            len(notas),
        )
    return out
