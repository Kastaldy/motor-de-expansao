"""Trava o contrato do sync do diretorio de concorrentes que o dashboard/PDFs leem.

O bug que originou o script (medido em producao em 2026-07-29): o ciclo semanal
alimentava `concorrentes_mapeados.parquet` mas nunca o diretorio
`/opt/motor-expansao/concorrentes`, que os servicos montam em `/app/concorrentes`.
As 68 redes novas sumiam do mapa do Streamlit e os pins do piloto web/PDFs caiam no
fallback de sigla por falta de `logo_<slug>.png`.

Dois comportamentos precisam ficar travados:
  1. a NORMALIZACAO do nome das logos (o coletor guarda `AD3_logo.png`,
     `Malibu_logo.png`, `companhiafit_logo.png`; o canonico e `logo_<slug>.png`);
  2. a regra de nunca REDUZIR unidades — uma coleta parcial nao pode apagar o que ja
     estava visivel em producao.

Sem PII: so nomes de REDE/unidade, nunca de pessoa.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from motor_expansao.dashboard.competitors import COMPETITOR_LOGO_FILES

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sync_concorrentes_dashboard.py"


def _carregar_modulo():
    spec = importlib.util.spec_from_file_location("sync_concorrentes_dashboard", _SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


sync = _carregar_modulo()

def _png(cor: tuple[int, int, int] = (200, 30, 40)) -> bytes:
    """PNG 4x4 valido — o sync so copia bytes, mas um PNG real evita falso positivo."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), cor).save(buffer, format="PNG")
    return buffer.getvalue()


PNG_MINIMO = _png()

CSV_HEADER = "nome_unidade;latitude;longitude;data_coleta\n"


def _csv(n: int) -> str:
    linhas = [CSV_HEADER]
    for i in range(n):
        linhas.append(f"Unidade {i};-23.5{i:03d};-46.6{i:03d};2026-07-26\n")
    return "".join(linhas)


@pytest.fixture()
def arvore(tmp_path: Path) -> tuple[Path, Path]:
    gym = tmp_path / "gymscraping"
    (gym / "Logos").mkdir(parents=True)
    (gym / "Unidades").mkdir(parents=True)
    destino = tmp_path / "concorrentes"
    destino.mkdir()
    return gym, destino


# ── normalizacao de nome de logo ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("arquivo_origem", "slug"),
    [
        ("AD3_logo.png", "ad3"),
        ("Acuas_fitness_logo.png", "acuas_fitness"),
        ("BG_fitness_logo.png", "bg_fitness"),
        ("Mansao_maromba_logo.png", "mansao_maromba"),
        ("YMCA_logo.png", "ymca"),
        ("companhiafit_logo.png", "companhia_fit"),
        ("marrafit_logo.png", "marra_fit"),
        ("matchfit_logo.png", "match_fit"),
        ("moinhosfit_logo.png", "moinhos_fitness"),
        ("Malibu_logo.png", "malibu_fitness"),
        ("logo_smart_fit.png", "smart_fit"),
    ],
)
def test_resolve_nome_fora_do_padrao(arvore, arquivo_origem: str, slug: str) -> None:
    gym, _ = arvore
    (gym / "Logos" / arquivo_origem).write_bytes(PNG_MINIMO)
    indice = sync.indexar_logos(gym / "Logos")
    assert sync.resolver_logo(slug, indice) == arquivo_origem


def test_logo_copiada_com_nome_canonico(arvore) -> None:
    gym, destino = arvore
    (gym / "Logos" / "AD3_logo.png").write_bytes(PNG_MINIMO)
    (gym / "Unidades" / "unidades_ad3.csv").write_text(_csv(3), encoding="utf-8")

    assert sync.sincronizar(gym, destino, aplicar=True) == 0

    assert (destino / COMPETITOR_LOGO_FILES["ad3"]).is_file()
    assert (destino / "logo_ad3.png").read_bytes() == PNG_MINIMO
    # o nome de origem NAO pode vazar para o destino
    assert not (destino / "AD3_logo.png").exists()


def test_rede_sem_arte_fica_sem_logo(arvore) -> None:
    """Fallback de sigla e o comportamento projetado — nao inventar arquivo."""
    gym, destino = arvore
    (gym / "Unidades" / "unidades_ad3.csv").write_text(_csv(2), encoding="utf-8")

    sync.sincronizar(gym, destino, aplicar=True)

    assert not (destino / "logo_ad3.png").exists()


def test_logo_do_destino_preservada_quando_coletor_nao_tem(arvore) -> None:
    """`biohit` e `evolve` so existem no destino; o sync nao pode apaga-las."""
    gym, destino = arvore
    (destino / COMPETITOR_LOGO_FILES["biohit"]).write_bytes(PNG_MINIMO)

    sync.sincronizar(gym, destino, aplicar=True)

    assert (destino / COMPETITOR_LOGO_FILES["biohit"]).read_bytes() == PNG_MINIMO


