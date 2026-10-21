"""E0 do plano de correcao da renda: a renda exibida tem UM ponto de aplicacao.

Fator temporal, uplift de composicao e moradores por domicilio so multiplicam (ou dividem) uma
renda DENTRO de `src/motor_expansao/renda/`. Fora dele, o codigo CHAMA `renda_domiciliar`,
`renda_per_capita`, `fator_composto_domiciliar`, `renda_domiciliar_hex`... e passa o uplift
como ARGUMENTO, nunca como operando.

Por que um teste e nao uma convencao
------------------------------------
Antes da E0 o fator temporal multiplicava a renda em CINCO lugares (`censo_point` duas vezes,
`censo_map`, `renda_hex`, `app.py`), cada um lendo um atributo de modulo reatribuido no boot do
piloto. Trocar a fonte do fator (CAGED -> PNAD, com F_pc != F_dom) exigiria acertar os cinco
de uma vez, e a sexta copia que alguem escrevesse depois passaria calada -- e a mesma familia
dos defeitos de renda de 2026-08-13 (k aplicado duas vezes) e 2026-10-16 (PDF com formula
propria). Este arquivo e o fio de alarme: molde de `test_fio_de_alarme_pais.py` (DEC-047).

O que ele procura (AST, sem docstrings; comentarios nao entram na arvore)
--------------------------------------------------------------------------
- **R1** -- os nomes do fator temporal de antes da E0 (`FATOR_TEMPORAL_RENDA`,
  `fator_temporal_renda`, `_carregar_fator_temporal`, `DATA_REFERENCIA_RENDA`) como
  identificador, atributo, nome importado, parametro OU dentro de string (cobre `getattr`,
  chave de dicionario e f-string). As chaves de resultado que o motor do ponto mantem por
  contrato sao montadas DENTRO do modulo (`campos_referencia_ponto`).
- **R2** -- `*` ou `/` (tambem `*=` e `/=`) com um operando que contenha nome ou atributo
  casando `uplift` (sem diferenciar caixa). Pega `x * uplift`, `x * float(mod.uplift_setor(..))`
  e `renda / uplift`. NAO conta `fracao_uplift_extrapolado*`, que e uma fracao de peso, nao
  um fator de renda.
- **R3** -- o mesmo para QUALQUER identificador com `morador` (sem diferenciar caixa) e para
  coluna indexada por string com `morador` (`row["avg_moradores_..."]`): a conversao
  domiciliar <-> per capita tem de sair do modulo, senao a per capita volta a ser derivada da
  domiciliar (`renda_domiciliar_total / moradores`, a linha de antes da E0) e carrega o F_dom.
  A reconstrucao da V06004 pela per capita bruta tambem mora no modulo
  (`v06004_de_fallback`).
- **R4** -- importar o modulo aposentado `motor_expansao.dashboard.renda_hex`.
- **R5** -- o fator pela API NOVA fora do dono: `fator`/`fator_hex` como atributo ou nome
  importado de `motor_expansao.renda`, o nome `fator_hex` em qualquer posicao,
  `fator_composto_domiciliar` como operando de `*`/`/`, e os literais dos fatores de TODA
  versao empacotada, exatos e com 4 casas (`1.1641` da v0, `1.3401`/`1.247` da PNAD 2025...). Sem isto, `x * _renda.fator(uf, "domiciliar")` abriria um segundo ponto de
  aplicacao que o `VIGENTE` novo nao alcancaria.

- **R6** (E1) -- SUPERFICIE servindo renda CRUA: num campo de payload/linha cujo nome tem
  `renda` (chave de dict literal ou `x["...renda..."] = ...`), o valor LE diretamente (argumento
  de chamada, como `r.get("...")`/`media("...")`, ou indice `df["..."]`) uma coluna de renda
  crua -- a V06004 (`renda_responsavel_media_setor_2022`), a calibrada na escala do score, a per
  capita bruta, a SIDRA municipal (`renda_per_capita`), a `renda_leitura` do hexagono, as
  copias do coletor (`censo_renda_per_capita_hex`, `m1_renda_per_capita`) ou a base pre-uplift
  do motor do ponto (`renda_media_domiciliar_raio`) -- SEM passar por uma conversao do modulo
  (chamada cujo nome tem `renda_domiciliar`/`renda_per_capita`/`renda_pc`, como
  `_renda_per_capita_hex(r)` ou `renda_domiciliar_da_linha(r, uf, cod)`). Copiar uma COLUNA DE
  INSUMO do artefato sob o PROPRIO nome (`{"renda_per_capita_setor_2022": r.get(<mesmo nome>)}`)
  nao e exibir renda: e passar o insumo adiante. Escopo: as superficies (`web/server/`,
  `src/motor_expansao/api/`, `src/motor_expansao/dashboard/`); o score, o M1 e os produtores
  LEEM as colunas cruas por definicao. Era o defeito das telas da frente (b): mapa de calor de
  setor, `/api/hexagonos`, rede, Oportunidades e o campo `renda_media_domiciliar_raio` da API.

"Operando de `*` ou `/`" inclui as formas equivalentes por chamada (`a.mul(b)`, `.div`,
`.truediv`, `np.multiply`, `np.divide`, `operator.mul`, `operator.truediv`...) e os ALIASES:
um nome atribuido a partir de uplift/moradores (`fator_setor = uplift_setor(...)`,
`f = float(u.uplift_municipio(...))`) herda a marca, no arquivo inteiro.

O que ele NAO procura: coluna de UPLIFT indexada por string (`df["uplift_composicao_final"]
* ...`). Os unicos usos assim sao os pipelines PRODUTORES do uplift (`derivar_uplift_*`), que
calculam o proprio uplift -- nao aplicam fator a renda exibida. Proibi-los exigiria uma lista
de excecoes, e a lista daqui nasce VAZIA e fica vazia.

Escopo dos PRODUTORES (`src/motor_expansao/pipelines/`): eles FABRICAM a base do Censo
(V06004 = per capita x moradores no pacote AR, per capita bruta = V06004 / moradores na malha),
entao neles a R3 volta ao lookup do modulo (`moradores_por_domicilio`) e nao ha aliases. R1, R2,
R4 e R5 valem igual. E uma regra de ESCOPO declarada aqui, nao uma excecao por arquivo.
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
#: Universo: codigo Python que serve trafego ou gera artefato.
_RAIZES = ("src", "web/server", "scripts")
#: O dono legitimo das formulas fica FORA da varredura.
_DONO = "src/motor_expansao/renda/"
_IGNORAR = {"__pycache__", ".venv", "node_modules", "build", "dist"}

#: R1 -- nomes do fator temporal de antes da E0.
_NOMES_FATOR = (
    "FATOR_TEMPORAL_RENDA",
    "fator_temporal_renda",
    "_carregar_fator_temporal",
    "DATA_REFERENCIA_RENDA",
)
_RE_NOMES_FATOR = re.compile(r"\b(?:" + "|".join(map(re.escape, _NOMES_FATOR)) + r")\b")
#: R2 -- identificador de uplift como operando de `*` ou `/`.
_RE_UPLIFT = re.compile(r"(?i)uplift")
#: `fracao_uplift_extrapolado*` e `uplift_extrapolado` sao fracao de peso / predicado booleano
#: (setor fora do envelope da calibracao), nao fator de renda.
_RE_UPLIFT_PERMITIDO = re.compile(r"(?i)^(?:fracao_uplift_extrapolado|uplift_extrapolado$)")
#: Chamada que DEVOLVE um insumo (a API de `renda.insumos`): so ela marca alias. Casar `uplift`
#: em qualquer lugar do nome marcaria `df = derivar_uplift(...)` (um DataFrame) como fator.
_RE_CHAMADA_INSUMO = re.compile(r"(?i)^_?(?:uplift|moradores)")
#: Pipelines PRODUTORES da base do Censo (V06004, per capita bruta, uplift): multiplicam e
#: dividem por moradores para FABRICAR as colunas, nao para exibir renda. Fora deles valem R3
#: ampla e os aliases; neles, R3 so pega o lookup do modulo (`moradores_por_domicilio`).
_PRODUTORES = "src/motor_expansao/pipelines/"
_RE_MORADORES_PRODUTOR = re.compile(r"^moradores_por_domicilio$")
#: R3 -- moradores como operando de `*` ou `/` (identificador OU coluna por string).
_RE_MORADORES = re.compile(r"(?i)morador")
#: R4 -- modulo aposentado na E0.
_MODULO_APOSENTADO = "motor_expansao.dashboard.renda_hex"
#: R5 -- a API nova do fator, fora do dono.
_ATRIBUTOS_FATOR = frozenset({"fator", "fator_hex"})
_NOMES_FATOR_SEMPRE = frozenset({"fator_hex"})
_FATOR_COMPOSTO = "fator_composto_domiciliar"


def _literais_das_versoes() -> frozenset[float]:
    """Todo fator per capita/domiciliar de TODA versao empacotada (nacional e excecoes), exato e
    arredondado a 4 casas -- a grafia de quem o copiaria a mao. `1.0` fica de fora (a AR e o
    `moradores` da v0 o usam, e `x * 1.0` nao e fator)."""
    import json

    raiz = Path(__file__).resolve().parents[2] / "src" / "motor_expansao" / "renda" / "fatores"
    out: set[float] = {1.1641}
    for arq in raiz.glob("*/*.json"):
        dados = json.loads(arq.read_text(encoding="utf-8"))
        grupos = [dados["nacional"], *dados.get("excecoes_aprovadas", {}).values()]
        for g in grupos:
            for tipo in ("per_capita", "domiciliar"):
                v = float(g[tipo])
                if v != 1.0:
                    out |= {v, round(v, 4)}
    return frozenset(out)


_LITERAIS_FATOR = _literais_das_versoes()
#: Chamadas equivalentes a `*` e `/` (metodo do pandas/numpy ou funcao de `operator`/`np`).
_CHAMADAS_ARITMETICAS = frozenset(
    {
        "mul", "rmul", "multiply", "div", "rdiv", "truediv", "rtruediv", "divide",
        "floordiv", "rfloordiv", "imul", "itruediv",
    }
)
#: Embrulhos que nao mudam a natureza do valor: o alias de `float(uplift(...))` e um uplift.
_EMBRULHOS = frozenset(
    {
        "float", "int", "round", "Series", "to_numeric", "asarray", "array", "list", "tuple",
        "where", "fillna", "astype", "clip", "mask", "abs",
    }
)

#: R6 -- superficies (quem serve tela, payload e PDF).
_SUPERFICIES = ("web/server/", "src/motor_expansao/api/", "src/motor_expansao/dashboard/")
#: R6 -- colunas de INSUMO do artefato (copia-las sob o proprio nome e passar o insumo).
_COLUNAS_INSUMO_RENDA = frozenset(
    {
        "renda_responsavel_media_setor_2022",
        "renda_per_capita_setor_2022_calibrada",
        "renda_per_capita_setor_2022",
        "renda_per_capita",
    }
)
#: R6 -- tudo que e renda CRUA: os insumos e as copias/derivadas sem conversao.
_COLUNAS_RENDA_CRUA = _COLUNAS_INSUMO_RENDA | frozenset(
    {
        "renda_leitura",
        "censo_renda_per_capita_hex",
        "m1_renda_per_capita",
        "renda_media_domiciliar_raio",
    }
)
_RE_CAMPO_RENDA = re.compile(r"(?i)renda")
#: Chamada que CONVERTE a renda pela cadeia canonica (do modulo ou o wrapper dele).
_RE_CONVERSAO_RENDA = re.compile(r"(?i)renda_(?:domiciliar|per_capita|pc)")
#: Chamadas que NAO devolvem o valor da renda (mascara, contagem, teste): nao a carregam.
_CHAMADAS_SEM_VALOR = frozenset(
    {
        "len", "notna", "isna", "notnull", "isnull", "count", "nunique", "any", "all",
        "isin", "between", "isinstance", "bool", "hasattr", "eq", "ne", "gt", "ge", "lt", "le",
    }
)

#: Excecoes. Nasce VAZIA e um teste proprio trava que continue vazia: se um caso legitimo
#: aparecer, a regra e que muda (num PR visivel), nao a lista.
_EXCECOES: frozenset[str] = frozenset()


def _fontes() -> list[tuple[Path, str]]:
    achados: list[tuple[Path, str]] = []
    for raiz in _RAIZES:
        base = _REPO / raiz
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            rel = p.relative_to(_REPO).as_posix()
            if _IGNORAR & set(p.relative_to(_REPO).parts) or rel.startswith(_DONO):
                continue
            achados.append((p, rel))
    return achados


def _docstrings(arvore: ast.AST) -> set[int]:
    """`id()` dos nos de docstring (modulo, classe, funcao): texto explicativo, nao codigo."""
    ids: set[int] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(corpo, list) or not corpo:
            continue
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            ids.add(id(primeiro.value))
    return ids


def _identificadores(no: ast.AST) -> list[str]:
    """Nomes e atributos dentro de `no` (inclui o nome de funcao chamada: `mod.uplift_x(...)`)."""
    nomes: list[str] = []
    for filho in ast.walk(no):
        if isinstance(filho, ast.Name):
            nomes.append(filho.id)
        elif isinstance(filho, ast.Attribute):
            nomes.append(filho.attr)
    return nomes


def _nome_chamado(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _operandos(no: ast.AST) -> list[ast.AST]:
    """Operandos de `*`/`/` -- tambem na forma de chamada (`a.mul(b)`, `np.divide(a, b)`)."""
    if isinstance(no, ast.BinOp) and isinstance(no.op, (ast.Mult, ast.Div, ast.FloorDiv)):
        return [no.left, no.right]
    if isinstance(no, ast.AugAssign) and isinstance(no.op, (ast.Mult, ast.Div, ast.FloorDiv)):
        return [no.target, no.value]
    if isinstance(no, ast.Call) and _nome_chamado(no.func) in _CHAMADAS_ARITMETICAS:
        operandos: list[ast.AST] = list(no.args) + [k.value for k in no.keywords]
        if isinstance(no.func, ast.Attribute):
            operandos.append(no.func.value)  # o receptor de `a.mul(b)` e operando
        return operandos
    return []


def _casa_insumo(nome: str) -> bool:
    return bool(
        (_RE_UPLIFT.search(nome) and not _RE_UPLIFT_PERMITIDO.search(nome))
        or _RE_MORADORES.search(nome)
    )


def _coluna_morador(no: ast.AST) -> bool:
    return (
        isinstance(no, ast.Subscript)
        and isinstance(no.slice, ast.Constant)
        and isinstance(no.slice.value, str)
        and bool(_RE_MORADORES.search(no.slice.value))
    )


def _eh_insumo(expr: ast.AST) -> bool:
    """`expr` E (nao so contem) um uplift/moradores: nome, chamada ou embrulho deles.

    Nao desce nos argumentos de uma chamada qualquer: `renda_domiciliar(v, uplift, uf)` e uma
    RENDA, nao um uplift, e marcar o resultado como alias geraria falso positivo.
    """
    if isinstance(expr, ast.Name):
        return _casa_insumo(expr.id)
    if isinstance(expr, ast.Attribute):
        return _casa_insumo(expr.attr)
    if isinstance(expr, ast.Call):
        nome = _nome_chamado(expr.func)
        if _RE_CHAMADA_INSUMO.search(nome) and _casa_insumo(nome):
            return True
        if nome in _EMBRULHOS:
            alvos: list[ast.AST] = list(expr.args)
            if isinstance(expr.func, ast.Attribute):
                alvos.append(expr.func.value)
            return any(_eh_insumo(a) for a in alvos)
        return False
    if isinstance(expr, ast.IfExp):
        return _eh_insumo(expr.body) or _eh_insumo(expr.orelse)
    if isinstance(expr, (ast.List, ast.Tuple)):
        return any(_eh_insumo(e) for e in expr.elts)
    if isinstance(expr, (ast.ListComp, ast.GeneratorExp)):
        return _eh_insumo(expr.elt)
    if isinstance(expr, ast.Subscript):
        return _eh_insumo(expr.value) or _coluna_morador(expr)
    return False


def _aliases(arvore: ast.AST) -> set[str]:
    """Nomes atribuidos a partir de uplift/moradores, no arquivo inteiro (ate ponto fixo)."""
    marcados: set[str] = set()
    while True:
        antes = len(marcados)
        for no in ast.walk(arvore):
            if isinstance(no, ast.Assign):
                alvos, valor = no.targets, no.value
            elif isinstance(no, (ast.AnnAssign, ast.NamedExpr)) and no.value is not None:
                alvos, valor = [no.target], no.value
            else:
                continue
            if _eh_insumo(valor) or (isinstance(valor, ast.Name) and valor.id in marcados):
                marcados.update(a.id for a in alvos if isinstance(a, ast.Name))
        if len(marcados) == antes:
            return marcados


def _imports_do_fator(arvore: ast.AST) -> list[tuple[int, str]]:
    """`from motor_expansao.renda[...] import fator|fator_hex` -- R5."""
    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and (no.module or "").startswith("motor_expansao.renda"):
            for a in no.names:
                if a.name in _ATRIBUTOS_FATOR:
                    achados.append((no.lineno, f"from {no.module} import {a.name}"))
    return achados


def _leitura_crua(no: ast.AST) -> str | None:
    """A string `no`, se ela for o NOME de uma coluna de renda crua (argumento ou indice)."""
    if isinstance(no, ast.Constant) and isinstance(no.value, str) and no.value in _COLUNAS_RENDA_CRUA:
        return no.value
    return None


def _crus(expr: ast.AST | None, vars_crus: dict[str, set[str]]) -> set[str]:
    """Colunas de renda CRUA que chegam ao VALOR de `expr`, avaliado por OPERANDO.

    Le a coluna crua: argumento string de chamada (`r.get("x")`, `_numeric(df, "x")`) ou indice
    (`df["x"]`, `df.loc[m, "x"]`). Propaga por embrulho/metodo/aritmetica/indice e por variavel
    marcada (`vars_crus`). Uma chamada de CONVERSAO devolve renda canonica (vazio) -- so ela, e
    nao a expressao inteira: em `cru or convertido` o ramo cru continua cru. Comparacao e
    chamada que nao devolve o valor (`notna`, `len`...) tambem nao carregam renda.
    """
    if expr is None or isinstance(expr, (ast.Constant, ast.Compare, ast.Lambda)):
        return set()
    if isinstance(expr, ast.Name):
        return set(vars_crus.get(expr.id, ()))
    if isinstance(expr, ast.BoolOp):
        return set().union(*(_crus(v, vars_crus) for v in expr.values))
    if isinstance(expr, ast.IfExp):
        return _crus(expr.body, vars_crus) | _crus(expr.orelse, vars_crus)
    if isinstance(expr, ast.BinOp):
        return _crus(expr.left, vars_crus) | _crus(expr.right, vars_crus)
    if isinstance(expr, ast.UnaryOp):
        return _crus(expr.operand, vars_crus)
    if isinstance(expr, (ast.Attribute, ast.Starred, ast.Await)):
        return _crus(expr.value, vars_crus)
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        return set().union(*(_crus(e, vars_crus) for e in expr.elts))
    if isinstance(expr, ast.Call):
        nome = _nome_chamado(expr.func)
        if _RE_CONVERSAO_RENDA.search(nome) or nome in _CHAMADAS_SEM_VALOR:
            return set()
        lidas: set[str] = set()
        for arg in [*expr.args, *(k.value for k in expr.keywords)]:
            coluna = _leitura_crua(arg)
            lidas |= {coluna} if coluna else _crus(arg, vars_crus)
        if isinstance(expr.func, ast.Attribute):
            lidas |= _crus(expr.func.value, vars_crus)  # receptor: `renda.mean()`
        return lidas
    if isinstance(expr, ast.Subscript):
        lidas = _crus(expr.value, vars_crus)
        indices = expr.slice.elts if isinstance(expr.slice, ast.Tuple) else [expr.slice]
        lidas |= {c for c in (_leitura_crua(i) for i in indices) if c}
        return lidas
    return set()


def _filhos_do_escopo(escopo: ast.AST) -> list[ast.AST]:
    """Nos do escopo SEM descer em funcao aninhada (que e escopo proprio, herdando este)."""
    nos: list[ast.AST] = []
    pilha = list(ast.iter_child_nodes(escopo))
    while pilha:
        no = pilha.pop()
        nos.append(no)
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            pilha.extend(ast.iter_child_nodes(no))
    return nos


def _marcar_vars(nos: list[ast.AST], herdadas: dict[str, set[str]]) -> dict[str, set[str]]:
    """Variaveis do escopo que guardam renda crua (ate ponto fixo; insensivel a fluxo)."""
    marcadas = {k: set(v) for k, v in herdadas.items()}
    while True:
        mudou = False
        for no in nos:
            if isinstance(no, ast.Assign):
                alvos, valor = no.targets, no.value
            elif isinstance(no, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and no.value is not None:
                alvos, valor = [no.target], no.value
            else:
                continue
            crus = _crus(valor, marcadas)
            if not crus:
                continue
            for alvo in alvos:
                if isinstance(alvo, ast.Name) and not crus <= marcadas.get(alvo.id, set()):
                    marcadas.setdefault(alvo.id, set()).update(crus)
                    mudou = True
        if not mudou:
            return marcadas


def _campos_de_renda(no: ast.AST) -> list[tuple[str, ast.AST, bool]]:
    """(campo, valor, e_coluna) servidos por `no`: chave de dict, `x["campo"] = v` (coluna) e
    `f(campo=v)`."""
    if isinstance(no, ast.Dict):
        return [
            (k.value, v, False)
            for k, v in zip(no.keys, no.values, strict=True)
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        ]
    if isinstance(no, ast.Assign):
        return [
            (alvo.slice.value, no.value, True)
            for alvo in no.targets
            if isinstance(alvo, ast.Subscript)
            and isinstance(alvo.slice, ast.Constant)
            and isinstance(alvo.slice.value, str)
        ]
    if isinstance(no, ast.Call) and not _RE_CONVERSAO_RENDA.search(_nome_chamado(no.func)):
        # `.update(renda=...)`, `dict(renda=...)`, schema(renda_x=...). A chamada de conversao
        # recebe a renda crua como INSUMO por keyword: isso e o certo, nao servir.
        return [(k.arg, k.value, False) for k in no.keywords if k.arg]
    return []


def _crua_permitida(campo: str, crus: set[str], *, e_coluna: bool) -> bool:
    """Renda crua LEGITIMA no campo: e o proprio insumo, nao renda servida ao usuario.

    (a) insumo copiado sob o PROPRIO nome (registro interno do mapa do PDF);
    (b) intermediario de nome declarado cru (`_COLUNAS_RENDA_CRUA`, fora dos insumos) nascendo
        SO de insumos -- ex.: `renda_media_domiciliar_raio` do motor, V06004 pre-uplift: o nome
        ja diz cru, e quem o servir sera pego ao LER esse nome;
    (c) coluna de insumo preenchida por OUTRO insumo no proprio frame (fallback de entrada,
        `df["<insumo>"] = <insumo>`) -- so em atribuicao de coluna, nunca em chave de dict, que
        e onde o payload nasce.
    """
    if not crus <= _COLUNAS_INSUMO_RENDA:
        return False
    if crus == {campo}:
        return True
    if campo in _COLUNAS_RENDA_CRUA - _COLUNAS_INSUMO_RENDA:
        return True
    return e_coluna and campo in _COLUNAS_INSUMO_RENDA


def _violacoes_superficie(texto: str) -> list[tuple[int, str, str]]:
    """R6: campo de renda de payload/linha servindo coluna de renda CRUA sem conversao.

    Segue a renda crua guardada em VARIAVEL (por escopo de funcao) ate o campo servido.
    """
    achados: list[tuple[int, str, str]] = []

    def _varrer(escopo: ast.AST, herdadas: dict[str, set[str]]) -> None:
        nos = _filhos_do_escopo(escopo)
        vars_crus = _marcar_vars(nos, herdadas)
        for no in nos:
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _varrer(no, vars_crus)
                continue
            for campo, valor, e_coluna in _campos_de_renda(no):
                if not _RE_CAMPO_RENDA.search(campo):
                    continue
                crus = _crus(valor, vars_crus)
                if crus and not _crua_permitida(campo, crus, e_coluna=e_coluna):
                    achados.append(
                        (getattr(valor, "lineno", 0), "R6", f"{campo} <- {sorted(crus)[0]}")
                    )

    _varrer(ast.parse(texto), {})
    return sorted(set(achados))


def _violacoes(texto: str, *, produtor: bool = False) -> list[tuple[int, str, str]]:
    """(linha, regra, trecho) de cada violacao em `texto` (codigo Python).

    `produtor=True` (arquivo em `_PRODUTORES`): R3 estreita e sem aliases; R1/R2/R4/R5 iguais.
    """
    arvore = ast.parse(texto)
    docs = _docstrings(arvore)
    aliases = set() if produtor else _aliases(arvore)
    re_moradores = _RE_MORADORES_PRODUTOR if produtor else _RE_MORADORES
    achados: list[tuple[int, str, str]] = []

    def _r1(linha: int, nome: str) -> None:
        if _RE_NOMES_FATOR.search(nome):
            achados.append((linha, "R1", nome))

    for no in ast.walk(arvore):
        linha = getattr(no, "lineno", 0)
        # R1: o nome em qualquer posicao sintatica.
        if isinstance(no, ast.Name):
            _r1(linha, no.id)
        elif isinstance(no, ast.Attribute):
            _r1(linha, no.attr)
        elif isinstance(no, ast.alias):
            _r1(linha, no.name)
            if no.asname:
                _r1(linha, no.asname)
        elif isinstance(no, ast.arg):
            _r1(linha, no.arg)
        elif isinstance(no, ast.keyword) and no.arg:
            _r1(linha, no.arg)
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _r1(linha, no.name)
        elif (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in docs
            and _RE_NOMES_FATOR.search(no.value)
        ):
            achados.append((linha, "R1", _RE_NOMES_FATOR.search(no.value).group(0)))
        # R4: o modulo aposentado, em qualquer forma de import.
        if isinstance(no, ast.Import):
            for a in no.names:
                if a.name == _MODULO_APOSENTADO:
                    achados.append((linha, "R4", a.name))
        elif isinstance(no, ast.ImportFrom):
            mod = no.module or ""
            if mod == _MODULO_APOSENTADO or (
                mod == "motor_expansao.dashboard" and any(a.name == "renda_hex" for a in no.names)
            ):
                achados.append((linha, "R4", f"from {mod} import ..."))
        # R5: a API nova do fator, fora do dono.
        if isinstance(no, ast.Attribute) and no.attr in _ATRIBUTOS_FATOR:
            achados.append((linha, "R5", no.attr))
        elif isinstance(no, ast.Name) and no.id in _NOMES_FATOR_SEMPRE:
            achados.append((linha, "R5", no.id))
        elif (
            isinstance(no, ast.Constant)
            and isinstance(no.value, float)
            and no.value in _LITERAIS_FATOR
        ):
            achados.append((linha, "R5", repr(no.value)))
        # R2 / R3 / R5: operandos de * e / (e das formas equivalentes), com os aliases.
        for operando in _operandos(no):
            for nome in _identificadores(operando):
                if _RE_UPLIFT.search(nome) and not _RE_UPLIFT_PERMITIDO.search(nome):
                    achados.append((linha, "R2", nome))
                elif re_moradores.search(nome):
                    achados.append((linha, "R3", nome))
                elif nome in aliases:
                    achados.append((linha, "R2/R3", f"{nome} (alias de uplift/moradores)"))
                if nome == _FATOR_COMPOSTO:
                    achados.append((linha, "R5", nome))
            for sub in ast.walk(operando):
                if not produtor and _coluna_morador(sub):
                    achados.append((linha, "R3", sub.slice.value))  # type: ignore[attr-defined]
    achados.extend((n, "R5", t) for n, t in _imports_do_fator(arvore))
    return sorted(set(achados))


def test_renda_exibida_tem_um_ponto_unico_de_aplicacao() -> None:
    ocorrencias: list[str] = []
    for arquivo, rel in _fontes():
        if rel in _EXCECOES:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            # Pular seria passar calado (como o SyntaxError abaixo): um .py salvo em cp1252
            # com `x * FATOR_TEMPORAL_RENDA` nao seria varrido e o teste ficaria verde.
            ocorrencias.append(f"{rel}: ilegivel ({exc})")
            continue
        try:
            violacoes = _violacoes(texto, produtor=rel.startswith(_PRODUTORES))
        except SyntaxError as exc:  # arquivo que nao parseia nao pode passar calado
            ocorrencias.append(f"{rel}: nao parseia ({exc})")
            continue
        ocorrencias.extend(f"{rel}:{n}: [{regra}] {trecho}" for n, regra, trecho in violacoes)

    assert not ocorrencias, (
        "A renda exibida so recebe fator temporal, uplift e moradores DENTRO de\n"
        "`motor_expansao.renda` (E0). Fora dele, chame `renda_domiciliar`, `renda_per_capita`,\n"
        "`fator_composto_domiciliar` ou as funcoes de `renda.hex`, passando o uplift como\n"
        "argumento; o fator vem de `fator(uf, tipo)`.\n\nAchado em:\n  "
        + "\n  ".join(ocorrencias)
    )


def test_nenhuma_superficie_serve_renda_crua() -> None:
    """R6 (E1): tela, payload e PDF so servem renda que passou pela cadeia canonica do modulo."""
    ocorrencias: list[str] = []
    for arquivo, rel in _fontes():
        if rel in _EXCECOES or not rel.startswith(_SUPERFICIES):
            continue
        try:
            violacoes = _violacoes_superficie(arquivo.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError, SyntaxError) as exc:
            # Pular seria passar calado, como na varredura principal.
            ocorrencias.append(f"{rel}: ilegivel/nao parseia ({exc})")
            continue
        ocorrencias.extend(f"{rel}:{n}: [{regra}] {trecho}" for n, regra, trecho in violacoes)
    assert not ocorrencias, (
        "Superficie servindo renda CRUA (V06004, calibrada do score, SIDRA sem fator, "
        "`renda_leitura`...). Converta pelo modulo `motor_expansao.renda` (`renda.setor`, "
        "`renda.hex`, `_renda_per_capita_hex`/`_renda_domiciliar_hex`).\n\nAchado em:\n  "
        + "\n  ".join(ocorrencias)
    )


def test_a_varredura_de_superficie_cobre_as_telas_da_e1() -> None:
    """As superficies corrigidas na E1 continuam DENTRO do escopo da R6."""
    rels = {rel for _, rel in _fontes() if rel.startswith(_SUPERFICIES)}
    for rel in (
        "web/server/app.py",
        "web/server/rede_inteligencia.py",
        "src/motor_expansao/api/service.py",
        "src/motor_expansao/dashboard/censo_point.py",
        "src/motor_expansao/dashboard/relatorio_municipal.py",
    ):
        assert rel in rels, rel


@pytest.mark.parametrize(
    "trecho",
    [
        # As cinco linhas de antes da E1, como estavam.
        '{"renda": _num(r.get("renda_per_capita_setor_2022_calibrada"))}',
        '{"renda": _num(r.get("renda_leitura"))}',
        '{"renda_per_capita": _r(media("renda_per_capita_setor_2022_calibrada"), 0)}',
        '{"renda_pc": _op_num(d.get("censo_renda_per_capita_hex")) or _op_num(d.get("m1_renda_per_capita"))}',
        '{"renda_media_domiciliar_raio": result.get("renda_media_domiciliar_raio")}',
        # V06004 bruta e SIDRA sem fator, por indice e por atribuicao.
        'item["renda_media"] = float(df["renda_responsavel_media_setor_2022"].mean())',
        'linha = {"renda": row["renda_per_capita"]}',
        'x = {"renda_bairro": _coluna_numerica(df, "renda_per_capita_setor_2022")}',
        # As outras duas superficies de antes da E1: a leitura crua GUARDADA numa variavel e
        # so depois servida (perfil do bairro em censo_point; painel per capita e tabela de
        # hexagonos em relatorio_municipal).
        textwrap.dedent(
            """
            def agregar(subset, dom, result):
                renda = _numeric(subset, "renda_responsavel_media_setor_2022")
                renda_mask = renda.notna() & dom.notna() & dom.gt(0)
                result["renda_media_domiciliar"] = round(
                    float(np.average(renda[renda_mask], weights=dom[renda_mask])), 2
                )
            """
        ),
        textwrap.dedent(
            """
            def agregar_municipio(df_muni):
                renda = _coluna_numerica(df_muni, "renda_per_capita")
                pesos = _coluna_numerica(df_muni, "pop_total_setor_2022")
                valid = renda.notna() & pesos.notna() & (pesos > 0)
                renda_per_capita_media = float(
                    (renda[valid] * pesos[valid]).sum() / pesos[valid].sum()
                )
                return {"renda_per_capita_media": renda_per_capita_media}
            """
        ),
        textwrap.dedent(
            """
            def _tabela_hexes(df_muni, mapa_dom):
                if mapa_dom:
                    renda = df_muni["hex_id"].map(mapa_dom)
                else:
                    renda = _coluna_numerica(df_muni, "renda_per_capita_setor_2022_calibrada")
                return pd.DataFrame({"renda": renda})
            """
        ),
        # Isencao por OPERANDO: um ramo convertido nao lava o ramo cru.
        '{"renda_pc": _op_num(d.get("censo_renda_per_capita_hex")) or _renda_per_capita_hex(r)}',
        '{"renda": _renda_per_capita_hex(r) if ok else r.get("renda_leitura")}',
        # Keyword (`.update`, `dict(...)`, schema).
        'item.update(renda=_num(r.get("renda_leitura")))',
        'Resp(renda_media=df["renda_per_capita"].mean())',
        # Variavel a variavel, e indice com mascara.
        textwrap.dedent(
            """
            v = r.get("renda_leitura")
            w = float(v)
            linha = {"renda": w}
            """
        ),
        'x = {"renda": df.loc[m, "renda_per_capita_setor_2022_calibrada"].mean()}',
    ],
)
def test_r6_pega_superficie_com_renda_crua(trecho: str) -> None:
    assert "R6" in {r for _, r, _ in _violacoes_superficie(trecho)}, trecho


@pytest.mark.parametrize(
    "trecho",
    [
        # Convertida pelo modulo (ou pelo wrapper do app, que chama o modulo).
        '{"renda": _renda_per_capita_hex(r)}',
        '{"renda_domiciliar": _num(_renda_setor.renda_domiciliar_da_linha(r, uf, cod))}',
        '{"renda_media_domiciliar_raio": result.get("renda_domiciliar_total_raio")}',
        'item["renda_pc"] = _renda_hex.renda_per_capita_por_linha(df, precedencia=("renda_per_capita",))',
        # Insumo copiado sob o PROPRIO nome (registro interno do mapa do PDF).
        '{"renda_responsavel_media_setor_2022": row.get("renda_responsavel_media_setor_2022")}',
        # Comparacao com o nome da coluna (procedencia de leitura), nao leitura de valor.
        '{"renda_municipal": r.get("renda_origem") == "renda_per_capita"}',
        # Mapeamento de nomes (literal solto) e campo que nao e renda.
        '{"censo_renda_per_capita_hex": "renda_per_capita_setor_2022_calibrada"}',
        '{"score": _num(r.get("score_setor_2022_calibrado"))}',
        # Variavel que passa pela conversao antes de ser servida.
        textwrap.dedent(
            """
            def f(df):
                renda = _renda_pc_canonica(df, "renda_per_capita")
                return {"renda_per_capita_media": float(renda.mean())}
            """
        ),
        # Contagem/mascara da renda crua nao e servir a renda.
        textwrap.dedent(
            """
            renda = _numeric(df, "renda_per_capita")
            x = {"n_renda": int(renda.notna().sum())}
            """
        ),
        # Insumo entregue por keyword a quem CONVERTE.
        'x = {"renda": renda_domiciliar_da_linha(renda=r.get("renda_responsavel_media_setor_2022"))}',
        # Intermediario de nome declarado cru nascendo de insumo (motor: V06004 pre-uplift).
        textwrap.dedent(
            """
            v = _numeric(s, "renda_responsavel_media_setor_2022")
            result["renda_media_domiciliar_raio"] = media(v)
            """
        ),
        # Fallback de entrada entre colunas de insumo do proprio frame.
        textwrap.dedent(
            """
            renda = _numeric(df, "renda_per_capita_setor_2022")
            df["renda_per_capita_setor_2022_calibrada"] = renda
            """
        ),
        # A mesma variavel em OUTRA funcao nao contamina esta.
        textwrap.dedent(
            """
            def a(df):
                renda = df["renda_leitura"]
                return renda.isna()

            def b(df):
                renda = _renda_per_capita_hex(df)
                return {"renda": renda}
            """
        ),
    ],
)
def test_r6_nao_pega_o_que_e_legitimo(trecho: str) -> None:
    assert _violacoes_superficie(trecho) == [], trecho


def test_a_lista_de_excecoes_continua_vazia() -> None:
    """Se a lista crescer, o ponto unico deixou de ser unico: decisao visivel num PR."""
    assert _EXCECOES == frozenset()


#: Todo consumidor de renda exibida (inventario da E0). Se um deles sair do universo, o fio
#: de alarme parou de olhar para ele.
_CONSUMIDORES = (
    "web/server/app.py",
    "src/motor_expansao/api/service.py",
    "src/motor_expansao/dashboard/censo_point.py",
    "src/motor_expansao/dashboard/censo_map.py",
    "src/motor_expansao/dashboard/censo_report.py",
    "src/motor_expansao/dashboard/relatorio_municipal.py",
    "src/motor_expansao/dashboard/relatorio_praca.py",
    "src/motor_expansao/dashboard/rede_export.py",
    "src/motor_expansao/dashboard/constants.py",
)


def test_o_universo_nao_esta_vazio_e_exclui_so_o_dono() -> None:
    """Um glob quebrado deixaria o teste principal verde varrendo nada."""
    rels = {rel for _, rel in _fontes()}
    faltando = [c for c in _CONSUMIDORES if c not in rels]
    assert not faltando, faltando
    assert len(rels) >= 150, len(rels)
    assert not any(r.startswith(_DONO) for r in rels)


def test_a_lista_de_ignorados_e_so_de_diretorio_gerado() -> None:
    """Igualdade EXATA: acrescentar "dashboard" aqui tiraria tres consumidores da varredura."""
    assert _IGNORAR == {"__pycache__", ".venv", "node_modules", "build", "dist"}
    assert _RAIZES == ("src", "web/server", "scripts")


@pytest.mark.parametrize(
    ("trecho", "regra"),
    [
        ("x = constants.FATOR_TEMPORAL_RENDA", "R1"),
        ("from motor_expansao.dashboard.constants import FATOR_TEMPORAL_RENDA", "R1"),
        ("f, ref = _const._carregar_fator_temporal()", "R1"),
        ("print(DATA_REFERENCIA_RENDA)", "R1"),
        ('d = {"fator_temporal_renda": 1.0}', "R1"),
        ('v = getattr(mod, "FATOR_TEMPORAL_RENDA")', "R1"),
        ('s = f"fator {FATOR_TEMPORAL_RENDA}"', "R1"),
        ("def f(fator_temporal_renda): pass", "R1"),
        ("g(fator_temporal_renda=1.0)", "R1"),
        ("total = renda * uplift", "R2"),
        ("total = renda * uplift_setor * fator", "R2"),
        ("total = renda * float(mod.uplift_composicao_por_setor(c, uf, cod)) * f", "R2"),
        ("base = valor / uplift", "R2"),
        ("x = (\n    renda\n    * UPLIFT_NACIONAL\n)", "R2"),
        ("renda *= uplift", "R2"),
        ("pc = dom / moradores_por_domicilio(uf, cod)", "R3"),
        ("pc = dom / mod.moradores_por_domicilio(uf, cod)", "R3"),
        # As duas linhas de antes da E0 (censo_point / censo_map): a per capita derivada da
        # domiciliar, que carregaria o F_dom e a queda de moradores.
        (
            "renda_per_capita_domiciliar = renda_domiciliar_total / moradores.where(moradores > 0)",
            "R3",
        ),
        ("pc = float(renda_domiciliar_total / moradores)", "R3"),
        ("pc = dom / MORADORES_DOMICILIO_NACIONAL", "R3"),
        ("pc = dom / insumos.moradores_nacional()", "R3"),
        ('pc = dom / row["avg_moradores_domicilio_setor_2022"]', "R3"),
        ("x = renda.div(moradores_por_domicilio(uf, c))", "R3"),
        # Formas equivalentes por chamada.
        ("x = renda.mul(uplift)", "R2"),
        ("x = np.multiply(renda, uplift)", "R2"),
        ("x = operator.mul(renda, uplift)", "R2"),
        # Aliases.
        ("u = uplift_setor(c)\nx = renda * u", "R2/R3"),
        ("fator_setor = _renda_insumos.uplift_setor(c, uf, m)\nx = renda * fator_setor", "R2/R3"),
        ("f = float(uplift_municipio(uf, m))\ng = f\nx = renda * g", "R2/R3"),
        ("m = moradores_por_domicilio(uf, c)\nx = np.divide(renda, m)", "R2/R3"),
        # A API nova do fator, fora do dono.
        ("total = v * _renda.fator(uf, 'domiciliar')", "R5"),
        ("from motor_expansao.renda.hex import fator_hex\nd = b * fator_hex(uf, c, 'dom')", "R5"),
        ("from motor_expansao.renda import fator", "R5"),
        ("d = b * _renda.fator_composto_domiciliar(u, uf)", "R5"),
        ("total = v * 1.1641", "R5"),
        ("total = v * 1.3401", "R5"),  # nacional per capita da PNAD 2025, copiado a mao
        ("total = v * 1.3461", "R5"),  # domiciliar de PE
        ("from motor_expansao.dashboard import renda_hex", "R4"),
        ("from motor_expansao.dashboard.renda_hex import renda_domiciliar_por_hex", "R4"),
        ("import motor_expansao.dashboard.renda_hex", "R4"),
    ],
)
def test_a_regra_pega_o_que_deve_pegar(trecho: str, regra: str) -> None:
    """Sem isto, uma regra quebrada deixaria o teste verde para sempre."""
    assert regra in {r for _, r, _ in _violacoes(trecho)}, trecho


@pytest.mark.parametrize(
    "trecho",
    [
        # Chamar o modulo, com o uplift como ARGUMENTO, e a forma certa.
        "total = renda_domiciliar(v, uplift_setor(c, uf, cod), uf)",
        "pc = _renda.renda_per_capita(v, _renda_insumos.uplift_setor(c), m, uf)",
        "f = round(_renda.fator_composto_domiciliar(uplift_efetivo, uf), 4)",
        "u = round(uplift_efetivo, 4)",
        # Alias de uplift passado como ARGUMENTO segue legitimo.
        "fs = uplift_setor(c)\nt = _renda.renda_domiciliar(v, fs, uf)\ny = t * 12",
        # Reconstrucao da V06004 pelo modulo.
        "v = _renda.v06004_de_fallback(v, pc_bruta, moradores)",
        # Contar moradores nao e dividir por eles.
        "n = len(moradores)",
        # Predicado de extrapolacao usado como MASCARA dentro de uma divisao.
        "e = pd.Series([uplift_extrapolado(c) for c in cods])\ny = p[e].sum() / p.sum()",
        # Funcao que so tem `uplift` no nome e devolve outra coisa (DataFrame).
        "df = derivar_uplift(raiz)\ny = df.x * 2",
        # Fracao de peso, nao fator de renda.
        "y = fracao_uplift_extrapolado_raio * 100",
        # Coluna por string: pipeline PRODUTOR do uplift, fora do escopo.
        'df["uplift_composicao"] = df["renda_dom"] / df["renda_resp"]',
        # Docstring e comentario nao sao codigo.
        'def f():\n    """Usa FATOR_TEMPORAL_RENDA x uplift."""\n    return 1',
        "x = 1  # FATOR_TEMPORAL_RENDA * uplift",
        # Nomes parecidos que NAO sao o fator temporal.
        "fator_temporal = 1.0",
        "data_referencia = rotulo",
        "from motor_expansao.renda import hex as renda_hex",
    ],
)
def test_a_regra_nao_pega_o_que_e_legitimo(trecho: str) -> None:
    assert _violacoes(trecho) == [], trecho


def test_produtor_fabrica_a_base_mas_nao_aplica_fator() -> None:
    """No pipeline produtor, fabricar V06004/per capita bruta com moradores e legitimo..."""
    fabricar = 'per_capita = (responsavel / moradores).where(moradores > 0)\nr = df["avg_moradores_x"] / 2'
    assert _violacoes(fabricar, produtor=True) == []
    # ...mas o fator temporal, o uplift como operando e o lookup do modulo continuam proibidos.
    for trecho, regra in [
        ("x = constants.FATOR_TEMPORAL_RENDA", "R1"),
        ("total = renda * uplift", "R2"),
        ("pc = dom / moradores_por_domicilio(uf, cod)", "R3"),
        ("total = v * _renda.fator(uf, 'domiciliar')", "R5"),
    ]:
        assert regra in {r for _, r, _ in _violacoes(trecho, produtor=True)}, trecho
    # E fora do produtor a mesma fabricacao e violacao (R3 ampla).
    assert "R3" in {r for _, r, _ in _violacoes(fabricar)}
