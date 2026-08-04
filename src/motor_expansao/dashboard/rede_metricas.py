"""Nucleo semantico da rede Ultra instalada (base Growth API) - BLK-EXEC-01/01b.

Camada PARALELA, **READ-ONLY sobre o M1**: le `growth_api_historico.parquet` (ingestao
diaria da Growth, DEC-013) e devolve um fechamento mensal por unidade. Nao toca score,
peso, carteira nem artefato oficial.

Por que este modulo existe
--------------------------
A base e' DIARIA e mistura duas semanticas na mesma linha, sem marcacao nenhuma:

* **cumulativas (MTD)** - `faturamento`, `cancelados`, `visitas`, `vendas`... acumulam
  dentro do mes e **resetam no dia 1**. Medido em 2026-08-04 contra a base de producao:
  `faturamento` nao cai em 100,0% dos dias e o dia 1 e' o minimo do mes em 100,0% dos
  unidade-mes.
* **snapshots** - `pagantes`, `ativos_total`, `NPS`, `em_cobranca`... sao a foto do dia
  (sobem e descem livremente: `pagantes` nao cai em apenas 54,9% dos dias).

Tratar uma cumulativa como snapshot subestima o numero pelo tanto de mes que ainda nao
passou. Foi exatamente o que aconteceu com o "ticket medio" da Visao Executiva v1:
`ticket_medio_pagantes` **e** `faturamento_sem_agregador / pagantes` acumulado no mes
(confere em 100,00% de 66.424 linhas), e era exibido como se fosse a foto do dia - no dia
2 de junho, SP aparecia com R$ 20,28 contra R$ 163,67 reais (76% subestimado).

Vocabulario
-----------
Os rotulos seguem o PowerBI `Dashboard - Analise Diaria - MVP.pbix`, que consome a MESMA
base e e' a lingua que o time de campo fala: **recorrentes** = pagantes de balcao,
**agregadores** = Gympass + Totalpass, `saldo_operacional` = `vendas - cancelados`.

Uma excecao deliberada: o que aqui se chama `receita_por_recorrente` **nao** e' o
`TICKET_MEDIO` do PowerBI. Aquele e' o ticket da VENDA
(`SUM(FT_RELATORIO_VENDAS[VALOR_REAL]) / COUNTROWS(...)`, com piso de R$ 19,90) e vem de
uma tabela de vendas individuais que a API Growth **nao expoe** - so ha a contagem
`vendas`. A correlacao entre as duas grandezas e' de 0,285; sao coisas diferentes.
Chamar a nossa de "ticket medio" faria o time compara-la com o PowerBI e concluir que um
dos dois esta errado.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Identidade das unidades
# ---------------------------------------------------------------------------

# Siglas de UF que aparecem como SUFIXO do nome da unidade, em tres grafias que convivem
# nas bases: "Bangu / RJ", "BANGU - RJ" e "Icarai RJ". O separador e' OBRIGATORIO no
# padrao - sem ele, "NATAL" viraria "NAT" (o "AL" de Alagoas) e "VISCONDE DE RIO CLARO"
# viraria "...CLA" (o "RO" de Rondonia).
_UFS_BR = "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"
_UF_SUFIXO_RE = re.compile(rf"(?:\s*[/-]\s*|\s+)(?:{_UFS_BR})$")


def _sem_acento(valor: object) -> str:
    """MAIUSCULAS, sem acento, espacos colapsados. Preserva o sufixo de UF."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).upper().strip()
    return " ".join(texto.split())


def chave_unidade(valor: object) -> str:
    """Chave de join de unidade, tolerante as grafias que convivem nas bases.

    Remove acento, caixa e o sufixo de UF em qualquer das tres grafias. NAO serve para
    IDENTIDADE sozinha: "AGUAS CLARAS" e "AGUAS CLARAS - DF" colapsam na mesma chave e
    sao unidades DIFERENTES (ver `resolver_identidade`).
    """
    texto = _sem_acento(valor)
    anterior = None
    while anterior != texto:  # "Sao Pedro da Aldeia / RJ" -> "SAO PEDRO DA ALDEIA"
        anterior = texto
        texto = _UF_SUFIXO_RE.sub("", texto).strip()
    return texto


