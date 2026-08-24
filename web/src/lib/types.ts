import type { CriterioPonto, ReguasPonto } from './recomendacao'

export type { CriterioPonto, ReguasPonto }

/** Contrato entre o front e o backend do piloto (web/server/app.py). */

/** Resposta do /api/me — controle temporário de acesso por aba (web/server/acesso.py).
 *  `abas` chega como string[] cru de propósito: quem valida e estreita é
 *  `abasDoPayload` em lib/acesso.ts, defensiva contra payload velho ou inesperado. */
export interface MePayload {
  usuario: string | null
  abas: string[]
}

/** Tom do chip do ranking. Fronteira TS<->Python sem contrato gerado: o produtor
 *  e' web/server/app.py. Note que `RankItem.tag_cor` tem PRECEDENCIA sobre o tom no
 *  `Chip` — onde a etiqueta sai de uma faixa da legenda, quem pinta e' a cor exata
 *  da faixa, e o tom nem e' consultado. */
export type Tom = 'blue' | 'green' | 'amber' | 'red' | 'gray'

export interface Hex {
  id: string
  lat: number
  lng: number
  /** score_priorizacao — camada executiva M1 */
  m1: number | null
  /** score_setor_2022_calibrado — camada censitaria (primaria no dia a dia) */
  censo: number | null
  /** score_expansao_hibrido */
  hib: number | null
  /** score_oportunidade_residual */
  res: number | null
  /** oferta_efetiva_disponivel, em alunos */
  oferta: number | null
  /** sam_fitness_potencial, em alunos */
  sam: number | null
  pop: number | null
  /** renda per capita (R$/mes) */
  renda: number | null
  /** renda media domiciliar (R$/mes) = renda per capita x fator municipal */
  renda_dom: number | null
  /** rotulo da faixa de oportunidade M1 (ex.: "Alta") */
  faixa: string | null
  /**
   * Bairro/distrito dominante da celula (IBGE), quando o backend o resolveu.
   *
   * So' vem na rota de MUNICIPIO — depende do codigo dele, e a visao de UF serve
   * dezenas de cidades numa resposta so'. Ausente ali nao significa "sem bairro", e por
   * isso quem rotula cai no municipio em vez de mostrar vazio.
   */
  bairro?: string | null
  conc: number
  ultra: number
  /* CONTAGEM de unidades mapeadas DENTRO do hexagono (celula H3 res-7), vinda dos MESMOS
     pontos que viram pin no mapa. Nao confundir com `conc`/`ultra` acima: `conc` e'
     `oferta_consumida_mercado_estimada / 2.500` (capacidade do modelo de 2 km, nao
     contagem) e `ultra` vem da camada de performance. E' esta a leitura que a ficha do
     hexagono promete no rotulo.
     `null` = base de pontos nao montada ("nao sei"); `0` = montada e vazia aqui ("nao ha
     unidade neste hexagono"). Sao afirmacoes diferentes e a tela nao pode fundi-las. */
  conc_hex?: number | null
  ultra_hex?: number | null
  /* PROTOTIPO da chave de raio (2 km centroide vs 1 km por area).
     `conc1k` = quantas concorrentes ALCANCAM este hexagono pelo disco de 1 km — e o que
     colore o mapa no modo novo. `oferta1k` = residual sob esse modelo.
     Ausentes (undefined) quando o backend nao tem o parquet de concorrentes montado;
     e' isso que faz a chave nem aparecer, em vez de mostrar zeros mentirosos. */
  conc1k?: number | null
  oferta1k?: number | null
  /** Alunos que ESTE hexagono perde para concorrentes: rateado por area (1 km) e no
   *  modelo atual (2 km). E' o par que deixa o rateio visivel — a concorrente na borda
   *  cobra parte daqui e parte do vizinho, em vez dos 2.500 inteiros de um lado so'. */
  cons1k?: number | null
  cons2k?: number | null
  /* Passo 4 — Crescimento do município. Camada de CONTEXTO: repassa o que o
     projeto Crescimento Regional TEC apura (CAGED, Receita Federal).
     NADA de municipal mora aqui. O que é igual em toda a cidade viaja UMA vez, em
     `MapaResposta.cres_mun` (chaveado por `mun`), pelo mesmo motivo que já tinha
     tirado `cres_dims`/`cres_series` do hexágono: repetido em 15.000 hexes eram
     ~2,2 MB por carga de UF. Aqui ficam só os dois campos que variam POR hexágono. */
  /** Nome do município — chave para `MapaResposta.cres_mun`. */
  mun: string | null
  /** taxa de crescimento da área construída DESTE hexágono, 2016→2023, em % */
  cres_hex_taxa: number | null
  /** "Em alta" | "Estável" | "Sem obra nova" — é o que colore o mapa no passo 4.
   *  RÓTULO de exibição, já acentuado pela API (`_ROTULO_CLASSE` em app.py); o
   *  identificador no parquet é ASCII. `crescClasseToColor` em lib/colors.ts compara
   *  este rótulo por literal, e `test_paridade_classe_crescimento_web.py` trava os
   *  dois lados — sem ele, renomear um rótulo pinta a camada inteira de cinza. */
  cres_hex_classe: string | null
}

/** Leitura de crescimento de uma cidade — a mesma para todos os hexes dela. */
export interface CrescimentoMunicipal {
  /** "Em alta" | "Estável" | "Em queda" — null quando não há leitura confiável */
  tend: string | null
  /** variação do emprego formal em %, dez/2022→jun/2026 (CAGED sobre estoque RAIS 2022) */
  emp: number | null
  /** saldo de empresas abertas menos fechadas, 2020→2025 (Receita Federal) */
  empresas: number | null
  /** salário médio de admissão nos últimos 12 meses (R$) */
  salario: number | null
  /** setor cuja abertura de empresas está mais ACIMA do normal nesta cidade */
  setor: string | null
  /** mediana de `emp` na UF — dá escala ao número da cidade */
  uf_mediana: number | null
}

export interface RankItem {
  rank: number
  hex_id: string
  /** Presente na visão de UF: clicar no item filtra para este município (drill-down). */
  municipio?: string | null
  titulo: string
  sub: string | null
  valor: number | null
  label: string
  /** Rótulo curto que muda entre linhas (Excelente / Livre / Agora…). Nas camadas
   *  1/2/3 sai das MESMAS faixas da legenda do mapa (`constants.FAIXAS_MAPA_*`). */
  tag: string
  tom: Tom
  /** Cor EXATA da faixa da legenda (hex). Tem precedência sobre `tom` no Chip —
   *  sem ela, "Excelente" saía azul enquanto o bloco na legenda é verde-escuro.
   *  `null` no ranking de municípios, que usa vocabulário próprio, não faixa. */
  tag_cor?: string | null
  /** Visão de UF, passo 4: dimensões DESTE município, no formato produzido por `_dims_por_municipio`. */
  dims?: string | null
  /** Visão de UF, passo 4: séries DESTE município, no formato produzido por `_series_por_municipio`. */
  series?: string | null
}

export interface Passo {
  n: 1 | 2 | 3 | 4 | 5
  mode: string
  titulo: string
  narrativa: string
  funil_big: number
  funil_unit: string
  funil_from: string
  metrica: string
  itens: RankItem[]
  hexes: string[]
  /** Passo 4, visão de município: dimensões da cidade, uma vez só.
   *  Formato `"nome:valor:unidade:posição:período"` separadas por `;`. */
  dims?: string | null
  /** Passo 4, visão de município: uma série por dimensão, uma vez só.
   *  Formato `"nome|unidade|ini|fim|v1,v2,…"` separadas por `;`. */
  series?: string | null
}

/* --- Metodologia (manual do funil, /api/metodologia) ---------------------- */

/** Uma métrica de uma camada, em dois níveis: `resumo` + `fonte` sempre visíveis,
 *  `regra` revelada sob demanda. `coluna` é o nome no parquet, para quem auditar.
 *  `ressalva` só existe onde o número tem limite conhecido — e aí é sempre visível,
 *  porque esconder limitação é o que faz tratarem estimativa como contagem. */
