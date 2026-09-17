import { num, pctVar, renda } from './format'
import type { ContextoMunicipio } from './types'

/** Uma leitura pronta para virar `MiniLeitura` na ficha. */
export interface LeituraContexto {
  chave: string
  valor: string
  rotulo: string
  nota?: string
}

/**
 * Traduz as camadas de leitura argentinas nos cartões da ficha do hexágono.
 *
 * TRÊS REGRAS, e as três são a razão desta função existir em vez de o JSX ler o objeto
 * direto. Cada uma já custou um defeito do lado do produtor do dado:
 *
 * 1. **Ausência não vira zero.** Campo nulo não produz cartão — não produz um cartão com
 *    "0". Vazio aqui significa partido sem pesquisa do INDEC, célula suprimida por sigilo
 *    ou fonte que não alcança o lugar; zero significa que se mediu e deu zero. São
 *    afirmações opostas, e a segunda é rara e verdadeira (La Paz autorizou 84 m² em 2022
 *    e 0 em 2025).
 * 2. **Número sem período não sai.** As cinco fontes têm janelas diferentes; "34.900 m²"
 *    sozinho não diz se descreve o ano passado ou 2019. O período entra como nota do
 *    próprio cartão, não num rodapé que ninguém liga ao número.
 * 3. **`fluxo_dia` é uso ATRIBUÍDO, não passante medido.** O uso da linha foi repartido
 *    entre os hexágonos pelo comprimento do trajeto dentro de cada um. O rótulo diz isso
 *    na tela, porque "usos/dia" solto se lê como gente contada na esquina.
 *
 * E uma regra de escala, herdada do CAGED (`lerCrescimento`): variação percentual só
 * aparece GRUDADA no valor absoluto que a gerou. "+37%" sozinho não tem tamanho — pode
 * ser 84 m² virando 115.
 */
export function leiturasDoContexto(ctx: ContextoMunicipio | null | undefined): LeituraContexto[] {
  if (!ctx) return []
  const out: LeituraContexto[] = []
  const periodo = (p?: string | null) => (p ? `período ${p}` : undefined)
  const com = (base: string | undefined, extra: string | null) =>
    [extra, base].filter(Boolean).join(' · ') || undefined

  if (ctx.obras_m2 != null) {
    out.push({
      chave: 'obras',
      valor: `${num(ctx.obras_m2)} m²`,
      rotulo: 'Obra autorizada (12 meses)',
      nota: com(periodo(ctx.obras_periodo), ctx.obras_var != null ? pctVar(ctx.obras_var) : null),
    })
  }
  if (ctx.soc_n != null) {
    out.push({
      chave: 'soc',
      valor: num(ctx.soc_n),
      rotulo: 'Sociedades abertas',
      nota: com(
        ctx.soc_janela ? `janela ${ctx.soc_janela}` : undefined,
        ctx.soc_var != null ? pctVar(ctx.soc_var) : null,
      ),
    })
  }
  if (ctx.emp_estoque != null) {
    out.push({
      chave: 'emp',
      valor: num(ctx.emp_estoque),
      rotulo: 'Empresas empregadoras',
      nota: periodo(ctx.emp_periodo),
    })
  }
  if (ctx.emp_salario != null) {
    out.push({
      chave: 'salario',
      valor: renda(ctx.emp_salario),
      rotulo: 'Salário médio do departamento',
      nota: periodo(ctx.emp_periodo),
    })
  }
  if (ctx.emp_constr != null) {
    out.push({
      chave: 'constr',
      valor: `${num(ctx.emp_constr, 1)}%`,
      rotulo: 'Construção no emprego local',
      nota: periodo(ctx.emp_periodo),
    })
  }
  if (ctx.fluxo_dia != null) {
    out.push({
      chave: 'fluxo',
      valor: num(ctx.fluxo_dia),
      /* "atribuídos" no RÓTULO, não numa nota de rodapé: é o que separa esta leitura de
         uma contagem de passantes, e quem lê o número tem de ler a ressalva junto. */
      rotulo: 'Usos de transporte/dia (atribuídos)',
      nota: periodo(ctx.fluxo_periodo),
    })
  }
  return out
}
