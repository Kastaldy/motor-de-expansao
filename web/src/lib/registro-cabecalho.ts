import { useSyncExternalStore } from 'react'

/**
 * O CABECALHO DO MAPA, publicado por quem o desenha (`MapScreen`) e lido por quem precisa
 * medir a borda de baixo dele: a `JanelaFicha` (topo minimo, `lib/janela`) e a camada do
 * ponto (caixa de colar e botao "Ver a ficha", `lib/botao-ver-ficha`).
 *
 * POR QUE UM REGISTRO, e nao o DOM (revisao de 21/10/2026). Os leitores achavam o cabecalho
 * subindo pelos ancestrais UMA vez, na montagem. Mas a camada do ponto e o `MapScreen` sao
 * IRMAOS no `App`, e o cabecalho vai e volta por baixo dela: no Explorar sem UF o
 * `MapScreen` desenha a Landing (sem cabecalho) enquanto a janela do ponto ja' existe, e
 * trocar main <-> Landing remonta o cabecalho num elemento NOVO. Medido so' na montagem,
 * o leitor ficava com "sem cabecalho" para sempre, ou observando um elemento desligado do
 * DOM (`bottom` 0) -- e a barra de titulo da janela voltava a poder subir por baixo do
 * cabecalho (z 29, ACIMA dela), sem alca. Com o registro, todo leitor re-renderiza quando
 * o cabecalho aparece, some ou e' trocado.
 *
 * UM cabecalho por vez: so' existe um `MapScreen` montado. O `ref` do React chama com
 * `null` na desmontagem ANTES de chamar com o elemento novo no mesmo commit, entao a ordem
 * e' sempre "solta o velho, publica o novo".
 */
let atual: HTMLElement | null = null
const ouvintes = new Set<() => void>()

/** O `ref` do cabecalho do mapa: `ref={registrarCabecalhoMapa}`. Identidade estavel. */
export function registrarCabecalhoMapa(el: HTMLElement | null): void {
  if (el === atual) return
  atual = el
  for (const avisar of [...ouvintes]) avisar()
}

/** O cabecalho publicado agora (`null` = nenhum na tela). */
export function cabecalhoMapaAtual(): HTMLElement | null {
  return atual
}

/** Avisa a cada troca. Devolve a funcao que cancela a assinatura. */
export function assinarCabecalhoMapa(avisar: () => void): () => void {
  ouvintes.add(avisar)
  return () => {
    ouvintes.delete(avisar)
  }
}

/** O cabecalho do mapa como estado React: re-renderiza quando ele aparece, some ou troca. */
export function useCabecalhoMapa(): HTMLElement | null {
  return useSyncExternalStore(assinarCabecalhoMapa, cabecalhoMapaAtual, () => null)
}
