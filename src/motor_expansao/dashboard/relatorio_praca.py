"""Leitura da PRACA: o que o motor sabe da cidade, alem do raio de 1 km do ponto.

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
domiciliar na metade de cima da propria cidade; entre os elegiveis a ordem e' o `indice_praca`
da DEC-041 (70% socioeconomico, 30% demanda). E' uma leitura do PDF: o funil, `/api/hexagonos`
e o `indice_praca` nao mudam.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from motor_expansao.pipelines.pressao_concorrencial_1km import RAIO_INFLUENCIA_M

TOP_N_ONDE_CRESCER = 5

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

#: Precedencia da populacao do hexagono: a MESMA de `app.COLS_POP_LEITURA`. A base do bot
#: (camada de mercado) nao tem `pop_leitura`; a do motor so' a tem depois de `_derivar`.
COLS_POPULACAO: tuple[str, ...] = (
    COL_POPULACAO,
    "populacao_corte_hex",
    "pop_total_setor_2022",
    "pop_total",
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


def selecionar_onde_crescer(
    hexes: pd.DataFrame,
    *,
    n: int = TOP_N_ONDE_CRESCER,
) -> SelecaoOndeCrescer:
    """Os `n` melhores hexagonos do municipio para crescer.

    Elegivel: `oferta_efetiva_disponivel > 0` E renda domiciliar >= mediana da renda domiciliar
    do proprio municipio (mediana sobre os hexagonos COM renda). Ordem: `indice_praca`
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
    com_renda = renda[renda.notna() & (renda > 0)]
    mediana = float(com_renda.median()) if len(com_renda) else None

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
        else:
            aviso = (
                f"Só {n_eleg} hexágono(s) do município têm residual positivo e renda domiciliar "
                "na metade de cima da cidade; a lista mostra os que existem."
            )
    return SelecaoOndeCrescer(hexagonos=top, mediana_renda=mediana, n_elegiveis=n_eleg, aviso=aviso)


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
    raio_m: float = RAIO_INFLUENCIA_M,
) -> PressaoNoPonto:
    """Conta os discos de `raio_m` que alcancam o ponto.

    O raio e' o de influencia do modelo de mercado desde a DEC-051 (`RAIO_INFLUENCIA_M`, 1 km):
    o mesmo que desconta o residual e o mesmo que a camada de pressao do mapa desenha. Um disco
    alcanca o ponto quando o centro dele esta a ate `raio_m` do ponto.
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


def _fmt_pct(v: Any) -> str | None:
    x = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
    return None if pd.isna(x) else f"{float(x):+.1f}%".replace(".", ",")


def _fmt_int(v: Any) -> str | None:
    x = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
    return None if pd.isna(x) else f"{int(round(float(x))):,}".replace(",", ".")


_ROTULO_CONFIABILIDADE = {
    "alta": "Alta",
    "media": "Média",
    "baixa": "Baixa",
    "muito_baixa": "Muito baixa",
}


def resumir_crescimento(
    municipio: Mapping[str, Any] | None,
    *,
    uf: str | None = None,
    frase: str | None = None,
    rotulo_tendencia: Mapping[str, str] | None = None,
) -> CrescimentoCidade:
    """Transforma a linha municipal de crescimento nas linhas da pagina.

    `municipio` e' o dict com as colunas `cres_*` e `v_frase` do municipio (ou `None`). Sem
    tendencia E sem veredito, a pagina diz que nao ha dado -- nunca some.
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
    veredito = _v("v_frase")
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
    saldo = _fmt_int(_v("cres_saldo_empresas"))
    if saldo is not None:
        linhas.append(("Saldo de empresas abertas", saldo))
    sal = _fmt_int(_v("cres_salario"))
    if sal is not None:
        var = _fmt_pct(_v("cres_salario_var"))
        linhas.append(("Salário de admissão", f"R$ {sal}" + (f" ({var} no ano)" if var else "")))
    setor = _v("cres_setor")
    if setor:
        linhas.append(("Setor que mais abre empresas", str(setor)))
    conf = _v("cres_confiab")
    if conf:
        linhas.append(("Confiabilidade da medição", _ROTULO_CONFIABILIDADE.get(str(conf), str(conf))))

    return CrescimentoCidade(
        disponivel=True,
        linhas=[(texto_pdf(r), texto_pdf(v)) for r, v in linhas],
        frase=texto_pdf(frase if frase else (veredito or "")),
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


def preparar_hexes_da_cidade(
    df_muni: pd.DataFrame,
    renda_domiciliar_por_hex: Mapping[str, Any] | None,
) -> pd.DataFrame:
    """Frame NOVO com as tres colunas que as paginas da cidade leem.

    - `renda_domiciliar`: do mapa `hex_id -> renda` que o relatorio municipal ja carrega para a
      tabela de regioes (`carregar_renda_domiciliar_por_hex`). Sem o mapa a coluna fica nula e a
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
    renda_municipal: bool = False


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
