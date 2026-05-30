"""
jobs/pipelines/imovel_qualification.py — M3 Motor Imobiliário
Aplica filtros de elegibilidade e calcula imovel_score para candidatos.
"""

from dataclasses import dataclass, field

import pandas as pd
import structlog

try:
    from api.config import settings
except ModuleNotFoundError:
    from config import settings  # estrutura flat (desenvolvimento)

log = structlog.get_logger()

# Status da esteira
STATUS_NOVO        = "novo"
STATUS_QUALIFICADO = "qualificado"
STATUS_DESCARTADO  = "descartado"


@dataclass
class ResultadoQualificacao:
    qualificado: bool
    imovel_score: float | None
    motivo_desqualificacao: str | None
    status: str
    detalhes: dict = field(default_factory=dict)


def qualificar_imovel(row: dict) -> ResultadoQualificacao:
    """
    Aplica filtros de elegibilidade em um imóvel candidato.

    Filtros ELIMINATÓRIOS (desqualificam automaticamente):
    - area_m2 < 1.200
    - lat ou lng nulo / fora do Brasil
    - preco_aluguel nulo
    - distância de unidade Ultra < 2km (anti-canibalização)

    Filtros POSITIVOS (aumentam o score):
    - area adequada (1.200–2.000m²+)
    - preço/m² competitivo
    - tem_estacionamento
    - tem_fachada
    """

    area = row.get("area_m2")
    lat = row.get("lat")
    lng = row.get("lng")
    preco = row.get("preco_aluguel")
    dist_ultra = row.get("dist_ultra_mais_proxima_km")

    # --- Filtros eliminatórios ---
    if not area or area < settings.AREA_MIN_M2:
        return ResultadoQualificacao(
            qualificado=False,
            imovel_score=None,
            motivo_desqualificacao=f"Área insuficiente: {area}m² (mínimo {settings.AREA_MIN_M2}m²)",
            status=STATUS_DESCARTADO,
        )

    if not lat or not lng:
        return ResultadoQualificacao(
            qualificado=False,
            imovel_score=None,
            motivo_desqualificacao="Coordenadas inválidas ou ausentes",
            status=STATUS_DESCARTADO,
        )

    # Validar que está no Brasil (bounds aproximados)
    if not (-33.75 <= lat <= 5.27 and -73.98 <= lng <= -28.85):
        return ResultadoQualificacao(
            qualificado=False,
            imovel_score=None,
            motivo_desqualificacao=f"Coordenadas fora do Brasil: ({lat}, {lng})",
            status=STATUS_DESCARTADO,
        )

    if not preco:
        return ResultadoQualificacao(
            qualificado=False,
            imovel_score=None,
            motivo_desqualificacao="Preço de aluguel não informado",
            status=STATUS_DESCARTADO,
        )

    if dist_ultra is not None and dist_ultra < settings.DIST_MIN_ULTRA_KM:
        return ResultadoQualificacao(
            qualificado=False,
            imovel_score=None,
            motivo_desqualificacao=f"Canibalização: unidade Ultra a {dist_ultra:.1f}km (mínimo {settings.DIST_MIN_ULTRA_KM}km)",
            status=STATUS_DESCARTADO,
        )

    # --- Cálculo do score (0-100) ---
    score_area = _score_area(area)
    score_preco = _score_preco_m2(preco, area, row.get("cidade", ""))
    score_estacionamento = 100.0 if row.get("tem_estacionamento") else 50.0
    score_fachada = 100.0 if row.get("tem_fachada") else 50.0

    imovel_score = round(
        score_area          * 0.35 +
        score_preco         * 0.25 +
        score_fachada       * 0.20 +
        score_estacionamento * 0.20,
        2,
    )

    return ResultadoQualificacao(
        qualificado=True,
        imovel_score=imovel_score,
        motivo_desqualificacao=None,
        status=STATUS_QUALIFICADO,
        detalhes={
            "score_area": score_area,
            "score_preco": score_preco,
            "score_estacionamento": score_estacionamento,
            "score_fachada": score_fachada,
        },
    )


def _score_area(area: float) -> float:
    """Score de área: ideal entre 1.500–2.000m². Penaliza extremos.

    Faixas:
      < 1.200m²         → 0.0  (eliminatório)
      1.200 a 1.500m²   → linear 60–85
      1.500 a 2.000m²   → 100.0 (faixa ideal)
      2.000 a 3.500m²   → 85.0  (bom, acima do ideal)
      > 3.500m²         → 65.0  (muito grande, custo operacional alto)
    """
    if area < settings.AREA_MIN_M2:  # < 1200
        return 0.0
    if 1500 <= area <= 2000:
        return 100.0
    if settings.AREA_MIN_M2 <= area < 1500:
        # Linear de 60 a 85 entre 1200 e 1500
        return 60.0 + (area - settings.AREA_MIN_M2) / (1500 - settings.AREA_MIN_M2) * 25.0
    if area <= 3500:
        return 85.0  # 2000–3500 = bom mas acima do ideal
    return 65.0  # > 3500 = muito grande, custo operacional alto


def _score_preco_m2(preco: float, area: float, cidade: str) -> float:
    """
    Score de preço por m²: compara com benchmarks por cidade.
    Benchmarks baseados em dados de mercado (R$/m²/mês).
    Ajustar conforme pesquisa real de mercado.
    """
    BENCHMARKS_PRECO_M2 = {
        "São Paulo":       65.0,
        "Rio de Janeiro":  55.0,
        "Belo Horizonte":  35.0,
        "Brasília":        45.0,
        "default":         30.0,
    }

    benchmark = BENCHMARKS_PRECO_M2.get(cidade, BENCHMARKS_PRECO_M2["default"])
    preco_m2 = preco / area

    if preco_m2 <= benchmark * 0.8:
        return 100.0  # 20% abaixo do benchmark = ótimo
    if preco_m2 <= benchmark:
        return 80.0   # Dentro do benchmark = bom
    if preco_m2 <= benchmark * 1.2:
        return 60.0   # 20% acima = aceitável
    return 30.0       # Muito acima = caro


def processar_lote_imoveis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Processa um lote de imóveis e retorna o DataFrame com colunas de qualificação.
    Input: DataFrame com colunas raw dos scrapers/APIs.
    Output: DataFrame enriquecido com imovel_score, qualificado, status.
    """
    df = df.copy()
    if df.empty:
        return df.assign(
            qualificado=pd.Series(dtype=bool),
            imovel_score=pd.Series(dtype="float64"),
            motivo_desqualificacao=pd.Series(dtype=object),
            status=pd.Series(dtype=object),
        )

    resultados = []

    for _, row in df.iterrows():
        res = qualificar_imovel(row.to_dict())
        resultados.append({
            "qualificado": res.qualificado,
            "imovel_score": res.imovel_score,
            "motivo_desqualificacao": res.motivo_desqualificacao,
            "status": res.status,
        })

    df_res = pd.DataFrame(resultados, index=df.index)
    df_enriquecido = pd.concat([df, df_res], axis=1)

    total = len(df_enriquecido)
    qualificados = df_enriquecido["qualificado"].sum()
    log.info(
        "lote_imoveis_processado",
        total=total,
        qualificados=int(qualificados),
        taxa=f"{qualificados/total*100:.1f}%",
    )

    return df_enriquecido
