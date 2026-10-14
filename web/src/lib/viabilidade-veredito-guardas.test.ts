import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * Guardas de FONTE da aba Viabilidade: a área de resultado só existe quando existe
 * resultado.
 *
 * ## O que isto trava, e aconteceu
 *
 * A condição era `!res && (demanda == null || faltaTicket)`. O `&&` condicionava a
 * proteção a faltar TAMBÉM a premissa — então, com premissa presente e cálculo
 * falhado, a tela desenhava os cartões vazios ("não atinge") E o selo "Requer revisão
 * de premissas" E a faixa "Fora da régua de viabilidade". Em 2026-10-13 um operador
 * levou um 422 na instância argentina e a tela afirmou que o ponto estava fora da
 * régua — sobre um ponto onde o motor nunca rodou.
 *
 * O comentário que já estava no código nomeava o risco com todas as letras: "cartões
 * vazios dizendo 'não atinge' seriam lidos como veredito". A regra é que um veredito
 * sem conta é resultado INVENTADO, e um "reprovado" inventado custa mais que uma tela
 * vazia.
 *
 * ## Por que de fonte, e não de componente
 *
 * `ViabilityScreen.tsx` não tem teste de componente neste repo (o vitest roda em
 * ambiente `node`, sem testing-library). Esta regressão vive dentro do componente e
 * não tinha rede nenhuma — nenhuma suíte a apanhou enquanto ela existiu de verdade.
 */

const TELA = readFileSync(
  resolve(import.meta.dirname, '..', 'screens', 'ViabilityScreen.tsx'),
  'utf-8',
)

/* Lê o fonte SEM comentários: a explicação acima e a do próprio componente citam
   `semResultado` e a condição antiga, e sem isto as guardas acusariam o texto que as
   documenta. Mesma lição que `entrar-bundle.test.ts` já registra. */
const CODIGO = TELA.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

describe('sem resultado não há veredito', () => {
  it('`semResultado` é só a ausência de resultado — sem `&&` com premissa', () => {
    const m = CODIGO.match(/const semResultado = ([^\n]+)/)
    expect(m, '`semResultado` sumiu da tela').not.toBeNull()
    expect(m![1].trim(), 'a ausência de resultado voltou a depender da premissa').toBe('!res')
  })

  it('a área de resultado é guardada por `semResultado`, não pela premissa', () => {
    expect(CODIGO).toMatch(/\{!semResultado && \(/)
  })

  it('`aguardandoPremissa` não guarda mais nada — o nome velho sumiu do código', () => {
    /* Enquanto os dois nomes coexistirem, um `!aguardandoPremissa` esquecido em outro
       bloco reabre o buraco sem conflito nenhum no git. */
    expect(CODIGO).not.toMatch(/aguardandoPremissa/)
  })

  it('o painel de espera aparece sempre que não há resultado', () => {
    expect(CODIGO).toMatch(/\{semResultado && !calculando && \(/)
  })

  it('`faltaPremissa` só escolhe TEXTO — nunca guarda a área de resultado', () => {
    const i = CODIGO.search(/\{!semResultado && \(/)
    expect(i).toBeGreaterThan(-1)
    expect(
      CODIGO.slice(Math.max(0, i - 120), i + 60),
      'a área de resultado voltou a depender da premissa',
    ).not.toMatch(/faltaPremissa/)
  })
})

describe('a guarda de faixa roda nas três saídas', () => {
  /* `calcular`, `gerarPdf` e `gerarXlsx` mandam o MESMO corpo ao motor. Guardar só o
     `calcular` deixaria o PDF e a planilha levarem o 422 — e o PDF tem caminho de erro
     próprio, que também imprimia "[object Object]". */
  for (const fn of ['calcular', 'gerarXlsx'] as const) {
    it(`\`${fn}\` checa a faixa dos campos`, () => {
      const i = CODIGO.search(new RegExp(`async function ${fn}\\(`))
      expect(i, `\`${fn}\` desapareceu`).toBeGreaterThan(-1)
      expect(CODIGO.slice(i, i + 800)).toMatch(/erroDeFaixa\(/)
    })
  }

  it('`gerarPdf` também checa a faixa', () => {
    const i = CODIGO.search(/async function gerarPdf\(/)
    expect(i).toBeGreaterThan(-1)
    expect(CODIGO.slice(i, i + 800)).toMatch(/erroDeFaixa\(/)
  })

  it('a guarda recebe a demanda QUE VAI AO MOTOR, não a do estado', () => {
    /* `calcular` aceita uma demanda diferente da do estado (`montarPayload(demandaUsar)`).
       Checar o estado deixaria passar exatamente o número enviado. */
    const i = CODIGO.search(/async function calcular\(/)
    expect(CODIGO.slice(i, i + 800)).toMatch(/erroDeFaixa\(demandaUsar\)/)
  })

  it('a guarda de studio NÃO foi substituída pela de faixa — as duas correm', () => {
    /* Elas medem coisas diferentes (ticket de studio <= 0 é da DEC-068; a faixa é dos
       campos de parcela/prazo). Trocar uma pela outra compila limpo e reabre o buraco. */
    const i = CODIGO.search(/async function calcular\(/)
    const corpo = CODIGO.slice(i, i + 800)
    expect(corpo).toMatch(/erroTicketsStudios\(\)/)
    expect(corpo).toMatch(/erroDeFaixa\(/)
  })
})

describe('o cliente não imprime objeto cru', () => {
  const API = readFileSync(resolve(import.meta.dirname, 'api.ts'), 'utf-8')
  const CODIGO_API = API.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

  it('nenhum `ApiError` nasce de `String(detalhe)`', () => {
    /* Era daqui que saía "[object Object]": o `detail` de um 422 é uma LISTA. */
    expect(CODIGO_API).not.toMatch(/new ApiError\(String\(/)
  })

  it('os DOIS caminhos de erro passam por `mensagemDoDetalhe`', () => {
    /* `pedir` (JSON) e o download binário (PDF/XLSX) tinham o mesmo defeito, copiado. */
    const n = (CODIGO_API.match(/mensagemDoDetalhe\(/g) ?? []).length
    expect(n, 'algum caminho de erro deixou de normalizar o detalhe').toBeGreaterThanOrEqual(3)
  })
})
