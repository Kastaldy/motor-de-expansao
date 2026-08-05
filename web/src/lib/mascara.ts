/**
 * MASCARA VIVA de milhar pt-BR — funcoes PURAS, sem nenhum DOM.
 *
 * Existe para os campos numericos do Cenario da viabilidade mostrarem o ponto de
 * milhar ENQUANTO a pessoa digita (1500 vira "1.500" na tecla, nao no rotulo).
 *
 * POR QUE A LOGICA MORA AQUI, E NAO DENTRO DO COMPONENTE: o runner do piloto
 * (vitest.config.ts) roda em ambiente 'node' e so' casa `src/**\/*.test.ts` — nao
 * ha DOM nem testing-library. Logica escrita dentro do .tsx ficaria sem nenhuma
 * rede de seguranca. Entao o miolo (digitos -> texto, caret, colagem, seta) e'
 * funcao pura testada aqui, e components/CampoNumero.tsx fica deliberadamente
 * burro: le o input, chama estas funcoes, escreve de volta.
 *
 * GRAMATICA DE ENTRADA: "." e espaco sao separador de milhar e somem, a PRIMEIRA
 * virgula e' decimal. E' a mesma gramatica que a secao Investimento usava no
 * `parseNum` (ViabilityScreen.tsx) antes de migrar para ca'. Duas gramaticas de
 * numero na mesma sidebar seria pior que qualquer uma das duas isoladamente.
 * Consequencia assumida e' visivel no ato: colar "35,000" da' 35 (leitura pt-BR),
 * nao 35 mil.
 *
 * MODO INTEIRO x MODO DECIMAL: todo o pipeline recebe `casas` (default 0). Com
 * `casas = 0` a virgula e' ruido e o codigo percorrido e' EXATAMENTE o de antes —
 * e' por isso que a extensao decimal nao pode regredir os campos do Cenario.
 * Com `casas > 0` a primeira virgula e' aceita e a fracao e' TRUNCADA em `casas`
 * digitos ao digitar (arredondar no meio da digitacao engoliria a proxima tecla);
 * so' a COLAGEM arredonda. `maxDigitos` continua medindo a PARTE INTEIRA nos dois
 * modos, senao a mesma prop mediria coisas diferentes em cada campo.
 *
 * Todo campo aqui e' NAO-NEGATIVO. Fracao colada em campo inteiro e' arredondada e
 * o sinal e' descartado — nao existe aluguel de -R$ 200.
 */

import { num } from './format'

const RE_DIGITO = /[0-9]/

function ehDigito(c: string | undefined): boolean {
  return c !== undefined && RE_DIGITO.test(c)
}

/** So' os digitos ASCII. `\d` em JS nao casa numeral arabe-indico — proposital. */
function apenasDigitos(txt: string): string {
  return txt.replace(/\D/g, '')
}

/** "007" -> "7"; "0" continua "0" (zero e' valor, zero a esquerda e' ruido). */
function semZeroEsquerda(digitos: string): string {
  return digitos.replace(/^0+(?=\d)/, '')
}

/**
 * Teto de sanidade para colagem absurda. Acima de 1e15 o `String(n)` do V8 escorrega
 * para notacao exponencial ("1e+21") e a mascara viraria lixo. Como o teto de digitos
 * de cada campo e' 7, cortar aqui nao perde nada real.
 */
const VALOR_MAX = 1e15

/** Digitos de um numero, sempre em notacao decimal simples. Negativo vira "0". */
export function digitosDoNumero(v: number): string {
  if (!Number.isFinite(v)) return ''
  const n = Math.round(Math.min(Math.max(v, 0), VALOR_MAX))
  return String(n)
}

/**
 * Texto exibido a partir de um NUMERO (sincronizacao valor -> campo). String vazia
 * para valor invalido OU AUSENTE: o campo vazio e' estado legitimo — de digitacao no
 * Cenario, e de "usa o padrao do motor" no Investimento —, e "Não disponível" dentro
 * de uma caixa de input nao faz sentido nenhum.
 *
 * `casas` NAO e' cosmetico: sem ele o `Math.round` reescreveria "1,8" como "2" no
 * blur, uma corrupcao de 10x no gesto mais banal da tela. Exibe SEM zero a direita
 * (1,8 e nao 1,80; 25 e nao 25,00) — o campo e' de digitacao, nao de leitura.
 */
