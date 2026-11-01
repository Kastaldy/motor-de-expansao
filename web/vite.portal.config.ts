import { resolve } from 'node:path'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Build do PORTAL DO APEX (`ultra-expansao.tech`) — um TERCEIRO artefato, no MESMO `dist/`
 * do piloto e da tela de entrar.
 *
 * POR QUE UM BUILD SEPARADO, e não uma segunda entrada do build principal (a mesma razão
 * do `vite.entrar.config.ts`). A página é servida na raiz do apex, que é PAÍS-NEUTRO
 * (DEC-047) e não deve carregar o bundle da SPA do piloto — as rotas internas da API
 * viajam nele, e quem está no apex só vai escolher um país (ou nem entrou). Com uma
 * entrada a mais no build principal, os arquivos das três páginas cairiam juntos em
 * `assets/`, e servir o portal exigiria abrir `assets/` inteiro. Um `assetsDir` próprio
 * resolve isso: os arquivos do portal vivem num prefixo que só ele usa.
 *
 * `emptyOutDir: false` é OBRIGATÓRIO: este build roda DEPOIS do principal e do da tela de
 * entrar, e apagaria o `dist/` deles. A ordem está no script `build` do `package.json` —
 * o principal PRIMEIRO (é ele que esvazia o `dist/`), os outros dois depois.
 *
 * O HTML buildado é `dist/portal.html`, e o backend o serve numa rota própria
 * `GET /portal.html`.
 */
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    assetsDir: 'portal-assets',
    sourcemap: false,
    rollupOptions: {
      input: resolve(import.meta.dirname, 'portal.html'),
    },
  },
})
