"""Nucleo semantico da rede Ultra (BLK-EXEC-01/01b).

Trava, com dado sintetico, cada armadilha que a Visao Executiva v1 caiu ou quase caiu:
cumulativa lida como snapshot, sentinela de NPS entrando na media, serie partida pela
correcao de encoding, `max` no lugar de `last` e volta do laco Python por unidade.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.dashboard import rede_coorte, rede_diagnostico
from motor_expansao.dashboard import rede_metricas as rm
from tests.unit.rede_fixtures import base, mes, unidade_saudavel

# ---------------------------------------------------------------------------
# Identidade
# ---------------------------------------------------------------------------


def _identidade(df: pd.DataFrame) -> dict[str, rm.Unidade]:
    return rm.catalogo_de(rm.preparar_base(df))


def test_identidade_funde_serie_partida_por_encoding() -> None:
    """Datas DISJUNTAS + mesma inauguracao = a MESMA unidade.

    Reproduz o caso real: a ingestao passou a gravar UTF-8 correto em 20/02/2026 e partiu
    a serie da Patio Brasil em dois nomes crus. Sem fundir, a ficha mostraria 5 meses de
    historico em vez de 11.
    """
    df = base(
        mes("PATIO BRASIL - DF", 2026, 1, uf="DF", inauguracao="15/09/2025"),
        mes("PATIO BRASIL - DF", 2026, 3, uf="DF", inauguracao="15/09/2025"),
    )
    df.loc[df["data"].str.endswith("/01/2026"), "unidade"] = "PÁTIO BRASIL - DF"

    catalogo = _identidade(df)
    assert len(catalogo) == 1, "duas grafias da mesma unidade deveriam virar uma so"
    unidade = next(iter(catalogo.values()))
    assert set(unidade.nomes_crus) == {"PÁTIO BRASIL - DF", "PATIO BRASIL - DF"}
    assert unidade.nome == "PATIO BRASIL", "o nome de exibicao sai do registro mais recente"


def test_identidade_nao_funde_unidades_distintas() -> None:
    """Datas SOBREPOSTAS ou inauguracao diferente = unidades diferentes.

    As duas "Aguas Claras" existem de verdade: uma e' academia (DF/GO, 2023) e a outra e'
    um studio (ULTRA, 2024). Fundi-las por nome normalizado somaria as duas operacoes.
    """
    df = base(
        mes("AGUAS CLARAS", 2026, 5, uf="DF", master="DF/GO", inauguracao="20/03/2023"),
        mes("AGUAS CLARAS - DF", 2026, 5, uf="DF", master="ULTRA", inauguracao="19/10/2024"),
    )
    catalogo = rm.catalogo_de(rm.preparar_base(df))
    assert len(rm.resolver_identidade(df.assign(_data=pd.to_datetime(df["data"], format="%d/%m/%Y")))[1]) == 2
    # ...e a que sobra na rede comparavel e' a ACADEMIA, nunca o studio.
    assert list(catalogo) == ["aguas-claras-df"]
    assert catalogo["aguas-claras-df"].nomes_crus == ("AGUAS CLARAS",)


def test_exclusao_casa_por_nome_cru_e_poupa_a_academia() -> None:
    """A v1 excluia por chave normalizada e derrubava uma academia real em producao."""
    assert rm.eh_excluida("AGUAS CLARAS - DF") is True
    assert rm.eh_excluida("AGUAS CLARAS") is False
    assert rm.eh_excluida("Chacara Sto Antonio - SP") is True
    assert rm.eh_excluida("BOTAFOGO - RJ") is False


@pytest.mark.parametrize(
    "nome, esperado",
    [
        ("NATAL - RN", "NATAL"),
        ("Bangu / RJ", "BANGU"),
        ("Icarai RJ", "ICARAI"),
        ("VISCONDE DE RIO CLARO", "VISCONDE DE RIO CLARO"),
        ("AMERICANA CENTRO", "AMERICANA CENTRO"),
        ("CEILANDIA QNN32 - DF ", "CEILANDIA QNN32"),
    ],
)
def test_chave_unidade_nao_come_letras_sem_separador(nome: str, esperado: str) -> None:
    """O separador antes da UF e' OBRIGATORIO: sem ele "NATAL" viraria "NAT"."""
    assert rm.chave_unidade(nome) == esperado


# ---------------------------------------------------------------------------
# Fechamento mensal
# ---------------------------------------------------------------------------


def test_fechamento_usa_last_nao_max() -> None:
    """`cancelados` CAI dentro do mes (estorno): `max` congelaria o pico."""
    df = base(
        unidade_saudavel("X", 2026, 5, trajetoria={"cancelados": [10, 40, 40, 25]}, dias=4)
    )
    fech = rm.fechamento_mensal(rm.preparar_base(df))
    assert float(fech.iloc[0]["cancelados"]) == 25.0


