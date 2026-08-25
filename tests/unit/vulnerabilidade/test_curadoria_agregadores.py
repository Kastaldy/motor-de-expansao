"""BLK-MA-21 / DEC-038: testes da curadoria dos feeds dos agregadores.

Fixtures 100% SINTETICAS em `tmp_path` (CSVs com `sep=";"` / `encoding="utf-8-sig"`, nomes
inventados). Nenhum teste toca o clone real do coletor -- ele e' irmao deste repo, carrega PII na
origem e nao pode ser premissa de suite.

O que estes testes travam sao as DUAS decisoes que, tomadas errado, produzem um NUMERO MAIOR em vez
de um erro: qual diretorio e' a fonte de cada agregador (D3) e se o feed esta fresco (D4). Nenhum
deles depende do relogio: `agora` e' injetado.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.vulnerabilidade import curadoria_agregadores as cur

AGORA = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)


def _escrever_csv(caminho: Path, linhas: int = 3, *, data_coleta: str = "2026-08-24") -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "slug": [f"academia-{i}" for i in range(linhas)],
            "nome": [f"Academia {i}" for i in range(linhas)],
            "latitude": [-23.55 - i * 0.01 for i in range(linhas)],
            "longitude": [-46.63 - i * 0.01 for i in range(linhas)],
            "uf": ["SP"] * linhas,
            "data_coleta": [data_coleta] * linhas,
        }
    ).to_csv(caminho, sep=";", encoding="utf-8-sig", index=False)


def _envelhecer(caminho: Path, dias: float, *, agora: datetime = AGORA) -> None:
    """Empurra o mtime do arquivo para `dias` atras de `agora` (nao mexe no relogio do sistema)."""
    alvo = agora.timestamp() - dias * 86400.0
    os.utime(caminho, (alvo, alvo))


def _envelhecer_conteudo(caminho: Path, dias: int, *, agora: datetime = AGORA) -> None:
    """Empurra a coluna `data_coleta` DENTRO do CSV, preservando o mtime.

    E' a regua PRIMARIA desde a emenda de 2026-08-25 a' DEC-038 -- e a razao de ela existir e'
    exatamente que as duas podem DIVERGIR: `split_by_state` reescreve os CSVs por UF em modo "w" ao
    fim de toda execucao, mesmo sem recoletar nada, o que rejuvenesce o mtime sem tocar o dado.
    """
    antes = caminho.stat()
    texto = caminho.read_text(encoding="utf-8-sig")
    alvo = (agora.date() - timedelta(days=dias)).isoformat()
    caminho.write_text(texto.replace("2026-08-24", alvo), encoding="utf-8-sig")
    os.utime(caminho, (antes.st_atime, antes.st_mtime))


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    """Clone sintetico do coletor: `TotalPass/csvs`, `Wellhub/csvs` e `Wellhub/csvs_musculacao`."""
    raiz = tmp_path / "gymscraping"
    _escrever_csv(raiz / "TotalPass" / "csvs" / "unidades_totalpass_sp.csv", linhas=4)
    _escrever_csv(raiz / "Wellhub" / "csvs" / "unidades_wellhub_sp.csv", linhas=9)
    _escrever_csv(raiz / "Wellhub" / "csvs_musculacao" / "unidades_wellhub_sp_musculacao.csv", 3)
    for arquivo in raiz.rglob("*.csv"):
        _envelhecer(arquivo, 1.0)
    return raiz


# --------------------------------------------------------------------------- #
# D3 - qual diretorio e' a fonte de cada agregador
# --------------------------------------------------------------------------- #
def test_totalpass_sempre_csvs(origem: Path) -> None:
    """O TotalPass nao tem escolha: o filtro de musculacao e' hardcoded no coletor."""
    diretorio, motivo = cur.escolher_diretorio_fonte(origem, "totalpass")
    assert diretorio == origem / "TotalPass" / "csvs"
    assert "hardcoded" in motivo


