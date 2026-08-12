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


#: Rótulos da procedência do faturamento de cada linha do fechamento.
ORIGEM_UX = "ux"
ORIGEM_FINANCEIRO = "financeiro"

#: Coluna do fechamento -> coluna da planilha do Financeiro. A substituição acontece no
#: fechamento CRU, antes das derivadas: assim `faturamento_agregador`,
#: `receita_por_recorrente` e `pct_agregador_receita` se recalculam sozinhas a partir da
#: fonte nova, em vez de sobrarem coerentes com a antiga.
_COLUNAS_DO_FINANCEIRO: dict[str, str] = {
    "faturamento": "faturamento",
    "faturamento_sem_agregador": "vendas_ux",
}


def aplicar_faturamento_financeiro(
    fech: pd.DataFrame, financeiro: pd.DataFrame, catalogo: Mapping[str, Unidade]
) -> pd.DataFrame:
    """Sobrepoe o faturamento da planilha do Financeiro no fechamento MENSAL.

    OVERRIDE, nunca INSERT: unidade que so existe na planilha nao vira linha nova na
    carteira. Ela nao teria pagantes, churn nem NPS, e entraria na tela como uma unidade
    pela metade -- alem de mexer no denominador de toda media ponderada da aba. Quem ficou
    de fora sai em `attrs["financeiro_sem_par"]` para o operador cobrar a inclusao na
    Growth (medido em 2026-07: Sao Carlos-SP, Jardim das Americas-MT e Vila Izabel-PR,
    R$ 523 mil/mes invisiveis).

    O join e' por nome CRU normalizado, atraves do catalogo -- nunca por `chave_unidade`.
    A diferenca e' a mesma das "Aguas Claras": a chave normalizada colapsa a academia e o
    studio numa coisa so, e o faturamento de uma iria parar na outra.
    """
    fora = fech.assign(origem_faturamento=ORIGEM_UX)
    if not len(fech) or not len(financeiro) or not catalogo:
        fora.attrs["financeiro_aplicado"] = 0
        fora.attrs["financeiro_sem_par"] = []
        return fora

    por_nome = {
        _sem_acento(nome): uid
        for uid, unidade in catalogo.items()
        for nome in unidade.nomes_crus
    }
    fin = financeiro.copy()
    resgate = _resgate_por_aperto(por_nome, fin["unidade_ux"])
    fin["unidade_id"] = fin["unidade_ux"].map(
        lambda nome: por_nome.get(_sem_acento(nome)) or resgate.get(nome)
    )
    com_valor = fin[fin["faturamento"].notna()]
    sem_par = sorted(
        {
            str(n)
            for n in com_valor.loc[com_valor["unidade_id"].isna() & (com_valor["faturamento"] > 0), "unidade_ux"]
            if not eh_excluida(n)
        }
    )
    fin = fin[fin["unidade_id"].notna() & fin["faturamento"].notna()]

    colunas = [c for c in _COLUNAS_DO_FINANCEIRO.values() if c in fin.columns]
    # Dois codigos do Financeiro podem apontar para a MESMA unidade da Growth; o de-para
    # dizendo isso e' o Financeiro afirmando que sao a mesma academia, entao somam.
    fin = (
        fin.groupby(["unidade_id", "competencia"], as_index=False)[colunas]
        .sum(min_count=1)
        .rename(columns={v: f"_fin_{k}" for k, v in _COLUNAS_DO_FINANCEIRO.items() if v in colunas})
    )

    fora["_competencia_txt"] = fora["competencia"].astype(str)
    fora = fora.merge(
        fin, left_on=["unidade_id", "_competencia_txt"], right_on=["unidade_id", "competencia"],
        how="left", suffixes=("", "_fin"),
    ).drop(columns=["competencia_fin", "_competencia_txt"], errors="ignore")

    casou = fora["_fin_faturamento"].notna()
    for destino in _COLUNAS_DO_FINANCEIRO:
        origem = f"_fin_{destino}"
        if origem in fora.columns and destino in fora.columns:
            fora[destino] = fora[origem].where(casou, fora[destino])
    fora.loc[casou, "origem_faturamento"] = ORIGEM_FINANCEIRO
    fora = fora.drop(columns=[c for c in fora.columns if c.startswith("_fin_")], errors="ignore")

    fora.attrs["financeiro_aplicado"] = int(casou.sum())
    fora.attrs["financeiro_sem_par"] = sem_par
    return fora


