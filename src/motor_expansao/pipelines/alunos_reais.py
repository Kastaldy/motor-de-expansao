"""Crosswalk de ALUNOS REAIS por unidade de concorrente (BLK-ALUNOS-01).

O QUE ESTE MODULO RESOLVE. Temos duas metades que nunca se encontraram: planilhas de
alunos reais por unidade (`data/validacao/`, entregues pelas proprias redes) e coordenadas
por unidade (coletores proprios + coletor WellHub). O join entre elas existia em
`dimensionamento/base_multirede.py`, mas (a) le `concorrentes/Unidades/*.csv`, diretorio
que nao viaja no repo -- as duas de tres funcoes levantam `FileNotFoundError` hoje --,
(b) so conhece 3 redes e (c) casa a SkyFit por CIDADE, jogando fora a coluna de nome da
unidade que a planilha tem. Medido: 39,2% pela cidade contra 86,8% pelo nome.

A FONTE DE COORDENADA AQUI E' O ARTEFATO QUE A PRODUCAO SERVE (`concorrentes_mapeados`,
atualizado pelo cron semanal), com o feed WellHub (`vulnerabilidade_ma_redes`) como
segunda fonte. E' de proposito: o pino que o operador ve no mapa nasce desse artefato, e
o numero de alunos precisa pousar na MESMA linha para chegar ao tooltip.

O QUE DERRUBA A TAXA DE MATCH E' ORTOGRAFICO, NAO SEMANTICO. Cada coletor carimba o rotulo
de um jeito: sufixo de UF (`Vila Granada - SP`), prefixo de rede (`PACER Ribeirania`),
bairro concatenado com cidade (`Desvio Rizzo Caxias do Sul`). Sao tres normalizacoes
baratas que valem mais que qualquer afrouxamento de corte -- por isso o corte fica ALTO
(0,95) e o trabalho e' feito antes de comparar.

ALUNOS = PLANOS + AGREGADORES. Convencao do Felipe (2026-09-10) e das proprias fontes:
a SkyFit publica `Alunos Totais = EVO + Gympass + TotalPass` e a Engenharia,
`= Ativos + Gympass`. As duas metades ficam em colunas SEPARADAS para quem precisar
separar depois; `alunos_total` e' a soma, e e' ela que a tela mostra.

READ-ONLY sobre o M1: nao recalcula score, nao escreve artefato oficial. O consumo disso
no residual (trocar a capacidade proxy de 2.500) e' passo SEGUINTE e exige DEC propria.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

_logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]

CONCORRENTES_PATH = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"
WELLHUB_PATH = ROOT / "data" / "staging" / "vulnerabilidade_ma_redes.parquet"
ESTRUTURAL_PATH = ROOT / "data" / "staging" / "brasil_estrutural.parquet"
VALIDACAO_DIR = ROOT / "data" / "validacao"
#: Planilha de coordenadas da Smart Fit vinda da analise externa da DEC-012. OPCIONAL:
#: `NAO_ABRA/` e' gitignored e nao existe em todo checkout. Sem ela o crosswalk roda e
#: perde ~22 unidades; com ela, entra a ponte por coordenada (ver `_ponte_por_coordenada`).
SMARTFIT_COORDS_XLSX = ROOT / "NAO_ABRA" / "01_SmartFit.xlsx"

OUT_PATH = ROOT / "data" / "staging" / "alunos_reais_por_unidade.parquet"

#: Corte do fuzzy. ALTO de proposito -- ver docstring do modulo. Abaixo disso a linha vira
#: `nao_casado` e entra no relatorio de auditoria, em vez de casar errado em silencio.
LIMIAR_FUZZY: float = 0.95
#: Raio da ponte por coordenada. Mesma regua da DEC-034 (`d <= 150 m`), que ja e' a
#: constante de dedup entre fontes deste repo -- nao inventar uma segunda.
PONTE_RAIO_M: float = 150.0

VERSAO_CONTRATO = "alunos_reais_v1"

COLUNAS_SAIDA = (
    "concorrente_id",
    "rede",
    "nome_unidade",
    "lat",
    "lng",
    "hex_id_res7",
    "rotulo_fonte",
    "uf",
    "alunos_planos",
    "alunos_agregador",
    "alunos_total",
    "metragem",
    "fonte_alunos",
    "metodo_match",
    "confianca_match",
    "score_match",
    "versao_contrato",
)

_UF_SET = frozenset(
    "ac al ap am ba ce df es go ma mt ms mg pa pb pr pe pi rj rn rs ro rr sc sp se to".split()
)
#: Prefixo de REDE no rotulo do coletor (`PACER Ribeirania`, `SkyFit Academia - X`). Sem
#: tirar isso, a Pacer casava 0 de 13 -- as 12 unidades estavam la, todas prefixadas.
_PREFIXO_REDE_RE = re.compile(
    r"^\s*(pacer|redfit|red fit|skyfi?[tr]\s+academia|skyfit|smart\s*fit|"
    r"ecb?|engenharia do corpo|academia)\b[\s\-]*",
    re.IGNORECASE,
)
#: Numeracao/prefixo administrativo do relatorio interno (`12 - REDFIT - Matriz Pasteur`).
_PREFIXO_NUM_RE = re.compile(r"^\s*\d+\s*-\s*")
#: Numero de SEQUENCIA da unidade, escrito em romano de um lado e arabe do outro
#: (`Bonfim I` x `Bonfim 1`, `Sertaozinho II` x `Sertaozinho 2`). Sao a MESMA academia e
#: o `SequenceMatcher` nao tem como saber -- `sertaozinho ii` x `sertaozinho 2` da 0,89 e
#: morre abaixo do corte. So' converte o ULTIMO token: `Vila Rica` nao pode virar `Vila 0`.
_ROMANOS = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6"}


# ---------------------------------------------------------------------------
# Normalizacao de rotulo
# ---------------------------------------------------------------------------


def normalizar(valor: object) -> str:
    """Minuscula, sem acento, sem pontuacao, espaco unico."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", texto.lower()).split())