def test_wellhub_prefere_csvs_musculacao(origem: Path) -> None:
    """Com os dois presentes e o subset nao mais antigo, vence `csvs_musculacao/`.

    Os dois universos diferem por 2-3x (16.432 x 6.850 linhas, medido em SP): copiar `csvs/` por
    engano infla o universo do funil de M&A com academias sem musculacao, em silencio.
    """
    diretorio, motivo = cur.escolher_diretorio_fonte(origem, "wellhub")
    assert diretorio == origem / "Wellhub" / "csvs_musculacao"
    assert "musculacao" in motivo


def test_wellhub_sem_csvs_musculacao_usa_csvs(origem: Path) -> None:
    """Modo DEFAULT do coletor: com o filtro do pipeline ligado, `csvs/` ja' sai filtrado."""
    for arquivo in (origem / "Wellhub" / "csvs_musculacao").glob("*.csv"):
        arquivo.unlink()

    diretorio, motivo = cur.escolher_diretorio_fonte(origem, "wellhub")
    assert diretorio == origem / "Wellhub" / "csvs"
    assert "default" in motivo


def test_wellhub_musculacao_mais_antigo_levanta(origem: Path) -> None:
    """Mudanca de modo do coletor: escolher em silencio troca "erro" por "numero maior"."""
    for arquivo in (origem / "Wellhub" / "csvs_musculacao").glob("*.csv"):
        _envelhecer(arquivo, 40.0)

    with pytest.raises(ValueError, match="ambiguo"):
        cur.escolher_diretorio_fonte(origem, "wellhub")


def test_agregador_fora_do_contrato_levanta(origem: Path) -> None:
    """`unidades` NAO e' curado aqui: e' feed de cadeias, com cadencia semanal propria."""
    with pytest.raises(ValueError, match="fora do contrato"):
        cur.escolher_diretorio_fonte(origem, "unidades")


# --------------------------------------------------------------------------- #
# D4 - guarda de FRESCOR
# --------------------------------------------------------------------------- #
def test_feed_velho_nao_e_publicado(origem: Path, tmp_path: Path) -> None:
    """O defeito mais PROVAVEL do cron, nao o mais exotico.

    O snapshot mensal roda depois de ~21h de coleta. Se o coletor do WellHub morrer no meio da
    janela de 20h, os CSVs antigos ficam no disco -- e fotografa-los faz o `hash_campos_raspados`
    sair identico ao do mes anterior, `semanas_sem_mudanca` crescer sozinho e o S4 marcar o
    universo INTEIRO daquela fonte como "parado". Falso positivo em massa, com codigo de saida 0.
    """
    # Os DOIS diretorios do WellHub envelhecem junto: o coletor nao rodou, entao nada la' e' novo.
    # Envelhecer so' um deles cairia no ramo de AMBIGUIDADE de D3, que e' outro defeito.
    # Envelhece CONTEUDO e mtime: aqui as duas reguas concordam, e e' esse o caso comum.
    for arquivo in (origem / "Wellhub").rglob("*.csv"):
        _envelhecer_conteudo(arquivo, 30)
        _envelhecer(arquivo, 30.0)

    relatorio = cur.curar(origem, tmp_path / "destino", agora=AGORA, max_idade_dias=7)

    assert relatorio["fontes_publicadas"] == ["totalpass"]
    assert relatorio["wellhub"]["publicado"] is False
    assert "feed velho" in relatorio["wellhub"]["motivo_recusa"]
    assert relatorio["wellhub"]["idade_dias"] == pytest.approx(30.0, abs=0.1)
    # Recusar uma fonte NAO pode derrubar a outra: meia foto e' melhor que nenhuma, e a metade
    # que falta e' declarada pelo `fontes_lidas` do parquet.
    assert relatorio["totalpass"]["publicado"] is True
    assert (tmp_path / "destino" / "totalpass" / "csvs").is_dir()
    assert not (tmp_path / "destino" / "wellhub").exists()


def test_feed_no_limite_ainda_e_fresco(origem: Path, tmp_path: Path) -> None:
    """A borda e' INCLUSIVA: exatamente `max_idade_dias` ainda passa."""
    fresco, idade = cur.feed_esta_fresco(origem / "TotalPass" / "csvs", 1.0, AGORA)
    assert fresco is True
    assert idade == pytest.approx(1.0, abs=0.01)

    apertado, _ = cur.feed_esta_fresco(origem / "TotalPass" / "csvs", 0.5, AGORA)
    assert apertado is False


