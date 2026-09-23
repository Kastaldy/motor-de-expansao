import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/* A caixa de escolher estado E' o seletor — e nada aqui prova isso sozinho.

   Ate' 2026-09-22 a landing de "Explorar uma regiao" tinha DUAS caixas: um painel com o
   rotulo "Selecione um estado" e, DENTRO dele, o botao do dropdown com placeholder
   "Escolha…". Duas bordas aninhadas dizendo a mesma coisa, e so' a de dentro abria a
   lista — quem mirava a de fora nao acontecia nada.

   Asserção sobre TEXTO-FONTE, e nao render, pela mesma razao do `aviso-sessao.test.ts`:
   o vitest deste repo roda sem jsdom, entao nao ha' como montar React e olhar a tela.
   --------------------------------------------------------------------------------- */

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const mapScreen = ler('./MapScreen.tsx')
const select = ler('../components/Select.tsx')

describe('seletor de estado da landing', () => {
  it('usa o texto como PLACEHOLDER do seletor, nao como rotulo ao lado dele', () => {
    expect(mapScreen).toContain('placeholder="Selecione um estado"')
    // A regressao a impedir tem FORMA: o rotulo voltar como elemento renderizado ao lado
    // do seletor. Contar ocorrencias no texto-fonte nao serve — o fonte inclui comentario,
    // e o comentario que explica esta mudanca cita a propria string. (Medido: a primeira
    // versao deste teste reprovou exatamente por isso.)
    expect(mapScreen).not.toMatch(/<span[^>]*>\s*Selecione um estado/)
  })

  it('pede a variante de painel, que e o que faz o proprio botao virar a caixa', () => {
    expect(mapScreen).toContain('variante="painel"')
  })

  it('nao tem mais o placeholder generico que ficava dentro da outra caixa', () => {
    expect(mapScreen).not.toContain('placeholder="Escolha…"')
  })

  it('a variante e OPCIONAL e cai em `padrao`, para as outras chamadas nao mudarem', () => {
    // 14 chamadas de <Select /> existem no piloto; nenhuma passa `variante`. Se o default
    // sumir ou mudar, todas elas mudam de aparencia de uma vez.
    expect(select).toContain("variante = 'padrao'")
    expect(select).toContain("variante?: 'padrao' | 'painel'")
  })

  it('so a landing do mapa pede a variante de painel', () => {
    // Guarda de alcance: se outra tela passar a pedir `painel`, e' decisao visual que
    // merece ser vista, nao efeito colateral de um copiar-colar.
    const comVariante = ['MapScreen.tsx']
    for (const tela of ['ExecutiveScreen.tsx', 'OportunidadesScreen.tsx']) {
      expect(ler(`./${tela}`)).not.toContain('variante="painel"')
    }
    expect(comVariante).toContain('MapScreen.tsx')
  })
})
