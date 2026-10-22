"""Instancia SEM regua (AR): `/api/municipio`, `/api/uf` e `/api/metodologia` BYTE A BYTE.

A recomendacao unica (DEC-077) entra no piloto pela presenca do bloco `recomendacao` no
topo do payload, e so quando o pais da instancia tem regua (`carregar_regra(PERFIL.pais)`).
A Argentina nao tem diretorio de regua: ali o payload tem de sair EXATAMENTE como saia antes
da Fase 4 -- mesmas chaves, mesma ordem, mesmos textos, mesmos numeros. "Quase igual" e o
defeito mais barato de introduzir neste PR: um texto de leitura trocado para o Brasil que
vaza para a outra instancia, ou um passo 5 montado pelo caminho novo sem a regua.

## O golden

O "antes" foi gerado chamando o caminho LEGADO com o `app.py` intocado (antes de qualquer
edicao da Fase 4), sobre o cenario sintetico abaixo e com o perfil ARGENTINO carregado. Fica
guardado como impressao digital: o sha256 do JSON canonico INTEIRO (`"*"`, que trava bytes e
ordem de chaves) e um sha256 curto de cada secao (chave de topo; cada passo; cada camada da
metodologia), que diz ONDE a divergencia esta quando o teste fica vermelho.

O golden so muda por decisao explicita: regerar com `MOTOR_GERAR_GOLDEN_AR=<arquivo.json>`
(o teste grava as impressoes no arquivo e pula) e justificar no PR por que o payload da
instancia sem regua mudou.

Chama as funcoes de rota DIRETO (sem TestClient), como o resto da suite do piloto.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from motor_expansao.perfil import PERFIL_BR_EMBARCADO, carregar_perfil
from tests.unit.test_piloto_web_endpoints import _clear_caches, _point_app_at, pilot

ENV_GERAR = "MOTOR_GERAR_GOLDEN_AR"
_PERFIL_AR = PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json"


# ---------------------------------------------------------------------------
# Cenario -- AUTOCONTIDO de proposito: uma mudanca na fixture compartilhada do piloto
# nao pode mover o golden sem que ninguem perceba de onde veio a diferenca.
# ---------------------------------------------------------------------------


def _enriquecido() -> pd.DataFrame:
    """2 municipios em SP; acende os 5 passos (livre, adensar e saturado em cada um).

    `fonte_pop_hex_base` entra no arquivo, como no artefato real. O codigo legado nem a
    projetava; o novo projeta (insumo da recomendacao). O payload sem regua nao pode mudar
    por isso.
    """
    linhas: list[dict[str, object]] = []
    for mi, (nome, cod) in enumerate([("Sao Paulo", "3550308"), ("Campinas", "3509502")]):
        for h in range(4):
            linhas.append(
                {
                    "hex_id": f"87a{mi}{h}0000000ffff",
                    "lat": -23.55 + 0.01 * mi + 0.001 * h,
                    "lng": -46.63 + 0.01 * mi + 0.001 * h,
                    "nome_municipio": nome,
                    "cod_municipio": cod,
                    "score_priorizacao": 80.0 + h,
                    "score_setor_2022_calibrado": 75.0 + h,
                    "score_expansao_hibrido": 70.0 + h,
                    "score_oportunidade_residual": 5000.0 + 100 * h,
                    "oferta_efetiva_disponivel": 3000.0 + 500 * h,
                    "oferta_consumida_mercado_estimada": 2500.0 * h,
                    "sam_fitness_potencial": 4000.0 + h,
                    "populacao_corte_hex": 8000.0 + 100 * h,
                    "pop_total": 8000.0 + 100 * h,
                    "pop_total_setor_2022": 8000.0 + 100 * h,
                    "fonte_pop_hex_base": "censo_2022_setor",
                    "renda_per_capita": 2500.0 + 10 * h,
                    "renda_per_capita_setor_2022_calibrada": 2600.0 + 10 * h,
                    "faixa_oportunidade": "alta",
                    "n_unidades_ultra_performance_hex": h % 2,
                    "capacidade_default_concorrente_alunos": 2500.0,
                    "densidade_pop_setor_hab_km2": 5000.0,
                }
            )
    return pd.DataFrame(linhas)


def _crescimento_municipal() -> pd.DataFrame:
    """Com `v_frase` (o veredito que a tela BR deixa de ler) e Campinas sem tendencia."""
    return pd.DataFrame(
        [
            {
                "cod6": "355030",
                "cres_chave_nome": "SP|SAO PAULO",
                "cres_tendencia": "Estavel",
                "cres_emp_pct": 8.8,
                "cres_saldo_empresas": 61553.0,
                "cres_confiab": "alta",
                "cres_salario": 2501.0,
                "cres_salario_var": 3.7,
                "cres_setor": "Transporte e logística",
                "cres_uf_mediana": 9.0,
                "cres_dims": "Renda:25.8:%:25:2020→2024;Emprego:8.8:%:59:2022→jun/2026",
                "cres_series": "Renda|R$|2020|2024|3243,3500,3900,4200,4643",
                "v_frase": "São Paulo cresceu em empresas e emprego. É praça para entrar.",
            },
            {
                "cod6": "350950",
                "cres_chave_nome": "SP|CAMPINAS",
                "cres_tendencia": None,
                "cres_emp_pct": 4.2,
                "cres_saldo_empresas": 900.0,
                "cres_confiab": "muito_baixa",
                "cres_salario": 1900.0,
                "cres_salario_var": 1.1,
                "cres_setor": "Comércio",
                "cres_uf_mediana": 9.0,
                "cres_dims": "Renda:12.0:%:30:2020→2024",
                "cres_series": "Renda|R$|2020|2024|2000,2100,2200,2300,2400",
                "v_frase": "Campinas cresceu em renda.",
            },
        ]
    )


def _crescimento_hex(hex_ids: pd.Series) -> pd.DataFrame:
    n = len(hex_ids)
    return pd.DataFrame(
        {
            "hex_id": hex_ids.astype(str).tolist(),
            "cres_hex_taxa": ([12.0, 45.0, -3.0, 200.0] * n)[:n],
            "cres_hex_classe": (["Estavel", "Em alta", "Sem obra nova", "Em alta"] * n)[:n],
        }
    )


@pytest.fixture
def cenario_ar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Piloto apontado para o cenario sintetico, com o perfil ARGENTINO (sem regua)."""
    part = tmp_path / "outputs" / "hexagonos_dashboard_enriquecido" / "uf=SP"
    part.mkdir(parents=True)
    enriquecido = _enriquecido()
    enriquecido.to_parquet(part / "part-0.parquet")  # escrita do TESTE, nao do app
    staging = tmp_path / "staging"
    staging.mkdir()
    _crescimento_municipal().to_parquet(staging / "crescimento_municipal.parquet", index=False)
    _crescimento_hex(enriquecido["hex_id"]).to_parquet(
        staging / "crescimento_hex.parquet", index=False
    )
    _point_app_at(monkeypatch, tmp_path)
    # Calculados no import e fora do `_point_app_at`: sem isto o golden dependeria do disco
    # de quem roda (o parquet de mercado alimenta `n_unidades_ultra_2km`).
    monkeypatch.setattr(pilot, "CONCORRENTES_PATH", staging / "concorrentes_mapeados.parquet")
    monkeypatch.setattr(
        pilot,
        "DASHBOARD_NACIONAL_PATH",
        tmp_path / "outputs" / "hexagonos_brasil_dashboard.parquet",
    )
    monkeypatch.setattr(pilot, "MERCADO_PARQUET", staging / "hexagonos_mercado_mapeado.parquet")
    monkeypatch.setattr(pilot, "PERFIL", carregar_perfil(_PERFIL_AR))
    _clear_caches()
    yield tmp_path
    _clear_caches()


