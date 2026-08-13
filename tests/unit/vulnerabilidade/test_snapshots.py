"""BLK-MA-02: testes offline do materializador de snapshots semanais.

Fixtures 100% SINTÃ‰TICAS em `tmp_path` (CSVs com `sep=";"` / `encoding="utf-8-sig"`, coordenadas
reais do Brasil, nomes inventados). NENHUM teste le a fonte real -- ela e gitignored, vive na VPS
e carrega PII na origem (DEC-012).

Cobre: isolamento de import (AST), contrato de 10 colunas + `_assert_schema`, anti-PII provado
RELENDO o parquet do disco (inclusive nos bytes do arquivo), partiÃ§Ã£o por semana ISO e
idempotÃªncia, limpeza de ruido com auditoria sÃ³ de contagens, `hash_campos_raspados`, estabilidade
do `slug` / rebaixamento de chave, e poda de retencao.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from motor_expansao.vulnerabilidade import alvos_ma as malvos
from motor_expansao.vulnerabilidade import churn_staleness as mchurn
from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade import presenca_agregador as mpresenca
from motor_expansao.vulnerabilidade import pressao_competitiva as mpressao
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
                    # 3 boas (a Ãºltima junto a divisa de UF)
                    "Academia Boa Centro",
                    "Academia Boa Norte",
                    "Academia Boa Divisa",
                ],
                "latitude": [
                    -23.55,
                    0.0,
                    0.0,
                    -23.55,
                    -23.55,
                    -23.55,
                    -23.55,
                    -23.55,
                    -23.55,
                    -23.55,
                    -23.60,
                    -25.45,
                ],
                "longitude": [
                    -46.63,
                    0.0,
                    -20.0,
                    -46.63,
                    -46.63,
                    -46.63,
                    -46.63,
                    -46.63,
                    -46.63,
                    -46.63,
                    -46.70,
                    -53.20,
                ],
                "cidade": ["X"] * 12,
                "uf": [
                    "SP",
                    "SP",
                    "SP",
                    "AM",
                    "SP",
                    "SP",
                    "SP",
                    "SP",
                    "SP",
                    "SP",
                    "SP",
                    "SP",
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
# CA-1 â€” isolamento de imports (AST) sobre os 5 mÃ³dulos do pacote + o prÃ³prio pacote
# --------------------------------------------------------------------------- #
def test_isolamento_imports() -> None:
    """Pacote DISJUNTO: nenhum import pode casar M1/dashboard/api/censo/config raiz.

    O AST olha os IMPORTS reais, nunca a prosa do docstring (que cita os caminhos proibidos como
    guardrail). `normalizar_concorrentes` entra na lista: Ã© `_DENY_CRITICO` do loop_guard e a sua
    fÃ³rmula foi REPLICADA no `contrato`, jamais importada.

    Esta tupla Ã© a garantia COMPARTILHADA do pacote; ela **nÃ£o** proÃ­be `demanda_revelada` (nem
    poderia: `snapshots.py` o importa). A proibiÃ§Ã£o especÃ­fica dos mÃ³dulos do sinal 1 e do score
    vive em `test_presenca_agregador.py::test_modulo_nao_importa_demanda_revelada` e em
    `test_score.py::test_modulo_nao_importa_demanda_revelada`.
    """
    import motor_expansao.vulnerabilidade as pacote

    from .._ast_imports import casa_proibicao, nomes_importados

    for modulo in (pacote, c, m, mchurn, mpresenca, mscore, malvos, mpressao):
        for n in nomes_importados(modulo):
            # As checagens por SUBSTRING sÃ£o mantidas como estavam: sÃ£o mais amplas que
            # um prefixo (pegam `dashboard.censo_map`, por exemplo) e afrouxÃ¡-las para
            # caber num laÃ§o uniforme reduziria o guardrail.
            assert "pipelines.m1" not in n, (modulo.__name__, n)
            assert "censo" not in n, (modulo.__name__, n)
            assert "normalizar_concorrentes" not in n, (modulo.__name__, n)
            # Estas passam por `casa_proibicao` porque o import RELATIVO
            # (`from .. import dashboard`) deixa sÃ³ o alias no AST, e o `startswith`
            # anterior nÃ£o o via.
            for proibido in (
                "motor_expansao.dashboard",
                "motor_expansao.api",
                "motor_expansao.config",
            ):
                assert not casa_proibicao(n, proibido), (modulo.__name__, n, proibido)


def test_pacote_nao_carrega_dependencia_pesada() -> None:
    """Isolamento por `sys.modules`, nÃ£o por AST â€” o AST sÃ³ vÃª import DIRETO.

    O `test_isolamento_imports` fica verde mesmo quando isto falha, e as duas coisas sÃ£o
    verdadeiras ao mesmo tempo: o pacote nÃ£o escreve nenhum import proibido, mas o que ele
    importa pode arrastar meio mundo junto. Um mÃ³dulo destinado ao cron precisa das duas
    garantias â€” se `sklearn`/`scipy` nÃ£o estiverem no host do coletor, o passo quebra no import.

    Fechado pelo `BLK-MA-02-FU1` item 2: o `__init__` de `demanda_revelada` passou a reexportar
    por `__getattr__` (PEP 562). Antes disto: ~18 s, com sklearn/scipy/shapely/requests/pyproj e
    5 mÃ³dulos de `dashboard/`. Depois: ~3 s e nenhum dos dois.

    **O subprocesso precisa medir ESTE checkout.** Sem `PYTHONPATH` explÃ­cito ele resolveria
    `motor_expansao` pela instalaÃ§Ã£o editÃ¡vel â€” que aponta para o clone principal, nÃ£o para o
    worktree â€”, e o teste passaria a medir outra Ã¡rvore em silÃªncio. Aconteceu de verdade durante
    o desenvolvimento desta correÃ§Ã£o, daÃ­ a asserÃ§Ã£o de procedÃªncia abaixo.
    """
    import os
    import subprocess
    import sys
    import textwrap
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "src"
    assert (src / "motor_expansao").is_dir(), f"layout inesperado: {src}"

    codigo = textwrap.dedent(
        """
        import sys
        import motor_expansao.vulnerabilidade as alvo
        pesados = sorted(
            {m.split(".")[0] for m in sys.modules}
            & {"sklearn", "scipy", "shapely", "requests", "matplotlib", "geopandas", "pyproj"}
        )
        dash = [m for m in sys.modules if m.startswith("motor_expansao.dashboard")]
        print(";".join(pesados) + "|" + str(len(dash)) + "|" + alvo.__file__)
        """
    )
    # `stdin=DEVNULL` nÃ£o e' decorativo: sob a captura do pytest no Windows, o stdin herdado nÃ£o
    # tem descritor real e o `subprocess` levanta `OSError: [WinError 6]` antes de rodar qualquer
    # coisa. Enquanto este teste esteve marcado `xfail(strict=True)`, essa OSError contava como
    # "falha esperada" â€” ou seja, o teste ERRAVA em vez de medir, e ninguem tinha como perceber.
    env = {**os.environ, "PYTHONPATH": str(src)}
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        stdin=subprocess.DEVNULL,
    ).stdout.strip()
    pesados, n_dashboard, origem = saida.split("|")

    assert Path(origem).is_relative_to(src), (
        f"o subprocesso mediu OUTRA arvore ({origem}), nao este checkout ({src}) - "
        "a medicao seria sobre codigo que nao esta sob teste"
    )
    assert not pesados, f"dependencias pesadas carregadas: {pesados}"
    assert n_dashboard == "0", f"modulos de dashboard carregados: {n_dashboard}"


def test_checagem_de_import_pega_as_cinco_formas() -> None:
    """Sonda de injeÃ§Ã£o: a checagem de isolamento nÃ£o pode ter ponto cego.

    Antes da correÃ§Ã£o, das cinco formas de escrever o import proibido a checagem por
    AST pegava **2** e deixava passar **3**: `from motor_expansao import dashboard`
    (sÃ³ o pai entrava na lista), `from .. import dashboard` (o nÃ³ era descartado
    inteiro quando `node.module is None`) e `importlib.import_module(...)` (Ã© uma
    chamada, nÃ£o um nÃ³ de import).

    Este teste falha com a implementaÃ§Ã£o antiga e Ã© o que impede o guardrail de voltar
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
# CA-12 â€” nenhum teste do pacote aponta para caminho de fonte real
# --------------------------------------------------------------------------- #
def test_sem_caminho_real_nos_testes() -> None:
    """Os literais proibidos sÃ£o MONTADOS por concatenaÃ§Ã£o para nÃ£o se auto-acusarem."""
    proibidos = ["concorrentes" + "/", "data/" + "staging", "data/" + "outputs", "data/" + "raw"]
    for arquivo in sorted(Path(__file__).parent.glob("test_*.py")):
        tree = ast.parse(arquivo.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for proibido in proibidos:
                    assert proibido not in node.value, (arquivo.name, proibido)


def test_defaults_iguais_aos_da_ingestao_existente() -> None:
    """R6: os diretÃ³rios default NÃƒO podem divergir dos jÃ¡ usados pela ingestÃ£o densa."""
    from motor_expansao.demanda_revelada import concorrentes_densos as densos

    assert m.DIR_TOTALPASS_DEFAULT == densos.DIR_TOTALPASS_DEFAULT
    assert m.DIR_WELLHUB_DEFAULT == densos.DIR_WELLHUB_DEFAULT
    assert m.DIR_UNIDADES_DEFAULT == densos.DIR_UNIDADES_DEFAULT


# --------------------------------------------------------------------------- #
# CA-2 â€” contrato de 10 colunas + _assert_schema
# --------------------------------------------------------------------------- #
def test_schema_snapshot_12_colunas_em_ordem(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    assert list(snap.columns) == list(c.CONTRATO_COLUNAS_SNAPSHOT.keys())
    # 10 -> 12 no BLK-MA-09 / DEC-026: as duas colunas-fato de rating, sem peso.
    assert len(list(snap.columns)) == 12
    assert snap["nota_wellhub"].dtype == "Float64"
    assert snap["qtd_avaliacoes_wellhub"].dtype == "Int64"
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
# CA-3 â€” anti-PII provado RELENDO o parquet do disco
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
    # O literal nÃ£o pode sobreviver nem em metadado/estatÃ­stica de coluna do prÃ³prio arquivo.
    assert marcador.encode() not in arquivos[0].read_bytes()


# --------------------------------------------------------------------------- #
# CA-4 / CA-17 â€” partiÃ§Ã£o por semana ISO, idempotÃªncia e escrita defensiva
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
    """P1: a semana sai da EXECUÃ‡ÃƒO. Um CSV velho (coletor falho) nÃ£o reescreve semana passada."""
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
    """Prova do `delete_matching`: a 2a execuÃ§Ã£o SUBSTITUI a partiÃ§Ã£o, nÃ£o soma a ela."""
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
# CA-5 â€” limpeza de ruido com auditoria SÃ“ de contagens
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
    """Anti-PII: a auditoria carrega SÃ“ inteiros, jamais o texto ofensor."""
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
# CA-6 â€” hash_campos_raspados
# --------------------------------------------------------------------------- #
def _hash(df: pd.DataFrame) -> str:
    return str(m.calcular_hash_campos_raspados(df)["hash_campos_raspados"].iloc[0])


def test_hash_ignora_data_coleta() -> None:
    assert _hash(_frame_tp(data_coleta="2026-07-27")) == _hash(_frame_tp(data_coleta="2026-08-03"))


def test_hash_ignora_a_taxonomia_inteira() -> None:
    """Sucessor de `test_hash_ignora_ordem_das_modalidades` (emenda BLK-MA-11 / DEC-025).

    A versÃ£o anterior sÃ³ provava invariÃ¢ncia Ã  ORDEM dos tokens. Desde a emenda, a taxonomia saiu
    do hash por completo: trocar os prÃ³prios rÃ³tulos tambÃ©m nÃ£o pode mexer no hash. Motivo medido:
    o WellHub renomeou "MusculaÃ§Ã£o" para "Treino de forÃ§a"/"Fisiculturismo" e o campo mudou em
    99,1% das unidades sem que uma sÃ³ academia mudasse - com a taxonomia dentro, o sinal 4 morreria
    de uma vez para a base inteira.
    """
    base = _hash(_frame_tp(modalidades="Musculacao, Natacao"))
    assert base == _hash(_frame_tp(modalidades="Natacao; Musculacao")), "ordem"
    assert base == _hash(_frame_tp(modalidades="Treino de forca, Natacao")), "rotulo renomeado"
    assert base == _hash(_frame_tp(modalidades="")), "taxonomia ausente"


def test_hash_ignora_slug() -> None:
    """Rotacao de UUID no slug NÃƒO e mudanca de negocio."""
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
        # de ser "mudanÃ§a de cadastro". A invariÃ¢ncia agora Ã© asserida em
        # `test_hash_ignora_a_taxonomia_inteira`.
    ],
)
def test_hash_muda_com_campo_real(campo: str, valor: object) -> None:
    assert _hash(_frame_tp()) != _hash(_frame_tp(**{campo: valor}))