def _apertar(valor: object) -> str:
    """Chave "apertada": so letras e digitos, sem acento. PRESERVA o sufixo de UF.

    E' o que casa "CEILANDIA QNN 32 - DF" com "CEILANDIA QNN32 - DF " e
    "SAO GONCALO CENTRO - RJ" com "SAO GONCALO - CENTRO - RJ" -- variacoes de espaco e
    hifen que o de-para do Financeiro ainda nao cobre. Como o sufixo de UF sobrevive,
    "AGUAS CLARAS" e "AGUAS CLARAS - DF" continuam SEPARADAS, que e' o ponto todo.
    """
    return re.sub(r"[^A-Z0-9]+", "", _sem_acento(valor))


def _resgate_por_aperto(
    por_nome: Mapping[str, str], nomes_do_financeiro: Iterable[object]
) -> dict[object, str]:
    """Segunda passada do join, so' para o que sobrou -- e so' quando NAO ha ambiguidade.

    Uma chave apertada que atrai duas unidades da Growth (ou dois nomes do Financeiro) fica
    de fora: um palpite errado aqui joga o faturamento de uma academia na outra, e um
    buraco visivel e' melhor que um numero silenciosamente trocado.
    """
    catalogo_apertado: dict[str, list[str]] = {}
    for nome, uid in por_nome.items():
        catalogo_apertado.setdefault(_apertar(nome), []).append(uid)

    pendentes: dict[str, list[object]] = {}
    for bruto in nomes_do_financeiro:
        if _sem_acento(bruto) not in por_nome:
            pendentes.setdefault(_apertar(bruto), []).append(bruto)

    resgate: dict[object, str] = {}
    for apertado, candidatos_do_fin in pendentes.items():
        candidatos = set(catalogo_apertado.get(apertado, []))
        if len(candidatos) == 1 and len({_sem_acento(n) for n in candidatos_do_fin}) == 1:
            for bruto in candidatos_do_fin:
                resgate[bruto] = next(iter(candidatos))
    return resgate


