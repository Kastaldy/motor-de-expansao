"""BLK-MA-02: testes do contrato canônico da camada de vulnerabilidade (primitivas congeladas).

Tudo aqui é PURO (sem I/O, sem `tmp_path`) e 100% sintético — o `contrato.py` não toca disco.

O teste mais importante deste arquivo é o cruzamento das 27 capitais contra `BBOX_UF`: os
retângulos foram digitados à mão (por um LLM) e um typo silencioso descartaria academias legítimas
como "coord fora do bbox da UF". As coordenadas das capitais são digitadas de forma INDEPENDENTE
aqui — duas digitações independentes precisam concordar.
"""

from __future__ import annotations

import hashlib

import h3
import pytest

from motor_expansao.vulnerabilidade import contrato as c

# Capitais das 27 UFs, digitadas de forma INDEPENDENTE do `BBOX_UF` (cross-check do D4).
CAPITAIS: dict[str, tuple[float, float]] = {
    "AC": (-9.9747, -67.8100),   # Rio Branco
    "AL": (-9.6658, -35.7353),   # Maceio
    "AM": (-3.1190, -60.0217),   # Manaus
    "AP": (0.0389, -51.0664),    # Macapa
    "BA": (-12.9777, -38.5016),  # Salvador
    "CE": (-3.7319, -38.5267),   # Fortaleza
    "DF": (-15.7939, -47.8828),  # Brasilia
    "ES": (-20.3155, -40.3128),  # Vitoria
    "GO": (-16.6869, -49.2648),  # Goiania
    "MA": (-2.5297, -44.3028),   # Sao Luis
    "MG": (-19.9167, -43.9345),  # Belo Horizonte
    "MS": (-20.4697, -54.6201),  # Campo Grande
    "MT": (-15.6014, -56.0979),  # Cuiaba
    "PA": (-1.4558, -48.5044),   # Belem
    "PB": (-7.1195, -34.8450),   # Joao Pessoa
    "PE": (-8.0476, -34.8770),   # Recife
    "PI": (-5.0892, -42.8019),   # Teresina
    "PR": (-25.4284, -49.2733),  # Curitiba
    "RJ": (-22.9068, -43.1729),  # Rio de Janeiro
    "RN": (-5.7945, -35.2110),   # Natal
    "RO": (-8.7619, -63.9039),   # Porto Velho
    "RR": (2.8235, -60.6758),    # Boa Vista
    "RS": (-30.0346, -51.2177),  # Porto Alegre
    "SC": (-27.5954, -48.5480),  # Florianopolis
    "SE": (-10.9472, -37.0731),  # Aracaju
    "SP": (-23.5505, -46.6333),  # Sao Paulo
    "TO": (-10.1689, -48.3317),  # Palmas
}


# --------------------------------------------------------------------------- #
# CA-4 — semana ISO
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("iso", "esperado"),
    [
        ("2026-12-28", "2026-53"),
        ("2027-01-01", "2026-53"),  # trap: `date.year` seria 2027
        ("2025-12-29", "2026-01"),  # trap espelhada: `date.year` seria 2025
        ("2026-01-26", "2026-05"),  # zero-padding (nunca "2026-5")
        ("2027-01-04", "2027-01"),
    ],
)
def test_derivar_semana_iso_usa_iso_year(iso: str, esperado: str) -> None:
    from datetime import date

    assert c.derivar_semana_iso(date.fromisoformat(iso)) == esperado
    assert c.RE_SEMANA.match(esperado)


# --------------------------------------------------------------------------- #
# CA-6 — campos do hash
# --------------------------------------------------------------------------- #
def test_campos_hash_por_fonte_nao_inclui_data_coleta_nem_slug() -> None:
    """`data_coleta` no hash zeraria a staleness; `slug` no hash faria UUID rotativo virar mudanca."""
    assert set(c.CAMPOS_HASH_POR_FONTE) == set(c.FONTES_VALIDAS)
    for fonte, campos in c.CAMPOS_HASH_POR_FONTE.items():
        assert not (set(campos) & c.CAMPOS_NUNCA_HASHEADOS), fonte
        assert len(set(campos)) == len(campos), f"campo repetido em {fonte}"


