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

Mais a revisao de 2026-10-22: subtitulo e nota lidos das vagas e da regua, cidade sem regiao e
base recusada pelo modulo com o motivo na pagina, e a ligacao do preparo (`service`) travada nos
dois paises.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

import motor_expansao.renda as renda_pacote
from motor_expansao import recomendacao
from motor_expansao.api import service
from motor_expansao.api.errors import APIError
from motor_expansao.api.settings import Settings
from motor_expansao.dashboard import relatorio_municipal as rm
from motor_expansao.dashboard import relatorio_praca as rp
from motor_expansao.dashboard import relatorio_praca_mapas as rpm
from motor_expansao.dashboard.relatorio_municipal import (
    CHAVE_RESPOSTA_UNICA,
    MOTIVO_BASE_RECUSADA,
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
from tests.unit.recomendacao_fixtures import regra_teste
from tests.unit.test_relatorio_municipal import (
    _bairros_geo_sample,
    _paginas_do_pdf,
    _sample_df,
)
from tests.unit.test_relatorio_municipal_praca import (
    _LAT,
    _LNG,
    _TITULOS,
    _df_cidade,
    _praca,
    _resultado,
)


def _regra():
    regra = carregar_regra()
    assert regra is not None, "o Brasil tem regua de recomendacao (DEC-077)"
    return regra


def _item(seg: str, pos: int, hex_id: str, *, residual: float, populacao: float, renda: float = 6_200.0,
          renda_municipal: bool = False) -> ItemRecomendado:
    return ItemRecomendado(
        segmento=seg, posicao=pos, hex_id=hex_id, renda_domiciliar=renda,
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


def _rec(*, n_mata_virgem: int = 3, n_premium: int | None = None, indisponivel: bool = False,
         regra=None, hexes: list[str] | None = None) -> Recomendacao:
    """Recomendacao como o modulo devolve: Mata Virgem com vagas vazias, Premium cheio.

    Valores distintos por linha (renda, residual, populacao): uma coluna lida do item errado ou
    uma linha fora de ordem muda o texto da tabela. `hexes` troca os ids sinteticos por hexagonos
    reais (os do mapa)."""
    regra = regra or _regra()
    n = regra.vagas_por_segmento
    n_premium = n if n_premium is None else n_premium
    ids_mv = hexes[:n_mata_virgem] if hexes else [f"mv{i}" for i in range(n_mata_virgem)]
    ids_pr = hexes[n_mata_virgem:n_mata_virgem + n_premium] if hexes else [f"pr{i}" for i in range(n_premium)]
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
            _item("mata_virgem", i + 1, h, residual=4_155.0 - 100 * i, populacao=21_000.0,
                  renda=6_200.0 + 100 * i)
            for i, h in enumerate(ids_mv)
        ], n)
        pr = _segmento("premium", [
            _item("premium", i + 1, h, residual=900.0 - 100 * i, populacao=38_685.0 - 1_000 * i,
                  renda=5_100.0 + 100 * i, renda_municipal=(i == 4))
            for i, h in enumerate(ids_pr)
        ], n)
    return Recomendacao(
        regra=regra, recorte=Recorte(nivel="municipio", uf="SP", cod_municipio="3550308", nome="São Paulo"),
        n_hexes_recorte=200, renda=None, mata_virgem=mv, premium=pr,
    )


_ROTULOS = {"mv0": "Bosque dos Eucaliptos", "mv1": "Vila São Geraldo", "mv2": "Jardim Colonial",
            "pr0": "Parque Industrial", "pr1": "Jardim Satélite", "pr2": "Parque Residencial Aquarius",
            "pr3": "Vila Ema"}
_VAGA = "Vaga vazia: Não há outra região que atenda à régua neste recorte"


def _resultado_br(df: pd.DataFrame) -> dict:
    return {**_resultado(df), CHAVE_RESPOSTA_UNICA: True}


def _pagina(paginas: list[str], titulo: str) -> str:
    return next(p for p in paginas if p.startswith(titulo))


def _onde_crescer(praca, df: pd.DataFrame | None = None) -> str:
    df = _df_cidade(2) if df is None else df
    paginas = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado_br(df), None, praca=praca))
    return _pagina(paginas, "Onde crescer")


def _linhas_por_segmento(onde: str) -> dict[str, list[tuple[str, ...]]]:
    """As linhas de cada tabela, na ordem do PDF: (posicao, nome, residual, populacao, renda) ou
    (posicao, vaga vazia). O texto cru traz uma celula por linha; a nota encerra as tabelas."""
    trechos = onde.splitlines()
    tabelas: dict[str, list[tuple[str, ...]]] = {}
    atual = None
    i = 0
    while i < len(trechos):
        t = trechos[i]
        if t.startswith("Mata Virgem (ordem"):
            atual = "mata_virgem"
            tabelas[atual] = []
        elif t.startswith("Premium (ordem"):
            atual = "premium"
            tabelas[atual] = []
        elif t.startswith("Mata Virgem = "):
            atual = None
        elif atual and re.fullmatch(r"[1-9]", t) and i + 1 < len(trechos):
            if trechos[i + 1].startswith("Vaga vazia"):
                tabelas[atual].append((t, trechos[i + 1]))
                i += 2
                continue
            tabelas[atual].append(tuple(trechos[i:i + 5]))
            i += 5
            continue
        i += 1
    return tabelas


