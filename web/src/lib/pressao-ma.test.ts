import { describe, expect, it } from 'vitest'

import { rotuloDoRegime, SINAL_ROTULO } from './pressao-ma'

describe('rótulo do regime de sinais', () => {
  it('traduz o regime vigente para linguagem de tela', () => {
    expect(rotuloDoRegime('s1,s6')).toBe('presença em agregador · pressão competitiva')
  })

  it('preserva a ordem canônica que o backend envia', () => {
    // `sinais_disponiveis` é montado iterando `SINAIS_ORDEM` no Python — nunca um `set`.
    // Reordenar aqui faria a tela contradizer o contrato.
    expect(rotuloDoRegime('s1,s3,s4,s6')).toBe(
      'presença em agregador · churn · cadastro parado · pressão competitiva',
    )
  })

  it('vazio, nulo e indefinido devolvem string vazia (a linha some do tooltip)', () => {
    expect(rotuloDoRegime('')).toBe('')
    expect(rotuloDoRegime(null)).toBe('')
    expect(rotuloDoRegime(undefined)).toBe('')
  })

  it('token DESCONHECIDO sai cru, nunca descartado', () => {
    // Um sinal novo no backend (s5) apareceria feio, mas visível. Descartá-lo faria a
    // declaração de regime mentir por omissão — e é ela que diz sob qual régua o número foi
    // composto.
    expect(rotuloDoRegime('s1,s5')).toBe('presença em agregador · s5')
  })

  it('tolera espaço em volta dos tokens', () => {
    expect(rotuloDoRegime(' s1 , s6 ')).toBe('presença em agregador · pressão competitiva')
  })

  it('cobre TODOS os sinais do contrato, inclusive o inativo', () => {
    // O mapa é do CONTRATO (`SINAIS_ORDEM` em contrato.py), não do que está ativo hoje:
    // reativar o s2 não pode fazer o rótulo sumir em silêncio.
    for (const s of ['s1', 's2', 's3', 's4', 's6']) {
      expect(SINAL_ROTULO[s]).toBeTruthy()
    }
  })

  it('nenhum rótulo escapa para vocabulário de vulnerabilidade (DEC-028)', () => {
    const texto = Object.values(SINAL_ROTULO).join(' ').toLowerCase()
    for (const proibido of ['vulnerab', 'alvo', 'aquisi']) {
      expect(texto).not.toContain(proibido)
    }
  })
})
