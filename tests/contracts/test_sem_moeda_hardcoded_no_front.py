"""Bloco A / commit A10 — o símbolo de moeda não volta para `web/src/lib/**`.

O A9 tirou o `R$` dos formatadores. Sem uma guarda, o próximo módulo de formatação o
reintroduz e nada acusa — e o defeito não aparece no Brasil, só numa instância que serve
outra moeda, meses depois, na tela de outra pessoa.

Três decisões deste arquivo, todas MEDIDAS
------------------------------------------
**1. É teste de contrato, não regra de ESLint.** Não há ESLint neste projeto: o
`web/package.json` não traz `eslint` em `devDependencies` e define `"lint": "tsc
--noEmit"`; não existe `eslint.config.*` nem `.eslintrc*` em lugar nenhum. Escrever a
guarda como regra de lint significaria introduzir ESLint + `typescript-eslint` + um passo
de CI — dependência e frente novas, num commit cujo papel é fechar uma porta.

**2. O escopo é `web/src/lib/**`, não `web/src/**`.** Medido: fora de `*.test.*` e fora
de comentário, `web/src` tem 63 ocorrências de `R$` em 15 arquivos. A maioria vive em
`ViabilityScreen.tsx` — os `prefixo="R$"` das caixas e os `title` que explicam a unidade
—, e convertê-los **contrariaria a decisão 0.6**: a viabilidade argentina sobe em REAIS,
com tributo brasileiro, como provisório declarado. Um símbolo parametrizado ali escreveria
"$" numa tela cujos números continuam sendo reais: pior que o provisório assumido, porque
some com o único sinal de que são reais. Saem com o BLK-INTL-11, não antes.

*Emenda de 2026-10-29 (achado a-03 da conferência da higiene dos docs).* Sem guarda nenhuma
fora de `lib`, o "R$" cravado sobre RENDA ficou em telas que a Argentina abre — a ficha do
ponto, o detalhe da região e a recomendação escreviam "R$" sobre renda em DÓLAR (defeito S4
de `docs/expansao-latam/00-baseline-argentina.md`). Fora de `lib` passa a valer uma SEGUNDA
guarda, com lista declarada e catraca (`_R_FORA_DE_LIB`, no fim deste arquivo); a de `lib`
segue de tolerância zero.

**3. Um seletor só de literal de string não serviria.** Das 11 ocorrências que havia em
`web/src/lib`, apenas 3 eram `Literal` de string; as seis de `brl`/`brlCurto` eram
TEMPLATE literal — exatamente os sítios que este bloco existe para mover. Por isso a
varredura é textual, sobre a linha sem comentário.

Spec: `docs/spec_bloco_a_perfil.md` §2.7 e §5.9 item 6.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_LIB = _REPO / "web" / "src" / "lib"

#: Vazia, e é essa a graça. O A9 moveu as 11 ocorrências que havia aqui — inclusive a de
#: `recomendacao.ts`, que a primeira passada do A9 deixou para trás e esta guarda pegou.
_ALLOWLIST: frozenset[str] = frozenset()

_MOEDA = re.compile(r"R\$")


def _linhas_de_codigo(texto: str) -> list[tuple[int, str]]:
    """Linhas fora de comentário — de linha (`//`) e de bloco (`/* ... */`).

    Separar código de comentário é trabalho de parser, não de `grep`: `web/src/lib` cita
    `R$` legitimamente em comentário de `imovel.ts`, `mascara.ts`, `sparkline.ts`,
    `types.ts`, `exec.ts` e `report.ts`. Um `grep` cru acusaria os seis.
    """
    fora: list[tuple[int, str]] = []
    em_bloco = False
    for n, bruta in enumerate(texto.splitlines(), 1):
        linha = bruta
        if em_bloco:
            fim = linha.find("*/")
            if fim < 0:
                continue
            linha = linha[fim + 2 :]
            em_bloco = False
        # blocos abertos e fechados na mesma linha
        while "/*" in linha:
            ini = linha.find("/*")
            fim = linha.find("*/", ini + 2)
            if fim < 0:
                linha = linha[:ini]
                em_bloco = True
                break
            linha = linha[:ini] + linha[fim + 2 :]
        corte = linha.find("//")
        if corte >= 0:
            linha = linha[:corte]
        if linha.strip():
            fora.append((n, linha))
    return fora


#: Fora do ESCOPO, e isto não é uma exceção tolerada — é uma categoria diferente.
#: `perfil-br.ts` é o perfil brasileiro COMPILADO: `"simbolo": "R$"` ali é o DADO, o
#: lugar onde o símbolo deve estar. O que esta guarda persegue é símbolo cravado em
#: código que FORMATA dinheiro. E o arquivo já tem guarda própria e mais forte:
#: `test_perfil_front_espelha_o_python.py` prova, campo a campo, que ele bate com o
#: `data/perfis/BR/perfil.json`.
_FORA_DO_ESCOPO = frozenset({"perfil-br.ts"})


def _fontes() -> list[Path]:
    return [
        p
        for p in sorted(_LIB.rglob("*.ts"))
        if p.is_file()
        and ".test." not in p.name
        and ".d." not in p.name
        and p.name not in _FORA_DO_ESCOPO
    ]


def test_o_escopo_nao_esta_vazio() -> None:
    """Se um refactor mover `lib/` de lugar, a varredura passaria a olhar para o nada e
    ficaria verde para sempre. Um guarda que não vê arquivo nenhum não é um guarda."""
    assert _LIB.is_dir(), f"{_LIB} nao existe"
    assert len(_fontes()) >= 20, "web/src/lib com menos arquivos que o esperado"


def test_sem_simbolo_de_moeda_cravado_em_web_src_lib() -> None:
    ocorrencias: list[str] = []
    for arquivo in _fontes():
        rel = arquivo.relative_to(_REPO).as_posix()
        if rel in _ALLOWLIST:
            continue
        for n, linha in _linhas_de_codigo(arquivo.read_text(encoding="utf-8")):
            if _MOEDA.search(linha):
                ocorrencias.append(f"{rel}:{n}: {linha.strip()}")

    assert not ocorrencias, (
        "Simbolo de moeda cravado em `web/src/lib`. Use `moeda()` de `lib/perfil.ts` —\n"
        "numa instancia que serve outra moeda, o literal escreve o simbolo errado e\n"
        "nenhum teste brasileiro percebe.\n\nAchado em:\n  " + "\n  ".join(ocorrencias)
    )


def test_a_allowlist_continua_vazia() -> None:
    """Nasceu vazia porque o A9 moveu tudo. Enchê-la tem de ser decisão visível num PR,
    e não o caminho mais curto para fazer o teste passar."""
    assert _ALLOWLIST == frozenset()


def test_o_unico_arquivo_fora_do_escopo_e_o_perfil_compilado() -> None:
    """`perfil-br.ts` é DADO, não código de formatação — e tem guarda própria e mais
    forte no `test_perfil_front_espelha_o_python.py`. Qualquer outro nome entrando aqui
    é uma violação disfarçada de escopo."""
    assert _FORA_DO_ESCOPO == frozenset({"perfil-br.ts"})
    assert (_LIB / "perfil-br.ts").is_file(), "o arquivo excluido tem de existir"


@pytest.mark.parametrize(
    ("fonte", "espera"),
    [
        ("const a = `R$ ${v}`", True),  # template literal — o sitio que mais importa
        ("const a = 'R$'", True),  # literal de string
        ("// custo em R$ por m2", False),  # comentario de linha
        ("/* R$ aqui */ const a = 1", False),  # bloco fechado na mesma linha
        ("const a = 1 /* R$ */", False),
    ],
)
def test_a_varredura_separa_codigo_de_comentario(fonte: str, espera: bool) -> None:
    """Sem estes casos, um bug no separador deixaria a guarda verde para sempre."""
    achou = any(_MOEDA.search(linha) for _, linha in _linhas_de_codigo(fonte))
    assert achou is espera, fonte


def test_bloco_de_varias_linhas_e_ignorado_ate_o_fim() -> None:
    fonte = "/*\n * R$ no meio de um bloco\n */\nconst a = 1\n"
    assert not any(_MOEDA.search(linha) for _, linha in _linhas_de_codigo(fonte))


# ----------------------------------------------------------------------------------------
# Fora de `web/src/lib`: telas, componentes e o resto de `web/src` (emenda de 2026-10-29)
# ----------------------------------------------------------------------------------------
_SRC = _REPO / "web" / "src"

#: arquivo (relativo a `web/src`) -> (linhas com "R$" em código, superfície que tem de seguir
#: FECHADA fora do Brasil ou `None`, motivo). A contagem foi medida em 2026-10-29 e é CATRACA
#: nos dois sentidos: uma linha NOVA num arquivo listado reprova como num arquivo de fora, e
#: uma que SAI pede para baixar o número. Assim a lista encolhe junto com o BLK-INTL-11 em vez
#: de virar licença.
_R_FORA_DE_LIB: dict[str, tuple[int, str | None, str]] = {
    "screens/ViabilityScreen.tsx": (
        8, None, "decisão 0.6: a viabilidade sobe em REAIS fora do Brasil até o BLK-INTL-11",
    ),
    "components/ViabilityCharts.tsx": (1, None, "decisão 0.6, como a ViabilityScreen"),
    "components/ViabilityNotes.tsx": (
        1, None, "decisão 0.6; e o adicional do IRPJ (R$ 20 mil/mês) é lei brasileira",
    ),
    "screens/OportunidadesImobiliariasScreen.tsx": (
        16, "imobiliaria",
        "anúncios do coletor de imóveis (aluguel, R$/m²) e renda do território, tudo do Brasil",
    ),
    "components/FichaImovel.tsx": (
        7, None,
        "ficha do imóvel do coletor brasileiro; abre também pelo pin do Mapa, mas o pin só "
        "existe onde há o artefato de imóveis",
    ),
    "components/HexMap.tsx": (
        1, None, "dica do pin de IMÓVEL (R$/m²): o pin só existe onde há o artefato de imóveis",
    ),
    "components/exec/FichaMapa.tsx": (
        3, "executiva", "Visão Executiva: renda do censo brasileiro e preço de plano em reais",
    ),
}


def _fontes_fora_de_lib() -> list[Path]:
    return [
        p
        for p in sorted(_SRC.rglob("*"))
        if p.is_file()
        and p.suffix in (".ts", ".tsx")
        and not p.relative_to(_SRC).as_posix().startswith("lib/")
        and ".test." not in p.name
        and ".d." not in p.name
    ]


def _linhas_com_moeda(arquivo: Path) -> list[str]:
    return [
        f"{n}: {linha.strip()}"
        for n, linha in _linhas_de_codigo(arquivo.read_text(encoding="utf-8"))
        if _MOEDA.search(linha)
    ]


def test_o_escopo_fora_de_lib_nao_esta_vazio() -> None:
    fontes = _fontes_fora_de_lib()
    assert len(fontes) >= 50, "web/src fora de lib com menos arquivos que o esperado"
    assert any(p.suffix == ".tsx" for p in fontes), "a varredura deixou de ver .tsx"


def test_sem_moeda_cravada_fora_de_lib_alem_do_declarado() -> None:
    novos: list[str] = []
    contagem_mudou: list[str] = []
    for arquivo in _fontes_fora_de_lib():
        rel = arquivo.relative_to(_SRC).as_posix()
        linhas = _linhas_com_moeda(arquivo)
        if rel not in _R_FORA_DE_LIB:
            novos.extend(f"web/src/{rel}:{linha}" for linha in linhas)
        elif len(linhas) != _R_FORA_DE_LIB[rel][0]:
            contagem_mudou.append(
                f"web/src/{rel}: {len(linhas)} linhas, a lista declara {_R_FORA_DE_LIB[rel][0]}"
            )
    assert not novos, (
        "Símbolo de moeda cravado fora de `web/src/lib`. Renda sai por `renda()`/`moedaRenda()`\n"
        "e dinheiro na moeda oficial por `brl()`/`moeda()`: numa instância que serve outra\n"
        "moeda, o literal escreve o símbolo errado e nenhum teste brasileiro percebe.\n\n"
        "Achado em:\n  " + "\n  ".join(novos)
    )
    assert not contagem_mudou, (
        "A contagem de `R$` mudou num arquivo declarado. Se SUBIU, a linha nova precisa de\n"
        "`moeda()`/`moedaRenda()` ou de decisão visível aqui; se DESCEU, baixe o número em\n"
        "`_R_FORA_DE_LIB` (ou tire o arquivo, se zerou).\n\n  " + "\n  ".join(contagem_mudou)
    )


def test_todo_arquivo_declarado_existe() -> None:
    """Arquivo renomeado ou apagado deixaria uma entrada morta, e a catraca não veria o novo."""
    faltando = [rel for rel in _R_FORA_DE_LIB if not (_SRC / rel).is_file()]
    assert not faltando, f"Entradas de `_R_FORA_DE_LIB` sem arquivo: {faltando}"


def test_superficie_so_do_brasil_segue_fechada_nos_outros_paises() -> None:
    """Parte da lista se justifica porque a superfície só abre no Brasil. Se ela abrir noutro
    país, o "R$" desses arquivos passa a aparecer lá sobre dado que não é em reais, e o motivo
    deixa de valer sem nenhum outro teste ficar vermelho."""
    abertas: list[str] = []
    perfis = sorted((_REPO / "data" / "perfis").glob("*/perfil.json"))
    assert len(perfis) >= 2, "a varredura de perfis não achou os perfis do repositório"
    for perfil in perfis:
        dados = json.loads(perfil.read_text(encoding="utf-8"))
        if dados["pais"] == "BR":
            continue
        superficies = set(dados["superficies"])
        for rel, (_, superficie, _) in _R_FORA_DE_LIB.items():
            if superficie is not None and superficie in superficies:
                abertas.append(f"{dados['pais']}: `{superficie}` abriu e web/src/{rel} escreve R$")
    assert not abertas, "\n".join(abertas)


def test_as_telas_do_a03_nao_entram_na_lista() -> None:
    """As telas que a Argentina abre e que escreviam "R$" sobre renda em dólar não podem
    entrar na lista: seria o caminho mais curto para fazer a guarda passar."""
    for rel in (
        "screens/PontoScreen.tsx",
        "components/DetalheRegiao.tsx",
        "components/Recomendacao.tsx",
        "components/TabelaRanking.tsx",
    ):
        assert rel not in _R_FORA_DE_LIB, rel
