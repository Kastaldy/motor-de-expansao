/**
 * Incluir unidade Ultra pelo Mapa (DEC-085): a parte do formulário que não depende de tela.
 *
 * O fluxo tem TRÊS passos, e o do meio é a razão da feature: nada é gravado sem a pessoa ver,
 * numa tela de revisão, o que vai entrar no cadastro — nome, UF, cidade, ponto e a unidade da
 * rede mais perto. Corrigir uma coordenada errada custa um clique aqui; no cadastro, depois de
 * 1 dia, custa um PR.
 *
 *   formulário  --Revisar-->  revisão (POST /previa, não grava)  --Confirmar-->  salvo
 *        ^------------------------ Corrigir --------------------------|
 *
 * A pessoa digita só o NOME e a COORDENADA (prévia de 13/11/2026): a coordenada já diz o
 * estado e a cidade. O servidor os tira do ponto pela malha municipal, e a revisão os mostra
 * para conferência — ponto no mar ou fora do país é recusado ali.
 */
import { chaveDaCoordenada } from './comparacao-pontos'
import { parseCoordinate } from './coord'
import type { Pins, PreviaUnidadeSite, UnidadeSite } from './types'

export interface FormularioUnidade {
  unidade: string
  /** "latitude, longitude" como o Google Maps copia, ou o link do mapa */
  coordenadas: string
}

export const FORMULARIO_VAZIO: FormularioUnidade = { unidade: '', coordenadas: '' }

/** O corpo das rotas `/api/mapa/unidades-site` (sem o `confirmado`, que só o passo 3 manda). */
export interface CamposUnidade {
  unidade: string
  lat: number
  lng: number
}

export type LeituraDoFormulario = { ok: true; campos: CamposUnidade } | { ok: false; erro: string }

const espacos = (s: string) => s.trim().replace(/\s+/g, ' ')

/** Lê o formulário antes de pedir a revisão. A conferência de verdade (nome repetido, menos de
 *  200 m de outra unidade, fora do país) é do servidor; aqui só o que dá para dizer na hora. */
export function lerFormulario(f: FormularioUnidade): LeituraDoFormulario {
  const unidade = espacos(f.unidade)
  if (unidade.length < 2) return { ok: false, erro: 'Preencha o nome da unidade.' }
  if (!f.coordenadas.trim()) {
    return { ok: false, erro: 'Cole as coordenadas da unidade (latitude, longitude).' }
  }
  const ponto = parseCoordinate(f.coordenadas)
  if (!ponto) {
    return {
      ok: false,
      erro:
        'Coordenada não reconhecida ou fora do país. Use "latitude, longitude", do jeito que o ' +
        'Google Maps copia (ex.: -22.407291, -42.965760).',
    }
  }
  return { ok: true, campos: { unidade, lat: ponto.lat, lng: ponto.lng } }
}

/** A coordenada no formato que o próprio `parseCoordinate` lê de volta (ponto decimal). */
export function coordenadaTexto(lat: number, lng: number): string {
  return `${lat.toFixed(6)}, ${lng.toFixed(6)}`
}

/** "Corrigir" a partir da revisão: o formulário volta com o nome e a coordenada revisados. */
export function formularioDaPrevia(p: PreviaUnidadeSite): FormularioUnidade {
  return { unidade: p.unidade, coordenadas: coordenadaTexto(p.lat, p.lng) }
}

/** "Alterar" uma unidade do primeiro dia: o formulário volta com o que está gravado. */
export function formularioDaUnidade(u: UnidadeSite): FormularioUnidade {
  return { unidade: u.unidade, coordenadas: coordenadaTexto(u.lat, u.lng) }
}

/**
 * As coordenadas que DEIXARAM de ser de uma unidade do site entre duas listas: a removida e o
 * ponto antigo da alterada. O payload do recorte que o mapa já tem pode ainda trazê-las como
 * pino — `pinsComUnidadesDoSite` as tira.
 */
