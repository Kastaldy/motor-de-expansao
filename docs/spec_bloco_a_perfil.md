# SPEC EXECUTÁVEL — Bloco A: o perfil do país

- Data: 2026-08-31 | Status: **PRONTA PARA CODAR** | Dono do arquivo: esta spec (o `docs/plano_multipais.md` e `docs/decisions/` têm outros donos e **não** são alterados por aqui)
- Escopo: **Bloco A da §5.0** do `plano_multipais.md` = **BLK-INTL-02** (parte de perfil), sob a **DEC-047**.
- Esforço declarado no plano: **7-11 dias · 1 dev**. Exige **`critica-aprovada`** (ver §8).
- Objetivo operacional: depois deste bloco, **nenhum literal brasileiro de identidade territorial, de moeda, de fonte de dado ou de régua absoluta vive em constante de módulo**. Todos são lidos de um objeto congelado resolvido uma vez no import.

---

## 0. Como ler esta spec — e uma correção de linha que você vai precisar

**Toda referência `arquivo:linha` desta spec foi conferida no working tree em 2026-08-31.**

> ⚠️ **AVISO QUE POUPA MEIA HORA.** As referências a `web/server/app.py` **acima da linha ~3200** no
> `docs/plano_multipais.md` estão **14 linhas defasadas** (o arquivo tem 8.647 linhas e cresceu depois
> que o plano foi escrito). A DEC-047 já registra a mesma defasagem para `limpar_caches`
> (`3092-3103` no plano → **`3106-3117`** de fato). Exemplos que você vai encontrar:
>
> | o plano diz | está de fato em | o quê |
> |---|---|---|
> | `app.py:3202` | **`:3216`** | `@app.get("/api/ufs")` |
> | `app.py:3513` | **`:3527`** | `def montar_metodologia` |
> | `app.py:3536` | **`:3550`** | `F_CENSO` |
> | `app.py:3539` | **`:3553`** | `F_CRES` |
> | `app.py:3612` | **`:3626`** | a frase "R$ 300 vale 0 e R$ 4.000 vale 100" |
> | `app.py:3939` / `:3964` | **`:3953`** / **`:3978`** | `/api/geocode` e `countrycodes: "br"` |
> | `app.py:4357`, `:4372`, `:4504` | **`:4371`**, **`:4386`**, **`:4518`** | as 3 chamadas de `validar_brasil` |
> | `app.py:4508`, `:5210`, `:7725`, `:7994` | **`:4522`**, **`:5224`**, **`:7739`**, **`:8008`** | os 4 sítios que constroem `Settings` |
> | `app.py:5524` | **`:5538`** | `@app.post("/api/viabilidade")` |
>
> **As linhas abaixo de ~3200 batem** (`_DEFAULT_DATA` `:99-101`, `DATA_DIR` `:102`, `OFERTA_DESTAQUE_MIN`
> `:153`, `SCORE_CORTE_QUENTE` `:161`, `_COLS_DESEJADAS` `:376`, `_UF_RE` `:412`, `carregar_uf` `:422`).
> Referências fora de `app.py` (coord.py, competitors.py, coord.ts, entrada-ponto.ts, calibrar_*) batem
> todas. **Nesta spec, todos os números são os CONFERIDOS**, não os do plano.

---

## 1. O schema do `perfil.json`

### 1.1 Regra de admissão de campo

**Um campo só entra se esta spec puder apontar a LINHA que o lê.** A coluna "quem lê" abaixo não é
documentação: é o critério. Campos que o §6.2 do plano lista mas que **nenhuma linha deste repositório
consome** estão na §1.4 (recusados), com o motivo — pôr um campo sem leitor é criar um número que
envelhece calado, que é exatamente a classe de defeito que a DEC-045 e a DEC-047 combatem.

### 1.2 O schema, campo a campo

`perfil.json` mora na **raiz do `MOTOR_DATA_DIR`**: `${MOTOR_DATA_DIR}/perfil.json`. As **fontes
versionadas** são `data/perfis/BR/perfil.json` e `data/perfis/AR/perfil.json` (§3.1) — e o BR é
também o default de dev/teste.

> ⚠️ **CORREÇÃO DE 2026-09-02 — "o deploy copia para a raiz do volume" era instrução IMPOSSÍVEL.**
> Esta linha dizia que o deploy copia a fonte certa "para a raiz do volume". **Não existe raiz de
> volume para copiar.** `/app/data` **não é** um mount: o `docker-compose.prod.yml` monta apenas
> **subdiretórios** dele — `outputs` (`:223`), `staging` (`:228`), `ibge` (`:229`), `ultra` (`:230`)
> e `oportunidades` (`:235`). O `/app/data` em si é diretório **da imagem** (`Dockerfile.web:85`,
> `mkdir -p /app/data`), e escrever nele no host não chega ao container. Com `MOTOR_DATA_DIR=/app/data`
> fixo em `Dockerfile.web:30` e repetido em `docker-compose.prod.yml:162`, o loader da §3.1 procura
> `/app/data/perfil.json` — **um caminho sem origem**. Como se chega ao arquivo está na
> **pré-condição de infra do A3** (§6.1); a prova está no critério de aceite nº 11 (§7).
>
> **A MESMA frase está em `data/perfis/LEIA-ME.md:29`**, e o diagrama de `:21-27` desenha
> `MOTOR_DATA_DIR/` como uma árvore única — o modelo mental que produziu o erro. Aquele arquivo
> **não é desta spec** e não foi editado aqui: fica registrado que precisa da mesma correção.

**Duas regras de admissão do loader, para o schema ser UM só** (acrescentadas em 2026-08-31, quando se
descobriu que esta tabela, o `data/perfis/LEIA-ME.md` §3.2 e os dois `perfil.json` entregues descreviam
**três** schemas diferentes — e que os dois arquivos entregues **não passariam** neste loader):

1. **Chave iniciada por `_` é comentário e o loader a IGNORA** — sem validar tipo, sem reprovar. É onde
   moram os campos da §1.4: nos arquivos entregues, `_rotulos`, `_particao`, `_subdivisoes`,
   `_metas_big_numbers`, `_idioma`, `geocode._sufixo` e `fontes._fator_temporal`. O conteúdo continua
   versionado e revisável em PR; promover um deles ao schema é apagar o `_` **e** acrescentar a linha
   que o lê, nessa ordem.
2. **Campo fora desta tabela e sem `_` é TOLERADO, não reprovado.** O fail-closed da §3.2 é sobre
   **ausência** e **tipo** do que a tabela exige; o que sobra passa. É o que deixa `reguas.score_pesos`,
   `reguas.taxa_fitness`, `reguas.faixas_*`, `avisos` e `operacao` viverem nos arquivos com leitor
   previsto em bloco POSTERIOR (B, C, C+) sem virarem contrato do Bloco A.

```jsonc
{
  "schema_versao": 1,
  "pais": "BR",
  "nome": "Brasil",
  "locale": "pt-BR",
  "moeda": { "codigo": "BRL", "simbolo": "R$" },
  "bbox": { "lat_min": -34.0, "lat_max": 5.5, "lng_min": -74.0, "lng_max": -28.0 },
  "vista_padrao": { "lat": -14.5, "lng": -52.9, "zoom": 3.4 },
  "geocode": {
    "countrycodes": "br",
    "idioma": "pt-BR",
    "regex_cp": "\\b(\\d{5})-?(\\d{3})\\b"
  },
  "fontes": {
    "censo":       { "nome": "Censo 2022 (IBGE)",
                     "detalhe": "Renda, domicílios e população por setor censitário — …" },
    "crescimento": { "nome": "CAGED, RAIS, Receita Federal e satélite",
                     "detalhe": "As quatro leituras de movimento do município: …" }
  },
  "reguas": {
    "renda_abs_min": 300.0,
    "renda_abs_max": 4000.0,
    "pop_abs_min": 1000.0,
    "pop_abs_max": 100000.0,
    "score_corte_quente": 30.0,
    "pop_min_acionavel": 5000,
    "oferta_destaque_min": 2000.0,
    "capacidade_concorrente": 2500.0,
    "capacidade_unidade_alunos": 2500
  },
  "superficies": ["mapa", "oportunidades", "imobiliaria", "executiva", "viabilidade"]
}
```

| campo | tipo | obrigatório | qual literal ele substitui, e **quem lê hoje** |
|---|---|---|---|
| `schema_versao` | `int`, `== 1` | **sim** | nada. Existe para o loader **falhar alto** quando um pacote antigo do Juan encontrar um loader novo. Leitor: o próprio validador (§3.4). |
| `pais` | `str`, `^[A-Z]{2}$` | **sim** | nada em produção **hoje**. Leitores criados neste bloco: a linha de log de boot (§3.3) e o teste do fio de alarme (§5.9). O campo `pais` em `GET /api/ufs` (`app.py:3216`) está **FORA** deste bloco por decisão da §5.0.2 do plano. |
| `nome` | `str`, não-vazio | **sim** | `"Brasil"` dentro de `"Coordenada fora do Brasil"` — `src/motor_expansao/api/coord.py:75`; e `'Essa coordenada está fora do Brasil…'` — `web/src/lib/entrada-ponto.ts:116`. |
| `locale` | `str` BCP-47 | **sim** | `'pt-BR'` em `new Intl.NumberFormat('pt-BR', …)` — `web/src/lib/format.ts:6`. |
| `moeda.simbolo` | `str`, não-vazio | **sim** | os `R$` de `web/src/lib/format.ts`: `:38`, `:39`, `:41` (`brl`), `:52`, `:53`, `:54` (`brlCurto`) e `:105` (`valorComUnidade`); e o `R$` da frase da âncora em `web/server/app.py:3626`. |
| `moeda.codigo` | `str` ISO-4217 | **sim** | nada hoje. Leitor criado neste bloco: nenhum — **mas ele é a chave que o Bloco C+ carimba no PDF/XLSX** (decisão 0.7). Único campo que entra sem leitor de produção, e entra **declarado**: se o Bloco C+ for cortado, este campo sai junto. |
| `bbox.lat_min/lat_max/lng_min/lng_max` | `float` | **sim** | as **seis** cópias do §2.1. Invariante validada: `lat_min < lat_max`, `lng_min < lng_max`, todos em `[-90,90]`/`[-180,180]`. |
| `vista_padrao.lat/lng/zoom` | `float` | **sim** | `VISTA_BRASIL = { longitude: -52.9, latitude: -14.5, zoom: 3.4 }` — `web/src/lib/mapa-ponto.ts:32`, consumido por `web/src/components/MapaPonto.tsx:63`. **Achado desta spec:** não está em nenhuma das listas do plano nem da DEC-047, e é superfície do DIA 1. |
| `geocode.countrycodes` | `str`, `^[a-z]{2}(,[a-z]{2})*$` | **sim** | `"countrycodes": "br"` em **dois** lugares: `web/server/app.py:3978` (a sétima restrição do plano) **e** `src/motor_expansao/api/maps_geocoder.py:246` (**oitava — achado desta spec**, não listada em lugar nenhum). |
| `geocode.idioma` | `str` BCP-47 | **sim** | `"Accept-Language": "pt-BR"` — `src/motor_expansao/api/maps_geocoder.py:256`. (`/api/geocode` **não** manda `Accept-Language` hoje; passa a mandar neste bloco.) |
| `geocode.regex_cp` | `str` (regex) | opcional (`null` = sem código postal) | `CEP_RE = re.compile(r"\b(\d{5})-?(\d{3})\b")` — `src/motor_expansao/api/maps_geocoder.py:32`. Consumido por `normalize_cep` (`:113`) e `split_address_cep` (`:119`). |
| `fontes.censo.nome` | `str` | **sim** | `F_CENSO = "Censo 2022 (IBGE)"` — `web/server/app.py:3550`. Usada em `:3570`, `:3617`, `:3642`, `:3671`. |
| `fontes.censo.detalhe` | `str` | **sim** | o parágrafo de `web/server/app.py:3572-3575` (contém "setor censitário", vocabulário brasileiro). |
| `fontes.crescimento.nome` | `str` | **sim** | `F_CRES = "CAGED, RAIS, Receita Federal e satélite"` — `web/server/app.py:3553`. Usada em `:3597`, `:3789`, `:3815`. |
| `fontes.crescimento.detalhe` | `str` | **sim** | o parágrafo de `web/server/app.py:3599-3603`. |
| `reguas.renda_abs_min` / `renda_abs_max` | `float` | **sim** | `RENDA_ABS_MIN = 300.0` / `RENDA_ABS_MAX = 4_000.0` — `src/motor_expansao/pipelines/calibrar_renda_setor_2022.py:89-90`; e a frase de `web/server/app.py:3626`. |
| `reguas.pop_abs_min` / `pop_abs_max` | `float` | **sim** | `POP_ABS_MIN = 1_000.0` / `POP_ABS_MAX = 100_000.0` — `calibrar_renda_setor_2022.py:91-92`; e a frase de `web/server/app.py:3627-3628`. |
| `reguas.score_corte_quente` | `float` | **sim** | `SCORE_CORTE_QUENTE = 30.0` — `web/server/app.py:161`. Leitor real: `_quente` (`:2085`). |
| `reguas.pop_min_acionavel` | `int` | **sim** | **duas** cópias: `web/server/app.py:154` e `src/motor_expansao/dashboard/constants.py:144`. Leitores: `_povoado` (`app.py:2090`), `app.py:2758`, `:2769`, `derive_pop_cut_columns` (`dashboard/data.py:571`). |
| `reguas.oferta_destaque_min` | `float` | **sim** | **duas** cópias: `web/server/app.py:153` e `src/motor_expansao/dashboard/relatorio_municipal.py:61`. Leitores: `_com_residual` (`app.py:2093`), `app.py:2145`, `relatorio_municipal.py:397`. |
| `reguas.capacidade_concorrente` | `float` | **sim** | `CAPACIDADE_CONCORRENTE_PADRAO = 2500.0` — `web/server/app.py:152`. Leitores: `_derivar` (`:804`), `_comporta_entrada` (`:2129`, `:2133`). |
| `reguas.capacidade_unidade_alunos` | `int` | **sim** | **três** cópias: `src/motor_expansao/dashboard/constants.py:379`, `web/src/lib/faixas.ts:84`, `web/src/lib/mapa-ponto.ts:49`. Leitores: `app.py:1802`, `faixas.ts:97-98`, `mapa-ponto.ts:61`, `medidor.ts:127`. |
| `superficies` | `list[str]`, subconjunto de `ABAS_VALIDAS` (`web/server/acesso.py:39`) | **sim** | nada **neste** bloco. O Bloco A apenas **carrega e valida**; quem consome é o Bloco C. Entra aqui porque o fail-closed do perfil precisa reprovar uma lista inválida **no boot**, não na primeira requisição. |

