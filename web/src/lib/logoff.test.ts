import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { hostDeAutenticacao, urlDeLogoff } from './logoff'

/* O botão de SAIR do Dock (2026-09-10). Duas metades:
   - a PURA (`lib/logoff.ts`), exercitada por comportamento;
   - o COMPONENTE (`components/BotaoSair.tsx`), guardado por asserção sobre o
     TEXTO-FONTE, no molde de `escala-app.test.ts` — o vitest aqui roda em node, sem
     jsdom, então não há como montar React e clicar. */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')

describe('URL de logoff — derivada do host, nunca cravada', () => {
  it('o piloto brasileiro aponta para o portal do próprio apex', () => {
    // `auth.ultra-expansao.tech` é o portal deste deploy (docs/infra_producao.md e o
    // `rd=` do forward_auth em deploy/caddy/piloto-ar.Caddyfile.template).
    expect(urlDeLogoff('piloto.ultra-expansao.tech')).toBe(
      'https://auth.ultra-expansao.tech/logout?rd=https%3A%2F%2Fpiloto.ultra-expansao.tech%2F',
    )
  })

  it('a instância argentina cai no MESMO portal — há um Authelia só', () => {
    expect(urlDeLogoff('piloto-ar.ultra-expansao.tech')).toBe(
      'https://auth.ultra-expansao.tech/logout?rd=https%3A%2F%2Fpiloto-ar.ultra-expansao.tech%2F',
    )
  })

  it('domínio ccSLD não vira `auth.com.br` — o apex mandava o operador para fora', () => {
    /* O domínio corporativo da Ultra é um `.com.br`, então isto não é hipótese: a regra
       antiga (dois últimos rótulos) devolvia `auth.com.br`, que qualquer terceiro pode
       registrar. Trocar o primeiro rótulo acerta. */
    expect(hostDeAutenticacao('piloto.ultraacademia.com.br')).toBe('auth.ultraacademia.com.br')
  })

  it('host que não é do piloto falha FECHADO em vez de navegar para um palpite', () => {
    /* A raiz do domínio não é servida por nenhum deploy (deploy/caddy só conhece
       `piloto.` e `piloto-ar.`), e host desconhecido não tem portal derivável. `null`
       faz o botão explicar que não há portal, em vez de mandar o operador a um chute. */
    for (const host of ['ultra-expansao.tech', 'ultraacademia.com.br', 'app.gov.br', 'meu-pc.local']) {
      expect(hostDeAutenticacao(host)).toBeNull()
    }
  })

  it('dev local não tem portal — devolve null em vez de um 404 mudo', () => {
    for (const host of ['localhost', 'piloto.localhost', '127.0.0.1', '0.0.0.0', '::1']) {
      expect(urlDeLogoff(host)).toBeNull()
    }
  })

  it('IP nu, host sem ponto, vazio e nulo também não têm portal', () => {
    for (const host of ['10.0.0.7', 'vps', '', '   ', null, undefined]) {
      expect(urlDeLogoff(host)).toBeNull()
    }
  })

  it('normaliza caixa e o ponto final do FQDN', () => {
    expect(urlDeLogoff('PILOTO.Ultra-Expansao.TECH.')).toBe(
      'https://auth.ultra-expansao.tech/logout?rd=https%3A%2F%2Fpiloto.ultra-expansao.tech%2F',
    )
  })
})

