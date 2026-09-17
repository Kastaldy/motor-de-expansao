"""Alias: o indice de praca (DEC-041) mora em `motor_expansao.dashboard.praca_indice`.

Mudou para `src/` porque o Relatorio Municipal da API/bot tambem ordena "Onde crescer" por ele,
e o container da API nao importa `web/server`. O alias troca o proprio modulo em `sys.modules`:
`import praca_indice` devolve o MESMO objeto, entao monkeypatch e constantes lidas por atributo
continuam valendo nos dois nomes.
"""

import sys

from motor_expansao.dashboard import praca_indice as _modulo

sys.modules[__name__] = _modulo
