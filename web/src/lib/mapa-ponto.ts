import type { PontoPayload, PontoVizinho } from './types'

/**
 * Regras do mapa do modo de ponto.
 *
 * POR QUE ISTO VIVE NUMA LIB E NAO NO COMPONENTE. O vitest roda em ambiente `node` e so'
 * casa arquivos `.test.ts` dentro de `src/` — componente React nao entra na suite. Entao
 * a REGRA (o que da' para desenhar, em que escala de cor, para onde a camera vai, e o que
 * declarar quando nao ha' o que desenhar) mora aqui, testada, e o `.tsx` fica burro.
 *
 * Este modulo nasceu quando a Analise de ponto passou a ABRIR no mapa: antes o mapa era
 * uma caixa de 300px dentro da ficha e podia assumir que sempre havia um ponto resolvido.
 * Agora ele e' a tela, e precisa de enquadramento valido com zero ponto colado.
 */

/** Vizinho que o mapa consegue desenhar: sem `hex_id` nao existe celula H3 para pintar. */
export type VizinhoDesenhavel = PontoVizinho & { hex_id: string }

export interface Vista {
  longitude: number
  latitude: number
  zoom: number
}

/**
 * Camera de partida, antes de existir qualquer ponto: o Brasil inteiro.
 *
 * Nao e' enfeite. Como a tela abre no mapa, sem esta vista o deck.gl montaria em
 * `lat/lng` indefinidos — e o que aparece e' um cinza sem explicacao, que se le como
 * defeito de carregamento.
 */
export const VISTA_BRASIL: Vista = { longitude: -52.9, latitude: -14.5, zoom: 3.4 }

/** Enquadramento do entorno — o mesmo do mini-mapa que esta tela substituiu. */
export const ZOOM_PONTO = 12.4

/** Para onde a camera voa quando um ponto e' resolvido. */
export function vistaDoPonto(lat: number, lng: number): Vista {
  return { longitude: lng, latitude: lat, zoom: ZOOM_PONTO }
}

/**
 * Capacidade default de uma unidade, em alunos.
 *
 * Espelha `CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS` do motor (CLAUDE.md §4) — a MESMA
 * referencia que o `score_oportunidade_residual` usa. Manter as duas iguais e' o que
 * permite a cor do mapa falar a mesma lingua do score, sem normalizacao inventada aqui.
 */
export const CAPACIDADE_UNIDADE_ALUNOS = 2500

/**
 * Residual em ALUNOS -> posicao 0-100 na rampa de 10 faixas do produto.
 *
 * O clamp inferior existe porque residual pode chegar NEGATIVO (oferta instalada maior
 * que o mercado potencial do hexagono). Sem ele, a faixa negativa cairia fora da rampa e
 * o hexagono mais saturado de todos pintaria de cor indefinida — justo o caso que o
 * operador mais precisa enxergar.
 */
export function faixaDoResidual(residual: number | null | undefined): number | null {
  if (residual == null || !Number.isFinite(residual)) return null
  return Math.min(100, Math.max(0, (residual / CAPACIDADE_UNIDADE_ALUNOS) * 100))
}

/** So' os vizinhos com celula H3: o resto nao tem o que pintar. */
export function vizinhosDesenhaveis(
  vizinhos: readonly PontoVizinho[] | null | undefined,
): VizinhoDesenhavel[] {
  if (!vizinhos) return []
  return vizinhos.filter(
    (v): v is VizinhoDesenhavel => typeof v.hex_id === 'string' && v.hex_id.length > 0,
  )
}

/**
 * Frase de ultimo recurso quando nem o servidor disse por que a camada faltou.
 *
 * Era a unica frase possivel antes deste modulo existir — ficava fixa no componente.
 */
export const MOTIVO_SEM_MERCADO_PADRAO =
  'O mapa colore os hexágonos por residual, que vem da camada de mercado — e ela não está montada neste servidor.'

/**
 * O que declarar quando o mapa nao tem hexagono nenhum para colorir.
 *
 * Regra da casa: bloco sem dado DECLARA o motivo por extenso, nunca some em silencio.
 * O motivo do SERVIDOR tem prioridade porque e' ele quem sabe por que a camada faltou —
 * a cadeia de dados degrada de proposito (staging ausente devolve vazio sem excecao), e
 * um mapa que ficasse so' com o basemap seria lido como bug de rede.
 *
 * Devolve `null` quando nao ha' nada a declarar: sem ficha (a tela ainda esta pedindo o
 * ponto) ou com hexagonos desenhaveis (o mapa se explica sozinho).
 */
export function motivoSemHexagonos(ficha: PontoPayload | null | undefined): string | null {
  if (!ficha) return null
  if (vizinhosDesenhaveis(ficha.vizinhos).length > 0) return null
  const doServidor = ficha.mercado?.motivo
  return doServidor && doServidor.trim() ? doServidor : MOTIVO_SEM_MERCADO_PADRAO
}