def test_hash_usa_o_conjunto_de_campos_da_propria_fonte() -> None:
    """O feed `unidades` hasheia `nome_unidade` (nÃ£o `nome`) + coordenadas."""
    base = _frame_tp(
        fonte="unidades", rede="selfit", nome="Selfit Norte", nome_unidade="Selfit Norte", slug=""
    )
    outro = base.copy()
    outro.loc[0, "cidade"] = "OUTRA CIDADE"  # fora de CAMPOS_HASH_POR_FONTE["unidades"]
    assert _hash(base) == _hash(outro)
    mudou = base.copy()
    mudou.loc[0, "nome_unidade"] = "Selfit Norte II"
    assert _hash(base) != _hash(mudou)


# --------------------------------------------------------------------------- #
# CA-7 â€” estabilidade do slug e rebaixamento auditavel da chave
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
    assert (
        m.derivar_chave(_frame_tp(), taxa_slug_persistente=float("nan"))["chave_origem"].iloc[0]
        == "slug"
    )
    assert m.derivar_chave(_frame_tp(), politica="hash_estavel")["chave_origem"].iloc[0] == (
        "hash_estavel"
    )
    with pytest.raises(ValueError, match="politica"):
        m.derivar_chave(_frame_tp(), politica="ordinal")


def test_chave_origem_slug_duplicado_no_snapshot() -> None:
    """Rebaixamento POR LINHA (sÃ³ informacao local da semana): slug repetido nÃ£o serve de chave."""
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
# CA-11 â€” poda de retencao (I/O DESTRUTIVA)
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
    """A poda APAGA disco: `materializar` nÃ£o pode alcanca-la em hipotese alguma."""

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
    assert set(tpwh["rede"]) == {"independente"}  # nomes sinteticos nÃ£o casam cadeia alguma


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


