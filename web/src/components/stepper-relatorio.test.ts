import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { botoesDoStepper } from './StepperBar'

const fonte = readFileSync(fileURLToPath(new URL('./StepperBar.tsx', import.meta.url)), 'utf-8')

describe('botoesDoStepper — relatório municipal em todas as camadas', () => {
  it('no município, toda camada antes da última mostra avançar E o relatório', () => {
    for (let atual = 1; atual < 5; atual++) {
      expect(botoesDoStepper({ atual, total: 5, nivelUf: false })).toEqual({
        navegacao: 'proxima',
        relatorio: true,
      })
    }
  })

  it('na última camada só o relatório fica', () => {
    expect(botoesDoStepper({ atual: 5, total: 5, nivelUf: false })).toEqual({
      navegacao: null,
      relatorio: true,
    })
  })

  it('na visão de UF não há município, então não há relatório', () => {
    expect(botoesDoStepper({ atual: 2, total: 5, nivelUf: true })).toEqual({
      navegacao: 'proxima',
      relatorio: false,
    })
    expect(botoesDoStepper({ atual: 5, total: 5, nivelUf: true })).toEqual({
      navegacao: 'escolha-municipio',
      relatorio: false,
    })
  })

  it('o relatório é o ÚLTIMO botão da barra (ponta direita) e é ciano', () => {
    const iRelatorio = fonte.indexOf('{relatorio && (')
    expect(iRelatorio).toBeGreaterThan(fonte.indexOf('{navegacao && ('))
    expect(fonte.indexOf('<button', iRelatorio + 1)).toBeGreaterThan(-1)
    expect(fonte.indexOf('<button', fonte.indexOf('</button>', iRelatorio))).toBe(-1)
    const bloco = fonte.slice(iRelatorio)
    expect(bloco).toContain("background: 'var(--ac)',")
    expect(bloco).toContain("color: 'var(--ac-on)',")
  })
})
