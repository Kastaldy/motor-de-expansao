"""Cadastro operacional editavel (BLK-EXEC-00/00b).

E' a PRIMEIRA escrita do piloto, e o backend e' read-only por CI. Estes testes provam que
a escrita acontece SO no diretorio proprio, que a lista branca segura o que pode ser
gravado e que duas edicoes simultaneas nao se sobrescrevem em silencio.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from motor_expansao.dashboard import rede_cadastro as rcad


@pytest.fixture
def base(tmp_path: Path) -> Path:
    diretorio = tmp_path / "cadastro"
    diretorio.mkdir()
    rcad.gravar_cadastro(
        rcad.Cadastro(
            versao=1,
            atualizado_em="2026-08-04T00:00:00+00:00",
            unidades={
                "botafogo-rj": {"consultor": "MARISE", "cidade": "Rio de Janeiro"},
                "orfa-sp": {"consultor": "", "cidade": "Sao Paulo"},
            },
        ),
        diretorio,
    )
    return diretorio


def test_leitura_degrada_sem_o_volume(tmp_path: Path) -> None:
    """CI e dev local nao tem o volume montado -- a aba tem de subir do mesmo jeito."""
    cadastro = rcad.ler_cadastro(tmp_path / "nao-existe")
    assert cadastro.disponivel is False
    assert cadastro.unidades == {}
    assert cadastro.versao == 0
    assert cadastro.de("qualquer") == {}


def test_leitura_de_json_corrompido_nao_derruba_a_aba(tmp_path: Path) -> None:
    diretorio = tmp_path / "cadastro"
    diretorio.mkdir()
    (diretorio / rcad.ARQUIVO_CADASTRO).write_text("{ isto nao e json", encoding="utf-8")
    assert rcad.ler_cadastro(diretorio).disponivel is False


def test_atribuir_consultor(base: Path) -> None:
    novo = rcad.atribuir("orfa-sp", {"consultor": "JAILSON"}, autor="felipe", base=base)
    assert novo.de("orfa-sp")["consultor"] == "JAILSON"
    assert novo.versao == 2
    assert rcad.ler_cadastro(base).de("orfa-sp")["consultor"] == "JAILSON"
    # ...sem tocar o que ja estava la.
    assert novo.de("orfa-sp")["cidade"] == "Sao Paulo"
    assert novo.de("botafogo-rj")["consultor"] == "MARISE"


def test_campo_fora_da_lista_branca_e_rejeitado(base: Path) -> None:
    """O cadastro nao vira porta de escrita para qualquer coisa."""
    with pytest.raises(rcad.CampoNaoEditavel):
        rcad.atribuir("botafogo-rj", {"faturamento": 999}, base=base)
    with pytest.raises(rcad.CampoNaoEditavel):
        rcad.atribuir("botafogo-rj", {"consultor": "X", "inauguracao": "01/01/2000"}, base=base)
    assert rcad.ler_cadastro(base).versao == 1, "nada pode ter sido gravado"
    assert set(rcad.CAMPOS_EDITAVEIS) == {"consultor", "consultor_2", "master_franquia"}


def test_concorrencia_otimista(base: Path) -> None:
    """Sem banco, e' a versao que impede dois consultores se sobrescreverem."""
    rcad.atribuir("orfa-sp", {"consultor": "A"}, versao_cliente=1, base=base)
    with pytest.raises(rcad.ConflitoDeVersao) as erro:
        rcad.atribuir("orfa-sp", {"consultor": "B"}, versao_cliente=1, base=base)
    assert erro.value.versao_atual == 2
    assert rcad.ler_cadastro(base).de("orfa-sp")["consultor"] == "A"


def test_edicao_sem_mudanca_nao_incrementa_versao(base: Path) -> None:
    igual = rcad.atribuir("botafogo-rj", {"consultor": "MARISE"}, base=base)
    assert igual.versao == 1


def test_auditoria_registra_quem_mudou_o_que(base: Path) -> None:
    rcad.atribuir("orfa-sp", {"consultor": "JAILSON"}, autor="felipe@ultra", base=base)
    linhas = (base / rcad.ARQUIVO_LOG).read_text(encoding="utf-8").strip().splitlines()
    registro = json.loads(linhas[-1])
    assert registro["autor"] == "felipe@ultra"
    assert registro["unidade_id"] == "orfa-sp"
    assert registro["campo"] == "consultor"
    assert registro["de"] == ""
    assert registro["para"] == "JAILSON"


def test_escrita_acontece_so_no_diretorio_do_cadastro(base: Path, tmp_path: Path) -> None:
    """A prova que autoriza a primeira escrita do piloto: nada sai deste diretorio."""
    outros = {
        caminho: caminho.stat().st_mtime_ns
        for caminho in tmp_path.rglob("*")
        if caminho.is_file() and base not in caminho.parents
    }
    rcad.atribuir("orfa-sp", {"consultor": "JAILSON"}, base=base)
    for caminho, mtime in outros.items():
        assert caminho.stat().st_mtime_ns == mtime
    escritos = {p.name for p in base.iterdir()}
    assert escritos <= {rcad.ARQUIVO_CADASTRO, rcad.ARQUIVO_LOG}


