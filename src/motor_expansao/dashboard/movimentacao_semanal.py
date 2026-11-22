"""Movimentação da concorrência pela SÉRIE SEMANAL do coletor (emenda 1 da DEC-064).

Até 19/11/2026 a tela lia só o pacote garimpado em 15/09 (`movimentacao_concorrencia`, fotos de
02/08 a 06/09), que não se regenera. O card "Crescimento da concorrência" e a ficha da unidade
ficaram parados em setembro, enquanto a série semanal (`snapshots_concorrentes`) e a ponte de
identidade (`ponte_identidade_concorrentes`, D3 da DEC-064, que diz QUEM é e ONDE fica cada
chave) seguiam chegando todo domingo. Este módulo lê as duas e devolve os eventos no MESMO formato
do pacote (`movimentacao_concorrencia.COLUNAS`), com `confianca = "semanal"`. O pacote fica como
histórico.

A diferença crua entre duas semanas inventa movimento. As regras abaixo existem por isso, todas
medidas na base de produção em 19/11/2026 (semanas 38 a 46):

1. **Troca de cadastro não é movimento.** Quando o coletor troca o nome ou a coordenada de uma
   unidade, a chave muda (âncora `nome_base` + célula res-5, DEC-063) e a unidade aparece fechando
   e abrindo. Saída e entrada da MESMA rede, na mesma semana, a até 1 km formam um par, e as duas
   saem (a regra do pacote, `DIST_TROCA_CADASTRO_M`). No Wellhub, o par exige até 1 km E um termo
   próprio do nome em comum (a regra de `descartar_trocas_de_nome_no_agregador`). Entram no
   casamento também a chave que VOLTA depois de sumir (o coletor desfez uma troca) e a chave de uma
   semana só (troca em duas etapas): nenhuma das duas vira evento, mas as duas desfazem pares.
2. **Abertura é chave INÉDITA.** Conta a semana em que a chave aparece pela primeira vez na série
   inteira; quem some e volta não abre de novo. Rede que estreia na coleta não abre unidades na
   estreia: foi o coletor que passou a enxergá-la.
3. **Fechamento só depois de `SEMANAS_PARA_FECHAR` semanas coletadas sem a chave.** Uma semana fora
   pode ser falha do coletor. Até lá o fechamento fica PENDENTE: contado no laudo, fora da tela.
4. **Recalibração e salto de cobertura da rede ficam fora.** Rede com pelo menos
   `REDE_MIN_RECALIBRACAO` unidades que, numa semana, troca de chave em pelo menos
   `FRACAO_RECALIBRACAO` delas (saídas E entradas) teve o cadastro recalibrado, e nenhum evento dela
   naquela semana conta. Medido: a Velocity trocou 126 de 126 chaves numa semana; Evoque, Kore e
   Redfit fizeram o mesmo. E rede que CRESCE de uma vez, em termos líquidos (unidades novas menos
   saídas sem par), `SALTO_REDE_MIN` unidades ou mais e pelo menos `FRACAO_SALTO_REDE` do tamanho,
   é o coletor achando mais páginas dela: as entradas daquela semana ficam fora (Selfit +17 de 232
   em 18/10).
5. **Salto de cobertura do Wellhub fica fora.** Semana em que mais de `FRACAO_COBERTURA_AGREGADOR`
   das academias do Wellhub entra (ou sai) de uma vez, depois de casar as trocas, é o coletor
   ampliando (ou reduzindo) o que enxerga, não credenciamento. Medido: +369 e +730 em duas semanas,
   contra ~50 nas outras.
6. **Anúncio vem do nome na ponte**, pela MESMA regra que tira o marcador da chave (`nome_base`,
   `_RE_MARCADOR_PIPELINE`): "Em breve", "Pré-lançamento", "Pré-venda", "Pré-abertura", "Próxima
   abertura", "Inauguração", "Lançamento" — menos "Inaugurada", que diz que já abriu. Chave nova
   anunciada não é abertura. Perder o marcador é inauguração, com a mesma chave ou com o par de
   troca de cadastro. O pipeline é o que segue anunciado na última semana. Anúncio que some não é
   fechamento, nem pendente.
7. **Pisca não conta.** Chave vista numa semana só, fora da última, não abre nem fecha.

Camada visual e READ-ONLY sobre o M1. `ler_serie` lê o disco; `eventos_da_serie` e os resumos são
puros.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from motor_expansao.vulnerabilidade.contrato import _RE_MARCADOR_PIPELINE, normalizar_texto

from .movimentacao_concorrencia import (
    COLUNAS,
    DIST_TROCA_CADASTRO_M,
    DIST_TROCA_NOME_AGREGADOR_M,
    _distancias_m,
    _termos_proprios,
    resumo_agregadores,
)

DIR_SNAPSHOTS = "snapshots_concorrentes"
DIR_PONTE = "ponte_identidade_concorrentes"
FONTE_CADASTRO = "unidades"
FONTE_AGREGADOR = "wellhub"
FONTES: tuple[str, ...] = (FONTE_CADASTRO, FONTE_AGREGADOR)

#: Rótulo da confiança dos eventos da série; o pacote usa "alta" e "cautela".
CONFIANCA = "semanal"
#: Semanas COLETADAS seguidas sem a chave para o fechamento valer (regra 3).
SEMANAS_PARA_FECHAR = 2
#: Fração das unidades de uma rede trocando de chave na mesma semana que denuncia recalibração (regra 4).
FRACAO_RECALIBRACAO = 0.20
#: Rede menor que isto não passa pela regra 4: em rede de 3 unidades, 1 abertura já seria 33%.
REDE_MIN_RECALIBRACAO = 5
#: Rede que CRESCE de uma vez, em termos líquidos, pelo menos `SALTO_REDE_MIN` unidades e esta fração
#: do tamanho teve a cobertura do coletor ampliada (regra 4). Medido em 19/11: Selfit +17 de 232 numa
#: semana (18/10) e Ufit +9 de 25 (15/11); Smart Fit (5 de 1.060) e Panobianco (6 de 530) seguem
#: contando. Saída em massa NÃO passa por aqui: fechamento só vale com a chave ausente até a última
#: semana, então a falha do coletor se desfaz sozinha quando ele volta a achar a unidade; a entrada
#: inédita, não.
FRACAO_SALTO_REDE = 0.05
SALTO_REDE_MIN = 5
#: Fração do Wellhub entrando (ou saindo) de uma vez que denuncia salto de cobertura (regra 5).
FRACAO_COBERTURA_AGREGADOR = 0.01

#: Como a série marca a academia SEM rede no Wellhub. O pacote (e a tela) usam rede vazia para
#: isso: é o que separa "independentes" de "unidades de rede" no resumo do agregador.
REDE_INDEPENDENTE = "independente"


#: "Inaugurada" casa no `inaugura\w*` do marcador da chave (e lá está certo: "X - Inaugurada" e "X"
#: são a mesma unidade), mas diz que a unidade JÁ ABRIU. Medido em 19/11: a Bluefit marca as recém
#: abertas com "- Inaugurada", e sem esta exceção 20 delas viravam "Em breve".
_RE_JA_INAUGURADA = re.compile(r"\binaugurad[ao]s?\b")


def anunciada(nome: Any) -> bool:
    """O nome traz marcador de anúncio ("Em breve", "Pré-lançamento"...), pela regra da chave.

    Exceção: "Inaugurada"/"Inaugurado" não é anúncio, é o contrário.
    """
    if not isinstance(nome, str):
        return False
    texto = _RE_JA_INAUGURADA.sub(" ", normalizar_texto(nome))
    return bool(_RE_MARCADOR_PIPELINE.search(texto))


def _rede_da_linha(rede: Any) -> str | None:
    if rede is None or (not isinstance(rede, str) and pd.isna(rede)):
        return None
    texto = str(rede).strip()
    return None if not texto or texto.lower() == REDE_INDEPENDENTE else texto


@dataclass
class Serie:
    """A série semanal já reduzida ao que a movimentação usa (ver `ler_serie`).

    - `semanas`: por fonte, as semanas coletadas, em ordem;
    - `inicio`: por fonte, a primeira semana com ponte: a janela da tela começa nela;
    - `datas`: `(fonte, semana)` -> data da coleta (AAAA-MM-DD);
    - `chaves`: uma linha por `(fonte, chave_snapshot)`, com `rede` (a da última semana), `primeira`
      e `ultima` (semanas da primeira e da última observação, na série INTEIRA);
    - `voltas`: `fonte, semana, chave_snapshot, rede` das chaves que reapareceram naquela semana
      depois de faltar na coleta anterior (não são inéditas);
    - `ausencias`: as chaves que faltaram naquela semana e voltaram depois (o espelho de `voltas`);
    - `tamanho_rede`: unidades de cada rede de cadastro por semana (`fonte, semana, rede, n`);
    - `tamanho_fonte`: `(fonte, semana)` -> chaves na semana;
    - `ponte`: `fonte, semana, chave_snapshot, nome, lat, lng`, só nas linhas que a conta usa.
    """

    semanas: dict[str, list[str]]
    inicio: dict[str, str]
    datas: dict[tuple[str, str], str]
    chaves: pd.DataFrame
    tamanho_rede: pd.DataFrame
    tamanho_fonte: dict[tuple[str, str], int] = field(default_factory=dict)
    ponte: pd.DataFrame = field(default_factory=pd.DataFrame)
    voltas: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["fonte", "semana", "chave_snapshot", "rede"])
    )
    #: `fonte, semana, anterior, chave_snapshot, rede` das chaves que faltaram naquela semana e
    #: VOLTARAM depois (ausência temporária): o lado de saída do casamento, que nunca vira evento.
    ausencias: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["fonte", "semana", "anterior", "chave_snapshot", "rede"])
    )


def _semana_da_particao(diretorio: Path) -> str:
    return diretorio.parent.name.split("=", 1)[1]


def _particoes(raiz: Path, fonte: str) -> list[Path]:
    return sorted((p for p in raiz.glob(f"semana=*/fonte={fonte}") if p.is_dir()), key=_semana_da_particao)


def _data_da_coleta(t: pd.DataFrame, semana: str) -> str:
    datas = t["snapshot_date"].dropna().astype(str)
    return str(datas.max())[:10] if len(datas) else semana


def ler_serie(staging: Path | str) -> Serie | None:
    """Lê a série e a ponte em duas passadas, sem segurar a série inteira na memória.

    Passada 1 (série): por semana, só `chave_snapshot`, `rede` e `snapshot_date`. Guarda a primeira
    e a última semana de cada chave, as chaves que VOLTARAM (presentes na semana e ausentes na coleta
    anterior, sem serem inéditas), o tamanho de cada rede (e de cada fonte) e a data da coleta.
    Passada 2 (ponte): nome e coordenada só das linhas que a conta usa. São as chaves que nascem,
    somem ou voltam em cada semana da janela, e, nas unidades de rede, as que estão anunciadas no
    nome ou estavam na semana anterior.

    Sem a série, ou sem nenhuma semana com ponte, devolve `None`.
    """
    raiz_s, raiz_p = Path(staging) / DIR_SNAPSHOTS, Path(staging) / DIR_PONTE
    if not raiz_s.is_dir() or not raiz_p.is_dir():
        return None
    semanas: dict[str, list[str]] = {}
    inicio: dict[str, str] = {}
    datas: dict[tuple[str, str], str] = {}
    tamanho_fonte: dict[tuple[str, str], int] = {}
    vidas: list[pd.DataFrame] = []
    tamanhos: list[pd.DataFrame] = []
    voltas: list[pd.DataFrame] = []
    sumicos: list[pd.DataFrame] = []
    for fonte in FONTES:
        primeira: dict[str, str] = {}
        ultima: dict[str, str] = {}
        rede_de: dict[str, str | None] = {}
        lista: list[str] = []
        anteriores: set[str] = set()
        for particao in _particoes(raiz_s, fonte):
            semana = _semana_da_particao(particao)
            t = pd.read_parquet(particao, columns=["chave_snapshot", "rede", "snapshot_date"])
            t = t.dropna(subset=["chave_snapshot"]).drop_duplicates("chave_snapshot")
            if not len(t):
                continue
            chaves_semana = t["chave_snapshot"].astype(str)
            atuais = set(chaves_semana)
            if lista:
                voltaram = sorted(c for c in atuais - anteriores if c in primeira)
                if voltaram:
                    voltas.append(
                        pd.DataFrame(
                            {"fonte": fonte, "semana": semana, "chave_snapshot": voltaram, "rede": [rede_de[c] for c in voltaram]}
                        )
                    )
                sumiram = sorted(anteriores - atuais)
                if sumiram:
                    sumicos.append(
                        pd.DataFrame(
                            {
                                "fonte": fonte,
                                "semana": semana,
                                "anterior": lista[-1],
                                "chave_snapshot": sumiram,
                                "rede": [rede_de[c] for c in sumiram],
                            }
                        )
                    )
            lista.append(semana)
            datas[(fonte, semana)] = _data_da_coleta(t, semana)
            tamanho_fonte[(fonte, semana)] = len(t)
            for chave, rede in zip(chaves_semana, t["rede"], strict=True):
                primeira.setdefault(chave, semana)
                ultima[chave] = semana
                rede_de[chave] = _rede_da_linha(rede)
            anteriores = atuais
            if fonte == FONTE_CADASTRO:
                n = t["rede"].dropna().astype(str).value_counts()
                tamanhos.append(
                    pd.DataFrame({"fonte": fonte, "semana": semana, "rede": n.index.astype(str), "n": n.to_numpy()})
                )
        if not lista:
            continue
        semanas[fonte] = lista
        com_ponte = {_semana_da_particao(p) for p in _particoes(raiz_p, fonte)}
        janela = [s for s in lista if s in com_ponte]
        if janela:
            inicio[fonte] = janela[0]
        vidas.append(
            pd.DataFrame(
                {
                    "fonte": fonte,
                    "chave_snapshot": list(primeira),
                    "rede": [rede_de[c] for c in primeira],
                    "primeira": [primeira[c] for c in primeira],
                    "ultima": [ultima[c] for c in primeira],
                }
            )
        )
    if not inicio:
        return None
    chaves = pd.concat(vidas, ignore_index=True)
    tabela_voltas = (
        pd.concat(voltas, ignore_index=True)
        if voltas
        else pd.DataFrame(columns=["fonte", "semana", "chave_snapshot", "rede"])
    )
    # Ausência TEMPORÁRIA: a chave sumiu naquela semana e reapareceu depois (a última observação é
    # posterior à semana em que ela faltou). A que não voltou é `fecha`, tratada pela regra 3.
    tabela_ausencias = pd.DataFrame(columns=["fonte", "semana", "anterior", "chave_snapshot", "rede"])
    if sumicos:
        todas = pd.concat(sumicos, ignore_index=True)
        ultimas = chaves.set_index(["fonte", "chave_snapshot"])["ultima"]
        ult_da_chave = [ultimas.get((fo, ch)) for fo, ch in zip(todas["fonte"], todas["chave_snapshot"], strict=True)]
        voltou = [u is not None and str(u) > str(ant) for u, ant in zip(ult_da_chave, todas["anterior"], strict=True)]
        tabela_ausencias = todas.loc[_mascara(todas, voltou)].reset_index(drop=True)
    pontes: list[pd.DataFrame] = []
    for fonte, comeco in inicio.items():
        lista = semanas[fonte]
        vida = chaves[chaves["fonte"] == fonte]
        ult = lista[-1]
        anunciadas_antes: set[str] = set()
        for semana in (s for s in lista if s >= comeco):
            caminho = raiz_p / f"semana={semana}" / f"fonte={fonte}"
            if not caminho.is_dir():
                anunciadas_antes = set()
                continue
            p = pd.read_parquet(caminho, columns=["chave_snapshot", "nome", "lat", "lng"])
            p = p.dropna(subset=["chave_snapshot"]).drop_duplicates("chave_snapshot")
            p["chave_snapshot"] = p["chave_snapshot"].astype(str)
            # Entrada só conta DEPOIS da primeira semana da janela; saída, até a penúltima.
            usadas = set(
                vida.loc[
                    ((vida["primeira"] == semana) & (semana != comeco))
                    | ((vida["ultima"] == semana) & (vida["ultima"] != ult)),
                    "chave_snapshot",
                ]
            )
            if semana != comeco:
                daqui = tabela_voltas[(tabela_voltas["fonte"] == fonte) & (tabela_voltas["semana"] == semana)]
                usadas |= set(daqui["chave_snapshot"])
            # A ausência temporária precisa do nome e da coordenada da última semana em que apareceu.
            antes_de_sumir = tabela_ausencias[
                (tabela_ausencias["fonte"] == fonte) & (tabela_ausencias["anterior"] == semana)
            ]
            usadas |= set(antes_de_sumir["chave_snapshot"])
            manter = p["chave_snapshot"].isin(usadas)
            if fonte == FONTE_CADASTRO:
                marca = p["nome"].map(anunciada).astype(bool)
                manter = manter | marca | p["chave_snapshot"].isin(anunciadas_antes)
                anunciadas_antes = set(p.loc[marca, "chave_snapshot"])
            pontes.append(p[manter].assign(fonte=fonte, semana=semana))
    ponte = (
        pd.concat(pontes, ignore_index=True)
        if pontes
        else pd.DataFrame(columns=["chave_snapshot", "nome", "lat", "lng", "fonte", "semana"])
    )
    tamanho_rede = (
        pd.concat(tamanhos, ignore_index=True)
        if tamanhos
        else pd.DataFrame(columns=["fonte", "semana", "rede", "n"])
    )
    return Serie(semanas, inicio, datas, chaves, tamanho_rede, tamanho_fonte, ponte, tabela_voltas, tabela_ausencias)


def _pares(
    saidas: pd.DataFrame, entradas: pd.DataFrame, *, limite_m: float, por_rede: bool, exigir_nome: bool
) -> list[tuple[Any, Any]]:
    """Pares (saída, entrada) da mesma unidade, um para um, do mais perto ao mais longe.

    `por_rede` só casa dentro da mesma rede (cadastro); `exigir_nome` pede um termo próprio do nome
    em comum (Wellhub, onde a `rede` vem quase sempre nula).
    """
    if not len(saidas) or not len(entradas):
        return []
    candidatos: list[tuple[float, Any, Any]] = []
    lat_e = entradas["lat"].to_numpy(dtype=float)
    lng_e = entradas["lng"].to_numpy(dtype=float)
    rede_e = entradas["rede"].astype("string").fillna("").to_numpy()
    termos_e: dict[Any, set[str]] = {}
    for i, s in saidas.iterrows():
        d = _distancias_m(float(s["lat"]), float(s["lng"]), lat_e, lng_e)
        perto = np.isfinite(d) & (d <= limite_m)
        if por_rede:
            perto &= rede_e == ("" if pd.isna(s["rede"]) else str(s["rede"]))
        if not perto.any():
            continue
        termos_s = _termos_proprios(s["nome"]) if exigir_nome else set()
        for k in np.flatnonzero(perto):
            j = entradas.index[k]
            if exigir_nome:
                if j not in termos_e:
                    termos_e[j] = _termos_proprios(entradas.at[j, "nome"])
                if not termos_s & termos_e[j]:
                    continue
            candidatos.append((float(d[k]), i, j))
    usados_s: set[Any] = set()
    usados_e: set[Any] = set()
    pares: list[tuple[Any, Any]] = []
    for _, i, j in sorted(candidatos, key=lambda c: c[0]):
        if i in usados_s or j in usados_e:
            continue
        usados_s.add(i)
        usados_e.add(j)
        pares.append((i, j))
    return pares


def _com_ponte(quadro: pd.DataFrame, ponte: pd.DataFrame, semana: str) -> pd.DataFrame:
    """Acrescenta nome e coordenada da `semana`; quem não tem coordenada não vira evento."""
    if not len(quadro):
        return quadro.assign(nome=pd.Series(dtype="string"), lat=pd.Series(dtype=float), lng=pd.Series(dtype=float))
    daquela = ponte[ponte["semana"] == semana][["chave_snapshot", "nome", "lat", "lng"]]
    juntos = quadro.merge(daquela, on="chave_snapshot", how="left")
    juntos["lat"] = pd.to_numeric(juntos["lat"], errors="coerce")
    juntos["lng"] = pd.to_numeric(juntos["lng"], errors="coerce")
    return juntos.dropna(subset=["lat", "lng"]).reset_index(drop=True)


def _evento(fonte: str, tipo: str, linha: Any, de: str, ate: str) -> dict[str, Any]:
    rede = linha["rede"]
    return {
        "fonte": fonte,
        "tipo": tipo,
        "confianca": CONFIANCA,
        "rede": None if pd.isna(rede) else str(rede),
        "nome": None if pd.isna(linha["nome"]) else str(linha["nome"]),
        "lat": float(linha["lat"]),
        "lng": float(linha["lng"]),
        "de": de,
        "ate": ate,
    }


def _mascara(quadro: pd.DataFrame, valores: Iterable[bool]) -> pd.Series:
    """Máscara `bool` explícita: vazia, ela viria `object` e o pandas a leria como lista de COLUNAS."""
    return pd.Series(list(valores), index=quadro.index, dtype=bool)


def eventos_da_serie(serie: Serie | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Eventos da janela (da primeira semana com ponte à última coletada) e o laudo do que ficou fora.

    Devolve `(eventos, laudo)`. `eventos` tem as colunas do pacote (`COLUNAS`), com `fonte` =
    `cadastro` (abertura, inauguração, fechamento), `em_breve` (pipeline na última semana) ou
    `wellhub` (entrou/saiu do agregador). Cada evento semanal tem `de`/`ate` = datas das duas
    coletas entre as quais ele aconteceu. O pipeline vai da primeira semana da chave na janela até a
    última. O `laudo` traz a janela por fonte e o que as regras 3 a 5 tiraram da conta: fechamentos
    pendentes POR REDE (`{fonte: {rede ou "": n}}`, para a tela tirar estúdios), recalibrações e
    saltos de cobertura.
    """
    vazio = pd.DataFrame({c: pd.Series(dtype="string") for c in COLUNAS}).astype({"lat": float, "lng": float})
    laudo: dict[str, Any] = {
        "janela": {},
        "pendentes": {},
        "recalibracoes": [],
        "cobertura_redes": [],
        "cobertura_agregador": [],
    }
    if serie is None:
        return vazio, laudo
    eventos: list[dict[str, Any]] = []
    for fonte in FONTES:
        if fonte not in serie.inicio:
            continue
        cadastro = fonte == FONTE_CADASTRO
        lista = serie.semanas[fonte]
        janela = [s for s in lista if s >= serie.inicio[fonte]]
        ult = lista[-1]
        laudo["janela"][fonte] = {
            "de": serie.datas[(fonte, janela[0])],
            "ate": serie.datas[(fonte, ult)],
            "semanas": len(janela),
        }
        pendentes: dict[str, int] = {}
        laudo["pendentes"][fonte] = pendentes
        pos = {s: i for i, s in enumerate(lista)}
        vida = serie.chaves[serie.chaves["fonte"] == fonte]
        # Regra 7: a chave de uma semana só fica no casamento (desfaz troca em duas etapas), mas
        # nunca vira evento.
        pisca = set(vida.loc[(vida["primeira"] == vida["ultima"]) & (vida["ultima"] != ult), "chave_snapshot"])
        ponte = serie.ponte[serie.ponte["fonte"] == fonte]
        voltas = serie.voltas[serie.voltas["fonte"] == fonte] if len(serie.voltas) else serie.voltas
        ausencias = serie.ausencias[serie.ausencias["fonte"] == fonte] if len(serie.ausencias) else serie.ausencias
        estreia: dict[str, str] = {}
        tam_rede = serie.tamanho_rede[serie.tamanho_rede["fonte"] == fonte] if len(serie.tamanho_rede) else serie.tamanho_rede
        if cadastro and len(tam_rede):
            estreia = tam_rede.groupby("rede")["semana"].min().to_dict()
        for anterior, semana in zip(janela, janela[1:], strict=False):
            de, ate = serie.datas[(fonte, anterior)], serie.datas[(fonte, semana)]
            abre = vida[vida["primeira"] == semana]
            fecha = vida[vida["ultima"] == anterior]
            volta = voltas[voltas["semana"] == semana][["chave_snapshot", "rede"]] if len(voltas) else voltas
            aus = ausencias[ausencias["semana"] == semana][["chave_snapshot", "rede"]] if len(ausencias) else ausencias
            tam_antes = (
                tam_rede[tam_rede["semana"] == anterior].set_index("rede")["n"] if len(tam_rede) else pd.Series(dtype=int)
            )
            if cadastro:
                abre = abre.loc[_mascara(abre, (estreia.get(str(r), semana) < semana for r in abre["rede"]))]  # regra 2
                entradas_por_rede = pd.concat([abre["rede"], volta["rede"]]).value_counts()
                saidas_brutas = pd.concat([fecha["rede"], aus["rede"]]).value_counts()
                recalibradas = []
                for rede in sorted(set(entradas_por_rede.index) & set(saidas_brutas.index)):
                    unidades = int(tam_antes.get(rede, 0))
                    trocas = int(min(entradas_por_rede[rede], saidas_brutas[rede]))
                    if unidades >= REDE_MIN_RECALIBRACAO and trocas >= FRACAO_RECALIBRACAO * unidades:
                        recalibradas.append(rede)
                        laudo["recalibracoes"].append(
                            {"rede": str(rede), "de": de, "ate": ate, "trocas": trocas, "unidades": unidades}
                        )
                abre = abre[~abre["rede"].isin(recalibradas)]  # regra 4
                fecha = fecha[~fecha["rede"].isin(recalibradas)]
                volta = volta[~volta["rede"].isin(recalibradas)]
                aus = aus[~aus["rede"].isin(recalibradas)]
            a = _com_ponte(abre.assign(_volta=False), ponte, semana)
            v = _com_ponte(volta.assign(_volta=True), ponte, semana)
            entradas = pd.concat([a, v], ignore_index=True) if len(v) else a
            # Lado de saída: quem saiu de vez (`fecha`) e quem faltou só por um tempo (`aus`); a
            # ausência temporária desfaz par de troca, mas nunca vira fechamento.
            f = _com_ponte(fecha.assign(_ausente=False), ponte, anterior)
            au = _com_ponte(aus.assign(_ausente=True), ponte, anterior)
            saidas = pd.concat([f, au], ignore_index=True) if len(au) else f
            pares = _pares(
                saidas,
                entradas,
                limite_m=DIST_TROCA_CADASTRO_M if cadastro else DIST_TROCA_NOME_AGREGADOR_M,
                por_rede=cadastro,
                exigir_nome=not cadastro,
            )  # regra 1
            casadas_s = {i for i, _ in pares}
            casadas_e = {j for _, j in pares}
            # Quem volta só serve para desfazer par: nunca é abertura (regra 2).
            fora_e = casadas_e | {j for j in entradas.index if bool(entradas.at[j, "_volta"])}
            novas = entradas.loc[
                _mascara(
                    entradas,
                    (
                        j not in fora_e
                        and entradas.at[j, "chave_snapshot"] not in pisca
                        and not (cadastro and anunciada(entradas.at[j, "nome"]))
                        for j in entradas.index
                    ),
                )
            ]
            # Saídas DE VEZ sem par (a ausência temporária volta, não é saída).
            soltas_s = saidas.loc[
                _mascara(saidas, (i not in casadas_s and not bool(saidas.at[i, "_ausente"]) for i in saidas.index))
            ]
            if cadastro:
                # Regra 4, a outra metade: rede que CRESCE de uma vez (líquido) é o coletor passando a
                # achar mais páginas dela. Depois da regra 1, para a troca de chave não contar.
                saidas_por_rede = soltas_s["rede"].value_counts()
                for rede, grupo in novas.groupby("rede"):
                    unidades = int(tam_antes.get(rede, 0))
                    liquido = len(grupo) - int(saidas_por_rede.get(rede, 0))
                    if liquido >= SALTO_REDE_MIN and liquido >= FRACAO_SALTO_REDE * unidades:
                        laudo["cobertura_redes"].append(
                            {"rede": str(rede), "de": de, "ate": ate, "entradas": len(grupo), "unidades": unidades}
                        )
                        fora_e |= set(grupo.index)
            else:
                # Regra 5 DEPOIS da regra 1: na semana do salto o coletor também troca chaves, e
                # cortar as entradas antes de casar deixava as saídas dessas trocas soltas (medido:
                # 180 saídas em 07/11, contra 51 depois de casar).
                base = int(serie.tamanho_fonte.get((fonte, anterior), 0))
                for sentido, quadro, cortadas in (("entradas", novas, fora_e), ("saidas", soltas_s, casadas_s)):
                    if base and len(quadro) > FRACAO_COBERTURA_AGREGADOR * base:  # regra 5
                        laudo["cobertura_agregador"].append(
                            {"de": de, "ate": ate, "sentido": sentido, "n": int(len(quadro)), "base": base}
                        )
                        cortadas |= set(quadro.index)
            inauguradas = {
                j
                for i, j in pares
                if cadastro
                and not bool(entradas.at[j, "_volta"])
                and not bool(saidas.at[i, "_ausente"])
                and anunciada(saidas.at[i, "nome"])
                and not anunciada(entradas.at[j, "nome"])
            }
            for j, linha in entradas.iterrows():
                if j in inauguradas:
                    eventos.append(_evento("cadastro", "inauguracao", linha, de, ate))
                elif j in novas.index and j not in fora_e:
                    tipo = ("cadastro", "abertura") if cadastro else ("wellhub", "entrou_agregador")
                    eventos.append(_evento(tipo[0], tipo[1], linha, de, ate))
            for i, linha in saidas.iterrows():
                if i in casadas_s or bool(linha["_ausente"]) or linha["chave_snapshot"] in pisca:
                    continue
                if cadastro and anunciada(linha["nome"]):  # regra 6: anúncio que some não fecha
                    continue
                if pos[ult] - pos[anterior] < SEMANAS_PARA_FECHAR:  # regra 3
                    chave_rede = "" if pd.isna(linha["rede"]) else str(linha["rede"])
                    pendentes[chave_rede] = pendentes.get(chave_rede, 0) + 1
                else:
                    tipo = ("cadastro", "fechamento") if cadastro else ("wellhub", "saiu_agregador")
                    eventos.append(_evento(tipo[0], tipo[1], linha, de, ate))
            if cadastro:  # regra 6: perdeu o marcador com a MESMA chave
                antes = ponte[(ponte["semana"] == anterior) & ponte["nome"].map(anunciada).astype(bool)]
                depois = ponte[(ponte["semana"] == semana) & ~ponte["nome"].map(anunciada).astype(bool)]
                mesmas = depois[depois["chave_snapshot"].isin(set(antes["chave_snapshot"]))]
                if len(mesmas):
                    mesmas = mesmas.merge(vida[["chave_snapshot", "rede"]], on="chave_snapshot", how="inner")
                    for _, linha in mesmas.dropna(subset=["lat", "lng"]).iterrows():
                        eventos.append(_evento("cadastro", "inauguracao", linha, de, ate))
        if cadastro:  # regra 6: o pipeline é o que segue anunciado na última semana
            ainda = ponte[(ponte["semana"] == ult) & ponte["nome"].map(anunciada).astype(bool)]
            ainda = ainda.merge(vida[["chave_snapshot", "rede", "primeira"]], on="chave_snapshot", how="inner")
            for _, linha in ainda.dropna(subset=["lat", "lng"]).iterrows():
                desde = max(str(linha["primeira"]), janela[0])
                eventos.append(
                    _evento("em_breve", "em_breve", linha, serie.datas.get((fonte, desde), desde), serie.datas[(fonte, ult)])
                )
    if not eventos:
        return vazio, laudo
    quadro = pd.DataFrame(eventos, columns=list(COLUNAS))
    for c in ("fonte", "tipo", "confianca", "rede", "nome", "de", "ate"):
        quadro[c] = quadro[c].astype("string")
    return quadro, laudo


