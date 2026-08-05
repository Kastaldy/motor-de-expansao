import { describe, expect, it } from 'vitest'

import {
  apagarVizinho,
  digitosColados,
  digitosDoNumero,
  formatarMilhar,
  formatarNumero,
  mascarar,
  numeroDoTexto,
  parsePtBr,
  partesColadas,
  posCaret,
  passoSeta,
} from './mascara'

/**
 * Cada bloco cobre uma armadilha concreta da mascara viva. Nos casos de caret a
 * posicao vai marcada com "|" dentro da string, so' para a intencao ficar legivel —
 * a funcao recebe o indice, nao o marcador.
 */

/** "1.5|00" -> { bruto: "1.500", caret: 3 }. */
function comCaret(marcado: string): { bruto: string; caret: number } {
  const caret = marcado.indexOf('|')
  return { bruto: marcado.replace('|', ''), caret: caret < 0 ? marcado.length : caret }
}

describe('formatarMilhar', () => {
  it('poe o ponto de milhar pt-BR', () => {
    expect(formatarMilhar('1500')).toBe('1.500')
    expect(formatarMilhar('1234567')).toBe('1.234.567')
  })
  it('campo vazio continua vazio (nao vira "0")', () => {
    expect(formatarMilhar('')).toBe('')
  })
  it('zero sozinho e valor', () => {
    expect(formatarMilhar('0')).toBe('0')
  })
  it('descarta zero a esquerda', () => {
    expect(formatarMilhar('007')).toBe('7')
    expect(formatarMilhar('00')).toBe('0')
  })
})

describe('formatarNumero / digitosDoNumero / numeroDoTexto', () => {
  it('numero -> texto formatado', () => {
    expect(formatarNumero(20000)).toBe('20.000')
    expect(formatarNumero(0)).toBe('0')
  })
  it('NaN/Infinity viram vazio, nunca "Não disponível" dentro do input', () => {
    expect(formatarNumero(NaN)).toBe('')
    expect(formatarNumero(Infinity)).toBe('')
    expect(digitosDoNumero(NaN)).toBe('')
  })
  it('negativo e clampado em zero (nenhum campo do Cenario aceita negativo)', () => {
    expect(formatarNumero(-200)).toBe('0')
    expect(digitosDoNumero(-5)).toBe('0')
  })
  it('texto vazio -> undefined (e NAO zero)', () => {
    expect(numeroDoTexto('')).toBeUndefined()
    expect(numeroDoTexto('R$ ')).toBeUndefined()
  })
  it('le o numero do texto ja mascarado', () => {
    expect(numeroDoTexto('1.500')).toBe(1500)
    expect(numeroDoTexto('0')).toBe(0)
  })
})

describe('posCaret', () => {
  it('zero digitos a esquerda -> inicio do campo', () => {
    expect(posCaret('1.500', 0)).toBe(0)
  })
  it('para logo DEPOIS do n-esimo digito, atravessando o separador', () => {
    expect(posCaret('1.500', 1)).toBe(1)
    expect(posCaret('1.500', 2)).toBe(3)
    expect(posCaret('1.500', 4)).toBe(5)
  })
  it('mais digitos do que o texto tem -> fim do campo', () => {
    expect(posCaret('1.500', 9)).toBe(5)
  })
})

describe('mascarar — digitacao normal', () => {
  it('formata na tecla e mantem o caret depois do digito recem-digitado', () => {
    const r = mascarar('1500', 4, 5)
    expect(r.texto).toBe('1.500')
    expect(r.caret).toBe(5)
    expect(r.digitos).toBe('1500')
  })
  it('o separador que NASCE nao empurra o caret para tras', () => {
    // 4o digito de "100" -> "1.000": o caret tem 4 digitos a esquerda, e o ponto
    // recem-criado nao pode fazer ele parar antes do zero digitado.
    const r = mascarar('1000', 4, 5)
    expect(r.texto).toBe('1.000')
    expect(r.caret).toBe(5)
  })
  it('digitar no MEIO mantem o caret depois do digito inserido', () => {
    // Em "1.500", caret depois do "5", digita "9": o texto vira "15.900" e o ponto
    // ANDA de casa — o caret tem de andar com ele.
    const { bruto, caret } = comCaret('1.59|00')
    const r = mascarar(bruto, caret, 5)
    expect(r.texto).toBe('15.900')
    expect(r.caret).toBe(4) // "15.9|00"
    expect(r.digitos).toBe('15900')
  })
  it('caret no inicio permanece no inicio', () => {
    const { bruto, caret } = comCaret('|1.500')
    expect(mascarar(bruto, caret, 5).caret).toBe(0)
  })
})

