"""BLK-MA-02: testes offline do materializador de snapshots semanais.

Fixtures 100% SINTETICAS em `tmp_path` (CSVs com `sep=";"` / `encoding="utf-8-sig"`, coordenadas
reais do Brasil, nomes inventados). NENHUM teste le a fonte real -- ela e gitignored, vive na VPS
e carrega PII na origem (DEC-012).

Cobre: isolamento de import (AST), contrato de 10 colunas + `_assert_schema`, anti-PII provado
RELENDO o parquet do disco (inclusive nos bytes do arquivo), particao por semana ISO e
idempotencia, limpeza de ruido com auditoria so de contagens, `hash_campos_raspados`, estabilidade
do `slug` / rebaixamento de chave, e poda de retencao.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import churn_staleness as mchurn
from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade import presenca_agregador as mpresenca
from motor_expansao.vulnerabilidade import score as mscore
from motor_expansao.vulnerabilidade import snapshots as m

REF = date(2026, 7, 29)  # semana ISO 2026-31
SEMANA_REF = "2026-31"


# --------------------------------------------------------------------------- #
# Helpers de fixture sintetica
# --------------------------------------------------------------------------- #
def _escrever_csv(caminho: Path, df: pd.DataFrame) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, sep=";", encoding="utf-8-sig", index=False)


def _frame_tp(**kwargs: object) -> pd.DataFrame:
    """Frame de trabalho minimo (uma linha) no schema TotalPass, para os testes de hash."""
    base: dict[str, object] = {
        "fonte": "totalpass",
        "rede": "independente",
        "slug": "academia-alfa",
        "nome": "Academia Alfa",
        "nome_unidade": "",
        "latitude": -23.5500,
        "longitude": -46.6300,
        "cidade": "Sao Paulo",
        "uf": "SP",
        "cep": "01000-000",
        "endereco_formatado": "Rua A, 100",
        "modalidades": "Musculacao, Natacao",
        "atividades": "",
        "data_coleta": "2026-07-27",
    }
    base.update(kwargs)
    return pd.DataFrame([base])


@pytest.fixture
def dirs_sinteticos(tmp_path: Path) -> tuple[Path, Path, Path]:
    """3 pastas com CSVs sinteticos limpos (2 TP + 2 WH + 2 unidades)."""
    tp, wh, un = tmp_path / "tp", tmp_path / "wh", tmp_path / "un"
    _escrever_csv(
        tp / "unidades_totalpass_sp.csv",
        pd.DataFrame(
            {
                "slug": ["academia-alfa", "academia-beta"],
                "nome": ["Academia Alfa", "Academia Beta"],
                "latitude": [-23.5500, -23.6500],
                "longitude": [-46.6300, -46.7300],
                "cidade": ["Sao Paulo", "Sao Paulo"],
                "uf": ["SP", "SP"],
                "cep": ["01000-000", "04000-000"],
                "endereco_formatado": ["Rua A, 100", "Rua B, 200"],
                "modalidades": ["Musculacao, Natacao", "Musculacao"],
                "data_coleta": ["2026-07-27", "2026-07-27"],
            }
        ),
    )
    _escrever_csv(
        wh / "unidades_wellhub_rj.csv",
        pd.DataFrame(
            {
                "slug": ["academia-gama", "academia-delta"],
                "nome": ["Academia Gama", "Academia Delta"],
                "latitude": [-22.9100, -22.8500],
                "longitude": [-43.1800, -43.3000],
                "cidade": ["Rio de Janeiro", "Rio de Janeiro"],
                "uf": ["RJ", "RJ"],
                "cep": ["20000-000", "21000-000"],
                "endereco_formatado": ["Rua C, 300", "Rua D, 400"],
                "atividades": ["Musculacao", "Crossfit; Musculacao"],
                "data_coleta": ["2026-07-26", "2026-07-26"],
            }
        ),
    )
    _escrever_csv(
        un / "unidades_selfit.csv",
        pd.DataFrame(
            {
                "nome_unidade": ["Selfit Norte", "Selfit Sul"],
                "latitude": [-23.4000, -23.7000],
                "longitude": [-46.5000, -46.8000],
                "data_coleta": ["2026-07-25", "2026-07-25"],
            }
        ),
    )
    return tp, wh, un


@pytest.fixture
def dirs_com_ruido(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Uma linha sintetica por CLASSE de ruido (+ 3 linhas boas), todas no feed TotalPass."""
    tp, wh, un = tmp_path / "tp", tmp_path / "wh", tmp_path / "un"
    tp.mkdir(parents=True, exist_ok=True)
    wh.mkdir(parents=True, exist_ok=True)
    un.mkdir(parents=True, exist_ok=True)
    _escrever_csv(
        tp / "unidades_totalpass_mix.csv",
        pd.DataFrame(
            {
                "slug": [f"s{i}" for i in range(1, 13)],
                "nome": [
                    # 1 por motivo de descarte
                    "Academia Data Ruim",
                    "Academia Zero Zero",
                    "Academia No Atlantico",
                    "Academia Coord Trocada",
                    "Teste Raised",
                    "Zon Tecnologia",
                    "SAGAZ Sistemas",
                    "TSITECH Solucoes",
                    "DATAFITNESS - TTP",
                    # 3 boas (a ultima junto a divisa de UF)
                    "Academia Boa Centro",
                    "Academia Boa Norte",
                    "Academia Boa Divisa",
                ],
                "latitude": [
                    -23.55, 0.0, 0.0, -23.55, -23.55, -23.55, -23.55, -23.55, -23.55,
                    -23.55, -23.60, -25.45,
                ],
                "longitude": [
                    -46.63, 0.0, -20.0, -46.63, -46.63, -46.63, -46.63, -46.63, -46.63,
                    -46.63, -46.70, -53.20,
                ],
                "cidade": ["X"] * 12,
                "uf": [
                    "SP", "SP", "SP", "AM", "SP", "SP", "SP", "SP", "SP",
                    "SP", "SP", "SP",
                ],
                "cep": ["01000-000"] * 12,
                "endereco_formatado": ["Rua Z"] * 12,
                "modalidades": ["Musculacao"] * 12,
                "data_coleta": ["31/12/2026"] + ["2026-07-27"] * 11,
            }
        ),
    )
    return tp, wh, un


