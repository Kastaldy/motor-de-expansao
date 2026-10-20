"""Fatores de atualizacao da renda: arquivos versionados DENTRO do pacote, lidos com erro explicito.

Um arquivo por versao em `fatores/<PAIS>/<versao>.json`, nunca editado depois de publicado, e
um `fatores/<PAIS>/VIGENTE` com o nome da versao em uso. Os arquivos viajam na imagem (sao
`.json` e um arquivo sem extensao: o hatch empacota os dois; `.csv` seria descartado em
silencio pelo `.gitignore`) e sobem por digest, com o mesmo controle de mudanca do codigo.
NAO moram no `MOTOR_DATA_DIR` de proposito: o `perfil.json` montado na VPS ja sofreu drift.

O diretorio e escolhido pelo pais do perfil (DEC-047) -- leitura de configuracao declarada,
nunca um ramo de codigo por pais.

Diferenca deliberada para o `_carregar_fator_temporal` de `dashboard/constants.py`: aquele
caia em 1,0 EM SILENCIO quando o JSON faltava ou era implausivel. Aqui arquivo ausente,
ilegivel ou incoerente levanta `FatoresRendaInvalidos` -- tambem em dev, porque a
configuracao vai na imagem e ausencia e build quebrado, nao acidente de ambiente.

Rollback de emergencia sem rebuild: `MOTOR_FATORES_RENDA_VERSAO=<versao>` fixa uma versao
que JA EXISTE no diretorio do pais (log WARNING a cada carga).
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

_LOG = logging.getLogger("motor_expansao.renda")

#: Raiz dos fatores versionados (um subdiretorio por pais).
DIR_FATORES = Path(__file__).resolve().parent / "fatores"
#: Nome do arquivo que aponta a versao em uso.
ARQUIVO_VIGENTE = "VIGENTE"
#: Variavel de ambiente de rollback/fixacao de versao.
ENV_VERSAO = "MOTOR_FATORES_RENDA_VERSAO"

#: Faixa plausivel de QUALQUER fator (per capita, domiciliar, moradores).
FAIXA_FATOR = (0.9, 1.8)
#: Tolerancia da coerencia interna |per_capita x moradores / domiciliar - 1|.
TOLERANCIA_COERENCIA = 0.005

TIPOS_FATOR = ("per_capita", "domiciliar")

_CHAVES_OBRIGATORIAS = (
    "versao",
    "pais",
    "ano_base_renda",
    "data_referencia_base",
    "ano_alvo",
    "fonte",
    "data_extracao",
    "metodo",
    "nacional",
    "regra_excecao",
    "candidatas_regra",
    "excecoes_aprovadas",
    "ponte_ipca",
    "dec",
    "aprovado_por",
    "relatorio",
    "rotulo_referencia",
    "rotulo_pdf",
    "artefatos_obrigatorios",
    "artefato_k_obrigatorio",
)

# Nome de versao e de pais viram caminho: so caracteres que nao escapam do diretorio.
_RE_VERSAO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_RE_PAIS = re.compile(r"^[A-Z]{2}$")


class FatoresRendaInvalidos(RuntimeError):
    """Configuracao de fatores de renda ausente, ilegivel ou incoerente (erro na subida)."""


@dataclass(frozen=True)
class FatoresGrupo:
    """Fatores de um recorte (nacional ou UF de excecao)."""

    per_capita: float
    domiciliar: float
    moradores: float


@dataclass(frozen=True)
class FatoresRenda:
    """Uma versao de fatores validada. Imutavel: o cache devolve a MESMA instancia."""

    versao: str
    pais: str
    ano_base_renda: int
    data_referencia_base: str
    ano_alvo: int
    fonte: dict[str, Any]
    data_extracao: str
    metodo: str
    nacional: FatoresGrupo
    regra_excecao: dict[str, Any] | None
    candidatas_regra: tuple[str, ...]
    excecoes_aprovadas: dict[str, FatoresGrupo]
    evidencias_excecao: dict[str, Any]
    ponte_ipca: float | None
    dec: str | None
    aprovado_por: str | None
    relatorio: dict[str, Any] | None
    rotulo_referencia: str
    rotulo_pdf: str
    artefatos_obrigatorios: tuple[str, ...]
    artefato_k_obrigatorio: bool
    fixada_por_env: bool
    caminho: Path = field(compare=False)

    def grupo(self, uf: object) -> FatoresGrupo:
        """Fatores da UF se ela tem excecao APROVADA; senao, os nacionais."""
        if uf is None or uf != uf:  # None/NaN -> nacional
            return self.nacional
        chave = str(uf).strip().upper()
        return self.excecoes_aprovadas.get(chave, self.nacional)


# --------------------------------------------------------------------------------
# Validacao
# --------------------------------------------------------------------------------


def _erro(caminho: Path, problema: str) -> FatoresRendaInvalidos:
    return FatoresRendaInvalidos(f"fatores de renda {caminho}: {problema}")


def _numero(valor: Any, caminho: Path, campo: str) -> float:
    # bool e subclasse de int: `true` no JSON nao pode passar por fator 1.
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise _erro(caminho, f"`{campo}` deveria ser numero, veio {type(valor).__name__}")
    f = float(valor)
    if not math.isfinite(f):
        raise _erro(caminho, f"`{campo}` nao e finito ({valor!r})")
    return f


def _inteiro(valor: Any, caminho: Path, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise _erro(caminho, f"`{campo}` deveria ser inteiro, veio {type(valor).__name__}")
    return valor


def _texto(valor: Any, caminho: Path, campo: str, *, nulo: bool = False) -> str | None:
    if valor is None and nulo:
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise _erro(caminho, f"`{campo}` deveria ser texto nao vazio, veio {valor!r}")
    return valor


def _grupo(bruto: Any, caminho: Path, campo: str) -> FatoresGrupo:
    if not isinstance(bruto, dict):
        raise _erro(caminho, f"`{campo}` deveria ser objeto")
    valores = {}
    for chave in ("per_capita", "domiciliar", "moradores"):
        if chave not in bruto:
            raise _erro(caminho, f"`{campo}.{chave}` ausente e obrigatorio")
        v = _numero(bruto[chave], caminho, f"{campo}.{chave}")
        lo, hi = FAIXA_FATOR
        if not lo <= v <= hi:
            raise _erro(caminho, f"`{campo}.{chave}` = {v} fora da faixa plausivel [{lo}, {hi}]")
        valores[chave] = v
    g = FatoresGrupo(**valores)
    # Coerencia interna: domiciliar = per capita x moradores. E a identidade que impede a
    # dupla correcao -- a queda de moradores entra UMA vez, dentro do fator domiciliar.
    desvio = abs(g.per_capita * g.moradores / g.domiciliar - 1.0)
    if desvio > TOLERANCIA_COERENCIA:
        raise _erro(
            caminho,
            f"`{campo}` incoerente: per_capita x moradores / domiciliar - 1 = {desvio:.4%} "
            f"(tolerancia {TOLERANCIA_COERENCIA:.1%})",
        )
    return g


def validar_versao(dados: Any, caminho: Path, *, pais: str, versao: str) -> dict[str, Any]:
    """Valida o JSON bruto de uma versao e devolve os campos ja tipados (sem `fixada_por_env`)."""
    if not isinstance(dados, dict):
        raise _erro(caminho, "o arquivo deveria conter um objeto JSON")
    faltando = [c for c in _CHAVES_OBRIGATORIAS if c not in dados]
    if faltando:
        raise _erro(caminho, f"chave(s) obrigatoria(s) ausente(s): {', '.join(faltando)}")

    if dados["versao"] != versao:
        raise _erro(caminho, f"`versao` = {dados['versao']!r} difere do nome do arquivo ({versao!r})")
    if dados["pais"] != pais:
        raise _erro(caminho, f"`pais` = {dados['pais']!r} difere do pais pedido ({pais!r})")

    fonte = dados["fonte"]
    if not isinstance(fonte, dict):
        raise _erro(caminho, "`fonte` deveria ser objeto")
    _texto(fonte.get("pesquisa"), caminho, "fonte.pesquisa")

    nacional = _grupo(dados["nacional"], caminho, "nacional")

    regra = dados["regra_excecao"]
    if regra is not None and not isinstance(regra, dict):
        raise _erro(caminho, "`regra_excecao` deveria ser objeto ou null")

    candidatas = dados["candidatas_regra"]
    if not isinstance(candidatas, list) or not all(isinstance(c, str) for c in candidatas):
        raise _erro(caminho, "`candidatas_regra` deveria ser lista de UFs")
    candidatas_norm = tuple(c.strip().upper() for c in candidatas)

    excecoes_bruto = dados["excecoes_aprovadas"]
    if not isinstance(excecoes_bruto, dict):
        raise _erro(caminho, "`excecoes_aprovadas` deveria ser objeto UF -> fatores")
    excecoes: dict[str, FatoresGrupo] = {}
    evidencias: dict[str, Any] = {}
    for uf_bruta, bruto in excecoes_bruto.items():
        uf = str(uf_bruta).strip().upper()
        # A regra so APONTA candidatas; o humano aprova entre elas. UF aprovada fora da
        # lista e aprovacao sem regra -- recusada.
        if uf not in candidatas_norm:
            raise _erro(
                caminho, f"excecao aprovada para {uf!r}, que nao esta em `candidatas_regra`"
            )
        excecoes[uf] = _grupo(bruto, caminho, f"excecoes_aprovadas.{uf}")
        if "evidencia" not in bruto:
            raise _erro(caminho, f"`excecoes_aprovadas.{uf}.evidencia` ausente e obrigatorio")
        evidencias[uf] = bruto["evidencia"]

    ponte = dados["ponte_ipca"]
    ponte_f = None if ponte is None else _numero(ponte, caminho, "ponte_ipca")

    relatorio = dados["relatorio"]
    if relatorio is not None:
        if not isinstance(relatorio, dict):
            raise _erro(caminho, "`relatorio` deveria ser objeto {caminho, sha256} ou null")
        for chave in ("caminho", "sha256"):
            _texto(relatorio.get(chave), caminho, f"relatorio.{chave}")

    rotulo_pdf = _texto(dados["rotulo_pdf"], caminho, "rotulo_pdf")
    assert rotulo_pdf is not None
    # O PDF (fpdf2, fonte core) troca por "?" em silencio tudo que nao e latin-1; o
    # rotulo e ASCII puro para nao depender de quem o desenha.
    if not rotulo_pdf.isascii():
        raise _erro(caminho, "`rotulo_pdf` deveria ser ASCII puro (render do PDF)")

    artefatos = dados["artefatos_obrigatorios"]
    if not isinstance(artefatos, list) or not all(
        isinstance(a, str) and a and "/" not in a and "\\" not in a for a in artefatos
    ):
        raise _erro(caminho, "`artefatos_obrigatorios` deveria ser lista de nomes de arquivo")
    exige_k = dados["artefato_k_obrigatorio"]
    if not isinstance(exige_k, bool):
        raise _erro(caminho, "`artefato_k_obrigatorio` deveria ser booleano")

    return {
        "versao": versao,
        "pais": pais,
        "ano_base_renda": _inteiro(dados["ano_base_renda"], caminho, "ano_base_renda"),
        "data_referencia_base": _texto(
            dados["data_referencia_base"], caminho, "data_referencia_base"
        ),
        "ano_alvo": _inteiro(dados["ano_alvo"], caminho, "ano_alvo"),
        "fonte": dict(fonte),
        "data_extracao": _texto(dados["data_extracao"], caminho, "data_extracao"),
        "metodo": _texto(dados["metodo"], caminho, "metodo"),
        "nacional": nacional,
        "regra_excecao": None if regra is None else dict(regra),
        "candidatas_regra": candidatas_norm,
        "excecoes_aprovadas": excecoes,
        "evidencias_excecao": evidencias,
        "ponte_ipca": ponte_f,
        "dec": _texto(dados["dec"], caminho, "dec", nulo=True),
        "aprovado_por": _texto(dados["aprovado_por"], caminho, "aprovado_por", nulo=True),
        "relatorio": None if relatorio is None else dict(relatorio),
        "rotulo_referencia": _texto(dados["rotulo_referencia"], caminho, "rotulo_referencia"),
        "rotulo_pdf": rotulo_pdf,
        "artefatos_obrigatorios": tuple(artefatos),
        "artefato_k_obrigatorio": exige_k,
    }


# --------------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------------


def _pais_padrao() -> str:
    # Import tardio: o pais so e resolvido quando alguem pede fator, nunca no import do
    # pacote (o bot importa `perfil` sem staging -- DEC-049).
    from motor_expansao.perfil import resolver_perfil

    return resolver_perfil().pais


def _ler_fatores(raiz: Path, pais: str) -> FatoresRenda:
    if not isinstance(pais, str) or not _RE_PAIS.match(pais):
        raise FatoresRendaInvalidos(f"pais invalido para fatores de renda: {pais!r}")
    dir_pais = raiz / pais
    if not dir_pais.is_dir():
        raise FatoresRendaInvalidos(
            f"fatores de renda: diretorio do pais {pais!r} ausente ({dir_pais})"
        )

    versao_env = os.environ.get(ENV_VERSAO, "").strip()
    fixada_por_env = bool(versao_env)
    if fixada_por_env:
        versao = versao_env
        _LOG.warning(
            "ROLLBACK/fixacao de versao ativo: %s=%s fixa os fatores de renda de %s "
            "(o arquivo %s e ignorado)",
            ENV_VERSAO, versao, pais, ARQUIVO_VIGENTE,
        )
    else:
        vigente = dir_pais / ARQUIVO_VIGENTE
        if not vigente.is_file():
            raise FatoresRendaInvalidos(f"fatores de renda: {vigente} ausente")
        versao = vigente.read_text(encoding="utf-8").strip()
        if not versao:
            raise FatoresRendaInvalidos(f"fatores de renda: {vigente} vazio")

    if not _RE_VERSAO.match(versao):
        raise FatoresRendaInvalidos(f"fatores de renda: nome de versao invalido {versao!r}")
    caminho = dir_pais / f"{versao}.json"
    if not caminho.is_file():
        origem = ENV_VERSAO if fixada_por_env else ARQUIVO_VIGENTE
        raise FatoresRendaInvalidos(
            f"fatores de renda: versao {versao!r} (de {origem}) nao existe em {dir_pais}"
        )
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _erro(caminho, f"JSON invalido ({exc})") from exc

    campos = validar_versao(dados, caminho, pais=pais, versao=versao)
    return FatoresRenda(**campos, fixada_por_env=fixada_por_env, caminho=caminho)


@lru_cache(maxsize=8)
def carregar_fatores(pais: str | None = None, *, raiz: Path | None = None) -> FatoresRenda:
    """Versao de fatores em uso para `pais` (default: o pais do perfil da instancia).

    `raiz` alternativa existe SO para teste. A variavel `MOTOR_FATORES_RENDA_VERSAO` e lida
    na primeira carga e fica no cache -- trocar a fixacao exige restart (ou `cache_clear`).
    """
    return _ler_fatores(
        Path(raiz) if raiz is not None else DIR_FATORES,
        pais if pais is not None else _pais_padrao(),
    )
