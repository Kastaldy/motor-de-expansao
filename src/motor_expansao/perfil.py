"""Perfil do pais da instancia — resolvido UMA vez, no import.

Este modulo e a entrada da DEC-047: o pais e propriedade do DEPLOY, nao um `if` no
codigo. Um processo serve um pais so; qual pais e isso esta declarado no `perfil.json`
que mora na raiz do `MOTOR_DATA_DIR`, e e lido aqui.

Nao existe (e nao deve passar a existir) nenhum `if pais == "AR"` na plataforma: o que
muda entre paises sao os NUMEROS e os TEXTOS que este arquivo carrega, nunca o caminho
de codigo. `tests/contracts/test_fio_de_alarme_pais.py` (commit A10) e o que trava isso.

Ver `docs/spec_bloco_a_perfil.md` §1 (schema), §3 (carga) e `docs/decisions/DEC-047.md`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

__all__ = [
    "Ancoras",
    "Bbox",
    "Fonte",
    "Fontes",
    "Geocode",
    "Metas",
    "Moeda",
    "Perfil",
    "PerfilInvalidoError",
    "Reguas",
    "Vista",
    "PERFIL_BR_EMBARCADO",
    "SCHEMA_VERSAO",
    "SUPERFICIES_VALIDAS",
    "carregar_perfil",
    "resolver_perfil",
]


class PerfilInvalidoError(RuntimeError):
    """Perfil ausente, ilegivel ou fora do contrato -> o processo NAO sobe.

    Fail-closed de proposito: um perfil pela metade nao produz erro, produz numero
    errado com cara de certo. A mensagem SEMPRE nomeia o campo e o arquivo.
    """


#: Unica versao de schema aceita. Existe para um pacote antigo do pipeline encontrar
#: um loader novo e falhar ALTO, em vez de ser lido com campo faltando.
SCHEMA_VERSAO = 1

#: Vocabulario de superficie. E o ESPELHO de `ABAS_VALIDAS` (`web/server/acesso.py`),
#: copiado e nao importado porque `src/motor_expansao/` nunca importa de `web/server/`
#: (o pacote roda tambem na imagem da API, onde `web/server` nao esta no sys.path).
#: `tests/contracts/test_perfil_espelha_abas_validas.py` trava que os dois batem — se
#: alguem criar uma aba nova em `acesso.py` e esquecer daqui, o teste falha nomeando-a.
SUPERFICIES_VALIDAS = frozenset(
    {"executiva", "imobiliaria", "mapa", "oportunidades", "viabilidade"}
)

_RE_PAIS = re.compile(r"^[A-Z]{2}$")
_RE_MOEDA = re.compile(r"^[A-Z]{3}$")
#: Tag BCP-47 UNICA. E o que `locale` tem de ser: quem o consome e
#: `new Intl.NumberFormat(locale, ...)`, que quer uma tag, nao uma lista.
_RE_LOCALE = re.compile(r"^[a-z]{2}(-[A-Za-z0-9]{2,8})*$")

#: `geocode.idioma` NAO e um locale: e o valor de um header `Accept-Language`, que por
#: RFC 9110 aceita LISTA com fallback e q-value — `es-AR,es` e `pt-BR,pt;q=0.9` sao
#: validos e uteis. Ate 2026-09-02 este campo era validado por `_RE_LOCALE`, e o efeito
#: era concreto: o `data/perfis/AR/perfil.json`, que declara `es-AR,es`, REPROVAVA no
#: loader — ou seja, a instancia argentina nao subiria, e o defeito so apareceria no
#: primeiro boot da AR. Dois campos com formatos diferentes precisam de duas regras.
_RE_ACCEPT_LANGUAGE = re.compile(
    r"^[a-z]{2}(-[A-Za-z0-9]{2,8})*(;q=[01](\.\d{1,3})?)?"
    r"(\s*,\s*[a-z]{2}(-[A-Za-z0-9]{2,8})*(;q=[01](\.\d{1,3})?)?)*$"
)

_RE_COUNTRYCODES = re.compile(r"^[a-z]{2}(,[a-z]{2})*$")


@dataclass(frozen=True, slots=True)
class Bbox:
    """Caixa do pais. No Brasil e a B1 (spec §1.3), a caixa que as rotas ja aceitam."""

    lat_min: float
    lat_max: float
    lng_min: float
    lng_max: float

    def contem(self, lat: float, lng: float) -> bool:
        return (
            self.lat_min <= lat <= self.lat_max
            and self.lng_min <= lng <= self.lng_max
        )


@dataclass(frozen=True, slots=True)
class Moeda:
    codigo: str
    simbolo: str


@dataclass(frozen=True, slots=True)
class Vista:
    """Vista inicial do mapa. Lida na PRIMEIRA pintura — ver spec §3.5, classe (2)."""

    lat: float
    lng: float
    zoom: float


@dataclass(frozen=True, slots=True)
class Geocode:
    countrycodes: str
    idioma: str
    #: `None` = o pais nao tem codigo postal com formato unico. Quem le trata o None.
    regex_cp: str | None


@dataclass(frozen=True, slots=True)
class Fonte:
    nome: str
    detalhe: str


@dataclass(frozen=True, slots=True)
class Fontes:
    censo: Fonte
    crescimento: Fonte


@dataclass(frozen=True, slots=True)
class Metas:
    """As sete metas do semaforo do Relatorio Pontual.

    Sao ALVOS de tela, nao cortes de funil: pintam o card de verde ou vermelho e nao
    entram em decisao nenhuma. Mesmo assim moram no perfil, porque quatro delas sao em
    MOEDA ou em escala do pais — contra renda em outra moeda, o semaforo pinta tudo de
    uma cor por construcao, que e a classe de defeito que produz NUMERO ERRADO em vez de
    erro.
    """

    pop_total_raio: float
    renda_per_capita_media_raio: float
    renda_domiciliar_total_raio: float
    domicilios_total_raio: float
    score_setor_medio: float
    sam_fitness_potencial: float
    residual_fitness_disponivel: float


@dataclass(frozen=True, slots=True)
class Reguas:
    renda_abs_min: float
    renda_abs_max: float
    pop_abs_min: float
    pop_abs_max: float
    score_corte_quente: float
    pop_min_acionavel: int
    oferta_destaque_min: float
    capacidade_concorrente: float
    capacidade_unidade_alunos: int
    #: Responsavel -> domicilio inteiro. E o FALLBACK nacional: no Brasil as tabelas por
    #: municipio e por setor tem precedencia, e este valor so vale onde elas nao alcancam.
    #: Num pais sem essas tabelas, e o unico valor que vale — e por isso ele mora aqui.
    uplift_composicao: float
    #: Moradores medios por domicilio. Mesmo papel de fallback do campo acima.
    moradores_por_domicilio: float
    #: Metas do semaforo do Relatorio Pontual.
    metas_big_numbers: Metas


@dataclass(frozen=True, slots=True)
class Ancoras:
    """As quatro ancoras da regua absoluta, no formato que o pipeline consome.

    Construida a partir de `Reguas` por `Perfil.ancoras()`. Quem a recebe e
    `calibrar_renda_setor_2022` (commit A8), com default `ANCORAS_BR` — este bloco
    entrega a CAPACIDADE de receber ancoras, nao troca ancora nenhuma.
    """

    renda_min: float
    renda_max: float
    pop_min: float
    pop_max: float


@dataclass(frozen=True, slots=True)
class Perfil:
    schema_versao: int
    pais: str
    nome: str
    locale: str
    moeda: Moeda
    bbox: Bbox
    vista_padrao: Vista
    geocode: Geocode
    fontes: Fontes
    reguas: Reguas
    superficies: tuple[str, ...]
    #: Pasta de onde o `perfil.json` veio. E o que substitui o `DATA_DIR` de
    #: `web/server/app.py:102` — os diretorios derivados (outputs, staging, ibge,
    #: ultra, censo_geo, enriched) continuam pendurados nela sem mudar uma linha.
    raiz: Path

    def ancoras(self) -> Ancoras:
        return Ancoras(
            renda_min=self.reguas.renda_abs_min,
            renda_max=self.reguas.renda_abs_max,
            pop_min=self.reguas.pop_abs_min,
            pop_max=self.reguas.pop_abs_max,
        )

    def tem_superficie(self, aba: str) -> bool:
        return aba in self.superficies


#: Perfil BR embarcado. E o default de DEV e de TESTE (§3.2) — NUNCA de producao.
#: Caminho decidido: `data/perfis/BR/perfil.json`, o arquivo que ja esta versionado e
#: que o `data/perfis/LEIA-ME.md` documenta. `data/perfil.json` nao existe.
PERFIL_BR_EMBARCADO = (
    Path(__file__).resolve().parents[2] / "data" / "perfis" / "BR" / "perfil.json"
)


# --------------------------------------------------------------------------------
# Validacao. Duas regras de admissao, para o schema ser UM so (spec §1.2):
#   1. Chave iniciada por `_` e COMENTARIO: o loader a ignora, sem validar tipo.
#   2. Campo fora do schema e sem `_` e TOLERADO, nao reprovado. O fail-closed e
#      sobre AUSENCIA e TIPO do que o schema exige; o que sobra passa. E o que deixa
#      `reguas.score_pesos`, `avisos` e `operacao` viverem nos arquivos com leitor
#      previsto para bloco POSTERIOR sem virarem contrato do Bloco A.
# --------------------------------------------------------------------------------


def _erro(caminho: Path, campo: str, problema: str) -> PerfilInvalidoError:
    return PerfilInvalidoError(f"{caminho}: campo `{campo}` {problema}")


def _obj(bruto: Any, caminho: Path, campo: str) -> dict[str, Any]:
    if not isinstance(bruto, dict):
        raise _erro(caminho, campo, f"deveria ser objeto, veio {type(bruto).__name__}")
    return bruto


def _pegar(dados: dict[str, Any], campo: str, caminho: Path, prefixo: str = "") -> Any:
    nome = f"{prefixo}{campo}"
    if campo not in dados:
        raise _erro(caminho, nome, "ausente e obrigatorio")
    return dados[campo]


def _texto(
    dados: dict[str, Any],
    campo: str,
    caminho: Path,
    *,
    prefixo: str = "",
    padrao: re.Pattern[str] | None = None,
) -> str:
    nome = f"{prefixo}{campo}"
    valor = _pegar(dados, campo, caminho, prefixo)
    if not isinstance(valor, str) or not valor.strip():
        raise _erro(caminho, nome, "deveria ser string nao-vazia")
    if padrao is not None and not padrao.match(valor):
        raise _erro(caminho, nome, f"nao casa com {padrao.pattern!r} (veio {valor!r})")
    return valor


def _numero(
    dados: dict[str, Any], campo: str, caminho: Path, *, prefixo: str = ""
) -> float:
    nome = f"{prefixo}{campo}"
    valor = _pegar(dados, campo, caminho, prefixo)
    # `bool` e subclasse de `int` em Python; `true` num campo numerico e erro de
    # digitacao que passaria calado sem esta linha.
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise _erro(caminho, nome, f"deveria ser numero, veio {type(valor).__name__}")
    return float(valor)


def _inteiro(
    dados: dict[str, Any], campo: str, caminho: Path, *, prefixo: str = ""
) -> int:
    nome = f"{prefixo}{campo}"
    valor = _pegar(dados, campo, caminho, prefixo)
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise _erro(caminho, nome, f"deveria ser inteiro, veio {type(valor).__name__}")
    return valor


def _ler_bbox(dados: dict[str, Any], caminho: Path) -> Bbox:
    bruto = _obj(_pegar(dados, "bbox", caminho), caminho, "bbox")
    bbox = Bbox(
        lat_min=_numero(bruto, "lat_min", caminho, prefixo="bbox."),
        lat_max=_numero(bruto, "lat_max", caminho, prefixo="bbox."),
        lng_min=_numero(bruto, "lng_min", caminho, prefixo="bbox."),
        lng_max=_numero(bruto, "lng_max", caminho, prefixo="bbox."),
    )
    if not -90.0 <= bbox.lat_min <= 90.0 or not -90.0 <= bbox.lat_max <= 90.0:
        raise _erro(caminho, "bbox", "latitude fora de [-90, 90]")
    if not -180.0 <= bbox.lng_min <= 180.0 or not -180.0 <= bbox.lng_max <= 180.0:
        raise _erro(caminho, "bbox", "longitude fora de [-180, 180]")
    if bbox.lat_min >= bbox.lat_max:
        raise _erro(caminho, "bbox", "degenerada: lat_min >= lat_max")
    if bbox.lng_min >= bbox.lng_max:
        raise _erro(caminho, "bbox", "degenerada: lng_min >= lng_max")
    return bbox


def _ler_geocode(dados: dict[str, Any], caminho: Path) -> Geocode:
    bruto = _obj(_pegar(dados, "geocode", caminho), caminho, "geocode")
    # `regex_cp` e o UNICO campo do schema que aceita null — pais sem codigo postal de
    # formato unico. Ausente e erro; null e declaracao.
    regex_cp = _pegar(bruto, "regex_cp", caminho, "geocode.")
    if regex_cp is not None:
        if not isinstance(regex_cp, str) or not regex_cp:
            raise _erro(caminho, "geocode.regex_cp", "deveria ser string ou null")
        try:
            re.compile(regex_cp)
        except re.error as exc:
            raise _erro(
                caminho, "geocode.regex_cp", f"nao compila como regex: {exc}"
            ) from exc
    return Geocode(
        countrycodes=_texto(
            bruto, "countrycodes", caminho, prefixo="geocode.", padrao=_RE_COUNTRYCODES
        ),
        idioma=_texto(
            bruto, "idioma", caminho, prefixo="geocode.", padrao=_RE_ACCEPT_LANGUAGE
        ),
        regex_cp=regex_cp,
    )


def _ler_fonte(dados: dict[str, Any], chave: str, caminho: Path) -> Fonte:
    prefixo = f"fontes.{chave}."
    bruto = _obj(_pegar(dados, chave, caminho, "fontes."), caminho, f"fontes.{chave}")
    return Fonte(
        nome=_texto(bruto, "nome", caminho, prefixo=prefixo),
        detalhe=_texto(bruto, "detalhe", caminho, prefixo=prefixo),
    )


def _ler_metas(reguas: dict[str, Any], caminho: Path) -> Metas:
    bruto = _obj(
        _pegar(reguas, "metas_big_numbers", caminho, "reguas."),
        caminho,
        "reguas.metas_big_numbers",
    )
    p = "reguas.metas_big_numbers."
    metas = Metas(
        pop_total_raio=_numero(bruto, "pop_total_raio", caminho, prefixo=p),
        renda_per_capita_media_raio=_numero(
            bruto, "renda_per_capita_media_raio", caminho, prefixo=p
        ),
        renda_domiciliar_total_raio=_numero(
            bruto, "renda_domiciliar_total_raio", caminho, prefixo=p
        ),
        domicilios_total_raio=_numero(bruto, "domicilios_total_raio", caminho, prefixo=p),
        score_setor_medio=_numero(bruto, "score_setor_medio", caminho, prefixo=p),
        sam_fitness_potencial=_numero(bruto, "sam_fitness_potencial", caminho, prefixo=p),
        residual_fitness_disponivel=_numero(
            bruto, "residual_fitness_disponivel", caminho, prefixo=p
        ),
    )
    # Meta <= 0 pinta o card de VERDE sempre — e um semaforo que nunca acusa e pior que
    # semaforo nenhum, porque parece estar funcionando.
    for campo in (
        "pop_total_raio",
        "renda_per_capita_media_raio",
        "renda_domiciliar_total_raio",
        "domicilios_total_raio",
        "score_setor_medio",
        "sam_fitness_potencial",
        "residual_fitness_disponivel",
    ):
        if getattr(metas, campo) <= 0:
            raise _erro(caminho, f"{p}{campo}", "deveria ser > 0 (meta <= 0 nunca acusa)")
    # O score e 0-100 por construcao: meta acima de 100 nunca fica verde.
    if metas.score_setor_medio > 100:
        raise _erro(caminho, f"{p}score_setor_medio", "deveria ser <= 100")
    return metas


def _ler_reguas(dados: dict[str, Any], caminho: Path) -> Reguas:
    bruto = _obj(_pegar(dados, "reguas", caminho), caminho, "reguas")
    p = "reguas."
    reguas = Reguas(
        renda_abs_min=_numero(bruto, "renda_abs_min", caminho, prefixo=p),
        renda_abs_max=_numero(bruto, "renda_abs_max", caminho, prefixo=p),
        pop_abs_min=_numero(bruto, "pop_abs_min", caminho, prefixo=p),
        pop_abs_max=_numero(bruto, "pop_abs_max", caminho, prefixo=p),
        score_corte_quente=_numero(bruto, "score_corte_quente", caminho, prefixo=p),
        pop_min_acionavel=_inteiro(bruto, "pop_min_acionavel", caminho, prefixo=p),
        oferta_destaque_min=_numero(bruto, "oferta_destaque_min", caminho, prefixo=p),
        capacidade_concorrente=_numero(
            bruto, "capacidade_concorrente", caminho, prefixo=p
        ),
        capacidade_unidade_alunos=_inteiro(
            bruto, "capacidade_unidade_alunos", caminho, prefixo=p
        ),
        uplift_composicao=_numero(bruto, "uplift_composicao", caminho, prefixo=p),
        moradores_por_domicilio=_numero(
            bruto, "moradores_por_domicilio", caminho, prefixo=p
        ),
        metas_big_numbers=_ler_metas(bruto, caminho),
    )
    # Regua degenerada nao levanta na leitura: levanta uma divisao por zero LA na
    # frente, dentro de `nota_renda_absoluta`, com traceback que nao menciona perfil.
    if reguas.renda_abs_min >= reguas.renda_abs_max:
        raise _erro(caminho, "reguas", "degenerada: renda_abs_min >= renda_abs_max")
    if reguas.pop_abs_min >= reguas.pop_abs_max:
        raise _erro(caminho, "reguas", "degenerada: pop_abs_min >= pop_abs_max")
    # A nota de populacao entra em LOG (`np.log(POP_ABS_MIN)`): zero ou negativo nao e
    # numero ruim, e `-inf` silencioso.
    if reguas.pop_abs_min <= 0:
        raise _erro(caminho, "reguas.pop_abs_min", "deveria ser > 0 (a escala e log)")
    # Os dois sao MULTIPLICADORES de renda exibida. Zero ou negativo nao produz erro:
    # produz renda zerada ou negativa na tela, que se le como "regiao pobre".
    if reguas.uplift_composicao <= 0:
        raise _erro(caminho, "reguas.uplift_composicao", "deveria ser > 0")
    if reguas.moradores_por_domicilio <= 0:
        raise _erro(caminho, "reguas.moradores_por_domicilio", "deveria ser > 0")
    return reguas


def _ler_superficies(dados: dict[str, Any], caminho: Path) -> tuple[str, ...]:
    bruto = _pegar(dados, "superficies", caminho)
    if not isinstance(bruto, list) or not bruto:
        raise _erro(caminho, "superficies", "deveria ser lista nao-vazia")
    fora = [s for s in bruto if not isinstance(s, str) or s not in SUPERFICIES_VALIDAS]
    if fora:
        raise _erro(
            caminho,
            "superficies",
            f"valor fora do vocabulario: {fora!r} "
            f"(validos: {sorted(SUPERFICIES_VALIDAS)})",
        )
    return tuple(bruto)


def carregar_perfil(caminho: Path, *, raiz: Path | None = None) -> Perfil:
    """Le, valida e congela o perfil. Qualquer defeito levanta `PerfilInvalidoError`.

    `raiz` e a pasta de dados da instancia — a que vira `DATA_DIR` e de onde penduram
    `outputs/`, `staging/`, `ibge/`, `ultra/`. Default: a pasta do proprio arquivo, que
    e o certo em PRODUCAO (`${MOTOR_DATA_DIR}/perfil.json`). O ramo de dev precisa
    passar explicito: o BR embarcado mora em `data/perfis/BR/`, e derivar dali daria
    `data/perfis/BR/outputs/` — um caminho que nao existe, em silencio.
    """
    caminho = Path(caminho)
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PerfilInvalidoError(
            f"perfil.json ausente em {caminho}. Em producao o arquivo e montado no "
            f"volume (`MOTOR_DATA_DIR`); ver docs/spec_bloco_a_perfil.md §6.1."
        ) from exc
    except OSError as exc:
        raise PerfilInvalidoError(f"perfil.json ilegivel em {caminho}: {exc}") from exc

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise PerfilInvalidoError(f"{caminho}: JSON invalido: {exc}") from exc

    if not isinstance(dados, dict):
        raise PerfilInvalidoError(f"{caminho}: raiz deveria ser objeto JSON")

    versao = _pegar(dados, "schema_versao", caminho)
    if versao != SCHEMA_VERSAO:
        raise _erro(
            caminho,
            "schema_versao",
            f"e {versao!r}; este loader so entende {SCHEMA_VERSAO}",
        )

    fontes_bruto = _obj(_pegar(dados, "fontes", caminho), caminho, "fontes")
    moeda_bruto = _obj(_pegar(dados, "moeda", caminho), caminho, "moeda")
    vista_bruto = _obj(_pegar(dados, "vista_padrao", caminho), caminho, "vista_padrao")

    return Perfil(
        schema_versao=SCHEMA_VERSAO,
        pais=_texto(dados, "pais", caminho, padrao=_RE_PAIS),
        nome=_texto(dados, "nome", caminho),
        locale=_texto(dados, "locale", caminho, padrao=_RE_LOCALE),
        moeda=Moeda(
            codigo=_texto(
                moeda_bruto, "codigo", caminho, prefixo="moeda.", padrao=_RE_MOEDA
            ),
            simbolo=_texto(moeda_bruto, "simbolo", caminho, prefixo="moeda."),
        ),
        bbox=_ler_bbox(dados, caminho),
        vista_padrao=Vista(
            lat=_numero(vista_bruto, "lat", caminho, prefixo="vista_padrao."),
            lng=_numero(vista_bruto, "lng", caminho, prefixo="vista_padrao."),
            zoom=_numero(vista_bruto, "zoom", caminho, prefixo="vista_padrao."),
        ),
        geocode=_ler_geocode(dados, caminho),
        fontes=Fontes(
            censo=_ler_fonte(fontes_bruto, "censo", caminho),
            crescimento=_ler_fonte(fontes_bruto, "crescimento", caminho),
        ),
        reguas=_ler_reguas(dados, caminho),
        superficies=_ler_superficies(dados, caminho),
        raiz=Path(raiz) if raiz is not None else caminho.parent,
    )


@lru_cache(maxsize=1)
def resolver_perfil() -> Perfil:
    """Resolve o perfil da instancia UMA vez por processo.

    `MOTOR_DATA_DIR` setado  => PRODUCAO: fail-closed em `${MOTOR_DATA_DIR}/perfil.json`.
    `MOTOR_DATA_DIR` ausente => DEV/TESTE: carrega o BR versionado do repositorio.

    O ramo de dev existe por uma razao material, nao por conveniencia: 15 modulos de
    teste fazem `import app` no TOPO do arquivo e so depois reapontam caminhos por
    monkeypatch. Um fail-closed incondicional derrubaria os 15 na COLETA do pytest,
    com traceback que nao menciona nada do Bloco A. Ver spec §3.2.
    """
    raiz = os.environ.get("MOTOR_DATA_DIR")
    if raiz:
        return carregar_perfil(Path(raiz) / "perfil.json", raiz=Path(raiz))
    # `parents[2]` do BR embarcado = o `data/` do repositorio, que e a raiz de dados de
    # dev — e NAO a `data/perfis/BR/` onde o arquivo mora.
    return carregar_perfil(
        PERFIL_BR_EMBARCADO, raiz=PERFIL_BR_EMBARCADO.parents[2]
    )
