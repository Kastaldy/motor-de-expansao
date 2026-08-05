"""Semeia `cadastro_unidades.json` a partir da aba DADOS da planilha do time de campo.

As dimensoes de negocio (consultor, master franquia, franqueado, cidade, departamento,
Gold, modalidades, tiers) NAO existem na API Growth -- vivem numa planilha mantida a mao.
Este script casa aquela planilha com a base Growth pela chave de unidade e escreve o
cadastro que a Visao Executiva le (e, a partir dali, edita pela propria tela).

Roda UMA vez por semeadura; depois disso a fonte de verdade e' o proprio JSON, que a tela
atualiza. Rodar de novo NAO sobrescreve o que foi editado na tela: campos ja preenchidos no
JSON vencem os da planilha, a menos que se passe `--forcar-planilha`.

Uso:
    python scripts/semear_cadastro_unidades.py \
        --planilha "ANALISE DIARIA DASHBOARD.xlsx" \
        --growth data/staging/growth_api_historico.parquet \
        --saida data/cadastro
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from motor_expansao.dashboard.rede_cadastro import (  # noqa: E402
    Cadastro,
    gravar_cadastro,
    ler_cadastro,
)
from motor_expansao.dashboard.rede_metricas import (  # noqa: E402
    carregar_base,
    catalogo_de,
    chave_unidade,
)

# A planilha prefixa a marca no nome ("ULT - AUGUSTA"); a base Growth nao.
_PREFIXO_MARCA = re.compile(r"^(?:ULT|ICON|ICN)\s*-\s*")

# Coluna da planilha -> campo do cadastro. Nomes de coluna conferidos em 2026-08-04.
_COLUNAS: dict[str, str] = {
    "COD UNIDADE": "cod_unidade",
    "CIDADE": "cidade",
    "DPTO": "dpto",
    "MASTER FRANQUIA": "master_franquia",
    "FRANQUEADO": "franqueado",
    "CONSULTOR FRANQUEADORA": "consultor",
    "CONSULTOR MASTER FRANQUEADO": "consultor_2",
    "GOLD": "gold",
    "LIFE TIME": "life_time",
    "LTV": "ltv",
    "WELLHUB": "wellhub",
    "TOTALPASS": "totalpass",
}
_MODALIDADES = ("PISCINA", "STUDIOS", "BIKE", "LUTAS", "PILATES")

# Duas unidades cuja grafia diverge entre a base Growth e a planilha, e que normalizacao
# nenhuma reconcilia. Cada uma foi conferida em 2026-08-04: o alvo existe na planilha,
# esta LIVRE (nenhuma outra unidade da Growth o reivindica) e a cidade confere.
# `chave na Growth -> chave na planilha`.
_ALIAS_PLANILHA: dict[str, str] = {
    # A planilha escreve "QNM32"; a Growth, "QNN32". As QNM24 e QNM33 existem nas duas
    # bases e casam sozinhas, entao a QNM32 da planilha so pode ser esta.
    "CEILANDIA QNN32": "CEILANDIA QNM32",
    # Mesma unidade, sem o hifen do lado da planilha.
    "SAO GONCALO - CENTRO": "SAO GONCALO CENTRO",
}


def _chave_planilha(nome: object) -> str:
    return chave_unidade(_PREFIXO_MARCA.sub("", str(nome or "").strip()))


def _texto(valor: object) -> str:
    return " ".join(str(valor).split()) if valor is not None else ""


def _numero(valor: object) -> float | None:
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def ler_planilha(caminho: Path) -> dict[str, dict[str, Any]]:
    import openpyxl

    livro = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    aba = livro["DADOS"]
    linhas = list(aba.values)
    cabecalho = [_texto(c) for c in linhas[0]]
    indice = {nome: i for i, nome in enumerate(cabecalho)}

    registros: dict[str, dict[str, Any]] = {}
    for linha in linhas[1:]:
        nome = _texto(linha[indice["UNIDADE"]]) if "UNIDADE" in indice else ""
        if not nome:
            continue
        registro: dict[str, Any] = {}
        for coluna, campo in _COLUNAS.items():
            if coluna not in indice:
                continue
            bruto = linha[indice[coluna]]
            registro[campo] = (
                _numero(bruto) if campo in {"gold", "life_time", "ltv"} else _texto(bruto)
            )
        modalidades = {
            m.lower(): _texto(linha[indice[m]]).upper().startswith("SIM")
            for m in _MODALIDADES
            if m in indice
        }
        registro["modalidades"] = modalidades
        registros[_chave_planilha(nome)] = registro
    return registros


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planilha", required=True, type=Path)
    parser.add_argument("--growth", required=True, type=Path)
    parser.add_argument("--saida", required=True, type=Path)
    parser.add_argument(
        "--forcar-planilha",
        action="store_true",
        help="a planilha sobrescreve valores ja gravados no JSON (default: o JSON vence)",
    )
    args = parser.parse_args(argv)

    base = carregar_base(args.growth)
    if not len(base):
        print(f"ERRO: base Growth vazia ou ausente em {args.growth}", file=sys.stderr)
        return 2
    catalogo = catalogo_de(base)
    planilha = ler_planilha(args.planilha)

    args.saida.mkdir(parents=True, exist_ok=True)
    atual = ler_cadastro(args.saida)
    unidades = dict(atual.unidades)

    casadas, orfas_growth = 0, []
    usadas: set[str] = set()
    for uid, unidade in sorted(catalogo.items()):
        chaves = {chave_unidade(n) for n in unidade.nomes_crus} | {chave_unidade(unidade.nome)}
        chaves |= {_ALIAS_PLANILHA[c] for c in chaves if c in _ALIAS_PLANILHA}
        achado = next((planilha[c] for c in sorted(chaves) if c in planilha), None)
        if achado is None:
            orfas_growth.append(unidade.nome)
            unidades.setdefault(uid, {})
            continue
        usadas |= {c for c in chaves if c in planilha}
        casadas += 1
        existente = dict(unidades.get(uid, {}))
        for campo, valor in achado.items():
            if args.forcar_planilha or not str(existente.get(campo) or "").strip():
                existente[campo] = valor
        unidades[uid] = existente

    novo = Cadastro(
        versao=atual.versao + 1,
        atualizado_em=datetime.now(UTC).isoformat(timespec="seconds"),
        unidades=unidades,
        disponivel=True,
    )
    gravar_cadastro(novo, args.saida)

    orfas_planilha = sorted(set(planilha) - usadas)
    print(f"unidades na base Growth (comparaveis): {len(catalogo)}")
    print(f"casadas com a planilha             : {casadas}")
    print(f"sem cadastro (ficam sem consultor)  : {len(orfas_growth)} -> {orfas_growth}")
    print(f"na planilha e sem metrica           : {len(orfas_planilha)}")
    print(f"gravado em {args.saida / 'cadastro_unidades.json'} (versao {novo.versao})")
    com_consultor = sum(1 for r in unidades.values() if str(r.get("consultor") or "").strip())
    print(f"com consultor atribuido             : {com_consultor} de {len(unidades)}")
    print(json.dumps(orfas_planilha, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
