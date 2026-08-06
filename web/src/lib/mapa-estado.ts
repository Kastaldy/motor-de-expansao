/**
 * Foto do Mapa Territorial — o estado que precisa sobreviver a ida e volta pela
 * Viabilidade.
 *
 * POR QUE EXISTE. O `App` troca de tela por render CONDICIONAL (`tela === 'mapa' ? ...`),
 * entao abrir o estudo pontual DESMONTA o `MapScreen` e o `HexMap`. Com eles morre todo
 * o `useState` local: passo do funil, hexagono selecionado, pin da busca, cenario
 * multi-hex e a camera do deck.gl. Ao voltar pelo breadcrumb "vindo do mapa" a tela
 * remontava zerada — passo 1, sem pin, sem hexagono e a camera de volta ao centro do
 * municipio em zoom 9.6. UF e municipio nunca se perderam: esses moram no `App`.
 *
 * A foto e' guardada no `App` (que nao desmonta) e devolvida ao `MapScreen` na
 * remontagem.
 *
 * A foto carrega o CONTEXTO (uf + municipio) em que foi tirada. Sem isso, uma foto de
 * Sao Paulo/SP poderia ser aplicada depois de um drill-down em Campinas, restaurando um
 * pin e uma camera de outra cidade. `fotoAplicavel` e' o portao que impede isso — a
 * regra fica aqui, pura e testavel, em vez de depender so' da ordem dos efeitos do React.
 */

import type { SearchPin, ViewState } from '../components/HexMap'

export interface EstadoMapa {
  /** UF em que a foto foi tirada. */
  uf: string
  /** Municipio em que a foto foi tirada (vazio = visao da UF inteira). */
  municipio: string
  /** Passo do funil narrativo (1..5). */
  passoN: number
  /** Hexagono destacado no mapa. */
  selecionado: string | null
  /** Pin da busca por coordenada/endereco. */
  pin: SearchPin | null
  /** Texto cru da caixa de busca, para o operador reler o que digitou. */
  busca: string
  /** Filtro global "melhores hexes" (faixa M1). */
  filtroFaixa: string
  /** Cenario multi-hex: modo ligado e hexes somados. */
  modoCenario: boolean
  cenario: string[]
  /** Camera do deck.gl (centro, zoom, pitch, bearing). `null` = usar o padrao. */
  camera: ViewState | null
}

/** Foto neutra: o mapa comeca como sempre comecou. */
export const ESTADO_MAPA_VAZIO: EstadoMapa = {
  uf: '',
  municipio: '',
  passoN: 1,
  selecionado: null,
  pin: null,
  busca: '',
  filtroFaixa: '',
  modoCenario: false,
  cenario: [],
  camera: null,
}

/** Chave de contexto: muda quando o operador troca de UF ou faz drill-down. */
export function chaveContexto(uf: string, municipio: string): string {
  return `${uf}|${municipio}`
}

/**
 * Devolve a foto se ela pertencer ao contexto atual; senao devolve a foto vazia.
 *
 * E' o portao que impede restaurar pin/hexagono/camera de OUTRO municipio ou de OUTRA
 * UF. Uma foto sem contexto (`uf` vazio) e' sempre descartada: ou e' a foto neutra, ou
 * veio de uma versao anterior do estado.
 */
export function fotoAplicavel(
  foto: EstadoMapa | null | undefined,
  uf: string,
  municipio: string,
): EstadoMapa {
  if (!foto || !foto.uf) return ESTADO_MAPA_VAZIO
  if (chaveContexto(foto.uf, foto.municipio) !== chaveContexto(uf, municipio)) {
    return ESTADO_MAPA_VAZIO
  }
  return foto
}