def _nota(onde: str) -> str:
    """A nota da pagina numa linha so' (a `multi_cell` quebra onde a largura manda)."""
    return " ".join(onde[onde.index("Mata Virgem = "):].split())


# --------------------------------------------------------------------------- #
# 1. Onde crescer = Top 10 do modulo unico                                     #
# --------------------------------------------------------------------------- #
def test_onde_crescer_mostra_mata_virgem_e_premium_do_modulo():
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(), rotulos_recomendacao=_ROTULOS))

    # A lista por coluna (Argentina) nao aparece no Brasil.
    assert "Maior residual" not in onde and "Maior socioeconômico" not in onde
    assert onde.index("Mata Virgem (ordem: residual)") < onde.index("Premium (ordem: população)")
    # Cada vaga sob o seu segmento, na ordem do modulo, com os numeros do proprio item. Sem rotulo
    # (pr4), o municipio. As vagas 4 e 5 do Mata Virgem saem SINALIZADAS, com o motivo do modulo.
    assert _linhas_por_segmento(onde) == {
        "mata_virgem": [
            ("1", "Bosque dos Eucaliptos", "4.155", "21.000", "R$ 6.200"),
            ("2", "Vila São Geraldo", "4.055", "21.000", "R$ 6.300"),
            ("3", "Jardim Colonial", "3.955", "21.000", "R$ 6.400"),
            ("4", _VAGA),
            ("5", _VAGA),
        ],
        "premium": [
            ("1", "Parque Industrial", "900", "38.685", "R$ 5.100"),
            ("2", "Jardim Satélite", "800", "37.685", "R$ 5.200"),
            ("3", "Parque Residencial Aquarius", "700", "36.685", "R$ 5.300"),
            ("4", "Vila Ema", "600", "35.685", "R$ 5.400"),
            ("5", "São Paulo", "500", "34.685", "R$ 5.500*"),
        ],
    }
    nota = _nota(onde)
    regra = _regra()
    assert f"Régua {regra.versao} ({regra.dec})" in nota
    # Renda municipal (sem renda por setor) marcada e explicada; regiao sem bairro tambem.
    assert "Renda do município" in nota and "(sem bairro mapeado, o do município)" in nota
    assert "No mapa, verde = Mata Virgem e azul = Premium" in nota
    # Nenhum hexagono nas duas listas -> a nota nao fala em "cortado ao meio".
    assert "cortado ao meio" not in onde


def test_nota_le_numeros_e_criterios_da_regua():
    """A nota descreve a regua que decidiu a lista: com outros numeros, outro texto. Com a v1 o
    Premium diz que o residual e' medido (o estimado nao entra, DEC-077 itens 3 e 6)."""
    v1 = _nota(_onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(), rotulos_recomendacao=_ROTULOS)))
    assert ("Mata Virgem = renda domiciliar a partir de R$ 4.500 e residual medido a partir de 2.000 "
            "alunos, em ordem de residual.") in v1
    assert ("Premium = região que não é Mata Virgem, com score censitário a partir de 50 e 10.000 "
            "habitantes ou mais e residual medido, em ordem de população.") in v1

    outra = regra_teste(versao="2099-01_v9", renda_min=5_123.0, residual_min=2_345.0, mv_pop_min=12_000.0,
                        score_min=61.0, premium_pop_min=None, premium_exige_medido=False)
    nota = _nota(_onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(regra=outra),
                                      rotulos_recomendacao=_ROTULOS)))
    assert ("renda domiciliar a partir de R$ 5.123 e residual medido a partir de 2.345 alunos e 12.000 "
            "habitantes ou mais, em ordem de residual") in nota
    assert "score censitário a partir de 61, em ordem de população" in nota
    assert "Régua 2099-01_v9 (DEC-077)" in nota


def test_onde_crescer_sem_k_da_malha_diz_indisponivel_numa_linha_so():
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(indisponivel=True)))
    motivo = "Renda indisponível: recomendação suspensa até a base ser corrigida"
    assert onde.count(motivo) == 2  # uma linha por segmento, nao cinco
    assert f"1\n{motivo}" not in onde  # sem o "1": o motivo vale para a lista toda
    assert "Vaga vazia:" not in onde  # nenhuma linha de vaga vazia (a nota explica o termo)
    assert "No mapa," not in _nota(onde)  # o mapa nao tem regiao a explicar


