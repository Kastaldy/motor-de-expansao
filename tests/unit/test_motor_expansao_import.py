import motor_expansao
import motor_expansao.dashboard
import motor_expansao.dashboard.data
import motor_expansao.dashboard.components
import motor_expansao.dashboard.pages
import motor_expansao.core
import motor_expansao.core.constants
import motor_expansao.core.scoring
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
    for mod in (
        motor_expansao.dashboard.data,
        motor_expansao.dashboard.components,
        motor_expansao.dashboard.pages,
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


def test_dashboard_components_exports():
    from motor_expansao.dashboard.components import (
        build_kpis,
        build_hybrid_kpis,
        build_map_figure,
        _sort_carteira_by_m1,
    )
    assert all(callable(f) for f in [build_kpis, build_hybrid_kpis, build_map_figure, _sort_carteira_by_m1])


def test_dashboard_pages_exports():
    from motor_expansao.dashboard.pages import (
        inject_styles,
        render_header,
        render_sidebar_filters,
        render_visao_executiva,
    )
    assert all(callable(f) for f in [inject_styles, render_header, render_sidebar_filters, render_visao_executiva])


def test_m1_pipeline_modules_importable():
    for mod in (
        motor_expansao.pipelines.m1.base_h3_brasil,
        motor_expansao.pipelines.m1.fase1_bi_exports,
        motor_expansao.pipelines.m1.hex_enrichment,
    ):
        assert mod is not None


def test_legacy_m1_wrappers_export_modules():
    import base_h3_brasil
    import fase1_bi_exports
    import hex_enrichment

    assert callable(base_h3_brasil.main)
    assert callable(fase1_bi_exports.main)
    assert callable(hex_enrichment.main)
