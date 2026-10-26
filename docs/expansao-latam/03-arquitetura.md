# 03 — Arquitetura-alvo multi-país (CO, MX, PE, PY)

- **Data:** 2026-10-16 · **Status:** PROPOSTA. Nada aqui está decidido: as decisões saem como **propostas de DEC** (§9), na matriz de autonomia da DEC-016 (Alta → `aprovado-humano`; Crítica → `critica-aprovada` do dono).
- **Insumos:** `00-baseline-argentina.md` (acoplamento e contrato), `01-dossie-*.md` (os 4 países + transversal), `anexos/auditoria-*.md`.
- **Restrições herdadas, que este documento NÃO reabre:**
  - **DEC-047:** instância por país, país declarado no `perfil.json`, nenhum `if pais ==`, fronteira plataforma × pipeline.
  - **Decisão 0.1 do `docs/plano_multipais.md`:** sem comparação entre países.
  - **D4:** interface em português até ordem do dono.
  - **M1 READ-ONLY.**
  - **DEC-041:** o funil é triagem (política declarada), não previsão. A DEC-043 foi revogada pela DEC-078 em 21/10/2026, que pôs na Viabilidade do BR uma sugestão de faturamento calibrada em unidades Ultra.

---

## 1. Princípio: o silo da DEC-047 está certo. O que falta é a parte compartilhada do silo

A literatura de SaaS chama de **silo** o que a DEC-047 escolheu: recurso dedicado por inquilino, com onboarding, identidade e operação compartilhados (AWS Well-Architected SaaS Lens, *silo/pool/bridge*; verificado pelo agente transversal). Há três motivos para não migrar ao **pool** (modelo único multi-país):
- os 40 `lru_cache` e os 6 caches de renda sem `cache_clear`, que tornariam o pool um defeito de correção;
- o *noisy neighbor* de CPU já medido;
- a recusa de comparação entre países.

**O que a Argentina mostrou é que a metade "compartilhada" do silo não existe:**
- **onboarding:** não há validador de pacote nem exportador genérico, e a AR foi feita à mão;
- **operação:** compose, Caddy, Authelia, portal e healthcheck são copiados à mão;
- **identidade:** são dois cadastros de usuário.

É aí que o 3º ao 6º país ficam caros, não no código do app. A arquitetura-alvo é, portanto:

```
                   ┌──────────────────────────── PLATAFORMA (este repo) ─────────────────────────────┐
  repo pipeline CO ─┤ kit de país (lib) ─► pacote ─► VALIDADOR SEMÂNTICO ─► scp ─► volume /pais=CO   │
  repo pipeline MX ─┤   (dasimetria, raking,          (contrato canônico          │                    │
  repo pipeline PE ─┤    renda modelada, dedup,        por camada +              ▼                    │
  repo pipeline PY ─┤    calibração de oferta)         manifesto de fontes) instância web_CO … (1 por │
                   │                                                         país, mesma imagem)     │
                   │  registry paises.yml ─► gera compose / Caddy / portal / healthcheck / grupos    │
                   │  identidade única ─► autorização por host (grupo expansao_<pais>)               │
                   └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Componentes

### 2.1 Núcleo comum (já existe; continua um binário)

O núcleo é o que já está no ar: serving do funil, mapa, ficha, PDFs, motor de viabilidade e controle de acesso. **Ele não ganha eixo de país.** Ganha só:
- **réguas faltantes no perfil** (§3);
- **leitores** para os campos hoje mortos;
- **fail-closed** nos fallbacks brasileiros escondidos.

### 2.2 Contrato canônico por camada + validador semântico (novo; o item mais importante)

`docs/contrato_pacote_pais.md` + `scripts/validar_pacote_pais.py`, versionados na plataforma e rodados **pelo produtor** antes do `scp` (DEC-047 §1.1, consequência 1). O schema canônico é o da §2 do `00-baseline-argentina.md`, camada a camada.

**Três níveis de checagem.** O terceiro é o que a AR provou faltar:

| Nível | Checa | Exemplo do defeito que pega |
|---|---|---|
| 1 — Presença | coluna obrigatória por camada e por superfície ligada no perfil | `oferta_consumida_mercado_estimada` ausente → camada 3 inteira "livre" |
| 2 — Tipo e formato | dtype, chave como **string com zero à esquerda**, CRS declarado, `hex_id` res 7 válido | `regiao` int64 × string (AR); `cod_municipio` `"05001"` virando 5001 (CO) |
| 3 — **Semântica** | invariantes numéricos contra referências declaradas no manifesto | Soma de `pop_total_setor_2022` = total do censo/projeção ±2 % (pegaria o falso amigo `pop_total`, 391× o BR). Score recomputado pela plataforma bate o do pacote (pegaria o percentil renomeado). Moeda do indicador = âncoras no mesmo mês-base. Mediana do residual > `oferta_destaque_min` em pelo menos X % dos municípios (pegaria o piso inalcançável). Metas do semáforo na escala do país (pegaria SAM = 2.000 na AR). Fração de quentes em [1 %, 15 %] |

**Manifesto de fontes (registry):** `manifesto.json` dentro do pacote, com uma linha por fonte. Campos de cada linha:
- `id`, `url`, `licença`, `safra`, `data_acesso`, `hash`;
- `camadas_alimentadas`;
- `uso_comercial_permitido` (bool).

**O validador recusa o pacote** se qualquer fonte que alimenta superfície servida tiver `uso_comercial_permitido = false`. Isso vem da lição do Relative Wealth Index (Meta), que é CC BY-NC (ver auditoria de dados). O manifesto também alimenta a frase de fonte e o ano de cada PDF, o que mata os "IBGE/Censo 2022/CAGED" fixos (C1 do baseline).

### 2.3 Adaptadores por país

Há dois níveis, e só o primeiro mora fora:

1. **Repositório de pipeline do país** (dono: Juan, ou quem for designado). Contém o **método**: censo → dasimetria H3 → renda modelada → concorrentes → mercado → pacote. Não serve tráfego. **Não muda** (DEC-047).
2. **De-para declarativo na plataforma:** `data/perfis/<XX>/depara.json`, que mapeia as colunas do pipeline para as canônicas. Substitui o `exportar_piloto_ar.py` (1.100 linhas, argentino, com `import nacional_academia` externo e **duas cópias divergentes**) por um **exportador genérico**.
   - O exportador recomputa o score na régua da plataforma (lição 2 da AR).
   - Deriva `hex_id`/`lat`/`lng`.
   - Escreve as partições.
   - O país novo entrega dado e um JSON, nunca código na plataforma.

### 2.4 Kit comum de pipeline (novo; proposta DEC-073/D2)

Os 4 países repetem os mesmos cinco algoritmos que o Juan escreveu para a AR. Reescrever cada um 4 vezes é o maior custo evitável do programa:
- dasimetria de unidade censitária → H3 res 7;
- raking a totais oficiais;
- renda modelada por pesquisa domiciliar (EPH na AR; GEIH, ENIGH, ENAHO e EPHC agora) com covariáveis censitárias;
- dedup de concorrentes multi-fonte;
- calibração de capacidade por fator de cobertura.

A proposta é uma **biblioteca Python versionada** (`motor_pais_kit`). Ela é consumida pelos repos de pipeline e **não é importada pelo serving**, então não viola a fronteira da DEC-047, que separa quem serve tráfego de quem produz dado.

---

## 3. Refatoração para tirar o acoplamento identificado na Fase 0

Ordenada por dependência. Códigos (S1, Q3…) remetem ao `00-baseline-argentina.md` §3.

| # | Refatoração | Fecha | Natureza | Criticidade (guard) |
|---|---|---|---|---|
| R1 | **Réguas de ficha e zona morta no perfil:** `reguas.renda_min_ficha` (BR = 4.500), `renda_zona_morta_min` (BR = 500, DEC-042), `pop_zona_morta_min` (BR = 5.000). Leitores em `app.py:6478` e `viabilidade_ponto.py:72` | S1, S2 (AR **hoje**) | Literal → perfil, BR idêntico ao bit | Alta (`viabilidade_ponto.py` em GOVERNANCA) |
| R2 | **Front lê as faixas e a moeda do perfil:** `colors.ts` consome `bandas_*` do `/api/me`, que passa a servir também as faixas DOMICILIARES do perfil (desde o #473 o calor de renda pinta a domiciliar, e o `bandas_renda_setor` de hoje é per capita); renda rotulada por `moedaRenda()` (a legenda do calor já usa). Guarda anti-moeda estendida a `screens/` e `components/` (allowlist só da viabilidade) | S3, S4 (AR **hoje**) | Front | Alta (`web/`) |
| R3 | **Réguas do funil completas:** `demanda_min/max_alunos`, `peso_socio/demanda`, `conc_adensar_max`, `crit_ponto_*`, `consumo_1km_cortes`. **Derivação declarada:** âncoras de demanda = f(`capacidade_concorrente`), e não literal | S7, S9, S8 | Literal → perfil | Crítica (`constants.py`) |
| R4 | **Campos mortos:** ligar leitor (`score_pesos`, `separador_*`, `faixas_mapa_*`) ou remover do schema (`taxa_fitness`, `mem_limit_alvo`, `basemap_labels_url_obrigatoria`), com o loader **recusando** chave desconhecida em vez de "tolerar" | S11 | Loader | Alta |
| R5 | **Fallbacks BR fail-closed:** `k = 1.0239`, `fillna(2_500)`, `TAXA_FITNESS_FALLBACK = 0,10`. O fator temporal já é fail-closed por país desde a DEC-075 (sem `renda/fatores/<PAIS>/` a subida falha), e o k também quando o arquivo do país declara `artefato_k_obrigatorio` (o BR declara; a AR, não). Com perfil ≠ BR e insumo ausente, a resposta é **"indisponível"** com motivo, nunca o número brasileiro | S10 | Serving | Crítica (parte em `constants.py`) |
| R6 | **Chave de município integral e declarada:** `perfil.identidade.chave_municipio` = `{comprimento, regex}`. O join do crescimento passa a casar a chave inteira normalizada, e não `str[:6]` | S6 (CO 5, MX 5, PY 4 dígitos; PE 6 casa por acaso) | Serving | Alta |
| R7 | **Partição alfanumérica:** `_UF_RE` → `^[A-Za-z0-9]{2,6}$`, com teste de traversal no mesmo commit (BLK-INTL-04). Rótulos de nível 1 (nome, bandeira, vocabulário "departamento/estado/provincia") saem das tabelas TS por sigla e vão para o perfil. **Isso elimina a fabricação de siglas e o problema das colisões** (`AM` em CO e PY; `SP`, `CE`, `AP` em PY; `MG`, `SP` em MX) | Q3, C2 | Segurança | **Crítica** (sink anti-traversal) |
| R8 | **`mascara.ts` por locale:** gramática numérica do `perfil.moeda.separador_*`. **Obrigatório antes de MX e PE** (`1,500.00`) | S5 | Front puro, com testes | Alta |
| R9 | **Camadas de leitura declaradas:** `_CAMADAS_AR` (`app.py:910-925`) → `perfil.camadas_leitura` (lista de colunas + rótulo + unidade). País novo com camadas próprias = JSON, não `app.py` | C8 | Serving | Alta |
| R10 | **Nomes de artefato neutros:** `hexagonos_brasil_dashboard.parquet` (dependência da camada de 1 km) passa a ter nome canônico no contrato, com alias para o BR | S13 | Serving + contrato | Alta |
| R11 | **Textos de fonte do manifesto:** instituto, ano do censo e fonte de emprego (CAGED/RAIS → IMSS, ELIC…) lidos do perfil/manifesto nos PDFs, na metodologia e no funil | C1 | Texto | Alta |

**Invariante de toda a refatoração:** com o perfil BR, a saída é **idêntica ao bit**. Ela é travada por:
- golden de Londrina;
- snapshot de hash do funil BR antes e depois (§7);
- perfil AR com os defeitos S1–S4/S8 **corrigidos** (a AR é o único caso onde o número **deve** mudar).

---

## 4. Malha H3 e infraestrutura

### 4.1 Universo e particionamento

**Não replicar o universo territorial do Brasil.** O 1,54 M existe porque o M1 ranqueia o território inteiro, e nenhum país novo tem M1. A regra (molde AR) tem três partes:
- **calcular** sobre o universo ≥ 3 hab/km², que cobre ~98 % da população;
- **servir** "habitáveis + anel de 1 vizinho";
- **particionar** pelo nível 1 administrativo.

| País | Universo territorial (sobreposição) | Universo ≥ 3 hab/km² (est.) | **Servidos (est.)** | **Acionáveis** (captação ≥ 5.000, gate do funil) | Partições nível 1 |
|---|---|---|---|---|---|
| BR (ref.) | 1.542.531 | — | 1.303.414 | — | 27 |
| AR (ref.) | 664.228 | 42.388 (medido) | 15.186 (medido) | — | 24 |
| **MX** | 332.845 | ~50.500 | **~41.400** | ~22.500 | 32 |
| **CO** | 215.258 | ~28.800 | **~13.300** | ~7.400 | 33 |
| **PE** | 221.264 | ~24.800 | **~11.800** | ~4.900 | 25 (+ Lima Metropolitana à parte?) |
| **PY** | 86.384 | ~9.300 | **~2.500** | ~1.000 | 18 (escopo recomendado: 3–5) |

Fontes: dossiê transversal e auditoria de dados (Kontur r8 → r7 reescalado ao total oficial). O dossiê transversal contava a população **do hexágono** ≥ 5.000; o funil corta pela **captação** (hex + 6 vizinhos), daí os acionáveis ~5× maiores. Os fatores Kontur → pacote (×0,517 e ×0,724) foram medidos **só na AR**, então a precisão é ±30 % (premissa F14). O número real sai do pacote.

### 4.2 Armazenamento e RAM: não são restrição

- **Disco.** Os 4 países somam ~115 MB de pacote hexagonal. A malha fina da superfície `ponto` fica em dezenas a centenas de MB por país; **só o México em nível de manzana chegaria a GB**, e a recomendação é AGEB. Tiles `.mbtiles`, se gerados, ocupam 3–6 GB por país. O pior caso fica abaixo de 40 GB nos 200 GB.
- **RAM.**
  - A AR tem RSS medido de 82 → 108 MiB.
  - O MX servido (~41 mil hex) é estimado em 150–300 MiB.
  - **Mesmo** com o universo territorial completo, a maior entidade mexicana (~48 mil hex) é do tamanho de RO (330 MB de pico).
  - `mem_limit` provisório: PY 1 GB, CO e PE 1,5 GB, MX 2 GB, revisto após 24 h de RSS em regime.

### 4.3 CPU é o gate (proposta DEC-073/D7)

`_PDF_CONCORRENCIA_MAX` é **por processo**. Hoje são BR 3 + AR 1; com +4 instâncias a 1 cada, seriam **8 jobs de PDF em 4 vCPU**. Somam-se as coletas semanais de concorrentes de cada país, cerca de 20 min com 4 workers no molde da AR, e, desde a DEC-074, o Valhalla na mesma VPS (`valhalla-infra/docker-compose.yml`: `cpus: 1.0` e `mem_limit` medido por env), que responde às isócronas do BR. Isso degrada o p95 do Brasil **sem erro, sem log e sem alerta**. Proposta, compatível com a DEC-047 (que proíbe multiplexar país **dentro** do processo, não limitar recurso **no host**):

1. `cpus:` por container nas instâncias novas (ex.: 1,0), o que protege o BR;
2. `pdf_concorrencia_max = 1` em todo país novo;
3. **calendário de coletas escalonado e declarado no registry**, com a data da última coleta no `/api/health` (dívida 0.10 da AR, ainda aberta);
4. **gatilho de segunda VPS escrito agora:** p95 do BR acima de 1,2× a baseline com as instâncias novas no ar, **ou** a 7ª instância. Hoje a baseline do piloto web **não existe** (`perf_baseline_piloto_web.md`) e tem de ser medida antes do 1º país novo.

### 4.4 Infra gerada, não copiada (proposta DEC-073/D7)

Hoje um país novo exige ~12–15 artefatos copiados à mão, metade em caminho CRÍTICO do guard:
- compose;
- template Caddy e Caddyfile;
- regra Authelia;
- portal com `$br/$ar` e matchers N²;
- healthcheck com `EDGE_URL` escalar;
- teste de compose literal.

A proposta é um **registry `deploy/paises.yml`**, com uma entrada por país (`sigla, host, grupo, mem_limit, cpus, pdf_max, janela_coleta, caminho_volume`). A partir dele:
- um gerador produz `docker-compose.<xx>.yml`, o bloco Caddy, o cartão do portal e a linha do healthcheck;
- **um teste de contrato** verifica que o gerado bate com o registry e que todo serviço que importa o pacote recebe o perfil (lição da DEC-049, o bot em crash loop).

O deploy continua **manual, por digest e comando a comando** (§6 do CLAUDE.md). O gerador produz arquivos para revisão; ele não deploya.

---

## 5. Moeda e câmbio

### 5.1 As três moedas, declaradas (o que a AR já ensinou)

| Papel | AR hoje | Proposta para os novos (DEC-073/D5) |
|---|---|---|
| Moeda do **país** (rótulo, ticket, aluguel) | ARS | moeda local (COP, MXN, PEN, PYG) |
| Moeda do **indicador de renda** (score, faixas, metas) | USD (câmbio BCRA de mai/2026) | **Moeda local constante num mês-base declarado**, e **não USD**. Motivo medido nos dossiês: em 12 meses o COP valorizou ~23 %, o PYG ~17 % e o MXN oscilou +8,9 % em 6 semanas. Uma âncora em USD faria o score "andar" com o câmbio, sem mudança real de renda. Câmbio do banco central do mês-base e fator PPC de consumo privado (Banco Mundial `PA.NUS.PRVT.PP`) viajam como **metadado** |
| Moeda da **viabilidade** (DRE, payback) | BRL, com tributo BR, como provisório carimbado | **Moeda local**, com premissas fiscais do país (§5.2). O BRL vira só uma coluna de leitura para o comitê, convertida pelo câmbio declarado no pacote e com a data visível |

**Regras:**
- **nunca converter em tempo de requisição**;
- a âncora é **recalibrada pela distribuição do país** (receita p05/p99 da AR), nunca convertida do BR;
- as âncoras de população ficam idênticas (1.000 / 100.000; corte 5.000; decisão 0.18).

### 5.2 Viabilidade: motor de premissas multi-regime (BLK-INTL-11; proposta DEC-073/D6)

Hoje o motor **não lê o perfil**. A estrutura de imposto é Lucro Presumido fixa em `Premissas.ir_csll` e há furos fora de `Premissas`:
- `aluguel_teto_clusters`;
- `flag_viavel`;
- payload;
- XLSX.

Trocar alíquota é parâmetro; trocar **regime** é código. Os 4 países exigem **regimes**, não alíquotas:

| País | Indireto sobre a mensalidade | Sobre o lucro | Folha / outros | Pegadinha |
|---|---|---|---|---|
| MX | IVA 16 % **por dentro** | ISR 30 % + **PTU 10 %** (≈ 37 % do lucro) | ISN estadual 2–4 %; jornada de 40 h até 2030 | **A COF (LFPPI art. 245) exige informar investimento e retorno ao franqueado 30 dias antes: o DRE vira número com responsabilidade legal** |
| CO | **IVA 19 % sobre a mensalidade** (verificado: Consejo de Estado, 2020) + ICA municipal + GMF 0,4 % | renda 35 % + tributação mínima de 15 % | salário mínimo +23 % em 2026 | ICA é **municipal**: alíquota por nível 2. Royalty ao BR: **20 % + IVA 19 % autorretido** (tratado aprovado, mas não promulgado) |
| PE | IGV 18 % por dentro (2026: 15,5 % + IPM 2,5 %), **com crédito** sobre capex e aluguel | IR 29,5 % (RMT 10 % no 1º tramo) | gratificações + CTS + EsSalud | aluguel cotado em **USD + IGV** (modelo bimonetário). Tratado com o BR em vigor (15 %) |
| PY | IVA 10 % por dentro | IRE 10 % + IDU 8 %/15 % | IPS 16,5 % | INR de 15 % sobre royalty remetido; **sem tratado** com o BR |

**Desenho proposto:** um `RegimeFiscal` **declarativo** (dados, não código por país), lido do pacote de premissas do país e composto de:
- imposto indireto "por dentro" com alíquota e flag de crédito;
- imposto de renda com alíquota e faixas;
- participação nos lucros sobre a base tributável;
- encargos sobre a folha;
- tributo municipal por nível 2 resolvido **na montagem** das `Premissas`, nunca dentro de `simular()` (guardrail do plano §3).

O golden de Londrina continua travando o BR. Cada país ganha seu próprio golden, com caso de referência assinado pelo time financeiro. **O carimbo "tributo provisório" deixa de ser aceitável no MX** por causa da COF: lá, a superfície `viabilidade` só liga com premissas MX assinadas.

---

## 6. API, piloto web, bot e controle de acesso com vários países

| Superfície | Proposta | Por quê |
|---|---|---|
| **Piloto web** | Uma instância por país, mesma imagem e mesmo digest. Superfícies por `perfil.superficies` | Já funciona (AR) |
| **Portal** | Cartões gerados do registry; "um favorito só" | Hoje são `$br/$ar` escritos à mão e matchers N² |
| **Identidade** | **Uma identidade, autorização por host** (proposta DEC-073/D8). O banco de usuários próprio (DEC-067/069) vira a fonte única. Os grupos `expansao_<pais>` passam a ser tabela de autorização usuário × país no mesmo banco, servida ao Caddy/`forward_auth` de cada host | Fim dos dois cadastros ("quem sai da empresa tem de sair dos dois"). **Não** é eixo de país no domínio: é autorização de acesso, como o grupo Authelia já é |
| **API GeoEspacial** | **Continua só BR** nesta onda (decisão registrada do plano §3). Se pedida para um país, é bloco próprio: `api/geo.py` lendo o perfil, uma instância por país, sem multiplexar | É o item mais caro do serving (`_carregar_mercado_full`, "~1,9 GB" de docstring nunca medido) |
| **Bot Telegram** | **Continua só BR.** O `_UFS` das 27 UFs fica fixo | Um token por país seria um bot por país; não foi pedido |
| **Trilha de acesso / Acessos** | Uma por instância (já é); o rollup do bot e o `/acessos` passam a ler a matriz do registry | Hoje leem só a trilha BR |

---

## 7. Estratégia de testes e regressão (BR e AR não podem quebrar)

1. **Golden BR inviolável:** `test_viabilidade_golden.py` (Londrina, tolerância de R$ 0,01) e um **novo snapshot de hash** das saídas do funil BR (camadas 1–5 para 3 UFs de referência: SP, PR, AM). O snapshot é gerado **antes** da refatoração e comparado a cada PR do núcleo. O molde já existe para a AR desde a DEC-077: `tests/unit/test_piloto_web_recomendacao_legado_ar.py` trava por sha256 `/api/municipio`, `/api/uf` e `/api/metodologia` da instância sem régua, e mudança deliberada no funil da AR (R3) tem de regerá-lo com `MOTOR_GERAR_GOLDEN_AR`.
2. **Matriz de perfis:** todo teste de contrato de perfil roda parametrizado sobre `data/perfis/*/perfil.json` (BR, AR e os novos à medida que entram). **Em subprocesso por país**, porque um país por processo vale também para a suíte (lição 14 da AR: o cache do perfil envenenava outros testes).
3. **Pacotes-fixture sintéticos por país** (centenas de linhas, gerados a partir do contrato) no CI. O validador semântico roda contra cada um, e o serving sobe com cada perfil e responde às rotas das superfícies ligadas (*smoke* HTTP, não chamada de função, lição do PR do 422).
4. **Testes negativos do validador:** um fixture por defeito real da AR:
   - `pop_total` falso amigo;
   - score percentil;
   - uplift 1,632;
   - renda em USD rotulada "$";
   - piso inalcançável;
   - meta na escala errada;
   - fonte NC.

   O validador tem de **recusar** cada um.
5. **Fio de alarme e anti-moeda ampliados:**
   - nenhum `if pais ==`;
   - nenhum `R$` literal fora da allowlist da viabilidade em `web/src/**`;
   - nenhum `str[:6]` em chave de município;
   - nenhum literal de âncora monetária fora do perfil.
6. **Compose e infra:** teste que gera os artefatos do registry e compara com os versionados, além do teste "todo serviço que importa o pacote recebe o perfil".
7. **Golden por país na viabilidade**, com caso de referência assinado pelo financeiro antes de ligar a superfície.
8. **Gate de desempenho:** baseline do piloto web versionada antes do 1º país novo. Cada país que entra mede p95 do BR com geração simultânea de PDF nas instâncias.

---

## 8. O que esta arquitetura deliberadamente NÃO faz

| Fora | Por quê |
|---|---|
| Instância única multi-país, seletor de país em runtime, export LATAM | DEC-047, decisão 0.1 |
| i18n / tradução para espanhol | D4 fechada pelo dono: português até ordem dele. **Risco anotado:** operadores locais nativos em espanhol podem pedir. Gatilho de reabertura = pedido do time local |
| Google Places como base persistida | Os termos proíbem armazenar e cachear (verificado). No máximo, verificação pontual manual |
| Relative Wealth Index (Meta) em superfície servida | CC BY-NC (verificado): uso comercial proibido |
| Contornar anti-bot de portais imobiliários | MX (LFDA art. 114 Bis) e CO (termos da Ciencuadras) tornam isso risco jurídico. A superfície `imobiliaria` só entra com parceria ou licença |
| Previsão de desempenho por praça | DEC-041 (funil = política declarada); a DEC-043 foi revogada pela DEC-078, cuja sugestão de faturamento depende de unidades Ultra para calibrar |

---

## 9. Propostas de DEC

> **Registro.** As dez propostas estão registradas como **uma DEC só, a [DEC-073](../decisions/DEC-073.md)**, com os itens **D1 a D10** abaixo. A forma foi escolhida para não reservar dez números para decisões ainda não tomadas (o repositório já teve 6 colisões) e para o índice do `CLAUDE.md` §8 crescer uma linha, não dez. Cada item é aprovado, emendado ou recusado **individualmente**, por emenda no arquivo da DEC-073. Um item aprovado que mude código segue a criticidade própria, declarada abaixo, no PR que o implementar. Nenhum está aprovado. Todos são READ-ONLY sobre o M1.

### D1 — Contrato de pacote de país v1, validador semântico e manifesto de fontes como gate de entrega
- Item: DEC-073/D1 | Data: 2026-10-16 | Criticidade: **Alta** (muda a fronteira de entrega de todo país; não toca score nem M1)
- Status: **PROPOSTA** — aguarda Felipe Silva
- Decisão: nenhum pacote de país entra no volume sem passar `scripts/validar_pacote_pais.py`, rodado pelo produtor, nos três níveis da §2.2 (presença, tipo/formato, **semântica**). Junto, o pacote traz um `manifesto.json` de fontes (licença, safra, hash, uso comercial). Fonte com uso comercial proibido em superfície servida **reprova**. O contrato vive em `docs/contrato_pacote_pais.md`.
- Por quê: os defeitos dominantes da AR foram semânticos (`pop_total`, percentil, uplift, moeda, piso, metas) e nenhum teste de presença/tipo os pegaria. O próprio plano escreveu "inaceitável rodar o segundo país sem ele", e o validador ainda não existe.
- Consequências: a AR é revalidada pelo contrato e deve **falhar** nos itens S1–S4/S8 até a correção. O custo por país cai na cauda (estimativa: de ~4 semanas para 1–2).
- Relação: implementa a consequência 1 da DEC-047 §1.1. Não revoga nada.

### D2 — Kit comum de pipeline (`motor_pais_kit`) para os repositórios de país
- Item: DEC-073/D2 | Data: 2026-10-16 | Criticidade: **Estratégica**
- Status: **PROPOSTA** — aguarda Felipe Silva e Juan (dono dos pipelines)
- Decisão: os cinco algoritmos repetidos (dasimetria → H3, raking, renda modelada por pesquisa domiciliar, dedup multi-fonte, calibração de capacidade por cobertura) viram uma biblioteca versionada. Os repos de país a consomem; **o serving não a importa**.
- Por quê: o pipeline da AR custou ~7 semanas de uma pessoa, e os 4 países repetem o método. Sem o kit, são 4 reimplementações divergentes (a AR já tem dois exportadores divergentes).
- Pergunta para o dono: o kit mora num repo próprio (recomendado) ou num subpacote deste repo fora do path-filter das imagens?
- Relação: complementa a DEC-047 §1.1. Não muda a fronteira serving × pipeline.

### D3 — Réguas do país completas no perfil e fail-closed dos fallbacks brasileiros
- Item: DEC-073/D3 | Data: 2026-10-16 | Criticidade: **Crítica** (toca `dashboard/constants.py`, `viabilidade_ponto.py`, `praca_indice.py`; muda o veredito da ficha e da zona morta na AR)
- Status: **PROPOSTA** — aguarda Felipe Silva
- Decisão: R1, R3, R4 e R5 da §3. As réguas de ficha, zona morta, camada 5, adensamento e cortes de consumo saem de literal para perfil, com o BR idêntico ao bit. Desde a DEC-075 e a DEC-077 a plataforma tem um segundo molde para régua de país, fora do `perfil.json` de propósito: arquivo versionado na imagem (`src/motor_expansao/renda/fatores/<PAIS>/`, `src/motor_expansao/recomendacao/regra/<PAIS>/`); escolher o molde faz parte desta decisão. Os campos mortos ganham leitor ou saem do schema. Fallback BR com perfil ≠ BR vira "indisponível com motivo".
- Por quê: são 5 defeitos ativos hoje na AR (00-baseline §3.1), e as mesmas peças morderiam os 4 países.
- Efeito esperado na AR: a ficha do ponto deixa de reprovar toda praça, a zona morta deixa de disparar por R$ 500 sobre USD e as metas SAM/residual saem da escala BR. **Medir antes de decidir os valores AR**, como no molde da DEC-042.
- Relação: preserva DEC-042 (BR = R$ 500, pop 5.000) e DEC-030 (selos). Emenda o perfil v1 da DEC-047.

### D4 — Chave de município integral e partição alfanumérica
- Item: DEC-073/D4 | Data: 2026-10-16 | Criticidade: **Crítica** (`_UF_RE` é sink anti-path-traversal, BLK-SEC-05)
- Status: **PROPOSTA** — aguarda Felipe Silva
- Decisão: R6 + R7. `_UF_RE` → `^[A-Za-z0-9]{2,6}$` com teste de traversal no mesmo commit. O join do crescimento casa a chave inteira declarada no perfil. O rótulo de nível 1 vem do perfil.
- Por quê: os códigos são DANE de 5 dígitos, INEGI de 5, INE-PY de 4 e UBIGEO de 6. Hoje a camada 4 fica vazia em silêncio em CO, MX e PY, e as siglas fabricadas colidem com UFs (`AM`, `SP`, `CE`, `AP`, `MG`).
- Alternativa recusada: continuar fabricando siglas no exportador. É barata hoje, mas propaga tabelas TS por sigla e colisões.
- Relação: executa o BLK-INTL-04 previsto no plano.

### D5 — Renda em moeda local constante; câmbio e PPC como metadado; viabilidade em moeda local
- Item: DEC-073/D5 | Data: 2026-10-16 | Criticidade: **Estratégica**
- Status: **PROPOSTA** — aguarda Felipe Silva (e time financeiro na parte de viabilidade)
- Decisão: §5.1. Para os países novos, `moeda.indicadores_renda` = moeda local num mês-base declarado (não USD). Câmbio do banco central e PPC viajam no manifesto. O DRE é calculado em moeda local, e o BRL vira leitura secundária com data. **A AR mantém USD** até decisão própria (a âncora USD está assinada na decisão 0.19).
- Por quê: volatilidade cambial medida (COP −23 %, PYG −17 % a/a; MXN +8,9 % em 6 semanas). Uma âncora em USD moveria o score sem mudança de renda.
- Relação: emenda, **só para os países novos**, a decisão 0.6/0.14 do plano (viabilidade em reais com tributo BR). Não toca BR nem AR.

### D6 — Motor de premissas fiscais multi-regime (BLK-INTL-11) e fim do "tributo provisório" onde houver responsabilidade legal
- Item: DEC-073/D6 | Data: 2026-10-16 | Criticidade: **Crítica** (`dimensionamento/config.py`, golden de viabilidade)
- Status: **PROPOSTA** — aguarda Felipe Silva + time financeiro + assessor fiscal por país
- Decisão: §5.2. `RegimeFiscal` declarativo (imposto por dentro com ou sem crédito, IR, participação nos lucros, folha, tributo municipal por nível 2 resolvido na montagem). Golden por país assinado. **No MX, a superfície `viabilidade` só liga com premissas MX assinadas**, porque a COF transforma o DRE em informação pré-contratual com responsabilidade.
- Por quê: os 4 países mudam o **regime** e não só a alíquota (IVA/IGV por dentro, PTU, crédito de IGV, ICA municipal, INR). O carimbo de provisório, aceitável na AR por decisão 0.14, não protege contra uso na COF.
- Relação: executa o BLK-INTL-11. Golden de Londrina intacto. DEC-068 intacta.

### D7 — Infra de país gerada de um registry, com limites de CPU por container e teto de PDF por host
- Item: DEC-073/D7 | Data: 2026-10-16 | Criticidade: **Crítica** (compose, Caddy, portal, healthcheck)
- Status: **PROPOSTA** — aguarda Felipe Silva / Vinicius
- Decisão: §4.3 e §4.4. `deploy/paises.yml` gera compose, Caddy, portal e healthcheck, com teste de contrato. `cpus:` por instância nova, `pdf_concorrencia_max = 1`, calendário de coletas escalonado e data da última coleta no `/api/health`. Gatilho de segunda VPS escrito: p95 BR > 1,2× a baseline, ou a 7ª instância.
- Por quê: são 12–15 artefatos copiados por país, metade CRÍTICOS, com N² linhas de matcher no portal, e o risco de host é CPU (8 jobs de PDF em 4 vCPU).
- Relação: generaliza o Bloco E/BLK-INTL-09. O deploy continua manual, por digest (§6, DEC-016).

### D8 — Identidade única com autorização por país
- Item: DEC-073/D8 | Data: 2026-10-16 | Criticidade: **Crítica** (portão de sessão; DEC-067)
- Status: **PROPOSTA** — aguarda Felipe Silva / Vinicius
- Decisão: §6. O banco de usuários próprio (DEC-067/069) vira fonte única de identidade. A autorização usuário × país é tabela no mesmo banco, servida ao portão de cada host. A AR sai do Authelia quando a migração for segura (com o Authelia como reserva, lição do #425).
- Por quê: hoje já são dois cadastros (o banco do BR e o `users_database.yml` do Authelia, que até o corte do P19 autentica BR e AR). Com 6 instâncias seriam 6.
- Relação: emenda a emenda de 25/09 da DEC-067 (AR presa ao Authelia). Não cria eixo de país no domínio: é autorização de acesso.

### D9 — Protocolo de liberação de país sem unidade Ultra (triagem, não previsão)
- Item: DEC-073/D9 | Data: 2026-10-16 | Criticidade: **Alta**
- Status: **PROPOSTA** — aguarda Felipe Silva
- Decisão: uma superfície de país só liga após **cinco gates pré-registrados**:
  1. validador semântico verde;
  2. sensibilidade de âncoras (top-30 compartilhado ≥ 25/30 entre âncoras candidatas, Spearman ≥ 0,95; molde da decisão 0.19);
  3. **teste de falso-veto com a Smart Fit**: fração das unidades dela em hexágono "frio" (score < corte ou pop < 5.000) abaixo de um teto declarado antes da medição;
  4. **backtest de ordenação** com aberturas da Smart Fit 2021–2025;
  5. **ranking cego** de 20–30 praças com o time local (Spearman como diagnóstico, não como nota).
- Ressalvas escritas: a amostra Smart Fit é condicionada no desfecho, então prova falso-veto e não acerto (DEC-042). Há circularidade (ela escolhe ponto com lógica parecida). Nada de R² de faturamento (DEC-041; a DEC-043 foi revogada pela DEC-078).
- Relação: confirmava a DEC-043, revogada pela DEC-078 em 21/10/2026; apoia-se na DEC-041 (o funil segue política declarada). Detalhe em `02-matriz-viabilidade.md` §5.

### D10 — Ordem de entrada dos países e escopo geográfico por país
- Item: DEC-073/D10 | Data: 2026-10-16 | Criticidade: **Estratégica** (decisão de produto do dono)
- Status: **PROPOSTA** — aguarda Felipe Silva / time de Expansão Internacional
- Decisão: a ordem e os escopos recomendados em `02-matriz-viabilidade.md` §4, incluindo o PY **só nas regiões metropolitanas**.
- Relação: decisão 0.15 do plano (os 5 países são programa real) intacta. Ordena, não corta.