def test_diretorio_sem_csv_nunca_e_fresco(tmp_path: Path) -> None:
    """Diretorio vazio (ou ausente) nao pode passar por "fresco" por falta de evidencia."""
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    assert cur.feed_esta_fresco(vazio, 7.0, AGORA) == (False, None)
    assert cur.feed_esta_fresco(tmp_path / "nao_existe", 7.0, AGORA) == (False, None)
    assert cur.idade_do_feed(vazio, AGORA) == (None, cur.REGUA_INDISPONIVEL)


# --------------------------------------------------------------------------- #
# D4, emenda de 2026-08-25: a idade sai de `data_coleta`, NAO do mtime
# --------------------------------------------------------------------------- #
def test_idade_sai_da_data_coleta_e_nao_do_mtime(origem: Path) -> None:
    """O DEFEITO CENTRAL do critico 2, reproduzido: mtime fresco sobre conteudo velho.

    E' o estado medido no clone real em 2026-08-25: os 27 CSVs de `TotalPass/csvs/` tinham mtime de
    HOJE e `data_coleta = 2026-06-01` em 15.982 de 15.986 linhas -- 85 dias reportados como `0`. A
    causa e' o `split_by_state` do coletor, que reescreve cada arquivo de UF em modo "w" ao fim de
    TODA execucao, mesmo quando o checkpoint impediu qualquer recoleta.
    """
    csvs = origem / "TotalPass" / "csvs"
    for arquivo in csvs.glob("*.csv"):
        _envelhecer_conteudo(arquivo, 85)
        _envelhecer(arquivo, 0.0)  # mtime de AGORA: o feed "parece" recem-tocado

    idade, regua = cur.idade_do_feed(csvs, AGORA)
    assert regua == cur.REGUA_DATA_COLETA
    assert idade == pytest.approx(85.0), "a regua de mtime diria ~0 dia sobre o mesmo diretorio"

    fresco, _ = cur.feed_esta_fresco(csvs, 7.0, AGORA)
    assert fresco is False, "feed de 85 dias com mtime de hoje NAO pode passar por fresco"


def test_regua_cai_no_mtime_quando_data_coleta_falta(origem: Path) -> None:
    """Feed sem a coluna: o fallback existe, e ele DIZ que e' fallback."""
    csvs = origem / "TotalPass" / "csvs"
    for arquivo in csvs.glob("*.csv"):
        texto = arquivo.read_text(encoding="utf-8-sig")
        cabecalho, *corpo = texto.splitlines()
        colunas = cabecalho.split(";")
        indice = colunas.index("data_coleta")
        del colunas[indice]
        linhas_sem = [
            ";".join(c for i, c in enumerate(linha.split(";")) if i != indice) for linha in corpo
        ]
        arquivo.write_text("\n".join([";".join(colunas), *linhas_sem]), encoding="utf-8-sig")
        _envelhecer(arquivo, 3.0)

    idade, regua = cur.idade_do_feed(csvs, AGORA)
    assert regua == cur.REGUA_MTIME
    assert idade == pytest.approx(3.0, abs=0.01)


def test_regua_cai_no_mtime_quando_data_coleta_e_ilegivel(origem: Path) -> None:
    """Coluna presente mas com lixo: nao inventa data, cai no fallback e declara."""
    csvs = origem / "Wellhub" / "csvs_musculacao"
    for arquivo in csvs.glob("*.csv"):
        arquivo.write_text(
            arquivo.read_text(encoding="utf-8-sig").replace("2026-08-24", "31/02/2026"),
            encoding="utf-8-sig",
        )
        _envelhecer(arquivo, 2.0)

    idade, regua = cur.idade_do_feed(csvs, AGORA)
    assert regua == cur.REGUA_MTIME
    assert idade == pytest.approx(2.0, abs=0.01)


def test_regua_usada_vai_ao_relatorio(origem: Path, tmp_path: Path) -> None:
    """`regua_idade` por agregador: "3 dias" nunca pode ser um numero sem procedencia."""
    relatorio = cur.curar(origem, tmp_path / "destino", agora=AGORA, dry_run=True)
    for agregador in cur.AGREGADORES:
        assert relatorio[agregador]["regua_idade"] == cur.REGUA_DATA_COLETA


