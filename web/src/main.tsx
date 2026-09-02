import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { api } from './lib/api'
import { definirPerfil } from './lib/perfil'
import './styles/global.css'

const el = document.getElementById('root')
if (!el) throw new Error('#root não encontrado no index.html')
const raiz = el

/**
 * Bootstrap em duas fases (Bloco A / DEC-047).
 *
 * O perfil do país é resolvido ANTES de a árvore ser importada, e a ordem aqui não é
 * estilo — é o que impede a tela de nascer no país errado.
 *
 * `import App from './App'` no topo avaliaria o grafo de módulos INTEIRO na hora,
 * inclusive todo `export const` derivado do perfil (`POP_MIN_ACIONAVEL` em `colors.ts`,
 * `CAPACIDADE_UNIDADE_ALUNOS` em `faixas.ts` e `mapa-ponto.ts`, `VISTA_PADRAO`) — todos
 * congelariam no default brasileiro compilado. E nenhum teste pegaria, porque é
 * exatamente esse default que os testes de módulo puro exercitam. O import DINÂMICO,
 * depois do `definirPerfil`, fecha essa porta estruturalmente em vez de por disciplina.
 *
 * Falha de rede não trava a abertura: segue com o default compilado, que é o Brasil — o
 * único país em produção hoje. Quem falha alto quando o perfil falta é o BACKEND, no
 * boot do container, onde a mensagem nomeia o campo que faltou.
 */
async function iniciar(): Promise<void> {
  try {
    definirPerfil((await api.me()).perfil)
  } catch {
    /* sem /api/me -> segue no default; o backend continua barrando o que deve */
  }
  const { default: App } = await import('./App')
  createRoot(raiz).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void iniciar()
