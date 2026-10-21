/**
 * A viagem da unidade até o território dela, por COMPORTAMENTO (revisão de 21/10/2026: a
 * fiação do `MapScreen` só tinha testes de texto). Cada caso reproduz uma sequência real de
 * gestos, com a resposta da lista de municípios chegando DEPOIS.
 */
import { describe, expect, it } from 'vitest'

import { criarViagemUnidade } from './viagem-unidade'

type Carga = { unidade: string }

/** O que o `MapScreen` faz quando a lista chega: só troca se a escolha ainda vale. */
function respostaChega(v: ReturnType<typeof criarViagemUnidade<Carga>>, seq: number, chave: string) {
  if (!v.vale(seq)) return false
  return v.embarcar(seq, chave, { unidade: 'U' })
}

describe('a viagem da unidade', () => {
  it('sem gesto no meio: a resposta troca o território e a ficha atravessa a troca', () => {
    const v = criarViagemUnidade<Carga>()
    const seq = v.iniciar()
    expect(respostaChega(v, seq, 'RJ|Niterói')).toBe(true)
    expect(v.chegar('RJ|Niterói')).toEqual({ unidade: 'U' })
  })

  it('gesto com a lista em voo (hexágono, imóvel, ponto, busca): a resposta não troca nada', () => {
    const v = criarViagemUnidade<Carga>()
    const seq = v.iniciar()
    v.cancelar()
    expect(respostaChega(v, seq, 'RJ|Niterói')).toBe(false)
    // e o contexto, que não mudou por ela, não devolve ficha nenhuma
    expect(v.chegar('SP|São Paulo')).toBeNull()
  })

  it('desmontar o mapa com a lista em voo: a resposta que chega depois não troca nada', () => {
    const v = criarViagemUnidade<Carga>()
    const seq = v.iniciar()
    v.cancelar() // o cleanup da desmontagem
    expect(respostaChega(v, seq, 'RJ|Niterói')).toBe(false)
  })

  it('outra unidade escolhida: só a resposta da ÚLTIMA vale', () => {
    const v = criarViagemUnidade<Carga>()
    const primeira = v.iniciar()
    const segunda = v.iniciar()
    expect(respostaChega(v, primeira, 'RJ|Niterói')).toBe(false)
    expect(respostaChega(v, segunda, 'SP|Santos')).toBe(true)
    expect(v.chegar('SP|Santos')).toEqual({ unidade: 'U' })
  })

  it('escolher outra unidade depois do embarque descarta a carga da anterior', () => {
    const v = criarViagemUnidade<Carga>()
    const seq = v.iniciar()
    respostaChega(v, seq, 'RJ|Niterói')
    v.iniciar()
    expect(v.chegar('RJ|Niterói')).toBeNull()
  })

  it('troca de território à mão (contexto diferente do pedido): fecha a ficha e cancela o pendente', () => {
    const v = criarViagemUnidade<Carga>()
    const seq = v.iniciar()
    expect(v.chegar('MG|Belo Horizonte')).toBeNull()
    expect(respostaChega(v, seq, 'RJ|Niterói')).toBe(false)
  })

  it('a carga é entregue UMA vez: a troca seguinte fecha a ficha normalmente', () => {
    const v = criarViagemUnidade<Carga>()
    const seq = v.iniciar()
    respostaChega(v, seq, 'RJ|Niterói')
    expect(v.chegar('RJ|Niterói')).not.toBeNull()
    expect(v.chegar('RJ|Niterói')).toBeNull()
  })
})
