import { resolve } from 'node:path'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Build da TELA DE ENTRAR — um segundo artefato, no MESMO `dist/` do piloto.
 *
 * POR QUE UM BUILD SEPARADO, e não uma segunda entrada do build principal. A página é
 * servida na raiz de `auth.ultra-expansao.tech`, host que ela divide com o portal do
 * Authelia. O Caddy manda para o nosso container só a raiz e o prefixo `entrar-assets/`;
 * todo o resto daquele host vai para o Authelia.
 *
 * Com uma entrada a mais no build principal, os arquivos das duas páginas cairiam juntos
 * em `assets/` — e para servir a tela seria preciso abrir `assets/` inteiro naquele host,
 * expondo o bundle do piloto a quem ainda não entrou (as rotas internas da API estão lá
 * dentro). Um `assetsDir` próprio resolve isso na raiz: os arquivos da tela vivem num
 * prefixo que só ela usa, e é só esse prefixo que fica público.
 *
 * `emptyOutDir: false` é OBRIGATÓRIO: este build roda DEPOIS do principal e apagaria o
 * `dist/` dele. A ordem está no script `build` do `package.json`.
 */
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    assetsDir: 'entrar-assets',
    sourcemap: false,
    rollupOptions: {
      input: resolve(import.meta.dirname, 'entrar.html'),
    },
  },
})
