# 04 — Roadmap de implementação (CO, MX, PE, PY)

- **Data:** 2026-10-16 · **Status:** PLANO. Nenhuma fase começa sem a aprovação das DECs que ela pressupõe (`03-arquitetura.md` §9). Cada fase é **testável** e tem critério de aceite próprio.
- **Ordem recomendada:** **MX → CO → PE → PY** (justificativa em `02-matriz-viabilidade.md` §4). A ordem é a proposta DEC-073/D10; trocar a ordem não muda as fases de plataforma.

---

## 0. Como as estimativas foram feitas (e onde elas erram)

Baseline medido na Argentina (`00-baseline-argentina.md` §5):

| Componente | AR real | Como escala aqui |
|---|---|---|
| Plataforma (Blocos A–E) | Plano de **5 semanas/2 devs**; execução em **~1,5 dia**, com IA sobre spec de 913 linhas + ~3 dias de spec antes | **Não** se repete a velocidade sem spec executável. Estimo **calendário** = spec + execução + revisão + gate do dono + deploy |
| Pipeline do país | **~7 semanas**, 1 pessoa + IA | × fator do país (§0.1). Com o kit (DEC-073/D2), −25 a −35 % a partir do 2º país (*estimativa*) |
| Cauda de correções | **~4 semanas**, 11 PRs, não orçada | Orçada aqui: 2–4 semanas por país. Cai para 1–2 com o validador semântico (*estimativa*) |
| Gate humano | Decisões do dono em ~3 dias | **O gargalo real.** Toda fase tem DEC ou decisão de régua como dependência |

### 0.1 Fator de pipeline por país (contra a AR = 1,0)

| País | Fator | Por quê |
|---|---|---|
| MX | **1,2–1,4** | Melhor dado: AGEB/manzana, DENUE georreferenciado, renda medida no município, agregadores presentes. **Mas** a escala é ~2,7× a AR em hexes servidos, há 32 entidades, crosswalk IMSS→INEGI, AGEB alfanumérica, supressão `*` e gramática decimal invertida |
| CO | **0,9–1,1** | Manzana + estrato observados, mas o censo é de 2018 (reescala não uniforme), sem agregador (coleta = Smart Fit + OSM + Overture) e hosts do governo bloqueados fora do país |
| PE | **1,1–1,3** | O censo 2025 só existe até distrito. Base de manzana 2017 via REDATAM, **geometria de manzana sem download oficial** (pedido ao INEI). Sem agregador. Gramática decimal |
| PY | **0,5–0,7** | Escopo de 3–5 partições e ~2,5 mil hex. A renda intraurbana é o problema (sem covariável abaixo do distrito; RWI proibido para uso comercial) |

> Faixas são **estimativa**, não medida. O primeiro país novo recalibra o fator dos demais (gate de reestimativa no fim da Fase 2).

---

## 1. Visão geral

Cenário recomendado: **duas pessoas de dados** (A e B) + IA. Semanas de calendário.

```
Semana →           1-2   3-5   6-8   9-11  12-14  15-17  18-20  21-23  24-26  27-28
Plataforma
  F0 Correções AR  █
  F1 Núcleo        ░███  ███
  F1b Infra/ID           ███   ███
  F1c Kit pipeline ░███  ███
  F1d Viab. multi-regime ███   ███   ███   ███    (+ fiscal por país, humano, em paralelo)
Pessoa A
  F2 MX MVP              ███   ███   ███   ██▲               ▲ = MVP no ar (~sem. 14-15)
  F3 MX completo                                  ███   ███
  F5 PE MVP                                       ███   ███   ███   ██▲      (~sem. 24-25)
Pessoa B
  F4 CO MVP                    ███   ███   ███   █▲                          (~sem. 15-16)
  F6 PY MVP (sob demanda)                               ███   ██▲            (~sem. 22-23)
  F7 CO/PY completos                                                ███   ███
```

- **Com duas pessoas de dados:** os 4 MVPs ficam no ar em **~25 semanas (~6 meses)**; os completos em **~28 semanas**.
- **Com uma pessoa** (o Juan sozinho, cenário de hoje), os países serializam:
  - MX na sem. ~15;
  - CO na ~24;
  - PE na ~34;
  - PY na ~39.

  São **~9–10 meses**.
