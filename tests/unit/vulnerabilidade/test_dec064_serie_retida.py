"""DEC-064: retenção integral, leitura recortada, estreia por listagem e ponte de identidade.

O que estes testes protegem, e por quê:

  **D1 — a poda não roda em regime.** Ela é a única função do pacote que APAGA diretório, e o que
  ela apagaria é justamente a série de que o reprocessamento depende. A invariante `>= 1` de
  `podar_snapshots` fica INTACTA: quem decide não podar é o orquestrador, não a função que apaga.

  **A leitura recortada é o que PAGA a retenção integral.** Reter tudo custa 2,6 MB de disco por
  semana; o que cobrava caro era `ler_snapshots` carregar a série inteira (~70,5 MB de RSS por
  semana retida, medidos no D5 da DEC-039). O recorte virou filtro de PARTIÇÃO, e isso é
  observável: uma folha corrompida FORA do recorte não é sequer aberta.

  **D5 — a estreia sai da LISTAGEM.** Com leitura recortada, tirá-la do frame lido devolveria a
  borda da janela — o defeito do PR #383 por outro caminho (22.877 chaves lidas como recém-chegadas
  contra 327 reais).

  **D3 — a ponte responde QUEM e ONDE, inclusive para quem SAIU.** É a pergunta que os pins
  `vulnerabilidade_ma_*` não respondem: eles são retrato do presente, e a chave que sumiu não está
  no arquivo novo.

Fixtures 100% sintéticas, como o resto do pacote.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade import snapshots as m

REF_1 = date(2026, 7, 29)  # semana ISO 2026-31
REF_2 = date(2026, 8, 5)  # semana ISO 2026-32
SEMANA_1 = "2026-31"
SEMANA_2 = "2026-32"


def _escrever_rede(dir_unidades: Path, rede: str, n: int, *, data_coleta: str) -> None:
    """CSV sintético de uma rede, no schema real do feed `unidades` (4 colunas)."""
    dir_unidades.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "nome_unidade": [f"{rede} unidade {i}" for i in range(n)],
            "latitude": [-23.55 - i * 0.01 for i in range(n)],
            "longitude": [-46.63 - i * 0.01 for i in range(n)],
            "data_coleta": [data_coleta] * n,
        }
    ).to_csv(dir_unidades / f"unidades_{rede}.csv", sep=";", encoding="utf-8-sig", index=False)


@pytest.fixture
def serie_de_duas_semanas(tmp_path: Path) -> tuple[Path, Path, Path]:
    """`(dir_unidades, base_dir, ponte_dir)` com 2026-31 e 2026-32 publicadas."""
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    _escrever_rede(un, "alfa", 6, data_coleta="2026-07-27")
    m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1,
        fontes=["unidades"],
    )
    _escrever_rede(un, "alfa", 6, data_coleta="2026-08-03")
    m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_2,
        fontes=["unidades"],
    )
    return un, base, m.ponte_dir_de(base)


# --------------------------------------------------------------------------- #
# D1 — retencao integral
# --------------------------------------------------------------------------- #
def test_executar_no_default_NAO_poda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Em regime a poda não pode ser sequer CONSULTADA — ela apaga disco."""

    def _explode(*_a: object, **_k: object) -> None:
        raise AssertionError("executar() no default NUNCA pode chamar podar_snapshots")

    monkeypatch.setattr(m, "podar_snapshots", _explode)
    un, base = tmp_path / "un", tmp_path / "snapshots"
    _escrever_rede(un, "alfa", 6, data_coleta="2026-07-27")
    auditoria = m.executar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1,
        fontes=["unidades"],
    )
    assert auditoria["retencao_semanas"] == c.RETENCAO_TUDO
    assert auditoria["semanas_removidas"] == 0


