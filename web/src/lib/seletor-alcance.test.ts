import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  AVISO_RELENDO_ALCANCE,
  ESTILO_ROTULO_ALCANCE,
  ESTILO_TRILHO_ALCANCE,
  ROTULO_SELETOR_ALCANCE,
  estiloDaOpcaoAlcance,
} from './seletor-alcance'

const pontoScreen = readFileSync(fileURLToPath(new URL('../screens/PontoScreen.tsx', import.meta.url)), 'utf-8')

/** Nenhuma cor cravada: o seletor acompanha os temas pelos tokens. */
const SEM_HEX = /#[0-9a-f]{3,8}\b|rgba?\(/i

describe('o seletor de alcance em destaque (pedido de 20/10/2026)', () => {
  it('a opção marcada é CHEIA na cor de ação do sistema; a desmarcada, sem fundo', () => {
    const marcada = estiloDaOpcaoAlcance(true)
    expect(marcada.background).toBe('var(--ac)')
    expect(marcada.color).toBe('var(--ac-on)')
    const livre = estiloDaOpcaoAlcance(false)
    expect(livre.background).toBe('transparent')
    expect(livre.color).toBe('var(--tx-soft)')
  })

  it('as opções dividem a largura por igual (controle segmentado, não pílulas)', () => {
    for (const m of [true, false]) {
      expect(estiloDaOpcaoAlcance(m).flex).toBe(1)
      expect(Number(estiloDaOpcaoAlcance(m).minHeight)).toBeGreaterThanOrEqual(36)
    }
    expect(ESTILO_TRILHO_ALCANCE.display).toBe('flex')
    expect(ESTILO_TRILHO_ALCANCE.flexWrap).toBeUndefined()
  })

  it('só tokens, nenhuma cor cravada', () => {
    const estilos = [ESTILO_TRILHO_ALCANCE, ESTILO_ROTULO_ALCANCE, estiloDaOpcaoAlcance(true), estiloDaOpcaoAlcance(false)]
    for (const e of estilos) expect(JSON.stringify(e)).not.toMatch(SEM_HEX)
  })

  it('o rótulo é visível e forte; a releitura é dita em texto', () => {
    expect(ROTULO_SELETOR_ALCANCE).toBe('Alcance da análise')
    expect(ESTILO_ROTULO_ALCANCE.color).toBe('var(--tx-strong)')
    expect(AVISO_RELENDO_ALCANCE).toMatch(/^Atualizando/)
  })

  it('a ficha desenha o seletor DENTRO da identificação, antes dos chips e dos números', () => {
    const identificacao = pontoScreen.indexOf("<Eyebrow dot>{area ? 'Área desenhada' : 'Ponto analisado'}</Eyebrow>")
    const seletor = pontoScreen.indexOf('<SeletorAlcance\n')
    const chipHex = pontoScreen.indexOf('<Chip>hex {ficha.hex_id}</Chip>')
    const socio = pontoScreen.indexOf("titulo={area ? 'Quem mora na área'")
    expect(identificacao).toBeGreaterThan(-1)
    expect(seletor).toBeGreaterThan(identificacao)
    expect(seletor).toBeLessThan(chipHex)
    expect(seletor).toBeLessThan(socio)
    // Um lugar só: o antigo, abaixo da identificação, saiu.
    expect(pontoScreen.split('<SeletorAlcance\n')).toHaveLength(2)
  })

  it('a ficha usa os estilos travados aqui e diz a releitura em voo', () => {
    expect(pontoScreen).toContain('style={estiloDaOpcaoAlcance(marcado)}')
    expect(pontoScreen).toContain('style={ESTILO_TRILHO_ALCANCE}')
    expect(pontoScreen).toContain('{ROTULO_SELETOR_ALCANCE}')
    expect(pontoScreen).toContain('{AVISO_RELENDO_ALCANCE}')
    expect(pontoScreen).toContain('aria-busy={trocando}')
    // A lógica não mudou: quem troca é o mesmo callback.
    expect(pontoScreen).toContain('onClick={() => onTrocar(a)}')
  })
})
