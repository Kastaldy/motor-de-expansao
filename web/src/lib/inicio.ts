/**
 * Menu de entrada do piloto: a definicao dos 3 modos de analise, PURA.
 *
 * POR QUE VIVE AQUI E NAO NO .tsx. Mesmo motivo de `lib/mascara.ts` e `lib/faixas.ts`:
 * o vitest do piloto roda em ambiente `node` e so casa `src/**\/*.test.ts` — nao ha
 * testing-library. Entao a REGRA (quais modos existem, para onde cada um leva, em que
 * passo do funil o mapa deve abrir) fica aqui, testavel sem DOM, e `InicioScreen.tsx`
 * fica deliberadamente burro: so desenha o que esta declarado neste arquivo.
 *
 * ESCOPO DESTA ETAPA. Os 3 cards ja levam a telas REAIS que existem hoje — nada de
 * stub. As telas dedicadas de cada modo entram nas etapas seguintes; quando entrarem,
 * o unico ajuste aqui e' o campo `destino`.
 */

/** Os 3 modos que o operador escolhe na entrada. Identificadores SEM acento (regra do CLAUDE.md §2). */
export type ModoInicio = 'ponto' | 'regiao' | 'oportunidades'

/**
 * Telas que um card pode abrir hoje. E' um SUBCONJUNTO do `Tela` do `App.tsx`, e nao um
 * import dele de proposito: este modulo precisa continuar carregavel pelo vitest sem
 * arrastar React, deck.gl e o app inteiro para dentro do teste.
 */
export type DestinoInicio = 'mapa' | 'ponto'

export interface ModoDefinicao {
  id: ModoInicio
  /** Rotulo curto acima do titulo do card. */
  eyebrow: string
  titulo: string
  /** Uma frase: o que este modo responde. */
  resumo: string
  /** O que o card lista como entregavel. */
  bullets: readonly string[]
  /** Texto do botao. */
  chamada: string
  destino: DestinoInicio
  /**
   * Passo do funil (1..5) em que o mapa deve abrir quando o modo pede um recorte
   * especifico. `null` = abre como sempre abriu (passo 1).
   */
  passoAlvo: number | null
}

/** Menor e maior passo do funil narrativo servido por `/api/uf` e `/api/municipio`. */
export const PASSO_MIN = 1
export const PASSO_MAX = 5

export const MODOS: readonly ModoDefinicao[] = Object.freeze([
  Object.freeze({
    id: 'ponto',
    eyebrow: 'Um endereço',
    titulo: 'Analisar um ponto ou imóvel',
    resumo:
      'Você tem um imóvel na mão e quer ler o entorno dele: quem mora em volta, com que renda, e quantos concorrentes disputam o mesmo aluno.',
    // Só prometer o que a tela entrega HOJE. Break-even, payback e teto de aluguel
    // dependem de metragem e aluguel pedido, que este modo ainda não coleta — eles
    // seguem na tela de Viabilidade até a etapa que trouxer os dois campos para cá.
    bullets: Object.freeze([
      'Cole o link do Maps ou a coordenada',
      'População, renda e densidade no raio de 1,0 km',
      'Concorrentes e unidades Ultra em volta',
    ]),
    chamada: 'Analisar um ponto',
    destino: 'ponto',
    passoAlvo: null,
  }),
  Object.freeze({
    id: 'regiao',
    eyebrow: 'Um estado ou cidade',
    titulo: 'Explorar uma região',
    resumo:
      'Você ainda não tem endereço e quer ler o território: o mapa percorre as camadas do funil, do potencial socioeconômico até as cidades com mais espaço para abrir.',
    bullets: Object.freeze([
      'Funil de 5 camadas sobre o estado inteiro',
      'Drill-down do estado para o município',
      'Crescimento das cidades e onde há espaço',
    ]),
    chamada: 'Escolher um estado',
    destino: 'mapa',
    passoAlvo: null,
  }),
  Object.freeze({
    id: 'oportunidades',
    eyebrow: 'A fila pronta',
    titulo: 'Ver as melhores oportunidades',
    resumo:
      'Você quer a resposta direta: os hexágonos com mais alunos não atendidos, já filtrados por potencial socioeconômico, população e ausência de concorrente.',
    bullets: Object.freeze([
      'Fila dos 10 hexágonos com maior residual',
      'Só onde não há concorrente mapeado',
      'Ordenada por alunos não atendidos',
    ]),
    chamada: 'Ver a fila',
    destino: 'mapa',
    // Passo 5 = "Para onde crescer", a fila que ja roda em producao. NAO ligamos tambem
    // o filtro MELHORES: ele filtra os hexes DO MAPA por faixa M1, enquanto a fila e'
    // montada no servidor por `oferta_efetiva_disponivel` — os dois recortes sao
    // independentes, e combina-los esconderia do mapa itens que a fila continua
    // listando. Item some sem explicacao e' exatamente o que o modo nao pode fazer.
    passoAlvo: PASSO_MAX,
  }),
])

/** Busca defensiva: id desconhecido (payload velho, link antigo) devolve `null`. */
export function modoPorId(id: string): ModoDefinicao | null {
  return MODOS.find((m) => m.id === id) ?? null
}

/**
 * Passo do funil com que o mapa deve abrir para este modo, ja validado.
 * Passo fora de 1..5 e' tratado como ausente — o mapa cai no padrao em vez de pedir
 * ao backend um passo que nao existe.
 */
export function passoAlvoDoModo(id: ModoInicio): number | null {
  const passo = modoPorId(id)?.passoAlvo ?? null
  if (passo === null) return null
  if (!Number.isInteger(passo) || passo < PASSO_MIN || passo > PASSO_MAX) return null
  return passo
}