### 1.3 A escolha do `bbox` do Brasil — decisão que precisa estar escrita

**As seis cópias NÃO são iguais.** Conferido: são **três caixas distintas**.

| caixa | valor | onde |
|---|---|---|
| **B1** | lat `[-34.0, 5.5]`, lng `[-74.0, -28.0]` | `api/coord.py:13-14`; `web/src/lib/coord.ts:8`; `web/src/lib/entrada-ponto.ts:44` |
| **B2** | lat `[-33.75, 5.27]`, lng `[-73.99, -28.65]` | `api/maps_geocoder.py:171-172`; `dashboard/data.py:624-627` |
| **B3** | lat `[-34.0, 6.0]`, lng `[-75.0, -28.0]` | `dashboard/competitors.py:10-11` |

**`perfil.bbox` do Brasil = B1.** Justificativa, em uma linha cada:

1. **B1 nunca ESTREITA o que as rotas de coordenada já aceitam.** O plano avisa (§8, R1) que unificar
   sem o perfil "só pode significar todas recusando a capital, o que é regressão". Escolher B2 estreitaria
   `/api/ponto` e `/api/resolver-ponto`; escolher B3 os alargaria para fora do país.
2. **B1 contém os extremos reais do Brasil** (+5,27 Monte Caburaí; −33,75 Chuí; −73,99 Serra do Divisor;
   −28,85 Martin Vaz). **B2 exclui Martin Vaz** (`-28.65 <= -28.85` é falso) — ou seja, B2 já está errada hoje.
3. **B3 é mais larga só onde não há Brasil** (lat até 6,0 e lng até −75,0), então B1 não perde nada real
   ao substituí-la em `competitors.py`.

**Duas mudanças de comportamento produzidas por essa unificação, e ambas têm teste** (§5.2 e §5.3):
alargar B2 → B1 em `dashboard/data.py`, e estreitar B3 → B1 em `competitors.py`.

### 1.4 Campos RECUSADOS, com o motivo

| campo do §6.2 do plano | por que não entra |
|---|---|
| `idioma` (separado de `locale`) | Nenhum leitor. `format.ts:6` lê **locale**; `maps_geocoder.py:256` lê **`geocode.idioma`**. Dois campos para o mesmo dado é a duplicação que o bloco existe para matar. |
| `geocode.region` | **Zero leitores.** É parâmetro da Google Geocoding API; este repositório geocodifica com **Nominatim** (`app.py:3949`, `maps_geocoder.py:187`), que não tem `region`. |
| `geocode.sufixo` (ancoragem) | **Zero leitores.** Conferido: nem `app.py:3977-3980` nem `maps_geocoder.py:241-248` concatenam sufixo à query. |
| `rotulos {nivel1, nivel2, unidade_censitaria}` | Os leitores desses rótulos são as ~2.400 linhas de copy do front e os 453 textos de PDF — **BLK-INTL-12**, explicitamente fora desta onda (§5.0.2). O único texto de rótulo que o Bloco A precisa mover está coberto por `fontes.censo.detalhe`, que entra como string inteira. |
| `subdivisoes {código → nome}` | Leitor seria `_UF_RE` afrouxado — **BLK-INTL-04**, fora do caminho crítico (§5.0.2, dívida nº 1). |
| `reguas.taxa_fitness`, `metas_big_numbers`, `faixas_renda` | As metas do semáforo (`dashboard/censo_report.py:139-152`) e as faixas de renda só são lidas pelas superfícies `ponto` e `municipal`, que o Bloco C **bloqueia** no dia 1. Entram no BLK-INTL-10. |
| `fontes.fator_temporal` | Zero leitores. |
| `vista_padrao` do `BRASIL_CENTER` | `src/motor_expansao/dashboard/constants.py:145` (`BRASIL_CENTER = {"lat": -14.235, "lon": -51.9253}`) tem **zero consumidores** — conferido por grep em `src/` e `web/`. É constante morta. **Não** entra no perfil; deletá-la é housekeeping de outro PR. `vista_padrao` do perfil serve `mapa-ponto.ts:32`, que é vivo. |

---

## 2. A tabela de substituição, sítio a sítio

Legenda de classe: **[6BB]** = uma das seis cópias de bbox do plano · **[7ª]** = a sétima restrição
(`countrycodes`) · **[NOVO]** = sítio **achado por esta spec**, ausente do plano e da DEC-047.

### 2.1 As seis cópias de bbox + as achadas

| # | arquivo:linha (conferido) | literal de hoje | vira | nota |
|---|---|---|---|---|
| 1 | `src/motor_expansao/api/coord.py:13-14` | `BRASIL_LAT_MIN, BRASIL_LAT_MAX = -34.0, 5.5` / `BRASIL_LNG_MIN, BRASIL_LNG_MAX = -74.0, -28.0` | `PERFIL.bbox.*` | **[6BB]** Único leitor: `validar_brasil` (`:71-72`). Renomear a função para `validar_no_pais` é **opcional** e custa 3 call sites (`app.py:4371`, `:4386`, `:4518`) + `test_api_coord.py` — **fica para o Bloco B**; nesta onda só o corpo muda. |
| 2 | `src/motor_expansao/api/maps_geocoder.py:171-172` | `_BR_LAT_MIN, _BR_LAT_MAX = -33.75, 5.27` / `_BR_LNG_MIN, _BR_LNG_MAX = -73.99, -28.65` | `PERFIL.bbox.*` | **[6BB]** Leitores: `:233`, `:272`, `:350`. **Alarga** (B2 → B1). |
| 3 | `src/motor_expansao/dashboard/data.py:624-627` | `_BRAZIL_LAT_MIN = -33.75` … `_BRAZIL_LNG_MAX = -28.65` | `PERFIL.bbox.*` | **[6BB]** Leitor: `_validate_brazil_bbox` (`:631`), chamado em `:657`, `:666`, `:676`, `:686`. **Alarga** (B2 → B1) → quebra teste, §5.2. |
| 4 | `src/motor_expansao/dashboard/competitors.py:10-11` | `LAT_MIN, LAT_MAX = -34.0, 6.0` / `LNG_MIN, LNG_MAX = -75.0, -28.0` | `PERFIL.bbox.*` | **[6BB]** Leitor: `_coord_in_brazil` (`:469-470`). **Estreita** (B3 → B1) → §5.3. |
| 5 | `web/src/lib/coord.ts:8` | `const BR = { latMin: -34.0, latMax: 5.5, lngMin: -74.0, lngMax: -28.0 }` | `perfilDoCliente().bbox` | **[6BB]** Leitor: `noBrasil` (`:17-18`). Ver §3.5 (como o perfil chega ao front). |
| 6 | `web/src/lib/entrada-ponto.ts:44` | idem | `perfilDoCliente().bbox` | **[6BB]** Leitor: `:69`. **Sem esta linha, Buenos Aires é recusada ANTES de sair requisição.** |
| 7 | `src/motor_expansao/pipelines/normalizar_unidades_ultra.py:27-28` | `LAT_MIN, LAT_MAX = -34.0, 6.0` / `LNG_MIN, LNG_MAX = -75.0, -28.0` | **fica como está** | **[NOVO]** Sétima cópia de bbox, idêntica a B3, **não listada em nenhum documento**. É pipeline de ingestão da base Ultra brasileira, não serve tráfego, e é **CRITICO** no `loop_guard`. Fica fora do Bloco A **de propósito** — mas precisa estar escrito, senão a próxima pessoa acredita que "as seis" era a lista completa. |
| 8 | `web/src/components/HexMap.tsx:506-507` | `longitude: centro.lng ?? -47.9` / `latitude: centro.lat ?? -15.78` | `?? PERFIL.vista_padrao.lng/lat` | **[NOVO]** Fallback de câmera para Brasília, na superfície do DIA 1. |
| 9 | `src/motor_expansao/vulnerabilidade/contrato.py:142-169` (`BBOX_UF`, 27 UFs) | tabela por UF | **fica como está** | **[NOVO]** Mecanismo diferente (bbox por subdivisão, com tolerância em `:100`). Camada `vulnerabilidade` não serve o dia 1. Registrado para a lista não mentir. |

### 2.2 A sétima restrição — geocoder

| # | arquivo:linha | de | para |
|---|---|---|---|
| 10 | `web/server/app.py:3978` | `params={"q": termo, "format": "json", "limit": 1, "countrycodes": "br"}` | `"countrycodes": PERFIL.geocode.countrycodes` | **[7ª]** |
| 11 | `web/server/app.py:3979` | `headers={"User-Agent": _GEOCODE_UA}` | `headers={"User-Agent": _GEOCODE_UA, "Accept-Language": PERFIL.geocode.idioma}` | novo header |
| 12 | `src/motor_expansao/api/maps_geocoder.py:246` | `"countrycodes": "br"` | `PERFIL.geocode.countrycodes` | **[NOVO]** — segunda cópia de `countrycodes`, **não listada** no plano nem na DEC-047. |
| 13 | `src/motor_expansao/api/maps_geocoder.py:256` | `"Accept-Language": "pt-BR"` | `PERFIL.geocode.idioma` | **[NOVO]** |
| 14 | `src/motor_expansao/api/maps_geocoder.py:32` | `CEP_RE = re.compile(r"\b(\d{5})-?(\d{3})\b")` | compilado de `PERFIL.geocode.regex_cp`; `None` ⇒ `normalize_cep` devolve `""` e `split_address_cep` devolve `(texto, "")` | **[NOVO]** |

### 2.3 A validação do resultado do geocoder — hoje NÃO existe

**Conferido:** `/api/geocode` (`web/server/app.py:3953-4005`) devolve o **top-1 cru** do Nominatim.
Trecho literal de `:3989-3996`:

```python
    top = arr[0]
    try:
        out = {
            "found": True,
            "lat": _num(float(top["lat"]), 6),
            "lng": _num(float(top["lon"]), 6),
            "nome": str(top.get("display_name", ""))[:140],
        }
```

