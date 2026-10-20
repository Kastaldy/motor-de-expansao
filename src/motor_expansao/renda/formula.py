"""Ponto unico de aplicacao do fator temporal da renda exibida.

Cada renda com o SEU fator:

    renda_domiciliar = (V06004 x uplift) x F_dom(uf)
    renda_per_capita = ((V06004 x uplift) x F_pc(uf)) / moradores

A per capita NUNCA e derivada da domiciliar. Hoje (versao 0) F_pc == F_dom e as duas
grafias coincidem bit a bit; quando os fatores PNAD entrarem, F_dom = F_pc x queda de
moradores 2022 -> ano alvo, e `domiciliar / moradores` carregaria essa queda para dentro
da per capita (-6,9% no setor exemplo do plano, secao 9.3). O `moradores` daqui e o de
2022: so converte a domiciliar de 2022 em per capita de 2022, nao e ajuste temporal.

A ORDEM das operacoes e parte do contrato: e a mesma dos consumidores de antes da E0
(`censo_point`, `censo_map`, `app.py`), para que nenhum numero exibido mude no float.
"""

from __future__ import annotations

from typing import Any

from motor_expansao.renda.carregador import TIPOS_FATOR, carregar_fatores


def fator(uf: object, tipo: str) -> float:
    """Fator temporal da versao vigente: o da UF se ela tem excecao aprovada, senao o nacional.

    `uf` None, NaN ou desconhecida -> nacional. `tipo` em {"per_capita", "domiciliar"}.
    """
    if tipo not in TIPOS_FATOR:
        raise ValueError(f"tipo de fator invalido: {tipo!r} (esperado um de {TIPOS_FATOR})")
    grupo = carregar_fatores().grupo(uf)
    return grupo.per_capita if tipo == "per_capita" else grupo.domiciliar


def renda_domiciliar(v06004: Any, uplift: Any, uf: object) -> Any:
    """Renda media domiciliar = (V06004 x uplift) x F_dom. Escalar, numpy ou pandas.

    Nao recebe moradores de proposito: a queda de moradores ja esta DENTRO do F_dom, e
    aplica-la de novo aqui seria a segunda armadilha da secao 9.3 do plano.
    """
    return (v06004 * uplift) * fator(uf, "domiciliar")


def renda_per_capita(v06004: Any, uplift: Any, moradores: Any, uf: object) -> Any:
    """Renda domiciliar per capita = ((V06004 x uplift) x F_pc) / moradores (de 2022).

    Calculada com o PROPRIO fator -- nunca `renda_domiciliar(...) / moradores`.
    """
    return ((v06004 * uplift) * fator(uf, "per_capita")) / moradores


def v06004_de_fallback(v06004: Any, per_capita_bruta: Any, moradores: Any) -> Any:
    """V06004 do setor; onde ela falta, reconstruida pela per capita BRUTA x moradores (2022).

    Nunca pela per capita CALIBRADA: ela carrega o k e o reintroduziria pela porta dos fundos.
    Mora aqui porque e a unica outra conta da renda exibida que usa moradores -- fora deste
    pacote, `x * moradores` / `x / moradores` e proibido (fio de alarme da E0, R3).

      - pandas Series: `v06004.where(v06004.notna(), pc x m)` (a forma de `censo_point`);
      - escalar: `v06004` se presente; senao `pc x m`, ou None se `pc`/`m` for None
        (NaN em `pc`/`m` propaga como NaN, como antes).
    """
    import pandas as pd

    if isinstance(v06004, pd.Series):
        return v06004.where(v06004.notna(), per_capita_bruta * moradores)
    if v06004 is not None and not pd.isna(v06004):
        return v06004
    if per_capita_bruta is None or moradores is None:
        return None
    return per_capita_bruta * moradores


def fator_composto_domiciliar(uplift: Any, uf: object) -> Any:
    """uplift x F_dom: o "fator de uplift" exibido no Relatorio Pontual.

    Substitui `round(uplift_efetivo * FATOR_TEMPORAL_RENDA, 4)` de `censo_point`; o
    arredondamento de exibicao fica no chamador.
    """
    return uplift * fator(uf, "domiciliar")


def campos_referencia_ponto(uf: object = None) -> dict[str, Any]:
    """Os dois campos de procedencia que o motor do ponto (`censo_point`) grava no resultado.

    Nomes de chave de antes da E0, preservados porque sao CONTRATO do resultado (travados em
    `test_analisar_geometria_motor`) e porque a tela le `data_referencia_renda`:
      - `fator_temporal_renda` = o fator DOMICILIAR da UF (o nacional quando ela nao tem
        excecao aprovada) -- e o mesmo que entra em `fator_uplift_renda_domiciliar`. Na
        versao 0 F_dom == F_pc, entao o numero e o mesmo de antes; quando divergirem, o
        per capita esta em `fator(uf, "per_capita")` e a versao inteira em `proveniencia()`.
      - `data_referencia_renda` = `rotulo_referencia` da versao vigente (byte a byte o texto
        que `constants.DATA_REFERENCIA_RENDA` montava antes).

    As chaves moram AQUI, e nao no `censo_point`, para que nenhum identificador do fator
    temporal sobreviva fora do pacote (varredura de ponto unico).
    """
    return {
        "fator_temporal_renda": fator(uf, "domiciliar"),
        "data_referencia_renda": carregar_fatores().rotulo_referencia,
    }


def proveniencia() -> dict[str, Any]:
    """`renda_meta`: de onde e de quando vem a renda exibida (payloads, health, PDFs)."""
    f = carregar_fatores()
    return {
        "versao_fator": f.versao,
        "pais": f.pais,
        "ano_base": f.ano_base_renda,
        "data_referencia_base": f.data_referencia_base,
        "ano_alvo": f.ano_alvo,
        "fonte": str(f.fonte["pesquisa"]),
        "rotulo": f.rotulo_referencia,
        "rotulo_pdf": f.rotulo_pdf,
        "fixada_por_env": f.fixada_por_env,
        "excecoes_uf": sorted(f.excecoes_aprovadas),
    }


def renda_meta() -> dict[str, Any]:
    """`renda_meta` dos payloads JSON: a `proveniencia()` SEM `rotulo_pdf`.

    O `rotulo_pdf` e o texto ASCII da nota de fontes dos PDFs; na tela quem vale e o `rotulo`
    (com acento). Mandar os dois ao front seria convidar a tela a exibir o texto sem acento.
    Devolve um dict NOVO a cada chamada: quem o recebe pode mexer sem contaminar o seguinte.
    """
    meta = proveniencia()
    del meta["rotulo_pdf"]
    return meta


def fatores_do_health() -> dict[str, Any]:
    """Bloco `renda_fatores` dos healthchecks: so a versao vigente e se ela foi fixada por env.

    Sem caminho e sem infra de proposito (o `/api/health` do piloto foi enxugado no pentest,
    Onda B #8). A versao do fator e informacao publica de metodologia -- e e por ela que se
    confere, de fora, se o deploy subiu com a versao esperada ou com um rollback por env.
    """
    f = carregar_fatores()
    return {"versao": f.versao, "fixada_por_env": bool(f.fixada_por_env)}
