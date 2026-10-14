import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* As DUAS entradas do mapa respondem igual (decisão do dono, 2026-10-14).

   "Explorar uma região" e "Analisar um ponto" eram dois ramos no `App.tsx`, com o MESMO
   `MapScreen` e props diferentes — e a divergência estava exatamente nas props: a busca
   abria a ficha do hexágono num e a do ponto no outro, o cabeçalho mostrava UNIDADES num e
   MELHORES no outro, o clique em hexágono abria ficha num e nada no outro. Nada no
   repositório impedia o segundo ramo de voltar e as props de divergirem de novo.

   Asserção sobre TEXTO-FONTE pela mesma razão do `aviso-sessao.test.ts`: o vitest deste
   repo roda sem jsdom, então não há como montar React e olhar a tela. As REGRAS (lista de
   pontos, janela do hexágono, ferramenta) têm teste próprio em `lib/`; aqui se trava só a
   FIAÇÃO que as liga.
   --------------------------------------------------------------------------------- */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const app = ler('../App.tsx')
const mapScreen = ler('./MapScreen.tsx')
const pontoScreen = ler('./PontoScreen.tsx')

/** Ocorrências de `trecho` no texto. */
const contar = (texto: string, trecho: string) => texto.split(trecho).length - 1

describe('App: um ramo só para as duas entradas do mapa', () => {
  it('as duas telas caem no MESMO ramo', () => {
    expect(app).toContain("tela === 'mapa' || tela === 'ponto' ? (")
    // Nenhum ramo próprio sobrou para nenhuma das duas.
    expect(app).not.toMatch(/\) : tela === 'ponto' \? \(/)
    expect(app).not.toMatch(/\) : tela === 'mapa' \? \(/)
  })

  it('há UM `<MapScreen>` e UM `<PontoScreen>` no App', () => {
    expect(contar(app, '<MapScreen')).toBe(1)
    expect(contar(app, '<PontoScreen')).toBe(1)
  })

  it('a busca vira ponto e o cabeçalho mostra UNIDADES nas duas entradas', () => {
    expect(app).toContain('onPontoBuscado={pedirPonto}')
    // `telaLiberada` e não `true`: quem não tem a aba executiva segue no MELHORES, porque
    // `/api/rede/*` responderia 403.
    expect(app).toContain("verUnidades={telaLiberada('executiva', abas)}")
  })

  it('a entrada decide só o hero da tela vazia', () => {
    expect(app).toContain("semLanding={tela === 'ponto'}")
    expect(app).toContain("comHero={tela === 'ponto'}")
  })

  it('a lista de pontos mora no App e chega ao mapa e à ficha', () => {
    expect(app).toContain('const pontos = usePontos()')
    expect(app).toContain('pontosComparados={pontos.pins}')
    expect(app).toContain('fichas={pontos.fichas}')
  })
})

describe('MapScreen: a busca não solta pin local nem abre a ficha do hexágono', () => {
  it('o boolean `janelaDoHex` saiu; quem decide é `janelaDoHexVisivel`', () => {
    expect(mapScreen).not.toContain('janelaDoHex =')
    expect(mapScreen).toContain('janelaDoHexVisivel({')
  })

  it('o cartão "Estudo pontual →" e o `estudoPontualDoPin` saíram', () => {
    expect(mapScreen).not.toContain('estudoPontualDoPin')
    expect(mapScreen).not.toContain('Estudo pontual →')
  })

  it('a régua é uma ferramenta do estado único, não um booleano próprio', () => {
    expect(mapScreen).toContain("useState<FerramentaMapa>('nenhuma')")
    expect(mapScreen).not.toContain('setMedindo')
  })

  it('o ponto ativo vence o destino de lista, que vence o pin local', () => {
    expect(mapScreen).toContain('searchPin={pontoAtivo ?? pinFixo ?? pin}')
  })
})

describe('PontoScreen: sem estado próprio de lista', () => {
  it('não guarda mais as fichas em `useState`', () => {
    expect(pontoScreen).not.toMatch(/useState<PontoPayload\[\]>/)
  })

  it('o hero só existe com `comHero`', () => {
    expect(pontoScreen).toContain('if (semMapa && comHero) {')
  })
})