Entre `float(top["lat"])` e o `return out` **não há uma linha de bbox**. Compare com
`resolve_endereco_http`, que valida em `maps_geocoder.py:272`, e com `resolve_plus_code`, que valida
em `:350`. `/api/geocode` é a **única** das quatro rotas de coordenada que sobrevive ao gate do
Bloco C no dia 1, e é a que a barra de busca do Mapa consome
(`web/src/screens/MapScreen.tsx:647` → `web/src/lib/api.ts:381-383` → `MapScreen.tsx:649` →
`aplicarPonto` em `:626`).

**Mudança exigida (nova, não é substituição de literal):** **depois** do `except` que fecha em
`:3998` e **antes** do bloco de cache que abre em `:4000` — nunca dentro do `try`, senão um
`KeyError` do bbox vira "found: false" pelo motivo errado — inserir

```python
    if not _no_bbox_do_pais(out["lat"], out["lng"]):
        return {"found": False, "motivo": "fora_do_pais"}
```

onde `_no_bbox_do_pais` é o helper único de `PERFIL.bbox`. **Não cachear a rejeição** — o cache de
`:3966` (leitura) e `:4001-4002` (escrita) é por hash do termo e sobreviveria a uma troca de perfil.
Um "Buenos Aires" recusado sob perfil BR não pode ficar gravado em disco e voltar recusado depois de
a instância virar AR.

### 2.4 O painel de metodologia — rota LIVRE, fora do alcance do Bloco C

`/api/metodologia` (`web/server/app.py:3941-3944`) está em `ROTAS_LIVRES`
(`web/server/acesso.py:115`) e `motivo_bloqueio` (`acesso.py:275`) só consulta `REGRAS_DE_ACESSO` —
rota livre **não tem linha em tabela nenhuma**. Logo o gate do Bloco C **não a alcança por
construção**, e o conserto é aqui.

| # | arquivo:linha | de | para |
|---|---|---|---|
| 15 | `web/server/app.py:3550` | `F_CENSO = "Censo 2022 (IBGE)"` | `F_CENSO = PERFIL.fontes.censo.nome` |
| 16 | `web/server/app.py:3571-3576` | o `detalhe` de `F_CENSO` (strings em `:3572-3575`) | `PERFIL.fontes.censo.detalhe` |
| 17 | `web/server/app.py:3553` | `F_CRES = "CAGED, RAIS, Receita Federal e satélite"` | `F_CRES = PERFIL.fontes.crescimento.nome` |
| 18 | `web/server/app.py:3598-3604` | o `detalhe` de `F_CRES` (strings em `:3599-3603`) | `PERFIL.fontes.crescimento.detalhe` |
| 19 | `web/server/app.py:3626-3628` | `"linear em que R$ 300 vale 0 e R$ 4.000 vale 100; e a população do setor (peso 0,40), numa escala logarítmica em que 1.000 habitantes valem 0 e 100.000 valem 100."` | f-string derivada de `PERFIL.reguas.renda_abs_min/max`, `pop_abs_min/max` e `PERFIL.moeda.simbolo` |

`F_CONC = "Mapeamento de concorrentes"` (`:3551`) e `F_ULTRA = "Base de unidades Ultra"` (`:3552`)
**ficam como estão**: são neutras de país. Idem os `detalhe` delas.

> **Nota de honestidade que o plano já autoriza (§5.0, A2):** se o prazo apertar, a alternativa mínima
> é um cabeçalho no painel da instância AR declarando que fontes e régua descritas são as do **Brasil**.
> Feio, mas não mente. **Não** é a entrega desta spec — é o fallback declarado.

### 2.5 As réguas absolutas

| # | arquivo:linha | de | para |
|---|---|---|---|
| 20 | `web/server/app.py:161` | `SCORE_CORTE_QUENTE = 30.0` | `SCORE_CORTE_QUENTE = PERFIL.reguas.score_corte_quente` — **o NOME de módulo permanece** (§5.5 explica por que isso não é preguiça) |
| 21 | `web/server/app.py:153` | `OFERTA_DESTAQUE_MIN = 2000.0` | `= PERFIL.reguas.oferta_destaque_min` |
| 22 | `web/server/app.py:154` | `POP_MIN_ACIONAVEL = 5000` | `= PERFIL.reguas.pop_min_acionavel` |
| 23 | `web/server/app.py:152` | `CAPACIDADE_CONCORRENTE_PADRAO = 2500.0` | `= PERFIL.reguas.capacidade_concorrente` |
| 24 | `src/motor_expansao/dashboard/constants.py:379` | `CAPACIDADE_UNIDADE_ALUNOS = 2500` | `= PERFIL.reguas.capacidade_unidade_alunos` — **arquivo CRITICO** (§8) |
| 25 | `src/motor_expansao/dashboard/constants.py:144` | `POP_MIN_ACIONAVEL = 5_000` | `= PERFIL.reguas.pop_min_acionavel` — **segunda cópia**, CRITICO |
| 26 | `src/motor_expansao/dashboard/relatorio_municipal.py:61` | `OFERTA_DESTAQUE_MIN = 2000.0` | `= PERFIL.reguas.oferta_destaque_min` — **segunda cópia**, CRITICO |
| 27 | `src/motor_expansao/pipelines/calibrar_renda_setor_2022.py:89-92` | `RENDA_ABS_MIN/MAX`, `POP_ABS_MIN/MAX` | **permanecem como estão**, e viram o `ANCORAS_BR` default — ver §4 |
| 28 | `web/src/lib/faixas.ts:84` | `export const CAPACIDADE_UNIDADE_ALUNOS = 2500` | `perfilDoCliente().reguas.capacidade_unidade_alunos` |
| 29 | `web/src/lib/mapa-ponto.ts:49` | `export const CAPACIDADE_UNIDADE_ALUNOS = 2500` | idem — **terceira cópia** |
| 30 | `web/src/lib/colors.ts:65` | `export const POP_MIN_ACIONAVEL = 5000` | `perfilDoCliente().reguas.pop_min_acionavel` |

### 2.6 Moeda, locale e a morte do `_DEFAULT_DATA`

| # | arquivo:linha | de | para |
|---|---|---|---|
| 31 | `web/src/lib/format.ts:6` | `new Intl.NumberFormat('pt-BR', …)` | `new Intl.NumberFormat(perfilDoCliente().locale, …)` |
| 32 | `web/src/lib/format.ts:38,39,41` | `` `R$ ${…}` `` (3×, em `brl`) | `` `${moeda()} ${…}` `` |
| 33 | `web/src/lib/format.ts:52,53,54` | `` `R$ ${…}` `` (3×, em `brlCurto`) | idem |
| 33b | `web/src/lib/format.ts:105` (`valorComUnidade`) | `if (unidade === 'R$') return \`R$ ${num(v)}\`` | **só a METADE de saída** vira `moeda()`. A metade de **comparação** (`unidade === 'R$'`) lê um rótulo que os próprios chamadores do front cravam — `web/src/lib/comparacao-pontos.ts:60` e `web/src/lib/comparacao.ts:98`, ambos `unidade: 'R$'`. **[NOVO]** Esses dois são superfície de comparação (`imobiliaria`), fora do dia 1 da AR — mas o lint da §2.7 os pega. Converta os três no commit A9 ou a allowlist do lint deixa de ser vazia. |
| 34 | `src/motor_expansao/api/coord.py:75` | `raise CoordenadaInvalidaError("Coordenada fora do Brasil")` | `f"Coordenada fora d{'o' if …} {PERFIL.nome}"` → **use a forma neutra**: `f"Coordenada fora de {PERFIL.nome}"`. Ver §5.6: **isso quebra dois testes de asserção de texto.** |
| 35 | `web/src/lib/entrada-ponto.ts:116` | `'Essa coordenada está fora do Brasil. …'` | `` `Essa coordenada está fora de ${perfilDoCliente().nome}. …` `` — §5.7 |
| 36 | `web/server/app.py:99-101` | `_DEFAULT_DATA = Path(r"C:\Users\Felipe Silva\Downloads\…\data")` | **DELETADO** |
| 37 | `web/server/app.py:102` | `DATA_DIR = Path(os.environ.get("MOTOR_DATA_DIR", str(_DEFAULT_DATA)))` | ver §3.2 — resolução fail-closed em produção, default de repo em dev/teste |

> **Item 34, cuidado com concordância.** Não escreva `f"fora do {PERFIL.nome}"`: sai "fora do
> Argentina". A forma `f"Coordenada fora de {PERFIL.nome}"` funciona em pt-BR para Brasil, Argentina,
> Colômbia, México, Peru e Paraguai (todos aceitam "de" sem artigo em registro formal). É deliberado
> e está escrito aqui para não ser "consertado" depois.

### 2.7 Guarda que impede a volta

**Escopo: `web/src/lib/**/*.ts`, allowlist vazia.** Uma guarda que falha quando `R$` reaparece fora
de comentário nesses arquivos, com o motivo escrito nela. Sem isso, o próximo módulo de formatação
reintroduz o símbolo e nada acusa.

> ⚠️ **REESCRITA EM 2026-09-02. A versão anterior dizia "regra de ESLint sobre `web/src/**/*.{ts,tsx}`,
> `no-restricted-syntax` sobre `Literal[value=/R\$/]`, allowlist vazia". Ela não fechava, por dois
> motivos independentes — e ambos foram MEDIDOS.**

**Por que o escopo é `lib/` e não `web/src/**`.** Medido hoje em `web/src`, fora de `*.test.*` e fora
de comentário: **63 ocorrências de `R$` em 15 arquivos**. Delas, **32 literais de string em 11
arquivos** (33 ocorrências — `ViabilityScreen.tsx:969` traz duas no mesmo literal) casariam com
`Literal[value=/R\$/]`; **21 vivem em template literal** e **9 em texto JSX**, que o seletor
`Literal[]` **não enxerga**. Uma regra sobre `web/src/**` com allowlist vazia não é a porta fechada:
são **32 erros no dia 1** num PR de front que já não auto-mergeia (`^web/` é GOVERNANCA, §8) — e
ainda deixaria passar as 21+9 que o A9 mais precisa travar.

Em `web/src/lib/**/*.ts` são **11 ocorrências em 4 arquivos**: `format.ts` (8 — `:38`, `:39`, `:41`,
`:52`, `:53`, `:54` e as duas de `:105`), `comparacao.ts:98`, `comparacao-pontos.ts:60` e
`recomendacao.ts:206`. **As 11 são movidas pelo A9**, então a allowlist nasce vazia **e** verde. Note
que só **3** delas são `Literal` de string (`comparacao.ts:98`, `comparacao-pontos.ts:60`,
`format.ts:105`): as seis do `brl`/`brlCurto` (`format.ts:38-54`) são **template literal**. Um
seletor só de `Literal[]` deixaria passar exatamente o sítio que este bloco existe para matar.

**Por que teste de contrato e não ESLint — NÃO HÁ ESLint NESTE PROJETO.** Conferido:
`web/package.json` não traz `eslint` em `devDependencies` e define `"lint": "tsc --noEmit"`; não há
`eslint.config.*` nem `.eslintrc*` em lugar nenhum do repositório. Escrever a guarda como regra de
ESLint significa **introduzir ESLint + `typescript-eslint` + passo de CI** — dependência e trabalho
que não estão nos 7-11 dias do bloco, num commit cujo papel é fechar a porta, não abrir uma frente.
**A guarda é um teste de contrato**, `tests/contracts/test_sem_moeda_hardcoded_no_front.py`, no mesmo
padrão de `test_faixas_mapa_espelho.py`: varre `web/src/lib/**/*.ts` atrás de `R$` fora de comentário
e falha nomeando arquivo e linha. Mesmo efeito, zero dependência nova, e roda no `pytest` que o
critério de aceite já executa. (Análogo do lado Python, no mesmo teste: `web/server/app.py` e
`src/motor_expansao/dashboard/` atrás de `R$` em string de usuário — ver §5.9.)

**Os `R$` de `ViabilityScreen.tsx` NÃO entram no escopo** — `:580`, `:582`, `:595`, `:597`, `:874`,
`:877`, `:904`, `:907`, `:966` e as duas de `:969` (os `prefixo="R$"` das caixas e os `title` que
explicam a unidade). Convertê-los **contrariaria a decisão 0.6**: a viabilidade argentina sobe **em
reais, com tributo brasileiro**, como provisório declarado. Um símbolo parametrizado ali escreveria
"$" numa tela cujos números continuam sendo reais — pior do que o provisório assumido, porque some
com o único sinal de que são reais. Saem junto com o BLK-INTL-11, não antes.

---