# ── regra de nao regredir contagem ────────────────────────────────────────────


def test_csv_maior_substitui_o_menor(arvore) -> None:
    gym, destino = arvore
    (destino / "unidades_ad3.csv").write_text(_csv(2), encoding="utf-8")
    (gym / "Unidades" / "unidades_ad3.csv").write_text(_csv(9), encoding="utf-8")

    sync.sincronizar(gym, destino, aplicar=True)

    assert (destino / "unidades_ad3.csv").read_text(encoding="utf-8").count("Unidade ") == 9


def test_coleta_parcial_nao_reduz_o_que_ja_estava_visivel(arvore) -> None:
    """O coletor ja falhou em 45/106 redes num domingo — CSV truncado nao apaga prod."""
    gym, destino = arvore
    (destino / "unidades_ad3.csv").write_text(_csv(40), encoding="utf-8")
    (gym / "Unidades" / "unidades_ad3.csv").write_text(_csv(3), encoding="utf-8")

    sync.sincronizar(gym, destino, aplicar=True)

    assert (destino / "unidades_ad3.csv").read_text(encoding="utf-8").count("Unidade ") == 40


def test_dry_run_nao_escreve(arvore) -> None:
    gym, destino = arvore
    (gym / "Logos" / "AD3_logo.png").write_bytes(PNG_MINIMO)
    (gym / "Unidades" / "unidades_ad3.csv").write_text(_csv(5), encoding="utf-8")

    sync.sincronizar(gym, destino, aplicar=False)

    assert list(destino.iterdir()) == []


def test_rede_nova_entra_no_destino(arvore) -> None:
    gym, destino = arvore
    (gym / "Unidades" / "unidades_ymca.csv").write_text(_csv(18), encoding="utf-8")
    (gym / "Logos" / "YMCA_logo.png").write_bytes(PNG_MINIMO)

    sync.sincronizar(gym, destino, aplicar=True)

    assert (destino / "unidades_ymca.csv").is_file()
    assert (destino / "logo_ymca.png").is_file()


def test_destino_inexistente_e_criado(tmp_path: Path) -> None:
    gym = tmp_path / "gym"
    (gym / "Unidades").mkdir(parents=True)
    (gym / "Unidades" / "unidades_ad3.csv").write_text(_csv(1), encoding="utf-8")
    destino = tmp_path / "nao_existe" / "concorrentes"

    assert sync.sincronizar(gym, destino, aplicar=True) == 0
    assert (destino / "unidades_ad3.csv").is_file()


def test_origem_sem_unidades_falha(tmp_path: Path) -> None:
    gym = tmp_path / "gym"
    gym.mkdir()
    assert sync.sincronizar(gym, tmp_path / "destino", aplicar=True) == 1


def test_empate_de_contagem_com_conteudo_novo_propaga(arvore) -> None:
    """Coleta que so corrige coordenada nao muda o total — e mesmo assim precisa entrar."""
    gym, destino = arvore
    (destino / "unidades_ad3.csv").write_text(
        CSV_HEADER + "Unidade 0;-23.500;-46.600;2026-06-01\n", encoding="utf-8"
    )
    corrigido = CSV_HEADER + "Unidade 0;-23.511;-46.611;2026-07-26\n"
    (gym / "Unidades" / "unidades_ad3.csv").write_text(corrigido, encoding="utf-8")

    sync.sincronizar(gym, destino, aplicar=True)

    assert (destino / "unidades_ad3.csv").read_text(encoding="utf-8") == corrigido


def test_sync_e_idempotente(arvore) -> None:
    """Rodar duas vezes seguidas nao pode mudar nenhum arquivo."""
    gym, destino = arvore
    (gym / "Logos" / "AD3_logo.png").write_bytes(PNG_MINIMO)
    (gym / "Unidades" / "unidades_ad3.csv").write_text(_csv(4), encoding="utf-8")

    sync.sincronizar(gym, destino, aplicar=True)
    antes = {p.name: p.read_bytes() for p in sorted(destino.iterdir())}
    sync.sincronizar(gym, destino, aplicar=True)
    depois = {p.name: p.read_bytes() for p in sorted(destino.iterdir())}

    assert antes == depois


def test_uma_logo_nao_e_reaproveitada_por_duas_redes(arvore) -> None:
    """Guarda contra casamento por prefixo largo demais (ex.: `pro3` puxar `profit`)."""
    gym, _ = arvore
    (gym / "Logos" / "logo_profit.png").write_bytes(PNG_MINIMO)
    indice = sync.indexar_logos(gym / "Logos")

    assert sync.resolver_logo("profit", indice) == "logo_profit.png"
    assert sync.resolver_logo("pro3", indice) is None
