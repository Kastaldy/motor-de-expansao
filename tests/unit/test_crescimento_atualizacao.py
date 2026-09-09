"""Atualizacao trimestral da camada de crescimento (DEC-052).

O que se trava aqui, na ordem do risco:

1. o VALIDADOR reprova a assinatura da execucao parcial (15 de 33 colunas) e o
   dominio fechado quebrado — os dois modos "plausivel e errado, HTTP 200";
2. a agregacao do CAGED reproduz a conta do consolidado real e a atualizacao e'
   por SUBSTITUICAO de competencia (re-rodada nao duplica linha);
3. o AVISO diz o que mudou nos dois desfechos e nunca carrega token;
4. as PARIDADES entre Python e shell (limiar do monitor, nomes de modulo no
   wrapper, nome do consolidado em `_raizes.py`) — a mesma grandeza em dois
   arquivos so' e' segura com um teste comparando os dois lados.

Sem FTP, sem py7zr e sem rodar a cadeia: CI nao tem os insumos (o README dos
geradores explica por que nao pode ter).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.crescimento import aviso, caged, constantes, validar
from motor_expansao.crescimento.atualizar import ORDEM_SCRIPTS

RAIZ_REPO = Path(__file__).resolve().parents[2]
DIR_CADEIA = RAIZ_REPO / "data" / "reports" / "crescimento"


# ---------------------------------------------------------------- validador --
def _municipal_integro(n_extras: int = 19) -> pd.DataFrame:
    base = {c: ["x"] * 6000 for c in validar.COLUNAS_CONSUMIDAS_MUNICIPAL}
    base["cres_tendencia"] = ["Em alta", "Em queda", "Estavel", None, "Estavel", "Em alta"] * 1000
    base["cres_confiab"] = ["alta", "media", "baixa", "muito_baixa", "alta", "media"] * 1000
    base["cres_dims"] = ["Renda:25.8:%:25:2020->2024;Emprego:8.8:%:59:2022->jun/2026"] * 6000
    for i in range(n_extras):
        base[f"extra_{i}"] = [0] * 6000
    return pd.DataFrame(base)


def test_municipal_integro_passa():
    assert validar.validar_municipal(_municipal_integro()) == []


def test_municipal_mutilado_reprova():
    """A assinatura do `03` rodado sozinho: poucas colunas, sem veredito/dims."""
    df = _municipal_integro().drop(
        columns=["v_frase", "v_classe", "cres_dims", "cres_series"]
        + [f"extra_{i}" for i in range(19)]
    )
    erros = validar.validar_municipal(df)
    assert any("execucao parcial" in e for e in erros)
    assert any("colunas" in e for e in erros)


def test_municipal_dominio_quebrado_reprova():
    df = _municipal_integro()
    df.loc[0, "cres_tendencia"] = "Estável"  # acentuar identificador quebra o SPA
    assert any("cres_tendencia" in e for e in validar.validar_municipal(df))


def test_municipal_dims_sem_periodo_reprova():
    """`10_periodo.py` pulado: bloco de dims com 4 campos em vez de 5."""
    df = _municipal_integro()
    df["cres_dims"] = ["Renda:25.8:%:25"] * len(df)
    assert any("periodo" in e for e in validar.validar_municipal(df))


def test_hex_integro_e_dominio():
    ok = pd.DataFrame(
        {
            "hex_id": [f"h{i}" for i in range(31000)],
            "cres_hex_classe": ["Em alta", "Estavel", "Sem obra nova", None] * 7750,
            "cres_hex_taxa": [0.1] * 31000,
        }
    )
    assert validar.validar_hex(ok) == []
    ruim = ok.copy()
    ruim.loc[0, "cres_hex_classe"] = "Estável"
    assert any("cres_hex_classe" in e for e in validar.validar_hex(ruim))
    assert any("hexes" in e for e in validar.validar_hex(ok.head(100)))
    # a taxa e' consumida pelo payload do mapa: hex de 2 colunas nao passa
    sem_taxa = ok.drop(columns=["cres_hex_taxa"])
    assert any("cres_hex_taxa" in e for e in validar.validar_hex(sem_taxa))


# ------------------------------------------------------------------- CAGED --
def _microdado(comp: str) -> pd.DataFrame:
    # 2 municipios; salario com virgula decimal como no txt do PDET
    return pd.DataFrame(
        {
            "competencia": [comp] * 5,
            "uf": ["35"] * 3 + ["41"] * 2,
            "cod_municipio": ["355030", "355030", "355030", "410690", "410690"],
            "saldo": [1, 1, -1, 1, -1],
            "salario": ["1500,50", "2500,50", "999", "1800", "888"],
        }
    )


def test_agregar_microdado_reproduz_contrato():
    g = caged.agregar_microdado(_microdado("202607"), "202607")
    assert list(g.columns) == caged.COLUNAS_CONSOLIDADO
    sp = g.set_index("cod_municipio").loc["355030"]
    assert sp["saldo"] == 1 and sp["admissoes"] == 2 and sp["desligamentos"] == 1
    assert sp["salario_medio_adm"] == pytest.approx(2000.50)  # media das ADMISSOES


def test_meses_candidatos_para_no_mes_corrente():
    from datetime import date

    meses = caged.meses_candidatos("202603", hoje=date(2026, 9, 8))
    assert meses == ["202604", "202605", "202606", "202607", "202608"]
    assert caged.meses_candidatos("202608", hoje=date(2026, 9, 8)) == []


def test_atualizar_consolidado_substitui_competencia(tmp_path):
    csv = tmp_path / caged.NOME_CONSOLIDADO
    antigo = pd.DataFrame(
        {
            "competencia": ["202605", "202606"],
            "cod_municipio": ["355030", "355030"],
            "uf": ["35", "35"],
            "saldo": [10, 99],  # o 99 de 202606 sera' SUBSTITUIDO
            "admissoes": [20, 100],
            "desligamentos": [10, 1],
            "salario_medio_adm": [1500.0, 1500.0],
        }
    )
    antigo.to_csv(csv, index=False, encoding="utf-8")
    novos = caged.agregar_microdado(_microdado("202606"), "202606")
    caged.atualizar_consolidado(csv, novos)
    depois = pd.read_csv(csv, dtype={"competencia": str, "cod_municipio": str})
    assert list(depois.columns) == caged.COLUNAS_CONSOLIDADO
    m606 = depois[depois["competencia"] == "202606"]
    assert len(m606) == 2  # os 2 municipios do novo; a linha antiga de 202606 caiu
    assert int(m606[m606["cod_municipio"] == "355030"]["saldo"].iloc[0]) == 1
    assert len(depois[depois["competencia"] == "202605"]) == 1  # intacta
    assert not list(tmp_path.glob("*.tmp-*"))  # escrita atomica nao deixa resto


def test_resolver_consolidado_prefere_canonico(tmp_path):
    legado = tmp_path / caged.NOME_CONSOLIDADO_LEGADO
    legado.write_text("competencia\n", encoding="utf-8")
    assert caged.resolver_consolidado(tmp_path) == legado
    novo = tmp_path / caged.NOME_CONSOLIDADO
    novo.write_text("competencia\n", encoding="utf-8")
    assert caged.resolver_consolidado(tmp_path) == novo


def test_atualizar_exige_consolidado_existente(tmp_path):
    with pytest.raises(SystemExit, match="consolidado ausente"):
        caged.atualizar(tmp_path / caged.NOME_CONSOLIDADO)


def test_guarda_de_absurdo_por_meses_demais(tmp_path):
    csv = tmp_path / caged.NOME_CONSOLIDADO
    pd.DataFrame(
        {c: ["202301"] if c == "competencia" else ["x"] for c in caged.COLUNAS_CONSOLIDADO}
    ).to_csv(csv, index=False)
    with pytest.raises(SystemExit, match="acima da guarda"):
        caged.atualizar(csv)


# ------------------------------------------------------------------- aviso --
def test_aviso_sucesso_diz_o_que_mudou():
    texto = aviso.montar_sucesso(
        {
            "meses_caged_novos": ["202605", "202606"],
            "emprego_ate": "jun/2026",
            "municipios": 5571,
            "hexes": 41135,
            "colunas_municipal": 33,
            "vereditos_antes": {"acima": 100},
            "vereditos_depois": {"acima": 120},
            "publicado": True,
        }
    )
    assert "202605, 202606" in texto
    assert "jun/2026" in texto
    assert "5571" in texto and "41135" in texto
    # honestidade da idade por dimensao: o trimestre atualiza o EMPREGO
    assert "safras anuais" in texto


def test_aviso_falha_carrega_a_etapa_e_o_log():
    """O estado do staging vem NA DESCRICAO da etapa (que o wrapper escolhe por exit
    code) — uma linha fixa "staging intacto" seria falsa nas falhas pos-publicacao."""
    texto = aviso.montar_falha("cadeia 01..10 falhou (rc=3) — nada publicado, staging intacto")
    assert "FALHOU" in texto and "rc=3" in texto and "staging intacto" in texto
    assert "atualizacao_crescimento_latest.log" in texto
    assert "O staging seguiu" not in texto  # a linha fixa contraditoria morreu


def test_aviso_sem_credencial_falha_com_mensagem(monkeypatch):
    monkeypatch.delenv("API_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("MONITOR_TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(SystemExit, match="API_TELEGRAM_TOKEN"):
        aviso.enviar("oi")


# -------------------------------------------------------------- orquestrador --
def test_preparar_trabalho_exige_eixo(tmp_path):
    """Sem o `_eixo_trajetoria.parquet` (projeto irmao) a rodada aborta ANTES da
    cadeia, com mensagem que diz de onde o insumo vem."""
    from motor_expansao.crescimento import atualizar as at

    scripts = tmp_path / "cadeia"
    scripts.mkdir()
    for n in [*at.ORDEM_SCRIPTS, "_raizes.py"]:
        (scripts / n).write_text("# stub", encoding="utf-8")
    with pytest.raises(SystemExit, match="poc_satelite"):
        at.preparar_trabalho(scripts, scripts / "_eixo_trajetoria.parquet", tmp_path / "wk")


def test_publicar_por_rename_atomico(tmp_path):
    """Os dois parquets atravessam por `.tmp` + replace; nada de `.tmp` sobra e o
    conteudo anterior e' substituido inteiro."""
    from motor_expansao.crescimento import atualizar as at

    rascunho = tmp_path / "rascunho"
    real = tmp_path / "staging"
    rascunho.mkdir()
    real.mkdir()
    for nome in (at.ARTEFATO_MUNICIPAL, at.ARTEFATO_HEX):
        (rascunho / nome).write_bytes(b"novo")
        (real / nome).write_bytes(b"velho-e-maior-que-o-novo")
    at.publicar(rascunho, real)
    for nome in (at.ARTEFATO_MUNICIPAL, at.ARTEFATO_HEX):
        assert (real / nome).read_bytes() == b"novo"
    assert not list(real.glob("*.tmp-*"))


