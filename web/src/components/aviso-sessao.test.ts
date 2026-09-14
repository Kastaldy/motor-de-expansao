import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { PARAGRAFOS_SESSAO, ROTULO_BOTAO_SESSAO, TITULO_SESSAO } from './AvisoSessao'

/* O pop-up de SESSÃO ENCERRADA podia sumir INTEIRO com a suíte verde.

   Medido por mutação: trocar a linha do mount no `App.tsx` por
   `{sessaoCaiu && false && <AvisoSessao ... />}` deixava o `tsc` limpo e os 910 testes
   passando — nada no repositório afirmava que o componente chega à tela. O arquivo
   ainda exportava `TITULO_SESSAO`, `PARAGRAFOS_SESSAO` e `ROTULO_BOTAO_SESSAO` sem um
   único consumidor, então nem o texto tinha guarda.

   Duas metades, como em `lib/logoff.test.ts`:
   - o TEXTO, por importação de verdade (são constantes puras, rodam em node);
   - o MOUNT, por asserção sobre o texto-fonte do `App.tsx` — o vitest aqui roda sem
     jsdom, então não há como montar React, derrubar a sessão e olhar a tela.
   --------------------------------------------------------------------------------- */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const app = ler('../App.tsx')
const componente = ler('./AvisoSessao.tsx')

describe('o aviso de sessão chega à tela', () => {
  it('o App monta o <AvisoSessao> quando a sessão cai — sem condição a mais no meio', () => {
    /* A asserção é a LINHA inteira, de propósito: é o que pega a mutação do `&& false`,
       que nenhum outro teste enxergava. Mudar a forma do mount aqui é legítimo — mudar
       esta linha junto é o preço, e é barato perto de perder o pop-up em produção. */
    expect(app).toContain('{sessaoCaiu && <AvisoSessao onEntrar={entrarNovamente} />}')
    expect(app).toContain("import AvisoSessao from './components/AvisoSessao'")
  })

  it('o estado do mount é o que a sonda de sessão liga, e não outro qualquer', () => {
    // `assinarQuedaDeSessao` (lib/sessao.ts) é quem classifica a falha como SESSÃO; sem
    // esta ligação o pop-up existiria e nunca apareceria, que é o mesmo defeito por outra
    // porta.
    expect(app).toContain('assinarQuedaDeSessao(() => setSessaoCaiu(true))')
    expect(app).toContain('const [sessaoCaiu, setSessaoCaiu] = useState(false)')
  })

  it('o que o componente desenha são EXATAMENTE as constantes exportadas', () => {
    // Guardar a acentuação das constantes só vale se forem elas que chegam ao pixel.
    expect(componente).toContain('titulo={TITULO_SESSAO}')
    expect(componente).toContain('paragrafos={PARAGRAFOS_SESSAO}')
    expect(componente).toContain('{ROTULO_BOTAO_SESSAO}')
  })
})

describe('texto do aviso de sessão com acentuação correta (CLAUDE.md §2)', () => {
  const textos = [TITULO_SESSAO, ...PARAGRAFOS_SESSAO, ROTULO_BOTAO_SESSAO]

  it('título e botão são os textos de produto, acentuados', () => {
    expect(TITULO_SESSAO).toBe('Sessão encerrada')
    expect(ROTULO_BOTAO_SESSAO).toBe('Entrar novamente')
    expect(PARAGRAFOS_SESSAO).toHaveLength(3)
  })

  it('os parágrafos explicam que não é falha do sistema e o que fazer', () => {
    const corpo = PARAGRAFOS_SESSAO.join(' ')
    expect(corpo).toContain('Seu acesso expirou e você foi desconectado da conta.')
    expect(corpo).toContain('Não é uma falha do sistema')
    expect(corpo).toContain(`Clique em "${ROTULO_BOTAO_SESSAO}" para voltar à tela de login.`)
  })

  it('nenhuma palavra volta para a forma sem acento', () => {
    /* A regressão que a regra do CLAUDE.md descreve não é digitar errado: é alguém
       reescrever a frase sem os acentos ao editar.

       A comparação é por PALAVRA INTEIRA — nem por trecho, nem por `\b`.

       Por trecho é armadilha: `ja` casa dentro de "janela" e `apos` dentro de "aposta",
       e um texto correto futuro reprovaria por uma palavra legítima, com uma mensagem
       que não explica nada. E `\b` não resolve em JavaScript, porque o acento não conta
       como caractere de palavra: `\bja\b` casaria dentro de "já", que é justamente a
       forma certa. Daí quebrar por `\p{L}` e comparar com `===`.

       A lista tem SÓ formas que não existem em português sem o acento. `esta` ficou de
       fora de propósito: "esta tela" é tão correto quanto "está aberta", e o teste não
       tem como separar as duas. */
    const FORMAS_SEM_ACENTO = new Set([
      'sessao',
      'nao',
      'voce',
      'pagina',
      'apos',
      'tambem',
      'usuario',
      'ja',
    ])
    for (const texto of textos) {
      const reincidentes = texto
        .toLowerCase()
        .split(/[^\p{L}]+/u)
        .filter((palavra) => FORMAS_SEM_ACENTO.has(palavra))
      expect(reincidentes, texto).toEqual([])
    }
    expect(textos.join(' ')).toMatch(/[áàâãéêíóôõúç]/i)
  })
})