def _fora(excluir: Iterable[str]) -> set[str]:
    return {str(r).lower() for r in excluir} | {"ultra"}


def resumo_por_rede(eventos: pd.DataFrame | None, excluir: Iterable[str] = ()) -> dict[str, dict[str, int]]:
    """Aberturas (com inaugurações), fechamentos, saldo e "Em breve" de cada rede, na série."""
    if eventos is None or not len(eventos):
        return {}
    fora = _fora(excluir)
    cad = eventos[eventos["fonte"].isin(["cadastro", "em_breve"]) & eventos["rede"].notna()]
    saida: dict[str, dict[str, int]] = {}
    for rede, g in cad.groupby("rede"):
        if str(rede).lower() in fora:
            continue
        abre = int(g["tipo"].isin(["abertura", "inauguracao"]).sum())
        fecha = int(g["tipo"].eq("fechamento").sum())
        saida[str(rede)] = {
            "aberturas": abre,
            "fechamentos": fecha,
            "saldo": abre - fecha,
            "em_breve": int(g["tipo"].eq("em_breve").sum()),
        }
    return saida


def redes_da_serie(serie: Serie | None) -> set[str]:
    """Redes de cadastro que a série enxerga desde a PRIMEIRA semana da janela.

    Nelas, zero quer dizer "não mexeu". Rede que só passou a ser coletada no meio da janela não
    entra: zero ali afirmaria que ela ficou parada num período em que a série não a enxergava.
    """
    if serie is None or FONTE_CADASTRO not in serie.inicio or not len(serie.tamanho_rede):
        return set()
    tam = serie.tamanho_rede
    no_inicio = (tam["fonte"] == FONTE_CADASTRO) & (tam["semana"] == serie.inicio[FONTE_CADASTRO])
    return {str(r) for r in tam.loc[no_inicio, "rede"]}


