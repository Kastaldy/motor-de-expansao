/* Unidades no mapa para todos que têm o mapa, sem a Executiva (pedido do Felipe, 11/11/2026).
   Quem só tinha o mapa via o filtro antigo "Faixa M1" no lugar do seletor UNIDADES e não
   tirava o relatório de concorrência das unidades, porque tudo lia `/api/rede/*`. */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')
const mapa = ler('../screens/MapScreen.tsx')
const ficha = ler('../components/FichaUnidadeNoMapa.tsx')

describe('o seletor UNIDADES é de todos que têm o mapa', () => {
  it('a lista vem pela porta do mapa, sem depender da aba executiva', () => {
    expect(mapa).toContain('.mapaUnidades()')
    expect(mapa).not.toContain('.redeCarteira()')
    expect(mapa).not.toContain('verUnidades')
  })

  it('o filtro antigo "Faixa M1" saiu do cabeçalho', () => {
    expect(mapa).not.toContain('filtroFaixa')
    expect(mapa).not.toContain('FAIXA_FILTROS')
  })
})

describe('a ficha da unidade sem a Executiva é só território', () => {
  it('quem não vê a rede lê a porta do mapa, e o PDF também sai por ela', () => {
    expect(ficha).toContain('const soTerritorio = semRede || !verRede')
    expect(ficha).toContain('.mapaUnidade(unidadeId)')
    expect(ficha).toContain('await api.mapaUnidadeConcorrenciaPdf(unidadeId)')
  })

  it('os alunos só aparecem para quem vê a rede', () => {
    expect(ficha).toContain(') : !verRede ? null : (')
  })
})
