"""Pico de maturação padrão por estado (emenda de 2026-10-29 da DEC-078).

Três coisas são travadas aqui:
- a RÉGUA (a do UNI-03): quem entra, o nível maduro, a regra do pico — com uma rede sintética de
  forma conhecida, em que o pico de cada unidade é decidido na construção;
- a DECISÃO de 29/10/2026: corte de 5 unidades maduras, peso n/(n+10) sobre a diferença para a
  rede, 10 do motor fixo, freio de 1 mês por atualização — e os números que ela dá com a medição
  de 28/10 (SP 11, MG 9, DF 10, RJ 10), que foram os mostrados ao Vinicius;
- a PUBLICAÇÃO e a LEITURA: portão reprovado não publica, a escrita é atômica, a leitura relê
  quando o arquivo muda e cai nos 10 do motor sem artefato.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dimensionamento import pico_por_uf as p
from motor_expansao.dimensionamento.config import SIM_MES_PICO_RAMPA_PADRAO

CORTE = "2026-09"


def _fechamento(spec: list[tuple[str, str, str, int]], corte: str = CORTE) -> pd.DataFrame:
    """Fechamento mensal sintético. `spec` = (unidade, uf, inauguração, pico).

    Cada unidade abre com 60% da demanda madura e sobe em linha reta até 100% no mês `pico`,
    plana depois: o pico medido tem de ser exatamente o da construção. Todo mês é completo
    (30 dias com dado, último dia no fim do mês) e não há época do ano.
    """
    linhas = []
    fim = pd.Period(corte, "M")
    for uid, uf, inaug, pico in spec:
        ina = pd.Timestamp(inaug)
        k0 = ina.to_period("M")
        mes = k0
        while mes <= fim:
            k = (mes - k0).n
            frac = 0.6 if k == 0 else min(1.0, 0.6 + 0.4 * k / pico)
            linhas.append(
                {
                    "unidade_id": uid,
                    "competencia": mes,
                    "inauguracao": ina.strftime("%Y-%m-%d"),
                    "dias_com_dado": 30,
                    "dia_ref": mes.to_timestamp(how="end").normalize(),
                    "ativos": 2000.0 * frac,
                    "uf": uf,
                }
            )
            mes += 1
    return pd.DataFrame(linhas)


def _rede() -> list[tuple[str, str, str, int]]:
    """16 unidades rápidas (pico 8) em CC, 6 lentas (pico 12) em AA e 4 lentas em BB, todas
    elegíveis e maduras; mais as que têm de ficar FORA da conta."""
    spec = [(f"cc-{i}", "CC", f"2023-{(i % 12) + 1:02d}-10", 8) for i in range(16)]
    spec += [(f"aa-{i}", "AA", f"2024-{(i % 6) + 1:02d}-10", 12) for i in range(6)]
    spec += [(f"bb-{i}", "BB", f"2024-{(i % 4) + 7:02d}-10", 12) for i in range(4)]
    spec += [
        ("provisoria", "AA", "2021-08-23", 3),  # data provisória do cadastro
        ("antiga", "AA", "2021-12-01", 3),  # abriu antes de abr/2022: sem a subida no dado
        ("jovem", "AA", "2025-12-01", 3),  # ainda sem os meses 11 a 13
    ]
    return spec


# ------------------------------------------------------------------------------- a régua


def test_a_regua_le_o_pico_que_a_rede_sintetica_tem() -> None:
    m = p.medir(_fechamento(_rede()))
    assert m.n_grupo == 26, "entram as 26 maduras; provisória, antiga e jovem ficam fora"
    assert m.pico_rede == 8, "a maioria (16 de 26) amadurece no mês 8"
    assert m.por_uf == {"AA": (6, 12), "BB": (4, 12), "CC": (16, 8)}
    assert m.competencia_corte == CORTE


def test_o_portao_mede_so_o_grupo_da_exploracao() -> None:
    """Grupo da exploração = primeiro ano fechado até dez/2025 (inauguração até nov/2024)."""
    m = p.medir(_fechamento(_rede()))
    assert m.n_exploracao == 26  # todas as maduras da rede sintética abriram até nov/2024
    assert m.pico_exploracao == 8


def test_nivel_maduro_exige_dois_dos_meses_11_a_13() -> None:
    """Com o corte em out/2025, quem abriu em out/2024 tem só o mês 12 e o 11: entra; quem abriu
    em nov/2024 tem só o 11: fica fora."""
    spec = [("um", "AA", "2024-10-10", 8), ("dois", "AA", "2024-11-10", 8)]
    m = p.medir(_fechamento(spec, corte="2025-10"))
    assert m.n_grupo == 1


def test_regra_do_pico() -> None:
    assert p.pico_da_curva([0.8, 0.9, 0.995, 1.0]) == 2  # 99,5% arredonda a 100%
    assert p.pico_da_curva([1.0, 0.9, 0.98, 1.01]) == 3  # o mês 0 não conta
    assert p.pico_da_curva([0.5] * 13) == 13  # não chegou no 1º ano


# ------------------------------------------------------------------------------- a decisão


def test_a_decisao_de_29_10_com_a_medicao_de_28_10() -> None:
    """Os números mostrados ao Vinicius: rede 8; DF 19 un./8, SP 17/10, MG 5/6, RJ 5/7, GO 4/6.
    Com o corte de 5 e o peso n/(n+10): SP 11, MG 9, DF e RJ 10, e GO fora."""
    medicao = p.Medicao(
        n_exploracao=33,
        pico_exploracao=10,
        n_grupo=60,
        pico_rede=8,
        por_uf={"DF": (19, 8), "SP": (17, 10), "MG": (5, 6), "RJ": (5, 7), "GO": (4, 6)},
        competencia_corte="2026-09",
        fator_epoca=(1.0,) * 12,
    )
    assert p.alvos(medicao) == {"DF": 10, "SP": 11, "MG": 9, "RJ": 10}


def test_o_corte_de_5_e_o_peso_na_rede_sintetica() -> None:
    """AA (6 unidades, +4 meses sobre a rede): peso 6/16 = 0,375 -> +1,5 -> +2 -> 12. BB, com 4,
    fica fora do corte. CC empata com a rede -> 10."""
    alvo = p.alvos(p.medir(_fechamento(_rede())))
    assert alvo == {"AA": 12, "CC": 10}


def test_peso_e_arredondamento() -> None:
    assert p.peso(5) == pytest.approx(1 / 3)
    assert p.peso(10) == pytest.approx(0.5)
    assert [p._arredondar(x) for x in (0.5, -0.5, 1.26, -0.67, -0.4, 0.4)] == [1, -1, 1, -1, 0, 0]


def test_o_10_do_motor_nao_se_move() -> None:
    """A emenda NÃO mexe no padrão nacional: ele segue a curva do UNI-03."""
    assert SIM_MES_PICO_RAMPA_PADRAO == 10
    assert p.alvos(p.Medicao(33, 10, 60, 8, {"XX": (40, 8)}, CORTE, (1.0,) * 12)) == {"XX": 10}


def test_freio_de_um_mes_por_atualizacao() -> None:
    assert p.aplicar_freio({"SP": 12}, {}) == {"SP": 11}  # parte dos 10
    assert p.aplicar_freio({"SP": 12}, {"SP": 11}) == {"SP": 12}
    assert p.aplicar_freio({"MG": 7}, {"MG": 9}) == {"MG": 8}
    assert p.aplicar_freio({}, {"SP": 12}) == {"SP": 11}  # saiu do corte: volta aos poucos
    assert p.aplicar_freio({}, {"SP": 11}) == {}  # chegou aos 10: some
    assert p.aplicar_freio({"DF": 10}, {}) == {"DF": 10}  # do corte, mesmo nos 10


# ------------------------------------------------------------------------------- publicação


def _medicao(pico_exploracao: int = 10, sp: int = 12) -> p.Medicao:
    return p.Medicao(
        33, pico_exploracao, 60, 8, {"SP": (17, sp), "DF": (19, 8)}, CORTE, (1.0,) * 12
    )


def test_portao_reprovado_nao_publica_e_mantem_o_anterior(tmp_path: Path, monkeypatch) -> None:
    saida = tmp_path / p.ARQUIVO
    saida.write_text('{"anterior": true}', encoding="utf-8")
    monkeypatch.setattr(p, "fechamento_da_growth", lambda _g: None)
    monkeypatch.setattr(p, "medir", lambda _f: _medicao(pico_exploracao=9))
    codigo, artefato, _m = p.rodar(tmp_path / "growth.parquet", saida)
    assert codigo == 2 and artefato is None
    assert saida.read_text(encoding="utf-8") == '{"anterior": true}'


def test_publicacao_parte_do_publicado_antes(tmp_path: Path, monkeypatch) -> None:
    """SP pede 13 (diferença +5, peso 17/27 -> +3): com 11 publicado antes, sai 12."""
    saida = tmp_path / p.ARQUIVO
    monkeypatch.setattr(p, "fechamento_da_growth", lambda _g: None)
    monkeypatch.setattr(p, "medir", lambda _f: _medicao(sp=13))
    p.gravar_atomico(
        saida, p.montar_artefato(_medicao(), {"SP": 11}, {"SP": 11}, hoje=date(2026, 10, 2))
    )
    codigo, artefato, _m = p.rodar(tmp_path / "growth.parquet", saida, hoje=date(2026, 11, 2))
    assert codigo == 0
    assert artefato["estados"]["SP"]["alvo"] == 13
    assert artefato["estados"]["SP"]["publicado"] == 12
    assert json.loads(saida.read_text(encoding="utf-8"))["estados"]["SP"]["publicado"] == 12


def test_modo_seco_nao_grava(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(p, "fechamento_da_growth", lambda _g: None)
    monkeypatch.setattr(p, "medir", lambda _f: _medicao())
    codigo, artefato, _m = p.rodar(
        tmp_path / "growth.parquet", tmp_path / p.ARQUIVO, publicar=False
    )
    assert codigo == 0 and artefato is not None
    assert not (tmp_path / p.ARQUIVO).exists()


def test_gravacao_atomica_nao_deixa_temporario(tmp_path: Path) -> None:
    saida = tmp_path / p.ARQUIVO
    p.gravar_atomico(saida, p.montar_artefato(_medicao(), {"SP": 11}, {"SP": 11}))
    assert json.loads(saida.read_text(encoding="utf-8"))["esquema"] == p.ESQUEMA
    assert sorted(x.name for x in tmp_path.iterdir()) == [p.ARQUIVO]


# ------------------------------------------------------------------------------- leitura


@pytest.fixture(autouse=True)
def _cache_limpo():
    p.limpar_cache()
    yield
    p.limpar_cache()


def _publicar(staging: Path, publicado: dict[str, int], alvo: dict[str, int]) -> None:
    p.gravar_atomico(staging / p.ARQUIVO, p.montar_artefato(_medicao(), publicado, alvo))


def test_sem_artefato_volta_aos_10_do_motor(tmp_path: Path) -> None:
    pp = p.pico_padrao("SP", tmp_path)
    assert (pp.meses, pp.origem) == (10, p.ORIGEM_PADRAO)


def test_estado_com_padrao_proprio(tmp_path: Path) -> None:
    _publicar(tmp_path, {"SP": 11, "DF": 10}, {"SP": 12, "DF": 10})
    sp = p.pico_padrao("sp", tmp_path)
    assert (sp.meses, sp.origem, sp.uf, sp.unidades_maduras, sp.competencia_corte) == (
        11,
        p.ORIGEM_ESTADO,
        "SP",
        17,
        CORTE,
    )
    df = p.pico_padrao("DF", tmp_path)
    assert (df.meses, df.origem) == (10, p.ORIGEM_ESTADO)  # mediu e deu 10: segue do estado


def test_estado_fora_do_corte_fica_na_rede(tmp_path: Path) -> None:
    _publicar(tmp_path, {"SP": 11}, {"SP": 11})
    go = p.pico_padrao("GO", tmp_path)
    assert (go.meses, go.origem, go.unidades_maduras) == (10, p.ORIGEM_REDE, 0)
    sem_uf = p.pico_padrao(None, tmp_path)
    assert (sem_uf.meses, sem_uf.origem) == (10, p.ORIGEM_REDE)


def test_a_leitura_rele_quando_o_arquivo_muda(tmp_path: Path) -> None:
    """Publicar não exige restart do site nem da API: a leitura confere o mtime."""
    _publicar(tmp_path, {"SP": 11}, {"SP": 11})
    assert p.pico_padrao("SP", tmp_path).meses == 11
    _publicar(tmp_path, {"SP": 12}, {"SP": 12})
    arquivo = tmp_path / p.ARQUIVO
    st = arquivo.stat()
    os.utime(arquivo, (st.st_atime, st.st_mtime + 5))
    assert p.pico_padrao("SP", tmp_path).meses == 12


def test_artefato_ilegivel_ou_de_outro_esquema_e_ignorado(tmp_path: Path) -> None:
    (tmp_path / p.ARQUIVO).write_text('{"esquema": "outro"}', encoding="utf-8")
    assert p.pico_padrao("SP", tmp_path).origem == p.ORIGEM_PADRAO
    p.limpar_cache()
    (tmp_path / p.ARQUIVO).write_text("{nao e json", encoding="utf-8")
    assert p.pico_padrao("SP", tmp_path).origem == p.ORIGEM_PADRAO


def test_valor_publicado_fora_do_intervalo_e_contido(tmp_path: Path) -> None:
    artefato = p.montar_artefato(_medicao(), {"SP": 99}, {"SP": 99})
    (tmp_path / p.ARQUIVO).write_text(json.dumps(artefato), encoding="utf-8")
    assert p.pico_padrao("SP", tmp_path).meses == 36


# ------------------------------------------------------------------------------- operação


def test_o_artefato_guarda_de_onde_cada_numero_partiu() -> None:
    """O freio só é auditável se o arquivo disser o valor de antes de cada estado."""
    artefato = p.montar_artefato(
        _medicao(sp=13), {"SP": 12, "DF": 10}, {"SP": 13, "DF": 10}, anterior={"SP": 11}
    )
    assert artefato["estados"]["SP"]["anterior"] == 11
    assert artefato["estados"]["DF"]["anterior"] == 10  # sem publicação anterior: os 10


@pytest.mark.skipif(os.name == "nt", reason="permissão POSIX: o job roda no Linux da VPS")
def test_o_arquivo_publicado_e_legivel_por_outro_usuario(tmp_path: Path) -> None:
    """`mkstemp` cria 0600 e o job grava como root: sem o chmod, o site e a API não leriam."""
    saida = tmp_path / p.ARQUIVO
    p.gravar_atomico(saida, p.montar_artefato(_medicao(), {"SP": 11}, {"SP": 11}))
    assert saida.stat().st_mode & 0o044 == 0o044


def test_o_resumo_diz_o_que_mudou() -> None:
    artefato = p.montar_artefato(
        _medicao(sp=13), {"SP": 12, "DF": 10}, {"SP": 13, "DF": 10}, anterior={"SP": 11, "DF": 10}
    )
    texto = p.resumo(artefato, _medicao(sp=13))
    assert "SP: 12 meses (antes 11; 17 unidades maduras; a conta pede 13)" in texto
    assert "DF: 10 meses (sem mudança; 19 unidades maduras; a conta pede 10)" in texto
    assert "Os demais estados seguem nos 10 meses da rede." in texto


def test_o_resumo_do_portao_reprovado_diz_que_nada_foi_publicado() -> None:
    texto = p.resumo(None, _medicao(pico_exploracao=9))
    assert "NADA PUBLICADO" in texto


def test_falha_manda_a_etapa_ao_chat_de_ops(monkeypatch) -> None:
    enviados: list[tuple[str, bool]] = []
    monkeypatch.setattr(p, "_enviar", lambda texto, stdout: enviados.append((texto, stdout)))
    assert p.main(["--falha", "job do pico por estado (rc=1)"]) == 0
    assert len(enviados) == 1 and enviados[0][1] is False
    assert "falhou em: job do pico por estado (rc=1)" in enviados[0][0]
    assert "Nada foi publicado" in enviados[0][0]


def test_avisar_no_modo_seco_imprime_em_vez_de_mandar(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "growth_api_historico.parquet").write_bytes(b"")
    enviados: list[tuple[str, bool]] = []
    monkeypatch.setattr(p, "_enviar", lambda texto, stdout: enviados.append((texto, stdout)))
    monkeypatch.setattr(p, "fechamento_da_growth", lambda _g: None)
    monkeypatch.setattr(p, "medir", lambda _f: _medicao())
    assert p.main(["--staging", str(tmp_path), "--seco", "--avisar"]) == 0
    assert len(enviados) == 1 and enviados[0][1] is True
    assert not (tmp_path / p.ARQUIVO).exists()