def bloco_do_card(
    eventos: pd.DataFrame | None,
    laudo: Mapping[str, Any],
    redes_observadas: Iterable[str],
    *,
    excluir: Iterable[str] = (),
) -> dict[str, Any]:
    """O bloco `semanal` do card "Crescimento da concorrência": janela, agregador e o que ficou fora.

    `excluir` (estúdios boutique, DEC-056) e a Ultra saem também do laudo: o rodapé não cita rede
    que a tabela não mostra, nem conta pendente que nunca vai aparecer como fechamento.
    """
    janela = dict(laudo.get("janela") or {})
    cad = janela.get(FONTE_CADASTRO)
    agr = janela.get(FONTE_AGREGADOR)
    if not cad and not agr:
        return {"disponivel": False}
    fora = _fora(excluir)
    agregadores = resumo_agregadores(eventos)
    for linha in agregadores:
        if agr:
            linha["de"], linha["ate"] = agr["de"], agr["ate"]
    if agr and not agregadores:
        # Janela sem nenhuma entrada ou saída ainda é leitura: zero, e não "sem dado".
        agregadores = [
            {"agregador": FONTE_AGREGADOR, "grupo": g, "entradas": 0, "saidas": 0, "saldo": 0, "de": agr["de"], "ate": agr["ate"]}
            for g in ("independentes", "redes")
        ]
    pendentes = {
        fonte: sum(int(n) for rede, n in dict(por_rede or {}).items() if str(rede).lower() not in fora)
        for fonte, por_rede in dict(laudo.get("pendentes") or {}).items()
    }
    return {
        "disponivel": True,
        "de": (cad or agr or {}).get("de"),
        "ate": (cad or agr or {}).get("ate"),
        "semanas": int((cad or agr or {}).get("semanas") or 0),
        "agregador_de": agr["de"] if agr else None,
        "agregador_ate": agr["ate"] if agr else None,
        "agregadores": agregadores,
        "redes_observadas": sorted({str(r) for r in redes_observadas if str(r).lower() not in fora}),
        "pendentes": pendentes,
        "recalibracoes": [r for r in laudo.get("recalibracoes") or [] if str(r["rede"]).lower() not in fora],
        "cobertura_redes": [r for r in laudo.get("cobertura_redes") or [] if str(r["rede"]).lower() not in fora],
        "cobertura_agregador": list(laudo.get("cobertura_agregador") or []),
    }


