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
  /** Rótulo curto que muda entre linhas (Quente / White space / Agora…). */
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
  /** Obra (CAPEX, equity): base do ROIC/payback; parcelada sem juros. */
  obra?: number
  /** Parcelas da obra em meses (default 4, sem juros). */
  parcelas_obra?: number
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
  /** Taxa de franquia (R$, à vista no M-4). Editável pelo operador; vazio = R$ 160.000. */
  taxa_franquia?: number
  /** Deduções (devoluções) como FRAÇÃO do faturamento bruto. */
  deducoes_pct?: number
  reajuste_ticket_aa?: number
  reajuste_aluguel_aa?: number
  reajuste_custos_aa?: number
  /** Taxa de desconto do VPL/TIR, ao ano, em FRAÇÃO. */
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
  folha_pct: number
  deducoes_pct: number
  impostos_receita_pct: number
  custo_variavel_pct: number
  reajuste_ticket_aa: number
  reajuste_aluguel_aa: number
  reajuste_custos_aa: number
  taxa_desconto_aa: number
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
  /** EBITDA - IR/CSLL (otica DESALAVANCADA: antes da PMT). */
  resultado_apos_ir: number | null
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
}

/** Retorno do capital. A otica padrao e a DESALAVANCADA; equity nunca no mesmo KPI. */
export interface RetornoViabilidade {
  otica: string
  retorno_anual_desalavancado: number | null
  retorno_anual_equity: number | null
  /** TIR ao ano em FRACAO; null quando nao ha troca de sinal. */
  tir_anual: number | null
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

/** Aluguel-teto como % do faturamento bruto steady. Canonico = excecao (30%). */
export interface AluguelTeto {
  base: string
  /** 15% do faturamento — faixa saudável. */
  ideal: number | null
  /** 20% do faturamento — teto recomendado. */
  teto: number | null
  /** 30% do faturamento — exceção (máximo tolerável). */
  excecao: number | null
  /** O que a tela chama de "aluguel-teto" (= exceção, por decisão do dono do produto). */
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