describe('mascarar — letra, sinal e pontuacao', () => {
  it.each(['a', '-', '+', 'e', '.', ','])('tecla "%s" no fim nao deixa rastro', (c) => {
    const bruto = `1.500${c}`
    const r = mascarar(bruto, bruto.length, 5)
    expect(r.texto).toBe('1.500')
    expect(r.digitos).toBe('1500')
    // O caret volta para depois do ultimo digito — o React nao o joga para o fim
    // do campo porque o handler ja' escreveu esta mesma string no DOM.
    expect(r.caret).toBe(5)
  })
  it('letra digitada no MEIO nao move o caret nem muda o numero', () => {
    const { bruto, caret } = comCaret('1.5a|00')
    const r = mascarar(bruto, caret, 5)
    expect(r.texto).toBe('1.500')
    expect(r.caret).toBe(3) // continua entre o "5" e o "0"
  })
})

describe('mascarar — selecao substituida e ruido colado', () => {
  it('Ctrl+A e digitar por cima deixa o caret depois do unico digito', () => {
    const r = mascarar('7', 1, 5)
    expect(r.texto).toBe('7')
    expect(r.caret).toBe(1)
  })
  it('texto com ruido nao numerico e reduzido aos digitos', () => {
    const bruto = 'R$ 35.000'
    const r = mascarar(bruto, bruto.length, 7)
    expect(r.texto).toBe('35.000')
    expect(r.digitos).toBe('35000')
  })
})

describe('mascarar — campo vazio', () => {
  it('apagar tudo devolve texto vazio e NENHUM digito (nunca 0)', () => {
    const r = mascarar('', 0, 5)
    expect(r.texto).toBe('')
    expect(r.digitos).toBe('')
    expect(r.caret).toBe(0)
  })
  it('campo so com separador tambem e vazio', () => {
    expect(mascarar('.', 1, 5).digitos).toBe('')
  })
})

describe('mascarar — zero a esquerda', () => {
  it('"007" vira "7" e o caret desconta os zeros que sumiram a esquerda dele', () => {
    // "0|07": 1 digito a esquerda do caret, mas era um dos zeros removidos.
    const { bruto, caret } = comCaret('0|07')
    const r = mascarar(bruto, caret, 5)
    expect(r.texto).toBe('7')
    expect(r.caret).toBe(0)
  })
  it('digitar "5" no inicio de "0" nao deixa "05"', () => {
    const { bruto, caret } = comCaret('5|0')
    const r = mascarar(bruto, caret, 5)
    expect(r.texto).toBe('50')
    expect(r.caret).toBe(1)
  })
  it('zero sozinho sobrevive', () => {
    const r = mascarar('0', 1, 5)
    expect(r.texto).toBe('0')
    expect(r.digitos).toBe('0')
  })
})

describe('mascarar — teto de digitos', () => {
  it('digitar no fim de um campo cheio nao faz nada (digito excedente ignorado)', () => {
    const r = mascarar('999999', 6, 5)
    expect(r.texto).toBe('99.999')
    expect(r.caret).toBe(6) // caret preso no fim, sem pular
  })
  it('estouro IGNORA o excedente, como o input nativo', () => {
    // Esta funcao ja' grampeou em noves aqui, para resolver a colagem de valor grande.
    // Foi pior: o grampeamento pega TODO caminho, entao uma tecla a mais reescrevia o
    // numero inteiro ("12.345" + 1 tecla = "99.999") e destruia o que o operador ja'
    // tinha digitado. O corte por prefixo apenas ignora a tecla, que e' o que o input
    // nativo faz. O caso da COLAGEM e' grampeado no `onPaste` do CampoNumero, que sabe
    // que aquele excedente chegou de fora de uma vez so'.
    expect(mascarar('1500000000', 10, 5).texto).toBe('15.000')
    expect(mascarar('12000000', 8, 7).texto).toBe('1.200.000')
  })
  it('cada campo tem o seu teto', () => {
    expect(mascarar('99999999', 8, 7).texto).toBe('9.999.999') // aluguel
    expect(mascarar('99999', 5, 4).texto).toBe('9.999') // ticket
  })
})

