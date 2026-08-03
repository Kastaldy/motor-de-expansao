import motor_expansao
import motor_expansao.core
import motor_expansao.core.constants
import motor_expansao.core.scoring
import motor_expansao.dashboard
import motor_expansao.dashboard.competitors
import motor_expansao.dashboard.data
import motor_expansao.data
import motor_expansao.pipelines
import motor_expansao.pipelines.m1
import motor_expansao.pipelines.m1.base_h3_brasil
import motor_expansao.pipelines.m1.fase1_bi_exports
import motor_expansao.pipelines.m1.hex_enrichment


def test_package_importable():
    assert motor_expansao.__version__ == "0.1.0"


def test_subpackages_importable():
    for mod in (
        motor_expansao.dashboard,
        motor_expansao.core,
        motor_expansao.data,
        motor_expansao.pipelines,
        motor_expansao.pipelines.m1,
    ):
        assert mod is not None


def test_core_modules_importable():
    for mod in (
        motor_expansao.core.constants,
        motor_expansao.core.scoring,
    ):
        assert mod is not None


def test_dashboard_modules_importable():
    # DEC-022: pages/components (UI Streamlit) sairam; o pacote dashboard segue como
    # motor compartilhado (censo_*, relatorio_municipal, competitors, data).
    for mod in (
        motor_expansao.dashboard.competitors,
        motor_expansao.dashboard.data,
    ):
        assert mod is not None


def test_dashboard_data_exports():
    from motor_expansao.dashboard.data import (
        apply_global_filters,
        build_city_summary,
        build_uf_summary,
        enrich_dashboard_data,
    )
    assert all(callable(f) for f in [apply_global_filters, build_city_summary, build_uf_summary, enrich_dashboard_data])


def test_dashboard_competitors_exports():
    from motor_expansao.dashboard.competitors import (
        competitor_icon_data,
        load_competitor_points,
    )

    assert all(callable(f) for f in [competitor_icon_data, load_competitor_points])


def test_m1_pipeline_modules_importable():
    for mod in (
        motor_expansao.pipelines.m1.base_h3_brasil,
        motor_expansao.pipelines.m1.fase1_bi_exports,
        motor_expansao.pipelines.m1.hex_enrichment,
    ):
        assert mod is not None