def test_data_coleta_lida_com_parser_csv_e_nao_por_split(tmp_path: Path) -> None:
    """`cut -d';'` desalinha em campo com `;` dentro de aspas -- foi medido no clone real."""
    caminho = tmp_path / "csvs" / "unidades_totalpass_sp.csv"
    caminho.parent.mkdir(parents=True)
    caminho.write_text(
        "slug;nome;endereco_formatado;data_coleta\n"
        'a-1;Academia 1;"Rua X, 01, Anapolis - GO, 75091-170";2026-08-20\n'
        'a-2;Academia 2;"Av. Y; sala 3, Uberlandia - MG";2026-08-22\n',
        encoding="utf-8-sig",
    )
    idade, regua = cur.idade_do_feed(caminho.parent, AGORA)
    assert regua == cur.REGUA_DATA_COLETA
    assert idade == pytest.approx(3.0), "leu a data mais NOVA, sem se perder no `;` entre aspas"


def test_piso_relativo_barra_coleta_que_morreu_na_metade(origem: Path, tmp_path: Path) -> None:
    """O teto pega universo que INFLA; o piso pega coleta que morreu no meio.

    Sem piso, CSVs frescos com metade das linhas passam -- e as linhas que faltam viram
    `sumiu_recente` em massa no S1, que e' o sinal de MAIOR peso.
    """
    destino = tmp_path / "destino"
    # Baseline: 20 linhas ja' publicadas no mes anterior.
    _escrever_csv(destino / "wellhub" / "csvs" / "unidades_wellhub_sp_musculacao.csv", linhas=20)

    relatorio = cur.curar(origem, destino, agora=AGORA)  # a origem tem 3 linhas (15%)

    assert relatorio["wellhub"]["publicado"] is False
    assert "ABAIXO do piso" in relatorio["wellhub"]["motivo_recusa"]
    assert relatorio["wellhub"]["n_linhas_publicadas_antes"] == 20
    assert relatorio["fontes_publicadas"] == ["totalpass"], "recusa de uma nao derruba a outra"


def test_piso_e_inerte_sem_baseline_e_desligavel(origem: Path, tmp_path: Path) -> None:
    """Primeira execucao NAO pode ser barrada pelo piso: nao ha' com o que comparar."""
    relatorio = cur.curar(origem, tmp_path / "primeira", agora=AGORA, dry_run=True)
    assert relatorio["fontes_publicadas"] == ["totalpass", "wellhub"]
    for agregador in cur.AGREGADORES:
        assert relatorio[agregador]["n_linhas_publicadas_antes"] == 0

    destino = tmp_path / "destino"
    _escrever_csv(destino / "wellhub" / "csvs" / "unidades_wellhub_sp_musculacao.csv", linhas=20)
    solto = cur.curar(origem, destino, agora=AGORA, piso_relativo=0.0, dry_run=True)
    assert "wellhub" in solto["fontes_publicadas"], "`--piso-relativo 0` tem de desligar a guarda"


def test_curadoria_e_tudo_ou_nada_quando_a_decisao_levanta(origem: Path, tmp_path: Path) -> None:
    """Ambiguidade do WellHub NAO pode deixar o TotalPass ja' publicado no destino.

    A ordem canonica poe `totalpass` primeiro; no laco unico anterior ele ja' tinha sido COPIADO
    quando a excecao do `wellhub` subia, e o destino ficava com meia curadoria de um mes novo
    enquanto o wrapper abortava.
    """
    # Estado ambiguo de D3: `csvs_musculacao/` estritamente mais antigo que `csvs/`.
    for arquivo in (origem / "Wellhub" / "csvs_musculacao").glob("*.csv"):
        _envelhecer(arquivo, 10.0)

    destino = tmp_path / "destino"
    with pytest.raises(ValueError, match="ambiguo"):
        cur.curar(origem, destino, agora=AGORA)

    assert not destino.exists(), "a excecao de decisao alcancou o disco de destino"


