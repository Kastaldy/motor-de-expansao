import { describe, expect, it } from 'vitest'

import { SINAIS, sinaisDoRegime } from './sinais'

describe('sinais medidos, por extenso', () => {
  it('traduz o regime vigente para linguagem de tela', () => {
    const s = sinaisDoRegime('s1,s6')
    expect(s.map((x) => x.rotulo)).toEqual(['Presença em agregador', 'Concorrentes por perto'])
    for (const x of s) expect(x.explica.length).toBeGreaterThan(10)
  })

  it('preserva a ordem canônica que o backend envia', () => {
    // `sinais_disponiveis` é montado iterando `SINAIS_ORDEM` no Python — nunca um `set`.
    // Reordenar aqui faria a tela contradizer o contrato.
    expect(sinaisDoRegime('s1,s3,s4,s6').map((x) => x.rotulo)).toEqual([
      'Presença em agregador',
      'Sumiu do agregador',
      'Cadastro parado',
      'Concorrentes por perto',
    ])
  })

  it('vazio, nulo e indefinido devolvem lista vazia (a seção some do tooltip)', () => {
    expect(sinaisDoRegime('')).toEqual([])
    expect(sinaisDoRegime(null)).toEqual([])
    expect(sinaisDoRegime(undefined)).toEqual([])
  })

  it('token DESCONHECIDO aparece cru, nunca é descartado', () => {
    // Um sinal novo no backend (s5) sairia feio, mas visível. Descartá-lo faria a declaração
    // de régua mentir por omissão — e é ela que diz sob qual base o número foi composto.
    const s = sinaisDoRegime('s1,s5')
    expect(s).toHaveLength(2)
    expect(s[1].rotulo).toBe('s5')
    expect(s[1].explica).toContain('não catalogado')
  })

  it('tolera espaço em volta dos tokens', () => {
    expect(sinaisDoRegime(' s1 , s6 ').map((x) => x.rotulo)).toEqual([
      'Presença em agregador',
      'Concorrentes por perto',
    ])
  })

  it('cobre TODOS os sinais do contrato, inclusive o inativo', () => {
    // O mapa é do CONTRATO (`SINAIS_ORDEM`), não do que está ativo hoje: o dia em que o
    // BLK-MA-08 remover o `s2` de `SINAIS_INATIVOS`, ele passa a viajar no payload — e sem
    // rótulo estrearia cru na tela, no mesmo PR em que alguém comemora ter ligado o sinal.
    for (const s of ['s1', 's2', 's3', 's4', 's6']) {
      expect(SINAIS[s]?.rotulo).toBeTruthy()
      expect(SINAIS[s]?.explica).toBeTruthy()
    }
  })

  it('nenhuma descrição afirma fragilidade da academia (DEC-028)', () => {
    // As frases descrevem o que foi MEDIDO, não o veredito. Enquanto S3/S4 estiverem imaturos,
    // afirmar fragilidade é vender o sinal 6 com o rótulo do 3.
    const texto = Object.values(SINAIS)
      .map((s) => `${s.rotulo} ${s.explica}`)
      .join(' ')
      .toLowerCase()
    for (const proibido of ['vulnerab', 'frágil', 'fragil', 'alvo', 'aquisi', 'fechar']) {
      expect(texto).not.toContain(proibido)
    }
  })

  it('cada descrição carrega a DIREÇÃO, que é o que permite ler o número', () => {
    // Sem direção, "Presença em agregador" não diz se aparecer em mais apps é bom ou ruim.
    expect(SINAIS.s1.explica).toContain('menos')
    expect(SINAIS.s6.explica).toContain('próxima')
    expect(SINAIS.s4.explica).toContain('sem')
  })
})