# ---------------------------------------------------------------------------
# Impressao digital do payload
# ---------------------------------------------------------------------------


def _canonico(obj: Any) -> str:
    """O JSON que se compara. `allow_nan=False`: NaN no payload ja e defeito por si."""
    return json.dumps(obj, ensure_ascii=False, indent=1, allow_nan=False)


def _sha(texto: str, n: int = 64) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:n]


def _impressao(payload: dict[str, Any]) -> dict[str, str]:
    """sha256 do payload INTEIRO (`"*"`) + um sha curto por secao, para localizar a diferenca."""
    saida = {"*": _sha(_canonico(payload))}
    for chave, valor in payload.items():
        if chave in ("passos", "camadas") and isinstance(valor, list):
            for item in valor:
                saida[f"{chave}[{item.get('n')}]"] = _sha(_canonico(item), 16)
        else:
            saida[chave] = _sha(_canonico(valor), 16)
    return saida


#: Gerado com o `app.py` de `32abc1f0` (antes da Fase 4), perfil AR, cenario acima; conferido
#: identico com dois `PYTHONHASHSEED` diferentes (nenhuma ordem de `set` vaza para o payload).
#: A renda do hexagono (`renda`/`renda_dom`) sai do pacote da renda com os fatores VERSIONADOS:
#: uma versao nova dos fatores tambem move estas impressoes -- e e caso legitimo de regerar.
GOLDEN: dict[str, dict[str, str]] = {
    "municipio_sao_paulo": {
        "*": "8581d21448caae1dd1e22ad78c705ffdce24e83629ff12797a76e738a8f2b67c",
        "centro": "53421058f6db8346",
        "cres_mun": "fea4aa14c6988639",
        "ctx_mun": "44136fa355b3678a",
        "hexes": "98628699ffcb3413",
        "independentes": "e738d2b823e8633d",
        "municipio": "60754d8071992edd",
        "n_hex_mapa": "4b227777d4dd1fc6",
        "n_hex_total": "4b227777d4dd1fc6",
        "nivel": "5d282a18868546c6",
        "passos[1]": "25f4747432aa7358",
        "passos[2]": "8d262f3d17b2f76a",
        "passos[3]": "5275a8cf6ac0e765",
        "passos[4]": "d4c34c165386e51d",
        "passos[5]": "6b47719857bc667d",
        "pins": "8319b972a2d41a3b",
        "resumo": "3f3d2c8e1d595a29",
        "uf": "a62498dcf95a6b05",
    },
    "municipio_campinas": {
        "*": "c0f8be107a4ede40749315ea5cf97554e9b0ce85757f2005bb5f8fc59ee5d95c",
        "centro": "be18b5e84c8923e1",
        "cres_mun": "a701fd60570196b2",
        "ctx_mun": "44136fa355b3678a",
        "hexes": "f31141ef04ee11da",
        "independentes": "e738d2b823e8633d",
        "municipio": "2a1a2a1e6d76bf79",
        "n_hex_mapa": "4b227777d4dd1fc6",
        "n_hex_total": "4b227777d4dd1fc6",
        "nivel": "5d282a18868546c6",
        "passos[1]": "0189bd1a09ef6e5c",
        "passos[2]": "efaa56a30b4ae7aa",
        "passos[3]": "0451c665d8c4e550",
        "passos[4]": "1f78c5f744bc9249",
        "passos[5]": "b30d85ec70d73de9",
        "pins": "8319b972a2d41a3b",
        "resumo": "3f3d2c8e1d595a29",
        "uf": "a62498dcf95a6b05",
    },
    "uf_sp": {
        "*": "7c181d44d71eaa76b538088f262b4de78c82dbbe330446877e18e7fcef6d2dc4",
        "centro": "6f1343d80f7a6fbd",
        "cres_mun": "dd8f93ea4a448833",
        "crescimento_estado": "df74406d745abae9",
        "ctx_mun": "44136fa355b3678a",
        "hexes": "a98b5713d273e7cd",
        "municipio": "74234e98afe7498f",
        "n_hex_mapa": "2c624232cdd22177",
        "n_hex_total": "2c624232cdd22177",
        "nivel": "99561add75cd0d01",
        "passos[1]": "640200ecaf297e90",
        "passos[2]": "c8327d55a97216aa",
        "passos[3]": "0f9eb2b3f3c8246d",
        "passos[4]": "30774aaf092dbfb8",
        "passos[5]": "d6135417ba3aa5f1",
        "pins": "761970da2c39b57e",
        "resumo": "5915c0e5374b6b72",
        "uf": "a62498dcf95a6b05",
    },
    "metodologia": {
        "*": "48906d459ad27acbe6a8da389f63d4d800d626b9cb8781f99c3d77e4b763c288",
        "camadas[1]": "989d03bbfd2219d8",
        "camadas[2]": "6f6d4544f8432859",
        "camadas[3]": "3b4783a10bcee93e",
        "camadas[4]": "b97b8937bf9cc66d",
        "camadas[5]": "d2c87b637caa3864",
        "fontes": "10269c20bcf24fe3",
        "intro": "476d56331aae6e27",
        "parametros": "9aee0f055dc3eb1d",
    },
}


