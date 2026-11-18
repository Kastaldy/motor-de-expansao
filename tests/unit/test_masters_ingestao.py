"""Ingestão da planilha dos masters para o piloto (DEC-089): planilha e config SINTÉTICAS em
tmp_path; nenhum teste abre a planilha real, que é confidencial e fica fora do git."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from motor_expansao.masters.ingestao import (
    ARQ_CONTRATOS,
    ARQ_INAUGURADAS,
    ARQ_MANIFESTO,
    ARQ_PIPELINE,
    ESQUEMA,
    IngestaoRecusada,
    gravar,
    montar_tabelas,
    nome_do_master,
)

#: Como a planilha escreve o titular: o território na frente, o nome do master depois.
TITULAR = "DF — Fulano de Tal Ltda"


def _planilha(tmp_path: Path, *, sem_aba: str | None = None, master_extra: bool = False) -> Path:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    abas = {
        "Masters": [
            ("Masters — territórios e prazos", None, None, None, None),
            (
                "Master",
                "Titular / razão social",
                "Tipo de área",
                "Área (texto do levantamento)",
                "Vencimento do prazo",
            ),
            ("Alfa — Fulano", TITULAR, "Exclusividade", "Área: Distrito Federal", "11/03/2027"),
            ("Beta — Ciclano", "Ciclano SA", "Sem exclusividade", "Área: nacional", "—"),
        ],
        "Inauguradas": [
            ("Inauguradas por master", None, None, None, None),
            ("Master (seção)", "Unidade", "UF", "Meta de abertura", "Operação"),
            ("Alfa — Fulano", "Asa Norte", "df", "Alfa — Fulano", "Alfa — Fulano"),
            ("Alfa — Fulano", "Gama", "DF", "Holding operação", "Alfa — Fulano"),
            ("Beta — Ciclano", "Bertioga", "SP", "Beta — Ciclano", "Alfa — Fulano"),
        ],
        "Pipeline": [
            ("Master", "Unidade", "Cidade", "UF", "Fase", "Dentro do território do contrato?"),
            ("Alfa — Fulano", "Sudoeste", "Brasília", "DF", "Obras", "Sim"),
            ("Alfa — Fulano", "Guará", None, "DF", "sem status II", "Não"),
            ("Beta — Ciclano", "Jandira", None, "SP", "Pré Venda", None),
        ],
    }
    if master_extra:
        abas["Pipeline"].append(("Gama — Beltrano", "Lugar", None, "RJ", "Obras", "Sim"))
    for nome, linhas in abas.items():
        if nome == sem_aba:
            continue
        ws = wb.create_sheet(nome)
        for linha in linhas:
            ws.append(list(linha))
    caminho = tmp_path / "masters.xlsx"
    wb.save(caminho)
    return caminho


def _territorios(tmp_path: Path) -> Path:
    caminho = tmp_path / "territorios.json"
    caminho.write_text(
        json.dumps(
            {
                "versao": "2026-11-15",
                "masters": [
                    {
                        "id": "alfa",
                        "nome_planilha": "Alfa — Fulano",
                        "nome_exibicao": "Alfa",
                        "regioes": [
                            {
                                "id": "df",
                                "nome": "Distrito Federal",
                                "tipo": "exclusividade",
                                "ufs": ["DF"],
                            }
                        ],
                        "meta_aberturas": {
                            "quantidade": 5,
                            "prazo": "2027-03-11",
                            "conta_tambem": ["Santos"],
                        },
                    },
                    {
                        "id": "beta",
                        "nome_planilha": "Beta — Ciclano",
                        "nome_exibicao": "Beta",
                        "nota": "Sem território.",
                        "regioes": [],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return caminho


def test_ingestao_grava_so_o_que_a_tela_mostra(tmp_path: Path) -> None:
    tabelas = montar_tabelas(_planilha(tmp_path), _territorios(tmp_path))
    feitos = gravar(tabelas, tmp_path / "staging")
    assert [p.name for p in feitos] == [ARQ_CONTRATOS, ARQ_INAUGURADAS, ARQ_PIPELINE, ARQ_MANIFESTO]

    contratos = pd.read_parquet(tmp_path / "staging" / ARQ_CONTRATOS)
    assert list(contratos["master_id"]) == ["alfa", "beta"]
    alfa = contratos.iloc[0]
    # O nome do master (18/11/2026, Juan: não o do estado): o titular sem o território.
    assert alfa["nome"] == "Fulano de Tal Ltda"
    assert alfa["territorio"] == "Alfa"
    assert contratos.iloc[1]["nome"] == "Ciclano SA"  # sem travessão, o texto inteiro
    assert alfa["tipo_area"] == "Exclusividade"
    assert list(alfa["regioes"]) == ["Distrito Federal"]
    assert list(alfa["regioes_tipos"]) == ["Exclusividade"]
    assert int(alfa["meta_quantidade"]) == 5 and alfa["meta_prazo"] == "2027-03-11"
    assert list(alfa["conta_tambem"]) == ["Santos"]
    assert contratos.iloc[1]["tipo_area"] == "Sem exclusividade"

    inaug = pd.read_parquet(tmp_path / "staging" / ARQ_INAUGURADAS)
    assert list(inaug["master_id"]) == ["alfa", "alfa", "beta"]
    assert list(inaug["uf"]) == ["DF", "DF", "SP"]
    # Meta atribuída a quem não é master da config ("Holding…") vira vazio, sem o texto cru.
    assert inaug.loc[1, "meta_master_id"] is None
    # Bertioga: meta do Beta, operação do Alfa.
    assert (inaug.loc[2, "meta_master_id"], inaug.loc[2, "operacao_master_id"]) == ("beta", "alfa")

    pipe = pd.read_parquet(tmp_path / "staging" / ARQ_PIPELINE)
    assert list(pipe["fase"]) == ["Obras", "sem status", "Pré Venda"]
    assert list(pipe["dentro_territorio"]) == [True, False, None]
    assert pipe.loc[0, "cidade"] == "Brasília" and pipe.loc[1, "cidade"] is None

    manifesto = json.loads((tmp_path / "staging" / ARQ_MANIFESTO).read_text(encoding="utf-8"))
    assert manifesto["esquema"] == ESQUEMA
    assert manifesto["contagens"] == {"masters": 2, "inauguradas": 3, "pipeline": 3}
    assert manifesto["planilha"]["arquivo"] == "masters.xlsx"
    assert len(manifesto["planilha"]["sha256"]) == 64
    assert manifesto["territorios"]["versao"] == "2026-11-15"


def test_so_o_que_a_tela_mostra_sai_da_planilha(tmp_path: Path) -> None:
    """O texto livre da área, a atribuição de meta fora da config ("Holding…") e o master como a
    planilha o escreve na coluna "Master" não chegam a nenhum arquivo gravado; o nome do master
    vai sem o território."""
    tabelas = montar_tabelas(_planilha(tmp_path), _territorios(tmp_path))
    gravar(tabelas, tmp_path / "staging")
    texto = ""
    for nome in (ARQ_CONTRATOS, ARQ_INAUGURADAS, ARQ_PIPELINE):
        df = pd.read_parquet(tmp_path / "staging" / nome)
        texto += df.astype(str).to_string()
    texto += (tmp_path / "staging" / ARQ_MANIFESTO).read_text(encoding="utf-8")
    for proibido in (TITULAR, "Alfa — Fulano", "Beta — Ciclano", "Holding", "Área:"):
        assert proibido not in texto


def test_nome_do_master() -> None:
    assert nome_do_master("DF/GO — Fulano de Tal") == "Fulano de Tal"
    assert nome_do_master("ES — Beltrano Souza / Exemplo Master Ltda") == (
        "Beltrano Souza / Exemplo Master Ltda"
    )
    assert nome_do_master("Ginseng") == "Ginseng"
    assert nome_do_master("  ") is None and nome_do_master(None) is None


def test_aba_faltando_recusa_sem_gravar(tmp_path: Path) -> None:
    with pytest.raises(IngestaoRecusada, match="Pipeline"):
        montar_tabelas(_planilha(tmp_path, sem_aba="Pipeline"), _territorios(tmp_path))
    with pytest.raises(IngestaoRecusada, match="Masters"):
        montar_tabelas(_planilha(tmp_path, sem_aba="Masters"), _territorios(tmp_path))
    assert not (tmp_path / "staging").exists()


def test_master_fora_da_config_recusa(tmp_path: Path) -> None:
    with pytest.raises(IngestaoRecusada, match="fora do territorios.json"):
        montar_tabelas(_planilha(tmp_path, master_extra=True), _territorios(tmp_path))