def test_fechamento_marca_mes_incompleto() -> None:
    df = base(unidade_saudavel("X", 2026, 5, dias=12))
    fech = rm.fechamento_mensal(rm.preparar_base(df))
    assert bool(fech.iloc[0]["mes_completo"]) is False
    assert int(fech.iloc[0]["dias_com_dado"]) == 12


def test_unidade_inaugurada_no_mes_nao_e_comparavel() -> None:
    """Gate que substitui o piso de R$ 20 mil da v1 (literal financeiro nao nomeado)."""
    df = base(
        unidade_saudavel("NOVA", 2026, 5, inauguracao="20/05/2026"),
        unidade_saudavel("VELHA", 2026, 5, inauguracao="01/01/2020"),
    )
    fech = rm.fechamento_mensal(rm.preparar_base(df)).set_index("unidade_cru")
    assert bool(fech.loc["NOVA", "operacao_mes_cheio"]) is False
    assert bool(fech.loc["VELHA", "operacao_mes_cheio"]) is True


def test_inauguracao_sentinela_vira_maturidade_indefinida() -> None:
    """Epoch (31/12/1969) ja apareceu na base e produzia 677 meses de operacao."""
    df = base(unidade_saudavel("X", 2026, 5, inauguracao="31/12/1969"))
    fech = rm.fechamento_mensal(rm.preparar_base(df))
    assert pd.isna(fech.iloc[0]["inauguracao"])
    assert pd.isna(fech.iloc[0]["meses_operacao"])


def test_saldo_operacional_usa_vendas_nao_novos_alunos() -> None:
    """`SALDO_OPERACIONAL = [VENDAS_DIA] - [CANCELADOS_DIA]` (DAX oficial).

    Com `novos_alunos` a unidade abaixo ficaria negativa; com `vendas`, positiva. Na base
    real, 23 unidades TROCAM DE SINAL entre as duas definicoes.
    """
    df = base(
        unidade_saudavel(
            "X", 2026, 5, cumulativas={"vendas": 120.0, "novos_alunos": 60.0, "cancelados": 80.0}
        )
    )
    linha = rm.fechamento_mensal(rm.preparar_base(df)).iloc[0]
    assert float(linha["saldo_operacional"]) == 40.0


def test_churn_usa_recorrentes_do_mes_anterior() -> None:
    """`CHURN_DIA = [CANCELADOS_DIA] / [REC_MES_ANTERIOR]` (DAX oficial)."""
    df = base(
        unidade_saudavel("X", 2026, 4, snapshots={"pagantes": 1_000.0}),
        unidade_saudavel(
            "X", 2026, 5, snapshots={"pagantes": 500.0}, cumulativas={"cancelados": 50.0}
        ),
    )
    fech = rm.fechamento_mensal(rm.preparar_base(df)).set_index("competencia")
    # 50 cancelados sobre os 1.000 do mes ANTERIOR = 5%, nao 10% sobre os 500 do proprio.
    assert float(fech.loc["2026-05", "churn_pct"]) == pytest.approx(5.0)
    assert pd.isna(fech.loc["2026-04", "churn_pct"]), "primeiro mes da serie nao tem base"


# ---------------------------------------------------------------------------
# NPS
# ---------------------------------------------------------------------------


def test_nps_999_vira_nulo() -> None:
    """999 e' sentinela de "sem pesquisa no periodo" (5,63% das linhas, 56 unidades)."""
    df = base(unidade_saudavel("X", 2026, 5, snapshots={"NPS": 999.0}))
    linha = rm.fechamento_mensal(rm.preparar_base(df)).iloc[0]
    assert pd.isna(linha["nps"])
    assert bool(linha["nps_valido"]) is False


def test_nps_negativo_e_preservado() -> None:
    """Trava contra o "conserto" errado: filtrar `v > 0` descartaria NPS legitimo.

    A base tem 3.183 linhas com NPS negativo (minimo -100). Sao unidades com problema
    real, exatamente as que o time de campo precisa ver.
    """
    df = base(unidade_saudavel("X", 2026, 5, snapshots={"NPS": -40.0}))
    linha = rm.fechamento_mensal(rm.preparar_base(df)).iloc[0]
    assert float(linha["nps"]) == -40.0
    assert bool(linha["nps_valido"]) is True


# ---------------------------------------------------------------------------
# Receita por recorrente (o conserto do "ticket medio")
# ---------------------------------------------------------------------------