export interface MetricaMetodologia {
  nome: string
  coluna: string
  /** De onde vem o dado — o "com o quê" da conta. */
  fonte: string
  resumo: string
  regra: string
  ressalva?: string
}

/** Base de dados que alimenta o funil. */
export interface FonteMetodologia {
  nome: string
  detalhe: string
}

/** Faixa de etiqueta. `escopo` vazio vale nos dois funis; senão, 'municipio' | 'uf'. */
export interface FaixaMetodologia {
  etiqueta: string
  condicao: string
  tom: Tom
  escopo: string
  /** Hex EXATO da faixa. Só as derivadas da rampa o trazem: ali o painel promete a cor
   *  que o mapa pinta, e a paleta de 5 `tom` nomeados não cobre as 5 cores da rampa 1:1
   *  — "Promissor" saía cinza no manual e amarelo no mapa. */
  cor?: string | null
}

export interface CamadaMetodologia {
  /** Mesma numeracao de `Passo.n` — o painel documenta o funil, camada a camada.
   *  Ja' passou de 4 para 5 (entrou "Como a cidade está indo"); ao mexer num, mexa
   *  no outro, senao o painel descreve um funil que nao existe mais. */
  n: 1 | 2 | 3 | 4 | 5
  titulo: string
  pergunta: string
  corte: string
  metricas: MetricaMetodologia[]
  /** Etiquetas que o RANKING emite — o chip de cada item da lista. */
  faixas: FaixaMetodologia[]
  /** Cores do MAPA, quando a camada pinta por categoria em vez da rampa de score.
   *  Separado de `faixas` de proposito: cor de hexágono e etiqueta de item respondem
   *  perguntas diferentes, e publicá-las no mesmo bloco fez o painel descrever a régua
   *  errada na camada 4. */
  legenda_mapa?: FaixaMetodologia[]
  /** Ressalva da camada, quando o que a tela mostra pede aviso. */
  nota?: string
}

export interface MetodologiaPayload {
  /** Como ler o funil, antes de entrar nas camadas. */
  intro: string
  fontes: FonteMetodologia[]
  camadas: CamadaMetodologia[]
  parametros: { nome: string; valor: string }[]
}

export interface Resumo {
  residual_total: number | null
  pop_total: number | null
  score_m1_medio: number | null
  n_concorrentes: number
  n_ultra: number
  espaco_academias: number
}

/** Pin de mapa (concorrente ou Ultra). `rede`/`label` só em concorrentes. */
export interface Pin {
  lat: number
  lng: number
  rede?: string
  label?: string
  nome: string
  /**
   * `true` quando esta unidade veio do feed de um agregador (WellHub/TotalPass) e por isso temos
   * DADOS EXTRAS sobre ela — pressão medida da coordenada dela, nota, presença na série.
   *
   * Ela é uma bandeira igual a todas as outras, e isso é deliberado: uma academia de rede é uma
   * academia de rede, e dar-lhe outra forma obrigaria o operador a ligar uma chave para ver
   * concorrência que sempre existiu. O que muda é um **halo** em volta do quadrado, e o bloco
   * extra que o tooltip abre.
   *
   * **Não há `score` aqui, e a ausência é a decisão (DEC-035):** numa rede, presença em agregador
   * e churn medem negociação da MARCA, não fragilidade desta unidade.
   */
  diag?: boolean
  /** Pressão competitiva medida da coordenada desta unidade. Só quando `diag`. */
  pressao?: number | null
  nota?: number | null
  n_aval?: number | null
  /** Estado de presença na série semanal — fato sem peso. */
  churn?: string | null
  /** A conta por trás da pressão, igual à do pin de independente. */
  n_conc?: number | null
  n_indep?: number | null
  n_cadeias_feed?: number | null
  oferta?: number | null
  dist_m?: number | null
}

/** Pins do município + ícones quadrados por rede (data URI SVG). */
/** PROTOTIPO — area coberta pelo raio de 1 km, ja recortada DENTRO dos hexagonos.
 *  Cada anel e' [[lng, lat], ...]. `truncado` avisa que o teto de poligonos cortou a
 *  devolucao: um corte silencioso mentiria sobre a extensao da cobertura. */
export interface PecaCobertura {
  hex: string
  /** `coberto` = sob o raio de alguma concorrente; `livre` = o resto do hexagono. */
  tipo: 'livre' | 'coberto'
  /** Score 0-100 DAQUELE pedaco, na mesma regua das faixas do mapa. A parte livre
   *  costuma pontuar mais alto: ali nenhuma concorrente desconta residual. */
  score: number
  anel: number[][]
}

export interface Cobertura1k {
  pecas: PecaCobertura[]
  /** UMA peca por (hexagono, concorrente). Empilhadas com alpha baixo, escurecem a area
   *  proporcionalmente a quantas concorrentes cobrem aquele ponto. */
  sombras: number[][][][]
  /** Fronteira da UNIAO dos discos: UMA linha do alcance total, sem cruzamentos
   *  internos. Substitui o desenho de um circulo por concorrente, que num aglomerado
   *  virava um emaranhado de arcos. */
  contorno: number[][][][]
  n_discos: number
  truncado: boolean
}

export interface Pins {
  concorrentes: Pin[]
  ultra: Pin[]
  icones: Record<string, string>
  /**
   * O artefato de unidades de rede do agregador (DEC-035) existe e foi lido? (BLK-MA-19)
   *
   * `false` significa ARTEFATO AUSENTE — nunca "este recorte não tem unidade de agregador",
   * que devolve `true` com nenhuma bandeira de halo. Sem esta chave, os dois casos eram
   * indistinguíveis no payload, e foi assim que a camada passou cinco dias morta em produção
   * sem ninguém notar. Opcional: payload antigo não a traz.
   */
  redes_disponivel?: boolean
}

/**
 * Academia INDEPENDENTE com identidade e score (BLK-MA-15).
 *
 * Lista própria, nunca misturada a `Pins.concorrentes`: são universos de semântica OPOSTA — o
 * concorrente é quem disputa o mercado com a Ultra; a independente é quem se COMPRA. A interseção
 * entre os dois é vazia por construção, porque o universo de M&A exclui cadeias (sem esse filtro a
 * Smart Fit entraria na lista de alvos).
 */
export interface PinIndependente {
  lat: number | null
  lng: number | null
  nome: string
  /** `score_vulnerabilidade` — preenchido sempre que há ≥ 1 sinal. */
  score: number | null
  /** `score_vulnerabilidade_ordenavel` — NULO no regime provisório (G-D1). O par com `score`
   *  existe porque um diz o número e o outro diz se ele pode ordenar. */
  ordenavel: number | null
  /** Pressão competitiva medida da coordenada DESTA academia (grão unidade, DEC-029). */
  pressao: number | null
  /** Nota do WellHub. Anda SEMPRE com `n_aval` ao lado (DEC-026). */
  nota: number | null
  n_aval: number | null
  /** Regime de sinais (ex.: `"s1,s6"`) — réguas de regimes diferentes não se comparam. */
  regime: string | null
  provisorio: boolean
  /**
   * A CONTA por trás de `pressao` (BLK-MA-18). Sem ela o número não é conferível: a saturação
   * `100·(1 − 1/(1+oferta))` gasta METADE da escala numa única unidade equivalente, então `40,4`
   * significa **0,68 concorrentes efetivos** — e não "40% de pressão", que é a leitura que um
   * número de 0 a 100 num pin convida a fazer.
   *
   * `n_conc` é o que dá para contar no mapa; `oferta` é o mesmo conjunto DEPOIS do decaimento. A
   * diferença entre os dois é, literalmente, a distância.
   */
  n_conc: number | null
  /** Quantos dos `n_conc` são independentes — o resto é cadeia. Muda a tese de M&A. */
  n_indep: number | null
  /** Concorrentes EFETIVOS (soma dos pesos por distância). */
  oferta: number | null
  /** Distância até o concorrente mais próximo, em metros. Responde o que a soma esconde. */
  dist_m: number | null
  /**
   * Quantos dos `n_conc` são unidades de REDE vindas do agregador (DEC-034). Ela existe porque a
   * promessa da auditoria é "conta os pins no mapa e o número fecha", e parte dessas unidades
   * **não tinha pin desenhado** até a metade 1 do BLK-MA-17. Medido: 5.451 de 19.329 linhas
   * (28,2%) têm valor > 0 — eram 7.218 (37,3%) antes de o FU4 colapsar 320 duplicatas por nome.
   * Sem esta parcela, a conta não fechava e a explicação não estava em
   * lugar nenhum da tela.
   */
  n_cadeias_feed: number | null
}

