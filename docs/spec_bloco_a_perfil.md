# SPEC EXECUTÁVEL — Bloco A: o perfil do país

- Data: 2026-08-31 | Status: **PRONTA PARA CODAR** | Dono do arquivo: esta spec (o `docs/plano_multipais.md` e `docs/decisions/` têm outros donos e **não** são alterados por aqui)
- Escopo: **Bloco A da §5.0** do `plano_multipais.md` = **BLK-INTL-02** (parte de perfil), sob a **DEC-046**.
- Esforço declarado no plano: **7-11 dias · 1 dev**. Exige **`critica-aprovada`** (ver §8).
- Objetivo operacional: depois deste bloco, **nenhum literal brasileiro de identidade territorial, de moeda, de fonte de dado ou de régua absoluta vive em constante de módulo**. Todos são lidos de um objeto congelado resolvido uma vez no import.

---

## 0. Como ler esta spec — e uma correção de linha que você vai precisar

**Toda referência `arquivo:linha` desta spec foi conferida no working tree em 2026-08-31.**

> ⚠️ **AVISO QUE POUPA MEIA HORA.** As referências a `web/server/app.py` **acima da linha ~3200** no
> `docs/plano_multipais.md` estão **14 linhas defasadas** (o arquivo tem 8.647 linhas e cresceu depois
> que o plano foi escrito). A DEC-046 já registra a mesma defasagem para `limpar_caches`
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
envelhece calado, que é exatamente a classe de defeito que a DEC-045 e a DEC-046 combatem.

### 1.2 O schema, campo a campo

`perfil.json` mora na **raiz do `MOTOR_DATA_DIR`**: `${MOTOR_DATA_DIR}/perfil.json`. As **fontes
versionadas** que o deploy copia para lá são `data/perfis/BR/perfil.json` e `data/perfis/AR/perfil.json`
(§3.1) — e o BR é também o default de dev/teste.

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
| `vista_padrao.lat/lng/zoom` | `float` | **sim** | `VISTA_BRASIL = { longitude: -52.9, latitude: -14.5, zoom: 3.4 }` — `web/src/lib/mapa-ponto.ts:32`, consumido por `web/src/components/MapaPonto.tsx:63`. **Achado desta spec:** não está em nenhuma das listas do plano nem da DEC-046, e é superfície do DIA 1. |
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
(`countrycodes`) · **[NOVO]** = sítio **achado por esta spec**, ausente do plano e da DEC-046.

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
| 12 | `src/motor_expansao/api/maps_geocoder.py:246` | `"countrycodes": "br"` | `PERFIL.geocode.countrycodes` | **[NOVO]** — segunda cópia de `countrycodes`, **não listada** no plano nem na DEC-046. |
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

### 2.7 Lint que impede a volta

No mesmo bloco, uma regra de ESLint proibindo o literal `R$` em `web/src/**/*.{ts,tsx}`
(`no-restricted-syntax` sobre `Literal[value=/R\$/]`), com allowlist **vazia** e o motivo no arquivo
de config. Sem isso, o próximo componente reintroduz o símbolo e nada acusa. (Análogo Python: um teste
de contrato que varre `web/server/app.py` e `src/motor_expansao/dashboard/` atrás de `R$` em string
de usuário — ver §5.9.)

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

**Não** entra rota nova (DEC-046: "não entra requisição"). O front já pede `GET /api/me` na abertura
(`web/server/app.py:3221`). O payload de `/api/me` ganha um campo `perfil` com **exatamente** o que o
front lê: `nome`, `locale`, `moeda`, `bbox`, `vista_padrao`, `reguas.pop_min_acionavel`,
`reguas.capacidade_unidade_alunos`. Nada mais.

`web/src/lib/perfil.ts` (novo) expõe `perfilDoCliente(): PerfilCliente` a partir de um módulo-estado
preenchido uma vez no bootstrap, **com um default BR compilado** — porque `coord.ts`,
`entrada-ponto.ts`, `format.ts`, `faixas.ts`, `colors.ts` e `mapa-ponto.ts` são módulos **puros**
testados pelo Vitest **sem servidor**, e sem esse default os testes de §5.7 e §5.8 quebram por
`undefined`, não por régua. O default BR do front vive num único `perfil-br.ts` gerado do mesmo
`data/perfis/BR/perfil.json` — e um teste de contrato trava que os dois batem (§5.9).

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

As âncoras argentinas de **renda (USD)** e de **população por hexágono**. As brasileiras saem de
distribuição de **setor censitário** (`calibrar_renda_setor_2022.py:85-86`: p05 = 1.103, p95 = 28.845);
a AR alimentaria com população de **hexágono**. Converter só a moeda e manter `POP_ABS_MIN/MAX` **não
é escolher âncora argentina — é trocar a unidade em silêncio**.

