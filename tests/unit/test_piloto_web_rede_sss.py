"""SSS com maturação mínima de 3 meses no ano-base (DEC-088).

A unidade só entra no SSS se já tinha `SSS_MATURACAO_MIN_MESES` de operação no dia 1º do
período-base (regra POR DATA, `rede_metricas.madura_no_inicio`) e se faturou mais que zero
nele. A unidade em rampa de abertura no ano-base inflava o número: out/2026 da rede saía
−0,7% com 69 unidades; com a regra, −3,0% com 60 (base de produção, 17/11/2026).

Fixture PRÓPRIA, e não a `_base_anual` de `test_piloto_web_rede.py`: acrescentar unidade
lá mexe nas somas de funil, faixas e conversão que as outras suítes fixam.

Chama as funções de rota DIRETO (sem TestClient), como o resto da suíte do piloto.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

from motor_expansao.dashboard import rede_cadastro, rede_export, rede_metricas  # noqa: E402
from motor_expansao.dashboard.pdf_base import PAGINA_LARGURA, UltraPDF, ascii_seguro  # noqa: E402
from tests.unit.rede_fixtures import mes as mes_sintetico  # noqa: E402

# ---------------------------------------------------------------------------
# A regra pura
# ---------------------------------------------------------------------------


def _datas(*valores: str | None) -> pd.Series:
    return pd.to_datetime(pd.Series(list(valores)), format="%Y-%m-%d", errors="coerce")


def test_madura_no_inicio_e_por_data_e_inclui_os_3_meses_exatos() -> None:
    inicio = pd.Timestamp("2025-10-01")
    madura = rede_metricas.madura_no_inicio(
        _datas("2025-07-01", "2025-07-02", "2025-08-01", "2020-01-01", None), inicio
    )
    # 01/07 tem exatamente 3 meses em 01/10 e entra; 02/07 não; vazia conta como madura.
    assert list(madura) == [True, False, False, True, True]
    assert rede_metricas.SSS_MATURACAO_MIN_MESES == 3


def test_madura_no_inicio_aceita_inicio_por_linha_e_outro_n() -> None:
    inauguracao = _datas("2025-05-01", "2025-05-01")
    inicio = pd.Series([pd.Timestamp("2025-08-01"), pd.Timestamp("2025-07-01")])
    assert list(rede_metricas.madura_no_inicio(inauguracao, inicio)) == [True, False]
    assert list(rede_metricas.madura_no_inicio(inauguracao, pd.Timestamp("2025-08-01"), 6)) == [
        False,
        False,
    ]


def test_madura_no_inicio_grampeia_o_fim_de_mes() -> None:
    """31/05 menos 3 meses é 28/02 (DateOffset), não 03/03: o calendário manda."""
    madura = rede_metricas.madura_no_inicio(
        _datas("2025-02-28", "2025-03-01"), pd.Timestamp("2025-05-31")
    )
    assert list(madura) == [True, False]


# ---------------------------------------------------------------------------
# Rede sintética: seis unidades, uma para cada caso
# ---------------------------------------------------------------------------

# (nome, inauguração, faturamento 2025, faturamento 2026, anos com dado)
_PERFIS: tuple[tuple[str, str, float, float, tuple[int, ...]], ...] = (
    # Madura desde sempre: entra.
    ("VELHA", "01/01/2020", 100_000.0, 110_000.0, (2025, 2026)),
    # Exatamente 3 meses antes de 01/07/2025: entra em julho.
    ("EXATA", "01/04/2025", 50_000.0, 60_000.0, (2025, 2026)),
    # 2 meses antes de 01/07/2025: operou julho/2025 INTEIRO, mas em rampa -> fora.
    ("RAMPA", "01/05/2025", 20_000.0, 120_000.0, (2025, 2026)),
    # Sem data de inauguração: conta como madura, entra.
    ("SEM DATA", "", 80_000.0, 72_000.0, (2025, 2026)),
    # Madura, mas sem faturamento no ano-base: fica fora (base zero).
    ("ZERADA", "01/01/2020", 0.0, 60_000.0, (2025, 2026)),
    # Não existia há um ano: fora, como sempre.
    ("NOVA", "01/03/2026", 0.0, 90_000.0, (2026,)),
)


def _base_maturacao() -> pd.DataFrame:
    linhas: list[dict[str, object]] = []
    for nome, inauguracao, fat_2025, fat_2026, anos in _PERFIS:
        for ano in anos:
            for numero_mes, dias in ((6, None), (7, None), (8, 3)):
                faturamento = fat_2025 if ano == 2025 else fat_2026
                linhas += mes_sintetico(
                    nome,
                    ano,
                    numero_mes,
                    uf="SP",
                    master="ULTRA",
                    inauguracao=inauguracao,
                    dias=dias,
                    cumulativas={
                        "faturamento": faturamento,
                        "faturamento_sem_agregador": faturamento,
                        "cancelados": 30.0,
                        "visitas": 100.0,
                        "convertidos": 50.0,
                        "novos_alunos": 40.0,
                        "vendas": 45.0,
                    },
                    snapshots={
                        "pagantes": 1_000.0,
                        "ativos_total": 1_200.0,
                        "alunos_gympass": 100.0,
                        "alunos_totalpass": 100.0,
                        "NPS": 60.0,
                        "em_cobranca": 50.0,
                        "inadimplente": 40.0,
                        "treino_ativo": 50.0,
                    },
                )
    return pd.DataFrame(linhas)


@pytest.fixture
def rede_maturacao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    _base_maturacao().to_parquet(staging / "growth_api_historico.parquet")

    cadastro_dir = tmp_path / "cadastro"
    cadastro_dir.mkdir()
    rede_cadastro.gravar_cadastro(
        rede_cadastro.Cadastro(
            versao=1,
            atualizado_em="2026-11-17T00:00:00+00:00",
            unidades={
                "velha-sp": {"consultor": "MARISE"},
                "rampa-sp": {"consultor": "MARISE"},
                "nova-sp": {"consultor": "MARISE"},
                "exata-sp": {"consultor": "JAILSON"},
                "sem-data-sp": {"consultor": "JAILSON"},
                "zerada-sp": {"consultor": "JAILSON"},
            },
        ),
        cadastro_dir,
    )

    monkeypatch.setattr(pilot, "STAGING_DIR", staging)
    monkeypatch.setattr(pilot, "GROWTH_PARQUET", staging / "growth_api_historico.parquet")
    monkeypatch.setattr(pilot, "ULTRA_PERF_PARQUET", staging / "nao_existe.parquet")
    monkeypatch.setattr(pilot, "ULTRA_MAPEADAS_PARQUET", staging / "tambem_nao.parquet")
    # Constante de MODULO: repontar `STAGING_DIR` não a move (ver `rede_anual`).
    monkeypatch.setattr(
        pilot, "FATURAMENTO_FINANCEIRO_PARQUET", staging / "sem_planilha.parquet"
    )
    monkeypatch.setattr(pilot, "CADASTRO_DIR", cadastro_dir)
    pilot.limpar_caches()
    yield tmp_path
    pilot.limpar_caches()


def _por_id(payload: dict) -> dict[str, dict]:
    return {u["id"]: u for u in payload["unidades"]}


# ---------------------------------------------------------------------------
# SSS do recorte
# ---------------------------------------------------------------------------


def test_unidade_em_rampa_no_ano_base_fica_fora_do_sss(rede_maturacao: Path) -> None:
    """Julho/2026 contra julho/2025: entram VELHA, EXATA e SEM DATA.

    Sem a regra, RAMPA (20k -> 120k) e ZERADA (0 -> 60k) entravam e o recorte "crescia"
    +68,8%: (242 + 120 + 60) / (230 + 20 + 0). Com ela, (110 + 60 + 72) / (100 + 50 + 80).
    """
    sss = pilot._rede_carteira_payload(mes="2026-07")["sss"]
    assert sss["disponivel"] is True
    assert sss["metricas"]["faturamento"]["var_pct"] == pytest.approx(5.2)
    assert sss["unidades"] == 3
    assert sss["unidades_recorte"] == 6
    assert sss["unidades_fora"] == 1  # NOVA
    assert sss["unidades_rampa"] == 2  # RAMPA (maturação) e ZERADA (base zero)
    assert sss["unidades_base_zero"] == 1
    assert sss["maturacao_min_meses"] == 3
    # A conta fecha com o recorte: ninguém some nem é contado duas vezes.
    assert sss["unidades"] + sss["unidades_fora"] + sss["unidades_rampa"] == sss["unidades_recorte"]


def test_contas_fecham_com_o_recorte_em_qualquer_filtro(rede_maturacao: Path) -> None:
    for filtro, esperado in (
        ({"consultor": "MARISE"}, (1, 1, 1)),  # VELHA entra; NOVA fora; RAMPA em rampa
        ({"consultor": "JAILSON"}, (2, 0, 1)),  # EXATA e SEM DATA entram; ZERADA base zero
    ):
        sss = pilot._rede_carteira_payload(mes="2026-07", **filtro)["sss"]
        assert (sss["unidades"], sss["unidades_fora"], sss["unidades_rampa"]) == esperado, filtro
        assert sss["unidades_recorte"] == sum(esperado)


def test_aviso_de_base_pequena_nao_esconde_o_numero(rede_maturacao: Path) -> None:
    sss = pilot._rede_carteira_payload(mes="2026-07")["sss"]
    assert sss["base_pequena"] is True
    assert sss["base_pequena_min"] == rede_metricas.SSS_BASE_PEQUENA_MIN == 5
    assert sss["metricas"]["faturamento"]["var_pct"] is not None


def test_base_de_cinco_ou_mais_nao_e_pequena() -> None:
    """A régua no limite, direto no `_rede_sss`: 5 unidades maduras não levam aviso."""
    nomes = [f"LOJA {letra}" for letra in "ABCDE"]
    linhas: list[dict[str, object]] = []
    for nome in nomes:
        for ano, valor in ((2025, 100_000.0), (2026, 110_000.0)):
            linhas += mes_sintetico(
                nome, ano, 7, inauguracao="01/01/2020", cumulativas={"faturamento": valor}
            )
    base = rede_metricas.preparar_base(pd.DataFrame(linhas))
    atual = rede_metricas.fechamento_periodo(
        base, pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-31")
    )
    ano_anterior = rede_metricas.fechamento_periodo(
        base, pd.Timestamp("2025-07-01"), pd.Timestamp("2025-07-31")
    )
    cinco = pilot._rede_sss(atual, ano_anterior, list(atual["unidade_id"]))
    assert cinco["unidades"] == 5
    assert cinco["base_pequena"] is False
    quatro = pilot._rede_sss(atual, ano_anterior, list(atual["unidade_id"])[:4])
    assert quatro["unidades"] == 4
    assert quatro["base_pequena"] is True


def test_pre_venda_antes_da_inauguracao_nao_vira_unidade_madura() -> None:
    """Dado no ano-base ANTES de a unidade abrir não faz dela uma loja madura.

    O quadro do ano-base apagava a inauguração que cai depois do último dia dele, e data
    vazia conta como madura: a unidade com pré-venda (Noroeste, dado em 31/12/2024 e
    inauguração em 06/01/2025) entraria com a base de um dia. A cesta lê a data do período
    atual, e desde o achado E da revisão da DEC-088 o próprio quadro do ano-base guarda a
    data (o limite é o último dia da BASE, não o da janela): as duas defesas valem.
    """
    linhas: list[dict[str, object]] = []
    for ano, valor in ((2025, 100_000.0), (2026, 110_000.0)):
        linhas += mes_sintetico("VELHA", ano, 7, inauguracao="01/01/2020", cumulativas={"faturamento": valor})
    linhas += mes_sintetico("PRE VENDA", 2025, 7, inauguracao="15/08/2025", cumulativas={"faturamento": 5_000.0})
    linhas += mes_sintetico("PRE VENDA", 2026, 7, inauguracao="15/08/2025", cumulativas={"faturamento": 90_000.0})
    base = rede_metricas.preparar_base(pd.DataFrame(linhas))
    atual = rede_metricas.fechamento_periodo(
        base, pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-31")
    )
    ano_anterior = rede_metricas.fechamento_periodo(
        base, pd.Timestamp("2025-07-01"), pd.Timestamp("2025-07-31")
    )
    # O quadro do ano-base guarda a data posterior a ele (o limite é o fim da BASE) e já não
    # chama de "operou o período inteiro" quem abriu depois dele.
    base_por_id = ano_anterior.set_index("unidade_id")
    assert base_por_id.loc["pre-venda-sp", "inauguracao"] == pd.Timestamp("2025-08-15")
    assert bool(base_por_id.loc["pre-venda-sp", "operacao_periodo_cheio"]) is False

    sss = pilot._rede_sss(atual, ano_anterior, list(atual["unidade_id"]))
    assert sss["unidades"] == 1
    assert sss["metricas"]["faturamento"]["var_pct"] == pytest.approx(10.0)
    # Não existia (abriu depois do início do ano-base): é "fora", não "rampa".
    assert sss["unidades_fora"] == 1
    assert sss["unidades_rampa"] == 0
    por_unidade = pilot._rede_sss_por_unidade(atual, ano_anterior)
    assert por_unidade["pre-venda-sp"]["motivo"] == "sem_ano_anterior"
    assert por_unidade["pre-venda-sp"]["var_pct"] is None


# ---------------------------------------------------------------------------
# SSS por unidade
# ---------------------------------------------------------------------------


def test_sss_por_unidade_marca_o_motivo_de_quem_fica_fora(rede_maturacao: Path) -> None:
    unidades = _por_id(pilot._rede_carteira_payload(mes="2026-07"))
    rampa = unidades["rampa-sp"]["sss"]
    assert rampa["var_pct"] is None
    assert rampa["motivo"] == "em_rampa"
    # O valor do ano-base vai junto: é o que explica por que ela não entra.
    assert rampa["ano_anterior"] == pytest.approx(20_000.0)

    assert unidades["zerada-sp"]["sss"]["motivo"] == "base_zero"
    assert unidades["zerada-sp"]["sss"]["var_pct"] is None
    assert unidades["nova-sp"]["sss"]["motivo"] == "sem_ano_anterior"
    assert unidades["nova-sp"]["sss"]["ano_anterior"] is None

    for entra in ("velha-sp", "exata-sp", "sem-data-sp"):
        assert unidades[entra]["sss"]["motivo"] is None, entra
        assert unidades[entra]["sss"]["var_pct"] is not None, entra
    assert unidades["exata-sp"]["sss"]["var_pct"] == pytest.approx(20.0)


def test_sss_por_unidade_soma_o_agregado_com_a_regra_nova(rede_maturacao: Path) -> None:
    payload = pilot._rede_carteira_payload(mes="2026-07")
    entram = [u for u in payload["unidades"] if (u.get("sss") or {}).get("var_pct") is not None]
    assert len(entram) == payload["sss"]["unidades"]
    assert sum(u["sss"]["faturamento"] for u in entram) == pytest.approx(
        payload["sss"]["metricas"]["faturamento"]["atual"], abs=0.05
    )
    assert sum(u["sss"]["ano_anterior"] for u in entram) == pytest.approx(
        payload["sss"]["metricas"]["faturamento"]["ano_anterior"], abs=0.05
    )


# ---------------------------------------------------------------------------
# Série mês a mês
# ---------------------------------------------------------------------------


def test_serie_mede_a_maturacao_no_ano_base_de_cada_mes(rede_maturacao: Path) -> None:
    """Junho/2026 compara com junho/2025, e o corte é 01/03/2025: EXATA (01/04) ainda era
    rampa lá, embora entre em julho. Cada ponto tem a SUA base."""
    serie = pilot._rede_carteira_payload(mes="2026-07")["sss"]["serie"]
    por_mes = dict(zip(serie["meses"], serie["var_pct"], strict=True))
    tamanho = dict(zip(serie["meses"], serie["unidades"], strict=True))

    assert tamanho["2026-07"] == 3
    assert por_mes["2026-07"] == pytest.approx(5.2)  # igual ao SSS do recorte
    assert tamanho["2026-06"] == 2  # só VELHA e SEM DATA
    assert por_mes["2026-06"] == pytest.approx(1.1)  # (110 + 72) / (100 + 80)


# ---------------------------------------------------------------------------
# Janela livre
# ---------------------------------------------------------------------------


def test_janela_livre_mede_a_maturacao_no_inicio_do_periodo_base(rede_maturacao: Path) -> None:
    """01/06 a 31/07/2026 contra 01/06 a 31/07/2025: o corte é 01/03/2025.

    EXATA (01/04/2025) fica fora. Se a regra medisse no FIM do ano-base (31/07/2025 menos
    3 meses = 30/04) ou pelo `meses_operacao` do fim da janela (3 meses em julho), ela
    entraria — é exatamente o furo das janelas longas.
    """
    payload = pilot._rede_carteira_payload(inicio="2026-06-01", fim="2026-07-31")
    sss = payload["sss"]
    assert sss["unidades"] == 2  # VELHA e SEM DATA
    assert sss["unidades_rampa"] == 3  # EXATA, RAMPA e ZERADA
    assert sss["unidades_fora"] == 1  # NOVA
    # (220 + 144) / (200 + 160)
    assert sss["metricas"]["faturamento"]["var_pct"] == pytest.approx(1.1)
    assert _por_id(payload)["exata-sp"]["sss"]["motivo"] == "em_rampa"


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def test_pdf_separa_a_rampa_de_quem_nao_existia(rede_maturacao: Path) -> None:
    linhas = rede_export.linhas_do_sss(pilot._rede_carteira_payload(mes="2026-07")["sss"])
    assert linhas[0].startswith("Mesma base ano a ano (SSS) - base pequena: 3 de 6 unidades")
    assert "com 3 meses ou mais de operação no ano-base" in linhas[0]
    assert linhas[1] == (
        "Fora da conta: 1 não existia há um ano (ou não operou o período inteiro), "
        "1 estava nos 3 primeiros meses de operação no ano-base (rampa de abertura) "
        "e 1 sem faturamento no ano-base."
    )


def test_pdf_de_payload_antigo_sai_como_antes() -> None:
    linhas = rede_export.linhas_do_sss(
        {
            "disponivel": True,
            "competencia_base": "2025-07",
            "unidades": 2,
            "unidades_recorte": 2,
            "metricas": {"faturamento": {"var_pct": 11.1}},
        }
    )
    assert linhas == [
        "Mesma base ano a ano (SSS): 2 de 2 unidades do recorte estavam abertas nos dois "
        "períodos; faturamento +11,1% contra 2025-07."
    ]


def test_linhas_do_sss_cabem_no_pdf_no_pior_caso() -> None:
    """`cell` não quebra linha: texto longo demais sai cortado pela margem, sem erro."""
    pior = {
        "disponivel": True,
        "competencia_base": "01/08/2025 a 31/10/2025",
        "unidades": 4,
        "unidades_recorte": 100,
        "unidades_fora": 88,
        "unidades_rampa": 8,
        "unidades_base_zero": 2,
        "maturacao_min_meses": 3,
        "base_pequena": True,
        "metricas": {"faturamento": {"var_pct": -12.3}},
    }
    pdf = UltraPDF()
    pdf.set_font("Helvetica", "", 9)
    for linha in rede_export.linhas_do_sss(pior):
        assert linha.encode("latin-1", "replace").decode("latin-1") == linha, linha
        assert pdf.get_string_width(ascii_seguro(linha)) <= PAGINA_LARGURA - 72, linha


def test_pdf_da_carteira_sai_valido_com_a_regra_nova(rede_maturacao: Path) -> None:
    payload = pilot._rede_carteira_payload(mes="2026-07")
    pdf = rede_export.carteira_pdf(payload)
    assert pdf[:5] == b"%PDF-"
