/**
 * Os dois botoes FIXOS do rodape da ficha de ponto: "Estudo" e "Simulador" (2026-10-14).
 *
 * Substituem a secao "Fecha a conta?" (o antigo `BlocoViabilidadePonto`), que saiu por
 * decisao do dono: a ficha de ponto e' leitura do TERRITORIO; a conta do contrato e' do
 * Simulador (tela de Viabilidade), que ja' tinha tudo e mais — DRE, grade, planilha.
 *
 * - "Estudo" baixa o Relatorio Pontual no modo SO-ESTUDO: exclusivamente demografico,
 *   sem viabilidade, DRE, aluguel, payback ou teto, com a Conclusao so' com o selo
 *   DEMOGRAFICO (DEC-030). E' o mesmo modo do bot. Desde a fase 2 da DEC-071 (DEC-074)
 *   ele sai tambem do RECORTE da ficha: area desenhada, raio de 2 km e 10 min de carro.
 * - "Simulador" leva a coordenada EXATA do ponto aberto para a tela de Viabilidade.
 *
 * As regras de quando cada botao fica travado vivem aqui, testadas, porque o Vitest roda
 * sem DOM — e porque botao travado sem explicacao e' botao morto (a dica e' obrigatoria).
 * O VISUAL dos dois tambem (`estiloDoBotaoEstudo`/`estiloDoBotaoSimulador`): a decisao de
 * cor e de largura e' do dono, e so' fica travada se estiver num lugar que o teste alcanca.
 */
import type { CSSProperties } from 'react'

import { alcanceDoItem, type Alcance } from './alcance'
import { ACC, ACC_GLOW, ACC_ON } from './imovel'
import { ehAreaDesenhada, rotuloDoRaio, tipoDoRecorte } from './recorte'
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
   * Travado por um motivo que o operador PRECISA ler (aba vetada, area sem contorno): a
   * tela o escreve abaixo dos botoes. `null` quando o botao esta' livre ou quando a
   * propria trava ja' se explica (o "Gerando o estudo..." com spinner).
   */
  travadoPorque: string | null
}

/** O que os botoes leem da ficha: o recorte (tipo, raio, contorno) e o mercado. */
type FichaDoRodape = Pick<PontoPayload, 'mercado' | 'geometria'> &
  Partial<Pick<PontoPayload, 'raio_km' | 'recorte'>>

export const ROTULO_ESTUDO = 'Estudo'
export const ROTULO_ESTUDO_GERANDO = 'Gerando o estudo...'
export const DICA_ESTUDO =
  'PDF só demográfico: quem mora no raio, a concorrência e o mercado, sem nenhum dado financeiro.'
/** A mesma promessa, quando o recorte não é o raio de 1 km (área desenhada, 2 km, 10 min). */
export const DICA_ESTUDO_RECORTE =
  'PDF só demográfico do recorte desta ficha: quem mora nele, a concorrência e o mercado, sem nenhum dado financeiro.'
/**
 * Área desenhada SEM o contorno no payload (só o `grao` do mercado a denuncia): sem os
 * vértices não há o que mandar ao servidor, e o PDF sairia do RAIO em volta do ponto
 * central com o nome da área — o "PDF certo sobre o recorte errado" da DEC-071.
 */
export const DICA_ESTUDO_SEM_CONTORNO =
  'O contorno desta área não chegou do servidor: analise a área de novo para gerar o estudo dela.'

export const ROTULO_SIMULADOR = 'Simulador'
export const DICA_SIMULADOR = 'Abre a tela de Viabilidade com a coordenada deste ponto.'
export const DICA_SIMULADOR_VETADO = 'Sua conta não tem acesso à tela de Viabilidade.'
export const DICA_SIMULADOR_AREA =
  `Abre a tela de Viabilidade no ponto central da área. Lá o estudo é do ${rotuloDoRaio(1)} em volta desse ponto, não da área desenhada.`
/** O ponto de outro alcance (DEC-074) vai ao Simulador pela ORIGEM, que é o ponto clicado. */
export const DICA_SIMULADOR_ALCANCE =
  `Abre a tela de Viabilidade neste ponto. Lá o estudo é do ${rotuloDoRaio(1)} em volta dele, não do recorte escolhido aqui.`

/**
 * O recorte que o "Estudo" manda ao servidor, no CORPO do pedido (`api.relatorioPontual`):
 *  - área desenhada: o Polygon do desenho (os vértices que o servidor normalizou);
 *  - raio de 2 km / 10 min de carro: só o ALCANCE — o servidor recalcula o contorno (a
 *    isócrona sai do cache dele), nunca confia num polígono mandado pela tela;
 *  - raio de 1 km: nada, é o default do servidor.
 * `null` quando o recorte é uma área sem contorno: não há como pedi-lo.
 */
export function recorteDoEstudo(
  ficha: FichaDoRodape,
):
  | { alcance?: Alcance; geometria?: { type: 'Polygon'; coordinates: [number, number][][] } }
  | null {
  if (ehAreaDesenhada(ficha)) {
    return ficha.geometria?.length ? { geometria: { type: 'Polygon', coordinates: ficha.geometria } } : null
  }
  const alcance = alcanceDoItem({
    raio_km: ficha.raio_km ?? null,
    geometria: ficha.geometria,
    recorte: ficha.recorte ?? null,
    mercado: ficha.mercado,
  })
  return alcance && alcance !== 'raio_1km' ? { alcance } : {}
}