def test_escrita_sem_volume_falha_com_mensagem_clara(tmp_path: Path) -> None:
    with pytest.raises(rcad.CadastroIndisponivel):
        rcad.atribuir("x", {"consultor": "Y"}, base=tmp_path / "nao-existe")


def test_valor_e_limpo_e_limitado(base: Path) -> None:
    novo = rcad.atribuir("orfa-sp", {"consultor": "  ANA   MARIA \n"}, base=base)
    assert novo.de("orfa-sp")["consultor"] == "ANA MARIA"
    novo = rcad.atribuir("orfa-sp", {"consultor": "X" * 500}, base=base)
    assert len(novo.de("orfa-sp")["consultor"]) == 120


def test_gravacao_e_atomica(base: Path) -> None:
    """`os.replace` no lugar de escrita direta: nunca ha JSON pela metade em disco."""
    rcad.atribuir("orfa-sp", {"consultor": "JAILSON"}, base=base)
    assert not list(base.glob("*.tmp")), "arquivo temporario ficou para tras"
    json.loads((base / rcad.ARQUIVO_CADASTRO).read_text(encoding="utf-8"))


def test_valores_distintos_alimenta_o_filtro(base: Path) -> None:
    assert rcad.valores_distintos(rcad.ler_cadastro(base), "consultor") == ["MARISE"]
    rcad.atribuir("orfa-sp", {"consultor": "JAILSON"}, base=base)
    assert rcad.valores_distintos(rcad.ler_cadastro(base), "consultor") == ["JAILSON", "MARISE"]


def test_diretorio_default_fica_fora_do_motor_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum artefato do M1 pode ficar sob um mount de escrita."""
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/opt/motor-expansao/cadastro")
    assert rcad.cadastro_dir() == Path("/opt/motor-expansao/cadastro")
    monkeypatch.delenv("MOTOR_CADASTRO_DIR")
    assert "data" in rcad.cadastro_dir().parts and rcad.cadastro_dir().name == "cadastro"


def test_escritas_simultaneas_nao_perdem_edicao(base: Path) -> None:
    """Sem trava, os DOIS passam pela checagem de versao e um dos dois some do disco.

    Perda silenciosa e' o pior tipo: a tela do autor mostra sucesso e a atribuicao
    simplesmente nao esta la. Com a trava, o segundo recebe conflito e a tela recarrega.
    """
    import threading

    resultados: list[object] = []

    def gravar(unidade: str, valor: str) -> None:
        try:
            resultados.append(rcad.atribuir(unidade, {"consultor": valor}, versao_cliente=1, base=base))
        except rcad.ConflitoDeVersao as erro:
            resultados.append(erro)

    linhas = [
        threading.Thread(target=gravar, args=("botafogo-rj", "A")),
        threading.Thread(target=gravar, args=("orfa-sp", "B")),
    ]
    for linha in linhas:
        linha.start()
    for linha in linhas:
        linha.join()

    conflitos = [r for r in resultados if isinstance(r, rcad.ConflitoDeVersao)]
    assert len(conflitos) == 1, "exatamente um dos dois tem de receber conflito"
    final = rcad.ler_cadastro(base)
    assert final.versao == 2, "so' uma das duas gravacoes pode ter valido"
    assert not list(base.glob("*.tmp")), "temporario ficou para tras numa corrida"


def test_valor_nao_finito_no_cadastro_nao_derruba_a_leitura(base: Path) -> None:
    """A planilha e' mantida a mao: uma celula de GOLD/LTV vazia chega como NaN.

    `json.loads` aceita `NaN`; o `json.dumps(allow_nan=False)` do FastAPI, nao — e a ficha
    daquela unidade respondia 500 para todo mundo, sem pista de que o problema estava no
    cadastro.
    """
    import json

    caminho = base / rcad.ARQUIVO_CADASTRO
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["unidades"]["botafogo-rj"]["gold"] = float("nan")
    caminho.write_text(json.dumps(dados, allow_nan=True), encoding="utf-8")

    registro = rcad.ler_cadastro(base).de("botafogo-rj")
    assert registro["gold"] is None
    json.dumps(registro, allow_nan=False)


def test_gravacao_recusa_valor_nao_finito(base: Path) -> None:
    cadastro = rcad.ler_cadastro(base)
    quebrado = rcad.Cadastro(
        versao=cadastro.versao + 1,
        atualizado_em=None,
        unidades={"x": {"ltv": float("inf")}},
    )
    with pytest.raises(ValueError):
        rcad.gravar_cadastro(quebrado, base)
