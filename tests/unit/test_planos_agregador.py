"""Planos dos agregadores (`motor_expansao.dashboard.planos_agregador`).

Trava a forma: preço de teste não vira preço, a Ultra não concorre com ela mesma, e
academia fora do TotalPass não ganha plano por aproximação larga.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dashboard import planos_agregador as pa


def _bruto(linhas):
    base = {
        "slug": "s", "nome": "x", "latitude": "-23.0", "longitude": "-46.0", "cidade": "SP", "uf": "sp",
        "cep": "", "endereco_formatado": "", "modalidades": "Musculação", "plano_totalpass": "TP 1",
        "preco_plano_totalpass": "109.90", "data_coleta": "2026-09-10",
    }
    return pd.DataFrame([{**base, **linha} for linha in linhas])


def test_normalizar_zera_preco_de_teste_e_descarta_sem_coordenada():
    bruto = _bruto(
        [
            {"slug": "a"},
            {"slug": "b", "plano_totalpass": "TP Free", "preco_plano_totalpass": "1.00"},
            {"slug": "c", "latitude": "abc"},
            {"slug": "a"},
            {"slug": "d", "modalidades": "Pilates,Yoga"},
        ]
    )
    q = pa.normalizar(bruto)
    assert list(q["slug"]) == ["a", "b", "d"]
    assert q.loc[q.slug == "b", "preco"].isna().all() and q.loc[q.slug == "b", "plano"].item() == "TP Free"
    assert q.loc[q.slug == "a", "uf"].item() == "SP"
    assert q.loc[q.slug == "d", "musculacao"].item() is False or not q.loc[q.slug == "d", "musculacao"].item()


def test_normalizar_recusa_csv_sem_coluna_do_contrato():
    with pytest.raises(ValueError, match="plano_totalpass"):
        pa.normalizar(_bruto([{}]).drop(columns=["plano_totalpass"]))


def _planos():
    return pa.normalizar(
        _bruto(
            [
                {"slug": "u", "nome": "ULTRA ACADEMIA ACLIMAÇÃO", "latitude": "-23.00005", "plano_totalpass": "TP 2", "preco_plano_totalpass": "199.90"},
                {"slug": "u2", "nome": "Ultra Academia Cambuci", "latitude": "-23.009", "plano_totalpass": "TP 2", "preco_plano_totalpass": "199.90"},
                {"slug": "b", "nome": "Barata", "latitude": "-23.004", "plano_totalpass": "TP 1", "preco_plano_totalpass": "109.90"},
                {"slug": "m", "nome": "Mesmo", "latitude": "-23.005", "plano_totalpass": "TP 2", "preco_plano_totalpass": "199.90"},
                {"slug": "c", "nome": "Cara", "latitude": "-23.006", "plano_totalpass": "TP 4", "preco_plano_totalpass": "499.90"},
                {"slug": "f", "nome": "Teste", "latitude": "-23.007", "plano_totalpass": "TP Free", "preco_plano_totalpass": "1.00"},
                {"slug": "l", "nome": "Longe", "latitude": "-23.5", "plano_totalpass": "TP 1", "preco_plano_totalpass": "109.90"},
            ]
        )
    )


def test_entorno_acha_a_propria_ultra_e_compara_so_com_concorrentes_com_preco():
    r = pa.planos_no_entorno(-23.0, -46.0, _planos())
    assert r["ultra"] == {"nome": "ULTRA ACADEMIA ACLIMAÇÃO", "plano": "TP 2", "preco": 199.9}
    # a outra Ultra sai da concorrência; o TP Free entra na lista mas não na comparação
    assert r["total"] == 4
    assert (r["mais_baratas"], r["mesmo_nivel"], r["mais_caras"]) == (1, 1, 1)
    assert [x["plano"] for x in r["distribuicao"]] == ["TP 1", "TP 2", "TP 4"]
    assert r["academias"][0]["nome"] == "Barata"


def test_sem_ultra_no_feed_nao_inventa_comparacao():
    planos = _planos()
    r = pa.planos_no_entorno(-23.0, -46.0, planos[~planos["nome"].str.contains("ULTRA", case=False)])
    assert r["ultra"] is None and r["mais_baratas"] is None
    assert r["total"] == 4


def test_pino_so_ganha_plano_no_mesmo_ponto():
    pinos = [{"lat": -23.004, "lng": -46.0}, {"lat": -23.3, "lng": -46.0}]
    pa.anexar_planos(pinos, _planos())
    assert pinos[0]["plano"] == "TP 1" and pinos[0]["preco_plano"] == 109.9
    assert pinos[1]["plano"] is None and pinos[1]["preco_plano"] is None
    assert pa.anexar_planos([{"lat": 1.0, "lng": 1.0}], None)[0]["plano"] is None


def _bruto_wellhub(linhas):
    base = {
        "slug": "s", "nome": "x", "latitude": "-23.0", "longitude": "-46.0", "cidade": "SP", "uf": "sp",
        "cep": "", "endereco_formatado": "", "atividades": "Musculação", "nota_wellhub": "4.7",
        "qtd_avaliacoes_wellhub": "10", "tier_wellhub": "Silver", "preco_tier_wellhub": "149.99",
        "data_coleta": "2026-09-14",
    }
    return pd.DataFrame([{**base, **linha} for linha in linhas])


def test_wellhub_normaliza_pela_regua_propria_e_zera_o_digital():
    q = pa.normalizar(
        _bruto_wellhub([{"slug": "a"}, {"slug": "b", "tier_wellhub": "Digital", "preco_tier_wellhub": "0"}]),
        "wellhub",
    )
    assert q.loc[q.slug == "a", ["plano", "preco"]].values.tolist() == [["Silver", 149.99]]
    assert q.loc[q.slug == "b", "preco"].isna().all() and q.loc[q.slug == "a", "musculacao"].item()
    with pytest.raises(ValueError, match="tier_wellhub"):
        pa.normalizar(_bruto_wellhub([{}]).drop(columns=["tier_wellhub"]), "wellhub")
    with pytest.raises(ValueError, match="desconhecida"):
        pa.normalizar(_bruto_wellhub([{}]), "gympass")


def test_pino_recebe_as_duas_fontes_sem_uma_apagar_a_outra():
    wellhub = pa.normalizar(_bruto_wellhub([{"slug": "w", "latitude": "-23.004"}]), "wellhub")
    pinos = [{"lat": -23.004, "lng": -46.0}]
    pa.anexar_planos(pinos, _planos(), fonte="totalpass")
    pa.anexar_planos(pinos, wellhub, fonte="wellhub")
    assert (pinos[0]["plano"], pinos[0]["plano_wellhub"], pinos[0]["preco_plano_wellhub"]) == ("TP 1", "Silver", 149.99)
    assert pa.arquivo_staging("wellhub") == "planos_wellhub.parquet"


def test_entorno_tira_estudio_e_quem_nao_tem_musculacao_e_da_a_media():
    planos = pa.normalizar(
        _bruto(
            [
                {"slug": "b", "nome": "Barata", "latitude": "-23.004", "plano_totalpass": "TP 1", "preco_plano_totalpass": "100"},
                {"slug": "c", "nome": "Cara", "latitude": "-23.005", "plano_totalpass": "TP 3", "preco_plano_totalpass": "300"},
                {"slug": "v", "nome": "Tonus Gym / Vidya Studio - Asa Sul", "latitude": "-23.006", "preco_plano_totalpass": "900"},
                {"slug": "y", "nome": "Yoga da Esquina", "latitude": "-23.007", "modalidades": "Yoga", "preco_plano_totalpass": "900"},
            ]
        )
    )
    padrao = pa.padrao_de_redes({"vidya_studio", "jab_house"})
    r = pa.planos_no_entorno(-23.0, -46.0, planos, excluir_nomes=padrao, somente_musculacao=True)
    assert [a["nome"] for a in r["academias"]] == ["Barata", "Cara"]
    assert (r["media_preco"], r["n_com_preco"]) == (200.0, 2)
    assert pa.planos_no_entorno(-23.0, -46.0, planos)["n_com_preco"] == 4
    assert pa.padrao_de_redes([]) is None


# ---------------------------------------------------------------------------
# Vocabulário V2 de musculação (DEC-025) — BLK-FIX-PLANOS-MUSC-01
# ---------------------------------------------------------------------------

# Rótulos reais da taxonomia nova do WellHub, com as ocorrências medidas no consolidado de
# 2026-08-07 que a DEC-025 usou para escolher o V2: "Treino de força" 19.462, "Fisiculturismo"
# 11.613, "Treino Híbrido" 4.345, "Personal trainer - Levantamento de peso" 1.197, contra
# "Musculação" 140.
ROTULOS_V2 = [
    "Musculação",
    "Treino de força",
    "Fisiculturismo",
    "Treino Híbrido",
    "Personal trainer - Levantamento de peso",
    "Levantamento de Peso Olimpico",
    "Treino muscular",
]


@pytest.mark.parametrize("rotulo", ROTULOS_V2)
def test_a_taxonomia_nova_do_wellhub_conta_como_musculacao(rotulo: str) -> None:
    """O rótulo "Musculação" quase desapareceu do feed entre maio e agosto de 2026.

    Procurar a substring literal é falha SILENCIOSA: a coluna continua lá, só nasce errada.
    Medido em 2026-09-28 no parquet que a produção serve — o WellHub marcava 86,65% das
    22.091 linhas e o V2 marca 100,00%, **+2.949 academias (13,35%)** que desapareciam
    quando o piloto filtra `somente_musculacao=True`.
    """
    assert pa.tem_musculacao(rotulo) is True
    assert pa.tem_musculacao(f"Dança,{rotulo},Funcional,Muay Thai") is True


@pytest.mark.parametrize("rotulo", ["Yoga", "Pilates", "Natação,Hidroginástica", "Cross training", "", None])
def test_quem_nao_oferece_musculacao_continua_de_fora(rotulo: object) -> None:
    """O V2 é superconjunto do V1, não troca de régua: ele não pode passar a marcar estúdio.

    "Cross training" é o caso decisivo — a DEC-025 recusou o V3 exatamente por ele arrastar
    box de CrossFit como se fosse academia de musculação.
    """
    assert pa.tem_musculacao(rotulo) is False


def test_a_coluna_gravada_sai_do_vocabulario_v2_nas_duas_fontes() -> None:
    """Uma régua por fonte seria a mesma taxonomia lida de dois jeitos.

    O WellHub e o TotalPass se renomeiam no TEMPO, não entre si — e a emenda 1 da DEC-025
    estendeu o V2 ao TotalPass por precaução. Medido em 2026-09-28: lá o ganho não é zero
    como a emenda registrou, são **+382 linhas de 17.602** com "Levantamento de Peso
    Olimpico" sem "Musculação" ao lado.
    """
    tp = pa.normalizar(_bruto([{"slug": "a", "modalidades": "Fisiculturismo,Dança"}]))
    assert tp["musculacao"].item() is True or bool(tp["musculacao"].item())

    wh = pa.normalizar(
        _bruto_wellhub([{"slug": "b", "atividades": "Levantamento de peso,CrossFit"}]), "wellhub"
    )
    assert bool(wh["musculacao"].item())


def test_o_vocabulario_e_o_da_dec_025_com_o_termo_base_como_PREFIXO() -> None:
    """`muscula`, não `musculacao`: o prefixo cobre "musculação" E "muscular".

    É a forma que a emenda 1 da DEC-025 fixou ao estender a régua ao TotalPass.
    """
    assert "muscula" in pa.VOCABULARIO_MUSCULACAO_V2
    assert set(pa.VOCABULARIO_MUSCULACAO_V2) == {
        "muscula", "treino de forca", "fisiculturismo", "levantamento de peso", "treino hibrido",
    }


# ---------------------------------------------------------------------------
# A Ultra se reconhece no feed mesmo sem a palavra "academia" no nome
# ---------------------------------------------------------------------------

# Os nomes vêm do parquet que a produção serve, lidos em 2026-09-28. À esquerda, as 10
# listagens nossas que a régua antiga ("ultra academia") perdia; à direita, as marcas ALHEIAS
# que o feed realmente tem. Classificar as duas colunas erradas dói de jeitos diferentes: à
# esquerda a unidade não acha o próprio plano E entra na lista de concorrentes da Ultra
# vizinha; à direita um concorrente real sai da comparação de preço.
NOSSAS_NO_FEED = [
    "Ultra Sagrada Família",
    "ULTRA TAGUATINGA SUL",
    "Ultra Guarapari",
    "ULTRA UNAI",
    "Ultra Jardim das Américas",
    "Ultra André de Barros",
    "Ultra Vila Guanabara",
    "Ultra Berrini",
    "Ultra Villa Branca",
    "ULTRA SÃO GONÇALO",
    # as que a régua antiga já pegava continuam pegadas
    "ULTRA ACADEMIA ACLIMAÇÃO",
    "Ultra Academia - Guarujá",
    "Ultra academia Paranoa",
]
ALHEIAS_NO_FEED = [
    "Academia Ultra Fit",
    "Academia Ultra Fit Heliópolis",
    "Academia Ultra Fitness",
    "Academia Ultra Fitness / Roofbox Crossfit Arrecife",
    "Academia Ultrafit",
    "Academia Ultragym",
    "Academia Ultralife",
    "Academia VO2 MAX Ultra",
    "Edu Ultra Team",
    "Jéssica Dultra Fisioterapia, Pilates e RPG",
    "ULTRA FITNESS",
    "ULTRALINE Trainer",
    "Ultra FitCamp",
    "Ultra Fitness Performance",
    "Smart Fit Ultrabox Águas Lindas de Goiás",
    "Fit box Ultra",
    "Ultra Fit Tancredo Neves",
]


@pytest.mark.parametrize("nome", NOSSAS_NO_FEED)
def test_listagem_da_propria_ultra_e_reconhecida(nome: str) -> None:
    assert pa.e_ultra(nome) is True


@pytest.mark.parametrize("nome", ALHEIAS_NO_FEED)
def test_marca_alheia_com_ultra_no_nome_nao_e_nossa(nome: str) -> None:
    """O que separa os dois grupos é o que vem DEPOIS de "ultra".

    Nas nossas é sempre um LUGAR; nas alheias, palavra genérica de academia. É lista de
    CATEGORIA, não de marca, e por isso envelhece devagar: nome de unidade nossa não usa
    "fit"/"gym"/"box". `Ultrafit`, `Ultrabox` e `Dultra` numa palavra só nem chegam à régua,
    porque `\\bultra\\b` não casa dentro de palavra.
    """
    assert pa.e_ultra(nome) is False


def test_ultra_no_fim_do_nome_nao_e_nossa() -> None:
    """"Academia VO2 MAX Ultra" termina em "ultra": a régua exige algo DEPOIS."""
    assert pa.e_ultra("Academia VO2 MAX Ultra") is False
    assert pa.e_ultra("Ultra") is False
    assert pa.e_ultra("") is False
    assert pa.e_ultra(None) is False


def test_pontuacao_entre_ultra_e_o_lugar_nao_esconde_a_unidade() -> None:
    """"ULTRA - Brasilândia" lê "brasilandia"; "Ultra-Fit" lê "fit"."""
    assert pa.e_ultra("ULTRA ACADEMIA - Brasilândia") is True
    assert pa.e_ultra("ULTRA - Brasilândia") is True
    assert pa.e_ultra("Ultra-Fit") is False


def test_a_ultra_reconhecida_sai_da_concorrencia_e_acha_o_proprio_plano() -> None:
    """O dano de não reconhecer é duplo, e este teste cobre os dois de uma vez.

    Risco medido antes de alargar a régua: a marca alheia com "ultra" mais PRÓXIMA de uma
    Ultra Academia está a 5.996 m no WellHub e a 7.153 m no TotalPass — nenhuma entra nos
    120 m do casamento da própria, e nenhuma entra nem nos 2.000 m do raio de concorrência.
    """
    planos = pa.normalizar(
        _bruto(
            [
                {"slug": "p", "nome": "Ultra Sagrada Família", "latitude": "-23.00001",
                 "plano_totalpass": "TP 2", "preco_plano_totalpass": "199.90"},
                {"slug": "v", "nome": "ULTRA TAGUATINGA SUL", "latitude": "-23.010",
                 "plano_totalpass": "TP 2", "preco_plano_totalpass": "199.90"},
                {"slug": "x", "nome": "Ultra Fitness", "latitude": "-23.004",
                 "plano_totalpass": "TP 1", "preco_plano_totalpass": "109.90"},
            ]
        )
    )
    r = pa.planos_no_entorno(-23.0, -46.0, planos)
    assert r["ultra"] is not None and r["ultra"]["nome"] == "Ultra Sagrada Família"
    # a Ultra vizinha sai da concorrência; a marca alheia com "ultra" no nome FICA
    assert [a["nome"] for a in r["academias"]] == ["Ultra Fitness"]
