"""SIDRA/IBGE: CONFERENCIA de nivel (tabela 7531) e ponte IPCA informativa (tabela 1737).

O QUE ESTE MODULO NAO FAZ — e por que (ajuste do Felipe, 2026-10-20):

* **Nunca calcula crescimento a partir da 7531.** A tabela 7531 (rendimento medio mensal real
  domiciliar per capita, variavel 10824, classe "Total") MISTURA visitas: o ano 2022 reproduz
  a VISITA 5 da PNAD anual e o ano 2025 reproduz a VISITA 1. A visita 1 mede renda ~6% maior
  que a visita 5 no mesmo ano, entao 7531(2025)/7531(2022) carrega um artefato de visita.
* **Nunca devolve um valor que entre no fator.** `conferir_nivel_7531` recebe os niveis ja'
  calculados dos microdados e devolve SO' os erros relativos por UF (diagnostico). Se algum
  passar da tolerancia, aborta. O calculo dos fatores (`motor_expansao.renda.pnad`) nao
  importa nem recebe nada daqui — um teste de contrato varre isso por AST.

A conferencia compara, para CADA ano, o nivel per capita por UF dos microdados NA VISITA QUE
A TABELA USA NAQUELE ANO contra o nivel publicado. A visita de cada ano e' um PARAMETRO
DECLARADO (`VISITA_SIDRA_7531`), gravado no arquivo de versao; ano sem visita declarada
aborta (nao se infere a visita — a atribuicao so' foi conferida para 2022 e 2025).

A ponte IPCA (1737, variavel 2266) e' INFORMATIVA: vai para `ponte_ipca` no arquivo de versao
e nunca e' aplicada a nenhuma renda.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

API = "https://apisidra.ibge.gov.br/values"
TABELA_7531 = 7531
VARIAVEL_7531 = 10824
CLASSE_TOTAL = "49243"
TABELA_IPCA = 1737
VARIAVEL_IPCA = 2266

#: Visita da PNAD anual que a 7531 reproduz em cada ano (medido em 2026-10-20: erro maximo
#: por UF 0,318% em 2022 v5 e 0,370% em 2025 v1; com a visita trocada passa de 18%).
VISITA_SIDRA_7531: dict[int, int] = {2022: 5, 2025: 1}

#: Tolerancia do erro relativo por UF na conferencia de nivel.
TOLERANCIA_NIVEL = 0.005

#: Codigo IBGE da UF -> sigla (copia local: este modulo nao importa o modulo de calculo).
_COD_UF = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}  # fmt: skip

ObterJson = Callable[[str], Any]


class ConferenciaSidraFalhou(SystemExit):
    """A conferencia de nivel contra a SIDRA reprovou (ou nao pode ser feita)."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(f"[sidra] {mensagem}")
        self.mensagem = mensagem


def url_7531(anos: Iterable[int]) -> str:
    p = ",".join(str(a) for a in sorted(set(anos)))
    return (
        f"{API}/t/{TABELA_7531}/n1/all/n3/all/v/{VARIAVEL_7531}/p/{p}"
        f"/c1019/{CLASSE_TOTAL}?formato=json"
    )


def url_ipca(ano_base: int, ano_alvo: int) -> str:
    return (
        f"{API}/t/{TABELA_IPCA}/n1/all/v/{VARIAVEL_IPCA}/p/{ano_base}01-{ano_alvo}12?formato=json"
    )


