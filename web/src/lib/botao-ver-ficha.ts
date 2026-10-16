/**
 * ONDE MORA O BOTÃO "Ver a ficha" — no canto superior esquerdo, logo abaixo do cabeçalho
 * flutuante do mapa (pedido do dono, 2026-10-16).
 *
 * Antes ele ficava no canto inferior DIREITO e caía em cima da caixa de informações da
 * direita (o painel da camada). Agora fica onde a ficha estava: a `JanelaFicha` nasce à
 * esquerda, logo abaixo do cabeçalho, e fechar/reabrir deixa o gesto no mesmo lugar.
 *
 * O topo NÃO é uma constante, e a razão é medida: o cabeçalho é `flex-wrap`. Em 1440 px
 * ele tem uma linha (~54 px) e o botão cabe em `top: 88`; em ~1100 px ele quebra em DUAS
 * linhas e o mesmo `top: 88` punha o botão em cima dos KPIs do cabeçalho. Por isso o topo
 * sai da BORDA DE BAIXO medida do cabeçalho, com a mesma folga que separa o cabeçalho do
 * corpo da tela. Sem medida (cabeçalho ainda não montado), vale o topo padrão da janela.
 */

/** O topo em que a `JanelaFicha` nasce (o mesmo `TOPO_PADRAO` dela). */
export const TOPO_BOTAO_PADRAO = 88

/** Folga entre a borda de baixo do cabeçalho e o botão. */
export const FOLGA_ABAIXO_DO_CABECALHO = 8

/**
 * Topo do botão, em px de LAYOUT (o que vai no `style.top`), relativo ao contêiner em que
 * ele é posicionado.
 *
 * `fundoCabecalho` e `topoContainer` vêm do `getBoundingClientRect`, que está em px de TELA.
 * As duas réguas NÃO são a mesma: o `#root` é encolhido por `transform: scale(--escala-app)`
 * (0,85; `styles/global.css`), e o retângulo medido já sai encolhido enquanto o `top` é
 * aplicado antes da escala. Sem dividir pela `escala`, o botão subia 15% da distância e
 * entrava no cabeçalho (medido: 64,6 px na tela contra a borda do cabeçalho em 68).
 *
 * `null` em qualquer medida = sem medida, e o topo padrão vale. Escala inválida vira 1.
 * Nunca devolve negativo.
 */
export function topoDoBotaoVerFicha(
  fundoCabecalho: number | null,
  topoContainer: number | null,
  escala = 1,
): number {
  if (fundoCabecalho == null || topoContainer == null) return TOPO_BOTAO_PADRAO
  if (!Number.isFinite(fundoCabecalho) || !Number.isFinite(topoContainer)) return TOPO_BOTAO_PADRAO
  const e = Number.isFinite(escala) && escala > 0 ? escala : 1
  return Math.max(0, Math.round((fundoCabecalho - topoContainer) / e + FOLGA_ABAIXO_DO_CABECALHO))
}
