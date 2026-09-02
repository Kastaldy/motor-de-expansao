#!/usr/bin/env python
"""
Exporta a base argentina no LAYOUT QUE O PILOTO WEB JÁ LÊ.

PROCEDÊNCIA: `pipelines/exportar_piloto_rep.py` do repositório `juancalu/motor-argentina`,
autoria do Juan. Trazido para cá em 2026-09-02 (Bloco B) porque enquanto ficasse lá a
ponte entre o pacote e a instância no ar era dependência de PESSOA, não de código: é este
script que deriva `hex_id`, `lat`, `lng`, `cidade` e `cod_municipio`, que NÃO existem no
parquet entregue. Agora o contrato e o consumidor moram no mesmo repositório, e o teste de
contrato quebra junto quando um dos dois muda.

TRÊS COISAS MUDARAM AO ATRAVESSAR A FRONTEIRA, e nenhuma é cosmética:

1. **Sem `import config`.** Aquele módulo é o layout do repositório do Juan. Os quatro
   caminhos que ele fornecia viraram argumentos (`--dados`, `--hex`, `--saida`), com
   default relativo ao `--dados`. O script roda contra qualquer árvore de dados.

2. **O score é RECOMPUTADO, não renomeado.** O de-para original mandava
   `score_setor_2022_calibrado ← hex_score_estrutural`. Renomear ali troca a pergunta em
   silêncio: o score argentino é PERCENTIL (0,40·renda + 0,60·pop, percentis nacionais) e
   o corte de 30 do funil brasileiro é ABSOLUTO. Um número de 0-100 vira outro número de
   0-100 e nada acusa. Agora se recomputa com `calcular_score_calibrado` nas âncoras do
   `perfil.json` argentino — a mesma função e a mesma fórmula (0,60·renda + 0,40·pop) do
   Brasil, sobre a régua ARGENTINA. Ver a decisão P3 do perfil AR.

3. **Sem `MOTOR_PAIS`.** O original instruía exportar `MOTOR_PAIS=AR` para o piloto tratar
   o uplift de composição familiar como identidade — sem o que a renda do Relatório Pontual
   sai 63% acima da real. A variável nunca existiu nesta plataforma, e não vai existir: país
   escolhendo caminho de execução é o que a DEC-047 proíbe. O mesmo defeito é resolvido por
   `reguas.uplift_composicao = 1.0` no perfil argentino, que é um MULTIPLICADOR, não um ramo.

Por que existe: o piloto (`web/` do Motor de Expansão REP — SPA + FastAPI) roda a
Argentina **sem uma linha de código alterada**. Foi medido: basta apontar o
`MOTOR_DATA_DIR` dele para a saída deste script. O motivo é que o backend descobre as
unidades por `glob("uf=*")` e lê colunas **por nome**, de forma defensiva
(`[c for c in _COLS_DESEJADAS if c in disponiveis]`) — então o contrato entre os dois
motores é só um conjunto de nomes de pasta e de coluna.

A consequência é a decisão de arquitetura: a costura fica **deste lado**. Este
repositório passa a emitir o contrato que o REP já consome, em vez de o REP ganhar um
caso especial de Argentina. O de-para vem de `felipe/HANDOFF.md` §4.

Saída (dentro de `outputs/`, portanto fora do versionamento):
    outputs/motor_data_ar/
      outputs/hexagonos_dashboard_enriquecido/uf=<CC>/part-0.parquet
      staging/concorrentes_mapeados.parquet
      staging/hexagonos_mercado_mapeado.parquet

Uso no piloto (a variável vai pelo AMBIENTE — ver a armadilha 3 no fim do arquivo).
O `perfil.json` argentino tem de estar na RAIZ do MOTOR_DATA_DIR, senão o processo não
sobe — é o fail-closed do Bloco A, e é deliberado:
    $env:MOTOR_DATA_DIR = "<saida>/motor_data_ar"
    python -m uvicorn app:app --host 127.0.0.1 --port 8900

Uso:  python -m motor_expansao.pipelines.exportar_piloto_ar --dados <arvore de dados>
      python -m motor_expansao.pipelines.exportar_piloto_ar --dados <d> --hex <parquet>
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

import h3
import numpy as np
import pandas as pd

from motor_expansao.perfil import Perfil, carregar_perfil
from motor_expansao.pipelines.calibrar_renda_setor_2022 import calcular_score_calibrado


class Caminhos:
    """As quatro raizes que o `config.py` do repo do Juan fornecia.

    Viraram argumento porque o modulo dele e o LAYOUT do repositorio dele: importa-lo aqui
    amarraria este script a uma arvore de diretorios que nao e a nossa.
    """

    def __init__(self, dados: Path, saida: Path) -> None:
        self.dados = Path(dados)
        self.saida = Path(saida)

    def fonte(self, *partes: str) -> Path:
        return self.dados.joinpath(*partes)


#: Preenchidos por `main()`. Modulo-globais porque as funcoes de escrita ja tinham essa
#: forma no original, e mudar a assinatura de todas seria churn sem ganho.
#:
#: Nascem `None` de proposito, e nao como anotacao nua: anotacao nao cria atributo, e a
#: falha sairia como `AttributeError` no meio da exportacao — mensagem que nao diz o que
#: falta. Com o `None` explicito, `_exigir_perfil` falha dizendo qual passo nao rodou.
CAMINHOS: Caminhos | None = None
PERFIL: Perfil | None = None


def _exigir_perfil() -> Perfil:
    if PERFIL is None:
        raise RuntimeError(
            "perfil nao resolvido: `main()` o carrega de `--perfil`. Sem ele nao ha "
            "ancoras, e sem ancoras o score sairia na regua do pais errado."
        )
    return PERFIL


def _exigir_caminhos() -> Caminhos:
    if CAMINHOS is None:
        raise RuntimeError("caminhos nao resolvidos: `main()` os monta de `--dados`.")
    return CAMINHOS


def score_do_pais(renda, pop) -> np.ndarray:
    """Score da camada 1 RECOMPUTADO nas ancoras do perfil — nao renomeado.

    O de-para original mandava `score_setor_2022_calibrado <- hex_score_estrutural`. Nao
    da: o score argentino e PERCENTIL (0,40 x renda_pct + 0,60 x pop_pct, percentis
    NACIONAIS) e o corte de 30 que o funil brasileiro aplica sobre essa coluna e
    ABSOLUTO. Renomear faz um numero de 0-100 virar outro numero de 0-100 sem que nada
    acuse — e ai o corte de "hexagono quente" passa a significar "top 70% da Argentina"
    em vez de "renda e populacao acima da regua".

    Aqui se usa a MESMA funcao e a MESMA formula do Brasil (0,60 x renda + 0,40 x pop,
    mais o ajuste executivo), sobre as ANCORAS ARGENTINAS do perfil. E o que a decisao P3
    do `data/perfis/AR/perfil.json` fixou em 2026-09-02.
    """
    _, _, score = calcular_score_calibrado(
        np.asarray(renda, dtype="float64"),
        np.asarray(pop, dtype="float64"),
        ancoras=_exigir_perfil().ancoras(),
    )
    return score

# ---------------------------------------------------------------------------
# Códigos de província — o seletor "UF" do piloto mostra exatamente isto
# ---------------------------------------------------------------------------
# DUAS RESTRIÇÕES SIMULTÂNEAS, e o espaço entre elas é estreito:
#
# 1. EXATAMENTE 2 LETRAS. O backend valida no sink com `^[A-Za-z]{2}$` (guardrail de
#    path-traversal, BLK-SEC-05): a UF compõe o caminho da partição (`uf=XX`), então um
#    valor como `x/../../etc` leria diretório arbitrário. Código de 3-4 letras (BSAS,
#    CABA) leva HTTP 400. Não se afrouxa esse regex para caber a Argentina — a defesa é
#    legítima e vale para os dois países.
#
# 2. NÃO PODE COLIDIR COM UF BRASILEIRA. As siglas "óbvias" colidiam em cinco casos:
#    PB (Buenos Aires × Paraíba), BA (CABA × Bahia), RN (Río Negro × Rio Grande do
#    Norte), SC (Santa Cruz × Santa Catarina) e SE (Santiago del Estero × Sergipe).
#    Num seletor que mostra só "PB", o operador lê Paraíba.
#
# As 24 abaixo satisfazem as duas. Onde a sigla natural estava tomada, usa-se a segunda
# consoante forte — BS (Buenos Aires), CA (CABA), CZ (Santa Cruz), SG (Santiago), RG.
SIGLA_PROVINCIA = {
    "Ciudad Autónoma de Buenos Aires": "CA", "Buenos Aires": "BS",
    "Catamarca": "CT", "Chaco": "CH", "Chubut": "CU", "Córdoba": "CB",
    "Corrientes": "CR", "Entre Ríos": "ER", "Formosa": "FO", "Jujuy": "JU",
    "La Pampa": "LP", "La Rioja": "LR", "Mendoza": "MZ", "Misiones": "MI",
    "Neuquén": "NQ", "Río Negro": "RG", "Salta": "SA", "San Juan": "SJ",
    "San Luis": "SL", "Santa Cruz": "CZ", "Santa Fe": "SF",
    "Santiago del Estero": "SG", "Tucumán": "TU",
}

# UFs brasileiras — existem aqui só para GARANTIR que nenhum código argentino colida.
UF_BR = frozenset(
    "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
)

_COD_RE = re.compile(r"^[A-Z]{2}$")

# Distância máxima entre um radio e a localidade que lhe empresta o nome de bairro, em
# GRAUS (~5 km em latitude). Ver `localidade_por_radio` para o porquê de graus e do teto.
TETO_BAIRRO_GRAUS = 0.045

# Corte operacional do piloto (`POP_MIN_ACIONAVEL` no backend). Não é nosso: é a régua
# do motor BR, replicada aqui só para a checagem de sanidade no fim.
POP_MIN_PILOTO = 5_000


def codigo_provincia(nome: str, usados: set[str]) -> str:
    """Código de 2 letras da província (ver as duas restrições acima).

    Fallback para nome fora do dicionário: primeira letra + primeira letra livre.
    Nunca inventa 3 letras — o backend recusaria com 400.
    """
    if nome in SIGLA_PROVINCIA:
        return SIGLA_PROVINCIA[nome]
    puro = "".join(
        c for c in unicodedata.normalize("NFD", nome) if unicodedata.category(c) != "Mn"
    ).upper()
    letras = [c for c in puro if c.isalpha()] or ["X"]
    ocupados = set(SIGLA_PROVINCIA.values()) | UF_BR | usados
    for segunda in letras[1:] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        cand = letras[0] + segunda
        if cand not in ocupados:
            return cand
    return "XX"


def montar_hexagonos(hx: pd.DataFrame) -> pd.DataFrame:
    """De-para AR → contrato do piloto. READ-ONLY sobre a base do motor."""
    latlng = [h3.cell_to_latlng(c) for c in hx["h3_id"]]
    return pd.DataFrame(
        {
            # --- identidade ---------------------------------------------------
            "hex_id": hx["h3_id"],
            # o piloto consome lat/lng prontos; a AR guarda só o índice H3
            "lat": [p[0] for p in latlng],
            "lng": [p[1] for p in latlng],
            "nome_municipio": hx["nome_departamento"],
            "cidade": hx["nome_departamento"],
            "cod_municipio": hx["cod_departamento"],
            # --- scores ------------------------------------------------------
            # RECOMPUTADO nas âncoras do perfil, não renomeado do `hex_score_estrutural`
            # — ver `score_do_pais` e a decisão P3 do perfil AR. Esta é a coluna sobre a
            # qual o funil aplica o corte ABSOLUTO de 30; herdar um percentil aqui
            # trocaria a pergunta em silêncio.
            "score_setor_2022_calibrado": score_do_pais(
                hx["renda_estimada_usd"], hx["pop_total"]
            ),
            # O estrutural argentino continua vindo, com o nome dele, para auditoria:
            # é percentil e NÃO é o que o mapa pinta.
            "hex_score_estrutural_ar": hx["hex_score_estrutural"],
            "score_priorizacao": hx["score_priorizacao"],
            "score_oportunidade_residual": hx["score_oportunidade_residual"],
            "score_expansao_hibrido": hx["hex_score_final"],
            # --- mercado ------------------------------------------------------
            "oferta_efetiva_disponivel": hx["residual_membros"],
            "oferta_consumida_mercado_estimada": hx["oferta_consumida_mercado"],
            "capacidade_default_concorrente_alunos": hx["capacidade_concorrente_calibrada"],
            "sam_fitness_potencial": hx["sam_membros_potencial"],
            # --- população: A DECISÃO QUE MAIS MUDA O MAPA --------------------
            # O backend monta `pop_leitura` na precedência populacao_corte_hex >
            # pop_total_setor_2022 > pop_total, e o front corta em 5.000 sobre ela.
            # O motor argentino aplica esses MESMOS 5.000 sobre a CAPTAÇÃO (hexágono +
            # 6 vizinhos, ~25 km²) — confere 100% com `flag_pop_min_5k`. Com
            # `pop_total` (célula de ~4,3 km², mediana de 40 moradores) o corte apagaria
            # 5.325 hexágonos que o motor considera viáveis, 932 deles "abrir agora".
            "populacao_corte_hex": hx["pop_captacao"],
            "pop_total": hx["pop_total"],
            # --- renda --------------------------------------------------------
            # Em USD/mês. Até o Bloco A o piloto rotulava "R$" fixo e o símbolo saía
            # errado; desde o commit A9 ele lê `moeda.simbolo` do perfil, e o argentino
            # diz "$". ARS deixaria a ordem de grandeza absurda ao lado do Brasil.
            "renda_per_capita": hx["renda_estimada_usd"],
            # --- faixa: os valores crus da AR JÁ SÃO o FAIXA_ORDEM do BR ------
            # Os dois motores seguem a mesma regra de "nunca acentuar identificador",
            # então `prioridade_maxima`/`alta`/... casam sem tradução.
            "faixa_oportunidade": hx["faixa_oportunidade"],
            # --- rede Ultra: não existe na Argentina --------------------------
            # Zero é a resposta CERTA, não dado faltando.
            "n_unidades_ultra_performance_hex": 0,
            "n_unidades_ultra_2km": 0,
        }
    )


def escrever_particoes(
    out: pd.DataFrame, provincias: pd.Series, dest: Path
) -> tuple[int, dict[str, str]]:
    """Uma partição `uf=<CC>` por província, com os guarda-corpos de código.

    Devolve `(linhas, {nome_da_provincia: sigla})`. O de-para sobe porque a malha
    administrativa e a base setorial precisam falar do MESMO universo do seletor:
    província sem hexágono habitado não entra em lugar nenhum.
    """
    _limpar(dest)
    dest.mkdir(parents=True, exist_ok=True)

    out = out.assign(_prov=provincias.values)
    usados: dict[str, str] = {}
    linhas = 0
    for nome, grupo in out.groupby("_prov", sort=True):
        cod = codigo_provincia(str(nome), set(usados))
        # Falhar aqui é melhor do que servir um mapa trocado — ou, pior, uma partição
        # que o backend recusa com 400 só quando alguém clica nela.
        if not _COD_RE.match(cod):
            raise SystemExit(
                f"ERRO: código {cod!r} ({nome}) não tem 2 letras maiúsculas; o backend "
                f"valida com ^[A-Za-z]{{2}}$ e devolveria HTTP 400."
            )
        if cod in UF_BR:
            raise SystemExit(f"ERRO: código {cod!r} ({nome}) colide com UF brasileira.")
        if cod in usados:
            raise SystemExit(f"ERRO: código {cod!r} repetido ({nome} e {usados[cod]}).")
        usados[cod] = str(nome)

        d = dest / f"uf={cod}"
        d.mkdir(parents=True, exist_ok=True)
        grupo.drop(columns=["_prov"]).to_parquet(d / "part-0.parquet", index=False)
        linhas += len(grupo)
        print(f"    uf={cod}  {str(nome)[:34]:<34} {len(grupo):>6,} hexes")
    return linhas, {nome: cod for cod, nome in usados.items()}


def _limpar(dest: Path) -> None:
    """Remove as partições da rodada anterior.

    Não é higiene cosmética: `listar_ufs()` do piloto faz glob em `uf=*`, então uma
    pasta VAZIA que sobre de uma rodada antiga vira "estado" no seletor e devolve 404 ao
    ser aberta. Como a saída costuma estar no OneDrive, que segura o handle do diretório
    por instantes após o arquivo sair, cada remoção tenta algumas vezes.
    """
    if not dest.exists():
        return
    for velho in dest.glob("uf=*/part-0.parquet"):
        try:
            velho.unlink()
        except OSError:
            pass
    shutil.rmtree(dest, ignore_errors=True)

    resistiram = []
    for d in dest.glob("uf=*"):
        if not d.is_dir():
            continue
        for _ in range(4):
            try:
                d.rmdir()
                break
            except OSError:
                time.sleep(0.4)
        else:
            resistiram.append(d.name)
    if resistiram:
        print(
            f"  ATENÇÃO: {len(resistiram)} pastas vazias resistiram e virarão estado "
            f"fantasma no seletor: {', '.join(resistiram)}"
        )
        print("           feche o backend/Explorer e rode de novo.")


def escrever_concorrentes(dest_staging: Path) -> tuple[set[str], set[str]]:
    """Pinos de concorrente do mapa. Devolve as REDES presentes (para os logos).

    Sem isto o mapa argentino sai visivelmente mais POBRE que o brasileiro: o piloto
    devolve lista vazia quando o arquivo falta (não quebra, só some) e o operador vê
    hexágono sem nenhuma academia em volta.

    Contrato lido pelo piloto: rede, nome_unidade, lat, lng, hex_id_res7.
    """
    fonte = _exigir_caminhos().fonte("concorrentes", "concorrentes_ar.parquet")
    if not fonte.exists():
        fonte = _exigir_caminhos().fonte("concorrentes", "concorrentes_ar.parquet")
    if not fonte.exists():
        print("  [aviso] concorrentes_ar.parquet ausente — o mapa sai sem pinos")
        return set(), set()

    MOSTRADAS = ["concorrente", "studio", "revisar"]
    c = pd.read_parquet(fonte)
    # `excluido` é o que a taxonomia argentina já descartou (clube esportivo, paddle...):
    # a maior parte das linhas. Entrar com eles encheria o mapa de pontos que o próprio
    # motor não considera concorrência.
    c = c[c["categoria"].isin(MOSTRADAS)].copy()
    c["porte"] = c["porte"] if "porte" in c.columns else None

    # --- A CAMADA WEB TAMBÉM VAI PARA O MAPA (2026-08-26) --------------------
    # Antes só o OSM virava pino, e o mapa mentia por omissão: 94% dos POIs de academia do
    # OSM argentino são casa de bairro sem marca, então o piloto mostrava um país só de
    # independentes — SportClub (852 unidades), Megatlón, Smart Fit e Fiter simplesmente
    # não existiam na tela. Quem olhava concluía "não há rede na Argentina", que é o
    # contrário do que a coleta descobriu.
    #
    # Pior: o MOTOR já contava as duas fontes (`nacional_academia.extrair_academias`), então
    # o mapa contradizia o número que ele mesmo exibia — hexágono com residual baixo por
    # causa de uma rede que não aparecia em lugar nenhum.
    #
    # A dedup é a MESMA de `nacional_academia` (<150 m E nome parecido), pelo mesmo motivo:
    # só ~14% das unidades se sobrepõem entre as fontes, e distância sozinha funde
    # academias vizinhas distintas.
    web_arq = _exigir_caminhos().fonte("concorrentes", "redes_ar.parquet")
    if web_arq.exists():
        w = pd.read_parquet(web_arq)
        w = w[w["categoria"].isin(MOSTRADAS)].dropna(subset=["lat", "lon"]).copy()
        if len(w):
            import nacional_academia as NA
            antes_osm = len(c)
            c = NA._sem_duplicatas(c.rename(columns={"name": "name"}), w)
            w_out = pd.DataFrame({
                "name": w["nome"],
                "cadeia": w["rede"],
                "porte": w.get("porte"),
                "lat": w["lat"], "lon": w["lon"], "h3_id": w["h3_id"],
                "categoria": w["categoria"],
                # A FOTO da unidade (nome do arquivo em dados/concorrentes/fotos). So a
                # camada web tem: o POI do OSM nao carrega imagem nenhuma. Vira a foto do
                # balao do pino no piloto — ver `escrever_fotos` abaixo.
                "foto": w.get("foto"),
            })
            repetidos = antes_osm - len(c)
            c = pd.concat([c, w_out], ignore_index=True)
            print(f"  pinos: OSM {antes_osm:,} (-{repetidos:,} ja presentes na web) "
                  f"+ web {len(w_out):,} = {len(c):,}")
    else:
        print("  [aviso] redes_ar.parquet ausente — o mapa sai só com os pinos do OSM")

    # --- status_registro: a camada de RAIO DE 1 KM depende dela ---------------
    # `cobertura_1km.py` lê o parquet com `columns=["lat","lng","status_registro"]`
    # — coluna AUSENTE derruba a rota inteira com 500 (pyarrow: "No match for
    # FieldRef.Name(status_registro)"), e o raio simplesmente não aparecia no mapa.
    #
    # No Brasil a coluna separa `valido` de `descartado_duplicado` /
    # `descartado_coord`. A taxonomia argentina classifica OUTRA coisa — `categoria`
    # diz se o ponto é academia (o `excluido` é clube, paddle, yoga), não se o
    # REGISTRO presta. Então derivamos o status do que a Argentina realmente sabe
    # sobre a qualidade do registro:
    #
    #   descartado_coord      lat/lng ausente — o ponto não tem onde pousar
    #   descartado_duplicado  mesma rede na mesma coordenada (a coleta repetiu)
    #   valido                o resto
    #
    # Só `valido` entra no cálculo do raio, dos dois lados.
    c = c.reset_index(drop=True)
    dup = c.duplicated(subset=["cadeia", "lat", "lon"], keep="first")
    sem_coord = c["lat"].isna() | c["lon"].isna()
    status = pd.Series("valido", index=c.index, dtype="object")
    status = status.mask(dup, "descartado_duplicado")
    status = status.mask(sem_coord, "descartado_coord")

    out = pd.DataFrame(
        {
            # `cadeia` só existe para uma minoria — o resto é academia de bairro.
            # "Independente" é a leitura correta, e não dado faltando.
            "rede": c["cadeia"].fillna("Independente"),
            "nome_unidade": c["name"].fillna("(sem nome)"),
            "lat": c["lat"],
            "lng": c["lon"],
            "hex_id_res7": c["h3_id"],
            "flag_coord_valida": ~sem_coord,
            "status_registro": status,
            # Nome do arquivo, nao caminho: quem serve decide onde a pasta esta. Vazio para
            # o POI do OSM, que nao tem imagem — o balao simplesmente sai sem foto.
            "foto": c["foto"] if "foto" in c.columns else None,
        }
    ).dropna(subset=["lat", "lng"])

    dest_staging.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dest_staging / "concorrentes_mapeados.parquet", index=False)
    de_rede = int(out["rede"].ne("Independente").sum())
    validos = int((out["status_registro"] == "valido").sum())
    print(f"  concorrentes: {len(out):,} pinos ({de_rede:,} de rede conhecida) "
          f"· {validos:,} válidos para o raio de 1 km")
    # As redes que de fato viraram pino — e' esse o conjunto que precisa de logo.
    redes = set(out.loc[out["rede"].ne("Independente"), "rede"].dropna().astype(str))
    fotos = set(out["foto"].dropna().astype(str)) - {""}
    return redes, fotos


# De-para da camada de MERCADO: nome argentino -> nome que o piloto lê.
#
# Não é conversão, é RENOMEAÇÃO — as duas bases calculam a mesma coisa. Verificado linha a
# linha nas 42.388: `oferta_efetiva_disponivel` no REP é
# `max(sam_fitness_potencial - oferta_consumida_total_estimada, 0)` e `residual_membros`
# aqui é `max(sam_membros_potencial - oferta_consumida_mercado, 0)` — 100% das linhas batem.
#
# `score_setor_2022_calibrado` NÃO está mais aqui: ele deixou de ser renomeação e passou a
# ser RECOMPUTO (`score_do_pais`), porque o argentino é percentil e o corte do funil é
# absoluto. Ver o cabeçalho deste arquivo, item 2.
MERCADO_DE_PARA = {
    "h3_id": "hex_id",
    "sam_membros_potencial": "sam_fitness_potencial",
    "oferta_consumida_mercado": "oferta_consumida_mercado_estimada",
    "residual_membros": "oferta_efetiva_disponivel",
    "score_oportunidade_residual": "score_oportunidade_residual",
}


def escrever_mercado(dest_staging: Path, hx: pd.DataFrame) -> int:
    """`staging/hexagonos_mercado_mapeado.parquet` — a camada de MERCADO do estudo de ponto.

    SEM ESTE ARQUIVO o relatório pontual perde três coisas de uma vez, e nenhuma delas
    levanta erro (Juan, 2026-08-31):

      - a página "Socioeconomia e Residual Fitness" sai com "Mapa indisponível para esta
        camada" DUAS vezes e zero imagens (`_hexes_vizinhos_do_ponto` devolve `None`);
      - os cards "SAM Fitness" e "Residual Fitness" dos Big Numbers saem "Não disponível";
      - a ficha do ponto na tela mostra o bloco de mercado vazio.

    O backend lê por `hex_id` com filtro de dataset (`pyarrow`), uma linha por consulta —
    por isso o arquivo é ÚNICO e não particionado, ao contrário dos hexágonos.

    ABORTA se uma coluna de origem sumir da base. Gravar um parquet sem ela faria a tela
    dizer "sem leitura de mercado para este hexágono" — a MESMA mensagem de arquivo
    ausente —, e o operador procuraria o defeito no lugar errado.
    """
    faltando = [c for c in MERCADO_DE_PARA if c not in hx.columns]
    if faltando:
        raise SystemExit(
            f"ERRO: a base de hexágonos não tem {faltando}. A camada de mercado sai de "
            "`sam_mercado_argentina.py` — rode-o antes do exportador."
        )

    out = hx[list(MERCADO_DE_PARA)].rename(columns=MERCADO_DE_PARA).copy()
    out["hex_id"] = out["hex_id"].astype(str)
    for col in out.columns:
        if col != "hex_id":
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # Hexágono repetido faria a consulta por `hex_id` devolver a linha errada (o backend
    # pega `slice(0, 1)`); duplicata aqui é base montada errada, não caso de borda.
    dup = int(out["hex_id"].duplicated().sum())
    if dup:
        raise SystemExit(f"ERRO: {dup} hex_id duplicados na camada de mercado.")

    dest_staging.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dest_staging / "hexagonos_mercado_mapeado.parquet", index=False)

    com_sam = int((out["sam_fitness_potencial"] > 0).sum())
    com_res = int((out["oferta_efetiva_disponivel"] > 0).sum())
    print(f"  mercado: {len(out):,} hexes ({com_sam:,} com SAM, {com_res:,} com residual)")
    return len(out)


def escrever_logos(saida: Path, redes: set[str]) -> None:
    """Logos das redes no layout que o piloto le: `logo_<slug>.png`.

    POR QUE ISTO EXISTE. O piloto resolve o pino de cada rede em
    `COMPETITOR_LOGO_FILES.get(rede)` — um dicionario FIXO de redes brasileiras. "SportClub",
    "Megatlon" e as demais nao estao la, entao todas caiam no quadrado de cor + sigla, e o
    mapa argentino aparecia sem nenhuma marca (relato do Juan, 2026-08-26). O lado do piloto
    tambem muda (patch `logo por slug` em `piloto_rep/`); esta funcao e' a metade daqui:
    entregar os arquivos com o nome que aquele slug produz.

    O SLUG E' DERIVADO DA REDE, nao de uma tabela. `"Megatlon"` -> `megatlon`,
    `"ON FIT"` -> `on_fit`, `"Smart Fit"` -> `smart_fit` (que por acaso ja e' a chave
    brasileira, entao a Smart Fit funciona dos dois jeitos). Uma tabela aqui teria de ser
    mantida em dois repositorios e envelheceria calada.

    PARCEIRA HERDA A MARCA DA REDE. "SportClub (parceira)" e' casa de terceiro com a placa
    da rede na porta: no mapa ela mostra a mesma logo. Isso e' feito por ARQUIVO (uma copia
    com o slug da parceira) e nao por regra no piloto — assim o piloto continua com uma
    regra so', e quem decide o que herda de quem e' quem conhece as redes.

    Rede sem logo coletada (HammerX nao tem site ativo) simplesmente nao ganha arquivo, e o
    piloto cai no quadrado com a sigla — que e' o comportamento certo para "nao tenho".
    """
    origem = _exigir_caminhos().fonte("concorrentes", "logos")
    if not origem.is_dir():
        print("  [aviso] dados/concorrentes/logos ausente — os pinos sairao com sigla")
        return
    dest = saida / "logos"
    dest.mkdir(parents=True, exist_ok=True)
    for velho_png in dest.glob("logo_*.png"):
        velho_png.unlink()

    # slug do NOME do arquivo coletado (`smart-fit.png` -> `smart_fit`) para casar com o
    # slug da REDE (`Smart Fit` -> `smart_fit`).
    disponiveis = {_slug_rede(f.stem): f for f in origem.glob("*.png")}
    escritos, faltando = [], []
    for rede in sorted(redes):
        slug = _slug_rede(rede)
        # "sportclub_parceira" nao tem arquivo proprio: herda o da rede-mae, tirando o
        # sufixo. Generico de proposito — vale para qualquer rede que ganhe parceiras.
        fonte = disponiveis.get(slug) or disponiveis.get(slug.replace("_parceira", ""))
        if fonte is None:
            faltando.append(rede)
            continue
        shutil.copyfile(fonte, dest / f"logo_{slug}.png")
        escritos.append(slug)
    print(f"  logos: {len(escritos)} redes com marca "
          + (f"· sem logo: {', '.join(faltando)}" if faltando else ""))
    print(f"         MOTOR_COMPETITORS_LOGO_DIR={dest}")


def escrever_fotos(saida: Path, fotos: set[str]) -> None:
    """Copia para a saida SO as fotos das unidades que viraram pino.

    A pasta de origem tem 8.729 arquivos de coletas acumuladas; o recorte de hoje usa uma
    fracao. Copiar tudo levaria centenas de MB de imagem morta para dentro do diretorio que
    o piloto monta — e um diretorio de dados que so' cresce e' um que ninguem limpa depois.
    """
    origem = _exigir_caminhos().fonte("concorrentes", "fotos")
    if not origem.is_dir() or not fotos:
        return
    dest = saida / "fotos"
    dest.mkdir(parents=True, exist_ok=True)
    for velha in dest.glob("*.jpg"):
        velha.unlink()
    copiadas = 0
    for nome in sorted(fotos):
        f = origem / nome
        if f.is_file():
            shutil.copyfile(f, dest / nome)
            copiadas += 1
    print(f"  fotos: {copiadas:,} unidades com imagem no balao")
    print(f"         MOTOR_COMPETITORS_PHOTO_DIR={dest}")


def _slug_rede(nome: str) -> str:
    """`"Megatlón"` -> `megatlon`. Mesma regra que o piloto aplica do outro lado."""
    puro = "".join(
        c for c in unicodedata.normalize("NFD", str(nome))
        if unicodedata.category(c) != "Mn"
    ).lower()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", puro)).strip("_")


def _fonte(*partes: str) -> Path:
    """Caminho do insumo: `dados/` do repo, com fallback no pacote do handoff."""
    p = _exigir_caminhos().fonte(*partes)
    if p.exists():
        return p
    return p


def escrever_malha(saida: Path, sigla_por_prov: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Malha administrativa no lugar da malha municipal do IBGE.

    O piloto resolve "em que municipio caiu este ponto" por ponto-em-poligono sobre
    `<data>/ibge/municipios_<UF>.geojson` (`api/service._carregar_malha`). Sem esses
    arquivos ele levanta **500 "Malha municipal IBGE ausente ou vazia"** — era o erro
    seguinte ao da caixa de coordenada, e a analise de ponto morria ali.

    O analogo argentino e' o DEPARTAMENTO (partido, em Buenos Aires). O leitor do
    piloto aceita `codarea`, `CD_MUN` ou `cod_municipio` como codigo; usamos
    `codarea` com o id de 5 digitos do IGN, que e' a MESMA chave de
    `cod_departamento` no parquet de hexagonos — entao o municipio resolvido casa
    com a particao que o piloto vai ler em seguida.

    Devolve `{cod_departamento: (sigla_provincia, nome_departamento)}`, que a base
    setorial reusa para nao repetir o mesmo casamento.
    """
    import json

    fonte = _fonte("malha_admin", "departamentos.geojson")
    if not fonte.exists():
        print("  [aviso] departamentos.geojson ausente — a analise de ponto dara 500")
        return {}

    dados = json.loads(fonte.read_text(encoding="utf-8"))
    por_sigla: dict[str, list] = {}
    mapa_dep: dict[str, tuple[str, str]] = {}
    fora = 0
    for feat in dados.get("features", []):
        props = feat.get("properties") or {}
        prov = props.get("provincia")
        nome_prov = prov.get("nombre") if isinstance(prov, dict) else None
        sigla = sigla_por_prov.get(str(nome_prov))
        if not sigla:
            fora += 1
            continue
        cod = str(props.get("id") or "").strip()
        nome_dep = str(props.get("nombre") or cod)
        if not cod or not feat.get("geometry"):
            continue
        mapa_dep[cod] = (sigla, nome_dep)
        por_sigla.setdefault(sigla, []).append(
            {
                "type": "Feature",
                "geometry": feat["geometry"],
                "properties": {"codarea": cod, "nome": nome_dep, "provincia": nome_prov},
            }
        )

    dest = saida / "ibge"
    dest.mkdir(parents=True, exist_ok=True)
    for sigla, feats in sorted(por_sigla.items()):
        (dest / f"municipios_{sigla}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
            encoding="utf-8",
        )
    print(f"  malha: {len(mapa_dep):,} departamentos em {len(por_sigla)} arquivos"
          + (f" · {fora} fora do universo exportado" if fora else ""))
    return mapa_dep


