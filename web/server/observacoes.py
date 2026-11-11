"""Anotações nos pinos de concorrentes: a âncora da academia e o que cada pessoa enxerga.

Três regras de produto (Juan, 05/11/2026) vivem aqui, e não no banco, porque são de
APRESENTAÇÃO — o banco guarda tudo, sempre:

1. **O nome do autor só sai para quem tem `concorrente.ver_autor` (Growth).** Os demais recebem
   `Pessoa 1`, `Pessoa 2`… O filtro é no SERVIDOR: esconder no front deixaria o nome no JSON, e
   qualquer um o leria no F12 → Rede.
2. **A numeração é por ACADEMIA e estável.** Ordem da primeira anotação de cada autor, contando
   as apagadas — senão "Pessoa 2" viraria "Pessoa 1" quando alguém apagasse. Numeração global
   (entre academias) deixaria cruzar anotações e descobrir quem é quem.
3. **Apagada some para quem não é Growth.** Growth vê a anotação apagada, por quem e quando, e o
   histórico de versões de cada uma.

A âncora (`chave_concorrente`) é calculada aqui para os DOIS universos de pino — o cadastro de
cadeias (`concorrentes_mapeados`) e as unidades de rede do agregador —, e é a única coisa que o
front devolve ao servidor: rede, nome e coordenada da academia anotada saem do índice de pinos do
próprio servidor, nunca do corpo da requisição.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict
from typing import Any

from motor_expansao.db.observacoes import CamposObservacao, Observacao, RegistroHistorico
from motor_expansao.vulnerabilidade.contrato import nome_base

#: Versão da fórmula da chave. Mudar a fórmula sem mudar este prefixo faria as anotações antigas
#: só serem achadas pela proximidade — funciona, mas em silêncio.
PREFIXO_CHAVE = "obs-v1"

#: Resolução da célula na chave: a MESMA da chave de churn (DEC-063, `H3_RES_CHAVE_CHURN`), pela
#: mesma razão medida lá — res-7 trocava de célula em re-geocodificação sem a academia sair do
#: lugar. O que ainda cruza res-5 a leitura por proximidade recupera.
RES_CELULA_CHAVE = 5

#: As faixas dos CHECK da 023, repetidas aqui para o erro sair legível (422) em vez de 500.
#: (campo, rótulo na tela, mínimo, máximo) dos inteiros.
INTEIROS = (
    ("metragem_m2", "Metragem", 50, 20_000),
    ("vagas", "Vagas de estacionamento", 0, 5_000),
    ("nota_conservacao", "A nota de conservação", 1, 5),
    ("nota_fachada", "A nota de fachada", 1, 5),
    ("nota_atendimento", "A nota de atendimento", 1, 5),
    ("alunos_estimados", "Alunos estimados", 1, 50_000),
)
#: Teto de caracteres dos três textos livres (pedido de 11/11/2026; eram 1.000, 1.000 e 2.000).
#: Mais justo que o CHECK `chk_observacao_tamanho_texto` da 023, que segue em 1.000/2.000: o banco
#: mais largo que a aplicação é o lado seguro e dispensa migration. O MESMO número de
#: `TEXTO_MAXIMO` em `web/src/lib/observacoes.ts` (teste amarra os dois).
TEXTO_MAXIMO = 250
#: (campo, rótulo, teto de caracteres) dos textos livres.
TEXTOS = (
    ("equipamentos", "O campo de equipamentos", TEXTO_MAXIMO),
    ("comodidades", "O campo de comodidades e aulas coletivas", TEXTO_MAXIMO),
    ("comentario", "O comentário", TEXTO_MAXIMO),
)


def chave_concorrente(rede: object, nome: object, lat: object, lng: object) -> str | None:
    """sha1 de `obs-v1 | rede | nome-base | célula res-5`. `None` para coordenada inválida."""
    import h3

    try:
        la, ln = float(lat), float(lng)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if la != la or ln != ln or not (-90 <= la <= 90 and -180 <= ln <= 180):
        return None
    celula = h3.latlng_to_cell(la, ln, RES_CELULA_CHAVE)
    payload = f"{PREFIXO_CHAVE}|{str(rede or '').strip()}|{nome_base(nome)}|{celula}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class CampoInvalido(ValueError):
    """Corpo bem formado com valor fora da regra (422)."""


#: Texto que vale como inteiro: só dígitos ASCII (`str.isdigit` aceitaria "²" e outros).
_SO_DIGITOS = re.compile(r"[0-9]+")


def _texto(valor: object, limite: int, rotulo: str) -> str | None:
    """Texto livre é `str`: número, booleano, lista ou objeto são recusados, nunca passados
    por `str()` (que gravaria "12", "True" ou "{'a': 1}" como se alguém tivesse escrito)."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise CampoInvalido(f"{rotulo} precisa ser texto.")
    texto = valor.strip()
    if len(texto) > limite:
        raise CampoInvalido(f"{rotulo} passa de {limite:,} caracteres.".replace(",", "."))
    return texto or None


