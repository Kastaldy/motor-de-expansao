# `perfil.json` — o país deixa de ser constante e passa a ser declarado

- Data: 2026-08-31 · Escopo: Bloco A da §5.0 / BLK-INTL-02 de `docs/plano_multipais.md`
- Arquivos: `data/perfis/AR/perfil.json` (Argentina, preenchida) e `data/perfis/BR/perfil.json` (Brasil, transcrito do código)
- Este documento explica **como o arquivo é usado**, **o que é obrigatório**, **o que acontece quando falta**, e **o que muda quando o Felipe decidir as âncoras**.

---

## 1. Para que serve

Hoje o Brasil está escrito no código em forma de literal: seis cópias de bounding box, um `countrycodes="br"`, `R$` espalhado em `.tsx`, `RENDA_ABS_MIN = 300.0`, `SCORE_CORTE_QUENTE = 30.0`, `POP_MIN_ACIONAVEL` declarado em três arquivos. Nenhum deles está errado — todos estão **escondidos**.

O `perfil.json` é a mudança de forma: **literal brasileiro → leitura de um objeto congelado**. Nada mais. Não entra rota, não entra chave de cache, não entra dimensão de país no domínio.

**A regra que sustenta tudo isto, e que precisa virar regra escrita:** nenhum `if pais == 'AR'` no repositório da plataforma. O país é **lido de um arquivo**, nunca é variável de decisão no código. No minuto em que virar `if`, existe um fork escondido dentro de um repo só.

## 2. Como o arquivo é usado

O perfil vive **dentro do `MOTOR_DATA_DIR`**, não no git da plataforma. Trocar o volume troca o país.

```
MOTOR_DATA_DIR/
├── perfil.json          ← este arquivo
├── outputs/
├── staging/
└── ibge/
```

Os arquivos em `data/perfis/AR/` e `data/perfis/BR/` são as **fontes versionadas**: o deploy copia o certo para a raiz do volume da instância. Versionar aqui e servir de lá é deliberado — o conteúdo é revisável em PR, e o volume continua sendo a única coisa que distingue uma instância da outra.

**Quando é lido:** uma vez, no import, ao lado de onde `MOTOR_DATA_DIR` já é resolvido (`web/server/app.py:99-108`). Congelado num objeto imutável. **Zero I/O em caminho quente** — o alvo de latência acrescida por requisição é 0 ms, e um dict congelado entrega isso por construção.

**Uma instância = um país = um processo.** É essa propriedade que mantém corretos os 35 `@functools.lru_cache` de `app.py` e os 5 de `api/service.py` sem uma linha de mudança: `carregar_uf("SC")` só é inequívoco porque existe uma SC por processo.

## 3. O que é obrigatório, e o que acontece quando falta

O boot é **fail-closed**. As três formas de falha são diferentes de propósito:

### 3.1 Perfil ausente ou JSON inválido → o container não sobe — **a regra tem duas pernas**

**Corrigido em 2026-08-31.** A redação anterior desta seção dizia "não há default embutido, não existe 'assume Brasil se não achar'". Isso está **errado como regra de implementação** e é o oposto do que a spec §3.2 e o plano (BLK-INTL-02) exigem. A regra correta, que é a única que se pode codar:

> **`MOTOR_DATA_DIR` SETADO ⇒ fail-closed absoluto.** É produção — é onde a instância argentina vive. Perfil ausente, JSON inválido, `schema_versao` divergente, campo obrigatório faltando, tipo errado, bbox degenerada ou `superficies` fora de `ABAS_VALIDAS` derrubam o processo **no import**, e a mensagem nomeia o campo e o caminho procurado.
>
> **`MOTOR_DATA_DIR` AUSENTE ⇒ carrega o `data/perfis/BR/perfil.json` versionado no repositório.** É dev e é teste, e continua fail-closed **sobre esse arquivo** (um BR embarcado quebrado derruba igual).