def localidade_por_radio(r: pd.DataFrame) -> dict:
    """De cada radio para a LOCALIDADE que o contém — o análogo argentino do bairro.

    POR QUE PRECISA EXISTIR. A página "Perfil do Bairro/Distrito" do relatório pontual
    resolve a unidade por `cod_bairro` e, no fallback, por `nome_distrito`. O export
    argentino não emitia nenhuma das duas, então `agregar_perfil_bairro_distrito` devolvia
    o default com `flag_perfil_disponivel=False` e a página inteira saía "Perfil não
    disponível — Fora da malha de setores ou unidade sem dado suficiente" (Juan,
    2026-08-31). Não era falta de dado: era falta de EXPORTAR o dado.

    A unidade é a LOCALIDADE (`dados/malha_admin/localidades.geojson`, 4.037 nomeadas), e
    não o departamento — o departamento já viaja como `nome_municipio`, e repeti-lo aqui
    faria a página dizer a mesma coisa que a linha acima dela.

    A malha de localidades é de PONTOS, não de polígonos — 4.037 pontos, um por localidade.
    Por isso a junção é por VIZINHO MAIS PRÓXIMO, e não `within`: ponto-em-polígono devolve
    zero de 66.502 (foi o que aconteceu na primeira tentativa).

    O TETO de {TETO_BAIRRO_GRAUS:g}° (~5 km em latitude) é o que impede o vizinho mais
    próximo de virar absurdo. Em CABA os barrios distam ~1 km e o teto nunca morde; num
    radio de estepe patagônica, a localidade mais próxima pode estar a 80 km, e herdar o
    nome dela seria inventar um bairro que não existe. Radio além do teto fica FORA do
    dicionário: o `.map` deixa `NaN`, o piloto trata como ausente e aquele ponto cai no
    "não disponível" — que ali é a verdade.

    O teto é medido em GRAUS, não em metros: reprojetar a Argentina inteira (de -22° a
    -55°) para um CRS métrico exigiria escolher zona, e um teto grosseiro de sanidade não
    paga essa complexidade. O grau de latitude é constante (~111,3 km); o de longitude
    encolhe com a latitude, o que torna o teto mais APERTADO no sul — conservador, que é o
    lado certo para errar.

    A geometria do radio chega em WKB (é assim que ela viaja no parquet), então o ponto de
    junção é construído aqui, pelo `representative_point`.
    """
    arq = _fonte("malha_admin", "localidades.geojson")
    if not arq.exists():
        print("  [aviso] localidades.geojson ausente — o Perfil do Bairro sai indisponível")
        return {}

    import geopandas as gpd
    from shapely import wkb as _wkb

    loc = gpd.read_file(arq)[["nombre", "geometry"]]
    loc = loc[loc["nombre"].notna() & loc.geometry.notna()]
    if loc.empty:
        return {}

    def _ponto(g):
        try:
            return _wkb.loads(bytes(g)).representative_point()
        except Exception:  # geometria malformada -> radio sem bairro, sem derrubar o export
            return None

    pontos = gpd.GeoDataFrame(
        {"COD_2022": r["COD_2022"].values},
        geometry=[_ponto(g) for g in r["geometry"]],
        crs=loc.crs,
    )
    pontos = pontos[pontos.geometry.notna()]
    if pontos.empty:
        return {}

    j = gpd.sjoin_nearest(
        pontos, loc, how="inner", max_distance=TETO_BAIRRO_GRAUS, distance_col="_d"
    )
    # Empate exato de distância (duas localidades no mesmo ponto): fica a primeira,
    # deterministicamente, em vez de o radio aparecer duas vezes no dicionário.
    j = j.sort_values(["COD_2022", "_d"]).drop_duplicates(subset="COD_2022", keep="first")
    print(f"  localidades: {len(j):,} de {len(r):,} radios com bairro "
          f"({100 * len(j) / max(len(r), 1):.1f}%)")
    return dict(zip(j["COD_2022"], j["nombre"], strict=False))


