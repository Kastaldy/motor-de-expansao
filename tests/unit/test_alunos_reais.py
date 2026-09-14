"""Crosswalk de alunos reais por unidade (BLK-ALUNOS-01).

O modulo casa planilha de alunos (`data/validacao/`) com unidade mapeada (coletor proprio
+ feed WellHub). O risco nao e' o calculo -- e' o MATCH: casar errado poe o numero de uma
academia no tooltip de outra, e o operador nao tem como auditar isso na tela.

Por isso os testes aqui sao quase todos sobre a FORMA do match, nao sobre aritmetica:
o que a normalizacao pode e nao pode colapsar, e o que cada trava impede.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.pipelines.alunos_reais import (
    LIMIAR_FUZZY,
    PONTE_RAIO_M,
    _casar_por_contencao,
    _casar_por_nome,
    _ponte_por_coordenada,
    _subsequencia_de,
    chave_rotulo,
    ler_coords_smart_fit,
    montar_crosswalk,
    montar_pool,
    normalizar,
    normalizar_sequencia,
    remover_uf_terminal,
)


def _pool(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    df["chave"] = df["nome_unidade"].map(chave_rotulo)
    for col, padrao in (("uf", None), ("lat", 0.0), ("lng", 0.0)):
        if col not in df.columns:
            df[col] = padrao
    return df


def _alvos(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    df["chave"] = df["rotulo_fonte"].map(chave_rotulo)
    if "uf" not in df.columns:
        df["uf"] = ""
    return df


# ---------------------------------------------------------------------------
# Normalizacao -- o que derruba a taxa de match e' ortografico
# ---------------------------------------------------------------------------


def test_normalizar_tira_acento_caixa_e_pontuacao() -> None:
    assert normalizar("Água Rasa - SP!") == "agua rasa sp"


def test_remove_uf_terminal_do_rotulo_do_coletor() -> None:
    """`Vila Granada - SP` e `Vila Granada` sao a mesma academia."""
    assert remover_uf_terminal("vila granada sp") == "vila granada"


def test_uf_terminal_nao_come_rotulo_de_um_token_so() -> None:
    """`SP` sozinho e' o rotulo inteiro; virar string vazia casaria com qualquer coisa."""
    assert remover_uf_terminal("sp") == "sp"


def test_prefixo_de_rede_sai_do_rotulo() -> None:
    """A Pacer casava 0 de 13: as 12 unidades estavam la, todas prefixadas com a marca."""
    assert chave_rotulo("PACER Ribeirania") == "ribeirania"
    assert chave_rotulo("SkyFit Academia - Vila Nova") == "vila nova"


def test_numeracao_administrativa_sai_do_rotulo() -> None:
    assert chave_rotulo("12 - REDFIT - Matriz Pasteur") == "matriz pasteur"


def test_sequencia_romana_vira_arabe() -> None:
    """`Sertaozinho II` x `Sertaozinho 2` da 0,89 e morreria abaixo do corte."""
    assert chave_rotulo("SERTAOZINHO II") == "sertaozinho 2"
    assert chave_rotulo("Bonfim I") == "bonfim 1"


def test_sequencia_so_converte_o_ultimo_token() -> None:
    """`Vila` nao pode virar numero, e `V` sozinho pode ser o nome da academia."""
    assert normalizar_sequencia("vila rica") == "vila rica"
    assert normalizar_sequencia("v") == "v"


# ---------------------------------------------------------------------------
# Match por nome -- o corte e o recorte de UF
# ---------------------------------------------------------------------------


def test_casa_rotulos_equivalentes_apos_normalizacao() -> None:
    casado = _casar_por_nome(
        _alvos([{"rotulo_fonte": "Vila Granada", "uf": "SP"}]),
        _pool([{"nome_unidade": "Vila Granada - SP", "uf": "SP"}]),
    )
    assert list(casado) == [0]
    assert casado[0][0] >= LIMIAR_FUZZY


def test_uf_impede_o_centro_de_uma_cidade_casar_com_o_de_outra() -> None:
    """`Centro` existe em quase todo municipio -- sem o recorte o score seria 1,000.

    Match perfeito e completamente errado e' o pior desfecho possivel aqui: nada no
    numero denuncia que ele veio do outro lado do pais.
    """
    casado = _casar_por_nome(
        _alvos([{"rotulo_fonte": "Centro", "uf": "AM"}]),
        _pool([{"nome_unidade": "Centro", "uf": "RS"}]),
    )
    assert casado == {}


def test_abaixo_do_corte_nao_casa() -> None:
    casado = _casar_por_nome(
        _alvos([{"rotulo_fonte": "Jardim Paulista", "uf": "SP"}]),
        _pool([{"nome_unidade": "Vila Mariana", "uf": "SP"}]),
    )
    assert casado == {}