def fechamento_mensal(
    df: pd.DataFrame,
    dia_corte: int | None = None,
    financeiro: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Uma linha por (`unidade_id`, competencia) com o ultimo dia COM DADO do mes.

    `dia_corte` limita cada mes aos dias `<= dia_corte`, que e' como se compara mes
    parcial com mes parcial: o acumulado de 1..12/06 contra o acumulado de 1..12/05. Sem
    ele, cada mes vale por inteiro (a serie fechada que alimenta coorte e historico).

    Cumulativas usam sempre o **ultimo** valor do mes, nunca o maximo: `cancelados` CAI
    dentro do mes em 36,7% dos unidade-mes (estorno de cancelamento), e `max` congelaria
    o pico em vez do fechamento real.

    `financeiro` sobrepoe o faturamento pela planilha do Financeiro (base dos royalties) e
    so vale para o mes FECHADO: com `dia_corte` a janela e' parcial e a planilha, mensal,
    nao sabe responder por ela -- ver `aplicar_faturamento_financeiro`.

    Vetorizado de proposito - substitui o laco Python por unidade da v1. Medido: 2.132
    linhas em ~17 ms para a rede inteira.
    """
    # `origem_faturamento` e' do fechamento MENSAL, nao da janela livre: so' aqui existe
    # sobreposicao do Financeiro. Por isso entra aqui e nao em `_fechamento_vazio`, de onde
    # `fechamento_periodo` tambem tira as colunas dele.
    vazio = _fechamento_vazio().assign(origem_faturamento=pd.Series(dtype="object"))
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
    if financeiro is not None and dia_corte is None:
        fech = aplicar_faturamento_financeiro(fech, financeiro, catalogo_de(df))
    else:
        fech = fech.assign(origem_faturamento=ORIGEM_UX)
    diagnostico = dict(fech.attrs)
    derivado = _derivar_metricas(fech)
    derivado.attrs.update(diagnostico)
    return derivado


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


def _derivar_comuns(fech: pd.DataFrame) -> pd.DataFrame:
    """Métricas que NÃO dependem do formato da janela (mês fechado ou intervalo livre).

    Vive separada de `_derivar_metricas` porque `fechamento_periodo` precisa exatamente
    das MESMAS contas: duplicá-las faria as duas versões divergirem na primeira
    manutenção, e a tela exibe as duas lado a lado -- "julho" e "01/07 a 20/07" têm de
    responder com a mesma definição de ativos, de agregador e de NPS válido.

    O que fica de fora é só o que a janela define: completude, gate de operação, churn
    (o denominador muda de base) e maturidade.
    """
    f = fech.copy()
    f["inauguracao"] = pd.to_datetime(f["inauguracao_cru"], format="%d/%m/%Y", errors="coerce")
    limite = f["dia_ref"].max()
    f.loc[f["inauguracao"].dt.year < _ANO_INAUGURACAO_MIN, "inauguracao"] = pd.NaT
    f.loc[f["inauguracao"] > limite, "inauguracao"] = pd.NaT

    for coluna in list(COLUNAS_CUMULATIVAS) + list(COLUNAS_SNAPSHOT):
        if coluna not in f.columns:
            f[coluna] = pd.NA
        f[coluna] = pd.to_numeric(f[coluna], errors="coerce")

    f["ativos"] = f["ativos_total"]
    f["agregadores"] = f["alunos_gympass"].fillna(0) + f["alunos_totalpass"].fillna(0)
    # A separacao entre receita de recorrente e de agregador so' e' CONHECIDA quando o
    # faturamento veio da planilha do Financeiro. Na Growth, `faturamento` e
    # `faturamento_sem_agregador` sao identicos em 100% das linhas desde maio/2025 -- a
    # subtracao da zero, e zero aqui e' uma AFIRMACAO falsa ("esta unidade nao fatura com
    # Gympass") e nao uma medida. Sem dado e' o que ela realmente e'. Sem isto, o painel de
    # SSS anunciava "Receita de agregadores R$ 0 vs R$ 0" para uma rede que fatura R$ 5,1
    # milhoes por mes com agregador.
    f["faturamento_agregador"] = f["faturamento"] - f["faturamento_sem_agregador"]
    if "origem_faturamento" in f.columns:
        do_financeiro = f["origem_faturamento"].eq(ORIGEM_FINANCEIRO)
        f["faturamento_agregador"] = f["faturamento_agregador"].where(do_financeiro)
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
    return f


def _janela_completa(
    dias_com_dado: pd.Series, dia_ref: pd.Series, fim_da_janela: pd.Series | pd.Timestamp
) -> pd.Series:
    """A janela tem dias coletados o bastante E a coleta CHEGOU ao fim dela.

    Os dois lados são obrigatórios: só o piso de dias já fazia o mês EM CURSO passar por
    fechado do dia 25 em diante (ver `TOLERANCIA_FIM_DE_MES_DIAS`).
    """
    return (dias_com_dado >= DIAS_MINIMOS_MES_COMPLETO) & (
        dia_ref >= fim_da_janela - pd.Timedelta(days=TOLERANCIA_FIM_DE_MES_DIAS)
    )


def _derivar_metricas(fech: pd.DataFrame) -> pd.DataFrame:
    """Deriva as metricas de negocio sobre o fechamento MENSAL cru. Puro, sem IO."""
    f = _derivar_comuns(fech)
    fim_do_mes = f["competencia"].dt.to_timestamp(how="end").dt.normalize()
    f["mes_completo"] = _janela_completa(f["dias_com_dado"], f["dia_ref"], fim_do_mes)
    # Unidade inaugurada DENTRO da competencia nao operou a janela inteira: o numero e'
    # real, mas nao e' comparavel com o de quem operou o mes todo. E' o gate que substitui
    # o piso de faturamento de R$ 20 mil da v1 -- um literal financeiro nao nomeado, que
    # `dimensionamento/config.py` proibe. Medido em jul/2026: as 4 unicas unidades abaixo
    # daquele piso (Paulinia, Limeira, Sao Goncalo Centro, Bonsucesso) sao exatamente as
    # que inauguraram no proprio mes -- ou seja, o gate semantico explica 100% dos casos
    # que o piso pegava, sem derrubar academia nenhuma da carteira.
    inicio_competencia = f["competencia"].dt.to_timestamp(how="start")
    f["operacao_mes_cheio"] = f["inauguracao"].isna() | (f["inauguracao"] <= inicio_competencia)

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
# Fechamento de um intervalo livre de datas
# ---------------------------------------------------------------------------


def _meses_inteiros_na_janela(
    competencias: pd.Series, inicio: pd.Timestamp, fim: pd.Timestamp
) -> pd.Series:
    """Quais competencias a janela cobre do dia 1 ao ultimo dia.

    So' nelas a planilha do Financeiro pode entrar: ela conhece o TOTAL do mes e nada
    abaixo disso. Numa janela de 10/06 a 05/08, junho e agosto ficam de fora e julho entra.
    """
    return (competencias.dt.to_timestamp(how="start") >= inicio) & (
        competencias.dt.to_timestamp(how="end").dt.normalize() <= fim
    )


def fechamento_periodo(
    df: pd.DataFrame,
    inicio: pd.Timestamp,
    fim: pd.Timestamp,
    financeiro: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Uma linha por unidade com o agregado de `[inicio, fim]` - as DUAS pontas dentro.

    É o `fechamento_mensal` para uma janela que o calendário não define ("de 10/06 a
    05/08"), e a conta muda por causa do reset do dia 1. Nenhuma das duas leituras
    ingênuas serve para uma cumulativa:

    * **somar os valores diários** conta o acumulado N vezes (a base já é MTD, não
      diária);
    * **pegar o último valor do intervalo** joga fora tudo o que aconteceu antes da
      última virada de mês - de 20/06 a 05/07 o faturamento sairia com 5 dias de julho.

    O certo é fatiar o intervalo por MÊS e somar as parcelas: dentro de cada mês,
    `valor no último dia da porção - valor no último dia com dado ANTES dela` (e zero
    quando a porção começa no dia 1, porque ali o cumulativo já começou do zero). Parcela
    NEGATIVA é legítima e não se clampa: `cancelados` CAI dentro do mês em 36,7% dos
    unidade-mês por estorno, e zerar isso inventaria cancelamento que não houve.

    Snapshots seguem sendo foto: o valor do ÚLTIMO dia com dado até `fim`, sem soma nem
    média - somar `pagantes` de 30 dias daria 30x a base de alunos.

    `pagantes_inicio` (novo aqui) é a base de recorrentes com que o intervalo COMEÇOU: o
    snapshot do último dia com dado ANTERIOR a `inicio`, em qualquer mês. É o denominador
    do churn da janela, o análogo livre do `[REC_MES_ANTERIOR]` do PowerBI. NaN quando a
    unidade não tem histórico antes do intervalo - churn sem base é desconhecido, nunca
    zero (dividir por zero pintaria de vermelho quem só é nova).

    `financeiro` sobrepoe o faturamento pela planilha do Financeiro, mas SO' nas
    competencias que a janela cobre inteiras -- e' o unico recorte para o qual a planilha,
    que e' mensal, tem resposta. Numa competencia coberta inteira a parcela do intervalo E'
    o total do mes (nao ha base a descontar: ou a janela comeca no dia 1, ou o mes comecou
    na virada), entao a substituicao e' exata. `origem_faturamento` diz o que aconteceu com
    cada unidade: `financeiro`, `ux`, ou `misto` quando a janela pega meses dos dois tipos.

    Devolve DataFrame vazio (mesmas colunas) para base vazia, intervalo invertido ou
    intervalo sem dado nenhum.
    """
    inicio = pd.Timestamp(inicio).normalize()
    fim = pd.Timestamp(fim).normalize()
    vazio = _fechamento_periodo_vazio()
    if not len(df) or pd.isna(inicio) or pd.isna(fim) or inicio > fim:
        return vazio

    janela = df[(df["_data"] >= inicio) & (df["_data"] <= fim)]
    if not len(janela):
        return vazio
    janela = janela.sort_values(["unidade_id", "_data"], kind="stable")

    presentes_cum = [c for c in COLUNAS_CUMULATIVAS if c in janela.columns]
    presentes_snap = [c for c in COLUNAS_SNAPSHOT if c in janela.columns]

    # Passo 1: fechar cada (unidade, mês) tocado pelo intervalo. `last` - e nunca `max` -
    # pelo mesmo motivo do fechamento mensal (estorno faz a cumulativa cair).
    competencia = janela["_data"].dt.to_period("M")
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
    por_mes = (
        janela.groupby(["unidade_id", competencia.rename("competencia")], observed=True)
        .agg(**agregacoes)
        .reset_index()
        .sort_values(["unidade_id", "competencia"], kind="stable")
    )

    # Passo 2: colapsar os meses numa linha por unidade. Como `por_mes` está em ordem
    # crescente de competência, o `last` de um snapshot já É o último dia com dado até
    # `fim` -- e `dias_com_dado` soma porque um dia pertence a um mês só.
    agregacoes_unidade: dict[str, tuple[str, str]] = {
        "dia_ref": ("dia_ref", "max"),
        "dias_com_dado": ("dias_com_dado", "sum"),
        "uf": ("uf", "last"),
        "master": ("master", "last"),
        "unidade_cru": ("unidade_cru", "last"),
        "inauguracao_cru": ("inauguracao_cru", "last"),
    }
    for coluna in presentes_snap:
        agregacoes_unidade[coluna] = (coluna, "last")
    fech = por_mes.groupby("unidade_id", observed=True).agg(**agregacoes_unidade).reset_index()

    if presentes_cum:
        parcelas = _parcelas_cumulativas(df, por_mes, presentes_cum, inicio)
        for coluna in presentes_cum:
            fech[coluna] = fech["unidade_id"].map(parcelas[coluna])

    fech = _sobrepor_periodo(fech, por_mes, financeiro, catalogo_de(df), inicio, fim)

    base_recorrentes = _ultimo_valor_antes(df, ["pagantes"], inicio)
    fech["pagantes_inicio"] = pd.to_numeric(
        fech["unidade_id"].map(base_recorrentes["pagantes"]), errors="coerce"
    )
    fech["periodo_inicio"] = inicio
    fech["periodo_fim"] = fim
    return _derivar_periodo(fech, inicio, fim)


ORIGEM_MISTA = "misto"


def _sobrepor_periodo(
    fech: pd.DataFrame,
    por_mes: pd.DataFrame,
    financeiro: pd.DataFrame | None,
    catalogo: Mapping[str, Unidade],
    inicio: pd.Timestamp,
    fim: pd.Timestamp,
) -> pd.DataFrame:
    """Substitui, na janela livre, o faturamento das competencias cobertas INTEIRAS.

    A parcela de um mes coberto inteiro E' o total daquele mes -- nao ha base a descontar,
    porque ou a janela comeca no dia 1, ou o mes comecou na virada. Entao a soma do
    intervalo pode ser recomposta como "o que a planilha diz dos meses inteiros" mais "o
    que a Growth diz do resto", e a unidade recebe `misto` quando as duas parcelas existem.

    Sem isso, escolher julho na tela mostrava o faturamento da Growth no topo e o do
    Financeiro no grafico de 12 meses -- dois numeros para o mesmo mes, na mesma tela.
    """
    if financeiro is None or not len(fech):
        return fech.assign(origem_faturamento=ORIGEM_UX)

    inteiros = _meses_inteiros_na_janela(por_mes["competencia"], inicio, fim)
    if not inteiros.any():
        return fech.assign(origem_faturamento=ORIGEM_UX)

    # `reset_index`: `aplicar_faturamento_financeiro` faz merge e devolve indice novo; sem
    # zerar aqui, a subtracao do delta alinharia pelo indice antigo e trocaria as unidades.
    dentro = por_mes.loc[inteiros, ["unidade_id", "competencia"]].reset_index(drop=True)
    for coluna in _COLUNAS_DO_FINANCEIRO:
        dentro[coluna] = (
            pd.to_numeric(por_mes.loc[inteiros, coluna], errors="coerce").reset_index(drop=True)
            if coluna in por_mes
            else pd.NA
        )
    sobreposto = aplicar_faturamento_financeiro(dentro, financeiro, catalogo)
    casou = sobreposto["origem_faturamento"] == ORIGEM_FINANCEIRO

    fora = fech.copy()
    for coluna in _COLUNAS_DO_FINANCEIRO:
        if coluna not in fora.columns:
            continue
        # delta por unidade = (planilha - Growth) somado sobre os meses que casaram. Somar
        # o DELTA, e nao substituir o total, preserva a parcela dos meses parciais da janela.
        delta = (
            (pd.to_numeric(sobreposto[coluna], errors="coerce") - pd.to_numeric(dentro[coluna], errors="coerce"))
            .where(casou, 0.0)
            .groupby(sobreposto["unidade_id"])
            .sum()
        )
        fora[coluna] = pd.to_numeric(fora[coluna], errors="coerce") + fora["unidade_id"].map(delta).fillna(0.0)

    meses_por_unidade = por_mes.groupby("unidade_id")["competencia"].nunique()
    casados = sobreposto.loc[casou].groupby("unidade_id")["competencia"].nunique()
    fora["origem_faturamento"] = [
        ORIGEM_FINANCEIRO
        if casados.get(uid, 0) and casados.get(uid, 0) == meses_por_unidade.get(uid, 0)
        else ORIGEM_MISTA
        if casados.get(uid, 0)
        else ORIGEM_UX
        for uid in fora["unidade_id"]
    ]
    return fora


def _parcelas_cumulativas(
    df: pd.DataFrame, por_mes: pd.DataFrame, colunas: list[str], inicio: pd.Timestamp
) -> pd.DataFrame:
    """Soma por unidade das parcelas `valor_fim - valor_base` de cada mês do intervalo.

    Só o PRIMEIRO mês desconta base, e só quando o intervalo não começa no dia 1: nos
    meses seguintes a porção começa na virada, onde o cumulativo já vale zero. Unidade sem
    dado antes do início DENTRO daquele mês também desconta zero -- para ela o acumulado
    do mês começou a existir dentro do próprio intervalo.
    """
    parcelas = por_mes[["unidade_id", "competencia"]].copy()
    for coluna in colunas:
        parcelas[coluna] = pd.to_numeric(por_mes[coluna], errors="coerce")

    if inicio.day != 1:
        mes_inicio = inicio.to_period("M")
        base = _ultimo_valor_antes(df, colunas, inicio, desde=mes_inicio.to_timestamp())
        primeiro_mes = parcelas["competencia"] == mes_inicio
        for coluna in colunas:
            desconto = parcelas.loc[primeiro_mes, "unidade_id"].map(base[coluna])
            desconto = pd.to_numeric(desconto, errors="coerce").fillna(0.0)
            parcelas.loc[primeiro_mes, coluna] = parcelas.loc[primeiro_mes, coluna] - desconto

    # `min_count=1` preserva o NaN de quem não tem o dado: com o `sum` padrão, coluna
    # ausente na ingestão viraria 0,0 e passaria por "faturou zero".
    return parcelas.groupby("unidade_id", observed=True)[colunas].sum(min_count=1)


def _ultimo_valor_antes(
    df: pd.DataFrame,
    colunas: list[str],
    limite: pd.Timestamp,
    desde: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Valor das `colunas` no último dia com dado ANTES de `limite` (>= `desde`), por unidade.

    Indexado por `unidade_id` e possivelmente VAZIO - quem não aparece aqui não tinha dado
    naquela janela, e cabe a quem chama decidir se isso é zero (base do cumulativo) ou
    desconhecido (base do churn).
    """
    presentes = [c for c in colunas if c in df.columns]
    anteriores = df[df["_data"] < limite] if len(df) else df
    if desde is not None and len(anteriores):
        anteriores = anteriores[anteriores["_data"] >= desde]
    if not len(anteriores) or not presentes:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in colunas})
    valores = (
        anteriores.sort_values(["unidade_id", "_data"], kind="stable")
        .groupby("unidade_id", observed=True)[presentes]
        .last()
    )
    for coluna in colunas:
        valores[coluna] = (
            pd.to_numeric(valores[coluna], errors="coerce")
            if coluna in valores.columns
            else float("nan")
        )
    return valores[colunas]


def _derivar_periodo(
    fech: pd.DataFrame, inicio: pd.Timestamp, fim: pd.Timestamp
) -> pd.DataFrame:
    """Deriva as métricas sobre o fechamento de intervalo. Puro, sem IO."""
    f = _derivar_comuns(fech)

    # "Completo" continua querendo dizer MÊS CIVIL fechado: as réguas do time (faixa de
    # faturamento, diagnóstico) são limiares de mês inteiro. Um intervalo de 10 dias pode
    # ter 10 dias de coleta perfeitos e ainda assim não ser comparável com elas.
    mes_inicio = inicio.to_period("M")
    mes_civil_inteiro = bool(
        inicio == mes_inicio.to_timestamp(how="start").normalize()
        and fim == mes_inicio.to_timestamp(how="end").normalize()
    )
    f["periodo_completo"] = (
        _janela_completa(f["dias_com_dado"], f["dia_ref"], fim) if mes_civil_inteiro else False
    )
    # Mesmo gate do mensal, só que contra a ponta esquerda do intervalo: quem inaugurou
    # DENTRO da janela não operou a janela inteira e não entra em ranking nem em média.
    f["operacao_periodo_cheio"] = f["inauguracao"].isna() | (f["inauguracao"] <= inicio)
    # Churn da janela: cancelados do intervalo sobre a base com que ele COMEÇOU. O
    # `pagantes_m1` do mensal não serve aqui - o "mês anterior" de um intervalo livre não
    # existe, e para um mês civil os dois coincidem (ver os testes de equivalência).
    f["churn_pct"] = _divisao(100.0 * f["cancelados"], f["pagantes_inicio"])
    competencia_fim = pd.Series([fim.to_period("M")] * len(f), index=f.index, dtype="period[M]")
    f["meses_operacao"] = _meses_operacao(f["inauguracao"], competencia_fim)
    return f.drop(columns=["inauguracao_cru", "ativos_total"], errors="ignore")


#: Colunas do fechamento de intervalo: as do mensal, menos o que só o calendário define,
#: mais as da janela livre. Derivada de `_fechamento_vazio` de propósito -- duas listas
#: escritas à mão divergiriam, e o front quebra pela COLUNA que falta, não pelo cálculo.
_TROCAS_PERIODO: tuple[str, ...] = ("competencia", "mes_completo", "operacao_mes_cheio")
_EXTRAS_PERIODO: tuple[str, ...] = (
    "periodo_inicio", "periodo_fim", "periodo_completo", "operacao_periodo_cheio",
    "pagantes_inicio", "origem_faturamento",
)


def _fechamento_periodo_vazio() -> pd.DataFrame:
    colunas = [c for c in _fechamento_vazio().columns if c not in _TROCAS_PERIODO]
    colunas.extend(_EXTRAS_PERIODO)
    return pd.DataFrame({c: pd.Series(dtype="float64") for c in colunas})


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
    # As duas dependencias de agregador convivem, e o rotulo diz QUAL porque elas discordam
    # muito: medido em 2026-07, a rede tem 37,1% dos ALUNOS vindos de agregador e apenas
    # 22,9% da RECEITA -- mediana de 14,8 p.p. de diferenca por unidade, e ate 33,3 p.p.
    # (Sao Goncalo Shopping: 57,9% dos alunos, 24,5% da receita). Ate maio/2025 so' a de
    # alunos existia de fato, porque a Growth zerava a receita de agregador.
    # Acentuados: `rotulo` viaja no payload publico de `/api/rede/filtros` e vira cabecalho
    # de coluna e item de ordenacao na tela. Os vizinhos sem acento sao anteriores a este
    # trabalho e ficam como estao -- mexer neles alargaria o diff sem necessidade.
    EspecMetrica("pct_agregador_alunos", "Dependência de agregador (alunos)", "asc", False, "pct"),
    EspecMetrica("pct_agregador_receita", "Dependência de agregador (receita)", "asc", False, "pct"),
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