## 3. Onde o perfil é carregado e como é injetado

### 3.1 O módulo

**Arquivo novo: `src/motor_expansao/perfil.py`** — LIMPO no `loop_guard` (§8), o que é uma vantagem:
o módulo em si auto-mergeia; o que exige aprovação são os sítios que o consomem.

```python
# src/motor_expansao/perfil.py
from __future__ import annotations
import json, os, re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

class PerfilInvalidoError(RuntimeError):
    """Perfil ausente, ilegível ou fora do contrato -> o processo NÃO sobe."""

@dataclass(frozen=True, slots=True)
class Bbox:
    lat_min: float; lat_max: float; lng_min: float; lng_max: float
    def contem(self, lat: float, lng: float) -> bool:
        return self.lat_min <= lat <= self.lat_max and self.lng_min <= lng <= self.lng_max

@dataclass(frozen=True, slots=True)
class Moeda:      codigo: str; simbolo: str
@dataclass(frozen=True, slots=True)
class Vista:      lat: float; lng: float; zoom: float
@dataclass(frozen=True, slots=True)
class Geocode:    countrycodes: str; idioma: str; regex_cp: str | None
@dataclass(frozen=True, slots=True)
class Fonte:      nome: str; detalhe: str
@dataclass(frozen=True, slots=True)
class Fontes:     censo: Fonte; crescimento: Fonte
@dataclass(frozen=True, slots=True)
class Reguas:
    renda_abs_min: float; renda_abs_max: float
    pop_abs_min: float;   pop_abs_max: float
    score_corte_quente: float
    pop_min_acionavel: int
    oferta_destaque_min: float
    capacidade_concorrente: float
    capacidade_unidade_alunos: int

@dataclass(frozen=True, slots=True)
class Perfil:
    schema_versao: int
    pais: str; nome: str; locale: str
    moeda: Moeda; bbox: Bbox; vista_padrao: Vista
    geocode: Geocode; fontes: Fontes; reguas: Reguas
    superficies: tuple[str, ...]

#: Perfil BR embarcado. É o default de DEV e de TESTE (ver §3.2) — nunca de produção.
#: CAMINHO DECIDIDO em 2026-08-31: é `data/perfis/BR/perfil.json`, NÃO `data/perfil.json`.
#: É o arquivo que JÁ está versionado, é o que o `data/perfis/LEIA-ME.md` documenta, e é o que
#: separa BR de AR na mesma árvore (`data/perfis/AR/perfil.json`). `data/perfil.json` NÃO existe.
PERFIL_BR_EMBARCADO = Path(__file__).resolve().parents[2] / "data" / "perfis" / "BR" / "perfil.json"

def carregar_perfil(caminho: Path) -> Perfil: ...      # parse + validar, ou PerfilInvalidoError

@lru_cache(maxsize=1)
def resolver_perfil() -> Perfil:
    """Resolvido UMA vez por processo, ao lado de onde MOTOR_DATA_DIR já é resolvido."""
    raiz = os.environ.get("MOTOR_DATA_DIR")
    if raiz:                                            # PRODUÇÃO -> fail-closed
        return carregar_perfil(Path(raiz) / "perfil.json")
    return carregar_perfil(PERFIL_BR_EMBARCADO)         # dev/teste -> BR do repo
```

### 3.2 Fail-closed — e a ressalva que não é negociável

**A regra:** perfil ausente, JSON inválido, `schema_versao != 1`, campo obrigatório faltando, tipo
errado, bbox degenerada ou `superficies` fora de `ABAS_VALIDAS` ⇒ `PerfilInvalidoError` **no import**,
o container não sobe, e a mensagem nomeia o campo.

**A ressalva, e por que ela existe.** Conferido nesta data:

```
$ grep -rn MOTOR_DATA_DIR tests/ conftest.py .github/
(nenhuma saída)
```

Não existe **uma linha** de `MOTOR_DATA_DIR` na suíte nem no CI. E **15 módulos de teste** fazem
`import app` **no topo do arquivo** e só depois reapontam caminhos por monkeypatch — é o padrão que a
própria docstring de `limpar_caches` (`web/server/app.py:3106-3117`) descreve:

`tests/unit/test_check_artifacts.py:44`, `test_contagem_no_hexagono.py:43`, `test_exec_coordenadas.py:32`,
`test_acesso_log.py:26`, `tests/contracts/test_metodologia_espelha_o_funil.py:30`,
`tests/unit/test_piloto_web_endpoints.py:38`, `test_piloto_web_api.py:23`,
`test_piloto_web_acesso.py:24`, `test_piloto_web_seguranca.py:24`, `test_piloto_web_rede.py:32`,
`test_relatorio_pontual_origem_centroide_rota.py:49`, `test_piloto_web_ponto.py:23`,
`test_piloto_web_simulador_xlsx.py:37`, `test_renda_domiciliar_hex.py:37`,
`test_piloto_web_oportunidades.py:34`.

(Um 16º, `tests/unit/test_paridade_classe_crescimento_web.py:51`, importa **dentro de função** — ele
falharia na *execução*, não na coleta. Contado à parte de propósito: a falha dele tem outra cara.)

Um loader fail-closed **incondicional** derruba os 15 na **coleta** do pytest, com um traceback que
não menciona nada do Bloco A. Por isso:

> **`MOTOR_DATA_DIR` setado ⇒ fail-closed absoluto (é produção).**
> **`MOTOR_DATA_DIR` ausente ⇒ carrega o `data/perfis/BR/perfil.json` embarcado no repositório.**

O arquivo `data/perfis/BR/perfil.json` é **versionado** (LIMPO no `loop_guard`) e é a **fonte da
verdade dos contratos brasileiros**: é ele que os testes de régua passam a ler no lugar do regex sobre o
texto-fonte (§5.1). A alternativa — fixture de sessão em `conftest.py` apontando `MOTOR_DATA_DIR` —
resolve igual, custa o mesmo, **e transforma um arquivo CRITICO** (`conftest.py`, §8) num arquivo do
diff deste bloco. Recusada por isso.

### 3.3 O ponto único de resolução no `app.py`

Substitui `web/server/app.py:99-102`:

```python
# --- antes (:99-102) ---
_DEFAULT_DATA = Path(r"C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\data")
DATA_DIR = Path(os.environ.get("MOTOR_DATA_DIR", str(_DEFAULT_DATA)))

# --- depois ---
from motor_expansao.perfil import resolver_perfil
PERFIL = resolver_perfil()
DATA_DIR = PERFIL.raiz            # o loader guarda a raiz de onde leu o perfil
logger.info("perfil: pais=%s nome=%s bbox=%s superficies=%s raiz=%s",
            PERFIL.pais, PERFIL.nome, PERFIL.bbox, PERFIL.superficies, DATA_DIR)
```

`OUTPUTS_DIR` (`:103`), `STAGING_DIR` (`:104`), `IBGE_DIR` (`:105`), `ULTRA_DIR` (`:106`),
`CENSO_GEO_DIR` (`:107`) e `ENRICHED_DIR` (`:108`) continuam derivando de `DATA_DIR` **sem uma linha
de mudança** — é o que o §2 do plano chama de "a malha já mora no volume" (R8).

`Perfil` ganha um campo `raiz: Path` preenchido pelo loader (a pasta de onde o `perfil.json` veio).
No caminho de dev/teste, `raiz` = o `data/` do repositório.

### 3.4 Os 4 sítios que constroem `Settings` — **confirmados**

O plano diz `4508`, `5210`, `7725`, `7994`. **Conferido hoje: `4522`, `5224`, `7739`, `8008`** (a
mesma defasagem de 14 do §0). Os quatro têm forma idêntica:

```python
cfg = Settings(censo_geo_dir=CENSO_GEO_DIR, ibge_dir=IBGE_DIR,
               ultra_dir=ULTRA_DIR, staging_dir=STAGING_DIR)
```

| linha | dentro de |
|---|---|
| `4522` | `/api/ponto` (`@app.get` em `:4481`) |
| `5224` | `_catchment_setores`, chamado pela viabilidade |
| `7739` | `/api/relatorio/municipal` (`@app.post` em `:7698`) |
| `8008` | `/api/relatorio/pontual` (`@app.post` em `:7895`) |

**Como o perfil chega lá.** `src/motor_expansao/api/settings.py` ganha **um** campo, com default:

```python
    # Perfil do país da instância. Default None = "quem construiu não passou" -> o
    # consumidor cai em resolver_perfil(). NÃO é Optional por indecisão: é para os
    # 4 sítios acima poderem ser convertidos UM POR COMMIT, cada um verde sozinho.
    perfil: Perfil | None = None
```

e os quatro sítios passam a incluir `perfil=PERFIL`. **Ordem obrigatória:** o campo com default entra
**antes** dos quatro `Settings(...)` serem alterados (commit A1 x commit A6 na §6) — senão o
`pydantic-settings` levanta em todos os quatro ao mesmo tempo, e o commit não é verde sozinho.

> `Settings` é `BaseSettings` com `extra="ignore"` (`settings.py:32`) e prefixo de env `API_`
> (`:29`). Um campo de tipo dataclass **não é** preenchível por env, o que é desejável aqui: o perfil
> não pode ser sobrescrito por variável de ambiente — ele é o arquivo, e só.

### 3.5 Como o perfil chega ao front

**Não** entra rota nova (DEC-047: "não entra requisição"). O front já pede `GET /api/me` na abertura
(`web/server/app.py:3221`). O payload de `/api/me` ganha um campo `perfil` com **exatamente** o que o
front lê: `nome`, `locale`, `moeda`, `bbox`, `vista_padrao`, `reguas.pop_min_acionavel`,
`reguas.capacidade_unidade_alunos`. Nada mais.

`web/src/lib/perfil.ts` (novo) expõe `perfilDoCliente(): PerfilCliente` a partir de um módulo-estado
preenchido uma vez no bootstrap, **com um default BR compilado** — porque `coord.ts`,
`entrada-ponto.ts`, `format.ts`, `faixas.ts`, `colors.ts` e `mapa-ponto.ts` são módulos **puros**
testados pelo Vitest **sem servidor**, e sem esse default os testes de §5.7 e §5.8 quebram por
`undefined`, não por régua. O default BR do front vive num único `perfil-br.ts` gerado do mesmo
`data/perfis/BR/perfil.json` — e um teste de contrato trava que os dois batem (§5.9).

**QUANDO é seguro ler o perfil no cliente — acrescentado em 2026-09-02.** O `/api/me` chega num
`useEffect` de `web/src/App.tsx` (`useState<Set<Aba>|null>(null)` em `:65`, `useEffect(…, [])` em
`:66-79`): **o payload só existe DEPOIS da primeira pintura.** Junte isso ao default BR compilado do
parágrafo acima e aparece o modo de falha que nenhum teste pega: uma substituição
**literal-por-literal** dos sítios de front deixa a leitura acontecer cedo demais, o default
responde, e o resultado é o **bbox brasileiro congelado** — a instância AR recusando Buenos Aires na
barra de busca do mapa, que é superfície do DIA 1 (decisão 0.6). Os quatro testes da §5.8 ficam
**verdes por construção**, porque é o default que eles exercitam. Por isso cada sítio do A9 precisa
ser classificado **antes** de ser tocado, em duas classes:

| classe | como é hoje | o que o A9 faz | por quê |
|---|---|---|---|
| **(1) leitura sob INPUT do usuário** | `const BR = { latMin: -34.0, … }` de **módulo**: `web/src/lib/coord.ts:8` (lido por `noBrasil`, `:15-20`) e `web/src/lib/entrada-ponto.ts:44` | **mover a leitura para o CORPO da função** — `noBrasil()` passa a chamar `perfilDoCliente().bbox` a cada chamada, em vez de fechar sobre uma const de módulo avaliada no import | Essas funções só rodam quando o operador **digita**, sempre depois do `/api/me`. O custo é um acesso a objeto; o ganho é validar contra o país da instância em vez de contra o Brasil de sempre. Aqui um getter **resolve** |
| **(2) leitura na PRIMEIRA RENDERIZAÇÃO** | o inicializador preguiçoso `useState<ViewState>(() => …)` de `web/src/components/HexMap.tsx:494-512`, com os literais `-47.9` / `-15.78` em **`:506-507`**; e `VISTA_BRASIL` (`web/src/lib/mapa-ponto.ts:32`) lido no corpo de `web/src/components/MapaPonto.tsx:63` | **o perfil tem de estar resolvido ANTES da primeira pintura**: o bootstrap preenche `perfil.ts` antes de montar a árvore, ou a árvore não monta enquanto ele não chegar | Inicializador de `useState` roda **antes de qualquer efeito**. Aqui **getter NÃO resolve**: por mais tardia que a leitura seja escrita, ela acontece cedo demais. Uma câmera que nasce em Brasília e voa para Buenos Aires depois do `/api/me` não é chateação de teste — é a tela nascendo no país errado |