- **Caminho crítico:** F0 → F1 (contrato + validador) → MVP de cada país. A ingestão bruta do MX (censo, DENUE, ENIGH) começa **em paralelo** com a F1, porque não depende do contrato; só a emissão do pacote final depende dele. Viabilidade e completos ficam fora do caminho crítico do MVP.
- Com duas pessoas, **a Colômbia pode ficar pronta junto ou antes do México**, porque é menor. A "ordem" vale como prioridade da pessoa A e do primeiro deploy, não como fila obrigatória.

---

## 2. Fases

### F0 — Correções da Argentina (pré-requisito de tudo)

| Item | Conteúdo |
|---|---|
| Entregáveis | R1 (renda mínima da ficha e zona morta no perfil); R2 (front lê faixas e moeda do perfil; guarda anti-moeda estendida); metas SAM/residual AR na escala certa (S8); higiene do perfil e do backlog (P5/P7 marcados `ausente`; BLK-INTL-A1…C2 como "Pendente"; nenhum BLK-INTL em `completed.md`); decidir **qual exportador AR é o canônico** (há dois divergentes) |
| Aceite | Ficha do ponto AR **não** reprova toda praça; taxa de `flag_zona_morta` na base AR **medida** e explicada; mapa de setores AR pinta pelas faixas do perfil; nenhuma renda USD rotulada "R$"; BR idêntico ao bit (golden de Londrina + snapshot de hash do funil) |
| Testes | Matriz BR+AR dos novos campos; snapshot BR; teste de tela AR (rótulo de moeda) |
| Estimativa | **1–1,5 semana** de calendário (3–5 dias de execução + medição + gate) |
| Dependências | DEC-073/D3 (parte R1) aprovada; medição da zona morta AR **antes** de escolher o valor |
| Riscos | Mudar o veredito AR que o time já viu. Mitigação: comunicar antes, porque é correção e não mudança de régua |

### F1 — Núcleo multi-país (refatoração; um país por vez depois dela)

| Item | Conteúdo |
|---|---|
| Entregáveis | (a) `docs/contrato_pacote_pais.md` v1 + `scripts/validar_pacote_pais.py` nos 3 níveis + `manifesto.json` (DEC-073/D1). (b) Exportador **genérico** com `depara.json` por país; a AR é **reempacotada** por ele (teste de aceite). (c) R3–R11 (réguas completas, campos mortos, fail-closed, chave integral, partição alfanumérica, `mascara.ts` por locale, camadas de leitura e textos de fonte declarados). (d) Testes em matriz de perfis em subprocesso, fixtures sintéticos por país e testes negativos com os 7 defeitos reais da AR. (e) Baseline de desempenho do piloto web versionada |
| Aceite | AR reempacotada pelo exportador genérico passa o validador e produz o **mesmo** serving que hoje (salvo as correções da F0); o validador **recusa** cada um dos 7 fixtures negativos; BR idêntico ao bit; fio de alarme verde e ampliado; `_UF_RE` novo com teste de traversal verde |
| Testes | Ver `03-arquitetura.md` §7, itens 1–6 |
| Estimativa | **3–4 semanas** de calendário: ~1 semana de spec executável (molde da `docs/archive/spec_bloco_a_perfil.md`), 1–2 de execução com IA, ~1 de revisão e gates Críticos (R3, R5, R7) |
| Dependências | F0; DEC-073/D1, DEC-073/D3, DEC-073/D4 aprovadas |
| Riscos | R7 mexe num sink de segurança, então tem revisão adversarial obrigatória. O exportador genérico pode não cobrir a AR inteira (14 colunas extras da cópia do Juan); a mitigação é tratá-las como `camadas_leitura` declaradas |

### F1b — Infra gerada + identidade única (paralela à F1)

