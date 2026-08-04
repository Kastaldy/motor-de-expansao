"""FIO ponta a ponta do aviso de origem-centroide, do query param ate o gerador do PDF.

O aviso "o estudo saiu do CENTROIDE do hexagono, nao de um endereco exato" atravessa
quatro camadas antes de virar tinta no PDF:

    ViabilityScreen.tsx  ->  lib/api.ts        ->  rota /api/relatorio/pontual
    (`origemCentroideHex`)   (`origem_centroide_hex=true`)   (query param, default False)
                                                  -> `_gerar_relatorio_pontual_pdf` (threadpool)
                                                  -> `gerar_pdf_relatorio_pontual_classico`

Ate aqui SO a ponta final tinha teste (`test_relatorio_pontual_censitario_export.py` chama
o gerador direto). Os elos do meio -- a rota receber o parametro, a rota REPASSAR ao worker,
o worker repassar ao gerador -- nao eram verificados por ninguem: apagar
`origem_centroide_hex=origem_centroide_hex` da chamada final deixava a suite inteira verde e
o PDF voltava a sair calado, com cara de laudo de endereco exato. Este arquivo fecha isso.

Infraestrutura imitada de `test_piloto_web_endpoints.py` (o molde do backend do piloto):
chama a funcao de rota DIRETO (sem TestClient/httpx), aponta os globais de caminho do app
para um `tmp_path`, e captura os kwargs entregues ao colaborador num dict -- em vez de um
mock `lambda *a, **k`, que aceitaria qualquer assinatura e ficaria verde justamente quando o
kwarg deixasse de ser passado.

ARMADILHA (documentada no molde): os imports desta rota sao LAZY, feitos DENTRO de
`_gerar_relatorio_pontual_pdf`. Monkeypatch em `app.<nome>` NAO pega nada, porque o nome so
passa a existir no escopo local da funcao, resolvido do modulo de ORIGEM a cada chamada. Por
isso todo patch aqui e aplicado no MODULO DE ORIGEM (`motor_expansao.api.service`,
`...dashboard.censo_map`, `...censo_point`, `...censo_report`) -- mesmo padrao de
`test_relatorio_municipal_renderiza_e_passa_os_mapas` no molde.

READ-ONLY sobre o M1: nada aqui escreve artefato; o unico I/O e criar o diretorio vazio que
a rota exige para nao curto-circuitar em 404.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

# Endereco LEGITIMO terminado em parenteses -- a entrada que a implementacao antiga (aviso
# concatenado ao `rotulo`) mutilava. Aqui ele serve para provar que o texto do operador
# atravessa a ROTA sem ser reinterpretado, nao so o gerador.
_ROTULO_COM_PARENTESES = "Av. Paulista, 1500 (Shopping Center 3)"

_LAT, _LNG = -23.55, -46.63


def _point_app_at(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    """Reaponta os globais de caminho do app para um data_dir de teste.

    Mesmo helper do molde, reduzido aos globais que ESTA rota le (`DATA_DIR` para o cache
    de tiles, `CENSO_GEO_DIR` para o gate de 404, `IBGE_DIR`/`ULTRA_DIR`/`STAGING_DIR` para
    o `Settings`). Os loaders com `lru_cache` do molde nao entram no caminho desta rota,
    entao nao ha cache a limpar aqui.
    """
    data_dir = Path(data_dir)
    outputs = data_dir / "outputs"
    monkeypatch.setattr(pilot, "DATA_DIR", data_dir)
    monkeypatch.setattr(pilot, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(pilot, "STAGING_DIR", data_dir / "staging")
    monkeypatch.setattr(pilot, "IBGE_DIR", data_dir / "ibge")
    monkeypatch.setattr(pilot, "ULTRA_DIR", data_dir / "ultra")
    monkeypatch.setattr(pilot, "CENSO_GEO_DIR", outputs / "setores_censitarios_2022_geo")


@pytest.fixture
def gerador_espiao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Rota pronta para rodar sem parquets; devolve o dict com os kwargs vistos pelo gerador.

    Os colaboradores pesados (resolucao da coordenada, motor censitario, render de mapas,
    satelite) viram stubs: o que esta sob teste e o TRANSPORTE do parametro, nao o conteudo
    do PDF -- esse ja e coberto, sobre o PDF de verdade, em
    `test_relatorio_pontual_censitario_export.py`.
    """
    # Unico artefato que a rota exige existir (senao levanta 404 antes de qualquer coisa).
    (tmp_path / "outputs" / "setores_censitarios_2022_geo").mkdir(parents=True)
    _point_app_at(monkeypatch, tmp_path)

    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import censo_map, censo_point, censo_report

    setores = pd.DataFrame({"cod_setor": ["355030801000001"], "nome_municipio": ["SAO PAULO"]})
    monkeypatch.setattr(
        api_service, "_resolver_e_carregar", lambda lat, lng, cfg: ("SP", "3550308", setores)
    )
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))
    monkeypatch.setattr(api_service, "_nome_municipio_de", lambda df: "SAO PAULO")
    monkeypatch.setattr(api_service, "_residual_do_ponto", lambda lat, lng, cfg: None)
    monkeypatch.setattr(
        censo_point, "analisar_ponto_censitario_setores", lambda *a, **k: {"lat": _LAT, "lng": _LNG}
    )
    monkeypatch.setattr(censo_point, "agregar_perfil_bairro_distrito", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_mapas_censitarios_combinados", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_foto_satelite_ponto", lambda *a, **k: None)
    # A rota REESCREVE este global do modulo de mapas (reaponta o cache de tiles para
    # `DATA_DIR`). Registrar o valor ATUAL no monkeypatch faz o pytest restaura-lo no fim --
    # sem isso o modulo ficaria apontando para um `tmp_path` ja apagado pelo resto da sessao.
    monkeypatch.setattr(censo_map, "_BASEMAP_CACHE_DIR", censo_map._BASEMAP_CACHE_DIR)

    visto: dict[str, object] = {}

    def _fake_gerar(result, mapas, **kwargs):
        # Assinatura EXPLICITA nos posicionais + captura dos kwargs (padrao do molde): se a
        # rota parar de passar um kwarg, a chave some do dict e o assert quebra com KeyError,
        # em vez de passar em silencio como faria um `lambda *a, **k`.
        visto["result"] = result
        visto["mapas"] = mapas
        visto.update(kwargs)
        return b"%PDF-1.4 stub"

    monkeypatch.setattr(censo_report, "gerar_pdf_relatorio_pontual_classico", _fake_gerar)
    return visto


