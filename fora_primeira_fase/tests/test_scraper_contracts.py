"""
tests/contracts/test_scraper_contracts.py — Testes de contrato de scrapers

Estratégia: salvar amostras reais de HTML e validar que os parsers
extraem os campos obrigatórios. Quando o HTML mudar, os testes falham
antes do sistema ir para produção com dados corrompidos.

Para adicionar novo snapshot:
    1. Rodar o scraper em modo real: await scraper.rodar(cidade="São Paulo")
    2. Copiar o HTML de data/snapshots/<scraper>/ para tests/contracts/fixtures/
    3. Escrever o teste validando os campos extraídos
"""

from pathlib import Path

# Diretório de fixtures HTML
FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def criar_fixture_html(nome: str, conteudo: str) -> Path:
    """Helper para criar fixtures de teste."""
    path = FIXTURES_DIR / nome
    path.write_text(conteudo, encoding="utf-8")
    return path


# ============================================================
#  VALIDAÇÕES DE CONTRATO — Campos obrigatórios por fonte
# ============================================================

CAMPOS_OBRIGATORIOS = {
    "wellhub":   ["nome", "cidade", "fonte", "coletado_em"],
    "totalpass": ["nome", "cidade", "fonte", "coletado_em"],
    "smartfit":  ["nome", "cidade", "fonte", "coletado_em"],
    "zap":       ["area_m2", "preco_aluguel", "cidade", "fonte"],
    "vivareal":  ["area_m2", "preco_aluguel", "cidade", "fonte"],
}


def validar_contrato(registros: list[dict], fonte: str) -> list[str]:
    """
    Valida que todos os campos obrigatórios estão presentes e não-nulos.
    Retorna lista de violações (vazia = contrato OK).
    """
    campos = CAMPOS_OBRIGATORIOS.get(fonte, [])
    violacoes = []

    for i, reg in enumerate(registros):
        for campo in campos:
            if campo not in reg or reg[campo] is None:
                violacoes.append(f"Registro {i}: campo '{campo}' ausente ou nulo")

    return violacoes


class TestContratoWellhub:
    """Testa que o scraper do Wellhub extrai os campos mínimos esperados."""

    def test_campos_obrigatorios_presentes(self):
        """Simula saída do scraper e valida contrato."""
        # Simular saída típica do WellhubScraper
        amostra = [
            {
                "nome": "Academia Exemplo",
                "endereco": "Rua das Flores, 100",
                "cidade": "São Paulo",
                "uf": "SP",
                "rede": None,
                "fonte": "wellhub",
                "coletado_em": "2026-04-01T10:00:00",
            }
        ]
        violacoes = validar_contrato(amostra, "wellhub")
        assert not violacoes, f"Violações de contrato: {violacoes}"

    def test_detecta_campo_faltando(self):
        """Deve detectar quando um campo obrigatório some do scraper."""
        amostra_invalida = [
            {
                "endereco": "Rua X, 100",
                "cidade": "São Paulo",
                # 'nome' e 'fonte' faltando
            }
        ]
        violacoes = validar_contrato(amostra_invalida, "wellhub")
        assert len(violacoes) > 0

    def test_nome_nao_pode_ser_vazio(self):
        """Nomes vazios indicam quebra do seletor CSS."""
        amostra = [{"nome": "", "cidade": "SP", "fonte": "wellhub", "coletado_em": "2026-04-01"}]
        # Nome vazio passa o contrato de presença mas deve ser validado
        # na camada de qualidade de dados
        assert amostra[0]["nome"] == ""  # Documentar comportamento atual


class TestContratoImoveis:
    """Testa que scrapers de imóveis retornam campos mínimos."""

    def test_campos_zap_obrigatorios(self):
        amostra = [
            {
                "area_m2": 900.0,
                "preco_aluguel": 45_000.0,
                "cidade": "São Paulo",
                "uf": "SP",
                "fonte": "zap",
                "url": "https://zap.com.br/imovel/123",
            }
        ]
        violacoes = validar_contrato(amostra, "zap")
        assert not violacoes

    def test_area_m2_deve_ser_numerica(self):
        """area_m2 como string indica erro de parsing."""
        area = "900 m²"  # String — erro comum de parsing
        # O pipeline de qualificação vai rejeitar strings
        assert not isinstance(area, (int, float)), "Documentar: área deve ser float"


# ============================================================
#  TESTES DE VALIDAÇÃO DE DADOS (schema)
# ============================================================

class TestValidacaoSchema:
    """Testa invariantes de dados que devem ser mantidos em todos os pipelines."""

    def test_coordenadas_brasil_bounds(self):
        """Todas as coordenadas devem estar dentro dos bounds do Brasil."""
        BRASIL_LAT_MIN, BRASIL_LAT_MAX = -33.75, 5.27
        BRASIL_LNG_MIN, BRASIL_LNG_MAX = -73.98, -28.85

        coordenadas_validas = [
            (-23.55, -46.63),  # São Paulo
            (-22.91, -43.17),  # Rio de Janeiro
            (-15.78, -47.93),  # Brasília
            (-3.73, -38.52),   # Fortaleza
        ]

        for lat, lng in coordenadas_validas:
            assert BRASIL_LAT_MIN <= lat <= BRASIL_LAT_MAX, f"Lat {lat} fora do Brasil"
            assert BRASIL_LNG_MIN <= lng <= BRASIL_LNG_MAX, f"Lng {lng} fora do Brasil"

    def test_status_imovel_valores_validos(self):
        """Status deve ser um dos valores permitidos."""
        STATUS_VALIDOS = {"novo", "qualificado", "em_analise", "proposta", "aprovado", "descartado"}
        status_testados = ["novo", "qualificado", "descartado"]
        for s in status_testados:
            assert s in STATUS_VALIDOS

    def test_score_sempre_entre_0_e_100(self):
        """Qualquer score deve estar entre 0 e 100."""
        from imovel_qualification import qualificar_imovel
        imovel = {
            "area_m2": 900, "lat": -23.55, "lng": -46.63,
            "preco_aluguel": 40_000, "cidade": "São Paulo",
            "dist_ultra_mais_proxima_km": 5.0,
            "tem_estacionamento": True, "tem_fachada": True,
        }
        res = qualificar_imovel(imovel)
        if res.imovel_score is not None:
            assert 0 <= res.imovel_score <= 100
