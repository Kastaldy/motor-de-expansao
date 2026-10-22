"""Contrato: os tipos TypeScript do Top 10 espelham o payload que o servidor manda.

O bloco `recomendacao` tem UM serializador, `Recomendacao.para_payload` (pacote
`motor_expansao.recomendacao`), e o front o le pelas interfaces de `web/src/lib/types.ts`
(`RecomendacaoTop10`, `ReguaTop10`, `RecorteTop10`, `RendaTop10`, `SegmentoTop10Payload`,
`VagaTop10`, `HexagonosTop10Payload`). Nada amarra os dois lados sozinho: o vitest usa uma
fixture escrita a mao, o `tsc` nao enxerga o JSON do servidor e o pytest nao le TypeScript.
Se o modulo renomear ou tirar uma chave (`residual_medido`, por exemplo), o front passa a ler
`undefined` -- e toda Mata Virgem viraria "não medido" -- com as tres suites verdes.

Mesmo molde de `test_perfil_front_espelha_o_python.py` e de
`test_todo_tom_publicado_existe_no_tipo_Tom_do_front`: este arquivo le o `types.ts` e confere,
para payloads REAIS das rotas (vaga preenchida, vaga vazia, segmento indisponivel sem o
carimbo k):

- toda chave que o servidor manda esta declarada no tipo, e todo campo obrigatorio do tipo
  vem no payload;
- todo campo que o servidor manda nulo e' `| null` no tipo;
- string literal (`'mata_virgem' | 'premium'`, status, motivo, nivel) cai dentro da uniao;
- `string`/`number`/`boolean` batem com o valor.

O "parser" de TypeScript aqui e' deliberadamente pequeno: so' interfaces de campos simples,
objetos inline e aliases de uniao de literais -- e o teste falha alto se nao reconhecer uma
linha, em vez de ignora-la.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from tests.unit.test_piloto_web_recomendacao_top10 import (  # noqa: F401
    SEGMENTOS,
    pilot,
    top10_data,
    top10_sem_k,
)

_TIPOS = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "types.ts"
#: Aliases de uniao de literais que os campos do Top 10 usam.
_ALIASES = ("SegmentoTop10", "StatusSegmentoTop10", "MotivoVagaTop10")


def _fonte() -> str:
    return _TIPOS.read_text(encoding="utf-8").replace("\r\n", "\n")


def _sem_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    return re.sub(r"//[^\n]*", "", texto)


def _corpo_da_interface(fonte: str, nome: str) -> str:
    achado = re.search(rf"export interface {nome}\b[^{{]*\{{", fonte)
    assert achado, f"types.ts deixou de declarar `export interface {nome}`"
    i = inicio = achado.end()
    profundidade = 1
    while profundidade:
        if fonte[i] == "{":
            profundidade += 1
        elif fonte[i] == "}":
            profundidade -= 1
        i += 1
    return fonte[inicio : i - 1]


def _campos(corpo: str) -> dict[str, tuple[bool, str]]:
    """`campo -> (opcional, tipo)`, no nivel de cima do corpo.

    O tipo vem CRU (objeto inline inteiro, com as quebras de linha que separam os campos dele):
    quem compara normaliza os espacos.
    """
    campos: dict[str, tuple[bool, str]] = {}
    profundidade = 0
    atual: list[str] = []
    for c in _sem_comentarios(corpo) + "\n":
        if c in "{(<[":
            profundidade += 1
        elif c in "})>]":
            profundidade -= 1
        if c in "\n;" and profundidade == 0:
            linha = "".join(atual).strip()
            atual = []
            if not linha:
                continue
            achado = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(\?)?\s*:\s*(.+)$", linha, flags=re.S)
            assert achado, f"linha de types.ts que este contrato nao sabe ler: {linha!r}"
            campos[achado.group(1)] = (bool(achado.group(2)), achado.group(3).strip())
        else:
            atual.append(c)
    return campos


def _literais(fonte: str, alias: str) -> set[str]:
    achado = re.search(rf"export type {alias} =([^\n]+)", fonte)
    assert achado, f"types.ts deixou de declarar `export type {alias}` numa linha so"
    return set(re.findall(r"'([^']*)'", achado.group(1)))


def _conferir(
    obj: dict[str, Any],
    campos: dict[str, tuple[bool, str]],
    onde: str,
    literais: dict[str, set[str]],
    problemas: list[str],
) -> None:
    obrigatorios = {k for k, (opcional, _) in campos.items() if not opcional}
    if faltam := sorted(obrigatorios - set(obj)):
        problemas.append(f"{onde}: o payload nao traz {faltam}, que o tipo do front exige")
    if sobram := sorted(set(obj) - set(campos)):
        problemas.append(f"{onde}: o payload traz {sobram}, que o tipo do front nao declara")
    for chave, valor in obj.items():
        if chave not in campos:
            continue
        tipo = campos[chave][1]
        if tipo.startswith("{"):
            if isinstance(valor, dict):
                _conferir(valor, _campos(tipo[1:-1]), f"{onde}.{chave}", literais, problemas)
            elif valor is not None:
                problemas.append(f"{onde}.{chave}: o tipo e' um objeto e veio {valor!r}")
            continue
        tipo = " ".join(tipo.split())
        alternativas = {t.strip() for t in tipo.split("|")}
        if valor is None:
            if "null" not in alternativas:
                problemas.append(
                    f"{onde}.{chave}: o servidor manda null e o tipo diz {tipo!r} (falta | null)"
                )
            continue
        permitidos: set[str] = set()
        for t in alternativas:
            if t.startswith("'"):
                permitidos.add(t.strip("'"))
            elif t in literais:
                permitidos |= literais[t]
        if permitidos and valor not in permitidos:
            problemas.append(f"{onde}.{chave}: {valor!r} fora da uniao {sorted(permitidos)}")
        primitivos = alternativas - {"null"}
        if primitivos == {"string"} and not isinstance(valor, str):
            problemas.append(f"{onde}.{chave}: o tipo diz string e veio {valor!r}")
        if primitivos == {"number"} and (
            isinstance(valor, bool) or not isinstance(valor, (int, float))
        ):
            problemas.append(f"{onde}.{chave}: o tipo diz number e veio {valor!r}")
        if primitivos == {"boolean"} and not isinstance(valor, bool):
            problemas.append(f"{onde}.{chave}: o tipo diz boolean e veio {valor!r}")


def _problemas_do_bloco(bloco: dict[str, Any], onde: str) -> list[str]:
    fonte = _fonte()
    literais = {alias: _literais(fonte, alias) for alias in _ALIASES}

    def interface(nome: str) -> dict[str, tuple[bool, str]]:
        return _campos(_corpo_da_interface(fonte, nome))

    problemas: list[str] = []
    _conferir(bloco, interface("RecomendacaoTop10"), onde, literais, problemas)
    _conferir(bloco["regra"], interface("ReguaTop10"), f"{onde}.regra", literais, problemas)
    _conferir(bloco["recorte"], interface("RecorteTop10"), f"{onde}.recorte", literais, problemas)
    _conferir(bloco["renda"], interface("RendaTop10"), f"{onde}.renda", literais, problemas)
    for segmento in SEGMENTOS:
        aqui = f"{onde}.{segmento}"
        _conferir(bloco[segmento], interface("SegmentoTop10Payload"), aqui, literais, problemas)
        for vaga in bloco[segmento]["vagas"]:
            _conferir(
                vaga, interface("VagaTop10"), f"{aqui}[{vaga['posicao']}]", literais, problemas
            )
    return problemas


def _vagas(bloco: dict[str, Any]) -> list[dict[str, Any]]:
    return [v for s in SEGMENTOS for v in bloco[s]["vagas"]]


def test_payload_com_vagas_preenchidas_e_vazias_bate_com_os_tipos(top10_data: Path) -> None:  # noqa: F811
    blocos = {
        "municipio": pilot.municipio("SP", "Sao Paulo")["recomendacao"],
        "uf": pilot.uf_view("SP")["recomendacao"],
        "brasil": pilot.hexagonos()["recomendacao"],
    }
    # Anti-vacuidade: o contrato ve vaga preenchida E vazia, e renda setorial E municipal.
    vagas = [v for b in blocos.values() for v in _vagas(b)]
    assert any(v["vazia"] for v in vagas) and any(not v["vazia"] for v in vagas)
    assert any(v["renda_municipal"] for v in vagas if not v["vazia"])
    problemas = [p for nome, b in blocos.items() for p in _problemas_do_bloco(b, nome)]
    assert not problemas, "\n".join(problemas)


def test_payload_indisponivel_sem_k_bate_com_os_tipos(top10_sem_k: Path) -> None:  # noqa: F811
    """Sem o carimbo k: renda com `k`/`carimbo`/`fatores_versao` nulos, os dois segmentos
    `indisponivel` e as vagas com `motivo = renda_indisponivel` -- os nulos que mais pesam."""
    bloco = pilot.municipio("SP", "Sao Paulo")["recomendacao"]
    assert bloco["renda"]["k"] is None and bloco["mata_virgem"]["status"] == "indisponivel"
    problemas = _problemas_do_bloco(bloco, "sem_k")
    assert not problemas, "\n".join(problemas)


def test_hexagonos_e_municipio_declaram_o_bloco(top10_data: Path) -> None:  # noqa: F811
    fonte = _fonte()
    corpo = pilot.hexagonos(uf="SP")
    literais = {alias: _literais(fonte, alias) for alias in _ALIASES}
    problemas: list[str] = []
    _conferir(
        corpo,
        _campos(_corpo_da_interface(fonte, "HexagonosTop10Payload")),
        "hexagonos",
        literais,
        problemas,
    )
    assert not problemas, "\n".join(problemas)
    # No payload do mapa o bloco e' OPCIONAL (ausente = instancia sem regua, o legado).
    assert _campos(_corpo_da_interface(fonte, "MunicipioPayload"))["recomendacao"] == (
        True,
        "RecomendacaoTop10",
    )


def test_o_contrato_acusa_divergencia(top10_data: Path) -> None:  # noqa: F811
    """Anti-vacuidade do proprio verificador: chave renomeada, chave nova, nulo nao
    declarado e literal fora da uniao viram problema nomeado."""
    bloco = copy.deepcopy(pilot.municipio("SP", "Sao Paulo")["recomendacao"])
    vaga = next(v for v in bloco["mata_virgem"]["vagas"] if not v["vazia"])
    vaga["residual_medido_v2"] = vaga.pop("residual_medido")
    bloco["recorte"]["nivel"] = "bairro"
    bloco["regra"]["versao"] = None
    texto = "\n".join(_problemas_do_bloco(bloco, "mutado"))
    assert "nao traz ['residual_medido']" in texto
    assert "nao declara" in texto and "residual_medido_v2" in texto
    assert "'bairro' fora da uniao" in texto
    assert "regra.versao: o servidor manda null" in texto
