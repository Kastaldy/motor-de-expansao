import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Piloto web do Motor de Expansao.
// Porta 5000 por pedido do Felipe (o .cmd na raiz do repo sobe por aqui).
// O backend Python (relatorios PDF + analises) responde em 8899 e e acessado
// via proxy /api, para o front nao precisar lidar com CORS em dev.
//
// As DUAS portas sao parametrizaveis por env, e existe um caso concreto para isso:
// com o RBAC no banco, a identidade em dev vem do `MOTOR_DEV_USUARIO` do PROCESSO do
// backend. Comparar dois perfis exigia reiniciar o backend entre um e outro -- ou,
// agora, subir duas instancias e olhar as duas telas lado a lado:
//
//   backend A (growth):    --port 8899   +  MOTOR_DEV_USUARIO=vinicius.teste
//   backend B (expansao):  --port 8898   +  MOTOR_DEV_USUARIO=ana.teste
//   SPA A:  npm run dev
//   SPA B:  $env:MOTOR_WEB_PORT=5001; $env:MOTOR_API_URL="http://127.0.0.1:8898"; npm run dev
//
// Sem efeito em producao: o SPA e' servido estatico pelo mesmo container do backend,
// e este proxy so' existe no servidor de desenvolvimento do Vite.
const PORTA_WEB = Number(process.env.MOTOR_WEB_PORT ?? 5000)
const API_ALVO = process.env.MOTOR_API_URL ?? 'http://127.0.0.1:8899'

export default defineConfig({
  plugins: [react()],
  server: {
    port: PORTA_WEB,
    // `strictPort` de proposito: com duas instancias, o Vite escolhendo outra porta em
    // silencio faria voce olhar a tela do perfil errado sem nenhum sinal disso.
    strictPort: true,
    open: false,
    proxy: {
      '/api': {
        target: API_ALVO,
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
