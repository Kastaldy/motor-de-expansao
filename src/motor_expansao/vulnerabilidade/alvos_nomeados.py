"""BLK-MA-15: a variante NOMEADA (D1-B) — score de vulnerabilidade com identidade e coordenada.

É o único módulo do pacote que **junta identidade e score**. Todo o resto da camada é anti-PII por
construção: o snapshot mata nome e coordenada na projeção das 12 colunas, e o score trabalha com
`chave_snapshot` opaca. Aqui os dois lados se encontram de novo, e é por isso que este arquivo tem
mais guardrail que código.

**POR QUE ELE EXISTE.** Sem ele o piloto não consegue responder "qual academia, especificamente,
está espremida?" — o mapa mostrava hexágonos e os pins eram só de CADEIAS (Smart Fit, Skyfit...),
que por construção nunca têm score: o universo de M&A exclui cadeias, senão a Smart Fit entraria na
lista de alvos. Medido em 2026-08-14: a interseção entre os pins do mapa e o universo do score era
**VAZIA**. Este módulo produz o que faltava.

**A AUTORIZAÇÃO É EXPLÍCITA E DATADA.** O D1-B estava deferido e a DEC-028 dizia em letra que
"nenhuma variante NOMEADA é servida pelo piloto". A **emenda de 2026-08-14 à DEC-028**, decidida por
Vinicius, reverte essa parte: o piloto passa a servir nome + coordenada + score. Duas razões
pesaram, e a segunda é a que decide:

  1. O piloto inteiro está atrás do Authelia — não é publicação, é alcance interno.
  2. **Esconder o nome não protegeria nada.** Um pin em coordenada exata sobre um mapa com ruas já
     identifica o estabelecimento. A opção "sem nome" entregaria a MESMA exposição com menos
     utilidade — a pior das duas.

**O QUE CONTINUA VEDADO, e o §11 não foi afrouxado nisto:** texto ou autor de review (nunca
coletados), qualquer dado de PESSOA. O que entra aqui é identidade de ESTABELECIMENTO COMERCIAL,
que é o mesmo tipo de dado que os pins de concorrentes já servem desde sempre.

**O ARTEFATO NASCE GITIGNORED**, como o contrato exige desde o D1: ele vive em `data/staging/`, que
o `.gitignore` corta inteiro. `_assert_destino_gitignored` transforma isso em código — gravar em
`data/outputs/` (parcialmente versionado) levanta, em vez de vazar identidade para o repositório.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .contrato import (
    CONTRATO_COLUNAS_ALVOS_NOMEADOS,
    CONTRATO_COLUNAS_SCORE,
    VERSAO_CONTRATO_ALVOS_NOMEADOS,
)

_logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
NOMEADOS_PATH_DEFAULT = ROOT / "data" / "staging" / "vulnerabilidade_ma_nomeadas.parquet"

# Colunas que o score traz e que viajam para o artefato nomeado. `rede` fica FORA: é sempre
# `independente` no universo de M&A (travado no `_assert_schema_score`), então carregá-la seria
# repetir uma constante 19 mil vezes.
_DO_SCORE: tuple[str, ...] = (
    "fonte",
    "chave_snapshot",
    "hex_id_res7",
    "status_churn",
    "nota_wellhub",
    "qtd_avaliacoes_wellhub",
    "v6",
    "pressao_competitiva",
    "pressao_grao",
    "universo_oferta",
    "sinais_disponiveis",
    "n_sinais_disponiveis",
    "score_vulnerabilidade",
    "score_vulnerabilidade_ordenavel",
    "flag_score_provisorio",
)


def _assert_destino_gitignored(caminho: Path) -> None:
    """Barra a gravação fora de `data/staging/`. O D1-B exige artefato gitignored.

    Não é zelo: `data/outputs/` é PARCIALMENTE versionado (o `.gitignore` corta só alguns nomes de
    lá), então um caminho errado ali colocaria nome e coordenada de 19 mil estabelecimentos no
    repositório — e um `git rm` depois não apaga o histórico.
    """
    partes = {p.lower() for p in caminho.resolve().parts}
    if "staging" not in partes:
        raise ValueError(
            f"artefato NOMEADO so' pode ser gravado sob `data/staging/` (gitignored); "
            f"recebido: {caminho}"
        )


def montar_alvos_nomeados(score: pd.DataFrame, coordenadas: pd.DataFrame) -> pd.DataFrame:
    """Score (opaco) + coordenadas do feed -> uma linha por academia, COM identidade. Função pura.

    `coordenadas` é a saída de `snapshots.coordenadas_por_chave` acrescida de `nome` — o mesmo
    frame que o cálculo de pressão já consome, com uma coluna a mais.

    **Join `1:1` pela chave primária `(fonte, chave_snapshot)`**, e a direção importa: o SCORE é o
    lado que sobrevive. Uma academia no feed que não está no score não entra (pode ser cadeia, que o
    universo de M&A exclui de propósito); uma academia com score e sem coordenada entra **sem pin** —
    ela existe, só não é desenhável, e sumir com ela esconderia um alvo por acidente de coleta.
    """
    faltando = [c for c in _DO_SCORE if c not in score.columns]
    if faltando:
        raise AssertionError(f"frame de score fora do contrato do BLK-MA-04: faltam {faltando}")
    exigidas = ("fonte", "chave_snapshot", "nome", "lat", "lng")
    ausentes = [c for c in exigidas if c not in coordenadas.columns]
    if ausentes:
        raise AssertionError(f"frame de coordenadas sem coluna(s): {ausentes}")

    if score.empty:
        vazio = pd.DataFrame(
            {c: pd.Series(dtype=d) for c, d in CONTRATO_COLUNAS_ALVOS_NOMEADOS.items()}
        )
        _assert_schema_nomeados(vazio)
        return vazio

    chaves = ["fonte", "chave_snapshot"]
    coord = coordenadas.drop_duplicates(subset=chaves, keep="first").copy()
    for c in chaves:
        coord[c] = coord[c].astype("string")

    base = score[list(_DO_SCORE)].copy()
    for c in chaves:
        base[c] = base[c].astype("string")

    out = base.merge(
        coord[[*chaves, "nome", "lat", "lng"]], on=chaves, how="left", validate="one_to_one"
    )
    sem_pin = int(out["lat"].isna().sum())
    if sem_pin:
        # AVISO, não descarte: a academia tem score e o operador precisa saber que ela existe,
        # mesmo que o mapa não consiga desenhá-la.
        _logger.warning("academia com score e SEM coordenada (nao desenhavel): %d", sem_pin)

    out["versao_contrato"] = VERSAO_CONTRATO_ALVOS_NOMEADOS
    out = out[list(CONTRATO_COLUNAS_ALVOS_NOMEADOS.keys())].copy()
    for coluna, dtype in CONTRATO_COLUNAS_ALVOS_NOMEADOS.items():
        out[coluna] = out[coluna].astype(dtype)
    out = out.sort_values(["fonte", "chave_snapshot"], kind="mergesort").reset_index(drop=True)
    _assert_schema_nomeados(out)
    return out


def _assert_schema_nomeados(df: pd.DataFrame) -> None:
    """Contrato do artefato nomeado.

    NÃO reusa `COLUNAS_PII_PROIBIDAS`: aqui `nome`/`lat`/`lng` são o PONTO do artefato, autorizados
    pela emenda à DEC-028. O que este guard protege é o resto — que a autorização de identidade de
    ESTABELECIMENTO não vire porta de entrada para dado de PESSOA (§11: nunca texto/autor de
    review) nem para campos que ninguém decidiu servir.
    """
    # A ORDEM destas duas checagens importa: com a de contrato primeiro, um campo vedado sairia
    # rotulado como "coluna fora do contrato" e o motivo real (§11) se perderia na mensagem.
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
        raise AssertionError(f"campo vedado pelo §11 no artefato nomeado: {vazando}")
    esperado = list(CONTRATO_COLUNAS_ALVOS_NOMEADOS.keys())
    if list(df.columns) != esperado:
        raise AssertionError(f"artefato nomeado fora do contrato: {list(df.columns)}")
    if df.empty:
        return
    if bool(df.duplicated(subset=["fonte", "chave_snapshot"]).any()):
        raise AssertionError("artefato nomeado com `(fonte, chave_snapshot)` duplicado")


def materializar_alvos_nomeados(
    score: pd.DataFrame,
    coordenadas: pd.DataFrame,
    *,
    saida: Path = NOMEADOS_PATH_DEFAULT,
    dry_run: bool = False,
) -> dict[str, object]:
    """Monta e grava o artefato nomeado. Devolve auditoria só com escalares."""
    nomeados = montar_alvos_nomeados(score, coordenadas)
    com_pin = int(nomeados["lat"].notna().sum()) if not nomeados.empty else 0
    auditoria: dict[str, object] = {
        "academias_nomeadas": int(len(nomeados)),
        "com_coordenada": com_pin,
        "sem_coordenada": int(len(nomeados)) - com_pin,
        "dry_run": bool(dry_run),
    }
    if dry_run:
        _logger.info("dry-run: nada gravado. %s", auditoria)
        return auditoria

    _assert_destino_gitignored(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    nomeados.to_parquet(saida, index=False)
    _logger.info("artefato NOMEADO (gitignored): %s", saida)
    return auditoria


__all__ = [
    "NOMEADOS_PATH_DEFAULT",
    "montar_alvos_nomeados",
    "materializar_alvos_nomeados",
    "CONTRATO_COLUNAS_SCORE",
]