def test_normalizar_lista_ordena_e_normaliza_tokens() -> None:
    assert c.normalizar_lista("Musculacao, Natação; Yoga") == "musculacao,natacao,yoga"
    assert c.normalizar_lista("Yoga;Natação|Musculacao") == "musculacao,natacao,yoga"
    assert c.normalizar_lista("") == ""
    assert c.normalizar_lista(None) == ""
    assert c.normalizar_lista("A,,B") == "a,b"


def test_normalizar_numero_e_sentinela_fixa() -> None:
    assert c.normalizar_numero(-23.55) == "-23.55000"
    assert c.normalizar_numero("-46.63") == "-46.63000"
    assert c.normalizar_numero("") == ""
    assert c.normalizar_numero(None) == ""
    assert c.normalizar_numero(float("nan")) == ""


# --------------------------------------------------------------------------- #
# CA-14 — identificadores 100% ASCII (CLAUDE.md §2)
# --------------------------------------------------------------------------- #
def test_identificadores_do_contrato_sao_ascii() -> None:
    alvos: list[str] = [
        *c.CONTRATO_COLUNAS_SNAPSHOT.keys(),
        *c.CONTRATO_COLUNAS_CHURN.keys(),
        *c.MOTIVOS_DESCARTE,
        *c.STATUS_CHURN_VALIDOS,
        *sorted(c.FONTES_VALIDAS),
        *sorted(c.CHAVE_ORIGEM_VALIDAS),
        *sorted(c.COLUNAS_PII_PROIBIDAS),
        *c.BBOX_UF.keys(),
        c.VERSAO_CONTRATO_SNAPSHOT,
        c.VERSAO_CONTRATO_CHURN,
        c.COLUNA_PARTICAO,
    ]
    for valor in alvos:
        assert valor.isascii(), f"identificador com caractere fora de ASCII: {valor!r}"
        assert valor == valor.strip()


def test_motivos_de_descarte_sao_os_seis_do_contrato() -> None:
    assert set(c.MOTIVOS_DESCARTE) == {
        "coord_zero_zero",
        "coord_fora_envelope_brasil",
        "coord_fora_bbox_uf",
        "rotulo_de_teste",
        "entrada_tecnologia_totalpass",
        "data_coleta_invalida",
    }


# --------------------------------------------------------------------------- #
# D4 — bbox por UF
# --------------------------------------------------------------------------- #
def test_bbox_uf_tem_27_ufs_ascii() -> None:
    assert len(c.BBOX_UF) == 27
    for uf, bbox in c.BBOX_UF.items():
        assert uf.isascii() and uf.isupper() and len(uf) == 2
        lat_min, lat_max, lng_min, lng_max = bbox
        assert lat_min < lat_max, uf
        assert lng_min < lng_max, uf


@pytest.mark.parametrize("uf", sorted(CAPITAIS))
def test_bbox_uf_contem_capital(uf: str) -> None:
    """Cross-check das 27 capitais: pega typo de digitacao nos retangulos do `BBOX_UF`."""
    lat, lng = CAPITAIS[uf]
    assert c.coord_no_bbox_uf(lat, lng, uf), f"capital de {uf} fora do proprio bbox"
    assert c.coord_no_envelope(lat, lng), f"capital de {uf} fora do envelope do Brasil"


def test_bbox_uf_dentro_do_envelope_brasil() -> None:
    env_lat_min, env_lat_max, env_lng_min, env_lng_max = c.ENVELOPE_BRASIL
    for uf, (lat_min, lat_max, lng_min, lng_max) in c.BBOX_UF.items():
        assert env_lat_min <= lat_min and lat_max <= env_lat_max, uf
        assert env_lng_min <= lng_min and lng_max <= env_lng_max, uf


