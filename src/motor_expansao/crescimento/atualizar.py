"""Orquestra a atualizacao da camada de crescimento: CAGED -> cadeia 01..10 ->
validacao -> publicacao atomica.

Por que um orquestrador, e nao "rode os scripts na mao": os quatro gotchas do
README dos geradores custaram tempo real e TODOS produzem artefato plausivel e
errado sem erro na tela — `03` sozinho mutila, `09` duas vezes acumula o acumulado,
`08` depois do `10` apaga o periodo, rodada parcial perde o veredito. Aqui a ordem
canonica vive num lugar SO', a falha de qualquer passo aborta a rodada inteira e o
que chega ao staging passou pelo portao do `validar.py`.

Duas decisoes de desenho que nao sao obvias:

1. **A cadeia roda num MOTOR_DATA_DIR de RASCUNHO**, nunca no staging vivo. Os
   scripts 03..10 MUTAM `staging/crescimento_municipal.parquet` em sequencia; rodar
   sobre o staging que o piloto serve deixaria o web lendo artefato meio-escrito por
   minutos (a mesma janela de truncamento que o runbook de publicacao mata com o
   rename atomico). O rascunho recebe um espelho de `outputs/` (so' o que o `03` le)
   e, no fim, SO' os dois parquets validados atravessam para o staging real, por
   `.tmp` + `os.replace`.

2. **Os scripts sao COPIADOS para um diretorio de trabalho.** `_raizes.TRABALHO`
   ancora os intermediarios na pasta dos scripts; rodar direto no checkout da VPS
   sujaria a arvore git (a licao do wrapper dos agregadores: nunca escrever dentro
   de um clone versionado). O `_eixo_trajetoria.parquet` — insumo do projeto irmao
   `poc_satelite`, que NAO e' gerado pela cadeia — e' copiado junto.

Exit codes: 0 ok · 1 insumo/ambiente faltando (SystemExit com mensagem acionavel) ·
3 cadeia falhou · 4 validacao reprovou · 5 publicacao falhou (staging pode ter ficado
PARCIAL — ver `publicar`). O wrapper distingue o 5 no texto do aviso.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

from motor_expansao.crescimento import caged, validar

#: Ordem OBRIGATORIA (README dos geradores): rodar parcial ou fora de ordem produz
#: artefato silenciosamente errado. O `10` vem por ultimo porque o `08` reescreve
#: `cres_dims` sem o periodo.
ORDEM_SCRIPTS = [
    "01_municipal.py",
    "02_enriquecer.py",
    "03_artefato.py",
    "04_dimensoes.py",
    "05_veredito.py",
    "06_encode_dims.py",
    "07_series.py",
    "08_populacao_e_hex.py",
    "09_nivel.py",
    "10_periodo.py",
]

#: O que o rascunho precisa espelhar de `outputs/` (leitura do `03_artefato.py`).
OUTPUTS_LIDOS = ["carteira_expansao_acionavel.parquet"]

ARTEFATO_MUNICIPAL = "crescimento_municipal.parquet"
ARTEFATO_HEX = "crescimento_hex.parquet"

#: Meses pt-BR para o periodo do aviso (abreviacoes sem acento — mar/marco cabe).
_MES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

#: Timeout generoso por script: a cadeia inteira mede minutos, nao horas; um passo
#: pendurado por mais de 1h e' falha, nao lentidao.
TIMEOUT_SCRIPT_S = 3600


def _competencia_legivel(comp: str) -> str:
    return f"{_MES_PT[int(comp[4:6]) - 1]}/{comp[:4]}"


def _raizes_do_ambiente() -> dict[str, Path]:
    """As 4 raizes de dados, TODAS por env — fail-closed com mensagem acionavel."""
    faltando = [
        v
        for v in ("MOTOR_DATA_DIR", "SOCIOECONOMICO_DIR", "CRESCIMENTO_TEC_DIR", "POC_SATELITE_DIR")
        if not os.environ.get(v)
    ]
    if faltando:
        raise SystemExit(
            "variaveis de ambiente ausentes: " + ", ".join(faltando)
            + "\n  (as 4 raizes de `data/reports/crescimento/_raizes.py`; ver o README de la')"
        )
    return {
        "MOTOR": Path(os.environ["MOTOR_DATA_DIR"]),
        "SOCIO": Path(os.environ["SOCIOECONOMICO_DIR"]),
        "TEC": Path(os.environ["CRESCIMENTO_TEC_DIR"]),
        "POC": Path(os.environ["POC_SATELITE_DIR"]),
    }


def preparar_trabalho(scripts_dir: Path, eixo: Path, trabalho: Path) -> None:
    """Copia a cadeia + `_raizes.py` + o eixo do satelite para o diretorio de trabalho."""
    faltam = [n for n in [*ORDEM_SCRIPTS, "_raizes.py"] if not (scripts_dir / n).exists()]
    if faltam:
        raise SystemExit(f"scripts da cadeia ausentes em {scripts_dir}: {faltam}")
    if not eixo.exists():
        raise SystemExit(
            f"falta o insumo do satelite: {eixo}\n"
            "  `_eixo_trajetoria.parquet` vem do projeto irmao poc_satelite e NAO e' "
            "gerado pela cadeia (README dos geradores)."
        )
    trabalho.mkdir(parents=True, exist_ok=True)
    for nome in [*ORDEM_SCRIPTS, "_raizes.py"]:
        shutil.copy2(scripts_dir / nome, trabalho / nome)
    shutil.copy2(eixo, trabalho / "_eixo_trajetoria.parquet")


def preparar_rascunho_motor(motor_real: Path, rascunho: Path) -> None:
    """Espelha em `rascunho` o minimo de `outputs/` que a cadeia le."""
    (rascunho / "staging").mkdir(parents=True, exist_ok=True)
    (rascunho / "outputs").mkdir(parents=True, exist_ok=True)
    for nome in OUTPUTS_LIDOS:
        origem = motor_real / "outputs" / nome
        if not origem.exists():
            raise SystemExit(f"outputs/ real sem {nome} (o 03_artefato.py precisa dele)")
        shutil.copy2(origem, rascunho / "outputs" / nome)


def rodar_cadeia(trabalho: Path, rascunho_motor: Path) -> None:
    """Roda 01..10 na ordem, abortando no primeiro erro (exit 3)."""
    env = dict(os.environ)
    env["MOTOR_DATA_DIR"] = str(rascunho_motor)
    for nome in ORDEM_SCRIPTS:
        t0 = time.monotonic()
        print(f">> {nome}", flush=True)
        proc = subprocess.run(
            [sys.executable, str(trabalho / nome)],
            cwd=trabalho,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SCRIPT_S,
        )
        if proc.returncode != 0:
            print(proc.stdout[-4000:])
            print(proc.stderr[-4000:], file=sys.stderr)
            raise SystemExit(3)
        print(f"   ok em {time.monotonic() - t0:.0f}s", flush=True)


def _contagem_vereditos(parquet: Path) -> dict[str, int]:
    """Contagem de `v_classe` para o antes->depois do aviso; {} se nao der.

    O artefato ANTERIOR pode ser mutilado (sem `v_classe` — foi exatamente assim que
    a camada quebrou uma vez) ou ilegivel: nada disso pode derrubar a rodada que vai
    consertar o problema, entao aqui e' tolerante em vez de estrito.
    """
    if not parquet.exists():
        return {}
    try:
        df = pd.read_parquet(parquet, columns=["v_classe"])
    except (OSError, KeyError, ValueError):
        return {}
    return {str(k): int(v) for k, v in df["v_classe"].value_counts(dropna=False).items()}


def publicar(rascunho_staging: Path, staging_real: Path) -> None:
    """Atravessa os dois parquets validados por `.tmp` + rename atomico.

    Em DUAS fases de proposito: primeiro TODAS as copias (a parte lenta e falivel —
    disco cheio, I/O), depois os dois `os.replace` seguidos (rapidos). Uma falha na
    fase de copia deixa o staging 100% intacto; a unica janela de estado parcial
    (municipal novo + hex velho) e' entre os dois renames — microssegundos, nao a
    duracao de uma copia.
    """
    staging_real.mkdir(parents=True, exist_ok=True)
    prontos: list[tuple[Path, Path]] = []
    for nome in (ARTEFATO_MUNICIPAL, ARTEFATO_HEX):
        destino = staging_real / nome
        tmp = destino.with_suffix(destino.suffix + f".tmp-{os.getpid()}")
        shutil.copy2(rascunho_staging / nome, tmp)
        # 0644 explicito (runbook §4 passo 3): o job roda como root e o container do
        # web le como appuser non-root — um umask restritivo aqui apagaria a camada
        # inteira da tela, sem erro no job. `chmod` antes do rename: o artefato ja'
        # nasce legivel no instante em que aparece.
        os.chmod(tmp, 0o644)
        prontos.append((tmp, destino))
    for tmp, destino in prontos:
        os.replace(tmp, destino)
        print(f">> publicado {destino}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--scripts-dir", type=Path, required=True,
        help="pasta com a cadeia 01..10 + _raizes.py (ex.: data/reports/crescimento do checkout)",
    )
    ap.add_argument(
        "--eixo", type=Path, default=None,
        help="_eixo_trajetoria.parquet (default: <scripts-dir>/_eixo_trajetoria.parquet)",
    )
    ap.add_argument("--pular-caged", action="store_true", help="nao baixar meses novos do CAGED")
    ap.add_argument("--sem-publicar", action="store_true", help="gera e valida, sem tocar o staging real")
    ap.add_argument("--resumo", type=Path, default=None, help="onde gravar o resumo JSON (p/ o aviso)")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    raizes = _raizes_do_ambiente()
    eixo = args.eixo or (args.scripts_dir / "_eixo_trajetoria.parquet")
    consolidado = caged.resolver_consolidado(raizes["SOCIO"] / "caged")

    meses_novos: list[str] = []
    if not args.pular_caged:
        meses_novos = caged.atualizar(consolidado)
    competencias = caged.competencias_existentes(consolidado)
    if not competencias:
        # Com --pular-caged (modo seco) o erro acionavel de `caged.atualizar` nao
        # roda — sem esta guarda, consolidado ausente viraria IndexError cru.
        raise SystemExit(
            f"consolidado do CAGED ausente ou vazio: {consolidado}\n"
            "  O repasse inicial de insumos nao foi feito (docs/repasse_cron_crescimento.md)."
        )
    ultima = competencias[-1]

    with tempfile.TemporaryDirectory(prefix="crescimento_") as tmp:
        trabalho = Path(tmp) / "cadeia"
        rascunho_motor = Path(tmp) / "motor"
        preparar_trabalho(args.scripts_dir, eixo, trabalho)
        preparar_rascunho_motor(raizes["MOTOR"], rascunho_motor)
        rodar_cadeia(trabalho, rascunho_motor)

        rascunho_staging = rascunho_motor / "staging"
        erros = validar.validar_par(
            rascunho_staging / ARTEFATO_MUNICIPAL, rascunho_staging / ARTEFATO_HEX
        )
        if erros:
            for e in erros:
                print(f"FALHA: {e}", file=sys.stderr)
            print("nada publicado: o staging real segue com o artefato anterior.")
            return 4
        # A mesma frase do CLI de `validar` — e' o que o repasse manda o operador
        # conferir na saida do modo seco.
        print("artefatos integros (colunas consumidas, dominios e cobertura OK)")

        staging_real = raizes["MOTOR"] / "staging"
        antes = _contagem_vereditos(staging_real / ARTEFATO_MUNICIPAL)
        depois = _contagem_vereditos(rascunho_staging / ARTEFATO_MUNICIPAL)
        municipal = pd.read_parquet(rascunho_staging / ARTEFATO_MUNICIPAL)
        hexes = pd.read_parquet(rascunho_staging / ARTEFATO_HEX, columns=["hex_id"])

        if args.sem_publicar:
            print(">> --sem-publicar: artefatos validados ficaram so' no rascunho")
        else:
            try:
                publicar(rascunho_staging, staging_real)
            except OSError as exc:
                print(f"FALHA na publicacao: {exc}", file=sys.stderr)
                return 5

    resumo = {
        "ok": True,
        "meses_caged_novos": meses_novos,
        "emprego_ate": _competencia_legivel(ultima),
        "municipios": int(len(municipal)),
        "hexes": int(len(hexes)),
        "colunas_municipal": int(len(municipal.columns)),
        "vereditos_antes": antes,
        "vereditos_depois": depois,
        "publicado": not args.sem_publicar,
        "duracao_s": round(time.monotonic() - t0, 1),
    }
    if args.resumo:
        args.resumo.parent.mkdir(parents=True, exist_ok=True)
        args.resumo.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