def test_nome_com_o_mesmo_bairro_dominante_mostra_o_segundo_bairro():
    """DEC-077 item 10: duas regioes do mesmo bairro dominante se separam pelo 2o bairro ("A / B").
    Cortado pelo fim, o B sumia e as duas linhas saiam iguais (Passo Fundo, Bauru, Sumare)."""
    centro = 'Região do Bairro Centro "Centro e Vila Vergueiro"'
    rotulos = {"mv0": "Parque Residencial Aquarius / Jardim Aquarius",
               "mv1": "Parque Residencial Aquarius / Jardim Apolo",
               "mv2": f"{centro} / Região do Bairro Boqueirão",
               "pr0": f"{centro} / Região do Bairro Petrópolis"}
    onde = _onde_crescer(_praca(_df_cidade(2), recomendacao=_rec(), rotulos_recomendacao=rotulos))
    for segundo in ("/ Jardim Aquarius", "/ Jardim Apolo", "/ Região do Bairro Boqueirão",
                    "/ Região do Bairro Petrópolis"):
        assert segundo in onde.splitlines(), segundo
    assert onde.count("Parque Residencial Aquarius\n/ Jardim") == 2


def test_listas_do_mapa_saem_da_recomendacao():
    rec = _rec()
    mv, pr = service._listas_da_recomendacao(rec)
    assert list(mv["hex_id"]) == ["mv0", "mv1", "mv2"] and list(mv["posicao"]) == [1, 2, 3]
    assert list(pr["hex_id"]) == [f"pr{i}" for i in range(5)]
    assert not set(mv["hex_id"]) & set(pr["hex_id"])


def test_subtitulo_do_mapa_conta_as_vagas_preenchidas_e_le_o_teto_da_regua():
    assert service._subtitulos_onde_crescer(_rec()) == (
        "3 Mata Virgem e 5 Premium, de 5 vagas cada", "Nenhuma regiao da cidade atende a regua",
    )
    com, _ = service._subtitulos_onde_crescer(_rec(n_mata_virgem=2, n_premium=1, regra=regra_teste(vagas=4)))
    assert com == "2 Mata Virgem e 1 Premium, de 4 vagas cada"
    indisponivel = service._subtitulos_onde_crescer(_rec(indisponivel=True))
    assert indisponivel[1] == "Recomendacao indisponivel"
    # A fonte embutida dos mapas nao tem os acentos: texto de mapa so' em ASCII.
    assert all(s.isascii() for s in (*service._subtitulos_onde_crescer(_rec()), *indisponivel))


def _espiar_legenda(monkeypatch) -> list[str]:
    escritos: list[str] = []
    original = rpm._legenda

    def _espia(draw, titulo, itens, *a, **kw):
        escritos.extend(rotulo for rotulo, _ in itens)
        return original(draw, titulo, itens, *a, **kw)

    monkeypatch.setattr(rpm, "_legenda", _espia)
    return escritos


def _espiar_subtitulos(monkeypatch) -> dict[str, str | None]:
    """Titulo -> subtitulo de cada mapa da praca (os mapas sao desenhados em paralelo)."""
    vistos: dict[str, str | None] = {}
    original = rpm._base

    def _espia(quadro, titulo, subtitulo, **kw):
        vistos[titulo] = subtitulo
        return original(quadro, titulo, subtitulo, **kw)

    monkeypatch.setattr(rpm, "_base", _espia)
    return vistos


def test_mapa_das_duas_listas_diz_mata_virgem_e_premium(monkeypatch):
    escritos = _espiar_legenda(monkeypatch)
    df = _df_cidade(2)
    hexes = rp.preparar_hexes_da_cidade(df, {})
    mv = pd.DataFrame({"hex_id": list(df["hex_id"][:2]), "posicao": [1, 2]})
    pr = pd.DataFrame({"hex_id": list(df["hex_id"][2:4]), "posicao": [1, 2]})
    png = rpm.render_onde_crescer_duas_listas(
        hexes, mv, pr, basemap=False, rotulos_listas=("Mata Virgem", "Premium"),
        subtitulo="2 Mata Virgem e 2 Premium, de 5 vagas cada",
    )
    assert png is not None
    assert "Mata Virgem" in escritos and "Premium" in escritos
    assert "Maior residual" not in escritos


def test_mapa_sem_nenhuma_regiao_mostra_a_cidade_so_com_o_subtitulo_pedido(monkeypatch):
    escritos = _espiar_legenda(monkeypatch)
    hexes = rp.preparar_hexes_da_cidade(_df_cidade(2), {})
    vazio = pd.DataFrame(columns=["hex_id", "posicao"])
    # Sem o subtitulo (Argentina): como antes, sem mapa.
    assert rpm.render_onde_crescer_duas_listas(hexes, vazio, vazio, basemap=False) is None
    png = rpm.render_onde_crescer_duas_listas(hexes, vazio, vazio, basemap=False,
                                              subtitulo_sem_regiao="Nenhuma regiao da cidade atende a regua")
    assert png is not None and escritos == ["Regioes da cidade"]