# --------------------------------------------------------------------------- #
# BLK-MA-09 / DEC-026 â€” colunas-fato de rating, sem peso
# --------------------------------------------------------------------------- #
def test_ler_snapshots_sobrevive_a_esquema_misto(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """O teste que justifica o `schema=` explÃ­cito em `ler_snapshots`.

    Um bump de contrato produz, por definiÃ§Ã£o, uma sÃ©rie com partiÃ§Ãµes de esquemas diferentes.
    Sem schema declarado o pyarrow infere o do PRIMEIRO arquivo: se a partiÃ§Ã£o antiga for lida
    primeiro, as colunas novas somem de TODAS as outras, e o laÃ§o de preenchimento as recria como
    `pd.NA` â€” coluna nula para o universo inteiro, sem erro e sem log. Aqui a partiÃ§Ã£o prÃ©-bump Ã©
    a mais antiga E a primeira em ordem alfabÃ©tica, que Ã© a ordem em que o dataset varre.
    """
    base = tmp_path / "serie"
    snap = _snapshot_valido(dirs_sinteticos)

    # Semana 1: PRÃ‰-bump â€” grava sem as duas colunas novas, como faria o contrato v2.
    pre = snap.drop(columns=["nota_wellhub", "qtd_avaliacoes_wellhub"]).copy()
    pre["semana"] = "2026-01"
    dir_pre = base / "semana=2026-01"
    dir_pre.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pandas(pre.drop(columns=["semana"]), preserve_index=False),
        str(dir_pre / "parte-0.parquet"),
    )

    # Semana 2: PÃ“S-bump, com nota preenchida.
    pos = snap.copy()
    pos.loc[:, "nota_wellhub"] = 4.25
    pos.loc[:, "qtd_avaliacoes_wellhub"] = 88
    m.escrever_particao_semana(pos, base, semana="2026-02")

    lido = m.ler_snapshots(base)

    assert set(lido["semana"]) == {"2026-01", "2026-02"}
    antigo = lido[lido["semana"] == "2026-01"]
    novo = lido[lido["semana"] == "2026-02"]
    assert antigo["nota_wellhub"].isna().all(), "partiÃ§Ã£o prÃ©-bump deveria ficar nula"
    # `notna()` ANTES da comparaÃ§Ã£o, e nÃ£o `(sÃ©rie == 4.25).all()`: numa sÃ©rie toda-NA o `.all()`
    # de pandas ignora os nulos e devolve `True`, entÃ£o a versÃ£o ingÃªnua deste teste passaria
    # exatamente no cenÃ¡rio que ele existe para pegar. Medido: sem o `schema=` em
    # `ler_snapshots`, a coluna volta 100% nula e a asserÃ§Ã£o ingÃªnua fica verde.
    assert novo["nota_wellhub"].notna().all(), (
        "a partiÃ§Ã£o pÃ³s-bump perdeu a nota â€” o schema do primeiro arquivo venceu"
    )
    assert (novo["nota_wellhub"] == 4.25).all()
    assert novo["qtd_avaliacoes_wellhub"].notna().all()
    assert (novo["qtd_avaliacoes_wellhub"] == 88).all()