def test_candidato_nao_e_reusado_por_dois_alvos() -> None:
    """Sem exclusao mutua, duas unidades receberiam a MESMA coordenada."""
    casado = _casar_por_nome(
        _alvos([
            {"rotulo_fonte": "Vila Nova", "uf": "SP"},
            {"rotulo_fonte": "Vila Nova", "uf": "SP"},
        ]),
        _pool([{"nome_unidade": "Vila Nova", "uf": "SP"}]),
    )
    assert len(casado) == 1


def test_candidato_ocupado_por_rota_anterior_nao_e_reatribuido() -> None:
    """O defeito real da 1a versao: 9 pinos saiam com DUAS contagens de alunos.

    Cada rota comecava com o pool limpo, entao a contencao e a ponte podiam tomar um
    candidato que o nome ja tinha levado -- e no merge uma das duas vencia em silencio.
    """
    pool = _pool([{"nome_unidade": "Vila Nova", "uf": "SP"}])
    casado = _casar_por_nome(
        _alvos([{"rotulo_fonte": "Vila Nova", "uf": "SP"}]), pool, ocupados={0}
    )
    assert casado == {}


# ---------------------------------------------------------------------------
# Contencao -- a rota permissiva, e as travas que a tornam usavel
# ---------------------------------------------------------------------------


def test_subsequencia_exige_bloco_contiguo() -> None:
    assert _subsequencia_de(["desvio", "rizzo"], ["desvio", "rizzo", "caxias"])
    assert not _subsequencia_de(["desvio", "caxias"], ["desvio", "rizzo", "caxias"])


def test_contencao_casa_bairro_com_bairro_mais_cidade() -> None:
    """`ECB - DESVIO RIZZO` x `Desvio Rizzo - Caxias do Sul` da 0,63 no fuzzy."""
    casado = _casar_por_contencao(
        _alvos([{"rotulo_fonte": "ECB - DESVIO RIZZO, RS", "uf": "RS"}]),
        _pool([{"nome_unidade": "Desvio Rizzo - Caxias do Sul, RS", "uf": "RS"}]),
        set(),
    )
    assert list(casado) == [0]


def test_contencao_recusa_rotulo_de_um_token_so() -> None:
    """Fragmento produz contencao falsa.

    Medido na 1a versao: `Alvorada` casou com `Nova Iguacu - Jardim Alvorada` e `Goias`
    com `Assai SCS - Av. Goias` -- unicos na UF e ambos errados.
    """
    casado = _casar_por_contencao(
        _alvos([{"rotulo_fonte": "Alvorada", "uf": "RJ"}]),
        _pool([{"nome_unidade": "Nova Iguacu - Jardim Alvorada", "uf": "RJ"}]),
        set(),
    )
    assert casado == {}


def test_contencao_recusa_quando_ha_dois_candidatos() -> None:
    """Com dois, escolher o primeiro da lista e' sorteio disfarcado de match."""
    casado = _casar_por_contencao(
        _alvos([{"rotulo_fonte": "Jardim Paulista", "uf": "SP"}]),
        _pool([
            {"nome_unidade": "Jardim Paulista Norte", "uf": "SP"},
            {"nome_unidade": "Jardim Paulista Sul", "uf": "SP"},
        ]),
        set(),
    )
    assert casado == {}


def test_contencao_nao_reavalia_quem_o_nome_ja_casou() -> None:
    casado = _casar_por_contencao(
        _alvos([{"rotulo_fonte": "Desvio Rizzo", "uf": "RS"}]),
        _pool([{"nome_unidade": "Desvio Rizzo - Caxias do Sul", "uf": "RS"}]),
        {0},
    )
    assert casado == {}


def test_contencao_grava_score_real_e_nao_teto() -> None:
    """Cravar 1,0 esconderia da auditoria o quanto os dois rotulos divergem."""
    casado = _casar_por_contencao(
        _alvos([{"rotulo_fonte": "Desvio Rizzo", "uf": "RS"}]),
        _pool([{"nome_unidade": "Desvio Rizzo - Caxias do Sul", "uf": "RS"}]),
        set(),
    )
    assert casado[0][0] < 1.0


# ---------------------------------------------------------------------------
# Ponte por coordenada
# ---------------------------------------------------------------------------


def test_ponte_resgata_pelo_endereco_quem_o_nome_nao_alcancou() -> None:
    """Coordenada nao tem variante ortografica; a mediana medida foi de 19 m."""
    coords = pd.DataFrame(
        {"chave": ["paseo joinville"], "lat": [-26.3044], "lng": [-48.8487], "uf": [None]}
    )
    casado = _ponte_por_coordenada(
        _alvos([{"rotulo_fonte": "Paseo Joinville", "uf": "SC"}]),
        _pool([{"nome_unidade": "Shopping Paseo", "uf": "SC", "lat": -26.3045, "lng": -48.8488}]),
        coords,
        set(),
    )
    assert list(casado) == [0]


