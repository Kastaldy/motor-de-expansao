"""Regressao anti-"?" da acentuacao dos relatorios PDF (BLK-ACENTO-02).

Garante que TODO texto-fonte voltado ao usuario dos 2 relatorios (`censo_report.py` e
`relatorio_municipal.py`) renderiza em latin-1 (core font Helvetica do fpdf2) sem cair no
`errors="replace"` do `_ascii()` -- ou seja, sem tipografia fora de latin-1 (travessao,
bullet, seta, reticencias, aspas curvas, (c)) que viraria "?" silenciosamente.

Duas camadas complementares:

- 5.1 (PRIMARIA): envolve `_ascii()` dos 2 modulos num wrapper que tenta
  `encode("latin-1", errors="strict")` ANTES da impl real. Qualquer caractere fora de latin-1
  que chegue a `_ascii` acumula uma falha; a impl real segue rodando por baixo (replace) para
  o PDF sair. Testa a CAUSA RAIZ na fonte exata do dano, imune a imagens embutidas.
- 5.2 (COMPLEMENTAR): varredura dos bytes crus (compressao OFF). IMPORTANTE: os PDFs sao
  gerados SEM imagens embutidas (`mapas=None`/`{}` + `ultra_dir` vazio), porque o binario PNG
  (mapas de calor + fundos de branding) contem bytes `0x3F` ("?") LEGITIMOS que nao sao
  artefato de encoding -- confirmado empiricamente (BLK-ACENTO-02): sem imagens, o municipal
  fica com ZERO "?" e o Relatorio Pontual com EXATAMENTE 1, vindo da URL do Google Maps do
  link clicavel (allowlist abaixo). BLK-RELPON-14: o template "recente" foi unificado no
  classico, entao os dois simbolos do pontual caem no mesmo caso (1 "?" da URL).

Reusa os fixtures sinteticos dos 2 arquivos de teste existentes (sem duplicar dicts).
Nenhum teste bate na rede.
"""

from __future__ import annotations

from motor_expansao.dashboard import censo_report, relatorio_municipal
from motor_expansao.dashboard.censo_report import (
    gerar_pdf_relatorio_pontual_censitario,
    gerar_pdf_relatorio_pontual_classico,
)
from motor_expansao.dashboard.relatorio_municipal import (
    agregar_municipio,
    gerar_pdf_relatorio_municipal,
    render_mapas_municipio,
)
from tests.unit.test_relatorio_municipal import _sample_df, _sample_dominio
from tests.unit.test_relatorio_pontual_censitario_export import _RESIDUAL_OK, _sample_result

# Unico "?" LEGITIMO: a URL de busca do Google Maps embutida como link clicavel na pagina de
# Realizacao do template `classico` (via `build_search_url`) contem "?" de sintaxe de URL
# (query string). Essa URL NAO passa por `_ascii()` e NAO e artefato de encoding. Confirmado
# empiricamente (BLK-ACENTO-02): o classico gerado SEM imagens sobra exatamente 1 "?" e ele
# vem deste padrao. Nao expandir a allowlist alem do necessario.
_QMARK_ALLOWLIST = (b"/maps/search/?api=1&query=",)


def _municipio_result():
    df = _sample_df()
    muni = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", dominio_df=_sample_dominio())
    return df, muni


# ---------------------------------------------------------------------------
# 5.1 (PRIMARIA) - auditoria de encoding em errors="strict" no ponto do _ascii
# ---------------------------------------------------------------------------
def test_relatorios_sem_caractere_fora_de_latin1(monkeypatch):
    """Nenhuma string que chega a `_ascii()` nos 2 modulos contem caractere fora de latin-1."""
    falhas: list[str] = []

    def _make_audit(real):
        def _audit(text: str) -> str:
            try:
                str(text).encode("latin-1", errors="strict")
            except UnicodeEncodeError as exc:
                falhas.append(f"{text!r}: {exc}")
            return real(text)

        return _audit

    monkeypatch.setattr(censo_report, "_ascii", _make_audit(censo_report._ascii))
    monkeypatch.setattr(relatorio_municipal, "_ascii", _make_audit(relatorio_municipal._ascii))

    # Template recente + classico do Relatorio Pontual (com mapas reais e rotulo).
    result, mapas = _sample_result()
    gerar_pdf_relatorio_pontual_censitario(result, mapas, residual=_RESIDUAL_OK, rotulo="Av Teste, 100")
    gerar_pdf_relatorio_pontual_classico(result, mapas, residual=_RESIDUAL_OK, rotulo="Av Teste, 100")

    # Relatorio Municipal (com mapas reais offline).
    df, muni = _municipio_result()
    mapas_muni = render_mapas_municipio(df, muni, basemap=False)
    gerar_pdf_relatorio_municipal(muni, mapas_muni)

    assert falhas == [], f"strings fora de latin-1 chegaram a _ascii(): {falhas}"


# ---------------------------------------------------------------------------
# 5.2 (COMPLEMENTAR) - varredura de bytes crus, sem imagens embutidas
# ---------------------------------------------------------------------------
def test_pdf_municipal_sem_link_zero_qmark_nos_bytes(tmp_path):
    """Municipal (sem link externo) -> ZERO "?" nos bytes crus (sem imagens).

    BLK-RELPON-14: o template "recente" do Relatorio Pontual foi unificado no classico (virou
    wrapper depreciado), entao ele deixou de ser um caso "sem link" -- passou a cair na
    allowlist da URL do Google Maps, coberta em `test_pontual_qmark_apenas_da_url_do_maps`.
    """
    _, muni = _municipio_result()
    pdf_muni = gerar_pdf_relatorio_municipal(muni, {}, ultra_dir=tmp_path)
    assert b"?" not in pdf_muni


def test_pontual_qmark_apenas_da_url_do_maps(tmp_path):
    """Relatorio Pontual (sem imagens) -> o unico "?" vem da URL do Google Maps (allowlist).

    BLK-RELPON-14: vale para os DOIS simbolos, ja que o "recente" virou wrapper do classico.
    """
    result, _ = _sample_result()
    pdfs = (
        gerar_pdf_relatorio_pontual_classico(
            result, None, residual=_RESIDUAL_OK, ultra_dir=tmp_path
        ),
        gerar_pdf_relatorio_pontual_censitario(
            result, None, residual=_RESIDUAL_OK, ultra_dir=tmp_path
        ),
    )
    for pdf_bytes in pdfs:
        scrubbed = pdf_bytes
        for pattern in _QMARK_ALLOWLIST:
            scrubbed = scrubbed.replace(pattern, b"")
        assert b"?" not in scrubbed
