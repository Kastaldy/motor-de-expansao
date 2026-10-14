"""A faixa que a TELA barra tem de ser a mesma que o MOTOR aceita.

`web/src/lib/viabilidade-limites.ts` e' a SEGUNDA redacao de uma regra que ja' existe em
`ViabilidadeInputs` (`src/motor_expansao/dimensionamento/payload_viabilidade.py`). Duas
redacoes da mesma regra nao dao erro: desencontram em SILENCIO, e cada lado passa a
proteger contra outra coisa.

As duas direcoes do desencontro machucam, e de jeitos diferentes:

- TELA MAIS FROUXA que o motor -> o valor atravessa, o motor devolve 422 e o operador
  ve um erro que a tela podia ter explicado. E' exatamente o que aconteceu em
  2026-10-13: digitar `0` em "Parcelas franquia" (o `min={1}` do `CampoNumero` nunca
  impediu digitacao) devolveu um 422 que chegava a tela como "[object Object]".
- TELA MAIS SEVERA que o motor -> a tela REPROVA valor que o motor aceita, e isso e'
  pior: vira regra de negocio nova, inventada por um conserto, que ninguem decidiu.

Este teste le o arquivo da tela e compara campo a campo. Mexer no limite de um lado so'
deixa o CI vermelho.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from motor_expansao.dimensionamento.payload_viabilidade import ViabilidadeInputs

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO_DA_TELA = RAIZ / "web" / "src" / "lib" / "viabilidade-limites.ts"

# Os nomes sao os do pydantic de proposito: a comparacao e' direta, sem traducao no meio
# (uma traducao e' mais um lugar onde as duas redacoes podem desencontrar).
CHAVES = ("gt", "ge", "lt", "le")


def _limites_da_tela() -> dict[str, dict[str, float]]:
    """Le a tabela `LIMITES_DO_MOTOR` do TypeScript, sem executar JS."""
    texto = ARQUIVO_DA_TELA.read_text(encoding="utf-8")
    corpo = re.search(
        r"export const LIMITES_DO_MOTOR = \{(.*?)\n\} as const", texto, re.S
    )
    assert corpo, f"nao achei `LIMITES_DO_MOTOR` em {ARQUIVO_DA_TELA}"
    achados: dict[str, dict[str, float]] = {}
    for linha in corpo.group(1).splitlines():
        m = re.match(r"\s*(\w+):\s*\{(.+)\},\s*$", linha)
        if not m:
            continue
        campo, dentro = m.group(1), m.group(2)
        achados[campo] = {
            chave: json.loads(valor)
            for chave in CHAVES
            if (valor := (lambda x: x.group(1) if x else None)(
                re.search(rf"\b{chave}:\s*(-?[\d.]+)", dentro)
            ))
            is not None
        }
    assert achados, "a tabela da tela foi lida vazia — o formato do arquivo mudou"
    return achados


def _limites_do_motor(campo: str) -> dict[str, float]:
    """As restricoes declaradas no `Field(...)` daquele campo do modelo."""
    info = ViabilidadeInputs.model_fields[campo]
    achados: dict[str, float] = {}
    for meta in info.metadata:
        for chave in CHAVES:
            # annotated_types usa `Gt`, `Ge`, `Lt`, `Le`, cada um com o atributo homonimo.
            valor: Any = getattr(meta, chave, None)
            if valor is not None:
                achados[chave] = float(valor)
    return achados


def test_a_tabela_da_tela_foi_lida():
    """Se o parser quebrar, os testes abaixo passariam VAZIOS — guarda anti-vacuo."""
    tabela = _limites_da_tela()
    assert len(tabela) >= 4, f"li so' {len(tabela)} campo(s): {sorted(tabela)}"
    assert "parcelas_franquia" in tabela, "o campo do incidente de 2026-10-13 sumiu"


@pytest.mark.parametrize("campo", sorted(_limites_da_tela()))
def test_cada_campo_da_tela_existe_no_motor(campo: str):
    assert campo in ViabilidadeInputs.model_fields, (
        f"a tela barra `{campo}`, que nao e' campo do motor — guarda sobre fantasma"
    )


@pytest.mark.parametrize("campo", sorted(_limites_da_tela()))
def test_a_faixa_da_tela_e_a_mesma_do_motor(campo: str):
    da_tela = _limites_da_tela()[campo]
    do_motor = _limites_do_motor(campo)
    assert da_tela == do_motor, (
        f"`{campo}`: a tela diz {da_tela} e o motor diz {do_motor}.\n"
        f"Mais FROUXA que o motor deixa o 422 chegar ao operador; mais SEVERA reprova "
        f"valor que o motor aceita (regra nova sem decisao). Acerte os dois: "
        f"{ARQUIVO_DA_TELA.relative_to(RAIZ)} e payload_viabilidade.py."
    )


def test_o_motor_nao_ganhou_faixa_que_a_tela_ignora():
    """Campo de INTEIRO com faixa e sem guarda na tela = o proximo incidente.

    Nao exige cobertura total (o resto cai na rede geral do `mensagemDoDetalhe`): exige
    que um campo NOVO com faixa seja uma DECISAO, declarada aqui.
    """
    # Cada dispensa tem a razao MEDIDA, nao presumida: ou a tela nunca manda o campo
    # (contado no fonte), ou o valor ja' nasce travado antes de virar payload.
    fora_de_proposito = {
        # --- a tela NUNCA manda (zero ocorrencia em ViabilityScreen.tsx) -------------
        "deducoes_pct",
        "reajuste_ticket_aa",
        "reajuste_aluguel_aa",
        "reajuste_custos_aa",
        "juros_financiamento_am",  # LEGADO (caminho do capex unico)
        "capex_financiado_pct",  # LEGADO
        "capex_parcelas_meses",  # LEGADO
        "margem_alvo",  # LEGADO
        # `taxa_desconto_aa` aparece 1x, e e' LEITURA (`premissas.taxa_desconto_aa`,
        # para exibir "a.a." no rodape) — nao ha campo que a envie.
        "taxa_desconto_aa",
        # --- o valor ja' nasce dentro da faixa ---------------------------------------
        "n_studios",  # `clampNStudios` trava 0..3 no proprio onChange
        "rampa_meses",  # so' botoes +/-, com Math.max(1) e Math.min(36)
        "share_balcao",  # `fracaoDoPercentual` devolve undefined fora de 0..100
        "taxa_minima_negocio_aa",  # idem, percentual convertido
        "juros_equipamentos_am",  # idem
        # --- 0 e' valor LEGITIMO; so' o teto seria violavel, e cai na rede geral ------
        "carencia_aluguel_meses",
        # --- a coordenada nao e' digitada: vem do ponto escolhido no mapa ------------
        "lat",
        "lng",
    }
    da_tela = set(_limites_da_tela())
    com_faixa = {
        campo
        for campo in ViabilidadeInputs.model_fields
        if any(k in _limites_do_motor(campo) for k in ("gt", "ge", "lt", "le"))
        # `ge=0` sozinho nunca e' violavel: o `CampoNumero` nao digita negativo.
        and _limites_do_motor(campo) != {"ge": 0.0}
    }
    descobertos = com_faixa - da_tela - fora_de_proposito
    assert not descobertos, (
        f"campo(s) com faixa no motor e sem guarda nem dispensa na tela: "
        f"{sorted(descobertos)}. Entre na tabela de {ARQUIVO_DA_TELA.name} ou declare "
        f"aqui por que nao precisa."
    )