def test_ponte_recusa_pino_alem_do_raio() -> None:
    """Fora de `PONTE_RAIO_M` sao academias diferentes, por mais parecido que seja o nome."""
    coords = pd.DataFrame(
        {"chave": ["centro"], "lat": [-23.55], "lng": [-46.63], "uf": [None]}
    )
    casado = _ponte_por_coordenada(
        _alvos([{"rotulo_fonte": "Centro", "uf": "SP"}]),
        _pool([{"nome_unidade": "Outro", "uf": "SP", "lat": -23.60, "lng": -46.70}]),
        coords,
        set(),
    )
    assert casado == {}
    assert PONTE_RAIO_M == 150.0


def test_ponte_sem_planilha_de_coordenada_e_no_op() -> None:
    """`NAO_ABRA/` e' gitignored -- ausencia e' caminho normal, nao erro."""
    casado = _ponte_por_coordenada(
        _alvos([{"rotulo_fonte": "X", "uf": "SP"}]),
        _pool([{"nome_unidade": "X", "uf": "SP"}]),
        pd.DataFrame(columns=["chave", "lat", "lng", "uf"]),
        set(),
    )
    assert casado == {}


def test_coords_smart_fit_ausentes_devolvem_frame_vazio(tmp_path) -> None:
    assert ler_coords_smart_fit(tmp_path / "nao_existe.xlsx").empty


# ---------------------------------------------------------------------------
# Contrato de saida
# ---------------------------------------------------------------------------


def _leitor_fake(linhas: list[dict]):
    def _ler() -> pd.DataFrame:
        return pd.DataFrame(linhas)

    return _ler


def test_alunos_total_soma_planos_e_agregador() -> None:
    """Convencao do Felipe e das proprias fontes: aluno de plataforma conta."""
    cross, _ = montar_crosswalk(
        pool=_pool([{"nome_unidade": "Vila Nova", "rede": "redfit", "uf": "SP",
                     "concorrente_id": "c1", "hex_id_res7": "87a"}]),
        leitores=(
            _leitor_fake([{
                "rede": "redfit", "rotulo_fonte": "Vila Nova", "uf": "SP",
                "alunos_planos": 371.0, "alunos_agregador": 518.0, "alunos_total": 889.0,
                "metragem": None, "fonte_alunos": "teste",
            }]),
        ),
        coords_smart_fit=pd.DataFrame(columns=["chave", "lat", "lng", "uf"]),
    )
    assert float(cross["alunos_total"].iloc[0]) == 889.0
    assert float(cross["alunos_planos"].iloc[0]) == 371.0
    assert float(cross["alunos_agregador"].iloc[0]) == 518.0


def test_confianca_media_e_reservada_a_contencao() -> None:
    """A tela le so' `alta`. Contencao e' inferencia e o operador nao pode auditar."""
    cross, _ = montar_crosswalk(
        pool=_pool([{"nome_unidade": "Desvio Rizzo - Caxias do Sul", "rede": "engenharia_do_corpo",
                     "uf": "RS", "concorrente_id": "c1", "hex_id_res7": "87a"}]),
        leitores=(
            _leitor_fake([{
                "rede": "engenharia_do_corpo", "rotulo_fonte": "ECB - DESVIO RIZZO, RS",
                "uf": "RS", "alunos_planos": 100.0, "alunos_agregador": None,
                "alunos_total": 100.0, "metragem": None, "fonte_alunos": "teste",
            }]),
        ),
        coords_smart_fit=pd.DataFrame(columns=["chave", "lat", "lng", "uf"]),
    )
    assert cross["metodo_match"].iloc[0] == "contencao_uf"
    assert cross["confianca_match"].iloc[0] == "media"


def test_auditoria_sai_mesmo_com_zero_match() -> None:
    """Distingue "rede sem planilha" de "planilha existe e nao casou nada".

    Um parquet vazio confunde os dois estados, e o segundo e' um defeito silencioso.
    """
    cross, auditoria = montar_crosswalk(
        pool=_pool([{"nome_unidade": "Outra Coisa", "rede": "redfit", "uf": "SP",
                     "concorrente_id": "c1", "hex_id_res7": "87a"}]),
        leitores=(
            _leitor_fake([{
                "rede": "redfit", "rotulo_fonte": "Vila Nova", "uf": "SP",
                "alunos_planos": 1.0, "alunos_agregador": None, "alunos_total": 1.0,
                "metragem": None, "fonte_alunos": "teste",
            }]),
        ),
        coords_smart_fit=pd.DataFrame(columns=["chave", "lat", "lng", "uf"]),
    )
    assert cross.empty
    assert len(auditoria) == 1
    assert int(auditoria["n_com_alunos"].iloc[0]) == 1
    assert int(auditoria["n_casadas"].iloc[0]) == 0


