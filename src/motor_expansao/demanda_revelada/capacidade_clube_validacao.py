"""BLK-TP-06-FU2: leitor anti-PII de capacidade de CLUBE por rede (de `data/validacao/`).

Modulo IRMAO, DISJUNTO de `revalidacao_residual_candidatos.py`: a fronteira anti-PII de
leitura dos xlsx reais de `data/validacao/` (dados reais gitignored, com PII na origem) fica
ISOLADA aqui para ser auditavel de uma vez. As funcoes sao PURAS (sem estado global) e leem os
xlsx SO para extrair, NA FRONTEIRA, a **mediana de alunos/unidade por rede** -- um `dict[str,
float]`. Qualquer DataFrame com PII (nome de unidade/endereco/cidade/coord/linha) e descartado
IMEDIATAMENTE apos a agregacao; NADA de PII atravessa a fronteira nem e persistido em
arquivo/log/teste.

Casamento por REDE CANONICA de `concorrentes_mapeados`: so `smart_fit` (KPIs Smart) e
`engenharia_do_corpo` (Academias) casam com uma rede mapeada e recebem capacidade REAL; as ~26
redes restantes usam `FALLBACK_CAPACIDADE` (2.500, §4 -- neutro, low-cost). Sky Fit NAO e rede
mapeada -> entra SO como ANCORA/PRIOR documentada no relatorio (nenhum ponto recebe peso Sky).

GATE (decisao AUTONOMA do orquestrador, 2026-07-02; usuario delegou):
  (A) capacidade real Smart ~2.370 / Engenharia ~3.106; fallback 2.500 p/ ~26 redes; Sky ancora.
  (E) leitor de `data/validacao/` anti-PII em modulo irmao (este arquivo).

GUARDRAILS (DEC-012 anti-PII; CLAUDE.md §2/§5):
  - `data/validacao/*.xlsx` sao DADOS REAIS gitignored -- NUNCA versionar; agregar POR REDE na
    fronteira e DESCARTAR PII. Zero PII em artefato/log/teste. Fixtures SINTETICAS nos testes.
  - Pacote `demanda_revelada/` DISJUNTO: este modulo NAO importa de `pipelines/m1/`, `censo_*`,
    `dashboard/`, `api`, `config.py` raiz nem pipelines pesados. Dep: so `pandas`(+`openpyxl` base).
  - READ-ONLY sobre o M1: nada aqui recalcula score/pesos/artefatos.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path

import pandas as pd

# Rede de seguranca anti-PII (mesma lista do contrato da camada).
from .contrato import COLUNAS_PII_PROIBIDAS

_logger = logging.getLogger(__name__)

# Capacidade de CLUBE default (§4 do projeto): 2.500 alunos/unidade. Usada como FALLBACK das
# redes sem capacidade real em `data/validacao/`. Travavel no gate (decisao (A)).
FALLBACK_CAPACIDADE: float = 2500.0

# Diretorio das bases de validacao (gitignored, dados reais). Default relativo ao repo.
DIR_VALIDACAO_DEFAULT: Path = Path("data/validacao")


# Contrato de leitura por REDE CANONICA de `concorrentes_mapeados`.
#   rede -> (arquivo, sheet, coluna_de_alunos, coluna_de_unidade|None)
# `coluna_de_unidade`: quando presente, agrega para a linha mais recente por unidade ANTES da
# mediana (evita ponderar unidades por nº de meses no dump); None => mediana direta das linhas.
# So as 2 redes que CASAM com `concorrentes_mapeados` entram (smart_fit, engenharia_do_corpo).
_ContratoRede = tuple[str, str, str, str | None]
REDES_VALIDACAO_ARQUIVOS: dict[str, _ContratoRede] = {
    "smart_fit": ("KPIs_Smart_2025_02 (1).xlsx", "Base", "Alunos Totais SF", "Sigla"),
    "engenharia_do_corpo": (
        "academias_engenharia_do_corpo.xlsx",
        "Academias",
        "Alunos Totais",
        None,
    ),
}

# Coluna de "membros de clube" da base Sky (ANCORA documentada; NUNCA vira peso).
_SKY_ARQUIVO = "Sky Fit dados.xlsx"
_SKY_SHEET = "Sell Out"
_SKY_HEADER_LINHA = 3  # a 4ª linha (0-based=3) traz o cabecalho real; acima e branco.
_SKY_COLUNA_ALUNOS = "Alunos EVO"  # base de alunos do proprio clube (EVO), sem agregadores.


def _assert_sem_pii_em_dict(d: Mapping[str, float]) -> None:
    """Falha se alguma CHAVE do dict for uma coluna PII proibida (rede de seguranca).

    As chaves sao REDES-CATEGORIA (ex.: "smart_fit") e os valores sao floats -- jamais PII. O
    assert e cheap e garante que nenhum nome/campo PII virou chave por engano.
    """
    baixo_pii = {c.lower() for c in COLUNAS_PII_PROIBIDAS}
    for k, v in d.items():
        if str(k).lower() in baixo_pii:  # pragma: no cover - rede de seguranca
            raise AssertionError(f"PII vazou como chave de capacidade: {k!r}")
        float(v)  # valores devem ser numericos (nunca strings de PII)


def _mediana_por_rede_de_xlsx(
    caminho: Path, sheet: str, coluna_alunos: str, coluna_unidade: str | None
) -> float | None:
    """Le UM xlsx e retorna SO a mediana de alunos/unidade (float). NADA de PII atravessa.

    - Coage `coluna_alunos` para numerico.
    - Se `coluna_unidade` for dada, mantem a ULTIMA linha por unidade (dump multi-mes do Smart:
      usa o mes mais recente por `Sigla`) antes da mediana.
    - O DataFrame (que contem PII) e descartado ao fim da funcao -- so o `float` sai.
    Retorna None se o arquivo/sheet/coluna nao existir ou nao houver valor numerico.
    """
    try:
        df = pd.read_excel(caminho, sheet_name=sheet)
    except Exception as exc:  # pragma: no cover - arquivo ausente/ilegivel cai no fallback
        _logger.warning("capacidade: xlsx ilegivel (%s): %s", caminho.name, exc)
        return None

    df.columns = [str(c) for c in df.columns]
    if coluna_alunos not in df.columns:
        _logger.warning("capacidade: coluna '%s' ausente em %s", coluna_alunos, caminho.name)
        return None

    alunos = pd.to_numeric(df[coluna_alunos], errors="coerce")

    if coluna_unidade is not None and coluna_unidade in df.columns:
        # Ultima observacao por unidade (mes mais recente do dump multi-mes).
        ordem = None
        for cand in ("Data_Ref", "data_ref"):
            if cand in df.columns:
                ordem = pd.to_datetime(df[cand], errors="coerce")
                break
        aux = pd.DataFrame({"_u": df[coluna_unidade].astype(str), "_al": alunos})
        if ordem is not None:
            aux = aux.assign(_dt=ordem).sort_values("_dt")
        aux = aux.dropna(subset=["_al"])
        if aux.empty:
            return None
        por_unidade = aux.groupby("_u", sort=False)["_al"].last()
        med = float(por_unidade.median())
        del df, aux, por_unidade  # descarta PII explicitamente
        return med

    alunos = alunos.dropna()
    if alunos.empty:
        return None
    med = float(alunos.median())
    del df, alunos  # descarta PII explicitamente
    return med


def ler_capacidade_clube_por_rede(
    base_dir: Path = DIR_VALIDACAO_DEFAULT,
    *,
    fallback: float = FALLBACK_CAPACIDADE,
) -> dict[str, float]:
    """Le a mediana de alunos/CLUBE por rede das bases de `data/validacao/` (anti-PII).

    Retorna `{rede -> capacidade_mediana}` APENAS para as redes de `REDES_VALIDACAO_ARQUIVOS`
    lidas com sucesso (arquivo presente + coluna valida). Nenhum nome/endereco/coord/linha
    atravessa a fronteira -- so floats. Redes ausentes/ilegiveis NAO entram no dict (o chamador
    aplica `fallback` via `capacidade_por_rede_com_fallback`). `fallback` aqui e so a assinatura
    canonica (nao usado neste retorno, mas mantido para simetria/testes).
    """
    base_dir = Path(base_dir)
    out: dict[str, float] = {}
    for rede, (arquivo, sheet, coluna_alunos, coluna_unidade) in REDES_VALIDACAO_ARQUIVOS.items():
        caminho = base_dir / arquivo
        if not caminho.exists():
            _logger.info("capacidade: %s ausente -> rede '%s' cai no fallback", arquivo, rede)
            continue
        med = _mediana_por_rede_de_xlsx(caminho, sheet, coluna_alunos, coluna_unidade)
        if med is not None and med > 0.0:
            out[rede] = med
    _assert_sem_pii_em_dict(out)
    return out


def ancora_capacidade_sky(base_dir: Path = DIR_VALIDACAO_DEFAULT) -> float | None:
    """Mediana de alunos de clube da base Sky Fit -- SO como ANCORA/PRIOR documentada.

    Sky NAO e rede de `concorrentes_mapeados` -> NENHUM ponto recebe peso Sky. Este valor entra
    apenas no relatorio para sustentar a escolha de fallback (contexto low-cost). Retorna None se
    a base nao existir. Anti-PII: so o float da mediana sai.
    """
    caminho = Path(base_dir) / _SKY_ARQUIVO
    if not caminho.exists():
        return None
    try:
        df = pd.read_excel(caminho, sheet_name=_SKY_SHEET, header=_SKY_HEADER_LINHA)
    except Exception as exc:  # pragma: no cover
        _logger.warning("capacidade: Sky ilegivel: %s", exc)
        return None
    df.columns = [str(c) for c in df.columns]
    if _SKY_COLUNA_ALUNOS not in df.columns:
        return None
    alunos = pd.to_numeric(df[_SKY_COLUNA_ALUNOS], errors="coerce").dropna()
    if alunos.empty:
        return None
    med = float(alunos.median())
    del df, alunos
    return med


def capacidade_por_rede_com_fallback(
    redes_alvo: Iterable[str],
    cap_lidas: Mapping[str, float],
    *,
    fallback: float = FALLBACK_CAPACIDADE,
) -> dict[str, float]:
    """Dicionario COMPLETO `{rede -> capacidade}` para TODAS as `redes_alvo`.

    Usa `cap_lidas[rede]` quando existir (capacidade real de validacao); senao `fallback`
    (2.500). Declarável e testável de forma isolada. Retorno so `dict[str,float]` (sem PII).
    """
    cap: dict[str, float] = {}
    for rede in redes_alvo:
        r = str(rede)
        cap[r] = float(cap_lidas[r]) if r in cap_lidas else float(fallback)
    _assert_sem_pii_em_dict(cap)
    return cap


__all__ = [
    "DIR_VALIDACAO_DEFAULT",
    "FALLBACK_CAPACIDADE",
    "REDES_VALIDACAO_ARQUIVOS",
    "ancora_capacidade_sky",
    "capacidade_por_rede_com_fallback",
    "ler_capacidade_clube_por_rede",
]