def test_limite_de_linhas_barra_universo_inflado(origem: Path, tmp_path: Path) -> None:
    """Universo que dobra costuma ser troca de modo do coletor, nao crescimento real."""
    relatorio = cur.curar(
        origem,
        tmp_path / "destino",
        agora=AGORA,
        limites={"wellhub": 2},
    )

    assert relatorio["fontes_publicadas"] == ["totalpass"]
    assert "volume acima do limite" in relatorio["wellhub"]["motivo_recusa"]
    assert relatorio["wellhub"]["n_linhas"] == 3


# --------------------------------------------------------------------------- #
# Publicacao: destino, contagens e o que ela NAO faz
# --------------------------------------------------------------------------- #
def test_destino_em_minusculo(origem: Path, tmp_path: Path) -> None:
    """O destino e' `DIR_WELLHUB_DEFAULT`/`DIR_TOTALPASS_DEFAULT` do snapshot -- em MINUSCULO.

    A origem e' `Wellhub/`/`TotalPass/` (caixa exata, exigida no Linux); o destino e'
    `wellhub/csvs/`/`totalpass/csvs/`. Trocar as duas caixas faz o glob do snapshot nao casar com
    nada e o dry-run devolver `linhas_snapshot = 0` SEM erro nenhum.
    """
    from motor_expansao.vulnerabilidade import snapshots as snap

    destino = tmp_path / "destino"
    cur.curar(origem, destino, agora=AGORA)

    assert (destino / "wellhub" / "csvs").is_dir()
    assert (destino / "totalpass" / "csvs").is_dir()
    # E a arvore criada e' EXATAMENTE a que o snapshot procura sob o mount. Os defaults do
    # snapshot sao relativos a raiz do container (`concorrentes/<fonte>/csvs`), e o wrapper monta
    # `HOST_AGREGADORES` justamente em `/app/concorrentes` -- logo o `destino` faz o papel do
    # primeiro componente, e o que tem de casar sao os componentes seguintes.
    assert snap.DIR_WELLHUB_DEFAULT.parts[1:] == ("wellhub", "csvs")
    assert snap.DIR_TOTALPASS_DEFAULT.parts[1:] == ("totalpass", "csvs")
    for agregador in cur.AGREGADORES:
        assert (destino / agregador / "csvs").is_dir()


def test_dry_run_nao_copia(origem: Path, tmp_path: Path) -> None:
    """Modo seco decide e relata, sem criar diretorio nem copiar byte."""
    destino = tmp_path / "destino"
    relatorio = cur.curar(origem, destino, agora=AGORA, dry_run=True)

    assert relatorio["fontes_publicadas"] == ["totalpass", "wellhub"]
    assert relatorio["dry_run"] is True
    assert not destino.exists(), "dry-run criou diretorio no destino"


def test_relatorio_traz_contagem_por_agregador(origem: Path, tmp_path: Path) -> None:
    """A contagem e' diagnostico de volume: sem ela, "publicou" nao distingue 9 linhas de 0."""
    relatorio = cur.curar(origem, tmp_path / "destino", agora=AGORA)

    assert relatorio["totalpass"]["n_arquivos"] == 1
    assert relatorio["totalpass"]["n_linhas"] == 4
    assert relatorio["wellhub"]["n_arquivos"] == 1
    assert relatorio["wellhub"]["n_linhas"] == 3, "contou `csvs/` (9) no lugar do subset (3)"
    assert relatorio["fontes_publicadas"] == ["totalpass", "wellhub"]


def test_nao_apaga_csv_existente_no_destino(origem: Path, tmp_path: Path) -> None:
    """Copia POR CIMA, nunca espelho.

    Um CSV de UF que sumiu do coletor e' sintoma de coleta parcial muito mais vezes do que de
    universo que encolheu -- mesma direcao segura do "nunca reduzir" do sync de concorrentes.
    """
    destino = tmp_path / "destino"
    orfao = destino / "wellhub" / "csvs" / "unidades_wellhub_ba.csv"
    _escrever_csv(orfao, linhas=2)

    cur.curar(origem, destino, agora=AGORA)

    assert orfao.exists(), "a curadoria apagou um CSV que o coletor deixou de emitir"
    assert (destino / "wellhub" / "csvs" / "unidades_wellhub_sp_musculacao.csv").exists()


