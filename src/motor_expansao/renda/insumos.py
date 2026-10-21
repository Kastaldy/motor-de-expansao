"""Insumos da renda exibida: uplift de composicao e moradores por domicilio, com cascata e cache.

Movido de `dashboard/constants.py` (E0). La os caminhos eram RELATIVOS ao CWD
("data/staging/..."): no container da API resolviam pelo `WORKDIR /app`, no piloto local
nao resolviam, e o `web/server/app.py` reapontava os atributos do modulo no boot. Aqui o
caminho base e um so -- `staging_dir()` = `<raiz do perfil>/staging` --, configuravel por
`configurar_staging(path)`, que tambem zera os caches.

Cascatas (as mesmas de antes):
  - uplift do municipio: municipio -> mediana da UF (so municipios `uplift_confiavel`) -> nacional;
  - moradores por domicilio: municipio -> mediana da UF -> nacional;
  - uplift do setor: setor -> uplift do municipio.

Os nacionais (`uplift_composicao`, `moradores_por_domicilio`) vem do perfil do pais: na
Argentina, sem tabelas, eles sao os UNICOS valores que respondem.

Artefato ausente cai na cascata nacional com WARNING (como antes, mas nao mais em silencio).
Em producao a ausencia e barrada antes, na subida (`validar_na_subida`).
"""

from __future__ import annotations

import logging
from pathlib import Path

_LOG = logging.getLogger("motor_expansao.renda")

UPLIFT_MUNICIPIO_ARQUIVO = "uplift_renda_domiciliar_municipio.parquet"
UPLIFT_SETOR_ARQUIVO = "uplift_composicao_setor.parquet"

_staging_configurado: Path | None = None

_uplift_cache: dict[str, float] | None = None
_uplift_uf_cache: dict[str, float] | None = None
_moradores_cache: dict[str, float] | None = None
_moradores_uf_cache: dict[str, float] | None = None
_uplift_setor_cache: dict[str, float] | None = None
_uplift_setor_extrapolado_cache: set[str] | None = None


def staging_dir() -> Path:
    """Diretorio de staging de onde saem os insumos (`<raiz do perfil>/staging` por default)."""
    if _staging_configurado is not None:
        return _staging_configurado
    from motor_expansao.perfil import resolver_perfil

    return resolver_perfil().raiz / "staging"


def configurar_staging(path: Path | str | None) -> None:
    """Aponta os insumos para `path` (None volta ao default do perfil) e zera os caches."""
    global _staging_configurado
    _staging_configurado = None if path is None else Path(path)
    limpar_caches()


def limpar_caches() -> None:
    """Zera os seis caches; a proxima leitura volta ao disco."""
    global _uplift_cache, _uplift_uf_cache, _moradores_cache, _moradores_uf_cache
    global _uplift_setor_cache, _uplift_setor_extrapolado_cache
    _uplift_cache = None
    _uplift_uf_cache = None
    _moradores_cache = None
    _moradores_uf_cache = None
    _uplift_setor_cache = None
    _uplift_setor_extrapolado_cache = None


#: Colunas que a leitura EXIGE de cada insumo (as mesmas de `_carregar_*`). A subida le com
#: elas para que um artefato presente mas ilegivel falhe no boot, e nao por rota.
COLUNAS_EXIGIDAS: dict[str, tuple[str, ...]] = {
    UPLIFT_MUNICIPIO_ARQUIVO: (
        "uf",
        "cod_municipio",
        "uplift_composicao_final",
        "uplift_confiavel",
        "moradores_por_domicilio_municipio",
    ),
    UPLIFT_SETOR_ARQUIVO: ("cod_setor", "uplift_composicao_setor"),
}


def conferir_leitura(base: Path | str, nomes: tuple[str, ...] | list[str]) -> list[str]:
    """Le cada insumo de `nomes` em `base` com as colunas exigidas. Devolve os problemas.

    Nao toca nos caches: e so a prova de que a leitura de verdade (`_carregar_*`) vai
    funcionar. Nome sem colunas declaradas em `COLUNAS_EXIGIDAS` e ignorado.
    """
    import pandas as pd

    problemas: list[str] = []
    for nome in nomes:
        colunas = COLUNAS_EXIGIDAS.get(nome)
        if colunas is None:
            continue
        caminho = Path(base) / nome
        try:
            pd.read_parquet(caminho, columns=list(colunas))
        except Exception as exc:  # noqa: BLE001 -- qualquer falha de leitura vira problema
            problemas.append(f"{nome} ilegivel ({type(exc).__name__}: {exc})")
    return problemas


def uplift_nacional() -> float:
    """Uplift de composicao do pais (perfil): ultimo degrau da cascata."""
    from motor_expansao.perfil import resolver_perfil

    return resolver_perfil().reguas.uplift_composicao


def moradores_nacional() -> float:
    """Moradores por domicilio do pais (perfil): ultimo degrau da cascata."""
    from motor_expansao.perfil import resolver_perfil

    return resolver_perfil().reguas.moradores_por_domicilio


def _ausente(caminho: Path) -> None:
    _LOG.warning(
        "insumo de renda ausente: %s -- usando a cascata nacional do perfil", caminho
    )