export interface Independentes {
  itens: PinIndependente[]
  disponivel: boolean
  /** Quantas existem no recorte, ANTES do teto. */
  total: number
  /** true = o teto cortou. Declarado porque corte silencioso mente sobre a densidade. */
  truncado: boolean
}

export interface MunicipioPayload {
  /** "uf" = visão de estado inteiro (recomenda municípios); "municipio" = drill-down. */
  nivel: 'uf' | 'municipio'
  /** Só na visão de UF: crescimento do estado inteiro (ver `CrescimentoEstado`). */
  crescimento_estado?: CrescimentoEstado | null
  uf: string
  municipio: string | null
  n_hex_total: number
  n_hex_mapa: number
  centro: { lat: number | null; lng: number | null }
  resumo: Resumo
  passos: Passo[]
  hexes: Hex[]
  /** Passo 4, uma entrada por cidade. Esparso: cidade sem leitura não aparece. */
  cres_mun: Record<string, CrescimentoMunicipal>
  pins: Pins
  /** Academias independentes com score (BLK-MA-15). Ausente em payload antigo. */
  independentes?: Independentes
}

export interface MunicipioItem {
  nome: string
  n_hex: number
  residual: number | null
  score: number | null
}

/** Viabilidade — a demanda e PREMISSA do operador, nunca prevista (DEC-009). */
export interface ViabilidadeIn {
  lat: number
  lng: number
  m2: number
  aluguel: number
  demanda: number
  ticket?: number
  formato?: string
  /** Numero de studios extras (0..3); cada studio adiciona R$6.000/mes de folha. */
  n_studios?: number
  /** Obra (CAPEX): parte do APORTE INICIAL do sócio, parcelada sem juros. */
  obra?: number
  /** Parcelas da obra em meses (default 4, sem juros). */
  parcelas_obra?: number
  /** Parcelas da TAXA DE FRANQUIA (default 4, sem juros): caem nos meses de contrato
   *  1..N (M-4..M-1), junto da obra. É só timing de caixa — melhora TIR/VPL e NÃO
   *  altera EBITDA, margem nem break-even. Vazio = padrão 4. */
  parcelas_franquia?: number
  /** Equipamentos (OPEX): financiado; a PMT entra abaixo do EBITDA. */
  equipamentos?: number
  /** Prazo do financiamento de equipamentos em meses (36–60). */
  prazo_equipamentos?: number
  /** Juros mensal do financiamento de equipamentos (fração, ex.: 0.018 = 1,8% a.m.). */
  juros_equipamentos_am?: number
  /** LEGADO (compat): CAPEX único; sem valor o motor usa o default (R$ 2,34M). */
  capex?: number
  capex_financiado_pct?: number
  capex_financiado_valor?: number
  juros_financiamento_am?: number
  capex_parcelas_meses?: number
  /** LEGADO: não dirige mais o aluguel-teto (agora por clusters); só alunos-para-alvo. */
  margem_alvo?: number
  /** Meses iniciais sem pagar aluguel (beneficio de rampa; melhora payback/FCF). */
  carencia_aluguel_meses?: number
  /** Meses de rampa de maturacao do balcao (Simulador E13; default do motor = 8). */
  rampa_meses?: number
  /* --- Premissas explícitas (FIN-VIAB-01). Todas OPCIONAIS: vazio = default do
     `dimensionamento/config.py`, a fonte única. Estavam escondidas como literal no
     meio do código; hoje o operador pode sobrescrever. --------------------- */
  /** Taxa de franquia (R$, parcelada sem juros — ver `parcelas_franquia`). Editável
   *  pelo operador; vazio = R$ 160.000. */
  taxa_franquia?: number
  /** Deduções (devoluções) como FRAÇÃO do faturamento bruto. */
  deducoes_pct?: number
  reajuste_ticket_aa?: number
  reajuste_aluguel_aa?: number
  reajuste_custos_aa?: number
  /** Taxa mínima do NEGÓCIO ao ano, em FRAÇÃO (0.25 = 25% a.a.) — a ÚNICA taxa
   *  configurável do modelo. A taxa mínima do SÓCIO não entra aqui: ela é DERIVADA
   *  pelo motor a partir desta, do custo da dívida e da alavancagem, justamente para
   *  que ninguém possa digitar uma taxa de sócio menor que a que o banco cobra. */
  taxa_minima_negocio_aa?: number
  /** @deprecated ALIAS (1 versão) de `taxa_minima_negocio_aa`. O nome novo tem
   *  precedência quando os dois forem enviados. */
  taxa_desconto_aa?: number
  custo_pre_operacional_mes?: number
  valor_residual_mes_60?: number
  capex_renovacao?: number
}

/** Faixa de alunos por metragem (curva tamanho->densidade), independe da demanda. */
export interface FaixaAlunos {
  p10: number | null
  p50: number | null
  p90: number | null
  n_comparaveis: number
}

/**
 * Uma oportunidade imobiliaria (imovel de locacao coletado, ja joinado ao M1).
 *
 * Espelha o que `/api/oportunidades` devolve — um SUBCONJUNTO do viaveis.parquet,
 * SEM PII (as colunas de corretor nunca saem do backend). Numeros ausentes vem `null`.
 */
export interface Oportunidade {
  id: string
  titulo: string
  tipo: string
  operacao: string | null
  uf: string
  municipio: string
  bairro: string | null
  area: number | null
  aluguel: number | null
  iptu: number | null
  condominio: number | null
  rs_m2: number | null
  hex_id: string
  residual: number | null
  residual_total: number | null
  score: number | null
  censo_score: number | null
  faixa: string | null
  pop: number | null
  renda_pc: number | null
  sam: number | null
  n_ultra: number | null
  first_seen: string | null
  lat: number | null
  lng: number | null
  url: string | null
  /** Alunos p50 da curva tamanho->densidade (simulador de Viabilidade), pela área. */
  alunos_p50?: number | null
  /** Faturamento projetado/mês = alunos_p50 × ticket (servido pronto pelo backend). */
  fat_proj?: number | null
  /** Ticket (mensalidade balcão) usado no fat_proj — do dimensionamento/config. */
  ticket_proj?: number | null
  /** Se o coletor gerou um dossiê PDF para este imóvel (top-N por praça). */
  tem_dossie?: boolean
}

export interface OportunidadesPayload {
  /** Universo inteiro, independente da UF pedida. */
  total: number
  /**
   * Quantas existem NO RECORTE pedido (a UF, ou o universo). É o denominador honesto:
   * sem ele, filtrar por UF fazia a tela comparar os 1.501 de SP contra os 4.003
   * nacionais. Opcional porque um backend anterior a 2026-08-24 não o manda.
   */
  total_recorte?: number
  /** UFs do UNIVERSO — nunca as UFs dos `itens`, que são só o recorte capado. */
  ufs: string[]
  itens: Oportunidade[]
}

/**
 * Gestos da camada imobiliária registrados na trilha de acesso (DEC-027).
 *
 * Espelho EXATO de `ACOES_IMOBILIARIA` em `web/server/app.py` — ação fora da lista
 * recebe 404 do backend e some do rastro. Cada ação também precisa de rótulo próprio
 * em `FEATURES_ROTULOS` (`acesso_analytics.py`), senão a ficha do usuário no painel
 * de Acessos mostra o balde genérico; há teste travando isso nos dois lados.
 */