def test_receita_por_recorrente_usa_rolling30_e_nao_o_mtd_parcial() -> None:
    """Regressao do R$ 20,28 vs R$ 163,67 exibido em producao.

    No dia 2 do mes, o acumulado do mes vale 2 dias. A janela de 30 dias reconstroi o mes
    inteiro com a cauda do mes anterior e devolve a ordem de grandeza certa.
    """
    df = rm.preparar_base(
        base(
            unidade_saudavel(
                "X", 2026, 4, cumulativas={"faturamento_sem_agregador": 150_000.0}
            ),
            unidade_saudavel(
                "X", 2026, 5, cumulativas={"faturamento_sem_agregador": 150_000.0}
            ),
        )
    )
    cheio = rm.fechamento_mensal(df)
    corte = rm.fechamento_mensal(df, dia_corte=2)

    mtd_parcial = float(corte[corte["competencia"] == "2026-05"].iloc[0]["receita_por_recorrente"])
    rolling = float(rm.receita_por_recorrente_30d(corte, cheio, "2026-05").iloc[0])
    fechado_m1 = float(cheio[cheio["competencia"] == "2026-04"].iloc[0]["receita_por_recorrente"])

    assert mtd_parcial < 20.0, "o MTD de 2 dias e' o numero errado que a v1 exibia"
    assert rolling == pytest.approx(fechado_m1, rel=0.05), (
        "a janela de 30 dias tem de concordar com o mes fechado anterior"
    )


def test_ticket_medio_da_api_nao_e_usado() -> None:
    """Trava o conserto ERRADO. `ticket_medio` da API e' outra grandeza.

    Medido: 26,5% de zeros no dia 1, correlacao de 0,313 com o ticket real e nenhuma de 6
    formulas candidatas explica mais que 11% dos seus valores. O `TICKET_MEDIO` do PowerBI
    tambem nao serve: vem de `FT_RELATORIO_VENDAS[VALOR_REAL]`, que a API nao expoe.
    """
    fonte = (rm.__file__,)
    codigo = "".join(open(caminho, encoding="utf-8").read() for caminho in fonte)
    assert '"ticket_medio"' not in codigo and "'ticket_medio'" not in codigo
    assert "ticket_medio" not in rm.COLUNAS_CUMULATIVAS + rm.COLUNAS_SNAPSHOT
    assert "ticket_medio_pagantes" not in rm.COLUNAS_CUMULATIVAS + rm.COLUNAS_SNAPSHOT


def test_receita_por_recorrente_nao_se_chama_ticket() -> None:
    """O rotulo importa: o time compara com o PowerBI e concluiria que um dos dois erra."""
    rotulos = {e.rotulo.lower() for e in rm.METRICAS}
    assert not any("ticket" in r for r in rotulos)
    assert "receita por recorrente" in rotulos


# ---------------------------------------------------------------------------
# Contexto comparativo (o quarteto do time de campo)
# ---------------------------------------------------------------------------


def test_ranking_de_churn_e_pela_taxa_e_ao_contrario() -> None:
    """Regra do time: churn ranqueia pela TAXA e ASCENDENTE (1 = menor churn)."""
    df = rm.preparar_base(
        base(
            unidade_saudavel("A", 2026, 4, snapshots={"pagantes": 1_000.0}),
            unidade_saudavel("B", 2026, 4, snapshots={"pagantes": 1_000.0}),
            unidade_saudavel(
                "A", 2026, 5, snapshots={"pagantes": 1_000.0}, cumulativas={"cancelados": 20.0}
            ),
            unidade_saudavel(
                "B", 2026, 5, snapshots={"pagantes": 1_000.0}, cumulativas={"cancelados": 90.0}
            ),
        )
    )
    fech = rm.fechamento_mensal(df)
    ctx = rm.contexto_comparativo(fech[fech["competencia"] == "2026-05"]).set_index("unidade_cru")
    assert float(ctx.loc["A", "rank_churn_pct"]) == 1.0
    assert float(ctx.loc["B", "rank_churn_pct"]) == 2.0
    # ...e faturamento, que ranqueia ao contrario, empata entre as duas.
    assert float(ctx.loc["A", "rank_faturamento"]) == 1.0
    assert float(ctx.loc["B", "rank_faturamento"]) == 1.0, "empate = mesma posicao (RANK.EQ)"