def _dirs_com_rating(tmp_path: Path, notas: list[str], qtds: list[str]) -> tuple[Path, Path, Path]:
    """3 pastas de CSV em que o feed WellHub CARREGA as colunas de rating, como no coletor real.

    A fixture `dirs_sinteticos` nÃ£o tem essas colunas â€” por isso os testes que se apoiavam nela
    asseriam as 12 colunas com a nota 100% nula e passavam mesmo quando a ingestÃ£o era removida.
    """
    tp, wh, un = tmp_path / "tp", tmp_path / "wh", tmp_path / "un"
    n = len(notas)
    _escrever_csv(
        wh / "unidades_wellhub_rj.csv",
        pd.DataFrame(
            {
                "slug": [f"academia-{i}" for i in range(n)],
                "nome": [f"Academia {i}" for i in range(n)],
                "latitude": [-22.91 - i * 0.01 for i in range(n)],
                "longitude": [-43.18 - i * 0.01 for i in range(n)],
                "cidade": ["Rio de Janeiro"] * n,
                "uf": ["RJ"] * n,
                "cep": ["20000-000"] * n,
                "endereco_formatado": [f"Rua {i}, 100" for i in range(n)],
                "atividades": ["Musculacao"] * n,
                "nota_wellhub": notas,
                "qtd_avaliacoes_wellhub": qtds,
                "data_coleta": ["2026-07-26"] * n,
            }
        ),
    )
    for d in (tp, un):
        d.mkdir(parents=True, exist_ok=True)
    return tp, wh, un


def test_tres_estados_do_rating_sobrevivem_a_INGESTAO_do_csv(tmp_path: Path) -> None:
    """Os trÃªs estados da DEC-024 pelo caminho REAL: CSV -> `materializar` -> snapshot.

    A versÃ£o anterior deste teste montava os trÃªs estados Ã  mÃ£o sobre um frame jÃ¡ materializado e
    sÃ³ chamava `_assert_schema_snapshot` â€” era tautolÃ³gica. Sonda de mutaÃ§Ã£o provou: apagar as duas
    colunas de `_COLUNAS_TRABALHO` (o rating nunca Ã© lido do CSV) deixava a suÃ­te inteira verde.
    """
    tp, wh, un = _dirs_com_rating(tmp_path, ["4.81", "", ""], ["105", "0", ""])
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    snap = snap.sort_values("slug").reset_index(drop=True)

    assert snap["nota_wellhub"].dtype == "Float64"
    assert snap["qtd_avaliacoes_wellhub"].dtype == "Int64"
    # tem nota
    assert snap.loc[0, "nota_wellhub"] == 4.81
    assert snap.loc[0, "qtd_avaliacoes_wellhub"] == 105
    # sem avaliaÃ§Ãµes: a contagem `0` Ã© o que o distingue de "nÃ£o lido"
    assert pd.isna(snap.loc[1, "nota_wellhub"])
    assert snap.loc[1, "qtd_avaliacoes_wellhub"] == 0
    # nÃ£o lido (parser quebrado)
    assert pd.isna(snap.loc[2, "nota_wellhub"])
    assert pd.isna(snap.loc[2, "qtd_avaliacoes_wellhub"])
    assert auditoria["rating_ilegivel"] == 0