describe('parsePtBr / digitosColados — colagem', () => {
  it.each([
    ['R$ 35.000', 35000],
    ['1 500', 1500],
    ['1.500 m²', 1500],
    ['1.500 m2', 1500],
    ['20000,00', 20000],
    ['R$ 20.000,49/mês', 20000],
    ['R$ 20.000,50/mês', 20001],
  ])('cola "%s" -> %i', (txt, esperado) => {
    expect(Math.round(parsePtBr(txt) as number)).toBe(esperado)
  })
  it('"35,000" e trinta e cinco: em pt-BR a virgula e decimal', () => {
    // Ambiguidade real, resolvida pela MESMA gramatica do parseNum da secao
    // Investimento. Uma segunda gramatica na mesma sidebar seria pior.
    expect(parsePtBr('35,000')).toBe(35)
  })
  it('NBSP e espaco fino tambem sao separador de milhar (e o que o Intl produz)', () => {
    expect(parsePtBr('1 500')).toBe(1500)
    expect(parsePtBr('1 500')).toBe(1500)
  })
  it('sinal e descartado (nenhum campo do Cenario e negativo)', () => {
    expect(parsePtBr('-200')).toBe(200)
  })
  it('texto sem digito nenhum -> undefined', () => {
    expect(parsePtBr('abc')).toBeUndefined()
    expect(parsePtBr('')).toBeUndefined()
  })
  it('digitosColados entrega digitos prontos para o pipeline', () => {
    expect(digitosColados('R$ 35.000')).toBe('35000')
    expect(digitosColados('abc')).toBe('')
  })
  it('colagem absurda nao escapa para notacao exponencial', () => {
    expect(/^\d+$/.test(digitosColados('9'.repeat(40)))).toBe(true)
  })
})

describe('apagarVizinho — Backspace/Delete em cima do separador', () => {
  it('Backspace depois do ponto apaga o DIGITO anterior, nao o ponto', () => {
    const { bruto, caret } = comCaret('1.|500')
    const r = apagarVizinho(bruto, caret, -1)
    expect(r).not.toBeNull()
    const m = mascarar(r!.bruto, r!.caret, 5)
    expect(m.texto).toBe('500') // e nao "1.500" de volta, com a tecla parecendo morta
    expect(m.caret).toBe(0)
  })
  it('Delete em cima do ponto apaga o digito SEGUINTE', () => {
    const { bruto, caret } = comCaret('1|.500')
    const r = apagarVizinho(bruto, caret, 1)
    expect(r).not.toBeNull()
    const m = mascarar(r!.bruto, r!.caret, 5)
    expect(m.texto).toBe('100')
    expect(m.caret).toBe(1)
  })
  it('vizinho digito -> null (o comportamento nativo ja faz o certo)', () => {
    expect(apagarVizinho('1.500', 5, -1)).toBeNull()
    expect(apagarVizinho('1.500', 0, 1)).toBeNull()
  })
  it('borda do campo -> null', () => {
    expect(apagarVizinho('1.500', 0, -1)).toBeNull()
    expect(apagarVizinho('1.500', 5, 1)).toBeNull()
  })
  it('so separador do outro lado -> null (nao ha digito para apagar)', () => {
    expect(apagarVizinho('..', 2, -1)).toBeNull()
    expect(apagarVizinho('..', 0, 1)).toBeNull()
  })
})

/* ===========================================================================
   MODO DECIMAL (`casas > 0`) — os campos "Juros equip. (% a.m.)" e "Taxa mínima
   do negócio (% a.a.)" do Investimento. Tudo abaixo é regra NOVA; os blocos
   acima continuam sendo a prova de que `casas = 0` não mudou de comportamento.
   =========================================================================== */