def test_ranking_ignora_quem_nao_operou_o_mes_inteiro() -> None:
    """Uma unidade inaugurada no dia 20 nao recebe "3o de 3" -- recebe posicao nula."""
    df = rm.preparar_base(
        base(
            unidade_saudavel("VELHA A", 2026, 5),
            unidade_saudavel("VELHA B", 2026, 5),
            unidade_saudavel("NOVA", 2026, 5, inauguracao="20/05/2026"),
        )
    )
    ctx = rm.contexto_comparativo(rm.fechamento_mensal(df)).set_index("unidade_cru")
    assert pd.isna(ctx.loc["NOVA", "rank_faturamento"])
    assert pd.isna(ctx.loc["NOVA", "vs_media_faturamento"])
    assert int(ctx.loc["VELHA A", "rank_total_faturamento"]) == 2


def test_vs_media_da_rede_e_percentual() -> None:
    df = rm.preparar_base(
        base(
            unidade_saudavel("A", 2026, 5, cumulativas={"faturamento": 100_000.0}),
            unidade_saudavel("B", 2026, 5, cumulativas={"faturamento": 300_000.0}),
        )
    )
    ctx = rm.contexto_comparativo(rm.fechamento_mensal(df)).set_index("unidade_cru")
    assert float(ctx.loc["A", "vs_media_faturamento"]) == pytest.approx(-50.0)
    assert float(ctx.loc["B", "vs_media_faturamento"]) == pytest.approx(50.0)


def test_serie_diaria_desacumula_e_reseta_no_dia_1() -> None:
    """O bloco "Novos alunos diario" que o time cola a mao, 31 colunas por vez."""
    df = rm.preparar_base(
        base(
            mes("X", 2026, 4, dias=3, cumulativas={"novos_alunos": 30.0}),
            mes("X", 2026, 5, dias=3, cumulativas={"novos_alunos": 60.0}),
        )
    )
    serie = rm.serie_diaria(df, df["unidade_id"].iloc[0], "novos_alunos")
    assert list(serie["valor"]) == pytest.approx([10, 10, 10, 20, 20, 20])


# ---------------------------------------------------------------------------
# Degradacao e desempenho
# ---------------------------------------------------------------------------


def test_sem_base_nao_quebra() -> None:
    vazio = pd.DataFrame()
    assert not len(rm.preparar_base(vazio))
    assert not len(rm.fechamento_mensal(vazio))
    assert rm.catalogo_de(vazio) == {}
    assert not len(rm.contexto_comparativo(rm.fechamento_mensal(vazio)))


def test_parquet_ausente_devolve_vazio(tmp_path) -> None:
    assert not len(rm.carregar_base(tmp_path / "nao_existe.parquet"))


#: Espelha `_ESCRITORES_ARTEFATO | _FS_DESTRUTIVO` de `test_piloto_web_endpoints.py`.
_PROIBIDOS_READ_ONLY = {
    "to_parquet", "to_csv", "to_feather", "to_excel", "to_hdf", "to_pickle", "to_sql",
    "to_stata", "to_orc", "rmtree", "rmdir", "unlink", "remove",
}


def test_modulos_de_rede_sao_read_only_por_ast() -> None:
    """Mover logica para `src/` nao pode ser mover logica para FORA do guardrail.

    O AST read-only do piloto parseia so `web/server/app.py`. Como o calculo da Visao
    Executiva 2.0 nasce em `src/motor_expansao/dashboard/rede_*`, a mesma analise se
    aplica aqui. `rede_cadastro` fica de FORA de proposito: e' o unico modulo que escreve,
    num diretorio proprio, e tem provas dedicadas em `test_rede_cadastro.py`.
    """
    ofensas: list[tuple[str, str, int]] = []
    for modulo in (rm, rede_diagnostico, rede_coorte):
        arvore = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
                if no.func.attr in _PROIBIDOS_READ_ONLY:
                    ofensas.append((Path(modulo.__file__).name, no.func.attr, no.lineno))
    assert not ofensas, f"camada de rede deve ser READ-ONLY sobre o M1: {ofensas}"


def test_fechamento_e_vetorizado() -> None:
    """Teto de tempo que impede a volta do laco Python por unidade da v1.

    100 unidades x 12 meses ~ o dobro da rede real. Na producao, 2.132 linhas saem em
    ~17 ms; o teto de 3 s aqui e' folgado o bastante para nao piscar em CI lento e
    apertado o bastante para reprovar um `for` por unidade.
    """
    grupos = [
        unidade_saudavel(f"U{i:03d}", 2026, numero_mes)
        for i in range(100)
        for numero_mes in range(1, 13)
    ]
    df = rm.preparar_base(base(*grupos))
    inicio = time.perf_counter()
    fech = rm.fechamento_mensal(df)
    duracao = time.perf_counter() - inicio
    assert len(fech) == 1_200
    assert duracao < 3.0, f"fechamento_mensal levou {duracao:.2f}s - laco por unidade de volta?"
