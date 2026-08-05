"""Cadastro operacional das unidades da rede - BLK-EXEC-00/00b.

As dimensoes que o time de campo usa todo dia **nao existem na API Growth**: consultor,
master franquia, franqueado, cidade, departamento, preco do plano Gold, modalidades e os
tiers Wellhub/Totalpass. Elas vivem numa aba `DADOS` de planilha, mantida a mao. Este
modulo e' o repositorio dessas dimensoes -- semeado daquela planilha e, a partir da
DEC-023, **editavel pela propria Visao Executiva** para atribuir consultor e master
franqueado a quem ainda nao tem.

Por que JSON, e nao parquet
---------------------------
O backend do piloto e' READ-ONLY por CI: `test_backend_read_only_por_ast` reprova qualquer
`to_parquet`/`to_csv`/`to_excel` e `test_leituras_nao_mutam_artefatos` prova por snapshot
do filesystem que nada e' escrito. Esse guardrail existe para proteger **artefato do M1** e
nao deve ser afrouxado. A saida nao e' abrir excecao no teste, e' **separar fisicamente**:

* diretorio proprio (`MOTOR_CADASTRO_DIR`), FORA do `MOTOR_DATA_DIR`, o unico montado
  `:rw` em producao -- nenhum artefato M1 fica sob um mount de escrita;
* **JSON**, nao parquet: some a tentacao do `to_parquet` e o AST guardrail continua
  integro, sem excecao nenhuma;
* escrita atomica por `os.replace`, que esta deliberadamente FORA da lista de proibidos
  (o comentario do teste diz que `replace`/`move` ficam de fora).

Concorrencia e auditoria
------------------------
Sem banco, dois consultores editando ao mesmo tempo se sobrescreveriam em silencio. O
payload carrega uma `versao` e o `PUT` so aplica se ela bater com a do disco; senao devolve
conflito e a tela recarrega. Cada edicao grava uma linha em `cadastro_log.jsonl` (quem,
quando, unidade, campo, de -> para), append-only. O autor sai do header `Remote-User`, que
o Caddy **ja** repassa ao piloto.

A interface e' estreita de proposito (`ler_cadastro`, `atribuir`): quando o PostgreSQL com
usuarios e permissoes entrar, troca-se UMA implementacao, nao codigo espalhado.
"""

from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ARQUIVO_CADASTRO = "cadastro_unidades.json"
ARQUIVO_LOG = "cadastro_log.jsonl"

#: Unica lista branca de campos que a tela pode escrever. O cadastro NAO e' porta de
#: escrita para qualquer coisa: faturamento, inauguracao e identidade vem da Growth e
#: continuam intocaveis pela interface.
CAMPOS_EDITAVEIS: tuple[str, ...] = ("consultor", "consultor_2", "master_franquia")

#: Campos que a leitura devolve (os editaveis mais os semeados da planilha).
CAMPOS_CADASTRO: tuple[str, ...] = (
    "cod_unidade",
    "cidade",
    "dpto",
    "master_franquia",
    "franqueado",
    "consultor",
    "consultor_2",
    "gold",
    "life_time",
    "ltv",
    "wellhub",
    "totalpass",
    "modalidades",
)

_TAMANHO_MAXIMO_VALOR = 120

# Serializa ler-conferir-gravar. Sem isto, dois PUTs simultaneos passam os DOIS pela
# checagem de versao (ambos leem 5, ambos gravam 6) e uma das duas edicoes some do disco
# com a tela mostrando sucesso -- perda silenciosa, o pior tipo. Cobre o processo do
# uvicorn, que e' como o piloto roda; com varios workers, o passo seguinte e' o banco que
# a DEC-023 ja aponta como destino.
_TRAVA = threading.Lock()


class CadastroIndisponivel(RuntimeError):
    """O diretorio de cadastro nao esta montado (leitura degrada, escrita falha)."""


class ConflitoDeVersao(RuntimeError):
    """Outro usuario gravou antes; o cliente precisa recarregar."""

    def __init__(self, versao_atual: int) -> None:
        super().__init__(
            "O cadastro foi alterado por outra pessoa enquanto esta edição estava aberta. "
            "Recarregue a tela e refaça a alteração."
        )
        self.versao_atual = versao_atual


