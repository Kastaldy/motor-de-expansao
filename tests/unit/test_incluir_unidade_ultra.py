"""O script de incluir/mover unidade Ultra (scripts/incluir_unidade_ultra.py, roteiro no infra_producao).

Monta cópias pequenas dos dois arquivos no formato da VPS e confere: a linha nova sai no padrão do
Ultra.csv e do parquet, nenhuma outra linha muda, as recusas não gravam nada e os comandos impressos
levam os hashes da base e dos arquivos novos.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import h3
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("incluir_unidade_ultra", RAIZ / "scripts" / "incluir_unidade_ultra.py")
iu = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(iu)

CABECALHO = (
    '"UNIDADE";"ENDEREÇO";"CIDADE";"ESTADO";"Precisão de mapeamento";"Processo de Geocodificação";'
    '"Latitude";"Longitude";"Microárea";"Bairro";"Bairros Cortex";"Região Geográfica Intermediária";'
    '"Região Geográfica Imediata";"Microrregião";"Mesorregião";"Região Geográfica"'
)
LINHAS_CSV = [
    '"Ultra - codCamada:abc"',
    CABECALHO,
    '"Cabo Frio / RJ";"Av. Teste, 1";"Cabo Frio";"RJ";"Máxima";"Manual";"-22,88242";"-42,02299";;;;;;;;"Sudeste"',
    '"Maricá / RJ";;"Maricá";"RJ";"Máxima";"Manual";"-22,922484";"-42,817391";;;;;;;;"Sudeste"',
    '"Itaperuna";;"Itaperuna";"RJ";"Máxima";"Manual";"-21,197595";"-41,897679";;;;;;;;"Sudeste"',
]
UNIDADES = [
    ("Cabo Frio / RJ", "RJ", "Cabo Frio", -22.88242, -42.02299),
    ("Maricá / RJ", "RJ", "Maricá", -22.922484, -42.817391),
    ("Itaperuna", "RJ", "Itaperuna", -21.197595, -41.897679),
]


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    m = pd.DataFrame(
        [
            {
                "ultra_id": hashlib.sha1(f"id-fixo-{i}".encode()).hexdigest(),
                "unidade": u, "uf": uf, "cidade": c, "lat": la, "lng": ln,
                "flag_coord_valida": True, "hex_id_res7": h3.latlng_to_cell(la, ln, 7),
            }
            for i, (u, uf, c, la, ln) in enumerate(UNIDADES)
        ]
    )
    m.to_parquet(tmp_path / iu.ARQ_PARQUET, index=False)
    (tmp_path / iu.ARQ_CSV).write_bytes(("\n".join(LINHAS_CSV) + "\n").encode("latin-1"))
    return tmp_path


def _incluir(pasta: Path, *extra: str) -> int:
    return iu.main([
        "incluir", "--pasta", str(pasta), "--nome", "Teresópolis", "--uf", "RJ", "--cidade", "Teresópolis",
        "--lat", "-22.407291115271388", "--lng", "-42.96576019198278", *extra,
    ])


def test_incluir_acrescenta_a_linha_no_padrao_e_nao_muda_as_outras(pasta: Path, capsys) -> None:
    assert _incluir(pasta) == 0
    antes = pd.read_parquet(pasta / iu.ARQ_PARQUET)
    depois = pd.read_parquet(pasta / "novo" / iu.ARQ_PARQUET)
    assert len(depois) == len(antes) + 1
    assert depois.iloc[: len(antes)].reset_index(drop=True).equals(antes)
    nova = depois.iloc[-1]
    assert (nova["unidade"], nova["uf"], nova["cidade"]) == ("Teresópolis", "RJ", "Teresópolis")
    assert nova["hex_id_res7"] == h3.latlng_to_cell(-22.407291115271388, -42.96576019198278, 7)
    assert nova["ultra_id"] == hashlib.sha1("Teresópolis|-22.407291|-42.965760".encode()).hexdigest()
    b_antes = (pasta / iu.ARQ_CSV).read_bytes()
    b_depois = (pasta / "novo" / iu.ARQ_CSV).read_bytes()
    assert b_depois.startswith(b_antes)
    assert b_depois[len(b_antes):].decode("latin-1") == (
        '"Teresópolis";;"Teresópolis";"RJ";"Máxima";"Manual";"-22,407291115271388";"-42,96576019198278";;;;;;;;'
        '"Sudeste"\n'
    )
    saida = capsys.readouterr().out
    for arq in (pasta / iu.ARQ_PARQUET, pasta / iu.ARQ_CSV, pasta / "novo" / iu.ARQ_PARQUET, pasta / "novo" / iu.ARQ_CSV):
        assert hashlib.sha256(arq.read_bytes()).hexdigest() in saida
    assert "restart web api" in saida and "verificar_unidade.py" in saida
    assert "'Teresópolis'" in (pasta / "novo" / "verificar_unidade.py").read_text(encoding="utf-8")


def test_incluir_recusa_nome_que_ja_existe(pasta: Path) -> None:
    assert iu.main([
        "incluir", "--pasta", str(pasta), "--nome", "itaperuna", "--uf", "RJ", "--cidade", "Itaperuna",
        "--lat", "-21.3", "--lng", "-41.9",
    ]) == 2
    assert not (pasta / "novo").exists()


def test_incluir_recusa_unidade_a_menos_de_200_m(pasta: Path) -> None:
    assert iu.main([
        "incluir", "--pasta", str(pasta), "--nome", "Cabo Frio II", "--uf", "RJ", "--cidade", "Cabo Frio",
        "--lat", "-22.88250", "--lng", "-42.02300",
    ]) == 2
    assert not (pasta / "novo").exists()


def test_mover_troca_so_as_coordenadas_e_mantem_o_id(pasta: Path) -> None:
    antes = pd.read_parquet(pasta / iu.ARQ_PARQUET)
    assert iu.main([
        "mover", "--pasta", str(pasta), "--nome", "Maricá / RJ", "--lat", "-22.9101", "--lng", "-42.8202",
    ]) == 0
    depois = pd.read_parquet(pasta / "novo" / iu.ARQ_PARQUET)
    assert len(depois) == len(antes)
    assert depois.loc[[0, 2]].equals(antes.loc[[0, 2]])
    assert depois.loc[1, "ultra_id"] == antes.loc[1, "ultra_id"]
    assert (depois.loc[1, "lat"], depois.loc[1, "lng"]) == (-22.9101, -42.8202)
    assert depois.loc[1, "hex_id_res7"] == h3.latlng_to_cell(-22.9101, -42.8202, 7)
    linhas_depois = (pasta / "novo" / iu.ARQ_CSV).read_bytes().decode("latin-1").split("\n")
    assert linhas_depois[3] == '"Maricá / RJ";;"Maricá";"RJ";"Máxima";"Manual";"-22,9101";"-42,8202";;;;;;;;"Sudeste"'
    assert [lin for k, lin in enumerate(linhas_depois) if k != 3] == [
        lin for k, lin in enumerate(LINHAS_CSV + [""]) if k != 3
    ]


def test_caminho_do_windows_sai_no_formato_do_git_bash() -> None:
    assert iu.caminho_git_bash(Path("C:/Users/Fulano de Tal/x.parquet")).startswith("/c/Users/Fulano de Tal/")
