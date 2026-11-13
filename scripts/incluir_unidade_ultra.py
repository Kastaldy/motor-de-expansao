"""Inclui ou move uma unidade Ultra nos dois arquivos que o Motor usa (roteiro em docs/infra_producao.md).

Roda na ESTAÇÃO, sobre as cópias baixadas da VPS, e grava só em <pasta>/novo/:

    python scripts/incluir_unidade_ultra.py incluir --pasta <pasta> --nome "Teresópolis" --uf RJ \
        --cidade "Teresópolis" --lat -22.407291115271388 --lng -42.96576019198278 [--endereco "..."]
    python scripts/incluir_unidade_ultra.py mover --pasta <pasta> --nome "Núcleo Bandeirante / DF" \
        --lat -15.87447704716228 --lng -47.97866495440901

<pasta> precisa ter `unidades_ultra_mapeadas.parquet` (os pins e a rede própria do mercado) e
`Ultra.csv` (o registro das unidades), os dois baixados da VPS no mesmo momento. No fim, o script
imprime os comandos de envio, gravação e desfazer, com os hashes da base e dos arquivos novos: a
gravação recusa se a VPS mudou desde a cópia ou se o envio chegou diferente.

Nada aqui toca o M1: os pins e a rede própria são camada de apoio.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

import h3
import pandas as pd
import pyarrow.parquet as pq

# As regras (distância mínima, nome repetido, colunas do parquet) moram numa fonte só, que o
# site também usa (DEC-085). O script roda na estação sem o pacote instalado, então o `src`
# do próprio checkout entra no caminho.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from motor_expansao.cadastro_ultra import (  # noqa: E402
    ARQ_CADASTRO,
    COLUNAS_CADASTRO,
    DIST_MIN_M,
    H3_RES,
    Recusa,
    distancia_m,
    nome_ja_existe,
)

ARQ_PARQUET = ARQ_CADASTRO
ARQ_CSV = "Ultra.csv"
COLUNAS_PARQUET = list(COLUNAS_CADASTRO)
REGIAO_POR_UF = {
    **dict.fromkeys(["AC", "AM", "AP", "PA", "RO", "RR", "TO"], "Norte"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
    **dict.fromkeys(["DF", "GO", "MS", "MT"], "Centro-Oeste"),
}
VPS = "deploy@2.25.137.241"
CHAVE = "~/.ssh/id_ultra_deploy"
DATA_VPS = "/opt/motor-expansao/data"
COMPOSE = "/opt/motor-expansao/app/docker-compose.prod.yml"

VERIFICADOR = '''"""Roda DENTRO do container do site: lê o arquivo de unidades como o site o vê."""
import pandas as pd

m = pd.read_parquet("/app/data/staging/unidades_ultra_mapeadas.parquet")
print("unidades no arquivo que o site le:", len(m))
t = m[m["unidade"] == {nome!r}]
print("linhas da unidade:", len(t))
for _, r in t.iterrows():
    print(r["unidade"], r["uf"], r["cidade"], round(float(r["lat"]), 6), round(float(r["lng"]), 6), r["hex_id_res7"])
'''


def coord(texto: str, eixo: str) -> float:
    valor = float(texto.replace(",", "."))
    limites = (-34.0, 6.0) if eixo == "lat" else (-75.0, -28.0)
    if not limites[0] <= valor <= limites[1]:
        raise Recusa(f"{eixo} {valor} fora do Brasil")
    return valor


def texto_decimal(texto: str) -> str:
    """Coordenada como o Ultra.csv grava: vírgula decimal, os dígitos que vieram na entrada."""
    return texto.strip().replace(".", ",")


def emitir_linha(campos: list[str]) -> str:
    """Estilo do Ultra.csv: todo campo não vazio entre aspas; vazio, sem nada."""
    for v in campos:
        if '"' in v or "\n" in v:
            raise Recusa(f"campo com aspas ou quebra de linha não é aceito: {v!r}")
    return ";".join(f'"{v}"' if v else "" for v in campos)


def ler_csv(caminho: Path) -> tuple[bytes, list[str], list[str]]:
    b = caminho.read_bytes()
    if b"\r" in b or not b.endswith(b"\n"):
        raise Recusa("Ultra.csv com fim de linha inesperado (o da VPS é LF e termina em quebra de linha)")
    linhas = b.decode("latin-1").split("\n")
    cab = next(csv.reader([linhas[1]], delimiter=";"))
    for c in ("UNIDADE", "CIDADE", "ESTADO", "Latitude", "Longitude"):
        if c not in cab:
            raise Recusa(f"Ultra.csv sem a coluna {c!r} (é o da VPS, com a linha de metadado no topo?)")
    return b, linhas, cab


def incluir(args: argparse.Namespace, m: pd.DataFrame, linhas: list[str], cab: list[str]):
    lat, lng = coord(args.lat, "lat"), coord(args.lng, "lng")
    nome, uf = args.nome.strip(), args.uf.strip().upper()
    if nome_ja_existe(nome, m["unidade"]):
        raise Recusa(f"{nome!r} já está no {ARQ_PARQUET}: para mudar o lugar, use `mover`")
    nomes_csv = [next(csv.reader([lin], delimiter=";"))[cab.index("UNIDADE")] for lin in linhas[2:] if lin]
    if nome in nomes_csv:
        raise Recusa(f"{nome!r} já está no {ARQ_CSV}")
    dist = m.apply(lambda r: distancia_m(lat, lng, r["lat"], r["lng"]), axis=1)
    perto = m.loc[dist.idxmin()]
    print(f"a unidade mais perto é {perto['unidade']} ({perto['cidade']}/{perto['uf']}), a {dist.min() / 1000:.1f} km")
    if dist.min() < DIST_MIN_M and not args.forcar_perto:
        raise Recusa(f"há unidade a menos de {DIST_MIN_M:.0f} m: pode ser a mesma (use --forcar-perto se não for)")
    novo_id = hashlib.sha1(f"{nome}|{lat:.6f}|{lng:.6f}".encode()).hexdigest()
    if novo_id in set(m["ultra_id"]):
        raise Recusa("ultra_id repetido")
    linha = pd.DataFrame([{
        "ultra_id": novo_id, "unidade": nome, "uf": uf, "cidade": args.cidade.strip(), "lat": lat, "lng": lng,
        "flag_coord_valida": True, "hex_id_res7": h3.latlng_to_cell(lat, lng, H3_RES),
    }])
    novo = pd.concat([m, linha], ignore_index=True).astype(m.dtypes.to_dict())
    valores = {
        "UNIDADE": nome, "ENDEREÇO": (args.endereco or "").strip(), "CIDADE": args.cidade.strip(), "ESTADO": uf,
        "Precisão de mapeamento": "Máxima", "Processo de Geocodificação": "Manual",
        "Latitude": texto_decimal(args.lat), "Longitude": texto_decimal(args.lng),
        "Região Geográfica": REGIAO_POR_UF.get(uf, ""),
    }
    nova_linha = emitir_linha([valores.get(c, "") for c in cab])
    novas_linhas = linhas[:-1] + [nova_linha, ""]
    return novo, novas_linhas, nome, [len(m)]


def mover(args: argparse.Namespace, m: pd.DataFrame, linhas: list[str], cab: list[str]):
    lat, lng = coord(args.lat, "lat"), coord(args.lng, "lng")
    nome = args.nome.strip()
    alvo = m.index[m["unidade"].str.strip().eq(nome)].tolist()
    if len(alvo) != 1:
        raise Recusa(f"{nome!r} aparece {len(alvo)} vez(es) no {ARQ_PARQUET} (o nome tem de ser exato)")
    i = alvo[0]
    novo = m.copy()
    novo.loc[i, ["lat", "lng"]] = [lat, lng]
    novo.loc[i, "hex_id_res7"] = h3.latlng_to_cell(lat, lng, H3_RES)
    novo.loc[i, "flag_coord_valida"] = True
    ic, ilat, ilng = cab.index("UNIDADE"), cab.index("Latitude"), cab.index("Longitude")
    achadas = [k for k, lin in enumerate(linhas) if k >= 2 and lin and next(csv.reader([lin], delimiter=";"))[ic] == nome]
    if len(achadas) != 1:
        raise Recusa(f"{nome!r} aparece {len(achadas)} vez(es) no {ARQ_CSV}")
    k = achadas[0]
    campos = next(csv.reader([linhas[k]], delimiter=";"))
    if emitir_linha(campos) != linhas[k]:
        raise Recusa("a linha da unidade no Ultra.csv tem um formato que o script não reproduz igual")
    campos[ilat], campos[ilng] = texto_decimal(args.lat), texto_decimal(args.lng)
    novas_linhas = linhas[:k] + [emitir_linha(campos)] + linhas[k + 1 :]
    print(f"{nome}: de ({m.loc[i, 'lat']:.6f}, {m.loc[i, 'lng']:.6f}) para ({lat:.6f}, {lng:.6f}), "
          f"{distancia_m(m.loc[i, 'lat'], m.loc[i, 'lng'], lat, lng):.0f} m")
    return novo, novas_linhas, nome, [i]


def caminho_git_bash(p: Path) -> str:
    """O `scp` do Git Bash lê `C:/...` como host `C`: o caminho sai no formato `/c/...`."""
    s = str(p).replace("\\", "/")
    if not re.match(r"^[A-Za-z]:/", s):
        s = str(p.resolve()).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", s)
    return f"/{m.group(1).lower()}/{m.group(2)}" if m else s


def comandos(pasta: Path, base_pq: str, base_csv: str, novo_pq: str, novo_csv: str) -> list[str]:
    novo = pasta / "novo"
    bkp = f"backup-unidade-ultra-{datetime.now():%Y%m%d-%H%M}"
    envio = " && ".join(
        f'scp -i {CHAVE} "{caminho_git_bash(novo / origem)}" {VPS}:{destino}'
        for origem, destino in (
            (ARQ_PARQUET, "mapeadas.novo.parquet"), (ARQ_CSV, "Ultra.novo.csv"), ("verificar_unidade.py", "verificar_unidade.py"),
        )
    )
    verificar = "docker exec -i motor_expansao_web python - < verificar_unidade.py"
    reinicio = f"docker compose -f {COMPOSE} restart web api 2>&1 | tail -n 4"
    pq_vps, csv_vps = f"{DATA_VPS}/staging/{ARQ_PARQUET}", f"{DATA_VPS}/ultra/{ARQ_CSV}"
    gravacao = (
        f"ssh -i {CHAVE} {VPS} 'cd ~; "
        f"if sha256sum {pq_vps} | grep -q ^{base_pq} && sha256sum {csv_vps} | grep -q ^{base_csv}; "
        "then echo base-confere; else echo A-BASE-MUDOU-nada-foi-gravado; exit 1; fi; "
        f"if sha256sum mapeadas.novo.parquet | grep -q ^{novo_pq} && sha256sum Ultra.novo.csv | grep -q ^{novo_csv}; "
        "then echo envio-confere; else echo ENVIO-DIFERENTE-nada-foi-gravado; exit 1; fi; "
        f"mkdir -p {bkp} && cp -p {pq_vps} {csv_vps} {bkp}/ && echo backup-feito && "
        f"cp mapeadas.novo.parquet {pq_vps} && cp Ultra.novo.csv {csv_vps} && echo arquivos-gravados && "
        f"{reinicio} && {verificar}'"
    )
    desfazer = (
        f"ssh -i {CHAVE} {VPS} 'cd ~ && cp {bkp}/{ARQ_PARQUET} {pq_vps} && cp {bkp}/{ARQ_CSV} {csv_vps} && "
        f"echo originais-de-volta && {reinicio} && {verificar}'"
    )
    return [envio, gravacao, desfazer]


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("modo", choices=["incluir", "mover"])
    p.add_argument("--pasta", type=Path, required=True)
    p.add_argument("--nome", required=True, help="como aparece no pin (incluir) ou o nome exato (mover)")
    p.add_argument("--uf", default="")
    p.add_argument("--cidade", default="")
    p.add_argument("--lat", required=True)
    p.add_argument("--lng", required=True)
    p.add_argument("--endereco", default="")
    p.add_argument("--forcar-perto", action="store_true")
    args = p.parse_args(argv)
    if args.modo == "incluir" and not (args.uf and args.cidade):
        p.error("incluir pede --uf e --cidade")

    arq_pq, arq_csv = args.pasta / ARQ_PARQUET, args.pasta / ARQ_CSV
    try:
        m = pd.read_parquet(arq_pq)
        if list(m.columns) != COLUNAS_PARQUET:
            raise Recusa(f"colunas inesperadas no {ARQ_PARQUET}: {list(m.columns)}")
        b, linhas, cab = ler_csv(arq_csv)
        novo, novas_linhas, nome, mexidas = (incluir if args.modo == "incluir" else mover)(args, m, linhas, cab)
    except Recusa as e:
        print(f"RECUSADO, nada foi gravado: {e}")
        return 2

    saida = args.pasta / "novo"
    saida.mkdir(exist_ok=True)
    destino_pq, destino_csv = saida / ARQ_PARQUET, saida / ARQ_CSV
    novo.to_parquet(destino_pq, index=False)
    relido = pd.read_parquet(destino_pq)
    intactas = [i for i in range(len(m)) if i not in mexidas]
    assert relido.loc[intactas].reset_index(drop=True).equals(m.loc[intactas].reset_index(drop=True)), "outra linha mudou"
    assert pq.read_schema(destino_pq).remove_metadata().equals(pq.read_schema(arq_pq).remove_metadata()), "tipos mudaram"
    novo_b = "\n".join(novas_linhas).encode("latin-1")
    destino_csv.write_bytes(novo_b)
    if args.modo == "incluir":
        assert novo_b.startswith(b), "o começo do Ultra.csv mudou"
    (saida / "verificar_unidade.py").write_text(VERIFICADOR.format(nome=nome), encoding="utf-8")

    print(f"{ARQ_PARQUET}: {len(m)} -> {len(relido)} unidades; {ARQ_CSV}: {len(linhas) - 3} -> {len(novas_linhas) - 3}")
    print(relido.loc[relido["unidade"] == nome].to_string(index=False))
    h = lambda caminho: hashlib.sha256(caminho.read_bytes()).hexdigest()  # noqa: E731
    cmds = comandos(args.pasta, h(arq_pq), h(arq_csv), h(destino_pq), h(destino_csv))
    for rotulo, c in zip(("ENVIO", "GRAVAÇÃO", "DESFAZER"), cmds, strict=True):
        print(f"\n--- {rotulo} ---\n{c}")
    (saida / "comandos.txt").write_text("\n\n".join(cmds) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