# --------------------------------------------------------------------------- #
# CA-1 — isolamento de imports (AST) sobre os 4 modulos do pacote
# --------------------------------------------------------------------------- #
def test_isolamento_imports() -> None:
    """Pacote DISJUNTO: nenhum import pode casar M1/dashboard/api/censo/config raiz.

    O AST olha os IMPORTS reais, nunca a prosa do docstring (que cita os caminhos proibidos como
    guardrail). `normalizar_concorrentes` entra na lista: é `_DENY_CRITICO` do loop_guard e a sua
    fórmula foi REPLICADA no `contrato`, jamais importada.

    Esta tupla é a garantia COMPARTILHADA do pacote; ela **não** proíbe `demanda_revelada` (nem
    poderia: `snapshots.py` o importa). A proibição específica dos módulos do sinal 1 e do score
    vive em `test_presenca_agregador.py::test_modulo_nao_importa_demanda_revelada` e em
    `test_score.py::test_modulo_nao_importa_demanda_revelada`.
    """
    import motor_expansao.vulnerabilidade as pacote

    from .._ast_imports import casa_proibicao, nomes_importados

    for modulo in (pacote, c, m, mchurn, mpresenca, mscore):
        for n in nomes_importados(modulo):
            # As checagens por SUBSTRING são mantidas como estavam: são mais amplas que
            # um prefixo (pegam `dashboard.censo_map`, por exemplo) e afrouxá-las para
            # caber num laço uniforme reduziria o guardrail.
            assert "pipelines.m1" not in n, (modulo.__name__, n)
            assert "censo" not in n, (modulo.__name__, n)
            assert "normalizar_concorrentes" not in n, (modulo.__name__, n)
            # Estas passam por `casa_proibicao` porque o import RELATIVO
            # (`from .. import dashboard`) deixa só o alias no AST, e o `startswith`
            # anterior não o via.
            for proibido in ("motor_expansao.dashboard", "motor_expansao.api", "motor_expansao.config"):
                assert not casa_proibicao(n, proibido), (modulo.__name__, n, proibido)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BLK-MA-02-FU1 item 2: vazamento TRANSITIVO de import, em aberto. "
        "`snapshots.py` importa `classificar_rede` de `demanda_revelada`, cujo `__init__` "
        "reexporta os 9 submodulos de forma eager e puxa sklearn/scipy/shapely/requests. "
        "Bloqueante para o BLK-MA-06 (plug no cron). Quando a correcao entrar, este teste "
        "PASSA e o `strict=True` avisa para remover a marca."
    ),
)
def test_pacote_nao_carrega_dependencia_pesada() -> None:
    """Isolamento por `sys.modules`, nao por AST — o AST so ve import DIRETO.

    O `test_isolamento_imports` continua verde enquanto isto falha, e as duas coisas sao
    verdadeiras ao mesmo tempo: o pacote nao escreve nenhum import proibido, mas o que ele
    importa arrasta meio mundo junto. Um modulo destinado ao cron precisa das duas garantias.
    """
    import subprocess
    import sys
    import textwrap

    codigo = textwrap.dedent(
        """
        import sys
        import motor_expansao.vulnerabilidade  # noqa: F401
        pesados = sorted(
            {m.split(".")[0] for m in sys.modules}
            & {"sklearn", "scipy", "shapely", "requests", "matplotlib", "geopandas"}
        )
        dash = [m for m in sys.modules if m.startswith("motor_expansao.dashboard")]
        print(";".join(pesados) + "|" + str(len(dash)))
        """
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    ).stdout.strip()
    pesados, n_dashboard = saida.split("|")
    assert not pesados, f"dependencias pesadas carregadas: {pesados}"
    assert n_dashboard == "0", f"modulos de dashboard carregados: {n_dashboard}"