def escrever_setores_geo(saida: Path, mapa_dep: dict[str, tuple[str, str]],
                         hx: pd.DataFrame) -> None:
    """Radios censales no lugar dos setores censitarios do IBGE.

    Resolvido o departamento, o piloto le
    `outputs/setores_censitarios_2022_geo/uf=<UF>/cod_municipio=<cod>/` e recorta os
    setores pelo raio de 1 km. Sem isso ele devolve **404 `base_geo_ausente`**.

    PROJECAO — nao ha reprojecao a fazer. O piloto trata a geometria como
    `EPSG:4674` (SIRGAS 2000) e reprojeta para uma azimutal equidistante CENTRADA
    NO PROPRIO PONTO (`censo_point._local_metric_crs`), o que funciona em qualquer
    lugar do planeta. Os radios do INDEC vem em WGS84, e a diferenca entre os dois
    datums e' centimetrica — irrelevante na area de um setor.

    RENDA — o INDEC nao publica renda por radio; o motor argentino a modela por
    HEXAGONO. Trazemos de volta pela ponte `radios_nacional_h3` (COD_2022 -> h3, com
    fracao de area), como media ponderada pela fracao. E' a MESMA renda que o
    hexagono mostra, redistribuida: nao inventa precisao que o modelo nao tem, e o
    numero do raio fecha com o da celula.
    """
    import numpy as np
    from shapely import wkb as _wkb

    arq_radios = _fonte("censo_indec", "radios-2022.parquet")
    if not arq_radios.exists():
        print("  [aviso] radios-2022.parquet ausente — a analise de ponto dara 404")
        return

    r = pd.read_parquet(arq_radios)
    r["cod_departamento"] = (
        r["PROV"].astype(str).str.zfill(2) + r["DEPTO"].astype(str).str.zfill(3)
    )

    # --- localidade (o "bairro" do Perfil do Bairro/Distrito) -----------------
    bairro_por_radio = localidade_por_radio(r)

    # --- renda e score por radio, pela ponte com o hexagono ------------------
    #
    # DUAS MUDANCAS em 2026-09-02, e a segunda nao e so consequencia da primeira.
    #
    # (1) O score e RECOMPUTADO nas ancoras do perfil, como no mapa (`score_do_pais`).
    #
    # (2) Ele e recomputado a partir da renda e da populacao AGREGADAS ao radio — e nao
    #     pela media ponderada dos scores dos hexagonos que o cobrem. Media de score nao
    #     e score da media: a nota de populacao e LOGARITMICA e a formula ainda leva um
    #     ajuste executivo com degraus em 25 e 75. Promediar depois de aplicar as duas
    #     coisas devolve um numero que nao corresponde a radio nenhum. O original fazia a
    #     media porque so tinha o score pronto para carregar; com o recompute disponivel,
    #     agregar os INSUMOS e a ordem certa.
    renda_por_radio: dict = {}
    score_por_radio: dict = {}
    arq_ponte = _fonte("renda_modelo", "radios_nacional_h3.parquet")
    if arq_ponte.exists():
        ponte = pd.read_parquet(arq_ponte, columns=["COD_2022", "h3", "frac"])
        base = hx[["h3_id", "renda_estimada_usd", "pop_total"]]
        ponte = ponte.merge(base, left_on="h3", right_on="h3_id", how="inner")
        ponte["w"] = pd.to_numeric(ponte["frac"], errors="coerce").clip(lower=0).fillna(0)
        ponte = ponte[ponte["w"] > 0]
        if not ponte.empty:
            ponte["_r"] = ponte["renda_estimada_usd"] * ponte["w"]
            # Renda e MEDIA ponderada (intensiva); populacao e SOMA (extensiva) — o radio
            # tem a fracao de gente de cada hexagono que ele cobre, nao a media dela.
            ponte["_p"] = ponte["pop_total"] * ponte["w"]
            g = ponte.groupby("COD_2022")[["_r", "_p", "w"]].sum()
            renda_radio = g["_r"] / g["w"]
            pop_radio = g["_p"]
            renda_por_radio = renda_radio.to_dict()
            score_por_radio = dict(
                zip(g.index, score_do_pais(renda_radio.values, pop_radio.values), strict=False)
            )

    # --- area do radio, em m2 -----------------------------------------------
    # Aproximacao local (grau x grau no centroide do proprio radio). Basta para o
    # PESO de intersecao: o piloto recalcula a area exata na azimutal centrada no
    # ponto quando faz o recorte de 1 km.
    def _area_m2(g) -> float:
        try:
            s = _wkb.loads(bytes(g))
            return float(s.area) * 111_320.0 * 110_540.0 * abs(np.cos(np.radians(s.centroid.y)))
        except Exception:
            return float("nan")

    dest = saida / "outputs" / "setores_censitarios_2022_geo"
    shutil.rmtree(dest, ignore_errors=True)

    escritos = particoes = sem_dep = 0
    for dep, grupo in r.groupby("cod_departamento", sort=True):
        info = mapa_dep.get(str(dep))
        if not info:
            sem_dep += len(grupo)
            continue
        sigla, nome_dep = info
        d = dest / f"uf={sigla}" / f"cod_municipio={dep}"
        d.mkdir(parents=True, exist_ok=True)

        pop = pd.to_numeric(grupo["POB_TOT_P"], errors="coerce").fillna(0.0)
        viv = pd.to_numeric(grupo["VIV_TOT_P"], errors="coerce").fillna(0.0)
        area = grupo["geometry"].map(_area_m2)
        moradores = (pop / viv.where(viv > 0)).clip(lower=1.0, upper=10.0)
        renda = grupo["COD_2022"].map(renda_por_radio)
        score = grupo["COD_2022"].map(score_por_radio)

        pd.DataFrame(
            {
                "cod_setor": grupo["COD_2022"].astype(str).values,
                "uf": sigla,
                "cod_municipio": str(dep),
                "nome_municipio": nome_dep,
                # `nome_distrito` e' o FALLBACK que `agregar_perfil_bairro_distrito` usa
                # quando nao ha `cod_bairro`. Sem ele, "Perfil nao disponivel".
                "nome_distrito": grupo["COD_2022"].map(bairro_por_radio).values,
                "geometry_wkb": grupo["geometry"].values,
                "area_setor_m2": area.values,
                "pop_total_setor_2022": pop.values,
                "domicilios_particulares_ocupados_setor_2022": viv.values,
                "renda_per_capita_setor_2022_calibrada": renda.values,
                "renda_per_capita_domiciliar_setor": renda.values,
                # Moradores por domicilio, do proprio censo argentino (pop / viviendas).
                # Sem esta coluna o relatorio de ponto divide por NaN e a renda sai
                # `null` — foi exatamente o que aconteceu no primeiro teste.
                "avg_moradores_domicilio_setor_2022": moradores.values,
                # RENDA DOMICILIAR do radio. A coluna tem nome brasileiro porque é o
                # que o piloto lê, mas o papel dela é "a renda que, multiplicada pelo
                # uplift de composição, vira renda do domicílio". No Brasil o Censo
                # publica a renda do RESPONSÁVEL e o uplift (1,632) faz a conversão;
                # o modelo argentino já entrega PER CAPITA, então aqui a coluna já sai
                # na escala domiciliar e o uplift é identidade — o piloto sabe disso
                # por `MOTOR_PAIS` (ver `_censo_publica_renda_do_responsavel`).
                #
                # Antes esta linha dividia por 1,632 para o fator cancelar no outro
                # lado. Funcionava, mas prendia este arquivo a uma constante do
                # repositório do piloto: se ela mudasse lá, a renda argentina
                # escorregaria em silêncio. Agora nenhum número emprestado atravessa
                # a fronteira.
                "renda_responsavel_media_setor_2022": (renda.values * moradores.values),
                "densidade_pop_setor_hab_km2": np.where(
                    area.values > 0, pop.values / (area.values / 1_000_000.0), np.nan
                ),
                "score_setor_2022_calibrado": score.values,
                "flag_renda_disponivel": renda.notna().values,
                "flag_geometria_valida": (area.notna() & (area > 0)).values,
                "qualidade_join_uf": "ok",
            }
        ).to_parquet(d / "part-000.parquet", index=False)
        escritos += len(grupo)
        particoes += 1

    com_renda = len(renda_por_radio)
    print(f"  setores: {escritos:,} radios em {particoes} departamentos "
          f"· {com_renda:,} com renda modelada"
          + (f" · {sem_dep:,} radios fora do universo" if sem_dep else ""))


