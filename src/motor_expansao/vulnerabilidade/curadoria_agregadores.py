"""BLK-MA-21: curadoria dos feeds dos AGREGADORES, entre o clone do coletor e o motor.

`<clone GymScraping>/{Wellhub,TotalPass}/csvs*` -> `<destino>/{wellhub,totalpass}/csvs/*.csv`, que
é onde `snapshots.py` procura (`DIR_WELLHUB_DEFAULT` / `DIR_TOTALPASS_DEFAULT`). É o passo 2 do cron
MENSAL (`scripts/cron/run_snapshot_agregadores.sh`), entre a coleta e o snapshot.

**Por que isto é código versionado e testado, e não três `cp` no shell (DEC-038, D6).** Ele decide
duas coisas que, decididas errado, produzem um NÚMERO MAIOR em vez de um erro:

  1. **QUAL diretório é a fonte de cada agregador.** No WellHub os dois universos coexistem no
     clone e diferem por 2-3x (16.432 x 6.850 linhas, medido em SP): `csvs/` é o consolidado do
     pipeline — que **já sai filtrado** quando o filtro do pipeline está ligado, o modo default —
     e `csvs_musculacao/` é o subset pós-split, que só é gerado quando o filtro do pipeline está
     DESLIGADO (`Wellhub/coletor_wellhub.py`, ramo `--no-musculacao-filter`). Copiar o errado
     infla o universo do funil de M&A com academias sem musculação, em silêncio. No TotalPass não
     há escolha: o filtro é `hardcoded` no coletor e só existe `csvs/`.
  2. **Se o feed é FRESCO o bastante para ser fotografado.** O snapshot mensal roda depois de ~21h
     de coleta; se um coletor falhar no meio, os CSVs **antigos continuam no disco** e publicá-los
     faria o `hash_campos_raspados` sair idêntico ao do mês anterior -> `semanas_sem_mudanca`
     cresce sozinho -> o **S4 marca o universo inteiro daquela fonte como "parado"**, que é o
     próprio sinal de vulnerabilidade. Falso positivo em massa, no sinal de segundo maior peso,
     com `exit 0`. É a mesma razão pela qual o cron SEMANAL roda `--fontes unidades`.

**A idade sai da coluna `data_coleta`, DENTRO do CSV — não do `mtime` `[emenda de 2026-08-25 à
DEC-038]`.** A guarda nasceu medindo `p.stat().st_mtime`, e isso a tornava cega justamente ao caso
que ela existe para pegar. Medido nesta estação, no clone real: os 27 CSVs de `TotalPass/csvs/`
tinham `mtime = 2026-08-25` (idade `0` dia) e `data_coleta = 2026-06-01` em **15.982 de 15.986**
linhas — idade real de **85 dias**. A explicação é o `split_by_state` do coletor, que abre cada
arquivo de UF em modo `"w"` ao fim de TODA execução: com o checkpoint cheio, o coletor não recoleta
nada, mas **reescreve conteúdo idêntico com `mtime` de agora**. O `mtime` mede quando o arquivo foi
TOCADO; `data_coleta` mede quando o dado foi COLHIDO, e é essa a pergunta. Motivo independente: o
`mtime` **não sobrevive** a `scp`, `git clone`, `cp -r` nem a restore de volume — a régua antiga
protegia só a estação em que o arquivo nasceu, não a VPS.

O `mtime` continua como **fallback declarado** (feed sem `data_coleta` legível) e continua sendo a
régua da AMBIGUIDADE de D3 — lá a pergunta é outra: "qual dos dois diretórios o coletor escreveu por
último", e nela `mtime` é a resposta certa (os dois carregam o mesmo `data_coleta`). Qual régua
decidiu cada agregador sai no relatório (`regua_idade`) e no log.

Quem recusa uma fonte é esta camada; quem age sobre a recusa é o wrapper, tirando a fonte do
`--fontes` do snapshot. Daí a chave `fontes_publicadas` do relatório e a linha de stdout em formato
fixo (`fontes_publicadas=<a,b>`), que o shell lê sem parsear dicionário Python.

GUARDRAILS (CLAUDE.md §1/§2; DEC-012):
  - READ-ONLY sobre o M1: não lê nem escreve `score_priorizacao`, `hex_score_estrutural`, pesos,
    carteira, plano ou artefato oficial. Não importa `pipelines/`, `dashboard/` nem `config.py`.
  - Anti-PII: **copia arquivo, não deriva dado**. Nada é parseado, nada é persistido além do
    próprio CSV que o coletor já produziu. A contagem de linhas é feita em modo texto.
  - CSV do projeto: `sep=";"`, `encoding="utf-8-sig"` — respeitado por cópia byte a byte
    (`shutil.copy2`), que preserva o BOM e o mtime.
  - **Nunca apaga nada no destino.** Cópia por cima; um CSV de UF que sumiu do coletor permanece.
    Mesma direção segura do "nunca reduzir" do `sync_concorrentes_dashboard.py`: sumiço de arquivo
    é sintoma de coleta parcial muito mais vezes do que de universo que encolheu.
"""

