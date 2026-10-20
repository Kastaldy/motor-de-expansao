import { useCallback, useMemo, useRef, useState } from 'react'

import { ALCANCE_PADRAO, ehAlcance, type Alcance } from './alcance'
import { api, ApiError } from './api'
import { MAX_PONTOS, chaveDaCoordenada, indiceDoMesmoPonto, type PosicaoGeoJson } from './comparacao-pontos'
import { avisoDeEstudoDePonto, ehRecusaDoEstudoDaUnidade } from './estudo-ultra'
import { pontoInterno } from './geometria-desenho'
import {
  PONTOS_VAZIO,
  TROCAS_VAZIO,
  abrir as abrirAba,
  esquecerTroca,
  chegou,
  concluirTroca,
  decidirPedido,
  falhou,
  itemAtivo,
  LEITURA_ULTRA,
  leituraDaFicha,
  limpar as limparTudo,
  limparTrocas,
  mostrar as mostrarItem,
  pedir,
  pedirTroca,
  pendenteDoPedido,
  pinsDoEstado,
  pontosEmTroca,
  releituraAoChegar,
  remover as removerFicha,
  substituir,
  type EstadoPontos,
  type TrocasDeModo,
} from './pontos-estado'
import { ehAreaDesenhada } from './recorte'
import type { PontoPayload } from './types'

