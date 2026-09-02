import { moeda } from './perfil'
/**
 * O que fazer para o imovel fechar a conta — deterministico, e honesto sobre limites.
 *
 * NAO E' UM SCORE NOVO. Nao existe "nota do imovel": o que existe sao as reguas que o
 * projeto ja usa (`SCORE_CORTE_QUENTE`, `POP_MIN_ACIONAVEL`, `OFERTA_DESTAQUE_MIN`,
 * `RENDA_MIN`), o booleano `dre.flag_viavel` do motor, e a sugestao que o proprio
 * motor calcula (`melhoria_payback`). Este modulo so' ORDENA isso em acoes.
 *
 * A DISTINCAO QUE MANDA EM TUDO: ha coisas que o operador PODE mudar (aluguel,
 * metragem, obra, ticket) e coisas que ele NAO pode (quem mora em volta, quanta renda
 * tem, quantos concorrentes ja abriram). Quando a reprovacao vem do que nao se muda,
 * a resposta certa e' "esse imovel nao da" — e nao uma lista de ajustes que nao
 * resolveriam. Sugerir "baixe o aluguel" para um ponto sem populacao faz o operador
 * negociar por semanas um imovel que nunca ia fechar.
 *
 * METRAGEM x CONCORRENCIA: o pedido original era "se tem muitos concorrentes, aumentar
 * a metragem". O projeto NAO tem como calcular isso — nao existe metragem de
 * concorrente em base nenhuma, e derivar m2 da geografia viola a DEC-009, que fixou o
 * motor como property-first (m2 e' ENTRADA do operador). O que sai daqui e' um AVISO
 * rotulado como regra de bolso, que nao altera numero nenhum a jusante.
 */

/** Um criterio do imovel ja avaliado pelo servidor (`/api/ponto`). */
export interface CriterioPonto {
  chave: string
  rotulo: string
  valor: number | null
  regua: number | null
  unidade: string
  maior_melhor: boolean
  /** `null` = sem dado para avaliar; nunca tratar como reprovado. */
  passa: boolean | null
}

export interface ReguasPonto {
  pop_minima: number | null
  score_minimo: number | null
  renda_domiciliar_minima: number | null
  area_min_m2: number | null
  area_ideal_min_m2: number | null
  area_ideal_max_m2: number | null
  conc_regiao_disputada: number | null
}

/** O que o motor sugere cortar para o payback bater o alvo. */
export interface MelhoriaPaybackEntrada {
  alvo_meses: number
  reduzir_capex: number | null
  reduzir_aluguel: number | null
}

export interface EntradaRecomendacao {
  criterios: readonly CriterioPonto[]
  reguas: ReguasPonto | null
  /** `null` enquanto o operador nao calculou a viabilidade. */
  viavel: boolean | null
  m2: number | null
  aluguel: number | null
  /** `aluguel_teto.teto` do motor. */
  tetoAluguel: number | null
  melhoria: MelhoriaPaybackEntrada | null
  /** Nenhuma celula da grade de sensibilidade fecha a conta. */
  gradeSemViavel: boolean
}

export type TipoAcao = 'bloqueio' | 'acao' | 'aviso' | 'ok'

export interface Acao {
  tipo: TipoAcao
  titulo: string
  /** Uma frase dizendo por que, com o numero que sustenta. */
  detalhe: string
}

/**
 * Criterios que o operador NAO consegue mudar negociando o imovel.
 *
 * Populacao, renda e concorrencia instalada sao do TERRITORIO. Metragem e aluguel
 * sao do contrato. Residual e' consequencia dos dois primeiros mais a concorrencia,
 * entao tambem nao se negocia.
 */
const ESTRUTURAIS = new Set(['populacao', 'renda_domiciliar', 'score', 'residual'])