# --------------------------------------------------------------------------- #
# Preparo do Brasil (`service._praca_da_cidade` com a regua)                   #
# --------------------------------------------------------------------------- #
def _staging_com_crescimento(tmp_path, v_frase: str = "É praça para entrar.") -> Settings:
    pd.DataFrame({"cod6": ["355030"], "cres_chave_nome": ["SP|SAO PAULO"], "cres_tendencia": ["Em alta"],
                  "v_frase": [v_frase]}).to_parquet(tmp_path / "crescimento_municipal.parquet")
    return Settings(staging_dir=tmp_path, censo_geo_dir=tmp_path, ibge_dir=tmp_path, ultra_dir=tmp_path)


def _setores_um_bairro_por_hex(hexes: list[str]) -> pd.DataFrame:
    import h3

    linhas = []
    for i, h in enumerate(hexes):
        lat, lng = h3.cell_to_latlng(h)
        linhas.append({"nome_bairro": f"Bairro {i}", "nome_municipio": "São Paulo", "pop_total_setor_2022": 100.0,
                       "bbox_minx": lng - 1e-4, "bbox_maxx": lng + 1e-4,
                       "bbox_miny": lat - 1e-4, "bbox_maxy": lat + 1e-4})
    return pd.DataFrame(linhas)


def _praca_br(tmp_path, df: pd.DataFrame, **kw):
    conc = pd.DataFrame({"rede": ["smart_fit"], "lat": [_LAT], "lng": [_LNG]})
    return service._praca_da_cidade(
        df, uf="SP", nome_municipio="São Paulo", cod="3550308", comp_df=conc, ultra_df=None,
        poligono=None, renda_dom={h: 2_000.0 + i for i, h in enumerate(df["hex_id"])},
        settings=_staging_com_crescimento(tmp_path), basemap=False, **kw,
    )


def test_praca_do_brasil_sai_da_recomendacao_unica(tmp_path, monkeypatch):
    df = _df_cidade(2).assign(cod_municipio="3550308")
    hexes = list(df["hex_id"])
    rec = _rec(hexes=hexes)
    monkeypatch.setattr(recomendacao, "montar_recomendacao", lambda *a, **k: rec)
    legendas = _espiar_legenda(monkeypatch)
    subtitulos = _espiar_subtitulos(monkeypatch)
    praca = _praca_br(tmp_path, df, regra=_regra(), setores_nomes=_setores_um_bairro_por_hex(hexes[:8]))

    assert praca.recomendacao is rec
    assert list(praca.top_residual["hex_id"]) == hexes[:3]
    assert list(praca.top_socio["hex_id"]) == hexes[3:8]
    assert set(praca.rotulos_recomendacao) == set(hexes[:8])  # nome nos DOIS segmentos
    assert praca.crescimento.disponivel and "praça para entrar" not in praca.crescimento.frase
    assert "Mata Virgem" in legendas and "Premium" in legendas
    assert subtitulos["Onde crescer"] == "3 Mata Virgem e 5 Premium, de 5 vagas cada"


def test_praca_sem_regua_mantem_o_veredito(tmp_path):
    praca = _praca_br(tmp_path, _df_cidade(2).assign(cod_municipio="3550308"))
    assert praca.recomendacao is None and "praça para entrar" in praca.crescimento.frase


def test_cidade_sem_nenhuma_regiao_mostra_a_cidade_em_cinza(tmp_path, monkeypatch):
    """59 das 313 cidades com 100 mil+ habitantes nao tem nenhuma regiao na regua (DEC-077): e'
    resultado, nao falha -- a pagina nao diz "Mapa indisponivel" nem fala de cores que nao ha."""
    df = _df_cidade(2).assign(cod_municipio="3550308")
    monkeypatch.setattr(recomendacao, "montar_recomendacao",
                        lambda *a, **k: _rec(n_mata_virgem=0, n_premium=0))
    subtitulos = _espiar_subtitulos(monkeypatch)
    praca = _praca_br(tmp_path, df, regra=_regra())

    assert "onde_crescer" in praca.mapas
    assert subtitulos["Onde crescer"] == "Nenhuma regiao da cidade atende a regua"
    onde = _onde_crescer(praca, df)
    assert "Mapa indisponível" not in onde
    assert onde.count(_VAGA) == 10
    nota = _nota(onde)
    assert "verde = Mata Virgem" not in nota and "a cidade em cinza: nenhuma região atende à régua" in nota