# --------------------------------------------------------------- paridades --
def test_ordem_da_cadeia_existe_no_repo():
    """Renomear um script da cadeia sem atualizar o orquestrador = rodada quebrada."""
    faltam = [n for n in ORDEM_SCRIPTS if not (DIR_CADEIA / n).exists()]
    assert faltam == []
    assert ORDEM_SCRIPTS == sorted(ORDEM_SCRIPTS)  # prefixo numerico = ordem canonica
    assert (DIR_CADEIA / "_raizes.py").exists()


def test_paridade_limiar_monitor_shell_python():
    """MONITOR_CRESCIMENTO_MAX_DIAS (shell) == LIMIAR_IDADE_DIAS (Python)."""
    sh = (RAIZ_REPO / "scripts" / "healthcheck_vps.sh").read_text(encoding="utf-8")
    m = re.search(r"MONITOR_CRESCIMENTO_MAX_DIAS:-(\d+)", sh)
    assert m, "healthcheck_vps.sh perdeu o default de MONITOR_CRESCIMENTO_MAX_DIAS"
    assert int(m.group(1)) == constantes.LIMIAR_IDADE_DIAS


def test_paridade_crontab_com_constantes():
    """A linha de crontab documentada no wrapper usa os meses de `constantes.MESES_CRON`."""
    sh = (RAIZ_REPO / "scripts" / "cron" / "run_atualizacao_crescimento.sh").read_text(
        encoding="utf-8"
    )
    esperado = ",".join(str(m) for m in constantes.MESES_CRON)
    assert f"0 3 5 {esperado} *" in sh


