/**
 * Menu de entrada do piloto: a definicao dos modos de analise, PURA.
 *
 * POR QUE VIVE AQUI E NAO NO .tsx. Mesmo motivo de `lib/mascara.ts` e `lib/faixas.ts`:
 * o vitest do piloto roda em ambiente `node` e so casa `src/**\/*.test.ts` — nao ha
 * testing-library. Entao a REGRA (quais modos existem, em que trilha, para onde cada um
 * leva) fica aqui, testavel sem DOM, e `InicioScreen.tsx` fica deliberadamente burro: so
 * desenha o que esta declarado neste arquivo.
 *
 * AS DUAS TRILHAS (2026-09-22). Ate' aqui o Inicio so' sabia perguntar "onde abrir" — os
 * 3 cards eram todos de EXPANSAO. Quem tinha acesso so' a Visao Executiva caia numa tela
 * literalmente vazia, porque `modosLiberados` nao encontrava um card sequer para ele (e
 * `telaInicial` so' o desviava na PRIMEIRA carga; a logo do Dock trazia de volta para o
 * vazio). Agora existe uma segunda trilha, OPERACOES, que pergunta "como vai o que ja'
 * abriu" e leva a' Executiva em tres profundidades. Quem tem as duas ve' uma pilula para
 * alternar; quem tem uma so' nao ve' pilula nenhuma — a escolha nao existe para ele.
 */

/**
 * Os modos que o operador escolhe na entrada. Identificadores SEM acento e sem hifen
 * (regra do CLAUDE.md §2; o teste de contrato exige `^[a-z]+$`).
 */
export type ModoInicio =
  // Trilha de EXPANSAO
  | 'oportunidades'
  | 'regiao'
  | 'ponto'
  // Trilha de OPERACOES
  | 'panorama'
  | 'recorte'
  | 'unidade'

/** As duas perguntas que a entrada sabe fazer. */
export type TrilhaInicio = 'expansao' | 'operacoes'

/**
 * Telas que um card pode abrir hoje. E' um SUBCONJUNTO do `Tela` do `App.tsx`, e nao um
 * import dele de proposito: este modulo precisa continuar carregavel pelo vitest sem
 * arrastar React, deck.gl e o app inteiro para dentro do teste.
 */
export type DestinoInicio = 'mapa' | 'ponto' | 'oportunidades' | 'executiva'

/**
 * Chave da ilustracao do card. Mora AQUI, e nao no `Artes.tsx` que a desenha, para o
 * teste do menu poder afirmar que todo card tem arte sem importar React.
 */
export type ArteInicio = 'brasil' | 'estado' | 'ponto' | 'painel' | 'rede' | 'ficha'

/**
 * SEGUNDO PASSO que um card faz ANTES de navegar (2026-09-22).
 *
 * A pergunta que o card faz e' sempre a MESMA que a tela de destino faria no primeiro
 * gesto — a diferenca e' que ela e' respondida aqui, e o operador cai no resultado em
 * vez de cair na tela vazia que pede a resposta.
 *
 * Vale nas DUAS trilhas:
 *   `recorte`  -> por que eixo cortar a carteira (estado, master ou consultor)
 *   `unidade`  -> qual unidade abrir a ficha
 *   `uf`       -> qual estado o mapa territorial abre (era a `Landing` do mapa)
 *   `endereco` -> que ponto analisar (era a caixa de colar do modo de ponto)
 *
 * `null` = o card navega direto. Sobrou para dois, e nos dois isso e' DELIBERADO: o
 * panorama da rede e' a rede inteira por definicao, e a fila nacional promete no proprio
 * texto "sem escolher estado antes" — pedir um recorte ali contradiria o card.
 */
export type SegundoPasso = 'recorte' | 'unidade' | 'uf' | 'endereco' | null

/** Por qual eixo a carteira pode ser recortada na entrada. */
export type DimensaoRecorte = 'uf' | 'master' | 'consultor'

export interface DimensaoDefinicao {
  id: DimensaoRecorte
  /** Texto do chip. */
  rotulo: string
  /** Rotulo do seletor que aparece depois de escolher a dimensao. */
  convite: string
}

/** Ordem dos chips. Estado primeiro: e' o recorte mais pedido e o de vocabulario menor. */
export const DIMENSOES_RECORTE: readonly DimensaoDefinicao[] = Object.freeze([
  Object.freeze({ id: 'uf', rotulo: 'Estado', convite: 'Escolha o estado' }),
  Object.freeze({ id: 'master', rotulo: 'Master', convite: 'Escolha o master' }),
  Object.freeze({ id: 'consultor', rotulo: 'Consultor', convite: 'Escolha o consultor' }),
])

export function dimensaoPorId(id: string): DimensaoDefinicao | null {
  return DIMENSOES_RECORTE.find((d) => d.id === id) ?? null
}

