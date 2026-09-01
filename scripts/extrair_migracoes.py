"""Extrai as migrations do `banco-de-reservas` (documentacao) para `.sql` aplicaveis.

Por que existe
--------------
O `banco-de-reservas` e', por escrita propria, uma pasta EXCLUSIVAMENTE documentacional: o
DDL vive em blocos ```sql dentro de `.md`, copiados a mao para o Query Tool do pgAdmin.
Producao precisa de arquivo aplicavel e versionado -- e a `convencoes.md` §7 daquela pasta
ja' decidiu onde ele mora: "migrations vivem no repositorio do motor".

Este script faz a ponte, e a faz de forma RASTREAVEL: cada `.sql` gerado carrega no
cabecalho o documento de origem e o sha256 do bloco, e o manifesto registra os dois. Copiar
a mao daria o mesmo arquivo hoje e um drift silencioso em tres meses.

O que ele NAO e'
----------------
Nao roda no CI, e nao deve: o `banco-de-reservas` e' outro REPOSITORIO, e o CI do motor nao
o tem. Por isso a verificacao continua no motor pelo manifesto (`test_migracoes.py` confere
os hashes dos arquivos versionados), e este script e' a ferramenta de ESTACAO DE TRABALHO
que os regenera quando o documento muda. E' a mesma divisao do diagrama do esquema, que a
`esquema-do-banco.md` gera por um comando documentado em vez de manter a mao.

Uso
---
    python scripts/extrair_migracoes.py --origem ../banco-de-reservas/sql
    python scripts/extrair_migracoes.py --origem ../banco-de-reservas/sql --conferir

`--conferir` nao escreve nada: compara o que sairia com o que esta versionado e devolve
codigo 1 na primeira divergencia. E' o modo para rodar depois de mexer na documentacao.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

#: Onde os `.sql` gerados vivem, DENTRO do pacote: assim eles entram na wheel e na imagem
#: (`packages = ["src/motor_expansao"]` no pyproject), e o runner os encontra no container
#: sem depender do checkout do repositorio.
DESTINO_PADRAO = Path("src/motor_expansao/db/migracoes")
ARQUIVO_MANIFESTO = "manifesto.json"

#: Migrations do MOTOR, sem documento no `banco-de-reservas`. Lista fechada de proposito:
#: sem ela, um `.sql` que perdeu o documento de origem (renomeado, removido) cairia no
#: ramo das nativas e seria re-registrado com `documento: null`, sem erro nenhum.
NATIVAS_CONHECIDAS = frozenset({"000-migracoes-aplicadas.sql"})

#: Os documentos numerados da fase de teste. `papeis-e-privilegios.md`, `dados-ficticios.md`
#: e `verificacao.md` ficam de FORA de proposito: o primeiro vai para producao por outro
#: caminho (GRANT no banco real, D20) e os outros dois sao apoio de teste, que a propria
#: pasta declara que "nao devem ir para producao".
PADRAO_NOME = re.compile(r"^(?P<numero>\d{3})-(?P<slug>[a-z0-9-]+)\.md$")

#: A migration e' SEMPRE o primeiro bloco ```sql do documento -- verificado nos dez. Os
#: blocos seguintes sao teste (varios FALHAM de proposito, para provar que um CHECK vale),
#: diagnostico ou rollback, e nenhum deles pode entrar num arquivo aplicavel.
PADRAO_BLOCO = re.compile(r"^```sql$(?P<sql>.*?)^```$", re.MULTILINE | re.DOTALL)

#: Cercas que o padrao acima NAO enxerga: indentadas (dentro de item de lista ou citacao),
#: com info-string diferente (```SQL, ```postgresql) ou com 4 crases. Nenhuma existe hoje
#: ANTES do bloco 1 de nenhum documento, mas `009-*.md` ja' tem uma cerca ```sql indentada
#: mais abaixo -- prova de que o caso e' real nesta base. Se uma dessas aparecer antes do
#: bloco 1, a migration extraida muda em SILENCIO. Por isso o extrator avisa.
PADRAO_CERCA_ESCONDIDA = re.compile(
    r"^(?:\s+```sql|```(?:SQL|postgresql|pgsql)|````+sql)", re.MULTILINE
)

#: O bloco 1 tem de ABRIR uma migration. Sem esta assercao, um snippet ilustrativo
#: inserido acima dele viraria "a migration" sem que nada acusasse -- e `--conferir` nao
#: protegeria, porque ele compara com o que sairia AGORA, nao com o que deveria sair.
INICIOS_VALIDOS = ("BEGIN;", "CREATE EXTENSION")


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def extrair_primeiro_bloco(markdown: str) -> str | None:
    achado = PADRAO_BLOCO.search(markdown)
    if achado is None:
        return None
    return achado.group("sql").strip("\n")


def primeira_linha_de_codigo(sql: str) -> str:
    """Primeira linha que nao e' comentario nem vazia."""
    for linha in sql.splitlines():
        limpa = linha.strip()
        if limpa and not limpa.startswith("--"):
            return limpa
    return ""