| Item | Conteúdo |
|---|---|
| Entregáveis | `deploy/paises.yml` + gerador de compose, Caddy, cartão do portal e healthcheck, com teste de contrato. `cpus:` por instância, `pdf_concorrencia_max` = 1 nos novos, calendário de coletas declarado e data da última coleta no `/api/health` (DEC-073/D7). Identidade única com autorização por país; AR migrada do Authelia com reserva (DEC-073/D8) |
| Aceite | Os artefatos gerados para BR e AR são **idênticos** aos versionados hoje (diff vazio); um país fictício "ZZ" gera um stack completo que passa os testes; login BR e AR pela mesma identidade, com o Authelia como reserva testada (lição do #425) |
| Estimativa | **3–4 semanas** (Crítica: aprovação por item, deploy manual comando a comando) |
| Dependências | DEC-073/D7, DEC-073/D8 |
| Riscos | Indisponibilidade de login (já ocorreu no #425). Mitigação: corte em duas etapas, como o portal (decisão 0.12b) |

### F1c — Kit comum de pipeline (paralela à F1, outro repositório)

| Item | Conteúdo |
|---|---|
| Entregáveis | `motor_pais_kit`: dasimetria → H3 res 7 (com raking a totais oficiais), modelo de renda por pesquisa domiciliar (interface comum; EPH, ENIGH, GEIH, ENAHO e EPHC como adaptadores), dedup multi-fonte de concorrentes, calibração de capacidade por cobertura, emissão do pacote + manifesto no contrato v1 |
| Aceite | **Reproduz o pacote AR** a partir das entradas do Juan com tolerância declarada (população por hex, renda por hex, concorrentes); passa o validador da F1 |
| Estimativa | **3–4 semanas** (Juan + IA; extração do pipeline AR existente, não escrita do zero) |
| Dependências | DEC-073/D2; contrato v1 da F1 (o kit emite nele) |
| Riscos | Acoplar demais o kit à AR. Mitigação: o 1º adaptador novo (MX) entra no aceite da F2 |

### F1d — Viabilidade multi-regime (trilha paralela longa)

| Item | Conteúdo |
|---|---|
| Entregáveis | `RegimeFiscal` declarativo; os furos fora de `Premissas` fechados (`aluguel_teto_clusters`, `flag_viavel`, payload, XLSX); DRE em moeda local; BRL como leitura; golden por país assinado pelo financeiro; pacote de premissas MX primeiro (por causa da COF) |
| Aceite | Golden de Londrina idêntico; golden MX assinado; nenhum literal BR alcançável com perfil ≠ BR |
| Estimativa | **Engenharia: 3–5 semanas, uma vez. Por país: 3–6 semanas humanas** (assessor fiscal + financeiro), em paralelo aos pipelines |
| Dependências | DEC-073/D5, DEC-073/D6; contratação de assessoria fiscal por país (decisão do dono) |
| Riscos | É o único item com potencial de estourar o escopo (plano §3). Mitigação: tributo sub-nacional resolvido **na montagem** das `Premissas`, nunca em `simular()` |

### F2 — México MVP

| Item | Conteúdo |
|---|---|
| Escopo MVP | Superfície **`mapa`** com camadas 1–3 e ficha do hex; Relatório Pontual por **AGEB urbana**; funil municipal (vem junto com `mapa`, lição da AR). **Sem `viabilidade`** até a F1d MX (COF) |
| Entregáveis | Pacote MX: CPV 2020 AGEB/manzana + ITER rural, reescalado pela EIC 2025 no município. Renda modelada (CPV ampliado `INGTRMEN` + ENIGH 2024 por município; ordem intra-municipal por covariáveis da AGEB; validação contra NSE AMAI e IMU). Concorrência: DENUE 713943 + sites de rede + WellHub/TotalPass, com capacidade **por estrato de pessoal ocupado**. `taxa_fitness` declarada com faixa e fonte; perfil MX; malha municipal; DNS `piloto-mx.` |
| Aceite | Os 5 gates da DEC-073/D9 (validador; sensibilidade de âncoras; **falso-veto Smart Fit** — 488 unidades; backtest de ordenação; ranking cego com o time local em 2 cidades); RSS e p95 do BR medidos com MX no ar; decisões de régua MX assinadas (âncoras de renda em MXN constante, corte, capacidade, taxa) |
| Estimativa | **Pipeline 8–10 semanas** (fator 1,2–1,4 com o kit ainda novo) + **1 semana** de subida + **2–3 de cauda** |
| Dependências | F1 (contrato, R7, R8), F1b (infra), F1c (kit, ao menos dasimetria e renda) |
| Riscos | Penetração sem fonte primária (3–6 %) define a escala do residual. O DENUE superestima micro-academias fechadas. A volatilidade do MXN não afeta o score se a DEC-073/D5 for aprovada |

### F3 — México completo
- **Entregáveis:**
  - camada 4: IMSS asegurados com crosswalk IMSS→INEGI, saldo de estabelecimentos DENUE entre versões e população 2020→2025;
  - `viabilidade` com premissas MX assinadas;
  - M&A/vulnerabilidade com os agregadores MX (reaproveita a cadeia BR);
  - coleta semanal na VPS em janela própria.
- **Fica fora:** `imobiliaria`. Só entra com parceria (portais 403/401; LFDA).
- **Estimativa e aceite:**
  - **4–6 semanas**;
  - aceite = golden MX assinado e camada 4 com chave integral.

### F4 — Colômbia MVP

| Item | Conteúdo |
|---|---|
| Escopo MVP | `mapa` com camadas 1–3 + Relatório Pontual por **manzana** (geometria de melhor resolução entre os 4) |
| Entregáveis | MGN 2018 + CNPV por manzana, reescalado às projeções municipais de 2026 (fator não uniforme, redistribuído com ELIC/CEED ou grade WorldPop). Renda modelada pela GEIH/Pobreza Monetária por domínio × **estrato**, aplicada à distribuição de estratos da manzana. Concorrência: sitemap Smart Fit (245 sedes) + **agregadores locais Fitpass CO (400+) e Fitpal (600+, 23 cidades)**, no lugar do WellHub argentino e **sujeitos à leitura de termos e robots**, + sites de rede + OSM + Overture (~4,7 mil `gym`). **O pipeline roda de rede com acesso aos hosts do DANE** (3 hosts recusaram conexão daqui) |
| Aceite | 5 gates da DEC-073/D9 (falso-veto com as 232 Smart Fit); carimbo do ano real do censo (2018) visível na tela e no PDF |
| Estimativa | **Pipeline 5–7 semanas** (com kit) + 1 de subida + 2–3 de cauda |
| Dependências | F1, F1b, F1c; estabilização da F2 (o kit já usado uma vez) |
| Riscos | Se os termos de Fitpass/Fitpal vetarem a coleta, os independentes ficam quase invisíveis ("não mapeado vira livre"). O CENU 2024 **não** resolve: não foi publicado e o acesso previsto é só para pesquisa. IVA de 19 % sobre a mensalidade **confirmado** (afeta só a viabilidade). País mais saturado de Smart Fit (4,3 por milhão) |

### F5 — Peru MVP

| Item | Conteúdo |
|---|---|
| Escopo MVP | `mapa` com camadas 1–3; malha nacional, com foco em Lima+Callao, Arequipa, Trujillo, Chiclayo e Piura |
| Entregáveis | Manzana 2017 (REDATAM) agregada ao hex e **reescalada ao total distrital do Censo 2025**; geometria de manzana obtida por pedido formal ao INEI (Lei 27806) ou SIGRID/CENEPRED. Renda modelada pela ENAHO 2025, com covariáveis do **REDATAM distrital do Censo 2025** (que existe, ao contrário do que dizia o dossiê) e **validada contra os Planos Estratificados por manzana** (245 distritos), o único país com régua externa de renda por manzana. Concorrência por OSM + sites + Overture (~3,4 mil `gym`), sem agregador. UBIGEO como string de 6 |
| Aceite | 5 gates da DEC-073/D9; acerto do estrato previsto contra os Planos Estratificados reportado |
| Estimativa | **Pipeline 6–8 semanas** + 1 + 2–3 |
| Dependências | F1, F1c; **resposta do INEI sobre a geometria** (risco de prazo externo, iniciar o pedido já na F1) |
| Riscos | Se o INEI publicar a manzana do Censo 2025 durante a fase, trocar a base (ganho) ou seguir com 2017 (prazo). Inflação acima da meta (4,55 %): mês-base declarado |

### F6 — Paraguai MVP (escopo reduzido)

| Item | Conteúdo |
|---|---|
| Escopo MVP | **Só regiões metropolitanas**: Gran Asunción (Asunción + Central), CDE metropolitana e Encarnación (+ PJC opcional), com 3–5 partições e ~2,5 mil hex |
| Entregáveis | População: grade WorldPop raked aos totais distritais da projeção Rev. 2025 (e aos 68 barrios em Asunción). Renda: nível por distrito do **Mapa de Pobreza Monetária INE + Banco Mundial** (SAE) + EPHC; ordem intradistrital por **altura e área construída** (Google Open Buildings 2.5D, CC BY, e GHSL BUILT-C/H), **validada nos 67 barrios de Asunción** antes de ir para Central/CDE. **Não** o RWI, que é CC BY-NC. Pedido formal ao INE do NSE por segmento. Concorrência: Smart Fit (19, coordenadas no site) + redes locais + OSM + Overture |
| Aceite | 5 gates da DEC-073/D9, com ressalva escrita: a Smart Fit tem só 19 pontos, então o falso-veto tem poder estatístico baixo, e o ranking cego com o time local pesa mais |
| Estimativa | **Pipeline 3–5 semanas** + 1 + 1–2 |
| Riscos | Teto de mercado de ~3–8 unidades Ultra em 3–5 anos (*estimativa*). O motor pode custar mais que a decisão que ele informa. Lei 194/93 (rescisão de franquia) exige parecer, mas não bloqueia o motor |

### F7 — CO, PE e PY completos
- **Camada 4:**
  - CO: ELIC/CEED + RUES agregado (sem PII);
  - PE: intercensal 2017–2025 + RENAMU + diferença de RUC;
  - PY: só demografia.
- **Demais entregáveis:**
  - viabilidade com premissas locais, quando a F1d entregar cada país;
  - coleta semanal em janela própria.
- **Fica fora:** `imobiliaria` só com parceria.
  - CO: Ciencuadras proíbe scraping; Finca Raíz bloqueia.
  - PE: os portais estão atrás de Cloudflare.
  - PY: o InfoCasas é viável **se** os termos permitirem (não lidos).
- **Estimativa:** 3–5 semanas por país, em paralelo.

---

## 3. MVP × versão completa, por país

| | MVP (já gera ranking útil) | Completo |
|---|---|---|
| Superfícies | `mapa` (camadas 1–3, ficha do hex, funil municipal) + Relatório Pontual onde houver unidade censitária com geometria (MX AGEB, CO manzana; PE e PY depois) | + `oportunidades` (Modo 3) com réguas da camada 5 do país; + `viabilidade` com premissas locais assinadas; + camada 4; + M&A (só MX) |
| Dados mínimos | identidade + camada 1 (pop medida/reescalada + renda modelada) + camada 2 (taxa e capacidade **declaradas com faixa e fonte**, carimbo "não calibrado") + camada 3 (redes + OSM/Overture/DENUE) | + momentum, coleta recorrente na VPS, aluguel/imobiliário com parceria |
| Gate | DEC-073/D9 (5 gates) | + golden fiscal do país assinado |
| O que o MVP **não** promete | previsão de desempenho (o funil é política declarada, DEC-041); viabilidade; ranking entre países | — |

---

## 4. Execução paralela com worktrees e agentes

### 4.1 O que roda em paralelo

| Trilha | Onde | Paralelismo | Agentes |
|---|---|---|---|
| **A — Plataforma** (F0, F1, F1b) | este repo, **uma worktree por bloco** (`ciclo/BLK-INTL-*`) | Blocos com arquivos disjuntos rodam juntos: front (R2, R8) ∥ validador/contrato ∥ exportador genérico ∥ registry de infra ∥ identidade | 1 agente-executor por worktree, sobre spec numerada (molde do Bloco A). 1 agente revisor adversarial por PR Crítico |
| **B — Pipelines** (F1c, F2, F4–F6) | repos de pipeline (um por país) + repo do kit | **Países em paralelo** depois do kit. Dentro de um país, as etapas ingestão de censo ∥ concorrentes ∥ renda (pesquisa domiciliar) rodam juntas e convergem no mercado | Por país: 1 agente por etapa + 1 agente de validação que roda o validador da plataforma contra o pacote |
| **C — Fiscal** (F1d) | este repo (engenharia) + humano (premissas) | Engenharia ∥ levantamento fiscal por país | 1 agente-executor; o levantamento de premissas é **humano** (assessor fiscal) com um agente de pesquisa de apoio |
| **D — Validação de país** (gates DEC-073/D9) | scripts de medição em worktree própria | Falso-veto, sensibilidade e backtest em paralelo, por país | 1 agente por gate; o ranking cego é humano |

### 4.2 O que é obrigatoriamente sequencial

1. **F0 → F1:** o contrato precisa nascer com os defeitos da AR como fixtures negativos.
2. **Contrato v1 (F1-a) → qualquer pacote de país final:** o kit e os pipelines emitem no contrato.
3. **R7 (`_UF_RE`) e R8 (`mascara.ts`) → primeiro deploy MX/PE.**
4. **Merges Críticos são seriais**, um por vez, com `update-branch` entre eles (prática do repo) e label `critica-aprovada` do dono.
5. **Deploy de cada país:** manual, por digest, comando a comando na VPS (§6 do CLAUDE.md). Nunca dois países subindo ao mesmo tempo, para que o p95 do BR seja medido país a país.
6. **Gates da DEC-073/D9 → ligar superfície.**

### 4.3 Regras para os agentes (herdadas do repo)
- Nenhum bloco desta epic é `loop-safe` por padrão: quase todos tocam `web/`, `constants.py`, `dimensionamento/`, `deploy/` ou o sink de traversal. Quem marca `loop-safe` é humano (§6.1 do CLAUDE.md).
- **Grafo antes de varredura:** os agentes consultam `python -m graphify query` antes de grep amplo.
- **Um país por processo vale na suíte:** testes de país rodam em subprocesso.

---

## 5. Riscos do programa (consolidados)

| # | Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|---|
| P1 | **Uma pessoa de pipeline** (Juan) serializa os 4 países | Média (2ª pessoa, estagiário, em contratação desde 16/10/2026) | +10–14 semanas se a contratação atrasar | Estagiário como pessoa B: 2–4 semanas de ambientação, começa pela CO sobre o kit já usado no MX, com revisão do Juan em todo pacote e validador obrigatório |
| P2 | Cauda de "número errado silencioso" se repete a cada país | Alta sem DEC-073/D1 | 2–4 semanas por país + perda de confiança do time | Validador semântico com os 7 fixtures da AR |
| P3 | Penetração e capacidade sem fonte primária (MX, PY; CO com duas fontes divergentes) | Alta | Escala do residual errada → fila "só socio" | Declarar faixa e fonte no perfil; sensibilidade obrigatória; carimbo "não calibrado" |
| P4 | Concorrência independente invisível sem agregador (PE, PY; CO se Fitpass/Fitpal vetarem a coleta). O OSM cobre ~9 % do parque | Alta | "Não mapeado vira livre" e o ranking favorece bairros de independentes | Overture + OSM + coleta direta; fator de cobertura declarado por país; aviso na tela |
| P5 | Viabilidade usada na COF mexicana com premissa BR | Média | **Legal** | DEC-073/D6: `viabilidade` MX só com premissas assinadas |
| P6 | CPU do host (8 PDFs em 4 vCPU + coletas) | Média | p95 do BR degrada em silêncio | DEC-073/D7: `cpus:`, PDF = 1, janelas, gatilho de 2ª VPS |
| P7 | Dependências externas de dado (INEI geometria; INE-PY tabulação; CENU-CO; hosts DANE) | Média | Atraso de semanas | Iniciar os pedidos formais na F1; MVP com o que é público |
| P8 | Smart Fit já ocupou as melhores praças (CO 232, MX 488, PE 95, PY 19; RI de 30/06/2026) | Alta | Menos residual do que o BR interiorano | É **o que o motor mede** (camada 3). Não é bloqueio do plano, é premissa de negócio a validar com o time local |
| P9 | Português na interface para operadores locais | Média | Adoção | D4 é do dono; gatilho = pedido do time local |
| P10 | Colisão de número de DEC | Média | Retrabalho | Número pego no commit (`registrar-decisao`) |