def test_contagem_nao_inteira_nao_aborta_a_semana(tmp_path: Path) -> None:
    """O crÃ­tico: uma cÃ©lula ruim NÃƒO pode custar a semana inteira.

    `pd.to_numeric("1.262")` devolve `1.262`, e um `.astype("Int64")` direto levanta
    `TypeError: cannot safely cast non-equivalent`. Como `montar_snapshot` roda antes de gravar e o
    `run_weekly_90.sh` sobrescreve os CSVs a cada coleta, a exceÃ§Ã£o nÃ£o perderia uma linha â€” perderia
    a semana, para sempre. `1.262` Ã© como a UI pt-BR renderiza 1262, e contagem de 4 dÃ­gitos existe
    no universo (a DEC-024 cita "4,73 com 1.262").
    """
    tp, wh, un = _dirs_com_rating(tmp_path, ["4.81", "4.70"], ["1.262", "88"])
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    snap = snap.sort_values("slug").reset_index(drop=True)

    # A cÃ©lula ilegÃ­vel degrada para "nÃ£o lido"; a linha sÃ£ ao lado Ã© preservada.
    assert pd.isna(snap.loc[0, "qtd_avaliacoes_wellhub"])
    assert snap.loc[1, "qtd_avaliacoes_wellhub"] == 88
    # E a degradaÃ§Ã£o Ã© VISÃVEL, nÃ£o silenciosa.
    assert auditoria["rating_ilegivel"] == 1


def test_quarto_estado_vira_nao_lido_e_e_contado(tmp_path: Path) -> None:
    """Nota ilegÃ­vel com contagem legÃ­vel nÃ£o existe na DEC-024 â€” nÃ£o pode virar "sem avaliaÃ§Ãµes".

    Ã‰ o que uma troca de locale no `value` produziria (`4,81` nÃ£o parseia, `105` parseia). Deixar
    passar faria uma quebra de parser entrar no funil disfarÃ§ada de academia sem avaliaÃ§Ã£o.
    """
    tp, wh, un = _dirs_com_rating(tmp_path, ["4,81"], ["105"])
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)

    assert pd.isna(snap.loc[0, "nota_wellhub"])
    assert pd.isna(snap.loc[0, "qtd_avaliacoes_wellhub"]), (
        "virou 'sem avaliacoes' em vez de 'nao lido'"
    )
    assert auditoria["rating_ilegivel"] == 1


def test_assert_schema_rejeita_rating_fora_do_dominio(tmp_path: Path) -> None:
    """Rede para frames montados Ã  mÃ£o â€” que Ã© como boa parte desta camada constrÃ³i insumo."""
    tp, wh, un = _dirs_com_rating(tmp_path, ["4.81"], ["105"])
    base, _ = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)

    ruim = base.copy()
    ruim.loc[0, "nota_wellhub"] = 42.0
    with pytest.raises(ValueError, match=r"nota_wellhub fora de"):
        m._assert_schema_snapshot(ruim)

    # `0.0` Ã© o retorno natural de um parser quebrado e o piso do domÃ­nio Ã© `1.0`, nÃ£o `0.0`.
    ruim = base.copy()
    ruim.loc[0, "nota_wellhub"] = 0.0
    with pytest.raises(ValueError, match=r"nota_wellhub fora de"):
        m._assert_schema_snapshot(ruim)

    ruim = base.copy()
    ruim.loc[0, "qtd_avaliacoes_wellhub"] = -7
    with pytest.raises(ValueError, match="negativa"):
        m._assert_schema_snapshot(ruim)

    ruim = base.copy()
    ruim.loc[0, "nota_wellhub"] = pd.NA  # nota ausente com qtd = 105 -> o quarto estado
    with pytest.raises(ValueError, match="rating incoerente"):
        m._assert_schema_snapshot(ruim)

    # Nota presente com ZERO avaliaÃ§Ãµes: nÃ£o hÃ¡ avaliaÃ§Ã£o que sustente a mÃ©dia.
    ruim = base.copy()
    ruim.loc[0, "qtd_avaliacoes_wellhub"] = 0
    with pytest.raises(ValueError, match="rating incoerente"):
        m._assert_schema_snapshot(ruim)

    # Nota presente com contagem ausente: o terceiro par que a DEC-024 nÃ£o prevÃª.
    ruim = base.copy()
    ruim.loc[0, "qtd_avaliacoes_wellhub"] = pd.NA
    with pytest.raises(ValueError, match="rating incoerente"):
        m._assert_schema_snapshot(ruim)


@pytest.mark.parametrize("nota_ruim", ["9.9", "481", "-1.0", "0.0"])
def test_nota_fora_do_dominio_nao_aborta_a_semana(tmp_path: Path, nota_ruim: str) -> None:
    """A assimetria que o PR original deixou: `1.262` degradava, mas `9.9` LEVANTAVA.

    As duas cÃ©lulas chegam pelo mesmo caminho (CSV do coletor -> `montar_snapshot`, que roda ANTES
    de gravar) e tÃªm a mesma consequÃªncia: como o `run_weekly_90.sh` sobrescreve os CSVs crus a cada
    coleta, a exceÃ§Ã£o nÃ£o perde uma linha â€” perde a semana inteira, para sempre.

    `481` Ã© `4.81` sem o separador decimal; `0.0`, o default de um parser que nÃ£o achou o campo.
    """
    tp, wh, un = _dirs_com_rating(tmp_path, [nota_ruim, "4.70"], ["105", "88"])
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    snap = snap.sort_values("slug").reset_index(drop=True)

    assert pd.isna(snap.loc[0, "nota_wellhub"]), f"{nota_ruim} entrou na serie como nota legitima"
    assert pd.isna(snap.loc[0, "qtd_avaliacoes_wellhub"]), "par sobrou fora dos tres estados"
    # A linha sÃ£ ao lado sobrevive: a degradaÃ§Ã£o Ã© por cÃ©lula, nÃ£o por semana.
    assert snap.loc[1, "nota_wellhub"] == 4.70
    assert snap.loc[1, "qtd_avaliacoes_wellhub"] == 88
    assert auditoria["rating_ilegivel"] == 1