export function formatarNumero(v: number | null | undefined, casas = 0): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return ''
  const x = Math.min(Math.max(v, 0), VALOR_MAX)
  const c = Math.max(0, Math.floor(casas))
  if (c === 0) return num(Math.round(x))
  const [i, f = ''] = x.toFixed(c).split('.')
  const fracao = f.replace(/0+$/, '')
  return num(Number(i)) + (fracao ? `,${fracao}` : '')
}

/** Texto exibido a partir de uma sequencia de DIGITOS. "" -> "" (campo vazio). */
export function formatarMilhar(digitos: string): string {
  const d = semZeroEsquerda(apenasDigitos(digitos))
  if (!d) return ''
  return num(Number(d))
}

/** Numero do texto ja' mascarado. `undefined` para campo vazio — nunca 0, nunca NaN. */
export function numeroDoTexto(texto: string): number | undefined {
  const d = apenasDigitos(texto)
  if (!d) return undefined
  const n = Number(d)
  return Number.isFinite(n) ? n : undefined
}

/**
 * Posicao do caret DEPOIS do n-esimo digito do texto formatado.
 *
 * A ancora e' o DIGITO, nunca o caractere: a formatacao insere e remove pontos, entao
 * contar caracteres a esquerda do caret erra por um a cada separador que nasce ou morre.
 */
export function posCaret(formatado: string, nDigitos: number): number {
  if (nDigitos <= 0) return 0
  let vistos = 0
  for (let i = 0; i < formatado.length; i++) {
    if (ehDigito(formatado[i])) {
      vistos++
      if (vistos === nDigitos) return i + 1
    }
  }
  return formatado.length
}

export interface Mascarado {
  /** Texto a exibir no input (ja' com ponto de milhar e, se houver, a virgula). */
  texto: string
  /**
   * Digitos da PARTE INTEIRA normalizados. "" = sem parte inteira. Com `casas = 0`
   * e' o campo inteiro, como sempre foi; com `casas > 0` NAO e' o numero — ler
   * `digitos` de "1,8" da' "1" e ler os digitos crus daria DEZOITO. Use `valor`.
   */
  digitos: string
  /** Parte inteira (= `digitos`, com o nome que o modo decimal pede). */
  inteiro: string
  /** Casas decimais ja' truncadas em `casas`. "" quando nao ha virgula. */
  fracao: string
  /**
   * O NUMERO do campo. `undefined` = campo vazio, que nao e' zero nem o ultimo
   * valor. Calculado aqui dentro justamente para o componente nunca precisar
   * remontar o numero a partir de `digitos`.
   */
  valor: number | undefined
  /** Posicao do caret dentro de `texto`. */
  caret: number
}

/**
 * Pipeline da tecla: le o valor BRUTO que o browser ja' escreveu no input mais a
 * posicao do caret, e devolve o texto formatado com o caret no lugar certo.
 *
 * Nunca reconstruir o valor a partir de `event.key`: ler `input.value` faz
 * substituicao de selecao, arrastar-e-soltar, autofill e undo do browser caírem
 * todos neste mesmo caminho, de graca.
 *
 * `maxDigitos` e' teto por CONTAGEM DE DIGITOS DA PARTE INTEIRA. Ao estourar, o valor
 * e' GRAMPEADO no maior numero representavel (todos 9), nunca cortado pelo prefixo —
 * ver o comentario no corpo. Digitar no fim de um campo cheio continua nao fazendo nada.
 *
 * `casas > 0` liga o modo decimal. A ANCORA DO CARET deixa de ser "quantos digitos ha'
 * a esquerda" e passa a ser o par (PARTE, quantos digitos dentro da parte): "1|,8" e
 * "1,|8" tem 1 digito a esquerda nos DOIS casos, entao a contagem sozinha jogaria o
 * caret para antes da virgula e o proximo digito cairia na parte inteira ("1,8" -> "18").
 */