def test_poda_continua_disponivel_como_ato_manual(tmp_path: Path) -> None:
    """Passar N >= 1 reativa a poda. A DEC desliga o REGIME, não a capacidade."""
    un, base = tmp_path / "un", tmp_path / "snapshots"
    for velha in ("2026-01", "2026-02"):
        (base / f"semana={velha}" / "fonte=unidades").mkdir(parents=True)
    _escrever_rede(un, "alfa", 6, data_coleta="2026-07-27")
    auditoria = m.executar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1,
        retencao_semanas=1, fontes=["unidades"],
    )
    assert auditoria["semanas_removidas"] == 2
    assert sorted(p.name for p in base.iterdir()) == [f"semana={SEMANA_1}"]


def test_a_sentinela_nunca_alcanca_a_funcao_que_apaga() -> None:
    """A invariante `>= 1` de `podar_snapshots` fica INTACTA, e a sentinela é inalcançável por ela.

    É a trava que separa as duas responsabilidades: se um dia a sentinela passasse por aqui, ela
    viraria `keep-newest-0` — apagar TUDO, que é o oposto exato de reter tudo.
    """
    assert c.RETENCAO_TUDO < 1
    with pytest.raises(ValueError, match="retencao_semanas"):
        m.podar_snapshots(Path("."), c.RETENCAO_TUDO)


# --------------------------------------------------------------------------- #
# Leitura RECORTADA — o que paga a retencao integral
# --------------------------------------------------------------------------- #
def test_recorte_nao_abre_folha_fora_do_pedido(serie_de_duas_semanas: tuple[Path, Path, Path]) -> None:
    """Prova de PODA DE PARTIÇÃO, não de filtro em pandas.

    A folha de 2026-31 é corrompida. Se o recorte fosse aplicado depois do `to_pandas` — como era
    antes da DEC-064 —, ler 2026-32 levantaria, porque a série inteira subiria primeiro. Ler sem
    recorte ainda levanta, e é isso que torna este teste uma medição e não uma opinião.
    """
    _un, base, _ponte = serie_de_duas_semanas
    for parquet in sorted((base / f"semana={SEMANA_1}" / "fonte=unidades").glob("*.parquet")):
        parquet.write_bytes(b"nao e' parquet")

    recortado = m.ler_snapshots(base, semanas=[SEMANA_2], fontes=["unidades"])
    assert len(recortado) == 6
    assert set(recortado["semana"].astype(str)) == {SEMANA_2}

    with pytest.raises(Exception):  # noqa: B017 — a classe vem do pyarrow; o que importa e' levantar
        m.ler_snapshots(base)


def test_recorte_devolve_o_mesmo_que_filtrar_depois(
    serie_de_duas_semanas: tuple[Path, Path, Path],
) -> None:
    """Equivalência: o que muda é o pico de memória, nunca o resultado."""
    _un, base, _ponte = serie_de_duas_semanas
    inteira = m.ler_snapshots(base)
    esperado = inteira[inteira["semana"].astype(str) == SEMANA_2].reset_index(drop=True)
    recortado = m.ler_snapshots(base, semanas=[SEMANA_2])
    pd.testing.assert_frame_equal(
        recortado.sort_values("chave_snapshot").reset_index(drop=True),
        esperado.sort_values("chave_snapshot").reset_index(drop=True),
    )


# --------------------------------------------------------------------------- #
# D5 — estreia e observabilidade pela LISTAGEM
# --------------------------------------------------------------------------- #
def test_listagem_le_metadado_e_ignora_layout_legado(tmp_path: Path) -> None:
    """Consequência DECLARADA: no layout de 1 chave a `fonte` vive DENTRO do arquivo."""
    base = tmp_path / "snapshots"
    (base / f"semana={SEMANA_1}" / "fonte=unidades").mkdir(parents=True)
    (base / f"semana={SEMANA_2}" / "fonte=unidades").mkdir(parents=True)
    (base / f"semana={SEMANA_2}" / "fonte=wellhub").mkdir(parents=True)
    (base / "semana=2026-30").mkdir(parents=True)
    (base / "semana=2026-30" / "parte-0.parquet").write_bytes(b"legado")
    (base / "backup").mkdir()

    assert m.listar_particoes(base) == {
        "unidades": [SEMANA_1, SEMANA_2],
        "wellhub": [SEMANA_2],
    }
    assert m.listar_particoes(tmp_path / "nao_existe") == {}