def remover_uf_terminal(texto: str) -> str:
    """`vila granada sp` -> `vila granada`.

    O coletor carimba a UF no fim do rotulo; a planilha da rede nao. Comparar os dois
    como estao trava o `SequenceMatcher` abaixo de 0,95 por um motivo que nao tem nada
    a ver com serem ou nao a mesma academia.
    """
    partes = texto.split()
    if len(partes) > 1 and partes[-1] in _UF_SET:
        return " ".join(partes[:-1])
    return texto


def normalizar_sequencia(texto: str) -> str:
    """`bonfim i` -> `bonfim 1`, `sertaozinho ii` -> `sertaozinho 2`.

    Sequencia de unidade e' escrita em romano por uma fonte e em arabe pela outra. So' o
    ULTIMO token e convertido, e so' quando ha algo antes dele: `v` sozinho poderia ser o
    nome da academia, e `vila` nao pode virar numero.
    """
    partes = texto.split()
    if len(partes) > 1 and partes[-1] in _ROMANOS:
        partes[-1] = _ROMANOS[partes[-1]]
    return " ".join(partes)


def chave_rotulo(valor: object) -> str:
    """Normalizacao completa: numeracao, prefixo de rede, UF terminal e sequencia."""
    texto = _PREFIXO_NUM_RE.sub("", str(valor or ""))
    texto = _PREFIXO_REDE_RE.sub("", texto)
    return normalizar_sequencia(remover_uf_terminal(normalizar(texto)))


def _candidatos_na_uf(pool: pd.DataFrame, uf: object) -> pd.DataFrame:
    """Recorta o pool pela UF do alvo. FAIL-CLOSED contra UF conhecida e diferente.

    A primeira versao caia no pool INTEIRO quando o recorte saia vazio, e isso e' a pior
    combinacao possivel: um alvo `Centro` em AM sem candidato em AM ia buscar no pais
    todo e casava com um `Centro` do RS com score **1,000** -- match perfeito, errado, e
    sem nada no numero que denuncie a troca. E' o mesmo fail-open que a emenda E3 da
    DEC-039 teve de fechar na fronteira do coletor.

    UF NULA no candidato continua elegivel: e' AUSENCIA de informacao (hexagono que nao
    casou no estrutural), nao um estado diferente -- excluir seria punir o candidato pelo
    que nao sabemos dele.
    """
    texto = str(uf or "").strip().upper()
    if not texto or "uf" not in pool.columns:
        return pool
    return pool[pool["uf"].isna() | pool["uf"].astype(str).str.upper().eq(texto)]