**Corrigido em 2026-08-31 — a redação anterior desta seção descrevia um perfil que não é o entregue.**
Ela dizia que "o `perfil_ar.json` nasce com **as âncoras brasileiras copiadas** e um campo
`reguas._provisorio: true`", e que "o código do Bloco A fica pronto com âncora BR na AR". Nada disso
existe: **não há arquivo `perfil_ar.json`** (é `data/perfis/AR/perfil.json`), **não há campo
`reguas._provisorio`**, e as âncoras de renda **não** são brasileiras. Pior: "âncora BR na AR" é
exatamente o defeito que o §5.0 do plano chama de **"trocar a unidade em silêncio"** — a spec estava
recomendando o que o plano proíbe. O estado real, e o que vale:

> O `data/perfis/AR/perfil.json` **já nasce com âncoras argentinas medidas**: `renda_abs_min` = **350,0**
> e `renda_abs_max` = **1.000,0 USD**, `pop_abs_min` = **1.000** e `pop_abs_max` = **100.000**. A
> provisoriedade é marcada em `_nota_renda`/`_nota_pop` e nas pendências **P1** (renda) e **P2**
> (população) do próprio arquivo — não num campo `_provisorio`.

**De onde saem os 350/1.000.** Não é conversão de moeda — é o **critério** de
`calibrar_renda_setor_2022.py:83-92` (piso no p05 arredondado, teto acima do p99 e abaixo do máximo,
saturando < 0,4%) aplicado à distribuição argentina medida no pacote em 2026-08-31 (universo povoado,
pop ≥ 1.000, 5.148 hexágonos): p05 = 342,4 · p50 = 478,4 · p95 = 740,5 · p99 = 926,2 · max = 1.141,1.
Piso 350, teto 1.000 (satura 0,29%; o Brasil satura 0,38% com R$ 4.000). Os 1.000/100.000 de população
são os **mesmos números** do Brasil, e o `_nota_pop` do arquivo diz **por quê** e o que isso custa: a
âncora BR foi medida sobre **setor censitário** e a AR alimentaria com **hexágono** — unidades
diferentes, reusadas porque as duas distribuições coincidem **por medição** (BR p05 1.103 / p50 3.561 /
p95 28.845 · AR 1.127 / 3.699 / 28.500), não por analogia. É essa frase escrita que separa "âncora
provisória declarada" de "trocar a unidade em silêncio".

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
3. `tests/contracts/test_fio_de_alarme_pais.py` — DEC-046: varre `src/`, `web/`, `scripts/` atrás de
   `pais ==`, `pais==`, `country ==`; lista de exceções **vazia**. Medido hoje: **zero ocorrências**.
4. `tests/contracts/test_geocode_valida_o_bbox.py` — Nominatim mockado devolvendo Buenos Aires com
   perfil BR ⇒ `{"found": False, "motivo": "fora_do_pais"}`; com perfil AR ⇒ `found: True`.
   **É a prova do A1.**
5. `tests/contracts/test_perfil_front_espelha_o_python.py` — `web/src/lib/perfil-br.ts` bate com
   `data/perfis/BR/perfil.json`, no mesmo padrão do `test_faixas_mapa_espelho.py`.

---

## 6. Ordem de commits — cada um verde sozinho