from __future__ import annotations

import argparse
import csv
import logging
import shutil
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

_logger = logging.getLogger(__name__)

# Agregadores curados por este módulo, na ordem canônica de relatório. `unidades` NÃO entra: é o
# feed de cadeias, tem cadência semanal própria e já é lido direto do clone pelo cron semanal.
AGREGADORES: tuple[str, ...] = ("totalpass", "wellhub")

# Caixa EXATA dos diretórios no clone do coletor. No Linux isto importa: o `GymScraping` #11
# renomeou `Totalpass/` -> `TotalPass/` justamente porque o NTFS escondia a divergência e o clone
# da VPS morria com `ModuleNotFoundError` antes de qualquer log.
_DIR_ORIGEM_POR_AGREGADOR: dict[str, str] = {"totalpass": "TotalPass", "wellhub": "Wellhub"}

ORIGEM_DEFAULT = Path("gymscraping")
DESTINO_DEFAULT = Path("concorrentes")
MAX_IDADE_DIAS_DEFAULT = 7.0

# Coluna de data de coleta, ÚLTIMA por convenção nos dois coletores agregadores
# (`Wellhub/csv_writer.py` e `TotalPass/csv_writer.py`). É a régua PRIMÁRIA de frescor.
COLUNA_DATA_COLETA = "data_coleta"
DELIMITADOR_FEED = ";"

# Rótulos da régua que decidiu a idade — vão ao relatório e ao log, para que "3 dias" nunca seja um
# número sem procedência. `mtime` é o fallback e `indisponivel` é "não há CSV nenhum".
REGUA_DATA_COLETA = "data_coleta"
REGUA_MTIME = "mtime"
REGUA_INDISPONIVEL = "indisponivel"

# PISO relativo de volume: recusa o agregador cujo volume novo caia abaixo desta fração do que JÁ
# está publicado no destino. O teto (`--max-linhas-*`) pega universo que INFLA; sem piso, uma
# coleta que morreu na metade passa — os CSVs são frescos (`data_coleta` de hoje), só que com metade
# das linhas, e as que faltam viram `sumiu_recente` em massa no S1, que é o sinal de MAIOR peso.
# Inerte na primeira execução, por construção: sem destino publicado não há baseline para comparar.
PISO_RELATIVO_DEFAULT = 0.5


def _csvs(diretorio: Path) -> list[Path]:
    """`*.csv` diretos do diretório, em ordem estável. Diretório ausente contribui 0 e não levanta."""
    if not diretorio.is_dir():
        return []
    return sorted(p for p in diretorio.glob("*.csv") if p.is_file())


def _mtime_mais_novo(diretorio: Path) -> float | None:
    """mtime do CSV mais NOVO do diretório, ou `None` se não houver nenhum."""
    arquivos = _csvs(diretorio)
    if not arquivos:
        return None
    return max(p.stat().st_mtime for p in arquivos)


def _contar_linhas(arquivos: Sequence[Path]) -> int:
    """Linhas de DADOS dos CSVs (soma, já descontado 1 cabeçalho por arquivo).

    Leitura em modo TEXTO, sem parsear: a contagem é diagnóstico de volume, não ingestão. Parsear
    aqui significaria carregar PII em memória para responder "quantos", que é caro e desnecessário.
    Arquivo com só o cabeçalho (ou vazio) contribui 0, nunca negativo.
    """
    total = 0
    for arquivo in arquivos:
        with arquivo.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            n = sum(1 for linha in fh if linha.strip())
        total += max(0, n - 1)
    return total