describe('botão de sair — guarda por texto-fonte (não há jsdom)', () => {
  const dock = ler('../components/Dock.tsx')
  const botao = ler('../components/BotaoSair.tsx')
  const primitivas = ler('../components/primitives.tsx')

  /* O PÉ do rail — o bloco `marginTop: 'auto'` que empurra os controles de sessão para
     baixo. É o recorte certo para as duas asserções abaixo: o `Dock.tsx` inteiro tem
     quase 300 linhas de navegação, e varrê-lo atrás de um host faria o teste reprovar
     porque alguém CITOU o domínio num comentário de outro assunto. */
  const peDoRail = () => dock.match(/marginTop: 'auto'[\s\S]*?<\/div>/)?.[0] ?? ''

  it('mora no Dock, LOGO ABAIXO do alternador de tema (o pedido literal)', () => {
    const pe = peDoRail()
    const tema = pe.indexOf('<BotaoTema')
    const sair = pe.indexOf('<BotaoSair')
    expect(tema).toBeGreaterThanOrEqual(0)
    expect(sair).toBeGreaterThan(tema)
  })

  it('nenhum domínio cravado — a URL sai do host da página', () => {
    /* `botao` inteiro (é o arquivo que monta a URL) e, do Dock, SÓ o pé do rail, que é
       onde o botão vive: a asserção negativa precisa ser tão estreita quanto o que ela
       protege. */
    const pe = peDoRail()
    expect(pe).toContain('<BotaoSair')
    for (const fonte of [botao, pe]) {
      expect(fonte).not.toMatch(/ultra-expansao\.tech/)
      expect(fonte).not.toMatch(/https:\/\/auth\./)
    }
    expect(botao).toContain('urlDeLogoff(window.location.hostname)')
  })

  it('REVOGA no servidor antes de navegar, e só navega se a revogação deu certo', () => {
    /* Até 25/09/2026 esta guarda exigia `if (destino !== null) window.location.assign(destino)`
       — ou seja, fixava um botão que NUNCA chamava `api.sair()`. Enquanto o Authelia
       autenticava, quem encerrava era o portal e isso bastava. Depois do corte (DEC-067)
       deixaria de bastar EM SILÊNCIO: a pessoa iria ao portal, a sessão no nosso banco não
       seria revogada e o cookie continuaria válido — bastava voltar ao piloto para estar
       dentro. O próprio `/api/logout` declara isso inaceitável ("limpar estado no cliente
       NÃO é logout").

       A guarda passa a fixar as DUAS metades da correção: que a revogação é chamada, e que
       a navegação é CONDICIONAL ao desfecho dela. A decisão mora em `login-motor.ts::sair`,
       que tem teste de comportamento próprio; aqui garantimos que o botão a USA em vez de
       navegar por conta. */
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
    // A casca (véu + cartão + `role="dialog"`) mudou de casa na unificação dos três
    // modais: ela mora no `Modal` de `primitives.tsx`, e é lá que a semântica é medida.
    expect(botao).toContain('<Modal')
    expect(primitivas).toContain('role="dialog"')
    expect(primitivas).toContain('aria-modal="true"')
  })

  it('o diálogo sai por portal para o #root — nem preso no Dock, nem fora da escala', () => {
    /* Duas restrições ao mesmo tempo. (1) Não pode ficar dentro do Dock: o rail tem
       `backdrop-filter`, que prende qualquer `position: fixed` descendente. (2) Não pode
       ir para o `body`: o app é desenhado a 85% por um `transform: scale()` no `#root`
       (`styles/global.css`), e o `body` está fora dessa escala — portado para lá, este
       era o único diálogo em tamanho real, pedindo 460 px e desenhando 460 enquanto o
       cartão de sessão pedia 520 e pousava em 442. O `#root` satisfaz as duas: tem
       `transform`, logo também contém `fixed`. */
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

describe('destino do logoff (2026-09-22)', () => {
  it('volta para o HOST de onde a pessoa saiu, nao para a raiz de auth.', () => {
    /* Quem deslogou do piloto-ar deve voltar a entrar no piloto-ar. O caminho passa pelo
       `forward_auth` daquele host, que manda para a nossa tela com o `rd` preenchido —
       entao, ao entrar de novo, a pessoa cai onde estava. */
    expect(urlDeLogoff('piloto-ar.ultra-expansao.tech')).toContain(
      'rd=https%3A%2F%2Fpiloto-ar.ultra-expansao.tech%2F',
    )
    expect(urlDeLogoff('piloto.ultra-expansao.tech')).toContain(
      'rd=https%3A%2F%2Fpiloto.ultra-expansao.tech%2F',
    )
  })

  it('o destino vai CODIFICADO', () => {
    // Sem codificar, o `://` e as barras quebrariam a query no primeiro parser.
    const url = urlDeLogoff('piloto.ultra-expansao.tech')!
    expect(url).not.toContain('rd=https://')
    expect(url.split('?')[0]).toBe('https://auth.ultra-expansao.tech/logout')
  })

  it('ambiente sem portal continua sem URL — o destino nao ressuscita o botao', () => {
    expect(urlDeLogoff('localhost')).toBeNull()
    expect(urlDeLogoff('127.0.0.1')).toBeNull()
  })
})