describe('mascarar decimal — a virgula tem de ser digitavel', () => {
  it('"1," sobrevive na tela, com valor 1', () => {
    // Se a mascara normalizasse "1," para "1" a cada tecla, a virgula seria
    // IMPOSSIVEL de digitar: a tecla morreria e nunca haveria uma casa decimal.
    // Quem normaliza e o blur, que reescreve o texto a partir do numero.
    const r = mascarar('1,', 2, 3, 1)
    expect(r.texto).toBe('1,')
    expect(r.valor).toBe(1)
    expect(r.caret).toBe(2) // DEPOIS da virgula, senao o proximo digito vira "18"
  })
  it('o digito seguinte cai na FRACAO, e nao na parte inteira', () => {
    const r = mascarar('1,8', 3, 3, 1)
    expect(r.texto).toBe('1,8')
    expect(r.valor).toBe(1.8)
    expect(r.caret).toBe(3)
  })
  it('caret ANTES da virgula continua na parte inteira ("1|,8")', () => {
    // A ambiguidade que a ancora (parte, contagem) resolve: "1|,8" e "1,|8" tem
    // 1 digito a esquerda nos dois casos.
    const r = mascarar('1,8', 1, 3, 1)
    expect(r.texto).toBe('1,8')
    expect(r.caret).toBe(1)
  })
  it('caret logo DEPOIS da virgula, com a fracao ja preenchida ("1,|8")', () => {
    expect(mascarar('1,8', 2, 3, 1).caret).toBe(2)
  })
  it('virgula sem parte inteira vira ",5" e vale 0,5', () => {
    const r = mascarar(',5', 2, 3, 1)
    expect(r.texto).toBe(',5')
    expect(r.valor).toBe(0.5)
    expect(r.caret).toBe(2)
  })
})

describe('mascarar decimal — segunda virgula e ruido', () => {
  it('a PRIMEIRA virgula e a decimal; a segunda nao deixa rastro', () => {
    // Reinterpretar a ULTIMA virgula como decimal transformaria "1,50," noutro
    // numero em silencio. Descartar nao muda contagem de digito nenhuma, entao o
    // caret fica onde estava.
    const r = mascarar('1,5,', 4, 3, 1)
    expect(r.texto).toBe('1,5')
    expect(r.valor).toBe(1.5)
    expect(r.caret).toBe(3)
  })
  it('virgula digitada no MEIO da fracao tambem some', () => {
    const r = mascarar('1,2,5', 5, 3, 2)
    expect(r.texto).toBe('1,25')
    expect(r.valor).toBe(1.25)
  })
})

describe('mascarar decimal — casas limitadas', () => {
  it('a 3a casa nao faz nada, com o caret preso no fim (casas = 2)', () => {
    const r = mascarar('1,853', 5, 3, 2)
    expect(r.texto).toBe('1,85')
    expect(r.caret).toBe(4)
    expect(r.valor).toBe(1.85)
  })
  it('TRUNCA, nunca arredonda ao digitar — "1,87" com casas=1 e "1,8" e nao "1,9"', () => {
    // Arredondar no meio da digitacao faria a 3a tecla MUDAR a 2a casa: o numero
    // mudaria sozinho debaixo do dedo e a tecla seguinte seria engolida.
    expect(mascarar('1,87', 4, 3, 1).texto).toBe('1,8')
  })
})

describe('mascarar decimal — milhar na parte inteira', () => {
  it('"1.234,56": milhar no inteiro, fracao VERBATIM', () => {
    const r = mascarar('1234,56', 7, 7, 2)
    expect(r.texto).toBe('1.234,56')
    expect(r.caret).toBe(8)
    expect(r.valor).toBe(1234.56)
  })
  it('caret na parte inteira atravessa o ponto que nasceu', () => {
    const { bruto, caret } = comCaret('1234|,56')
    expect(mascarar(bruto, caret, 7, 2).caret).toBe(5) // "1.234|,56"
  })
  it('maxDigitos continua medindo a PARTE INTEIRA', () => {
    const r = mascarar('999,9', 5, 2, 1)
    expect(r.texto).toBe('99,9')
  })
})