def test_bbox_uf_fail_open_em_uf_desconhecida() -> None:
    """UF ausente/vazia/fora do dict NAO descarta a linha (so o envelope do Brasil vale)."""
    assert c.coord_no_bbox_uf(-23.55, -46.63, "") is True
    assert c.coord_no_bbox_uf(-23.55, -46.63, None) is True
    assert c.coord_no_bbox_uf(-23.55, -46.63, "XX") is True
    # ...mas UF conhecida e coordenada grosseiramente inconsistente e' descartada.
    assert c.coord_no_bbox_uf(-23.55, -46.63, "AM") is False


def test_bbox_uf_tolerancia_salva_divisa() -> None:
    """A tolerancia de 0,5 grau evita matar academia legitima junto a divisa de UF."""
    lat_min, _lat_max, lng_min, _lng_max = c.BBOX_UF["SP"]
    assert c.coord_no_bbox_uf(lat_min - 0.2, lng_min - 0.2, "SP") is True
    assert c.coord_no_bbox_uf(lat_min - 5.0, lng_min - 5.0, "SP") is False


def test_coord_no_envelope_rejeita_nao_numerico_e_fora() -> None:
    assert c.coord_no_envelope(-23.55, -46.63) is True
    assert c.coord_no_envelope(0.0, 0.0) is False  # Atlantico, fora do envelope
    assert c.coord_no_envelope("abc", -46.63) is False
    assert c.coord_no_envelope(None, None) is False
    assert c.coord_no_envelope(float("nan"), -46.63) is False


# --------------------------------------------------------------------------- #
# D2 — parser de data
# --------------------------------------------------------------------------- #
def test_parse_data_coleta_aceita_iso_e_falha_alto() -> None:
    from datetime import date

    assert c.parse_data_coleta("2026-06-01") == date(2026, 6, 1)
    assert c.parse_data_coleta("2026-06-01T13:45:00") == date(2026, 6, 1)
    assert c.parse_data_coleta("2026-06-01 13:45:00") == date(2026, 6, 1)
    for ruim in ("01/06/2026", "amanha", "2026-13-45", "nan"):
        with pytest.raises(ValueError):
            c.parse_data_coleta(ruim)
    with pytest.raises(ValueError):
        c.parse_data_coleta(None)


def test_parse_data_coleta_nao_ecoa_o_valor_no_erro() -> None:
    """Anti-PII no log: a mensagem carrega coluna e fonte, NUNCA o valor ofensor."""
    ofensor = "01/06/2026"
    with pytest.raises(ValueError) as exc:
        c.parse_data_coleta(ofensor, coluna="data_coleta", fonte="totalpass")
    mensagem = str(exc.value)
    assert ofensor not in mensagem
    assert "data_coleta" in mensagem
    assert "totalpass" in mensagem


# --------------------------------------------------------------------------- #
# D3 — primitivas CONGELADAS da chave
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Academia Ação & Cia.", "academia acao cia"),
        ("  DUPLO   espaço  ", "duplo espaco"),
        ("Smart Fit - Centro", "smart fit centro"),
        ("ÁÉÍÓÚ Ç", "aeiou c"),
        ("nan", ""),
        ("", ""),
        (None, ""),
        (float("nan"), ""),
    ],
)
def test_normalizar_texto_congelado(entrada: object, esperado: str) -> None:
    """CONGELADA: mudar esta funcao re-chaveia a serie inteira (bump de versao obrigatorio)."""
    assert c.normalizar_texto(entrada) == esperado