def test_copia_preserva_o_mtime(origem: Path, tmp_path: Path) -> None:
    """O mtime e' o FALLBACK da guarda de frescor do mes seguinte.

    Desde a emenda de 2026-08-25 a' DEC-038 a regua primaria e' `data_coleta`, que viaja DENTRO do
    arquivo e nao depende disto. Mas o fallback continua valendo para feed sem data legivel, e com
    `shutil.copy` puro (sem `2`) ele pareceria recem-coletado para sempre.
    """
    destino = tmp_path / "destino"
    cur.curar(origem, destino, agora=AGORA)

    original = origem / "TotalPass" / "csvs" / "unidades_totalpass_sp.csv"
    copia = destino / "totalpass" / "csvs" / "unidades_totalpass_sp.csv"
    assert copia.stat().st_mtime == pytest.approx(original.stat().st_mtime, abs=1.0)


def test_diretorio_ausente_recusa_sem_levantar(tmp_path: Path) -> None:
    """Clone sem os diretorios do coletor recusa as duas fontes -- e nao derruba a execucao."""
    relatorio = cur.curar(tmp_path / "vazio", tmp_path / "destino", agora=AGORA)

    assert relatorio["fontes_publicadas"] == []
    for agregador in cur.AGREGADORES:
        assert relatorio[agregador]["publicado"] is False
        assert "nenhum CSV" in relatorio[agregador]["motivo_recusa"]


# --------------------------------------------------------------------------- #
# CLI - o contrato de UMA LINHA entre o modulo e o wrapper de cron
# --------------------------------------------------------------------------- #
def test_cli_defaults() -> None:
    args = cur._parse_args([])
    assert args.origem == cur.ORIGEM_DEFAULT
    assert args.destino == cur.DESTINO_DEFAULT
    assert args.max_idade_dias == cur.MAX_IDADE_DIAS_DEFAULT
    assert args.max_linhas_wellhub is None
    assert args.max_linhas_totalpass is None
    assert args.piso_relativo == cur.PISO_RELATIVO_DEFAULT
    assert args.dry_run is False


def test_main_imprime_fontes_publicadas_em_formato_fixo(
    origem: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O shell le ESTA linha com `grep`/`cut`; nunca o dicionario Python, que muda de forma."""
    rc = cur.main(
        [
            "--origem",
            str(origem),
            "--destino",
            str(tmp_path / "destino"),
            "--max-idade-dias",
            "7",
            "--dry-run",
        ]
    )
    assert rc == 0
    linhas = capsys.readouterr().out.strip().splitlines()
    assert linhas[-1] == "fontes_publicadas=totalpass,wellhub"


def test_main_com_tudo_velho_imprime_a_linha_vazia(
    origem: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nenhuma fonte publicada imprime a linha VAZIA e sai 0.

    Quem decide que "nada fresco" e' falha e' o WRAPPER -- este modulo so' relata. Se o modulo
    saisse != 0 aqui, uma recusa legitima de UMA fonte ficaria indistinguivel de um erro de
    execucao, e o wrapper perderia a capacidade de seguir com meia foto.
    """
    agora_real = datetime.now(tz=UTC)
    for arquivo in origem.rglob("*.csv"):
        _envelhecer_conteudo(arquivo, 400, agora=agora_real)
        _envelhecer(arquivo, 400.0, agora=agora_real)

    rc = cur.main(["--origem", str(origem), "--destino", str(tmp_path / "destino"), "--dry-run"])

    assert rc == 0, "recusa por frescor nao pode virar erro de execucao"
    linhas = capsys.readouterr().out.strip().splitlines()
    assert linhas[-1] == "fontes_publicadas="


def test_modulo_nao_importa_o_m1_nem_dashboard() -> None:
    """Pacote DISJUNTO: a curadoria roda dentro da imagem da API, mas nao pode arrastar o M1."""
    from .._ast_imports import casa_proibicao, nomes_importados

    for n in nomes_importados(cur):
        assert "pipelines" not in n, n
        assert "censo" not in n, n
        assert "normalizar_concorrentes" not in n, n
        for proibido in (
            "motor_expansao.dashboard",
            "motor_expansao.api",
            "motor_expansao.config",
        ):
            assert not casa_proibicao(n, proibido), (n, proibido)