> **Correção de referência, para o A9 não perder um sítio.** `VISTA_BRASIL` **não** está em
> `HexMap.tsx:506-507`, como circulou na revisão. `:506-507` são os literais `-47.9`/`-15.78` — o
> fallback de Brasília para o centro do município —, e `VISTA_BRASIL` vive em `mapa-ponto.ts:32`,
> consumido em `MapaPonto.tsx:63`. **São dois sítios distintos, ambos da classe (2)**, e o
> `-47.9`/`-15.78` do `HexMap` não aparece em nenhuma lista do plano nem da DEC-047: some do A9 se
> alguém o classificar como "só bbox".

---

## 4. A parametrização das âncoras

### 4.1 O estado de hoje, conferido

`src/motor_expansao/pipelines/calibrar_renda_setor_2022.py`:

```python
:89  RENDA_ABS_MIN = 300.0
:90  RENDA_ABS_MAX = 4_000.0
:91  POP_ABS_MIN = 1_000.0
:92  POP_ABS_MAX = 100_000.0

:118 def nota_renda_absoluta(renda: np.ndarray) -> np.ndarray:
:121     return np.clip(100.0 * (r - RENDA_ABS_MIN) / (RENDA_ABS_MAX - RENDA_ABS_MIN), 0.0, 100.0)

:124 def nota_pop_absoluta(pop: np.ndarray) -> np.ndarray:
:127     escala = np.log(POP_ABS_MAX) - np.log(POP_ABS_MIN)
:128     return np.clip(100.0 * (np.log(p) - np.log(POP_ABS_MIN)) / escala, 0.0, 100.0)

:148 def calcular_score_calibrado(renda_abs, pop_abs) -> tuple[...]:
:158     nr   = nota_renda_absoluta(renda_abs)
:159     npop = nota_pop_absoluta(pop_abs)
```

**As três lêem as constantes de módulo direto. Nenhuma recebe âncora.** Confirmado.

### 4.2 A assinatura nova

```python
@dataclass(frozen=True, slots=True)
class Ancoras:
    renda_min: float
    renda_max: float
    pop_min: float
    pop_max: float

#: Âncoras do BRASIL — os MESMOS quatro números de :89-92, byte a byte. Continuam sendo
#: constantes de módulo porque `tests/contracts/test_regua_absoluta_censitaria.py:21-25`
#: as importa por nome, e porque este arquivo é CRITICO: um diff que MOVE número é caro
#: de revisar; um diff que só acrescenta um parâmetro com default é barato.
ANCORAS_BR = Ancoras(RENDA_ABS_MIN, RENDA_ABS_MAX, POP_ABS_MIN, POP_ABS_MAX)


def nota_renda_absoluta(renda, *, ancoras: Ancoras = ANCORAS_BR): ...
def nota_pop_absoluta(pop,   *, ancoras: Ancoras = ANCORAS_BR): ...
def calcular_score_calibrado(renda_abs, pop_abs, *, ancoras: Ancoras = ANCORAS_BR): ...
```

`calcular_score_calibrado` repassa: `nota_renda_absoluta(renda_abs, ancoras=ancoras)` e
`nota_pop_absoluta(pop_abs, ancoras=ancoras)`.

**Três propriedades desta forma, e cada uma vale um argumento numa revisão CRITICO:**

1. **Keyword-only (`*`).** Impede que alguém acrescente um terceiro posicional e o passe onde o
   `pop_abs` deveria ir. Num arquivo que produz o score primário operacional do Brasil, isso não é
   estilo.
2. **Default nas constantes de hoje ⇒ os contratos brasileiros continuam verdes byte a byte.**
   Os **quatro** chamadores de produção — `agregar_censo_hex_da_malha.py:290`,
   `fase_a_nacional_completo.py:147`, `fase_a_piloto_expandido.py:521`,
   `recalcular_score_absoluto.py:74`, mais `calibrar_renda_setor_2022.py:334` — **não mudam uma
   linha**. Os cinco são **CRITICO** no `loop_guard` (§8): não tocá-los tira cinco arquivos do diff.
3. **`ANCORAS_BR` é montada a partir das constantes, não as substitui.** `RENDA_ABS_MIN` etc.
   continuam existindo com o mesmo valor no mesmo lugar, porque
   `tests/contracts/test_regua_absoluta_censitaria.py:22-25` as importa por nome e
   `tests/contracts/test_regua_absoluta_censitaria.py:78-84` as usa como fronteira.

### 4.3 Quem constrói as âncoras do perfil

Ninguém, **neste bloco**. `Ancoras(**PERFIL.reguas.<as quatro>)` é construída pelo **exportador**
(`exportar_piloto_rep.py`) no **Bloco B**, que recomputa o score AR — porque a linha
`score_setor_2022_calibrado ← score_priorizacao` do `HANDOFF.md` §4 **não pode ser honrada**: o score
AR é percentil e o corte de 30 é absoluto.

**O Bloco A entrega só a capacidade.** É por isso que A→B é serial, e é a única razão.

### 4.4 A decisão do Felipe que este bloco NÃO toma

As âncoras argentinas de **renda (USD)** e de **população por hexágono**.

**Corrigido em 2026-09-02 — esta seção afirmava que a âncora brasileira de população vem de SETOR
CENSITÁRIO. É falso, e a consequência inverte a recomendação.** A âncora brasileira **também é de
hexágono H3 res 7**: `calibrar_renda_setor_2022.py:82` diz, com todas as letras,
`# Ancoras medidas no universo POVOADO (pop >= 1.000, 21.107 hexes)`, e `:265` imprime
`f"  Setor: {len(df_ufs):,} hexes"`. A coluna se chama `pop_total_setor_2022` porque isso é a
**procedência do atributo** — Censo 2022 por setor, atribuído ao hexágono —, não a unidade da linha.

Logo, manter `POP_ABS_MIN/MAX = 1.000/100.000` na Argentina **não é trocar a unidade em silêncio: é o
casamento correto de unidade**, mesma grade e mesma régua. Quem quiser derivar a âncora AR de *radio
censal* é que estaria criando descasamento — 66.502 radios contra uma régua medida em 21.107
hexágonos. O que continua sendo decisão do Felipe é o **valor**, não a unidade (pendência **P2** em
`data/perfis/AR/perfil.json`, cuja recomendação já foi invertida no mesmo commit).

**Corrigido antes, em 2026-08-31 — a redação anterior desta seção descrevia um perfil que não é o entregue.**
Ela dizia que "o `perfil_ar.json` nasce com **as âncoras brasileiras copiadas** e um campo
`reguas._provisorio: true`", e que "o código do Bloco A fica pronto com âncora BR na AR". Nada disso
existe: **não há arquivo `perfil_ar.json`** (é `data/perfis/AR/perfil.json`), **não há campo
`reguas._provisorio`**, e as âncoras de renda **não** são brasileiras — copiar a âncora de RENDA de um
país para o outro seria erro real, porque as duas distribuições nada têm a ver (R$ contra USD, p95/p05
de 6,4 contra 2,2). Isso vale para a renda e **só** para ela: a de população é a mesma grade, ver a
correção acima. O estado real, e o que vale:

> O `data/perfis/AR/perfil.json` **já nasce com âncoras argentinas medidas**: `renda_abs_min` = **350,0**
> e `renda_abs_max` = **1.000,0 USD**, `pop_abs_min` = **1.000** e `pop_abs_max` = **100.000**. A
> provisoriedade é marcada em `_nota_renda`/`_nota_pop` e nas pendências **P1** (renda) e **P2**
> (população) do próprio arquivo — não num campo `_provisorio`.

**De onde saem os 350/1.000.** Não é conversão de moeda — é o **critério** de
`calibrar_renda_setor_2022.py:83-92` (piso no p05 arredondado, teto acima do p99 e abaixo do máximo,
saturando < 0,4%) aplicado à distribuição argentina medida no pacote em 2026-08-31 (universo povoado,
pop ≥ 1.000, 5.148 hexágonos): p05 = 342,4 · p50 = 478,4 · p95 = 740,5 · p99 = 926,2 · max = 1.141,1.
Piso 350, teto 1.000 (satura 0,29%; o Brasil satura 0,38% com R$ 4.000). Os 1.000/100.000 de população
são os **mesmos números** do Brasil, e agora se sabe **por quê**: é a **mesma unidade**, hexágono H3
res 7 dos dois lados. As distribuições coincidem (BR p05 1.103 / p50 3.561 / p95 28.845 · AR 1.127 /
3.699 / 28.500) porque medem a mesma coisa sobre a mesma grade — não por coincidência a ser
desconfiada. O `_nota_pop` do arquivo carrega essa procedência.

**O que isto significa para o Bloco A: nada muda no código.** O bloco **não escolhe âncora nenhuma** —
ele entrega a *capacidade* de recebê-las (`Ancoras(...)` com default `ANCORAS_BR`, §4.2), e quem as
constrói é o exportador, no Bloco B (§4.3). Portanto **P1/P2 não travam o início**, e não travam por
uma razão melhor do que a anterior: o default no arquivo é argentino e medido, não brasileiro e
copiado. A decisão do Felipe **refina** um número; ela não é pré-requisito de linha de código nenhuma.

---

## 5. OS TESTES QUE VÃO QUEBRAR, e como

Varredura feita em `tests/`, `web/src/**/*.test.ts` e `fora_primeira_fase/`. **Nove itens.**

### 5.1 `tests/contracts/test_regua_absoluta_censitaria.py:103-121` — `test_corte_do_funil_bate_com_a_escala`

**Como quebra.** O teste **não importa** a constante — lê o **texto-fonte**:

```python
:114   fonte = _P("web/server/app.py").read_text(encoding="utf-8")
:115   m = re.search(r"^SCORE_CORTE_QUENTE\s*=\s*([0-9.]+)", fonte, re.M)
:116   assert m, "SCORE_CORTE_QUENTE nao encontrado em web/server/app.py"
:117   SCORE_CORTE_QUENTE = float(m.group(1))
:119   assert SCORE_CORTE_QUENTE == 30.0
```

No instante em que a linha `app.py:161` vira `SCORE_CORTE_QUENTE = PERFIL.reguas.score_corte_quente`,
o `([0-9.]+)` não casa, `m` é `None`, e o teste morre em `assert m` com a mensagem
**"SCORE_CORTE_QUENTE nao encontrado"** — que aponta para o lugar errado e faz perder uma hora.

**Correção, no MESMO commit que muda a `:161`:** trocar `:109-117` por leitura do perfil BR versionado.

```python
    from motor_expansao.perfil import carregar_perfil, PERFIL_BR_EMBARCADO  # noqa: PLC0415
    # Le do PERFIL versionado, nao do texto-fonte de app.py: `web/server/app.py` puxa
    # modulos que so' existem no sys.path do container do piloto (ex.: `acesso`), e desde
    # o Bloco A o numero MORA no perfil, nao no literal. O contrato continua sendo o mesmo:
    # o corte tem de bater com a escala das ancoras.
    SCORE_CORTE_QUENTE = carregar_perfil(PERFIL_BR_EMBARCADO).reguas.score_corte_quente
    assert SCORE_CORTE_QUENTE == 30.0
    assert _score(1_500.0, 15_000.0) >= SCORE_CORTE_QUENTE
```

**O contrato fica MAIS forte, não mais fraco:** hoje ele prova que o texto de `app.py` diz 30; depois
ele prova que **o número que o funil de fato aplica** diz 30 — a `:161` passa a ser derivada.

### 5.2 `tests/unit/test_coord_search.py:52-60` — `test_parse_limites_brasil`

**Como quebra.** Linha `:60`:

```python
    assert parse_coordinate_input("-34.0,-53.0") is None   # "fora do sul"
```

Hoje passa porque `dashboard/data.py:624` é `-33.75`. Com `perfil.bbox` = **B1** (`lat_min = -34.0`,
§1.3), `-34.0 <= -34.0` é **verdadeiro** e a função devolve `(-34.0, -53.0)`. **Falha.**