/**
 * O que o card entrega ao App quando o segundo passo termina, no recorte da trilha de
 * OPERACOES — e o que a Visao Executiva aplica na montagem. `null` = panorama.
 *
 * E' um tipo PROPRIO, e nao um ramo do `EntradaInicio` abaixo, para a Executiva nao
 * conseguir receber uma entrada de expansao: o compilador recusa `{tipo:'uf'}` ali.
 */
export type EntradaExecutiva =
  | { tipo: 'recorte'; dimensao: DimensaoRecorte; valor: string }
  | { tipo: 'unidade'; id: string }
  | null

/** O que os cards da trilha de EXPANSAO entregam. */
export type EntradaExpansao =
  | { tipo: 'uf'; uf: string }
  | { tipo: 'endereco'; texto: string }

/** Tudo que um card pode entregar ao App. */
export type EntradaInicio = NonNullable<EntradaExecutiva> | EntradaExpansao | null

/** Estreita para o que a Visao Executiva aceita; qualquer outra coisa vira `null`. */
export function entradaDaExecutiva(entrada: EntradaInicio): EntradaExecutiva {
  if (!entrada) return null
  return entrada.tipo === 'recorte' || entrada.tipo === 'unidade' ? entrada : null
}

/**
 * Guarda de borda: entrada malformada (valor vazio, dimensao desconhecida, id ou UF em
 * branco) vira `null` — o operador entra pelo caminho de sempre em vez de num recorte
 * que filtra por string vazia e devolve uma tela vazia sem explicar por que.
 */
export function entradaValida(entrada: EntradaInicio): EntradaInicio {
  if (!entrada) return null
  switch (entrada.tipo) {
    case 'unidade':
      return entrada.id.trim() ? entrada : null
    case 'uf':
      return entrada.uf.trim() ? entrada : null
    case 'endereco':
      return entrada.texto.trim() ? entrada : null
    case 'recorte':
      if (!dimensaoPorId(entrada.dimensao)) return null
      return entrada.valor.trim() ? entrada : null
    default:
      // Tipo desconhecido (payload velho, estado guardado de outra versao).
      return null
  }
}

export interface ModoDefinicao {
  id: ModoInicio
  trilha: TrilhaInicio
  /** Rotulo curto acima do titulo do card — a ESCALA ("Brasil", "Uma unidade"). */
  eyebrow: string
  titulo: string
  /** UMA linha: o que este card entrega. O card nao tem mais bullets. */
  linha: string
  arte: ArteInicio
  destino: DestinoInicio
  /**
   * Passo do funil (1..5) em que o mapa deve abrir quando o modo pede um recorte
   * especifico. `null` = abre como sempre abriu (passo 1).
   */
  passoAlvo: number | null
  /** So' faz sentido na trilha de operacoes; `null` no resto. */
  segundoPasso: SegundoPasso
}

/** Menor e maior passo do funil narrativo servido por `/api/uf` e `/api/municipio`. */
export const PASSO_MIN = 1
export const PASSO_MAX = 5

