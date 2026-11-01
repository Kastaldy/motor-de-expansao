"""Asserts de CI do portal de selecao de pais do apex (DEC-081).

O portal deixou de ser um template de texto estatico (`portal/index.html` +
`portal/sem-acesso.html`, APOSENTADOS) e passou a ser uma tela React servida na raiz do
apex: `web/src/portal.tsx` (orquestrador login/selecao/sem-acesso) + `web/src/screens/
SelecaoPais.tsx` (os cartoes) + `web/portal.html` (o entry). Estes asserts leem SOMENTE
esses arquivos RASTREADOS novos e por isso rodam no CI sem condicao nenhuma.

REGRA DE MANUTENCAO (e e a unica coisa que impede a regressao): este arquivo NAO PODE
abrir `Caddyfile` nem nada sob `authelia/` -- nem no corpo do teste, nem em fixture, nem
dentro de um `skipif`, nem num `Path(...).exists()` de guarda. No dia em que abrir, o CI
de todo mundo passa a depender de um arquivo que so existe na VPS. O que precisar deles
(a borda, os grupos) vai para o `scripts/aceite_portal_paises.sh`, rodado na VPS com a
saida colada no PR -- nao e deste arquivo.

O QUE CADA ASSERT GUARDA
------------------------
(a) nenhum literal de pais em ramo de codigo (`=== 'BR'`/`=== "AR"`/ternario/`case`): o
    pais e' uma ENTRADA na tabela `PAISES`, nunca um galho de `if`. E' o fio de alarme da
    DEC-047 em CI -- o mesmo que o teste de contrato do backend impoe no Python.
(b) nenhuma mencao ao autenticador aposentado (nem em comentario, que viaja no arquivo).
(c) os dois hosts de pais (`piloto.` e `piloto-ar.`) presentes -- sem eles os cartoes
    apontariam para o vazio.
(d) os cartoes sao <a> de verdade (link), nunca <div onClick>: teclado, "abrir em nova
    aba" e leitor de tela dependem disso.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PORTAL_TSX = _REPO / "web" / "src" / "portal.tsx"
_SELECAO_TSX = _REPO / "web" / "src" / "screens" / "SelecaoPais.tsx"
_PORTAL_HTML = _REPO / "web" / "portal.html"

# Os dois hosts de pais que os cartoes precisam carregar (SEM esquema -- o `href` monta
# `https://<host>/`). Ao entrar um terceiro pais, some o host dele aqui.
_HOST_BR = "piloto.ultra-expansao.tech"
_HOST_AR = "piloto-ar.ultra-expansao.tech"

# Literal de pais num RAMO de codigo. Cobre `=== 'BR'`, `=== "AR"` (e `!==`), os dois
# sentidos, e `case 'BR':`. A tabela usa as siglas como CHAVE sem aspas (`BR:`), que nao
# casa; `'Brasil'`/`'Argentina'` tambem nao (o conteudo nao e a sigla).
_LITERAL_DE_PAIS_EM_CONDICIONAL = re.compile(
    r"""(===|!==)\s*['"](BR|AR)['"]"""
    r"""|['"](BR|AR)['"]\s*(===|!==)"""
    r"""|case\s+['"](BR|AR)['"]"""
)


def _sem_comentarios(texto: str) -> str:
    """Remove comentarios de bloco e de LINHA INTEIRA.

    So' a linha-comentario que comeca a linha (`^\\s*//`) e' removida -- um `//` no meio
    de uma linha faz parte de `https://`, e apaga-lo mutilaria os hosts dos cartoes.
    """
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
    texto = re.sub(r"^\s*//.*$", "", texto, flags=re.MULTILINE)
    return texto


def test_sem_literal_de_pais_em_condicional() -> None:
    """(a) O pais e' chave de tabela, nunca condicao -- fio de alarme da DEC-047.

    Varre `portal.tsx` + `SelecaoPais.tsx` SEM comentarios (a propria prosa que explica a
    regra citaria o padrao proibido). Um `=== 'BR'` aqui seria o pais virando caminho de
    execucao no codigo da plataforma, exatamente o que a DEC-047 recusou.
    """
    codigo = _sem_comentarios(_PORTAL_TSX.read_text(encoding="utf-8"))
    codigo += "\n" + _sem_comentarios(_SELECAO_TSX.read_text(encoding="utf-8"))
    achado = _LITERAL_DE_PAIS_EM_CONDICIONAL.search(codigo)
    assert achado is None, (
        f"literal de pais em ramo de codigo ({achado.group(0)!r}): use a tabela PAISES, "
        "nao um `if`/ternario por sigla (DEC-047)"
    )


def test_sem_mencao_ao_authelia() -> None:
    """(b) Nenhum arquivo do apex cita o autenticador aposentado.

    Comentario tambem conta: ele viaja no arquivo e envelhece a documentacao. O corte da
    DEC-081 aposentou o autenticador externo; o portal novo nao fala dele em lugar nenhum.
    """
    for caminho in (_PORTAL_TSX, _SELECAO_TSX, _PORTAL_HTML):
        texto = caminho.read_text(encoding="utf-8")
        assert not re.search(r"authelia", texto, re.IGNORECASE), (
            f"{caminho.name} cita o autenticador aposentado (DEC-081 o removeu)"
        )


def test_os_dois_hosts_presentes() -> None:
    """(c) Os dois hosts de pais existem nos arquivos rastreados.

    Sem eles, os cartoes do portal apontariam para o vazio. Eles vivem na tabela PAISES
    de `SelecaoPais.tsx`; a busca varre os tres arquivos para nao presumir em qual estao.
    """
    rastreado = (
        _PORTAL_TSX.read_text(encoding="utf-8")
        + _SELECAO_TSX.read_text(encoding="utf-8")
        + _PORTAL_HTML.read_text(encoding="utf-8")
    )
    assert _HOST_BR in rastreado, f"host do Brasil ausente ({_HOST_BR})"
    assert _HOST_AR in rastreado, f"host da Argentina ausente ({_HOST_AR})"


def test_cartoes_sao_links_de_verdade() -> None:
    """(d) Os cartoes de pais sao <a> com href, nunca <div onClick>.

    Link de verdade e' o que faz o teclado alcancar, o "abrir em nova aba" funcionar e o
    leitor de tela anunciar como link. Um `<div onClick>` quebraria os tres em silencio.
    """
    selecao = _SELECAO_TSX.read_text(encoding="utf-8")
    assert re.search(r"<a\b[^>]*href=", selecao, re.DOTALL), (
        "nenhum <a href=...> em SelecaoPais.tsx -- os cartoes precisam ser links"
    )
    # Sem comentarios: a propria explicacao de "nunca <div onClick>" cita o padrao.
    assert "onClick" not in _sem_comentarios(selecao), (
        "SelecaoPais.tsx tem onClick -- cartao de pais e' <a href>, nunca <div onClick>"
    )