def _haversine_m(
    lat1: float, lng1: float, lat2: np.ndarray, lng2: np.ndarray
) -> np.ndarray:
    """Distancia em metros de 1 ponto para N pontos."""
    raio = 6371.0088
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lng2 - lng1)
    h = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * raio * np.arcsin(np.sqrt(h)) * 1000.0


# ---------------------------------------------------------------------------
# Pool de unidades com coordenada (as duas fontes)
# ---------------------------------------------------------------------------


def montar_pool(
    *,
    concorrentes_path: Path = CONCORRENTES_PATH,
    wellhub_path: Path = WELLHUB_PATH,
    estrutural_path: Path = ESTRUTURAL_PATH,
) -> pd.DataFrame:
    """Une coletor proprio + feed WellHub num pool de candidatos com coordenada.

    O coletor proprio vem PRIMEIRO e e' o unico que carrega `concorrente_id` -- e' o pino
    que a producao desenha. A unidade que so' existe no WellHub entra com `concorrente_id`
    nulo: ela ganha alunos no artefato (serve ao residual) mas nao tem pino para receber
    tooltip, e essa diferenca precisa ser LEGIVEL, nao inferida de um id vazio.
    """
    partes: list[pd.DataFrame] = []

    if concorrentes_path.exists():
        conc = pd.read_parquet(concorrentes_path)
        if "status_registro" in conc.columns:
            conc = conc[conc["status_registro"].eq("valido")]
        conc = conc[conc["lat"].notna() & conc["lng"].notna()].copy()
        partes.append(
            pd.DataFrame(
                {
                    "concorrente_id": conc["concorrente_id"].astype("string"),
                    "rede": conc["rede"].astype(str),
                    "nome_unidade": conc["nome_unidade"].astype(str),
                    "lat": pd.to_numeric(conc["lat"], errors="coerce"),
                    "lng": pd.to_numeric(conc["lng"], errors="coerce"),
                    "hex_id_res7": conc["hex_id_res7"].astype("string"),
                    "fonte_coord": "coletor_proprio",
                }
            )
        )
    else:
        _logger.warning("concorrentes_mapeados ausente em %s", concorrentes_path)

    if wellhub_path.exists():
        wh = pd.read_parquet(wellhub_path)
        wh = wh[wh["lat"].notna() & wh["lng"].notna()].copy()
        partes.append(
            pd.DataFrame(
                {
                    "concorrente_id": pd.Series([pd.NA] * len(wh), dtype="string"),
                    "rede": wh["rede"].astype(str),
                    "nome_unidade": wh["nome"].astype(str),
                    "lat": pd.to_numeric(wh["lat"], errors="coerce"),
                    "lng": pd.to_numeric(wh["lng"], errors="coerce"),
                    "hex_id_res7": wh["hex_id_res7"].astype("string"),
                    "fonte_coord": "wellhub",
                }
            )
        )
    else:
        _logger.warning("vulnerabilidade_ma_redes ausente em %s", wellhub_path)

    if not partes:
        return pd.DataFrame(columns=["concorrente_id", "rede", "nome_unidade", "lat", "lng", "hex_id_res7", "fonte_coord", "uf", "chave"])

    pool = pd.concat(partes, ignore_index=True)
    pool["uf"] = _uf_por_hex(pool["hex_id_res7"], estrutural_path)
    pool["chave"] = pool["nome_unidade"].map(chave_rotulo)
    return pool


def _uf_por_hex(hexes: pd.Series, estrutural_path: Path) -> pd.Series:
    """UF a partir do hexagono. O artefato de concorrentes nao tem coluna de UF.

    Ela importa porque o fuzzy roda DENTRO da UF: `Centro` existe em quase toda cidade do
    pais, e sem o recorte um `Centro` de Manaus casaria com um `Centro` de Porto Alegre
    com score 1,000 -- match perfeito e completamente errado.
    """
    if not estrutural_path.exists():
        _logger.warning("brasil_estrutural ausente; fuzzy vai rodar sem recorte de UF")
        return pd.Series([None] * len(hexes), index=hexes.index, dtype="object")
    estrutural = pd.read_parquet(estrutural_path, columns=["hex_id", "uf"])
    mapa = estrutural.set_index(estrutural["hex_id"].astype(str))["uf"].astype(str)
    return hexes.astype(str).map(mapa)