**A razão é material, não estética, e foi medida.** `grep -rn MOTOR_DATA_DIR tests/ conftest.py .github/` não devolve **uma linha**, e **15 módulos de teste** fazem `import app` no topo do arquivo, reapontando caminhos por monkeypatch só depois. Um fail-closed **incondicional** derruba os 15 na **COLETA** do pytest, com um traceback que não menciona nada do perfil — e a baseline que o critério de aceite nº 1 da spec §7 exige preservar é justamente essa: hoje `pytest --collect-only -q` coleta **3.857 testes com zero erros**. A alternativa (fixture de sessão em `conftest.py` apontando `MOTOR_DATA_DIR`) foi recusada com razão material: `conftest.py` é **CRITICO** no `scripts/loop_guard.py:145` e arrastaria `critica-aprovada` para dentro de um item de teste.

> **O que continua valendo do texto antigo.** O modo de falha que este arquivo existe para matar é o `_DEFAULT_DATA` de `web/server/app.py:99-101` — um caminho absoluto da máquina de um desenvolvedor. **Esse** morre, e é diferente do default de dev: o `_DEFAULT_DATA` apontava para **dados** de uma máquina que não existe no container e servia dado errado com HTTP 200; o perfil BR embarcado é **versionado, revisável em PR e travado por teste de contrato**, e em produção nunca é alcançado, porque em produção `MOTOR_DATA_DIR` está setado. Um default que só existe quando a env está ausente não pode subir uma instância com o país errado: se a env falta, não há volume de país nenhum para errar.

**Escrito também na DEC-046** (seção "Consequências para decisões anteriores"), para a próxima pessoa não "consertar" de volta para o fail-closed incondicional.

### 3.2 Campo obrigatório ausente ou nulo → o container não sobe

> **Reescrito em 2026-08-31, e é a lista que vale.** A versão anterior desta tabela declarava `rotulos.*`, `particao.*`, `subdivisoes` e `fontes.instituto` **obrigatórios para o boot** — campos que **nenhuma linha deste repositório lê**. Com isso havia **três** schemas em circulação (esta tabela, a spec §1.2 e os dois `perfil.json` entregues) e os dois JSONs eram formalmente inválidos contra o loader que o commit A1 manda escrever. **O schema canônico é o da spec `docs/spec_bloco_a_perfil.md` §1.2** — é o único em que cada campo tem a coluna "quem lê hoje" com `arquivo:linha`. Os dois `perfil.json` foram reescritos nele na mesma passada.

Obrigatórios em qualquer país, para qualquer superfície:

| Campo | Por que é obrigatório — **quem lê** |
|---|---|
| `schema_versao` (`int`, `== 1`) | ninguém lê o valor; existe para o loader **falhar alto** quando um pacote antigo encontrar um loader novo |
| `pais`, `nome`, `locale` | identidade e formatação. `nome` substitui o `"Brasil"` de `api/coord.py:75` e de `entrada-ponto.ts:116`; `locale` substitui o `'pt-BR'` de `format.ts:6` |
| `moeda.codigo`, `moeda.simbolo` | `simbolo` substitui os `R$` de `format.ts:38,39,41,52,53,54,105` e de `app.py:3626`. `codigo` entra **declarado sem leitor de produção**: é a chave que o Bloco C+ carimba no PDF/XLSX — se o C+ cair, o campo sai junto |
| `bbox` (4 números) | é a guarda de coordenada de quatro rotas; sem ela volta o corte em −34,0 que exclui Buenos Aires. Invariante validada: `lat_min < lat_max`, `lng_min < lng_max`, dentro de `[-90,90]`/`[-180,180]` |
| `vista_padrao.lat/lng/zoom` | `VISTA_BRASIL` de `mapa-ponto.ts:32`; sem ela o mapa abre em lugar nenhum |
| `geocode.countrycodes` | sem ele a busca de endereço casa homônimo brasileiro. **Duas** cópias: `app.py:3978` e `maps_geocoder.py:246` |
| `geocode.idioma` | o `"Accept-Language"` de `maps_geocoder.py:256` |
| `fontes.censo.{nome,detalhe}` | `F_CENSO` (`app.py:3550`) e o parágrafo de `:3572-3575`, no painel de metodologia — **rota livre**, que o gate do Bloco C não alcança |
| `fontes.crescimento.{nome,detalhe}` | `F_CRES` (`app.py:3553`) e o parágrafo de `:3599-3603` |
| `reguas.renda_abs_min/max`, `reguas.pop_abs_min/max` | **sem âncora não há score**; ver §4 |
| `reguas.score_corte_quente`, `reguas.pop_min_acionavel` | o piso do funil (`app.py:161`, lido por `_quente` em `:2085`) e o corte de população (duas cópias: `app.py:154` e `dashboard/constants.py:144`) |
| `reguas.oferta_destaque_min` | duas cópias: `app.py:153` e `dashboard/relatorio_municipal.py:61` — é esta segunda que faz do `relatorio_municipal.py` o **terceiro** arquivo CRITICO do Bloco A |
| `reguas.capacidade_concorrente` e `reguas.capacidade_unidade_alunos` | **são dois números diferentes** e o schema exige os dois: o primeiro é a capacidade de um CONCORRENTE (`app.py:152`), o segundo a de uma unidade ULTRA (`constants.py:379`, `faixas.ts:84`, `mapa-ponto.ts:49`). No Brasil os dois valem 2.500 e a duplicação passou despercebida; na Argentina valem 1.070 e 2.500 |
| `superficies` | não-vazio, e todo item dentro de `ABAS_VALIDAS` (`web/server/acesso.py:39`) |

