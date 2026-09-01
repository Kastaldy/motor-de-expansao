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
from motor_expansao.vulnerabilidade import curadoria_agregadores as mcuradoria
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

    for modulo in (pacote, c, m, mchurn, mpresenca, mscore, malvos, mpressao, mcuradoria):
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
def test_schema_snapshot_13_colunas_em_ordem(dirs_sinteticos: tuple[Path, Path, Path]) -> None:
    tp, wh, un = dirs_sinteticos
    snap, auditoria = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    assert list(snap.columns) == list(c.CONTRATO_COLUNAS_SNAPSHOT.keys())
    # 10 -> 12 no BLK-MA-09 / DEC-026 (as duas colunas-fato de rating, sem peso);
    # 12 -> 13 no BLK-MA-21 / DEC-039 (`fontes_lidas`, o recorte que a execucao pediu).
    assert len(list(snap.columns)) == 13
    assert (snap["fontes_lidas"] == "totalpass,unidades,wellhub").all()
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

    # `rglob`: desde o BLK-MA-21 os arquivos vivem em `semana=X/fonte=Y/`, nao soltos na semana.
    arquivos = sorted((base / f"semana={SEMANA_REF}").rglob("parte-*.parquet"))
    assert arquivos, "a particao da semana deveria ter ao menos um parte-*.parquet"

    relido = pd.read_parquet(arquivos[0])
    assert not (set(relido.columns) & c.COLUNAS_PII_PROIBIDAS)
    # 12 colunas FISICAS, nao as 13 do contrato: quando `fonte` virou a segunda chave de particao,
    # o pyarrow passou a remove-la de DENTRO do arquivo e a materializa-la a partir do caminho
    # (medido em 23.0.1). As 13 voltam por `ler_snapshots`, que declara as duas chaves; quem le uma
    # folha com `pd.read_parquet` cru nao ve `fonte` -- e nenhum codigo de producao faz isso.
    esperado_fisico = [k for k in c.CONTRATO_COLUNAS_SNAPSHOT if k != "fonte"]
    assert list(relido.columns) == esperado_fisico
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
    # Arvore de DUAS chaves (BLK-MA-21): uma folha `fonte=` por feed, e nenhum `parte-*.parquet`
    # solto no diretorio da semana (esse e' o layout LEGADO, que a escrita passou a recusar).
    assert sorted(p.name for p in particao.iterdir()) == [
        "fonte=totalpass",
        "fonte=unidades",
        "fonte=wellhub",
    ]
    assert not list(particao.glob("parte-*.parquet"))
    for folha in particao.iterdir():
        assert sorted(p.name for p in folha.glob("parte-*.parquet"))
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


def test_reescrita_encolhe_a_folha_e_preserva_as_irmas(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """A idempotencia passou a ser por FOLHA, nao por particao (BLK-MA-21 / DEC-039).

    Com UMA chave de particao, `delete_matching` casava a semana inteira: a execucao dos
    agregadores (terca) apagava o que a do `unidades` (domingo) tinha acabado de gravar na mesma
    semana ISO. Aqui a segunda execucao so' traz o TotalPass -- a folha `fonte=totalpass` encolhe
    de 2 para 2 (mesmo conteudo) e as folhas irmas `fonte=wellhub` e `fonte=unidades` SOBREVIVEM.
    """
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "snapshots"
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)
    assert len(m.ler_snapshots(base)) == 6

    # Segunda execucao com um SUBCONJUNTO do TotalPass: a folha dele encolhe de 2 para 1.
    tp_menor = tmp_path / "tp_menor"
    _escrever_csv(
        tp_menor / "unidades_totalpass_sp.csv",
        pd.DataFrame(
            {
                "slug": ["academia-alfa"],
                "nome": ["Academia Alfa"],
                "latitude": [-23.5500],
                "longitude": [-46.6300],
                "cidade": ["Sao Paulo"],
                "uf": ["SP"],
                "cep": ["01000-000"],
                "endereco_formatado": ["Rua A, 100"],
                "modalidades": ["Musculacao"],
                "data_coleta": ["2026-07-27"],
            }
        ),
    )
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    m.materializar(tp_menor, vazio, vazio, base_dir=base, data_referencia=REF, fontes=["totalpass"])

    serie = m.ler_snapshots(base)
    por_fonte = serie["fonte"].astype(str).value_counts().to_dict()
    assert por_fonte == {"totalpass": 1, "wellhub": 2, "unidades": 2}, (
        "a reescrita do TotalPass tocou folha irma: o defeito que este bloco existe para matar"
    )
    assert len(serie) == 5


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