def test_base_recusada_pelo_modulo_deixa_o_onde_crescer_indisponivel(tmp_path, monkeypatch, caplog):
    """O modulo valida a base (fail-closed). A recusa nao leva calor, pressao e crescimento, e o
    "Onde crescer" diz que a recomendacao esta indisponivel -- nunca mostra outra lista."""
    df = _df_cidade(2).assign(cod_municipio="3550308")

    def _recusa(*a, **k):
        raise ValueError("recomendacao: coluna(s) obrigatoria(s) ausente(s): fonte_pop_hex_base")

    monkeypatch.setattr(recomendacao, "montar_recomendacao", _recusa)
    subtitulos = _espiar_subtitulos(monkeypatch)
    with caplog.at_level("ERROR", logger="motor_expansao.relatorio_praca"):
        praca = _praca_br(tmp_path, df, regra=_regra())

    assert "recomendacao indisponivel" in caplog.text
    rec = praca.recomendacao
    assert rec is not None and not rec.hex_ids
    assert {v.motivo for v in rec.top10} == {MOTIVO_BASE_RECUSADA}
    assert subtitulos["Onde crescer"] == "Recomendacao indisponivel"
    paginas = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado_br(df), None, praca=praca))
    titulos = [p.splitlines()[0] for p in paginas if p]
    for titulo in _TITULOS:
        assert any(t.startswith(titulo) for t in titulos), titulo
    onde = _pagina(paginas, "Onde crescer")
    assert onde.count("Recomendação indisponível: a base desta cidade não passou na checagem") == 2
    assert "Maior residual" not in onde and "Vaga vazia:" not in onde


# --------------------------------------------------------------------------- #
# Preparo unico (`service.montar_pdf_municipio`): a chave segue a regua       #
# --------------------------------------------------------------------------- #
def _base_do_modulo(*, com_uf: bool = True) -> pd.DataFrame:
    df = _df_cidade(1).assign(
        cod_municipio="3550308", fonte_pop_hex_base="censo_2022_setor",
        renda_per_capita_setor_2022_calibrada=3_000.0,
    )
    return df if com_uf else df.drop(columns=["uf"])


@pytest.fixture
def dubles(monkeypatch, tmp_path) -> dict:
    """Fronteiras de leitura e de desenho trocadas; agregar, praca e recomendacao sao reais."""
    cap: dict = {}
    monkeypatch.setattr(service, "_competitors_ultra", lambda s: (None, None))
    monkeypatch.setattr(service, "_dominio_df", lambda s: None)
    monkeypatch.setattr(rm, "_carregar_bairros_por_hex", lambda *a, **k: None)
    monkeypatch.setattr(rm, "carregar_bairros_geo", lambda *a, **k: None)
    monkeypatch.setattr(rm, "carregar_poligono_municipio", lambda *a, **k: None)

    def _setores(*a, **k):
        cap["setores_pedidos"] = True
        return _setores_um_bairro_por_hex(list(_base_do_modulo()["hex_id"]))

    monkeypatch.setattr(rm, "carregar_setores_com_bairro", _setores)
    monkeypatch.setattr(renda_pacote, "renda_domiciliar_por_hex", lambda df, **k: None)
    monkeypatch.setattr(rm, "agregar_municipio",
                        lambda df, **k: {"uf": k.get("uf"), "nome_municipio": "São Paulo", "n_hex_total": len(df)})

    def _render(df_muni, result, **k):
        cap["hexes_top"] = k.get("hexes_top")
        cap["hexes_rotulados"] = k.get("hexes_rotulados")
        return {}

    monkeypatch.setattr(rm, "render_mapas_municipio", _render)

    def _payloads(result, mapas=None, **k):
        cap["result"] = dict(result)
        cap["praca"] = k.get("praca")

        class _P:
            pdf_bytes = b"%PDF-1.4"

        return _P()

    monkeypatch.setattr(rm, "gerar_payloads_download_relatorio_municipal", _payloads)
    for nome in ("render_calor_cidade", "render_pressao_cidade", "render_onde_crescer_duas_listas"):
        monkeypatch.setattr(rpm, nome, lambda *a, **k: b"PNG")
    cap["settings"] = _staging_com_crescimento(tmp_path)
    return cap


def _montar(dubles: dict, df: pd.DataFrame | None = None) -> None:
    service.montar_pdf_municipio(_base_do_modulo() if df is None else df, uf="SP", nome_municipio="São Paulo",
                                 settings=dubles["settings"], unidade="hexagono")


def test_brasil_liga_a_resposta_unica_e_tira_o_top_do_dominio(dubles, monkeypatch):
    rec = _rec(hexes=list(_base_do_modulo()["hex_id"]))
    monkeypatch.setattr(recomendacao, "montar_recomendacao", lambda *a, **k: rec)
    _montar(dubles)
    assert dubles["result"][CHAVE_RESPOSTA_UNICA] is True
    assert dubles["hexes_top"] is None and dubles["hexes_rotulados"] is None
    assert dubles.get("setores_pedidos") is True
    praca = dubles["praca"]
    assert praca is not None and praca.recomendacao is rec
    # Os nomes saem dos setores do CNEFE nos DOIS segmentos.
    assert set(praca.rotulos_recomendacao) == set(rec.hex_ids)
    assert "praça para entrar" not in praca.crescimento.frase


