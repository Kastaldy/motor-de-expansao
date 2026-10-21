"""Relatorio Municipal do Brasil com a resposta unica de "onde expandir" (DEC-077).

Pedido do Felipe (2026-10-21) para o PDF municipal, item a item:
1. "Onde crescer" = Top 10 do modulo unico (5 Mata Virgem por residual + 5 Premium por
   populacao), vaga vazia sinalizada, nome por `rotulos_das_regioes`; mesmo layout de duas
   tabelas e mesmo mapa de duas cores.
2. Uma resposta so': sem a tabela de bairros aprovados e sem o verde de aprovado nos mapas;
   Expansao de Dominio, Bairros por Zona e o card de zonas ficam fora ate' os dados do gestor.
3. Sem veredito: o `v_frase` ("E' praca para entrar") sai de "Como a cidade esta indo".
4. Espaco para academias so' como leitura, com o rotulo novo.
5. Mesma base da tela: a particao enriquecida, com a coluna `uf`. Sem regua (Argentina), o
   PDF segue como antes.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dashboard import relatorio_municipal as rm
from motor_expansao.dashboard import relatorio_praca as rp
from motor_expansao.dashboard.relatorio_municipal import (
    CHAVE_RESPOSTA_UNICA,
    agregar_municipio,
    gerar_pdf_relatorio_municipal,
    render_mapas_municipio,
)
from motor_expansao.recomendacao import (
    ItemRecomendado,
    Recomendacao,
    Recorte,
    ResultadoSegmento,
    VagaVazia,
    carregar_regra,
)
from tests.unit.test_relatorio_municipal import (
    _bairros_geo_sample,
    _paginas_do_pdf,
    _sample_df,
)
from tests.unit.test_relatorio_municipal_praca import _df_cidade, _praca, _resultado


def _regra():
    regra = carregar_regra()
    assert regra is not None, "o Brasil tem regua de recomendacao (DEC-077)"
    return regra


def _item(seg: str, pos: int, hex_id: str, *, residual: float, populacao: float,
          renda_municipal: bool = False) -> ItemRecomendado:
    return ItemRecomendado(
        segmento=seg, posicao=pos, hex_id=hex_id, renda_domiciliar=6_200.0,
        renda_municipal=renda_municipal, populacao=populacao, residual=residual,
        residual_medido=True, score_censitario=61.0, nome_municipio="São Paulo",
    )


def _segmento(seg: str, itens: list[ItemRecomendado], vagas: int) -> ResultadoSegmento:
    vazias = [VagaVazia(segmento=seg, posicao=i + 1, motivo="candidatos_insuficientes")
              for i in range(len(itens), vagas)]
    return ResultadoSegmento(
        segmento=seg, status="completo" if len(itens) >= vagas else "incompleto",
        vagas=(*itens, *vazias), n_elegiveis=len(itens),
    )


def _rec(*, n_mata_virgem: int = 3, indisponivel: bool = False) -> Recomendacao:
    """Recomendacao como o modulo devolve: Mata Virgem com vagas vazias, Premium cheio."""
    regra = _regra()
    n = regra.vagas_por_segmento
    if indisponivel:
        def _vazio(seg: str) -> ResultadoSegmento:
            return ResultadoSegmento(
                segmento=seg, status="indisponivel", n_elegiveis=0,
                vagas=tuple(VagaVazia(segmento=seg, posicao=i + 1, motivo="renda_indisponivel")
                            for i in range(n)),
            )

        mv, pr = _vazio("mata_virgem"), _vazio("premium")
    else:
        mv = _segmento("mata_virgem", [
            _item("mata_virgem", i + 1, f"mv{i}", residual=4_155.0 - 100 * i, populacao=21_000.0)
            for i in range(n_mata_virgem)
        ], n)
        pr = _segmento("premium", [
            _item("premium", i + 1, f"pr{i}", residual=0.0, populacao=38_685.0 - 1_000 * i,
                  renda_municipal=(i == 4))
            for i in range(n)
        ], n)
    return Recomendacao(
        regra=regra, recorte=Recorte(nivel="municipio", uf="SP", cod_municipio="3550308", nome="São Paulo"),
        n_hexes_recorte=200, renda=None, mata_virgem=mv, premium=pr,
    )


_ROTULOS = {"mv0": "Bosque dos Eucaliptos", "mv1": "Vila São Geraldo", "mv2": "Jardim Colonial",
            "pr0": "Parque Industrial", "pr1": "Jardim Satélite", "pr2": "Parque Residencial Aquarius",
            "pr3": "Vila Ema"}


def _resultado_br(df: pd.DataFrame) -> dict:
    return {**_resultado(df), CHAVE_RESPOSTA_UNICA: True}


def _pagina(paginas: list[str], titulo: str) -> str:
    return next(p for p in paginas if p.startswith(titulo))


# --------------------------------------------------------------------------- #
# 1. Onde crescer = Top 10 do modulo unico                                     #
# --------------------------------------------------------------------------- #
def test_onde_crescer_mostra_mata_virgem_e_premium_do_modulo():
    df = _df_cidade(2)
    praca = _praca(df, recomendacao=_rec(), rotulos_recomendacao=_ROTULOS)
    paginas = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado_br(df), None, praca=praca))
    onde = _pagina(paginas, "Onde crescer")

    assert "Mata Virgem (ordem: residual)" in onde
    assert "Premium (ordem: população)" in onde
    # A lista por coluna (Argentina) nao aparece no Brasil.
    assert "Maior residual" not in onde and "Maior socioeconômico" not in onde
    # Nome pela recomendacao; sem rotulo, o municipio (o modulo deixa o hexagono sem bairro de fora).
    for nome in ("Bosque dos Eucaliptos", "Jardim Colonial", "Parque Industrial", "Vila Ema"):
        assert nome in onde, nome
    assert "São Paulo" in onde
    # Mata Virgem com 3 regioes: as vagas 4 e 5 saem SINALIZADAS, com o motivo do modulo.
    assert onde.count("Vaga vazia: Não há outra região que atenda à régua neste recorte") == 2
    # Numeros da nota saem da regua, nao do codigo.
    regra = _regra()
    assert f"R$ {regra.mata_virgem.renda_domiciliar_min:,.0f}".replace(",", ".") in onde
    assert "residual medido a partir de 2.000 alunos" in onde
    assert "score censitário a partir de 50 e 10.000 habitantes ou mais" in onde
    assert f"Régua {regra.versao} ({regra.dec})" in onde
    # Renda municipal (sem renda por setor) marcada e explicada.
    assert "*" in onde and "Renda do município" in onde
    # Nenhum hexagono nas duas listas -> a nota nao fala em "cortado ao meio".
    assert "cortado ao meio" not in onde


def test_onde_crescer_sem_k_da_malha_diz_indisponivel_numa_linha_so():
    df = _df_cidade(2)
    praca = _praca(df, recomendacao=_rec(indisponivel=True))
    onde = _pagina(_paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado_br(df), None, praca=praca)),
                   "Onde crescer")
    motivo = "Renda indisponível: recomendação suspensa até a base ser corrigida"
    assert onde.count(motivo) == 2  # uma linha por segmento, nao cinco
    assert "Vaga vazia:" not in onde  # nenhuma linha de vaga vazia (a nota explica o termo)


def test_listas_do_mapa_e_hexes_rotulados_saem_da_recomendacao():
    from motor_expansao.api import service

    rec = _rec()
    mv, pr = service._listas_da_recomendacao(rec)
    assert list(mv["hex_id"]) == ["mv0", "mv1", "mv2"] and list(mv["posicao"]) == [1, 2, 3]
    assert list(pr["hex_id"]) == [f"pr{i}" for i in range(5)]
    assert not set(mv["hex_id"]) & set(pr["hex_id"])
    praca = _praca(_df_cidade(2), recomendacao=rec)
    assert service._hexes_da_recomendacao(praca) == ["mv0", "mv1", "mv2", "pr0", "pr1", "pr2", "pr3", "pr4"]
    assert service._hexes_da_recomendacao(_praca(_df_cidade(2))) == []


def test_mapa_das_duas_listas_diz_mata_virgem_e_premium(monkeypatch):
    from motor_expansao.dashboard import relatorio_praca_mapas as rpm

    escritos: list[str] = []
    original = rpm._legenda

    def _espia(draw, titulo, itens, *a, **kw):
        escritos.extend(rotulo for rotulo, _ in itens)
        return original(draw, titulo, itens, *a, **kw)

    monkeypatch.setattr(rpm, "_legenda", _espia)
    df = _df_cidade(2)
    hexes = rp.preparar_hexes_da_cidade(df, {})
    mv = pd.DataFrame({"hex_id": list(df["hex_id"][:2]), "posicao": [1, 2]})
    pr = pd.DataFrame({"hex_id": list(df["hex_id"][2:4]), "posicao": [1, 2]})
    png = rpm.render_onde_crescer_duas_listas(
        hexes, mv, pr, basemap=False, rotulos_listas=("Mata Virgem", "Premium"),
        subtitulo="5 Mata Virgem e 5 Premium (DEC-077)",
    )
    assert png is not None
    assert "Mata Virgem" in escritos and "Premium" in escritos
    assert "Maior residual" not in escritos


# --------------------------------------------------------------------------- #
# 2 e 4. Uma resposta so' e o Espaco como leitura                              #
# --------------------------------------------------------------------------- #
def test_resposta_unica_tira_as_outras_listas_de_onde_expandir():
    df = _df_cidade(2)
    praca = _praca(df, recomendacao=_rec(), rotulos_recomendacao=_ROTULOS)
    paginas = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado_br(df), None, praca=praca))
    texto = " ".join(paginas)
    titulos = [p.splitlines()[0] for p in paginas if p]

    assert not any(t.startswith("Expansão de Domínio") for t in titulos)
    assert not any(t.startswith("Bairros por Zona") for t in titulos)
    assert "zonas de atuação" not in texto
    assert "BAIRROS APROVADOS" not in texto
    assert "REGIÕES CONSIDERADAS" not in texto
    assert "aprovad" not in texto.casefold()
    # As paginas neutras continuam (Juan, 2026-10-22).
    assert any(t.startswith("Visão Geral do Município") for t in titulos)
    assert any(t.startswith("Resumo da Região") for t in titulos)
    # Espaco so' como leitura, com o rotulo do Felipe.
    assert "capacidade não atendida nas regiões com residual a partir de 2.000 alunos" in texto


def test_sem_regua_o_pdf_segue_como_antes():
    """Argentina (ou quem chama o PDF direto): sem a chave, nada da DEC-077 muda o relatorio."""
    df = _df_cidade(2)
    paginas = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado(df), None, praca=_praca(df)))
    titulos = [p.splitlines()[0] for p in paginas if p]
    texto = " ".join(paginas)
    assert any(t.startswith("Expansão de Domínio") for t in titulos)
    assert any(t.startswith("Bairros por Zona") for t in titulos)
    assert "zonas de atuação" in texto
    onde = _pagina(paginas, "Onde crescer")
    assert "Maior residual" in onde and "Mata Virgem" not in onde


def _cores_de_preenchimento(monkeypatch) -> list:
    """Escuta as cores com que cada poligono do mapa e' preenchido (hexagono ou bairro)."""
    from PIL import ImageDraw

    vistas: list = []
    original = ImageDraw.ImageDraw.polygon

    def _espia(self, xy, fill=None, outline=None, width=1):
        vistas.append(fill)
        return original(self, xy, fill=fill, outline=outline, width=width)

    monkeypatch.setattr(ImageDraw.ImageDraw, "polygon", _espia)
    return vistas