| # | commit | arquivos | verde sozinho porque |
|---|---|---|---|
| **A1** | `perfil: dataclass congelada + loader + perfil.json do Brasil` | `src/motor_expansao/perfil.py` (novo), `data/perfis/BR/perfil.json` (**já versionado — o commit o REESCREVE no schema da §1.2, não o cria**), `tests/unit/test_perfil_loader.py`, `tests/contracts/test_perfil_br_reproduz_as_constantes.py` | **Ninguém importa `perfil` ainda.** Zero risco. Todo o desenho fica revisável antes de qualquer sítio mudar. |
| **A2** | `perfil: campo em Settings, com default None` | `src/motor_expansao/api/settings.py` | Campo com default não muda nenhum construtor existente. **Precede A6 obrigatoriamente** (§3.4). |
| **A3** | `perfil: resolver no import, matar o _DEFAULT_DATA` | `web/server/app.py:99-102` | Fail-closed **só com `MOTOR_DATA_DIR`** (§3.2) ⇒ os 15 `import app` de topo seguem coletando. **Rode `pytest --collect-only` antes de abrir o PR** (§7, item 1). |
| **A4** | `perfil: bbox unificado nos 6 sítios + geocoder parametrizado + validação do resultado` | `api/coord.py:13-14`, `api/maps_geocoder.py:32,171-172,246,256`, `dashboard/data.py:624-627`, `dashboard/competitors.py:10-11`, `app.py:3978-3979` + validação em `:3997`, `tests/unit/test_coord_search.py:52-60`, `tests/contracts/test_geocode_valida_o_bbox.py` | O commit **maior** e o único que muda comportamento de aceite. Carrega a correção do §5.2 e o comando de verificação do §5.3. |
| **A5** | `perfil: reguas do funil derivadas do perfil` | `app.py:152-154,161`, `dashboard/constants.py:144,379`, `dashboard/relatorio_municipal.py:61`, `tests/contracts/test_regua_absoluta_censitaria.py:103-121` | **A correção do regex viaja NESTE commit** — é a condição para não quebrar longe da causa (§5.1). |
| **A6** | `perfil: injetar nos 4 sitios de Settings` | `app.py:4522,5224,7739,8008` | Depende de A2 e A3. Quatro linhas idênticas. |
| **A7** | `perfil: fontes e ancoras no painel de metodologia` | `app.py:3550,3553,3572-3577,3599-3605,3626-3628` | `test_metodologia_espelha_o_funil.py` continua verde (§5.5) e passa a provar que o painel lê o perfil. |
| **A8** | `ancoras: (valores, *, ancoras=ANCORAS_BR)` — **CRITICO, exige `critica-aprovada`** | `pipelines/calibrar_renda_setor_2022.py:118,124,148` (+ `ANCORAS_BR` novo) | Default nas constantes de hoje ⇒ os **5** chamadores não mudam e os contratos de régua ficam byte a byte (§4.2). **Isolado num commit só** para a revisão CRITICO ver um diff de ~15 linhas, não de 800. |
| **A9** | `perfil no front: bbox, locale, moeda, vista, reguas` | `web/src/lib/perfil.ts` + `perfil-br.ts` (novos), `coord.ts:8`, `entrada-ponto.ts:44,116`, `format.ts:6,38-41,51-53`, `faixas.ts:84`, `mapa-ponto.ts:32,49`, `colors.ts:65`, `HexMap.tsx:506-507`, `app.py` (`/api/me`), + os 4 `.test.ts` do §5.7/§5.8 | Sozinho porque `^web/` é **GOVERNANCA** e nenhum PR de front auto-mergeia (§8): separar poupa o Felipe de revisar front e Python no mesmo PR. |
| **A10** | `guardas: fio de alarme do pais + lint anti-R$ + espelho do perfil no front` | `tests/contracts/test_fio_de_alarme_pais.py`, `test_perfil_front_espelha_o_python.py`, config do ESLint | Fecha a porta de volta. Último de propósito: guarda que entra antes da mudança falha por motivo errado. |

**Serial obrigatório:** A1 → A2 → A3 → {A4, A5, A7} → A6; A8 independente; A9 depois de A3; A10 por último.
**A8 pode correr em paralelo desde o dia 1** — é o único que não depende do loader, e é o que precisa
da agenda do Felipe (§8). **Comece por ele e por A1 no mesmo dia.**

---

## 7. Critério de aceite do bloco — verificável por comando

Todos rodam da raiz do repositório. **Nenhum exige env nova.**

1. **A coleta do pytest fica verde sem `MOTOR_DATA_DIR`** — é o primeiro lugar onde o fail-closed quebra.
   ```
   python -m pytest --collect-only -q 2>&1 | tail -3
   ```
   Esperado: contagem de testes coletados, **zero erros**. (Rode **antes** de abrir o PR de A3.)

2. **A suíte brasileira passa sem um número se mover.** **Tome a baseline com o gate de governança
   VERDE:** até 2026-08-31 `tests/unit/test_claude_md_size.py` estava **vermelho** (a `DEC-046.md`
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
   grep -n 'R\$' web/src/lib/format.ts
   grep -nE '^(SCORE_CORTE_QUENTE|OFERTA_DESTAQUE_MIN|POP_MIN_ACIONAVEL|CAPACIDADE_CONCORRENTE_PADRAO)\s*=\s*[0-9]' web/server/app.py
   ```
   Esperado: **as quatro sem nenhuma linha de saída** (exceto `data/perfis/BR/perfil.json`, que é onde os
   números passam a morar).

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

6. **O fio de alarme da DEC-046 está armado e a casa continua limpa.**
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
`web/server/acesso.py` (é o Bloco C) · `authelia/**` (Bloco D) · `docker-compose*` e `Caddyfile`
(Bloco E) · `web/server/app.py:412` (`_UF_RE`, BLK-INTL-04) · `web/src/lib/pais-da-base.ts`
(§5.0.2, dívida nº 2) · `_COLS_DESEJADAS` (`app.py:376-405`) e as quatro leituras do funil (Bloco B) ·
`pipelines/normalizar_unidades_ultra.py:27-28` (§2.1, item 7) ·
`vulnerabilidade/contrato.py:142` (§2.1, item 9) · `dashboard/constants.py:145` (`BRASIL_CENTER`,
constante morta — §1.4).
