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
 * UF e cidade podem ficar em branco: a prévia as preenche pelo ponto (malha municipal), e o
 * "Corrigir" devolve o formulário já com elas, para a pessoa ajustar se o ponto errou.
 */
import { parseCoordinate } from './coord'
import type { PreviaUnidadeSite, UnidadeSite } from './types'

export interface FormularioUnidade {
  unidade: string
  /** "latitude, longitude" como o Google Maps copia, ou o link do mapa */
  coordenadas: string
  uf: string
  cidade: string
}

export const FORMULARIO_VAZIO: FormularioUnidade = { unidade: '', coordenadas: '', uf: '', cidade: '' }

/** O corpo das rotas `/api/mapa/unidades-site` (sem o `confirmado`, que só o passo 3 manda). */
export interface CamposUnidade {
  unidade: string
  lat: number
  lng: number
  uf: string | null
  cidade: string | null
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
  return {
    ok: true,
    campos: {
      unidade,
      lat: ponto.lat,
      lng: ponto.lng,
      uf: espacos(f.uf) || null,
      cidade: espacos(f.cidade) || null,
    },
  }
}

/** A coordenada no formato que o próprio `parseCoordinate` lê de volta (ponto decimal). */
export function coordenadaTexto(lat: number, lng: number): string {
  return `${lat.toFixed(6)}, ${lng.toFixed(6)}`
}

/** "Corrigir" a partir da revisão: o formulário volta com UF e cidade já preenchidas pelo ponto. */
export function formularioDaPrevia(p: PreviaUnidadeSite): FormularioUnidade {
  return { unidade: p.unidade, coordenadas: coordenadaTexto(p.lat, p.lng), uf: p.uf, cidade: p.cidade }
}

/** "Alterar" uma unidade do primeiro dia: o formulário volta com o que está gravado. */
export function formularioDaUnidade(u: UnidadeSite): FormularioUnidade {
  return { unidade: u.unidade, coordenadas: coordenadaTexto(u.lat, u.lng), uf: u.uf, cidade: u.cidade }
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
