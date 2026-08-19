"""`[BLK-MA-17 metade 1 / DEC-035]` Artefato NOMEADO das unidades de REDE do agregador.

As 2.844 unidades de rede que o WellHub lista entram na **oferta** do sinal 6 desde a DEC-034 e
não aparecem em lugar nenhum da tela. `_filtrar_universo_sinal_1` as corta antes do score — de
propósito, e esse propósito continua válido —, mas a camada de EXIBIÇÃO herdou o corte sem ter a
mesma razão para tê-lo: o que não serve para rede é a **régua de score**, não a leitura.

**FATO SIM, SCORE NÃO.** Este módulo emite `pressao_competitiva` (o S6, que é geográfico e não sabe
se a academia é de rede) e os fatos sem peso — `status_churn`, `nota_wellhub`,
`qtd_avaliacoes_wellhub`. **Não** emite `score_vulnerabilidade`, e a ausência é a decisão:

  - **S1 mede política comercial, não fragilidade.** A negociação com o agregador é CENTRALIZADA:
    "estar em 1 app em vez de 2" é decisão da rede, não exposição daquela unidade.
  - **S3 é correlacionado, e é o pior dos dois.** A concentração medida é *top 5 = 48,4% das
    unidades, máximo 440 numa rede só*. Quando a Panobianco sair do WellHub, **440 unidades viram
    `sumiu_recente` no mesmo dia** e o S3 — o maior peso do Plano B, `≈ 0,467` — dispara para todas
    simultaneamente, sem que uma única tenha se fragilizado. O score leria um evento de negociação
    como 440 alvos.

É o molde já usado duas vezes nesta epic (G-D2 no `status_churn`, DEC-026 no rating): **o fato entra
antes do peso**.

**O universo do sinal 1 não é tocado.** `_filtrar_universo_sinal_1` é compartilhado com o sinal 1, e
afrouxá-lo faria `n_academias_independentes_totalpass` e `..._wellhub` contarem redes **com o nome
dizendo o contrário**. Aqui há um filtro PRÓPRIO, de exibição, que é o complemento daquele — e a
lista de alvos de M&A continua só de independentes.

READ-ONLY sobre o M1.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .alvos_nomeados import _assert_destino_gitignored, _juntar_auditoria_da_pressao
from .contrato import (
    CATEGORIA_INDEPENDENTE,
    CONTRATO_COLUNAS_REDES_NOMEADAS,
    FONTES_AGREGADORES,
    PRESSAO_GRAO_ACADEMIA,
    VERSAO_CONTRATO_REDES_NOMEADAS,
)

_logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
REDES_NOMEADAS_PATH_DEFAULT = ROOT / "data" / "staging" / "vulnerabilidade_ma_redes.parquet"

# O que vem do frame de CHURN. `rede` entra como coluna do artefato (é o que distingue esta lista);
# os três seguintes são os fatos sem peso que a DEC-035 autoriza propagar.
_DO_CHURN: tuple[str, ...] = (
    "fonte",
    "chave_snapshot",
    "rede",
    "hex_id_res7",
    "status_churn",
    "nota_wellhub",
    "qtd_avaliacoes_wellhub",
)

# O que vem do frame de PRESSÃO, além da auditoria que `_juntar_auditoria_da_pressao` já traz.
# `pressao_grao` NAO esta aqui porque nao existe no frame de pressao: quem o carimba e' o
# SCORE, na saida. Aqui ele e' derivado por CONSTRUCAO -- o join e' por
# `(fonte, chave_snapshot)`, que so' o grao ACADEMIA tem (o grao hex e' indexado por
# `hex_id_res7`). Carimbar a constante e' afirmar o que o proprio join ja' provou.
_DA_PRESSAO: tuple[str, ...] = ("pressao_competitiva", "universo_oferta")


def filtrar_universo_exibicao_redes(df: pd.DataFrame) -> pd.DataFrame:
    """Universo de EXIBIÇÃO: `fonte in FONTES_AGREGADORES` **e** `rede != CATEGORIA_INDEPENDENTE`.

    É o COMPLEMENTO de `_filtrar_universo_sinal_1` dentro dos agregadores, e não uma versão
    afrouxada dele. A fonte `unidades` (feed do site de cada rede) continua fora nos dois: ela é o
    insumo de oferta mapeado, não o feed de agregador, e já tem pin próprio no funil.
    """
    if df.empty:
        return df
    manter = df["fonte"].astype(str).isin(set(FONTES_AGREGADORES)) & (
        df["rede"].astype(str) != CATEGORIA_INDEPENDENTE
    )
    return df[manter].reset_index(drop=True)


def chaves_com_pin_proprio(
    cadeias_do_feed: pd.DataFrame, pontos_mapeados: pd.DataFrame
) -> set[tuple[str, str]]:
    """Chaves que devem ganhar pin PRÓPRIO — as sobreviventes da dedup da DEC-034.

    A precedência de pin sai **de graça** daquela dedup, e por isso não é regra nova a justificar:
    as sobreviventes são, por construção, exatamente as unidades sem ponto equivalente em
    `concorrentes_mapeados`, logo as únicas sem pin já desenhado no funil. As colapsadas têm o pin
    do funil no mesmo endereço, e desenhar outro criaria dois pins no mesmo lugar.
    """
    from .pressao_competitiva import dedup_cadeias_do_feed

    if cadeias_do_feed.empty:
        return set()
    sobreviventes, _posicoes = dedup_cadeias_do_feed(cadeias_do_feed, pontos_mapeados)
    if sobreviventes.empty:
        return set()
    return set(
        zip(
            sobreviventes["fonte"].astype(str),
            sobreviventes["chave_snapshot"].astype(str),
            strict=True,
        )
    )


def montar_redes_nomeadas(
    churn: pd.DataFrame,
    coordenadas: pd.DataFrame,
    pressao: pd.DataFrame | None = None,
    com_pin_proprio: set[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Churn + coordenadas + pressão -> uma linha por unidade de REDE, com identidade. Função pura.

    O join é `1:1` por `(fonte, chave_snapshot)` e o lado que sobrevive é o **churn** — ele define
    quem existe na série. Uma unidade sem coordenada entra **sem pin**: ela existe, só não é
    desenhável, e sumir com ela esconderia concorrência por acidente de coleta.

    `com_pin_proprio` ausente = ninguém ganha pin próprio (`tem_pin_proprio = False` em todas), que
    é o default CONSERVADOR: sem saber quem sobreviveu à dedup, desenhar seria arriscar dois pins no
    mesmo endereço.
    """
    exigidas_churn = [c for c in _DO_CHURN if c not in churn.columns]
    if exigidas_churn:
        raise AssertionError(f"frame de churn sem coluna(s): {exigidas_churn}")
    exigidas_coord = [c for c in ("fonte", "chave_snapshot", "nome", "lat", "lng") if c not in coordenadas.columns]
    if exigidas_coord:
        raise AssertionError(f"frame de coordenadas sem coluna(s): {exigidas_coord}")

    universo = filtrar_universo_exibicao_redes(churn)
    if universo.empty:
        vazio = pd.DataFrame(
            {c: pd.Series(dtype=d) for c, d in CONTRATO_COLUNAS_REDES_NOMEADAS.items()}
        )
        _assert_schema_redes(vazio)
        return vazio

    chaves = ["fonte", "chave_snapshot"]
    base = universo[list(_DO_CHURN)].copy()
    for c in chaves:
        base[c] = base[c].astype("string")

    coord = coordenadas.drop_duplicates(subset=chaves, keep="first").copy()
    for c in chaves:
        coord[c] = coord[c].astype("string")

    out = base.merge(
        coord[[*chaves, "nome", "lat", "lng"]], on=chaves, how="left", validate="one_to_one"
    )
    out = _juntar_pressao_de_exibicao(out, pressao, chaves)
    out = _juntar_auditoria_da_pressao(out, pressao, chaves)

    chaves_pin = com_pin_proprio or set()
    out["tem_pin_proprio"] = [
        (str(f), str(k)) in chaves_pin
        for f, k in zip(out["fonte"], out["chave_snapshot"], strict=True)
    ]
    # Sem coordenada não há pin, por mais que a dedup diga que ele seria próprio.
    out.loc[out["lat"].isna() | out["lng"].isna(), "tem_pin_proprio"] = False

    sem_pin = int(out["lat"].isna().sum())
    if sem_pin:
        _logger.warning("unidade de rede SEM coordenada (nao desenhavel): %d", sem_pin)

    out["versao_contrato"] = VERSAO_CONTRATO_REDES_NOMEADAS
    out = out[list(CONTRATO_COLUNAS_REDES_NOMEADAS.keys())].copy()
    for coluna, dtype in CONTRATO_COLUNAS_REDES_NOMEADAS.items():
        out[coluna] = out[coluna].astype(dtype)
    out = out.sort_values(chaves, kind="mergesort").reset_index(drop=True)
    _assert_schema_redes(out)
    return out