describe('mascarar — valor e o unico numero confiavel', () => {
  it('campo vazio -> valor undefined (nem 0, nem o ultimo numero)', () => {
    expect(mascarar('', 0, 5).valor).toBeUndefined()
    expect(mascarar('abc', 3, 5, 2).valor).toBeUndefined()
    expect(mascarar(',', 1, 3, 2).valor).toBeUndefined()
  })
  it('em campo inteiro o valor e o de sempre', () => {
    expect(mascarar('1500', 4, 5).valor).toBe(1500)
    expect(mascarar('0', 1, 5).valor).toBe(0)
  })
  it('os DIGITOS de "1,8" sao "1" — quem le digitos nao pode montar o numero', () => {
    // O erro que este campo previne: `numeroDoTexto` dos digitos crus de "1,8"
    // daria DEZOITO por cento ao mes, com cara de numero legitimo.
    const r = mascarar('1,8', 3, 3, 1)
    expect(r.digitos).toBe('1')
    expect(r.inteiro).toBe('1')
    expect(r.fracao).toBe('8')
    expect(r.valor).toBe(1.8)
  })
  it('com casas = 0 a virgula ENCERRA o numero, nao concatena', () => {
    // Este teste ja' afirmou o contrario ('18'). Concatenar as duas partes fazia
    // "350,50" digitado num campo inteiro virar 35050 — CEM vezes o valor, com cara de
    // numero legitimo e a caminho do motor. Campo inteiro nao tem casa decimal: o que
    // vem depois da virgula e' descartado, como o input nativo faz ao recusar a tecla.
    const r = mascarar('1,8', 3, 5)
    expect(r.texto).toBe('1')
    expect(r.valor).toBe(1)
    expect(mascarar('350,50', 6, 5).valor).toBe(350)
  })
  it('com casas > 0 o PONTO tambem separa decimal (teclado numerico)', () => {
    // "1.8" em Juros equip. virava 18: dezoito por cento ao mes passa no `le=1` do
    // backend (0,18 < 1) e vai calcular em silencio. Quem digita no teclado numerico
    // so' tem ponto. So' vale onde o campo nunca exibe milhar (max <= 3 digitos).
    expect(mascarar('1.8', 3, 3, 1).valor).toBe(1.8)
    expect(mascarar('12.5', 4, 3, 1).valor).toBe(12.5)
    // Campo largo mantem o ponto como MILHAR — nao pode virar decimal.
    expect(mascarar('1.500', 5, 5, 2).valor).toBe(1500)
  })
})

describe('formatarNumero — casas e valor ausente', () => {
  it('sem casas, arredonda como sempre', () => {
    expect(formatarNumero(1.8)).toBe('2')
  })
  it('com casas, PRESERVA a fracao — o blur nao pode reescrever 1,8 como 2', () => {
    // O ponto de integracao mais perigoso da mudanca: o onBlur reescreve o texto a
    // partir do numero, e com Math.round o operador digitaria 1,8, sairia do campo
    // e levaria 2% a.m. para o motor sem nenhum sinal.
    expect(formatarNumero(1.8, 1)).toBe('1,8')
    expect(formatarNumero(1.8, 2)).toBe('1,8')
    expect(formatarNumero(1.85, 2)).toBe('1,85')
  })
  it('sem zero a direita: 25 nao vira "25,00"', () => {
    expect(formatarNumero(25, 2)).toBe('25')
    expect(formatarNumero(0, 2)).toBe('0')
  })
  it('milhar e fracao juntos', () => {
    expect(formatarNumero(1234.5, 2)).toBe('1.234,5')
  })
  it('valor AUSENTE vira campo vazio — e o que preserva o campo opcional vazio', () => {
    expect(formatarNumero(undefined)).toBe('')
    expect(formatarNumero(undefined, 2)).toBe('')
    expect(formatarNumero(null, 2)).toBe('')
  })
})

describe('partesColadas — colagem sem perder a fracao', () => {
  it('colar "1,8" num campo decimal da 1,8 (e nao 2, como digitosColados daria)', () => {
    expect(digitosColados('1,8')).toBe('2') // o caminho inteiro arredonda, de proposito
    expect(partesColadas('1,8', 2)).toEqual({ inteiro: '1', fracao: '8' })
  })
  it('na COLAGEM arredondar e correto: o evento e unico, nao ha proxima tecla', () => {
    expect(partesColadas('1,875', 2)).toEqual({ inteiro: '1', fracao: '88' })
  })
  it('campo inteiro (casas = 0) segue arredondando para digitos', () => {
    expect(partesColadas('R$ 35.000', 0)).toEqual({ inteiro: '35000', fracao: '' })
    expect(partesColadas('20.000,50')).toEqual({ inteiro: '20001', fracao: '' })
  })
  it('texto sem digito nao insere nada', () => {
    expect(partesColadas('abc', 2)).toEqual({ inteiro: '', fracao: '' })
  })
  it('sem zero a direita: "25,00" colado vira 25', () => {
    expect(partesColadas('25,00', 2)).toEqual({ inteiro: '25', fracao: '' })
  })
})

