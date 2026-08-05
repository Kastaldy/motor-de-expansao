import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import {
  apagarVizinho,
  formatarNumero,
  mascarar,
  parsePtBr,
  partesColadas,
  passoSeta,
} from '../lib/mascara'

/**
 * Input numerico com MASCARA VIVA: o ponto de milhar aparece dentro da caixa, na
 * tecla ("1500" ja' e' "1.500" antes de sair do campo), e a unidade fica visivel o
 * tempo todo como adorno.
 *
 * POR QUE type="text" E NAO type="number": com `type="number"` o `selectionStart` e'
 * `null` no Chrome e no Safari (o padrao so' expoe seleção em inputs de texto), e sem
 * ele o algoritmo de caret e' literalmente impossivel de escrever. Nao e' preferencia
 * estetica: mascara viva e input numerico nativo sao incompativeis.
 *
 * O QUE SE PERDE E O QUE VOLTA: perdem-se os botoezinhos de incremento (spinner) —
 * feios em 146px e sem componente no repo. O incremento em si volta por ArrowUp/
 * ArrowDown com o mesmo `step` (ver `passoSeta`), e e' o que o `title` avisa. Nao se
 * perde clamp nenhum: `min`/`max` nativos NUNCA impediram digitacao (hoje ja' da' para
 * digitar 50 numa metragem com min=200); eles so' valiam para as setas, que continuam
 * respeitando-os.
 *
 * ESTADO: o numero e' a fonte de verdade do motor e vive no pai; o TEXTO e' estado de
 * digitacao e vive aqui. As duas verdades sao separadas de proposito — texto pode ficar
 * vazio (a pessoa apagou tudo para redigitar), numero nem sempre.
 *
 * DUAS POLITICAS PARA O CAMPO VAZIO, escolhidas por campo e nao globalmente:
 *  - SEM `onVazio` (Cenario): vazio e' transitorio. O pai nao e' avisado e o motor
 *    segue com o ultimo numero valido, em vez de receber um 0 que ninguem digitou; ao
 *    sair do campo o texto volta a ser espelho do numero.
 *  - COM `onVazio` (Investimento): vazio e' um VALOR — "use o padrao do motor". O pai
 *    e' avisado, guarda `undefined`, a chave some do payload e o campo CONTINUA vazio
 *    depois do blur, com o placeholder de volta.
 * `onValor` e `onVazio` sao as duas metades do mesmo evento: quem nao passa `onVazio`
 * nao ouve o vazio. E' impossivel configurar isso de forma inconsistente.
 */
export interface CampoNumeroProps {
  /** Numero atual (fonte de verdade, vive no pai). `undefined` = campo vazio. */
  valor: number | undefined
  /** Chamado SO' quando o campo tem digitos e o numero mudou de fato. */
  onValor: (n: number) => void
  /**
   * Chamado quando o campo fica SEM digito nenhum. So' quem passa isto trata vazio
   * como valor; sem ele o comportamento e' o do Cenario (vazio nao avisa ninguem).
   */
  onVazio?: () => void
  /**
   * Teto por contagem de digitos da PARTE INTEIRA: garante que o pior caso caiba na
   * caixa. Nao muda de significado no modo decimal.
   */
  maxDigitos: number
  /** Casas decimais aceitas. 0 = campo inteiro (a virgula e' ruido, como hoje). */
  casas?: number
  min?: number
  max?: number
  /** Passo das setas ↑/↓. */
  step?: number
  /** Adorno a ESQUERDA do numero (moeda). */
  prefixo?: string
  /** Adorno a DIREITA do numero (unidade). */
  sufixo?: string
  /**
   * Nome acessivel. Os adornos sao `aria-hidden` (sao pintura), entao a unidade
   * precisa entrar aqui — senao o leitor de tela anuncia o campo sem unidade.
   */
  rotulo: string
  /** Texto do campo vazio. Nunca deve AFIRMAR um padrao que nao foi verificado. */
  placeholder?: string
  title?: string
}

/** Espaco reservado para o adorno nao ser sobreposto pelo numero. */
function reserva(adorno: string): number {
  return 13 + Math.max(1, adorno.length) * 8 + 5
}

const ESTILO_ADORNO: React.CSSProperties = {
  position: 'absolute',
  top: 0,
  bottom: 0,
  display: 'flex',
  alignItems: 'center',
  font: '500 12px/1 var(--f-ui)',
  color: 'var(--tx-sub)',
  // O clique tem de ATRAVESSAR o adorno e chegar ao input, senao o caret vai parar
  // no fim do texto em vez de onde a pessoa clicou.
  pointerEvents: 'none',
}