`:58` (`"6.0,-60.0" is None`) **continua verde** (6,0 > 5,5 de B1). `:54` e `:56` continuam verdes.

**Correção.** Trocar o par de fronteira por um valor claramente fora da caixa declarada, e **ancorar
no perfil em vez de no número**:

```python
def test_parse_limites_brasil():
    from motor_expansao.perfil import carregar_perfil, PERFIL_BR_EMBARCADO
    bb = carregar_perfil(PERFIL_BR_EMBARCADO).bbox
    assert parse_coordinate_input(f"{bb.lat_max - 0.5},-60.0") is not None
    assert parse_coordinate_input(f"{bb.lat_min + 0.5},-53.0") is not None
    assert parse_coordinate_input(f"{bb.lat_max + 0.5},-60.0") is None
    assert parse_coordinate_input(f"{bb.lat_min - 0.5},-53.0") is None
```

**Escreva no commit, no corpo da mensagem:** a caixa de `dashboard/data.py` **alargou** de
B2 (−33,75 / 5,27 / −73,99 / −28,65) para B1 (−34,0 / 5,5 / −74,0 / −28,0). É a decisão da §1.3,
não um efeito colateral.

`:44` (`test_parse_entrada_invalida_retorna_none`, com `"20.0,-50.0"`, `"-23.55,-5.0"`,
`"-40.0,-46.63"`, `"-23.55,-80.0"`) e `:316`
(`test_extract_any_coord_fora_do_brasil_rejeitado_pelo_bbox`, Torre Eiffel) **continuam verdes** sob
B1 — todos bem fora da caixa. Verificado valor a valor.

### 5.3 `dashboard/competitors.py` — estreitamento, **sem teste que pegue**

`_coord_in_brazil` (`competitors.py:469-470`) **estreita** de B3 (lat até 6,0; lng até −75,0) para B1
(5,5 / −74,0). **Nenhum teste em `tests/` exercita `_coord_in_brazil` diretamente** (conferido:
todas as ocorrências de `flag_coord_valida` em testes são colunas de fixture, não a função).

**Isso é pior do que um teste quebrando** — é uma mudança silenciosa numa camada visual. **Comando de
verificação obrigatório no commit** (§7, item 5): contar pins de concorrente descartados antes e
depois. Se o delta não for **zero**, a decisão da §1.3 precisa ser reaberta antes do merge.

### 5.4 `tests/unit/test_api_coord.py:43` e `:112`

`test_validar_brasil_dentro_e_fora` (`:43-46`) usa Paris (48,85 / 2,35) — verde sob B1.
`test_par_espurio_e_barrado_pelo_bounding_box` (`:112-123`) usa o par `1.0,2.0` — verde sob B1.

**Ambos ficam verdes**, mas **só enquanto `validar_brasil` mantiver o nome**. Se você renomear a
função nesta onda, os dois quebram no `import` (`:11`, `:119`). **Por isso a §2.1 item 1 diz para não
renomear agora.**

### 5.5 `tests/contracts/test_metodologia_espelha_o_funil.py:305-315`

```python
:308    assert f"{pilot.SCORE_CORTE_QUENTE:.0f}" in c1
:309    assert f"{pilot.POP_MIN_ACIONAVEL:,.0f}".replace(",", ".") in c1
:312    assert f"{pilot.OFERTA_DESTAQUE_MIN:,.0f}".replace(",", ".") in c2
```

**Fica VERDE — e é exatamente por isso que a §2.5 manda preservar os NOMES de módulo.** Se você
substituir os usos por `PERFIL.reguas.…` inline e **apagar** as constantes de `app.py:152-154` e
`:161`, os três viram `AttributeError` na coleta e você perde a rede de proteção mais útil do bloco:
esse teste prova que o painel publica o número que o funil aplica.

**Regra desta spec:** as constantes de módulo **sobrevivem, derivadas do perfil**. Preservar o nome
não é preguiça — é o que mantém 4 contratos verdes de graça (este, o `:112` abaixo, e os dois de
`test_piloto_web_endpoints.py`/`test_piloto_web_ponto.py` do §5.9).

`:112` (`alunos = ((de+ate)/2) * CAPACIDADE_UNIDADE_ALUNOS / 100`) idem: mantenha
`constants.CAPACIDADE_UNIDADE_ALUNOS` como nome.

**O que quebra de verdade neste arquivo:** o `import app as pilot` do topo (`:30`). Se o fail-closed
for incondicional (§3.2), este é um dos 15 módulos que morrem na **coleta** (§3.2).

### 5.6 `tests/unit/test_piloto_web_ponto.py:124-128` e `:161-165` — asserção do TEXTO

```python
:128    assert "fora do Brasil" in exc.value.detail
:165    assert "fora do Brasil" in r["motivo"]
```

A mensagem passa a ser `f"Coordenada fora de {PERFIL.nome}"` (§2.6, item 34) ⇒ `"fora do Brasil"`
**não está mais na string**. Ambos **falham**.

**Correção:** ancorar no perfil, não no literal.

```python
    from motor_expansao.perfil import resolver_perfil
    assert f"fora de {resolver_perfil().nome}" in exc.value.detail
```

Verifique também `src/motor_expansao/api/schemas/__init__.py:32`
(`detail: str = Field(examples=["Coordenada fora do Brasil"])`) — é **exemplo de OpenAPI**, não
comportamento. Atualize por higiene; nenhum teste o lê.

`src/motor_expansao/api/service.py:118` (`"Coordenada fora da malha municipal do IBGE (mar aberto,
fora do Brasil …)"`) é a mensagem da **malha**, não do bbox, e é travada por
`tests/unit/test_piloto_web_ponto.py:136` (`assert "malha municipal" in …`). **Fora do Bloco A**;
morre no BLK-INTL-03 junto com o 404 nomeado.

### 5.7 `web/src/lib/entrada-ponto.test.ts:89-107`

```ts
:97     expect(r.aviso).toMatch(/fora do Brasil/i)
```

Quebra pela mesma razão do §5.6 (item 35 da §2.6). `:94` e `:103` (`toBe('fora-do-brasil')`)
**ficam verdes** — o valor do enum não muda (renomeá-lo é churn puro; **não renomeie**).

**Correção:** `expect(r.aviso).toMatch(new RegExp('fora de ' + perfilDoCliente().nome, 'i'))`.

### 5.8 `web/src/lib/colors.test.ts:51-52`, `faixas.test.ts:68`, `coord.test.ts:29-35`, `mapa-ponto.test.ts:113-117`

| teste | assert | veredito |
|---|---|---|
| `colors.test.ts:52` | `expect(POP_MIN_ACIONAVEL).toBe(5000)` | **verde** se `perfil.ts` tiver default BR compilado (§3.5); **quebra por `undefined`** se não tiver |
| `faixas.test.ts:68` | `expect(CAPACIDADE_UNIDADE_ALUNOS).toBe(2500)` | idem |
| `coord.test.ts:29-35` | Nova York (40,7) e lng 10,0 → `null` | **verde** sob B1; quebra por `undefined` sem o default |
| `mapa-ponto.test.ts:113-117` | `VISTA_BRASIL.latitude < 0 && .longitude < 0` | **verde** (vale para AR também), mas **renomeie** `VISTA_BRASIL` → `VISTA_PADRAO` e o import de `:6` junto, senão fica um nome mentindo |

**O `perfil.ts` com default BR compilado é o que mantém quatro arquivos de teste verdes sem uma
linha de mudança neles.** É a razão de a §3.5 exigir esse default; não é conveniência.

### 5.9 Testes que NÃO quebram — e que você vai achar que quebram

Registrado para não gastar tempo:

| teste | por que fica verde |
|---|---|
| `tests/unit/test_piloto_web_ponto.py:248-250` e `test_piloto_web_endpoints.py:1519-1522` | lêem `pilot.SCORE_CORTE_QUENTE`, `pilot.POP_MIN_ACIONAVEL`, `pilot.OFERTA_DESTAQUE_MIN`, `pilot.CAPACIDADE_CONCORRENTE_PADRAO` **por atributo**. Verdes enquanto o nome sobreviver (§5.5). |
| `tests/contracts/test_faixas_mapa_espelho.py:94-101` | importa `CAPACIDADE_UNIDADE_ALUNOS` de `constants` (`:24`). Verde pelo mesmo motivo. `:119-120` e `:184-185` lêem o texto-fonte de `app.py`, mas atrás de `"hexágonos quentes"` e do plural de município — nada que este bloco move. |
| `tests/contracts/test_regua_absoluta_censitaria.py:36-100` e `:124-157` | só exercitam funções puras. O default `ancoras=ANCORAS_BR` (§4.2) as mantém **byte a byte**. |
| `tests/contracts/test_docs_vs_codigo.py` | ancorado em `core/constants.py` e `relatorio_municipal` PDF headers; nenhuma âncora de renda/pop. |
| `tests/contracts/test_parametros_canonicos.py` | `RENDA_MIN=4500` é do M1 estrutural (`config.py`), **não** é `RENDA_ABS_MIN`. Sem relação. |
| `tests/unit/test_loop_guard*.py` | só quebram se você **acrescentar padrão** ao `loop_guard.py` — o que este bloco **não** faz (§8). |
| `fora_primeira_fase/tests/test_scraper_contracts.py:130` | tem seu próprio `BRASIL_LAT_MIN = -33.75` local; fora do `testpaths`. Não tocar. |

**Testes NOVOS que este bloco precisa criar** (todos LIMPOS no `loop_guard`):

1. `tests/unit/test_perfil_loader.py` — cada campo obrigatório ausente levanta `PerfilInvalidoError`
   nomeando o campo; `schema_versao` divergente levanta; bbox degenerada levanta; `superficies` fora
   de `ABAS_VALIDAS` levanta; `MOTOR_DATA_DIR` setado e sem `perfil.json` levanta;
   `MOTOR_DATA_DIR` ausente carrega o BR embarcado.
2. `tests/contracts/test_perfil_br_reproduz_as_constantes.py` — o `data/perfis/BR/perfil.json` reproduz os
   **13** números de hoje: `bbox` = B1; `reguas` = `30.0 / 5000 / 2000.0 / 2500.0 / 2500 /
   300.0 / 4000.0 / 1000.0 / 100000.0`. **É este teste que garante "a suíte brasileira passa sem um
   número se mover".**
3. `tests/contracts/test_fio_de_alarme_pais.py` — DEC-047: varre `src/`, `web/`, `scripts/` atrás de
   `pais ==`, `pais==`, `country ==`; lista de exceções **vazia**. Medido hoje: **zero ocorrências**.
4. `tests/contracts/test_geocode_valida_o_bbox.py` — Nominatim mockado devolvendo Buenos Aires com
   perfil BR ⇒ `{"found": False, "motivo": "fora_do_pais"}`; com perfil AR ⇒ `found: True`.
   **É a prova do A1.**
5. `tests/contracts/test_perfil_front_espelha_o_python.py` — `web/src/lib/perfil-br.ts` bate com
   `data/perfis/BR/perfil.json`, no mesmo padrão do `test_faixas_mapa_espelho.py`.
6. `tests/contracts/test_sem_moeda_hardcoded_no_front.py` (A10) — varre `web/src/lib/**/*.ts` atrás de
   `R$` fora de comentário e falha nomeando arquivo e linha; allowlist **vazia**. Escopo e números
   medidos na §2.7. Substitui a regra de ESLint que a versão anterior desta spec pedia — **não há
   ESLint neste projeto**.

---

## 6. Ordem de commits — cada um verde sozinho