export function mascarar(
  bruto: string,
  caretBruto: number,
  maxDigitos: number,
  casas = 0,
): Mascarado {
  const max = Math.max(1, Math.floor(maxDigitos))
  const nCasas = Math.max(0, Math.floor(casas))
  const caret = Math.max(0, Math.min(caretBruto, bruto.length))

  // O PONTO tambem separa decimal quando o campo nao tem milhar para exibir.
  //
  // Sem isto, "1.8" em Juros equip. virava 18: `apenasDigitos` jogava o ponto fora e
  // fundia as partes. Dezoito por cento ao mes passa no `le=1` do backend (0,18 < 1) e
  // vai calcular em silencio. Quem digita no teclado numerico so' TEM ponto.
  //
  // A troca so' e' segura enquanto o campo nao usa ponto como MILHAR — por isso a
  // condicao `max <= 3`: com no maximo 3 digitos inteiros nunca nasce separador de
  // milhar, entao um ponto ali so' pode ser decimal. Em campo largo (Obra, Aluguel) o
  // ponto continua sendo milhar e nao vira virgula.
  const semMilhar = nCasas > 0 && max <= 3
  const normalizado = semMilhar && !bruto.includes(',') ? bruto.replace('.', ',') : bruto

  // A PRIMEIRA virgula e' a decimal; qualquer outra e' ruido, exatamente como letra
  // e sinal. Reinterpretar a ULTIMA como decimal transformaria "1,50," noutro numero
  // em silencio.
  //
  // Em campo INTEIRO (`casas = 0`) nao ha' separador decimal: o que vier depois da
  // virgula e' DESCARTADO, nunca concatenado. Concatenar fazia "350,50" virar 35050 —
  // cem vezes o valor, com cara de numero legitimo.
  const iBruta = normalizado.indexOf(',')
  const base = nCasas === 0 && iBruta >= 0 ? normalizado.slice(0, iBruta) : normalizado
  const iVirgula = nCasas > 0 ? base.indexOf(',') : -1
  const temVirgula = iVirgula >= 0
  const brutoInt = temVirgula ? base.slice(0, iVirgula) : base
  const brutoFrac = temVirgula ? base.slice(iVirgula + 1) : ''
  // Classificacao da parte feita no BRUTO, antes de qualquer normalizacao.
  const naFracao = temVirgula && caret > iVirgula

  let antes = apenasDigitos(brutoInt.slice(0, caret)).length
  const crus = apenasDigitos(brutoInt)
  const podados = semZeroEsquerda(crus)
  // Zero a esquerda sumindo ENCURTA a contagem: em "0|07" o caret tinha 1 digito a
  // esquerda, mas o "0" que ele contava deixou de existir. Sem este desconto o caret
  // cai um digito adiante do lugar.
  antes = Math.max(0, antes - (crus.length - podados.length))

  // Estouro de digitos: IGNORA o excedente (corte por prefixo), que e' o que o input
  // nativo faz — digitar no fim de um campo cheio nao acontece nada.
  //
  // Ja' tentei grampear em '9'.repeat(max) aqui para resolver a colagem de valor grande,
  // e foi pior: o grampeamento tambem dispara na DIGITACAO, entao uma unica tecla a mais
  // reescrevia o numero inteiro ("12.345" + 1 tecla = "99.999"). Destruir o que o
  // operador ja' digitou e' pior que ignorar a tecla. O caso da colagem e' tratado onde
  // ele nasce, no `onPaste` do CampoNumero, que sabe que aquilo veio de fora.
  const inteiro = podados.slice(0, max)
  antes = Math.min(antes, inteiro.length)

  // TRUNCA, nao arredonda: com `casas = 1`, "1,87" precisa virar "1,8" e prender o
  // caret no fim. Arredondar para "1,9" faria a 3a tecla MUDAR a 2a casa — o campo
  // engoliria a tecla seguinte e o numero mudaria sozinho debaixo do dedo.
  const fracao = apenasDigitos(brutoFrac).slice(0, nCasas)
  const antesFrac = Math.min(
    apenasDigitos(brutoFrac.slice(0, Math.max(0, caret - iVirgula - 1))).length,
    fracao.length,
  )

  // A fracao vai VERBATIM: nada de Intl aqui. O Intl completa e arredonda casas, e em
  // digitacao a fracao tem de ser literal — inclusive o estado "1," (virgula ainda sem
  // fracao), que precisa sobreviver na tela ou a virgula vira tecla morta. Quem
  // normaliza "1," para "1" e' o blur, que reescreve o texto a partir do numero.
  const texto = formatarMilhar(inteiro) + (temVirgula ? `,${fracao}` : '')

  // Sem digito nenhum o campo esta' VAZIO — e vazio nao e' zero: no Investimento ele
  // e' o que faz a chave sumir do payload e o motor usar o padrao dele.
  const bruta = inteiro || fracao ? Number(`${inteiro || '0'}.${fracao || '0'}`) : NaN
  const valor = Number.isFinite(bruta) ? bruta : undefined

  const posFinal = naFracao ? texto.indexOf(',') + 1 + antesFrac : posCaret(texto, antes)
  return { texto, digitos: inteiro, inteiro, fracao, valor, caret: posFinal }
}

