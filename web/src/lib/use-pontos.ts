import { useCallback, useMemo, useRef, useState } from 'react'

import { api, ApiError } from './api'
import { MAX_PONTOS } from './comparacao-pontos'
import {
  PONTOS_VAZIO,
  abrir as abrirAba,
  chegou,
  decidirPedido,
  falhou,
  itemAtivo,
  limpar as limparTudo,
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

  const abrir = useCallback((i: number) => aplicar((e) => abrirAba(e, i)), [aplicar])
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
    abrir,
    remover,
    limpar,
    limparErro,
  }
}