def _juntar_pressao_de_exibicao(
    df: pd.DataFrame, pressao: pd.DataFrame | None, chaves: list[str]
) -> pd.DataFrame:
    """Left join de `pressao_competitiva`/`pressao_grao`/`universo_oferta`. Ausência é NULA.

    A pressão destas unidades **já é calculada hoje** e depois descartada: o cálculo roda sobre o
    feed inteiro (22.173 linhas, incluindo as 2.844 de rede) e é o join do SCORE que as filtra. Este
    módulo não recalcula nada — só materializa o que existia e era jogado fora.
    """
    out = df.copy()
    if pressao is None or pressao.empty:
        for coluna in (*_DA_PRESSAO, "pressao_grao"):
            dtype = CONTRATO_COLUNAS_REDES_NOMEADAS[coluna]
            out[coluna] = pd.Series(pd.NA, index=out.index, dtype=dtype)
        return out

    faltando = [c for c in (*chaves, *_DA_PRESSAO) if c not in pressao.columns]
    if faltando:
        raise AssertionError(f"frame de pressao sem coluna(s): {faltando}")
    if bool(pressao.duplicated(subset=chaves).any()):
        raise AssertionError("frame de pressao com `(fonte, chave_snapshot)` duplicado")

    projecao = pressao[[*chaves, *_DA_PRESSAO]].copy()
    for c in chaves:
        projecao[c] = projecao[c].astype("string")
    out = out.merge(projecao, on=chaves, how="left", validate="many_to_one")
    # Carimbo do grao: `academia` onde HOUVE medicao, nulo onde nao houve. Nunca a constante em
    # linha sem pressao -- isso afirmaria de onde se mediu algo que nao foi medido.
    out["pressao_grao"] = pd.Series(pd.NA, index=out.index, dtype="string")
    out.loc[out["pressao_competitiva"].notna(), "pressao_grao"] = PRESSAO_GRAO_ACADEMIA
    return out


