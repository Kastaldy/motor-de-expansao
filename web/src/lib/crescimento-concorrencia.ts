/* Crescimento da concorrência — os textos, as datas e as células do card, montados do payload.

   O card juntava duas fontes com as datas escritas no código ("02/08 a 06/09", "31/08 a 12/09",
   "contagem oficial de 06/09") e ficou oito domingos parado sem que nada na tela denunciasse
   (diagnóstico de 04/11/2026). Daqui em diante toda data visível sai do dado, e as regras de
   texto e de célula moram aqui, em funções puras testadas sem DOM (o vitest roda em `node`).

   As duas fontes, cada uma com a sua data:
   - UNIDADES e VARIAÇÃO: contagem semanal do coletor (a do relatório de domingo no Telegram),
     julgada POR REDE contra a última contagem boa de cada uma; a rede não recoletada, ou com
     salto brusco ainda não confirmado, fica com o número anterior, e a tela diz qual e por quê;
   - ABERTURAS, FECHAMENTOS, SALDO e EM BREVE: o cadastro de setembro (pacote fixo). */

import { num, pct } from './format'
import type {
  RedeContagemRecusada,
  RedeContagemSemanal,
  RedeCrescimento,
  RedeCrescimentoRede,
  RedeMovimentoPeriodo,
  RedeSaltoContagem,
} from './types'

/** Decisão de 05/11/2026: o card é nacional de propósito, e diz isso antes da tabela. */
export const AVISO_NACIONAL = 'Visão nacional das redes concorrentes: este card não muda com os filtros do topo da página.'

/** Com a contagem mais velha que isto (em dias), a tela avisa que o histórico pode ter parado. */
export const DIAS_CONTAGEM_VELHA = 9

/** A data de HOJE no fuso de quem abre a página, em ISO ("2026-11-10"). Nunca `toISOString()`:
 *  ele dá a data em UTC, que em Brasília já vira o dia seguinte às 21h. */
export function hojeLocal(agora: Date = new Date()): string {
  const dois = (n: number) => String(n).padStart(2, '0')
  return `${agora.getFullYear()}-${dois(agora.getMonth() + 1)}-${dois(agora.getDate())}`
}

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

/** "A Selfit"; o nome que já começa por "A " fica como está ("A Fitness", nunca "A A Fitness"). */
export function comArtigo(slug: string | null | undefined): string {
  const nome = nomeRede(slug)
  return /^A\s/.test(nome) ? nome : `A ${nome}`
}

const ISO = /^\d{4}-\d{2}-\d{2}/

/** "2026-11-01" -> "01/11". O que não é data ISO vira "—", nunca um pedaço do texto. */
export function diaMes(iso: string | null | undefined): string {
  return iso && ISO.test(iso) ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : '—'
}

/** "2026-11-01" -> "01/11/2026", para quando o ano importa (contagem velha). */
export function diaMesAno(iso: string | null | undefined): string {
  return iso && ISO.test(iso) ? `${diaMes(iso)}/${iso.slice(0, 4)}` : '—'
}

/** Dias corridos de `de` até `ate` (datas ISO), ou `null` se alguma não for data. */
export function diasEntre(de: string | null | undefined, ate: string | null | undefined): number | null {
  if (!de || !ate || !ISO.test(de) || !ISO.test(ate)) return null
  const dia = (iso: string) => Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)))
  return Math.round((dia(ate) - dia(de)) / 86_400_000)
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

/** A coluna de variação só existe com DUAS contagens semanais para comparar. */
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

/* ------------------------------- células ------------------------------- */

/** `info` = rótulo com significado (precisa de contraste); `vazio` = "—" sem dado. */
export type TomVariacao = 'mais' | 'menos' | 'zero' | 'info' | 'vazio'

export interface CelulaVariacao {
  texto: string
  tom: TomVariacao
  titulo?: string
}

/** A célula de variação de uma rede. Cobertura nova e contagem segurada aparecem ESCRITAS na
 *  célula (e não só na dica do mouse, que não existe no celular): "nova", "segurada"... */
