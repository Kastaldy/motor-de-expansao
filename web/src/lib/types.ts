/** Contrato entre o front e o backend do piloto (web/server/app.py). */

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
  conc: number
  ultra: number
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
  /** Rótulo curto que muda entre linhas (Quente / Livre / Agora…). */
  tag: string
  tom: Tom
}

export interface Passo {
  n: 1 | 2 | 3 | 4
  mode: string
  titulo: string
  narrativa: string
  funil_big: number
  funil_unit: string
  funil_from: string
  metrica: string
  itens: RankItem[]
  hexes: string[]
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
}

/** Pins do município + ícones quadrados por rede (data URI SVG). */
export interface Pins {
  concorrentes: Pin[]
  ultra: Pin[]
  icones: Record<string, string>
}

export interface MunicipioPayload {
  /** "uf" = visão de estado inteiro (recomenda municípios); "municipio" = drill-down. */
  nivel: 'uf' | 'municipio'
  uf: string
  municipio: string | null
  n_hex_total: number
  n_hex_mapa: number
  centro: { lat: number | null; lng: number | null }
  resumo: Resumo
  passos: Passo[]
  hexes: Hex[]
  pins: Pins
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
  unidades: number
  metricas?: Record<string, { atual: number | null; ano_anterior: number | null; var_pct: number | null }>
}

export interface RedeCarteira {
  mes: string
  meses: string[]
  referencia: string
  referencia_m1: string
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
   *  servidor para que tela, CSV e PDF desenhem exatamente a mesma série. */
  serie_rede: (number | null)[]
  unidades: RedeUnidade[]
  notas: string[]
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
  mes?: string
  uf?: string
  master?: string
  consultor?: string
  coorte?: string
  severidade?: string
  busca?: string
  ordenar?: string
  direcao?: 'asc' | 'desc'
}
