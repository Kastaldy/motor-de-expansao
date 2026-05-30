"""Testes unitarios para render_mapa_pydeck_fragment.

Cobre:
- importabilidade e presenca do decorador @st.fragment
- ausencia de rerun sem clique novo
- escrita em session_state e st.rerun() ao detectar clique novo
- ausencia de rerun em clique identico
- ausencia de st.sidebar (chamada real, nao apenas mencao em comentario/docstring)
- assinatura da funcao nao aceita df nem acessa artefatos M1

Nota: os testes de comportamento (2-4) chamam `render_mapa_pydeck_fragment.__wrapped__`
diretamente, pois o decorator @st.fragment intercepta st.session_state em contexto de
app Streamlit. Chamar __wrapped__ garante que a logica de negocio seja testada
sem interferencia do runtime do fragmento.
"""
from __future__ import annotations

import ast
import inspect
import unittest.mock as mock

# ---------------------------------------------------------------------------
# Importabilidade
# ---------------------------------------------------------------------------


def test_render_mapa_pydeck_fragment_importavel():
    """render_mapa_pydeck_fragment deve ser importavel de streamlit_app."""
    import streamlit_app  # noqa: F401

    assert hasattr(streamlit_app, "render_mapa_pydeck_fragment")
    fn = streamlit_app.render_mapa_pydeck_fragment
    assert callable(fn)
    # @st.fragment aplica um wrapper que preserva __wrapped__ e __name__
    assert fn.__name__ == "render_mapa_pydeck_fragment"
    assert hasattr(fn, "__wrapped__")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_map_event_empty():
    """Retorna MagicMock simulando evento sem selecao (objects = {})."""
    event = mock.MagicMock()
    event.selection.objects = {}
    return event


def _make_map_event_with_click(lat: float, lng: float):
    """Retorna MagicMock simulando evento de clique com lat/lng."""
    event = mock.MagicMock()
    event.selection.objects = {"hexes": [{"lat": lat, "lng": lng}]}
    return event


def _mock_columns(sizes):
    """Side-effect para st.columns que retorna context managers nulos."""
    cols = []
    for _ in sizes:
        cm = mock.MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = mock.MagicMock(return_value=False)
        cols.append(cm)
    return cols


def _get_unwrapped():
    """Retorna o corpo original da funcao, sem o wrapper @st.fragment."""
    from motor_expansao.dashboard.pages import render_mapa_pydeck_fragment
    return render_mapa_pydeck_fragment.__wrapped__


# ---------------------------------------------------------------------------
# Teste 2 — sem clique, nao altera session_state nem chama rerun
# ---------------------------------------------------------------------------


def test_render_mapa_pydeck_fragment_sem_clique_nao_altera_session_state():
    """Evento vazio (sem selecao) nao deve gravar click_coord nem chamar st.rerun."""
    fn = _get_unwrapped()
    session = {}
    deck = mock.MagicMock()
    empty_event = _make_map_event_empty()

    with (
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.pydeck_chart", return_value=empty_event),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.button", return_value=False),
        mock.patch("streamlit.rerun") as mock_rerun,
        mock.patch("streamlit.session_state", session),
    ):
        fn(deck, 10, ["SP"], [])

    assert "click_coord" not in session
    mock_rerun.assert_not_called()


# ---------------------------------------------------------------------------
# Teste 3 — clique novo: escreve click_coord e chama rerun completo
# ---------------------------------------------------------------------------


def test_render_mapa_pydeck_fragment_clique_novo_escreve_click_coord_e_chama_rerun():
    """Clique novo deve gravar click_coord em session_state e chamar st.rerun() (sem scope)."""
    fn = _get_unwrapped()
    session = {}
    deck = mock.MagicMock()
    click_event = _make_map_event_with_click(-23.55, -46.63)

    with (
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.pydeck_chart", return_value=click_event),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.button", return_value=False),
        mock.patch("streamlit.rerun") as mock_rerun,
        mock.patch("streamlit.session_state", session),
    ):
        fn(deck, 10, ["SP"], [])

    assert session.get("click_coord") == (-23.55, -46.63)
    mock_rerun.assert_called_once()
    # Garantir que nao foi chamado com scope="fragment"
    call_args = mock_rerun.call_args
    assert call_args is None or call_args == mock.call(), (
        "st.rerun() deve ser chamado sem argumentos (rerun completo), nao com scope='fragment'"
    )


# ---------------------------------------------------------------------------
# Teste 4 — clique identico: nao chama rerun
# ---------------------------------------------------------------------------


def test_render_mapa_pydeck_fragment_clique_identico_nao_chama_rerun():
    """Clique com coordenada identica a prevista nao deve chamar st.rerun."""
    fn = _get_unwrapped()
    session = {"click_coord": (-23.55, -46.63)}
    deck = mock.MagicMock()
    click_event = _make_map_event_with_click(-23.55, -46.63)

    # click_coord ja esta no session; ao exibir botao/caption precisamos mockar columns
    with (
        mock.patch("streamlit.caption"),
        mock.patch("streamlit.pydeck_chart", return_value=click_event),
        mock.patch("streamlit.columns", side_effect=_mock_columns),
        mock.patch("streamlit.button", return_value=False),
        mock.patch("streamlit.rerun") as mock_rerun,
        mock.patch("streamlit.session_state", session),
    ):
        fn(deck, 10, ["SP"], [])

    mock_rerun.assert_not_called()


# ---------------------------------------------------------------------------
# Teste 5 — ausencia de st.sidebar (verificado via AST)
# ---------------------------------------------------------------------------


def test_render_mapa_pydeck_fragment_nao_acessa_sidebar():
    """A funcao nao deve conter chamadas reais a st.sidebar no codigo executavel."""
    fn = _get_unwrapped()
    src = inspect.getsource(fn)

    # Parseia o AST e verifica ausencia de acesso a st.sidebar
    tree = ast.parse(src)
    sidebar_accesses = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "st"
        and node.attr == "sidebar"
    ]
    assert sidebar_accesses == [], (
        "render_mapa_pydeck_fragment nao deve acessar st.sidebar"
    )


# ---------------------------------------------------------------------------
# Teste 6 — assinatura nao aceita df (guardrail: nao altera artefatos M1)
# ---------------------------------------------------------------------------


def test_render_mapa_pydeck_fragment_nao_altera_score_priorizacao():
    """A assinatura da funcao nao deve aceitar df nem referenciar artefatos M1.

    Este teste e documental/guardrail: verifica que:
    - 'df' nao e parametro da funcao
    - 'score_priorizacao' e 'hex_score_estrutural' nao aparecem como atribuicoes no AST
    """
    fn = _get_unwrapped()

    # Verifica parametros
    sig = inspect.signature(fn)
    assert "df" not in sig.parameters, (
        "render_mapa_pydeck_fragment nao deve aceitar 'df' como parametro"
    )

    # Verifica ausencia de atribuicoes a score_priorizacao ou hex_score_estrutural no AST
    src = inspect.getsource(fn)
    tree = ast.parse(src)
    guarded_names = {"score_priorizacao", "hex_score_estrutural"}
    assignments_to_guarded = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in guarded_names:
                    assignments_to_guarded.append(target.id)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id in guarded_names:
                assignments_to_guarded.append(node.target.id)

    assert assignments_to_guarded == [], (
        f"render_mapa_pydeck_fragment nao deve atribuir a: {assignments_to_guarded}"
    )
