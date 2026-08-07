# Camada de crescimento municipal (passo 4 do piloto web)

> Contrato de dados e runbook de publicação da camada "Como as cidades estão indo".
> Ligada em produção em 2026-08-07. READ-ONLY sobre o M1: não recalcula score, não toca
> pesos nem artefato oficial.

## 1. O que é

Passo 4 do funil do piloto web. Responde "esta cidade está crescendo?" cruzando emprego
formal, abertura de empresas, salário e (onde há cobertura de satélite) obra nova por
hexágono. Alimenta o número grande do passo 4, o ranking de cidades, a narrativa municipal
e a cor dos hexágonos no mapa.

## 2. Artefatos

Ambos vivem **só** em `data/staging/`. Não estão no git (`.gitignore:26` corta `*.parquet`)
nem na imagem (`.dockerignore` corta `data/`): em produção chegam **exclusivamente** pelo
bind mount `/opt/motor-expansao/data/staging:/app/data/staging:ro`, já declarado no
`docker-compose.prod.yml` para `web` e `api`. **Não é preciso mexer no compose.**

| arquivo | linhas | colunas | chave |
|---|---|---|---|
| `crescimento_municipal.parquet` | 5.571 (todos os municípios) | 33 | `cod6` (IBGE 6 dígitos, sem DV) |
| `crescimento_hex.parquet` | 41.135 | 3 | `hex_id` (H3 res-7) |

**Não são reproduzíveis só com este repo.** Rodar `data/reports/crescimento/03_artefato.py`
isolado recria o municipal com **15 das 33 colunas** — HTTP 200, sem erro e sem log, mas o
passo 4 perde veredito e gráfico. Se precisar regerar, rode a cadeia completa (`01`..`10`).
Guarde uma cópia fora do repo.

## 3. Contrato consumido pelo código

`web/server/app.py` projeta 13 das 33 colunas (`_COLS_CRESCIMENTO`); as outras 20 são peso
morto de disco, nunca carregadas em memória. A leitura é defensiva (`[c for c in _COLS if c
in disponiveis]`), então coluna ausente degrada em vez de estourar.

**Join municipal.** `cod_municipio` (7 dígitos) → `str[:6]` → `cod6`. Onde `cod_municipio`
é nulo (21 das 27 UFs), o fallback é por `cres_chave_nome`, no formato `UF|NOME` normalizado.
Cobertura medida em 2026-08-07: **`v_frase` chega em 1.542.006 de 1.542.531 hexes (99,97%)**.

**Join hex.** `hex_id` res-7, `validate="m:1"`. 41.135 de 41.135 casam — zero órfão.
Cobre 12 UFs: BA, CE, DF, ES, GO, MG, PE, PR, RJ, RS, SC, SP.

**Domínios fechados** (valor fora disso quebra a cor do SPA, que compara literal):

| coluna | valores |
|---|---|
| `cres_hex_classe` | `Em alta`, `Estavel`, `Sem obra nova` |
| `cres_tendencia` | `Em alta`, `Em queda`, `Estavel`, nulo (39%) |
| `cres_confiab` | `alta`, `media`, `baixa`, `muito_baixa` |

Os valores brutos são **sem acento** de propósito (§2 do CLAUDE.md: identificador/enum não
acentua); o acento entra na camada de label (`_ROTULO_TEND`/`_ROTULO_CLASSE`).

**Texto acentuado existe** em `v_frase`, `cres_setor`, `cres_dims` e `cres_series`, inclusive
caracteres **fora de latin-1** (`→`, `–`, `m²`). É seguro no caminho web (UTF-8), mas
**não pode ser reaproveitado no PDF** — o `fpdf2` com core font troca por `?` em silêncio.

## 4. Runbook de publicação

> O `LEIA-ME.txt` que acompanhou a primeira entrega tinha dois passos perigosos, corrigidos
> aqui. Use este procedimento.

**1. Enviar com nome temporário.** `scp` in-place tem uma janela em que o arquivo truncado
derruba `/api/uf`, `/api/municipio` e `/api/municipios` com **500** — e o `/api/health`
continua respondendo 200. O mount é de diretório, então `rename(2)` aparece no container na hora.

```bash
scp -i ~/.ssh/id_ultra_mcp crescimento_municipal.parquet \
    root@2.25.137.241:/opt/motor-expansao/data/staging/crescimento_municipal.parquet.tmp
scp -i ~/.ssh/id_ultra_mcp crescimento_hex.parquet \
    root@2.25.137.241:/opt/motor-expansao/data/staging/crescimento_hex.parquet.tmp
```

**2. Conferir antes de publicar.** Só siga se o md5 bater com a origem.

```bash
md5sum /opt/motor-expansao/data/staging/crescimento_*.parquet.tmp
```

**3. Publicar por rename atômico.**

```bash
chmod 0644 /opt/motor-expansao/data/staging/crescimento_*.parquet.tmp
mv -f .../crescimento_municipal.parquet.tmp .../crescimento_municipal.parquet
mv -f .../crescimento_hex.parquet.tmp       .../crescimento_hex.parquet
stat -c '%a %U:%G %n' /opt/motor-expansao/data/staging/crescimento_*.parquet   # 644 root:root
```

