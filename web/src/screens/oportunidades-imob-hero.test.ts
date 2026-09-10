import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* O hero da Ficha (o <article>) e' filho direto de um flex column E declara
   `overflow: hidden`, que o border-radius exige para recortar o fundo dos dois paineis.
   Essa combinacao zera o minimo automatico do item — `min-height: auto` so' vale com
   overflow visible —, e sem `flexShrink: 0` a coluna cobra do hero toda a altura que
   falta quando o zoom da pagina encolhe o viewport: medido em Chrome headless, 99px
   cortados ja' a 100% e colapso para ~2px de 125% em diante.

   O par `overflow: hidden` + `flexShrink: 0` e' o invariante. Este teste existe porque
   o defeito e' INVISIVEL para o resto da suite: um refator que reescreva o style inline
   do <article> reintroduz o bug sem quebrar mais nada. Molde herdado de
   lib/escala-app.test.ts (assercao sobre o texto-fonte; o projeto nao tem jsdom). */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const tela = ler('./OportunidadesImobiliariasScreen.tsx')

describe('hero da Ficha imobiliaria nao colapsa sob zoom', () => {
  it('o <article> trava flexShrink: 0 junto do overflow: hidden', () => {
    const abertura = tela.match(/<article style=\{\{[^}]*\}\}>/)
    expect(abertura).not.toBeNull()
    expect(abertura![0]).toContain("overflow: 'hidden'")
    expect(abertura![0]).toContain('flexShrink: 0')
  })

  it("a <section> que hospeda o hero rola — e' o que torna a trava segura", () => {
    /* Travar o filho so' e' correto porque o pai rola: sem `overflowY: auto` no pai, o
       conteudo que passa da altura ficaria inalcancavel em vez de rolavel. */
    expect(tela).toContain("overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 20")
  })

  it('o MiniMapa mantem altura fixa, o que impede o card Localizacao de virar a proxima valvula', () => {
    /* O card "Localizacao" tambem tem `overflow: hidden`. Ele nao e' esmagado porque o
       MiniMapa dentro dele tem altura definida, o que da ao grid um tamanho concreto.
       Trocar essa altura por algo elastico reabre a mesma classe de defeito ali. */
    expect(tela).toContain('height: 320')
  })
})