def _slug(texto: str) -> str:
    """Slug ASCII estavel para id de unidade (minusculo, hifens, sem borda)."""
    base = _sem_acento(texto).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    return base.strip("-")


# Unidades da base Growth que NAO sao academias da rede comparavel (Felipe, 2026-08-04).
#
# Casadas por **nome CRU** (acento e caixa normalizados, sufixo de UF PRESERVADO) - nunca
# pela chave normalizada. A diferenca nao e' cosmetica: existem DUAS "Aguas Claras" e elas
# sao unidades distintas -- `AGUAS CLARAS` (master DF/GO, inaugurada em 20/03/2023, ~2.088
# alunos ativos) e' academia; `AGUAS CLARAS - DF` (master ULTRA, inaugurada em 19/10/2024,
# ~282 ativos) e' um **studio**. A v1 excluia por chave normalizada e derrubava as duas,
# ou seja, uma academia real ficou fora da Visao Executiva em producao.
EXCLUIDAS_NOME_CRU: frozenset[str] = frozenset(
    {
        "NATAL - RN",
        "BATEL - PR",
        "BACACHERI - PR",
        "AGUAS CLARAS - DF",  # studio, nao academia
        "CHACARA STO ANTONIO - SP",
        "BARRA FUNDA",
        "ADMINISTRACAO",  # entrada administrativa da base, nao e' unidade fisica
    }
)


def eh_excluida(nome_cru: object) -> bool:
    """True se o nome CRU esta na lista de fora da rede comparavel."""
    return _sem_acento(nome_cru) in EXCLUIDAS_NOME_CRU


@dataclass(frozen=True)
class Unidade:
    """Identidade canonica de uma unidade da rede (uma ou mais grafias na base)."""

    id: str
    nome: str
    uf: str
    master: str
    inauguracao: pd.Timestamp | None
    nomes_crus: tuple[str, ...] = field(default_factory=tuple)
    excluida: bool = False


# Sentinela de data invalida na `inauguracao`: ja apareceu epoch (31/12/1969) na base, o
# que produzia "677 meses de operacao" e uma coorte impossivel. O gate e' barato e fica
# como rede de seguranca mesmo com a base atual limpa (medido 2026-08-04: 0 ocorrencias).
_ANO_INAUGURACAO_MIN = 1990


def _inauguracao_valida(valor: pd.Timestamp | None, limite: pd.Timestamp | None) -> pd.Timestamp | None:
    if valor is None or pd.isna(valor):
        return None
    if valor.year < _ANO_INAUGURACAO_MIN:
        return None
    if limite is not None and valor > limite:
        return None
    return valor


def _nome_exibicao(nome_cru: str) -> str:
    """Nome curto para a tabela: sem o sufixo de UF (ha coluna de UF) e sem espaco solto."""
    texto = " ".join(str(nome_cru).split())
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = _UF_SUFIXO_RE.sub("", texto).strip()
    return texto or " ".join(str(nome_cru).split())


