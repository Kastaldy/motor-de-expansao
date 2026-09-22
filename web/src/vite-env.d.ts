/// <reference types="vite/client" />

/**
 * Tipos dos assets importados como MÓDULO.
 *
 * O `vite/client` já declara `.png`, `.jpg`, `.svg` e companhia; `.avif` ficou de fora
 * da lista dele. Sem esta declaração o `tsc --noEmit` reprova o import do logo da tela
 * de entrar — e reprova com razão, porque para o TypeScript aquele caminho não existe.
 *
 * O import é o que garante que o caminho do logo seja resolvido no BUILD: a tela é
 * servida num host onde a raiz pertence ao Authelia, então um caminho absoluto só
 * quebraria em produção. Ver o comentário em `screens/LoginScreen.tsx`.
 */
declare module '*.avif' {
  const src: string
  export default src
}