# ---------------------------------------------------------------------------
# Leitores das planilhas de alunos (uma por rede)
# ---------------------------------------------------------------------------


def _frame_alunos(
    rede: str,
    rotulos: pd.Series,
    ufs: pd.Series,
    planos: pd.Series,
    agregador: pd.Series | None = None,
    metragem: pd.Series | None = None,
    *,
    fonte: str,
) -> pd.DataFrame:
    """Contrato comum de saida dos leitores. `alunos_total = planos + agregador`.

    A soma usa `min_count=1`: rede sem coluna de agregador tem `alunos_agregador` NULO,
    e nulo somado a numero teria virado nulo -- apagaria o total de quem so' publica
    plano. Nulo + nulo continua nulo (nao inventa zero para quem nao informou).
    """
    zero = pd.Series([pd.NA] * len(rotulos), index=rotulos.index, dtype="Float64")
    ag = zero if agregador is None else pd.to_numeric(agregador, errors="coerce").astype("Float64")
    pl = pd.to_numeric(planos, errors="coerce").astype("Float64")
    return pd.DataFrame(
        {
            "rede": rede,
            "rotulo_fonte": rotulos.astype(str).values,
            "uf": ufs.astype(str).str.strip().str.upper().values,
            "alunos_planos": pl.values,
            "alunos_agregador": ag.values,
            "alunos_total": pd.concat([pl, ag], axis=1).sum(axis=1, min_count=1).values,
            "metragem": (
                pd.Series([pd.NA] * len(rotulos), dtype="Float64").values
                if metragem is None
                else pd.to_numeric(metragem, errors="coerce").astype("Float64").values
            ),
            "fonte_alunos": fonte,
        }
    )


def ler_smart_fit(caminho: Path | None = None) -> pd.DataFrame:
    """Smart Fit: painel MENSAL (37 meses, 961 unidades). Usa o mes mais recente.

    A `Sigla` carrega a UF nas posicoes 3-4 (`SBRSPCABC01` -> `SP`), e e' isso que torna
    o recorte por UF possivel numa planilha que nao tem coluna de estado. `Alunos Totais
    SF` ja e' o total da rede -- nao ha coluna de agregador para somar.
    """
    caminho = caminho or _primeiro_existente(VALIDACAO_DIR, "KPIs_Smart_*.xlsx")
    if caminho is None:
        return _vazio()
    dados = pd.read_excel(caminho, sheet_name="Base")
    dados = dados[dados["Data_Ref"].eq(dados["Data_Ref"].max())].copy()
    ref = pd.to_datetime(dados["Data_Ref"].max()).date().isoformat()
    return _frame_alunos(
        "smart_fit",
        dados["Nome"],
        dados["Sigla"].astype(str).str[3:5],
        dados["Alunos Totais SF"],
        fonte=f"KPIs_Smart ({ref})",
    )


def ler_skyfit(caminho: Path | None = None) -> pd.DataFrame:
    """SkyFit: `Alunos Totais = EVO + Gympass + TotalPass` (a propria planilha soma).

    Guardamos EVO como `alunos_planos` e Gympass+TotalPass como `alunos_agregador`, em
    vez de ler a coluna ja somada: a separacao e' pedida e a planilha e' a unica fonte
    que a tem explicita. A chave e' `NOMENCLATURA UNIDADE`, NAO `CIDADE` -- e' a diferenca
    entre 86,8% e 39,2% de match.
    """
    caminho = caminho or _primeiro_existente(VALIDACAO_DIR, "Sky Fit dados.xlsx")
    if caminho is None:
        return _vazio()
    dados = pd.read_excel(caminho, sheet_name="Sell Out", header=3)
    dados = dados.dropna(subset=["CIDADE", "ESTADO"]).copy()
    agregador = pd.to_numeric(dados["Alunos Gympass"], errors="coerce").fillna(0) + pd.to_numeric(
        dados["Alunos TotalPass"], errors="coerce"
    ).fillna(0)
    return _frame_alunos(
        "skyfit",
        dados["NOMENCLATURA UNIDADE"],
        dados["ESTADO"],
        dados["Alunos EVO"],
        agregador,
        fonte="Sky Fit dados",
    )