describe('apagarVizinho decimal — a virgula e do USUARIO, o ponto e do formatador', () => {
  it('SEM o flag, Backspace na virgula come o digito da parte inteira', () => {
    // Documentado como o comportamento ERRADO para campo decimal: e' a razao de o
    // flag existir. Para o ponto de milhar, atravessar continua sendo o certo.
    const r = apagarVizinho('1,8', 2, -1)
    expect(r!.bruto).toBe(',8')
  })
  it('COM o flag, Backspace apaga a propria virgula e junta as partes', () => {
    const r = apagarVizinho('1,8', 2, -1, true)
    expect(r).toEqual({ bruto: '18', caret: 1 })
    const m = mascarar(r!.bruto, r!.caret, 3, 1)
    expect(m.texto).toBe('18')
    expect(m.caret).toBe(1) // o caret fica onde a virgula estava
  })
  it('Delete em cima da virgula faz o mesmo', () => {
    expect(apagarVizinho('1,8', 1, 1, true)).toEqual({ bruto: '18', caret: 1 })
  })
  it('a juncao que ESTOURA o teto descarta os excedentes da FRACAO, nao grampeia', () => {
    // Grampear daria "99", um numero que ninguem digitou. Aqui o excedente e
    // identificavel: e' o que estava depois da virgula.
    expect(apagarVizinho('12,34', 3, -1, true, 2)!.bruto).toBe('12')
    expect(apagarVizinho('99,99', 3, -1, true, 2)!.bruto).toBe('99')
    expect(apagarVizinho('1,85', 1, 1, true, 3)!.bruto).toBe('185')
  })
  it('o ponto de milhar continua sendo ATRAVESSADO mesmo em campo decimal', () => {
    const r = apagarVizinho('1.500,5', 2, -1, true, 7)
    expect(r).not.toBeNull()
    expect(mascarar(r!.bruto, r!.caret, 7, 1).texto).toBe('500,5')
  })
})

describe('passoSeta — incremento por ArrowUp/ArrowDown', () => {
  it('sobe e desce na grade do step', () => {
    expect(passoSeta(1500, 50, 1, 200)).toBe(1550)
    expect(passoSeta(1500, 50, -1, 200)).toBe(1450)
  })
  it('valor fora da grade e ARREDONDADO para o degrau, como o input nativo', () => {
    expect(passoSeta(147, 5, 1, 0)).toBe(150) // e nao 152
    expect(passoSeta(147, 5, -1, 0)).toBe(145)
  })
  it('a grade e ancorada no min', () => {
    expect(passoSeta(210, 50, 1, 200)).toBe(250)
    expect(passoSeta(210, 50, -1, 200)).toBe(200)
  })
  it('respeita min e max — as setas sao o unico lugar onde eles valem', () => {
    expect(passoSeta(200, 50, -1, 200)).toBe(200)
    expect(passoSeta(3, 1, 1, 0, 3)).toBe(3)
    expect(passoSeta(100, 1000, -1, 0)).toBe(0)
  })
  it('aluguel: 20.000 anda de 1.000 em 1.000', () => {
    expect(passoSeta(20000, 1000, 1, 0)).toBe(21000)
    expect(passoSeta(20500, 1000, -1, 0)).toBe(20000)
  })
  it('step FRACIONARIO exige casas — sem elas o Math.round zerava o passo', () => {
    // Juros de equipamentos: 1,8 -> 1,9. Com `Math.round` a seta saltaria de 1 em 1
    // ou travaria, e a seta e' justamente o que compensa a perda do spinner nativo.
    expect(passoSeta(1.8, 0.1, 1, 0, 100, 1)).toBe(1.9)
    expect(passoSeta(1.8, 0.1, -1, 0, 100, 1)).toBe(1.7)
  })
  it('campo VAZIO parte do min: o primeiro ArrowUp entrega exatamente um step', () => {
    // E NAO o padrao do motor: partir dele materializaria no payload um numero que
    // ninguem digitou, e o campo pararia de acompanhar o config.py.
    expect(passoSeta(0, 0.1, 1, 0, 100, 1)).toBe(0.1)
    expect(passoSeta(1, 1, 1, 1, 12)).toBe(2)
  })
})