def _como_inteiro(valor: object) -> int | None:
    """O inteiro que `valor` representa SEM conversão criativa, ou `None` se não for um.

    Vale: `int` (bool não: em Python `True` é 1), `float` sem parte decimal (o `7.0` de um
    cliente JSON) e texto só de dígitos (`" 1450 "`). Não vale: decimal, notação científica
    ("1e3" virava 1.000), `inf`/`NaN` (o `int(round(inf))` derrubava a rota com 500) e letra.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(valor) if math.isfinite(valor) and valor.is_integer() else None
    if isinstance(valor, str) and _SO_DIGITOS.fullmatch(valor.strip()):
        return int(valor.strip())
    return None


def _inteiro(valor: object, rotulo: str, minimo: int, maximo: int) -> int | None:
    if valor is None or (isinstance(valor, str) and valor.strip() == ""):
        return None
    inteiro = _como_inteiro(valor)
    if inteiro is None:
        raise CampoInvalido(f"{rotulo} precisa ser um número inteiro.")
    if not minimo <= inteiro <= maximo:
        faixa = f"{minimo:,} a {maximo:,}".replace(",", ".")
        raise CampoInvalido(f"{rotulo} fora da faixa aceita ({faixa}).")
    return inteiro


def normalizar_campos(**valores: object) -> CamposObservacao:
    """Mesmas regras dos CHECK da 023, para o erro sair legível em vez de 500 do banco.

    Recebe os campos pelo nome de `CamposObservacao`; campo ausente vale vazio.
    """
    saida: dict[str, Any] = {}
    for campo, rotulo, minimo, maximo in INTEIROS:
        saida[campo] = _inteiro(valores.get(campo), rotulo, minimo, maximo)
    for campo, rotulo, limite in TEXTOS:
        saida[campo] = _texto(valores.get(campo), limite, rotulo)
    if all(v is None for v in saida.values()):
        raise CampoInvalido("Preencha ao menos um campo da anotação.")
    return CamposObservacao(**saida)


def campos_json(campos: CamposObservacao) -> dict[str, Any]:
    """Os campos com os MESMOS nomes que o front manda e recebe."""
    return asdict(campos)


def rotulos_por_autor(observacoes: Sequence[Observacao]) -> dict[int, str]:
    """`id_usuario -> "Pessoa N"`, pela ordem da 1ª anotação de cada autor NESTA academia."""
    ordem: dict[int, str] = {}
    for obs in sorted(observacoes, key=lambda o: (o.criada_em, o.id_observacao)):
        if obs.id_usuario_autor not in ordem:
            ordem[obs.id_usuario_autor] = f"Pessoa {len(ordem) + 1}"
    return ordem


def _iso(valor: Any) -> str | None:
    return valor.isoformat() if valor is not None else None


def montar_resposta(
    observacoes: Sequence[Observacao],
    *,
    id_viewer: int,
    ver_autor: bool,
    pode_anotar: bool,
    historico: Iterable[RegistroHistorico] = (),
    nomes: Mapping[int, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """O payload do painel. Quem não é Growth NUNCA recebe nome, histórico nem apagada.

    `historico` e `nomes` só são consultados pela rota quando `ver_autor` é verdadeiro; se
    chegarem sem ele, são ignorados aqui também — a regra não depende da disciplina do chamador.
    """
    rotulos = rotulos_por_autor(observacoes)
    nomes = dict(nomes or {}) if ver_autor else {}
    por_obs: dict[int, list[RegistroHistorico]] = {}
    if ver_autor:
        for registro in historico:
            por_obs.setdefault(registro.id_observacao, []).append(registro)

    saida: list[dict[str, Any]] = []
    for obs in sorted(observacoes, key=lambda o: (o.criada_em, o.id_observacao)):
        apagada = obs.apagada_em is not None
        if apagada and not ver_autor:
            continue
        minha = obs.id_usuario_autor == id_viewer
        item: dict[str, Any] = {
            "id": obs.id_observacao,
            "autor_rotulo": rotulos[obs.id_usuario_autor],
            "minha": minha,
            **campos_json(obs.campos),
            "criada_em": _iso(obs.criada_em),
            "atualizada_em": _iso(obs.atualizada_em),
            "editada": obs.versao > 1,
            "versao": obs.versao,
            "pode_editar": minha and not apagada and pode_anotar,
            "pode_apagar": not apagada and pode_anotar and (minha or ver_autor),
        }
        if ver_autor:
            nome, perfil = nomes.get(obs.id_usuario_autor, ("(sem cadastro)", ""))
            item["autor_nome"] = nome
            item["autor_perfil"] = perfil
            item["apagada"] = (
                {
                    "por": nomes.get(obs.apagada_por or -1, ("(sem cadastro)", ""))[0],
                    "em": _iso(obs.apagada_em),
                    "moderacao": obs.apagada_por != obs.id_usuario_autor,
                }
                if apagada
                else None
            )
            anterior: RegistroHistorico | None = None
            linhas: list[dict[str, Any]] = []
            for registro in por_obs.get(obs.id_observacao, []):
                versao_anterior = None
                if registro.acao == "editada" and anterior is not None:
                    versao_anterior = campos_json(anterior.campos)
                linhas.append(
                    {
                        "acao": registro.acao,
                        "versao": registro.versao,
                        "por": nomes.get(registro.registrado_por or -1, ("(sistema)", ""))[0],
                        "em": _iso(registro.registrado_em),
                        "moderacao": registro.acao == "apagada"
                        and registro.registrado_por != obs.id_usuario_autor,
                        "versao_anterior": versao_anterior,
                    }
                )
                anterior = registro
            item["historico"] = linhas
        saida.append(item)

    return {"pode_anotar": pode_anotar, "pode_moderar": ver_autor, "observacoes": saida}


def ids_para_nomes(
    observacoes: Sequence[Observacao], historico: Iterable[RegistroHistorico]
) -> set[int]:
    """Todos os `id_usuario` que o payload de Growth vai nomear: autores, moderadores e editores."""
    ids = {o.id_usuario_autor for o in observacoes}
    ids |= {o.apagada_por for o in observacoes if o.apagada_por is not None}
    ids |= {r.registrado_por for r in historico if r.registrado_por is not None}
    return ids