O container roda como `appuser` non-root (`Dockerfile.web`), e o mount é `:ro` — `644` basta.
**Não** faça `chown` no staging: o diretório é compartilhado com a `api`.

**4. Provar legibilidade ANTES de reiniciar.** Se falhar aqui, o container atual ainda serve
o estado anterior e você corrige sem downtime. Esperado: `33` e `3`.

```bash
docker exec motor_expansao_web python -c "import pyarrow.parquet as pq; [print(p, len(pq.read_schema(p).names)) for p in ('/app/data/staging/crescimento_municipal.parquet','/app/data/staging/crescimento_hex.parquet')]"
```

**5. Reiniciar.** `carregar_crescimento()` e `carregar_crescimento_hex()` são
`@functools.lru_cache(maxsize=1)` — o processo cacheia a **ausência** e nunca mais olha o
disco. Sem reiniciar, copiar não muda nada na tela.

```bash
docker restart motor_expansao_web
```

**Não use `up -d --force-recreate`**: ele recria a partir de `${WEB_IMAGE}` do `.env` e
reaplica a definição inteira do serviço — se o `.env` divergir do que está rodando, você troca
a versão do piloto junto com o dado e passa a ter duas causas para qualquer problema. Se
precisar do compose, `docker compose -f docker-compose.prod.yml restart web` também não toca
a imagem.

## 5. Validação pós-deploy

**`/api/health` não serve** — ele responde 200 com todas as rotas de mapa em 500.

```bash
docker exec -i motor_expansao_web python - <<'PY'
import json, urllib.request, urllib.parse
B="http://127.0.0.1:8899"
g=lambda p: json.load(urllib.request.urlopen(B+p, timeout=300))
js=g("/api/uf/SP"); p4=[x for x in js["passos"] if x["n"]==4][0]
print("funil_big", p4["funil_big"], "| itens", len(p4["itens"]),
      "| cres_mun", len(js.get("cres_mun") or {}),
      "| hexes com cor", sum(1 for h in js["hexes"] if h.get("cres_hex_classe")))
m=g("/api/municipio/SP/"+urllib.parse.quote("São Paulo"))
s=[x for x in m["passos"] if x["n"]==4][0]
print("dims/series", bool(s.get("dims")), bool(s.get("series")), "|", s["narrativa"][:60])
PY
```

Referência medida em 2026-08-07: `funil_big=156`, `itens=10`, `cres_mun=370`,
`hexes com cor=4.500`, `dims/series=True/True`, narrativa começando pelo veredito
("São Paulo está próxima da mediana nacional...").

Os três sinais que provam a camada viva, em ordem de valor:

1. **`dims` e `series` não-nulos** — se vierem `False` com o resto funcionando, o parquet foi
   gerado por execução parcial do pipeline (15 colunas em vez de 33).
2. **A narrativa começa pelo veredito**, não por "O emprego formal em ... está". A frase de
   fallback é a assinatura do artefato mutilado.
3. **`hexes com cor > 1000` em SP** — prova que o `crescimento_hex.parquet` casou.

**Faça o aceite em SP.** Em MT, AM e PA o passo 4 acende hexágonos **cinza**: no nível de UF
ele acende pelo emprego municipal, mas a cor vem do satélite, que só cobre 12 UFs. Não é
defeito.

## 6. Limitações conhecidas

- **3 municípios não casam por grafia IBGE divergente** (525 hexes): `Arês`/RN (artefato:
  `RN|AREZ`), `Açu`/RN (`RN|ASSU`) e `São Luiz`/RR (`RR|SAO LUIZ DO ANAUA`, nome histórico).
  Degradam certo: HTTP 200 com "Sem leitura de crescimento para X". Não há mapa de alias.
- **`MT|BOA ESPERANCA DO NORTE`** existe no crescimento e não na base Censo 2022 (município
  novo). O merge é `how="left"`, então não faz nada.
- **4 municípios com `cres_emp_pct` nulo** ficam fora do número grande e do ranking da visão
  de estado, embora tenham narrativa municipal.
- **78,5% dos municípios têm confiabilidade `baixa`/`muito_baixa`** e recebem o aviso na tela.
  `cres_tendencia` é nula exatamente onde a confiabilidade é `muito_baixa` — é defensivo, não
  falha de dado.
- **A camada é declarada opcional mas não é isolada:** um parquet corrompido derruba
  `/api/uf`, `/api/municipio` e `/api/municipios` com 500, e o healthcheck não percebe. Ver
  `BLK-CRESC-01` no backlog.

## 7. Rollback

Volta ao estado anterior (testado: 200 em todas as rotas sem os arquivos).

```bash
mkdir -p /opt/motor-expansao/data/_passo4_off
mv /opt/motor-expansao/data/staging/crescimento_municipal.parquet \
   /opt/motor-expansao/data/staging/crescimento_hex.parquet \
   /opt/motor-expansao/data/_passo4_off/
docker restart motor_expansao_web
```

Guarde essa pasta: os arquivos não estão no git nem na imagem.