def conferir_bloco(documento: str, markdown: str, sql: str) -> None:
    """Barra os dois modos de o bloco 1 deixar de ser a migration, em silencio."""
    inicio = primeira_linha_de_codigo(sql)
    if not inicio.startswith(INICIOS_VALIDOS):
        raise SystemExit(
            f"ERRO: o primeiro bloco ```sql de {documento} comeca com {inicio!r}, e uma "
            f"migration abre com {' ou '.join(INICIOS_VALIDOS)}. Ou entrou um snippet "
            "ilustrativo acima da migration, ou a migration mudou de forma."
        )
    antes_do_bloco = markdown[: markdown.index("```sql")]
    escondida = PADRAO_CERCA_ESCONDIDA.search(antes_do_bloco)
    if escondida is not None:
        linha = antes_do_bloco[: escondida.start()].count("\n") + 1
        raise SystemExit(
            f"ERRO: {documento}:{linha} tem uma cerca de codigo que este extrator nao "
            "enxerga (indentada, com info-string diferente ou com 4 crases) ANTES do "
            "bloco 1. Normalize a cerca no documento antes de extrair."
        )


def cabecalho(documento: str, hash_bloco: str) -> str:
    return (
        "-- ARQUIVO GERADO -- nao editar a mao.\n"
        f"-- Origem: banco-de-reservas/sql/{documento} (primeiro bloco ```sql).\n"
        f"-- sha256 do bloco extraido: {hash_bloco}\n"
        "-- Regenerar: python scripts/extrair_migracoes.py --origem <.../banco-de-reservas/sql>\n"
        "--\n"
        "-- O `banco-de-reservas` e' a fonte da verdade do DESENHO (convencoes §7): mudanca de\n"
        "-- modelo entra la' primeiro e so' depois vira migration aqui. Editar este arquivo\n"
        "-- direto quebra essa ordem e o teste de manifesto acusa.\n"
        "\n"
    )


def coletar(origem: Path) -> list[tuple[str, str, str]]:
    """(numero, documento, sql) por migration, em ordem numerica."""
    itens: list[tuple[str, str, str]] = []
    for caminho in sorted(origem.glob("*.md")):
        achado = PADRAO_NOME.match(caminho.name)
        if achado is None:
            continue
        markdown = caminho.read_text(encoding="utf-8")
        sql = extrair_primeiro_bloco(markdown)
        if sql is None:
            raise SystemExit(f"ERRO: {caminho.name} nao tem bloco ```sql")
        conferir_bloco(caminho.name, markdown, sql)
        itens.append((achado.group("numero"), caminho.name, sql))
    if not itens:
        raise SystemExit(f"ERRO: nenhum documento NNN-*.md em {origem}")
    return itens