def _carregar_uplift() -> tuple[dict[str, float], dict[str, float]]:
    """Tabela de uplift por municipio (artefato do IBGE). Vazia se ausente (cai no nacional)."""
    global _uplift_cache, _uplift_uf_cache
    if _uplift_cache is None:
        por_municipio: dict[str, float] = {}
        por_uf: dict[str, float] = {}
        caminho = staging_dir() / UPLIFT_MUNICIPIO_ARQUIVO
        if caminho.exists():
            import pandas as pd

            df = pd.read_parquet(
                caminho,
                columns=["uf", "cod_municipio", "uplift_composicao_final", "uplift_confiavel"],
            )
            por_municipio = dict(
                zip(
                    df["cod_municipio"].astype(str),
                    pd.to_numeric(df["uplift_composicao_final"], errors="coerce"),
                    strict=False,
                )
            )
            confiavel = df[df["uplift_confiavel"].astype(bool)]
            por_uf = confiavel.groupby("uf")["uplift_composicao_final"].median().to_dict()
        else:
            _ausente(caminho)
        _uplift_cache = por_municipio
        _uplift_uf_cache = por_uf
    return _uplift_cache, _uplift_uf_cache or {}


def uplift_municipio(uf: str | None, cod_municipio: str | None = None) -> float:
    """Fator responsavel -> domicilio inteiro (IBGE). municipio -> mediana UF -> nacional."""
    por_municipio, por_uf = _carregar_uplift()
    if cod_municipio:
        valor = por_municipio.get(str(cod_municipio).strip())
        if valor is not None and valor == valor:  # descarta NaN
            return float(valor)
    if uf:
        valor = por_uf.get(str(uf).strip().upper())
        if valor is not None and valor == valor:
            return float(valor)
    return uplift_nacional()


def _carregar_moradores() -> tuple[dict[str, float], dict[str, float]]:
    """Moradores/domicilio por municipio (mesma tabela do uplift). Vazia se ausente."""
    global _moradores_cache, _moradores_uf_cache
    if _moradores_cache is None:
        por_municipio: dict[str, float] = {}
        por_uf: dict[str, float] = {}
        caminho = staging_dir() / UPLIFT_MUNICIPIO_ARQUIVO
        if caminho.exists():
            import pandas as pd

            df = pd.read_parquet(
                caminho,
                columns=["uf", "cod_municipio", "moradores_por_domicilio_municipio"],
            )
            valores = pd.to_numeric(df["moradores_por_domicilio_municipio"], errors="coerce")
            por_municipio = dict(zip(df["cod_municipio"].astype(str), valores, strict=False))
            por_uf = df.assign(_m=valores).groupby("uf")["_m"].median().to_dict()
        _moradores_cache = por_municipio
        _moradores_uf_cache = por_uf
    return _moradores_cache, _moradores_uf_cache or {}


def moradores_por_domicilio(uf: str | None, cod_municipio: str | None = None) -> float:
    """Moradores medios por domicilio (IBGE 2022). municipio -> mediana UF -> nacional."""
    por_municipio, por_uf = _carregar_moradores()
    if cod_municipio:
        valor = por_municipio.get(str(cod_municipio).strip())
        if valor is not None and valor == valor:  # descarta NaN
            return float(valor)
    if uf:
        valor = por_uf.get(str(uf).strip().upper())
        if valor is not None and valor == valor:
            return float(valor)
    return moradores_nacional()


def _carregar_uplift_setor() -> dict[str, float]:
    """Tabela de uplift por SETOR. Vazia se o artefato nao existir (cai no municipio).

    Le tambem `flag_extrapolacao`: o setor cuja composicao familiar cai FORA do envelope da
    calibracao municipal (leitura cautelosa). Ate 2026-08-13 a flag morria na carga.
    """
    global _uplift_setor_cache, _uplift_setor_extrapolado_cache
    if _uplift_setor_cache is None:
        mapa: dict[str, float] = {}
        extrapolados: set[str] = set()
        caminho = staging_dir() / UPLIFT_SETOR_ARQUIVO
        if caminho.exists():
            import pandas as pd

            colunas = ["cod_setor", "uplift_composicao_setor"]
            try:
                df = pd.read_parquet(caminho, columns=[*colunas, "flag_extrapolacao"])
            except (KeyError, ValueError):  # artefato antigo, sem a flag
                df = pd.read_parquet(caminho, columns=colunas)
            cods = df["cod_setor"].astype(str)
            mapa = dict(
                zip(
                    cods,
                    pd.to_numeric(df["uplift_composicao_setor"], errors="coerce"),
                    strict=False,
                )
            )
            if "flag_extrapolacao" in df.columns:
                extrapolados = set(cods[df["flag_extrapolacao"].fillna(False).astype(bool)])
        else:
            _ausente(caminho)
        _uplift_setor_cache = mapa
        _uplift_setor_extrapolado_cache = extrapolados
    return _uplift_setor_cache


def uplift_setor(
    cod_setor: object, uf: str | None = None, cod_municipio: str | None = None
) -> float:
    """Fator responsavel -> domicilio no nivel do SETOR. Setor -> municipio -> UF -> nacional."""
    if cod_setor is not None and cod_setor == cod_setor:  # descarta NaN
        valor = _carregar_uplift_setor().get(str(cod_setor).strip())
        if valor is not None and valor == valor:
            return float(valor)
    return uplift_municipio(uf, cod_municipio)


def uplift_extrapolado(cod_setor: object) -> bool:
    """O uplift deste setor foi EXTRAPOLADO para fora da faixa de calibracao do municipio?"""
    if cod_setor is None or cod_setor != cod_setor:  # descarta NaN
        return False
    _carregar_uplift_setor()  # popula os dois caches juntos
    return str(cod_setor).strip() in (_uplift_setor_extrapolado_cache or set())

