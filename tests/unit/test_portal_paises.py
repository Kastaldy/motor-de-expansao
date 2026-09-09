"""Asserts de CI do portal de seleção de país (BLK-INTL-13) — spec §7.4.1.

`docs/spec_portal_selecao_pais.md` §7.4 parte a verificação em DOIS artefatos, e o
motivo é o git: os asserts **7, 8, 11 e 12** (estes) leem SOMENTE arquivos rastreados
(`.dockerignore` e os dois `portal/*.html`, que nascem versionados neste bloco) e por
isso rodam no CI sem condição nenhuma. Os asserts 1-6, 9 e 10 leem `Caddyfile` e
`authelia/users_database.yml` — gitignored, inexistentes num checkout limpo — e vivem
em `scripts/aceite_portal_paises.sh`, rodado na VPS com a saída colada no PR (§7.4.2).

REGRA DE MANUTENÇÃO (spec §7.4.1, e é a única coisa que impede a regressão): este
arquivo NÃO PODE abrir `Caddyfile` nem nada sob `authelia/` — nem no corpo do teste,
nem em fixture, nem dentro de um `skipif`, nem num `Path(...).exists()` de guarda.
No dia em que abrir, o CI de todo mundo passa a depender de um arquivo que só existe
na VPS. O que precisar deles vai para o `scripts/aceite_portal_paises.sh`.

A numeração dos asserts é a ORIGINAL da spec e não muda (§7.4): o §0, o §2.3, o §3,
o §4.2 e o §5.4 citam asserts por número.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_DOCKERIGNORE = _REPO / ".dockerignore"
_INDEX = _REPO / "portal" / "index.html"
_SEM_ACESSO = _REPO / "portal" / "sem-acesso.html"

# Bloco de template Go POR PAÍS: `if` de UMA variável (`$br`, `$ar`, ...). Os blocos
# estruturais (`if or $br $ar`) não casam de propósito — eles não são "o if de um
# país" e o conteúdo deles fora dos ifs internos também não pode nomear país (§5.4).
_IF_PAIS_RE = re.compile(r"\{\{if \$\w+\}\}.*?\{\{end\}\}", re.DOTALL)

# `piloto-<pais>` concreto (o curinga documental `piloto-*` não casa — a proibição do
# §5.4 é sobre nome CONCRETO) e o host do primeiro país (`piloto.` + domínio).
_PAIS_OU_HOST_RE = re.compile(r"brasil|argentina|piloto-[a-z0-9]+|piloto\.", re.IGNORECASE)

_URL_RE = re.compile(r"https?://([A-Za-z0-9.-]+)")

# Pares seletor/declarações de CSS. Os blocos aninhados (`@media { :root { ... } }`)
# saem fragmentados, mas toda regra-folha (a única que pode carregar `display`) casa
# com o seu seletor imediato — que é o que o assert 11 precisa inspecionar.
_REGRA_CSS_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def test_assert_7_portal_no_dockerignore() -> None:
    """Assert 7 (§7.4.1): `portal/` está no `.dockerignore`.

    `Dockerfile.web` e `Dockerfile.api` fazem `COPY . .`: sem esta linha a página
    entra nas DUAS imagens de aplicação — exatamente o que a restrição "o portal
    não infla a imagem de país nenhum" proíbe (spec §5.2/§5.3). O defeito só
    apareceria meses depois, num `docker history`.
    """
    linhas = [
        linha.strip()
        for linha in _DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    ]
    assert "portal/" in linhas, "faltou a linha 'portal/' no .dockerignore (spec §5.3)"


def test_assert_8_index_nao_referencia_nada_fora_do_dominio() -> None:
    """Assert 8 (§7.4.1): nenhum `http://`/`https://` fora de `*.ultra-expansao.tech`.

    A CSP do bloco raiz é `default-src 'none'` (spec §2.3): qualquer asset externo
    seria bloqueado no ar — e é melhor falhar no CI que no ar (§5.4).
    """
    hosts = _URL_RE.findall(_INDEX.read_text(encoding="utf-8"))
    assert hosts, "esperava ao menos os links dos cartões de país no index.html"
    for host in hosts:
        assert host == "ultra-expansao.tech" or host.endswith(".ultra-expansao.tech"), (
            f"referência a host fora do domínio (a CSP bloquearia no ar): {host}"
        )


def test_assert_11_filtragem_e_de_renderizacao_nunca_de_css() -> None:
    """Assert 11 (§7.4.1): nenhuma das duas páginas esconde conteúdo de país por CSS.

    Nem `display:none` sobre `.pais`, nem seletor de classe sobre grupo
    (`[class*="expansao_"]`). Filtragem é de RENDERIZAÇÃO (spec §5.4): um cartão que
    o usuário não pode abrir NÃO É EMITIDO no corpo HTTP. Este assert é o que impede
    o vazamento do §6.2 de voltar como "só um display:none".
    """
    for pagina in (_INDEX, _SEM_ACESSO):
        texto = pagina.read_text(encoding="utf-8")
        for aspas in ('"', "'"):
            assert f"[class*={aspas}expansao_" not in texto, (
                f"{pagina.name}: seletor de classe sobre grupo — filtragem por CSS (§5.4)"
            )
        for seletor, corpo in _REGRA_CSS_RE.findall(texto):
            if re.search(r"display\s*:\s*none", corpo):
                assert ".pais" not in seletor and "expansao" not in seletor, (
                    f"{pagina.name}: display:none sobre conteúdo de país "
                    f"(seletor {seletor.strip()!r}) — filtragem por CSS (§5.4)"
                )


def test_assert_12_pais_so_dentro_do_if_do_proprio_pais() -> None:
    """Assert 12 (§7.4.1): nome de país e host `piloto-<pais>` só dentro dos ifs.

    Fora dos blocos `if` por país, `portal/index.html` não contém nome de país nem
    host de país; `portal/sem-acesso.html` não os contém em lugar NENHUM — comentário
    HTML incluído, porque ele viaja no corpo (spec §5.4). É a versão em CI dos
    aceites 6, 8 e 9 do §7.2 (o `grep` de lá não distingue comentário de conteúdo).
    """
    index = _INDEX.read_text(encoding="utf-8")
    blocos = _IF_PAIS_RE.findall(index)
    assert len(blocos) >= 2, (
        "esperava ao menos dois blocos '{{if $<pais>}}...{{end}}' no index.html — "
        "sem eles o assert passaria vazio sobre uma página quebrada"
    )
    fora_dos_ifs = _IF_PAIS_RE.sub("", index)
    vazou = _PAIS_OU_HOST_RE.search(fora_dos_ifs)
    assert vazou is None, (
        f"index.html vaza {vazou.group(0)!r} fora do if do próprio país (§5.4): "
        "o corpo HTTP diria quais países existem a quem não os tem"
    )

    sem_acesso = _SEM_ACESSO.read_text(encoding="utf-8")
    vazou = _PAIS_OU_HOST_RE.search(sem_acesso)
    assert vazou is None, (
        f"sem-acesso.html contém {vazou.group(0)!r}: a página de quem não tem país "
        "nenhum não pode nomear país nenhum (§5.4; aceite 8 do §7.2)"
    )
    # Espelho exato do grep do aceite 8 (§7.2): `grep -ci 'brasil\|argentina\|piloto'`
    # tem de dar 0 — inclusive `piloto` sem sufixo.
    assert re.search(r"piloto", sem_acesso, re.IGNORECASE) is None, (
        "sem-acesso.html contém 'piloto' — o grep do aceite 8 do §7.2 reprovaria"
    )


_IF_PAIS_CAPTURA_RE = re.compile(r"\{\{if \$(\w+)\}\}(.*?)\{\{end\}\}", re.DOTALL)

# O que o cartao de cada pais NAO pode conter: o nome/host DO OUTRO. Achado da
# revisao adversarial do PR #313: o assert 12 tratava qualquer `if` como zona segura
# para qualquer pais — "Argentina" dentro do `{{if $br}}` passava verde, e o corpo
# HTTP diria a um usuario so-BR quais outros paises existem (a classe de vazamento
# que o §6.2 fecha). Ao entrar o 3o pais, acrescentar a linha dele aqui.
_PROIBIDO_NO_BLOCO = {
    "br": re.compile(r"argentina|piloto-ar", re.IGNORECASE),
    "ar": re.compile(r"brasil|piloto\.ultra", re.IGNORECASE),
}


def test_assert_12b_cartao_de_um_pais_nao_cita_o_outro() -> None:
    """Complemento do assert 12: DENTRO do `if` de um pais, so aquele pais.

    A regra de ouro do proprio index.html: o nome entra APENAS dentro do `if`
    DAQUELE pais. Sem esta checagem, colar o cartao novo dentro do `if` errado
    passaria no CI e so seria pego pelo aceite manual §7.2 item 6, na VPS.
    """
    index = _INDEX.read_text(encoding="utf-8")
    blocos = _IF_PAIS_CAPTURA_RE.findall(index)
    assert blocos, "nenhum bloco '{{if $<pais>}}' capturado — regex ou pagina mudou"
    for var, corpo in blocos:
        proibido = _PROIBIDO_NO_BLOCO.get(var)
        if proibido is None:
            continue
        vazou = proibido.search(corpo)
        assert vazou is None, (
            f"index.html: bloco '{{{{if ${var}}}}}' cita o OUTRO pais "
            f"({vazou.group(0)!r}) — cartao no if errado vaza a lista de paises (§6.2)"
        )


def test_assert_11b_sem_display_none_inline() -> None:
    """Complemento do assert 11: `style=` inline com display:none tambem e proibido.

    O assert 11 varre corpos de regra CSS; um atributo inline escaparia. Nas duas
    paginas do portal nao ha uso legitimo de display:none inline — presenca e
    sinal de filtragem por CSS (§5.4), que e exatamente o que o assert existe
    para impedir.
    """
    for pagina in (_INDEX, _SEM_ACESSO):
        texto = pagina.read_text(encoding="utf-8")
        m = re.search(r"style=\"[^\"]*display\s*:\s*none", texto)
        assert m is None, f"{pagina.name}: display:none inline ({m.group(0)!r})"