export type AcaoImobiliaria =
  | 'abrir-aba'
  | 'abrir-imovel'
  | 'abrir-dossie'
  | 'marcar-visita'
  | 'desmarcar-visita'
  | 'ver-no-mapa'
  | 'filtrar'

/**
 * Alvo do gesto — vai na QUERY, que a trilha grava inteira (teto de 2000 chars).
 * SEM PII: nada de corretor, telefone ou contato; só o que identifica o imóvel e o
 * recorte. `origem` distingue o gesto feito na aba do gesto feito pelo pin do mapa.
 */
export interface AlvoEvento {
  imovel?: string | null
  uf?: string | null
  municipio?: string | null
  origem?: 'aba' | 'mapa' | null
  detalhe?: string | null
}

/* ---------------------------------------------------------------------------
   viabilidade_payload_v1 (FIN-VIAB-01)

   O backend devolve TUDO ja calculado pelo motor unico
   (`dimensionamento/simulador.py::simular`). O front so LE: nenhum numero
   financeiro pode ser derivado aqui. Foi a duplicacao (5 series mensais e 9 KPIs
   com implementacao dupla) que causou os 17 defeitos deste ciclo — por isso o
   `ir_csll` e as parcelas do custo agora chegam prontos, e a rampa de alunos
   e a serie do motor, nao uma reta desenhada pelo grafico.

   UNIDADES: toda taxa (margem, retorno, TIR, reajuste, folha_pct, share) vem em
   FRACAO (0,3873 = 38,73%). Converter para "%" e trabalho do formatador
   (`format.pctFrac`), nunca da tela.
   --------------------------------------------------------------------------- */

export const VIABILIDADE_PAYLOAD_VERSAO = 'viabilidade_payload_v1'

/** Premissas efetivamente aplicadas pelo motor (fonte unica: dimensionamento/config.py). */
export interface PremissasViabilidade {
  /** Mensalidade cheia do plano (input do operador). */
  ticket_cheio: number
  /** Ticket do agregador em R$ — ACOPLADO ao cheio (fator do config). */
  ticket_agregador: number
  /** Ticket medio por aluno TOTAL, liquido de churn/inadimplencia (somente-leitura). */
  ticket_blended: number
  /** Fracao do mix no balcao (0.69 = 69%). */
  share_balcao: number
  /** Fracao do ticket cheio que o agregador paga (0.60). Opcional: so para rotular o mix. */
  ticket_agregador_fator?: number | null
  /* --- Folha: FIXA desde o mês 1 (decisão de Felipe, 2026-07-24) --------------
     `folha_pct` NÃO é mais um percentual da receita do mês: ele DIMENSIONA a folha
     pelo faturamento MADURO (regime pleno, a preços do ano 1) e o valor resultante
     (`folha_fixa_mes`) é pago integralmente desde o mês 1 — a equipe existe antes
     dos alunos. Logo a folha é CUSTO FIXO: saiu do fator receita→EBITDA (k passou de
     0,628985 para 0,798985) e entrou no custo fixo. Era o defeito reportado ("a folha
     está escalando junto com a unidade"). A tela LÊ estes campos; nunca multiplica
     `folha_pct` por faturamento. ------------------------------------------------ */
  folha_pct: number
  /** R$/mês de folha, FIXO desde o mês 1 (= folha_pct × faturamento maduro). */
  folha_fixa_mes: number
  /** Faturamento de regime pleno usado como BASE do dimensionamento da folha. */
  folha_base_faturamento_maduro: number
  /** Sempre true no contrato v1: deixa explícito que a folha não acompanha a rampa. */
  folha_fixa_desde_mes_1: boolean
  /** Rótulo do regime da folha (identificador, sem acento — não exibir cru). */
  folha_regime: string
  deducoes_pct: number
  impostos_receita_pct: number
  custo_variavel_pct: number
  reajuste_ticket_aa: number
  reajuste_aluguel_aa: number
  reajuste_custos_aa: number
  /** Taxa mínima do NEGÓCIO ao ano, em FRAÇÃO — a única taxa que é premissa. A do
   *  SÓCIO é DERIVADA e viaja em `retorno.socio.taxa_minima_aa`. */
  taxa_minima_negocio_aa: number
  /** @deprecated ALIAS (1 versão) de `taxa_minima_negocio_aa` — mesmo número. */
  taxa_desconto_aa: number
  /** Margem EBITDA mínima do veredito, em FRAÇÃO (0.30 = 30%). Constante do motor
   *  (`SIM_MARGEM_VIAVEL_MIN`) servida para a tela rotular a régua sem cravá-la. */
  margem_viavel_min: number
  /** Payback máximo do veredito, em meses de operação (`SIM_PAYBACK_VIAVEL_MAX`). */
  payback_viavel_max: number
  /** Carencia EFETIVA aplicada, em meses contados a partir da entrega (M-4). */
  carencia_aluguel_meses: number
  /** Mes da linha do tempo (M-4..M60) em que o aluguel comeca a ser cobrado (LEITURA
   *  da serie). `null` quando nenhum mes tem aluguel (aluguel zerado no cenario). */
  mes_inicio_aluguel: number | null
  custo_pre_operacional_mes: number
  maturacao_meses: number
  horizonte_meses: number
  /* --- Anuidade (Simulador J10/J12) -----------------------------------------
     Linha de receita SEPARADA da mensalidade: R$ `anuidade_valor` UMA VEZ POR ANO
     por aluno de BALCAO que completa `anuidade_mes_inicio` meses de casa. O
     agregador (Gympass/TotalPass) nao paga — ele remunera por acesso. A tela
     EXIBE esses campos para que o operador veja de onde vem a diferenca no
     faturamento; nenhum deles entra em conta aqui. ------------------------- */
  /** R$ por aluno elegivel, cobrado 1x/ano (0 = anuidade desligada no cenario). */
  anuidade_valor: number
  /** Mes de casa em que o aluno passa a pagar a anuidade (12 = aniversario). */
  anuidade_mes_inicio: number
  /** true = so o balcao paga (agregador nunca paga anuidade). */
  anuidade_apenas_balcao: boolean
  /** Fracao de alunos que chega ao mes de cobranca, DERIVADA do churn:
   *  (1-churn)^anuidade_mes_inicio. 0.4759 = 47,59% no cenario padrao. */
  anuidade_elegivel_pct: number
  /** Mes de OPERACAO a que a DRE de steady-state se refere (regime pleno: alunos
   *  maduros E anuidade ja em cobranca) = max(maturacao_meses, anuidade_mes_inicio).
   *  LEIA daqui — recalcular a partir de `maturacao_meses` foi o que fez o waterfall
   *  do PDF divergir do card ao lado no mesmo slide. */
  mes_referencia_steady: number
  valor_residual_mes_60: number
  capex_renovacao: number
  fonte_base_calibracao: string | null
}

/** DRE do mes steady-state. `margem` em FRACAO; parcelas do custo ja separadas. */
export interface DreViabilidade {
  faturamento: number | null
  /** Parcela de ANUIDADE dentro do `faturamento` acima (0 antes do mes de inicio).
   *  O resto do faturamento sao as mensalidades. */
  receita_anuidade: number | null
  deducoes: number | null
  /** faturamento - deducoes, servido PRONTO (nao subtrair no cliente). */
  receita_liquida: number | null
  impostos: number | null
  /** receita_liquida - impostos, servido PRONTO (nao subtrair no cliente). */
  receita_pos_impostos: number | null
  /** total operacional = custos_variaveis + folha + custos_fixos */
  custos_op: number | null
  custos_variaveis: number | null
  folha: number | null
  /** outros fixos + aluguel */
  custos_fixos: number | null
  ebitda: number | null
  /** margem EBITDA em FRACAO (0.3873 = 38,73%). */
  margem: number | null
  ir_csll: number | null
  /** juros da parcela do financiamento no mes steady. */
  despesa_financeira: number | null
  /** EBITDA - IR/CSLL (ótica DO NEGÓCIO: antes da parcela do financiamento). */
  resultado_apos_ir: number | null
  /** Fração do faturamento bruto do resultado após IR, servida PRONTA
   *  (FIN-VIAB-01: a tela não divide). O percentual do EBITDA NÃO tem campo
   *  próprio — é o `margem` acima (`margem_ebitda_pct = ebitda / faturamento`). */
  resultado_apos_ir_pct_faturamento?: number | null
  /** viável? (decidido pelo motor: margem mínima + payback máximo). */
  flag_viavel?: boolean
}