class CampoNaoEditavel(ValueError):
    """Tentativa de escrever fora da lista branca."""


@dataclass(frozen=True)
class Cadastro:
    versao: int
    atualizado_em: str | None
    unidades: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: False quando o diretorio nao esta montado -- a tela mostra os filtros de cadastro
    #: desabilitados em vez de mentir que ninguem tem consultor.
    disponivel: bool = True

    def de(self, unidade_id: str) -> dict[str, Any]:
        return dict(self.unidades.get(unidade_id, {}))


def cadastro_dir() -> Path:
    """Diretorio do cadastro. `MOTOR_CADASTRO_DIR` manda; default = `<repo>/data/cadastro`."""
    bruto = os.environ.get("MOTOR_CADASTRO_DIR")
    if bruto:
        return Path(bruto)
    return Path(__file__).resolve().parents[3] / "data" / "cadastro"


def caminho_cadastro(base: Path | None = None) -> Path:
    return (base or cadastro_dir()) / ARQUIVO_CADASTRO


def ler_cadastro(base: Path | None = None) -> Cadastro:
    """Le o cadastro. NUNCA levanta: sem arquivo, devolve cadastro vazio indisponivel.

    Degradar em silencio aqui e' proposital -- o CI e o dev local nao tem o volume montado,
    e a Visao Executiva tem de subir do mesmo jeito, so sem as dimensoes de cadastro.
    """
    caminho = caminho_cadastro(base)
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Cadastro(versao=0, atualizado_em=None, unidades={}, disponivel=False)
    unidades = dados.get("unidades")
    if not isinstance(unidades, dict):
        unidades = {}
    return Cadastro(
        versao=int(dados.get("versao") or 0),
        atualizado_em=dados.get("atualizado_em"),
        unidades={
            str(k): _sanear(v) for k, v in unidades.items() if isinstance(v, dict)
        },
        disponivel=True,
    )


def _sanear(registro: dict[str, Any]) -> dict[str, Any]:
    """NaN/Infinity viram None. O cadastro nasce de uma planilha mantida a mao, e uma
    celula vazia de GOLD/LTV chegava como `NaN` -- que `json.loads` aceita e
    `json.dumps(allow_nan=False)` do FastAPI recusa, derrubando a ficha daquela unidade
    com 500 e sem nenhuma pista de que o problema esta no cadastro."""
    limpo: dict[str, Any] = {}
    for chave, valor in registro.items():
        if isinstance(valor, float) and not math.isfinite(valor):
            limpo[chave] = None
        else:
            limpo[chave] = valor
    return limpo