def nome_destino(documento: str) -> str:
    return documento.removesuffix(".md") + ".sql"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", required=True, help="pasta sql/ do banco-de-reservas")
    parser.add_argument("--destino", default=str(DESTINO_PADRAO))
    parser.add_argument(
        "--conferir",
        action="store_true",
        help="nao escreve; falha se o versionado divergir do que sairia agora",
    )
    args = parser.parse_args()

    origem = Path(args.origem)
    destino = Path(args.destino)
    if not origem.is_dir():
        raise SystemExit(f"ERRO: origem nao encontrada: {origem}")

    itens = coletar(origem)
    manifesto: dict[str, object] = {
        "origem": "banco-de-reservas/sql",
        "gerado_por": "scripts/extrair_migracoes.py",
        "migracoes": [],
    }
    divergencias: list[str] = []

    # Migrations NATIVAS do motor (a `000`, que cria a tabela de controle) nao tem
    # documento de origem e NAO podem ser apagadas do manifesto numa reextracao. Elas sao
    # preservadas como estao e registradas com `documento: null` — o runner precisa de
    # todas na mesma pasta, em ordem, e o teste de hash tem de cobri-las igual.
    gerados = {nome_destino(doc) for _, doc, _ in itens}
    nativos = sorted(p for p in destino.glob("*.sql") if p.name not in gerados)
    inesperados = [p.name for p in nativos if p.name not in NATIVAS_CONHECIDAS]
    if inesperados:
        raise SystemExit(
            f"ERRO: {', '.join(inesperados)} nao tem documento de origem e nao esta na "
            "lista de migrations nativas do motor (NATIVAS_CONHECIDAS). Se o documento "
            "sumiu da origem, o arquivo viraria 'nativo' em silencio e perderia a "
            "rastreabilidade; se e' migration nova do motor, declare-a na lista."
        )
    for caminho in nativos:
        achado = PADRAO_NOME.match(caminho.name.replace(".sql", ".md"))
        if achado is None:
            raise SystemExit(
                f"ERRO: {caminho.name} nao segue o padrao NNN-slug.sql e nao tem documento "
                "de origem — renomeie ou remova."
            )
        conteudo_nativo = caminho.read_text(encoding="utf-8")
        manifesto["migracoes"].append(  # type: ignore[union-attr]
            {
                "versao": achado.group("numero"),
                "arquivo": caminho.name,
                "documento": None,  # nativa do motor; ver o cabecalho do proprio arquivo
                "sha256_bloco": None,
                "sha256_arquivo": sha256(conteudo_nativo),
            }
        )

    for numero, documento, sql in itens:
        hash_bloco = sha256(sql)
        conteudo = cabecalho(documento, hash_bloco) + sql + "\n"
        alvo = destino / nome_destino(documento)

        if args.conferir:
            atual = alvo.read_text(encoding="utf-8") if alvo.exists() else None
            if atual != conteudo:
                divergencias.append(alvo.name)
        else:
            destino.mkdir(parents=True, exist_ok=True)
            # newline="\n" explicito: sem isso o Python no Windows grava CRLF e o arquivo
            # divergiria do gerado em Linux, quebrando a comparacao de hash entre maquinas.
            alvo.write_text(conteudo, encoding="utf-8", newline="\n")

        manifesto["migracoes"].append(  # type: ignore[union-attr]
            {
                "versao": numero,
                "arquivo": alvo.name,
                "documento": documento,
                "sha256_bloco": hash_bloco,
                "sha256_arquivo": sha256(conteudo),
            }
        )

    # Ordenar por versao: as nativas foram registradas antes das geradas, e o manifesto
    # tem de refletir a ORDEM DE APLICACAO — e' por ela que o runner caminha.
    manifesto["migracoes"].sort(key=lambda item: item["versao"])  # type: ignore[union-attr,index]

    caminho_manifesto = destino / ARQUIVO_MANIFESTO
    texto_manifesto = json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n"
    if args.conferir:
        atual = caminho_manifesto.read_text(encoding="utf-8") if caminho_manifesto.exists() else None
        if atual != texto_manifesto:
            divergencias.append(ARQUIVO_MANIFESTO)
        if divergencias:
            print("DIVERGENTE (regenere sem --conferir):", ", ".join(divergencias))
            return 1
        print(f"OK: {len(itens)} migrations conferem com a documentacao.")
        return 0

    caminho_manifesto.write_text(texto_manifesto, encoding="utf-8", newline="\n")
    print(f"OK: {len(itens)} migrations extraidas para {destino}/")
    for item in manifesto["migracoes"]:  # type: ignore[union-attr]
        print(f"  {item['versao']}  {item['arquivo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