def ler_engenharia(caminho: Path | None = None) -> pd.DataFrame:
    """Engenharia do Corpo: `Alunos Totais = Ativos + Gympass`, com metragem real."""
    caminho = caminho or _primeiro_existente(VALIDACAO_DIR, "academias_engenharia_do_corpo.xlsx")
    if caminho is None:
        return _vazio()
    dados = pd.read_excel(caminho, sheet_name="Academias").dropna(subset=["Unidade"]).copy()
    ufs = dados["Unidade"].astype(str).str.extract(r",\s*([A-Za-z]{2})\s*$")[0]
    return _frame_alunos(
        "engenharia_do_corpo",
        dados["Unidade"],
        ufs.fillna(""),
        dados["Total Alunos Ativos"],
        dados["Total Alunos Gympass"],
        dados.get("Metragem M²"),
        fonte="academias_engenharia_do_corpo",
    )


def ler_redfit(caminho: Path | None = None) -> pd.DataFrame:
    """RedFit: transcricao do relatorio de faturamento (junho/2026), entregue como imagem.

    `alunos_planos` = TOTAL ATIVOS e `alunos_agregador` = USUARIOS WELLHUB, que na fonte
    sao colunas distintas -- o usuario de agregador NAO esta dentro do total de ativos
    (Matriz Pasteur: 371 ativos e 518 WellHub). A transcricao foi conferida contra os
    dois totais impressos na propria imagem (12.326 e 20.794).
    """
    caminho = caminho or _primeiro_existente(VALIDACAO_DIR, "redfit_*.csv")
    if caminho is None:
        return _vazio()
    dados = pd.read_csv(caminho, sep=";", encoding="utf-8-sig")
    return _frame_alunos(
        "redfit",
        dados["unidade"],
        dados["uf"],
        dados["alunos_planos"],
        dados["alunos_wellhub"],
        fonte=caminho.stem,
    )


def ler_pacer(caminho: Path | None = None) -> pd.DataFrame:
    """Grupo Pacer: 13 unidades em Ribeirao Preto/Sertaozinho/Bonfim Paulista, com area.

    So' `ALUNOS ATIVOS` -- a fonte nao separa agregador, entao `alunos_agregador` fica
    NULO (e nao zero: nao sabemos que e' zero, sabemos que nao foi informado).
    """
    caminho = caminho or _primeiro_existente(VALIDACAO_DIR, "pacer_*.csv")
    if caminho is None:
        return _vazio()
    dados = pd.read_csv(caminho, sep=";", encoding="utf-8-sig")
    return _frame_alunos(
        "pacer",
        dados["unidade"],
        dados["uf"],
        dados["alunos_planos"],
        metragem=dados.get("metragem"),
        fonte=caminho.stem,
    )


LEITORES = (ler_smart_fit, ler_skyfit, ler_engenharia, ler_redfit, ler_pacer)


def _vazio() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "rede", "rotulo_fonte", "uf", "alunos_planos",
            "alunos_agregador", "alunos_total", "metragem", "fonte_alunos",
        ]
    )


def _primeiro_existente(pasta: Path, padrao: str) -> Path | None:
    """Primeiro arquivo do padrao, em ordem estavel. Ausencia e' AVISO, nao excecao.

    As fontes sao gitignored (dado real de concorrente) e nao existem em CI nem em
    checkout novo. Levantar aqui faria a cadeia inteira falhar por causa de uma rede.
    """
    achados = sorted(pasta.glob(padrao)) if pasta.exists() else []
    if not achados:
        _logger.warning("fonte de alunos ausente: %s/%s", pasta, padrao)
        return None
    return achados[0]


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------


