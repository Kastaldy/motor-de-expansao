import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Piloto web do Motor de Expansao.
// Porta 5000 por pedido do Felipe (o .cmd na raiz do repo sobe por aqui).
// O backend Python (relatorios PDF + analises) responde em 8899 e e acessado
// via proxy /api, para o front nao precisar lidar com CORS em dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5000,
    strictPort: true,
    open: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8899',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1600,
  },
})
