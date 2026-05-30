"""
db/models.py — Entidades principais do Motor de Expansão
Todas as tabelas com dados geoespaciais usam PostGIS (coluna geom).
"""

import uuid
from datetime import datetime
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
#  Hexágonos H3 — M1 Geográfico
# --------------------------------------------------------------------------- #

class Hexagono(Base):
    __tablename__ = "hexagonos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hex_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    geom = mapped_column(Geometry("POLYGON", srid=4326))
    cidade: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2))

    # Score composto (0-100)
    hex_score: Mapped[float | None] = mapped_column(Float)

    # Features demográficas (GeoFusion)
    renda_media: Mapped[float | None] = mapped_column(Float)
    densidade_pop: Mapped[float | None] = mapped_column(Float)
    pop_18_45: Mapped[float | None] = mapped_column(Float)
    potencial_consumo: Mapped[float | None] = mapped_column(Float)
    fluxo_estimado: Mapped[float | None] = mapped_column(Float)

    # Pressão competitiva (calculada via M2)
    n_concorrentes: Mapped[int] = mapped_column(Integer, default=0)
    score_competitivo: Mapped[float | None] = mapped_column(Float)

    # Cobertura Ultra existente
    tem_ultra_proxima: Mapped[bool] = mapped_column(Boolean, default=False)
    dist_ultra_mais_proxima_km: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    concorrentes: Mapped[list["Concorrente"]] = relationship(back_populates="hexagono")
    imoveis: Mapped[list["Imovel"]] = relationship(back_populates="hexagono")
    oportunidades: Mapped[list["Oportunidade"]] = relationship(back_populates="hexagono")


# --------------------------------------------------------------------------- #
#  Concorrentes — M2 Radar Competitivo
# --------------------------------------------------------------------------- #

class Concorrente(Base):
    __tablename__ = "concorrentes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    rede: Mapped[str | None] = mapped_column(String(100))

    # Classificação
    tipo: Mapped[str | None] = mapped_column(String(50))
    # rede_grande | rede_media | boutique | independente | low_cost

    endereco: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    geom = mapped_column(Geometry("POINT", srid=4326))

    hex_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("hexagonos.hex_id"))
    fonte: Mapped[str | None] = mapped_column(String(50))
    # wellhub | totalpass | smartfit | bluefit | google_places | manual

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    alvo_aquisicao: Mapped[bool] = mapped_column(Boolean, default=False)
    # True quando é academia independente em hex de alto potencial

    coletado_em: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    hexagono: Mapped[Optional["Hexagono"]] = relationship(back_populates="concorrentes")


# --------------------------------------------------------------------------- #
#  Imóveis — M3 Motor Imobiliário
# --------------------------------------------------------------------------- #

class Imovel(Base):
    __tablename__ = "imoveis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titulo: Mapped[str | None] = mapped_column(String(300))
    tipo: Mapped[str | None] = mapped_column(String(50))
    # galpao | loja | salao | comercial

    area_m2: Mapped[float | None] = mapped_column(Float)
    preco_aluguel: Mapped[float | None] = mapped_column(Float)
    preco_venda: Mapped[float | None] = mapped_column(Float)

    endereco: Mapped[str | None] = mapped_column(Text)
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    geom = mapped_column(Geometry("POINT", srid=4326))

    hex_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("hexagonos.hex_id"))
    fonte: Mapped[str | None] = mapped_column(String(50))
    url: Mapped[str | None] = mapped_column(Text)
    url_fotos: Mapped[str | None] = mapped_column(Text)

    # Atributos qualitativos (quando disponíveis)
    tem_estacionamento: Mapped[bool | None] = mapped_column(Boolean)
    tem_fachada: Mapped[bool | None] = mapped_column(Boolean)
    pe_direito_m: Mapped[float | None] = mapped_column(Float)
    zoneamento: Mapped[str | None] = mapped_column(String(20))

    # Score e qualificação
    imovel_score: Mapped[float | None] = mapped_column(Float)
    qualificado: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo_desqualificacao: Mapped[str | None] = mapped_column(Text)

    # Status na esteira — M5 Operacional
    status: Mapped[str] = mapped_column(String(30), default="novo")
    # novo | qualificado | em_analise | proposta | aprovado | descartado

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    hexagono: Mapped[Optional["Hexagono"]] = relationship(back_populates="imoveis")
    oportunidade: Mapped[Optional["Oportunidade"]] = relationship(back_populates="imovel")
    decisoes: Mapped[list["DecisaoImovel"]] = relationship(back_populates="imovel")


# --------------------------------------------------------------------------- #
#  Oportunidades rankeadas — M4 Scoring
# --------------------------------------------------------------------------- #

class Oportunidade(Base):
    __tablename__ = "oportunidades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("imoveis.id"), unique=True)
    hex_id: Mapped[str] = mapped_column(String(20), ForeignKey("hexagonos.hex_id"))

    # Scores parciais (0-100)
    score_area: Mapped[float | None] = mapped_column(Float)
    score_competitivo: Mapped[float | None] = mapped_column(Float)
    score_imovel: Mapped[float | None] = mapped_column(Float)
    score_abertura: Mapped[float | None] = mapped_column(Float)  # score final

    # Estimativas do modelo ML (M4)
    alunos_est: Mapped[float | None] = mapped_column(Float)
    faturamento_est: Mapped[float | None] = mapped_column(Float)
    ltv_est: Mapped[float | None] = mapped_column(Float)
    payback_est: Mapped[float | None] = mapped_column(Float)  # meses

    status: Mapped[str] = mapped_column(String(30), default="ativa")
    # ativa | em_analise | aprovada | descartada

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    imovel: Mapped["Imovel"] = relationship(back_populates="oportunidade")
    hexagono: Mapped["Hexagono"] = relationship(back_populates="oportunidades")


# --------------------------------------------------------------------------- #
#  Histórico de decisões — M5 Operacional
# --------------------------------------------------------------------------- #

class DecisaoImovel(Base):
    __tablename__ = "decisoes_imovel"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imovel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("imoveis.id"))
    status_anterior: Mapped[str] = mapped_column(String(30))
    status_novo: Mapped[str] = mapped_column(String(30))
    responsavel: Mapped[str | None] = mapped_column(String(100))
    motivo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    imovel: Mapped["Imovel"] = relationship(back_populates="decisoes")


# --------------------------------------------------------------------------- #
#  Execuções de pipelines — M6 Observabilidade
# --------------------------------------------------------------------------- #

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20))
    # running | success | failed | partial

    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str | None] = mapped_column(Text)
    log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
