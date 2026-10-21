"""Leitura da PRACA: o que o motor sabe da cidade, alem do raio de 1 km do ponto.

DOIS RAIOS convivem aqui, e nenhum e' redigitado. `RAIO_INFLUENCIA_M` (1 km, DEC-051) e' o raio
do MODELO de mercado: desconta o residual e desenha a pressao da cidade inteira no Relatorio
Municipal. `RAIO_PRESSAO_PONTO_M` (750 m, pedido do Juan em 2026-09-23) e' o raio de LEITURA da
pagina de pressao do Relatorio Pontual: o disco em volta de cada academia e a contagem de quem
alcanca o ponto. Trocar o segundo nao mexe no modelo; trocar o primeiro exige DEC.

Dois relatorios leem daqui (pedido do Felipe em 2026-09-10; divisao entre eles do Juan em
2026-09-17):

- **Relatorio Municipal** (`relatorio_municipal.gerar_pdf_relatorio_municipal`, parametro
  `praca`, pacote `PracaDaCidade`), quatro paginas: mapas de calor da cidade (renda domiciliar e
  densidade por hexagono), pressao concorrencial da cidade inteira (os discos de 1 km
  sobrepostos), como a cidade esta indo (camada de crescimento municipal) e onde crescer (os 5
  melhores hexagonos).
- **Relatorio Pontual** (`censo_report.gerar_pdf_relatorio_pontual_classico`, parametro `praca`,
  pacote `PracaDoPonto`), duas paginas: pressao concorrencial sobre o ponto e como a cidade esta
  indo, com o hexagono do ponto (obra nova 2016-2023, `crescimento_hex`) ao lado do municipio.

Este modulo e' PURO: recebe DataFrames ja carregados e devolve estruturas prontas para o render.
Nada aqui le arquivo, recalcula score ou grava artefato -- READ-ONLY sobre o M1. Quem carrega e'
`api/service.montar_pdf_municipio` (municipal, motor e bot pelo mesmo preparo) e o piloto web
(`web/server/app.py`, `_praca_para_pdf`, pontual).

POR QUE O TOP 5 NAO E' O RESIDUAL PURO. `oferta_efetiva_disponivel` tem Spearman ~0,995 com a
populacao (DEC-041): ordenar por ele poe no topo o hexagono mais POPULOSO, que nas capitais e'
com frequencia o mais pobre. Aqui o hexagono so' e' elegivel com residual positivo E renda
domiciliar igual ou acima da mediana da propria cidade PONDERADA PELA POPULACAO (DEC-072,
`mediana_renda_da_cidade`); entre os elegiveis a ordem e' o `indice_praca` da DEC-041 (70%
socioeconomico, 30% demanda). E' uma leitura do PDF: o funil, `/api/hexagonos` e o
`indice_praca` nao mudam.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from motor_expansao.pipelines.pressao_concorrencial_1km import RAIO_INFLUENCIA_M

# Raio de LEITURA da pagina de pressao do Relatorio PONTUAL (disco por academia + contagem de
# quem alcanca o ponto). Nao e' o raio do modelo (`RAIO_INFLUENCIA_M`): ver docstring do modulo.
RAIO_PRESSAO_PONTO_M = 750.0

TOP_N_ONDE_CRESCER = 5


def rotulo_raio(raio_m: float) -> str:
    """750 -> "750 m"; um quilometro -> "1,0 km". Em metros abaixo de 1 km: `.1f` faria 0,75 virar "0,8 km".

    Um formatador so' para a imagem (`relatorio_praca_mapas`) e a pagina (`censo_report`):
    os dois imprimem o mesmo raio e nao podem discordar.
    """
    metros_por_km = 1e3  # conversao de unidade, nao o raio do modelo (que este modulo nao redigita)
    if raio_m < metros_por_km:
        return f"{int(round(raio_m))} m"
    return f"{raio_m / metros_por_km:.1f}".replace(".", ",") + " km"

TITULO_MAPAS_CALOR_CIDADE = "Mapas de calor da cidade"
TITULO_PRESSAO_CONCORRENCIAL = "Pressão concorrencial"
TITULO_COMO_A_CIDADE_ESTA_INDO = "Como a cidade está indo"
TITULO_ONDE_CRESCER = "Onde crescer"

TEXTO_SEM_CRESCIMENTO = "Sem dado de crescimento para este município."
TEXTO_RENDA_MUNICIPAL = (
    "Atenção: nesta base a renda dos hexágonos é a do município inteiro, sem dado por setor. "
    "O filtro de renda não diferencia bairros e a lista sai ordenada só pelo índice de praça."
)

#: Colunas que a selecao le. Identificadores, nunca rotulo.
COL_RESIDUAL = "oferta_efetiva_disponivel"
COL_RENDA_DOMICILIAR = "renda_domiciliar"
COL_INDICE_PRACA = "indice_praca"
COL_DENSIDADE = "densidade_hab_km2"
COL_POPULACAO = "pop_leitura"
COL_SCORE_SOCIO = "score_setor_2022_calibrado"
COL_CRES_HEX_TAXA = "cres_hex_taxa"
COL_CRES_HEX_CLASSE = "cres_hex_classe"

#: Precedencia da populacao do hexagono. O SETOR vem primeiro, e isso e' DIFERENTE do funil
#: (`app.COLS_POP_LEITURA`, que comeca por `populacao_corte_hex`) de proposito: onde o join
#: censitario e' ruim, `populacao_corte_hex` carrega a populacao do MUNICIPIO INTEIRO repetida em
#: cada hexagono (DEC-054/058). Medido em Manaus: 2.063.689 habitantes nos 2.139 hexagonos, um
#: valor so'. Para o funil isso e' um gate conservador; para um mapa de densidade e' ficcao -- a
#: divisao por uma area quase igual virava faixas verticais, a "densidade em linhas" que o Juan
#: viu. Aqui a leitura e' por hexagono, entao a ordem comeca pelo dado de setor.
COLS_POPULACAO: tuple[str, ...] = (
    "pop_total_setor_2022",
    COL_POPULACAO,
    "populacao_corte_hex",
    "pop_total",
)

TEXTO_POP_MUNICIPAL = (
    "Atenção: nesta base a população dos hexágonos é a do município inteiro, sem dado por setor. "
    "O mapa de densidade não é publicado, porque dividiria o mesmo número pela área de cada célula."
)

_RAIO_TERRA_M = 6_371_008.8

#: Tipografia fora de latin-1 que o core font do fpdf2 troca por "?" em silencio (CLAUDE.md §2).
_TROCAS_PDF = {
    "—": "-",
    "–": "-",
    "•": "-",
    "→": "->",
    "…": "...",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "©": "(c)",
}


def texto_pdf(texto: Any) -> str:
    """Texto seguro para o core font: acento portugues passa, pontuacao tipografica vira ASCII.

    Existe porque parte do texto destas paginas vem PRONTO de outra camada (a frase do
    crescimento traz travessao) e sairia com "?" no meio, sem erro na geracao.
    """
    s = "" if texto is None else str(texto)
    for de, para in _TROCAS_PDF.items():
        s = s.replace(de, para)
    return s


def distancia_m(lat: float, lng: float, lats: Any, lngs: Any) -> np.ndarray:
    """Distancia haversine, em metros, de um ponto a um vetor de pontos."""
    la1 = np.radians(float(lat))
    lo1 = np.radians(float(lng))
    la2 = np.radians(pd.to_numeric(pd.Series(lats), errors="coerce").to_numpy(dtype="float64"))
    lo2 = np.radians(pd.to_numeric(pd.Series(lngs), errors="coerce").to_numpy(dtype="float64"))
    a = np.sin((la2 - la1) / 2.0) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2.0) ** 2
    return 2.0 * _RAIO_TERRA_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


# --------------------------------------------------------------------------- #
# Onde crescer                                                                #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SelecaoOndeCrescer:
    """Resultado da selecao. `hexagonos` ja vem ordenado, com a coluna `posicao` (1..n)."""

    hexagonos: pd.DataFrame
    mediana_renda: float | None
    n_elegiveis: int
    aviso: str | None
    #: `True` quando `mediana_renda` saiu ponderada pela populacao; `False` quando nao havia peso
    #: (nenhum hexagono com renda E populacao positiva) e ela caiu na mediana simples.
    mediana_ponderada: bool = False
    #: Cobertura do peso, para o PDF declarar a regua sem afirmar o que nao vale: hexagonos com
    #: renda > 0, quantos deles ficaram FORA do peso (populacao nula ou zero -- em geral os de
    #: `fonte_populacao_corte = 'total_municipal'`, que nao tem populacao de setor) e se a base
    #: trazia alguma coluna de populacao. Medido no pais (2026-10-16): 14.125 de 1.226.198
    #: hexagonos com renda, em 854 municipios (Porto Alegre 21 de 114, Rio 49 de 227), e eles NAO
    #: sao neutros (renda mediana 6.967 contra 3.917 em POA). Na base real nenhum deles entra na
    #: lista: sem populacao de setor tambem nao ha `score_setor_2022_calibrado`, logo nao ha
    #: `indice_praca` -- por isso o PDF declara a cobertura e NAO promete que "continuam elegiveis".
    n_com_renda: int = 0
    n_fora_do_peso: int = 0
    populacao_na_base: bool = False


def mediana_renda_da_cidade(
    renda: pd.Series,
    populacao: pd.Series | None,
) -> tuple[float | None, bool]:
    """Mediana da renda domiciliar da cidade PONDERADA PELA POPULACAO do hexagono (DEC-072).

    Por que ponderar: todo hexagono da cidade tem renda -- inclusive os rurais quase vazios, com
    frequencia de renda ALTA (chacaras, condominios de veraneio). Na mediana sem peso cada um
    vale o mesmo que um hexagono urbano de 10 mil habitantes e a regua sobe; com o rateio por
    area da DEC-072 a pagina "Onde crescer" esvaziava em 87 municipios (Trindade/GO,
    Pontalina/GO...). Ponderada, a mediana e' a renda do MORADOR mediano da cidade, nao a do
    hexagono mediano. A regra ficou quando a renda do PDF passou a ser a do card (`renda.hex`,
    PR #460, emenda 1 da DEC-072).

    Definicao (deterministica): entre os hexagonos com renda > 0 e populacao > 0, ordenados por
    renda crescente, e' o MENOR valor de renda cuja populacao acumulada atinge pelo menos 50% da
    populacao total desses hexagonos. Hexagono com populacao nula ou zero fica FORA do peso (nao
    entra no calculo; continua elegivel pela renda dele). Pesos iguais dao a mediana "inferior"
    (o elemento do meio por baixo), sem media dos dois centrais.

    Sem nenhum peso positivo cai na mediana SIMPLES dos hexagonos com renda e devolve
    `ponderada=False`, para o PDF declarar a regua. Sem renda: `(None, False)`.
    """
    r = pd.to_numeric(renda, errors="coerce")
    com_renda = r.notna() & (r > 0)
    if not com_renda.any():
        return None, False
    if populacao is not None:
        p = pd.to_numeric(pd.Series(populacao, index=r.index), errors="coerce")
        pesado = com_renda & p.notna() & (p > 0)
        if pesado.any():
            valores = r[pesado].to_numpy(dtype="float64")
            pesos = p[pesado].to_numpy(dtype="float64")
            ordem = np.argsort(valores, kind="mergesort")
            acumulado = np.cumsum(pesos[ordem])
            # `2*acumulado >= total` em vez de `acumulado >= total/2`: mesma regra, sem divisao.
            i = int(np.searchsorted(2.0 * acumulado, acumulado[-1], side="left"))
            return float(valores[ordem][i]), True
    return float(r[com_renda].median()), False


def selecionar_onde_crescer(
    hexes: pd.DataFrame,
    *,
    n: int = TOP_N_ONDE_CRESCER,
) -> SelecaoOndeCrescer:
    """Os `n` melhores hexagonos do municipio para crescer.

    Elegivel: `oferta_efetiva_disponivel > 0` E renda domiciliar >= mediana da renda domiciliar
    do proprio municipio PONDERADA PELA POPULACAO (`mediana_renda_da_cidade`, sobre os hexagonos
    COM renda; sem populacao cai na mediana simples e `mediana_ponderada` sai `False`). A MESMA
    selecao, com `n=10`, numera o Top 10 da camada de Dominio. Ordem: `indice_praca`
    decrescente, desempate por renda domiciliar decrescente e depois `hex_id` crescente --
    ordem total, entao o mesmo dado da' sempre a mesma lista.

    Com menos de `n` elegiveis devolve os que houver e diz por que no `aviso`.
    """
    necessarias = {"hex_id", COL_RESIDUAL, COL_RENDA_DOMICILIAR, COL_INDICE_PRACA}
    vazio = hexes.iloc[0:0].assign(posicao=pd.Series(dtype="int64")) if len(hexes.columns) else pd.DataFrame()
    if hexes is None or hexes.empty or not necessarias.issubset(hexes.columns):
        return SelecaoOndeCrescer(
            hexagonos=vazio,
            mediana_renda=None,
            n_elegiveis=0,
            aviso="Sem base de hexágonos com residual, renda e índice de praça para este município.",
        )

    renda = pd.to_numeric(hexes[COL_RENDA_DOMICILIAR], errors="coerce")
    residual = pd.to_numeric(hexes[COL_RESIDUAL], errors="coerce")
    indice = pd.to_numeric(hexes[COL_INDICE_PRACA], errors="coerce")
    populacao = (
        pd.to_numeric(hexes[COL_POPULACAO], errors="coerce")
        if COL_POPULACAO in hexes.columns
        else serie_populacao(hexes)
    )
    mediana, ponderada = mediana_renda_da_cidade(renda, populacao)
    com_renda = renda.notna() & (renda > 0)
    com_peso = com_renda & populacao.notna() & (populacao > 0)
    populacao_na_base = COL_POPULACAO in hexes.columns or any(c in hexes.columns for c in COLS_POPULACAO)

    if mediana is None:
        elegivel = pd.Series(False, index=hexes.index)
    else:
        elegivel = (residual > 0) & (renda >= mediana) & indice.notna()

    base = hexes.loc[elegivel].assign(
        _indice=indice[elegivel], _renda=renda[elegivel], _hex=hexes.loc[elegivel, "hex_id"].astype(str)
    )
    ordenado = base.sort_values(
        ["_indice", "_renda", "_hex"], ascending=[False, False, True], kind="mergesort"
    )
    top = ordenado.head(n).drop(columns=["_indice", "_renda", "_hex"]).reset_index(drop=True)
    top = top.assign(posicao=np.arange(1, len(top) + 1, dtype="int64"))

    n_eleg = int(elegivel.sum())
    aviso: str | None = None
    if renda_e_municipal(hexes):
        # Com a renda da cidade inteira repetida em cada hexagono, "acima da mediana" deixa
        # passar todos: a lista sai ordenada so' pelo indice, e o leitor precisa saber disso.
        aviso = TEXTO_RENDA_MUNICIPAL
    elif n_eleg < n:
        if mediana is None:
            aviso = "Nenhum hexágono do município tem renda domiciliar publicada."
        elif n_eleg == 0:
            # "So' 0 hexagono(s) ... a lista mostra os que existem" saia em Manaus, onde nao ha
            # nenhum: a frase prometia uma lista que nao existe.
            aviso = (
                "Nenhum hexágono do município tem, ao mesmo tempo, residual positivo e renda "
                "domiciliar igual ou acima da mediana da cidade."
            )
        elif n_eleg == 1:
            aviso = (
                "Só 1 hexágono do município tem residual positivo e renda domiciliar igual ou "
                "acima da mediana da cidade."
            )
        else:
            aviso = (
                f"Só {n_eleg} hexágonos do município têm residual positivo e renda domiciliar "
                "igual ou acima da mediana da cidade; a lista mostra os que existem."
            )
    return SelecaoOndeCrescer(
        hexagonos=top, mediana_renda=mediana, n_elegiveis=n_eleg, aviso=aviso,
        mediana_ponderada=ponderada,
        n_com_renda=int(com_renda.sum()),
        n_fora_do_peso=int((com_renda & ~com_peso).sum()),
        populacao_na_base=populacao_na_base,
    )


def texto_regua_onde_crescer(sel: SelecaoOndeCrescer) -> tuple[str, str | None]:
    """(nome da regua, nota de cobertura) para o texto do criterio no PDF (DEC-072).

    Uma funcao so' e testavel decide a frase, porque `mediana_ponderada=False` tem TRES causas
    diferentes e so' uma delas e' "a base nao traz populacao": (1) nao ha renda nenhuma
    (`mediana_renda is None`) -- ai nao ha regua a qualificar; (2) ha populacao, mas so' em
    hexagonos sem renda; (3) a base nao traz coluna de populacao. Com a regua ponderada, a nota
    declara quantos hexagonos com renda ficaram fora do peso: a regua nao os enxerga e eles nao
    sao um subconjunto neutro. A nota NAO diz que eles "continuam elegiveis" -- pela funcao
    continuam, mas na base real nao tem `indice_praca` e nunca entram na lista.
    """
    if sel.mediana_renda is None:
        return "mediana da cidade", None
    if sel.mediana_ponderada:
        nota = None
        if sel.n_fora_do_peso > 0:
            plural = sel.n_fora_do_peso > 1
            nota = (
                f"{sel.n_fora_do_peso} dos {sel.n_com_renda} hexágonos com renda "
                f"{'ficam' if plural else 'fica'} fora do peso da mediana: a base não traz "
                f"população própria para {'eles' if plural else 'ele'}, só o total do município."
            )
        return "mediana da cidade ponderada pela população", nota
    if not sel.populacao_na_base:
        return "mediana simples da cidade", "A base não traz população por hexágono, então a mediana não é ponderada."
    return (
        "mediana simples da cidade",
        "Nenhum hexágono com renda tem população própria na base, então a mediana não é ponderada.",
    )


def renda_e_municipal(hexes: pd.DataFrame) -> bool:
    """True quando a renda dos hexagonos nao diferencia bairros: e' a do municipio inteiro.

    Dois sinais, qualquer um basta: a maioria dos hexagonos com renda tem `renda_origem` =
    `renda_per_capita` (a coluna MUNICIPAL, ver `_serie_renda` no piloto), ou a renda domiciliar
    tem um valor so' na cidade toda. Acontece em artefato enriquecido anterior a DEC-045/054/055.
    """
    if hexes is None or hexes.empty or COL_RENDA_DOMICILIAR not in hexes.columns:
        return False
    renda = pd.to_numeric(hexes[COL_RENDA_DOMICILIAR], errors="coerce")
    com_renda = renda.notna() & (renda > 0)
    if com_renda.sum() < 2:
        return False
    if "renda_origem" in hexes.columns:
        origem = hexes.loc[com_renda, "renda_origem"].astype("string")
        if float((origem == "renda_per_capita").mean()) >= 0.5:
            return True
    return int(renda[com_renda].round(0).nunique()) <= 1


# --------------------------------------------------------------------------- #
# Pressao concorrencial                                                       #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PressaoNoPonto:
    """Quantos discos de influencia cobrem o ponto, e de quem."""

    raio_m: float
    n_concorrentes_sobre_ponto: int
    n_ultra_sobre_ponto: int
    redes_sobre_ponto: list[tuple[str, int]] = field(default_factory=list)
    n_independentes_sobre_ponto: int = 0
    dist_mais_proxima_m: float | None = None
    nome_mais_proxima: str | None = None

    @property
    def n_raios_sobre_ponto(self) -> int:
        return self.n_concorrentes_sobre_ponto + self.n_ultra_sobre_ponto


def _pontos_validos(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty or not {"lat", "lng"}.issubset(df.columns):
        return pd.DataFrame(columns=["lat", "lng"])
    lat = pd.to_numeric(df["lat"], errors="coerce")
    lng = pd.to_numeric(df["lng"], errors="coerce")
    return df.loc[lat.notna() & lng.notna()]


def _contar_redes(concorrentes: pd.DataFrame) -> tuple[list[tuple[str, int]], int]:
    """(redes em ordem total, n de independentes). Independente = sem `rede` (DEC-046)."""
    if concorrentes.empty:
        return [], 0
    rede = concorrentes["rede"] if "rede" in concorrentes.columns else pd.Series(pd.NA, index=concorrentes.index)
    rede = rede.astype("string").str.strip()
    n_indep = int((rede.isna() | (rede == "")).sum())
    contagem = rede[rede.notna() & (rede != "")].value_counts()
    # Ordem total: mais unidades primeiro, depois nome -- o PDF nao pode trocar a ordem
    # entre duas geracoes do mesmo dado.
    redes = sorted(((str(k), int(v)) for k, v in contagem.items()), key=lambda kv: (-kv[1], kv[0]))
    return redes, n_indep


def pressao_sobre_ponto(
    lat: float,
    lng: float,
    concorrentes: pd.DataFrame | None,
    ultra: pd.DataFrame | None,
    *,
    raio_m: float = RAIO_PRESSAO_PONTO_M,
) -> PressaoNoPonto:
    """Conta os discos de `raio_m` que alcancam o ponto.

    O raio e' o de LEITURA do Relatorio Pontual (`RAIO_PRESSAO_PONTO_M`, 750 m): o mesmo que
    `render_pressao_raios` desenha em volta de cada academia. Nao e' o raio do modelo de mercado
    (`RAIO_INFLUENCIA_M`, 1 km, DEC-051), que segue descontando o residual. Um disco alcanca o
    ponto quando o centro dele esta a ate `raio_m` do ponto.
    """
    conc = _pontos_validos(concorrentes)
    ult = _pontos_validos(ultra)

    d_conc = distancia_m(lat, lng, conc["lat"], conc["lng"]) if len(conc) else np.array([])
    d_ult = distancia_m(lat, lng, ult["lat"], ult["lng"]) if len(ult) else np.array([])

    sobre = conc.loc[d_conc <= raio_m] if len(conc) else conc
    redes, n_indep = _contar_redes(sobre)

    dist_min: float | None = None
    nome_min: str | None = None
    if len(conc):
        i = int(np.nanargmin(d_conc))
        dist_min = float(d_conc[i])
        linha = conc.iloc[i]
        for coluna in ("rede", "nome"):
            valor = linha.get(coluna) if coluna in conc.columns else None
            if valor is not None and not pd.isna(valor) and str(valor).strip():
                nome_min = str(valor).strip()
                break
        if nome_min is None:
            nome_min = "Academia independente"

    return PressaoNoPonto(
        raio_m=float(raio_m),
        n_concorrentes_sobre_ponto=int(len(sobre)),
        n_ultra_sobre_ponto=int((d_ult <= raio_m).sum()) if len(ult) else 0,
        redes_sobre_ponto=redes,
        n_independentes_sobre_ponto=n_indep,
        dist_mais_proxima_m=dist_min,
        nome_mais_proxima=nome_min,
    )


# --------------------------------------------------------------------------- #
# Como a cidade esta indo                                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CrescimentoCidade:
    """Linhas (rotulo, valor) prontas para a pagina e a frase de leitura."""

    disponivel: bool
    linhas: list[tuple[str, str]]
    frase: str
    #: rotulo -> subtitulo miudo embaixo dele (hoje so' o saldo: "abertas - fechadas").
    subtitulos: dict[str, str] = field(default_factory=dict)


def _fmt_pct(v: Any) -> str | None:
    x = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
    return None if pd.isna(x) else f"{float(x):+.1f}%".replace(".", ",")


def _fmt_int(v: Any) -> str | None:
    x = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
    return None if pd.isna(x) else f"{int(round(float(x))):,}".replace(",", ".")


# Confiabilidade da leitura de emprego: quantos vinculos formais sustentam a tendencia e a
# variacao do CAGED (cortes da base: alta >= 20 mil, media >= 5 mil, baixa >= 1 mil). Desde
# 2026-10-21 (Juan: "nao entendi por que manter") so' vira linha quando NAO e' alta -- como aviso
# de que poucas contratacoes mexem muito na variacao. Alta nao muda a leitura, entao nao aparece.
_LEITURA_FRAGIL = {
    "media": "leitura pouco firme",
    "baixa": "leitura frágil",
    "muito_baixa": "leitura muito frágil",
}
ROTULO_POUCOS_EMPREGOS = "Atenção: poucos empregos formais"


def referencias_da_uf(crescimento: pd.DataFrame | None, uf: str | None) -> dict[str, float]:
    """Medianas dos municipios da UF para comparar o salario de contratacao e a sua variacao.

    A variacao do emprego ja' chega com a mediana da UF (`cres_uf_mediana`); o salario saia solto
    e o leitor nao tinha como saber se era bom (Juan, 2026-10-20). O saldo de empresas por mil
    habitantes saiu da pagina em 2026-10-21. Vazio sem base ou sem UF.
    """
    if crescimento is None or crescimento.empty or not uf or "cres_chave_nome" not in crescimento.columns:
        return {}
    da_uf = crescimento.loc[crescimento["cres_chave_nome"].astype(str).str.split("|").str[0] == str(uf).upper()]
    saida: dict[str, float] = {}
    for chave, coluna in (("salario", "cres_salario"), ("salario_var", "cres_salario_var")):
        if coluna in da_uf.columns:
            v = pd.to_numeric(da_uf[coluna], errors="coerce").dropna()
            if not v.empty:
                saida[chave] = float(v.median())
    return saida


def _periodo_da_dimensao(cres_dims: Any, nome: str) -> str | None:
    """`"...;Empresas:110.0:/mil:99:2020–2025;..."` -> `"2020-2025"` (5o campo da dimensao)."""
    for parte in str(cres_dims or "").split(";"):
        campos = parte.split(":")
        if len(campos) >= 5 and campos[0].strip() == nome:
            return campos[4].strip().replace("–", "-").replace("→", "-")
    return None


def resumir_crescimento(
    municipio: Mapping[str, Any] | None,
    *,
    uf: str | None = None,
    frase: str | None = None,
    rotulo_tendencia: Mapping[str, str] | None = None,
    referencias: Mapping[str, float] | None = None,
    com_veredito: bool = True,
) -> CrescimentoCidade:
    """Transforma a linha municipal de crescimento nas linhas da pagina.

    `municipio` e' o dict com as colunas `cres_*` e `v_frase` do municipio (ou `None`). Sem
    tendencia E sem veredito, a pagina diz que nao ha dado -- nunca some.

    `com_veredito=False` (Relatorio Municipal do Brasil, DEC-077): o `v_frase` ("E' praca para
    entrar") nao vira a frase da pagina nem conta como dado -- a resposta de onde expandir e' so'
    a recomendacao unica. A frase passada por `frase` segue valendo.
    """
    m = dict(municipio or {})

    def _v(chave: str) -> Any:
        valor = m.get(chave)
        if valor is None:
            return None
        try:
            if pd.isna(valor):
                return None
        except (TypeError, ValueError):
            pass
        return valor

    tend = _v("cres_tendencia")
    veredito = _v("v_frase") if com_veredito else None
    if tend is None and not veredito:
        return CrescimentoCidade(disponivel=False, linhas=[], frase=TEXTO_SEM_CRESCIMENTO)

    linhas: list[tuple[str, str]] = []
    if tend is not None:
        linhas.append(("Tendência do emprego formal", (rotulo_tendencia or {}).get(str(tend), str(tend))))
    emp = _fmt_pct(_v("cres_emp_pct"))
    if emp is not None:
        med = _fmt_pct(_v("cres_uf_mediana"))
        ref = f" (mediana {uf or 'da UF'}: {med})" if med is not None else ""
        linhas.append(("Variação do emprego desde dez/2022", f"{emp}{ref}"))
    refs_uf = dict(referencias or {})
    sigla = uf or "da UF"
    subtitulos: dict[str, str] = {}
    saldo = _fmt_int(_v("cres_saldo_empresas"))
    if saldo is not None:
        # Saldo = aberturas MENOS fechamentos (ha municipio com saldo negativo na base). O periodo
        # vem da propria dimensao. (O saldo por mil habitantes contra a mediana da UF saiu em
        # 2026-10-21, a pedido do Juan.)
        periodo = _periodo_da_dimensao(_v("cres_dims"), "Empresas")
        rotulo_saldo = f"Saldo de empresas {periodo}" if periodo else "Saldo de empresas"
        linhas.append((rotulo_saldo, saldo))
        # As duas parcelas, quando o artefato as traz (desde 2026-10-20): o saldo e' o resultado.
        abertas = _fmt_int(_v("cres_aberturas_empresas"))
        fechadas = _fmt_int(_v("cres_fechamentos_empresas"))
        if abertas is not None and fechadas is not None:
            subtitulos[texto_pdf(rotulo_saldo)] = texto_pdf(f"{abertas} abertas - {fechadas} fechadas")
    # Salario: UMA linha, com a variacao de 12 meses do lado (Juan, 2026-10-21) e a regua da UF
    # embaixo -- a mediana do salario e a da variacao, para o leitor ver se e' muito ou pouco.
    # Antes "Mediana de admissao SP" era uma linha solta e parecia um segundo salario.
    sal = _fmt_int(_v("cres_salario"))
    if sal is not None:
        rot = "Salário de contratação"
        var = _fmt_pct(_v("cres_salario_var"))
        linhas.append((rot, f"R$ {sal}" + (f" ({var} em 12 meses)" if var else "")))
        partes: list[str] = []
        if "salario" in refs_uf:
            rel = round(100.0 * (float(_v("cres_salario")) / float(refs_uf["salario"]) - 1.0))
            lado = "perto dela" if abs(rel) < 5 else f"{abs(rel)}% {'acima' if rel > 0 else 'abaixo'}"
            partes.append(f"mediana {sigla}: R$ {_fmt_int(refs_uf['salario'])} ({lado})")
        if var and "salario_var" in refs_uf:
            partes.append(f"variação na mediana: {_fmt_pct(refs_uf['salario_var'])}")
        if partes:
            subtitulos[texto_pdf(rot)] = texto_pdf("; ".join(partes))
    setor = _v("cres_setor")
    if setor:
        linhas.append(("Setor que mais abre empresas", str(setor)))
    conf = _v("cres_confiab")
    if conf and str(conf) in _LEITURA_FRAGIL:
        vinc = pd.to_numeric(pd.Series([_v("cres_vinculos")]), errors="coerce").iloc[0]
        if pd.isna(vinc):
            valor = _LEITURA_FRAGIL[str(conf)]
        else:
            v = float(vinc)
            qtd = (f"{v / 1e6:.1f} mi" if v >= 1e6 else f"{v / 1e3:.0f} mil" if v >= 1e3 else f"{v:.0f}")
            valor = f"{qtd.replace('.', ',')} vínculos ({_LEITURA_FRAGIL[str(conf)]})"
        linhas.append((ROTULO_POUCOS_EMPREGOS, valor))

    return CrescimentoCidade(
        disponivel=True,
        linhas=[(texto_pdf(r), texto_pdf(v)) for r, v in linhas],
        frase=texto_pdf(frase if frase else (veredito or "")),
        subtitulos=subtitulos,
    )


def linha_crescimento_municipal(
    crescimento: pd.DataFrame | None,
    *,
    uf: str,
    cod_municipio: str | None,
    nome_municipio: str | None,
) -> dict[str, Any] | None:
    """A linha de `crescimento_municipal.parquet` do municipio, como dict (`None` se nao houver).

    Casa por `cod6` (codigo IBGE sem o DV) e, sem codigo ou sem casamento, por
    `cres_chave_nome` = `UF|NOME` normalizado -- os dois joins de
    `docs/camada_crescimento_municipal.md`, na mesma ordem do piloto (`_juntar_crescimento`).
    """
    if crescimento is None or crescimento.empty:
        return None
    alvo = crescimento.iloc[0:0]
    cod = str(cod_municipio or "").strip().split(".")[0]
    if cod and "cod6" in crescimento.columns:
        alvo = crescimento.loc[crescimento["cod6"].astype(str).str.split(".").str[0].str[:6] == cod[:6]]
    if alvo.empty and nome_municipio and "cres_chave_nome" in crescimento.columns:
        nome = unicodedata.normalize("NFKD", str(nome_municipio)).encode("ascii", "ignore").decode("ascii")
        chave = f"{str(uf).strip().upper()}|{' '.join(nome.upper().split())}"
        alvo = crescimento.loc[crescimento["cres_chave_nome"].astype(str) == chave]
    if alvo.empty:
        return None
    return dict(alvo.iloc[0].to_dict())


# --------------------------------------------------------------------------- #
# Hexagono do ponto na camada de crescimento (pontual)                        #
# --------------------------------------------------------------------------- #
_ROTULO_CLASSE_HEX = {"Em alta": "Em alta", "Estavel": "Estável", "Sem obra nova": "Sem obra nova"}

#: Acima disto a taxa e' de hexagono quase vazio em 2016 (o maximo medido passa de 498.000%):
#: escrever o numero cru poria um outlier no lugar de destaque.
TAXA_HEX_TETO = 500.0

TEXTO_SEM_CRESCIMENTO_HEX = (
    "Sem medição de obra nova neste hexágono. A camada de satélite cobre 12 UFs: "
    "BA, CE, DF, ES, GO, MG, PE, PR, RJ, RS, SC e SP."
)


@dataclass(frozen=True)
class CrescimentoDoHexagono:
    """Obra nova (area construida 2016-2023) no hexagono do ponto, contra a cidade."""

    disponivel: bool
    taxa_texto: str | None
    classe: str | None
    mediana_cidade_texto: str | None
    frase: str


def _texto_taxa_hex(v: float) -> str:
    if v > TAXA_HEX_TETO:
        return f"acima de +{int(TAXA_HEX_TETO)}%"
    return f"{v:+.1f}%".replace(".", ",")


def crescimento_do_hexagono(
    hex_do_ponto: Mapping[str, Any] | None,
    hexes_cidade: pd.DataFrame | None = None,
) -> CrescimentoDoHexagono:
    """Le `cres_hex_taxa`/`cres_hex_classe` do hexagono do ponto e compara com a cidade.

    A mediana e' so' dos hexagonos da cidade COM medicao. Fora das 12 UFs cobertas nao ha
    nenhum, e a pagina diz isso em vez de sumir com o bloco.
    """
    linha = dict(hex_do_ponto or {})
    taxa = pd.to_numeric(pd.Series([linha.get(COL_CRES_HEX_TAXA)]), errors="coerce").iloc[0]
    bruta = linha.get(COL_CRES_HEX_CLASSE)
    classe = None
    if bruta is not None and not pd.isna(bruta) and str(bruta).strip():
        classe = _ROTULO_CLASSE_HEX.get(str(bruta), str(bruta))
    if pd.isna(taxa):
        return CrescimentoDoHexagono(
            disponivel=False, taxa_texto=None, classe=classe, mediana_cidade_texto=None,
            frase=TEXTO_SEM_CRESCIMENTO_HEX,
        )

    taxa_txt = _texto_taxa_hex(float(taxa))
    mediana_txt: str | None = None
    comparacao: str | None = None
    if hexes_cidade is not None and COL_CRES_HEX_TAXA in hexes_cidade.columns:
        serie = pd.to_numeric(hexes_cidade[COL_CRES_HEX_TAXA], errors="coerce").dropna()
        if len(serie):
            mediana = float(serie.median())
            mediana_txt = _texto_taxa_hex(mediana)
            if float(taxa) > mediana:
                comparacao = "acima da mediana da cidade"
            elif float(taxa) < mediana:
                comparacao = "abaixo da mediana da cidade"
            else:
                comparacao = "igual à mediana da cidade"

    frase = f"A área construída deste hexágono variou {taxa_txt} entre 2016 e 2023"
    frase += f", {comparacao} ({mediana_txt})." if comparacao else "."
    return CrescimentoDoHexagono(
        disponivel=True, taxa_texto=taxa_txt, classe=classe, mediana_cidade_texto=mediana_txt, frase=frase,
    )


# --------------------------------------------------------------------------- #
# Pressao concorrencial da cidade inteira (municipal)                         #
# --------------------------------------------------------------------------- #
#: A partir de quantos discos sobrepostos o hexagono conta como "disputado" na pagina municipal.
#: Com 3 a sobreposicao deixa de ser so' a vizinhanca de duas academias.
N_DISCOS_DISPUTA = 3


@dataclass(frozen=True)
class PressaoNaCidade:
    """Academias do municipio e quanto da cidade os discos delas cobrem."""

    raio_m: float
    n_concorrentes: int
    n_ultra: int
    n_independentes: int = 0
    redes: list[tuple[str, int]] = field(default_factory=list)
    n_hexagonos: int = 0
    n_hex_cobertos: int = 0
    n_hex_disputados: int = 0
    max_discos_no_hex: int = 0

    @property
    def pct_coberto(self) -> float | None:
        return 100.0 * self.n_hex_cobertos / self.n_hexagonos if self.n_hexagonos else None

    @property
    def pct_disputado(self) -> float | None:
        return 100.0 * self.n_hex_disputados / self.n_hexagonos if self.n_hexagonos else None


def centros_hex(hex_ids: Any) -> tuple[np.ndarray, np.ndarray]:
    """(lats, lngs) dos centros H3; hexagono invalido fica NaN."""
    import h3

    ids = [str(h) for h in hex_ids]
    lats = np.full(len(ids), np.nan)
    lngs = np.full(len(ids), np.nan)
    for i, h in enumerate(ids):
        try:
            lats[i], lngs[i] = h3.cell_to_latlng(h)
        except Exception:  # noqa: BLE001 - hexagono invalido fica sem centro e nao conta
            continue
    return lats, lngs


def discos_por_hexagono(
    hexes: pd.DataFrame | None,
    pontos: pd.DataFrame | None,
    *,
    raio_m: float = RAIO_INFLUENCIA_M,
    bloco: int = 256,
) -> np.ndarray:
    """Quantos discos de `raio_m` alcancam o CENTRO de cada hexagono, na ordem de `hexes`.

    Centro, e nao a area da celula: e' a leitura do PDF, nao a camada
    `pressao_concorrencial_1km` (que cruza o disco com a celula inteira). Em blocos de
    academias para a matriz hexagono x academia ficar em poucos MB numa capital.
    """
    if hexes is None or hexes.empty or "hex_id" not in hexes.columns:
        return np.zeros(0, dtype="int64")
    contagem = np.zeros(len(hexes), dtype="int64")
    validos = _pontos_validos(pontos)
    if validos.empty:
        return contagem
    h_lat, h_lng = centros_hex(hexes["hex_id"])
    la1 = np.radians(h_lat)[:, None]
    lo1 = np.radians(h_lng)[:, None]
    p_lat = np.radians(pd.to_numeric(validos["lat"], errors="coerce").to_numpy(dtype="float64"))
    p_lng = np.radians(pd.to_numeric(validos["lng"], errors="coerce").to_numpy(dtype="float64"))
    for ini in range(0, len(p_lat), bloco):
        la2 = p_lat[None, ini : ini + bloco]
        lo2 = p_lng[None, ini : ini + bloco]
        a = np.sin((la2 - la1) / 2.0) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2.0) ** 2
        with np.errstate(invalid="ignore"):
            d = 2.0 * _RAIO_TERRA_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
            contagem += (d <= raio_m).sum(axis=1)
    return contagem


def pressao_na_cidade(
    hexes: pd.DataFrame | None,
    concorrentes: pd.DataFrame | None,
    ultra: pd.DataFrame | None,
    *,
    raio_m: float = RAIO_INFLUENCIA_M,
) -> PressaoNaCidade:
    """Resumo da pagina municipal: quem esta na cidade e quanto dela os discos cobrem.

    `concorrentes` e `ultra` chegam JA recortados ao municipio (o recorte do slide
    Concorrentes); a cobertura soma os dois, como o mapa desenha.
    """
    conc = _pontos_validos(concorrentes)
    ult = _pontos_validos(ultra)
    redes, n_indep = _contar_redes(conc)
    partes = [f[["lat", "lng"]] for f in (conc, ult) if not f.empty]
    todos = pd.concat(partes, ignore_index=True) if partes else None
    discos = discos_por_hexagono(hexes, todos, raio_m=raio_m)
    return PressaoNaCidade(
        raio_m=float(raio_m),
        n_concorrentes=int(len(conc)),
        n_ultra=int(len(ult)),
        n_independentes=n_indep,
        redes=redes,
        n_hexagonos=int(len(discos)),
        n_hex_cobertos=int((discos >= 1).sum()),
        n_hex_disputados=int((discos >= N_DISCOS_DISPUTA).sum()),
        max_discos_no_hex=int(discos.max()) if len(discos) else 0,
    )


# --------------------------------------------------------------------------- #
# Hexagonos da cidade (municipal)                                             #
# --------------------------------------------------------------------------- #
def serie_populacao(hexes: pd.DataFrame) -> pd.Series:
    """Populacao de leitura do hexagono, pela primeira coluna de `COLS_POPULACAO` que existir."""
    for coluna in COLS_POPULACAO:
        if coluna in hexes.columns:
            return pd.to_numeric(hexes[coluna], errors="coerce")
    return pd.Series(np.nan, index=hexes.index, dtype="float64")


def populacao_e_municipal(hexes: pd.DataFrame | None) -> bool:
    """True quando a populacao dos hexagonos nao diferencia bairros: e' a do municipio inteiro.

    Mesmo molde de `renda_e_municipal`: um valor so' na cidade toda (ou `fonte_populacao_corte`
    dizendo `total_municipal` na maioria) significa join censitario ruim (DEC-054/058).
    """
    if hexes is None or hexes.empty:
        return False
    if "fonte_populacao_corte" in hexes.columns and COL_POPULACAO in hexes.columns:
        fonte = hexes["fonte_populacao_corte"].astype("string")
        if float((fonte == "total_municipal").mean()) >= 0.5 and _populacao_sem_setor(hexes):
            return True
    return _populacao_sem_setor(hexes) and _valor_unico(hexes.get(COL_POPULACAO))


def _populacao_sem_setor(hexes: pd.DataFrame) -> bool:
    """A base nao traz populacao POR SETOR utilizavel (coluna ausente ou com um valor so')."""
    if "pop_total_setor_2022" not in hexes.columns:
        return True
    return _valor_unico(hexes["pop_total_setor_2022"])


def _valor_unico(serie: Any) -> bool:
    if serie is None:
        return True
    valores = pd.to_numeric(pd.Series(serie), errors="coerce")
    validos = valores[valores.notna() & (valores > 0)]
    if len(validos) < 2:
        return True
    return int(validos.round(0).nunique()) <= 1


def preparar_hexes_da_cidade(
    df_muni: pd.DataFrame,
    renda_domiciliar_por_hex: Mapping[str, Any] | None,
) -> pd.DataFrame:
    """Frame NOVO com as tres colunas que as paginas da cidade leem.

    - `renda_domiciliar`: do mapa `hex_id -> renda` que o relatorio municipal ja carrega para a
      tabela de regioes (`renda.hex.renda_domiciliar_por_hex`). Sem o mapa a coluna fica nula e a
      selecao diz que nao ha renda publicada -- cair na per capita trocaria a escala em silencio.
    - `densidade_hab_km2`: populacao de leitura sobre a area da CELULA. A coluna
      `densidade_pop_setor_hab_km2` e' do setor e repetiria o numero de um setor denso num
      hexagono quase vazio.
    - `indice_praca`: DEC-041, pela mesma funcao da camada 5 do funil (`praca_indice`).
    """
    import h3

    from motor_expansao.dashboard import praca_indice

    out = df_muni.copy()
    if out.empty or "hex_id" not in out.columns:
        return out.assign(**{COL_RENDA_DOMICILIAR: np.nan, COL_DENSIDADE: np.nan, COL_INDICE_PRACA: np.nan})
    ids = out["hex_id"].astype(str)
    mapa = dict(renda_domiciliar_por_hex or {})
    out[COL_RENDA_DOMICILIAR] = pd.to_numeric(ids.map(mapa), errors="coerce") if mapa else np.nan

    def _area(h: str) -> float:
        try:
            return float(h3.cell_area(h, unit="km^2"))
        except Exception:  # noqa: BLE001
            return float("nan")

    out[COL_POPULACAO] = serie_populacao(out)
    out[COL_DENSIDADE] = out[COL_POPULACAO] / ids.map(_area)

    if COL_SCORE_SOCIO in out.columns and COL_RESIDUAL in out.columns:
        nota_dem = praca_indice.nota_demanda(out[COL_RESIDUAL]).to_numpy()
        nota_socio = pd.to_numeric(out[COL_SCORE_SOCIO], errors="coerce").to_numpy()
        out[COL_INDICE_PRACA] = praca_indice.indice_praca(nota_socio, nota_dem).to_numpy()
    else:
        out[COL_INDICE_PRACA] = np.nan
    return out


# --------------------------------------------------------------------------- #
# Pacotes                                                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PracaDoPonto:
    """Paginas da praca no Relatorio Pontual. `mapas` = chave -> PNG."""

    municipio: str
    uf: str | None
    pressao: PressaoNoPonto
    crescimento: CrescimentoCidade
    crescimento_hex: CrescimentoDoHexagono
    mapas: dict[str, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class PracaDaCidade:
    """Paginas da praca no Relatorio Municipal. `mapas` = chave -> PNG."""

    municipio: str
    uf: str | None
    onde_crescer: SelecaoOndeCrescer
    pressao: PressaoNaCidade
    crescimento: CrescimentoCidade
    mapas: dict[str, bytes] = field(default_factory=dict)
    n_hexagonos_cidade: int = 0
    #: As duas listas da pagina "Onde crescer" (2026-10-20): maior residual e maior score
    #: socioeconomico, 5 hexagonos cada (`top_por_coluna`).
    top_residual: pd.DataFrame = field(default_factory=pd.DataFrame)
    top_socio: pd.DataFrame = field(default_factory=pd.DataFrame)
    renda_municipal: bool = False
    populacao_municipal: bool = False
    #: Recomendacao unica do Brasil (DEC-077, `motor_expansao.recomendacao.Recomendacao`): com
    #: ela, "Onde crescer" mostra Mata Virgem e Premium em vez das listas por coluna. `None` =
    #: pais sem regua (Argentina), e a pagina segue com `top_residual`/`top_socio`.
    recomendacao: Any = None
    #: `hex_id` -> nome da regiao recomendada (`recomendacao.rotulos_das_regioes`).
    rotulos_recomendacao: dict[str, str] = field(default_factory=dict)


def top_por_coluna(
    hexes: pd.DataFrame | None, coluna: str, n: int = 5, *, desempate: str | None = None,
) -> pd.DataFrame:
    """Os `n` hexagonos com maior `coluna` (valor ABSOLUTO, sem filtro de renda), com `posicao`.

    Juan (2026-10-20) pediu as duas leituras separadas na pagina "Onde crescer": onde sobra mais
    gente sem academia (residual) e onde a regiao e' mais forte socioeconomicamente (score). Uma
    regua so', que misturava as duas, escondia de qual lado vinha cada escolhido.

    `desempate`: coluna que ordena os EMPATADOS (desc). O score satura em 100 em muitos hexagonos
    de capital (Sao Paulo), e sem desempate o top 5 saia pela ordem do id -- com residual 0.
    """
    if hexes is None or hexes.empty or coluna not in hexes.columns:
        return pd.DataFrame()
    v = pd.to_numeric(hexes[coluna], errors="coerce")
    out = hexes.loc[v.notna()].assign(_v=v[v.notna()])
    d = (pd.to_numeric(out[desempate], errors="coerce").fillna(float("-inf"))
         if desempate and desempate in out.columns else pd.Series(0.0, index=out.index))
    out = out.assign(_d=d).sort_values(["_v", "_d", "hex_id"], ascending=[False, False, True])
    out = out.drop(columns=["_v", "_d"]).head(n).reset_index(drop=True)
    out["posicao"] = range(1, len(out) + 1)
    return out


COL_SOCIO_SEM_TETO = "_socio_sem_teto"


def com_socio_sem_teto(hexes: pd.DataFrame | None) -> pd.DataFrame | None:
    """`hexes` + a mesma mistura do score (60% renda, 40% populacao, DEC-040) SEM o teto de 100.

    So' para DESEMPATAR a lista "Maior socioeconomico" (Juan, 2026-10-20): em Sao Paulo varios
    hexagonos batem 100 -- a renda per capita satura na ancora maxima -- e o desempate pelo
    residual punha Consolacao, a de melhores numeros, em 5o. Mesmas ancoras do perfil do pais,
    sem `clip`; nao substitui o score (que segue sendo o criterio e o numero publicado).
    """
    if hexes is None or hexes.empty:
        return hexes
    from motor_expansao.perfil import resolver_perfil

    anc = resolver_perfil().ancoras()
    renda_col = next((c for c in ("renda_per_capita_setor_2022_calibrada", "renda_per_capita") if c in hexes.columns), None)
    if renda_col is None or COL_POPULACAO not in hexes.columns:
        return hexes.assign(**{COL_SOCIO_SEM_TETO: np.nan})
    renda = pd.to_numeric(hexes[renda_col], errors="coerce")
    pop = pd.to_numeric(hexes[COL_POPULACAO], errors="coerce").clip(lower=1.0)
    nota_renda = 100.0 * (renda - anc.renda_min) / (anc.renda_max - anc.renda_min)
    nota_pop = 100.0 * (np.log(pop) - np.log(anc.pop_min)) / (np.log(anc.pop_max) - np.log(anc.pop_min))
    return hexes.assign(**{COL_SOCIO_SEM_TETO: 0.60 * nota_renda + 0.40 * nota_pop})


def quebras_por_quantil(valores: Any, n_classes: int = 5) -> list[float]:
    """Limites SUPERIORES de `n_classes` faixas por quantil, so' sobre valores POSITIVOS.

    Zero e ausencia ficam fora do calculo e vao para a cor de "sem dado" no mapa: numa
    variavel com muito zero (densidade em hexagono vazio), incluir o zero puxaria a primeira
    faixa para zero e poria o vazio no meio da escala. Duplicatas colapsam -- cidade pequena
    pode ter menos faixas que `n_classes`.
    """
    s = pd.to_numeric(pd.Series(valores), errors="coerce")
    s = s[s.notna() & (s > 0)]
    if s.empty:
        return []
    qs = np.linspace(0.0, 1.0, n_classes + 1)[1:]
    # `lower`: o corte e' sempre um valor OBSERVADO na cidade -- a legenda nao mostra uma renda
    # interpolada que nenhum hexagono tem.
    limites = sorted({float(v) for v in s.quantile(qs, interpolation="lower").to_numpy()})
    return limites