def obter_json_http(url: str, *, timeout: float = 120.0) -> Any:
    import requests

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def ler_json_local(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _colunas(cabecalho: Mapping[str, str]) -> dict[str, str]:
    """Mapeia o papel de cada dimensao Dn a partir do rotulo do cabecalho da resposta."""
    papeis: dict[str, str] = {}
    for chave, rotulo in cabecalho.items():
        if not (chave.startswith("D") and chave.endswith("C")):
            continue
        r = str(rotulo).lower()
        if r.startswith("ano"):
            papeis["ano"] = chave
        elif r.startswith("variável") or r.startswith("variavel"):
            papeis["variavel"] = chave
        elif r.startswith("classes"):
            papeis["classe"] = chave
        elif "unidade da federa" in r or r.startswith("brasil"):
            papeis.setdefault("territorio", chave)
    return papeis


def niveis_7531(resposta: list[dict]) -> dict[int, dict[str, float]]:
    """Nivel publicado por ano e UF (classe Total, variavel 10824). So' parse — sem razao."""
    if not resposta or not isinstance(resposta, list):
        raise ConferenciaSidraFalhou("resposta da 7531 vazia ou em formato inesperado")
    papeis = _colunas(resposta[0])
    if "ano" not in papeis or "territorio" not in papeis:
        raise ConferenciaSidraFalhou(f"cabecalho da 7531 sem ano/territorio: {resposta[0]}")
    out: dict[int, dict[str, float]] = {}
    for linha in resposta[1:]:
        if str(linha.get("NC")) != "3":
            continue
        if "variavel" in papeis and str(linha.get(papeis["variavel"])) != str(VARIAVEL_7531):
            continue
        if "classe" in papeis and str(linha.get(papeis["classe"])) != CLASSE_TOTAL:
            continue
        uf = _COD_UF.get(str(linha.get(papeis["territorio"])).strip())
        if uf is None:
            continue
        try:
            valor = float(str(linha.get("V")).replace(",", "."))
        except ValueError:
            continue
        out.setdefault(int(str(linha.get(papeis["ano"]))), {})[uf] = valor
    return out


def conferir_nivel_7531(
    niveis_micro: Mapping[tuple[int, int], Mapping[str, float]],
    publicado: Mapping[int, Mapping[str, float]],
    visita_sidra: Mapping[int, int],
    anos: Iterable[int],
    *,
    tolerancia: float = TOLERANCIA_NIVEL,
) -> dict[str, dict[str, Any]]:
    """Confere o NIVEL de cada ano contra a visita declarada. Devolve SO' erros; aborta se falhar.

    `niveis_micro[(ano, visita)][uf]` = nivel per capita dos microdados (R$).
    `publicado[ano][uf]` = nivel da 7531 (R$).
    Retorno: {"<ano>": {"visita", "erro_max", "uf_erro_max", "erro_medio_abs", "erros_uf"}},
    com erros RELATIVOS (micro/publicado - 1). Nenhum valor daqui alimenta fator.
    """
    resultado: dict[str, dict[str, Any]] = {}
    falhas: list[str] = []
    for ano in sorted(set(anos)):
        if ano not in visita_sidra:
            raise ConferenciaSidraFalhou(
                f"ano {ano} sem visita declarada em visita_sidra {dict(visita_sidra)} — "
                "a visita que a 7531 usa em cada ano e' parametro declarado, nao se infere"
            )
        visita = int(visita_sidra[ano])
        micro = niveis_micro.get((ano, visita))
        if micro is None:
            raise ConferenciaSidraFalhou(f"sem niveis dos microdados para {ano} visita {visita}")
        pub = publicado.get(ano)
        if not pub:
            raise ConferenciaSidraFalhou(f"a 7531 nao trouxe o ano {ano}")
        faltam = sorted(set(micro) - set(pub))
        if faltam:
            raise ConferenciaSidraFalhou(f"a 7531 de {ano} nao trouxe as UFs {faltam}")
        erros = {uf: micro[uf] / pub[uf] - 1 for uf in sorted(micro)}
        uf_max = max(erros, key=lambda u: abs(erros[u]))
        resultado[str(ano)] = {
            "visita": visita,
            "erro_max": abs(erros[uf_max]),
            "uf_erro_max": uf_max,
            "erro_medio_abs": sum(abs(e) for e in erros.values()) / len(erros),
            "erros_uf": erros,
        }
        acima = {u: e for u, e in erros.items() if abs(e) > tolerancia}
        if acima:
            pior = ", ".join(
                f"{u} {e:+.3%}" for u, e in sorted(acima.items(), key=lambda x: -abs(x[1]))[:5]
            )
            falhas.append(
                f"{ano} visita {visita}: {len(acima)} UF(s) acima de {tolerancia:.1%} ({pior})"
            )
    if falhas:
        raise ConferenciaSidraFalhou(
            "conferencia de nivel contra a 7531 reprovou — "
            + "; ".join(falhas)
            + ". Confira a visita declarada (visita_sidra) e as amostras baixadas."
        )
    return resultado


def ponte_ipca(resposta: list[dict], ano_base: int, ano_alvo: int) -> dict[str, Any]:
    """Razao das medias anuais do numero-indice IPCA (alvo/base). INFORMATIVA, nunca aplicada."""
    if not resposta or not isinstance(resposta, list):
        raise ConferenciaSidraFalhou("resposta do IPCA (1737) vazia ou em formato inesperado")
    papeis = {k: v for k, v in resposta[0].items() if k.startswith("D") and k.endswith("C")}
    col_mes = next(
        (
            k
            for k, r in papeis.items()
            if str(r).lower().startswith("mês") or str(r).lower().startswith("mes")
        ),
        None,
    )
    if col_mes is None:
        raise ConferenciaSidraFalhou(f"cabecalho do IPCA sem mes: {resposta[0]}")
    serie: dict[int, float] = {}
    for linha in resposta[1:]:
        try:
            serie[int(str(linha[col_mes]))] = float(str(linha["V"]))
        except (KeyError, ValueError):
            continue
    base = [v for m, v in serie.items() if m // 100 == ano_base]
    alvo = [v for m, v in serie.items() if m // 100 == ano_alvo]
    if len(base) != 12 or len(alvo) != 12:
        raise ConferenciaSidraFalhou(
            f"IPCA incompleto: {len(base)} meses de {ano_base} e {len(alvo)} de {ano_alvo} (precisa 12+12)"
        )
    return {
        "valor": (sum(alvo) / 12) / (sum(base) / 12),
        "metodo": f"media anual do numero-indice IPCA {ano_alvo} / media anual {ano_base}",
        "tabela": TABELA_IPCA,
        "variavel": VARIAVEL_IPCA,
        "url": url_ipca(ano_base, ano_alvo),
        "uso": "informativo — nunca aplicado a renda",
    }