**`geocode.regex_cp`** é opcional (`null` = país sem código postal); no Brasil ele carrega o `CEP_RE` de `maps_geocoder.py:32`.

**Campos RECUSADOS** — estavam preenchidos nos dois arquivos e **saíram do schema**, `_`-prefixados (§3.4) para nada se perder: `idioma` de topo (duplica `locale`), `rotulos.*` e `subdivisoes` (leitor seria o BLK-INTL-12 / BLK-INTL-04), `particao.*` (BLK-INTL-04), `geocode.sufixo` (zero leitores — nem `app.py:3977-3980` nem `maps_geocoder.py:241-248` concatenam sufixo), `metas_big_numbers` (só `ponto`/`municipal`, BLK-INTL-10) e `fontes.fator_temporal` (zero leitores). A regra que os expulsou é a §1.1 da spec: **um campo só entra se houver a linha que o lê** — campo sem leitor é número que envelhece calado, a classe de defeito da DEC-045.

### 3.3 Campo obrigatório **da superfície declarada** ausente → o container não sobe

Esta é a checagem que o validador precisa fazer **por superfície**, não em bloco. Um perfil pode ser válido para `["mapa"]` e inválido para `["mapa","ponto"]`.

> **Ajuste de 2026-08-31:** o loader do **Bloco A** não implementa esta tabela — ele valida o schema da §3.2 (que já exige incondicionalmente `score_corte_quente`, `pop_min_acionavel`, `oferta_destaque_min`, `capacidade_concorrente` e `capacidade_unidade_alunos`) e checa que `superficies` é subconjunto de `ABAS_VALIDAS`. A tabela abaixo é o contrato do **validador de pacote de país** (BLK-INTL-07) e do BLK-INTL-10, e é o que impede o modo de falha do §1 do plano quando `ponto` for liberada.

| Se `superficies` contém | Então também é obrigatório |
|---|---|
| `mapa` | `reguas.faixas_mapa_potencial`, `reguas.faixas_mapa_demanda` (as réguas de corte já são obrigatórias pelo schema) |
| `oportunidades` (funil) | tudo de `mapa` + `reguas.taxa_fitness`, e `reguas.oferta_destaque_min` **revisada para o país** (na AR ela entrou com o valor brasileiro — pendência P9) |
| `viabilidade` | pacote de premissas financeiras do país **ou** `avisos.viabilidade_tributo_provisorio` **ativo** |
| `ponto` (quando existir como superfície) | `_metas_big_numbers` promovido de volta a `metas_big_numbers`, completo — os 7 números |

**O caso da Argentina, explicitamente:** `metas_big_numbers` é `null` e `faixas_renda` é `null`, e mesmo assim o perfil é **válido**, porque `ponto` não está em `superficies`. Se alguém acrescentar `ponto` à lista sem preencher as metas, o boot deve falhar. É esse acoplamento que impede o modo de falha do §1 do plano: meta de R$ 1.500 contra renda em USD pinta todo card de verde e **não gera erro nenhum**.

### 3.4 O que NÃO derruba o boot