def _casar_por_nome(
    alvos: pd.DataFrame, pool: pd.DataFrame, ocupados: set[int] | None = None
) -> dict[int, tuple[float, int]]:
    """Atribuicao GULOSA por score, dentro da UF, cada candidato usado uma vez.

    Guloso e nao "melhor para cada um" porque duas unidades da mesma rede podem ter o
    mesmo melhor candidato; sem a exclusao mutua, as duas receberiam a mesma coordenada
    e o artefato afirmaria que ha duas academias no mesmo ponto.

    `ocupados` sao candidatos que uma rota ANTERIOR ja tomou. Sem esse parametro cada
    rota comecava com o pool limpo e podia reatribuir um pino ja usado -- o mesmo
    `concorrente_id` saindo com duas contagens de alunos diferentes, e uma delas vencendo
    em silencio no merge. Media na primeira execucao: 9 pinos duplicados.
    """
    ocupados = set() if ocupados is None else set(ocupados)
    propostas: list[tuple[float, int, int]] = []
    for ia, alvo in alvos.iterrows():
        candidatos = _candidatos_na_uf(pool, alvo.get("uf"))
        chave = str(alvo["chave"])
        if not chave or candidatos.empty:
            continue
        melhor_score, melhor_idx = -1.0, None
        for idx, valor in candidatos["chave"].items():
            if int(idx) in ocupados:
                continue
            score = SequenceMatcher(None, chave, str(valor)).ratio()
            if score > melhor_score:
                melhor_score, melhor_idx = score, idx
        if melhor_idx is not None and melhor_score >= LIMIAR_FUZZY:
            propostas.append((float(melhor_score), int(ia), int(melhor_idx)))

    propostas.sort(reverse=True)
    usados: set[int] = set(ocupados)
    casado: dict[int, tuple[float, int]] = {}
    for score, ia, idx in propostas:
        if ia in casado or idx in usados:
            continue
        casado[ia] = (score, idx)
        usados.add(idx)
    return casado


def _subsequencia_de(pequeno: list[str], grande: list[str]) -> bool:
    """`pequeno` aparece em `grande` como bloco contiguo de tokens."""
    n = len(pequeno)
    if not n or n > len(grande):
        return False
    return any(grande[i : i + n] == pequeno for i in range(len(grande) - n + 1))


def _casar_por_contencao(
    alvos: pd.DataFrame,
    pool: pd.DataFrame,
    ja_casados: set[int],
    ocupados: set[int] | None = None,
) -> dict[int, tuple[float, int]]:
    """Segunda passada: um rotulo CONTEM o outro inteiro, so' que com cidade colada.

    A Engenharia do Corpo publica `EC - BLUMENAU` e o coletor gravou `Centro Blumenau`;
    `Desvio Rizzo` virou `Desvio Rizzo Caxias do Sul`. Sao a mesma academia com um
    qualificador a mais, e o `SequenceMatcher` pune isso proporcionalmente ao tamanho do
    que sobra -- `diamantino` x `diamantino caxias do sul` da 0,588, longe de qualquer
    corte defensavel.

    Duas travas, porque contencao e' mais permissiva que similaridade:
      1. **Unicidade** -- so' casa se EXATAMENTE UM candidato livre contem o rotulo. Com
         dois, `Centro` casaria com o primeiro da lista, que e' sorteio disfarcado.
      2. **Dois tokens no minimo** -- rotulo de UM token e' FRAGMENTO, e fragmento e'
         exatamente o que produz contencao falsa: `Alvorada` estava contido em
         `Nova Iguacu - Jardim Alvorada` e `Goias` em `Assai SCS - Av. Goias`, os dois
         unicos na UF e os dois errados. Medido na 1a versao: sem a trava entravam 17
         pares, 10 deles de um token e cerca de metade duvidosos. Custa alguns acertos
         legitimos (`Villagio` -> `Villagio - Caxias do Sul`) e esse e' o lado certo de
         errar: numero errado no tooltip e' pior que numero ausente.
      3. **Token distintivo** -- ao menos um token com 4+ letras, senao `ct` casaria
         com meio pais.
    """
    ocupados = set() if ocupados is None else set(ocupados)
    resgatados: dict[int, tuple[float, int]] = {}
    usados: set[int] = set(ocupados)
    for ia, alvo in alvos.iterrows():
        if ia in ja_casados:
            continue
        tokens = str(alvo["chave"]).split()
        if len(tokens) < 2 or not any(len(t) >= 4 for t in tokens):
            continue
        candidatos = _candidatos_na_uf(pool, alvo.get("uf"))
        achados = [
            idx
            for idx, valor in candidatos["chave"].items()
            if idx not in usados and _subsequencia_de(tokens, str(valor).split())
        ]
        if len(achados) != 1:
            continue
        idx = int(achados[0])
        # Grava a similaridade REAL, nao 1,0: quem decidiu foi a contencao, e um score
        # cravado no teto esconderia da auditoria o quanto os dois rotulos divergem.
        score = SequenceMatcher(None, str(alvo["chave"]), str(pool.loc[idx, "chave"])).ratio()
        resgatados[int(ia)] = (float(score), idx)
        usados.add(idx)
    return resgatados


