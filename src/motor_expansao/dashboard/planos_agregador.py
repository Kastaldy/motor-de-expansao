"""Planos dos agregadores (TotalPass e Wellhub) por academia — o posicionamento de preço.

O CSV do coletor (`unidades_totalpass.csv`) traz, por academia, o PLANO do TotalPass que o
aluno precisa ter para frequentá-la (`TP GO`, `TP 1`, `TP 1+`... `TP 7`) e o preço desse plano.

**O que este número É e o que NÃO é.** O preço é da ASSINATURA do TotalPass exigida, e é
fixo por nível (TP 1 = R$ 109,90 em 3.989 de 3.989 linhas, medido na coleta de 2026-09-10).
Ele NÃO é o ticket de balcão da academia. O que ele mede é POSICIONAMENTO: uma academia em
`TP 4` está, para o agregador, na mesma prateleira das premium; uma em `TP 1`, na das
low-cost. É por isso que serve para ler a concorrência de preço de uma Ultra.

O Wellhub (`unidades_wellhub_<uf>.csv`, um por UF) segue a mesma lógica com outra régua: o
`tier_wellhub` (`Starter`, `Basic`... `Diamond+`) e o preço do plano do Wellhub que dá acesso.
As duas fontes ficam em artefatos SEPARADOS: são réguas diferentes e não se comparam nível a nível.

Camada visual e READ-ONLY sobre o M1: nenhum score, ranking ou artefato oficial é tocado.
Funções puras; quem lê e grava arquivo é o script de ingestão e o piloto.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd

#: Nome do artefato do TotalPass no staging (o do Wellhub vem de `arquivo_staging`).
ARQUIVO_STAGING = "planos_totalpass.parquet"

#: Contrato de cada fonte: arquivo no staging e as colunas de plano, preço e modalidades do CSV.
FONTES: dict[str, dict[str, str]] = {
    "totalpass": {
        "arquivo": ARQUIVO_STAGING,
        "plano": "plano_totalpass",
        "preco": "preco_plano_totalpass",
        "modalidades": "modalidades",
    },
    "wellhub": {
        "arquivo": "planos_wellhub.parquet",
        "plano": "tier_wellhub",
        "preco": "preco_tier_wellhub",
        "modalidades": "atividades",
    },
}

COLUNAS_OBRIGATORIAS = (
    "slug",
    "nome",
    "latitude",
    "longitude",
    "uf",
    "plano_totalpass",
    "preco_plano_totalpass",
    "data_coleta",
)


def _fonte(fonte: str) -> dict[str, str]:
    if fonte not in FONTES:
        raise ValueError(f"fonte de planos desconhecida: {fonte!r} (esperado: {sorted(FONTES)})")
    return FONTES[fonte]


def arquivo_staging(fonte: str) -> str:
    """Nome do parquet da fonte no staging."""
    return _fonte(fonte)["arquivo"]


def colunas_obrigatorias(fonte: str) -> tuple[str, ...]:
    f = _fonte(fonte)
    return ("slug", "nome", "latitude", "longitude", "uf", f["plano"], f["preco"], "data_coleta")

#: `TP Free` sai a R$ 1,00 (10 linhas na coleta de 2026-09-10) e o `Digital` do Wellhub a R$ 0:
#: plano de teste ou só aplicativo, não preço de acesso.
#: Abaixo deste piso o preço vira nulo — um R$ 1,00 puxaria a mediana do entorno para baixo.
PRECO_MINIMO_VALIDO = 10.0

RAIO_ENTORNO_M = 2_000.0
#: A própria Ultra no feed casa com a coordenada da unidade a até esta distância.
CASAR_PROPRIA_M = 120.0
#: Pino do mapa casa com a linha do agregador a até esta distância.
CASAR_PINO_M = 60.0

#: Vocabulário "V2" de musculação da DEC-025, sobre a string de modalidades normalizada
#: (NFKD, sem acento, minúscula). O termo base é o PREFIXO `muscula` — cobre "musculação" e
#: "muscular" —, e não a palavra inteira; foi assim que a emenda 1 daquela DEC o estendeu ao
#: TotalPass.
#:
#: Existe porque entre maio e agosto de 2026 o WellHub RENOMEOU a taxonomia: "Musculação"
#: praticamente desapareceu e virou "Treino de força", "Fisiculturismo" e "Treino Híbrido".
#: Procurar a substring literal é uma falha SILENCIOSA — a coluna continua lá, só nasce
#: errada. Medido em 2026-09-28 sobre os dois parquets que a produção serve: o WellHub
#: marcava 19.142 de 22.091 linhas (86,65%) e o V2 marca 22.091 (100,00%) — **+2.949
#: academias, 13,35% do feed**, que somem quando o piloto filtra `somente_musculacao=True`;
#: o TotalPass ia de 17.220 de 17.602 (97,83%) para 17.602, **+382**. **Zero linhas
#: perdidas** nos dois: V2 é superconjunto de V1, não é troca de régua.
#:
#: A DEC-025 escolheu o V2 como joelho da curva: V1->V2 recupera +134 unidades de maio por
#: +175 linhas, e V2->V3 custa +2.831 para recuperar +8 e ainda arrasta box de CrossFit como
#: se fosse academia de musculação.
VOCABULARIO_MUSCULACAO_V2: tuple[str, ...] = (
    "muscula",
    "treino de forca",
    "fisiculturismo",
    "levantamento de peso",
    "treino hibrido",
)

#: Palavra que, logo DEPOIS de "ultra", diz que a academia é de OUTRA marca. Ver `_e_ultra`.
_GENERICOS_DEPOIS_DE_ULTRA = frozenset(
    {"fit", "fitness", "fitcamp", "fitclub", "gym", "box", "life", "team", "sport", "sports"}
)

#: "ultra" como PALAVRA (nunca dentro de `ultrafit`/`ultrabox`) e a palavra logo depois dela.
#: O `[^a-z0-9]*` no meio come espaço, hífen e barra: "ULTRA - Brasilândia" tem de ler
#: "brasilandia", e "Ultra-Fit" tem de ler "fit".
_PALAVRA_ULTRA = re.compile(r"\bultra\b[^a-z0-9]*(?P<seguinte>[a-z0-9]*)")


def _sem_acento(texto: object) -> str:
    bruto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in bruto if not unicodedata.combining(c)).lower()


def _distancias_m(lat: float, lng: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    raio_terra = 6_371_008.8
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lngs - lng) / 2) ** 2
    return 2 * raio_terra * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def tem_musculacao(modalidades: object) -> bool:
    """True se a string de modalidades/atividades oferece musculação, pelo V2 da DEC-025.

    Vale para as DUAS fontes. Uma régua por fonte seria a mesma taxonomia lida de dois
    jeitos: o WellHub e o TotalPass se renomeiam no tempo, não entre si.
    """
    texto = _sem_acento(modalidades)
    return any(termo in texto for termo in VOCABULARIO_MUSCULACAO_V2)


def _num(valor: Any, casas: int = 2) -> float | None:
    try:
        x = float(valor)
    except (TypeError, ValueError):
        return None
    return round(x, casas) if np.isfinite(x) else None


def normalizar(bruto: pd.DataFrame, fonte: str = "totalpass") -> pd.DataFrame:
    """CSV cru da `fonte` -> quadro do staging. Levanta `ValueError` se faltar coluna do contrato.

    Sai uma linha por academia com coordenada numérica. Preço abaixo de
    `PRECO_MINIMO_VALIDO` fica nulo (o plano continua, o preço não).
    """
    f = _fonte(fonte)
    faltam = [c for c in colunas_obrigatorias(fonte) if c not in bruto.columns]
    if faltam:
        raise ValueError(f"CSV do {fonte} sem as colunas {faltam}")

    preco = pd.to_numeric(bruto[f["preco"]].astype(str).str.replace(",", "."), errors="coerce")
    col_mod = f["modalidades"]
    modalidades = bruto[col_mod].fillna("") if col_mod in bruto.columns else pd.Series("", index=bruto.index)
    saida = pd.DataFrame(
        {
            "slug": bruto["slug"].astype(str),
            "nome": bruto["nome"].astype(str).str.strip(),
            "lat": pd.to_numeric(bruto["latitude"], errors="coerce"),
            "lng": pd.to_numeric(bruto["longitude"], errors="coerce"),
            "cidade": bruto["cidade"].astype(str) if "cidade" in bruto.columns else "",
            "uf": bruto["uf"].astype(str).str.upper().str.strip(),
            "modalidades": modalidades.astype(str),
            "musculacao": modalidades.map(tem_musculacao),
            "plano": bruto[f["plano"]].astype(str).str.strip(),
            "preco": preco.where(preco >= PRECO_MINIMO_VALIDO),
            "data_coleta": bruto["data_coleta"].astype(str),
        }
    )
    saida = saida.dropna(subset=["lat", "lng"])
    return saida.drop_duplicates("slug").reset_index(drop=True)


def padrao_de_redes(slugs: Iterable[str]) -> str | None:
    """Regex que casa o NOME de uma academia do feed com uma lista de slugs de rede.

    O feed do agregador não tem slug de rede, só o nome ("Tonus Gym / Vidya Studio - Asa Sul").
    `vidya_studio` vira `\\bvidya\\s*studio\\b`: casa com espaço, sem espaço e sem acento de
    diferença de caixa. Lista vazia devolve `None` (nada a excluir).
    """
    partes = [r"\s*".join(re.escape(p) for p in str(s).split("_") if p) for s in slugs]
    partes = [p for p in partes if p]
    return rf"\b(?:{'|'.join(sorted(partes))})\b" if partes else None


def e_ultra(nome: object) -> bool:
    """True se a listagem do agregador é uma unidade da própria Ultra.

    A regra antiga exigia a expressão "ultra academia" e perdia **9 das nossas unidades** no
    feed do WellHub — medido em 2026-09-28 sobre o parquet que a produção serve: `Ultra
    Sagrada Família`, `ULTRA TAGUATINGA SUL`, `Ultra Guarapari`, `ULTRA UNAI`, `Ultra Jardim
    das Américas`, `Ultra André de Barros`, `Ultra Vila Guanabara`, `Ultra Berrini` e `Ultra
    Villa Branca` (no TotalPass, `ULTRA SÃO GONÇALO`). O dano é duplo: a unidade não acha o
    PRÓPRIO plano, e pior, entra na lista de CONCORRENTES da Ultra vizinha — a rede
    disputando preço com ela mesma.

    Não dá para casar só pela palavra "ultra": o feed tem marcas alheias de verdade
    (`Academia Ultra Fit`, `Ultra Fitness`, `Ultra FitCamp`, `Edu Ultra Team`, `Academia VO2
    MAX Ultra`). O que separa os dois grupos é o que vem DEPOIS de "ultra": nas nossas é
    sempre um LUGAR (o nome da unidade); nas alheias, uma palavra genérica de academia.

    Por isso a régua é a palavra "ultra" seguida de algo que NÃO seja genérico — e seguida de
    algo: "Academia VO2 MAX Ultra" termina em "ultra" e não é nossa. É uma lista de
    CATEGORIA, não de marca, e é isso que a faz envelhecer devagar: nome de unidade nossa não
    usa "fit"/"gym"/"box". `Ultrabox` e `Ultrafit` numa palavra só nem chegam aqui, porque
    `\\bultra\\b` não casa dentro de palavra.

    Risco medido antes de alargar: a marca alheia com "ultra" mais PRÓXIMA de uma Ultra
    Academia está a **5.996 m** no WellHub e a **7.153 m** no TotalPass. Nenhuma entra nos
    120 m do casamento da própria, e nenhuma entra nem nos 2.000 m do raio de concorrência.
    """
    # `finditer`, e não `search`: o feed junta duas academias num nome só ("Academia Ultra
    # Fitness / Roofbox Crossfit Arrecife"), e basta UMA ocorrência ser nossa.
    return any(
        achado.group("seguinte")
        and achado.group("seguinte") not in _GENERICOS_DEPOIS_DE_ULTRA
        for achado in _PALAVRA_ULTRA.finditer(_sem_acento(nome))
    )


def _e_ultra(nomes: pd.Series) -> pd.Series:
    return nomes.map(e_ultra)


def planos_no_entorno(
    lat: float,
    lng: float,
    planos: pd.DataFrame,
    *,
    raio_m: float = RAIO_ENTORNO_M,
    casar_m: float = CASAR_PROPRIA_M,
    excluir_nomes: str | None = None,
    somente_musculacao: bool = False,
) -> dict[str, Any]:
    """O nível da própria Ultra no TotalPass e o das academias a até `raio_m`.

    A Ultra é a linha "Ultra Academia" mais próxima a até `casar_m`; qualquer outra Ultra do
    raio sai da concorrência (é da rede, não disputa preço com ela). A comparação
    mais barata / mesmo nível / mais cara só existe quando a própria Ultra tem preço.

    `excluir_nomes` (regex, sem caixa) tira da CONCORRÊNCIA as academias cujo nome casa —
    o piloto passa os estúdios boutique da DEC-056. `somente_musculacao` deixa só quem
    oferece musculação: estúdio independente de yoga ou pilates não disputa o aluno da Ultra.
    `media_preco` é a média simples do preço do plano entre as concorrentes com preço.
    """
    base = planos.dropna(subset=["lat", "lng"])
    vazio: dict[str, Any] = {
        "ultra": None, "academias": [], "distribuicao": [], "total": 0,
        "mais_baratas": None, "mesmo_nivel": None, "mais_caras": None, "mediana_preco": None,
        "media_preco": None, "n_com_preco": 0,
    }
    if not len(base):
        return vazio
    d = _distancias_m(lat, lng, base["lat"].to_numpy(), base["lng"].to_numpy())
    perto = base[d <= raio_m].assign(dist_m=d[d <= raio_m])
    if not len(perto):
        return vazio

    ultra_mask = _e_ultra(perto["nome"])
    candidatas = perto[ultra_mask & (perto["dist_m"] <= casar_m)].sort_values("dist_m")
    propria = candidatas.iloc[0] if len(candidatas) else None
    fora = ultra_mask
    if excluir_nomes:
        fora = fora | perto["nome"].astype(str).str.contains(excluir_nomes, case=False, regex=True)
    if somente_musculacao:
        fora = fora | ~perto["musculacao"].astype(bool)
    conc = perto[~fora].sort_values(["preco", "dist_m"], na_position="last", kind="stable")

    academias = [
        {
            "nome": str(r.nome),
            "plano": str(r.plano),
            "preco": _num(r.preco),
            "distancia_m": _num(r.dist_m, 0),
            "musculacao": bool(r.musculacao),
        }
        for r in conc.itertuples(index=False)
    ]
    com_preco = conc.dropna(subset=["preco"])
    distribuicao = [
        {"plano": str(plano), "preco": _num(preco), "n": int(n)}
        for (plano, preco), n in com_preco.groupby(["plano", "preco"]).size().sort_index(level=1).items()
    ]
    saida = {
        **vazio,
        "academias": academias,
        "distribuicao": distribuicao,
        "total": len(conc),
        "mediana_preco": _num(com_preco["preco"].median()) if len(com_preco) else None,
        "media_preco": _num(com_preco["preco"].mean()) if len(com_preco) else None,
        "n_com_preco": len(com_preco),
    }
    if propria is not None:
        saida["ultra"] = {
            "nome": str(propria["nome"]),
            "plano": str(propria["plano"]),
            "preco": _num(propria["preco"]),
        }
        preco_ultra = propria["preco"]
        if pd.notna(preco_ultra) and len(com_preco):
            saida["mais_baratas"] = int((com_preco["preco"] < preco_ultra).sum())
            saida["mesmo_nivel"] = int((com_preco["preco"] == preco_ultra).sum())
            saida["mais_caras"] = int((com_preco["preco"] > preco_ultra).sum())
    return saida


def anexar_planos(
    pinos: list[dict[str, Any]],
    planos: pd.DataFrame | None,
    *,
    fonte: str = "totalpass",
    casar_m: float = CASAR_PINO_M,
) -> list[dict[str, Any]]:
    """Anexa o plano do agregador a cada pino do mapa pela linha mais próxima da `fonte`.

    TotalPass grava `plano`/`preco_plano` (a chave que a tela já lia); Wellhub grava
    `plano_wellhub`/`preco_plano_wellhub`. Sem par a até `casar_m`, os dois ficam `None`: a
    academia pode simplesmente não estar no agregador, e isso não é "plano mais barato".
    """
    _fonte(fonte)
    sufixo = "" if fonte == "totalpass" else f"_{fonte}"
    chave_plano, chave_preco = f"plano{sufixo}", f"preco_plano{sufixo}"
    base = planos.dropna(subset=["lat", "lng"]) if planos is not None else None
    # As chaves nascem nulas em TODO pino, mesmo sem base: a tela distingue "sem plano" de
    # "campo ausente". A saída antecipada vem depois disso, e é ela que deixa `base`/`lats`/
    # `lngs` não-nulos no laço de casamento (sem ela o mypy não consegue estreitar os tipos).
    for pino in pinos:
        pino[chave_plano] = None
        pino[chave_preco] = None
    if base is None or not len(base):
        return pinos
    lats, lngs = base["lat"].to_numpy(), base["lng"].to_numpy()
    for pino in pinos:
        if pino.get("lat") is None or pino.get("lng") is None:
            continue
        d = _distancias_m(float(pino["lat"]), float(pino["lng"]), lats, lngs)
        i = int(np.argmin(d))
        if d[i] <= casar_m:
            linha: Mapping[str, Any] = base.iloc[i]
            pino[chave_plano] = str(linha["plano"])
            pino[chave_preco] = _num(linha["preco"])
    return pinos