def escolher_diretorio_fonte(origem: Path, agregador: str) -> tuple[Path, str]:
    """Diretório de origem do agregador + o MOTIVO da escolha, em prosa auditável.

    Regra por agregador (DEC-038, D3):

    | agregador | escolha |
    |---|---|
    | `totalpass` | sempre `TotalPass/csvs` — o filtro de musculação é `hardcoded` no coletor |
    | `wellhub` | `Wellhub/csvs_musculacao` quando ele existe e **não** é mais antigo que `Wellhub/csvs` |
    | `wellhub` | `Wellhub/csvs` quando `csvs_musculacao/` não existe (modo default: `csvs/` já sai filtrado) |
    | `wellhub` | **levanta** quando `csvs_musculacao/` existe e é ESTRITAMENTE mais antigo |

    O terceiro ramo é o que impede o modo de falha silencioso: `csvs_musculacao/` mais antigo
    significa que a coleta mais recente rodou noutro MODO (filtro do pipeline ligado, que pula o
    subset pós-split), e o diretório velho ficou para trás. Escolher em silêncio entre dois
    universos que diferem por 2-3x troca "erro" por "número maior", que ninguém percebe.
    """
    agregador = str(agregador)
    if agregador not in AGREGADORES:
        raise ValueError(f"agregador fora do contrato: {agregador!r}; aceitos: {list(AGREGADORES)}")
    raiz = Path(origem) / _DIR_ORIGEM_POR_AGREGADOR[agregador]

    if agregador == "totalpass":
        return (
            raiz / "csvs",
            "TotalPass so' emite `csvs/` (filtro de musculacao e' hardcoded no coletor)",
        )

    csvs = raiz / "csvs"
    musculacao = raiz / "csvs_musculacao"
    mtime_musc = _mtime_mais_novo(musculacao)
    if mtime_musc is None:
        return csvs, (
            "`csvs_musculacao/` ausente ou vazio: modo default do coletor, "
            "em que `csvs/` ja' sai filtrado por musculacao"
        )
    mtime_csvs = _mtime_mais_novo(csvs)
    if mtime_csvs is not None and mtime_musc < mtime_csvs:
        raise ValueError(
            "WellHub em estado ambiguo: `csvs_musculacao/` existe mas e' MAIS ANTIGO que `csvs/`, "
            "o que indica que a ultima coleta rodou noutro modo. Os dois universos diferem por "
            "2-3x, e escolher em silencio produz um numero maior, nao um erro. "
            f"{musculacao} (mais novo: {_iso(mtime_musc)}) x "
            f"{csvs} (mais novo: {_iso(mtime_csvs)}). "
            "Confira de que modo o coletor rodou e apague o diretorio obsoleto a mao."
        )
    return (
        musculacao,
        "`csvs_musculacao/` presente e nao mais antigo que `csvs/`: subset de musculacao",
    )


def _iso(mtime: float) -> str:
    """mtime -> ISO em UTC, para a mensagem de erro ser acionável sem depender do locale."""
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat(timespec="seconds")


def _data_coleta_mais_nova(arquivos: Sequence[Path]) -> date | None:
    """Maior `data_coleta` legível do conjunto, ou `None` se nenhuma linha oferecer uma.

    Leitura em modo TEXTO com o `csv` da stdlib — e **só** a coluna `data_coleta` é olhada; nenhuma
    outra célula é lida, guardada ou derivada (anti-PII do módulo). Um `cut -d';' -f10` do shell
    não serviria: campos com `;` dentro de aspas (endereço, lista de modalidades) desalinham, e foi
    exatamente o que se mediu no clone real — quatro linhas devolviam endereço no lugar da data.

    Tolerante por dentro, silenciosa por fora: arquivo sem a coluna, célula vazia ou data fora do
    ISO simplesmente não contribuem. Quem decide o que fazer com a ausência é `idade_do_feed`, que
    cai no fallback de `mtime` e DIZ que caiu.
    """
    melhor: date | None = None
    for arquivo in arquivos:
        try:
            with arquivo.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
                leitor = csv.reader(fh, delimiter=DELIMITADOR_FEED)
                cabecalho = next(leitor, None)
                if not cabecalho or COLUNA_DATA_COLETA not in cabecalho:
                    continue
                indice = cabecalho.index(COLUNA_DATA_COLETA)
                for linha in leitor:
                    if len(linha) <= indice:
                        continue
                    try:
                        valor = date.fromisoformat(linha[indice].strip())
                    except ValueError:
                        continue
                    if melhor is None or valor > melhor:
                        melhor = valor
        except OSError:  # pragma: no cover - disco/permissão; o fallback de mtime cobre
            continue
    return melhor