def test_estreia_e_POR_FONTE_nao_da_borda_da_serie(tmp_path: Path) -> None:
    """A regressão do PR #383, travada: a fonte que chega depois tem estreia PRÓPRIA.

    Se a estreia saísse da série (a menor semana de TODAS as fontes), a `wellhub` inteira nasceria
    "estreando" em 2026-31 — semana em que ela não existe — e todas as suas chaves passariam por
    recém-chegadas. Foi assim que 22.877 chaves foram lidas como novas contra 327 reais.
    """
    base = tmp_path / "snapshots"
    (base / f"semana={SEMANA_1}" / "fonte=unidades").mkdir(parents=True)
    (base / f"semana={SEMANA_2}" / "fonte=unidades").mkdir(parents=True)
    (base / f"semana={SEMANA_2}" / "fonte=wellhub").mkdir(parents=True)

    assert m.primeira_semana_por_fonte(base) == {"unidades": SEMANA_1, "wellhub": SEMANA_2}


# --------------------------------------------------------------------------- #
# D3 — ponte de identidade
# --------------------------------------------------------------------------- #
def test_ponte_nomeia_as_chaves_da_semana(serie_de_duas_semanas: tuple[Path, Path, Path]) -> None:
    """Uma linha por chave do snapshot, com nome e coordenada."""
    _un, base, ponte_dir = serie_de_duas_semanas
    ponte = m.ler_ponte_identidade(ponte_dir, semanas=[SEMANA_2])
    snapshot = m.ler_snapshots(base, semanas=[SEMANA_2])

    assert list(ponte.columns) == [*c.CONTRATO_COLUNAS_PONTE, "semana"]
    assert set(ponte["chave_snapshot"]) == set(snapshot["chave_snapshot"])
    assert ponte["nome"].notna().all()
    assert ponte["lat"].notna().all() and ponte["lng"].notna().all()


def test_ponte_nomeia_quem_SAIU(tmp_path: Path) -> None:
    """O ponto da DEC: o diff semanal sabia QUE uma chave sumiu, e não QUEM nem ONDE.

    A rede `beta` some na segunda semana. O retrato do presente (o snapshot de 2026-32) não tem as
    chaves dela — por construção, é o que "sumiu" significa. A ponte da semana ANTERIOR responde.
    """
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    _escrever_rede(un, "alfa", 6, data_coleta="2026-07-27")
    _escrever_rede(un, "beta", 6, data_coleta="2026-07-27")
    m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1,
        fontes=["unidades"],
    )
    (un / "unidades_beta.csv").unlink()
    _escrever_rede(un, "alfa", 6, data_coleta="2026-08-03")
    m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_2,
        fontes=["unidades"], forcar=True,  # a queda e' REAL nesta fixture, nao coleta parcial
    )

    ponte_dir = m.ponte_dir_de(base)
    antes = m.ler_ponte_identidade(ponte_dir, semanas=[SEMANA_1])
    agora = m.ler_snapshots(base, semanas=[SEMANA_2])
    sumiram = set(antes["chave_snapshot"]) - set(agora["chave_snapshot"])
    assert sumiram, "a fixture precisa de chave que saiu, senao o teste nao mede nada"

    nomes = set(antes.loc[antes["chave_snapshot"].isin(sumiram), "nome"].astype(str))
    assert all(n.startswith("beta unidade") for n in nomes)