/**
 * Gramatica pt-BR completa, usada SO' na colagem (ver CampoNumero.onPaste). Digitar
 * uma virgula no meio do campo NAO passa por aqui: transformar "1.5,00" em 15 por
 * causa de um tropeco no teclado numerico seria destrutivo e silencioso.
 *
 * "." , espaco e NBSP sao milhar e somem. A PRIMEIRA virgula e' decimal; o resto e'
 * fracao. Prefixo/sufixo nao numerico (R$, m², /mês) e' descartado.
 *
 * Limite conhecido: "m2" escrito com o algarismo 2 (em vez de "m²") e' indistinguivel
 * de um digito, entao ele e' removido explicitamente — sem isso "1.500 m2" viraria 15002.
 */
export function parsePtBr(txt: string): number | undefined {
  const semUnidade = txt.replace(/m2\b/gi, '')
  const limpo = semUnidade.replace(/[^\d,]/g, '')
  if (!limpo) return undefined
  const i = limpo.indexOf(',')
  const inteiro = i < 0 ? limpo : limpo.slice(0, i)
  const fracao = i < 0 ? '' : limpo.slice(i + 1).replace(/,/g, '')
  const n = Number(`${inteiro || '0'}.${fracao || '0'}`)
  return Number.isFinite(n) ? n : undefined
}

/** Texto colado -> a sequencia de digitos que deve ser inserida no campo INTEIRO. */
export function digitosColados(txt: string): string {
  const v = parsePtBr(txt)
  if (v === undefined) return ''
  return digitosDoNumero(v)
}

/**
 * Texto colado -> as duas partes a inserir num campo DECIMAL. Existe porque
 * `digitosColados` passa por `digitosDoNumero`, que arredonda: colar "1,8" num campo
 * de juros daria 2 — a colagem ficaria pior que a digitacao no unico caminho que ja'
 * lia virgula.
 *
 * Aqui ARREDONDAR e' correto (e nao truncar como na digitacao): a colagem e' um
 * evento unico e completo, nao ha proxima tecla para engolir.
 */
export function partesColadas(txt: string, casas = 0): { inteiro: string; fracao: string } {
  const v = parsePtBr(txt)
  if (v === undefined) return { inteiro: '', fracao: '' }
  const x = Math.min(Math.max(v, 0), VALOR_MAX)
  const c = Math.max(0, Math.floor(casas))
  if (c === 0) return { inteiro: String(Math.round(x)), fracao: '' }
  const [i, f = ''] = x.toFixed(c).split('.')
  return { inteiro: i, fracao: f.replace(/0+$/, '') }
}

export interface Recorte {
  bruto: string
  caret: number
}

/** Remove a virgula do indice `i` e corta da fracao o que nao couber em `maxDigitos`. */
function juntarNaVirgula(bruto: string, i: number, maxDigitos?: number): string {
  const esq = bruto.slice(0, i)
  const dir = bruto.slice(i + 1)
  if (maxDigitos === undefined) return esq + dir
  const sobra = Math.max(0, Math.floor(maxDigitos) - apenasDigitos(esq).length)
  let vistos = 0
  let corte = 0
  for (; corte < dir.length; corte++) {
    if (ehDigito(dir[corte])) {
      if (vistos >= sobra) break
      vistos++
    }
  }
  return esq + dir.slice(0, corte)
}