def test_contagem_negativa_nao_aborta_a_semana(tmp_path: Path) -> None:
    """Mesma assimetria, na outra coluna: contagem negativa levantava em vez de degradar."""
    tp, wh, un = _dirs_com_rating(tmp_path, ["4.81", "4.70"], ["-7", "88"])
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    snap = snap.sort_values("slug").reset_index(drop=True)

    assert pd.isna(snap.loc[0, "qtd_avaliacoes_wellhub"])
    assert snap.loc[1, "qtd_avaliacoes_wellhub"] == 88
    assert auditoria["rating_ilegivel"] == 1


def test_nota_zero_com_zero_avaliacoes_vira_SEM_AVALIACOES(tmp_path: Path) -> None:
    """O caso que mais engana: `0.0`/`0` passava como "tem nota 0,0", que nÃ£o Ã© estado nenhum.

    Ã‰ o que um extrator quebrado produz sobre uma unidade que de fato nÃ£o tem avaliaÃ§Ã£o. O destino
    correto Ã© "sem avaliaÃ§Ãµes" (`NA`/`0`) â€” e Ã© a ORDEM das regras em `_coagir_rating` (domÃ­nio
    antes do par) que o garante: a nota morre no domÃ­nio, e o par `NA`/`0` que sobra jÃ¡ Ã© vÃ¡lido.
    """
    tp, wh, un = _dirs_com_rating(tmp_path, ["0.0"], ["0"])
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)

    assert pd.isna(snap.loc[0, "nota_wellhub"])
    assert snap.loc[0, "qtd_avaliacoes_wellhub"] == 0, "virou 'nao lido' em vez de 'sem avaliacoes'"
    assert auditoria["rating_ilegivel"] == 1


def test_nota_com_zero_avaliacoes_vira_nao_lido(tmp_path: Path) -> None:
    """Nota boa com contagem `0`: nÃ£o existe mÃ©dia de zero avaliaÃ§Ãµes â€” o par Ã© impossÃ­vel."""
    tp, wh, un = _dirs_com_rating(tmp_path, ["4.81"], ["0"])
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)

    assert pd.isna(snap.loc[0, "nota_wellhub"])
    assert pd.isna(snap.loc[0, "qtd_avaliacoes_wellhub"])
    assert auditoria["rating_ilegivel"] == 1


def test_bordas_do_dominio_da_nota_sao_aceitas(tmp_path: Path) -> None:
    """`1.0` e `5.0` sÃ£o notas REAIS (DEC-026: `min = 1,0`), nÃ£o devem degradar."""
    tp, wh, un = _dirs_com_rating(tmp_path, ["1.0", "5.0"], ["3", "9"])
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    snap = snap.sort_values("slug").reset_index(drop=True)

    assert snap.loc[0, "nota_wellhub"] == 1.0
    assert snap.loc[1, "nota_wellhub"] == 5.0
    assert auditoria["rating_ilegivel"] == 0


def test_uma_linha_degradada_conta_UMA_vez(tmp_path: Path) -> None:
    """`9.9`/`105` aciona domÃ­nio E par. A auditoria conta LINHAS, senÃ£o inflaria o alarme."""
    tp, wh, un = _dirs_com_rating(tmp_path, ["9.9"], ["105"])
    _, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)

    assert auditoria["rating_ilegivel"] == 1


def test_montar_snapshot_vazio_respeita_os_dtypes_do_contrato(tmp_path: Path) -> None:
    """O ramo vazio tipava as 12 colunas como `string`, contra o prÃ³prio contrato.

    O gÃªmeo `_frame_snapshot_vazio` foi corrigido no mesmo diff e a docstring dele diz por quÃª
    ("um frame vazio mal tipado quebraria o `concat` da sÃ©rie"); este ramo tinha ficado para trÃ¡s.
    """
    vazio, auditoria = m.montar_snapshot(pd.DataFrame())
    assert vazio["nota_wellhub"].dtype == "Float64"
    assert vazio["qtd_avaliacoes_wellhub"].dtype == "Int64"
    assert dict(vazio.dtypes.astype(str)) == dict(c.CONTRATO_COLUNAS_SNAPSHOT)
    assert auditoria["rating_ilegivel"] == 0


def test_nota_nao_entra_no_hash_e_o_s4_sobrevive() -> None:
    """Guardrail inviolÃ¡vel da DEC-026: a nota oscila entre coletas e mataria a staleness.

    Medido no smoke do BLK-MA-08: uma unidade saiu de `4,81`/`105` para `4,76`/`97` entre duas
    coletas. Se isso entrasse no hash, `semanas_sem_mudanca` nunca sairia de 0 para nenhuma
    academia avaliada â€” o sinal 4 morreria em silÃªncio para o universo inteiro.
    """
    assert "nota_wellhub" not in c.CAMPOS_HASH_POR_FONTE["wellhub"]
    assert "qtd_avaliacoes_wellhub" not in c.CAMPOS_HASH_POR_FONTE["wellhub"]

    base = _frame_tp(fonte="wellhub", slug="academia-x")
    base["nota_wellhub"] = 4.81
    base["qtd_avaliacoes_wellhub"] = 105
    oscilou = base.copy()
    oscilou["nota_wellhub"] = 4.76
    oscilou["qtd_avaliacoes_wellhub"] = 97

    assert _hash(base) == _hash(oscilou), "a nota mudou o hash: o S4 morreria na prÃ³xima coleta"