def test_preparo_sem_regua_deixa_a_chave_desligada(dubles, monkeypatch):
    monkeypatch.setattr(recomendacao, "carregar_regra", lambda *a, **k: None)
    _montar(dubles)
    assert dubles["result"][CHAVE_RESPOSTA_UNICA] is False
    assert dubles["praca"] is not None and dubles["praca"].recomendacao is None
    assert "setores_pedidos" not in dubles


def test_base_da_web_sem_uf_chega_ao_modulo(dubles):
    """A web entrega a particao sem `uf`; o preparo a acrescenta. Recomendacao REAL: sem o carimbo
    k ela sai indisponivel pela RENDA -- base recusada seria o modulo barrando a falta da coluna."""
    _montar(dubles, _base_do_modulo(com_uf=False))
    praca = dubles["praca"]
    assert praca is not None and praca.recomendacao is not None
    assert {v.motivo for v in praca.recomendacao.top10} == {"renda_indisponivel"}


@pytest.fixture
def preparo_sem_regua(monkeypatch, tmp_path) -> dict:
    """Argentina: `montar_pdf_municipio` de verdade com `carregar_regra -> None`, dubles so' nas
    fronteiras de leitura e o gerador do PDF real (mapas sem fundo de ruas)."""
    cap: dict = {}
    monkeypatch.setattr(recomendacao, "carregar_regra", lambda *a, **k: None)
    conc = pd.DataFrame({"rede": ["smart_fit"], "lat": [_LAT], "lng": [_LNG]})
    monkeypatch.setattr(service, "_competitors_ultra", lambda s: (conc, None))
    monkeypatch.setattr(service, "_dominio_df", lambda s: None)
    monkeypatch.setattr(rm, "_carregar_bairros_por_hex", lambda *a, **k: None)
    monkeypatch.setattr(rm, "carregar_bairros_geo", lambda *a, **k: None)
    monkeypatch.setattr(rm, "carregar_setores_com_bairro", lambda *a, **k: cap.setdefault("setores", True))
    monkeypatch.setattr(renda_pacote, "renda_domiciliar_por_hex",
                        lambda d, **k: {h: 3_000.0 + 50.0 * i for i, h in enumerate(d["hex_id"])})
    monkeypatch.setattr(rm, "carregar_poligono_municipio", lambda *a, **k: None)
    render = rm.render_mapas_municipio

    def _render(df_muni, result, **k):
        cap["render"] = dict(k)
        cap["result"] = dict(result)
        return render(df_muni, result, **{**k, "basemap": False})

    monkeypatch.setattr(rm, "render_mapas_municipio", _render)
    for nome in ("render_calor_cidade", "render_pressao_cidade", "render_onde_crescer_duas_listas"):
        monkeypatch.setattr(rpm, nome, (lambda o: lambda *a, **k: o(*a, **{**k, "basemap": False}))(getattr(rpm, nome)))
    payloads = rm.gerar_payloads_download_relatorio_municipal

    def _payloads(result, mapas=None, **k):
        cap["praca"] = k.get("praca")
        return payloads(result, mapas, **k)

    monkeypatch.setattr(rm, "gerar_payloads_download_relatorio_municipal", _payloads)
    cap["pdf"] = service.montar_pdf_municipio(
        _df_cidade(2).assign(cod_municipio="3550308"), uf="SP", nome_municipio="São Paulo",
        settings=_staging_com_crescimento(tmp_path), unidade="hexagono",
    )
    return cap


def test_preparo_sem_regua_mantem_a_argentina_como_antes(preparo_sem_regua):
    cap = preparo_sem_regua
    assert cap["result"][CHAVE_RESPOSTA_UNICA] is False
    praca = cap["praca"]
    assert praca is not None and praca.recomendacao is None
    assert "praça para entrar" in praca.crescimento.frase
    assert "setores" not in cap  # os nomes da recomendacao nao sao lidos
    assert cap["render"]["hexes_top"], "sem regua a camada de Dominio numera o Top 10"
    assert cap["render"]["hexes_rotulados"] == {str(h) for h in praca.onde_crescer.hexagonos["hex_id"]}
    paginas = _paginas_do_pdf(cap["pdf"])
    titulos = [p.splitlines()[0] for p in paginas if p]
    assert any(t.startswith("Expansão de Domínio") for t in titulos)
    assert any(t.startswith("Bairros por Zona") for t in titulos)
    assert "praça para entrar" in " ".join(paginas)
    onde = _pagina(paginas, "Onde crescer")
    assert "Maior residual" in onde and "Mata Virgem" not in onde


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
    assert "Síntese - Diagnóstico" in titulos and "Recomendação" not in " ".join(titulos)
    assert "aprovad" not in texto.casefold()
    # As paginas neutras continuam (Juan, 2026-10-22).
    assert any(t.startswith("Visão Geral do Município") for t in titulos)
    assert any(t.startswith("Resumo da Região") for t in titulos)
    # Espaco so' como leitura, com o rotulo do Felipe -- tambem na capa.
    assert "capacidade não atendida nas regiões com residual a partir de 2.000 alunos" in texto
    assert "novas academias" not in texto
    assert "Ultra, concorrência e capacidade não atendida" in paginas[0]


