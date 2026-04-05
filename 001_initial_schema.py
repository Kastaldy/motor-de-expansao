"""
db/migrations/versions/001_initial_schema.py
Criação do schema inicial: hexagonos, concorrentes, imoveis, oportunidades,
decisoes_imovel, pipeline_runs. Habilita extensão PostGIS.
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
import sqlalchemy.dialects.postgresql as pg

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Habilitar extensão PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")

    # ----------------------------------------------------------------
    # hexagonos
    # ----------------------------------------------------------------
    op.create_table(
        "hexagonos",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hex_id", sa.String(20), unique=True, nullable=False),
        sa.Column("geom", Geometry("POLYGON", srid=4326), nullable=True),
        sa.Column("cidade", sa.String(100)),
        sa.Column("uf", sa.String(2)),
        sa.Column("hex_score", sa.Float),
        sa.Column("renda_media", sa.Float),
        sa.Column("densidade_pop", sa.Float),
        sa.Column("pop_18_45", sa.Float),
        sa.Column("potencial_consumo", sa.Float),
        sa.Column("fluxo_estimado", sa.Float),
        sa.Column("n_concorrentes", sa.Integer, server_default="0"),
        sa.Column("score_competitivo", sa.Float),
        sa.Column("tem_ultra_proxima", sa.Boolean, server_default="false"),
        sa.Column("dist_ultra_mais_proxima_km", sa.Float),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_hexagonos_hex_id", "hexagonos", ["hex_id"])
    op.create_index("ix_hexagonos_uf_cidade", "hexagonos", ["uf", "cidade"])
    op.execute("CREATE INDEX ix_hexagonos_geom ON hexagonos USING GIST (geom)")

    # ----------------------------------------------------------------
    # concorrentes
    # ----------------------------------------------------------------
    op.create_table(
        "concorrentes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("rede", sa.String(100)),
        sa.Column("tipo", sa.String(50)),
        sa.Column("endereco", sa.Text),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("geom", Geometry("POINT", srid=4326)),
        sa.Column("hex_id", sa.String(20), sa.ForeignKey("hexagonos.hex_id")),
        sa.Column("fonte", sa.String(50)),
        sa.Column("ativo", sa.Boolean, server_default="true"),
        sa.Column("alvo_aquisicao", sa.Boolean, server_default="false"),
        sa.Column("coletado_em", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_concorrentes_hex_id", "concorrentes", ["hex_id"])
    op.create_index("ix_concorrentes_rede", "concorrentes", ["rede"])
    op.execute("CREATE INDEX ix_concorrentes_geom ON concorrentes USING GIST (geom)")

    # ----------------------------------------------------------------
    # imoveis
    # ----------------------------------------------------------------
    op.create_table(
        "imoveis",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("titulo", sa.String(300)),
        sa.Column("tipo", sa.String(50)),
        sa.Column("area_m2", sa.Float),
        sa.Column("preco_aluguel", sa.Float),
        sa.Column("preco_venda", sa.Float),
        sa.Column("endereco", sa.Text),
        sa.Column("bairro", sa.String(100)),
        sa.Column("cidade", sa.String(100)),
        sa.Column("uf", sa.String(2)),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("geom", Geometry("POINT", srid=4326)),
        sa.Column("hex_id", sa.String(20), sa.ForeignKey("hexagonos.hex_id")),
        sa.Column("fonte", sa.String(50)),
        sa.Column("url", sa.Text),
        sa.Column("url_fotos", sa.Text),
        sa.Column("tem_estacionamento", sa.Boolean),
        sa.Column("tem_fachada", sa.Boolean),
        sa.Column("pe_direito_m", sa.Float),
        sa.Column("zoneamento", sa.String(20)),
        sa.Column("imovel_score", sa.Float),
        sa.Column("qualificado", sa.Boolean, server_default="false"),
        sa.Column("motivo_desqualificacao", sa.Text),
        sa.Column("status", sa.String(30), server_default="'novo'"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_imoveis_hex_id", "imoveis", ["hex_id"])
    op.create_index("ix_imoveis_status", "imoveis", ["status"])
    op.create_index("ix_imoveis_qualificado", "imoveis", ["qualificado"])
    op.create_index("ix_imoveis_cidade", "imoveis", ["cidade", "uf"])
    op.execute("CREATE INDEX ix_imoveis_geom ON imoveis USING GIST (geom)")

    # ----------------------------------------------------------------
    # oportunidades
    # ----------------------------------------------------------------
    op.create_table(
        "oportunidades",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("imovel_id", pg.UUID(as_uuid=True), sa.ForeignKey("imoveis.id"), unique=True),
        sa.Column("hex_id", sa.String(20), sa.ForeignKey("hexagonos.hex_id")),
        sa.Column("score_area", sa.Float),
        sa.Column("score_competitivo", sa.Float),
        sa.Column("score_imovel", sa.Float),
        sa.Column("score_abertura", sa.Float),
        sa.Column("alunos_est", sa.Float),
        sa.Column("faturamento_est", sa.Float),
        sa.Column("ltv_est", sa.Float),
        sa.Column("payback_est", sa.Float),
        sa.Column("status", sa.String(30), server_default="'ativa'"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_oportunidades_score", "oportunidades", ["score_abertura"])
    op.create_index("ix_oportunidades_status", "oportunidades", ["status"])

    # ----------------------------------------------------------------
    # decisoes_imovel
    # ----------------------------------------------------------------
    op.create_table(
        "decisoes_imovel",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("imovel_id", pg.UUID(as_uuid=True), sa.ForeignKey("imoveis.id")),
        sa.Column("status_anterior", sa.String(30)),
        sa.Column("status_novo", sa.String(30)),
        sa.Column("responsavel", sa.String(100)),
        sa.Column("motivo", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
    )

    # ----------------------------------------------------------------
    # pipeline_runs
    # ----------------------------------------------------------------
    op.create_table(
        "pipeline_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20)),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("records_processed", sa.Integer, server_default="0"),
        sa.Column("records_failed", sa.Integer, server_default="0"),
        sa.Column("errors", sa.Text),
        sa.Column("log", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_pipeline_runs_job", "pipeline_runs", ["job_name", "started_at"])

    # Trigger para updated_at automático
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    for tabela in ["hexagonos", "concorrentes", "imoveis", "oportunidades"]:
        op.execute(f"""
            CREATE TRIGGER trigger_updated_at_{tabela}
            BEFORE UPDATE ON {tabela}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """)


def downgrade() -> None:
    for tabela in ["hexagonos", "concorrentes", "imoveis", "oportunidades"]:
        op.execute(f"DROP TRIGGER IF EXISTS trigger_updated_at_{tabela} ON {tabela}")

    op.execute("DROP FUNCTION IF EXISTS update_updated_at()")
    op.drop_table("pipeline_runs")
    op.drop_table("decisoes_imovel")
    op.drop_table("oportunidades")
    op.drop_table("imoveis")
    op.drop_table("concorrentes")
    op.drop_table("hexagonos")