export interface InvestimentoViabilidade {
  obra: number | null
  equipamentos: number | null
  capex_total: number | null
  taxa_franquia: number | null
  investimento_total: number | null
  /** Parcela do financiamento de equipamentos (Price); 0 sem financiamento. */
  pmt: number | null
  juros_totais: number | null
  prazo_equipamentos?: number
  /** juros mensal em FRACAO (0.018 = 1,8% a.m.). */
  juros_equipamentos_am?: number | null
  parcelas_obra?: number
  /** Parcelas da taxa de franquia, sem juros (default 4), nos meses de contrato 1..N. */
  parcelas_franquia?: number
  /** R$ de CADA parcela da franquia (= taxa_franquia / parcelas_franquia). */
  franquia_parcela?: number | null
  /** APORTE INICIAL = obra + taxa de franquia: o dinheiro que o CONTRATO pede do
   *  sócio, e o denominador do retorno dele. É o número que antes se chamava
   *  "equity aportado" — o vocabulário mudou, a conta não. */
  aporte_inicial?: number | null
  /** CHEQUE TOTAL: o pior ponto do caixa acumulado — quanto o investidor precisa TER
   *  disponível, não quanto o contrato pede. No caso de referência R$ 1,14 mi contra
   *  R$ 760 mil de aporte. É o número que decide se o negócio é FINANCIÁVEL. */
  cheque_total?: number | null
  /** Mês da linha do tempo (M-4..M60) em que o caixa acumulado toca o fundo. */
  mes_cheque_total?: number | null
}

/** Uma ÓTICA de retorno: o par TIR + VPL com a taxa mínima que o desconta. */
export interface OticaRetorno {
  /** TIR ao ano em FRAÇÃO; null quando não há troca de sinal no fluxo. */
  tir_anual: number | null
  /** VPL do MESMO fluxo, descontado por `taxa_minima_aa`. */
  vpl: number | null
  /** Taxa mínima desta ótica, ao ano, em FRAÇÃO. */
  taxa_minima_aa: number | null
  /** Resultado anual / base da ótica, em FRAÇÃO. */
  retorno_anual: number | null
}

/**
 * Retorno do capital em DUAS ÓTICAS separadas — nunca no mesmo número.
 *
 * `negocio` (FCFF) roda sem financiamento, com o CAPEX inteiro desembolsado: mede o
 * ATIVO. `socio` (FCFE) tira a parcela inteira do caixa e conta só obra + franquia
 * como aporte: mede a ESTRUTURA de capital. A taxa do sócio é DERIVADA da do negócio
 * (ele é subordinado ao banco, logo exige mais que o credor), por isso ela não existe
 * como campo editável em lugar nenhum.
 *
 * As chaves PLANAS (`tir_anual`, `vpl`, `retorno_anual_*`, `otica`) seguem no contrato
 * como ALIAS porque o PDF e o XLSX leem delas: `tir_anual`/`vpl` são o par do SÓCIO.
 */
export interface RetornoViabilidade {
  /** Ótica do NEGÓCIO (o ativo, sem financiamento). */
  negocio?: OticaRetorno
  /** Ótica do SÓCIO (com a parcela do financiamento saindo do caixa). */
  socio?: OticaRetorno
  /** Custo da dívida ao ano, em FRAÇÃO (1,8% a.m. = 23,87% a.a.). */
  custo_divida_aa?: number | null
  /** Dívida / aporte inicial (1,8421 no caso de referência). */
  alavancagem_divida_sobre_aporte?: number | null
  /** VPL da dívida descontado à taxa mínima do negócio = a ARBITRAGEM. Sem escudo
   *  fiscal no Lucro Presumido, é a ÚNICA via pela qual a alavancagem cria valor.
   *  `null` enquanto o motor não publicar o campo — o backend não o calcula. */
  vpl_divida_arbitragem?: number | null
  /** true = a dívida custa MAIS que a taxa mínima do negócio: a alavancagem destrói
   *  valor em vez de criar. Aviso visível na tela. */
  alerta_divida_acima_da_taxa_negocio?: boolean
  /** DIAGNÓSTICO (não tolerância): VPL do sócio menos VPL do negócio, cada um na sua
   *  taxa. Não coincidem de propósito — a taxa do sócio usa a alavancagem INICIAL
   *  enquanto o saldo devedor cai a zero ao longo do contrato. */
  vpl_identidade_residuo?: number | null
  /** @deprecated ALIAS LEGADO — o PDF escolhe o rótulo do card por este valor. */
  otica: string
  /** @deprecated ALIAS de `negocio.retorno_anual`. */
  retorno_anual_desalavancado: number | null
  /** @deprecated ALIAS de `socio.retorno_anual`. */
  retorno_anual_equity: number | null
  /** @deprecated ALIAS de `socio.tir_anual` — o par do SÓCIO, não do negócio. */
  tir_anual: number | null
  /** @deprecated ALIAS de `socio.vpl` — o par do SÓCIO, não do negócio. */
  vpl: number | null
  /** Meses ate o acumulado virar; null quando nao vira dentro do horizonte. */
  payback: number | null
}

/** Os DOIS break-evens, sempre em alunos TOTAIS (comparaveis a demanda digitada). */
export interface BreakEvenViabilidade {
  unidade: string
  /** EBITDA = 0 (operacional). */
  ebitda: number | null
  /** Cobre tambem a PMT do financiamento (caixa). */
  caixa: number | null
}

/** Aluguel-teto como % do faturamento bruto steady. Canonico = TETO (20%). */
export interface AluguelTeto {
  base: string
  /** 15% do faturamento — faixa saudável. */
  ideal: number | null
  /** 20% do faturamento — teto recomendado. */
  teto: number | null
  /** 30% do faturamento — exceção (máximo tolerável). */
  excecao: number | null
  /** O que a tela chama de "aluguel-teto" (= faixa TETO de 20%, por decisão do dono do
   *  produto: o card grande mostra o limite que a operação defende, não a exceção). */
  canonico: number | null
  /** Mesmo teto calculado sobre o faturamento do cenário p10 (leitura conservadora). */
  teto_p10: number | null
}

/**
 * Linha da UNICA serie do sistema (M-4..M+60), como sai do motor.
 *
 * Todo campo numerico pode vir `null`: o backend passa a serie por um saneador
 * JSON-safe (NaN/inf viram null) porque o payload sai por
 * `json.dumps(..., allow_nan=False)` e um unico Infinity derrubaria a resposta.
 */
export interface SerieMensalLinha {
  /** negativo = pre-abertura (obra); >= 1 = operacao. Nao existe mes 0. */
  mes: number
  /** 1..N desde a ENTREGA da unidade (M-4) — e o relogio da carencia de aluguel. */
  mes_contrato: number
  fase: 'pre_operacional' | 'operacao'
  alunos_total: number | null
  alunos_balcao: number | null
  alunos_agregadores: number | null
  faturamento_mensal: number | null
  /** Parcela de anuidade do mes (0 antes de `premissas.anuidade_mes_inicio`). */
  receita_anuidade?: number | null
  deducoes: number | null
  receita_liquida: number | null
  impostos: number | null
  receita_pos_impostos: number | null
  custos_variaveis: number | null
  folha: number | null
  outros_fixos: number | null
  aluguel: number | null
  custo_pre_operacional: number | null
  custos_op: number | null
  ebitda_mensal: number | null
  ir_csll: number | null
  juros: number | null
  amortizacao: number | null
  pmt: number | null
  investimento: number | null
  /** Resultado de caixa DO MES. `fcf` e o alias curto do mesmo numero. */
  fcf_mensal?: number | null
  fcf?: number | null
  fcf_acumulado: number | null
}