export function celulaVariacao(
  r: Pick<RedeCrescimentoRede, 'variacao' | 'variacao_status' | 'lido'>,
  dataAnterior: string | null | undefined,
): CelulaVariacao {
  const desde = dataAnterior ? ` desde ${diaMes(dataAnterior)}` : ''
  const numero = (v: number): Pick<CelulaVariacao, 'texto' | 'tom'> => ({
    texto: comSinal(v),
    tom: v > 0 ? 'mais' : v < 0 ? 'menos' : 'zero',
  })
  switch (r.variacao_status) {
    case 'variou':
    case 'estavel':
      return numero(r.variacao ?? 0)
    case 'confirmada':
      return {
        ...numero(r.variacao ?? 0),
        titulo: 'Salto brusco que se manteve numa coleta mais nova: entrou nesta contagem.',
      }
    case 'novo':
      return {
        texto: 'nova',
        tom: 'info',
        titulo: `Rede que entrou na contagem do coletor${desde}: é cobertura nova, não abertura.`,
      }
    case 'segurada':
      return {
        texto: 'segurada',
        tom: 'info',
        titulo:
          r.lido != null
            ? `O coletor leu ${num(r.lido)} unidades, um salto brusco: fica a última contagem boa até a próxima coleta confirmar.`
            : 'Salto brusco: fica a última contagem boa até a próxima coleta confirmar.',
      }
    case 'nao_recoletada':
      return {
        texto: 'sem coleta',
        tom: 'info',
        titulo: 'O coletor não recoletou esta rede nesta semana: fica a última contagem, sem variação.',
      }
    case 'ausente':
      return { texto: 'ausente', tom: 'info', titulo: 'A rede não veio nesta contagem: fica a última por uma semana.' }
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

export type ColunaCadastro = 'aberturas' | 'fechamentos' | 'saldo' | 'em_breve'

export interface CelulaCadastro {
  /** `sem_leitura` = "—": a linha não tem leitura de cadastro, e zero afirmaria que não se mexeu */
  tipo: 'numero' | 'zero' | 'sem_leitura'
  valor: number
  titulo?: string
}

/** O que cada coluna do cadastro mostra numa linha. `aberturas`, `fechamentos` e `saldo` já vêm
 *  com o botão de cautela aplicado. O "Em breve" vem de outro arquivo do pacote, e a Smart Fit
 *  TEM leitura nele: só a rede fora da cobertura perde o número ali. */
export function celulaCadastro(
  r: Pick<RedeCrescimentoRede, 'rede' | 'sem_cadastro' | 'aberturas' | 'fechamentos' | 'saldo' | 'em_breve'>,
  coluna: ColunaCadastro,
): CelulaCadastro {
  const motivo = motivoSemCadastro(r)
  const valor = r[coluna]
  if (coluna === 'em_breve') {
    if (valor) return { tipo: 'numero', valor }
    return r.sem_cadastro === 'fora_da_cobertura'
      ? { tipo: 'sem_leitura', valor: 0, titulo: motivo ?? undefined }
      : { tipo: 'zero', valor: 0 }
  }
  if (motivo) return { tipo: 'sem_leitura', valor: 0, titulo: motivo }
  return valor ? { tipo: 'numero', valor } : { tipo: 'zero', valor: 0 }
}

/* ------------------------------- avisos ------------------------------- */

export interface AvisoCrescimento {
  tom: 'alerta' | 'info'
  texto: string
}

function plural(n: number, um: string, varios: string): string {
  return n === 1 ? um : varios
}

/** "Selfit, Panobianco e Bluefit"; acima de `max`, "Selfit, Panobianco, Bluefit e mais 8". */
function listaNomes(redes: string[], max = 3): string {
  const nomes = redes.map(nomeRede)
  if (nomes.length <= max) return nomes.length === 1 ? nomes[0] : `${nomes.slice(0, -1).join(', ')} e ${nomes[nomes.length - 1]}`
  return `${nomes.slice(0, max).join(', ')} e mais ${num(nomes.length - max)}`
}

/** Sujeito da frase: "A Selfit" com uma rede só, a lista de nomes com várias. */
function quem(redes: string[]): string {
  return redes.length === 1 ? comArtigo(redes[0]) : listaNomes(redes)
}

function listaDatas(itens: { execucao: string }[]): string {
  const ds = itens.map((r) => diaMes(r.execucao))
  return ds.length === 1 ? ds[0] : `${ds.slice(0, -1).join(', ')} e ${ds[ds.length - 1]}`
}

function motivoDaRecusa(r: RedeContagemRecusada): string {
  if (r.motivo === 'duplicada') return 'ela aparece duas vezes no histórico'
  if (r.queda_total_pct != null) {
    return `a soma das redes recoletadas caiu ${pct(r.queda_total_pct)}, sinal de coleta incompleta`
  }
  return 'ela veio incompleta'
}

/** "de 233 para 119" — o salto de uma rede, sem a palavra "unidades" (quem chama decide). */
function deAte(s: RedeSaltoContagem): string {
  return `de ${s.antes != null ? num(s.antes) : '—'} para ${num(s.agora)}`
}

function avisoSeguradas(seguradas: RedeSaltoContagem[], data: string): AvisoCrescimento {
  const fim = 'fica com a última contagem boa até a próxima coleta confirmar.'
  if (seguradas.length === 1) {
    const s = seguradas[0]
    const verbo = s.direcao === 'queda' ? 'caiu' : 'subiu'
    const leitura =
      s.direcao === 'queda' ? 'sinal de coleta incompleta' : 'um salto que costuma ser ajuste do coletor, e não abertura'
    const desde = s.desde && s.desde < data ? ` (segurada desde ${diaMes(s.desde)})` : ''
    return {
      tom: 'alerta',
      texto: `${comArtigo(s.rede)} ${verbo} ${deAte(s)} unidades na contagem de ${diaMes(data)}${desde}, ${leitura}: ela ${fim}`,
    }
  }
  const exemplos = seguradas.slice(0, 3).map((s) => `${nomeRede(s.rede)} (${deAte(s)})`)
  const resto = seguradas.length > 3 ? ` e mais ${num(seguradas.length - 3)}` : ''
  const lista = resto ? `${exemplos.join(', ')}${resto}` : `${exemplos.slice(0, -1).join(', ')} e ${exemplos[exemplos.length - 1]}`
  return {
    tom: 'alerta',
    texto: `${num(seguradas.length)} redes tiveram salto brusco na contagem de ${diaMes(data)} e cada uma ${fim} São elas: ${lista}.`,
  }
}

function avisoConfirmadas(confirmadas: RedeSaltoContagem[]): AvisoCrescimento {
  if (confirmadas.length === 1) {
    const s = confirmadas[0]
    const qual = s.direcao === 'queda' ? 'A queda' : 'O salto'
    return {
      tom: 'info',
      texto: `${qual} da ${nomeRede(s.rede)} (${deAte(s)} unidades) se manteve numa coleta mais nova e entrou nesta contagem.`,
    }
  }
  return {
    tom: 'info',
    texto: `${num(confirmadas.length)} saltos bruscos se mantiveram numa coleta mais nova e entraram nesta contagem: ${listaNomes(confirmadas.map((s) => s.rede))}.`,
  }
}

/** Tudo o que a tela precisa avisar antes da tabela. Lista vazia = semana normal.
 *  `hoje` (data ISO) liga o aviso de contagem velha: sem ele, um histórico que parou de chegar
 *  deixaria o card parado de novo sem denúncia nenhuma. */
export function avisosDaContagem(m: RedeCrescimento | undefined, hoje?: string): AvisoCrescimento[] {
  if (!m?.disponivel) return []
  const c = m.contagem
  const avisos: AvisoCrescimento[] = []
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
    avisos.push({ tom: 'alerta', texto: `${motivo}: ${unidades}, e a variação fica de fora.` })
  } else if (c?.data) {
    avisos.push(...avisosDaSemana(c, c.data, hoje))
  }
  if (!m.tem_cadastro) {
    avisos.push({
      tom: 'info',
      texto: 'O cadastro de aberturas e fechamentos (pacote de setembro) não está neste ambiente: o card mostra só a contagem semanal.',
    })
  }
  return avisos
}

function avisosDaSemana(c: RedeContagemSemanal, data: string, hoje?: string): AvisoCrescimento[] {
  const avisos: AvisoCrescimento[] = []
  // Duas idades diferentes: a do histórico (a última execução que CHEGOU) e a do card (a última
  // contagem que ENTROU). Medir só a do card mandaria procurar uma falha de cópia quando o
  // histórico chegou e a execução é que ficou de fora.
  const ultimaExecucao = c.execucao_mais_recente && c.execucao_mais_recente > data ? c.execucao_mais_recente : data
  const idadeHistorico = diasEntre(ultimaExecucao, hoje)
  const idadeCard = diasEntre(data, hoje)
  if (idadeHistorico != null && idadeHistorico > DIAS_CONTAGEM_VELHA) {
    avisos.push({
      tom: 'alerta',
      texto: `A execução mais recente do histórico semanal é de ${diaMesAno(ultimaExecucao)}, de ${num(idadeHistorico)} dias atrás: o histórico pode ter parado de chegar ao site.`,
    })
  } else if (idadeCard != null && idadeCard > DIAS_CONTAGEM_VELHA) {
    avisos.push({
      tom: 'alerta',
      texto: `Nenhuma contagem nova entra no card desde ${diaMesAno(data)}, há ${num(idadeCard)} dias: o histórico chega, mas as execuções seguintes ficaram de fora.`,
    })
  }
  const depois = c.recusadas.filter((r) => r.execucao > data)
  const entre = c.recusadas.filter((r) => r.execucao < data)
  if (depois.length) {
    const ultima = depois[depois.length - 1]
    const abre =
      depois.length === 1
        ? `A contagem de ${diaMes(ultima.execucao)} ficou de fora: ${motivoDaRecusa(ultima)}.`
        : `As contagens de ${listaDatas(depois)} ficaram de fora (na de ${diaMes(ultima.execucao)}, ${motivoDaRecusa(ultima)}).`
    avisos.push({ tom: 'alerta', texto: `${abre} O card segue na de ${diaMes(data)}.` })
  }
  const semColeta = (c.sem_coleta_nova ?? []).filter((e) => e > data)
  if (semColeta.length) {
    const abre =
      semColeta.length === 1
        ? `A execução de ${diaMes(semColeta[0])} não trouxe coleta nova`
        : `As execuções de ${listaDatas(semColeta.map((execucao) => ({ execucao })))} não trouxeram coleta nova`
    avisos.push({
      tom: 'alerta',
      texto: `${abre}: nenhuma rede foi recoletada. O card segue na contagem de ${diaMes(data)}.`,
    })
  }
  if (c.seguradas.length) avisos.push(avisoSeguradas(c.seguradas, data))
  if (c.confirmadas.length) avisos.push(avisoConfirmadas(c.confirmadas))
  if (c.total_confirmado) {
    avisos.push({ tom: 'info', texto: 'A queda do total se manteve por duas contagens seguidas, e esta entrou.' })
  }
  if (c.nao_recoletadas.length) {
    const n = c.nao_recoletadas.length
    avisos.push({
      tom: 'info',
      texto:
        n === 1
          ? `${comArtigo(c.nao_recoletadas[0])} não foi recoletada nesta semana: fica com a última contagem, sem variação.`
          : `${num(n)} redes não foram recoletadas nesta semana e ficam com a última contagem, sem variação: ${listaNomes(c.nao_recoletadas)}.`,
    })
  }
  if (c.ausentes.length) {
    avisos.push({
      tom: 'info',
      texto: `${quem(c.ausentes)} não ${plural(c.ausentes.length, 'veio', 'vieram')} na contagem de ${diaMes(data)}: ${plural(c.ausentes.length, 'fica', 'ficam')} com a última contagem por uma semana.`,
    })
  }
  if (c.removidas.length) {
    avisos.push({
      tom: 'info',
      texto: `${quem(c.removidas)} ${plural(c.removidas.length, 'saiu', 'saíram')} da contagem do coletor (não ${plural(c.removidas.length, 'veio', 'vieram')} duas semanas seguidas).`,
    })
  }
  if (entre.length && c.data_anterior) {
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
    avisos.push({ tom: 'info', texto: 'A variação aparece a partir da segunda contagem semanal.' })
  }
  if (c.linhas_sem_data) {
    avisos.push({
      tom: 'info',
      texto: `${num(c.linhas_sem_data)} ${plural(c.linhas_sem_data, 'linha do histórico veio', 'linhas do histórico vieram')} fora do formato (sem data ou com campos a mais) e ${plural(c.linhas_sem_data, 'ficou', 'ficaram')} de fora.`,
    })
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
      `Unidades: contagem semanal do coletor de ${diaMes(m.data_contagem)}, a mesma do relatório de domingo no ` +
        'Telegram, que já inclui as unidades anunciadas ("Em breve"). Cada rede é comparada com a última contagem ' +
        'boa dela: a que não foi recoletada, ou que deu um salto brusco ainda não confirmado, fica com a contagem ' +
        'anterior e sem variação.',
    )
    if (temVariacao(m)) partes.push('A variação mistura aberturas, anúncios e ajustes do coletor.')
    if (m.redes.some((r) => r.variacao_status === 'novo')) {
      partes.push('"nova": rede que o coletor passou a contar; não é abertura.')
    }
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
        `${comArtigo(teto.rede)} fica fora de aberturas e fechamentos: no cadastro, ela estava travada no teto ` +
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
