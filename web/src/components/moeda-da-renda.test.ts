import { afterEach, describe, expect, it } from 'vitest'

import { TEXTO_SEM_DADO } from '../lib/constants'
import { UNIDADE_MOEDA, UNIDADE_RENDA } from '../lib/format'
import { _resetarPerfilParaTeste, definirPerfil, type PerfilCliente } from '../lib/perfil'
import { valorFmt } from './Recomendacao'
import { formatar } from './TabelaRanking'

/* A RENDA sai na moeda da RENDA do perfil, nunca num "R$" cravado (achado a-03 da conferência
   de 2026-10-29; defeito S4 de `docs/expansao-latam/00-baseline-argentina.md`).

   Dois defeitos de uma raiz só, o símbolo da moeda fazendo papel de CHAVE de despacho:
   - a tabela da comparação comparava a unidade com o literal 'R$', que a comparação deixou
     de mandar em 2026-09-02 (`UNIDADE_MOEDA`, commit 5da90377). Desde então a renda saía SEM
     símbolo na tabela, também no Brasil;
   - a ficha do ponto recebia "R$" do servidor e o escrevia sobre a renda em DÓLAR da
     Argentina.

   As duas funções são exportadas dos componentes para este teste, no molde de
   `botoesDoStepper` (`StepperBar.tsx`): o vitest deste repo roda em node, sem jsdom. */

/** Mesma caixa de `lib/perfil.test.ts`: moeda oficial ARS, renda do pacote em USD. */
const AR: PerfilCliente = {
  pais: 'AR',
  nome: 'Argentina',
  locale: 'es-AR',
  moeda: { codigo: 'ARS', simbolo: '$', indicadores_renda: 'USD' },
  bbox: { lat_min: -55.2, lat_max: -21.6, lng_min: -74.0, lng_max: -53.4 },
  vista_padrao: { lat: -38.4, lng: -63.6, zoom: 3.6 },
  reguas: { pop_min_acionavel: 5000, capacidade_unidade_alunos: 2500 },
}

afterEach(() => {
  _resetarPerfilParaTeste()
})

describe('tabela da comparação (TabelaRanking)', () => {
  it('a renda volta a sair com o símbolo no Brasil', () => {
    expect(formatar(4500, UNIDADE_RENDA)).toBe('R$ 4.500')
  })

  it('na Argentina a renda sai em USD, e a moeda oficial com o símbolo do peso', () => {
    definirPerfil(AR)
    expect(formatar(508, UNIDADE_RENDA)).toBe('USD 508')
    expect(formatar(508, UNIDADE_MOEDA)).toBe('$ 508')
  })

  it('as outras unidades seguem como estavam', () => {
    expect(formatar(12.34, '%')).toBe('12,3%')
    expect(formatar(1.5, 'p.p.')).toBe('+1,5')
    expect(formatar(71.26, 'score')).toBe('71,3')
    expect(formatar(1234, 'alunos')).toBe('1.234')
    expect(formatar(null, UNIDADE_RENDA)).toBe(TEXTO_SEM_DADO)
  })
})

describe('critérios da ficha do ponto (Recomendacao)', () => {
  it('a renda sai com o símbolo da moeda da renda', () => {
    expect(valorFmt(4500, UNIDADE_RENDA)).toBe('R$ 4.500')
    definirPerfil(AR)
    expect(valorFmt(508, UNIDADE_RENDA)).toBe('USD 508')
  })

  it('as outras unidades seguem como estavam', () => {
    expect(valorFmt(71.26, 'score')).toBe('71,3')
    expect(valorFmt(66113, 'pessoas')).toBe('66.113')
    expect(valorFmt(null, UNIDADE_RENDA)).toBe(TEXTO_SEM_DADO)
  })
})