def main(argv: list[str] | None = None) -> int:
    # CONSOLE WINDOWS. Sem isto o `print` morre com UnicodeEncodeError em qualquer caractere
    # fora do cp1252 — e morre DEPOIS de `escrever_particoes`, deixando a saida pela metade:
    # sem malha (`ibge/`, o piloto da 500), sem setores (404), sem pinos, sem logos e sem
    # fotos. Numa pasta limpa sobram 24 arquivos em vez de 3.730. O guarda-corpo de
    # `piloto_rep/previa.ps1` so' testa se a PASTA existe — ela existe, ele passa, e o piloto
    # sobe servindo meio pais sem ninguem ver erro. Todos os outros pipelines de saida ja'
    # faziam isto; este era o unico sem, e foi reproduzido em 2026-08-31.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dados",
        type=Path,
        required=True,
        help="raiz da árvore de dados argentina (a `dados/` do pacote)",
    )
    ap.add_argument("--hex", type=Path, default=None,
                    help="parquet de hexágonos (default: <dados>/hexagonos_h3)")
    ap.add_argument("--saida", type=Path, default=None,
                    help="destino (default: <dados>/../outputs/motor_data_ar)")
    ap.add_argument(
        "--perfil",
        type=Path,
        default=Path("data/perfis/AR/perfil.json"),
        help="perfil do país — de onde saem as ÂNCORAS do score recomputado",
    )
    args = ap.parse_args(argv)

    global CAMINHOS, PERFIL
    saida = args.saida or (args.dados.parent / "outputs" / "motor_data_ar")
    CAMINHOS = Caminhos(args.dados, saida)

    # O perfil e lido AQUI e nao dentro das funcoes: as ancoras do score tem de ser as
    # mesmas para o pacote inteiro, e um perfil trocado no meio da exportacao produziria
    # partições com reguas diferentes — o tipo de defeito que nao aparece em teste nenhum.
    if not args.perfil.exists():
        print(f"ERRO: perfil não encontrado em {args.perfil} — sem ele não há âncoras.")
        return 1
    PERFIL = carregar_perfil(args.perfil)
    print(f"  perfil: {PERFIL.pais} ({PERFIL.nome}) · âncoras {PERFIL.ancoras()}")

    arq = args.hex or _exigir_caminhos().fonte("hexagonos_h3")
    if not Path(arq).exists():
        print(f"ERRO: base de hexágonos não encontrada em {arq}")
        return 1

    dest_hex = saida / "outputs" / "hexagonos_dashboard_enriquecido"

    hx = pd.read_parquet(arq)
    print(f"  lidos {len(hx):,} hexágonos, {len(hx.columns)} colunas")

    # --- SÓ OS HABITÁVEIS ---------------------------------------------------
    # A base do piloto é de hexágonos HABITÁVEIS — a própria narrativa dele diz
    # "N hexágonos habitáveis". Mandar a grade argentina inteira não é só feio, é outra
    # população de células:
    #
    #     mediana de pop_total   Brasil (SP)  20.250
    #                            Argentina        40   <- grade inteira
    #                            Argentina     2.236   <- só habitáveis
    #
    # 83,6% das células têm `hex_sem_populacao = True`: o valor de população ali é
    # resíduo do modelo, não gente. Com elas dentro o mapa abre vazio E a câmera cai no
    # meio do pampa, porque o piloto centra na MÉDIA SIMPLES de lat/lng. Nenhum
    # "abrir agora" se perde no filtro.
    antes = len(hx)
    habitaveis = set(hx.loc[~hx["hex_sem_populacao"].astype(bool), "h3_id"])

    # --- MOLDURA: os habitáveis MAIS o anel de vizinhos imediatos -------------
    # Só os habitáveis deixavam a malha esburacada: 21,7% das células ficavam com
    # 0 ou 1 vizinho na base, e o mapa lia como quebrado — hexágono solto pendurado,
    # borda serrilhada, buraco no meio do aglomerado. Não era geometria (o
    # `highPrecision` já resolveu isso); era a AUSÊNCIA das células vizinhas.
    #
    # Medido, sobre a base nacional:
    #     só habitáveis      6.956 hexes · 21,7% ilhados
    #     + anel de 1       15.186 hexes ·  2,7% ilhados   <- esta
    #     todos             42.388 hexes ·  3,2% ilhados
    #
    # O anel custa menos da metade das células de "todos" e resolve quase tudo. E é
    # honesto: são exatamente os hexágonos que fazem FRONTEIRA com área povoada.
    # Entram com os próprios números (não são inventados), e o piloto já os pinta
    # em cinza sozinho, porque caem no corte de população — viram moldura, não dado.
    #
    # O que NÃO se resolve: nem "todos" chega a zero, porque a própria grade
    # nacional tem buracos (célula sem terra, litoral, corpo d'água).
    anel = set()
    for c in habitaveis:
        anel.update(h3.grid_disk(c, 1))
    manter = (habitaveis | anel) & set(hx["h3_id"])

    hx = hx[hx["h3_id"].isin(manter)].copy()
    n_moldura = len(hx) - len(habitaveis)
    print(f"  habitáveis: {len(habitaveis):,} + moldura de vizinhos: {n_moldura:,} "
          f"= {len(hx):,} (de {antes:,})")
    if hx.empty:
        print("ERRO: nenhum hexágono habitável — base errada?")
        return 1

    out = montar_hexagonos(hx)
    linhas, sigla_por_prov = escrever_particoes(out, hx["nome_provincia"], dest_hex)
    print(f"\n  escritos {linhas:,} hexes em {len(list(dest_hex.glob('uf=*')))} partições")

    redes, fotos = escrever_concorrentes(saida / "staging")
    escrever_mercado(saida / "staging", hx)
    escrever_logos(saida, redes)
    escrever_fotos(saida, fotos)

    # A ANALISE DE PONTO precisa de mais duas camadas, e cada uma falha de um
    # jeito diferente: sem a malha o piloto da 500 ("Malha municipal IBGE ausente
    # ou vazia"), sem os setores da 404 ("base_geo_ausente"). Nenhum dos dois
    # aparece antes de alguem colar uma coordenada.
    mapa_dep = escrever_malha(saida, sigla_por_prov)
    if mapa_dep:
        escrever_setores_geo(saida, mapa_dep, hx)

    # --- sanidade: o corte do piloto tem de deixar algo em pé ----------------
    # Um export "bem-sucedido" que apaga o país inteiro na tela é o modo de falhar mais
    # caro aqui, porque não levanta erro nenhum — o mapa só fica cinza.
    acionaveis = int((out["populacao_corte_hex"] >= POP_MIN_PILOTO).sum())
    pct = 100 * acionaveis / max(len(out), 1)
    print(f"  acionáveis no corte de {POP_MIN_PILOTO:,} do piloto: {acionaveis:,} ({pct:.1f}%)")
    if acionaveis == 0:
        print("ERRO: nenhum hexágono sobrevive ao corte — o mapa sairia todo cinza.")
        return 1

    print(f"\n  MOTOR_DATA_DIR={saida}")
    print("  (o pais vem do perfil.json na raiz do MOTOR_DATA_DIR, nao de env)")
    return 0