| # | commit | arquivos | verde sozinho porque |
|---|---|---|---|
| **A1** | `perfil: dataclass congelada + loader + perfil.json do Brasil` | `src/motor_expansao/perfil.py` (novo), `data/perfis/BR/perfil.json` (**já versionado — o commit o REESCREVE no schema da §1.2, não o cria**), `tests/unit/test_perfil_loader.py`, `tests/contracts/test_perfil_br_reproduz_as_constantes.py` | **Ninguém importa `perfil` ainda.** Zero risco. Todo o desenho fica revisável antes de qualquer sítio mudar. |
| **A2** | `perfil: campo em Settings, com default None` | `src/motor_expansao/api/settings.py` | Campo com default não muda nenhum construtor existente. **Precede A6 obrigatoriamente** (§3.4). |
| **A3** | `perfil: resolver no import, matar o _DEFAULT_DATA` | `web/server/app.py:99-102` **+ `docker-compose.prod.yml` (mount do perfil em `web` e `api`) + `docs/deploy_piloto_web.md` (passo de cópia) — ver §6.1, é PRÉ-CONDIÇÃO, não opcional** | Fail-closed **só com `MOTOR_DATA_DIR`** (§3.2) ⇒ os 15 `import app` de topo seguem coletando. **Rode `pytest --collect-only` antes de abrir o PR** (§7, item 1) **e o critério nº 11, que roda o import DENTRO da imagem** — sem ele o commit fica verde no CI e indeployável na VPS. |
| **A4** | `perfil: bbox unificado nos 6 sítios + geocoder parametrizado + validação do resultado` | `api/coord.py:13-14`, `api/maps_geocoder.py:32,171-172,246,256`, `dashboard/data.py:624-627`, `dashboard/competitors.py:10-11`, `app.py:3978-3979` + validação em `:3997`, `tests/unit/test_coord_search.py:52-60`, `tests/contracts/test_geocode_valida_o_bbox.py` | O commit **maior** e o único que muda comportamento de aceite. Carrega a correção do §5.2 e o comando de verificação do §5.3. |
| **A5** | `perfil: reguas do funil derivadas do perfil` | `app.py:152-154,161`, `dashboard/constants.py:144,379`, `dashboard/relatorio_municipal.py:61`, `tests/contracts/test_regua_absoluta_censitaria.py:103-121` | **A correção do regex viaja NESTE commit** — é a condição para não quebrar longe da causa (§5.1). |
| **A6** | `perfil: injetar nos 4 sitios de Settings` | `app.py:4522,5224,7739,8008` | Depende de A2 e A3. Quatro linhas idênticas. |
| **A7** | `perfil: fontes e ancoras no painel de metodologia` | `app.py:3550,3553,3572-3577,3599-3605,3626-3628` | `test_metodologia_espelha_o_funil.py` continua verde (§5.5) e passa a provar que o painel lê o perfil. |
| **A8** | `ancoras: (valores, *, ancoras=ANCORAS_BR)` — **CRITICO, exige `critica-aprovada`** | `pipelines/calibrar_renda_setor_2022.py:118,124,148` (+ `ANCORAS_BR` novo) | Default nas constantes de hoje ⇒ os **5** chamadores não mudam e os contratos de régua ficam byte a byte (§4.2). **Isolado num commit só** para a revisão CRITICO ver um diff de ~15 linhas, não de 800. |
| **A9** | `perfil no front: bbox, locale, moeda, vista, reguas` | `web/src/lib/perfil.ts` + `perfil-br.ts` (novos), `coord.ts:8`, `entrada-ponto.ts:44,116`, `format.ts:6,38-41,51-53`, `faixas.ts:84`, `mapa-ponto.ts:32,49`, `colors.ts:65`, `HexMap.tsx:506-507`, `app.py` (`/api/me`), + os 4 `.test.ts` do §5.7/§5.8 | Sozinho porque `^web/` é **GOVERNANCA** e nenhum PR de front auto-mergeia (§8): separar poupa o Felipe de revisar front e Python no mesmo PR. |
| **A10** | `guardas: fio de alarme do pais + varredura anti-R$ + espelho do perfil no front` | `tests/contracts/test_fio_de_alarme_pais.py`, `test_perfil_front_espelha_o_python.py`, `test_sem_moeda_hardcoded_no_front.py` (escopo `web/src/lib/**/*.ts` — **NÃO** é regra de ESLint; não há ESLint no projeto, §2.7) | Fecha a porta de volta. Último de propósito: guarda que entra antes da mudança falha por motivo errado. |

**Serial obrigatório:** A1 → A2 → A3 → {A4, A5, A7} → A6; A8 independente; A9 depois de A3; A10 por último.
**A8 pode correr em paralelo desde o dia 1** — é o único que não depende do loader, e é o que precisa
da agenda do Felipe (§8). **Comece por ele e por A1 no mesmo dia.**

### 6.1 Pré-condição de INFRA do A3 — e por que ela pertence ao Bloco A

**O A3 é o commit que torna o `perfil.json` obrigatório para o processo subir. Ele não pode entrar
sozinho: hoje o arquivo NÃO EXISTE EM CONTAINER NENHUM, e o container `web` brasileiro não sobe no
primeiro deploy deliberado depois dele.** Conferido em 2026-09-02, no working tree:

1. `MOTOR_DATA_DIR=/app/data` está fixo em `Dockerfile.web:30` e repetido em
   `docker-compose.prod.yml:162` ⇒ o loader da §3.1 entra pelo ramo de **produção** e procura
   `/app/data/perfil.json`.
2. `/app/data` **não é** um mount. O compose monta só **subdiretórios**: `:223` (`outputs`), `:228`
   (`staging`), `:229` (`ibge`), `:230` (`ultra`), `:235` (`oportunidades`). O `/app/data` em si vem
   da imagem (`Dockerfile.web:85`). **`/app/data/perfil.json` não tem origem.**
3. O ramo embarcado tampouco salva: `.dockerignore:2` corta `data/` do contexto de build, e a
   instalação é **NÃO-EDITÁVEL** (`Dockerfile.web:45` / `Dockerfile.api:37`, `pip install "."`) — o
   mesmo motivo que o próprio compose já explica em `:59-60` para os `API_*_DIR`.
4. Não há passo de cópia em lugar nenhum: `grep -n perfil docs/deploy_piloto_web.md` devolve **zero
   linhas**.

**A correção é um par de mounts, e ela entra no MESMO commit A3:**

```yaml
# docker-compose.prod.yml — servico `web`, junto dos mounts de :223-:239
      - /opt/motor-expansao/data/perfil.json:/app/data/perfil.json:ro

# docker-compose.prod.yml — servico `api`, junto dos mounts de :81-:92
      - /opt/motor-expansao/data/perfil.json:/app/data/perfil.json:ro
    # ... e a env que o `api` NAO tem hoje:
    environment:
      MOTOR_DATA_DIR: "/app/data"
```

**Por que no `api` também, e por que ele precisa da env.** O A4 move `src/motor_expansao/api/coord.py`
e `src/motor_expansao/api/maps_geocoder.py` para o perfil, e os dois vivem na **imagem da API**
(`Dockerfile.api:37`). Lá `MOTOR_DATA_DIR` **não existe** — o compose só passa `API_*` (`:53-79`) —,
então o loader cairia no ramo embarcado; e `PERFIL_BR_EMBARCADO` é `parents[2]` a partir de
`__file__`, que sob instalação não-editável resolve para
`/usr/local/lib/python3.11/data/perfis/BR/perfil.json`, caminho que nunca existe. **A API quebraria
no A4 pelo mesmo defeito do A3, uma semana depois e longe da causa.** Acrescentar `MOTOR_DATA_DIR` ao
`api` é inerte para todo o resto: `grep -rn MOTOR_DATA_DIR src/ web/server/ scripts/` devolve como
únicos leitores `web/server/app.py:102` e `scripts/check_artifacts.py:24`, e o `Settings` da API tem
`env_prefix="API_"` (`src/motor_expansao/api/settings.py:29`), que não casa com `MOTOR_DATA_DIR`.

**Por que `.dockerignore` com `!data/perfis/` NÃO resolve — registrado para ninguém tentar.**
Un-ignorar a pasta põe o arquivo em `/app/data/perfis/BR/perfil.json` **dentro da imagem**, e nenhum
dos dois ramos do loader olha para lá:

- **Ramo de produção** (o do `web`): `MOTOR_DATA_DIR` está setado, então procura-se `/app/data/perfil.json`
  — a **raiz**, não `perfis/BR/`. Continua sem origem.
- **Ramo embarcado** (o do `api`, sem a env): `PERFIL_BR_EMBARCADO` resolve por `__file__`, e o
  `__file__` é o do pacote **instalado**, em `site-packages` — não o de `/app/src`, que não está no
  `sys.path`. Mudar o contexto de build não move esse caminho um milímetro.
- E o wheel não carregaria o arquivo nem se o contexto deixasse: `pyproject.toml:161-162`
  (`[tool.hatch.build.targets.wheel]`, `packages = ["src/motor_expansao"]`) empacota **só** o pacote;
  `data/` não é package data.

O `.dockerignore` é a **terceira** camada do problema, não a causa. Mexer nele sem o mount troca
"arquivo ausente" por "arquivo presente no lugar errado" — falha igual e explica pior.

**Por que esta linha de compose é do Bloco A e não do E — e por que isto CORRIGE a §8.4.** A §8.4
listava `docker-compose*` como território do Bloco E, e o Bloco E declara o compose intacto: o
conserto ficava **órfão**, que é como um bloqueador atravessa uma revisão inteira. Quem **cria** a
necessidade é o A3 — antes dele o compose está correto, depois dele está quebrado. Separar a linha do
commit que a exige abre uma janela em que a `main` fica **verde no CI e indeployável na VPS**,
exatamente a classe de defeito que só aparece no primeiro deploy deliberado, quando ninguém mais está
olhando para este PR. O que continua sendo do Bloco E é todo o resto do compose: serviço novo, rede,
Caddy, Authelia.

**Runbook, e ele também é do A3.** `docs/deploy_piloto_web.md` ganha, nas pré-condições, a linha que
hoje não existe — `scp data/perfis/BR/perfil.json <vps>:/opt/motor-expansao/data/perfil.json` (e
`AR/perfil.json` para a instância argentina), **antes** do `docker compose up -d`. Sem esse passo o
bind de arquivo do Docker cria um **diretório vazio** no host, e o container falha com "is a
directory" — mensagem pior do que a do fail-closed, e que não menciona perfil nenhum.

---

## 7. Critério de aceite do bloco — verificável por comando

Os itens **1 a 10** rodam da raiz do repositório e **nenhum exige env nova**. O item **11 é
diferente de propósito** — roda `docker build`/`docker run` — e é justamente por isso que ele existe:
tudo que roda no checkout fica verde com o container quebrado.

1. **A coleta do pytest fica verde sem `MOTOR_DATA_DIR`** — é o primeiro lugar onde o fail-closed quebra.
   ```
   python -m pytest --collect-only -q 2>&1 | tail -3
   ```
   Esperado: contagem de testes coletados, **zero erros**. (Rode **antes** de abrir o PR de A3.)

2. **A suíte brasileira passa sem um número se mover.** **Tome a baseline com o gate de governança
   VERDE:** até 2026-08-31 `tests/unit/test_claude_md_size.py` estava **vermelho** (a `DEC-047.md`
   existia sem linha-índice no `CLAUDE.md` §8 e sem entrada em `docs/decisions/README.md`), e uma
   baseline colhida ali embutiria uma falha alheia a este bloco na contagem de `passed`. Corrigido;
   confirme com `python -m pytest tests/unit/test_claude_md_size.py -q` **antes** de anotar o número.
   ```
   python -m pytest tests/contracts tests/unit -q
   ```
   Esperado: mesma contagem de `passed` de antes do bloco.

3. **O perfil BR reproduz as constantes de hoje, número a número.**
   ```
   python -m pytest tests/contracts/test_perfil_br_reproduz_as_constantes.py -q
   ```

4. **Não sobrou literal brasileiro de identidade nos sítios movidos.**
   ```
   grep -nE '(-34\.0|-33\.75|-73\.99|-74\.0|-75\.0|5\.27|-28\.65)' \
     src/motor_expansao/api/coord.py src/motor_expansao/api/maps_geocoder.py \
     src/motor_expansao/dashboard/data.py src/motor_expansao/dashboard/competitors.py \
     web/src/lib/coord.ts web/src/lib/entrada-ponto.ts
   grep -n 'countrycodes' web/server/app.py src/motor_expansao/api/maps_geocoder.py
   grep -nE '^(SCORE_CORTE_QUENTE|OFERTA_DESTAQUE_MIN|POP_MIN_ACIONAVEL|CAPACIDADE_CONCORRENTE_PADRAO)\s*=\s*[0-9]' web/server/app.py
   python -m pytest tests/contracts/test_sem_moeda_hardcoded_no_front.py -q
   ```
   Esperado: **os três `grep` sem nenhuma linha de saída** (exceto `data/perfis/BR/perfil.json`, que é
   onde os números passam a morar) e o **teste verde**.

   > **O `R$` virou teste, e não `grep`, por medição (2026-09-02).** A versão anterior deste critério
   > greppava **só o `web/src/lib/format.ts`**. Fora de comentário, `web/src/lib` tem `R$` em **quatro**
   > arquivos — `format.ts`, `comparacao.ts:98`, `comparacao-pontos.ts:60`, `recomendacao.ts:206`
   > (§2.7) —, então três passariam calados; e um `grep` cru também acusaria os **comentários** que
   > citam `R$` em `imovel.ts`, `mascara.ts`, `sparkline.ts`, `types.ts`, `exec.ts` e `report.ts`, que
   > são legítimos. Separar código de comentário é trabalho de parser, não de `grep`: é o teste do A10
   > que faz isso, e é ele o critério.

