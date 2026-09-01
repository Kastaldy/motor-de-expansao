"""Testes da limpeza de endereco (geo.py) — parte PURA, sem rede."""

from __future__ import annotations

from motor_expansao.api import geo


def test_link_maps_basico() -> None:
    link = geo.endereco_para_link_maps("Aguas da Prata, SP")
    assert link.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "Brasil" in geo.endereco_limpo("Aguas da Prata, SP")


def test_remove_cep() -> None:
    limpo = geo.endereco_limpo("Rua A, 10, Altinopolis - SP, CEP 14350-000")
    assert "cep" not in limpo.lower()
    assert "14350" not in limpo


def test_ancora_pais() -> None:
    assert geo.endereco_limpo("Rua A, 10, Altinopolis").endswith("Brasil")


def test_vazio() -> None:
    assert geo.endereco_para_link_maps("") == ""
    assert geo.endereco_limpo("   ") == ""


def test_percent_encoding_acentos() -> None:
    # 'ã' (U+00E3) em UTF-8 = 0xC3 0xA3 -> %C3%A3
    link = geo.endereco_para_link_maps("Endereco ã")
    assert "%C3%A3" in link.upper()
    # virgula (reservado) vira %2C
    assert "%2C" in geo.endereco_para_link_maps("Rua A, 10").upper()


# --- Link de place SEM coordenada na forma `?q=<endereco>` (BLK-FIX-MAPSQ) ------------
# Reportado por Juan (2026-08-19): https://maps.app.goo.gl/YtGkXfGvy3QgnmRJA?g_st=iwb
# expande para `google.com/maps?q=Av.+Santos+Dumont,+2915+...&ftid=0x...` -- sem `@lat,lng`
# e sem `!3d!4d`. O parser puro falha (correto) e, antes deste fix, o extrator de endereco
# so olhava `/maps/place/`, entao o link inteiro morria em "Nao consegui localizar".

_URL_Q_REAL = (
    "https://www.google.com/maps?q=Av.+Santos+Dumont,+2915+-+Aldeota,+Fortaleza+-+CE,"
    "+60150-165&ftid=0x7c7488830f41f11:0xf2e6d99ad01cba8e&entry=gps&shh=CAE&lucs=,942"
)


def test_extrai_endereco_do_parametro_q():
    from motor_expansao.api.geo import extrair_endereco_de_place_url

    assert extrair_endereco_de_place_url(_URL_Q_REAL) == (
        "Av. Santos Dumont, 2915 - Aldeota, Fortaleza - CE, 60150-165"
    )


def test_q_com_coordenada_pura_nao_vira_endereco():
    """`?q=-3.73,-38.48` e' coordenada e ja e' tratada pelo parser puro; nao pode virar texto
    de endereco, senao gastaria geocoding (e perderia precisao) por um dado que ja temos."""
    from motor_expansao.api.geo import extrair_endereco_de_place_url

    assert extrair_endereco_de_place_url("https://maps.google.com/?q=-3.7327,-38.4869") == ""
    assert extrair_endereco_de_place_url("https://maps.google.com/?q=-3.7327, -38.4869") == ""


def test_place_no_path_continua_tendo_prioridade():
    """O path `/maps/place/` segue sendo a 1a fonte; o `?q=` e' so o fallback."""
    from motor_expansao.api.geo import extrair_endereco_de_place_url

    url = "https://www.google.com/maps/place/Praca+da+Se,+Sao+Paulo+-+SP/@-23.55,-46.63,17z?q=outro"
    assert extrair_endereco_de_place_url(url).startswith("Praca da Se")


def test_url_sem_endereco_textual_devolve_vazio():
    from motor_expansao.api.geo import extrair_endereco_de_place_url

    assert extrair_endereco_de_place_url("https://www.google.com/maps/@-23.55,-46.63,17z") == ""
    assert extrair_endereco_de_place_url("") == ""
    assert extrair_endereco_de_place_url(None) == ""


def test_query_e_destination_tambem_sao_aceitos():
    """Links de navegacao usam `query=`/`destination=` no lugar de `q=`."""
    from motor_expansao.api.geo import extrair_endereco_de_place_url

    for param in ("query", "destination"):
        url = f"https://www.google.com/maps?{param}=Rua+XV+de+Novembro,+100+-+Curitiba+-+PR"
        assert extrair_endereco_de_place_url(url) == "Rua XV de Novembro, 100 - Curitiba - PR"


# --- Ultimo recurso: parametro DESCONHECIDO (BLK-FIX-MAPSQ) ---------------------------
# Sem iPhone para gerar um link real (Juan, 2026-08-19), a lista de nomes de parametro e'
# palpite. Estes testes cobrem o caminho que NAO depende do palpite.


def test_endereco_em_parametro_desconhecido():
    from motor_expansao.api.geo import extrair_endereco_de_place_url

    url = "https://maps.novo.app/?local_completo=Av.+Santos+Dumont,+2915+-+Fortaleza+-+CE"
    assert extrair_endereco_de_place_url(url) == "Av. Santos Dumont, 2915 - Fortaleza - CE"


def test_identificadores_nao_viram_endereco():
    """Geocodificar lixo daria um relatorio no LUGAR ERRADO -- pior que falhar com mensagem."""
    from motor_expansao.api.geo import extrair_endereco_de_place_url

    for url in (
        "https://www.google.com/maps?ftid=0x7c7488830f41f11:0xf2e6d99ad01cba8e",
        "https://www.google.com/maps?entry=gps&shh=CAE&lucs=,942",
        "https://maps.apple.com/?ll=-3.7327,-38.4869",
        "https://maps.apple.com/place?place-id=I1234567890",
    ):
        assert extrair_endereco_de_place_url(url) == "", url


def test_entre_varios_candidatos_vence_o_mais_longo():
    """Num link de place o endereco completo e' o campo mais extenso; os curtos sao rotulo."""
    from motor_expansao.api.geo import extrair_endereco_de_place_url

    url = "https://x.com/?nome=AYO+Gym&addr=Av.+Chanceler+Edson+Queiroz,+100+-+Fortaleza"
    assert extrair_endereco_de_place_url(url).startswith("Av. Chanceler")
