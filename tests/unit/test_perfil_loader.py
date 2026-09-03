"""Bloco A / commit A1 — o loader do `perfil.json` e fail-closed e nomeia o campo.

O que este arquivo prova, e por que cada coisa importa:

- **Campo obrigatorio ausente derruba o processo, dizendo qual.** Um perfil pela metade
  nao produz erro: produz numero errado com cara de certo (bbox de um pais, regua de
  outro). A mensagem tem de nomear o campo, senao a falha chega ao operador como um
  traceback de JSON.
- **Chave `_`-prefixada e comentario.** E onde moram os campos que a spec §1.4 RECUSOU
  por nao terem leitor. Se o loader os validasse, os dois perfis entregues reprovariam.
- **Campo extra sem `_` passa.** O fail-closed e sobre AUSENCIA e TIPO do que o schema
  exige. E o que deixa `reguas.score_pesos`, `avisos` e `operacao` viverem nos arquivos
  com leitor previsto para os Blocos B/C/C+ sem virarem contrato do Bloco A.

Spec: `docs/spec_bloco_a_perfil.md` §1.2, §3.1 e §3.2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from motor_expansao.perfil import (
    PERFIL_BR_EMBARCADO,
    PerfilInvalidoError,
    carregar_perfil,
    resolver_perfil,
)

# Perfil minimo VALIDO: exatamente os campos obrigatorios do schema (spec §1.2), e nada
# mais. Cada teste parte daqui e estraga UMA coisa — assim a falha nunca e ambigua.
PERFIL_MINIMO: dict = {
    "schema_versao": 1,
    "pais": "AR",
    "nome": "Argentina",
    "locale": "es-AR",
    "moeda": {"codigo": "USD", "simbolo": "US$", "indicadores_renda": "USD"},
    "bbox": {"lat_min": -55.1, "lat_max": -21.8, "lng_min": -73.6, "lng_max": -53.6},
    "vista_padrao": {"lat": -38.4, "lng": -63.6, "zoom": 3.6},
    "geocode": {"countrycodes": "ar", "idioma": "es-AR", "regex_cp": None},
    "fontes": {
        "censo": {"nome": "Censo 2022", "detalhe": "Detalhe do censo."},
        "crescimento": {"nome": "Fontes de crescimento", "detalhe": "Detalhe."},
    },
    "reguas": {
        "renda_abs_min": 350.0,
        "renda_abs_max": 1000.0,
        "pop_abs_min": 1000.0,
        "pop_abs_max": 100000.0,
        "score_corte_quente": 30.0,
        "pop_min_acionavel": 5000,
        "oferta_destaque_min": 2000.0,
        "capacidade_concorrente": 1070.0,
        "capacidade_unidade_alunos": 2500,
        "uplift_composicao": 1.0,
        "moradores_por_domicilio": 2.5654,
        "metas_big_numbers": {
            "pop_total_raio": 10000.0,
            "renda_per_capita_media_raio": 416.42,
            "renda_domiciliar_total_raio": 1068.28,
            "domicilios_total_raio": 3000.0,
            "score_setor_medio": 60.0,
            "sam_fitness_potencial": 2000.0,
            "residual_fitness_disponivel": 2000.0,
        },
    },
    "superficies": ["mapa", "viabilidade"],
    "malha_municipal_disponivel": False,
}

#: Caminho pontilhado de todo campo obrigatorio -> usado para remover um por vez.
CAMPOS_OBRIGATORIOS = [
    "schema_versao",
    "pais",
    "nome",
    "locale",
    "moeda.codigo",
    "moeda.simbolo",
    "bbox.lat_min",
    "bbox.lat_max",
    "bbox.lng_min",
    "bbox.lng_max",
    "vista_padrao.lat",
    "vista_padrao.lng",
    "vista_padrao.zoom",
    "geocode.countrycodes",
    "geocode.idioma",
    "geocode.regex_cp",
    "fontes.censo.nome",
    "fontes.censo.detalhe",
    "fontes.crescimento.nome",
    "fontes.crescimento.detalhe",
    "reguas.renda_abs_min",
    "reguas.renda_abs_max",
    "reguas.pop_abs_min",
    "reguas.pop_abs_max",
    "reguas.score_corte_quente",
    "reguas.pop_min_acionavel",
    "reguas.oferta_destaque_min",
    "reguas.capacidade_concorrente",
    "reguas.capacidade_unidade_alunos",
    "superficies",
]


def _copia_profunda(dados: dict) -> dict:
    return json.loads(json.dumps(dados))


def _gravar(tmp_path: Path, dados: dict, nome: str = "perfil.json") -> Path:
    caminho = tmp_path / nome
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return caminho


def _remover(dados: dict, caminho_pontilhado: str) -> dict:
    partes = caminho_pontilhado.split(".")
    alvo = dados
    for parte in partes[:-1]:
        alvo = alvo[parte]
    del alvo[partes[-1]]
    return dados


# --------------------------------------------------------------------------------
# O caminho feliz
# --------------------------------------------------------------------------------


def test_perfil_minimo_carrega(tmp_path: Path) -> None:
    perfil = carregar_perfil(_gravar(tmp_path, _copia_profunda(PERFIL_MINIMO)))
    assert perfil.pais == "AR"
    assert perfil.bbox.contem(-34.60, -58.38), "Buenos Aires tem de caber na caixa AR"
    assert not perfil.bbox.contem(-15.78, -47.93), "Brasilia NAO cabe na caixa AR"
    assert perfil.superficies == ("mapa", "viabilidade")
    assert perfil.tem_superficie("mapa") and not perfil.tem_superficie("executiva")


def test_ancoras_derivam_das_reguas(tmp_path: Path) -> None:
    """`Perfil.ancoras()` e a ponte para o commit A8 — mesma ordem, mesmos numeros."""
    perfil = carregar_perfil(_gravar(tmp_path, _copia_profunda(PERFIL_MINIMO)))
    a = perfil.ancoras()
    assert (a.renda_min, a.renda_max) == (350.0, 1000.0)
    assert (a.pop_min, a.pop_max) == (1000.0, 100000.0)


def test_raiz_default_e_a_pasta_do_arquivo(tmp_path: Path) -> None:
    """Em producao o `perfil.json` mora NA raiz de dados: `raiz` = a pasta dele."""
    perfil = carregar_perfil(_gravar(tmp_path, _copia_profunda(PERFIL_MINIMO)))
    assert perfil.raiz == tmp_path


def test_raiz_explicita_vence_a_pasta_do_arquivo(tmp_path: Path) -> None:
    """E o que o ramo de dev usa: o BR embarcado mora em `data/perfis/BR/`, mas a raiz
    de dados e `data/`. Sem isto, `DATA_DIR` derivaria `data/perfis/BR/outputs/`."""
    caminho = _gravar(tmp_path, _copia_profunda(PERFIL_MINIMO))
    perfil = carregar_perfil(caminho, raiz=tmp_path / "outra")
    assert perfil.raiz == tmp_path / "outra"


# --------------------------------------------------------------------------------
# Fail-closed: ausencia
# --------------------------------------------------------------------------------


@pytest.mark.parametrize("campo", CAMPOS_OBRIGATORIOS)
def test_campo_obrigatorio_ausente_levanta_nomeando_o_campo(
    tmp_path: Path, campo: str
) -> None:
    dados = _remover(_copia_profunda(PERFIL_MINIMO), campo)
    with pytest.raises(PerfilInvalidoError) as exc:
        carregar_perfil(_gravar(tmp_path, dados))
    # A mensagem tem de citar o campo — ou a folha, ou o objeto que sumiu com ela.
    msg = str(exc.value)
    folha = campo.split(".")[-1]
    assert folha in msg or campo in msg, f"mensagem nao nomeia `{campo}`: {msg}"


def test_arquivo_ausente_levanta_citando_o_caminho(tmp_path: Path) -> None:
    alvo = tmp_path / "nao_existe" / "perfil.json"
    with pytest.raises(PerfilInvalidoError) as exc:
        carregar_perfil(alvo)
    assert "perfil.json" in str(exc.value)
    assert "MOTOR_DATA_DIR" in str(exc.value), "a mensagem tem de dizer COMO consertar"


def test_json_invalido_levanta(tmp_path: Path) -> None:
    caminho = tmp_path / "perfil.json"
    caminho.write_text("{ nao e json ", encoding="utf-8")
    with pytest.raises(PerfilInvalidoError, match="JSON invalido"):
        carregar_perfil(caminho)


def test_raiz_json_nao_objeto_levanta(tmp_path: Path) -> None:
    caminho = tmp_path / "perfil.json"
    caminho.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(PerfilInvalidoError, match="objeto JSON"):
        carregar_perfil(caminho)


# --------------------------------------------------------------------------------
# Fail-closed: versao, tipo e invariante
# --------------------------------------------------------------------------------


@pytest.mark.parametrize("versao", [0, 2, "1", None])
def test_schema_versao_divergente_levanta(tmp_path: Path, versao: object) -> None:
    """Um pacote antigo do pipeline encontrando um loader novo tem de falhar ALTO."""
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["schema_versao"] = versao
    with pytest.raises(PerfilInvalidoError, match="schema_versao"):
        carregar_perfil(_gravar(tmp_path, dados))


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("pais", "ARG"),
        ("pais", "ar"),
        ("locale", "PT_BR"),
        ("nome", ""),
        ("nome", "   "),
    ],
)
def test_identidade_fora_do_formato_levanta(
    tmp_path: Path, campo: str, valor: str
) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados[campo] = valor
    with pytest.raises(PerfilInvalidoError, match=campo):
        carregar_perfil(_gravar(tmp_path, dados))


def test_moeda_fora_do_iso4217_levanta(tmp_path: Path) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["moeda"]["codigo"] = "dolar"
    with pytest.raises(PerfilInvalidoError, match="moeda.codigo"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_indicadores_renda_ausente_levanta_nomeando_o_campo(tmp_path: Path) -> None:
    """A Argentina reporta renda em USD com moeda oficial ARS — sem este campo, o
    formatador de renda cairia de volta ao simbolo da moeda oficial (o defeito de
    2026-09-03: "$" do peso sobre um numero que sao dolares)."""
    dados = _copia_profunda(PERFIL_MINIMO)
    del dados["moeda"]["indicadores_renda"]
    with pytest.raises(PerfilInvalidoError, match="moeda.indicadores_renda"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_indicadores_renda_fora_do_iso4217_levanta(tmp_path: Path) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["moeda"]["indicadores_renda"] = "dolar"
    with pytest.raises(PerfilInvalidoError, match="moeda.indicadores_renda"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_simbolo_renda_e_o_simbolo_do_pais_quando_as_moedas_coincidem(
    tmp_path: Path,
) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["moeda"] = {"codigo": "BRL", "simbolo": "R$", "indicadores_renda": "BRL"}
    perfil = carregar_perfil(_gravar(tmp_path, dados))
    assert perfil.moeda.simbolo_renda() == "R$"


def test_simbolo_renda_e_o_CODIGO_do_indicador_quando_diverge_da_moeda_oficial(
    tmp_path: Path,
) -> None:
    """A caixa real da Argentina: moeda oficial ARS ("$"), renda do pacote em USD.

    Sem simbolo dedicado para USD no perfil, o codigo e' o que desambigua — nunca o
    simbolo "$" da moeda oficial, que um leitor argentino leria como peso.
    """
    # PERFIL_MINIMO ja usa moeda USD/US$/USD: nao diverge, simbolo_renda() == simbolo.
    perfil = carregar_perfil(_gravar(tmp_path, PERFIL_MINIMO, "perfil_a.json"))
    assert perfil.moeda.simbolo_renda() == "US$"

    dados = _copia_profunda(PERFIL_MINIMO)
    dados["moeda"] = {"codigo": "ARS", "simbolo": "$", "indicadores_renda": "USD"}
    perfil = carregar_perfil(_gravar(tmp_path, dados, "perfil_b.json"))
    assert perfil.moeda.simbolo_renda() == "USD"
    assert perfil.moeda.simbolo_renda() != perfil.moeda.simbolo


@pytest.mark.parametrize(
    "bbox",
    [
        {"lat_min": 10.0, "lat_max": -10.0, "lng_min": -70.0, "lng_max": -50.0},
        {"lat_min": -10.0, "lat_max": 10.0, "lng_min": -50.0, "lng_max": -70.0},
        {"lat_min": -10.0, "lat_max": -10.0, "lng_min": -70.0, "lng_max": -50.0},
        {"lat_min": -100.0, "lat_max": 10.0, "lng_min": -70.0, "lng_max": -50.0},
        {"lat_min": -10.0, "lat_max": 10.0, "lng_min": -270.0, "lng_max": -50.0},
    ],
)
def test_bbox_degenerada_ou_fora_do_globo_levanta(tmp_path: Path, bbox: dict) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["bbox"] = bbox
    with pytest.raises(PerfilInvalidoError, match="bbox"):
        carregar_perfil(_gravar(tmp_path, dados))


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("renda_abs_min", 1000.0),  # >= renda_abs_max
        ("pop_abs_min", 100000.0),  # >= pop_abs_max
        ("pop_abs_min", 0.0),  # a nota de populacao entra em log
        ("pop_abs_min", -5.0),
        # Multiplicadores de renda EXIBIDA: zero ou negativo nao produz erro, produz
        # renda zerada ou negativa na tela, que se le como "regiao pobre".
        ("uplift_composicao", 0.0),
        ("uplift_composicao", -1.0),
        ("moradores_por_domicilio", 0.0),
    ],
)
def test_regua_degenerada_levanta(tmp_path: Path, campo: str, valor: float) -> None:
    """Sem esta guarda, o defeito aparece como divisao por zero ou `-inf` dentro de
    `nota_renda_absoluta`, num traceback que nao menciona perfil nenhum."""
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["reguas"][campo] = valor
    with pytest.raises(PerfilInvalidoError, match="reguas"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_booleano_em_campo_numerico_levanta(tmp_path: Path) -> None:
    """`bool` e subclasse de `int` em Python: sem a checagem explicita, `true` passaria
    como 1 e o corte do funil viraria 1,0 em silencio."""
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["reguas"]["score_corte_quente"] = True
    with pytest.raises(PerfilInvalidoError, match="score_corte_quente"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_float_onde_o_schema_pede_inteiro_levanta(tmp_path: Path) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["reguas"]["pop_min_acionavel"] = 5000.5
    with pytest.raises(PerfilInvalidoError, match="pop_min_acionavel"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_objeto_onde_o_schema_pede_objeto(tmp_path: Path) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["moeda"] = "BRL"
    with pytest.raises(PerfilInvalidoError, match="moeda"):
        carregar_perfil(_gravar(tmp_path, dados))


# --------------------------------------------------------------------------------
# `superficies` — o vocabulario de aba, validado no BOOT e nao na primeira requisicao
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "superficies",
    [
        ["mapa", "financeiro"],  # aba que nao existe
        ["Mapa"],  # vocabulario e case-sensitive (identificador, CLAUDE.md §2)
        [],  # instancia sem superficie nenhuma nao e instancia
        "mapa",  # string nao e lista
        ["mapa", 3],
    ],
)
def test_superficie_invalida_levanta_no_boot(
    tmp_path: Path, superficies: object
) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["superficies"] = superficies
    with pytest.raises(PerfilInvalidoError, match="superficies"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_malha_municipal_disponivel_ausente_levanta_no_boot(tmp_path: Path) -> None:
    """Campo do Bloco C — sem ele, o gate de `/api/ponto` etc. nao teria como decidir."""
    dados = _copia_profunda(PERFIL_MINIMO)
    del dados["malha_municipal_disponivel"]
    with pytest.raises(PerfilInvalidoError, match="malha_municipal_disponivel"):
        carregar_perfil(_gravar(tmp_path, dados))


@pytest.mark.parametrize("valor", ["true", 1, None, ["true"]])
def test_malha_municipal_disponivel_fora_do_tipo_levanta(
    tmp_path: Path, valor: object
) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["malha_municipal_disponivel"] = valor
    with pytest.raises(PerfilInvalidoError, match="malha_municipal_disponivel"):
        carregar_perfil(_gravar(tmp_path, dados))


# --------------------------------------------------------------------------------
# As duas regras de admissao (spec §1.2)
# --------------------------------------------------------------------------------


def test_chave_prefixada_por_underscore_e_ignorada(tmp_path: Path) -> None:
    """E onde moram os campos que a spec §1.4 recusou. Se o loader os validasse, os
    dois `perfil.json` entregues reprovariam — `_rotulos`, `_particao`, `_pendencias`."""
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["_rotulos"] = {"nivel1": "Provincia"}
    dados["_particao"] = "qualquer lixo aqui, ate uma string"
    dados["reguas"]["_nota_renda"] = "procedencia, nao configuracao"
    dados["geocode"]["_sufixo"] = None
    perfil = carregar_perfil(_gravar(tmp_path, dados))
    assert perfil.pais == "AR"


def test_campo_extra_sem_underscore_e_tolerado(tmp_path: Path) -> None:
    """Campo fora da tabela do schema PASSA. E o que deixa `score_pesos`, `avisos` e
    `operacao` viverem nos arquivos com leitor previsto para os Blocos B/C/C+."""
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["reguas"]["score_pesos"] = {"renda": 0.6, "pop": 0.4}
    dados["avisos"] = {"tributo": "provisorio"}
    dados["operacao"] = {"pdf_concorrencia_max": 3}
    perfil = carregar_perfil(_gravar(tmp_path, dados))
    assert perfil.reguas.score_corte_quente == 30.0


# --------------------------------------------------------------------------------
# `geocode.regex_cp` — o unico campo do schema que aceita null
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "idioma", ["es-AR,es", "pt-BR", "pt-BR,pt;q=0.9", "es-AR, es;q=0.8, en;q=0.5"]
)
def test_idioma_aceita_lista_de_accept_language(tmp_path: Path, idioma: str) -> None:
    """**Regressao de um defeito real, achado em 2026-09-02 pelo teste do A4.**

    `geocode.idioma` NAO e um locale: e o valor de um header `Accept-Language`, que por
    RFC 9110 aceita lista com fallback e q-value. Enquanto foi validado pela regex de
    `locale` (tag unica), o `data/perfis/AR/perfil.json` — que declara `es-AR,es` —
    REPROVAVA no loader. A instancia argentina nao subiria, e isso so apareceria no
    primeiro boot dela.
    """
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["geocode"]["idioma"] = idioma
    assert carregar_perfil(_gravar(tmp_path, dados)).geocode.idioma == idioma


@pytest.mark.parametrize("idioma", ["ES-ar", "es_AR", "", "es-AR;;q=2"])
def test_idioma_malformado_ainda_levanta(tmp_path: Path, idioma: str) -> None:
    """Afrouxar para aceitar lista nao pode virar aceitar qualquer coisa."""
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["geocode"]["idioma"] = idioma
    with pytest.raises(PerfilInvalidoError, match="idioma"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_locale_continua_exigindo_tag_unica(tmp_path: Path) -> None:
    """`locale` alimenta `new Intl.NumberFormat(locale, ...)`, que quer UMA tag. O
    afrouxamento do `geocode.idioma` nao pode ter vazado para ca."""
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["locale"] = "es-AR,es"
    with pytest.raises(PerfilInvalidoError, match="locale"):
        carregar_perfil(_gravar(tmp_path, dados))


def test_os_dois_perfis_versionados_carregam(tmp_path: Path) -> None:
    """O loader tem de aceitar os perfis que o repositorio de fato entrega — os dois.

    Sem este teste, um aperto de validacao passa verde no BR e so quebra no dia da
    subida da Argentina, que foi exatamente o que aconteceu com `geocode.idioma`.
    """
    raiz = PERFIL_BR_EMBARCADO.parents[1]
    for pais in ("BR", "AR"):
        perfil = carregar_perfil(raiz / pais / "perfil.json")
        assert perfil.pais == pais


def test_regex_cp_null_e_declaracao_nao_ausencia(tmp_path: Path) -> None:
    perfil = carregar_perfil(_gravar(tmp_path, _copia_profunda(PERFIL_MINIMO)))
    assert perfil.geocode.regex_cp is None


def test_regex_cp_que_nao_compila_levanta(tmp_path: Path) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["geocode"]["regex_cp"] = r"(\d{5}"
    with pytest.raises(PerfilInvalidoError, match="regex_cp"):
        carregar_perfil(_gravar(tmp_path, dados))


@pytest.mark.parametrize("valor", ["AR", "br,ar", "ar,br"])
def test_countrycodes_aceita_um_ou_mais_paises(tmp_path: Path, valor: str) -> None:
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["geocode"]["countrycodes"] = valor
    if valor.islower():
        assert carregar_perfil(_gravar(tmp_path, dados)).geocode.countrycodes == valor
    else:
        # Nominatim exige minusculo; maiusculo passaria calado e filtraria nada.
        with pytest.raises(PerfilInvalidoError, match="countrycodes"):
            carregar_perfil(_gravar(tmp_path, dados))


# --------------------------------------------------------------------------------
# `resolver_perfil` — os dois ramos (spec §3.2)
# --------------------------------------------------------------------------------


def test_sem_motor_data_dir_carrega_o_br_embarcado(monkeypatch: pytest.MonkeyPatch) -> None:
    """O ramo de DEV/TESTE. Sem ele, os 15 modulos que fazem `import app` no topo
    morreriam na COLETA do pytest, com traceback que nao menciona o Bloco A."""
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    resolver_perfil.cache_clear()
    try:
        perfil = resolver_perfil()
        assert perfil.pais == "BR"
        # A raiz de dados de dev e `data/`, NAO `data/perfis/BR/`.
        assert perfil.raiz == PERFIL_BR_EMBARCADO.parents[2]
        assert perfil.raiz.name == "data"
    finally:
        resolver_perfil.cache_clear()


def test_com_motor_data_dir_e_sem_perfil_levanta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ramo de PRODUCAO. E este teste que descreve o que a VPS faz sem o mount da
    spec §6.1: o container NAO sobe, e o log diz qual arquivo falta."""
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    resolver_perfil.cache_clear()
    try:
        with pytest.raises(PerfilInvalidoError) as exc:
            resolver_perfil()
        assert "perfil.json" in str(exc.value)
    finally:
        resolver_perfil.cache_clear()


