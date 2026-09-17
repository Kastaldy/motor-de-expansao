"""`eventos.ip` nao tem produtor, e passar a ter exige fechar o P15 antes.

A coluna `ip INET` existe desde a migration `005` e NUNCA foi escrita: os produtores de
`db/eventos.py` e as escritas de `db/usuarios.py` listam `id_usuario, tipo, entidade,
entidade_id, metadados`. Toda linha de `eventos` tem `ip` nulo.

POR QUE ISTO E' TESTE, E NAO COMENTARIO
--------------------------------------
O `ip` e' dado pessoal (LGPD) e a retencao de `eventos` NAO esta' configurada: a §8.2 do
esquema define o MECANISMO de expurgo, e o prazo -- com a base legal -- e' decisao juridica
ainda aberta (`banco-de-reservas/decisoes-pendentes.md`, **P15**). Acrescentar `ip` ao `INSERT`
custa uma palavra, nao quebra nada, nao muda DDL e por isso nao aparece em revisao de esquema
-- e a partir dela o banco passa a acumular PII sem prazo e sem base legal declarada, numa
tabela de onde apagar e' operacao a' parte. O defeito seria SILENCIOSO nos dois sentidos: nada
falha, e ninguem descobre ate' alguem perguntar por que ha' IP guardado ali.

Ate' 16/09/2026 tres documentos afirmavam o CONTRARIO -- que o log "guarda o IP
deliberadamente" --, e nenhum deles estava certo. Este teste existe para que a frase corrigida
continue verdadeira sem depender de ninguem lembrar dela.

O teste e' deliberadamente BURRO: varre TEXTO, nao AST. Quem montar o `INSERT` em pedacos
escapa dele -- e tambem tera' escapado da regra do proprio contrato, que manda o SQL de escrita
morar em constante localizavel justamente para ser varrivel.

QUANDO O P15 FECHAR: se a decisao for gravar, este arquivo sai no mesmo commit que criar o
produtor; se for nao gravar, ele fica e vira a trava definitiva.
"""

from __future__ import annotations

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]

#: Onde SQL de escrita pode aparecer. `scripts/` entra porque viaja DENTRO da imagem de
#: producao (`Dockerfile.web`), ao lado da credencial -- nao e' diretorio so' de apoio.
_FONTES = ("src/motor_expansao/db", "web/server", "scripts")

#: `INSERT INTO eventos (a, b, c)` -- captura a lista de colunas para inspecionar os nomes.
_INSERT_EM_EVENTOS = re.compile(r"INSERT\s+INTO\s+eventos\s*\(([^)]*)\)", re.IGNORECASE)


def _arquivos_python() -> list[Path]:
    achados: list[Path] = []
    for fonte in _FONTES:
        caminho = _RAIZ / fonte
        if caminho.exists():
            achados.extend(sorted(caminho.rglob("*.py")))
    return achados


def _colunas(lista: str) -> set[str]:
    return {coluna.strip().strip('"').lower() for coluna in lista.split(",")}


def test_nenhum_insert_em_eventos_menciona_ip() -> None:
    ofensores: list[str] = []
    for arquivo in _arquivos_python():
        texto = arquivo.read_text(encoding="utf-8")
        for lista in _INSERT_EM_EVENTOS.findall(texto):
            if "ip" in _colunas(lista):
                ofensores.append(str(arquivo.relative_to(_RAIZ)))

    assert not ofensores, (
        "INSERT em `eventos` com a coluna `ip` em: "
        + ", ".join(sorted(set(ofensores)))
        + ". O `ip` e' dado pessoal e a retencao de `eventos` nao esta' configurada -- base "
        "legal e prazo sao o P15, ainda ABERTO. Feche o P15 antes de gravar; se a decisao for "
        "gravar, remova este teste no mesmo commit que criar o produtor."
    )


def test_a_varredura_enxerga_um_insert_de_verdade() -> None:
    """Sem esta metade, o teste acima e' garantia FALSA.

    Um regex que parou de casar -- tabela renomeada, SQL remontado, arquivo movido para fora de
    `_FONTES` -- deixa o primeiro teste verde PARA SEMPRE, vigiando o vazio. E' a mesma licao que
    esta suite ja' aprendeu caro: guarda que nao pode falhar nao guarda nada.
    """
    vistos = [
        str(arquivo.relative_to(_RAIZ))
        for arquivo in _arquivos_python()
        if _INSERT_EM_EVENTOS.search(arquivo.read_text(encoding="utf-8"))
    ]
    assert vistos, (
        "a varredura nao achou NENHUM `INSERT INTO eventos` -- o regex ou as `_FONTES` pararam "
        "de casar com o codigo, e a trava do `ip` virou decorativa"
    )