def resolver_identidade(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Unidade]]:
    """Atribui `unidade_id` a cada linha e devolve o catalogo de unidades.

    Duas grafias do mesmo nome viram a MESMA unidade **se e somente se** as faixas de data
    forem **disjuntas** E a `inauguracao` for **identica**. A regra existe porque a
    ingestao passou a gravar UTF-8 correto em 20/02/2026 e partiu a serie de tres unidades
    ao meio (`PATIO BRASIL - DF` = 158 linhas ate 19/02 + 163 desde 20/02; idem
    `PICARRAS - SC` e `SAO GONCALO SHOPPING - RJ`); sem fundir, a ficha da Patio Brasil
    mostraria 5 meses de historico em vez de 11.

    O lado oposto e' o que impede resolver ingenuamente por nome normalizado: as duas
    "Aguas Claras" tem datas SOBREPOSTAS e inauguracoes diferentes -> continuam separadas.
    Medido contra a base de producao em 2026-08-04: 3 fusoes e 1 separacao, os 4 casos
    existentes classificados corretamente.
    """
    if not len(df):
        return df.assign(unidade_id=pd.Series(dtype="object")), {}

    trabalho = _com_colunas_de_identidade(df)
    if "_data" not in trabalho.columns:
        trabalho["_data"] = pd.to_datetime(trabalho["data"], format="%d/%m/%Y", errors="coerce")
    limite = trabalho["_data"].max()

    por_nome = (
        trabalho.groupby("unidade", observed=True)
        .agg(
            ini=("_data", "min"),
            fim=("_data", "max"),
            uf=("uf", "last"),
            master=("master", "last"),
            inauguracao=("inauguracao", "last"),
        )
        .reset_index()
    )
    por_nome["chave"] = por_nome["unidade"].map(chave_unidade)
    por_nome["inaug_dt"] = pd.to_datetime(
        por_nome["inauguracao"], format="%d/%m/%Y", errors="coerce"
    )
    # Ordem estavel: a serie mais ANTIGA primeiro, para que o desempate de id (`-2`, `-3`)
    # nao dependa da ordem de gravacao do parquet.
    por_nome = por_nome.sort_values(["chave", "ini", "unidade"], kind="stable")

    atribuicao: dict[str, str] = {}
    catalogo: dict[str, Unidade] = {}

    for chave, grupo in por_nome.groupby("chave", sort=True):
        linhas = list(grupo.itertuples(index=False))
        grupos: list[list] = []
        for linha in linhas:
            destino = None
            for candidato in grupos:
                if all(_fundir(linha, outro) for outro in candidato):
                    destino = candidato
                    break
            if destino is None:
                grupos.append([linha])
            else:
                destino.append(linha)

        for ordem, membros in enumerate(grupos, start=1):
            recente = max(membros, key=lambda m: m.fim)
            uf = str(recente.uf or "").upper().strip()
            base_id = f"{_slug(chave)}-{uf.lower()}" if uf else _slug(chave)
            uid = base_id if ordem == 1 else f"{base_id}-{ordem}"
            nomes = tuple(str(m.unidade) for m in membros)
            unidade = Unidade(
                id=uid,
                nome=_nome_exibicao(recente.unidade),
                uf=uf,
                master=str(recente.master or "").strip(),
                inauguracao=_inauguracao_valida(recente.inaug_dt, limite),
                nomes_crus=nomes,
                # Basta UMA grafia na lista para a unidade inteira ficar de fora: as
                # grafias de uma mesma unidade sao a mesma academia.
                excluida=any(eh_excluida(n) for n in nomes),
            )
            catalogo[uid] = unidade
            for nome in nomes:
                atribuicao[nome] = uid

    trabalho["unidade_id"] = trabalho["unidade"].map(atribuicao)
    return trabalho, catalogo


#: Colunas de identidade que a API traz hoje. Se alguma sumir num ciclo de ingestao, a
#: aba degrada (campo vazio) em vez de estourar -- a Visao Executiva nao pode cair por
#: causa de uma coluna de rotulo.
_COLUNAS_IDENTIDADE = ("unidade", "uf", "master", "inauguracao")


def _com_colunas_de_identidade(df: pd.DataFrame) -> pd.DataFrame:
    trabalho = df.copy()
    for coluna in _COLUNAS_IDENTIDADE:
        if coluna not in trabalho.columns:
            trabalho[coluna] = ""
    return trabalho


def _fundir(a, b) -> bool:
    """Regra de fusao: faixas de data DISJUNTAS **e** mesma `inauguracao`."""
    disjuntas = bool(a.fim < b.ini or b.fim < a.ini)
    mesma_inauguracao = bool(
        pd.notna(a.inaug_dt) and pd.notna(b.inaug_dt) and a.inaug_dt == b.inaug_dt
    )
    return disjuntas and mesma_inauguracao


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

COLUNAS_CUMULATIVAS: tuple[str, ...] = (
    "faturamento",
    "faturamento_sem_agregador",
    "cancelados",
    "visitas",
    "convertidos",
    "novos_alunos",
    "vendas",
    "passagens_gympass",
    "passagens_totalpass",
)
COLUNAS_SNAPSHOT: tuple[str, ...] = (
    "pagantes",
    "ativos_total",
    "alunos_gympass",
    "alunos_totalpass",
    "em_cobranca",
    "NPS",
    "inadimplente",
    "treino_ativo",
)