export default function CampoNumero({
  valor,
  onValor,
  onVazio,
  maxDigitos,
  casas = 0,
  min,
  max,
  step = 1,
  prefixo,
  sufixo,
  rotulo,
  placeholder,
  title,
}: CampoNumeroProps) {
  const ref = useRef<HTMLInputElement>(null)
  const caretRef = useRef<number | null>(null)
  const [texto, setTexto] = useState(() => formatarNumero(valor, casas))

  /** Teto efetivo das setas: nao adianta subir para um numero que nao cabe na mascara. */
  const tetoDigitos = 10 ** maxDigitos - 1
  const teto = max === undefined ? tetoDigitos : Math.min(max, tetoDigitos)

  // Sincroniza TEXTO <- NUMERO so' com o campo DESfocado. O Cenario muda valor por
  // fora de verdade (mexer em Studios reescreve o Ticket); sem isto o campo mostraria
  // o numero velho e mentiria para o operador. Com o campo focado o efeito nao pode
  // rodar: ele reescreveria o que esta' sendo digitado e tornaria impossivel esvaziar
  // o campo para redigitar.
  useEffect(() => {
    const el = ref.current
    if (el && document.activeElement === el) return
    setTexto(formatarNumero(valor, casas))
  }, [valor, casas])

  // Rede de seguranca do caret. Roda em TODO render porque a tela inteira re-renderiza
  // a cada tecla e o React pode reescrever o `value` do input controlado; quando ele
  // reescreve, o caret vai para o fim. `useLayoutEffect` e nao `useEffect` porque o
  // segundo roda depois da pintura — a pessoa veria um quadro com o caret no fim.
  // `caretRef` acompanha tambem clique e setas laterais (ver onSelect), entao restaurar
  // aqui devolve exatamente a posicao que o usuario tinha.
  useLayoutEffect(() => {
    const el = ref.current
    const pos = caretRef.current
    if (!el || pos === null || document.activeElement !== el) return
    if (el.selectionStart !== pos || el.selectionEnd !== pos) el.setSelectionRange(pos, pos)
  })

  /**
   * Aplica a mascara e ESCREVE NO DOM dentro do proprio handler, antes do setState.
   *
   * Isto nao e' redundante com o ciclo declarativo do React — e' o que faz o caret
   * sobreviver, nos dois caminhos:
   *  (a) com re-render: no commit o React so' escreve o value se ele diferir do DOM;
   *      como o DOM ja' tem a string final, ele nao toca em nada;
   *  (b) SEM re-render: se o texto formatado for igual ao anterior (digitou uma letra,
   *      apagou so' um ponto), o setState faz bail-out e nenhum efeito roda — mas o
   *      React ainda RESTAURA o input controlado com a prop `value`. Como o DOM ja'
   *      contem essa mesma string, a restauracao vira no-op.
   */
  function aplicar(el: HTMLInputElement, bruto: string, caret: number) {
    const r = mascarar(bruto, caret, maxDigitos, casas)
    el.value = r.texto
    el.setSelectionRange(r.caret, r.caret)
    caretRef.current = r.caret
    setTexto(r.texto)
    // `r.valor`, e NAO `numeroDoTexto(...)`: os digitos crus de "1,8" sao "18", e
    // dezoito por cento ao mes iria direto para o motor financeiro com cara de
    // numero legitimo. Quem sabe onde estava a virgula e' a mascara.
    if (r.valor === undefined) {
      // Campo vazio nao vira 0. Sem `onVazio` o pai nem fica sabendo e continua com o
      // ultimo numero valido (politica do Cenario).
      onVazio?.()
    } else if (r.valor !== valor) {
      onValor(r.valor)
    }
  }

  function comValor(el: HTMLInputElement, n: number) {
    const t = formatarNumero(n, casas)
    el.value = t
    el.setSelectionRange(t.length, t.length)
    caretRef.current = t.length
    setTexto(t)
    if (n !== valor) onValor(n)
  }

  function aoTeclar(e: React.KeyboardEvent<HTMLInputElement>) {
    const el = e.currentTarget
    // Atalho do sistema passa direto. Sem esta guarda, Ctrl+Backspace (apagar
    // palavra) e Alt+Backspace caiam no nosso `apagarVizinho` e apagavam UM digito,
    // e Ctrl+Seta (pular palavra) virava incremento de step. Sequestrar tecla so'
    // vale quando ela esta' sozinha; com modificador, quem manda e' o sistema.
    if (e.ctrlKey || e.metaKey || e.altKey) return
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      // preventDefault OBRIGATORIO: em input de texto ArrowUp leva o caret para o
      // inicio e ArrowDown para o fim. Sem isto a tecla faria a coisa errada.
      e.preventDefault()
      const atual = parsePtBr(el.value) ?? valor
      // Campo OPCIONAL vazio: a seta nao faz nada. Vazio ali nao e' "zero", e' "use o
      // padrao do motor" — a chave nem entra no payload. Partir do `min` materializaria
      // um numero que ninguem digitou: uma seta para baixo na Taxa de franquia gravaria
      // 0 no lugar dos R$ 160.000 do motor, e o PDF registraria como premissa do
      // operador. Quem quer um valor explicito digita; a seta so' ajusta o que ja' existe.
      if (atual === undefined && onVazio) return
      const base = atual ?? min ?? 0
      comValor(el, passoSeta(base, step, e.key === 'ArrowUp' ? 1 : -1, min, teto, casas))
      return
    }
    if (
      (e.key === 'Backspace' || e.key === 'Delete') &&
      el.selectionStart !== null &&
      el.selectionStart === el.selectionEnd
    ) {
      const r = apagarVizinho(
        el.value,
        el.selectionStart,
        e.key === 'Backspace' ? -1 : 1,
        casas > 0,
        maxDigitos,
      )
      if (!r) return // vizinho e' digito: o comportamento nativo ja' faz o certo
      e.preventDefault()
      aplicar(el, r.bruto, r.caret)
    }
  }

  return (
    <span style={{ position: 'relative', display: 'block' }}>
      {prefixo && <span aria-hidden style={{ ...ESTILO_ADORNO, left: 13 }}>{prefixo}</span>}
      <input
        ref={ref}
        // `num` e' a regra do projeto para numero, e aqui tem efeito pratico: com
        // figuras tabulares a largura nao oscila a cada tecla, entao o numero nao
        // "respira" nem invade o adorno enquanto e' digitado.
        className="num"
        type="text"
        // Teclado numerico no celular sem perder a seleção que a mascara exige. Em
        // campo decimal tem de ser "decimal": no iOS o teclado "numeric" nao traz a
        // vírgula, e sem ela o campo fica IMPOSSIVEL de preencher no celular.
        inputMode={casas > 0 ? 'decimal' : 'numeric'}
        autoComplete="off"
        aria-label={rotulo}
        placeholder={placeholder}
        title={title}
        value={texto}
        style={{
          paddingLeft: prefixo ? reserva(prefixo) : undefined,
          paddingRight: sufixo ? reserva(sufixo) : undefined,
        }}
        onChange={(e) => {
          const el = e.currentTarget
          aplicar(el, el.value, el.selectionStart ?? el.value.length)
        }}
        onKeyDown={aoTeclar}
        onPaste={(e) => {
          // A colagem e' o UNICO lugar que le virgula decimal: "R$ 35.000", "20000,00"
          // e "1 500" entram certo, e "35,000" vira 35 (leitura pt-BR, a mesma do
          // resto da sidebar). Digitar virgula, fora daqui, continua sendo ruido.
          const colado = e.clipboardData.getData('text')
          if (!colado) return
          e.preventDefault()
          const el = e.currentTarget
          const ini = el.selectionStart ?? el.value.length
          const fim = el.selectionEnd ?? ini
          const p = partesColadas(colado, casas)
          // Colagem maior que o campo: GRAMPEIA no teto. E' o unico lugar onde grampear
          // e' certo — aqui o excedente veio de fora de uma vez, e cortar pelo prefixo
          // daria uma ORDEM DE GRANDEZA a menos ("12.000.000" num campo de 7 digitos
          // viraria 1.200.000, com cara de valor legitimo, a caminho do motor
          // financeiro). Na digitacao o excedente e' so' ignorado, tecla a tecla.
          const inteiro =
            p.inteiro.length > maxDigitos ? '9'.repeat(maxDigitos) : p.inteiro
          // A fracao so' entra quando o campo a aceita; em campo inteiro `partesColadas`
          // ja' devolve fracao vazia (valor arredondado), como sempre foi.
          const d = p.fracao ? `${inteiro},${p.fracao}` : inteiro
          aplicar(el, el.value.slice(0, ini) + d + el.value.slice(fim), ini + d.length)
        }}
        onSelect={(e) => {
          // Acompanha o caret que a PESSOA moveu (clique, setas laterais, Home/End),
          // para a rede de seguranca restaurar a posicao dela e nao uma antiga.
          // Selecao com extensao (arrastar, Ctrl+A, Tab) nao e' caret: guarda `null`,
          // senao um re-render qualquer colapsaria a selecao no meio do gesto.
          const el = e.currentTarget
          caretRef.current = el.selectionStart === el.selectionEnd ? el.selectionStart : null
        }}
        onBlur={() => {
          // Saiu do campo: o texto volta a ser espelho do numero. Normaliza o estado
          // intermediario "1," e qualquer valor que o pai tenha ajustado. Com `valor`
          // `undefined` o espelho e' a string VAZIA — e' o que preserva o campo
          // opcional vazio (e traz o placeholder de volta) sem nenhum ramo extra.
          caretRef.current = null
          setTexto(formatarNumero(valor, casas))
        }}
      />
      {sufixo && <span aria-hidden style={{ ...ESTILO_ADORNO, right: 13 }}>{sufixo}</span>}
    </span>
  )
}