_VERDES_DE_APROVADO = (rm._HEX_APROVADO_RGBA, rm._HEX_DESTAQUE_RGBA)


def test_visao_geral_e_resumo_sem_o_verde_de_aprovado(monkeypatch):
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    cores = _cores_de_preenchimento(monkeypatch)
    antes = render_mapas_municipio(df, res, basemap=False, unidade=rm.UNIDADE_HEXAGONO)
    # O verde do aprovado existe sem a chave -- senao o teste nao prova nada.
    assert any(c in _VERDES_DE_APROVADO for c in cores)
    assert "dominio" in antes
    cores.clear()
    depois = render_mapas_municipio(df, {**res, CHAVE_RESPOSTA_UNICA: True}, basemap=False,
                                    unidade=rm.UNIDADE_HEXAGONO)
    assert not any(c in _VERDES_DE_APROVADO for c in cores)
    assert "dominio" not in depois


def test_visao_geral_por_bairro_sem_verde_e_sem_tabela(monkeypatch):
    df = _sample_df()
    geo = _bairros_geo_sample()
    hexes = list(df["hex_id"])
    geo["bairros"][0]["pesos_hex"] = {hexes[0]: 1.0, hexes[1]: 1.0}
    geo["bairros"][1]["pesos_hex"] = {hexes[2]: 1.0, hexes[3]: 1.0}
    res = {**agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP", bairros_geo=geo),
           CHAVE_RESPOSTA_UNICA: True}
    cores = _cores_de_preenchimento(monkeypatch)
    mapas = render_mapas_municipio(df, res, basemap=False)
    assert not any(c in _VERDES_DE_APROVADO for c in cores)
    paginas = _paginas_do_pdf(gerar_pdf_relatorio_municipal(res, mapas))
    visao = _pagina(paginas, "Visão Geral do Município")
    assert "BAIRROS APROVADOS" not in visao and "aprovad" not in visao.casefold()