def test_podar_mantem_a_retencao_configurada(tmp_path: Path) -> None:
    """Keep-newest-N sobre `RETENCAO_SEMANAS`, sem depender do LITERAL da constante.

    Antes este teste cravava `26` no nome e nas asserçoes, e por isso quebrava a cada revisao de
    retencao por um motivo que nada tinha a ver com a poda. O que ele existe para travar e' a
    semantica (as N mais NOVAS ficam), nao o valor -- esse e' travado em `test_churn_staleness.py`.
    """
    base = tmp_path / "snapshots"
    _criar_semanas(base, c.RETENCAO_SEMANAS + 4)
    removidas = m.podar_snapshots(base, c.RETENCAO_SEMANAS)
    assert removidas == ["2026-01", "2026-02", "2026-03", "2026-04"]
    restantes = sorted(p.name for p in base.iterdir())
    assert len(restantes) == c.RETENCAO_SEMANAS
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

    # Semana 1: PRÃ‰-bump â€” grava sem as duas colunas novas, como faria o contrato v2. A folha
    # `fonte=` e' escrita a mao porque o proposito e' simular um arquivo de OUTRA safra.
    pre = snap.drop(columns=["nota_wellhub", "qtd_avaliacoes_wellhub"]).copy()
    for fonte, bloco in pre.groupby("fonte", sort=True):
        dir_pre = base / "semana=2026-01" / f"fonte={fonte}"
        dir_pre.mkdir(parents=True)
        pq.write_table(
            pa.Table.from_pandas(bloco.drop(columns=["fonte"]), preserve_index=False),
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
    vazio, auditoria = m.montar_snapshot(pd.DataFrame(), fontes_lidas="unidades")
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
    arquivo = next(caminho.rglob("*.parquet"))  # `rglob`: os arquivos vivem sob `fonte=`
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
    # A migracao de layout APAGA arquivo: ela tem de ser um ato explicito, nunca o default.
    assert padrao.migrar_layout is False
    assert m._parse_args(["--migrar-layout"]).migrar_layout is True


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
    # `rglob`: desde o BLK-MA-21 os arquivos vivem sob a folha `fonte=`, nao soltos na semana.
    antes = sorted(str(p.relative_to(caminho)) for p in caminho.rglob("*.parquet"))
    assert antes, "pre-condicao: a particao foi gravada"

    vazio = cheio.iloc[0:0]
    devolvido = m.escrever_particao_semana(vazio, base, semana="2026-31")

    assert devolvido == caminho
    assert sorted(str(p.relative_to(caminho)) for p in caminho.rglob("*.parquet")) == antes, (
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
    """m2: o parÃ¢metro era morto e sugeria que o `snapshot_date` saÃ­a dele. NÃ£o saÃ­a.

    `fontes_lidas` (BLK-MA-21) entra pelo motivo OPOSTO: e' kwarg obrigatorio e SEM default,
    porque um default o tornaria adivinhavel -- exatamente o que a coluna existe para impedir.
    """
    import inspect

    assinatura = inspect.signature(m.montar_snapshot)
    assert list(assinatura.parameters) == ["df", "fontes_lidas"]
    parametro = assinatura.parameters["fontes_lidas"]
    assert parametro.kind is inspect.Parameter.KEYWORD_ONLY
    assert parametro.default is inspect.Parameter.empty, "`fontes_lidas` nao pode ter default"


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

    Quem ler a sÃ©rie semanas depois precisa saber que as semanas antigas sÃ³ tinham `unidades`, sob
    pena de interpretar a ausÃªncia de agregador como churn.
    """
    tp, wh, un = dirs_sinteticos

    snap, auditoria = m.materializar(
        tp, wh, un, data_referencia=REF, escrever=False, fontes=["unidades"]
    )

    assert set(snap["fonte"]) == {"unidades"}
    # A auditoria passou de LISTA para a MESMA STRING que vai ao parquet (BLK-MA-21): ela e'
    # calculada uma vez e reusada nos dois lugares, para nao poder divergir do que foi gravado.
    assert auditoria["fontes_lidas"] == "unidades"
    assert (snap["fontes_lidas"] == "unidades").all()

    _, auditoria_todas = m.materializar(tp, wh, un, data_referencia=REF, escrever=False)
    assert auditoria_todas["fontes_lidas"] == "totalpass,unidades,wellhub"


def test_cli_aceita_fontes_do_cron_semanal() -> None:
    """`--fontes unidades` Ã© o que a linha do cron vai passar."""
    args = m._parse_args(["--fontes", "unidades"])
    assert args.fontes == ["unidades"]

    assert m._parse_args([]).fontes is None, "default = todos os feeds"

    with pytest.raises(SystemExit):
        m._parse_args(["--fontes", "gympass"])  # nome antigo do WellHub: erro plausÃ­vel


# --------------------------------------------------------------------------- #
# BLK-MA-21 / DEC-039 - particao de 2 chaves, migracao de layout e `fontes_lidas`
# --------------------------------------------------------------------------- #
def _gravar_particao_legada(base: Path, semana: str, snap: pd.DataFrame) -> Path:
    """Grava uma particao no layout ANTIGO (1 chave, `fonte` DENTRO do arquivo).

    Feita a mao de proposito: a funcao de producao passou a recusar este layout, e o que se quer
    aqui e' exatamente o estado que existe em disco antes da migracao -- que era o de uma particao
    VIVA na estacao em 2026-08-25 (`semana=2026-33`, 22.173 linhas, so' WellHub, contrato `v3`).
    """
    diretorio = base / f"semana={semana}"
    diretorio.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pandas(snap, preserve_index=False),
        str(diretorio / "parte-0.parquet"),
    )
    return diretorio


def test_duas_fontes_coexistem_na_mesma_semana(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """T1 - o defeito que este bloco existe para matar: duas CADENCIAS, uma semana ISO.

    O cron de DOMINGO grava `--fontes unidades`; o da TERCA grava `--fontes totalpass wellhub` --
    as duas cadencias sao semanais e caem na MESMA semana ISO. Com uma
    chave de particao so', o segundo apagava o primeiro via `delete_matching` -- ~21h de coleta
    perdidas com `exit 0`. Aqui as tres folhas coexistem e nenhuma linha se perde.
    """
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "serie"

    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF, fontes=["unidades"])
    assert len(m.ler_snapshots(base)) == 2

    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF, fontes=["totalpass", "wellhub"])

    particao = base / f"semana={SEMANA_REF}"
    assert sorted(p.name for p in particao.iterdir()) == [
        "fonte=totalpass",
        "fonte=unidades",
        "fonte=wellhub",
    ]
    serie = m.ler_snapshots(base)
    assert len(serie) == 6, "a segunda cadencia apagou a folha da primeira"
    assert serie["fonte"].astype(str).value_counts().to_dict() == {
        "totalpass": 2,
        "unidades": 2,
        "wellhub": 2,
    }
    # E o carimbo distingue as duas execucoes DENTRO da mesma semana.
    por_fonte = {
        str(fonte): sorted({str(v) for v in bloco["fontes_lidas"]})
        for fonte, bloco in serie.groupby("fonte", sort=True)
    }
    assert por_fonte["unidades"] == ["unidades"]
    assert por_fonte["wellhub"] == ["totalpass,wellhub"]
    assert por_fonte["totalpass"] == ["totalpass,wellhub"]


def test_leitor_de_uma_chave_devolve_fonte_nula_em_silencio(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """T2 - caracteriza o defeito que a leitura de 2 chaves evita, e prova que producao nao o tem.

    Sobre a arvore de duas chaves, um `ds.dataset` que declare so' `semana` devolve `fonte` **nula
    para 100% das linhas, sem excecao, sem erro e sem log**. Como `(fonte, chave_snapshot)` e' a
    chave primaria composta de todo o pacote, isso colapsaria todas as fontes numa so'.
    """
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "serie"
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)

    import pyarrow.dataset as pds

    # A copia PLAUSIVEL do defeito: alguem reusa o `schema=` do contrato (que declara `fonte`) e
    # esquece de acrescentar a segunda chave ao `partitioning`. O schema faz a coluna existir; o
    # particionamento incompleto faz o pyarrow nao ter de onde preenche-la.
    defeituoso = pds.dataset(
        str(base),
        format="parquet",
        schema=m._schema_arrow_snapshot(),
        partitioning=pds.partitioning(pa.schema([("semana", pa.string())]), flavor="hive"),
    )
    df_defeituoso = defeituoso.to_table().to_pandas()
    assert len(df_defeituoso) == 6, "o leitor de 1 chave le as linhas normalmente..."
    assert df_defeituoso["fonte"].isna().all(), (
        "...e devolve `fonte` 100% nula, em silencio: e' esse o modo de falha"
    )

    # A funcao de PRODUCAO, sobre as MESMAS linhas, devolve a fonte correta e sem nulos.
    serie = m.ler_snapshots(base)
    assert len(serie) == 6
    assert not serie["fonte"].isna().any()
    assert set(serie["fonte"].astype(str)) == {"totalpass", "wellhub", "unidades"}


#: Chamadas de pyarrow.dataset que precisam declarar as DUAS chaves. `write_dataset` entrou na
#: emenda de 2026-08-25: o modo de falha DESTRUTIVO (a segunda execucao da semana apagando a folha
#: da primeira) vem do ESCRITOR, e a varredura original so' olhava o leitor.
_CHAMADAS_PARTICIONADAS: tuple[str, ...] = ("dataset", "write_dataset")


def _particionamento_declara_as_duas_chaves(no: ast.Call) -> bool:
    """O kwarg `partitioning` desta chamada declara as duas chaves de `COLUNAS_PARTICAO`?

    Duas formas ACEITAS: a canonica, `_particionamento_hive()` (fonte unica das chaves), e a
    literal, um `ds.partitioning(...)` cujo subgrafo cite os dois nomes. Qualquer outra coisa e'
    violacao -- inclusive um `partitioning` presente e de UMA chave, que era exatamente o bug que
    este bloco veio corrigir e que a versao anterior desta trava deixava passar VERDE.
    """
    valor = next((k.value for k in no.keywords if k.arg == "partitioning"), None)
    if valor is None:
        return False
    if isinstance(valor, ast.Call):
        alvo = valor.func
        nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", "")
        if nome == "_particionamento_hive":
            return True
    literais = {
        filho.value
        for filho in ast.walk(valor)
        if isinstance(filho, ast.Constant) and isinstance(filho.value, str)
    }
    return all(chave in literais for chave in c.COLUNAS_PARTICAO)


def varrer_particionamento(diretorio: Path) -> tuple[list[str], int]:
    """`(violacoes, nº de chamadas vistas)` nos `*.py` do diretorio. Publica para o teste-isca."""
    violacoes: list[str] = []
    chamadas = 0
    for arquivo in sorted(Path(diretorio).glob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            if not (isinstance(alvo, ast.Attribute) and alvo.attr in _CHAMADAS_PARTICIONADAS):
                continue
            chamadas += 1
            if not _particionamento_declara_as_duas_chaves(no):
                violacoes.append(f"{arquivo.name}:{no.lineno} (`{alvo.attr}`)")
    return violacoes, chamadas


def test_nenhum_leitor_do_pacote_usa_particionamento_de_uma_chave() -> None:
    """T3 - trava, por AST, contra um leitor OU escritor futuro nascer com o defeito do T2.

    Varre `src/motor_expansao/vulnerabilidade/*.py` e exige que toda chamada `ds.dataset(...)` e
    `ds.write_dataset(...)` declare as DUAS chaves do contrato. A prosa do docstring nao vale como
    guardrail: o defeito e' silencioso, e quem o reintroduzir nao vai ver teste nenhum ficar
    vermelho -- a menos que este exista.
    """
    violacoes, chamadas = varrer_particionamento(Path(m.__file__).parent)

    assert violacoes == [], (
        "chamada de pyarrow.dataset sem as DUAS chaves de particao: "
        f"{violacoes}. Use `_particionamento_hive()`"
    )
    assert chamadas >= 2, "a varredura nao achou leitor E escritor: o teste ficou decorativo"

    # E a fonte unica das chaves declara as DUAS, na ordem do contrato.
    assert c.COLUNAS_PARTICAO == ("semana", "fonte")
    assert [campo.name for campo in m._particionamento_hive().schema] == list(c.COLUNAS_PARTICAO)


def test_a_trava_de_ast_pega_o_defeito_que_ela_promete_pegar(tmp_path: Path) -> None:
    """A trava so' vale se PEGAR. Prova com arquivos-isca num diretorio temporario FORA do repo.

    Ate' 2026-08-25 esta varredura exigia apenas que o kwarg `partitioning` EXISTISSE -- ficava
    verde sobre um particionamento de UMA chave, que e' o proprio bug do bloco. E nao olhava o
    escritor, de onde vem o modo de falha destrutivo.
    """
    isca = tmp_path / "isca"
    isca.mkdir()
    (isca / "sem_kwarg.py").write_text(
        "import pyarrow.dataset as ds\nds.dataset('x', format='parquet')\n", encoding="utf-8"
    )
    (isca / "uma_chave_no_leitor.py").write_text(
        "import pyarrow as pa\nimport pyarrow.dataset as ds\n"
        "ds.dataset('x', partitioning=ds.partitioning(pa.schema([('semana', pa.string())])))\n",
        encoding="utf-8",
    )
    (isca / "uma_chave_no_escritor.py").write_text(
        "import pyarrow as pa\nimport pyarrow.dataset as ds\n"
        "ds.write_dataset(t, base_dir='x', "
        "partitioning=ds.partitioning(pa.schema([('semana', pa.string())])))\n",
        encoding="utf-8",
    )
    (isca / "correto.py").write_text(
        "import pyarrow as pa\nimport pyarrow.dataset as ds\n"
        "ds.write_dataset(t, base_dir='x', partitioning=ds.partitioning("
        "pa.schema([('semana', pa.string()), ('fonte', pa.string())]), flavor='hive'))\n",
        encoding="utf-8",
    )

    violacoes, chamadas = varrer_particionamento(isca)
    pegos = {v.split(":")[0] for v in violacoes}

    assert pegos == {"sem_kwarg.py", "uma_chave_no_leitor.py", "uma_chave_no_escritor.py"}, pegos
    assert chamadas == 4, "uma chamada varrida por arquivo (`ds.partitioning` nao e' varrido)"


def test_serie_mista_legado_e_folha_nova(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """T4 - a serie que JA EXISTE em disco continua legivel: provado, nao presumido.

    Havia (2026-08-25) uma particao viva no layout antigo. Uma particao legada de OUTRA semana ao
    lado das folhas novas tem de ser lida com `fonte` correta e ZERO nulos.
    """
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "serie"
    snap = _snapshot_valido(dirs_sinteticos)

    _gravar_particao_legada(base, "2026-30", snap)
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)

    serie = m.ler_snapshots(base)
    assert set(serie["semana"].astype(str)) == {"2026-30", SEMANA_REF}
    assert len(serie) == 12
    assert not serie["fonte"].isna().any(), "a particao legada voltou com `fonte` nula"
    legada = serie[serie["semana"].astype(str) == "2026-30"]
    assert set(legada["fonte"].astype(str)) == {"totalpass", "wellhub", "unidades"}


def test_escrita_recusa_semana_com_particao_legada(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """T5 - o UNICO caminho de corrupcao medido: legado + folha nova da MESMA semana.

    `delete_matching` de 2 chaves casa FOLHAS, nao o diretorio da semana, entao o arquivo legado
    sobreviveria e a linha voltaria DUAS vezes na leitura -- aparecendo dias depois, longe da
    causa, como `chave (semana, fonte, chave_snapshot) duplicada`.
    """
    base = tmp_path / "serie"
    snap = _snapshot_valido(dirs_sinteticos)
    _gravar_particao_legada(base, SEMANA_REF, snap)

    with pytest.raises(ValueError, match="particao legada"):
        m.escrever_particao_semana(snap, base, semana=SEMANA_REF)

    # E a recusa vale para o caminho publico tambem, nao so' para a funcao de baixo nivel.
    tp, wh, un = dirs_sinteticos
    with pytest.raises(ValueError, match="migrar-layout"):
        m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)


def test_migrar_layout_converte_legado_em_folhas(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """T6 - a migracao explicita: arquivo legado -> folhas `fonte=`, sem perder nem duplicar linha."""
    base = tmp_path / "serie"
    snap = _snapshot_valido(dirs_sinteticos)
    diretorio = _gravar_particao_legada(base, SEMANA_REF, snap)

    migradas = m.migrar_layout_particoes(base)

    assert migradas == [SEMANA_REF]
    assert not list(diretorio.glob("parte-*.parquet")), "o arquivo legado sobreviveu"
    assert sorted(p.name for p in diretorio.iterdir()) == [
        "fonte=totalpass",
        "fonte=unidades",
        "fonte=wellhub",
    ]
    serie = m.ler_snapshots(base)
    assert len(serie) == 6
    assert not serie["fonte"].isna().any()

    # Idempotente: rodar de novo nao encontra nada para migrar.
    assert m.migrar_layout_particoes(base) == []
    # E a escrita, que antes recusava, volta a funcionar na mesma semana.
    m.escrever_particao_semana(snap, base, semana=SEMANA_REF)


def test_migrar_layout_dry_run_nao_toca_disco(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """T6 - a migracao APAGA arquivo; o modo seco tem de listar sem tocar em nada."""
    base = tmp_path / "serie"
    snap = _snapshot_valido(dirs_sinteticos)
    diretorio = _gravar_particao_legada(base, SEMANA_REF, snap)
    antes = sorted(p.name for p in diretorio.iterdir())

    assert m.migrar_layout_particoes(base, dry_run=True) == [SEMANA_REF]

    assert sorted(p.name for p in diretorio.iterdir()) == antes
    assert (diretorio / "parte-0.parquet").exists()


def test_migrar_layout_recusa_estado_ambiguo(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """T6 - legado E folha da MESMA fonte na mesma semana: nao ha' como saber qual e' a boa."""
    base = tmp_path / "serie"
    snap = _snapshot_valido(dirs_sinteticos)
    m.escrever_particao_semana(snap, base, semana=SEMANA_REF)
    # Agora acrescenta um arquivo legado por cima da arvore nova.
    pq.write_table(
        pa.Table.from_pandas(snap, preserve_index=False),
        str(base / f"semana={SEMANA_REF}" / "parte-0.parquet"),
    )

    with pytest.raises(ValueError, match="ambiguo"):
        m.migrar_layout_particoes(base)


def test_migrar_layout_dry_run_diagnostica_em_vez_de_levantar(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Emenda de 2026-08-25: o modo seco reporta TODAS as ambiguas, sem levantar.

    Antes ele levantava na primeira, e com duas semanas ambiguas a segunda so' aparecia depois de
    a primeira ser resolvida a' mao -- uma por execucao. Diagnostico que aborta no primeiro achado
    nao e' diagnostico.
    """
    base = tmp_path / "serie"
    snap = _snapshot_valido(dirs_sinteticos)
    # Duas semanas AMBIGUAS (folha nova + legado da mesma fonte) e uma so' legada (migravel).
    for semana in ("2026-30", "2026-31"):
        m.escrever_particao_semana(snap, base, semana=semana)
        pq.write_table(
            pa.Table.from_pandas(snap, preserve_index=False),
            str(base / f"semana={semana}" / "parte-0.parquet"),
        )
    _gravar_particao_legada(base, "2026-32", snap)

    diagnostico = m.diagnosticar_layout_particoes(base)

    assert diagnostico == {"migraveis": ["2026-32"], "ambiguas": ["2026-30", "2026-31"]}
    assert m.migrar_layout_particoes(base, dry_run=True) == ["2026-32"], (
        "o modo seco nao pode levantar nem esconder a semana migravel por causa das ambiguas"
    )
    # E nada foi tocado no disco.
    assert (base / "semana=2026-30" / "parte-0.parquet").exists()
    assert (base / "semana=2026-32" / "parte-0.parquet").exists()


def test_migrar_layout_nao_deixa_temporario_para_tras(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """A migracao escreve FORA da serie e move por rename (emenda de 2026-08-25).

    Antes ela gravava direto no caminho final: um crash no meio do `write_dataset` deixava folha
    PARCIAL ao lado do legado -- o par que faz a leitura duplicar linha -- e a retentativa entao
    travava na guarda de ambiguidade. O temporario e' IRMAO de `base_dir` (mesmo sistema de
    arquivos, logo o rename e' atomico) e nao pode sobreviver a' funcao: dentro de `base` ele
    entraria no `ds.dataset` com profundidade errada de chaves.
    """
    raiz = tmp_path / "staging"
    base = raiz / "serie"
    snap = _snapshot_valido(dirs_sinteticos)
    _gravar_particao_legada(base, SEMANA_REF, snap)

    assert m.migrar_layout_particoes(base) == [SEMANA_REF]

    assert sorted(p.name for p in raiz.iterdir()) == ["serie"], (
        "sobrou diretorio temporario ao lado da serie"
    )
    assert not any(p.name.startswith(".migracao-") for p in base.rglob("*"))
    # A serie continua integra depois do rename.
    serie = m.ler_snapshots(base)
    assert len(serie) == 6
    assert not serie["fonte"].isna().any()


def test_ler_snapshots_valida_fonte_antes_da_saida_antecipada(tmp_path: Path) -> None:
    """M4 - a validacao vinha DEPOIS do `return` por base vazia, e o efeito era o oposto.

    Sobre base inexistente ou sem particao -- que e' exatamente o estado da VPS hoje, zero
    particoes -- um erro de digitacao na fronteira do D9 devolvia frame VAZIO em vez de levantar.
    "Nao ha' dado" e' a leitura errada, e a unica que nao faz ninguem procurar a causa.
    """
    inexistente = tmp_path / "nao_existe"
    sem_particao = tmp_path / "vazia"
    sem_particao.mkdir()

    for base in (inexistente, sem_particao):
        with pytest.raises(ValueError, match="fonte fora do contrato"):
            m.ler_snapshots(base, fontes=["wellub"])  # erro de digitacao de `wellhub`
        with pytest.raises(ValueError, match="vazio"):
            m.ler_snapshots(base, fontes=[])
        # E o caminho feliz continua devolvendo frame vazio bem-formado.
        assert m.ler_snapshots(base, fontes=["wellhub"]).empty


def test_fontes_lidas_carimbada_no_parquet(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """T7 - o carimbo tem de sobreviver ao disco, nao so' existir em memoria."""
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "serie"
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF, fontes=["unidades"])

    serie = m.ler_snapshots(base)
    assert (serie["fontes_lidas"] == "unidades").all()
    assert serie["fontes_lidas"].dtype == "string"


def test_fontes_lidas_distingue_tentado_de_vazio(tmp_path: Path) -> None:
    """T8 - a razao de ser da coluna: "nao foi tentado" x "foi tentado e recusado/veio vazio".

    Materializa pedindo TotalPass **e** WellHub, com o diretorio do TotalPass vazio. So' existe a
    folha `fonte=wellhub` -- e olhar as folhas presentes leria isso como "o TotalPass nunca foi
    pedido". O carimbo diz a verdade: os dois foram pedidos, e um nao rendeu linha.
    """
    tp, wh, un = tmp_path / "tp", tmp_path / "wh", tmp_path / "un"
    for d in (tp, wh, un):
        d.mkdir(parents=True, exist_ok=True)
    _escrever_csv(
        wh / "unidades_wellhub_rj.csv",
        pd.DataFrame(
            {
                "slug": ["academia-gama"],
                "nome": ["Academia Gama"],
                "latitude": [-22.9100],
                "longitude": [-43.1800],
                "cidade": ["Rio de Janeiro"],
                "uf": ["RJ"],
                "cep": ["20000-000"],
                "endereco_formatado": ["Rua C, 300"],
                "atividades": ["Musculacao"],
                "data_coleta": ["2026-07-26"],
            }
        ),
    )
    base = tmp_path / "serie"
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF, fontes=["totalpass", "wellhub"])

    particao = base / f"semana={SEMANA_REF}"
    assert sorted(p.name for p in particao.iterdir()) == ["fonte=wellhub"]
    serie = m.ler_snapshots(base)
    assert len(serie) == 1
    assert (serie["fontes_lidas"] == "totalpass,wellhub").all(), (
        "a folha ausente nao pode ser lida como fonte nao tentada"
    )


def test_ler_snapshots_recorta_por_fonte(
    dirs_sinteticos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """O recorte da DEC-039 (D9) e' IMPOSTO na leitura, nao prometido em prosa.

    A particao do `totalpass` e' GRAVADA desde a primeira semana (para o cronometro de MIN_SEMANAS
    correr), mas fica fora do consumo ate' o BLK-MA-20 calibrar a dedup TP x WH.
    """
    tp, wh, un = dirs_sinteticos
    base = tmp_path / "serie"
    m.materializar(tp, wh, un, base_dir=base, data_referencia=REF)

    assert len(m.ler_snapshots(base)) == 6, "default = serie inteira, como antes deste bloco"

    so_wh = m.ler_snapshots(base, fontes=["wellhub"])
    assert set(so_wh["fonte"].astype(str)) == {"wellhub"}
    assert len(so_wh) == 2
    # As colunas continuam as 13 do contrato + `semana`, mesmo com recorte.
    assert list(so_wh.columns) == list(c.CONTRATO_COLUNAS_SNAPSHOT.keys()) + ["semana"]

    # Fonte fora do contrato nao pode virar recorte silencioso de zero linha (mesmo molde do
    # `ler_feeds`): o erro de digitacao tem de falhar alto.
    with pytest.raises(ValueError, match="fonte fora do contrato"):
        m.ler_snapshots(base, fontes=["gympass"])
    with pytest.raises(ValueError, match="nao ha o que ler"):
        m.ler_snapshots(base, fontes=[])


def _serie_hash_constante(semanas: list[int]) -> list[pd.DataFrame]:
    """Uma serie de snapshots com UMA chave, presente nas `semanas` dadas, com hash CONSTANTE.

    Hash constante e' o pior caso do `v4`: nada muda, entao `semanas_sem_mudanca` cresce com a
    serie e satura (ou nao) contra `STALE_SEMANAS`. E' assim que se mede o PISO da retencao.
    """
    import h3

    hex_id = h3.latlng_to_cell(-23.5500, -46.6300, c.H3_RES_CONTRATO)
    frames: list[pd.DataFrame] = []
    for i in semanas:
        linha = {
            "snapshot_date": "2026-01-05",
            "slug": None,
            "concorrente_id": "0" * 40,
            "chave_snapshot": "k_parada",
            "chave_origem": "hash_estavel",
            "hex_id_res7": hex_id,
            "rede": "independente",
            "fonte": "wellhub",
            "hash_campos_raspados": "hash_congelado",
            "nota_wellhub": None,
            "qtd_avaliacoes_wellhub": None,
            "fontes_lidas": "totalpass,wellhub",
            "versao_contrato": c.VERSAO_CONTRATO_SNAPSHOT,
        }
        df = pd.DataFrame([linha], columns=list(c.CONTRATO_COLUNAS_SNAPSHOT.keys()))
        df["semana"] = f"2026-{i:02d}"
        frames.append(df)
    return frames


def test_retencao_satura_o_v4_na_cadencia_semanal() -> None:
    """T9 - trava a RAZAO da retencao, nao so' o valor. A cadencia e' UNIFORME (semanal).

    O teste anterior (`test_retencao_serve_as_duas_cadencias`) dividia a retencao por 4,345 para
    converter semanas de calendario em observacoes de um feed MENSAL, e cravava
    `assert 26 / semanas_por_mes < c.MIN_SEMANAS` -- uma REJEICAO HARD-CODED do valor que a
    cadencia semanal torna correto. Quem so' trocasse a constante veria CI vermelho e concluiria
    que o `26` esta errado.

    A razao nova, MEDIDA: com as tres fontes semanais, N particoes = N observacoes de CADA fonte no
    caminho feliz, e o piso para o `v4` saturar e' **13** -- porque `_semanas_sem_mudanca` conta
    observacoes ESTRITAMENTE apos a ultima mudanca (vale `k-1` com hash constante) contra o
    denominador `STALE_SEMANAS = 12`.
    """
    assert c.RETENCAO_SEMANAS >= 13, (
        "abaixo de 13 o v4 NUNCA satura: com k semanas, semanas_sem_mudanca vale k-1 e o "
        "denominador e' STALE_SEMANAS=12"
    )

    out = mchurn.extrair_churn_staleness(
        snapshots=_serie_hash_constante(list(range(1, c.RETENCAO_SEMANAS + 1)))
    )
    linha = out[out["chave_snapshot"] == "k_parada"].iloc[0]
    assert int(linha["n_semanas_serie"]) == c.RETENCAO_SEMANAS
    assert int(linha["semanas_sem_mudanca"]) == c.RETENCAO_SEMANAS - 1
    assert int(linha["semanas_sem_mudanca"]) >= c.STALE_SEMANAS, (
        "a retencao nao cobre o denominador do v4 (semanas_sem_mudanca / STALE_SEMANAS)"
    )
    assert bool(linha["flag_serie_imatura"]) is False
    assert bool(linha["flag_staleness_interpretavel"]) is True

    # O PISO, provado pelo lado de baixo: com 12 observacoes o v4 fica preso em 11/12 = 0,9167.
    doze = mchurn.extrair_churn_staleness(snapshots=_serie_hash_constante(list(range(1, 13))))
    assert int(doze[doze["chave_snapshot"] == "k_parada"].iloc[0]["semanas_sem_mudanca"]) == 11


def test_retencao_tolera_metade_das_semanas_perdidas() -> None:
    """`26` = 2x o piso: satura o `v4` mesmo com a fonte perdendo METADE das semanas.

    Fora do caminho feliz, N particoes NAO sao N observacoes: a fonte que perde a folha da semana
    (a curadoria recusa feed velho, o coletor cai) perde a observacao, mas a semana continua
    ocupando um slot de retencao. Com a fonte presente so' nas semanas pares dentro da janela de
    `RETENCAO_SEMANAS`, sobram 13 observacoes -- exatamente o piso.
    """
    pares = [i for i in range(1, c.RETENCAO_SEMANAS + 1) if i % 2 == 0]
    assert len(pares) >= 13, (
        "a janela retida nao entrega o piso de 13 observacoes com 50% de buraco"
    )

    out = mchurn.extrair_churn_staleness(snapshots=_serie_hash_constante(pares))
    linha = out[out["chave_snapshot"] == "k_parada"].iloc[0]
    assert int(linha["n_semanas_serie"]) == len(pares)
    assert int(linha["semanas_sem_mudanca"]) >= c.STALE_SEMANAS
