import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* O botão de SAIR do Dock (2026-09-10), guardado por asserção sobre o TEXTO-FONTE, no
   molde de `escala-app.test.ts` — o vitest aqui roda em node, sem jsdom, então não há
   como montar React e clicar.

   A metade PURA deste botão vivia em `lib/logoff.ts` (a URL do portal do Authelia) e saiu
   na DEC-081: o Authelia foi aposentado, o logoff é só `/api/logout` (`login-motor.ts`,
   que tem teste de comportamento próprio) e o botão não constrói mais URL nenhuma. Sobra o
   COMPONENTE. */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')

describe('botão de sair — guarda por texto-fonte (não há jsdom)', () => {
  const dock = ler('./Dock.tsx')
  const botao = ler('./BotaoSair.tsx')
  const primitivas = ler('./primitives.tsx')

  /* O PÉ do rail — o bloco `marginTop: 'auto'` que empurra os controles de sessão para
     baixo. É o recorte certo para a asserção de posição: o `Dock.tsx` inteiro tem quase
     300 linhas de navegação, e varrê-lo atrás de um domínio faria o teste reprovar porque
     alguém CITOU um host num comentário de outro assunto. */
  const peDoRail = () => dock.match(/marginTop: 'auto'[\s\S]*?<\/div>/)?.[0] ?? ''

  it('mora no Dock, LOGO ABAIXO do alternador de tema (o pedido literal)', () => {
    const pe = peDoRail()
    const tema = pe.indexOf('<BotaoTema')
    const sair = pe.indexOf('<BotaoSair')
    expect(tema).toBeGreaterThanOrEqual(0)
    expect(sair).toBeGreaterThan(tema)
  })

  it('não crava domínio nenhum — o logoff é a rota relativa `/api/logout`', () => {
    /* Depois da DEC-081 o botão não monta URL de portal; o que resta é a garantia de que
       ninguém volte a cravar um host aqui. `botao` inteiro e, do Dock, SÓ o pé do rail. */
    const pe = peDoRail()
    expect(pe).toContain('<BotaoSair')
    for (const fonte of [botao, pe]) {
      expect(fonte).not.toMatch(/ultra-expansao\.tech/)
      expect(fonte).not.toMatch(/https:\/\/auth\./)
    }
  })

  it('REVOGA no servidor antes de navegar, e só navega se a revogação deu certo', () => {
    /* A revogação é chamada (`api.sair()` -> `/api/logout`), e a navegação é CONDICIONAL
       ao desfecho dela. A decisão mora em `login-motor.ts::sair`, com teste próprio; aqui
       garantimos que o botão a USA em vez de navegar por conta. Antes da DEC-067 o botão
       navegava direto para o portal e NUNCA chamava `api.sair()` — a sessão no banco não
       era revogada e bastava voltar ao piloto para estar dentro. */
    expect(botao).toContain('api.sair()')
    expect(botao).toMatch(/decidirSaida\(/)
    // Uma única navegação no arquivo, e ela só acontece no ramo `'ir'`.
    expect(botao.match(/window\.location\.assign/g)).toHaveLength(1)
    expect(botao).toContain("if (saida.tipo === 'ir') window.location.assign(saida.destino)")
  })

  it('o clique no rail ABRE o diálogo, não sai direto', () => {
    // A confirmação é a decisão de produto do bloco: o botão é um ícone de 42 px
    // colado no alternador de tema, e o erro custa a análise inteira em tela.
    expect(botao).toContain('onClick={() => setPerguntando(true)}')
    expect(botao).toContain('Cancelar')
    // A casca (véu + cartão + `role="dialog"`) mora no `Modal` de `primitives.tsx`, e é
    // lá que a semântica é medida.
    expect(botao).toContain('<Modal')
    expect(primitivas).toContain('role="dialog"')
    expect(primitivas).toContain('aria-modal="true"')
  })

  it('o diálogo sai por portal para o #root — nem preso no Dock, nem fora da escala', () => {
    /* Duas restrições ao mesmo tempo. (1) Não pode ficar dentro do Dock: o rail tem
       `backdrop-filter`, que prende qualquer `position: fixed` descendente. (2) Não pode
       ir para o `body`: o app é desenhado a 85% por um `transform: scale()` no `#root`
       (`styles/global.css`), e o `body` está fora dessa escala. O `#root` satisfaz as
       duas: tem `transform`, logo também contém `fixed`. */
    expect(botao).toContain('createPortal(')
    expect(botao).toContain("document.getElementById('root') ?? document.body")
    // O `body` só pode aparecer como fallback da linha acima, nunca como alvo.
    expect(botao.match(/document\.body/g)).toHaveLength(1)
  })

  it('texto de usuário acentuado (CLAUDE.md §2)', () => {
    expect(botao).toContain('Sair da conta')
    expect(botao).toContain('não ficam salvas')
  })
})
