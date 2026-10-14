/**
 * Os dois botoes FIXOS do rodape da ficha de ponto: "Estudo" e "Simulador" (2026-10-14).
 *
 * Substituem a secao "Fecha a conta?" (o antigo `BlocoViabilidadePonto`), que saiu por
 * decisao do dono: a ficha de ponto e' leitura do TERRITORIO; a conta do contrato e' do
 * Simulador (tela de Viabilidade), que ja' tinha tudo e mais — DRE, grade, planilha.
 *
 * - "Estudo" baixa o Relatorio Pontual no modo SO-ESTUDO: exclusivamente demografico,
 *   sem viabilidade, DRE, aluguel, payback ou teto, com a Conclusao so' com o selo
 *   DEMOGRAFICO (DEC-030). E' o mesmo modo do bot.
 * - "Simulador" leva a coordenada EXATA do ponto aberto para a tela de Viabilidade.
 *
 * As regras de quando cada botao fica travado vivem aqui, testadas, porque o Vitest roda
 * sem DOM — e porque botao travado sem explicacao e' botao morto (a dica e' obrigatoria).
 */
import type { PontoPayload } from './types'

export interface EstadoBotao {
  habilitado: boolean
  rotulo: string
  /**
   * O que o botao faz, ou — travado — POR QUE nao faz. A tela mostra a dica escrita
   * quando o botao esta' travado: `title` em botao desabilitado nao aparece em todo
   * navegador, e um botao cinza mudo se le como defeito.
   */
  dica: string
  /**
   * Travado por um motivo que o operador PRECISA ler (aba vetada, area desenhada): a tela
   * o escreve abaixo dos botoes. `null` quando o botao esta' livre ou quando a propria
   * trava ja' se explica (o "Gerando o estudo..." com spinner).
   */
  travadoPorque: string | null
}

export const ROTULO_ESTUDO = 'Estudo'
export const ROTULO_ESTUDO_GERANDO = 'Gerando o estudo...'
export const DICA_ESTUDO =
  'PDF só demográfico: quem mora no raio, a concorrência e o mercado, sem nenhum dado financeiro.'
export const DICA_ESTUDO_GEOMETRIA = 'O PDF por área desenhada chega na próxima fase.'

export const ROTULO_SIMULADOR = 'Simulador'
export const DICA_SIMULADOR = 'Abre a tela de Viabilidade com a coordenada deste ponto.'
export const DICA_SIMULADOR_VETADO = 'Sua conta não tem acesso à tela de Viabilidade.'
export const DICA_SIMULADOR_AREA =
  'Abre a tela de Viabilidade no ponto central da área. Lá o estudo é do raio de 1,0 km em volta desse ponto, não da área desenhada.'

/**
 * O item aberto e' uma AREA DESENHADA (DEC-071), e nao um ponto com raio?
 *
 * Pela `geometria` do payload PRIMEIRO, e so' depois pelo `grao` do mercado: quando o
 * calculo de mercado falha no servidor, o bloco volta sem `grao` -- e, lida so' por ele,
 * a area desenhada destravaria o "Estudo", que geraria o PDF do RAIO em volta do ponto
 * interno dela, com o nome da area. Um PDF certo sobre o recorte errado.
 */
export function ehAreaDesenhada(
  ficha: Pick<PontoPayload, 'mercado' | 'geometria'> | null,
): boolean {
  return !!ficha?.geometria?.length || ficha?.mercado?.grao === 'geometria'
}

/**
 * Estado do botao "Estudo".
 *
 * `gerando` trava o botao: o PDF leva de 10 a 30 s e passa por um semaforo no servidor,
 * e um segundo clique enfileiraria um PDF duplicado.
 */
export function estadoDoEstudo(
  ficha: Pick<PontoPayload, 'mercado' | 'geometria'> | null,
  gerando: boolean,
): EstadoBotao {
  if (gerando) {
    return { habilitado: false, rotulo: ROTULO_ESTUDO_GERANDO, dica: DICA_ESTUDO, travadoPorque: null }
  }
  if (!ficha) return { habilitado: false, rotulo: ROTULO_ESTUDO, dica: DICA_ESTUDO, travadoPorque: null }
  if (ehAreaDesenhada(ficha)) {
    return {
      habilitado: false,
      rotulo: ROTULO_ESTUDO,
      dica: DICA_ESTUDO_GEOMETRIA,
      travadoPorque: DICA_ESTUDO_GEOMETRIA,
    }
  }
  return { habilitado: true, rotulo: ROTULO_ESTUDO, dica: DICA_ESTUDO, travadoPorque: null }
}

/**
 * Estado do botao "Simulador".
 *
 * `liberado` = a conta tem a aba Viabilidade. O `App` sinaliza isso NAO passando o
 * callback de navegacao; sem esta trava o botao apareceria ativo e o clique morreria em
 * silencio (o `irParaViabilidade` do `App` retorna calado quando a aba e' vetada).
 */
export function estadoDoSimulador(
  ficha: Pick<PontoPayload, 'mercado' | 'geometria'> | null,
  liberado: boolean,
): EstadoBotao {
  if (!liberado) {
    return {
      habilitado: false,
      rotulo: ROTULO_SIMULADOR,
      dica: DICA_SIMULADOR_VETADO,
      travadoPorque: DICA_SIMULADOR_VETADO,
    }
  }
  /* A area desenhada VAI ao Simulador (decisao do dono: pelo ponto central), mas a dica
     diz o que acontece la': a Viabilidade e o PDF dela sao do RAIO em volta desse ponto. */
  const dica = ehAreaDesenhada(ficha) ? DICA_SIMULADOR_AREA : DICA_SIMULADOR
  return { habilitado: ficha != null, rotulo: ROTULO_SIMULADOR, dica, travadoPorque: null }
}

/**
 * O rotulo com que o item chega a' Viabilidade (breadcrumb, titulo do PDF e da planilha).
 *
 * Para a AREA DESENHADA ele diz "Ponto central da area desenhada": a Viabilidade so' sabe
 * de coordenada, e o Relatorio Pontual que ela gera e' do RAIO de 1,0 km em volta do ponto
 * central. Com o rotulo cru ("Area desenhada #2") sairia um PDF intitulado com o nome da
 * area sobre um recorte que NAO e' a area -- o mesmo "PDF certo sobre o recorte errado" que
 * travou o "Estudo" (DEC-071). Ponto com raio segue com o proprio rotulo.
 */
export function rotuloParaSimulador(
  ficha: Pick<PontoPayload, 'mercado' | 'geometria'> | null,
  rotulo: string,
): string {
  if (!ehAreaDesenhada(ficha)) return rotulo
  const minusculo = rotulo.charAt(0).toLowerCase() + rotulo.slice(1)
  return `Ponto central da ${minusculo}`
}
