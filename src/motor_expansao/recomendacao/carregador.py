"""Regua da recomendacao unica: arquivo versionado DENTRO do pacote, lido com erro explicito.

Mesmo molde dos fatores da renda (`renda/carregador.py`): um arquivo por versao em
`regra/<PAIS>/<versao>.json`, nunca editado depois de publicado, e um `regra/<PAIS>/VIGENTE`
com o nome da versao em uso. Os arquivos viajam na imagem (`.json` e um arquivo sem extensao:
o hatch empacota os dois, como em `renda/fatores`) e sobem por digest, com o mesmo controle de
mudanca do codigo. NAO moram no `MOTOR_DATA_DIR`: a regua e decisao de produto (DEC-077), nao
dado de ambiente -- e o `perfil.json` montado na VPS ja sofreu drift.

O diretorio e escolhido pelo pais do perfil (DEC-047) -- leitura de configuracao declarada,
nunca um ramo de codigo por pais. Pais SEM diretorio (hoje a Argentina) devolve `None`: a
superficie segue o comportamento legado, sem recomendacao. Ja um diretorio presente com
arquivo ausente, JSON invalido, chave faltando, tipo errado ou numero fora de faixa levanta
`RegraRecomendacaoInvalida` nomeando o campo -- tambem em dev, porque a regua vai na imagem e
ausencia e build quebrado, nao acidente de ambiente.

Rollback/fixacao sem rebuild: `MOTOR_REGRA_RECOMENDACAO_VERSAO=<versao>` fixa uma versao que
JA EXISTE no diretorio do pais (log WARNING a cada carga).
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("motor_expansao.recomendacao")

#: Raiz das reguas versionadas (um subdiretorio por pais).
DIR_REGRA = Path(__file__).resolve().parent / "regra"
#: Nome do arquivo que aponta a versao em uso.
ARQUIVO_VIGENTE = "VIGENTE"
#: Variavel de ambiente de rollback/fixacao de versao.
ENV_VERSAO = "MOTOR_REGRA_RECOMENDACAO_VERSAO"
#: Faixa das vagas por segmento (o Top 10 de hoje = 2 x 5).
FAIXA_VAGAS = (1, 10)

_CHAVES_RAIZ = (
    "versao",
    "pais",
    "dec",
    "aprovado_por",
    "vagas_por_segmento",
    "mata_virgem",
    "premium",
)
_CHAVES_MATA_VIRGEM = (
    "renda_domiciliar_min",
    "residual_min",
    "populacao_min",
    "exige_residual_medido",
)
_CHAVES_PREMIUM = ("score_min", "populacao_min", "exige_residual_medido")

# Nome de versao e de pais viram caminho: so caracteres que nao escapam do diretorio.
_RE_VERSAO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_RE_PAIS = re.compile(r"^[A-Z]{2}$")


class RegraRecomendacaoInvalida(RuntimeError):
    """Regua da recomendacao ausente, ilegivel ou incoerente (erro na subida)."""


@dataclass(frozen=True)
class ReguaMataVirgem:
    """Corte do segmento Mata Virgem: renda alta com mercado residual MEDIDO sobrando.

    `populacao_min` None = a regua nao declara piso de populacao para o segmento (BR v1).
    """

    renda_domiciliar_min: float
    residual_min: float
    populacao_min: float | None
    exige_residual_medido: bool


@dataclass(frozen=True)
class ReguaPremium:
    """Corte do segmento Premium: bairro bom (score censitario) e populoso, que NAO e Mata Virgem.

    `exige_residual_medido` decide se um hexagono com residual ESTIMADO (populacao media da
    cidade) pode ser Premium. BR v1 sai com `true` (decisao do usuario em 21/10/2026: nada
    estimado e recomendado, nem no Premium).
    """

    score_min: float
    populacao_min: float | None
    exige_residual_medido: bool


@dataclass(frozen=True)
class Regra:
    """Uma versao da regua validada. Imutavel e hashable: o cache devolve a MESMA instancia."""

    versao: str
    pais: str
    dec: str
    aprovado_por: str
    vagas_por_segmento: int
    mata_virgem: ReguaMataVirgem
    premium: ReguaPremium
    fixada_por_env: bool = False
    caminho: Path | None = field(default=None, compare=False)


# --------------------------------------------------------------------------------
# Validacao
# --------------------------------------------------------------------------------


def _erro(caminho: Path, problema: str) -> RegraRecomendacaoInvalida:
    return RegraRecomendacaoInvalida(f"regua da recomendacao {caminho}: {problema}")


def _numero(valor: Any, caminho: Path, campo: str) -> float:
    # bool e subclasse de int: `true` no JSON nao pode passar por limite 1.
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise _erro(caminho, f"`{campo}` deveria ser numero, veio {type(valor).__name__}")
    f = float(valor)
    if not math.isfinite(f):
        raise _erro(caminho, f"`{campo}` nao e finito ({valor!r})")
    return f


def _positivo(valor: Any, caminho: Path, campo: str) -> float:
    f = _numero(valor, caminho, campo)
    if f <= 0:
        raise _erro(caminho, f"`{campo}` = {f} deveria ser > 0")
    return f


def _populacao(valor: Any, caminho: Path, campo: str) -> float | None:
    if valor is None:
        return None
    f = _numero(valor, caminho, campo)
    if f < 0:
        raise _erro(caminho, f"`{campo}` = {f} deveria ser >= 0 ou null")
    return f


def _booleano(valor: Any, caminho: Path, campo: str) -> bool:
    if not isinstance(valor, bool):
        raise _erro(caminho, f"`{campo}` deveria ser booleano, veio {type(valor).__name__}")
    return valor


def _texto(valor: Any, caminho: Path, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise _erro(caminho, f"`{campo}` deveria ser texto nao vazio, veio {valor!r}")
    return valor


def _objeto(bruto: Any, caminho: Path, campo: str, chaves: tuple[str, ...]) -> dict[str, Any]:
    """Objeto com EXATAMENTE `chaves` (fora as de comentario, prefixadas por `_`).

    Chave desconhecida tambem e erro: `residual_mini` no lugar de `residual_min` cairia como
    "chave ausente", mas `populacao_maxima` (que ninguem le) passaria calada -- e quem a
    escreveu acharia que a regua a aplica.
    """
    if not isinstance(bruto, dict):
        raise _erro(caminho, f"`{campo}` deveria ser objeto")
    faltando = [c for c in chaves if c not in bruto]
    if faltando:
        nomes = ", ".join(f"{campo}.{c}" for c in faltando)
        raise _erro(caminho, f"chave(s) obrigatoria(s) ausente(s): {nomes}")
    sobrando = [c for c in bruto if c not in chaves and not str(c).startswith("_")]
    if sobrando:
        nomes = ", ".join(f"{campo}.{c}" for c in sobrando)
        raise _erro(caminho, f"chave(s) desconhecida(s): {nomes}")
    return bruto


def validar_regra(dados: Any, caminho: Path, *, pais: str, versao: str) -> dict[str, Any]:
    """Valida o JSON bruto de uma versao e devolve os campos ja tipados (sem `fixada_por_env`)."""
    if not isinstance(dados, dict):
        raise _erro(caminho, "o arquivo deveria conter um objeto JSON")
    faltando = [c for c in _CHAVES_RAIZ if c not in dados]
    if faltando:
        raise _erro(caminho, f"chave(s) obrigatoria(s) ausente(s): {', '.join(faltando)}")
    sobrando = [c for c in dados if c not in _CHAVES_RAIZ and not str(c).startswith("_")]
    if sobrando:
        raise _erro(caminho, f"chave(s) desconhecida(s): {', '.join(map(str, sobrando))}")

    if dados["versao"] != versao:
        raise _erro(
            caminho, f"`versao` = {dados['versao']!r} difere do nome do arquivo ({versao!r})"
        )
    if dados["pais"] != pais:
        raise _erro(caminho, f"`pais` = {dados['pais']!r} difere do pais pedido ({pais!r})")

    vagas = dados["vagas_por_segmento"]
    if isinstance(vagas, bool) or not isinstance(vagas, int):
        raise _erro(
            caminho, f"`vagas_por_segmento` deveria ser inteiro, veio {type(vagas).__name__}"
        )
    lo, hi = FAIXA_VAGAS
    if not lo <= vagas <= hi:
        raise _erro(caminho, f"`vagas_por_segmento` = {vagas} fora da faixa [{lo}, {hi}]")

    mv = _objeto(dados["mata_virgem"], caminho, "mata_virgem", _CHAVES_MATA_VIRGEM)
    pr = _objeto(dados["premium"], caminho, "premium", _CHAVES_PREMIUM)

    score_min = _numero(pr["score_min"], caminho, "premium.score_min")
    # Escala absoluta 0-100 do score censitario (DEC-040): 0 deixaria todo hexagono com score
    # passar, e acima de 100 nenhum passaria -- os dois sao regua quebrada, nao decisao.
    if not 0 < score_min <= 100:
        raise _erro(caminho, f"`premium.score_min` = {score_min} fora da faixa (0, 100]")

    return {
        "versao": versao,
        "pais": pais,
        "dec": _texto(dados["dec"], caminho, "dec"),
        "aprovado_por": _texto(dados["aprovado_por"], caminho, "aprovado_por"),
        "vagas_por_segmento": vagas,
        "mata_virgem": ReguaMataVirgem(
            renda_domiciliar_min=_positivo(
                mv["renda_domiciliar_min"], caminho, "mata_virgem.renda_domiciliar_min"
            ),
            residual_min=_positivo(mv["residual_min"], caminho, "mata_virgem.residual_min"),
            populacao_min=_populacao(mv["populacao_min"], caminho, "mata_virgem.populacao_min"),
            exige_residual_medido=_booleano(
                mv["exige_residual_medido"], caminho, "mata_virgem.exige_residual_medido"
            ),
        ),
        "premium": ReguaPremium(
            score_min=score_min,
            populacao_min=_populacao(pr["populacao_min"], caminho, "premium.populacao_min"),
            exige_residual_medido=_booleano(
                pr["exige_residual_medido"], caminho, "premium.exige_residual_medido"
            ),
        ),
    }


# --------------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------------


def _pais_padrao() -> str:
    # Import tardio, como em `renda/carregador.py`: o pais so e resolvido quando alguem pede a
    # regua, nunca no import do pacote (o bot importa `perfil` sem staging -- DEC-049).
    from motor_expansao.perfil import resolver_perfil

    return resolver_perfil().pais


def _ler_regra(raiz: Path, pais: str) -> Regra | None:
    if not isinstance(pais, str) or not _RE_PAIS.match(pais):
        raise RegraRecomendacaoInvalida(f"pais invalido para a regua da recomendacao: {pais!r}")
    dir_pais = raiz / pais
    if not dir_pais.is_dir():
        # Pais sem regua declarada: nao e erro, e "este pais nao tem recomendacao unica".
        _LOG.info(
            "regua da recomendacao: pais %s sem diretorio (%s) -- sem recomendacao", pais, dir_pais
        )
        return None

    versao_env = os.environ.get(ENV_VERSAO, "").strip()
    fixada_por_env = bool(versao_env)
    if fixada_por_env:
        versao = versao_env
        _LOG.warning(
            "ROLLBACK/fixacao de versao ativo: %s=%s fixa a regua da recomendacao de %s "
            "(o arquivo %s e ignorado)",
            ENV_VERSAO,
            versao,
            pais,
            ARQUIVO_VIGENTE,
        )
    else:
        vigente = dir_pais / ARQUIVO_VIGENTE
        if not vigente.is_file():
            raise RegraRecomendacaoInvalida(f"regua da recomendacao: {vigente} ausente")
        try:
            versao = vigente.read_text(encoding="utf-8").strip()
        except (UnicodeDecodeError, OSError) as exc:
            raise _erro(vigente, f"ilegivel ({exc})") from exc
        if not versao:
            raise RegraRecomendacaoInvalida(f"regua da recomendacao: {vigente} vazio")

    if not _RE_VERSAO.match(versao):
        raise RegraRecomendacaoInvalida(
            f"regua da recomendacao: nome de versao invalido {versao!r}"
        )
    caminho = dir_pais / f"{versao}.json"
    if not caminho.is_file():
        origem = ENV_VERSAO if fixada_por_env else ARQUIVO_VIGENTE
        raise RegraRecomendacaoInvalida(
            f"regua da recomendacao: versao {versao!r} (de {origem}) nao existe em {dir_pais}"
        )
    try:
        texto = caminho.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        # Arquivo salvo fora de UTF-8 (cp1252 no Windows) ou sem leitura: erro DA REGUA, com o
        # arquivo nomeado -- nunca um `UnicodeDecodeError` cru no boot.
        raise _erro(caminho, f"ilegivel ({exc})") from exc
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise _erro(caminho, f"JSON invalido ({exc})") from exc

    campos = validar_regra(dados, caminho, pais=pais, versao=versao)
    return Regra(**campos, fixada_por_env=fixada_por_env, caminho=caminho)


@lru_cache(maxsize=8)
def carregar_regra(pais: str | None = None, *, raiz: Path | None = None) -> Regra | None:
    """Regua em uso para `pais` (default: o pais do perfil da instancia). `None` = pais sem regua.

    `raiz` alternativa existe SO para teste. A variavel `MOTOR_REGRA_RECOMENDACAO_VERSAO` e
    lida na primeira carga e fica no cache -- trocar a fixacao exige restart (ou
    `limpar_cache`).
    """
    return _ler_regra(
        Path(raiz) if raiz is not None else DIR_REGRA,
        pais if pais is not None else _pais_padrao(),
    )


def limpar_cache() -> None:
    """Zera o cache de `carregar_regra` (testes e troca de fixacao por env)."""
    carregar_regra.cache_clear()