# Faixa canonica do NPS. O filtro NAO pode ser `v > 0`: NPS **negativo e' legitimo** (a
# base tem 3.183 linhas negativas, minimo -100) e descarta-lo inflaria a media da mesma
# forma que a sentinela. O que sai e' so o `999` de "sem pesquisa no periodo" (5,63% das
# linhas, 56 unidades) - em SP a media exibida era 67,4 contra 62,8 reais.
NPS_MIN, NPS_MAX = -100.0, 100.0

# Metricas cuja definicao ainda nao foi confirmada com a Growth: `inadimplente` passa de
# 100% dos pagantes em ~10% dos fechamentos (denominador desconhecido) e `treino_ativo`
# passa de 100 em algumas linhas. Sao EXIBIDAS com aviso e ficam PROIBIDAS em alerta.
METRICAS_A_VALIDAR: frozenset[str] = frozenset({"inadimplente", "treino_ativo"})


def carregar_base(parquet: Path | str) -> pd.DataFrame:
    """Le a base Growth e normaliza a data. DataFrame vazio se o parquet nao existir."""
    caminho = Path(parquet)
    if not caminho.exists():
        return pd.DataFrame()
    df = pd.read_parquet(caminho)
    return preparar_base(df)


def preparar_base(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza data + identidade e derruba as unidades fora da rede comparavel."""
    if not len(df):
        return df
    trabalho = _com_colunas_de_identidade(df)
    trabalho["_data"] = pd.to_datetime(trabalho.get("data"), format="%d/%m/%Y", errors="coerce")
    trabalho = trabalho.dropna(subset=["_data"])
    trabalho, catalogo = resolver_identidade(trabalho)
    fora = {uid for uid, u in catalogo.items() if u.excluida}
    trabalho = trabalho[~trabalho["unidade_id"].isin(fora)]
    trabalho.attrs["catalogo"] = {uid: u for uid, u in catalogo.items() if uid not in fora}
    return trabalho.sort_values(["unidade_id", "_data"], kind="stable").reset_index(drop=True)


def catalogo_de(df: pd.DataFrame) -> dict[str, Unidade]:
    """Catalogo de unidades anexado por `preparar_base` (vazio se ausente)."""
    catalogo = df.attrs.get("catalogo") if hasattr(df, "attrs") else None
    return dict(catalogo) if catalogo else {}


# ---------------------------------------------------------------------------
# Fechamento mensal
# ---------------------------------------------------------------------------

# Um mes com menos que isto de dias coletados nao e' um mes: entra na serie marcado como
# incompleto. Medido: 150 de 2.132 unidade-mes.
DIAS_MINIMOS_MES_COMPLETO = 25

# ...e o dia de referencia tem de ter CHEGADO ao fim do mes. So' o piso de dias nao basta:
# do dia 25 em diante, o mes EM CURSO ja satisfazia `dias_com_dado >= 25` e era tratado como
# fechado -- o diagnostico entao comparava um acumulado parcial contra a media de 3 meses
# inteiros e acendia "queda de faturamento" na rede toda, todo fim de mes, em unidades cujo
# faturamento diario nao tinha variado um centavo. A tolerancia de 1 dia existe porque a
# ingestao perde a virada com frequencia (julho/2026 termina em 30/07 na base de producao).
TOLERANCIA_FIM_DE_MES_DIAS = 1


def fechamento_mensal(df: pd.DataFrame, dia_corte: int | None = None) -> pd.DataFrame:
    """Uma linha por (`unidade_id`, competencia) com o ultimo dia COM DADO do mes.

    `dia_corte` limita cada mes aos dias `<= dia_corte`, que e' como se compara mes
    parcial com mes parcial: o acumulado de 1..12/06 contra o acumulado de 1..12/05. Sem
    ele, cada mes vale por inteiro (a serie fechada que alimenta coorte e historico).

    Cumulativas usam sempre o **ultimo** valor do mes, nunca o maximo: `cancelados` CAI
    dentro do mes em 36,7% dos unidade-mes (estorno de cancelamento), e `max` congelaria
    o pico em vez do fechamento real.

    Vetorizado de proposito - substitui o laco Python por unidade da v1. Medido: 2.132
    linhas em ~17 ms para a rede inteira.
    """
    vazio = _fechamento_vazio()
    if not len(df):
        return vazio

    trabalho = df
    if dia_corte is not None:
        trabalho = trabalho[trabalho["_data"].dt.day <= int(dia_corte)]
    if not len(trabalho):
        return vazio

    trabalho = trabalho.sort_values(["unidade_id", "_data"], kind="stable")
    competencia = trabalho["_data"].dt.to_period("M")

    presentes_cum = [c for c in COLUNAS_CUMULATIVAS if c in trabalho.columns]
    presentes_snap = [c for c in COLUNAS_SNAPSHOT if c in trabalho.columns]
    agregacoes: dict[str, tuple[str, str]] = {
        "dia_ref": ("_data", "max"),
        "dias_com_dado": ("_data", "nunique"),
        "uf": ("uf", "last"),
        "master": ("master", "last"),
        "unidade_cru": ("unidade", "last"),
        "inauguracao_cru": ("inauguracao", "last"),
    }
    for coluna in presentes_cum + presentes_snap:
        agregacoes[coluna] = (coluna, "last")

    fech = (
        trabalho.groupby(["unidade_id", competencia.rename("competencia")], observed=True)
        .agg(**agregacoes)
        .reset_index()
    )
    return _derivar_metricas(fech)


def _fechamento_vazio() -> pd.DataFrame:
    colunas = [
        "unidade_id", "competencia", "dia_ref", "dias_com_dado", "uf", "master",
        "unidade_cru", "inauguracao", "mes_completo", "operacao_mes_cheio", "faturamento",
        "faturamento_sem_agregador", "faturamento_agregador", "pagantes", "ativos",
        "agregadores", "visitas", "convertidos", "conversao_pct", "novos_alunos",
        "vendas", "cancelados", "saldo_operacional", "churn_pct",
        "receita_por_recorrente", "nps", "nps_valido", "em_cobranca",
        "em_cobranca_pct", "inadimplente", "treino_ativo", "pct_agregador_receita",
        "pct_agregador_alunos", "meses_operacao",
    ]
    return pd.DataFrame({c: pd.Series(dtype="float64") for c in colunas})


def _derivar_metricas(fech: pd.DataFrame) -> pd.DataFrame:
    """Deriva as metricas de negocio sobre o fechamento cru. Puro, sem IO."""
    f = fech.copy()
    f["inauguracao"] = pd.to_datetime(f["inauguracao_cru"], format="%d/%m/%Y", errors="coerce")
    limite = f["dia_ref"].max()
    f.loc[f["inauguracao"].dt.year < _ANO_INAUGURACAO_MIN, "inauguracao"] = pd.NaT
    f.loc[f["inauguracao"] > limite, "inauguracao"] = pd.NaT
    fim_do_mes = f["competencia"].dt.to_timestamp(how="end").dt.normalize()
    f["mes_completo"] = (f["dias_com_dado"] >= DIAS_MINIMOS_MES_COMPLETO) & (
        f["dia_ref"] >= fim_do_mes - pd.Timedelta(days=TOLERANCIA_FIM_DE_MES_DIAS)
    )
    # Unidade inaugurada DENTRO da competencia nao operou a janela inteira: o numero e'
    # real, mas nao e' comparavel com o de quem operou o mes todo. E' o gate que substitui
    # o piso de faturamento de R$ 20 mil da v1 -- um literal financeiro nao nomeado, que
    # `dimensionamento/config.py` proibe. Medido em jul/2026: as 4 unicas unidades abaixo
    # daquele piso (Paulinia, Limeira, Sao Goncalo Centro, Bonsucesso) sao exatamente as
    # que inauguraram no proprio mes -- ou seja, o gate semantico explica 100% dos casos
    # que o piso pegava, sem derrubar academia nenhuma da carteira.
    inicio_competencia = f["competencia"].dt.to_timestamp(how="start")
    f["operacao_mes_cheio"] = f["inauguracao"].isna() | (f["inauguracao"] <= inicio_competencia)

    for coluna in list(COLUNAS_CUMULATIVAS) + list(COLUNAS_SNAPSHOT):
        if coluna not in f.columns:
            f[coluna] = pd.NA
        f[coluna] = pd.to_numeric(f[coluna], errors="coerce")

    f["ativos"] = f["ativos_total"]
    f["agregadores"] = f["alunos_gympass"].fillna(0) + f["alunos_totalpass"].fillna(0)
    f["faturamento_agregador"] = f["faturamento"] - f["faturamento_sem_agregador"]
    f["conversao_pct"] = _divisao(100.0 * f["convertidos"], f["visitas"])
    # `SALDO_OPERACIONAL = [VENDAS_DIA] - [CANCELADOS_DIA]` (DAX oficial). NAO e'
    # `novos_alunos - cancelados`: `vendas > novos_alunos` em 78,6% das linhas e 23
    # unidades TROCAM DE SINAL entre as duas definicoes.
    f["saldo_operacional"] = f["vendas"] - f["cancelados"]
    f["receita_por_recorrente"] = _divisao(f["faturamento_sem_agregador"], f["pagantes"])
    f["em_cobranca_pct"] = _divisao(100.0 * f["em_cobranca"], f["pagantes"])
    base_alunos = f["pagantes"].fillna(0) + f["agregadores"].fillna(0)
    f["pct_agregador_alunos"] = _divisao(100.0 * f["agregadores"], base_alunos.replace(0, pd.NA))
    f["pct_agregador_receita"] = _divisao(100.0 * f["faturamento_agregador"], f["faturamento"])

    nps = pd.to_numeric(f["NPS"], errors="coerce")
    f["nps_valido"] = nps.between(NPS_MIN, NPS_MAX)
    f["nps"] = nps.where(f["nps_valido"])

    # `CHURN_DIA = [CANCELADOS_DIA] / [REC_MES_ANTERIOR]` (DAX oficial): o denominador e'
    # a base de recorrentes com que o mes COMECOU, nao a do proprio mes. Merge (e nao
    # `shift`) porque ha unidades com buraco na serie - com `shift`, o mes anterior seria
    # "o registro anterior", que pode estar a dois meses de distancia.
    anterior = f[["unidade_id", "competencia", "pagantes"]].copy()
    anterior["competencia"] = anterior["competencia"] + 1
    anterior = anterior.rename(columns={"pagantes": "pagantes_m1"})
    f = f.merge(anterior, on=["unidade_id", "competencia"], how="left")
    f["churn_pct"] = _divisao(100.0 * f["cancelados"], f["pagantes_m1"])

    f["meses_operacao"] = _meses_operacao(f["inauguracao"], f["competencia"])
    f["competencia"] = f["competencia"].astype(str)
    return f.drop(columns=["inauguracao_cru", "ativos_total"], errors="ignore")


def _divisao(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    """Divisao JSON-safe: denominador 0/nulo -> NaN (nunca inf)."""
    denom = pd.to_numeric(denominador, errors="coerce")
    return pd.to_numeric(numerador, errors="coerce") / denom.where(denom.ne(0))


def _meses_operacao(inauguracao: pd.Series, competencia: pd.Series) -> pd.Series:
    """Meses completos entre a inauguracao e a competencia (NaN se data invalida)."""
    inaug = pd.to_datetime(inauguracao, errors="coerce").dt.to_period("M")
    delta = (competencia - inaug).map(lambda p: p.n if pd.notna(p) else None)
    meses = pd.to_numeric(delta, errors="coerce")
    return meses.where(meses >= 0)


# ---------------------------------------------------------------------------
# Janela de 30 dias sobre o cumulativo que reseta
# ---------------------------------------------------------------------------


def rolling30(
    fech_corte: pd.DataFrame, fech_cheio: pd.DataFrame, competencia: str, coluna: str
) -> pd.Series:
    """Soma dos ~30 dias que terminam no dia de referencia, por unidade.

    Reconstroi a janela sobre a cumulativa que reseta no dia 1:
    `MTD(mes) + (mes anterior COMPLETO - MTD(mes anterior ate o mesmo dia))`. Ex.: o
    faturamento de 12/06 = jun(1..12) + mai(13..31), ou seja um mes cheio, e nao os 12
    dias parciais.

    `fech_corte` = fechamento com `dia_corte` no dia de referencia; `fech_cheio` = sem
    corte. Indexado por `unidade_id`.
    """
    periodo = pd.Period(competencia, freq="M")
    anterior = str(periodo - 1)

    atual = _serie_por_unidade(fech_corte, competencia, coluna)
    parcial_m1 = _serie_por_unidade(fech_corte, anterior, coluna)
    cheio_m1 = _serie_por_unidade(fech_cheio, anterior, coluna)

    cauda = (cheio_m1 - parcial_m1).clip(lower=0.0)
    return atual.add(cauda.reindex(atual.index).fillna(0.0), fill_value=0.0).where(atual.notna())


def _serie_por_unidade(fech: pd.DataFrame, competencia: str, coluna: str) -> pd.Series:
    linhas = fech[fech["competencia"] == competencia]
    if not len(linhas):
        return pd.Series(dtype="float64", name=coluna)
    return pd.to_numeric(linhas.set_index("unidade_id")[coluna], errors="coerce")


def receita_por_recorrente_30d(
    fech_corte: pd.DataFrame, fech_cheio: pd.DataFrame, competencia: str
) -> pd.Series:
    """Receita de balcao dos ultimos ~30 dias por recorrente ativo, por unidade.

    Este e' o conserto do "ticket medio" da v1. Validacao contra a base de producao: o
    rolling-30 do dia 12/06 da R$ 163,67 e o mes de maio fechado da R$ 162,47 - concordam
    em 0,7%, enquanto o numero exibido em producao era R$ 20,28.

    NAO usar o campo `ticket_medio` da API para isto: ele tem 26,5% de zeros no dia 1,
    correlacao de 0,313 com o ticket real e nenhuma formula candidata explica mais que 11%
    dos seus valores - e' outra grandeza.
    """
    faturamento = rolling30(fech_corte, fech_cheio, competencia, "faturamento_sem_agregador")
    pagantes = _serie_por_unidade(fech_corte, competencia, "pagantes")
    return _divisao(faturamento, pagantes.reindex(faturamento.index))


# ---------------------------------------------------------------------------
# Contexto comparativo: ranking e % vs media da rede (BLK-EXEC-01b)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EspecMetrica:
    """Como uma metrica se compara: direcao do ranking e se subir e' bom."""

    chave: str
    rotulo: str
    #: 'desc' = maior e' 1o lugar; 'asc' = menor e' 1o lugar.
    direcao: str
    #: True quando subir e' melhoria (faturamento); False quando piora (churn).
    bom_subindo: bool
    #: 'brl' | 'int' | 'pct' | 'nota' - formatacao de exibicao.
    formato: str = "int"


# Regras deduzidas da planilha do time de campo (`ANALISE DIARIA DASHBOARD.xlsx`) e
# validadas numericamente contra a base: no faturamento, o ranking reproduzido bate em
# 89/89 unidades. As sutilezas nunca estiveram escritas em lugar nenhum - churn ranqueia
# pela TAXA (nao pela quantidade) e ao contrario; "em cobranca" pelo PERCENTUAL; NPS pela
# NOTA (nao pelo volume de pesquisas).
METRICAS: tuple[EspecMetrica, ...] = (
    EspecMetrica("faturamento", "Faturamento", "desc", True, "brl"),
    EspecMetrica("faturamento_sem_agregador", "Receita de recorrentes", "desc", True, "brl"),
    EspecMetrica("faturamento_agregador", "Receita de agregadores", "desc", True, "brl"),
    EspecMetrica("ativos", "Alunos ativos", "desc", True, "int"),
    EspecMetrica("pagantes", "Recorrentes", "desc", True, "int"),
    EspecMetrica("agregadores", "Agregadores", "desc", True, "int"),
    EspecMetrica("receita_por_recorrente", "Receita por recorrente", "desc", True, "brl"),
    EspecMetrica("churn_pct", "Churn", "asc", False, "pct"),
    EspecMetrica("saldo_operacional", "Saldo operacional", "desc", True, "int"),
    EspecMetrica("novos_alunos", "Novos alunos", "desc", True, "int"),
    EspecMetrica("vendas", "Vendas", "desc", True, "int"),
    EspecMetrica("cancelados", "Cancelados", "asc", False, "int"),
    EspecMetrica("visitas", "Visitas", "desc", True, "int"),
    EspecMetrica("conversao_pct", "Conversao", "desc", True, "pct"),
    EspecMetrica("nps", "NPS", "desc", True, "nota"),
    EspecMetrica("em_cobranca_pct", "Em cobranca", "asc", False, "pct"),
    EspecMetrica("pct_agregador_alunos", "Dependencia de agregador", "asc", False, "pct"),
    EspecMetrica("inadimplente", "Inadimplentes", "asc", False, "int"),
    EspecMetrica("treino_ativo", "Treino ativo", "desc", True, "int"),
)

METRICAS_POR_CHAVE: Mapping[str, EspecMetrica] = {m.chave: m for m in METRICAS}


def contexto_comparativo(
    mes: pd.DataFrame,
    metricas: Iterable[EspecMetrica] = METRICAS,
    comparaveis: pd.Series | None = None,
) -> pd.DataFrame:
    """Acrescenta, para cada metrica, `rank_<m>`, `rank_total_<m>` e `vs_media_<m>`.

    E' o **quarteto de contexto** da planilha do time -- `MES | M-1 | Ranking N/89 |
    % vs Media Rede`. Eles nao leem desempenho por cor: leem "estou 64% abaixo da media da
    rede e sou 79o de 89". Uma tela que substitua a planilha precisa entregar os quatro
    valores; o alerta por regua absoluta SOMA-SE a isso, nao substitui.

    Empates recebem a mesma posicao (equivalente ao `RANK.EQ` do Excel) e o total conta so
    quem tem valor -- ranquear "78o de 89" quando 20 unidades nao tem NPS seria mentira.
    A media da rede e' a media SIMPLES das unidades com valor, sobre o `mes` inteiro que
    chega aqui: quem filtra o recorte decide o universo, e a Visao Executiva sempre passa
    a rede toda (filtrar antes tornaria "media da rede" dependente do filtro da tela).

    `comparaveis` limita QUEM entra no ranking e na media -- por padrao, quem operou a
    janela inteira (`operacao_mes_cheio`). Uma unidade inaugurada no dia 30 recebe posicao
    e "% vs media" NULOS em vez de um "92o de 92" que so mede a data de abertura. A
    planilha do time comete esse erro de forma parecida, dividindo por 91 e incluindo a
    ADMINISTRACAO (R$ 218 de faturamento) na media contra a qual as 89 sao medidas.
    """
    saida = mes.copy()
    if comparaveis is None:
        comparaveis = (
            saida["operacao_mes_cheio"].fillna(False).astype(bool)
            if "operacao_mes_cheio" in saida.columns
            else pd.Series(True, index=saida.index)
        )
    comparaveis = comparaveis.reindex(saida.index).fillna(False).astype(bool)

    for espec in metricas:
        if espec.chave not in saida.columns:
            continue
        valores = pd.to_numeric(saida[espec.chave], errors="coerce").where(comparaveis)
        crescente = espec.direcao == "asc"
        saida[f"rank_{espec.chave}"] = valores.rank(method="min", ascending=crescente)
        saida[f"rank_total_{espec.chave}"] = int(valores.notna().sum())
        media = valores.mean()
        saida[f"vs_media_{espec.chave}"] = (
            _divisao(100.0 * (valores - media), pd.Series(media, index=valores.index))
            if pd.notna(media)
            else pd.Series(float("nan"), index=valores.index, dtype="float64")
        )
    return saida


def serie_diaria(df: pd.DataFrame, unidade_id: str, coluna: str) -> pd.DataFrame:
    """Serie DIARIA de uma coluna cumulativa (o `diff` dentro do mes; dia 1 = o valor).

    E' o bloco "Novos alunos diario" que hoje o time cola a mao, 31 colunas por vez.
    Colunas: `data`, `valor` (o do dia, ja des-acumulado).
    """
    sub = df[df["unidade_id"] == unidade_id].sort_values("_data")
    if not len(sub) or coluna not in sub.columns:
        return pd.DataFrame({"data": pd.Series(dtype="datetime64[ns]"), "valor": pd.Series(dtype="float64")})
    valores = pd.to_numeric(sub[coluna], errors="coerce")
    competencia = sub["_data"].dt.to_period("M")
    diario = valores.groupby(competencia, observed=True).diff()
    # Primeiro dia de cada mes: o cumulativo JA e' o valor do dia (reset no dia 1).
    diario = diario.fillna(valores)
    return pd.DataFrame({"data": sub["_data"].to_numpy(), "valor": diario.to_numpy()})
