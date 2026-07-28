"""BLK-RELPON-14 (DEC-013): as 68 redes do coletor semanal nos 3 registros de concorrentes.

As redes ja tinham CSV em `concorrentes/Unidades/unidades_<slug>.csv`, mas caiam em
`independente` porque `load_competitor_points` so itera `COMPETITOR_SPECS`. Este modulo trava o
contrato dos TRES registros que precisam andar juntos para a rede aparecer com marca propria:

- `COMPETITOR_SPECS`   -> chave `unidades_<slug>.csv` (o loader varre por nome de arquivo);
- `COMPETITOR_BRANDS`  -> `label`/`short`/`bg`/`fg` (o `short` e o FALLBACK do pin sem logo PNG);
- `COMPETITOR_LOGO_FILES` -> SEMPRE `logo_<slug>.png` (a normalizacao de nome do GymScraping
  acontece na copia dos PNGs para a VPS, nao neste registro).

Sem PII: so nomes de REDE/unidade, nunca de pessoa.
"""

from __future__ import annotations

from collections import Counter

from motor_expansao.dashboard.competitors import (
    COMPETITOR_BRANDS,
    COMPETITOR_LOGO_FILES,
    COMPETITOR_SPECS,
)

# As 68 redes novas, na ordem em que entraram nos registros. Lista EXPLICITA de proposito:
# derivar o conjunto do proprio modulo tornaria o teste vacuo (ele passaria se as 68 sumissem).
REDES_COLETOR_SEMANAL = (
    "a_melhor_academia",
    "academia_do_parque",
    "acuas_fitness",
    "ad3",
    "ajuste",
    "america",
    "bg_fitness",
    "biofisic",
    "body_shop",
    "bulkfit",
    "burnfit",
    "caixa_magica",
    "california",
    "ciafit",
    "companhia_fit",
    "competition",
    "corpo_e_saude",
    "cristal",
    "ctrc",
    "dffit",
    "domofit",
    "flexfitness",
    "force_one",
    "gofit",
    "grecoforma",
    "gymflix",
    "hammer",
    "hi",
    "inova",
    "ironberg",
    "korpus",
    "malibu_fitness",
    "mansao_maromba",
    "marra_fit",
    "match_fit",
    "moinhos_fitness",
    "monstrao",
    "nadarte",
    "nation_ct",
    "novafit",
    "one",
    "paulo_bedeu",
    "performance",
    "power_fit",
    "premium",
    "profit",
    "rede_lifefit",
    "reebok_sports_club",
    "romero_training",
    "rtesser",
    "runner",
    "simplifit",
    "sportdata",
    "summit_fitness",
    "target_gym",
    "tem_esportes",
    "the_simple_gym",
    "tntfit",
    "topfit",
    "ufit",
    "universal",
    "uplay",
    "usina_do_corpo",
    "vasco_neto",
    "voi_fit",
    "wave",
    "wellness_club",
    "ymca",
)


def test_sao_68_redes_sem_slug_repetido():
    assert len(REDES_COLETOR_SEMANAL) == 68
    assert len(set(REDES_COLETOR_SEMANAL)) == 68


def test_as_68_redes_estao_nos_tres_registros():
    """Sem as 3 entradas a rede nao chega ao mapa: ou nao e' carregada (SPECS), ou vira pin
    generico sem marca (BRANDS), ou perde a logo (LOGO_FILES)."""
    specs_por_rede = {spec["rede"]: arquivo for arquivo, spec in COMPETITOR_SPECS.items()}

    faltando_spec = [r for r in REDES_COLETOR_SEMANAL if r not in specs_por_rede]
    faltando_brand = [r for r in REDES_COLETOR_SEMANAL if r not in COMPETITOR_BRANDS]
    faltando_logo = [r for r in REDES_COLETOR_SEMANAL if r not in COMPETITOR_LOGO_FILES]

    assert faltando_spec == [], f"redes fora de COMPETITOR_SPECS: {faltando_spec}"
    assert faltando_brand == [], f"redes fora de COMPETITOR_BRANDS: {faltando_brand}"
    assert faltando_logo == [], f"redes fora de COMPETITOR_LOGO_FILES: {faltando_logo}"


def test_chave_do_spec_e_o_csv_canonico_do_coletor():
    """O loader varre por NOME DE ARQUIVO: a chave tem de ser `unidades_<slug>.csv`."""
    specs_por_rede = {spec["rede"]: arquivo for arquivo, spec in COMPETITOR_SPECS.items()}
    errados = {
        rede: specs_por_rede[rede]
        for rede in REDES_COLETOR_SEMANAL
        if specs_por_rede.get(rede) != f"unidades_{rede}.csv"
    }
    assert errados == {}, f"chave de CSV fora do padrao unidades_<slug>.csv: {errados}"


def test_nome_do_arquivo_de_logo_e_logo_slug_png():
    """`logo_<slug>.png` e o nome CANONICO no registro; a normalizacao dos PNGs do GymScraping
    (arquivos invertidos ou sob outro slug) acontece na copia para a VPS, nao aqui."""
    errados = {
        rede: COMPETITOR_LOGO_FILES[rede]
        for rede in REDES_COLETOR_SEMANAL
        if COMPETITOR_LOGO_FILES[rede] != f"logo_{rede}.png"
    }
    assert errados == {}, f"nome de logo fora do padrao logo_<slug>.png: {errados}"


def test_sigla_do_pin_e_unica_e_cabe_em_3_chars():
    """O pin sem logo cai no fallback de sigla (`short`, truncado em 3 chars). Colisao de sigla
    faria duas redes distintas virarem o MESMO marcador -- por isso a unicidade e GLOBAL, nao
    so entre as 68 novas."""
    siglas = [brand["short"] for brand in COMPETITOR_BRANDS.values()]
    repetidas = sorted(sigla for sigla, n in Counter(siglas).items() if n > 1)
    assert repetidas == [], f"siglas repetidas em COMPETITOR_BRANDS: {repetidas}"

    curtas_demais = [s for s in siglas if not 1 <= len(s) <= 3]
    assert curtas_demais == [], f"siglas fora de 1-3 chars (o pin trunca em [:3]): {curtas_demais}"

    # As 68 novas tambem precisam de label nao vazio e cores de marca definidas.
    for rede in REDES_COLETOR_SEMANAL:
        brand = COMPETITOR_BRANDS[rede]
        assert brand["label"].strip(), f"label vazio em {rede}"
        for chave in ("bg", "fg"):
            assert brand[chave].startswith("#") and len(brand[chave]) == 7, (
                f"cor {chave} invalida em {rede}: {brand[chave]!r}"
            )


def test_os_tres_registros_cobrem_exatamente_as_mesmas_redes():
    """Trava o desalinhamento silencioso: qualquer rede tem de existir nos 3 registros."""
    redes_spec = {spec["rede"] for spec in COMPETITOR_SPECS.values()}
    assert redes_spec == set(COMPETITOR_BRANDS)
    assert redes_spec == set(COMPETITOR_LOGO_FILES)
    # 39 redes historicas + as 68 do coletor semanal.
    assert len(redes_spec) == 39 + len(REDES_COLETOR_SEMANAL)
