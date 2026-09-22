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
  /* PREVIA DA TELA DE ENTRAR (2026-09-22).
   *
   * `/entrar` renderiza a tela de login em vez do app. Ela AINDA NAO AUTENTICA: quem
   * autentica e' o Authelia, na borda, e a decisao de para onde o `submit` vai bater
   * (API do Authelia agora, ou o motor depois do corte do P19) esta' em aberto. Isto
   * existe para a tela ser revisavel no ar antes daquela decisao — e o caminho `/entrar`
   * e' o mesmo que a rota do Caddy usaria quando ela entrar em servico.
   *
   * NAO e' um formulario de login falso exposto na internet: o host inteiro esta' atras
   * do `forward_auth`, entao so' quem JA' entrou alcanca esta rota. Ainda assim, o envio
   * responde com a falha `nao-ligado`, que diz na tela, com todas as letras, que a
   * autenticacao continua sendo a do Authelia — em vez de fingir que processou.
   *
   * O `StaticFiles(html=True)` do backend serve o index.html para caminho desconhecido,
   * entao `/entrar` chega aqui sem precisar de rota nova no servidor. */
  if (window.location.pathname === '/entrar') {
    /* `?tema=claro|escuro` força o tema NESTA prévia.
     *
     * Existe porque esta tela não tem alternador — ela não é o app, é a porta dele — e
     * o tema normal vem do depósito do navegador, que é POR ORIGEM. Comparar claro e
     * escuro lado a lado exigiria duas origens e um clique que não existe aqui; com o
     * parâmetro, basta abrir duas abas. Vale só para `/entrar`: o app continua lendo o
     * depósito, e nada aqui o escreve — fechar a aba não deixa rastro. */
    const temaPedido = new URLSearchParams(window.location.search).get('tema')
    if (temaPedido === 'claro' || temaPedido === 'escuro') {
      document.documentElement.setAttribute('data-tema', temaPedido)
    }

    const [{ default: LoginScreen }, { BaseProvider }] = await Promise.all([
      import('./screens/LoginScreen'),
      import('./lib/base-contexto'),
    ])
    const { ufs } = await api.ufs().catch(() => ({ ufs: [] as string[] }))
    createRoot(raiz).render(
      <StrictMode>
        <BaseProvider ufs={ufs}>
          <LoginScreen onEntrar={async () => 'nao-ligado'} />
        </BaseProvider>
      </StrictMode>,
    )
    return
  }

  const { default: App } = await import('./App')
  createRoot(raiz).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void iniciar()