5. **O estreitamento do bbox de concorrentes não descarta um pin sequer** (§5.3).
   ```
   python -c "
   import pandas as pd
   from motor_expansao.dashboard import competitors as c
   df = pd.read_parquet('data/staging/concorrentes_mapeados.parquet')
   b3 = ((df.lat.between(-34.0, 6.0)) & (df.lng.between(-75.0, -28.0))).sum()
   b1 = ((df.lat.between(-34.0, 5.5)) & (df.lng.between(-74.0, -28.0))).sum()
   print('B3', b3, 'B1', b1, 'delta', b3 - b1)
   "
   ```
   **JÁ RODADO em 2026-08-31, e o resultado autoriza B1:** 3.296 linhas no parquet, **B3 = 3.269,
   B1 = 3.269, delta 0** — estreitar `competitors.py` de B3 para B1 não descarta um pin sequer. É com
   base nisto que a pendência **BR-P1** do `data/perfis/BR/perfil.json` foi **FECHADA em B1** e que o
   arquivo deixou de trazer a união (`lat_max 6,0` / `lng_min -75,0`), que além de não ter ganho
   medido **quebrava** `tests/unit/test_coord_search.py:58` — a linha que a §5.2 afirma ficar verde.
   Rode de novo se o parquet for regenerado; se der diferente de zero, **pare** e reabra a §1.3.

6. **O fio de alarme da DEC-047 está armado e a casa continua limpa.**
   ```
   python -m pytest tests/contracts/test_fio_de_alarme_pais.py -q
   grep -rn "pais ==\|pais==\|country ==" --include=*.py --include=*.ts --include=*.tsx src web scripts
   ```
   Esperado: teste verde; grep **sem saída**.

7. **Container sem perfil não sobe, e o log diz por quê.**
   ```
   MOTOR_DATA_DIR=/tmp/vazio python -c "import sys; sys.path.insert(0,'web/server'); import app"
   ```
   Esperado: `PerfilInvalidoError` nomeando `perfil.json` e o caminho. **Exit code != 0.**

8. **A busca por endereço não devolve mais o homônimo brasileiro** (o A1).
   ```
   python -m pytest tests/contracts/test_geocode_valida_o_bbox.py -q
   ```

9. **O front continua verde e o espelho do perfil bate.**
   ```
   cd web && npm test -- --run
   ```

10. **O `loop_guard` classifica o diff como esperado** (§8):
    ```
    git diff --name-only origin/main... | python scripts/loop_guard.py --stdin
    ```
    Esperado: **CRITICO** apenas em `dashboard/constants.py`, `dashboard/relatorio_municipal.py` e
    `pipelines/calibrar_renda_setor_2022.py`. Qualquer outro CRITICO é escopo que vazou.

11. **O import roda DENTRO DA IMAGEM CONSTRUÍDA, não no checkout** — acrescentado em 2026-09-02.
    **É o único critério desta lista que pega o defeito da §6.1.** Os itens 1 e 7 rodam no working
    tree, onde `data/perfis/BR/perfil.json` existe e `/app/data` não: os dois ficariam **verdes com o
    container quebrado**. É a diferença entre provar que o código está certo e provar que o deploy sobe.
    ```
    docker build -f Dockerfile.web -t motor-expansao-web:local .

    # (a) SEM o mount do perfil -> tem de FALHAR, nomeando /app/data/perfil.json
    docker run --rm motor-expansao-web:local \
      python -c "import sys; sys.path.insert(0,'web/server'); import app"; echo "exit=$?"

    # (b) COM o mount da pre-condicao da §6.1 -> tem de imprimir BR
    docker run --rm -v /opt/motor-expansao/data/perfil.json:/app/data/perfil.json:ro \
      motor-expansao-web:local \
      python -c "import sys; sys.path.insert(0,'web/server'); import app; print(app.PERFIL.pais)"
    ```
    Esperado: **(a) `exit=1`, com `PerfilInvalidoError` citando `/app/data/perfil.json`; (b) `BR`.**
    Se **(a)** passar, o fail-closed não está armado. Se **(b)** falhar, o mount da §6.1 não entrou —
    e é este o cenário que hoje derruba o piloto no próximo deploy.

    E o mesmo para a imagem da API, que o A4 põe no mesmo caminho:
    ```
    docker build -f Dockerfile.api -t motor-expansao-api:local .
    docker run --rm -e MOTOR_DATA_DIR=/app/data \
      -v /opt/motor-expansao/data/perfil.json:/app/data/perfil.json:ro \
      motor-expansao-api:local \
      python -c "from motor_expansao.perfil import resolver_perfil; print(resolver_perfil().pais)"
    ```
    > **Por que `python -c` funciona nas duas imagens.** A camada BLK-SEC-04 remove
    > `pip`/`setuptools`/`wheel`, **não** o interpretador — o próprio smoke de `Dockerfile.web:80` é um
    > `python -c` que roda depois da remoção. E não há `ENTRYPOINT` em nenhum dos dois Dockerfiles
    > (só `CMD`, em `Dockerfile.web:94` e `Dockerfile.api:88`), então o argumento substitui o comando
    > em vez de virar parâmetro do uvicorn.

**O que NÃO é critério de aceite:** `/api/health` verde. Health verde é exatamente o que a instância
vazia devolve (§5.0.4 do plano).

---

## 8. A pegadinha de governança

### 8.1 Classificação medida, não estimada

Rodado agora contra `scripts/loop_guard.classificar`, com os caminhos deste bloco:

| arquivo do Bloco A | classe | motivo (do próprio guard) |
|---|---|---|
| `src/motor_expansao/dashboard/constants.py` | **CRITICO** | `constants.py - pesos/constantes M1/mapa` (`loop_guard.py:72`) |
| `src/motor_expansao/dashboard/relatorio_municipal.py` | **CRITICO** | `limiares do 'hexagono destacado' do Relatorio Municipal (DEC-011)` (`:97-100`) |
| `src/motor_expansao/pipelines/calibrar_renda_setor_2022.py` | **CRITICO** | `score/insumo paralelo servido em producao` (`:82-85`) |
| `src/motor_expansao/api/coord.py` | governanca | `API/bot servidos em producao` (`:180`) |
| `src/motor_expansao/api/maps_geocoder.py` | governanca | idem |
| `src/motor_expansao/api/settings.py` | governanca | idem |
| `src/motor_expansao/dashboard/data.py` | governanca | `camada que calcula/exibe os numeros do dashboard` (`:176-179`) |
| `web/server/app.py` | governanca | `piloto web servido em producao` (`:184`) |
| `web/src/lib/*.ts`, `web/src/components/*.tsx` | governanca | `^web/` (`:184`) |
| `src/motor_expansao/perfil.py` **(novo)** | **LIMPO** | — |
| `data/perfis/BR/perfil.json` (já existe; reescrito) | **LIMPO** | — |
| `tests/**` **(todos, novos e alterados)** | **LIMPO** | — |

**Veredito: 3 arquivos CRITICO ⇒ o bloco exige `critica-aprovada` do Felipe.** O plano cita dois
(`constants.py` e `calibrar_renda_setor_2022.py`); **`relatorio_municipal.py` é o terceiro, achado
por esta spec** — ele carrega a segunda cópia de `OFERTA_DESTAQUE_MIN` (`:61`) e nenhum documento o
listava.

### 8.2 Três achados de governança que mudam como você organiza os PRs

**(a) `dashboard/competitors.py` é LIMPO no `loop_guard` — e carrega uma das seis cópias de bbox.**
Conferido: o padrão `^src/motor_expansao/dashboard/(data|utils|censo_point|censo_map|censo_report)\.py$`
(`loop_guard.py:176-179`) **não inclui `competitors.py`**, e nenhum padrão CRITICO o alcança. Ou seja,
**um PR "Media" auto-mergeável pode hoje mudar o bounding box que filtra os pins de concorrente sem
olho humano.** Isso **não** é conserto do Bloco A (mexer no `loop_guard.py` é GOVERNANCA por si só,
`:164`, e infla o escopo), mas **tem de ficar escrito** — é candidato natural ao BLK-INTL-00.

**(b) Os 4 chamadores de `calcular_score_calibrado` são TODOS CRITICO.**
`agregar_censo_hex_da_malha.py`, `fase_a_nacional_completo.py`, `fase_a_piloto_expandido.py` e
`recalcular_score_absoluto.py` casam `produtor da camada censitaria` (`loop_guard.py:92-96`). **A
assinatura com default (§4.2) é o que mantém os quatro FORA do diff** — se você tornar `ancoras`
obrigatório, o commit A8 passa de 3 arquivos CRITICO para **7**, e a revisão do Felipe quadruplica.
Isso não é otimização: é a diferença entre um PR revisável e um PR que fica parado uma semana.

**(c) `conftest.py` e `pyproject.toml` são CRITICO** (`loop_guard.py:145`, `:143`). É a razão
material — não estética — para a §3.2 recusar a fixture de sessão e escolher o `perfil.json`
embarcado: a fixture arrastaria `conftest.py` para dentro de um bloco que já tem 3 CRITICO.

### 8.3 O que ainda precisa da agenda do Felipe

1. **`critica-aprovada`** no PR do commit **A8** (e nos de A5/A7 se você juntar `constants.py` neles —
   **não junte**).
2. **A escolha das âncoras argentinas** de renda (USD) e de população por hexágono (§4.4). **Não
   bloqueia o início:** o `data/perfis/AR/perfil.json` já traz âncoras argentinas **medidas**
   (350/1.000 USD, 1.000/100.000 hab), declaradas como provisórias nas pendências P1 e P2 do próprio
   arquivo, e o A8 sai hoje com o default `ANCORAS_BR` intacto. (Corrigido em 2026-08-31: esta linha
   dizia "`_provisorio: true` com âncoras BR" — campo que não existe e âncora que não é a entregue.)
3. **`^web/` é GOVERNANCA:** o commit **A9 não auto-mergeia**. Agende junto com A8, não depois.

### 8.4 O que este bloco NÃO toca — por decisão, não por esquecimento

`scripts/loop_guard.py` · `REVIEW.md` · `CLAUDE.md` · `docs/plano_multipais.md` · `docs/decisions/**` ·
`web/server/acesso.py` (é o Bloco C) · `authelia/**` (Bloco D) · `Caddyfile` e `docker-compose*`
**com UMA exceção nomeada** (Bloco E) · `web/server/app.py:412` (`_UF_RE`, BLK-INTL-04) · `web/src/lib/pais-da-base.ts`
(§5.0.2, dívida nº 2) · `_COLS_DESEJADAS` (`app.py:376-405`) e as quatro leituras do funil (Bloco B) ·
`pipelines/normalizar_unidades_ultra.py:27-28` (§2.1, item 7) ·
`vulnerabilidade/contrato.py:142` (§2.1, item 9) · `dashboard/constants.py:145` (`BRASIL_CENTER`,
constante morta — §1.4).

> ⚠️ **A EXCEÇÃO NOMEADA, e por que ela precisou existir (2026-09-02).** Este bloco **toca**
> `docker-compose.prod.yml` em exatamente **duas linhas de mount e uma de env** — o `perfil.json` nos
> serviços `web` e `api`, mais `MOTOR_DATA_DIR` no `api` — e **acrescenta o passo de cópia** em
> `docs/deploy_piloto_web.md`. Tudo especificado na **§6.1**, tudo dentro do commit **A3**.
>
> **Isto é correção de uma ORFANDADE, não expansão de escopo.** A versão anterior desta lista mandava
> todo `docker-compose*` para o Bloco E, e o Bloco E declara o compose intacto: o único conserto que
> faz o container subir depois do A3 não tinha dono em bloco nenhum. Um bloqueador sem dono não é
> adiado — ele é esquecido, e reaparece como o piloto que não sobe. Quem cria a necessidade é o A3, e
> por isso é o A3 que a paga. O resto do compose — serviço novo, rede, Caddy, Authelia — continua
> sendo do Bloco E, sem uma linha de sobreposição.