- `_nota`, `_procedencia`, `_medido`, `_metodo`, `_ver_tambem` e qualquer chave iniciada por `_` — são comentários. JSON não tem comentário; esta é a convenção que substitui. **É também onde moram os blocos RECUSADOS pela §3.2** (`_rotulos`, `_particao`, `_subdivisoes`, `_metas_big_numbers`, `_idioma`, `geocode._sufixo`, `fontes._fator_temporal`): o conteúdo continua no arquivo, revisável em PR, e o loader não o vê. Promover um deles de volta ao schema é apagar o `_` **e** acrescentar a linha que o lê — nessa ordem.
- **Campos extras que não estão no schema da §3.2** (`reguas.score_pesos`, `reguas.taxa_fitness`, `reguas.faixas_*`, `moeda.*` além de `codigo`/`simbolo`, `avisos`, `operacao`): o loader os **ignora** — ele valida presença e tipo do que a §3.2 exige e não reprova o que sobra. Eles têm leitor previsto em bloco posterior (B, C, C+) e ficam aqui declarados de propósito.
- `_pendencias` — é inventário, não configuração. O validador **lê** e imprime no log de boot ("subindo com 8 pendências declaradas: P1, P2, ..."), mas não bloqueia. Pendência declarada é dívida assumida; pendência silenciosa é surpresa.
- Campos opcionais nulos: `geocode.idioma`, `geocode.sufixo`, `geocode.regex_cp`, `moeda.comparacao`, `fontes.fator_temporal.artefato`.

## 4. As âncoras de renda e população — a decisão que ainda é do Felipe

É a única decisão do §9 ainda no caminho crítico da Argentina. Os arquivos sobem com um **default provisório declarado**, para não travar a implementação hoje.

### O que está lá, e de onde saiu

| Âncora | Brasil (hoje, no código) | Argentina (default provisório) |
|---|---|---|
| `renda_abs_min` | R$ 300 (p05 = R$ 296) | **US$ 350** (p05 = 342,4) |
| `renda_abs_max` | R$ 4.000 (satura 0,38%) | **US$ 1.000** (satura 0,29%) |
| `pop_abs_min` | 1.000 (p05 = 1.103) | **1.000** (p05 = 1.127) |
| `pop_abs_max` | 100.000 (satura 0,000%) | **100.000** (satura 0,136%) |

O método não foi inventado: é **literalmente o critério escrito** em `src/motor_expansao/pipelines/calibrar_renda_setor_2022.py:83-92` — piso no p05 arredondado, teto acima do p99 e abaixo do máximo, saturando menos de 0,4% — aplicado à distribuição argentina medida no parquet do Juan em 2026-08-31 (universo povoado, pop ≥ 1.000, 5.148 hexágonos).

**Sanidade verificada, não presumida:** com esses defaults, **5,5%** dos hexágonos argentinos ficam com score ≥ 30, contra **2,2%** dos brasileiros (medido nas 27 partições de `data/outputs/hexagonos_dashboard_enriquecido`, 1.303.414 hexágonos). Mesma ordem de grandeza. Para comparação, o score nativo do pacote argentino marcaria 12,2%.

### Duas coisas para não confundir

**(a) Isto não é conversão de moeda.** O teto brasileiro não vira o teto argentino dividido por 1.397,71. R$ 4.000 ÷ 1.397,71 = US$ 2,86 — número sem sentido. O que se transporta é o **critério** (qual percentil vira piso, qual saturação é aceitável), aplicado a uma distribuição diferente.

**(b) A âncora de população brasileira é de SETOR CENSITÁRIO; a argentina alimentaria com HEXÁGONO.** O cabeçalho do arquivo de calibração fala em "hexes", mas a coluna efetivamente usada é `pop_col = "pop_total_setor_2022"` (`:309`) — setor. Reusar 1.000/100.000 na Argentina só se sustenta porque as duas distribuições **coincidem por medição**:

| | p05 | p50 | p95 |
|---|---|---|---|
| BR, setor censitário povoado | 1.103 | 3.561 | 28.845 |
| AR, hexágono H3 res 7 povoado | 1.127 | 3.699 | 28.500 |

É coincidência empírica entre duas unidades diferentes, **não derivação**. Está escrito assim no `_nota_pop` do perfil AR de propósito: quem ler daqui a seis meses precisa saber que o número é reutilizado, não deduzido.