def _ponte_por_coordenada(
    alvos: pd.DataFrame,
    pool: pd.DataFrame,
    coords: pd.DataFrame,
    ja_casados: set[int],
    ocupados: set[int] | None = None,
) -> dict[int, tuple[float, int]]:
    """Resgata pelo ENDERECO quem o nome nao alcancou.

    A ideia: casar o rotulo da planilha contra uma SEGUNDA lista de rotulos (a da propria
    rede, com coordenada) e, tendo a coordenada, achar o pino mais proximo. Coordenada nao
    tem variante ortografica -- e a mediana medida entre as duas fontes da Smart Fit foi
    de 19 m, ou seja, sao as mesmas academias.

    So' roda para quem o nome NAO casou, e o resultado e' carimbado `ponte_coordenada`
    para que a auditoria consiga separar as duas rotas.
    """
    if coords.empty or pool.empty:
        return {}
    pendentes = alvos[~alvos.index.isin(ja_casados)]
    if pendentes.empty:
        return {}
    por_nome = _casar_por_nome(pendentes, coords)
    lat_pool = pool["lat"].to_numpy(dtype=float)
    lng_pool = pool["lng"].to_numpy(dtype=float)
    idx_pool = pool.index.to_numpy()

    resgatados: dict[int, tuple[float, int]] = {}
    usados: set[int] = set() if ocupados is None else set(ocupados)
    for ia, (score, idx_coord) in sorted(por_nome.items(), key=lambda kv: -kv[1][0]):
        lat = float(coords.loc[idx_coord, "lat"])
        lng = float(coords.loc[idx_coord, "lng"])
        distancias = _haversine_m(lat, lng, lat_pool, lng_pool)
        k = int(np.argmin(distancias))
        if distancias[k] > PONTE_RAIO_M or int(idx_pool[k]) in usados:
            continue
        resgatados[int(ia)] = (float(score), int(idx_pool[k]))
        usados.add(int(idx_pool[k]))
    return resgatados


def ler_coords_smart_fit(caminho: Path = SMARTFIT_COORDS_XLSX) -> pd.DataFrame:
    """Lista de coordenadas da Smart Fit (fonte externa, OPCIONAL).

    Le somente `Nome`/`Latitude`/`Longitude` -- localizacao de academia, nunca dado
    pessoal. A pasta e' gitignored e a ausencia dela e' caminho normal, nao erro.
    """
    if not caminho.exists():
        _logger.info("coords Smart Fit ausentes (%s); ponte por coordenada desligada", caminho)
        return pd.DataFrame(columns=["chave", "lat", "lng", "uf"])
    dados = pd.read_excel(caminho, sheet_name="Smart Fit")
    return pd.DataFrame(
        {
            "chave": dados["Nome"].map(chave_rotulo),
            "lat": pd.to_numeric(dados["Latitude"], errors="coerce"),
            "lng": pd.to_numeric(dados["Longitude"], errors="coerce"),
            "uf": None,
        }
    ).dropna(subset=["lat", "lng"])