def _conferir(nome: str, payload: dict[str, Any]) -> None:
    atual = _impressao(payload)
    destino = os.environ.get(ENV_GERAR)
    if destino:
        caminho = Path(destino)
        dados = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
        dados[nome] = atual
        caminho.write_text(json.dumps(dados, indent=1, sort_keys=True), encoding="utf-8")
        pytest.skip(f"golden de {nome} gravado em {caminho}")
    esperado = GOLDEN[nome]
    if atual == esperado:
        return
    divergentes = sorted(k for k in set(atual) | set(esperado) if atual.get(k) != esperado.get(k))
    raise AssertionError(
        f"{nome}: o payload SEM regua deixou de ser byte a byte o legado. Secoes que "
        f"divergem: {divergentes}. Se a mudanca for intencional, regere o golden "
        f"({ENV_GERAR}=<arquivo>) e justifique no PR."
    )


# ---------------------------------------------------------------------------
# Os testes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("municipio", "nome"),
    [("Sao Paulo", "municipio_sao_paulo"), ("Campinas", "municipio_campinas")],
)
def test_municipio_sem_regua_e_byte_a_byte_o_legado(
    cenario_ar: Path, municipio: str, nome: str
) -> None:
    _conferir(nome, pilot.municipio("SP", municipio))