/**
 * Estado do botao "Estudo".
 *
 * `gerando` trava o botao: o PDF leva de 10 a 30 s (a area grande, mais) e passa por um
 * semaforo no servidor, e um segundo clique enfileiraria um PDF duplicado.
 */
export function estadoDoEstudo(ficha: FichaDoRodape | null, gerando: boolean): EstadoBotao {
  const dica = ficha && tipoDoRecorte(ficha) !== 'raio_1km' ? DICA_ESTUDO_RECORTE : DICA_ESTUDO
  if (gerando) {
    return { habilitado: false, rotulo: ROTULO_ESTUDO_GERANDO, dica, travadoPorque: null }
  }
  if (!ficha) return { habilitado: false, rotulo: ROTULO_ESTUDO, dica, travadoPorque: null }
  if (recorteDoEstudo(ficha) == null) {
    return {
      habilitado: false,
      rotulo: ROTULO_ESTUDO,
      dica: DICA_ESTUDO_SEM_CONTORNO,
      travadoPorque: DICA_ESTUDO_SEM_CONTORNO,
    }
  }
  return { habilitado: true, rotulo: ROTULO_ESTUDO, dica, travadoPorque: null }
}

/**
 * Estado do botao "Simulador".
 *
 * `liberado` = a conta tem a aba Viabilidade. O `App` sinaliza isso NAO passando o
 * callback de navegacao; sem esta trava o botao apareceria ativo e o clique morreria em
 * silencio (o `irParaViabilidade` do `App` retorna calado quando a aba e' vetada).
 */
export function estadoDoSimulador(ficha: FichaDoRodape | null, liberado: boolean): EstadoBotao {
  if (!liberado) {
    return {
      habilitado: false,
      rotulo: ROTULO_SIMULADOR,
      dica: DICA_SIMULADOR_VETADO,
      travadoPorque: DICA_SIMULADOR_VETADO,
    }
  }
  /* A area desenhada VAI ao Simulador (decisao do dono: pelo ponto central), e o ponto de
     outro alcance vai pela origem; nos dois a dica diz o que acontece la': a Viabilidade
     e o PDF dela sao do RAIO de 1 km em volta desse ponto. */
  const tipo = ficha ? tipoDoRecorte(ficha) : 'raio_1km'
  const dica =
    tipo === 'poligono' ? DICA_SIMULADOR_AREA : tipo === 'raio_1km' ? DICA_SIMULADOR : DICA_SIMULADOR_ALCANCE
  return { habilitado: ficha != null, rotulo: ROTULO_SIMULADOR, dica, travadoPorque: null }
}

/**
 * O rotulo com que o item chega a' Viabilidade (breadcrumb, titulo do PDF e da planilha).
 *
 * Para a AREA DESENHADA ele diz "Ponto central da area desenhada": a Viabilidade so' sabe
 * de coordenada, e o Relatorio Pontual que ela gera e' do RAIO de 1,0 km em volta do ponto
 * central. Com o rotulo cru ("Area desenhada #2") sairia um PDF intitulado com o nome da
 * area sobre um recorte que NAO e' a area. Ponto com raio — de qualquer alcance — segue com
 * o proprio rotulo: ele ja' e' o nome do LUGAR clicado (a origem), nunca do recorte.
 */
export function rotuloParaSimulador(ficha: FichaDoRodape | null, rotulo: string): string {
  if (!ehAreaDesenhada(ficha)) return rotulo
  const minusculo = rotulo.charAt(0).toLowerCase() + rotulo.slice(1)
  return `Ponto central da ${minusculo}`
}

/**
 * Os dois botoes do rodape dividem o quadro AO MEIO (nota do dono, 19/10/2026): cada um
 * `flex: 1` com a mesma base, a mesma fonte e o mesmo padding — a mesma largura e a mesma
 * altura. `minWidth: 0` deixa os dois encolherem juntos na janela estreita (320 px), em
 * vez de o rotulo mais longo empurrar o outro para a linha de baixo.
 */
const BASE_RODAPE: CSSProperties = {
  flex: '1 1 0',
  minWidth: 0,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  font: '700 15px/1.15 var(--f-ui)',
  padding: '14px 18px',
  border: 'none',
}

/**
 * "Estudo" CHEIO no ROSA MAGENTA, o mesmo do "Ver no Mapa Territorial" da aba de imoveis:
 * os tokens vem de `lib/imovel` (ACC, ACC_ON, ACC_GLOW), sem copiar o hex. Travado, perde
 * so' o brilho — a cor e o texto continuam legiveis (a opacidade e' a do `Botao`).
 */
export function estiloDoBotaoEstudo(habilitado: boolean): CSSProperties {
  return { ...BASE_RODAPE, background: ACC, color: ACC_ON, boxShadow: habilitado ? ACC_GLOW : 'none' }
}

/**
 * "Simulador" CHEIO no AZUL do SISTEMA (`--ac`), o primario dos botoes da Viabilidade —
 * a tela para onde ele leva. Nao e' o `--info`: o mesmo engano ja' foi corrigido pelo
 * Felipe no link do anuncio (`OportunidadesImobiliariasScreen`).
 */
export function estiloDoBotaoSimulador(habilitado: boolean): CSSProperties {
  return {
    ...BASE_RODAPE,
    background: 'var(--ac)',
    color: 'var(--ac-on)',
    boxShadow: habilitado ? 'var(--ac-glow)' : 'none',
  }
}