export const MODOS: readonly ModoDefinicao[] = Object.freeze([
  /* ---------------- Trilha: EXPANSAO -------------------------------------
     Ordem do mockup: do pais para o endereco. Ela mudou em 2026-09-22 (antes era
     ponto -> regiao -> oportunidades) para o eyebrow de cada card formar uma escala
     que se le' da esquerda para a direita: Brasil, Estado ou cidade, Endereco. */
  Object.freeze({
    id: 'oportunidades',
    trilha: 'expansao',
    eyebrow: 'Brasil',
    titulo: 'Ver as melhores oportunidades',
    /* O texto DESTE card ja mentiu duas vezes, nas duas direcoes: prometeu hexagono
       enquanto a tela entregava municipio, e depois prometeu cidade enquanto a tela
       passava a entregar o ranking nacional por hexagono. Ele muda no MESMO commit da
       rota, nunca num commit de acompanhamento. */
    linha: 'A fila nacional de hexágonos, sem escolher estado antes.',
    arte: 'brasil',
    destino: 'oportunidades',
    /* Desde que o modo ganhou tela propria (`OportunidadesScreen`), a fila NAO e' mais
       um passo do mapa: ela e' a tela. */
    passoAlvo: null,
    segundoPasso: null,
  }),
  Object.freeze({
    id: 'regiao',
    trilha: 'expansao',
    eyebrow: 'Estado ou cidade',
    titulo: 'Explorar uma região',
    linha: 'O funil de 5 camadas até os municípios com espaço.',
    arte: 'estado',
    destino: 'mapa',
    passoAlvo: null,
    /* A `Landing` do mapa ja' fazia exatamente esta pergunta ao chegar. O card a faz
       antes, e o mapa abre no estado escolhido em vez de na tela de escolher estado. */
    segundoPasso: 'uf',
  }),
  Object.freeze({
    id: 'ponto',
    trilha: 'expansao',
    eyebrow: 'Endereço',
    titulo: 'Analisar um ponto ou imóvel',
    linha: 'Cole o link do Maps e leia o entorno e a viabilidade.',
    arte: 'ponto',
    destino: 'ponto',
    passoAlvo: null,
    /* Mesma logica: a caixa de colar do modo de ponto sobe para o card. O texto vai
       CRU para o `PontoScreen`, que ja' sabe classificar e resolver os quatro casos
       (coordenada, link longo, link curto, endereco) — ver `lib/entrada-ponto.ts`. */
    segundoPasso: 'endereco',
  }),

  /* ---------------- Trilha: OPERACOES ------------------------------------
     Os tres levam a' MESMA tela (a Visao Executiva), e isso e' deliberado: ela ja' e'
     carteira + mapa + ficha num scroller so'. O que o card escolhe e' por ONDE se
     entra nela — `segundoPasso` + `EntradaExecutiva`. Card que prometesse tela nova
     aqui estaria mentindo. */
  Object.freeze({
    id: 'panorama',
    trilha: 'operacoes',
    eyebrow: 'Rede inteira',
    titulo: 'Panorama das unidades',
    linha: 'Todas as unidades no mapa, priorizadas por atenção.',
    arte: 'painel',
    destino: 'executiva',
    passoAlvo: null,
    segundoPasso: null,
  }),
  Object.freeze({
    id: 'recorte',
    trilha: 'operacoes',
    eyebrow: 'Estado ou franqueado',
    titulo: 'Recortar a rede',
    linha: 'Só as unidades de uma região ou de um master.',
    arte: 'rede',
    destino: 'executiva',
    passoAlvo: null,
    segundoPasso: 'recorte',
  }),
  Object.freeze({
    id: 'unidade',
    trilha: 'operacoes',
    eyebrow: 'Uma unidade',
    titulo: 'Abrir a ficha da unidade',
    linha: 'Busque pelo nome e veja a unidade e o entorno dela.',
    arte: 'ficha',
    destino: 'executiva',
    passoAlvo: null,
    segundoPasso: 'unidade',
  }),
])

/** Ordem em que as trilhas aparecem na pilula. */
export const ORDEM_TRILHAS: readonly TrilhaInicio[] = Object.freeze(['expansao', 'operacoes'])

export interface TrilhaDefinicao {
  id: TrilhaInicio
  /** Texto do botao da pilula. */
  rotulo: string
  /** Subtitulo do hero quando ESTA trilha esta' ativa. */
  subtitulo: string
}

export const TRILHAS: Readonly<Record<TrilhaInicio, TrilhaDefinicao>> = Object.freeze({
  expansao: Object.freeze({
    id: 'expansao',
    rotulo: 'Expandir a rede',
    subtitulo:
      'Escolha em que escala você quer olhar o território: do Brasil inteiro até um endereço.',
  }),
  operacoes: Object.freeze({
    id: 'operacoes',
    rotulo: 'Acompanhar a rede',
    subtitulo:
      'Escolha em que escala você quer olhar a rede: do panorama completo até a ficha de uma unidade.',
  }),
})

/**
 * Subtitulo do hero quando o usuario tem as DUAS trilhas e ainda nao escolheu — na
 * pratica, o texto que acompanha a pilula. Fala das duas perguntas sem nomear escala,
 * porque as escalas das duas trilhas sao diferentes.
 */
export const SUBTITULO_AMBAS =
  'Escolha o que você quer fazer e em que escala: do panorama completo até um único ponto.'

/** Busca defensiva: id desconhecido (payload velho, link antigo) devolve `null`. */
export function modoPorId(id: string): ModoDefinicao | null {
  return MODOS.find((m) => m.id === id) ?? null
}

/** Os cards de uma trilha, na ordem declarada. */
export function modosDaTrilha(
  trilha: TrilhaInicio,
  modos: readonly ModoDefinicao[] = MODOS,
): readonly ModoDefinicao[] {
  return modos.filter((m) => m.trilha === trilha)
}

/**
 * Trilhas que sobraram depois do controle de acesso, na ordem da pilula. Uma trilha so'
 * existe se ALGUM card dela sobreviveu — quem nao tem a Executiva nao ve' "Acompanhar a
 * rede", e quem so' tem a Executiva nao ve' "Expandir a rede".
 */
export function trilhasDisponiveis(modos: readonly ModoDefinicao[]): readonly TrilhaInicio[] {
  return ORDEM_TRILHAS.filter((t) => modos.some((m) => m.trilha === t))
}

/**
 * Trilha com que o Inicio deve abrir. Com as duas, abre na de EXPANSAO — e' a pergunta
 * que o produto existe para responder, e a outra fica a um clique. Sem nenhuma (usuario
 * sem card algum), devolve `null` e a tela mostra a explicacao em vez de cards.
 */
export function trilhaInicial(modos: readonly ModoDefinicao[]): TrilhaInicio | null {
  return trilhasDisponiveis(modos)[0] ?? null
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
