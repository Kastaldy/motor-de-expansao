/**
 * Captura do mapa como imagem, para o mapa entrar no PDF.
 *
 * POR QUE PRINT, E NAO RENDER NO SERVIDOR. O motor tem um renderizador de mapa (o do
 * Relatorio Pontual), mas ele foi feito para o raio de 1 km de um PONTO: medido em
 * 2026-08-13, gasta ~7,8 s so' carregando os setores censitarios de UMA coordenada, e com
 * o raio dele um hexagono de ~5 km2 sai praticamente vazio — dos 6 concorrentes do
 * entorno, 5 ficavam fora do circulo. Capturar a tela custa perto de zero, enquadra o que
 * o operador escolheu e garante que o relatorio mostre EXATAMENTE o que ele viu, que e' a
 * classe de divergencia que este ciclo passou o dia inteiro corrigindo.
 *
 * DOIS CANVAS, NAO UM. O mapa e' `<DeckGL><Map/></DeckGL>`: o basemap do MapLibre pinta
 * num canvas e as camadas do deck.gl noutro, empilhados. Capturar so' um devolve ou ruas
 * sem hexagono, ou hexagono flutuando no vazio.
 */

/**
 * Empilha os canvas do mapa num so', na ORDEM EM QUE APARECEM.
 *
 * A ordem e' a do DOM, que e' a ordem de pintura: basemap primeiro, camadas por cima.
 * Inverte-la esconderia o mapa sob as ruas.
 *
 * Canvas de tamanho zero e' PULADO em vez de derrubar a captura: durante o remount que
 * liga o `preserveDrawingBuffer` um dos dois pode ser medido antes de existir de fato.
 *
 * Devolve `null` quando nao ha' nada capturavel — melhor um slide sem mapa, declarando a
 * ausencia, do que um retangulo preto no meio do relatorio.
 */
export function comporCanvas(
  fontes: readonly HTMLCanvasElement[],
  destino: HTMLCanvasElement,
  { tipo = 'image/png', qualidade }: { tipo?: string; qualidade?: number } = {},
): string | null {
  const uteis = fontes.filter((c) => c.width > 0 && c.height > 0)
  if (!uteis.length) return null

  const largura = Math.max(...uteis.map((c) => c.width))
  const altura = Math.max(...uteis.map((c) => c.height))
  if (!(largura > 0) || !(altura > 0)) return null

  destino.width = largura
  destino.height = altura
  const ctx = destino.getContext('2d')
  if (!ctx) return null

  for (const fonte of uteis) {
    // Cada canvas e' esticado para o quadro comum: com `devicePixelRatio` diferente entre
    // eles (acontece em tela externa), empilhar 1:1 desalinharia as camadas.
    ctx.drawImage(fonte, 0, 0, largura, altura)
  }
  return destino.toDataURL(tipo, qualidade)
}

/**
 * Quanto esperar depois de mandar o mapa voar, antes de capturar.
 *
 * Duas esperas somadas: a animacao do voo e o carregamento dos tiles do novo
 * enquadramento. Capturar antes rende um quadro borrado ou cinza — e como sao ate' 5
 * hexagonos em sequencia, o erro se repetiria em todos.
 *
 * E' folga deliberada, nao medicao: o `idle` do MapLibre nao esta' exposto aqui, e errar
 * para mais custa segundos, enquanto errar para menos custa um relatorio com mapa cinza.
 */
export const ESPERA_VOO_MS = 900
export const ESPERA_TILES_MS = 700

export function esperaDeCaptura(): number {
  return ESPERA_VOO_MS + ESPERA_TILES_MS
}
