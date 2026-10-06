import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * Guardas de FONTE da aba Viabilidade, no cruzamento entre a DEC-068 (studios com ticket
 * próprio) e a moeda do imóvel na instância AR.
 *
 * ## Por que de fonte, e não de componente
 *
 * `ViabilityScreen.tsx` não tem teste de componente neste repo (o vitest roda em ambiente
 * `node`, sem testing-library, e só casa `src/**\/*.test.ts`). As duas regressões que estas
 * guardas impedem vivem DENTRO do componente e não têm outra rede: nenhuma das suítes
 * apanhou nenhuma das duas quando elas existiram de verdade.
 *
 * ## As duas coisas que isto trava, e as duas aconteceram
 *
 * **1. Mudar o número de studios NÃO pode reescrever o ticket de musculação.** A escada
 * `TICKET_POR_STUDIO = [147, 157, 167, 177]` foi revogada pela DEC-068: cada studio tem
 * ticket próprio e o de musculação independe da contagem. O PR da moeda (#444) foi cortado
 * ANTES dessa decisão e ainda trazia, no `onChange` de Studios,
 * `if (!moedaLocal) setTicket(TICKET_POR_STUDIO[n])`. Trazê-lo sem desfazer isso reverteria
 * a DEC-068 — e **no Brasil**, porque `!moedaLocal` é sempre verdadeiro aqui. O merge não
 * acusa: é conflito de texto num arquivo, e "aceitar o nosso lado" compila.
 *
 * **2. O ticket de studio é dinheiro e tem de atravessar a conversão de moeda.** Era a única
 * caixa de dinheiro da aba que ia ao motor sem `paraReais`, e a única com `R$` cravado no
 * rótulo enquanto as vizinhas mostravam pesos. Pelos câmbios do perfil AR (1.397,71 ARS/USD
 * e 4,9837 BRL/USD) um peso vale cerca de R$ 0,0036: digitar como peso — o que o resto da
 * tela convida a fazer — entregaria ao motor um número da ordem de **280 vezes** maior.
 */

const TELA = readFileSync(
  resolve(import.meta.dirname, '..', 'screens', 'ViabilityScreen.tsx'),
  'utf-8',
)

/* Lê o fonte SEM comentários: a própria explicação acima cita `TICKET_POR_STUDIO` e
   `setTicket`, e sem isto as guardas acusariam o texto que as documenta. Mesma lição que
   `entrar-bundle.test.ts` já registra. */
const CODIGO = TELA.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

describe('a escada de ticket por studio não volta (DEC-068)', () => {
  it('não existe `TICKET_POR_STUDIO` no código da tela', () => {
    expect(CODIGO).not.toMatch(/TICKET_POR_STUDIO/)
  })

  it('o campo Studios NÃO chama `setTicket` — mudar a contagem não mexe no ticket', () => {
    /* Fatia o `onChange` do campo Studios e mede DENTRO dele. Medir no arquivo inteiro
       daria falso positivo: `setTicket` existe legitimamente no campo do ticket. */
    const i = CODIGO.search(/label="Studios"/)
    expect(i, 'o campo Studios desapareceu da tela').toBeGreaterThan(-1)
    const trecho = CODIGO.slice(i, i + 900)
    expect(trecho).toMatch(/onChange=\{\(e\) => setNStudios\(clampNStudios\(/)
    expect(trecho, 'o campo Studios voltou a reescrever o ticket de musculação').not.toMatch(
      /setTicket\(/,
    )
  })

  it('o ticket de musculação nasce do escalar, não de um índice', () => {
    expect(CODIGO).toMatch(/useState<number>\(TICKET_MUSCULACAO_PADRAO\)/)
  })
})

describe('todo campo de dinheiro atravessa a conversão de moeda', () => {
  it('`tickets_studios` passa por `paraReais` no payload', () => {
    expect(CODIGO.search(/tickets_studios:/), '`tickets_studios` saiu do payload').toBeGreaterThan(
      -1,
    )
    /* ANCORA NO `paraReais(t,` E NÃO NUMA JANELA: a 1ª versão desta guarda fatiava 220
       caracteres depois de `tickets_studios:` e exigia `paraReais(` em qualquer lugar da
       fatia — e a chave `obra: paraReais(obra, ...)` vem logo abaixo, dentro da janela.
       Tirando a conversão do ticket de studio, a guarda continuava VERDE pelo `paraReais`
       do vizinho. A própria sabotagem (2) pegou isso. `paraReais(t,` só existe no `map`
       dos tickets de studio. */
    expect(CODIGO, 'o ticket de studio voltou a ir ao motor sem conversão').toMatch(
      /tickets_studios:[\s\S]{0,140}paraReais\(t,/,
    )
  })

  it('a caixa do ticket de studio NÃO tem `R$` cravado', () => {
    const i = CODIGO.search(/Ticket do studio/)
    expect(i, 'a caixa do ticket de studio desapareceu').toBeGreaterThan(-1)
    const trecho = CODIGO.slice(Math.max(0, i - 200), i + 700)
    expect(trecho, 'a caixa do studio voltou a cravar R$ no prefixo').not.toMatch(
      /prefixo="R\$"/,
    )
    expect(trecho).toMatch(/prefixo=\{simbolo\}/)
  })

  it('trocar a moeda reescreve TAMBÉM os tickets de studio', () => {
    /* Sem isto, trocar de dólares para pesos deixa `157` como 157 PESOS: o mesmo número
       com outro significado, que é exatamente o que `trocarDeMoeda` existe para evitar. */
    const i = CODIGO.search(/trocarDeMoeda\(v, de, para/)
    expect(i, 'o trocador de moeda desapareceu').toBeGreaterThan(-1)
    const trecho = CODIGO.slice(Math.max(0, i - 400), i + 700)
    expect(trecho, 'os tickets de studio ficaram fora da troca de moeda').toMatch(
      /setTicketsStudios\(\(ts\) => ts\.map\(\(v\) => trocarDeMoeda\(/,
    )
  })
})

describe('as guardas de `calcular` e `gerarXlsx` coexistem', () => {
  /* Três condições de três origens: `demandaUsar == null` e `faltaTicket` são do PR da
     moeda, `erroTicketsStudios()` é da DEC-068. Elas caíram nas MESMAS linhas no merge, e
     resolver o conflito escolhendo um lado compila limpo e reabre o buraco do outro. */
  for (const fn of ['calcular', 'gerarXlsx'] as const) {
    it(`\`${fn}\` checa a demanda, o ticket convertível E o ticket de studio`, () => {
      const i = CODIGO.search(new RegExp(`async function ${fn}\\(`))
      expect(i, `\`${fn}\` desapareceu`).toBeGreaterThan(-1)
      const corpo = CODIGO.slice(i, i + 700)
      expect(corpo, 'perdeu a guarda de demanda/ticket (PR da moeda)').toMatch(/faltaTicket/)
      expect(corpo, 'perdeu a guarda de ticket de studio (DEC-068)').toMatch(
        /erroTicketsStudios\(\)/,
      )
    })
  }

  it('`gerarPdf` também tem a guarda de ticket de studio', () => {
    const i = CODIGO.search(/async function gerarPdf\(/)
    expect(i).toBeGreaterThan(-1)
    expect(CODIGO.slice(i, i + 700)).toMatch(/erroTicketsStudios\(\)/)
  })
})

describe('o complemento do mix lê a mesma função do payload', () => {
  it('o Agregador sai de `fracaoDoPercentual`, não de `100 - pctBalcao`', () => {
    /* `CampoNumero` documenta que `min`/`max` nativos não impedem digitação: 150 era
       aceito, a tela mostrava "Agregador -50%" e `fracaoDoPercentual` devolvia `undefined`,
       a chave saía do JSON e o MOTOR usava o padrão de 69%. Tela e conta discordando em
       silêncio. Lendo a mesma função, fora da faixa as duas caem no padrão juntas. */
    const i = CODIGO.search(/Agregador/)
    expect(i, 'o rótulo Agregador desapareceu').toBeGreaterThan(-1)
    const trecho = CODIGO.slice(i, i + 800)
    expect(trecho, 'o complemento voltou a ser calculado à mão').not.toMatch(
      /100 - pctBalcao/,
    )
    expect(trecho).toMatch(/fracaoDoPercentual\(pctBalcao\)/)
  })
})
