import { resolve } from 'node:path'

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
        // O PAPEL DO CADDY, em dev. Em produção o `forward_auth` autentica na borda e o
        // Caddy INJETA `Remote-User` em cada requisição; o backend nunca o vê ausente.
        // Localmente não há Caddy, então a identidade chegava vazia e o `/api/me` devolvia
        // `usuario: null` — a plataforma abria, mas sem dono, e a aba Acessos não conseguia
        // escrever (sem identidade não há autor para registrar a mudança).
        //
        // `MOTOR_DEV_REMOTE_USER` liga isso e é SÓ do servidor de desenvolvimento: este
        // arquivo não vai para a imagem, e em produção o SPA é servido estático pelo próprio
        // backend, sem proxy nenhum. Sem a env, nada é injetado e o comportamento é o de antes.
        ...(process.env.MOTOR_DEV_REMOTE_USER
          ? { headers: { 'Remote-User': process.env.MOTOR_DEV_REMOTE_USER } }
          : {}),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1600,
    // DUAS PAGINAS, e sem esta lista a segunda NAO EXISTE no que se publica.
    //
    // O Vite constroi so' o `index.html` por padrao. `entrar.html` estava no repositorio
    // desde o PR #400 e NUNCA SAIU NO BUILD -- medido em 25/09/2026 rodando `vite build`:
    // a pasta de saida tinha `index.html` e mais nada. A tela de entrar existia no fonte,
    // passava no lint e nos testes das partes puras, e nao chegava a imagem nenhuma. Um
    // defeito que nao da' erro em lugar nenhum: o build sai com sucesso, e o que falta so'
    // aparece quando alguem pede a pagina e leva 404.
    //
    // Sao bundles SEPARADOS de proposito, e a razao e' de seguranca: servir a SPA inteira
    // do piloto a quem ainda nao entrou entregaria as rotas internas da API para quem so'
    // deveria ver um formulario de login.
    rollupOptions: {
      input: {
        index: resolve(__dirname, 'index.html'),
        entrar: resolve(__dirname, 'entrar.html'),
      },
    },
  },
})