def idade_do_feed(diretorio: Path, agora: datetime) -> tuple[float | None, str]:
    """`(idade em dias, régua usada)` do feed. `(None, 'indisponivel')` quando não há CSV.

    A régua PRIMÁRIA é `data_coleta` (dentro do arquivo) e o fallback é `mtime` (do arquivo). A
    diferença não é acadêmica: medido no clone real em 2026-08-25, `TotalPass/csvs/` tinha
    `mtime` de HOJE e `data_coleta = 2026-06-01` em 15.982 de 15.986 linhas — 85 dias de idade
    reportados como `0`. O `split_by_state` do coletor reescreve os 27 CSVs por UF em modo `"w"`
    ao fim de toda execução, mesmo quando o checkpoint impediu qualquer recoleta.

    A granularidade da régua primária é o **DIA**, porque `data_coleta` é uma data (`AAAA-MM-DD`) e
    fingir precisão de hora seria inventar informação que o feed não carrega.
    """
    arquivos = _csvs(Path(diretorio))
    if not arquivos:
        return None, REGUA_INDISPONIVEL
    coletada = _data_coleta_mais_nova(arquivos)
    if coletada is not None:
        return float((agora.date() - coletada).days), REGUA_DATA_COLETA
    mtime = _mtime_mais_novo(Path(diretorio))
    if mtime is None:  # pragma: no cover - há CSV, logo há mtime
        return None, REGUA_INDISPONIVEL
    return (agora.timestamp() - mtime) / 86400.0, REGUA_MTIME


def feed_esta_fresco(
    diretorio: Path, max_idade_dias: float, agora: datetime
) -> tuple[bool, float | None]:
    """`(fresco?, idade em dias do feed)`. Diretório sem CSV nenhum nunca é fresco.

    Fina sobre `idade_do_feed`, que é quem sabe QUAL régua respondeu; aqui só se compara com o
    limite. A régua usada vai ao log em INFO — sem isso, "3,0 dias" é um número sem procedência, e
    a diferença entre as duas réguas já valeu 85 dias de erro numa medição real.

    `agora` é INJETADO de propósito: com `datetime.now()` dentro da lógica o teste dependeria do
    relógio, e a única forma de exercitar "feed velho" seria esperar uma semana.
    """
    idade, regua = idade_do_feed(Path(diretorio), agora)
    if idade is None:
        return False, None
    _logger.info(
        "idade do feed em %s: %.2f dia(s) pela regua `%s` (limite %.1f)",
        diretorio,
        idade,
        regua,
        float(max_idade_dias),
    )
    return idade <= float(max_idade_dias), idade


def _decidir(
    origem: Path,
    destino: Path,
    agregador: str,
    *,
    max_idade_dias: float,
    limite: int | None,
    piso_relativo: float,
    agora: datetime,
) -> tuple[dict[str, object], list[Path]]:
    """Decide UM agregador sem tocar o disco de destino: `(detalhe do relatório, arquivos)`.

    Separada de `curar` porque é ela que pode LEVANTAR (ambiguidade de D3), e levantar depois de já
    ter copiado o outro agregador deixaria estado parcial no destino — ver o docstring de `curar`.
    """
    dir_origem, motivo = escolher_diretorio_fonte(Path(origem), agregador)
    arquivos = _csvs(dir_origem)
    # UMA leitura da idade serve à decisão E ao relatório. Chamar `feed_esta_fresco` e
    # `idade_do_feed` em separado varreria os CSVs duas vezes e abriria a chance de a régua
    # relatada divergir da que decidiu — dois caminhos podem divergir; um não.
    idade, regua = idade_do_feed(dir_origem, agora)
    fresco = idade is not None and idade <= float(max_idade_dias)
    if idade is not None:
        _logger.info(
            "idade do feed em %s: %.2f dia(s) pela regua `%s` (limite %.1f)",
            dir_origem,
            idade,
            regua,
            float(max_idade_dias),
        )
    n_linhas = _contar_linhas(arquivos)
    publicado_antes = _contar_linhas(_csvs(Path(destino) / agregador / "csvs"))

    recusa: str | None = None
    if not arquivos:
        recusa = f"nenhum CSV em {dir_origem}"
    elif not fresco:
        recusa = (
            f"feed velho: idade {idade:.1f} dia(s) pela regua `{regua}`, "
            f"limite {float(max_idade_dias):.1f}. Fotografar feed nao recoletado faz o S4 "
            "marcar o universo inteiro desta fonte como parado"
        )
    elif limite is not None and n_linhas > int(limite):
        recusa = (
            f"volume acima do limite: {n_linhas} linha(s) > {int(limite)}. "
            "Universo inflado costuma ser troca de modo do coletor, nao crescimento real"
        )
    elif (
        piso_relativo > 0
        and publicado_antes > 0
        and n_linhas < publicado_antes * float(piso_relativo)
    ):
        recusa = (
            f"volume ABAIXO do piso: {n_linhas} linha(s) contra {publicado_antes} ja' publicada(s) "
            f"({n_linhas / publicado_antes:.0%}, piso {float(piso_relativo):.0%}). Queda brusca "
            "costuma ser coleta interrompida, e as linhas que faltam viram `sumiu_recente` em massa "
            "no S1. Confira o log do coletor; para publicar assim mesmo, `--piso-relativo 0`"
        )

    detalhe: dict[str, object] = {
        "diretorio_origem": str(dir_origem),
        "motivo": motivo,
        "n_arquivos": len(arquivos),
        "n_linhas": n_linhas,
        "n_linhas_publicadas_antes": publicado_antes,
        "idade_dias": None if idade is None else round(float(idade), 2),
        "regua_idade": regua,
        "publicado": recusa is None,
    }
    if recusa is not None:
        detalhe["motivo_recusa"] = recusa
    return detalhe, arquivos