def gravar_cadastro(cadastro: Cadastro, base: Path | None = None) -> Cadastro:
    """Grava o cadastro inteiro de forma atomica (tmp + `os.replace`).

    `os.replace` e' atomico no mesmo filesystem: ou o arquivo antigo continua inteiro, ou o
    novo aparece inteiro. Nunca ha um JSON pela metade em disco, nem se o processo morrer no
    meio da gravacao.
    """
    diretorio = base or cadastro_dir()
    if not diretorio.is_dir():
        raise CadastroIndisponivel(
            f"Diretório de cadastro ausente ({diretorio}). "
            "Em produção ele é o volume :rw montado no compose."
        )
    destino = diretorio / ARQUIVO_CADASTRO
    corpo = {
        "versao": cadastro.versao,
        "atualizado_em": cadastro.atualizado_em,
        "unidades": cadastro.unidades,
    }
    # Nome de temporario UNICO por processo: um `.tmp` fixo e' disputado por dois
    # escritores simultaneos, e um deles morre com PermissionError/FileNotFoundError no
    # meio do `os.replace` -- 500 no lugar de um 409 tratavel.
    temporario = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
    temporario.write_text(
        json.dumps(corpo, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(temporario, destino)
    return cadastro


def atribuir(
    unidade_id: str,
    campos: dict[str, Any],
    *,
    autor: str | None = None,
    versao_cliente: int | None = None,
    base: Path | None = None,
) -> Cadastro:
    """Aplica uma edicao no cadastro de UMA unidade e devolve o cadastro novo.

    `versao_cliente` implementa a concorrencia otimista: se nao bater com a do disco,
    levanta `ConflitoDeVersao` e nada e' gravado.
    """
    invalidos = sorted(set(campos) - set(CAMPOS_EDITAVEIS))
    if invalidos:
        raise CampoNaoEditavel(
            f"Campo(s) fora da lista branca do cadastro: {', '.join(invalidos)}. "
            f"Editáveis: {', '.join(CAMPOS_EDITAVEIS)}."
        )
    if not str(unidade_id).strip():
        raise ValueError("unidade_id vazio.")

    with _TRAVA:
        return _aplicar(unidade_id, campos, autor=autor, versao_cliente=versao_cliente, base=base)


def _aplicar(
    unidade_id: str,
    campos: dict[str, Any],
    *,
    autor: str | None,
    versao_cliente: int | None,
    base: Path | None,
) -> Cadastro:
    """Corpo de `atribuir`, ja sob a trava: ler, conferir a versao e gravar sao um passo so."""
    atual = ler_cadastro(base)
    if not atual.disponivel:
        raise CadastroIndisponivel(
            "Cadastro não disponível para escrita neste ambiente (volume não montado)."
        )
    if versao_cliente is not None and int(versao_cliente) != atual.versao:
        raise ConflitoDeVersao(atual.versao)

    anterior = atual.de(unidade_id)
    registro = dict(anterior)
    mudancas: list[tuple[str, Any, Any]] = []
    for campo, valor in campos.items():
        limpo = _limpar(valor)
        if registro.get(campo) == limpo:
            continue
        mudancas.append((campo, registro.get(campo), limpo))
        registro[campo] = limpo
    if not mudancas:
        return atual

    unidades = dict(atual.unidades)
    unidades[unidade_id] = registro
    novo = Cadastro(
        versao=atual.versao + 1,
        atualizado_em=datetime.now(UTC).isoformat(timespec="seconds"),
        unidades=unidades,
        disponivel=True,
    )
    gravar_cadastro(novo, base)
    _auditar(unidade_id, mudancas, autor, novo.versao, base)
    return novo


def _limpar(valor: Any) -> str:
    """Normaliza o valor editavel: string aparada, teto de tamanho, sem controle."""
    if valor is None:
        return ""
    texto = " ".join(str(valor).split())
    texto = "".join(c for c in texto if c.isprintable())
    return texto[:_TAMANHO_MAXIMO_VALOR]


def _auditar(
    unidade_id: str,
    mudancas: list[tuple[str, Any, Any]],
    autor: str | None,
    versao: int,
    base: Path | None,
) -> None:
    """Uma linha JSON por campo alterado. Append-only; falha de log nao derruba a edicao."""
    diretorio = base or cadastro_dir()
    linhas = [
        json.dumps(
            {
                "quando": datetime.now(UTC).isoformat(timespec="seconds"),
                "autor": (autor or "desconhecido").strip()[:120],
                "unidade_id": unidade_id,
                "campo": campo,
                "de": de,
                "para": para,
                "versao": versao,
            },
            ensure_ascii=False,
        )
        for campo, de, para in mudancas
    ]
    try:
        with (diretorio / ARQUIVO_LOG).open("a", encoding="utf-8") as arquivo:
            arquivo.write("\n".join(linhas) + "\n")
    except OSError:
        # O log e' rastro, nao transacao: perder uma linha nao pode desfazer a edicao que
        # ja esta em disco (e a atomicidade acima garante que ela esta inteira).
        pass


def valores_distintos(cadastro: Cadastro, campo: str) -> list[str]:
    """Valores nao vazios de um campo, ordenados - alimenta os filtros da tela."""
    vistos = {
        str(registro.get(campo)).strip()
        for registro in cadastro.unidades.values()
        if str(registro.get(campo) or "").strip()
    }
    return sorted(vistos)