def montar_crosswalk(
    *,
    pool: pd.DataFrame | None = None,
    leitores=LEITORES,
    coords_smart_fit: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Casa alunos reais com unidades mapeadas. Devolve (crosswalk, auditoria por rede).

    A auditoria sai SEMPRE, inclusive com zero match: e' ela que distingue "esta rede nao
    tem planilha" de "a planilha existe e nao casou nada" -- dois estados que um parquet
    vazio confunde.
    """
    pool = montar_pool() if pool is None else pool
    if coords_smart_fit is None:
        coords_smart_fit = ler_coords_smart_fit()

    linhas: list[dict] = []
    auditoria: list[dict] = []

    for leitor in leitores:
        alvos = leitor()
        if alvos.empty:
            continue
        rede = str(alvos["rede"].iloc[0])
        alvos = alvos.reset_index(drop=True)
        alvos["chave"] = alvos["rotulo_fonte"].map(chave_rotulo)
        candidatos = pool[pool["rede"].eq(rede)]

        # Tres rotas, da mais restritiva para a mais permissiva, cada uma so' olhando
        # quem a anterior nao alcancou. A ordem e' o que mantem a rota barata dominante:
        # invertida, a contencao roubaria pares que o nome resolveria melhor.
        por_nome = _casar_por_nome(alvos, candidatos)
        ocupados = {idx for _, idx in por_nome.values()}
        por_contencao = _casar_por_contencao(alvos, candidatos, set(por_nome), ocupados)
        ocupados |= {idx for _, idx in por_contencao.values()}
        casado = {**por_nome, **por_contencao}
        por_ponte: dict[int, tuple[float, int]] = {}
        if rede == "smart_fit" and not coords_smart_fit.empty:
            por_ponte = _ponte_por_coordenada(
                alvos, candidatos, coords_smart_fit, set(casado), ocupados
            )
            casado.update(por_ponte)

        for ia, (score, idx) in casado.items():
            alvo = alvos.loc[ia]
            unidade = candidatos.loc[idx]
            if ia in por_ponte:
                metodo = "ponte_coordenada"
            elif ia in por_contencao:
                metodo = "contencao_uf"
            else:
                metodo = "nome_uf"
            # `nome_uf` (rotulos equivalentes) e `ponte_coordenada` (19 m de mediana entre
            # duas fontes independentes) sao inequivocos. Contencao e' inferencia: o rotulo
            # da fonte e' um PEDACO do rotulo do coletor, e quem le o tooltip nao tem como
            # auditar isso. Marcado aqui para o consumo poder escolher -- a tela mostra so'
            # `alta`, o artefato guarda os dois.
            confianca = "media" if metodo == "contencao_uf" else "alta"
            linhas.append(
                {
                    "concorrente_id": unidade["concorrente_id"],
                    "rede": rede,
                    "nome_unidade": unidade["nome_unidade"],
                    "lat": unidade["lat"],
                    "lng": unidade["lng"],
                    "hex_id_res7": unidade["hex_id_res7"],
                    "rotulo_fonte": alvo["rotulo_fonte"],
                    "uf": alvo["uf"],
                    "alunos_planos": alvo["alunos_planos"],
                    "alunos_agregador": alvo["alunos_agregador"],
                    "alunos_total": alvo["alunos_total"],
                    "metragem": alvo["metragem"],
                    "fonte_alunos": alvo["fonte_alunos"],
                    "metodo_match": metodo,
                    "confianca_match": confianca,
                    "score_match": round(float(score), 4),
                    "versao_contrato": VERSAO_CONTRATO,
                }
            )

        auditoria.append(
            {
                "rede": rede,
                "n_com_alunos": int(len(alvos)),
                "n_no_pool": int(len(candidatos)),
                "n_casadas": int(len(casado)),
                "n_por_nome": int(len(por_nome)),
                "n_por_contencao": int(len(por_contencao)),
                "n_por_ponte": int(len(por_ponte)),
                "taxa_match": round(len(casado) / max(len(alvos), 1), 4),
                "alunos_casados": float(
                    pd.to_numeric(
                        alvos.loc[list(casado), "alunos_total"], errors="coerce"
                    ).sum()
                ),
                "alunos_totais_fonte": float(
                    pd.to_numeric(alvos["alunos_total"], errors="coerce").sum()
                ),
            }
        )

    if not linhas:
        return pd.DataFrame(columns=list(COLUNAS_SAIDA)), pd.DataFrame(auditoria)

    crosswalk = pd.DataFrame(linhas)[list(COLUNAS_SAIDA)]
    return crosswalk, pd.DataFrame(auditoria)


def salvar(crosswalk: pd.DataFrame, path: Path = OUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    crosswalk.to_parquet(path, index=False)
    _logger.info("alunos_reais_por_unidade: %d linhas -> %s", len(crosswalk), path)


__all__ = [
    "COLUNAS_SAIDA",
    "LIMIAR_FUZZY",
    "OUT_PATH",
    "PONTE_RAIO_M",
    "VERSAO_CONTRATO",
    "chave_rotulo",
    "ler_coords_smart_fit",
    "ler_engenharia",
    "ler_pacer",
    "ler_redfit",
    "ler_skyfit",
    "ler_smart_fit",
    "montar_crosswalk",
    "montar_pool",
    "normalizar",
    "remover_uf_terminal",
    "salvar",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _cross, _aud = montar_crosswalk()
    print(_aud.to_string(index=False))
    salvar(_cross)