### A tensão que o Felipe precisa resolver (P1)

O critério brasileiro tem **duas leituras defensáveis** que discordam em ~1,6×:

- **Mesma saturação** → teto US$ 1.000. É o default, e é o critério que está escrito no comentário do código.
- **Mesma posição relativa do p95** → o Brasil pôs o teto em 2,12× o p95; na Argentina isso daria US$ 1.570, **acima do máximo observado** (1.141). Impossível.

A razão da incompatibilidade importa: a distribuição argentina é **comprimida porque a renda é modelada** (EPH), não medida. p95/p05 = 2,2 na AR contra 6,4 no BR. Consequência prática do default: o hexágono mediano tira nota 20 de renda e o p95 tira 60 — contra 43 no p95 brasileiro. **O default é mais generoso no topo.**

### O que muda quando ele decidir

**Muda o arquivo. Não muda uma linha de código.** Editar `reguas.renda_abs_*` e `reguas.pop_abs_*` e reiniciar a instância AR recalcula nota de renda, nota de população, score, ranking, cor de cada hexágono no mapa e quem passa no corte quente — para os 42.388 hexágonos.

Dois efeitos em cascata a revisar **depois**, nunca antes:

1. **`score_corte_quente` (P6).** Está em 30,0 provisório. O percentual que passa no corte se move junto com as âncoras; revisar depois de P1 e P2.
2. **Se P2 migrar para radio censal**, a coincidência da tabela acima deixa de valer — a distribuição de 66.502 radios não é a de 42.388 hexágonos. Recalcular antes de trocar.

## 5. O aviso carimbado — condição de aceite inegociável

`avisos.viabilidade_tributo_provisorio` está preenchido no perfil AR, ativo, com três textos e `onde: ["tela","pdf","xlsx"]`.

**Por que é campo de perfil e não constante de plataforma:** o Brasil não carrega esse aviso, porque o modelo financeiro brasileiro foi **calibrado** contra células rastreáveis de planilha oficial e 6 DREs gerenciais reais. A Argentina carrega porque não há unidade operando no país. É diferença de país, logo é dado de país.

**Por que precisa viajar no arquivo:** o PDF e o XLSX vão ao locador e ao comitê; a tela fica no escritório. Aviso que não viaja no arquivo não é aviso.

O mecanismo já existe e não precisa ser construído: `_nota(ws, row, texto, n_cols, *, alerta=True)` em `src/motor_expansao/dimensionamento/simulador_xlsx.py:424` (fundo amarelo, negrito), e os impostos já saem de `Premissas` via `_bloco_impostos` (`:584`) — não de literal espalhado. O trabalho é ligar o campo ao mecanismo, não inventar mecanismo.

Os três textos existem porque os três lugares têm formatos diferentes:

- `texto_curto` — cabe na linha única mesclada do `_nota()` do XLSX;
- `texto_longo` — caixa do PDF e da tela;
- `texto_rodape` — rodapé de cada página de simulação.

Foram escritos para **locador e comitê**, sem jargão interno. A frase que faz o trabalho é a que diz o que a pessoa **não pode fazer** com o número: fechar contrato, definir aluguel, precificar mensalidade, aprovar aporte.

**Teste de contrato:** deve falhar se o PDF ou o XLSX da instância AR sair sem o aviso. Enquanto o pacote de premissas argentino (BLK-INTL-11) não existir, `ativo: true` e `obrigatorio: true` não se mexem.

## 6. Por que existe um perfil do Brasil

O `BR/perfil.json` não é um perfil novo. É a **transcrição** dos valores que hoje são literais no código, cada um com `arquivo:linha`.

Ele existe para uma coisa só: **provar que declarar o país não muda o comportamento brasileiro.** O teste do Bloco A compara cada campo com o literal citado. Se divergir, o teste falha — e o errado é o perfil, não o código.

Três consequências de disciplina, visíveis no arquivo:

- **`fontes.fator_temporal.valor` é `null`.** O fator é resolvido em runtime (`constants.py:457-473`, lê artefato, aceita 1,0–2,0, cai em 1,0 com rótulo "julho/2022"). Congelar um número aqui **quebraria** o comportamento atual. O perfil declara caminho e fallback, não valor.
- **`reguas.taxa_fitness` é 0,10, que é o *fallback*** — o valor real é calibrado em runtime. O perfil declara o único literal que existe.
- **`geocode` tem quatro `null` e `validar_contra_bbox: false`.** É a descrição honesta de `web/server/app.py:3953-4005` (o `countrycodes: "br"` está na `:3978`), que hoje devolve o top-1 cru do Nominatim sem validar nada. Ligar a validação no Brasil é mudança de comportamento e precisa de teste próprio; não entra de carona no perfil.

O `bbox` do Brasil é o único campo em que a transcrição não foi possível — há **seis cópias divergentes**, em **três** caixas distintas (listadas em `bbox._copias_hoje`).

**BR-P1 está FECHADA desde 2026-08-31, em B1** (`lat [-34,0 · 5,5]` · `lng [-74,0 · -28,0]`), que é o que a spec §1.3 já decidia. O default anterior deste arquivo era a **união** (`lat_max 6,0` / `lng_min -75,0` = a caixa B3 de `competitors.py`), e a justificativa dela — "unificar numa caixa mais estreita passaria a rejeitar coordenada hoje aceita" — foi **medida e não se sustenta**:

- O único sítio que a união preservava é o filtro de pins de `dashboard/competitors.py`. O comando de verificação obrigatório da spec §7.5, rodado sobre `data/staging/concorrentes_mapeados.parquet` (**3.296 linhas**): **B3 = 3.269, B1 = 3.269, delta 0**. Estreitar de B3 para B1 não descarta um pin sequer.
- As três cópias que validam **entrada do operador** (`api/coord.py:13-14`, `coord.ts:8`, `entrada-ponto.ts:44`) **já são B1** — B1 não estreita nada do que as rotas de coordenada aceitam hoje.
- A união **quebrava um teste que a spec afirma ficar verde**: com `lat_max = 6,0`, `assert parse_coordinate_input("6.0,-60.0") is None` (`tests/unit/test_coord_search.py:58`) falha, porque `6,0 <= 6,0`. A spec §5.2 diz literalmente que essa linha "continua verde" e só lista a correção da `:60`. Sob B1 quem quebra é a `:60`, exatamente como a spec previu e já corrige no commit A4.

As duas mudanças de comportamento resultantes são as declaradas na spec §1.3, e ambas têm teste: `dashboard/data.py` **alarga** de B2 para B1, e `competitors.py` **estreita** de B3 para B1.

## 7. O que este arquivo NÃO carrega

O perfil declara **réguas e identidade**. Ele **não** traduz **schema**. O de-para de colunas (`oferta_consumida_mercado`, `n_academias`, `renda_estimada_usd`, e a derivação de `hex_id`, `lat`, `lng`, `cidade`, `cod_municipio` que o parquet AR não tem) é o adaptador do Bloco B / BLK-INTL-02 item 10a, e depende de `exportar_piloto_rep.py` vir do repositório do Juan para a plataforma — hoje ele não está neste repo **nem** no pacote entregue.

Manter as duas coisas separadas é deliberado. São blocos diferentes, com donos e prazos diferentes, e confundi-los foi o erro de sequência que a revisão de 2026-08-31 pegou.

## 8. Inventário de pendências

Cada pendência tem `campo`, `estado`, `decide`, `pergunta`, `default`, `justificativa` e `o_que_muda_quando_decidir`. Dois estados:

- **`default_provisorio`** — há um valor usável no arquivo; a instância sobe; a decisão refina.
- **`ausente`** — o valor é `null`; a instância sobe **só porque a superfície que precisaria dele está bloqueada**. Liberar a superfície sem preencher deve falhar o boot (§3.3).

### Argentina — 9 pendências

