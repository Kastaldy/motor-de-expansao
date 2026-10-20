import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'

import {
  _resetarRendaMetaParaTeste,
  definirRendaMeta,
  rendaMeta,
  textoInfoRenda,
} from './renda-meta'

/* Proveniência da renda (E0): o `/api/me` traz `renda_meta` top-level e o ícone ⓘ ao lado
   de cada renda lê o `rotulo` daqui. A fiação nos componentes é verificada sobre o
   TEXTO-FONTE — o vitest deste repo roda em node, sem jsdom (mesma razão de
   `components/mapa-geometria.test.ts`). */

const META_BR = {
  versao_fator: '2026-08_caged_v0',
  pais: 'BR',
  ano_base: 2022,
  data_referencia_base: '2022-07',
  ano_alvo: 2026,
  fonte: 'Novo CAGED',
  rotulo: '06/2026 (CAGED; Censo jul/2022 x 1.1641)',
  fixada_por_env: false,
  excecoes_uf: [],
}

afterEach(() => _resetarRendaMetaParaTeste())

describe('renda_meta do /api/me', () => {
  it('nasce ausente: sem proveniência, o ícone não aparece', () => {
    expect(rendaMeta()).toBeNull()
    expect(textoInfoRenda()).toBeNull()
  })

  it('instala o rótulo e a versão do servidor, sem reescrever o texto', () => {
    definirRendaMeta(META_BR)
    expect(rendaMeta()).toEqual({
      versao_fator: '2026-08_caged_v0',
      rotulo: '06/2026 (CAGED; Censo jul/2022 x 1.1641)',
      fixada_por_env: false,
    })
    expect(textoInfoRenda()).toBe('Referência da renda: 06/2026 (CAGED; Censo jul/2022 x 1.1641)')
  })

  it('payload ausente ou malformado não instala nada e não derruba', () => {
    for (const ruim of [undefined, null, 'x', 1, {}, { rotulo: '' , versao_fator: 'v' }, { rotulo: 'r' }]) {
      definirRendaMeta(ruim)
      expect(rendaMeta()).toBeNull()
    }
  })

  it('uma segunda chamada malformada apaga a anterior (nunca rótulo velho)', () => {
    definirRendaMeta(META_BR)
    definirRendaMeta(undefined)
    expect(textoInfoRenda()).toBeNull()
  })
})

describe('fiação', () => {
  const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8')

  it('o main instala o renda_meta do /api/me antes de montar a árvore', () => {
    const main = ler('../main.tsx')
    expect(main).toContain('definirRendaMeta(me.renda_meta)')
    expect(main.indexOf('definirRendaMeta(me.renda_meta)')).toBeLessThan(main.indexOf("await import('./App')"))
  })

  it('o ícone usa o texto da proveniência no title e no aria-label', () => {
    const icone = ler('../components/InfoRenda.tsx')
    expect(icone).toContain('title={texto}')
    expect(icone).toContain('aria-label={texto}')
    expect(icone).toContain('textoInfoRenda()')
  })

  it.each([
    ['../components/FichaHex.tsx', 2],
    ['../screens/PontoScreen.tsx', 2],
    ['../components/FichaUnidadeNoMapa.tsx', 2],
    ['../components/exec/FichaInteligencia.tsx', 1],
  ])('%s põe o ícone ao lado de cada renda (%i)', (arquivo, n) => {
    expect(ler(arquivo).split('<InfoRenda />').length - 1).toBe(n)
  })
})
