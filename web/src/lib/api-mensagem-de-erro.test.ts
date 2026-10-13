import { describe, expect, it } from 'vitest'

import { mensagemDoDetalhe } from './api'

/**
 * O 422 do piloto devolve `detail` como LISTA de erros do pydantic
 * (`_erro_de_validacao`, web/server/app.py). O cliente fazia `String(detalhe)` nessa
 * lista, e `String([{…}])` dá exatamente **"[object Object]"** — a mensagem real era
 * engolida em TODO 422 do app, nos dois países, desde o commit original do piloto
 * (2026-07-20).
 *
 * Em 2026-10-13 um operador digitou `0` em "Parcelas franquia" na instância argentina.
 * A tela mostrou só "[object Object]": nem o campo, nem a regra. O corpo abaixo é o
 * que o servidor respondeu — reconstituído do tamanho registrado na trilha de acesso
 * (135 bytes) e confirmado contra o modelo.
 */
const CORPO_DO_MARCOS = [
  {
    type: 'greater_than',
    loc: ['body', 'parcelas_franquia'],
    msg: 'Input should be greater than 0',
    input: 0,
    ctx: { gt: 0 },
  },
]

describe('o detalhe de um erro nunca vira "[object Object]"', () => {
  it('o 422 real de 2026-10-13 vira texto que nomeia o campo e a regra', () => {
    const m = mensagemDoDetalhe(CORPO_DO_MARCOS, 422)
    expect(m).not.toContain('[object Object]')
    expect(m).toContain('parcelas_franquia')
    expect(m).toContain('maior que 0')
  })

  it('NENHUM formato de `detail` produz "[object Object]"', () => {
    /* A regressão não é "a lista": é QUALQUER coisa que não seja texto caindo num
       `String()`. Varre os formatos que o backend pode servir — e um objeto solto,
       que é o que um handler nosso devolveria se um dia parasse de mandar texto. */
    const formatos: unknown[] = [
      CORPO_DO_MARCOS,
      [...CORPO_DO_MARCOS, { type: 'missing', loc: ['body', 'demanda'], msg: 'Field required' }],
      { type: 'greater_than', loc: ['body', 'm2'], ctx: { gt: 0 } },
      [{ loc: ['body', 'tickets_studios', 0], type: 'greater_than', ctx: { gt: 0 } }],
      [],
      {},
      null,
      undefined,
    ]
    for (const f of formatos) {
      expect(mensagemDoDetalhe(f, 422), `formato ${JSON.stringify(f)}`).not.toContain(
        '[object Object]',
      )
    }
  })

  it('texto simples atravessa intacto (o 403 e o 503 do piloto mandam string)', () => {
    const t = 'Seu usuário não tem acesso a esta área do piloto. Fale com o Felipe.'
    expect(mensagemDoDetalhe(t, 403)).toBe(t)
  })

  it('dois campos reprovados aparecem os DOIS', () => {
    const m = mensagemDoDetalhe(
      [
        { type: 'greater_than', loc: ['body', 'parcelas_obra'], ctx: { gt: 0 } },
        { type: 'less_than_equal', loc: ['body', 'prazo_equipamentos'], ctx: { le: 60 } },
      ],
      422,
    )
    expect(m).toContain('parcelas_obra')
    expect(m).toContain('prazo_equipamentos')
  })

  it('o índice de um item de lista NÃO vira nome de campo', () => {
    /* `loc` de `tickets_studios[0]` é ["body","tickets_studios",0]: o último trecho é
       um NÚMERO. Pegar "o último elemento" daria o campo chamado "0". */
    const m = mensagemDoDetalhe(
      [{ type: 'greater_than', loc: ['body', 'tickets_studios', 0], ctx: { gt: 0 } }],
      422,
    )
    expect(m).toContain('tickets_studios')
    expect(m).not.toMatch(/"0"/)
  })

  it('tipo que não traduzimos cai no `msg` do pydantic, não em texto vazio', () => {
    const m = mensagemDoDetalhe(
      [{ type: 'string_pattern_mismatch', loc: ['body', 'formato'], msg: 'String should match' }],
      422,
    )
    expect(m).toContain('String should match')
  })

  it('lista vazia ainda diz alguma coisa, com o status', () => {
    expect(mensagemDoDetalhe([], 500)).toContain('500')
  })
})