def test_chave_estavel_absorve_jitter_dentro_do_hex() -> None:
    """Jitter de ~10 m dentro do mesmo hex NAO pode gerar chave nova (falso churn em S3)."""
    hex_id = h3.latlng_to_cell(-23.5500, -46.6300, 7)
    lat, lng = h3.cell_to_latlng(hex_id)
    hex_a = h3.latlng_to_cell(lat, lng, 7)
    hex_b = h3.latlng_to_cell(lat + 0.0001, lng + 0.0001, 7)  # ~11 m do centroide
    assert hex_a == hex_b, "pre-condicao: as duas coordenadas caem no mesmo hex"
    chave_a = c.chave_hash_estavel("unidades", "smart_fit", "Smart Fit Centro", hex_a)
    chave_b = c.chave_hash_estavel("unidades", "smart_fit", "Smart Fit  Centro", hex_b)
    assert chave_a == chave_b
    assert len(chave_a) == 40 and int(chave_a, 16) >= 0


def test_chave_muda_com_rede_diferente() -> None:
    hex_id = h3.latlng_to_cell(-23.5500, -46.6300, 7)
    base = c.chave_hash_estavel("unidades", "smart_fit", "Unidade Centro", hex_id)
    assert base != c.chave_hash_estavel("unidades", "selfit", "Unidade Centro", hex_id)
    assert base != c.chave_hash_estavel("totalpass", "smart_fit", "Unidade Centro", hex_id)
    assert base != c.chave_hash_estavel("unidades", "smart_fit", "Unidade Norte", hex_id)


def test_chave_do_slug_tambem_e_sha1_de_40() -> None:
    """Refinamento do gate: as DUAS variantes de chave sao sha1 hex de 40 (dtype uniforme)."""
    chave = c.chave_do_slug("totalpass", "smart-fit-isaura-parente")
    assert len(chave) == 40
    assert chave == c.chave_do_slug("totalpass", "Smart-Fit-Isaura-Parente")  # normalizado
    assert chave != c.chave_do_slug("wellhub", "smart-fit-isaura-parente")


def test_concorrente_id_replica_formula_producao() -> None:
    """Formula de producao REPLICADA (nunca importada: `normalizar_concorrentes` e _DENY_CRITICO)."""
    rede, nome, lat, lng = "smart_fit", "Smart Fit Centro", -23.5500, -46.6300
    esperado = hashlib.sha1(f"{rede}|{nome}|{lat:.6f}|{lng:.6f}".encode()).hexdigest()
    assert c.concorrente_id_producao(rede, nome, lat, lng) == esperado
    assert c.concorrente_id_producao(rede, nome, "abc", lng) == ""


# --------------------------------------------------------------------------- #
# hash_campos_raspados
# --------------------------------------------------------------------------- #
def test_hash_campos_raspados_exige_fonte_do_contrato() -> None:
    with pytest.raises(ValueError):
        c.hash_campos_raspados({"nome": "X"}, "fonte_inexistente")


def test_hash_campos_raspados_trata_campo_ausente_como_vazio() -> None:
    completo = c.hash_campos_raspados(
        {"nome_unidade": "X", "latitude": -23.55, "longitude": -46.63}, "unidades"
    )
    com_extra = c.hash_campos_raspados(
        {"nome_unidade": "X", "latitude": -23.55, "longitude": -46.63, "cep": "01000-000"},
        "unidades",
    )
    assert completo == com_extra, "campo fora de CAMPOS_HASH_POR_FONTE nao entra no hash"
    parcial = c.hash_campos_raspados({"nome_unidade": "X"}, "unidades")
    assert parcial != completo


def test_padroes_de_ruido_casam_os_exemplos_do_contrato() -> None:
    for nome in ("Teste Raised", "ACADEMIA DEMO", "Sandbox Fitness", "Homologacao TTP"):
        assert c.rotulo_de_teste(nome) is True
    assert c.rotulo_de_teste("Academia Testemunha") is False  # word-boundary, nao substring
    for nome in (
        "Zon Tecnologia",
        "SAGAZ Sistemas",
        "TSITECH Solucoes",
        "DATAFITNESS - TTP",
        "Batatao Jeans - Fornecedor X",
    ):
        assert c.entrada_tecnologia_totalpass(nome) is True
    assert c.entrada_tecnologia_totalpass("Academia Central") is False