/**
 * Backspace/Delete quando o vizinho do caret e' um SEPARADOR.
 *
 * Sem isto a tecla vira teatro: o browser apaga o ".", os digitos nao mudam, a
 * reformatacao devolve o mesmo "1.500" e nada acontece na tela — a tecla parece
 * morta e ainda custa duas batidas para apagar um digito. Aqui o separador e'
 * atravessado e quem morre e' o DIGITO do outro lado dele.
 *
 * `null` = nada a fazer, deixe o comportamento nativo do browser agir.
 *
 * A VIRGULA E' A EXCECAO, e a razao e' PROVENIENCIA: o ponto de milhar foi escrito
 * pelo FORMATADOR (ninguem digitou), entao apaga-lo tem de atravessar e matar o
 * digito do outro lado; a virgula foi digitada pelo USUARIO, entao apaga-la tem de
 * apagar A VIRGULA. Sem o flag `decimal`, Backspace logo depois dela comeria o
 * digito da parte inteira ("1,8" viraria ",8") em silencio.
 *
 * `maxDigitos` (opcional) cobre a juncao que ESTOURA o teto: "12,34" num campo de 2
 * digitos vira "12", com os excedentes da FRACAO descartados — e nao "99" do
 * grampeamento, que inventaria um numero que ninguem digitou. Aqui, ao contrario da
 * colagem, o excedente e' identificavel: e' o que estava depois da virgula.
 */
export function apagarVizinho(
  bruto: string,
  caret: number,
  direcao: -1 | 1,
  decimal = false,
  maxDigitos?: number,
): Recorte | null {
  if (decimal) {
    const i = direcao < 0 ? caret - 1 : caret
    if (i >= 0 && i < bruto.length && bruto[i] === ',') {
      // O caret fica onde a virgula estava: a contagem de digitos a esquerda dele
      // nao muda com a remocao de um caractere que nao e' digito.
      return { bruto: juntarNaVirgula(bruto, i, maxDigitos), caret: i }
    }
  }
  if (direcao < 0) {
    let i = caret - 1
    if (i < 0 || ehDigito(bruto[i])) return null
    while (i >= 0 && !ehDigito(bruto[i])) i--
    if (i < 0) return null
    return { bruto: bruto.slice(0, i) + bruto.slice(i + 1), caret: i }
  }
  let i = caret
  if (i >= bruto.length || ehDigito(bruto[i])) return null
  while (i < bruto.length && !ehDigito(bruto[i])) i++
  if (i >= bruto.length) return null
  // O digito removido esta' a DIREITA do caret: a contagem de digitos a esquerda nao
  // muda, entao o caret permanece no mesmo indice.
  return { bruto: bruto.slice(0, i) + bruto.slice(i + 1), caret }
}

/**
 * Incremento por ArrowUp/ArrowDown — o unico comportamento do `type="number"` que se
 * perde de verdade com a mascara (min/max nativos nunca impediram digitacao; so' as
 * setas os respeitavam). Varrer cenario de 50 em 50 / 1.000 em 1.000 e' fluxo real de
 * trabalho, entao ele volta pela tecla.
 *
 * A grade e' ancorada no `min`, como no input nativo: 147 com passo 5 sobe para 150,
 * nao para 152.
 */
export function passoSeta(
  valor: number,
  passo: number,
  direcao: 1 | -1,
  min?: number,
  max?: number,
  casas = 0,
): number {
  const p = Math.abs(passo) || 1
  const base = min ?? 0
  const k = (valor - base) / p
  // Epsilon contra ruido de ponto flutuante: sem ele um k = 2,9999999996 desceria
  // para o degrau errado.
  const eps = 1e-9
  const alvo = direcao > 0 ? base + (Math.floor(k + eps) + 1) * p : base + (Math.ceil(k - eps) - 1) * p
  // Arredondar por CASAS, nao por inteiro: `Math.round` zerava qualquer step
  // fracionario (step 0,1 nos juros viraria step 1), e a seta e' justamente o que
  // compensa a perda do spinner nativo. Com `casas = 0` continua sendo `Math.round`
  // — `toFixed(0)` diverge dele no meio-a-meio negativo, e nao vale trocar.
  const c = Math.max(0, Math.floor(casas))
  let n = c === 0 ? Math.round(alvo) : Number(alvo.toFixed(c))
  if (min !== undefined) n = Math.max(min, n)
  if (max !== undefined) n = Math.min(max, n)
  return n
}