def test_uf_sem_regua_e_byte_a_byte_o_legado(cenario_ar: Path) -> None:
    _conferir("uf_sp", pilot.uf_view("SP"))


def test_metodologia_sem_regua_e_byte_a_byte_a_de_hoje(cenario_ar: Path) -> None:
    _conferir("metodologia", pilot.metodologia())


def test_o_perfil_ar_nao_tem_regua(cenario_ar: Path) -> None:
    """A premissa do golden: com o perfil argentino a instancia NAO tem regua. Se a AR
    ganhar uma regua, o golden passa a comparar o payload novo com o legado e fica vermelho
    -- e e' o sinal certo: o payload argentino mudaria por decisao, nao por acidente."""
    assert pilot.PERFIL.pais == "AR"
    assert pilot._regra_recomendacao() is None


def test_sem_regua_o_modulo_nem_e_chamado(
    cenario_ar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem regua o modulo da recomendacao nao roda (custo zero) e a chave nao existe."""

    def proibido(*_a: object, **_k: object) -> None:  # pragma: no cover - so' se a guarda falhar
        raise AssertionError("a instancia sem regua chamou o modulo da recomendacao")

    monkeypatch.setattr(pilot, "montar_recomendacao", proibido)
    for payload in (
        pilot.municipio("SP", "Sao Paulo"),
        pilot.uf_view("SP"),
        pilot.hexagonos(),
        pilot.hexagonos(uf="SP"),
    ):
        assert "recomendacao" not in payload
    # `/api/hexagonos` sem regua e' o ranking legado (na AR a rota ja' e' 404 pelo gate de
    # superficie; aqui a funcao e' chamada direto).
    assert "itens" in pilot.hexagonos()