/** Lê o ponto na leitura descrita (`leituraDaFicha`) — a rota de sempre para o raio de 1 km. */
function lerNoModo(lat: number, lng: number, leitura: string): Promise<PontoPayload> {
  if (leitura === LEITURA_ULTRA) return api.ponto(lat, lng, { excluirUltraProxima: true })
  /* O raio de 1 km volta pela rota de SEMPRE (`GET /api/ponto`), byte a byte igual à
     ficha que o ponto teve ao entrar — e funciona com servidor anterior à DEC-074. */
  if (leitura === ALCANCE_PADRAO || !ehAlcance(leitura)) return api.ponto(lat, lng)
  return api.pontoAlcance(lat, lng, leitura)
}

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
  /* As releituras de modo em voo, com a geração de cada uma (`lib/pontos-estado`,
     `TrocasDeModo`). Espelho síncrono pelo mesmo motivo do `ref` acima: dois cliques na
     mesma passagem têm de ver um ao outro. */
  const trocasRef = useRef<TrocasDeModo>(TROCAS_VAZIO)
  /** As coordenadas (`chaveDaCoordenada`) cujas fichas estão sendo relidas em outro modo. */
  const [trocandoModo, setTrocandoModo] = useState<readonly string[]>([])
  const aplicarTrocas = useCallback((t: TrocasDeModo) => {
    if (t === trocasRef.current) return
    trocasRef.current = t
    setTrocandoModo(pontosEmTroca(t))
  }, [])

  /**
   * Relê o ponto `i` no OUTRO modo de estudo (emenda da DEC-070): estudo de ponto (a Ultra
   * próxima conta) <-> estudo da unidade Ultra (o consumo da própria unidade sai). A ficha
   * é TROCADA no lugar (`substituir`) — mesma aba, mesma cor, mesma posição. Falhou: a
   * ficha anterior fica, e o motivo do servidor vai para `erro`.
   *
   * O modo final é SEMPRE o do último clique (revisão do PR #457): cada releitura leva uma
   * geração, e só a vigente é aplicada — "liga, desliga" rápido cancela a primeira, e uma
   * resposta velha que chegue depois da nova é descartada (`pedirTroca`/`concluirTroca`).
   */
  const trocarLeitura = useCallback(
    async (i: number, querida: string, falha: string) => {
      const f = ref.current.fichas[i]
      if (!f || ehAreaDesenhada(f)) return
      const chave = chaveDaCoordenada(f.lat, f.lng)
      const { trocas, decisao } = pedirTroca(trocasRef.current, chave, leituraDaFicha(f), querida)
      aplicarTrocas(trocas)
      if (decisao.tipo !== 'ler') return
      setErro(null)
      try {
        const nova = await lerNoModo(f.lat, f.lng, querida)
        const fim = concluirTroca(trocasRef.current, chave, decisao.geracao)
        if (!fim.vale) return
        aplicarTrocas(fim.trocas)
        aplicar((e) => substituir(e, nova))
      } catch (e) {
        const fim = concluirTroca(trocasRef.current, chave, decisao.geracao)
        /* A falha de um pedido que o operador já desfez não é notícia: o modo que ele quer
           é o que está na tela. Falhou de verdade (o serviço de rotas fora do ar, 503): a
           ficha anterior FICA, e o motivo do servidor é dito — nunca cai em silêncio para
           o raio de 1 km. */
        if (!fim.vale) return
        aplicarTrocas(fim.trocas)
        setErro(e instanceof ApiError ? e.message : falha)
      }
    },
    [aplicar, aplicarTrocas],
  )

  const trocarModo = useCallback(
    /* O estudo da unidade Ultra é só do raio de 1 km (como o servidor): ligar a chave num
       ponto de outro alcance o devolve ao raio de 1 km; desligar mantém o raio de 1 km. */
    (i: number, estudoUltra: boolean) =>
      trocarLeitura(i, estudoUltra ? LEITURA_ULTRA : ALCANCE_PADRAO, 'Falha ao trocar o modo do estudo.'),
    [trocarLeitura],
  )

  /**
   * Troca o ALCANCE do ponto `i` (DEC-074): raio de 1 km, de 2 km ou 10 min de carro. A
   * ficha é relida e TROCADA no lugar — mesmo nome, mesma cor, mesma posição na lista —,
   * pela mesma regra de "último clique vence" do modo. Escolher outro alcance com o estudo
   * da unidade Ultra ligado sai do estudo da unidade: ele só existe no raio de 1 km.
   */
  const trocarAlcance = useCallback(
    (i: number, alcance: Alcance) => trocarLeitura(i, alcance, 'Falha ao trocar o alcance do ponto.'),
    [trocarLeitura],
  )

  /**
   * Pede a análise de uma coordenada já resolvida. Nunca rejeita: o erro vai para `erro`.
   * `doMapa`: o pedido veio de um clique no próprio mapa ("Selecionar ponto") — o pin não
   * voa nem aproxima a câmera (ver `PontoPendente.doMapa`).
   *
   * `estudoUltra` (emenda da DEC-070): o estudo PARTE DA UNIDADE Ultra (a ficha da unidade
   * no mapa) — a ficha já chega sem o consumo dela. Ponto já na lista em outro modo: abre a
   * aba e troca o modo. Se o servidor não achar a unidade a até 150 m (coordenada da base
   * da rede longe do cadastro do mapa), o ponto ENTRA como estudo de ponto e o aviso diz
   * por quê — perder a análise inteira por isso seria pior que analisar no outro modo.
   */
  const analisar = useCallback(
    async (lat: number, lng: number, opcoes?: { doMapa?: boolean; estudoUltra?: boolean }) => {
      const estudoUltra = opcoes?.estudoUltra === true
      const decisao = decidirPedido(ref.current, lat, lng, null, estudoUltra)
      setErro(null)
      /* TETO CHEIO: recusa e DIZ, antes de gastar a leitura. Engolir o ponto em silêncio
         foi a metade do "depois de algumas vezes ele buga" (Juan, 2026-08-14). */
      if (decisao.tipo === 'cheio') {
        setErro(`Máximo de ${MAX_PONTOS} pontos na comparação. Remova um para analisar outro.`)
        return
      }
      aplicar((e) => pedir(e, lat, lng, null, opcoes?.doMapa === true, estudoUltra))
      if (decisao.tipo === 'repetido') {
        if (estudoUltra) void trocarModo(decisao.indice, true)
        return
      }
      if (decisao.tipo !== 'ler') return
      const pedido = { lat, lng }
      try {
        let ficha: PontoPayload
        try {
          ficha = await api.ponto(lat, lng, estudoUltra ? { excluirUltraProxima: true } : undefined)
        } catch (e) {
          if (!(estudoUltra && e instanceof ApiError && ehRecusaDoEstudoDaUnidade(e))) throw e
          ficha = await api.ponto(lat, lng)
          setErro(avisoDeEstudoDePonto(e.message, 'ponto'))
        }
        /* O modo QUERIDO vive no pendente: se, enquanto esta leitura voava, o mesmo lugar
           foi pedido como estudo da unidade, a ficha que chegou está no modo velho e é
           relida no pedido (`releituraAoChegar`). */
        const pendente = pendenteDoPedido(ref.current, pedido)
        aplicar((e) => chegou(e, pedido, ficha))
        if (releituraAoChegar(pendente, estudoUltra, ficha)) {
          const i = indiceDoMesmoPonto(ref.current.fichas, ficha.lat, ficha.lng)
          if (i >= 0) void trocarModo(i, true)
        }
      } catch (e) {
        /* NÃO limpa os pontos já lidos: perder três leituras porque a quarta falhou seria
           punir o operador por um endereço mal digitado. */
        aplicar((s) => falhou(s, pedido))
        setErro(e instanceof ApiError ? e.message : 'Falha ao analisar o ponto.')
      }
    },
    [aplicar, trocarModo],
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
  const remover = useCallback(
    (i: number) => {
      const f = ref.current.fichas[i]
      aplicar((e) => removerFicha(e, i))
      /* A troca de modo em voo deste ponto morre com ele: senão, remover e analisar de novo
         o mesmo lugar deixava a resposta antiga trocar o modo da ficha nova. */
      if (f && !ehAreaDesenhada(f)) aplicarTrocas(esquecerTroca(trocasRef.current, chaveDaCoordenada(f.lat, f.lng)))
    },
    [aplicar, aplicarTrocas],
  )
  const limpar = useCallback(() => {
    aplicar(limparTudo)
    /* Releituras em voo de pontos que acabaram de sair: a resposta é descartada. A geração
       NÃO volta a 0 (`limparTrocas`): um pedido novo reusaria o número de um antigo no ar. */
    aplicarTrocas(limparTrocas(trocasRef.current))
    setErro(null)
  }, [aplicar, aplicarTrocas])
  const limparErro = useCallback(() => setErro(null), [])

  const pins = useMemo(() => pinsDoEstado(estado), [estado])
  const ativo = useMemo(() => itemAtivo(estado), [estado])

  return {
    fichas: estado.fichas,
    aberto: estado.aberto,
    revelar: estado.revelar,
    /** Sobe quando o operador escolhe um item — o mapa vai até ele (`movimentoDoMapa`). */
    foco: estado.foco,
    /** Há leitura em voo — o "Lendo os setores…" da tela. */
    carregando: estado.pendentes.length > 0,
    erro,
    pins,
    ativo,
    analisar,
    analisarGeometria,
    /** Troca o modo de estudo do ponto `i` (estudo de ponto <-> unidade Ultra). */
    trocarModo,
    /** Troca o alcance do ponto `i` no lugar (raio de 1 km, de 2 km, 10 min de carro). */
    trocarAlcance,
    /** `chaveDaCoordenada` dos pontos em releitura de modo ou de alcance. */
    trocandoModo,
    abrir,
    mostrar,
    remover,
    limpar,
    limparErro,
  }
}