def test_com_motor_data_dir_a_raiz_e_o_volume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gravar(tmp_path, _copia_profunda(PERFIL_MINIMO))
    monkeypatch.setenv("MOTOR_DATA_DIR", str(tmp_path))
    resolver_perfil.cache_clear()
    try:
        perfil = resolver_perfil()
        assert perfil.pais == "AR"
        assert perfil.raiz == tmp_path
    finally:
        resolver_perfil.cache_clear()


def test_resolver_perfil_e_resolvido_uma_vez_por_processo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEC-047: o pais e resolvido UMA vez, no import. Nao ha troca de pais em runtime,
    e e por isso que os 40 `lru_cache` do `app.py` continuam corretos sem chave de pais."""
    monkeypatch.delenv("MOTOR_DATA_DIR", raising=False)
    resolver_perfil.cache_clear()
    try:
        assert resolver_perfil() is resolver_perfil()
    finally:
        resolver_perfil.cache_clear()


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("renda_per_capita_media_raio", 0.0),
        ("renda_domiciliar_total_raio", -100.0),
        ("pop_total_raio", 0.0),
        # 0-100 por construcao: meta acima de 100 nunca fica verde.
        ("score_setor_medio", 101.0),
    ],
)
def test_meta_que_nunca_acusa_levanta(tmp_path: Path, campo: str, valor: float) -> None:
    """Meta <= 0 pinta o card de verde SEMPRE, e meta de score acima de 100 pinta de
    vermelho sempre. Um semaforo que nunca acusa e pior que semaforo nenhum, porque
    parece estar funcionando."""
    dados = _copia_profunda(PERFIL_MINIMO)
    dados["reguas"]["metas_big_numbers"][campo] = valor
    with pytest.raises(PerfilInvalidoError, match=campo):
        carregar_perfil(_gravar(tmp_path, dados))