def _chamar_rota(**kwargs) -> object:
    """Exercita a rota `async` como o molde faz (`asyncio.run` + kwargs nomeados).

    Nomes iguais aos do contrato HTTP: o FastAPI liga estes parametros a query string, e e
    exatamente essa grafia (`origem_centroide_hex`) que `web/src/lib/api.ts` escreve.
    """
    return asyncio.run(pilot.relatorio_pontual(lat=_LAT, lng=_LNG, **kwargs))


def test_rota_com_origem_centroide_true_entrega_a_flag_ao_gerador(gerador_espiao) -> None:
    """(a) `origem_centroide_hex=true` na rota -> o gerador recebe o kwarg True.

    Elo mais fragil do fio: e a linha `origem_centroide_hex=origem_centroide_hex` no fim de
    `_gerar_relatorio_pontual_pdf`. Apaga-la nao quebrava nada -- o gerador tem default
    False, entao o PDF simplesmente saia sem o aviso, calado.
    """
    resp = _chamar_rota(rotulo="Ponto do hexagono", origem_centroide_hex=True)

    assert resp.media_type == "application/pdf"
    assert resp.body == b"%PDF-1.4 stub", "a rota nao chegou ao gerador (stub nao foi usado)"
    assert gerador_espiao["origem_centroide_hex"] is True, (
        "a rota recebeu origem_centroide_hex=True mas o gerador nao viu a flag: o PDF sai "
        "sem o aviso de centroide e com cara de laudo de endereco exato"
    )


def test_rota_sem_o_parametro_entrega_false_ao_gerador(gerador_espiao) -> None:
    """(b) Sem o parametro na chamada -> o gerador recebe False EXPLICITO.

    Duas coisas de uma vez: o default da rota e False (fluxo de busca por endereco, onde o
    aviso seria mentira) e o kwarg CONTINUA sendo passado. Se a rota deixasse de repassa-lo,
    a chave nem existiria no dict e o assert quebraria -- e o que impede o teste (a) de ser
    satisfeito por um `origem_centroide_hex=True` fixo no worker.
    """
    _chamar_rota(rotulo="Av. Teste, 100")

    assert "origem_centroide_hex" in gerador_espiao, (
        "o gerador nem recebeu o kwarg: a rota parou de repassar o marcador de origem"
    )
    assert gerador_espiao["origem_centroide_hex"] is False


@pytest.mark.parametrize("origem_centroide_hex", [False, True])
def test_rotulo_com_parenteses_atravessa_a_rota_intacto(gerador_espiao, origem_centroide_hex):
    """(c) O `rotulo` chega ao gerador INTEIRO nos dois ramos, mesmo com parenteses.

    `rotulo` e texto livre do operador e a rota nao pode reinterpreta-lo: nem para extrair
    aviso, nem para anexar um. "Av. Paulista, 1500 (Shopping Center 3)" e endereco inteiro.
    Parametrizado nos dois ramos porque a heuristica antiga so era acionada quando havia
    aviso a tratar -- ou seja, no ramo True; cobrir apenas False deixaria o cruzamento que
    mais importa sem teste.
    """
    _chamar_rota(rotulo=_ROTULO_COM_PARENTESES, origem_centroide_hex=origem_centroide_hex)

    assert gerador_espiao["rotulo"] == _ROTULO_COM_PARENTESES, (
        "o rotulo foi alterado no caminho ate o gerador (origem_centroide_hex="
        f"{origem_centroide_hex}): nenhuma camada do fio pode mexer no texto do operador"
    )
    assert gerador_espiao["origem_centroide_hex"] is origem_centroide_hex


def test_nome_do_query_param_e_o_mesmo_que_o_front_envia() -> None:
    """O elo TS -> rota: a grafia do query param tem de casar dos dois lados.

    `web/src/lib/api.ts` escreve `q.set('origem_centroide_hex', 'true')`; o FastAPI liga o
    query param pelo NOME do parametro da funcao de rota. Renomear um lado sem o outro nao
    quebra build nem teste algum: o parametro passa a ser ignorado e o PDF volta a sair sem
    aviso, em silencio. (Precedente de teste Python lendo o front: os
    `tests/unit/test_paridade_*_web.py`.)
    """
    api_ts = _REPO / "web" / "src" / "lib" / "api.ts"
    if not api_ts.is_file():
        pytest.skip("piloto web (web/src) ausente nesta arvore -- nada a comparar")

    param = inspect.signature(pilot.relatorio_pontual).parameters["origem_centroide_hex"]
    assert param.default is False, "o default da rota tem de ser False (fluxo sem aviso)"
    assert f"'{param.name}'" in api_ts.read_text(encoding="utf-8"), (
        f"`web/src/lib/api.ts` nao envia o query param '{param.name}': o front e a rota "
        "deixaram de falar a mesma lingua e o aviso de centroide nunca chega ao PDF"
    )
