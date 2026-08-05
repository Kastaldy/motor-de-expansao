"""Coleta, por AST, TODOS os nomes de módulo que uma fonte importa.

Helper compartilhado pelos três testes de isolamento do pacote `vulnerabilidade`
(`test_snapshots.py::test_isolamento_imports`,
`test_presenca_agregador.py::test_modulo_nao_importa_demanda_revelada` e
`test_score.py::test_modulo_nao_importa_demanda_revelada`).

**Por que existe.** As três cópias anteriores tinham o mesmo ponto cego de uma linha:

    if isinstance(node, ast.ImportFrom) and node.module:
        nomes.append(node.module)

Quando `node.module is None` — que é exatamente o caso `from .. import X` — o nó era
descartado INTEIRO, e os aliases nunca eram coletados. E, mesmo com `node.module`
preenchido, só o módulo-pai entrava na lista: em `from motor_expansao import dashboard`
a lista recebia `"motor_expansao"`, que não casa nenhuma asserção sobre
`motor_expansao.dashboard`.

Resultado medido pelo QA do BLK-MA-03 (sonda de injeção): das cinco formas de escrever
o import proibido, a checagem pegava **2** e deixava passar **3**. Este helper cobre as
cinco. O guardrail é compartilhado, então a correção também é — triplicá-la foi o que
permitiu ela divergir em primeiro lugar.
"""

from __future__ import annotations

import ast
import inspect
from types import ModuleType

# As cinco formas de escrever um import, na ordem em que a sonda do QA as enumerou.
# `{alvo}` é substituído pelo módulo proibido sob teste.
CINCO_FORMAS: tuple[str, ...] = (
    "import {alvo}",
    "from {alvo} import algo",
    "from {pai} import {folha}",
    "from .. import {folha}",
    'importlib.import_module("{alvo}")',
)


def nomes_importados_da_fonte(fonte: str) -> list[str]:
    """Nomes de módulo importados por `fonte`, cobrindo as cinco formas.

    Para `from X import a, b` devolve `X`, `X.a` e `X.b` — não só `X` —, porque é o
    nome COMPLETO que as asserções de isolamento comparam. Para o import relativo
    `from .. import a`, onde `node.module is None`, devolve `a`.
    """
    nomes: list[str] = []
    for node in ast.walk(ast.parse(fonte)):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                nomes.append(node.module)
                nomes.extend(f"{node.module}.{a.name}" for a in node.names)
            else:
                # `from .. import X` / `from . import X`: o pai é relativo e não
                # aparece no AST, mas o alias é o nome do módulo importado.
                nomes.extend(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            nomes.extend(a.name for a in node.names)
        elif isinstance(node, ast.Call):
            # `importlib.import_module("X")` e `__import__("X")` são chamadas, não
            # nós de import — o AST puro nunca as veria.
            alvo = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if alvo in ("import_module", "__import__"):
                nomes.extend(
                    arg.value
                    for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                )
    return nomes


def nomes_importados(modulo: ModuleType) -> list[str]:
    """Idem, lendo a fonte de um módulo já importado."""
    return nomes_importados_da_fonte(inspect.getsource(modulo))


def casa_proibicao(nome: str, proibido: str) -> bool:
    """`nome` importado viola a proibição de `proibido`?

    Duas checagens, e as duas são necessárias:

    - **caminho**: `proibido` exato ou como prefixo (`motor_expansao.dashboard.pages`);
    - **segmento**: a folha de `proibido` como um segmento inteiro de `nome`. Um import
      relativo (`from .. import dashboard`) deixa no AST apenas o ALIAS — o pai não
      aparece em lugar nenhum —, então só a checagem por caminho o deixaria passar.

    Compara SEGMENTO, não substring, para não acusar um módulo cujo nome apenas contém
    a palavra (`dashboard_utils` não é `dashboard`).
    """
    if nome == proibido or nome.startswith(proibido + "."):
        return True
    return proibido.rpartition(".")[2] in nome.split(".")


def fontes_com_import_injetado(alvo: str) -> list[tuple[str, str]]:
    """`[(rotulo, fonte)]` — uma fonte sintética por forma de importar `alvo`.

    Usado pelas sondas de injeção que provam que a checagem pega as cinco formas.
    """
    pai, _, folha = alvo.rpartition(".")
    return [
        (forma, forma.format(alvo=alvo, pai=pai or alvo, folha=folha or alvo))
        for forma in CINCO_FORMAS
    ]