export interface ViabilidadeOut {
  /** Sempre `viabilidade_payload_v1`. */
  versao: string
  premissas: PremissasViabilidade
  dre: DreViabilidade
  investimento: InvestimentoViabilidade
  retorno: RetornoViabilidade
  break_even: BreakEvenViabilidade
  aluguel_teto: AluguelTeto | null
  faixa_alunos: FaixaAlunos
  /** A UNICA serie do sistema: grafico, KPI e PDF leem daqui. */
  serie_mensal: SerieMensalLinha[]
  /** 1o mes em que a operacao fecha no positivo e assim permanece; null se nunca. */
  mes_caixa_operacional_positivo: number | null
  acumulado_mes_final: number | null
  demanda_premissa: number
  /** Sempre "premissa_explicita" (DEC-009): a demanda nunca vem de lat/lng. */
  demanda_fonte: string
  split: { balcao: number | null; agregadores: number | null }
  flag_fora_envelope: boolean
  flag_zona_morta: boolean | null
  motivo_zona_morta: string | null
  grade: Record<string, unknown>[]
  /** Sugestão de ajuste quando o payback estoura (> 40 meses); null se ok. NÃO é KPI:
   *  é LEITURA da série do motor feita no backend, nunca uma conta da tela. */
  melhoria_payback: MelhoriaPayback | null
}

/** Quanto cortar de CAPEX ou de aluguel para o payback cair para ~alvo_meses. */
export interface MelhoriaPayback {
  alvo_meses: number
  /** R$ a reduzir do CAPEX (null se um corte só de CAPEX não bastar). */
  reduzir_capex: number | null
  /** R$/mês a reduzir do aluguel (null se um corte só de aluguel não bastar). */
  reduzir_aluguel: number | null
}

/* ---- Visão Executiva por estado (rede Ultra real, camada paralela) ---- */

export interface ExecUnidade {
  nome: string
  lat: number | null
  lng: number | null
  ativos: number | null
  pagantes: number | null
  agregadores: number | null
  faturamento: number | null
  /** churn em % (ex.: 2.79 = 2,79%) */
  churn: number | null
  ticket: number | null
  nps: number | null
  inauguracao: string
}

/** Métrica com comparação M-1 (mesmo dia do mês anterior). */
export interface ExecMetric {
  atual: number | null
  m1: number | null
  delta_pct: number | null
}

export interface ExecTotais {
  unidades: number
  com_coordenada: number
  faturamento: ExecMetric
  ativos: ExecMetric
  pagantes: ExecMetric
  agregadores: ExecMetric
  /** churn rolling 30 dias, em % */
  churn: ExecMetric
  ticket: ExecMetric
  nps: ExecMetric
  pct_pagantes: number | null
  pct_agregadores: number | null
}

export interface ExecutivaPayload {
  uf: string
  /** competência selecionada, ex.: "2026-06" */
  mes: string | null
  /** competências disponíveis (mais recentes primeiro), ex.: ["2026-06","2026-05",…] */
  meses: string[]
  /** dia de referência (MTD), ex.: "12/06/2026" */
  referencia: string | null
  /** mesmo dia do mês anterior, ex.: "12/05/2026" */
  referencia_m1: string | null
  centro: { lat: number | null; lng: number | null }
  /** bandeira quadrada da Ultra (data URI SVG) para o centro das bolhas do mapa. */
  ultra_icon: string | null
  totais: ExecTotais
  unidades: ExecUnidade[]
}

/** Campos opcionais do imovel que enriquecem o PDF do Relatorio Pontual. */
export interface InfoImovel {
  nome?: string
  valor_venda?: string
  pe_direito?: string
  vagas?: string
  tipo?: string
  observacoes?: string
}

/* ---- Visão Executiva 2.0 — a rede como carteira acionável (DEC-023) ---- */

/**
 * O QUARTETO DE CONTEXTO. Toda métrica da rede chega com os mesmos quatro valores,
 * porque é assim que o time de campo lê: nunca um número sozinho, sempre
 * `MÊS | M-1 | Ranking N/total | % vs Média Rede`. Eles não leem desempenho por cor
 * — leem "estou 64% abaixo da média da rede e sou 79º de 89".
 */
export interface RedeMetrica {
  atual: number | null
  m1: number | null
  /** variação relativa vs M-1, em % */
  delta_pct: number | null
  /** posição na rede (não no recorte filtrado); null se a unidade não é comparável */
  rank: number | null
  rank_total: number | null
  /** distância da média da rede, em % */
  vs_media_pct: number | null
}

export type RedeSeveridade = 'alta' | 'media' | 'ok' | 'sem_base'

export interface RedeAlerta {
  codigo: string
  titulo: string
  detalhe: string
  nivel: 'grave' | 'medio'
}

export interface RedeUnidade {
  id: string
  nome: string
  uf: string
  master: string
  cidade: string | null
  consultor: string | null
  consultor_2: string | null
  master_franquia: string | null
  franqueado: string | null
  coorte: string
  coorte_rotulo: string
  meses_operacao: number | null
  inauguracao: string | null
  lat: number | null
  lng: number | null
  /** false quando a unidade inaugurou dentro da competência (fora de ranking/média) */
  comparavel: boolean
  severidade: RedeSeveridade
  severidade_rotulo: string
  prioridade: number
  resumo: string
  faixa_faturamento: string
  faixa_faturamento_rotulo: string
  alertas: RedeAlerta[]
  metricas: Record<string, RedeMetrica>
  /** faturamento dos últimos 12 meses fechados (sparkline da carteira) */
  sparkline: (number | null)[]
  /** faturamento do último mês FECHADO e sua variação contra o mês anterior. É o que
   *  sustenta "quem puxa e quem segura": no dia 3 da competência em curso, a variação
   *  contra os mesmos 3 dias do mês passado é ruído de janela curta (+6.239% na base
   *  real). Ausente na ficha da unidade, que é outro payload. */
  fechado?: {
    competencia: string | null
    faturamento: number | null
    variacao_pct: number | null
  }
  /** SSS da unidade: o mesmo mês, um ano antes. `var_pct` nulo quando ela não operou o
   *  mês inteiro nos dois períodos — a unidade continua na lista, dizendo por que não
   *  entra na conta, em vez de sumir. Ausente na ficha, que é outro payload. */
  sss?: {
    competencia_base: string
    faturamento: number | null
    ano_anterior: number | null
    var_pct: number | null
  }
}

export interface RedeRegua {
  rotulo: string
  metrica: string
  sentido: 'acima' | 'abaixo' | 'persistencia'
  limiar: number
  limiar_grave?: number
  unidade?: string
  meses?: number
  meta?: number
}

export interface RedeSss {
  disponivel: boolean
  competencia_base: string
  /** unidades COMPARÁVEIS: as do recorte que operaram o mês inteiro nos dois períodos */
  unidades: number
  /** quantas unidades o recorte tem no mês escolhido */
  unidades_recorte: number
  /** `unidades_recorte - unidades` — as que não existiam há um ano e por isso não entram */
  unidades_fora: number
  metricas?: Record<string, { atual: number | null; ano_anterior: number | null; var_pct: number | null }>
  /** SSS mês a mês, alinhado a `serie_meses`. `unidades[i]` é a base comparável DAQUELE
   *  mês: ela muda de ponto para ponto, e sem ela uma alta de base pequena parece alta
   *  da rede inteira. */
  serie: { meses: string[]; var_pct: (number | null)[]; unidades: number[] }
}

/** Funil comercial somado do recorte. Mesma forma do funil da ficha da unidade. */
export interface RedeFunil {
  visitas: number | null
  convertidos: number | null
  vendas: number | null
  novos_alunos: number | null
  conversao_pct: number | null
  /** vem preenchido quando `vendas > convertidos`; o funil NÃO é clampado em 100% */
  aviso: string | null
}