export function coordenadasSuperadas(antes: UnidadeSite[], depois: UnidadeSite[]): string[] {
  const vivas = new Set(depois.map((u) => chaveDaCoordenada(u.lat, u.lng)))
  return antes.map((u) => chaveDaCoordenada(u.lat, u.lng)).filter((k) => !vivas.has(k))
}

/**
 * Os pinos do recorte com as unidades do site somadas: a recém-incluída aparece com a logo da
 * Ultra NA HORA, mesmo com o município já carregado (o payload dele é anterior à inclusão).
 * Sem duplicar o que o servidor já manda, e sem as coordenadas superadas. O ícone `__ultra__`
 * entra quando o recorte não tinha Ultra nenhuma — sem ele, o pino não teria imagem.
 */
export function pinsComUnidadesDoSite(
  pins: Pins | undefined,
  vivas: UnidadeSite[],
  superadas: ReadonlySet<string>,
  iconeUltra: string | null | undefined,
): Pins | undefined {
  if (!pins || (!vivas.length && !superadas.size)) return pins
  const ultra = pins.ultra.filter((p) => !superadas.has(chaveDaCoordenada(p.lat, p.lng)))
  const presentes = new Set(ultra.map((p) => chaveDaCoordenada(p.lat, p.lng)))
  const novas = vivas
    .filter((u) => !presentes.has(chaveDaCoordenada(u.lat, u.lng)))
    .map((u) => ({ lat: u.lat, lng: u.lng, nome: u.unidade }))
  if (!novas.length && ultra.length === pins.ultra.length) return pins
  const icones =
    pins.icones.__ultra__ || !iconeUltra ? pins.icones : { ...pins.icones, __ultra__: iconeUltra }
  return { ...pins, ultra: [...ultra, ...novas], icones }
}

const fmt1 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const fmt0 = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })

export function distanciaTexto(metros: number): string {
  return metros < 1000 ? `${fmt0.format(metros)} m` : `${fmt1.format(metros / 1000)} km`
}

const semAcento = (s: string) =>
  s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()

/** A unidade mais perto, para a revisão. A cidade só entra quando o nome não a traz: o cadastro
 *  tem nomes como "Maricá / RJ", e "Maricá / RJ (Maricá/RJ)" diria a mesma coisa duas vezes. */
export function rotuloMaisPerto(m: NonNullable<PreviaUnidadeSite['mais_perto']>): string {
  const local = m.cidade ? `${m.cidade}/${m.uf}` : m.uf
  if (!m.cidade || semAcento(m.unidade).includes(semAcento(m.cidade))) return `${m.unidade}, a ${distanciaTexto(m.distancia_m)}`
  return `${m.unidade} (${local}), a ${distanciaTexto(m.distancia_m)}`
}

/** "até 14/11 às 15:32": o fim do prazo para alterar ou remover, no fuso de quem olha. */
export function prazoTexto(prazoAteIso: string, timeZone?: string): string {
  const quando = new Date(prazoAteIso)
  const dia = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', timeZone }).format(quando)
  const hora = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', timeZone }).format(quando)
  return `até ${dia} às ${hora}`
}

/** O aviso da revisão: o que acontece depois de confirmar. Texto de produto, num lugar só. */
export function avisoDoPrazo(prazoHoras: number): string {
  const prazo = prazoHoras === 24 ? '1 dia' : `${prazoHoras} horas`
  return (
    `Depois de confirmar, a unidade aparece no mapa na hora, e você tem ${prazo} para alterar ou ` +
    `remover. Passado esse prazo, a correção é feita pelo time de tecnologia. A unidade entra no ` +
    `mercado na primeira atualização de domingo depois do prazo.`
  )
}

/** As que ainda podem mudar: as únicas que a lista do painel mostra com Alterar e Remover. */
export function unidadesNoPrazo(lista: UnidadeSite[]): UnidadeSite[] {
  return lista.filter((u) => u.no_prazo)
}
