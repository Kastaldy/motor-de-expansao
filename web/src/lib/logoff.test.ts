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
      'https://auth.ultra-expansao.tech/logout',
    )
  })

  it('a instância argentina cai no MESMO portal — há um Authelia só', () => {
    expect(urlDeLogoff('piloto-ar.ultra-expansao.tech')).toBe(
      'https://auth.ultra-expansao.tech/logout',
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
      'https://auth.ultra-expansao.tech/logout',
    )
  })
})

describe('botão de sair — guarda por texto-fonte (não há jsdom)', () => {
  const dock = ler('../components/Dock.tsx')
  const botao = ler('../components/BotaoSair.tsx')

  it('mora no Dock, LOGO ABAIXO do alternador de tema (o pedido literal)', () => {
    const pe = dock.match(/marginTop: 'auto'[\s\S]*?<\/div>/)?.[0] ?? ''
    const tema = pe.indexOf('<BotaoTema')
    const sair = pe.indexOf('<BotaoSair')
    expect(tema).toBeGreaterThanOrEqual(0)
    expect(sair).toBeGreaterThan(tema)
  })

  it('nenhum domínio cravado — a URL sai do host da página', () => {
    for (const fonte of [botao, dock]) {
      expect(fonte).not.toMatch(/ultra-expansao\.tech/)
      expect(fonte).not.toMatch(/https:\/\/auth\./)
    }
    expect(botao).toContain('urlDeLogoff(window.location.hostname)')
  })

  it('só navega quando existe portal — em dev o clique não leva a lugar nenhum', () => {
    // Uma única navegação no arquivo, e ela é guardada pelo destino não-nulo.
    expect(botao.match(/window\.location\.assign/g)).toHaveLength(1)
    expect(botao).toContain('if (destino !== null) window.location.assign(destino)')
  })

  it('o clique no rail ABRE o diálogo, não sai direto', () => {
    // A confirmação é a decisão de produto do bloco: o botão é um ícone de 42 px
    // colado no alternador de tema, e o erro custa a análise inteira em tela.
    expect(botao).toContain('onClick={() => setPerguntando(true)}')
    expect(botao).toContain('Cancelar')
    expect(botao).toContain('role="dialog"')
  })

  it('o diálogo sai por portal — o Dock tem backdrop-filter e prenderia um fixed', () => {
    expect(botao).toContain('createPortal(')
    expect(botao).toContain('document.body')
  })

  it('texto de usuário acentuado (CLAUDE.md §2)', () => {
    expect(botao).toContain('Sair da conta')
    expect(botao).toContain('não ficam salvas')
  })
})
