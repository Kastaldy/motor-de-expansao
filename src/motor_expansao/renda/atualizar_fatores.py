"""Gera uma NOVA versao do arquivo de fatores de renda a partir da PNAD Continua anual.

Uso:
    python -m motor_expansao.renda.atualizar_fatores --pais BR --ano-base 2022 --ano-alvo 2025 \\
        [--aprovar-uf PE ...] [--ponte-ipca] [--cache-dir DIR] [--saida-dir DIR]

O que faz, em ordem:
1. lista o FTP do IBGE e casa as 4 amostras (ano base/alvo x visitas 1 e 5) por regex;
2. baixa ou reusa o cache (sha256 no manifesto) e extrai as colunas pelo layout;
3. CALCULA os fatores so' dos microdados (`motor_expansao.renda.pnad`): mesma visita,
   media geometrica v1/v5, nacional do Brasil inteiro;
4. avalia a regra de excecao por UF e aceita `--aprovar-uf` SO' para UF candidata;
5. CONFERE o nivel de cada ano contra a SIDRA 7531 na visita que a tabela usa naquele ano
   (`visita_sidra`, parametro declarado e gravado). A conferencia devolve so' erros; se algum
   passar de 0,5% por UF, aborta. **Nada da 7531 entra no fator** — nunca se calcula
   crescimento pela 7531 (ela mistura visitas: v5 em 2022, v1 em 2025);
6. grava `fatores/<PAIS>/<AAAA-MM>_pnad<ano_alvo>_vN.json` (ou em `--saida-dir`) e um
   relatorio de mudanca `.md` ao lado. **Nao troca o VIGENTE**: virar a versao e' ato humano.

Modo offline (`--offline`): casa as amostras pelos nomes do `--cache-dir` e le a 7531 (e o
IPCA) de arquivos JSON locais (`--sidra-7531-json`, `--ipca-json`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from motor_expansao.renda import pnad, sidra

FATORES_DIR_PADRAO = Path(__file__).resolve().parent / "fatores"
CACHE_DIR_PADRAO = Path.home() / ".cache" / "motor_expansao" / "pnad"
LIMIAR_ALERTA_DELTA = 0.10


class AtualizacaoAbortada(SystemExit):
    def __init__(self, mensagem: str) -> None:
        super().__init__(f"[atualizar_fatores] {mensagem}")
        self.mensagem = mensagem


# ---------------------------------------------------------------------------
# Versao vigente e nome da nova versao
# ---------------------------------------------------------------------------


def ler_vigente(fatores_dir: Path, pais: str) -> dict[str, Any]:
    d = Path(fatores_dir) / pais
    vig = d / "VIGENTE"
    if not vig.exists():
        raise AtualizacaoAbortada(f"sem {vig}: o pais precisa de uma versao vigente para herdar")
    nome = vig.read_text(encoding="utf-8").strip()
    arq = d / f"{nome}.json"
    if not nome or not arq.exists():
        raise AtualizacaoAbortada(f"VIGENTE aponta para {nome!r}, mas {arq} nao existe")
    dados = json.loads(arq.read_text(encoding="utf-8"))
    for chave in (
        "versao",
        "ano_base_renda",
        "data_referencia_base",
        "nacional",
        "artefatos_obrigatorios",
        "artefato_k_obrigatorio",
    ):
        if chave not in dados:
            raise AtualizacaoAbortada(f"versao vigente {nome} sem a chave {chave!r}")
    return dados


def proxima_versao(prefixo_mes: str, ano_alvo: int, diretorios: Sequence[Path]) -> str:
    padrao = re.compile(rf"^\d{{4}}-\d{{2}}_pnad{ano_alvo}_v(\d+)\.json$")
    usados = [0]
    for d in diretorios:
        if Path(d).is_dir():
            usados += [int(m.group(1)) for p in Path(d).iterdir() if (m := padrao.match(p.name))]
    return f"{prefixo_mes}_pnad{ano_alvo}_v{max(usados) + 1}"


def fator_efetivo(versao: Mapping[str, Any], uf: str, tipo: str) -> float:
    exc = versao.get("excecoes_aprovadas") or {}
    if uf in exc:
        return float(exc[uf][tipo])
    return float(versao["nacional"][tipo])


# ---------------------------------------------------------------------------
# Montagem do arquivo de versao
# ---------------------------------------------------------------------------


def _fmt(x: float, casas: int = 4) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def _rotulo_referencia(ano_alvo: int, nac: Mapping[str, float]) -> str:
    """`rotulo_referencia` da versao (vira o `data_referencia_renda` do resultado do ponto)."""
    return (
        f"{ano_alvo} (PNAD Contínua; Censo jul/2022 x {_fmt(nac['per_capita'])} per capita, "
        f"x {_fmt(nac['domiciliar'])} domiciliar)"
    )


def _arquivos_fonte(insumos: pnad.Insumos) -> list[dict[str, Any]]:
    out = []
    for (ano, visita), (zc, lc) in sorted(insumos.arquivos.items()):
        for papel, a in (("microdados", zc), ("layout", lc)):
            out.append(
                {
                    "ano": ano,
                    "visita": visita,
                    "papel": papel,
                    "nome": a.nome,
                    "url": a.url,
                    "data_arquivo": a.data_arquivo,
                    "sha256": a.sha256,
                    "bytes": a.bytes,
                }
            )
    return out


def montar_versao(
    *,
    pais: str,
    versao: str,
    data_extracao: date,
    calc: pnad.FatoresCalculados,
    regra: list[dict],
    limiar: float,
    n_min: int,
    aprovadas: Sequence[str],
    vigente: Mapping[str, Any],
    arquivos_fonte: list[dict[str, Any]],
    conferencia: Mapping[str, Any],
    visita_sidra: Mapping[int, int],
    url_7531: str,
    ponte: Mapping[str, Any] | None,
) -> dict[str, Any]:
    cand = [r for r in regra if r["atende"]]
    por_uf = {r["uf"]: r for r in cand}
    excecoes: dict[str, Any] = {}
    for uf in sorted(aprovadas):
        r = por_uf[uf]
        excecoes[uf] = {
            "per_capita": r["per_capita"],
            "domiciliar": r["domiciliar"],
            "moradores": r["moradores"],
            "evidencia": (
                f"regra de excecao (limiar {limiar:.0%}, n_min {n_min}): desvio per capita contra o "
                f"nacional da mesma visita {r['desvio_pc_v1']:+.2%} (v1) e {r['desvio_pc_v5']:+.2%} (v5), "
                f"mesmo sinal; menor amostra {r['n_min_amostras']} pessoas; aprovada via --aprovar-uf "
                f"em {data_extracao.isoformat()}"
            ),
        }
    nac = calc.nacional
    rotulo_ref = _rotulo_referencia(calc.ano_alvo, nac)
    campos_candidata = (
        "uf",
        "desvio_pc_v1",
        "desvio_pc_v5",
        "desvio_dom_v1",
        "desvio_dom_v5",
        "menor_desvio_abs",
        "n_min_amostras",
        "per_capita",
        "domiciliar",
        "moradores",
    )
    return {
        "versao": versao,
        "pais": pais,
        "ano_base_renda": vigente["ano_base_renda"],
        "data_referencia_base": vigente["data_referencia_base"],
        "ano_alvo": calc.ano_alvo,
        "fonte": {
            "pesquisa": "PNAD Contínua anual (IBGE), visitas 1 e 5",
            "gerado_por": "python -m motor_expansao.renda.atualizar_fatores",
            "ano_base_pnad": calc.ano_base,
            "ano_alvo_pnad": calc.ano_alvo,
            "arquivos": arquivos_fonte,
            "variaveis": {
                "per_capita": pnad.VAR_PC,
                "domiciliar": pnad.VAR_DOM,
                "moradores": pnad.VAR_MORADORES,
                "peso": pnad.PESO,
                "domicilio": f"V2005 == '{pnad.COND_RESPONSAVEL}'",
                "universo": f"pessoas com {pnad.VAR_PC} nao nulo",
            },
            "fatores_por_visita": {
                g: {k: v for k, v in f.items()} for g, f in sorted(calc.fatores.items())
            },
            "niveis": {
                f"{a}v{v}": {g: dict(n) for g, n in sorted(niv.items())}
                for (a, v), niv in sorted(calc.niveis.items())
            },
            "tabela_sidra_conferencia": {
                "tabela": sidra.TABELA_7531,
                "variavel": sidra.VARIAVEL_7531,
                "classe": f"{sidra.CLASSE_TOTAL} (Total)",
                "url": url_7531,
                "tolerancia_por_uf": sidra.TOLERANCIA_NIVEL,
                "uso": "so' conferencia do NIVEL de cada ano na visita declarada; nunca entra no fator",
                "erros": conferencia,
            },
            "ponte_ipca": dict(ponte) if ponte else None,
            "regra_avaliacao_ufs": [
                {k: r[k] for k in (*campos_candidata, "mesmo_sinal", "atende")} for r in regra
            ],
        },
        "data_extracao": data_extracao.isoformat(),
        "metodo": (
            "fator = nivel(ano alvo, visita X) / nivel(ano base, mesma visita X), media geometrica "
            "das visitas 1 e 5; nivel = media ponderada por V1032; per capita VD5008 (pessoas com "
            "VD5008), domiciliar VD5007 e moradores VD2003 no registro V2005=='01'; nacional = Brasil "
            "inteiro"
        ),
        "nacional": dict(nac),
        "regra_excecao": {
            "variavel": "per_capita",
            "limiar": limiar,
            "n_min": n_min,
            "comparacao": "estrita (menor |desvio| > limiar); n_min >= (contagem de linhas de pessoas com renda, menor das 4 amostras)",
            "criterio": "desvio contra o nacional da MESMA visita, mesmo sinal nas visitas 1 e 5",
            # desvios das candidatas (a lista `candidatas_regra` e' so' de UFs, contrato do loader)
            "candidatas_detalhe": {
                r["uf"]: {k: r[k] for k in campos_candidata if k != "uf"} for r in cand
            },
        },
        "candidatas_regra": [r["uf"] for r in cand],
        "excecoes_aprovadas": excecoes,
        "ponte_ipca": float(ponte["valor"]) if ponte else None,
        "dec": None,
        "aprovado_por": None,
        "relatorio": None,
        "rotulo_referencia": rotulo_ref,
        "artefatos_obrigatorios": list(vigente["artefatos_obrigatorios"]),
        "artefato_k_obrigatorio": bool(vigente["artefato_k_obrigatorio"]),
        "visita_sidra": {str(a): int(v) for a, v in sorted(visita_sidra.items())},
    }


# ---------------------------------------------------------------------------
# Relatorio de mudanca
# ---------------------------------------------------------------------------


def _pct(x: float, casas: int = 2) -> str:
    return f"{x * 100:+.{casas}f}%".replace(".", ",")


def montar_relatorio(
    nova: Mapping[str, Any],
    vigente: Mapping[str, Any],
    calc: pnad.FatoresCalculados,
    regra: list[dict],
    n_min: int,
) -> str:
    nac = nova["nacional"]
    linhas = [
        f"# Relatório de mudança — fatores de renda {nova['versao']}",
        "",
        f"- País: {nova['pais']} · ano base {calc.ano_base} · ano alvo {calc.ano_alvo}",
        f"- Versão vigente comparada: `{vigente['versao']}`",
        f"- Gerado em {nova['data_extracao']}. **O VIGENTE não foi alterado.**",
        "",
        "## Fatores nacionais (Brasil inteiro, média geométrica das visitas 1 e 5)",
        "",
        "| tipo | visita 1 | visita 5 | fator | vigente | variação |",
        "|---|---|---|---|---|---|",
    ]
    br = calc.fatores["BR"]
    alertas: list[str] = []
    for tipo, chave in (("per_capita", "pc"), ("domiciliar", "dom"), ("moradores", "mor")):
        novo = nac[tipo]
        velho = float(vigente["nacional"][tipo])
        delta = novo / velho - 1
        linhas.append(
            f"| {tipo} | {br[f'{chave}_v1']:.6f} | {br[f'{chave}_v5']:.6f} | **{novo:.8f}** | {velho:.4f} | {_pct(delta)} |"
        )
    linhas += ["", "## Regra de exceção por UF", ""]
    rx = nova["regra_excecao"]
    linhas.append(
        f"Limiar {rx['limiar']:.0%} (estrito), amostra mínima {rx['n_min']} pessoas com renda em cada uma "
        "das 4 amostras, mesmo sinal nas duas visitas, contra o nacional da mesma visita."
    )
    linhas += [
        "",
        "| UF | desvio pc v1 | desvio pc v5 | menor \\|desvio\\| | n mín. | fator pc | fator dom | candidata |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in regra[:12]:
        linhas.append(
            f"| {r['uf']} | {_pct(r['desvio_pc_v1'])} | {_pct(r['desvio_pc_v5'])} | {r['menor_desvio_abs']:.4f} | "
            f"{r['n_min_amostras']} | {r['per_capita']:.6f} | {r['domiciliar']:.6f} | {'sim' if r['atende'] else 'não'} |"
        )
    linhas += ["", "Sensibilidade do limiar (mesmo n mínimo):", ""]
    for limiar in pnad.LIMIARES_SENSIBILIDADE:
        ufs = [r["uf"] for r in pnad.avaliar_regra(calc, limiar=limiar, n_min=n_min) if r["atende"]]
        linhas.append(f"- L = {limiar:.0%}: {', '.join(ufs) if ufs else '(nenhuma)'}")
    aprov = sorted(nova["excecoes_aprovadas"])
    linhas += [
        "",
        f"Exceções APROVADAS nesta versão (`--aprovar-uf`): {', '.join(aprov) if aprov else '(nenhuma)'}",
        "",
    ]

    linhas += [
        "## Variação por UF contra a versão vigente",
        "",
        "| UF | pc vigente | pc novo | Δ pc | dom vigente | dom novo | Δ dom |",
        "|---|---|---|---|---|---|---|",
    ]
    for uf in calc.ufs():
        vpc, vdom = (
            fator_efetivo(vigente, uf, "per_capita"),
            fator_efetivo(vigente, uf, "domiciliar"),
        )
        npc, ndom = fator_efetivo(nova, uf, "per_capita"), fator_efetivo(nova, uf, "domiciliar")
        dpc, ddom = npc / vpc - 1, ndom / vdom - 1
        for nome, d in (("per capita", dpc), ("domiciliar", ddom)):
            if abs(d) > LIMIAR_ALERTA_DELTA:
                alertas.append(f"{uf} {nome} {_pct(d)}")
        linhas.append(
            f"| {uf} | {vpc:.4f} | {npc:.4f} | {_pct(dpc)} | {vdom:.4f} | {ndom:.4f} | {_pct(ddom)} |"
        )
    for tipo in ("per_capita", "domiciliar"):
        d = nac[tipo] / float(vigente["nacional"][tipo]) - 1
        if abs(d) > LIMIAR_ALERTA_DELTA:
            alertas.insert(0, f"nacional {tipo} {_pct(d)}")

    conf = nova["fonte"]["tabela_sidra_conferencia"]
    linhas += [
        "",
        "## Conferência de nível contra a SIDRA 7531",
        "",
        "A 7531 só confere o NÍVEL de cada ano na visita que ela usa naquele ano "
        f"(`visita_sidra` = {nova['visita_sidra']}). Nenhum crescimento é calculado a partir dela "
        "e nenhum valor dela entra nos fatores.",
        "",
        "| ano | visita | erro máx. por UF | UF | erro médio \\|abs\\| |",
        "|---|---|---|---|---|",
    ]
    for ano, e in sorted(conf["erros"].items()):
        linhas.append(
            f"| {ano} | {e['visita']} | {e['erro_max'] * 100:.3f}% | {e['uf_erro_max']} | {e['erro_medio_abs'] * 100:.3f}% |"
        )
    linhas.append(f"\nTolerância: {conf['tolerancia_por_uf']:.1%} por UF — conferência APROVADA.")
    if nova["ponte_ipca"] is not None:
        linhas += ["", f"Ponte IPCA (informativa, nunca aplicada): {nova['ponte_ipca']:.6f}"]

    linhas += ["", "## Alertas", ""]
    if alertas:
        linhas.append(
            f"**ATENÇÃO: variação acima de {LIMIAR_ALERTA_DELTA:.0%} contra a versão vigente.**"
        )
        linhas += [f"- {a}" for a in alertas]
    else:
        linhas.append(f"Nenhum fator variou mais de {LIMIAR_ALERTA_DELTA:.0%}.")
    linhas += [
        "",
        "## Arquivos de origem",
        "",
        "| amostra | papel | arquivo | sha256 |",
        "|---|---|---|---|",
    ]
    for a in nova["fonte"]["arquivos"]:
        linhas.append(
            f"| {a['ano']} v{a['visita']} | {a['papel']} | {a['nome']} | `{a['sha256'][:16]}…` |"
        )
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------------------


def _parse_visita_sidra(itens: Sequence[str] | None) -> dict[int, int]:
    """Mapa ano -> visita da 7531: o PADRAO (`sidra.VISITA_SIDRA_7531`) com os `--visita-sidra`
    POR CIMA. Completa, nao substitui: o runbook manda declarar so o ano-alvo novo
    (`--visita-sidra 2026=1`), e substituir deixaria o ano-base 2022 sem visita.
    """
    out: dict[int, int] = dict(sidra.VISITA_SIDRA_7531)
    for it in itens or ():
        m = re.fullmatch(r"(\d{4})=(\d)", it.strip())
        if not m:
            raise AtualizacaoAbortada(f"--visita-sidra espera ANO=VISITA, recebi {it!r}")
        out[int(m.group(1))] = int(m.group(2))
    return out


def _gravar(path: Path, texto: str) -> None:
    if path.exists():
        raise AtualizacaoAbortada(f"{path} ja' existe — versoes sao imutaveis")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    tmp.replace(path)


def _validar_com_loader(dados: Mapping[str, Any], caminho: Path, *, pais: str, versao: str) -> None:
    """Passa o arquivo pelo MESMO validador da subida antes de gravar (faixa, coerencia, schema)."""
    from motor_expansao.renda.carregador import FatoresRendaInvalidos, validar_versao

    provisorio = dict(dados)
    provisorio["relatorio"] = {"caminho": f"{versao}.md", "sha256": "0" * 64}
    try:
        validar_versao(provisorio, caminho, pais=pais, versao=versao)
    except FatoresRendaInvalidos as exc:
        raise AtualizacaoAbortada(
            f"a versao gerada nao passa no validador do loader: {exc}"
        ) from exc


def _sha256_texto(texto: str) -> str:
    import hashlib

    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m motor_expansao.renda.atualizar_fatores",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--pais", required=True)
    p.add_argument("--ano-base", type=int, required=True)
    p.add_argument("--ano-alvo", type=int, required=True)
    p.add_argument("--aprovar-uf", action="extend", nargs="+", default=[], metavar="UF")
    p.add_argument("--ponte-ipca", action="store_true", help="grava a ponte IPCA (informativa)")
    p.add_argument("--cache-dir", type=Path, default=CACHE_DIR_PADRAO)
    p.add_argument("--saida-dir", type=Path, default=None, help="padrao: fatores/<PAIS> do pacote")
    p.add_argument("--fatores-dir", type=Path, default=FATORES_DIR_PADRAO, help=argparse.SUPPRESS)
    p.add_argument(
        "--offline", action="store_true", help="nao acessa a rede: casa amostras no cache"
    )
    p.add_argument("--sidra-7531-json", type=Path, default=None)
    p.add_argument("--ipca-json", type=Path, default=None)
    p.add_argument("--visita-sidra", action="append", default=None, metavar="ANO=VISITA")
    p.add_argument("--limiar", type=float, default=pnad.LIMIAR_PADRAO)
    p.add_argument("--n-min", type=int, default=pnad.N_MIN_PADRAO)
    return p


def executar(
    args: argparse.Namespace,
    *,
    listar: pnad.Listar | None = None,
    baixar: pnad.Baixar | None = None,
    obter_json: sidra.ObterJson | None = None,
    hoje: date | None = None,
) -> dict[str, Any]:
    pais = args.pais.strip().upper()
    hoje = hoje or date.today()
    vigente = ler_vigente(args.fatores_dir, pais)
    if int(vigente["ano_base_renda"]) != args.ano_base:
        raise AtualizacaoAbortada(
            f"--ano-base {args.ano_base} difere do ano base da renda da versao vigente "
            f"({vigente['ano_base_renda']}): o fator tem de partir do ano do Censo"
        )
    visita_sidra = _parse_visita_sidra(args.visita_sidra)
    for ano in (args.ano_base, args.ano_alvo):
        if ano not in visita_sidra:
            raise AtualizacaoAbortada(
                f"ano {ano} sem visita declarada em visita_sidra {visita_sidra} — declare com --visita-sidra"
            )

    # 1-2. amostras e cache
    if args.offline:
        listar_ = pnad.listar_diretorio_local(args.cache_dir)
        baixar_: pnad.Baixar | None = None
    else:
        listar_ = listar or pnad.listar_http
        baixar_ = baixar or pnad.baixar_http
    insumos = pnad.preparar_insumos(
        ano_base=args.ano_base,
        ano_alvo=args.ano_alvo,
        cache_dir=args.cache_dir,
        listar=listar_,
        baixar=baixar_,
    )

    # 3. calculo — SO' microdados
    calc = pnad.calcular_fatores(insumos.dados, args.ano_base, args.ano_alvo)

    # 4. regra de excecao e aprovacoes
    regra = pnad.avaliar_regra(calc, limiar=args.limiar, n_min=args.n_min)
    cand = [r["uf"] for r in regra if r["atende"]]
    aprovadas = sorted({u.strip().upper() for u in args.aprovar_uf})
    invalidas = [u for u in aprovadas if u not in cand]
    if invalidas:
        raise AtualizacaoAbortada(
            f"--aprovar-uf so' aceita UF candidata pela regra; {invalidas} nao e'(sao). "
            f"Candidatas: {cand or '(nenhuma)'}"
        )

    # 5. conferencia de NIVEL contra a 7531 (devolve so' erros; nada volta para o fator)
    anos = (args.ano_base, args.ano_alvo)
    url7531 = sidra.url_7531(anos)
    if args.sidra_7531_json is not None:
        resp7531 = sidra.ler_json_local(args.sidra_7531_json)
    elif args.offline:
        raise AtualizacaoAbortada("modo offline exige --sidra-7531-json")
    else:
        resp7531 = (obter_json or sidra.obter_json_http)(url7531)
    niveis_micro = {(a, v): pnad.nivel_pc_por_uf(calc, a, v) for (a, v) in calc.niveis}
    conferencia = sidra.conferir_nivel_7531(
        niveis_micro, sidra.niveis_7531(resp7531), visita_sidra, anos
    )

    ponte = None
    if args.ponte_ipca:
        if args.ipca_json is not None:
            resp_ipca = sidra.ler_json_local(args.ipca_json)
        elif args.offline:
            raise AtualizacaoAbortada("--ponte-ipca em modo offline exige --ipca-json")
        else:
            resp_ipca = (obter_json or sidra.obter_json_http)(
                sidra.url_ipca(args.ano_base, args.ano_alvo)
            )
        ponte = sidra.ponte_ipca(resp_ipca, args.ano_base, args.ano_alvo)

    # 6. gravacao
    saida = Path(args.saida_dir) if args.saida_dir else Path(args.fatores_dir) / pais
    saida.mkdir(parents=True, exist_ok=True)
    versao = proxima_versao(
        hoje.strftime("%Y-%m"), args.ano_alvo, [Path(args.fatores_dir) / pais, saida]
    )
    nova = montar_versao(
        pais=pais,
        versao=versao,
        data_extracao=hoje,
        calc=calc,
        regra=regra,
        limiar=args.limiar,
        n_min=args.n_min,
        aprovadas=aprovadas,
        vigente=vigente,
        arquivos_fonte=_arquivos_fonte(insumos),
        conferencia=conferencia,
        visita_sidra=visita_sidra,
        url_7531=url7531,
        ponte=ponte,
    )
    _validar_com_loader(nova, saida / f"{versao}.json", pais=pais, versao=versao)
    relatorio = montar_relatorio(nova, vigente, calc, regra, args.n_min)
    caminho_rel = saida / f"{versao}.md"
    _gravar(caminho_rel, relatorio)
    nova["relatorio"] = {"caminho": caminho_rel.name, "sha256": _sha256_texto(relatorio)}
    caminho_json = saida / f"{versao}.json"
    _gravar(caminho_json, json.dumps(nova, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return {
        "versao": versao,
        "json": caminho_json,
        "relatorio": caminho_rel,
        "dados": nova,
        "calc": calc,
        "regra": regra,
    }


def main(argv: Sequence[str] | None = None, **injecoes: Any) -> int:
    args = construir_parser().parse_args(argv)
    res = executar(args, **injecoes)
    nac = res["dados"]["nacional"]
    print(
        f"[atualizar_fatores] {res['versao']}: per_capita {nac['per_capita']:.8f} "
        f"domiciliar {nac['domiciliar']:.8f} moradores {nac['moradores']:.8f}; "
        f"candidatas {res['dados']['candidatas_regra']}; "
        f"aprovadas {sorted(res['dados']['excecoes_aprovadas'])}\n"
        f"  -> {res['json']}\n  -> {res['relatorio']}\n  (VIGENTE inalterado)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
