/* Crescimento da concorrência — os textos e as datas do card, montados a partir do payload.

   O card juntava duas fontes com as datas escritas no código ("02/08 a 06/09", "31/08 a 12/09",
   "contagem oficial de 06/09") e ficou oito domingos parado sem que nada na tela denunciasse
   (diagnóstico de 04/11/2026). Daqui em diante toda data visível sai do dado, e as regras de
   texto moram aqui, em funções puras testadas sem DOM (o vitest roda em `node`).

   As duas fontes, cada uma com a sua data:
   - UNIDADES e VARIAÇÃO: contagem semanal do coletor (a do relatório de domingo no Telegram),
     sempre a última ACEITA — contagem com queda brusca é recusada e a tela diz qual e por quê;
   - ABERTURAS, FECHAMENTOS, SALDO e EM BREVE: o cadastro de setembro (pacote fixo). */

import { num, pct } from './format'
import type {
  RedeContagemRecusada,
  RedeCrescimento,
  RedeCrescimentoRede,
  RedeMovimentoPeriodo,
  RedeQuedaContagem,
} from './types'

/** "smart_fit" -> "Smart Fit". O slug da rede vem do coletor. */
export function nomeRede(slug: string | null | undefined): string {
  if (!slug) return '—'
  return slug
    .replace(/[_-]+/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ')
}

/** "2026-11-01" -> "01/11". O que não é data ISO vira "—", nunca um pedaço do texto. */
export function diaMes(iso: string | null | undefined): string {
  return iso && /^\d{4}-\d{2}-\d{2}/.test(iso) ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : '—'
}

/** Inteiro com o sinal escrito ("+3", "-2", "0"): a cor sozinha não chega a todo leitor. */
export function comSinal(v: number): string {
  return `${v > 0 ? '+' : ''}${num(v)}`
}

export interface Janela {
  de: string | null
  ate: string | null
}

/** A janela que uma fonte do pacote cobre; com `confianca`, só a das fotos daquela confiança. */
export function janela(
  periodos: RedeMovimentoPeriodo[] | undefined,
  fonte: string,
  confianca?: string,
): Janela | null {
  const itens = (periodos ?? []).filter((p) => p.fonte === fonte && (!confianca || p.confianca === confianca))
  if (!itens.length) return null
  const des = itens.map((p) => p.de).filter((d): d is string => !!d).sort()
  const ates = itens.map((p) => p.ate).filter((d): d is string => !!d).sort()
  return { de: des[0] ?? null, ate: ates[ates.length - 1] ?? null }
}

/** "02/08 a 06/09"; com uma ponta só, "até 06/09" ou "desde 02/08". */
export function textoJanela(j: Janela | null): string {
  if (!j) return ''
  if (j.de && j.ate) return `${diaMes(j.de)} a ${diaMes(j.ate)}`
  if (j.ate) return `até ${diaMes(j.ate)}`
  if (j.de) return `desde ${diaMes(j.de)}`
  return ''
}

/** O período que as colunas de movimento somam: as fotos validadas, ou todas com o botão ligado. */
export function janelaDoCadastro(periodos: RedeMovimentoPeriodo[] | undefined, comCautela: boolean): Janela | null {
  return comCautela ? janela(periodos, 'cadastro') : janela(periodos, 'cadastro', 'alta')
}

/** A coluna de variação só existe com DUAS contagens semanais aceitas para comparar. */
export function temVariacao(m: RedeCrescimento | undefined): boolean {
  return m?.contagem_origem === 'semanal' && !!m.contagem?.data_anterior
}

export function rotuloContagem(m: RedeCrescimento): string {
  return m.data_contagem ? `Contagem de ${diaMes(m.data_contagem)}` : 'Contagem'
}

export function rotuloCadastro(m: RedeCrescimento, comCautela: boolean): string {
  const j = janelaDoCadastro(m.periodos, comCautela)
  return j ? `Cadastro de ${textoJanela(j)}` : 'Cadastro'
}

export type TomVariacao = 'mais' | 'menos' | 'zero' | 'vazio'

export interface CelulaVariacao {
  texto: string
  tom: TomVariacao
  titulo?: string
}

/** A célula de variação de uma rede. `novo`/`sumiu` são COBERTURA do coletor, nunca `+n`/`-n`. */
export function celulaVariacao(
  r: Pick<RedeCrescimentoRede, 'variacao' | 'variacao_status'>,
  dataAnterior: string | null | undefined,
): CelulaVariacao {
  const desde = dataAnterior ? ` desde ${diaMes(dataAnterior)}` : ''
  switch (r.variacao_status) {
    case 'variou':
    case 'estavel': {
      const v = r.variacao ?? 0
      return { texto: comSinal(v), tom: v > 0 ? 'mais' : v < 0 ? 'menos' : 'zero' }
    }
    case 'novo':
      return {
        texto: 'nova',
        tom: 'vazio',
        titulo: `Rede que entrou na contagem do coletor${desde}: é cobertura nova, não abertura.`,
      }
    case 'sumiu':
      return { texto: '—', tom: 'vazio', titulo: `Rede que saiu da contagem do coletor${desde}.` }
    default:
      return { texto: '—', tom: 'vazio' }
  }
}

/** Por que a linha mostra "—" nas colunas do cadastro (dica ao passar o mouse). */
export function motivoSemCadastro(r: Pick<RedeCrescimentoRede, 'rede' | 'sem_cadastro'>): string | null {
  if (r.sem_cadastro === 'teto_coletor') {
    return (
      `No cadastro de setembro, a ${nomeRede(r.rede)} estava travada no teto de 1.000 unidades do coletor; ` +
      'as aberturas e os fechamentos dela ficaram de fora.'
    )
  }
  if (r.sem_cadastro === 'fora_da_cobertura') return 'O coletor ainda não cobria esta rede no período do cadastro.'
  return null
}

/* ------------------------------- avisos ------------------------------- */

export interface AvisoCrescimento {
  tom: 'alerta' | 'info'
  texto: string
}

function listaDatas(itens: { execucao: string }[]): string {
  const ds = itens.map((r) => diaMes(r.execucao))
  return ds.length === 1 ? ds[0] : `${ds.slice(0, -1).join(', ')} e ${ds[ds.length - 1]}`
}

/** "a Selfit caiu de 231 para 119 unidades" — e a segunda rede, ou quantas mais. */
function fraseQueda(quedas: RedeQuedaContagem[]): string {
  const [primeira, segunda, ...resto] = quedas
  if (!primeira) return ''
  let t = `a ${nomeRede(primeira.rede)} caiu de ${num(primeira.antes)} para ${num(primeira.agora)} unidades`
  if (segunda && !resto.length) t += ` e a ${nomeRede(segunda.rede)}, de ${num(segunda.antes)} para ${num(segunda.agora)}`
  if (segunda && resto.length) t += `, e mais ${num(resto.length + 1)} redes caíram de forma brusca`
  return t
}

function motivoDaRecusa(r: RedeContagemRecusada): string {
  if (r.motivo === 'duplicada') return 'ela aparece duas vezes no histórico'
  if (r.redes.length) return `${fraseQueda(r.redes)}, sinal de coleta incompleta`
  if (r.queda_total_pct != null) return `o total caiu ${pct(r.queda_total_pct)}, sinal de coleta incompleta`
  return 'ela veio incompleta'
}

/** "da Selfit (de 231 para 150 unidades)"; com mais de uma rede, a primeira e quantas mais. */
function fraseConfirmada(c: NonNullable<RedeCrescimento['contagem']>): string {
  const [primeira, ...resto] = c.quedas_confirmadas
  if (primeira) {
    const quem = `da ${nomeRede(primeira.rede)} (de ${num(primeira.antes)} para ${num(primeira.agora)} unidades)`
    return resto.length ? `${quem} e de mais ${num(resto.length)} rede${resto.length > 1 ? 's' : ''}` : quem
  }
  if (c.queda_total_confirmada_pct != null) return `do total (${pct(c.queda_total_confirmada_pct)})`
  return 'na contagem'
}

/** Tudo o que a tela precisa avisar sobre a contagem antes da tabela. Lista vazia = semana normal. */
export function avisosDaContagem(m: RedeCrescimento | undefined): AvisoCrescimento[] {
  if (!m?.disponivel) return []
  const c = m.contagem
  if (m.contagem_origem !== 'semanal') {
    const motivo =
      c?.erro === 'ilegivel'
        ? 'O histórico semanal de contagem está ilegível neste ambiente'
        : c && !c.erro
          ? 'O histórico semanal ainda não tem contagem aceita'
          : 'O histórico semanal de contagem não está neste ambiente'
    const unidades = m.data_contagem
      ? `as unidades são da contagem de ${diaMes(m.data_contagem)}`
      : 'a coluna de unidades fica vazia'
    return [{ tom: 'alerta', texto: `${motivo}: ${unidades}, e a variação fica de fora.` }]
  }
  if (!c?.data) return []
  const avisos: AvisoCrescimento[] = []
  const data = c.data
  const depois = c.recusadas.filter((r) => r.execucao > data)
  const entre = c.recusadas.filter((r) => r.execucao < data)
  if (depois.length) {
    const ultima = depois[depois.length - 1]
    const abre =
      depois.length === 1
        ? `A contagem de ${diaMes(ultima.execucao)} ficou de fora: ${motivoDaRecusa(ultima)}.`
        : `As contagens de ${listaDatas(depois)} ficaram de fora (na de ${diaMes(ultima.execucao)}, ${motivoDaRecusa(ultima)}).`
    avisos.push({ tom: 'alerta', texto: `${abre} O card segue na de ${diaMes(data)}, a última aceita.` })
  }
  if (c.confirmada) {
    avisos.push({
      tom: 'info',
      texto:
        `A queda ${fraseConfirmada(c)} apareceu em duas contagens seguidas e foi aceita como real` +
        (c.data_anterior ? `; por isso a variação compara com ${diaMes(c.data_anterior)}.` : '.'),
    })
  } else if (entre.length && c.data_anterior) {
    avisos.push({
      tom: 'info',
      texto:
        `A variação compara com ${diaMes(c.data_anterior)} porque ` +
        (entre.length === 1
          ? `a contagem de ${diaMes(entre[0].execucao)} ficou de fora.`
          : `as contagens de ${listaDatas(entre)} ficaram de fora.`),
    })
  }
  if (!c.data_anterior) {
    avisos.push({ tom: 'info', texto: 'A variação aparece a partir da segunda contagem semanal aceita.' })
  }
  return avisos
}

/* ------------------------------- rodapé ------------------------------- */

/** O rodapé do card: de onde vem cada coluna e a data de cada fonte, tudo tirado do payload. */
export function rodapeCrescimento(m: RedeCrescimento, comCautela: boolean): string {
  const partes: string[] = []
  const c = m.contagem
  if (m.unidades_mapeadas) {
    let t = `Mercado mapeado: ${num(m.unidades_mapeadas)} unidades em ${num(m.redes_mapeadas ?? 0)} redes`
    if (m.variacao_total != null && c?.data_anterior) {
      t += ` (${comSinal(m.variacao_total)} desde ${diaMes(c.data_anterior)}, entre as redes das duas contagens)`
    }
    partes.push(`${t}.`)
  }
  if (m.contagem_origem === 'semanal') {
    partes.push(
      `Unidades: contagem semanal do coletor de ${diaMes(m.data_contagem)}, a mesma do relatório de domingo ` +
        'no Telegram; a contagem que chega com queda brusca é recusada, e o card fica na anterior.',
    )
  } else if (m.contagem_origem === 'pacote') {
    partes.push(`Unidades: contagem oficial de ${diaMes(m.data_contagem)}, do pacote de setembro.`)
  }
  if (m.tem_cadastro) {
    const alta = janela(m.periodos, 'cadastro', 'alta')
    const cautela = janela(m.periodos, 'cadastro', 'cautela')
    let t = `Aberturas, fechamentos e saldo: fotos do cadastro de ${textoJanela(alta) || 'setembro'}, validadas contra a contagem oficial`
    if (cautela) {
      t += comCautela
        ? `, mais a foto de ${textoJanela(cautela)}, que não foi validada`
        : ` (a foto de ${textoJanela(cautela)} entra só pelo botão)`
    }
    partes.push(`${t}; rede sem abertura nem fechamento aparece zerada.`)
    if (alta?.ate) partes.push(`"Em breve": anúncios que ainda não tinham inaugurado em ${diaMes(alta.ate)}.`)
    const teto = m.redes.find((r) => r.sem_cadastro === 'teto_coletor')
    if (teto) {
      partes.push(
        `A ${nomeRede(teto.rede)} fica fora de aberturas e fechamentos: no cadastro, ela estava travada no teto ` +
          'de 1.000 unidades do coletor.',
      )
    }
    if (m.redes.some((r) => r.sem_cadastro === 'fora_da_cobertura')) {
      partes.push('"—" no cadastro: rede que o coletor ainda não cobria naquele período.')
    }
    partes.push('Saída do site nem sempre é fechamento.')
  }
  partes.push('Estúdios boutique ficam fora (DEC-056).')
  return partes.join(' ')
}

/** Legenda da movimentação na ficha da unidade: até quando vai cada foto do pacote. */
export function legendaDoEntorno(periodos: RedeMovimentoPeriodo[] | undefined): string {
  const cadastro = janela(periodos, 'cadastro')
  const wellhub = janela(periodos, 'wellhub')
  const partes = [
    cadastro?.ate ? `do cadastro até ${diaMes(cadastro.ate)}` : null,
    wellhub?.ate ? `do Wellhub até ${diaMes(wellhub.ate)}` : null,
  ].filter((p): p is string => !!p)
  return partes.length ? `Fotos ${partes.join(' e ')}.` : ''
}