def test_ponte_mora_FORA_da_arvore_da_serie(serie_de_duas_semanas: tuple[Path, Path, Path]) -> None:
    """Um parquet de outro schema DENTRO da árvore da série quebraria `ler_snapshots`.

    A leitura declara um `schema=` só — o do snapshot —, e varre a raiz inteira. E `ler_snapshots`
    é o insumo de S3/S4, então o estrago sairia longe da causa. Por isso a ponte é árvore IRMÃ.
    """
    _un, base, ponte_dir = serie_de_duas_semanas
    assert ponte_dir.is_dir()
    assert base.resolve() not in ponte_dir.resolve().parents
    assert ponte_dir.name == m.PONTE_DIR_DEFAULT.name
    assert len(m.ler_snapshots(base)) == 12  # a serie segue legivel e intacta


def test_ponte_colapsa_colisao_pela_MESMA_linha_do_snapshot(tmp_path: Path) -> None:
    """Achado da revisão automática no PR #386, travado.

    Duas linhas com a MESMA chave e hashes diferentes são COLAPSADAS nas duas funções (nunca
    desambiguadas por ordinal — a colisão é falso negativo deliberado). O que este teste mede é que
    elas colapsam para a **mesma** linha: `montar_snapshot` ordena por `hash_campos_raspados` antes
    do `drop_duplicates`, e a ponte precisa do MESMO desempate. Sem isso, cada uma guardaria a linha
    que viesse primeiro no CSV, e a ficha exibiria o nome e a coordenada de uma academia que o
    snapshot não manteve — com as duas funções "certas" isoladamente.

    Puro, sem I/O: mesmo frame de trabalho entra nas duas.
    """
    un, vazio = tmp_path / "un", tmp_path / "vazio"
    un.mkdir(parents=True)
    vazio.mkdir()
    pd.DataFrame(
        {
            # Nome idêntico + mesma célula => MESMA chave; coordenadas distintas => hash distinto.
            "nome_unidade": ["Selfit Centro", "Selfit Centro"],
            "latitude": [-23.5500, -23.5501],
            "longitude": [-46.6300, -46.6301],
            "data_coleta": ["2026-07-27", "2026-07-27"],
        }
    ).to_csv(un / "unidades_selfit.csv", sep=";", encoding="utf-8-sig", index=False)

    bruto = m.ler_feeds(vazio, vazio, un, fontes=["unidades"])
    limpo, _ = m.limpar_ruido(bruto)
    com_chave = m.derivar_chave(m.calcular_hash_campos_raspados(limpo))
    snapshot, auditoria = m.montar_snapshot(com_chave, fontes_lidas="unidades")
    ponte = m.montar_ponte_identidade(com_chave)

    assert auditoria["chaves_colapsadas"] == 1, "a fixture precisa COLIDIR, senao nao mede nada"
    assert len(snapshot) == 1 and len(ponte) == 1

    sobrevivente = com_chave[
        com_chave["hash_campos_raspados"].astype(str) == str(snapshot.iloc[0]["hash_campos_raspados"])
    ].iloc[0]
    assert float(ponte.iloc[0]["lat"]) == pytest.approx(float(sobrevivente["latitude"]))
    assert float(ponte.iloc[0]["lng"]) == pytest.approx(float(sobrevivente["longitude"]))


def test_semana_reprovada_nao_deixa_ponte_orfa(tmp_path: Path) -> None:
    """As duas árvores nunca podem discordar sobre quais semanas existem.

    Uma ponte de semana que a guarda de coleta parcial RECUSOU descreveria chaves que a série não
    tem — e o consumidor leria identidade de um evento que nunca foi publicado.
    """
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    _escrever_rede(un, "alfa", 20, data_coleta="2026-07-27")
    m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_1,
        fontes=["unidades"],
    )
    _escrever_rede(un, "alfa", 6, data_coleta="2026-08-03")  # -70%: a guarda reprova
    _, auditoria = m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=REF_2,
        fontes=["unidades"],
    )

    assert auditoria["publicado"] is False
    ponte_dir = m.ponte_dir_de(base)
    assert not (ponte_dir / f"semana={SEMANA_2}").exists()
    assert (ponte_dir / f"semana={SEMANA_1}").is_dir()