def test_particao_toda_nula_nasce_com_o_tipo_do_contrato(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Trava a alegaÃ§Ã£o do `schema=` na ESCRITA, que antes era cÃ³digo defensivo nÃ£o exercitado.

    Sem ele, uma semana em que ninguÃ©m tem nota gravaria `nota_wellhub` como tipo Arrow `null` (o
    pandas nÃ£o tem o que inferir), e a sÃ©rie passaria a misturar `null` com `double` entre semanas.
    """
    base = tmp_path / "serie"
    snap = _snapshot_valido(dirs_sinteticos)  # a fixture nÃ£o tem rating -> colunas 100% nulas
    assert snap["nota_wellhub"].isna().all()

    caminho = m.escrever_particao_semana(snap, base, semana="2026-31")
    arquivo = next(caminho.glob("*.parquet"))
    schema = pq.read_schema(arquivo)

    assert schema.field("nota_wellhub").type == pa.float64()
    assert schema.field("qtd_avaliacoes_wellhub").type == pa.int64()


# --------------------------------------------------------------------------- #
# BLK-MA-02-FU1 (menores m1, m2, m3, m6) â€” ressalvas do QA de 2026-07-29
# --------------------------------------------------------------------------- #
def test_m6_dry_run_nao_grava_e_nao_poda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """m6: `--dry-run` roda o caminho inteiro sem tocar disco â€” nem grava, nem PODA.

    Este Ã© o Ãºnico ponto do pacote que APAGA arquivo, e Ã© o que vai ao cron da VPS (BLK-MA-06).
    Antes desta correÃ§Ã£o, `python -m ...snapshots` chamava `executar()` sem argumento nenhum:
    gravava na raiz de staging default e podava, sem `--base-dir` e sem modo seco.
    """
    tp, wh, un = tmp_path / "tp", tmp_path / "wh", tmp_path / "un"
    for d in (tp, wh, un):
        d.mkdir(parents=True, exist_ok=True)
    base = tmp_path / "serie"
    # Uma partiÃ§Ã£o ANTIGA, muito alÃ©m da retenÃ§Ã£o: seria podada numa execuÃ§Ã£o de verdade.
    antiga = base / "semana=2020-01"
    antiga.mkdir(parents=True)
    (antiga / "parte-0.parquet").write_bytes(b"nao e' parquet valido, e nao precisa ser")

    podou: list[object] = []
    monkeypatch.setattr(m, "podar_snapshots", lambda *a, **k: podou.append(a) or [])

    auditoria = m.executar(tp, wh, un, base_dir=base, data_referencia=REF, dry_run=True)

    assert auditoria["dry_run"] is True
    assert auditoria["semanas_removidas"] == 0
    assert not podou, "dry-run chamou a poda"
    assert (antiga / "parte-0.parquet").exists(), "dry-run apagou particao existente"
    assert not (base / f"semana={c.derivar_semana_iso(REF)}").exists(), "dry-run gravou particao"


def test_m6_cli_analisa_os_argumentos_do_cron() -> None:
    """m6: os flags que o cron precisa existem e chegam com o tipo certo."""
    args = m._parse_args(
        ["--base-dir", "/tmp/serie", "--data-referencia", "2026-07-29", "--dry-run"]
    )
    assert args.base_dir == Path("/tmp/serie")
    assert args.data_referencia == date(2026, 7, 29)
    assert args.dry_run is True
    assert args.retencao_semanas == c.RETENCAO_SEMANAS

    padrao = m._parse_args([])
    assert padrao.dry_run is False, "dry-run nao pode ser o default: o cron precisa gravar"
    assert padrao.data_referencia is None


def test_m1_frame_vazio_preserva_a_particao_existente(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """m1: zero linha Ã© sintoma de COLETA FALHA, nÃ£o de universo vazio â€” nÃ£o pode apagar a sÃ©rie.

    O docstring prometia idempotÃªncia "mesmo quando a semana encolhe"; para o encolhimento TOTAL
    isso nÃ£o valia, e o comportamento (seguro) nÃ£o tinha teste que o travasse.
    """
    base = tmp_path / "serie"
    cheio = _snapshot_valido(dirs_sinteticos)
    caminho = m.escrever_particao_semana(cheio, base, semana="2026-31")
    antes = sorted(p.name for p in caminho.glob("*.parquet"))
    assert antes, "pre-condicao: a particao foi gravada"

    vazio = cheio.iloc[0:0]
    devolvido = m.escrever_particao_semana(vazio, base, semana="2026-31")

    assert devolvido == caminho
    assert sorted(p.name for p in caminho.glob("*.parquet")) == antes, (
        "frame vazio apagou a particao â€” trocaria falha transitoria por perda permanente"
    )


def test_m1_frame_vazio_em_semana_inedita_nao_cria_diretorio(tmp_path: Path) -> None:
    """m1: e o caminho devolvido pode NÃƒO existir â€” estÃ¡ no docstring, agora estÃ¡ travado."""
    base = tmp_path / "serie"
    vazio = m._frame_snapshot_vazio(com_semana=False)

    devolvido = m.escrever_particao_semana(vazio, base, semana="2026-31")

    assert devolvido == base / "semana=2026-31"
    assert not devolvido.exists()


def test_m3_campo_nunca_hasheado_levanta_em_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """m3: `CAMPOS_NUNCA_HASHEADOS` era sÃ³ prosa â€” injetar `data_coleta` nÃ£o levantava nada.

    O efeito seria mudo e fatal: todo cadastro pareceria alterado a cada coleta,
    `semanas_sem_mudanca` nunca cresceria e o S4 morreria.
    """
    proibido = sorted(c.CAMPOS_NUNCA_HASHEADOS)[0]
    envenenado = dict(c.CAMPOS_HASH_POR_FONTE)
    envenenado["wellhub"] = (*c.CAMPOS_HASH_POR_FONTE["wellhub"], proibido)
    monkeypatch.setattr(c, "CAMPOS_HASH_POR_FONTE", envenenado)

    with pytest.raises(ValueError, match="CAMPOS_NUNCA_HASHEADOS"):
        c.hash_campos_raspados({"nome": "Academia X", proibido: "2026-08-11"}, "wellhub")


def test_m3_contrato_vigente_passa_pela_guarda_nova() -> None:
    """m3: a guarda nÃ£o pode quebrar as fontes reais â€” nenhuma hasheia campo proibido hoje."""
    for fonte in sorted(c.CAMPOS_HASH_POR_FONTE):
        assert c.hash_campos_raspados({"nome": "Academia X"}, fonte)


def test_m2_montar_snapshot_nao_recebe_mais_data_referencia() -> None:
    """m2: o parÃ¢metro era morto e sugeria que o `snapshot_date` saÃ­a dele. NÃ£o saÃ­a."""
    import inspect

    assert list(inspect.signature(m.montar_snapshot).parameters) == ["df"]


# --------------------------------------------------------------------------- #
# BLK-MA-06 â€” recorte de fontes por CADÃŠNCIA de coleta
# --------------------------------------------------------------------------- #
def test_fontes_restringe_o_feed_lido(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    """O cron semanal fotografa sÃ³ `unidades` â€” os agregadores nÃ£o sÃ£o recoletados toda semana.

    Este Ã© o nÃºcleo do BLK-MA-06: fotografar um feed estagnado Ã© PIOR que nÃ£o fotografar, porque o
    `hash_campos_raspados` sai idÃªntico toda semana e o S4 marcaria o universo inteiro daquela
    fonte como "parado" â€” o prÃ³prio sinal de vulnerabilidade.
    """
    tp, wh, un = dirs_sinteticos

    todas = m.ler_feeds(tp, wh, un)
    assert set(todas["fonte"]) == {"totalpass", "wellhub", "unidades"}, "pre-condicao da fixture"

    so_unidades = m.ler_feeds(tp, wh, un, fontes=["unidades"])
    assert set(so_unidades["fonte"]) == {"unidades"}
    assert len(so_unidades) < len(todas)

    so_agregadores = m.ler_feeds(tp, wh, un, fontes=["totalpass", "wellhub"])
    assert set(so_agregadores["fonte"]) == {"totalpass", "wellhub"}
    # As duas metades reconstroem o todo: o recorte nÃ£o perde nem duplica linha.
    assert len(so_unidades) + len(so_agregadores) == len(todas)


def test_fontes_invalida_levanta(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    """Fonte fora do contrato nÃ£o pode virar recorte silencioso de zero linha."""
    tp, wh, un = dirs_sinteticos
    with pytest.raises(ValueError, match="fonte fora do contrato"):
        m.ler_feeds(tp, wh, un, fontes=["unidade"])  # singular: erro de digitaÃ§Ã£o plausÃ­vel
    with pytest.raises(ValueError, match="nao ha o que ler"):
        m.ler_feeds(tp, wh, un, fontes=[])


def test_materializar_propaga_fontes_e_audita_o_recorte(
    dirs_sinteticos: tuple[Path, Path, Path],
) -> None:
    """O recorte tem de ficar VISÃVEL na auditoria.

    Quem ler a sÃ©rie meses depois precisa saber que as semanas antigas sÃ³ tinham `unidades`, sob
    pena de interpretar a ausÃªncia de agregador como churn.
    """
    tp, wh, un = dirs_sinteticos

    snap, auditoria = m.materializar(
        tp, wh, un, data_referencia=REF, escrever=False, fontes=["unidades"]
    )

    assert set(snap["fonte"]) == {"unidades"}
    assert auditoria["fontes_lidas"] == ["unidades"]

    _, auditoria_todas = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    assert auditoria_todas["fontes_lidas"] == ["totalpass", "unidades", "wellhub"]


def test_cli_aceita_fontes_do_cron_semanal() -> None:
    """`--fontes unidades` Ã© o que a linha do cron vai passar."""
    args = m._parse_args(["--fontes", "unidades"])
    assert args.fontes == ["unidades"]

    assert m._parse_args([]).fontes is None, "default = todos os feeds"

    with pytest.raises(SystemExit):
        m._parse_args(["--fontes", "gympass"])  # nome antigo do WellHub: erro plausÃ­vel