export interface RedeFaixa {
  chave: string
  rotulo: string
  n: number
  faturamento: number | null
}

/** Distribuição do recorte pelas faixas absolutas de faturamento do time de campo.
 *  `competencia` é sempre o último mês FECHADO, nunca a competência em curso. */
export interface RedeFaixas {
  competencia: string | null
  faixas: RedeFaixa[]
}

export interface RedeCoorteResumo {
  chave: string
  rotulo: string
  n: number
}

export interface RedeCarteira {
  /** competência do FIM do período: é ela que ancora a série de 12 meses, as faixas
   *  absolutas e o diagnóstico, que continuam mensais mesmo com período livre. */
  mes: string
  meses: string[]
  /** o intervalo analisado, as duas pontas inclusive */
  periodo: { inicio: string; fim: string; dias: number; mes_inteiro: boolean }
  /** contra o que as setas de variação comparam: mês inteiro -> mês anterior; qualquer
   *  outro recorte -> a janela imediatamente anterior de MESMO tamanho */
  periodo_anterior: { inicio: string; fim: string }
  /** primeira e última data com dado na base — o limite do calendário */
  limites: { min: string; max: string }
  referencia: string
  referencia_m1: string
  /** true só quando o período é um mês do calendário INTEIRO e já fechado */
  mes_completo: boolean
  /** competência FECHADA de onde vêm alertas e severidade */
  competencia_diagnostico: string | null
  totais: { rede: number; no_recorte: number; com_coordenada: number }
  kpis: Record<string, RedeMetrica>
  split: {
    recorrentes: number | null
    agregadores: number | null
    pct_recorrentes: number | null
    pct_agregadores: number | null
  }
  semaforo: Record<RedeSeveridade, number>
  sss: RedeSss
  centro: { lat: number | null; lng: number | null }
  bbox: { min_lat: number; min_lng: number; max_lat: number; max_lng: number } | null
  ultra_icon: string | null
  reguas: Record<string, RedeRegua>
  meta_nps: number
  /** competências FECHADAS que rotulam a sparkline e o gráfico agregado, em ordem
   *  cronológica. Vem do servidor: com a competência aberta, a série termina no mês
   *  anterior, e contar para trás a partir de `mes` desloca o gráfico inteiro. */
  serie_meses: string[]
  /** faturamento somado do recorte, um valor por mês de `serie_meses`. Vem pronto do
   *  servidor para que tela, CSV e PDF desenhem exatamente a mesma série.
   *  É literalmente `series.faturamento` — o painel de evolução não abriu segunda conta. */
  serie_rede: (number | null)[]
  /** séries de 12 meses fechados do recorte, uma por métrica do painel de evolução.
   *  Soma para volume, média PONDERADA para taxa — as mesmas regras dos KPIs do topo. */
  series: Record<string, (number | null)[]>
  funil: RedeFunil
  faixas: RedeFaixas
  coortes: RedeCoorteResumo[]
  unidades: RedeUnidade[]
  notas: string[]
  fonte_faturamento: RedeFonteFaturamento
}

/** De onde veio o faturamento de cada camada da aba.
 *
 *  A aba mistura duas fontes de propósito: os meses FECHADOS vêm da planilha do
 *  Financeiro (base dos royalties) e o período em curso vem da Growth, porque a planilha é
 *  mensal e não sabe responder por uma janela parcial. A diferença não é cosmética — a
 *  Growth parou de mandar a receita de agregador em maio/2025 e fica ~20% abaixo —, então
 *  a tela precisa dizer qual número é qual. */
export interface RedeFonteFaturamento {
  /** origem por competência de `serie_meses`. `misto` = o recorte tem unidades das duas. */
  por_mes: Record<string, 'financeiro' | 'ux' | 'misto'>
  /** o quarteto do topo e o SSS saem de janela livre, que nunca é sobreposta. */
  periodo: 'financeiro' | 'ux' | 'misto'
  /** unidades que faturam na planilha e não existem na Growth — ficam fora da carteira. */
  unidades_sem_par: string[]
}

export interface RedeFiltros {
  meses: string[]
  mes_padrao: string
  ufs: string[]
  masters: string[]
  consultores: string[]
  masters_franquia: string[]
  coortes: { chave: string; rotulo: string; n: number }[]
  severidades: { chave: RedeSeveridade; rotulo: string }[]
  metricas: {
    chave: string
    rotulo: string
    direcao: 'asc' | 'desc'
    bom_subindo: boolean
    formato: 'brl' | 'int' | 'pct' | 'nota'
  }[]
  reguas: Record<string, RedeRegua>
  meta_nps: number
  medios_para_alta: number
  faixas_faturamento: { ate: number | null; chave: string; rotulo: string }[]
  metricas_a_validar: string[]
  qualidade: {
    unidades: number
    com_coordenada: number
    com_consultor: number
    sem_nps: number
  }
  cadastro: { disponivel: boolean; versao: number; campos_editaveis: string[] }
  referencia: string
  fonte: string
}

export interface RedeCoorteComparacao {
  chave: string
  rotulo: string
  /** 'coorte' | 'coorte_vizinha' | 'rede' | 'sem_dado' — SEMPRE exibida */
  degradacao: string
  base_rotulo: string
  n: number
  metricas: Record<
    string,
    {
      unidade: number | null
      p25: number | null
      p50: number | null
      p75: number | null
      percentil: number | null
    }
  >
}

export interface RedeFicha {
  unidade: RedeUnidade & {
    dpto: string | null
    cod_unidade: string | null
    gold: number | null
    life_time: number | null
    ltv: number | null
    wellhub: string | null
    totalpass: string | null
    modalidades: Record<string, boolean>
  }
  mes: string
  meses: string[]
  referencia: string
  competencia_diagnostico: string | null
  metricas: Record<string, RedeMetrica>
  /** série FECHADA de 12 meses, em formato colunar (2,4x menor que array de objetos) */
  serie: { meses: string[] } & Record<string, (number | null)[]>
  serie_diaria: { datas: string[] } & Record<string, (number | null)[]>
  funil: {
    visitas: number | null
    convertidos: number | null
    vendas: number | null
    novos_alunos: number | null
    conversao_pct: number | null
    /** preenchido quando `vendas > convertidos` — o funil não fecha e isso é dito */
    aviso: string | null
  }
  coorte: RedeCoorteComparacao
  diagnostico: {
    competencia: string | null
    severidade: RedeSeveridade
    severidade_rotulo: string
    prioridade: number
    resumo: string
    alertas: RedeAlerta[]
    recomendacoes: { codigo: string; titulo: string; corpo: string }[]
  }
  cadastro: {
    disponivel: boolean
    versao: number
    campos_editaveis: string[]
    valores: Record<string, string>
  }
  reguas: Record<string, RedeRegua>
  meta_nps: number
  notas: string[]
}

/** Query da carteira. Tudo opcional: sem filtro nenhum, vem a rede do Brasil inteiro. */
export interface RedeQuery {
  /** competência (AAAA-MM). Continua aceita: é o que mantém os links antigos e o
   *  contrato v1 funcionando. Quando `inicio`/`fim` vêm juntos, eles mandam. */
  mes?: string
  /** período de análise, ISO AAAA-MM-DD, as duas pontas INCLUSIVE */
  inicio?: string
  fim?: string
  uf?: string
  master?: string
  consultor?: string
  coorte?: string
  severidade?: string
  busca?: string
  ordenar?: string
  direcao?: 'asc' | 'desc'
}

/* ------------------------------------------------------------------------- *
 * Modo de PONTO (GET /api/ponto)                                            *
 * ------------------------------------------------------------------------- */

/**
 * Bloco que pode não ter dado. O servidor manda `disponivel` e, quando falso, o
 * `motivo` por extenso — a tela NUNCA inventa o texto do estado vazio nem some com
 * o bloco em silêncio. Censo depende só da malha IBGE; concorrência e mercado
 * dependem de `data/staging`, que pode não estar montado.
 */