def assinatura_da_serie(staging: Path | str) -> tuple[tuple[str, int, int], ...]:
    """Identidade da série no disco (arquivo, `mtime` e tamanho): a chave do cache da tela.

    O lote de domingo grava a semana nova e a ponte dela; a assinatura muda e a tela relê na chamada
    seguinte, sem esperar restart. É por ARQUIVO, não por diretório: o `mtime` da pasta fica no
    instante em que o arquivo nasce, e uma leitura no meio da escrita (falha) ficaria presa no cache
    com a mesma chave de depois. Sem série, tupla vazia.
    """
    base = Path(staging)
    itens: list[tuple[str, int, int]] = []
    for raiz in (DIR_SNAPSHOTS, DIR_PONTE):
        for particao in sorted((base / raiz).glob("semana=*/fonte=*")):
            try:
                arquivos = sorted(particao.iterdir())
            except OSError:
                continue
            for arquivo in arquivos:
                try:
                    st = arquivo.stat()
                except OSError:
                    continue
                # Caminho ABSOLUTO: dois staging com a mesma árvore não dividem a mesma chave.
                itens.append((str(arquivo), st.st_mtime_ns, st.st_size))
    return tuple(itens)


def anexar_ao_card(
    payload: Mapping[str, Any], movimento: Mapping[str, Any] | None, *, excluir: Iterable[str] = ()
) -> dict[str, Any]:
    """Acrescenta a série ao card montado por `crescimento_por_rede`, sem mexer no que veio do pacote.

    Cada linha ganha `semanal` (`{aberturas, fechamentos, saldo, em_breve}`). Rede que mexeu na série
    leva os números; rede parada leva zeros se a série a enxerga desde o início da janela, e `None`
    se não (a tela mostra "—", nunca 0). Rede que só a série conhece entra no fim, sem leitura do
    pacote. O payload ganha o bloco `semanal` (`bloco_do_card`). Com a série disponível, o card está
    disponível mesmo sem pacote e sem contagem.
    """
    eventos = (movimento or {}).get("eventos")
    laudo = (movimento or {}).get("laudo") or {}
    observadas = {str(r) for r in (movimento or {}).get("redes") or ()}
    bloco = bloco_do_card(eventos, laudo, observadas, excluir=excluir)
    saida = dict(payload)
    saida["semanal"] = bloco
    linhas = [dict(linha) for linha in payload.get("redes") or []]
    if not bloco.get("disponivel"):
        for linha in linhas:
            linha["semanal"] = None
        saida["redes"] = linhas
        return saida
    resumo = resumo_por_rede(eventos, excluir)
    fora = _fora(excluir)
    zero = {"aberturas": 0, "fechamentos": 0, "saldo": 0, "em_breve": 0}
    vistas: set[str] = set()
    for linha in linhas:
        rede = str(linha["rede"])
        vistas.add(rede)
        if rede in resumo:
            linha["semanal"] = dict(resumo[rede])
        else:
            linha["semanal"] = dict(zero) if rede in observadas else None
    for rede in sorted(set(resumo) - vistas):
        if rede.lower() in fora:
            continue
        linhas.append(
            {
                "rede": rede,
                "aberturas": 0,
                "aberturas_conferidas": 0,
                "fechamentos": 0,
                "fechamentos_conferidos": 0,
                "em_breve": 0,
                "saldo": 0,
                "unidades": None,
                "variacao": None,
                "variacao_status": None,
                "lido": None,
                "sem_cadastro": "fora_da_cobertura" if payload.get("tem_cadastro") else None,
                "semanal": dict(resumo[rede]),
            }
        )
    saida["redes"] = linhas
    saida["disponivel"] = True
    return saida
