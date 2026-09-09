"""Bloco C+ — o aviso da viabilidade argentina EXISTE no perfil e viaja nos artefatos.

Este arquivo e o "teste que tem de FALHAR se o aviso sumir" que o proprio
`data/perfis/AR/perfil.json` exige no campo `_remover_quando` do bloco
`avisos.viabilidade_tributo_provisorio`: enquanto o pacote de premissas financeiras
argentino (BLK-INTL-11) nao for aprovado, a viabilidade da AR sai em reais com tributo
BRASILEIRO (decisao 0.6), e a UNICA coisa que separa isso do defeito R2 e o aviso
carimbado no PDF e no XLSX (decisao 0.7). Se alguem apagar ou desligar o aviso sem
fechar o BLK-INTL-11, este arquivo acusa com nome e sobrenome.

Tambem trava aqui o outro campo do mesmo bloco C+, pelo mesmo motivo de "o perfil
declara e o codigo obedece": `operacao.pdf_concorrencia_max` (decisao 0.5) — BR=3 (o
literal historico de `web/server/app.py`), AR=1 (duas instancias numa VPS de 4 vCPU).

Medido contra os DOIS perfis reais versionados, nunca contra um perfil sintetico.
"""

from __future__ import annotations

import pytest

from motor_expansao.perfil import PERFIL_BR_EMBARCADO, Perfil, carregar_perfil

_PERFIL_AR_JSON = PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json"


@pytest.fixture(scope="module")
def br() -> Perfil:
    return carregar_perfil(PERFIL_BR_EMBARCADO)


@pytest.fixture(scope="module")
def ar() -> Perfil:
    return carregar_perfil(_PERFIL_AR_JSON)


# --------------------------------------------------------------------------------
# O aviso da viabilidade argentina — obrigatorio ate o BLK-INTL-11 fechar
# --------------------------------------------------------------------------------


def test_ar_carrega_o_aviso_de_tributo_provisorio(ar: Perfil) -> None:
    """Se este teste falhar porque o aviso SUMIU do perfil, leia o `_remover_quando`
    do JSON antes de "consertar" o teste: o aviso so pode sair quando o pacote de
    premissas argentino for aprovado e passar no gate local."""
    assert "viabilidade_tributo_provisorio" in ar.avisos
    aviso = ar.avisos["viabilidade_tributo_provisorio"]
    assert aviso.codigo == "AR-VIAB-TRIB-PROVISORIO"
    assert aviso.ativo, "aviso desligado = viabilidade AR sem provisoriedade declarada"
    assert aviso.obrigatorio
    assert aviso.alerta, "sem `alerta` o carimbo do XLSX sairia sem o fundo de destaque"


def test_aviso_da_ar_tem_os_tres_textos_escritos(ar: Perfil) -> None:
    """Os tres textos JA ESTAO redigidos no perfil (o trabalho do C+ e fazer o carimbo
    viajar, nao redigi-lo): curto para a linha de nota do XLSX, rodape para as paginas
    financeiras do PDF, longo para a caixa do PDF e a tela."""
    aviso = ar.avisos["viabilidade_tributo_provisorio"]
    assert aviso.texto_curto.strip()
    assert aviso.texto_longo.strip()
    assert aviso.texto_rodape.strip()


def test_aviso_da_ar_viaja_no_pdf_e_no_xlsx(ar: Perfil) -> None:
    """A condicao de aceite inegociavel da 0.7: o PDF e o XLSX vao ao locador e ao
    comite; a tela fica no escritorio. `onde` tem de cobrir os dois artefatos."""
    aviso = ar.avisos["viabilidade_tributo_provisorio"]
    assert {"pdf", "xlsx"} <= aviso.onde


# --------------------------------------------------------------------------------
# Brasil: declarar o pais nao muda o comportamento brasileiro
# --------------------------------------------------------------------------------


def test_brasil_nao_carrega_aviso_nenhum(br: Perfil) -> None:
    """`avisos` = `{}` no BR e deliberado (modelo CALIBRADO): e o que garante que o
    caller do piloto passa `None` aos geradores e o par de artefatos brasileiro nao
    muda um byte."""
    assert dict(br.avisos) == {}


def test_teto_de_pdf_por_instancia_br_3_ar_1(br: Perfil, ar: Perfil) -> None:
    """Decisao 0.5: o semaforo e por PROCESSO e cada instancia roda UM worker uvicorn;
    duas instancias com viabilidade ligada numa VPS de 4 vCPU somam os tetos. O BR
    mantem o literal historico (3); a AR sobe com 1."""
    assert br.operacao.pdf_concorrencia_max == 3
    assert ar.operacao.pdf_concorrencia_max == 1
