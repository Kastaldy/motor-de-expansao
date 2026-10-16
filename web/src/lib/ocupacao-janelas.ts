/**
 * Onde estão as janelas ABERTAS do mapa — e quanto o trilho do canto inferior esquerdo
 * precisa andar para não ficar embaixo delas.
 *
 * Existe por um pedido do Vinicius (2026-10-14): "quando a caixa da esquerda é criada
 * (tanto hexágono, quanto ponto), as opções por baixo dela ficam ocultas". A ficha nasce
 * à esquerda, de cima até perto do stepper, e o trilho (Selecionar ponto, régua, Analisar
 * geometria, camadas, legenda) mora exatamente nessa faixa — com a janela por cima
 * (`zIndex` 26 contra 10), as ferramentas sumiam enquanto a ficha estivesse aberta, que é
 * justamente quando o operador quer marcar o próximo ponto.
 *
 * A saída escolhida é o TRILHO andar, não a janela encolher: o trilho tem ~300px de altura
 * com o painel de camadas aberto, e uma janela que parasse acima dele viraria uma fresta.
 *
 * O registro é de MÓDULO, e não estado do React, pelo mesmo motivo da pilha de Esc da
 * `JanelaFicha`: as janelas vivem em telas diferentes (a do ponto no `PontoScreen`, as do
 * hexágono no `MapScreen`) e o trilho precisa enxergar todas na mesma lista.
 *
 * Coordenadas em pixels da TELA (`clientX/clientY`), para que janelas de contêineres
 * diferentes e o trilho se comparem sem conversão.
 */

export interface Retangulo {
  esquerda: number
  topo: number
  largura: number
  altura: number
}

/** Folga entre a borda direita da janela e o trilho deslocado. */
export const FOLGA_TRILHO = 12

function sobrepoeNaVertical(a: Retangulo, b: Retangulo): boolean {
  return a.topo < b.topo + b.altura && b.topo < a.topo + a.altura
}

function sobrepoeNaHorizontal(esquerda: number, largura: number, j: Retangulo): boolean {
  return esquerda < j.esquerda + j.largura && j.esquerda < esquerda + largura
}

/**
 * Quantos pixels o trilho anda para a direita (0 = fica onde está).
 *
 * `trilho` é a posição NATURAL dele (sem deslocamento). Varre as janelas da esquerda para a
 * direita e, cada vez que uma cobre a posição corrente, pula para depois dela — assim duas
 * janelas em degrau, ou lado a lado, empurram o trilho para depois da última. Janela que
 * não alcança a faixa do trilho na vertical (recolhida lá em cima, arrastada para o alto)
 * não empurra nada.
 *
 * `larguraTela` é o teto: o trilho nunca é empurrado para fora da tela. Se não couber
 * depois das janelas, fica encostado na borda direita — parcialmente coberto, mas ainda é
 * o melhor que dá sem mexer na janela que o operador posicionou.
 */
export function deslocamentoDoTrilho(
  trilho: Retangulo,
  janelas: readonly Retangulo[],
  larguraTela: number,
  folga = FOLGA_TRILHO,
): number {
  const relevantes = janelas
    .filter((j) => j.largura > 0 && j.altura > 0 && sobrepoeNaVertical(trilho, j))
    .sort((a, b) => a.esquerda - b.esquerda)
  let x = trilho.esquerda
  for (let volta = 0; volta <= relevantes.length; volta++) {
    let andou = false
    for (const j of relevantes) {
      if (sobrepoeNaHorizontal(x, trilho.largura, j)) {
        x = j.esquerda + j.largura + folga
        andou = true
      }
    }
    if (!andou) break
  }
  const teto = Math.max(trilho.esquerda, larguraTela - trilho.largura - folga)
  return Math.max(0, Math.min(x, teto) - trilho.esquerda)
}

/* ---------------- Registro das janelas abertas ---------------- */

const abertas = new Map<symbol, Retangulo>()
let foto: readonly Retangulo[] = []
const ouvintes = new Set<() => void>()

function publicar(): void {
  foto = [...abertas.values()]
  for (const f of ouvintes) f()
}

function igual(a: Retangulo | undefined, b: Retangulo): boolean {
  return (
    !!a && a.esquerda === b.esquerda && a.topo === b.topo && a.largura === b.largura && a.altura === b.altura
  )
}

/** A janela `id` está aberta neste retângulo. Repetir o mesmo retângulo não acorda ninguém. */
export function registrarJanela(id: symbol, r: Retangulo): void {
  if (igual(abertas.get(id), r)) return
  abertas.set(id, r)
  publicar()
}

/** A janela `id` fechou (ou desmontou). */
export function removerJanela(id: symbol): void {
  if (!abertas.delete(id)) return
  publicar()
}

/** Para `useSyncExternalStore`: a mesma referência enquanto nada mudar. */
export function janelasAbertas(): readonly Retangulo[] {
  return foto
}

export function assinarJanelas(f: () => void): () => void {
  ouvintes.add(f)
  return () => {
    ouvintes.delete(f)
  }
}