| # | Campo | Estado | Decide | Trava o dia 1? |
|---|---|---|---|---|
| P1 | `reguas.renda_abs_min/max` | default provisório (350 / 1.000 USD) | **Felipe** | não |
| P2 | `reguas.pop_abs_min/max` | default provisório (1.000 / 100.000) | **Felipe** | não |
| P3 | `reguas.score_pesos` / qual score o mapa pinta | **ausente** | Felipe com o Juan | **decide o esforço do Bloco B** |
| P4 | `moeda.indicadores_renda` (USD ou ARS na tela) | default provisório (USD) | Felipe (produto) | não |
| P5 | `reguas.metas_big_numbers` | **ausente** | Felipe + Expansão Internacional | não — `ponto` está bloqueada |
| P6 | `reguas.score_corte_quente` | default provisório (30,0) | Felipe | não — revisar **depois** de P1/P2 |
| P7 | malha adm2 (`municipios_<COD>.geojson`) | **ausente** | Juan produz / Felipe aceita | não — bloqueia BLK-INTL-10 |
| P8 | `operacao.mem_limit_alvo` | default provisório (2g) | **medição do Bloco E**, não pessoa | não |
| P9 | `fontes.crescimento.*` e `reguas.oferta_destaque_min` | default provisório | **dev (Bloco A/B)** — não é decisão do Felipe | não — `oportunidades` está fora de `superficies` |

**P9 nasceu em 2026-08-31, junto com a unificação de schema.** São os dois campos que a spec §1.2 declara obrigatórios e para os quais o pacote do Juan não tem fonte argentina: o loader do commit A1 reprovaria o perfil sem eles. `fontes.crescimento` descreve a **ausência** de um equivalente ao CAGED/RAIS mensal em vez de traduzir a frase brasileira (que afirmaria CAGED e RAIS na Argentina); `oferta_destaque_min` entrou com o valor brasileiro (2.000) porque a régua é uma fração da capacidade de uma unidade **Ultra** — que é a mesma nos dois países (2.500) — e não da capacidade de um concorrente local (1.070 na AR). **Não toca a agenda do Felipe.**

**P3 merece destaque, porque é a única sem default seguro.** O motor brasileiro calcula `0,60·renda + 0,40·pop`. O parquet argentino já traz um `hex_score_estrutural` com os pesos **invertidos**: `100 × (0,40·renda_pct + 0,60·pop_pct)`. Se a plataforma recomputar o score nas âncoras AR, o valor vai divergir da coluna `score_priorizacao` que veio no pacote, e as duas vão existir lado a lado. Escolher em silêncio produz um mapa que discorda do parquet entregue — e ninguém descobre por erro; descobre por reunião.

### Brasil — 3 pendências

| # | Campo | Estado | Decide |
|---|---|---|---|
| BR-P1 | `bbox` (qual das três cópias vira a única) | **FECHADA em 2026-08-31: B1** (`lat_max 5,5` / `lng_min −74,0`) — ver §6 | Bloco A |
| BR-P2 | `geocode.validar_contra_bbox` | default provisório (`false` = hoje) | Bloco A |
| BR-P3 | `vista_padrao` (unificar os fallbacks de Brasília?) | default provisório | Bloco A |

## 9. Riscos herdados que o perfil declara mas não conserta

Estão escritos nos `_nota` para não virarem surpresa:

- **Renda argentina tem erro estrutural de ±15%** (mediana urbana; ±24% no P90), e **85% dos hexágonos têm `renda_confianca = "baixa"`** (rural, renda extrapolada da média urbana). O gate de população tira quase todos das teses — mas **a leitura do mapa não tem esse gate**.
- **A concorrência argentina enxerga ~37% do universo real** de academias. O fator de cobertura 2,675 corrige o **agregado**, não o hexágono individual.
- **`taxa_fitness_osm_calibrada = 0,358`** no parquet AR diverge **4,6×** do benchmark de 0,078 e é gravada sem alertar. **Não usar essa coluna** — o perfil declara `taxa_fitness: 0.078`.
- **`mem_limit: 2g` da AR é palpite de disco, não RSS medido.** `carregar_uf_completo` (`web/server/app.py:786-789`) faz `read_parquet` sem projeção de colunas, e o parquet AR carrega `geometry_wkb` por linha — coluna que o enriquecido brasileiro não tem. Medir no Bloco E **antes** de fixar.
- **O mapa argentino sobe sem nome de rua** (decisão 0.9, aceita por escrito). `_labels_tiles_url` (`censo_map.py:729-738`) devolve `None` sem `API_BASEMAP_LABELS_URL` e **não há fallback embutido** — a falha é silenciosa. `avisos.mapa_sem_toponimo` existe para o silêncio virar frase.