def test_nenhum_pino_recebe_duas_contagens() -> None:
    """Invariante de saida do artefato inteiro, nao de uma rota."""
    cross, _ = montar_crosswalk(
        pool=_pool([
            {"nome_unidade": "Vila Nova", "rede": "redfit", "uf": "SP",
             "concorrente_id": "c1", "hex_id_res7": "87a"},
            {"nome_unidade": "Vila Nova Centro", "rede": "redfit", "uf": "SP",
             "concorrente_id": "c2", "hex_id_res7": "87b"},
        ]),
        leitores=(
            _leitor_fake([
                {"rede": "redfit", "rotulo_fonte": "Vila Nova", "uf": "SP",
                 "alunos_planos": 10.0, "alunos_agregador": None, "alunos_total": 10.0,
                 "metragem": None, "fonte_alunos": "teste"},
                {"rede": "redfit", "rotulo_fonte": "Vila Nova Centro", "uf": "SP",
                 "alunos_planos": 20.0, "alunos_agregador": None, "alunos_total": 20.0,
                 "metragem": None, "fonte_alunos": "teste"},
            ]),
        ),
        coords_smart_fit=pd.DataFrame(columns=["chave", "lat", "lng", "uf"]),
    )
    assert not cross["concorrente_id"].dropna().duplicated().any()


@pytest.mark.parametrize("faltando", ["concorrentes", "wellhub", "estrutural"])
def test_pool_com_fonte_ausente_avisa_em_vez_de_levantar(tmp_path, faltando) -> None:
    """As fontes sao gitignored: nao existem em CI nem em checkout novo.

    Levantar aqui faria a cadeia inteira falhar por causa de uma fonte opcional -- que
    e' exatamente o defeito de `base_multirede.py`, cujas duas de tres funcoes hoje
    levantam `FileNotFoundError` e ninguem percebeu.
    """
    conc = tmp_path / "conc.parquet"
    wh = tmp_path / "wh.parquet"
    estr = tmp_path / "estr.parquet"
    if faltando != "concorrentes":
        pd.DataFrame({
            "concorrente_id": ["c1"], "rede": ["redfit"], "nome_unidade": ["X"],
            "lat": [-23.5], "lng": [-46.6], "hex_id_res7": ["87a"], "status_registro": ["valido"],
        }).to_parquet(conc)
    if faltando != "wellhub":
        pd.DataFrame({
            "rede": ["redfit"], "nome": ["Y"], "lat": [-23.5], "lng": [-46.6],
            "hex_id_res7": ["87a"],
        }).to_parquet(wh)
    if faltando != "estrutural":
        pd.DataFrame({"hex_id": ["87a"], "uf": ["SP"]}).to_parquet(estr)

    pool = montar_pool(concorrentes_path=conc, wellhub_path=wh, estrutural_path=estr)
    assert isinstance(pool, pd.DataFrame)


def test_unidade_so_do_wellhub_entra_sem_concorrente_id(tmp_path) -> None:
    """Ela serve ao residual mas NAO tem pino para receber tooltip.

    A diferenca precisa ser legivel no artefato, nao inferida de um id vazio pelo leitor.
    """
    conc = tmp_path / "conc.parquet"
    wh = tmp_path / "wh.parquet"
    estr = tmp_path / "estr.parquet"
    pd.DataFrame({
        "concorrente_id": ["c1"], "rede": ["redfit"], "nome_unidade": ["X"],
        "lat": [-23.5], "lng": [-46.6], "hex_id_res7": ["87a"], "status_registro": ["valido"],
    }).to_parquet(conc)
    pd.DataFrame({
        "rede": ["redfit"], "nome": ["Y"], "lat": [-23.4], "lng": [-46.5],
        "hex_id_res7": ["87a"],
    }).to_parquet(wh)
    pd.DataFrame({"hex_id": ["87a"], "uf": ["SP"]}).to_parquet(estr)

    pool = montar_pool(concorrentes_path=conc, wellhub_path=wh, estrutural_path=estr)
    so_wellhub = pool[pool["fonte_coord"].eq("wellhub")]
    assert len(so_wellhub) == 1
    assert so_wellhub["concorrente_id"].isna().all()
    assert pool[pool["fonte_coord"].eq("coletor_proprio")]["concorrente_id"].notna().all()
