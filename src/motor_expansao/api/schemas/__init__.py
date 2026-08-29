"""Schemas Pydantic de request/response da API (BLK-API-03).

Espelham `docs/api_geoespacial_openapi.yaml`. `AnalisarResponseJSON` deriva os
KPIs (READ-ONLY) do `result` de `analisar_ponto_censitario_setores` + carimbo de
versao/reprodutibilidade (Decisao 6).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "HealthResponse",
    "ErrorResponse",
    "AnalisarRequest",
    "AnalisarResponseJSON",
    "AnalisarMunicipioRequest",
    "MunicipiosResponse",
]


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str = "development"


class ErrorResponse(BaseModel):
    """Corpo de erro padrao (contrato §9)."""

    detail: str = Field(examples=["Coordenada fora do Brasil"])
    codigo: str = Field(examples=["coordenada_invalida"])


class AnalisarRequest(BaseModel):
    """Fornecer ``{lat,lng}`` OU ``maps_url``. Raio e fixo 1.0 km (nao e parametro)."""

    lat: float | None = Field(default=None, examples=[-21.9180])
    lng: float | None = Field(default=None, examples=[-46.6855])
    maps_url: str | None = Field(
        default=None,
        description="Link do Google Maps; parser puro extrai (lat,lng).",
        examples=["https://maps.google.com/?q=-21.9180,-46.6855"],
    )
    formato: Literal["json", "pdf"] = "json"
    rotulo: str | None = Field(
        default=None,
        description="Nome do endereco/estabelecimento; aparece na capa do PDF no lugar da coordenada.",
        examples=["Pastel da Sueli - Av. Nossa Sra. do Loreto, 927"],
    )

    @model_validator(mode="after")
    def _exige_coordenada(self) -> AnalisarRequest:
        tem_latlng = self.lat is not None and self.lng is not None
        if not tem_latlng and not self.maps_url:
            raise ValueError("Forneca {lat,lng} ou maps_url")
        return self


class AnalisarMunicipioRequest(BaseModel):
    """Relatorio Municipal: UF + nome do municipio (aceita sem acento)."""

    uf: str = Field(examples=["TO"], description="Sigla da UF (2 letras).")
    municipio: str = Field(examples=["Palmas"], description="Nome do municipio (sem acento tolerado).")
    formato: Literal["pdf"] = "pdf"
    # Unidade de leitura. Default "bairro" -- e' a leitura que o time de Expansao usa; quem
    # quiser o relatorio classico pede "hexagono" explicitamente.
    unidade: Literal["bairro", "hexagono"] = Field(
        default="bairro",
        description='Unidade dos mapas: "bairro" (12 paginas) ou "hexagono" (10 paginas).',
    )
    solicitante: str | None = Field(
        default=None,
        description="Nome de quem pediu; carimba a marca d'agua do PDF.",
        examples=["Juan"],
    )

    @model_validator(mode="after")
    def _exige_campos(self) -> AnalisarMunicipioRequest:
        if not (self.uf or "").strip() or not (self.municipio or "").strip():
            raise ValueError("Forneca uf e municipio")
        return self


class MunicipiosResponse(BaseModel):
    """Lista de municipios de uma UF (para escolha no bot)."""

    uf: str = Field(examples=["TO"])
    municipios: list[str] = Field(examples=[["Palmas", "Araguaina", "Gurupi"]])


class AnalisarResponseJSON(BaseModel):
    """KPIs derivados (READ-ONLY) do estudo do ponto + carimbo de versao."""

    lat: float
    lng: float
    raio_km: float = Field(examples=[1.0])
    area_km2: float | None = Field(default=None, examples=[3.14])
    metodo: str = Field(examples=["setor_censitario_intersecao_area_1km"])
    n_setores: int = 0
    pop_total_raio: float | None = None
    renda_per_capita_media_raio: float | None = None
    # Renda media domiciliar (ponderada por domicilios): metrica comparavel a GeoFusion.
    renda_media_domiciliar_raio: float | None = None
    renda_domiciliar_total_raio: float | None = None
    domicilios_total_raio: float | None = None
    metodo_renda_domiciliar_raio: str | None = None
    # ADITIVO (2026-08-14): fracao (0-1, por peso de domicilios) do raio cuja renda depende
    # de uplift EXTRAPOLADO para fora do envelope de calibracao — pede leitura cautelosa.
    fracao_uplift_extrapolado_raio: float | None = None
    densidade_pop_raio_hab_km2: float | None = None
    score_setor_medio: float | None = None
    score_setor_max: float | None = None
    n_concorrentes: int = 0
    n_ultra: int = 0
    # Carimbo de reprodutibilidade (Decisao 6).
    versao_contrato: str = Field(examples=["api-geoespacial/v1"])
    versao_score: str = Field(examples=["score_setor_2022_calibrado"])
    gerado_em: str = Field(examples=["2026-06-11T12:00:00Z"])
    consumidor: str | None = Field(default=None, examples=["bot-telegram"])