def test_wrapper_chama_modulos_que_existem():
    """O wrapper invoca `python -m <modulo>`; modulo renomeado quebraria so' na VPS."""
    import importlib

    sh = (RAIZ_REPO / "scripts" / "cron" / "run_atualizacao_crescimento.sh").read_text(
        encoding="utf-8"
    )
    modulos = set(re.findall(r"python -m (motor_expansao\.[\w.]+)", sh))
    assert modulos == {
        "motor_expansao.crescimento.atualizar",
        "motor_expansao.crescimento.aviso",
    }
    for m in modulos:
        importlib.import_module(m)


def test_paridade_competencia_legivel_com_raizes():
    """O rotulo AAAAMM->"mes/ano" existe em `_raizes.py` (cadeia) e em
    `atualizar.py` (aviso) — dois arquivos que nao se importam; a paridade e' o
    que impede o tooltip e o bot de dizerem meses diferentes."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_raizes_teste", DIR_CADEIA / "_raizes.py")
    assert spec and spec.loader
    raizes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(raizes)
    from motor_expansao.crescimento.atualizar import _competencia_legivel

    for comp in ("202001", "202603", "202612", "203107"):
        assert raizes.competencia_legivel(comp) == _competencia_legivel(comp)


def test_paridade_nome_consolidado_com_raizes():
    """Os DOIS nomes do consolidado em `_raizes.py` == constantes de `caged.py`."""
    raizes = (DIR_CADEIA / "_raizes.py").read_text(encoding="utf-8")
    assert f'"{caged.NOME_CONSOLIDADO}"' in raizes
    assert f'"{caged.NOME_CONSOLIDADO_LEGADO}"' in raizes


def test_cadeia_sem_rotulo_de_periodo_congelado():
    """Nenhum script da cadeia pode ter "jun/2026" (ou outro fim de serie) LITERAL:
    o cron avanca o dado e o rotulo congelado viraria contradicao publicada — o fim
    da serie CAGED sai de `competencia_legivel(...)`, derivado do consolidado."""
    for nome in ORDEM_SCRIPTS:
        fonte = (DIR_CADEIA / nome).read_text(encoding="utf-8")
        assert "jun/2026" not in fonte, nome


def test_cadeia_sem_caminho_windows():
    """Nenhum script da cadeia pode voltar a ter `rf\"{X}\\...\"`: na VPS (Linux) a
    barra invertida nao e' separador e o insumo 'some' com FileNotFoundError."""
    for nome in ORDEM_SCRIPTS:
        assert 'rf"' not in (DIR_CADEIA / nome).read_text(encoding="utf-8"), nome


def test_extra_crescimento_declarado_no_pyproject():
    """O py7zr viaja no extra [crescimento] e o Dockerfile.api o instala."""
    py = (RAIZ_REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "crescimento = [" in py and "py7zr" in py
    docker = (RAIZ_REPO / "Dockerfile.api").read_text(encoding="utf-8")
    assert "crescimento" in docker