export function recomendar(e: EntradaRecomendacao): Acao[] {
  const acoes: Acao[] = []

  const reprovados = e.criterios.filter((c) => c.passa === false)
  const estruturais = reprovados.filter((c) => ESTRUTURAIS.has(c.chave))
  const conc = e.criterios.find((c) => c.chave === 'concorrentes')

  // 1. O que nao se muda vem PRIMEIRO. Se o entorno nao sustenta, nenhum ajuste de
  //    contrato resolve, e a lista de ajustes so' faria o operador perder tempo.
  if (estruturais.length) {
    acoes.push({
      tipo: 'bloqueio',
      titulo: 'Este ponto não se resolve por negociação',
      detalhe:
        `Reprova em ${listar(estruturais.map((c) => c.rotulo.toLowerCase()))}. ` +
        'Isso é do território, não do contrato: baixar aluguel ou mudar metragem não muda ' +
        'quem mora em volta, com que renda, nem quantos concorrentes já abriram.',
    })
  }

  // 2. Concorrencia: contexto, com regra de bolso declarada.
  if (
    conc?.valor != null &&
    e.reguas?.conc_regiao_disputada != null &&
    conc.valor >= e.reguas.conc_regiao_disputada
  ) {
    const topo = e.reguas.area_ideal_max_m2
    acoes.push({
      tipo: 'aviso',
      titulo: 'Região disputada',
      detalhe:
        `${conc.valor} concorrentes no raio. Para brigar por aluno num entorno assim, a ` +
        `metragem costuma ir para o topo da faixa ideal${topo != null ? ` (${fmt(topo)} m²)` : ''}. ` +
        'É regra de bolso, não cálculo: o projeto não tem a metragem dos concorrentes, e ' +
        'dimensionar pela geografia contraria a decisão que fixou o m² como entrada do operador.',
    })
  }

  // 3. Viabilidade: so' fala quando o operador ja calculou.
  if (e.viavel === false) {
    if (e.melhoria?.reduzir_aluguel != null && e.aluguel != null) {
      const alvo = e.aluguel - e.melhoria.reduzir_aluguel
      acoes.push({
        tipo: 'acao',
        titulo: `Negociar o aluguel para ${fmtBrl(Math.max(alvo, 0))}`,
        detalhe:
          `Cortar ${fmtBrl(e.melhoria.reduzir_aluguel)} por mês leva o payback ao alvo de ` +
          `${e.melhoria.alvo_meses} meses. Cálculo do motor, não estimativa da tela.`,
      })
    }
    if (e.melhoria?.reduzir_capex != null) {
      acoes.push({
        tipo: 'acao',
        titulo: `Cortar ${fmtBrl(e.melhoria.reduzir_capex)} da obra`,
        detalhe:
          `Alternativa ao corte de aluguel: o mesmo alvo de ${e.melhoria.alvo_meses} meses ` +
          'sai reduzindo o CAPEX. Vale quando o proprietário não cede no aluguel.',
      })
    }
    // O teto entra quando o motor NAO sugeriu corte (payback dentro da faixa em que
    // ele nao opina) mas o aluguel pedido ja passa do que a operacao sustenta.
    if (!e.melhoria && e.aluguel != null && e.tetoAluguel != null && e.aluguel > e.tetoAluguel) {
      acoes.push({
        tipo: 'acao',
        titulo: `Aluguel acima do teto: negociar para ${fmtBrl(e.tetoAluguel)}`,
        detalhe:
          `O pedido é ${fmtBrl(e.aluguel)} e a operação sustenta ${fmtBrl(e.tetoAluguel)} ` +
          '(20% do faturamento) na premissa de alunos que está na tela.',
      })
    }
    if (e.m2 != null && e.reguas?.area_min_m2 != null && e.m2 < e.reguas.area_min_m2) {
      acoes.push({
        tipo: 'acao',
        titulo: `Metragem abaixo do mínimo (${fmt(e.reguas.area_min_m2)} m²)`,
        detalhe:
          `O imóvel tem ${fmt(e.m2)} m². Abaixo do mínimo da rede, o modelo de unidade ` +
          'não fecha independentemente do aluguel.',
      })
    }
    // Nenhuma combinacao da grade fecha: a conta nao e' de negociacao.
    if (e.gradeSemViavel && !e.melhoria) {
      acoes.push({
        tipo: 'bloqueio',
        titulo: 'Nenhum cenário testado fecha a conta',
        detalhe:
          'A grade de sensibilidade varre alunos e aluguel e não encontra combinação viável ' +
          'para este ponto. O problema não é o preço do contrato.',
      })
    }
  }

  if (!acoes.length) {
    acoes.push(
      e.viavel === true
        ? {
            tipo: 'ok',
            titulo: 'Fecha a conta na premissa atual',
            detalhe: 'Nenhum ajuste necessário para os números que estão na tela.',
          }
        : {
            tipo: 'ok',
            titulo: 'Nada reprova no entorno',
            detalhe:
              'Os critérios do território passam. Calcule a viabilidade para saber se o ' +
              'contrato fecha a conta.',
          },
    )
  }

  return acoes
}

function listar(xs: string[]): string {
  if (xs.length === 1) return xs[0]
  return `${xs.slice(0, -1).join(', ')} e ${xs[xs.length - 1]}`
}

function fmt(v: number): string {
  return v.toLocaleString('pt-BR', { maximumFractionDigits: 0 })
}

function fmtBrl(v: number): string {
  return `${moeda()} ${fmt(v)}`
}
