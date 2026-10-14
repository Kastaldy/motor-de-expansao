import { useCallback, useMemo, useRef, useState } from 'react'

import { api, ApiError } from './api'
import { MAX_PONTOS, type PosicaoGeoJson } from './comparacao-pontos'
import { pontoInterno } from './geometria-desenho'
import {
  PONTOS_VAZIO,
  abrir as abrirAba,
  chegou,
  decidirPedido,
  falhou,
  itemAtivo,
  limpar as limparTudo,
  mostrar as mostrarItem,
  pedir,
  pinsDoEstado,
  remover as removerFicha,
  type EstadoPontos,
} from './pontos-estado'

/**
 * A lista de pontos analisados, viva no `App` — a fiação React das regras puras de
 * `lib/pontos-estado` (que é onde mora o porquê; aqui só a mecânica).
 *
 * A leitura do `/api/ponto` mora AQUI, e não na tela da ficha, porque os pedidos nascem em
 * três lugares — a caixa de colar da ficha, a lupa do cabeçalho do mapa e o "Selecionar
 * ponto" do trilho — e os três têm de terminar na MESMA lista, com a mesma regra de
 * repetição e de teto. E porque a tela da ficha desmonta ao ir para o Simulador: uma
 * leitura em voo morreria com ela.
 */
export function usePontos() {
  const [estado, setEstado] = useState<EstadoPontos>(PONTOS_VAZIO)
  /* Espelho SÍNCRONO do estado. `analisar` decide (repetido? cheio?) ANTES de pedir ao
     servidor, e decidir pelo estado do último render erraria com dois pedidos na mesma
     passagem — o segundo não veria o pendente do primeiro e passaria pelo teto. Não é
     updater de `setState` de propósito: o StrictMode roda updater duas vezes. */
  const ref = useRef(estado)
  const aplicar = useCallback((f: (e: EstadoPontos) => EstadoPontos) => {
    const proximo = f(ref.current)
    if (proximo === ref.current) return
    ref.current = proximo
    setEstado(proximo)
  }, [])

  const [erro, setErro] = useState<string | null>(null)

  /** Pede a análise de uma coordenada já resolvida. Nunca rejeita: o erro vai para `erro`. */
  const analisar = useCallback(
    async (lat: number, lng: number) => {
      const decisao = decidirPedido(ref.current, lat, lng)
      setErro(null)
      /* TETO CHEIO: recusa e DIZ, antes de gastar a leitura. Engolir o ponto em silêncio
         foi a metade do "depois de algumas vezes ele buga" (Juan, 2026-08-14). */
      if (decisao.tipo === 'cheio') {
        setErro(`Máximo de ${MAX_PONTOS} pontos na comparação. Remova um para analisar outro.`)
        return
      }
      aplicar((e) => pedir(e, lat, lng))
      if (decisao.tipo !== 'ler') return
      const pedido = { lat, lng }
      try {
        const ficha = await api.ponto(lat, lng)
        aplicar((e) => chegou(e, pedido, ficha))
      } catch (e) {
        /* NÃO limpa os pontos já lidos: perder três leituras porque a quarta falhou seria
           punir o operador por um endereço mal digitado. */
        aplicar((s) => falhou(s, pedido))
        setErro(e instanceof ApiError ? e.message : 'Falha ao analisar o ponto.')
      }
    },
    [aplicar],
  )

  /**
   * Pede a análise de uma ÁREA DESENHADA no mapa (DEC-071, fase 1): `POST
   * /api/ponto/geometria`. Entra na MESMA lista dos pontos — mesma regra de repetição, mesmo
   * teto, mesma cor por posição —, porque a pergunta do operador é a mesma: "qual destes
   * lugares serve mais?". O pin provisório fica num ponto INTERNO calculado aqui; quando a
   * ficha chega, ele passa ao `representative_point` que o servidor devolveu.
   */
  const analisarGeometria = useCallback(
    async (geometria: PosicaoGeoJson[][]) => {
      const anel = geometria[0] ?? []
      if (anel.length < 4) return
      const { lat, lng } = pontoInterno(anel)
      const decisao = decidirPedido(ref.current, lat, lng, geometria)
      setErro(null)
      if (decisao.tipo === 'cheio') {
        setErro(`Máximo de ${MAX_PONTOS} itens na comparação. Remova um para analisar esta área.`)
        return
      }
      aplicar((e) => pedir(e, lat, lng, geometria))
      if (decisao.tipo !== 'ler') return
      const pedido = { lat, lng, geometria }
      try {
        const ficha = await api.pontoGeometria({ type: 'Polygon', coordinates: geometria })
        aplicar((e) => chegou(e, pedido, ficha))
      } catch (e) {
        aplicar((s) => falhou(s, pedido))
        setErro(e instanceof ApiError ? e.message : 'Falha ao analisar a área desenhada.')
      }
    },
    [aplicar],
  )

  const abrir = useCallback((i: number) => aplicar((e) => abrirAba(e, i)), [aplicar])
  /** Abre a aba `i` e a janela da ficha — o clique no pin colorido do mapa. */
  const mostrar = useCallback((i: number) => aplicar((e) => mostrarItem(e, i)), [aplicar])
  const remover = useCallback((i: number) => aplicar((e) => removerFicha(e, i)), [aplicar])
  const limpar = useCallback(() => {
    aplicar(limparTudo)
    setErro(null)
  }, [aplicar])
  const limparErro = useCallback(() => setErro(null), [])

  const pins = useMemo(() => pinsDoEstado(estado), [estado])
  const ativo = useMemo(() => itemAtivo(estado), [estado])

  return {
    fichas: estado.fichas,
    aberto: estado.aberto,
    revelar: estado.revelar,
    /** Há leitura em voo — o "Lendo os setores…" da tela. */
    carregando: estado.pendentes.length > 0,
    erro,
    pins,
    ativo,
    analisar,
    analisarGeometria,
    abrir,
    mostrar,
    remover,
    limpar,
    limparErro,
  }
}
