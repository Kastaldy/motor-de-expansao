"""DEC-064 (D2): churn/staleness como estado materializado e incremental.

**O teste que carrega o bloco é o de EQUIVALÊNCIA.** Varredura completa é consistente por
construção; incremental acumula erro se um passo for perdido ou se a regra mudar. A DEC repõe essa
garantia com `--reprocessar`, e a única forma de a reposição não ser uma promessa é medir: aplicar as
semanas uma a uma tem de produzir **exatamente** o mesmo frame de 19 colunas que
`extrair_churn_staleness` produz varrendo as mesmas semanas de uma vez.

Os demais testes cobrem o que é fácil errar em incremental e difícil de ver depois:

  * **idempotência por semana** — cron que roda duas vezes no mesmo domingo não pode somar
    `n_semanas_presente` nem envelhecer `semanas_sem_mudanca`;
  * **gap de feed não vira churn** — escopo `(fonte, rede)` não observado não avança o relógio da
    chave, que é a defesa de maior valor do algoritmo (sinal de peso ~0,467);
  * **`reprocessar` lê uma semana por vez** — reconstruir carregando a série inteira devolveria o
    pico de RSS que a DEC existe para eliminar, na única função onde ninguém notaria.

Fixtures 100% sintéticas.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import churn_estado as e
from motor_expansao.vulnerabilidade import contrato as c
from motor_expansao.vulnerabilidade import snapshots as m
from motor_expansao.vulnerabilidade.churn_staleness import extrair_churn_staleness

# 2026-31 .. 2026-34, uma segunda-feira por semana ISO.
REFS = [date(2026, 7, 27), date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 17)]
SEMANAS = ["2026-31", "2026-32", "2026-33", "2026-34"]


def _escrever_rede(dir_unidades: Path, rede: str, n: int, *, data_coleta: str) -> None:
    dir_unidades.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "nome_unidade": [f"{rede} unidade {i}" for i in range(n)],
            "latitude": [-23.55 - i * 0.01 for i in range(n)],
            "longitude": [-46.63 - i * 0.01 for i in range(n)],
            "data_coleta": [data_coleta] * n,
        }
    ).to_csv(dir_unidades / f"unidades_{rede}.csv", sep=";", encoding="utf-8-sig", index=False)


def _publicar(tmp_path: Path, base: Path, un: Path, ref: date) -> pd.DataFrame:
    """Materializa a semana de `ref` e devolve o snapshot gravado (13 colunas, sem `semana`)."""
    snapshot, auditoria = m.materializar(
        tmp_path / "tp", tmp_path / "wh", un, base_dir=base, data_referencia=ref,
        fontes=["unidades"], forcar=True,
    )
    assert auditoria["publicado"] is True
    return snapshot


# --------------------------------------------------------------------------- #
# A propriedade central: incremental == varredura
# --------------------------------------------------------------------------- #
def test_incremental_bate_com_a_varredura_completa(tmp_path: Path) -> None:
    """Quatro semanas com entrada, saída, reaparecimento e hash parado.

    O desenho da fixture é o ponto: se as semanas fossem todas iguais, o teste passaria com um
    incremental errado. Aqui a série exercita os quatro `status_churn` possíveis — `beta` sai na 3ª e
    volta na 4ª (`piscando`), `gama` nasce na 2ª, `alfa` nunca muda de hash (`semanas_sem_mudanca`
    crescendo), e a saída da `beta` tem de contar exatamente UM desaparecimento.
    """
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    estado, obs = e.estado_vazio(), e.observabilidade_vazia()

    for i, (ref, semana) in enumerate(zip(REFS, SEMANAS, strict=True)):
        coleta = ref.isoformat()
        _escrever_rede(un, "alfa", 5, data_coleta=coleta)
        if i >= 1:
            _escrever_rede(un, "gama", 3, data_coleta=coleta)
        if i == 2:
            (un / "unidades_beta.csv").unlink(missing_ok=True)
        else:
            _escrever_rede(un, "beta", 4, data_coleta=coleta)

        snapshot = _publicar(tmp_path, base, un, ref)
        estado, obs = e.aplicar_semana(estado, obs, snapshot, semana=semana)

    incremental = e.churn_do_estado(estado, obs)
    varredura = extrair_churn_staleness(base)

    assert not varredura.empty
    pd.testing.assert_frame_equal(incremental, varredura)


def test_reprocessar_reconstroi_o_mesmo_estado(tmp_path: Path) -> None:
    """`--reprocessar` é o caminho de reposição da consistência — tem de bater com a varredura."""
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    for i, ref in enumerate(REFS[:3]):
        _escrever_rede(un, "alfa", 5, data_coleta=ref.isoformat())
        if i != 1:  # `beta` falta na semana do meio
            _escrever_rede(un, "beta", 4, data_coleta=ref.isoformat())
        else:
            (un / "unidades_beta.csv").unlink(missing_ok=True)
        _publicar(tmp_path, base, un, ref)

    estado, obs = e.reprocessar(base)
    pd.testing.assert_frame_equal(e.churn_do_estado(estado, obs), extrair_churn_staleness(base))


# --------------------------------------------------------------------------- #
# O que e' facil errar em incremental
# --------------------------------------------------------------------------- #
def test_reaplicar_a_mesma_semana_e_no_op(tmp_path: Path) -> None:
    """Cron que roda duas vezes no mesmo domingo não pode envelhecer a série.

    Sem idempotência, `n_semanas_presente` somaria e `semanas_sem_mudanca` avançaria sem que nada
    tivesse acontecido no mundo — e `v4` (staleness) leria negócio parado onde houve só um retry.
    """
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    _escrever_rede(un, "alfa", 5, data_coleta=REFS[0].isoformat())
    snapshot = _publicar(tmp_path, base, un, REFS[0])

    estado, obs = e.aplicar_semana(e.estado_vazio(), e.observabilidade_vazia(), snapshot, semana=SEMANAS[0])
    de_novo, obs2 = e.aplicar_semana(estado, obs, snapshot, semana=SEMANAS[0])

    pd.testing.assert_frame_equal(estado, de_novo)
    pd.testing.assert_frame_equal(obs, obs2)


def test_escopo_nao_observado_nao_avanca_o_relogio_da_chave(tmp_path: Path) -> None:
    """Gap de feed NÃO pode virar churn — a defesa de maior valor do algoritmo.

    A rede `beta` não aparece na semana 2 porque o coletor dela caiu; o feed `unidades` é um CSV por
    rede, então a fonte continua "observada" pelas outras. Se o eixo fosse a FONTE, as 4 unidades da
    `beta` virariam `sumiu_recente` de uma vez — falso positivo em massa no sinal de peso ~0,467.
    """
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    _escrever_rede(un, "alfa", 5, data_coleta=REFS[0].isoformat())
    _escrever_rede(un, "beta", 4, data_coleta=REFS[0].isoformat())
    s1 = _publicar(tmp_path, base, un, REFS[0])
    estado, obs = e.aplicar_semana(e.estado_vazio(), e.observabilidade_vazia(), s1, semana=SEMANAS[0])

    (un / "unidades_beta.csv").unlink()
    _escrever_rede(un, "alfa", 5, data_coleta=REFS[1].isoformat())
    s2 = _publicar(tmp_path, base, un, REFS[1])
    estado, obs = e.aplicar_semana(estado, obs, s2, semana=SEMANAS[1])

    churn = e.churn_do_estado(estado, obs)
    beta = churn[churn["rede"].astype(str) == "beta"]
    assert len(beta) == 4
    assert set(beta["status_churn"].astype(str)) == {"novo"}, "gap de feed virou churn"
    assert set(beta["n_desaparecimentos"].astype(int)) == {0}
    assert set(beta["n_semanas_serie"].astype(int)) == {1}, "semana nao observada entrou no eixo"


def test_hash_parado_envelhece_e_mudanca_reseta(tmp_path: Path) -> None:
    """`semanas_sem_mudanca` conta observações APÓS a última mudança, e reseta na semana dela."""
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    estado, obs = e.estado_vazio(), e.observabilidade_vazia()
    for ref, semana in zip(REFS[:3], SEMANAS[:3], strict=True):
        _escrever_rede(un, "alfa", 5, data_coleta=ref.isoformat())
        estado, obs = e.aplicar_semana(estado, obs, _publicar(tmp_path, base, un, ref), semana=semana)
    assert set(estado["semanas_sem_mudanca"].astype(int)) == {2}

    # SÓ a unidade 0 muda de coordenada (~40 m): o cadastro dela muda, a célula da chave não.
    longitudes = [-46.63 - i * 0.01 for i in range(5)]
    longitudes[0] -= 0.0005
    chaves_antes = set(estado["chave_snapshot"].astype(str))
    pd.DataFrame(
        {
            "nome_unidade": [f"alfa unidade {i}" for i in range(5)],
            "latitude": [-23.55 - i * 0.01 for i in range(5)],
            "longitude": longitudes,
            "data_coleta": [REFS[3].isoformat()] * 5,
        }
    ).to_csv(un / "unidades_alfa.csv", sep=";", encoding="utf-8-sig", index=False)
    estado, obs = e.aplicar_semana(estado, obs, _publicar(tmp_path, base, un, REFS[3]), semana=SEMANAS[3])

    assert set(estado["chave_snapshot"].astype(str)) == chaves_antes, (
        "a mexida na coordenada trocou a CHAVE: o teste passaria a medir entrada de chave nova, "
        "que e' outra coisa"
    )
    zerados = int((estado["semanas_sem_mudanca"].astype(int) == 0).sum())
    assert zerados == 1, "a mudanca de hash tem de resetar exatamente a chave que mudou"
    assert int(estado["semanas_sem_mudanca"].astype(int).max()) == 3


# --------------------------------------------------------------------------- #
# I/O e fronteiras
# --------------------------------------------------------------------------- #
def test_estado_mora_fora_da_arvore_da_serie_e_deriva_do_base_dir(tmp_path: Path) -> None:
    """Mesma lição que a ponte do D3 custou neste bloco: default derivado, nunca absoluto."""
    base = tmp_path / "staging" / "snapshots_concorrentes"
    destino = e.estado_dir_de(base)
    assert destino.name == e.ESTADO_DIR_DEFAULT.name
    assert destino.parent == base.parent
    assert base.resolve() not in destino.resolve().parents
    assert e.estado_dir_de(base, tmp_path / "outro") == tmp_path / "outro"


def test_ausencia_de_estado_devolve_vazio_bem_formado(tmp_path: Path) -> None:
    """Primeira execução não é erro — é o estado legítimo de uma série que começa agora."""
    estado, obs = e.ler_estado(tmp_path / "nao_existe")
    assert estado.empty and obs.empty
    assert list(estado.columns) == list(c.CONTRATO_COLUNAS_CHURN_ESTADO)
    assert list(obs.columns) == list(c.CONTRATO_COLUNAS_OBSERVABILIDADE)
    assert e.churn_do_estado(estado, obs).empty


def test_ida_e_volta_no_disco_preserva_o_estado(tmp_path: Path) -> None:
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    _escrever_rede(un, "alfa", 5, data_coleta=REFS[0].isoformat())
    snapshot = _publicar(tmp_path, base, un, REFS[0])

    auditoria = e.atualizar(snapshot, base, semana=SEMANAS[0])
    assert auditoria["modo"] == "incremental"
    assert auditoria["chaves_no_estado"] == 5

    estado, obs = e.ler_estado(e.estado_dir_de(base))
    assert len(estado) == 5
    assert list(estado.columns) == list(c.CONTRATO_COLUNAS_CHURN_ESTADO)
    assert set(estado["versao_contrato"].astype(str)) == {c.VERSAO_CONTRATO_CHURN_ESTADO}
    assert len(obs) == 1  # um unico escopo (unidades, alfa) numa semana


def test_atualizar_com_reprocessar_ignora_o_estado_do_disco(tmp_path: Path) -> None:
    """O reprocessamento é função da SÉRIE — senão deixa de ser reproduzível."""
    un, base = tmp_path / "un", tmp_path / "staging" / "snapshots_concorrentes"
    _escrever_rede(un, "alfa", 5, data_coleta=REFS[0].isoformat())
    snapshot = _publicar(tmp_path, base, un, REFS[0])
    e.atualizar(snapshot, base, semana=SEMANAS[0])

    # Estado corrompido a mao: o reprocessamento tem de ignora-lo e reconstruir da serie.
    destino = e.estado_dir_de(base)
    e.escrever_estado(e.estado_vazio(), e.observabilidade_vazia(), destino)
    assert e.ler_estado(destino)[0].empty

    auditoria = e.atualizar(snapshot, base, semana=SEMANAS[0], reprocessar_tudo=True)
    assert auditoria["modo"] == "reprocessado"
    assert auditoria["chaves_no_estado"] == 5


def test_troca_de_origem_no_escopo_durante_gap_da_chave(tmp_path: Path) -> None:
    """Achado da revisão automática no PR #387, travado — e é o caso que o resto da suíte não vê.

    `flag_troca_chave_na_serie` pergunta se o conjunto de `chave_origem` do **ESCOPO** mudou entre
    semanas consecutivas. A varredura compara o histórico do escopo inteiro, **inclusive as semanas
    em que uma dada chave está ausente**. A 1ª versão deste módulo guardava as origens por CHAVE, e
    então só enxergava a última semana em que ELA foi vista: com gap de presença coincidindo com a
    troca de origem no escopo, incremental dava `False` e varredura dava `True`.

    O furo passou despercebido porque **todos os outros testes usam a fonte `unidades`**, onde
    `chave_origem` é sempre `hash_estavel` e a coluna nunca varia — ou seja, a suíte de equivalência
    não exercitava a dimensão que a coluna mede. Aqui a fonte é `wellhub`, com `slug`.

    Cenário: `k_gap` está presente nas semanas 1 e 4; nas semanas 2 e 3 o escopo é observado por
    outra chave e migra de `slug` para `hash_estavel`.
    """
    import h3

    hex_id = h3.latlng_to_cell(-23.5500, -46.6300, 7)

    def _linha(chave: str, origem: str, hash_: str = "h0") -> dict[str, object]:
        return {
            "snapshot_date": "2026-01-05",
            "slug": chave,
            "concorrente_id": "0" * 40,
            "chave_snapshot": chave,
            "chave_origem": origem,
            "hex_id_res7": hex_id,
            "rede": "independente",
            "fonte": "wellhub",
            "hash_campos_raspados": hash_,
            "nota_wellhub": None,
            "qtd_avaliacoes_wellhub": None,
            "fontes_lidas": "wellhub",
            "versao_contrato": c.VERSAO_CONTRATO_SNAPSHOT,
        }

    semanas_linhas = [
        (SEMANAS[0], [_linha("k_gap", "slug"), _linha("k_fixa", "slug")]),
        (SEMANAS[1], [_linha("k_fixa", "hash_estavel")]),  # k_gap ausente; o escopo TROCA de origem
        (SEMANAS[2], [_linha("k_fixa", "hash_estavel")]),
        (SEMANAS[3], [_linha("k_gap", "hash_estavel"), _linha("k_fixa", "hash_estavel")]),
    ]

    estado, obs = e.estado_vazio(), e.observabilidade_vazia()
    injetados = []
    for semana, linhas in semanas_linhas:
        snapshot = pd.DataFrame(linhas, columns=list(c.CONTRATO_COLUNAS_SNAPSHOT.keys()))
        estado, obs = e.aplicar_semana(estado, obs, snapshot, semana=semana)
        com_semana = snapshot.copy()
        com_semana["semana"] = semana
        injetados.append(com_semana)

    incremental = e.churn_do_estado(estado, obs)
    varredura = extrair_churn_staleness(snapshots=injetados)

    assert bool(varredura["flag_troca_chave_na_serie"].all()), (
        "a fixture precisa produzir TROCA na varredura, senao o teste nao mede nada"
    )
    pd.testing.assert_frame_equal(incremental, varredura)


def test_semana_fora_do_formato_iso_levanta() -> None:
    with pytest.raises(ValueError, match="AAAA-SS"):
        e.aplicar_semana(e.estado_vazio(), e.observabilidade_vazia(), pd.DataFrame(), semana="2026-7")