export interface BlocoOpcional {
  disponivel: boolean
  motivo: string | null
}

/** Min / mediana / max de uma leitura, entre os setores do raio. */
export interface PontoDistribuicao {
  min: number | null
  p50: number | null
  max: number | null
  /** Setores COM medição desta leitura — pode ser menor que o total do raio. */
  n: number
}

/** Os números BRUTOS da área: o que está por trás das médias da ficha. */
export interface PontoCensoDetalhe {
  n_setores: number | null
  /** Área do círculo (pi*r²) e a que a malha do IBGE realmente cobre dentro dele. */
  area_circulo_km2: number | null
  area_intersectada_km2: number | null
  /** Fixa divide por pi*r² (inclui água e vazio); válida, só pela área de setor. */
  densidade_fixa_hab_km2: number | null
  densidade_valida_hab_km2: number | null
  score_medio_raio: number | null
  score_max_raio: number | null
  /** Setor a setor: o que a média esconde. */
  distribuicao: {
    renda_per_capita: PontoDistribuicao | null
    score: PontoDistribuicao | null
    populacao: PontoDistribuicao | null
    densidade_hab_km2: PontoDistribuicao | null
  }
  /** O setor que CONTÉM o ponto — pode divergir da média do raio. */
  setor_do_ponto: {
    encontrado: boolean
    cod_setor: string | null
    renda_per_capita: number | null
    densidade_hab_km2: number | null
    score: number | null
    bairro: string | null
    distrito: string | null
  }
  /** Procedência, não método: de quando é o dado. */
  data_referencia: string | null
}

export interface PontoCenso extends BlocoOpcional {
  populacao: number | null
  domicilios: number | null
  renda_per_capita: number | null
  renda_media_domiciliar: number | null
  /** Densidade VÁLIDA: divide pela área de setor intersectada, não por pi*r². */
  densidade_hab_km2: number | null
  score_socioeconomico: number | null
  n_setores: number | null
  detalhe: PontoCensoDetalhe | null
}

export interface PontoConcorrencia extends BlocoOpcional {
  n_concorrentes: number | null
  n_ultra: number | null
  /** Cada concorrente do raio, por distância. Vazio quando não há base montada. */
  lista: { rede: string | null; dist_km: number | null }[]
}

export interface PontoMercado extends BlocoOpcional {
  sam: number | null
  residual: number | null
  score_residual: number | null
}

export interface PontoVizinho {
  hex_id: string | null
  residual: number | null
  score_censo: number | null
}

export interface PontoPayload {
  lat: number
  lng: number
  raio_km: number
  hex_id: string
  local: {
    uf: string
    municipio: string | null
    bairro: string | null
    /** Identificador cru ("bairro"/"distrito"), NÃO acentuado. Exibir `bairro`. */
    unidade_tipo: string | null
  }
  censo: PontoCenso
  concorrencia: PontoConcorrencia
  mercado: PontoMercado
  vizinhos: PontoVizinho[]
  /** Réguas do imóvel, legíveis por máquina (a metodologia traz as mesmas em texto). */
  reguas: ReguasPonto | null
  /** Cada métrica já comparada com a régua, NO SERVIDOR — a tela não re-decide. */
  criterios: CriterioPonto[]
}

/** Resposta de GET /api/resolver-ponto: texto colado -> coordenada. */
export interface PontoResolvido {
  found: boolean
  lat?: number
  lng?: number
  nome?: string
  /** Como resolveu: coordenada | link-expandido | endereco-do-link | endereco. */
  via?: string
  motivo?: string
}

/**
 * Crescimento do ESTADO INTEIRO — bloco próprio, fora de `passos`.
 *
 * Não confundir com o passo 4 do funil: aquele descreve as cidades que sobreviveram
 * aos filtros 1-3 (só white space), e por isso lista uma dúzia. Este olha a UF toda.
 */
export interface CrescimentoEstado {
  /** Mediana de crescimento do emprego na UF — a régua contra a qual tudo é lido. */
  mediana_uf: number | null
  n_municipios_com_medicao: number
  n_municipios_uf: number
  /** Piso de população aplicado ao ranking (`POP_MIN_ACIONAVEL`). */
  pop_minima: number
  /** Quantos municípios o piso deixou de fora — declarado, nunca silencioso. */
  n_fora_do_piso: number
  itens: RankItem[]
}

/* ------------------------------------------------------------------------- *
 * Ranking nacional por UF (GET /api/estados)                                *
 * ------------------------------------------------------------------------- */

export interface EstadoRanking {
  rank: number
  uf: string
  /** Alunos não atendidos ONDE ainda cabe abrir — o número que ordena. */
  residual_white_space: number | null
  hexes_elegiveis: number
  municipios_elegiveis: number | null
  /** Contexto: o tamanho do estado por trás do número elegível. */
  residual_total: number | null
  hexes_total: number
  pop_total: number | null
}

export interface EstadosPayload {
  reguas: {
    score_minimo: number
    pop_minima: number
    capacidade_concorrente: number
  }
  estados: EstadoRanking[]
}

/* ------------------------------------------------------------------------- *
 * Aba Acessos — analytics da trilha (emenda DEC-027; GET /api/acessos/*)    *
 * Restrita por allowlist de env no backend; a SPA só a mostra se /api/me    *
 * devolver a aba `acessos`.                                                 *
 * ------------------------------------------------------------------------- */

export interface AcessosSerieDia {
  dia: string
  acoes: number
  usuarios: number
}

export interface AcessosPorAba {
  /** Rótulo de exibição (acentuado) — o backend já aplica a camada de LABEL. */
  aba: string
  acoes: number
  usuarios: number
}

export interface AcessosUsuarioLinha {
  nome: string
  ultimo_dia: string | null
  ultimo_hora: string | null
  dias_ativos: number
  acoes: number
  abas: string[]
  /** Nº de IPs DISTINTOS na janela — sinal de anomalia, nunca o IP em si. */
  ips: number
  /** Ações/dia dos últimos 14 dias (sparkline da tabela). */
  serie14: number[]
}

export interface AcessosRotaLenta {
  rota: string
  n: number
  p95_ms: number | null
}

export interface AcessosSaude {
  total: number
  erros_4xx: number
  erros_5xx: number
  taxa_erro_pct: number
  lentas: AcessosRotaLenta[]
}

export interface AcessosResumo {
  gerado_em: string
  janela_dias: number
  hoje: {
    usuarios: number
    acoes: number
    aba_top: string | null
    ultimo: { usuario: string; hora: string | null } | null
  }
  serie: AcessosSerieDia[]
  /** 7 linhas (0 = segunda) × 24 horas BRT. */
  heatmap: number[][]
  por_aba: AcessosPorAba[]
  usuarios: AcessosUsuarioLinha[]
  saude: AcessosSaude
}

export interface AcessosFichaDia {
  dia: string
  ini: string
  fim: string
  acoes: number
}

export interface AcessosFeature {
  /** Rótulo humano ("Rodou simulação de viabilidade") — nunca a rota/conteúdo. */
  feature: string
  n: number
}

export interface AcessosSessao {
  dia: string
  ini: string
  fim: string
  acoes: number
  abas: string[]
}

/** Um evento da linha do tempo — FEATURE + hora, nunca rota/query/conteúdo. */
export interface AcessosEventoTempo {
  dia: string
  hora: string
  feature: string
  aba: string | null
  erro: boolean
}

export interface AcessosFicha {
  nome: string
  janela_dias: number
  acoes: number
  dias_ativos: number
  ultimo_dia: string
  ultimo_hora: string | null
  abas: string[]
  ips: number
  erros: number
  dias: AcessosFichaDia[]
  /** Mais recente primeiro; quebra por pausa > 30 min ou virada de dia. */
  sessoes: AcessosSessao[]
  features: AcessosFeature[]
  por_aba: { aba: string; acoes: number }[]
  heatmap: number[][]
  /** Mais recente primeiro; teto de 80 eventos. */
  linha_do_tempo: AcessosEventoTempo[]
}