def _assert_schema_redes(df: pd.DataFrame) -> None:
    """Contrato do artefato de redes + as duas travas que a DEC-035 exige.

    A primeira é anti-PII (§11), no molde do nomeado de independentes. A segunda é a que impede o
    bloco de virar aquilo que ele decidiu NÃO ser: **nenhuma coluna de score aqui**.
    """
    proibidas = {
        "review",
        "review_texto",
        "autor",
        "autor_review",
        "cpf",
        "email",
        "telefone",
        "modalidades",
        "atividades",
    }
    vazando = sorted(set(df.columns) & proibidas)
    if vazando:
        raise AssertionError(f"campo vedado pelo §11 no artefato de redes: {vazando}")

    # A trava da DEC-035. Sem ela, um join descuidado no futuro reintroduziria em silêncio o score
    # que a decisão recusou — e o artefato passaria a afirmar sobre redes o que S1/S3 não sabem.
    de_score = sorted(c for c in df.columns if c.startswith("score_") or c == "v6")
    if de_score:
        raise AssertionError(
            f"coluna de SCORE no artefato de redes, que a DEC-035 proibe: {de_score}"
        )

    esperado = list(CONTRATO_COLUNAS_REDES_NOMEADAS.keys())
    if list(df.columns) != esperado:
        raise AssertionError(f"artefato de redes fora do contrato: {list(df.columns)}")
    if df.empty:
        return
    if bool(df.duplicated(subset=["fonte", "chave_snapshot"]).any()):
        raise AssertionError("artefato de redes com `(fonte, chave_snapshot)` duplicado")
    if bool((df["rede"].astype(str) == CATEGORIA_INDEPENDENTE).any()):
        raise AssertionError("independente no artefato de REDES: o universo de exibicao vazou")


def materializar_redes_nomeadas(
    churn: pd.DataFrame,
    coordenadas: pd.DataFrame,
    *,
    pressao: pd.DataFrame | None = None,
    com_pin_proprio: set[tuple[str, str]] | None = None,
    saida: Path = REDES_NOMEADAS_PATH_DEFAULT,
    dry_run: bool = False,
) -> dict[str, object]:
    """Monta e grava o artefato de redes. Devolve auditoria só com escalares."""
    redes = montar_redes_nomeadas(churn, coordenadas, pressao, com_pin_proprio)
    total = int(len(redes))
    com_coord = int(redes["lat"].notna().sum()) if total else 0
    com_pin = int(redes["tem_pin_proprio"].fillna(False).sum()) if total else 0
    com_pressao = int(redes["pressao_competitiva"].notna().sum()) if total else 0
    auditoria: dict[str, object] = {
        "unidades_de_rede": total,
        "com_coordenada": com_coord,
        "sem_coordenada": total - com_coord,
        "com_pin_proprio": com_pin,
        "cobertas_por_pin_do_funil": total - com_pin,
        "com_pressao": com_pressao,
        "dry_run": bool(dry_run),
    }
    if dry_run:
        _logger.info("dry-run: nada gravado. %s", auditoria)
        return auditoria

    _assert_destino_gitignored(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    redes.to_parquet(saida, index=False)
    _logger.info("artefato de REDES (gitignored): %s", saida)
    return auditoria


__all__ = [
    "REDES_NOMEADAS_PATH_DEFAULT",
    "chaves_com_pin_proprio",
    "filtrar_universo_exibicao_redes",
    "montar_redes_nomeadas",
    "materializar_redes_nomeadas",
]