def test_espaco_no_brasil_mostra_quantas_cabem_sem_ranking_de_regioes():
    """Item 4 (ajustado pelo Felipe): o slide por hexagono fica e mostra quantas academias cabem.
    O painel "ONDE CABEM MAIS" (regioes nomeadas em ordem de residual) sai no Brasil: seria uma
    segunda lista de onde expandir ao lado do Top 10. Sem a chave (Argentina) ele continua."""
    df = _sample_df()

    def _espaco(res: dict) -> str:
        mapas = render_mapas_municipio(df, res, basemap=False, unidade=rm.UNIDADE_HEXAGONO)
        paginas = _paginas_do_pdf(gerar_pdf_relatorio_municipal(res, mapas, unidade=rm.UNIDADE_HEXAGONO))
        return _pagina(paginas, "Como chegamos ao Espaço para academias")

    base = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    br = {**base, CHAVE_RESPOSTA_UNICA: True}
    espaco = _espaco(br)
    assert "Cada número no mapa é quantas cabem" in espaco
    assert br["espaco_rotulos"]["pontos"], "o mapa tem de mostrar quantas cabem por regiao"
    assert "ONDE CABEM MAIS" not in espaco
    assert "ONDE CABEM MAIS" in _espaco(dict(base))


def test_sem_regua_o_pdf_segue_como_antes():
    """Argentina (ou quem chama o PDF direto): sem a chave, nada da DEC-077 muda o relatorio."""
    df = _df_cidade(2)
    paginas = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado(df), None, praca=_praca(df)))
    titulos = [p.splitlines()[0] for p in paginas if p]
    texto = " ".join(paginas)
    assert any(t.startswith("Expansão de Domínio") for t in titulos)
    assert any(t.startswith("Bairros por Zona") for t in titulos)
    assert "Síntese - Diagnóstico & Recomendação" in titulos
    assert "zonas de atuação" in texto
    assert "Ultra e espaço disponível para novas academias" in paginas[0]
    onde = _pagina(paginas, "Onde crescer")
    assert "Maior residual" in onde and "Mata Virgem" not in onde


def test_bairros_oficiais_sem_bairro_so_promete_zonas_fora_do_brasil():
    """Sem bairro na base, a nota da p2 apontava para "as zonas geometricas" -- paginas que o PDF
    do Brasil nao tem mais (2.981 municipios sem bairro real na malha 2022 sem o CNEFE)."""
    df = _df_cidade(2)
    frase = "zonas geométricas por distância ao centroide"
    br = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado_br(df), None))
    ar = _paginas_do_pdf(gerar_pdf_relatorio_municipal(_resultado(df), None))
    assert frase not in " ".join(_pagina(br, "Bairros Oficiais").split())
    assert frase in " ".join(_pagina(ar, "Bairros Oficiais").split())


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


def test_mapa_do_espaco_sem_o_verde_de_aprovado_no_brasil(monkeypatch):
    """O slide do Espaco fica (item 4), mas a regiao com espaco nao sai no verde do aprovado -- que
    no Brasil se confundiria com a Mata Virgem do "Onde crescer" (item 2)."""
    df = _sample_df()
    res = agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")
    verde_espaco = (20, 130, 65, 245)
    cores = _cores_de_preenchimento(monkeypatch)
    rm._render_mapa_municipio(df, camada="espaco", municipio_result=dict(res), basemap=False)
    assert verde_espaco in cores  # sem a chave (Argentina) o verde continua
    cores.clear()
    rm._render_mapa_municipio(df, camada="espaco", municipio_result={**res, CHAVE_RESPOSTA_UNICA: True},
                              basemap=False)
    assert verde_espaco not in cores and rm._HEX_ESPACO_RGBA in cores


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


def test_ajuda_do_bot_nao_anuncia_o_dominio():
    from motor_expansao.api import telegram_bot

    assert "dominio" not in telegram_bot._AJUDA and "onde crescer" in telegram_bot._AJUDA


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


def test_sem_tendencia_a_cidade_segue_com_os_outros_numeros():
    """A tendencia e' nula de proposito onde a confiabilidade e' muito baixa (2.182 municipios):
    sem o veredito, emprego, saldo, salario e setor continuam na pagina (Abaiara/CE, 2026-10)."""
    abaiara = {"v_frase": "É praça para entrar.", "cres_confiab": "muito_baixa", "cres_vinculos": 783,
               "cres_emp_pct": -29.0, "cres_saldo_empresas": 269, "cres_salario": 1621,
               "cres_setor": "Serviços administrativos"}
    sem = rp.resumir_crescimento(abaiara, uf="CE", com_veredito=False)
    rotulos = [r for r, _ in sem.linhas]
    assert sem.disponivel and sem.frase == ""
    assert any(r.startswith("Saldo de empresas") for r in rotulos)
    assert rp.ROTULO_POUCOS_EMPREGOS in rotulos
    com = rp.resumir_crescimento(abaiara, uf="CE")
    assert com.linhas == sem.linhas and "praça para entrar" in com.frase


