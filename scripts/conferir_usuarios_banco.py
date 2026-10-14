"""Confere, pessoa a pessoa, se quem acessa o piloto hoje está no banco — e com as mesmas abas.

Ferramenta do corte do banco (`docs/banco_deploy.md`, "Conferir antes de ligar"). Só LÊ: não
grava em lugar nenhum e nunca imprime senha, hash nem e-mail. Só biblioteca padrão e nada além
do Python 3.10, porque roda no `python3` do HOST da VPS, fora dos containers.

Três fontes, casadas pelo login sem diferenciar maiúscula (como a coluna CITEXT do banco):

  1. Authelia (`users_database.yml`) -> quem consegue ENTRAR hoje. Só as CHAVES de `users:`
     são lidas; o resto do arquivo (hash, e-mail) é ignorado linha a linha.
  2. JSON (`acesso_abas.json`)        -> que abas cada um vê HOJE, antes do banco. Mesma leitura
     de `web/server/acesso.py::_ler_mapa`: chave `_*` é comentário, `*` é o default de quem está
     fora da lista (e não uma pessoa), aba desconhecida sai.
  3. Banco (tabela `usuarios`)        -> quem o piloto reconhece DEPOIS de ligar o banco. As
     linhas chegam pela entrada padrão no formato `login|perfil|ativo(t/f)|aba1,aba2,...`, que é
     o que a consulta de `--sql` produz com `psql -At -F '|'`.

O de-para capacidade -> aba é o `CAPACIDADE_QUE_SUSTENTA_A_ABA` de `web/server/acesso.py`,
replicado em `CAPACIDADE_POR_ABA` (o script não importa o servidor: roda sem o repo instalado).
`tests/unit/test_conferir_usuarios_banco.py` trava a igualdade dos dois.

Uso:
    python3 conferir_usuarios_banco.py --sql          # imprime a consulta do banco
    <linhas do banco> | python3 conferir_usuarios_banco.py USERS_YML ACESSO_ABAS_JSON \\
        [--aceitar login:+aba,-aba ...]

`--aceitar` declara uma mudança de abas JÁ DECIDIDA (ex.: `--aceitar fulano_teste:+oportunidades`):
ela aparece como ACEITA e não conta como pendência. Só vale se a mudança real for EXATAMENTE a
declarada; qualquer outra (ou nenhuma) vira pendência.

Código de saída: 0 = tudo casa; 1 = há pendência; 2 = erro de uso ou de entrada.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TextIO

#: Espelho de `web/server/acesso.py::CAPACIDADE_QUE_SUSTENTA_A_ABA` (aba -> capacidade).
CAPACIDADE_POR_ABA: dict[str, str] = {
    "mapa": "territorio.explorar",
    "oportunidades": "territorio.ranking_nacional",
    "imobiliaria": "imovel.dossie_ver",
    "viabilidade": "viabilidade.simular",
    "executiva": "rede.ver",
}

#: Espelho de `web/server/acesso.py::ABAS_SENSIVEIS`: o curinga `*` nunca as concede.
ABAS_SENSIVEIS: frozenset[str] = frozenset({"executiva", "imobiliaria", "viabilidade"})

ABAS: tuple[str, ...] = tuple(CAPACIDADE_POR_ABA)

_LARGURA = 140


def sql_da_consulta() -> str:
    """A consulta que lista cada usuário do banco com as abas que as capacidades dele sustentam."""
    valores = ",\n                  ".join(
        f"('{capacidade}','{aba}')" for aba, capacidade in CAPACIDADE_POR_ABA.items()
    )
    return (
        "SELECT u.login_usuario, p.nome_perfil, u.ativo,\n"
        "       coalesce(string_agg(DISTINCT m.aba, ',' ORDER BY m.aba), '')\n"
        "FROM usuarios u JOIN perfis p USING (id_perfil)\n"
        "LEFT JOIN perfil_permissoes pp USING (id_perfil)\n"
        "LEFT JOIN permissoes pe USING (id_permissao)\n"
        f"LEFT JOIN (VALUES {valores}) AS m(chave, aba) ON m.chave = pe.chave\n"
        "GROUP BY 1, 2, 3 ORDER BY 1;"
    )


class EntradaInvalida(ValueError):
    """Entrada que o conferidor não sabe ler — código de saída 2, nunca um veredito."""


def logins_do_authelia(linhas: Iterable[str]) -> set[str]:
    """Só as CHAVES de `users:` (dois espaços de recuo). Nenhum valor do arquivo é guardado."""
    logins: set[str] = set()
    dentro = False
    for linha in linhas:
        if re.match(r"^users:\s*$", linha):
            dentro = True
            continue
        if dentro and re.match(r"^\S", linha):
            break
        m = re.match(r"^  ([^\s#][^:]*):\s*$", linha)
        if dentro and m:
            logins.add(m.group(1).strip().strip("'\""))
    return logins


def mapa_do_json(texto: str) -> tuple[dict[str, frozenset[str]], frozenset[str]]:
    """(pessoas -> abas, abas do curinga `*`), lidas como `_ler_mapa` lê.

    O que faria o piloto DESLIGAR o controle (raiz que não é objeto, abas que não são lista) é
    erro de entrada aqui: comparar contra um mapa que o piloto não usa daria veredito falso.
    """
    try:
        bruto = json.loads(texto)
    except ValueError as erro:
        raise EntradaInvalida(f"acesso_abas.json não é JSON válido: {erro}") from erro
    if not isinstance(bruto, dict):
        raise EntradaInvalida("a raiz do acesso_abas.json deve ser um objeto usuario -> [abas]")
    pessoas: dict[str, frozenset[str]] = {}
    curinga: frozenset[str] = frozenset()
    for usuario, abas in bruto.items():
        if usuario.startswith("_"):
            continue  # comentário
        if not isinstance(abas, list):
            raise EntradaInvalida(f"as abas de {usuario!r} no acesso_abas.json devem ser lista")
        validas = frozenset(a for a in abas if a in ABAS)
        if usuario == "*":
            # Default de quem está fora da lista, não uma pessoa. Nunca concede aba sensível.
            curinga = validas - ABAS_SENSIVEIS
        else:
            pessoas[usuario] = validas
    return pessoas, curinga


def linhas_do_banco(texto: str) -> dict[str, tuple[str, bool, frozenset[str]]]:
    """`login|perfil|ativo|abas` -> {login: (perfil, ativo, abas)}."""
    banco: dict[str, tuple[str, bool, frozenset[str]]] = {}
    for n, linha in enumerate(texto.splitlines(), start=1):
        if not linha.strip():
            continue
        partes = linha.split("|")
        if len(partes) != 4 or partes[2] not in ("t", "f"):
            raise EntradaInvalida(
                f"linha {n} do banco fora do formato login|perfil|ativo(t/f)|abas "
                "(a entrada veio da consulta de --sql com psql -At -F '|'?)"
            )
        login, perfil, ativo, abas = partes
        banco[login] = (perfil, ativo == "t", frozenset(a for a in abas.split(",") if a))
    return banco


def ler_aceitas(itens: Iterable[str]) -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """`login:+aba,-aba` -> {login casefold: (ganha, perde)}."""
    aceitas: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    for item in itens:
        login, _, mudancas = item.partition(":")
        partes = [m.strip() for m in mudancas.split(",") if m.strip()]
        if (
            not login.strip()
            or not partes
            or any(m[0] not in "+-" or m[1:] not in ABAS for m in partes)
        ):
            raise EntradaInvalida(f"--aceitar inválido: {item!r} (formato login:+aba,-aba)")
        ganha = frozenset(m[1:] for m in partes if m[0] == "+")
        perde = frozenset(m[1:] for m in partes if m[0] == "-")
        if ganha & perde:
            raise EntradaInvalida(f"--aceitar inválido: {item!r} ganha e perde a mesma aba")
        aceitas[login.strip().casefold()] = (ganha, perde)
    return aceitas


@dataclass(frozen=True)
class Linha:
    login: str
    no_authelia: bool
    banco: str
    abas_hoje: str
    problemas: tuple[str, ...]
    avisos: tuple[str, ...]

    @property
    def situacao(self) -> str:
        return " | ".join(self.problemas + self.avisos) or "ok"


def _abas_texto(abas: frozenset[str]) -> str:
    return ",".join(sorted(abas)) or "(nenhuma)"


def conferir(
    authelia: set[str],
    json_pessoas: dict[str, frozenset[str]],
    json_curinga: frozenset[str],
    banco: dict[str, tuple[str, bool, frozenset[str]]],
    aceitas: dict[str, tuple[frozenset[str], frozenset[str]]],
) -> list[Linha]:
    """Uma `Linha` por pessoa que aparece em qualquer fonte (ou num `--aceitar`)."""
    k_authelia = {n.casefold() for n in authelia}
    k_json = {n.casefold(): v for n, v in json_pessoas.items()}
    k_banco = {n.casefold(): v for n, v in banco.items()}

    exibicao: dict[str, str] = {}
    for fonte in (authelia, json_pessoas, banco):
        for login in fonte:
            exibicao.setdefault(login.casefold(), login)
    for k in aceitas:
        exibicao.setdefault(k, k)

    resultado: list[Linha] = []
    for k in sorted(exibicao):
        no_authelia = k in k_authelia
        no_banco = k in k_banco
        abas_hoje: frozenset[str] | None
        if k in k_json:
            abas_hoje = k_json[k]
            col_hoje = _abas_texto(abas_hoje)
        elif no_authelia:
            # Fora da lista, quem entra recebe o curinga — o mesmo ramo de `abas_do_usuario`.
            abas_hoje = json_curinga
            col_hoje = _abas_texto(abas_hoje) + " (*)"
        else:
            abas_hoje, col_hoje = None, "—"

        if no_banco:
            perfil, ativo, abas_banco = k_banco[k]
            col_banco = perfil if ativo else f"{perfil} (INATIVO)"
        else:
            ativo, abas_banco = False, frozenset()
            col_banco = "—"

        problemas: list[str] = []
        avisos: list[str] = []
        if no_authelia and not no_banco:
            problemas.append("FALTA NO BANCO: entra hoje e perde tudo ao ligar o banco")
        if no_banco and ativo and not no_authelia:
            problemas.append("falta no Authelia: está no banco mas não consegue entrar")
        if no_banco and not ativo:
            if no_authelia:
                problemas.append("inativo no banco: entra hoje e perde tudo ao ligar")
            else:
                avisos.append("inativo e fora do Authelia (coerente)")
        mudanca_real: tuple[frozenset[str], frozenset[str]] | None = None
        if no_banco and ativo and abas_hoje is not None and abas_banco != abas_hoje:
            ganha = abas_banco - abas_hoje
            perde = abas_hoje - abas_banco
            mudanca_real = (ganha, perde)
            partes = []
            if ganha:
                partes.append("ganha " + ",".join(sorted(ganha)))
            if perde:
                partes.append("PERDE " + ",".join(sorted(perde)))
            if aceitas.get(k) == mudanca_real:
                avisos.append("abas mudam (ACEITA): " + "; ".join(partes))
            else:
                problemas.append("abas mudam: " + "; ".join(partes))
        if k in aceitas and aceitas[k] != mudanca_real:
            problemas.append("--aceitar declarado, mas a mudança real é outra (ou nenhuma)")

        resultado.append(
            Linha(
                login=exibicao[k],
                no_authelia=no_authelia,
                banco=col_banco,
                abas_hoje=col_hoje,
                problemas=tuple(problemas),
                avisos=tuple(avisos),
            )
        )
    return resultado


def _argumentos() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="conferir_usuarios_banco.py",
        description=(
            "Confere Authelia x acesso_abas.json x banco (linhas na entrada padrão). Só lê. "
            "Saída 0 = tudo casa; 1 = pendência; 2 = erro de uso."
        ),
    )
    p.add_argument("authelia", nargs="?", help="users_database.yml (só as chaves de users:)")
    p.add_argument("acesso_abas", nargs="?", help="acesso_abas.json do piloto")
    p.add_argument(
        "--sql", action="store_true", help="imprime a consulta do banco e sai (nada mais é lido)"
    )
    p.add_argument(
        "--aceitar",
        action="append",
        nargs="+",
        default=[],
        metavar="LOGIN:+ABA,-ABA",
        help="mudança de abas já decidida; só vale se for exatamente a real",
    )
    return p


def main(
    argv: list[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    try:
        args = _argumentos().parse_args(argv)
    except SystemExit as saida:
        return 0 if saida.code == 0 else 2

    if args.sql:
        print(sql_da_consulta(), file=stdout)
        return 0
    if not args.authelia or not args.acesso_abas:
        print("erro: informe USERS_YML e ACESSO_ABAS_JSON (ou use --sql)", file=sys.stderr)
        return 2

    try:
        aceitas = ler_aceitas(item for grupo in args.aceitar for item in grupo)
        with open(args.authelia, encoding="utf-8") as f:
            authelia = logins_do_authelia(f)
        with open(args.acesso_abas, encoding="utf-8") as f:
            json_pessoas, json_curinga = mapa_do_json(f.read())
        banco = linhas_do_banco(stdin.read())
    except (OSError, EntradaInvalida) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2

    linhas = conferir(authelia, json_pessoas, json_curinga, banco, aceitas)
    pendencias = sum(1 for linha in linhas if linha.problemas)

    print(
        f"{'login':<28} {'Authelia':<9} {'banco':<22} {'abas hoje (JSON)':<44} situação",
        file=stdout,
    )
    print("-" * _LARGURA, file=stdout)
    for linha in linhas:
        print(
            f"{linha.login:<28} {'sim' if linha.no_authelia else 'NÃO':<9} {linha.banco:<22} "
            f"{linha.abas_hoje:<44} {linha.situacao}",
            file=stdout,
        )
    print("-" * _LARGURA, file=stdout)
    print(
        f"Authelia: {len(authelia)} | JSON: {len(json_pessoas)} | banco: {len(banco)} | "
        f"pessoas com pendência: {pendencias}",
        file=stdout,
    )
    return 1 if pendencias else 0


if __name__ == "__main__":
    sys.exit(main())