def curar(
    origem: Path = ORIGEM_DEFAULT,
    destino: Path = DESTINO_DEFAULT,
    *,
    max_idade_dias: float = MAX_IDADE_DIAS_DEFAULT,
    limites: dict[str, int | None] | None = None,
    piso_relativo: float = PISO_RELATIVO_DEFAULT,
    agora: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Escolhe, valida e publica os CSVs dos agregadores. Devolve o relatório por agregador.

    Chaves de saída: uma por agregador (`diretorio_origem`, `motivo`, `n_arquivos`, `n_linhas`,
    `n_linhas_publicadas_antes`, `idade_dias`, `regua_idade`, `publicado`, e `motivo_recusa`
    quando não publicado), mais `fontes_publicadas` — a lista ordenada das que passaram, que é **o
    que o wrapper transforma em `--fontes`**.

    Um agregador é recusado, e a execução **continua**, quando: o diretório escolhido não tem CSV;
    o feed está velho (`max_idade_dias`); o volume estoura o teto opcional de linhas; ou o volume
    cai abaixo do PISO relativo ao que já está publicado. Recusar um não pode derrubar o outro —
    meia foto é melhor que nenhuma, e a foto que falta é declarada (é para isso que `fontes_lidas`
    existe no parquet).

    `escolher_diretorio_fonte` levantando é OUTRA coisa e **derruba** a execução: ali o estado é
    ambíguo, e publicar o universo errado é pior que não publicar nada.

    **Tudo ou nada, e por isso em DUAS fases `[emenda de 2026-08-25 à DEC-038]`.** Decidir os dois
    agregadores primeiro e copiar depois é o que torna a promessa acima verdadeira: no laço único
    anterior, o `totalpass` (primeiro na ordem canônica) já tinha sido COPIADO quando a ambiguidade
    do `wellhub` levantava, e o destino ficava com meia curadoria de um mês novo enquanto o wrapper
    abortava. Agora nenhuma exceção de decisão alcança o disco de destino.

    `dry_run=True` faz tudo menos copiar — inclusive criar diretório.
    """
    agora = agora or datetime.now(tz=UTC)
    limites = dict(limites or {})
    destino = Path(destino)

    # FASE 1 — decidir os DOIS. Uma exceção aqui não deixa rastro no destino.
    decisoes: dict[str, tuple[dict[str, object], list[Path]]] = {
        agregador: _decidir(
            Path(origem),
            destino,
            agregador,
            max_idade_dias=max_idade_dias,
            limite=limites.get(agregador),
            piso_relativo=piso_relativo,
            agora=agora,
        )
        for agregador in AGREGADORES
    }

    # FASE 2 — publicar o que passou.
    relatorio: dict[str, object] = {}
    publicadas: list[str] = []
    for agregador, (detalhe, arquivos) in decisoes.items():
        if not detalhe["publicado"]:
            _logger.warning(
                "agregador %s NAO publicado: %s", agregador, detalhe.get("motivo_recusa")
            )
        else:
            destino_agregador = destino / agregador / "csvs"
            if not dry_run:
                destino_agregador.mkdir(parents=True, exist_ok=True)
                for arquivo in arquivos:
                    # `copy2` preserva o mtime, que é o FALLBACK da guarda de frescor do mês
                    # seguinte (a régua primária, `data_coleta`, viaja dentro do próprio arquivo e
                    # não depende disto). Com `copy` puro, um feed sem `data_coleta` legível
                    # pareceria recém-coletado para sempre.
                    shutil.copy2(arquivo, destino_agregador / arquivo.name)
            detalhe["destino"] = str(destino_agregador)
            publicadas.append(agregador)
            _logger.info(
                "agregador %s publicado: %d arquivo(s), %d linha(s), de %s (idade pela regua `%s`)",
                agregador,
                len(arquivos),
                detalhe["n_linhas"],
                detalhe["diretorio_origem"],
                detalhe["regua_idade"],
            )
        relatorio[agregador] = detalhe

    relatorio["fontes_publicadas"] = sorted(publicadas)
    relatorio["dry_run"] = bool(dry_run)
    return relatorio


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """CLI da curadoria. É o passo 2 do wrapper mensal — o wrapper lê `fontes_publicadas` do stdout."""
    p = argparse.ArgumentParser(
        prog="python -m motor_expansao.vulnerabilidade.curadoria_agregadores",
        description=(
            "Escolhe o diretorio certo de cada agregador no clone do coletor, recusa feed velho "
            "e publica os CSVs onde o snapshot os procura. READ-ONLY sobre o M1."
        ),
    )
    p.add_argument(
        "--origem",
        type=Path,
        default=ORIGEM_DEFAULT,
        help="raiz do clone do coletor (contem `Wellhub/` e `TotalPass/`, caixa exata)",
    )
    p.add_argument(
        "--destino",
        type=Path,
        default=DESTINO_DEFAULT,
        help="raiz que o motor le (recebe `wellhub/csvs/` e `totalpass/csvs/`, em minusculo)",
    )
    p.add_argument(
        "--max-idade-dias",
        type=float,
        default=MAX_IDADE_DIAS_DEFAULT,
        help=(
            f"idade maxima do CSV mais novo para o agregador ser publicado "
            f"(default {MAX_IDADE_DIAS_DEFAULT:g}); acima disso a fonte sai do `--fontes`"
        ),
    )
    p.add_argument(
        "--max-linhas-wellhub",
        type=int,
        default=None,
        help="teto opcional de linhas do WellHub; acima dele a fonte nao e' publicada",
    )
    p.add_argument(
        "--max-linhas-totalpass",
        type=int,
        default=None,
        help="teto opcional de linhas do TotalPass; acima dele a fonte nao e' publicada",
    )
    p.add_argument(
        "--piso-relativo",
        type=float,
        default=PISO_RELATIVO_DEFAULT,
        help=(
            f"fracao MINIMA do volume ja' publicado no destino (default {PISO_RELATIVO_DEFAULT:g}); "
            "abaixo dela a fonte nao e' publicada. `0` desliga. Inerte na primeira execucao, "
            "quando nao ha' baseline"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="decide e relata sem copiar arquivo nem criar diretorio",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entrada do `python -m`. `0` mesmo com fonte recusada; quem decide abortar é o wrapper.

    Imprime DUAS coisas, e a ordem importa para o shell: o relatório completo (diagnóstico humano,
    vai para o log) e, na ÚLTIMA linha, `fontes_publicadas=<a,b>` em formato fixo. O wrapper lê essa
    linha com `grep`/`cut` — nunca o dicionário Python, que mudaria de forma a cada campo novo.
    Nenhuma fonte publicada imprime `fontes_publicadas=` com o valor vazio, e é o wrapper que trata
    isso como falha (fotografar nada não é sucesso silencioso).
    """
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    relatorio = curar(
        args.origem,
        args.destino,
        max_idade_dias=args.max_idade_dias,
        limites={
            "wellhub": args.max_linhas_wellhub,
            "totalpass": args.max_linhas_totalpass,
        },
        piso_relativo=args.piso_relativo,
        dry_run=args.dry_run,
    )
    print(relatorio)
    publicadas: list[str] = relatorio["fontes_publicadas"]  # type: ignore[assignment]
    print(f"fontes_publicadas={','.join(publicadas)}")
    return 0


__all__ = [
    "AGREGADORES",
    "COLUNA_DATA_COLETA",
    "DESTINO_DEFAULT",
    "MAX_IDADE_DIAS_DEFAULT",
    "ORIGEM_DEFAULT",
    "PISO_RELATIVO_DEFAULT",
    "REGUA_DATA_COLETA",
    "REGUA_INDISPONIVEL",
    "REGUA_MTIME",
    "curar",
    "escolher_diretorio_fonte",
    "feed_esta_fresco",
    "idade_do_feed",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