def test_checagem_de_import_pega_as_cinco_formas() -> None:
    """Sonda de injeção: a checagem de isolamento não pode ter ponto cego.

    Antes da correção, das cinco formas de escrever o import proibido a checagem por
    AST pegava **2** e deixava passar **3**: `from motor_expansao import dashboard`
    (só o pai entrava na lista), `from .. import dashboard` (o nó era descartado
    inteiro quando `node.module is None`) e `importlib.import_module(...)` (é uma
    chamada, não um nó de import).

    Este teste falha com a implementação antiga e é o que impede o guardrail de voltar
    a ser decorativo.
    """
    from .._ast_imports import (
        casa_proibicao,
        fontes_com_import_injetado,
        nomes_importados_da_fonte,
    )

    alvos = (
        "motor_expansao.dashboard",
        "motor_expansao.api",
        "motor_expansao.config",
        "motor_expansao.demanda_revelada",
    )
    for proibido in alvos:
        for rotulo, fonte in fontes_com_import_injetado(proibido):
            nomes = nomes_importados_da_fonte(fonte)
            assert any(casa_proibicao(n, proibido) for n in nomes), (
                proibido,
                rotulo,
                nomes,
            )


# --------------------------------------------------------------------------- #
# CA-12 — nenhum teste do pacote aponta para caminho de fonte real
# --------------------------------------------------------------------------- #
def test_sem_caminho_real_nos_testes() -> None:
    """Os literais proibidos sao MONTADOS por concatenacao para nao se auto-acusarem."""
    proibidos = ["concorrentes" + "/", "data/" + "staging", "data/" + "outputs", "data/" + "raw"]
    for arquivo in sorted(Path(__file__).parent.glob("test_*.py")):
        tree = ast.parse(arquivo.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for proibido in proibidos:
                    assert proibido not in node.value, (arquivo.name, proibido)


def test_defaults_iguais_aos_da_ingestao_existente() -> None:
    """R6: os diretorios default NAO podem divergir dos ja usados pela ingestao densa."""
    from motor_expansao.demanda_revelada import concorrentes_densos as densos

    assert m.DIR_TOTALPASS_DEFAULT == densos.DIR_TOTALPASS_DEFAULT
    assert m.DIR_WELLHUB_DEFAULT == densos.DIR_WELLHUB_DEFAULT
    assert m.DIR_UNIDADES_DEFAULT == densos.DIR_UNIDADES_DEFAULT


# --------------------------------------------------------------------------- #
# CA-2 — contrato de 10 colunas + _assert_schema
# --------------------------------------------------------------------------- #
def test_schema_snapshot_10_colunas_em_ordem(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    assert list(snap.columns) == list(c.CONTRATO_COLUNAS_SNAPSHOT.keys())
    assert len(list(snap.columns)) == 10
    assert len(snap) == 6
    assert set(snap["fonte"]) == {"totalpass", "wellhub", "unidades"}
    assert (snap["versao_contrato"] == c.VERSAO_CONTRATO_SNAPSHOT).all()
    assert auditoria["semana"] == SEMANA_REF
    assert auditoria["chaves_colapsadas"] == 0


def _snapshot_valido(dirs: tuple[Path, Path, Path]) -> pd.DataFrame:
    tp, wh, un = dirs
    snap, _ = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    return snap


def test_assert_schema_rejeita_coluna_extra(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    snap = _snapshot_valido(dirs_sinteticos)
    ruim = snap.copy()
    ruim["extra"] = "x"
    with pytest.raises(ValueError, match="fora do contrato"):
        m._assert_schema_snapshot(ruim)


def test_assert_schema_rejeita_coluna_de_pii(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    snap = _snapshot_valido(dirs_sinteticos)
    ruim = snap.copy()
    ruim["nome"] = "Academia Qualquer"
    with pytest.raises(ValueError, match="PII"):
        m._assert_schema_snapshot(ruim)


def test_assert_schema_rejeita_ordem_trocada(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    snap = _snapshot_valido(dirs_sinteticos)
    ruim = snap[list(reversed(list(snap.columns)))]
    with pytest.raises(ValueError, match="ordem de colunas"):
        m._assert_schema_snapshot(ruim)


def test_assert_schema_rejeita_chave_vazia(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    ruim = _snapshot_valido(dirs_sinteticos).copy()
    ruim.loc[0, "chave_snapshot"] = ""
    with pytest.raises(ValueError, match="chave_snapshot"):
        m._assert_schema_snapshot(ruim)


def test_assert_schema_rejeita_hex_fora_res7(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    import h3

    ruim = _snapshot_valido(dirs_sinteticos).copy()
    ruim.loc[0, "hex_id_res7"] = h3.latlng_to_cell(-23.55, -46.63, 8)
    with pytest.raises(ValueError, match="res-7"):
        m._assert_schema_snapshot(ruim)


def test_assert_schema_rejeita_chave_duplicada(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    snap = _snapshot_valido(dirs_sinteticos)
    ruim = pd.concat([snap, snap.head(1)], ignore_index=True)
    with pytest.raises(ValueError, match="duplicada"):
        m._assert_schema_snapshot(ruim)


def test_assert_schema_rejeita_fonte_invalida(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    ruim = _snapshot_valido(dirs_sinteticos).copy()
    ruim.loc[0, "fonte"] = "instagram"
    with pytest.raises(ValueError, match="fonte fora do contrato"):
        m._assert_schema_snapshot(ruim)


def test_assert_schema_rejeita_chave_origem_invalida(
    dirs_sinteticos: tuple[Path, Path, Path],
) -> None:
    ruim = _snapshot_valido(dirs_sinteticos).copy()
    ruim.loc[0, "chave_origem"] = "concorrente_id"
    with pytest.raises(ValueError, match="chave_origem fora do contrato"):
        m._assert_schema_snapshot(ruim)


# --------------------------------------------------------------------------- #
# CA-3 — anti-PII provado RELENDO o parquet do disco
# --------------------------------------------------------------------------- #
def test_parquet_sem_pii_relendo_do_disco(tmp_path: Path) -> None:
    marcador = "XYZZY123"
    tp, wh, un = tmp_path / "tp", tmp_path / "wh", tmp_path / "un"
    tp.mkdir(parents=True, exist_ok=True)
    wh.mkdir(parents=True, exist_ok=True)
    un.mkdir(parents=True, exist_ok=True)
    _escrever_csv(
        tp / "unidades_totalpass_pii.csv",
        pd.DataFrame(
            {
                "slug": ["academia-sintetica-01"],
                "nome": [f"ACADEMIA SINTETICA {marcador}"],
                "latitude": [-23.5500],
                "longitude": [-46.6300],
                "cidade": [f"CIDADE {marcador}"],
                "uf": ["SP"],
                "cep": ["01000-000"],
                "endereco_formatado": [f"RUA {marcador}, 999"],
                "modalidades": [f"MODALIDADE {marcador}"],
                "data_coleta": ["2026-07-27"],
            }
        ),
    )
    base = tmp_path / "snapshots"
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF, escrever=True)

    arquivos = sorted((base / f"semana={SEMANA_REF}").glob("parte-*.parquet"))
    assert arquivos, "a particao da semana deveria ter ao menos um parte-*.parquet"

    relido = pd.read_parquet(arquivos[0])
    assert not (set(relido.columns) & c.COLUNAS_PII_PROIBIDAS)
    assert list(relido.columns) == list(c.CONTRATO_COLUNAS_SNAPSHOT.keys())
    for coluna in relido.columns:
        assert not relido[coluna].astype(str).str.contains(marcador).any(), coluna
    # O literal nao pode sobreviver nem em metadado/estatistica de coluna do proprio arquivo.
    assert marcador.encode() not in arquivos[0].read_bytes()


# --------------------------------------------------------------------------- #
# CA-4 / CA-17 — particao por semana ISO, idempotencia e escrita defensiva
# --------------------------------------------------------------------------- #
def test_particao_nomeada_por_semana_iso(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "snapshots"
    snap, auditoria = m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)
    particao = base / f"semana={SEMANA_REF}"
    assert particao.is_dir()
    assert sorted(p.name for p in particao.glob("parte-*.parquet"))
    assert auditoria["semana"] == SEMANA_REF
    # `semana` vive no CAMINHO, nunca dentro do arquivo.
    assert "semana" not in list(snap.columns)


def test_particao_usa_a_data_de_referencia_nao_o_data_coleta(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """P1: a semana sai da EXECUCAO. Um CSV velho (coletor falho) nao reescreve semana passada."""
    tp, wh, un = dirs_sinteticos  # data_coleta de 2026-07-25/26/27 (semana ISO 2026-30)
    base = tmp_path / "snapshots"
    ref_futura = date(2026, 8, 5)  # semana ISO 2026-32
    snap, _ = m.materializar(tp, wh, un, base_dir=base, data_referencia=ref_futura)
    assert (base / "semana=2026-32").is_dir()
    assert not (base / "semana=2026-30").exists()
    # ...e o `snapshot_date` por linha continua sendo o `data_coleta` (medidor de frescor).
    assert set(snap["snapshot_date"]) == {"2026-07-25", "2026-07-26", "2026-07-27"}


def test_materializar_duas_vezes_mesma_semana_nao_duplica(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "snapshots"
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)
    serie = m.ler_snapshots(base)
    assert len(serie) == 6
    assert set(serie["semana"]) == {SEMANA_REF}
    assert [p.name for p in sorted(base.iterdir())] == [f"semana={SEMANA_REF}"]


def test_materializar_semana_menor_na_segunda_execucao(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Prova do `delete_matching`: a 2a execucao SUBSTITUI a particao, nao soma a ela."""
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "snapshots"
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)
    assert len(m.ler_snapshots(base)) == 6
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    m.materializar(tp, vazio, vazio, base_dir=base, data_referencia=REF)
    serie = m.ler_snapshots(base)
    assert len(serie) == 2, "a semana encolheu de 6 para 2 linhas"


def test_escrever_particao_recusa_frame_multi_semana(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    snap = _snapshot_valido(dirs_sinteticos)
    multi = snap.copy()
    multi["semana"] = [SEMANA_REF] * 3 + ["2026-30"] * 3
    with pytest.raises(ValueError, match="exatamente 1 semana"):
        m.escrever_particao_semana(multi, tmp_path / "s", semana=SEMANA_REF)
    with pytest.raises(ValueError, match="ISO"):
        m.escrever_particao_semana(snap, tmp_path / "s", semana="2026-7")
    with pytest.raises(ValueError, match="ISO"):
        m.escrever_particao_semana(snap, tmp_path / "s", semana="semana-corrente")


def test_ler_snapshots_base_inexistente_ou_vazia(tmp_path: Path) -> None:
    esperado = list(c.CONTRATO_COLUNAS_SNAPSHOT.keys()) + ["semana"]
    vazia = m.ler_snapshots(tmp_path / "nao_existe")
    assert vazia.empty and list(vazia.columns) == esperado
    (tmp_path / "so_lixo").mkdir()
    (tmp_path / "so_lixo" / "leia-me.txt").write_text("x", encoding="utf-8")
    assert m.ler_snapshots(tmp_path / "so_lixo").empty


# --------------------------------------------------------------------------- #
# CA-5 — limpeza de ruido com auditoria SO de contagens
# --------------------------------------------------------------------------- #
def test_limpar_ruido_conta_por_motivo(dirs_com_ruido: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_com_ruido
    bruto = m.ler_feeds(tp, wh, un)
    limpo, auditoria = m.limpar_ruido(bruto)
    descartes = auditoria["descartes"]
    assert auditoria["linhas_lidas"] == 12
    assert auditoria["linhas_mantidas"] == 3
    assert descartes["data_coleta_invalida"] == 1
    assert descartes["coord_zero_zero"] == 1
    assert descartes["coord_fora_envelope_brasil"] == 1
    assert descartes["coord_fora_bbox_uf"] == 1
    assert descartes["rotulo_de_teste"] == 1
    assert descartes["entrada_tecnologia_totalpass"] == 4
    assert sum(descartes.values()) == 9
    assert len(limpo) == 3


def test_limpar_ruido_preserva_linhas_boas(dirs_com_ruido: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_com_ruido
    limpo, _ = m.limpar_ruido(m.ler_feeds(tp, wh, un))
    nomes = sorted(limpo["nome"])
    assert nomes == ["Academia Boa Centro", "Academia Boa Divisa", "Academia Boa Norte"]


def test_auditoria_so_tem_contagens(dirs_com_ruido: tuple[Path, Path, Path]) -> None:
    """Anti-PII: a auditoria carrega SO inteiros, jamais o texto ofensor."""
    tp, wh, un = dirs_com_ruido
    _limpo, auditoria = m.limpar_ruido(m.ler_feeds(tp, wh, un))

    def _valores(no: object) -> list[object]:
        if isinstance(no, dict):
            return [v for sub in no.values() for v in _valores(sub)]
        return [no]

    for valor in _valores(auditoria):
        assert isinstance(valor, int) and not isinstance(valor, bool), valor
    texto = repr(auditoria)
    for ofensor in ("Zon", "SAGAZ", "Teste Raised", "Academia", "Rua Z", "01000-000"):
        assert ofensor not in texto


def test_limpar_ruido_e_deterministico_por_linha(dirs_com_ruido: tuple[Path, Path, Path]) -> None:
    """A regra nunca pode depender do LOTE: metade do feed produz o mesmo veredito por linha."""
    tp, wh, un = dirs_com_ruido
    bruto = m.ler_feeds(tp, wh, un)
    inteiro, _ = m.limpar_ruido(bruto)
    metade, _ = m.limpar_ruido(bruto.head(6).reset_index(drop=True))
    assert set(metade["nome"]) <= set(inteiro["nome"])
    assert set(metade["nome"]) == set(inteiro["nome"]) & set(bruto.head(6)["nome"])


# --------------------------------------------------------------------------- #
# CA-6 — hash_campos_raspados
# --------------------------------------------------------------------------- #
def _hash(df: pd.DataFrame) -> str:
    return str(m.calcular_hash_campos_raspados(df)["hash_campos_raspados"].iloc[0])


def test_hash_ignora_data_coleta() -> None:
    assert _hash(_frame_tp(data_coleta="2026-07-27")) == _hash(
        _frame_tp(data_coleta="2026-08-03")
    )


def test_hash_ignora_a_taxonomia_inteira() -> None:
    """Sucessor de `test_hash_ignora_ordem_das_modalidades` (emenda BLK-MA-11 / DEC-025).

    A versão anterior só provava invariância à ORDEM dos tokens. Desde a emenda, a taxonomia saiu
    do hash por completo: trocar os próprios rótulos também não pode mexer no hash. Motivo medido:
    o WellHub renomeou "Musculação" para "Treino de força"/"Fisiculturismo" e o campo mudou em
    99,1% das unidades sem que uma só academia mudasse - com a taxonomia dentro, o sinal 4 morreria
    de uma vez para a base inteira.
    """
    base = _hash(_frame_tp(modalidades="Musculacao, Natacao"))
    assert base == _hash(_frame_tp(modalidades="Natacao; Musculacao")), "ordem"
    assert base == _hash(_frame_tp(modalidades="Treino de forca, Natacao")), "rotulo renomeado"
    assert base == _hash(_frame_tp(modalidades="")), "taxonomia ausente"


def test_hash_ignora_slug() -> None:
    """Rotacao de UUID no slug NAO e mudanca de negocio."""
    assert _hash(_frame_tp(slug="academia-alfa-b8491478-1111-2222-3333-444455556666")) == _hash(
        _frame_tp(slug="academia-alfa-99999999-aaaa-bbbb-cccc-dddddddddddd")
    )


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("nome", "Academia Alfa Renomeada"),
        ("endereco_formatado", "Rua A, 999"),
        ("latitude", -23.6000),
        ("cep", "09000-000"),
        # `modalidades` saiu desta lista na emenda BLK-MA-11 / DEC-025: renomear taxonomia deixou
        # de ser "mudança de cadastro". A invariância agora é asserida em
        # `test_hash_ignora_a_taxonomia_inteira`.
    ],
)
def test_hash_muda_com_campo_real(campo: str, valor: object) -> None:
    assert _hash(_frame_tp()) != _hash(_frame_tp(**{campo: valor}))


def test_hash_usa_o_conjunto_de_campos_da_propria_fonte() -> None:
    """O feed `unidades` hasheia `nome_unidade` (nao `nome`) + coordenadas."""
    base = _frame_tp(fonte="unidades", rede="selfit", nome="Selfit Norte",
                     nome_unidade="Selfit Norte", slug="")
    outro = base.copy()
    outro.loc[0, "cidade"] = "OUTRA CIDADE"  # fora de CAMPOS_HASH_POR_FONTE["unidades"]
    assert _hash(base) == _hash(outro)
    mudou = base.copy()
    mudou.loc[0, "nome_unidade"] = "Selfit Norte II"
    assert _hash(base) != _hash(mudou)


# --------------------------------------------------------------------------- #
# CA-7 — estabilidade do slug e rebaixamento auditavel da chave
# --------------------------------------------------------------------------- #
def _snap_slug(semana: str, slugs: list[str], fonte: str = "totalpass") -> pd.DataFrame:
    return pd.DataFrame({"semana": semana, "fonte": fonte, "slug": slugs})


def test_estabilidade_slug_metricas() -> None:
    snaps = [
        _snap_slug("2026-01", ["a", "b", "c"]),
        _snap_slug("2026-02", ["a", "b", "d"]),
        _snap_slug("2026-03", ["a", "b", "d"]),
    ]
    metricas = m.avaliar_estabilidade_slug(snaps)
    assert set(metricas) == {
        "taxa_slug_presente",
        "taxa_slug_unico_no_snapshot",
        "taxa_slug_persistente",
        "taxa_slug_com_uuid",
        "n_semanas_avaliadas",
        "n_pares_consecutivos",
    }
    assert metricas["taxa_slug_presente"] == 1.0
    assert metricas["taxa_slug_unico_no_snapshot"] == 1.0
    assert metricas["taxa_slug_persistente"] == pytest.approx(5 / 6)
    assert metricas["taxa_slug_com_uuid"] == 0.0
    assert metricas["n_semanas_avaliadas"] == 3.0
    assert metricas["n_pares_consecutivos"] == 2.0


def test_estabilidade_slug_sem_par_consecutivo_devolve_nan() -> None:
    metricas = m.avaliar_estabilidade_slug([_snap_slug("2026-01", ["a", "b"])])
    assert metricas["n_pares_consecutivos"] == 0.0
    assert metricas["taxa_slug_persistente"] != metricas["taxa_slug_persistente"]  # NaN
    vazio = m.avaliar_estabilidade_slug([])
    assert vazio["n_semanas_avaliadas"] == 0.0


def test_chave_origem_slug_estavel() -> None:
    """Slug estavel entre as 3 semanas -> taxa 1,0 -> a chave CONFIA no slug."""
    snaps = [_snap_slug(f"2026-0{i}", ["a", "b", "c"]) for i in (1, 2, 3)]
    taxa = m.avaliar_estabilidade_slug(snaps)["taxa_slug_persistente"]
    assert taxa == 1.0
    saida = m.derivar_chave(_frame_tp(), taxa_slug_persistente=taxa)
    assert saida["chave_origem"].iloc[0] == "slug"
    assert saida["chave_snapshot"].iloc[0] == c.chave_do_slug("totalpass", "academia-alfa")


def test_chave_origem_slug_uuid_rotativo() -> None:
    """UUID rotativo -> persistencia ~0 -> rebaixamento GLOBAL para `hash_estavel`."""
    snaps = [
        _snap_slug("2026-01", ["alfa-b8491478-1111-2222-3333-444455556666"]),
        _snap_slug("2026-02", ["alfa-99999999-aaaa-bbbb-cccc-dddddddddddd"]),
        _snap_slug("2026-03", ["alfa-77777777-eeee-ffff-0000-111122223333"]),
    ]
    metricas = m.avaliar_estabilidade_slug(snaps)
    assert metricas["taxa_slug_com_uuid"] == 1.0
    assert metricas["taxa_slug_persistente"] == 0.0
    saida = m.derivar_chave(_frame_tp(), taxa_slug_persistente=metricas["taxa_slug_persistente"])
    assert saida["chave_origem"].iloc[0] == "hash_estavel"


def test_rebaixamento_global_so_com_taxa_injetada() -> None:
    """Default `None`: o materializador NUNCA le semanas anteriores nem re-chaveia sozinho."""
    assert m.derivar_chave(_frame_tp())["chave_origem"].iloc[0] == "slug"
    assert m.derivar_chave(_frame_tp(), taxa_slug_persistente=float("nan"))[
        "chave_origem"
    ].iloc[0] == "slug"
    assert m.derivar_chave(_frame_tp(), politica="hash_estavel")["chave_origem"].iloc[0] == (
        "hash_estavel"
    )
    with pytest.raises(ValueError, match="politica"):
        m.derivar_chave(_frame_tp(), politica="ordinal")


def test_chave_origem_slug_duplicado_no_snapshot() -> None:
    """Rebaixamento POR LINHA (so informacao local da semana): slug repetido nao serve de chave."""
    df = pd.concat(
        [_frame_tp(nome="Academia Alfa I"), _frame_tp(nome="Academia Alfa II", latitude=-23.9)],
        ignore_index=True,
    )
    saida = m.derivar_chave(df)
    assert set(saida["chave_origem"]) == {"hash_estavel"}
    assert saida["chave_snapshot"].nunique() == 2


def test_chave_origem_slug_ausente_feed_unidades(
    dirs_sinteticos: tuple[Path, Path, Path],
) -> None:
    tp, wh, un = dirs_sinteticos
    snap, _ = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    unidades = snap[snap["fonte"] == "unidades"]
    assert len(unidades) == 2
    assert set(unidades["chave_origem"]) == {"hash_estavel"}
    assert unidades["slug"].isna().all(), "o feed de cadeias nao emite slug -> pd.NA"
    tp_wh = snap[snap["fonte"] != "unidades"]
    assert set(tp_wh["chave_origem"]) == {"slug"}


def test_colisao_de_chave_e_colapsada_nunca_desambiguada(tmp_path: Path) -> None:
    """Duas linhas com a MESMA chave viram UMA (falso negativo seguro), nunca duas por ordinal."""
    un = tmp_path / "un"
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    _escrever_csv(
        un / "unidades_selfit.csv",
        pd.DataFrame(
            {
                "nome_unidade": ["Selfit Centro", "Selfit Centro"],
                "latitude": [-23.5500, -23.5501],  # mesmo hex res-7
                "longitude": [-46.6300, -46.6301],
                "data_coleta": ["2026-07-27", "2026-07-27"],
            }
        ),
    )
    snap, auditoria = m.materializar(vazio, vazio, un, data_referencia=REF, escrever=False)
    assert len(snap) == 1
    assert auditoria["chaves_colapsadas"] == 1


# --------------------------------------------------------------------------- #
# CA-11 — poda de retencao (I/O DESTRUTIVA)
# --------------------------------------------------------------------------- #
def _criar_semanas(base: Path, n: int) -> None:
    base.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        (base / f"semana=2026-{i:02d}").mkdir()


def test_podar_mantem_26_de_30(tmp_path: Path) -> None:
    base = tmp_path / "snapshots"
    _criar_semanas(base, 30)
    removidas = m.podar_snapshots(base, c.RETENCAO_SEMANAS)
    assert removidas == ["2026-01", "2026-02", "2026-03", "2026-04"]
    restantes = sorted(p.name for p in base.iterdir())
    assert len(restantes) == 26
    assert restantes[0] == "semana=2026-05"


def test_podar_nao_remove_diretorio_irmao(tmp_path: Path) -> None:
    base = tmp_path / "snapshots"
    _criar_semanas(base, 3)
    (base / "backup").mkdir()
    (base / "semana_antiga").mkdir()
    (base / "leia-me.txt").write_text("x", encoding="utf-8")
    removidas = m.podar_snapshots(base, 1)
    assert removidas == ["2026-01", "2026-02"]
    nomes = {p.name for p in base.iterdir()}
    assert {"backup", "semana_antiga", "leia-me.txt", "semana=2026-03"} <= nomes


def test_podar_dry_run_nao_apaga(tmp_path: Path) -> None:
    base = tmp_path / "snapshots"
    _criar_semanas(base, 5)
    removidas = m.podar_snapshots(base, 2, dry_run=True)
    assert removidas == ["2026-01", "2026-02", "2026-03"]
    assert len(list(base.iterdir())) == 5


def test_podar_valida_retencao_e_base_ausente(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="retencao_semanas"):
        m.podar_snapshots(tmp_path, 0)
    assert m.podar_snapshots(tmp_path / "nao_existe") == []


def test_materializar_escrever_false_nao_poda(
    dirs_sinteticos: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A poda APAGA disco: `materializar` nao pode alcanca-la em hipotese alguma."""

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("materializar NUNCA pode chamar podar_snapshots")

    monkeypatch.setattr(m, "podar_snapshots", _explode)
    tp, wh, un = dirs_sinteticos
    m.materializar(tp, wh, un, data_referencia=REF, escrever=False)


# --------------------------------------------------------------------------- #
# Ingestao: rede, diretorio ausente, feed vazio
# --------------------------------------------------------------------------- #
def test_rede_unidades_vem_do_nome_do_arquivo(tmp_path: Path) -> None:
    un = tmp_path / "un"
    _escrever_csv(
        un / "unidades_smart_fit.csv",
        pd.DataFrame(
            {
                "nome_unidade": ["Unidade Qualquer"],
                "latitude": [-23.55],
                "longitude": [-46.63],
                "data_coleta": ["2026-07-27"],
            }
        ),
    )
    df = m.ler_feeds(tmp_path / "nada1", tmp_path / "nada2", un)
    assert list(df["rede"]) == ["smart_fit"]
    assert list(df["fonte"]) == ["unidades"]


def test_rede_tp_wh_vem_do_classificador(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    df = m.ler_feeds(tp, wh, un)
    tpwh = df[df["fonte"] != "unidades"]
    assert set(tpwh["rede"]) == {"independente"}  # nomes sinteticos nao casam cadeia alguma


def test_ler_feeds_diretorio_ausente_nao_levanta(tmp_path: Path) -> None:
    df = m.ler_feeds(tmp_path / "a", tmp_path / "b", tmp_path / "c")
    assert df.empty
    assert list(df.columns) == list(m._COLUNAS_TRABALHO)


def test_materializar_sem_csv_frame_vazio_bem_formado(tmp_path: Path) -> None:
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    snap, auditoria = m.materializar(
        vazio, vazio, vazio, base_dir=tmp_path / "s", data_referencia=REF, escrever=True
    )
    assert snap.empty
    assert list(snap.columns) == list(c.CONTRATO_COLUNAS_SNAPSHOT.keys())
    assert auditoria["linhas_lidas"] == 0
    assert auditoria["linhas_snapshot"] == 0