# ---------------------------------------------------------------------------
# Armadilhas já pagas — não repetir
# ---------------------------------------------------------------------------
# 1. Código de província: ver o bloco SIGLA_PROVINCIA (2 letras, sem colidir com o BR).
# 2. Pasta de partição vazia vira estado fantasma no seletor — ver `_limpar`.
# 3. NÃO passe `MOTOR_DATA_DIR` dentro da string do `cmd` (`set VAR=... &&`): o "Á" de
#    "Área de Trabalho" vira "??" e o `set` engole o espaço antes do `&&`. O piloto sobe
#    com `data_ok: false`. Passe pelo ambiente do shell, que o processo filho herda.
# 4. O uplift de composição familiar. A renda do relatório de ponto sairia 63% acima da
#    real se o fator brasileiro de 1,632 fosse aplicado sobre `renda_responsavel_media_
#    setor_2022`, que aqui JÁ está na escala domiciliar. A armadilha continua existindo;
#    o que mudou é a defesa: era `MOTOR_PAIS=AR` no ambiente, e passou a ser
#    `reguas.uplift_composicao = 1.0` no `perfil.json` argentino — multiplicador, não
#    variável de ambiente, e por isso não é um ramo de código por país (DEC-047).
# 5. O símbolo da moeda NÃO é mais problema. Até o Bloco A o piloto rotulava "R$" fixo
#    (`format.ts`), então a renda em USD saía com símbolo errado; agora ele lê
#    `moeda.simbolo` do perfil, e o argentino diz "$".

if __name__ == "__main__":
    sys.exit(main())