# --------------------------------------------------------------------------- #
# 3. Sem veredito                                                              #
# --------------------------------------------------------------------------- #
def test_como_a_cidade_esta_indo_sem_e_praca_para_entrar():
    linha = {"cres_tendencia": "Em alta", "v_frase": "É praça para entrar."}
    com = rp.resumir_crescimento(linha, uf="SP")
    sem = rp.resumir_crescimento(linha, uf="SP", com_veredito=False)
    assert "praça para entrar" in com.frase
    assert "praça para entrar" not in sem.frase and sem.disponivel
    # So' o veredito, sem tendencia: sem veredito nao ha dado a mostrar.
    so_veredito = rp.resumir_crescimento({"v_frase": "É praça para entrar."}, uf="SP", com_veredito=False)
    assert not so_veredito.disponivel
    # A frase de quem chama (o pontual da tela) segue valendo.
    assert rp.resumir_crescimento(linha, uf="SP", frase="Narrativa.", com_veredito=False).frase == "Narrativa."


# --------------------------------------------------------------------------- #
# 5. Mesma base da tela                                                        #
# --------------------------------------------------------------------------- #
def test_bot_le_a_particao_enriquecida_com_a_coluna_uf(tmp_path, monkeypatch):
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    part = tmp_path / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=AC"
    part.mkdir(parents=True)
    pd.DataFrame({"hex_id": ["ac1", "ac2"], "nome_municipio": ["Rio Branco", "Rio Branco"],
                  "cod_municipio": ["1200401", "1200401"], "so_no_enriquecido": [1, 2]}
                 ).to_parquet(part / "part-0.parquet", index=False)
    settings = Settings(staging_dir=tmp_path, censo_geo_dir=tmp_path / "outputs" / "setores",
                        ibge_dir=tmp_path, ultra_dir=tmp_path)
    monkeypatch.setattr(service, "resolver_municipio", lambda uf, m, s: ("Rio Branco", ["Rio Branco"]))
    monkeypatch.setattr(service, "_mercado_df", lambda s: pytest.fail("no Brasil o bot le a base da tela"))
    capturado: dict = {}

    def _montar(df_muni, **k):
        capturado["df"] = df_muni
        return b"%PDF"

    monkeypatch.setattr(service, "montar_pdf_municipio", _montar)
    service.gerar_pdf_municipio("AC", "Rio Branco", None, settings)
    df = capturado["df"]
    assert set(df["uf"]) == {"AC"} and "so_no_enriquecido" in df.columns


def test_sem_regua_o_bot_segue_na_camada_de_mercado(tmp_path, monkeypatch):
    from motor_expansao import recomendacao
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    monkeypatch.setattr(recomendacao, "carregar_regra", lambda: None)
    settings = Settings(staging_dir=tmp_path, censo_geo_dir=tmp_path / "outputs" / "setores",
                        ibge_dir=tmp_path, ultra_dir=tmp_path)
    assert service._enriquecido_uf_df(settings, "AC") is None