# --------------------------------------------------------------------------- #
# 5. Mesma base da tela                                                        #
# --------------------------------------------------------------------------- #
def _settings_com_particao(tmp_path) -> Settings:
    part = tmp_path / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=AC"
    part.mkdir(parents=True)
    pd.DataFrame({"hex_id": ["ac1", "ac2", "cz1"], "nome_municipio": ["Rio Branco", "Rio Branco", "Cruzeiro do Sul"],
                  "cod_municipio": ["1200401", "1200401", "1200203"], "so_no_enriquecido": [1, 2, 3]}
                 ).to_parquet(part / "part-0.parquet", index=False)
    return Settings(staging_dir=tmp_path, censo_geo_dir=tmp_path / "outputs" / "setores",
                    ibge_dir=tmp_path, ultra_dir=tmp_path)


def _capturar_o_preparo(monkeypatch) -> dict:
    capturado: dict = {}

    def _montar(df_muni, **k):
        capturado["df"] = df_muni
        return b"%PDF"

    monkeypatch.setattr(service, "montar_pdf_municipio", _montar)
    monkeypatch.setattr(service, "resolver_municipio", lambda uf, m, s: ("Rio Branco", ["Rio Branco"]))
    return capturado


def test_bot_le_a_particao_enriquecida_com_a_coluna_uf(tmp_path, monkeypatch):
    settings = _settings_com_particao(tmp_path)
    capturado = _capturar_o_preparo(monkeypatch)
    monkeypatch.setattr(service, "_mercado_df", lambda s: pytest.fail("no Brasil o bot le a base da tela"))
    service.gerar_pdf_municipio("AC", "Rio Branco", None, settings)
    df = capturado["df"]
    assert sorted(df["hex_id"]) == ["ac1", "ac2"]  # so' o municipio pedido, nao a UF inteira
    assert set(df["uf"]) == {"AC"} and "so_no_enriquecido" in df.columns


def test_sem_regua_o_bot_segue_na_camada_de_mercado(tmp_path, monkeypatch):
    settings = _settings_com_particao(tmp_path)  # a particao existe, mas sem regua nao e' a base
    monkeypatch.setattr(recomendacao, "carregar_regra", lambda *a, **k: None)
    assert service._enriquecido_uf_df(settings, "AC") is None
    capturado = _capturar_o_preparo(monkeypatch)
    mercado = pd.DataFrame({"hex_id": ["m1"], "nome_municipio": ["Rio Branco"], "uf": ["AC"], "so_no_mercado": [1]})
    monkeypatch.setattr(service, "_mercado_df", lambda s: mercado)
    service.gerar_pdf_municipio("AC", "Rio Branco", None, settings)
    assert "so_no_mercado" in capturado["df"].columns


def test_brasil_sem_a_particao_recusa_com_503(tmp_path, monkeypatch):
    """A camada de mercado e' outra base e daria outro Top 10 que o da tela, sem aviso no PDF."""
    settings = Settings(staging_dir=tmp_path, censo_geo_dir=tmp_path / "outputs" / "setores",
                        ibge_dir=tmp_path, ultra_dir=tmp_path)
    monkeypatch.setattr(service, "resolver_municipio", lambda uf, m, s: ("Rio Branco", ["Rio Branco"]))
    monkeypatch.setattr(service, "_mercado_df", lambda s: pytest.fail("no Brasil o bot nao cai no mercado"))
    with pytest.raises(APIError) as erro:
        service.gerar_pdf_municipio("AC", "Rio Branco", None, settings)
    assert erro.value.status_code == 503 and erro.value.codigo == "base_da_tela_ausente"


# --------------------------------------------------------------------------- #
# Subida da API (DEC-077 §7)                                                   #
# --------------------------------------------------------------------------- #
def test_subida_da_api_confere_a_recomendacao(monkeypatch):
    from motor_expansao.api import main
    from motor_expansao.renda import InsumoRendaInvalido

    dev = Settings(environment="development", tokens={"tok-forte-abc": "bot"},
                   api_call_token="tok-forte-abc", bot_senha="uma-senha-forte-123")
    monkeypatch.setattr(main, "get_settings", lambda: dev)
    chamadas: list = []
    monkeypatch.setattr(recomendacao, "validar_na_subida", lambda staging=None: chamadas.append(staging))
    main.create_app()
    assert chamadas == [dev.staging_dir]

    def _sem_carimbo(staging=None):
        raise InsumoRendaInvalido("carimbo k da malha ausente")

    monkeypatch.setattr(recomendacao, "validar_na_subida", _sem_carimbo)
    with pytest.raises(InsumoRendaInvalido):
        main.create_app()
