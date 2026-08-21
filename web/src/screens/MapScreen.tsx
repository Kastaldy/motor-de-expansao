import { latLngToCell } from 'h3-js'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import type { PontoEscolhido } from '../App'
import BotaoInicio from '../components/BotaoInicio'
import FichaHex from '../components/FichaHex'
import FichaImovel from '../components/FichaImovel'
import HexMap, { type SearchPin, type ViewState } from '../components/HexMap'
import JanelaFicha from '../components/JanelaFicha'
import MethodologyPanel from '../components/MethodologyPanel'
import NarrativePanel from '../components/NarrativePanel'
import PainelComparacao from '../components/PainelComparacao'
import ScoreLegend from '../components/ScoreLegend'
import Select from '../components/Select'
import StepperBar from '../components/StepperBar'
import { Botao } from '../components/primitives'
import { api, ApiError, baixar } from '../lib/api'
import { parseCoordinate } from '../lib/coord'
import { alunos, coord, num } from '../lib/format'
import { ACC, ACC_50, ACC_TX } from '../lib/imovel'
import { chaveContexto, fotoAplicavel, type EstadoMapa } from '../lib/mapa-estado'
import { MAX_COMPARADOS, ranquear } from '../lib/ranking-comparacao'
import type { AlvoCaptura } from '../lib/captura-mapa'
import { DIMENSOES, rotuloDoHex, rotulosDosHexes } from '../lib/comparacao'
import type {
  Cobertura1k,
  Hex,
  Independentes,
  MunicipioItem,
  MunicipioPayload,
  Oportunidade,
} from '../lib/types'

/** Filtro global "melhores hexes": faixas M1 permitidas por nível. */
const FAIXA_FILTROS: Record<string, Set<string>> = {
  prioridade: new Set(['Prioridade máxima']),
  alta: new Set(['Prioridade máxima', 'Alta']),
  media: new Set(['Prioridade máxima', 'Alta', 'Média']),
}

export interface MapScreenProps {
  ufs: string[]
  uf: string
  onUf: (uf: string) => void
  municipios: MunicipioItem[]
  municipio: string
  onMunicipio: (m: string) => void
  dados: MunicipioPayload | null
  carregando: boolean
  erro: string | null
  onAnalisarPonto: (p: PontoEscolhido) => void
  /**
   * Foto do mapa guardada pelo App. O `App` renderiza as telas por CONDICIONAL, entao
   * ir para a Viabilidade DESMONTA esta tela e mata todo o `useState` local: passo do
   * funil, hexagono selecionado, pin da busca, cenario multi-hex e a camera do deck.gl.
   * Era isso que fazia o mapa "resetar" na volta pelo breadcrumb "vindo do mapa".
   * A UF e o municipio nunca se perderam — moram no App desde sempre.
   */
  estadoInicial: EstadoMapa
  onEstado: (e: EstadoMapa) => void
  /** Volta ao menu de modos. Não limpa nada — ver `components/BotaoInicio`. */
  onInicio: () => void
  /**
   * Pin imposto DE FORA, que vence o da busca local.
   *
   * Existe para o modo de ponto: la' quem escolhe o territorio e' o endereco colado, nao
   * a lupa desta tela. Um pin em state local nao serviria — o efeito que zera a tela ao
   * trocar de UF/municipio (logo abaixo) limpa `pin`, e a troca de municipio e'
   * exatamente o que acontece quando o operador cola um endereco. Vindo do pai, ele
   * sobrevive a essa limpeza, que continua valendo para a busca manual.
   */
  pinFixo?: SearchPin | null
  /**
   * Avisa que a busca do cabecalho resolveu uma coordenada.
   *
   * E' o que deixa o modo de ponto usar ESTA busca como entrada, em vez de por uma
   * segunda caixa de colar por cima da tela — duas caixas pedindo a mesma coisa, lado a
   * lado, e' o defeito que o Juan apontou em 2026-08-11. Quem escuta decide o que fazer
   * com a coordenada; aqui o comportamento nao muda (pin + hexagono selecionado).
   */
  onPontoBuscado?: (lat: number, lng: number) => void
  /**
   * Se esta tela publica a janela da FICHA DO HEXAGONO.
   *
   * `false` no modo de ponto: la' quem cola um endereco ja' recebe a janela DELE, e o
   * endereco tambem seleciona o hexagono em que caiu — as duas janelas abriam juntas,
   * uma por cima da outra, dizendo coisas diferentes sobre o mesmo lugar (relato do Juan,
   * 2026-08-12). A selecao continua valendo: o contorno no mapa e o item do ranking
   * seguem marcados, so' a segunda janela nao aparece.
   */
  janelaDoHex?: boolean
  /** Sem UF escolhida, não desenha o hero — quem o publica é a camada de cima. */
  semLanding?: boolean
  /**
   * Publica a função de CAPTURA do mapa para quem está fora deste componente.
   *
   * O modo de ponto é irmão na árvore e usa o MESMO mapa (`App.tsx`), então ele precisa
   * pedir capturas sem ter o mapa em mãos. Mesmo motivo pelo qual o `pinFixo` mora no App:
   * quem consome o mapa é o mapa, e o App só reparte o canal.
   */
  registrarCaptura?: (capturar: (alvos: AlvoCaptura[]) => Promise<string[]>) => void
  /**
   * Leva para a ABA de Oportunidades Imobiliárias já focada num imóvel — o caminho
   * INVERSO do "Ver no Mapa Territorial" daquela aba. Quem troca de tela é o App
   * (mesmo motivo do `onAnalisarPonto`); ausente = o botão da janela não aparece.
   */
  onVerImovelNaAba?: (o: Oportunidade) => void
}

export default function MapScreen({
  registrarCaptura,
  ufs,
  uf,
  onUf,
  municipios,
  municipio,
  onMunicipio,
  dados,
  carregando,
  erro,
  onAnalisarPonto,
  estadoInicial,
  onEstado,
  onInicio,
  pinFixo = null,
  onPontoBuscado,
  janelaDoHex = true,
  semLanding = false,
  onVerImovelNaAba,
}: MapScreenProps) {
  // A foto so' vale se tiver sido tirada NESTA uf/municipio — `fotoAplicavel` faz esse
  // portao (lib/mapa-estado). Sem ele, um pin de Sao Paulo reapareceria depois de um
  // drill-down em Campinas. `useState(() => ...)` roda so' na montagem: e' o unico
  // momento em que a foto e' consumida.
  const [foto] = useState(() => fotoAplicavel(estadoInicial, uf, municipio))

  // Todo estado abaixo NASCE da foto, nao de um valor fixo — e' o que devolve a tela
  // como estava quando o operador volta da Viabilidade.
  const [passoN, setPassoN] = useState(foto.passoN)
  const [metodologiaAberta, setMetodologiaAberta] = useState(false)
  const [selecionado, setSelecionado] = useState<string | null>(foto.selecionado)
  const [gerando, setGerando] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)

  // Busca por coordenada: solta um pin, marca o hexagono e habilita o estudo pontual.
  const [busca, setBusca] = useState(foto.busca)
  const [pin, setPin] = useState<SearchPin | null>(foto.pin)
  const [buscaErro, setBuscaErro] = useState<string | null>(null)
  const [buscando, setBuscando] = useState(false)

  // Filtro global: mostra só os melhores hexes (por faixa M1).
  const [filtroFaixa, setFiltroFaixa] = useState(foto.filtroFaixa)
  // Cenário multi-hex: seleção de vários hexes para somar.
  const [modoCenario, setModoCenario] = useState(foto.modoCenario)
  const [cenario, setCenario] = useState<string[]>(foto.cenario)
  const [copiado, setCopiado] = useState(false)

  // PROTOTIPO da chave de raio. Comeca SEMPRE em 2 km: o piloto abre identico ao de
  // hoje e nenhum numero muda sem alguem clicar. Nao entra no EstadoMapa de proposito —
  // e experimento, nao preferencia a preservar entre telas.
  const [raio1km, setRaio1km] = useState(false)

  /* Pins das academias INDEPENDENTES com score (BLK-MA-15). Comeca DESLIGADO pela mesma razao da
     chave de raio: o piloto abre identico ao de hoje. Sao ate ~1,3 mil pontos numa capital, e
     desenha-los sem pedido roubaria a leitura dos hexagonos por baixo. */
  const [verIndependentes, setVerIndependentes] = useState(false)
  const independentes = dados?.independentes ?? null
  const temIndependentes = independentes?.disponivel === true && independentes.itens.length > 0

  /* A chave morre com o recorte que a justificava: sair de um municipio COM camada para um SEM
     deixaria a pilula ligada sem nada para desenhar. */
  useEffect(() => {
    if (!temIndependentes) setVerIndependentes(false)
  }, [temIndependentes])

  /* Camada de OPORTUNIDADES IMOBILIARIAS (a oferta da aba, sobre o territorio).
     Comeca DESLIGADA pela mesma razao das outras chaves: o piloto abre identico ao
     de hoje. O dado vem por UF assim que ela e' escolhida — NAO espera a chave —
     porque tambem alimenta a secao "Imoveis disponiveis aqui" da ficha do hexagono,
     que vale com a camada apagada. E' leve perto do raio (payload JSON do top da UF,
     cacheado no servidor), por isso nao repete o padrao sob demanda da cobertura. */
  const [verImoveis, setVerImoveis] = useState(false)
  const [imoveisUf, setImoveisUf] = useState<Oportunidade[] | null>(null)
  /* A janela de DETALHE de um imovel — aberta pelo pin da camada ou pela secao da
     ficha do hexagono. Janela propria (ancora direita), nao um modo da FichaHex:
     o operador compara o imovel COM o hexagono, entao as duas ficam lado a lado. */
  const [imovelAberto, setImovelAberto] = useState<Oportunidade | null>(null)

  useEffect(() => {
    if (!uf) {
      setImoveisUf(null)
      return
    }
    let vivo = true
    /* Zera ANTES de buscar: sem isto, trocar de UF com a camada ligada deixava os
       pontinhos (e a contagem da pilula) da UF ANTERIOR na tela ate' a resposta nova. */
    setImoveisUf(null)
    api
      .oportunidades(uf, 3000)
      .then((r) => {
        if (vivo) setImoveisUf(r.itens)
      })
      .catch(() => {
        /* Lista VAZIA, nao null: null e' "carregando" e pula o auto-desligamento da
           chave — com null, um fetch falho deixava `verImoveis` ligado invisivel e a
           camada reacendia sozinha na UF seguinte. Vazia, o efeito abaixo desliga.
           Sem a camada o mapa segue como antes — a pilula nem aparece. */
        if (vivo) setImoveisUf([])
      })
    return () => {
      vivo = false
    }
  }, [uf])

  /* O recorte da camada acompanha o drill-down: na visao da UF desenha a UF inteira,
     no municipio so' o municipio (mesma chave de nome que o `onVerNoMapa` da aba ja
     usa para chegar aqui). So' entram no MAPA os imoveis com coordenada; os sem
     coordenada continuam aparecendo na secao da ficha do hexagono (via `hex_id`). */
  const imoveisNoMapa = useMemo(() => {
    const xs = (imoveisUf ?? []).filter((o) => o.lat != null && o.lng != null)
    return municipio ? xs.filter((o) => o.municipio === municipio) : xs
  }, [imoveisUf, municipio])
  const temImoveis = imoveisNoMapa.length > 0

  /* Mesma regra das independentes: a chave morre com o recorte que a justificava. */
  useEffect(() => {
    if (imoveisUf != null && !temImoveis) setVerImoveis(false)
  }, [imoveisUf, temImoveis])

  /* Geometria do raio: buscada SOB DEMANDA, so' quando a chave liga. Fora do payload do
     mapa de proposito — custa ~2,4 s e ~3,9 MB na UF de SP, e quem nunca liga a chave nao
     deve pagar isso. Trocar de UF/municipio zera a geometria (ela e' daquele recorte) e
     dispara nova busca se a chave estiver ligada. */
  const [cobertura, setCobertura] = useState<Cobertura1k | null>(null)
  const [carregandoRaio, setCarregandoRaio] = useState(false)

  useEffect(() => {
    if (!raio1km || !uf) {
      setCobertura(null)
      return
    }
    let vivo = true
    setCarregandoRaio(true)
    api
      .cobertura(uf, municipio || undefined)
      .then((c) => {
        if (vivo) setCobertura(c)
      })
      .catch(() => {
        // Sem geometria o mapa apenas nao desenha a cobertura — nao derruba a tela.
        if (vivo) setCobertura(null)
      })
      .finally(() => {
        if (vivo) setCarregandoRaio(false)
      })
    return () => {
      vivo = false
    }
  }, [raio1km, uf, municipio])

  // Camera do deck.gl em REF, nao em state, de proposito: o `onViewStateChange` do
  // deck dispara a cada quadro de um voo (centenas de vezes em 800 ms). Em state, cada
  // quadro re-renderizaria esta tela E o App inteiro (StepperBar, NarrativePanel,
  // MethodologyPanel...). Em ref, gravar e' de graca e a camera segue sempre atual.
  const cameraRef = useRef<ViewState | null>(foto.camera)

  // Estavel de proposito (`[]`): o HexMap tem `onCamera` nas dependencias do efeito que
  // publica a camera. Um callback inline mudaria de identidade a cada render e faria
  // aquele efeito disparar em todo render, nao so' quando a camera muda.
  const publicarCamera = useCallback((v: ViewState) => {
    /* Copia so' os campos de CAMERA. O `onViewStateChange` do deck.gl emite a cada
       quadro DURANTE o voo, carregando `transitionDuration` e a instancia de
       `FlyToInterpolator` junto. Guardando o objeto cru: (a) clicar em "Estudo pontual"
       dentro dos 800 ms congelava um quadro do meio do caminho — e, na volta, o guard do
       pin suprime o voo corretivo, entao o enquadramento intermediario virava
       permanente; (b) a foto deixava de ser serializavel. */
    cameraRef.current = {
      longitude: v.longitude,
      latitude: v.latitude,
      zoom: v.zoom,
      pitch: v.pitch,
      bearing: v.bearing,
    }
  }, [])

  // Trocar de UF/município recomeça a história do passo 1 e limpa a busca/cenário.
  // O guarda por ref e' ESSENCIAL: sem ele o efeito rodaria tambem na MONTAGEM da tela
  // e apagaria na hora o estado que acabou de ser restaurado — o mapa continuaria
  // "resetando" na volta, so' que por outro caminho.
  const contextoAnterior = useRef(chaveContexto(uf, municipio))
  useEffect(() => {
    const contexto = chaveContexto(uf, municipio)
    if (contextoAnterior.current === contexto) return
    contextoAnterior.current = contexto
    setPassoN(1)
    setSelecionado(null)
    setPin(null)
    setBuscaErro(null)
    setBuscando(false)
    setFiltroFaixa('')
    setModoCenario(false)
    setCenario([])
    setImovelAberto(null)
    cameraRef.current = null
  }, [uf, municipio])

  /**
   * O pin vindo de fora TAMBEM seleciona o hexagono dele.
   *
   * Sem isto o endereco colado no modo de ponto so' ganhava a marca e o voo da camera: o
   * hexagono em que ele cai ficava sem o contorno de selecao, e o painel lateral seguia
   * mostrando o item errado (ou nenhum). Selecionar e' o que amarra as tres leituras — o
   * ponto no mapa, o hexagono em volta dele e a linha correspondente no ranking.
   *
   * DEPOIS do efeito que zera a tela ao trocar de UF/municipio, e nao antes: colar um
   * endereco muda as duas coisas na mesma passagem, e aquele efeito poe `selecionado` em
   * `null`. A ordem de declaracao e' a ordem de execucao — invertida, a limpeza apagaria
   * a selecao que este acabou de fazer.
   */
  useEffect(() => {
    if (!pinFixo) return
    setSelecionado(pinFixo.hexId)
  }, [pinFixo])


  // Espelho SEMPRE atual do estado, mantido num ref. Existe para o cleanup do efeito
  // abaixo poder ler valores frescos: um cleanup enxerga o closure do render em que foi
  // criado, entao ler as variaveis de estado direto ali guardaria uma foto velha.
  // SEM `camera`: ela nao vive aqui de proposito (ver o efeito de publicacao abaixo).
  // O tipo declara isso, para nao voltar por engano e reintroduzir a foto velha.
  const estadoRef = useRef<Omit<EstadoMapa, 'camera'>>(foto)
  useEffect(() => {
    estadoRef.current = {
      // O contexto viaja COM a foto: e' o que permite descarta-la depois se o operador
      // trocar de UF/municipio antes de voltar ao mapa.
      uf,
      municipio,
      passoN,
      selecionado,
      pin,
      busca,
      filtroFaixa,
      modoCenario,
      cenario,
    }
  })

  /* Publica a foto no App UMA vez, ao desmontar — que e' exatamente quando ela passa a
     importar (o operador saiu para a Viabilidade). Publicar a cada mudanca faria o App
     re-renderizar a arvore inteira a cada clique no mapa, sem ganho nenhum.
     `onEstado` e' o `setEstadoMapa` do `useState` do App, cuja identidade o React
     garante estavel — o efeito nao remonta e nao publica antes da hora.

     A CAMERA E' LIDA AQUI, do ref, e nao do `estadoRef`. Motivo: `estadoRef` so' e
     atualizado quando o MapScreen RE-RENDERIZA, e a camera muda sem render — o voo ate
     o pin acontece dentro do HexMap (setView local) DEPOIS do ultimo render do
     MapScreen. Guardando a camera no espelho, o que se publicava era o enquadramento
     de ANTES do voo: o operador buscava o endereco, ia ao estudo pontual e voltava para
     o municipio inteiro em zoom 9.6 — e, como a camera restaurada nao e' nula, o voo de
     aproximacao ficava suprimido e o enquadramento nunca voltava. Quebrava justamente o
     caso de uso que motivou este PR. Mesmo caminho ao dar zoom num hex antes de
     "Analisar". */
  useEffect(() => {
    return () => onEstado({ ...estadoRef.current, camera: cameraRef.current })
  }, [onEstado])

  const passo = dados?.passos.find((p) => p.n === passoN) ?? dados?.passos[0] ?? null
  const nivelUf = dados?.nivel === 'uf'

  const porId = useMemo(
    () => new Map((dados?.hexes ?? []).map((h) => [h.id, h])),
    [dados],
  )

  /* O hexágono da janela da ficha. Sai do `porId` e não de uma cópia do payload: o mesmo
     objeto que o mapa desenha é o que a janela lê, então não há como as duas leituras
     divergirem depois de uma troca de município. */
  const hexSelecionado = selecionado ? (porId.get(selecionado) ?? null) : null
  const cresMunDoHex = hexSelecionado?.mun ? (dados?.cres_mun?.[hexSelecionado.mun] ?? null) : null

  /* Os imoveis DESTE hexagono, para a secao da ficha. Casa por `hex_id` (H3 res-7,
     a MESMA malha do M1) sobre o conjunto da UF inteira — independe da chave da
     camada e do drill-down: o hexagono aberto ja' e' um recorte. */
  const imoveisDoHex = useMemo(
    () =>
      hexSelecionado && imoveisUf
        ? imoveisUf.filter((o) => o.hex_id === hexSelecionado.id)
        : [],
    [imoveisUf, hexSelecionado],
  )

  // Municípios do dropdown: "Todos" (volta à UF) + lista alfabética.
  const opcoesMunicipio = useMemo(
    () => [
      { value: '', label: 'Todos os municípios' },
      ...[...municipios]
        .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
        .map((m) => ({ value: m.nome, label: m.nome })),
    ],
    [municipios],
  )

  // Filtro global de "melhores hexes" por faixa M1 (aplicado ao mapa).
  const hexesFiltrados = useMemo(() => {
    const hs = dados?.hexes ?? []
    const permitidas = FAIXA_FILTROS[filtroFaixa]
    return permitidas ? hs.filter((h) => h.faixa != null && permitidas.has(h.faixa)) : hs
  }, [dados, filtroFaixa])

  /**
   * Os hexes a COMPARAR: de 2 a 5 selecionados.
   *
   * Somar e comparar respondem perguntas diferentes ("quanto vale este pedaço junto"
   * x "qual destes é melhor"), e o número de hexes escolhidos já diz qual delas o
   * operador está fazendo — 2 a 5 é comparação, 1 ou 6+ é soma. Por isso o painel
   * troca sozinho, sem mais um botão para ele decidir.
   */
  const hexesComparacao = useMemo(() => {
    if (cenario.length < 2 || cenario.length > MAX_COMPARADOS) return null
    const hs = cenario.map((id) => porId.get(id)).filter(Boolean) as Hex[]
    return hs.length === cenario.length ? hs : null
  }, [cenario, porId])

  /* Comparativo ao vivo dos dois modelos, somado no cliente a partir dos hexes que o
     backend serviu para o recorte atual. O funil (numeros grandes e narrativa) continua
     vindo do modelo de 2 km — trocar aquilo exige mexer no payload do servidor, e este
     experimento existe para VER o efeito, nao para virar a chave. */
  const comparativoRaio = useMemo(() => {
    const hs = dados?.hexes ?? []
    if (!hs.length || hs[0].conc1k == null) return null
    let res2 = 0
    let res1 = 0
    let comConc = 0
    for (const h of hs) {
      res2 += h.oferta ?? 0
      res1 += h.oferta1k ?? 0
      if ((h.conc1k ?? 0) > 0) comConc += 1
    }
    return { res2, res1, comConc, total: hs.length }
  }, [dados])

  // Agregação do cenário multi-hex (soma no cliente a partir dos hexes servidos).
  const resumoCenario = useMemo(() => {
    const hs = cenario.map((id) => porId.get(id)).filter(Boolean) as Hex[]
    if (!hs.length) return null
    const soma = (f: (h: Hex) => number | null) => hs.reduce((a, h) => a + (f(h) ?? 0), 0)
    const scores = hs.map((h) => h.censo).filter((v): v is number => v != null)
    return {
      n: hs.length,
      residual: soma((h) => h.oferta),
      pop: soma((h) => h.pop),
      conc: soma((h) => h.conc),
      scoreMedio: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null,
    }
  }, [cenario, porId])

  function copiarCenario() {
    navigator.clipboard?.writeText(cenario.join('\n')).then(() => {
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1500)
    })
  }

  /**
   * Clique num item da LISTA: seleciona e LEVA A CAMERA ate' o hexagono.
   *
   * Antes so' desenhava o contorno branco. Num municipio grande o item escolhido podia
   * estar fora do enquadramento, entao a tela respondia ao clique num lugar que o
   * operador nao estava vendo — parecia que nada acontecia (Juan, 2026-08-12). O contorno
   * CONTINUA: chegar sem marca nenhuma deixaria a duvida de qual dos hexagonos e' o item.
   *
   * O clique no proprio mapa segue por `setSelecionado` direto, sem voo: la' o hexagono
   * ja' esta' sob o cursor, e recentrar seria mexer no que o operador acabou de mirar.
   */
  const [voo, setVoo] = useState<{ hexId: string; n: number } | null>(null)
  const selecionarDaLista = useCallback((hexId: string) => {
    setSelecionado(hexId)
    setPin(null)
    setVoo((v) => ({ hexId, n: (v?.n ?? 0) + 1 }))
  }, [])

  /* ---- Deck de comparacao (PDF) --------------------------------------------
     O MapScreen orquestra porque so' ele tem as duas pontas: o mapa (que captura) e a
     lista comparada (que vira o ranking). O painel so' pede.

     A ORDEM importa: primeiro as capturas, depois o POST. O ranking e' calculado AQUI, no
     mesmo `ranquear` que a tela usa, e viaja pronto — o servidor so' desenha, para nao
     existir uma segunda regra de "quem vence" que possa divergir da tela. */
  const [pedidoCaptura, setPedidoCaptura] = useState<{
    alvos: AlvoCaptura[]
    n: number
  } | null>(null)
  const [gerandoDeck, setGerandoDeck] = useState(false)

  /* A captura vira uma PROMESSA, e nao um par pedido/callback espalhado pela tela. Duas
     razoes: o fluxo do deck fica linear (`await capturar(...)` e segue), e o modo de PONTO
     — que e' irmao deste componente na arvore e usa o MESMO mapa — precisa pedir capturas
     tambem. Publicar a funcao por `registrarCaptura` e' o mesmo caminho que o `pinFixo` do
     App ja' usa: quem consome o mapa e' o mapa, entao o canal mora aqui e o App so' o
     reparte. */
  const resolveCaptura = useRef<((imagens: string[]) => void) | null>(null)

  const capturar = useCallback(
    (alvos: AlvoCaptura[]) =>
      new Promise<string[]>((resolve) => {
        resolveCaptura.current = resolve
        setPedidoCaptura((p) => ({ alvos, n: (p?.n ?? 0) + 1 }))
      }),
    [],
  )

  const aoCapturarMapas = useCallback((imagens: string[]) => {
    const resolver = resolveCaptura.current
    resolveCaptura.current = null
    resolver?.(imagens)
  }, [])

  useEffect(() => {
    registrarCaptura?.(capturar)
  }, [registrarCaptura, capturar])

  /* Os MESMOS rótulos do painel, e desambiguados: cinco hexágonos da mesma cidade davam
     cinco itens "São Paulo" no PDF, indistinguíveis entre si. A regra vive no `lib/` —
     duas cópias divergiriam no primeiro ajuste, e uma delas é o que vai para o PDF. */
  const rotulosComparacao = useCallback((hs: Hex[]) => rotulosDosHexes(hs), [])

  const pedirDeck = useCallback(
    async () => {
      const hs = hexesComparacao
      if (!hs?.length || gerandoDeck) return
      setGerandoDeck(true)
      try {
        // Sem coordenada: a comparacao de hexagonos nao tem imovel para marcar — o
        // assunto de cada foto e' a celula inteira.
        const imagens = await capturar(hs.map((h) => ({ hexId: h.id })))
        const rotulos = rotulosComparacao(hs)
        const ranking = ranquear(DIMENSOES, hs, rotulos)
        /* O subtítulo nomeia a cidade só quando TODAS são da mesma. Na visão de UF o mapa
           serve 15.000 hexágonos de 163 municípios (medido em SP), então o cenário pode
           misturar cidades — e usar o município do primeiro fazia a capa afirmar
           "São Paulo" para um conjunto que tinha só um hexágono de lá. */
        const cidades = [...new Set(hs.map((h) => h.mun).filter(Boolean))] as string[]
        const cidade =
          cidades.length === 1
            ? `${cidades[0]} - `
            : cidades.length > 1
              ? `${cidades.length} municípios - `
              : ''
        const resposta = await fetch('/api/relatorio/comparacao', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...ranking,
            titulo: 'Comparação de hexágonos',
            subtitulo: `${cidade}${hs.length} áreas`,
            imagens,
          }),
        })
        if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`)
        const blob = await resposta.blob()
        // Baixa pelo link temporario e REVOGA a URL: sem o revoke o blob fica retido pela
        // aba enquanto ela viver, e um deck tem alguns MB de imagem dentro.
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'comparacao-hexagonos.pdf'
        a.click()
        URL.revokeObjectURL(url)
      } catch (erro) {
        console.error('[deck] falhou ao gerar o PDF da comparação', erro)
      } finally {
        setGerandoDeck(false)
      }
    },
    [hexesComparacao, rotulosComparacao, capturar, gerandoDeck],
  )

  /**
   * Poe ou tira um hexagono da comparacao, direto da lista.
   *
   * LIGA o modo cenario junto: sem isso o painel de comparacao — que so' aparece com
   * `modoCenario` — ficaria escondido, e o operador veria o item marcado sem nenhum
   * resultado na tela. O teto de `MAX_COMPARADOS` e' respeitado aqui tambem, e nao so'
   * no clique do mapa.
   */
  const comparar = useCallback((hexId: string) => {
    setModoCenario(true)
    setCenario((cs) => {
      if (cs.includes(hexId)) return cs.filter((x) => x !== hexId)
      if (cs.length >= MAX_COMPARADOS) return cs
      return [...cs, hexId]
    })
  }, [])

  function aplicarPonto(lat: number, lng: number) {
    const hexId = latLngToCell(lat, lng, 7)
    setBuscaErro(null)
    setPin({ lat, lng, hexId })
    setSelecionado(hexId)
    onPontoBuscado?.(lat, lng)
  }

  async function buscarCoordenada() {
    const termo = busca.trim()
    if (!termo || buscando) return
    // 1) coordenada / link do Maps (offline, instantâneo)
    const c = parseCoordinate(termo)
    if (c) {
      aplicarPonto(c.lat, c.lng)
      return
    }
    // 2) endereço livre -> geocoding (Nominatim, DEC-010)
    setBuscando(true)
    setBuscaErro(null)
    try {
      const r = await api.geocode(termo)
      if (r.found && r.lat != null && r.lng != null) {
        aplicarPonto(r.lat, r.lng)
      } else {
        setBuscaErro(
          'Não encontrei esse endereço. Tente "lat, lng", um link do Google Maps ou um endereço mais completo.',
        )
        setPin(null)
      }
    } catch {
      setBuscaErro('Busca de endereço indisponível agora. Use "lat, lng" ou um link do Google Maps.')
    } finally {
      setBuscando(false)
    }
  }

  function estudoPontualDoPin() {
    if (!pin) return
    const real = porId.get(pin.hexId)
    const hex: Hex = real ?? {
      id: pin.hexId,
      lat: pin.lat,
      lng: pin.lng,
      m1: null,
      censo: null,
      hib: null,
      res: null,
      oferta: null,
      sam: null,
      pop: null,
      renda: null,
      renda_dom: null,
      faixa: null,
      conc: 0,
      ultra: 0,
      mun: null,
      cres_hex_taxa: null,
      cres_hex_classe: null,
    }
    onAnalisarPonto({
      hex,
      rotulo: coord(pin.lat, pin.lng),
      municipio: dados?.municipio ?? '',
      uf: dados?.uf ?? uf,
      // A coordenada BUSCADA viaja junto. `hex` aqui costuma ser o `real` do dataset,
      // cujo lat/lng é o CENTROIDE do hexágono — usá-lo no relatório tirava a foto de
      // satélite e o mapa de quadra de até ~1,5 km do imóvel (e, na orla, jogava o
      // ponto no mar -> "fora do Brasil"). O hexágono continua o mesmo: por construção
      // `latLngToCell(pin.lat, pin.lng, 7) === pin.hexId === hex.id`.
      lat: pin.lat,
      lng: pin.lng,
    })
  }

  async function gerarRelatorioMunicipal() {
    if (!dados || dados.nivel !== 'municipio' || !dados.municipio) return
    setGerando(true)
    setAviso(null)
    try {
      const { blob, filename } = await api.relatorioMunicipal(dados.uf, dados.municipio)
      baixar(blob, filename)
    } catch (e) {
      setAviso(e instanceof ApiError ? e.message : 'Não foi possível gerar o relatório.')
    } finally {
      setGerando(false)
    }
  }

  function analisar(hexId: string) {
    const h = porId.get(hexId)
    if (!h || !dados) return
    const item = dados.passos.flatMap((p) => p.itens).find((i) => i.hex_id === hexId)
    onAnalisarPonto({
      hex: h,
      rotulo: item?.titulo ?? dados.municipio ?? dados.uf,
      municipio: dados.municipio ?? '',
      uf: dados.uf,
    })
  }

  // ---------------- Passo 2 do modo de região: escolha de estado ----------------
  // Já NÃO é a porta de entrada do produto — essa é a `InicioScreen`. Aqui só se
  // pergunta o estado, e por isso o hero grande saiu daqui (ver `Landing`).
  if (!uf) {
    /* No modo de ponto quem manda na tela vazia é o `PontoScreen`, que publica o mesmo
       hero com o texto DELE e a caixa de colar. Sem isto, os dois apareciam juntos:
       "Escolha o estado" no fundo e a caixa de endereço por cima. */
    if (semLanding) return null
    return (
      <Landing
        marcador="Explorar uma região"
        titulo="Escolha o estado"
        explicacao="O mapa lê o território inteiro e monta a sequência de camadas — do potencial socioeconômico até os municípios com mais espaço para abrir."
        onInicio={onInicio}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 12,
            padding: '14px 16px',
            background: 'var(--surf-panel)',
            border: '1px solid var(--ac-a30)',
            borderRadius: 'var(--r-lg)',
            backdropFilter: 'blur(16px)',
            boxShadow: 'var(--ac-glow)',
          }}
        >
          <span style={{ font: '600 13px/1 var(--f-ui)', color: 'var(--tx-soft)' }}>
            Selecione um estado
          </span>
          {ufs.length ? (
            <Select
              label="Escolha um estado para começar"
              value=""
              onChange={onUf}
              maxWidth={260}
              buscavel
              placeholder="Escolha…"
              options={ufs.map((u) => ({ value: u, label: u }))}
            />
          ) : (
            <span className="num" style={{ font: '500 12px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
              carregando estados…
            </span>
          )}
        </div>
      </Landing>
    )
  }

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      {/* ---------------- Mapa ao fundo ---------------- */}
      {dados && passo && (
        <HexMap
          hexes={hexesFiltrados}
          passo={passo}
          cresMun={dados.cres_mun}
          centro={dados.centro}
          municipio={dados.municipio ?? undefined}
          uf={dados.uf}
          pins={dados.pins}
          selecionado={modoCenario ? null : selecionado}
          cenario={cenario}
          raio1km={raio1km}
          independentes={verIndependentes ? independentes?.itens : undefined}
          imoveis={verImoveis ? imoveisNoMapa : undefined}
          onImovel={setImovelAberto}
          cobertura1k={cobertura}
          /* A foto CONGELA na montagem, e trocar de UF/municipio zera `cameraRef` mas
             nao tem como zerar `foto.camera`. Sem este portao: SP/Sao Paulo -> volta da
             Viabilidade (foto.camera = zoom 14 sobre SP) -> troca a UF -> a carga falha
             e o App zera `dados`, o que DESMONTA o HexMap -> nova selecao remonta com a
             camera de Sao Paulo e, como `centroAnterior` ja e' o centro novo, nem voa:
             territorio novo com a camera parada sobre SP. */
          cameraInicial={
            chaveContexto(uf, municipio) === chaveContexto(foto.uf, foto.municipio)
              ? foto.camera
              : null
          }
          onCamera={publicarCamera}
          onSelecionar={(h) => {
            setPin(null)
            if (modoCenario) {
              setCenario((cs) =>
                cs.includes(h.id) ? cs.filter((x) => x !== h.id) : [...cs, h.id],
              )
            } else {
              setSelecionado(h.id)
            }
          }}
          searchPin={pinFixo ?? pin}
          voarPara={voo}
          pedidoCaptura={pedidoCaptura}
          onCapturas={aoCapturarMapas}
        />
      )}

      {/* ---------------- Header ---------------- */}
      <header
        style={{
          position: 'relative',
          zIndex: 10,
          margin: '16px 16px 0',
          padding: '9px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: 'var(--surf-chrome)',
          border: '1px solid var(--line-soft)',
          borderRadius: 'var(--r-xl)',
          backdropFilter: 'blur(14px)',
          flexWrap: 'wrap',
        }}
      >
        <BotaoInicio onInicio={onInicio} />

        <h1
          style={{
            font: '600 14px/1 var(--f-ui)',
            letterSpacing: '-.01em',
            color: 'var(--tx-max)',
            margin: 0,
          }}
        >
          Inteligência de Expansão
        </h1>

        <Divisor />

        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
            UF
          </span>
          <Select
            label="Unidade federativa"
            value={uf}
            onChange={onUf}
            maxWidth={74}
            options={ufs.map((u) => ({ value: u, label: u }))}
          />
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
            MUNICÍPIO
          </span>
          <Select
            label="Município"
            value={municipio}
            onChange={onMunicipio}
            maxWidth={210}
            options={opcoesMunicipio}
          />
        </label>

        {/* Saida VISIVEL do drill-down. Voltar a' visao do estado ja era possivel,
            mas so' abrindo o seletor e achando "Todos os municipios" no meio da
            lista — caminho que existe e nao se anuncia (relato de Felipe,
            2026-07-31). So' aparece quando ha' municipio selecionado. */}
        {municipio && (
          <Botao
            variante="ghost"
            onClick={() => onMunicipio('')}
            title="Voltar à visão do estado inteiro"
            style={{ padding: '6px 11px', font: '600 11.5px/1 var(--f-ui)', whiteSpace: 'nowrap' }}
          >
            ← Todos os municípios
          </Botao>
        )}

        <Divisor />

        {/* Lupa de busca por coordenada */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            background: 'var(--surf-input)',
            border: `1px solid ${buscaErro ? 'rgba(255,90,110,.5)' : 'var(--line)'}`,
            borderRadius: 9,
            padding: '6px 10px',
            minWidth: 210,
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke={buscando ? 'var(--ac)' : 'var(--tx-muted)'}
            strokeWidth="1.8"
            strokeLinecap="round"
            aria-hidden
            style={buscando ? { animation: 'pulse 1s ease-in-out infinite' } : undefined}
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            value={busca}
            onChange={(e) => {
              setBusca(e.target.value)
              if (buscaErro) setBuscaErro(null)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') buscarCoordenada()
            }}
            placeholder={buscando ? 'Buscando endereço…' : 'Buscar endereço, coordenada ou link'}
            aria-label="Buscar por endereço ou coordenada"
            style={{
              flex: 1,
              minWidth: 0,
              background: 'transparent',
              border: 'none',
              padding: 0,
              font: '500 12.5px/1 var(--f-ui)',
              color: 'var(--tx-strong)',
            }}
          />
          {pin && (
            <button
              type="button"
              aria-label="Limpar busca"
              onClick={() => {
                setPin(null)
                setBusca('')
                setSelecionado(null)
              }}
              style={{ color: 'var(--tx-muted)', font: '500 15px/1 var(--f-ui)', padding: 0 }}
            >
              ×
            </button>
          )}
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="num" style={{ font: '500 11px/1 var(--f-num)', color: 'var(--tx-muted)' }}>
            MELHORES
          </span>
          <Select
            label="Filtrar pelos melhores hexes"
            value={filtroFaixa}
            onChange={setFiltroFaixa}
            maxWidth={150}
            options={[
              { value: '', label: 'Todos os hexes' },
              { value: 'prioridade', label: 'Prioridade máxima' },
              { value: 'alta', label: 'Alta ou +' },
              { value: 'media', label: 'Média ou +' },
            ]}
          />
        </label>

        {/* Manual do funil. Ao lado do MELHORES e ANTES do `flex:1`: ocupa a folga do
            meio, entao o bloco de metricas segue ancorado na borda direita.

            A quebra do header em duas linhas a 100% de zoom NAO vem daqui — a 1280 px
            logicos (notebook Full HD com escala 150% do Windows, padrao de fabrica)
            todos os paineis da tela quebram, com ou sem este botao. E' aperto geral de
            layout, assunto separado. */}
        <Botao
          variante="ghost"
          onClick={() => setMetodologiaAberta((v) => !v)}
          title="Metodologia — o que cada camada mede e onde corta"
          style={{
            padding: '6px 11px',
            font: '600 11.5px/1 var(--f-ui)',
            whiteSpace: 'nowrap',
            ...(metodologiaAberta
              ? { color: 'var(--ac)', borderColor: 'var(--ac)', background: 'var(--ac-a12)' }
              : {}),
          }}
        >
          Metodologia
        </Botao>

        <div style={{ flex: 1 }} />

        {dados && (
          <div
            style={{
              display: 'flex',
              alignItems: 'stretch',
              background: 'var(--surf-raised)',
              border: '1px solid var(--line-soft)',
              borderRadius: 'var(--r-lg)',
              overflow: 'hidden',
            }}
          >
            <Metrica rotulo="hexágonos" valor={num(dados.n_hex_total)} />
            <MetricaDivisor />
            <Metrica rotulo="residual" valor={alunos(dados.resumo.residual_total)} />
            <MetricaDivisor />
            <Metrica rotulo="espaço p/ academias" valor={num(dados.resumo.espaco_academias)} destaque />
          </div>
        )}
      </header>

      {buscaErro && (
        <div
          role="alert"
          style={{
            position: 'relative',
            zIndex: 10,
            margin: '8px 16px 0',
            padding: '8px 12px',
            width: 'fit-content',
            borderRadius: 'var(--r-md)',
            background: 'rgba(255,90,110,.12)',
            border: '1px solid rgba(255,90,110,.3)',
            color: 'var(--neg)',
            font: '500 12px/1.4 var(--f-ui)',
          }}
        >
          {buscaErro}
        </div>
      )}

      {/* ---------------- Corpo: painel + rodapé ---------------- */}
      <div
        style={{
          position: 'relative',
          zIndex: 10,
          flex: 1,
          display: 'flex',
          justifyContent: 'flex-end',
          padding: '14px 16px 0',
          minHeight: 0,
          pointerEvents: 'none',
        }}
      >
        {dados && passo && (
          <div
            style={{
              position: 'absolute',
              left: 16,
              bottom: 10,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              pointerEvents: 'none',
            }}
          >
            {pin && (
              <div
                style={{
                  pointerEvents: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  background: 'var(--surf-panel)',
                  border: '1px solid var(--ac-a30)',
                  borderRadius: 'var(--r-md)',
                  padding: '9px 11px',
                  backdropFilter: 'blur(16px)',
                  maxWidth: 340,
                }}
              >
                <span style={{ minWidth: 0 }}>
                  <span
                    className="num"
                    style={{ display: 'block', font: '600 12px/1 var(--f-num)', color: 'var(--tx-max)' }}
                  >
                    {coord(pin.lat, pin.lng)}
                  </span>
                  <span
                    className="num"
                    style={{ display: 'block', font: '400 10px/1.2 var(--f-num)', color: 'var(--tx-sub)', marginTop: 3 }}
                  >
                    hex {pin.hexId}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={estudoPontualDoPin}
                  style={{
                    flexShrink: 0,
                    background: 'var(--ac)',
                    color: 'var(--ac-on)',
                    font: '700 12px/1 var(--f-ui)',
                    padding: '9px 12px',
                    borderRadius: 9,
                    boxShadow: 'var(--ac-glow)',
                  }}
                >
                  Estudo pontual →
                </button>
              </div>
            )}
            {!nivelUf && (
              <div
                style={{
                  pointerEvents: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  maxWidth: 280,
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    if (modoCenario) setCenario([])
                    setModoCenario((m) => !m)
                    setSelecionado(null)
                  }}
                  style={{
                    alignSelf: 'flex-start',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    background: modoCenario ? 'var(--ac-a16)' : 'var(--surf-panel)',
                    border: `1px solid ${modoCenario ? 'var(--ac-a30)' : 'var(--line-soft)'}`,
                    borderRadius: 'var(--r-md)',
                    padding: '8px 11px',
                    font: '600 12px/1 var(--f-ui)',
                    color: modoCenario ? 'var(--ac-text)' : 'var(--tx-soft)',
                    backdropFilter: 'blur(16px)',
                  }}
                >
                  {modoCenario ? '◆ Comparando hexes' : '◇ Comparar vários hexes'}
                </button>

                {/* O conteúdo da comparação saiu daqui e foi para uma JANELA (abaixo, no
                    fim da árvore). Como caixa presa ao canto, ela crescia sobre o mapa sem
                    o operador poder tirá-la do caminho — e é justamente o território que
                    ele está comparando que ficava coberto. Este botão continua sendo o
                    liga/desliga do modo. */}
              </div>
            )}

            <ScoreLegend passoN={passo.n} />

            {/* Academias INDEPENDENTES com score (BLK-MA-15). Vale em QUALQUER passo: a
                pergunta "quem ja opera aqui e esta espremido?" e' a INVERSAO do funil (comprar,
                nao abrir), entao nao pertence a camada nenhuma dele. */}
            {temIndependentes && (
              <PilulaIndependentes
                ligado={verIndependentes}
                meta={independentes}
                onToggle={() => setVerIndependentes((v) => !v)}
              />
            )}

            {/* OPORTUNIDADES IMOBILIARIAS do recorte (a oferta da aba, como pontinhos).
                Tambem vale em qualquer passo: "que imovel existe aqui?" e' pergunta de
                territorio, nao de camada do funil. So aparece quando o recorte tem
                imovel coletado — pilula sem nada para desenhar mentiria disponibilidade. */}
            {temImoveis && (
              <PilulaImoveis
                ligado={verImoveis}
                n={imoveisNoMapa.length}
                onToggle={() => setVerImoveis((v) => !v)}
              />
            )}

            {/* PROTOTIPO — chave do raio de atuacao das concorrentes. So aparece nos
                passos que falam de oferta e disputa, e so quando o backend serviu os
                campos do modelo novo. */}
            {comparativoRaio && (passo.n === 2 || passo.n === 3) && (
              <PilulaRaio
                ligado={raio1km}
                carregando={carregandoRaio}
                onToggle={() => setRaio1km((v) => !v)}
              />
            )}
          </div>
        )}

        <div style={{ pointerEvents: 'auto', display: 'flex', minHeight: 0 }}>
          {carregando && !dados ? (
            <PainelMensagem>
              {nivelUf || !municipio
                ? `Lendo o território de ${uf}…`
                : `Lendo ${municipio}…`}{' '}
              A primeira leitura de uma UF carrega a partição inteira e pode levar alguns segundos.
            </PainelMensagem>
          ) : erro ? (
            <PainelMensagem>
              {erro}
              <br />
              <br />O backend do piloto responde na porta 8899. Se você abriu o app sem ele, feche e
              use o <code>iniciar-piloto-web.cmd</code>.
            </PainelMensagem>
          ) : dados && passo ? (
            <NarrativePanel
              passo={passo}
              hexes={dados.hexes}
              totalPassos={dados.passos.length}
              cresMun={dados.cres_mun}
              uf={dados.uf}
              passos={dados.passos}
              nivel={dados.nivel}
              crescimentoEstado={dados.crescimento_estado}
              selecionado={selecionado}
              onSelecionarHex={selecionarDaLista}
              onAnalisar={analisar}
              onDrillMunicipio={onMunicipio}
              onComparar={comparar}
              comparados={cenario}
              maxComparados={MAX_COMPARADOS}
            />
          ) : null}
        </div>
      </div>

      {/* ---------------- Barra dos 4 passos ---------------- */}
      {dados && passo && (
        <div style={{ position: 'relative', zIndex: 10, padding: '14px 16px 16px' }}>
          {aviso && (
            <div
              role="alert"
              style={{
                marginBottom: 10,
                padding: '10px 14px',
                borderRadius: 'var(--r-md)',
                background: 'rgba(217,164,65,.14)',
                border: '1px solid rgba(217,164,65,.35)',
                color: 'var(--warn-text)',
                font: '500 12.5px/1.4 var(--f-ui)',
                display: 'flex',
                justifyContent: 'space-between',
                gap: 12,
                alignItems: 'center',
              }}
            >
              <span>{aviso}</span>
              <Botao variante="ghost" onClick={() => setAviso(null)} style={{ padding: '6px 10px' }}>
                Fechar
              </Botao>
            </div>
          )}
          <StepperBar
            passos={dados.passos}
            atual={passoN}
            onIr={(n) => setPassoN(Math.min(dados.passos.length, Math.max(1, n)))}
            onGerarRelatorio={gerarRelatorioMunicipal}
            gerando={gerando}
            nivelUf={nivelUf}
          />
        </div>
      )}

      {/* Gaveta da metodologia. Ultima na arvore e com zIndex acima do header para
          cobrir o chrome do mapa; o mapa em si continua visivel a' esquerda. */}
      {/* ---------------- Janela da FICHA DO HEXÁGONO ----------------
          Mesma janela da análise de ponto (arrasta, redimensiona, recolhe), agora para o
          hexágono escolhido. Antes o dado dele só existia em dois lugares efêmeros — o
          tooltip, que some com o mouse, e a linha do ranking, que mostra UMA métrica (a da
          camada ativa). Comparar dois bairros exigia trocar de camada quatro vezes.

          Some no modo de comparação: ali quem manda é o conjunto, e duas janelas dizendo
          coisas diferentes sobre a mesma seleção competiriam entre si. */}
      <JanelaFicha
        aberta={janelaDoHex && hexSelecionado != null && !modoCenario}
        /* BAIRRO, o MESMO nome que o painel da direita usa na lista. O titulo saia como
           o municipio, entao clicar em "Aracaré" no ranking abria uma ficha chamada
           "Itaquaquecetuba" — e o item de baixo abria outra com o mesmo nome (Juan,
           2026-08-19). Duas fichas com o titulo da cidade nao dizem qual area e' qual. */
        titulo={hexSelecionado ? rotuloDoHex(hexSelecionado) : 'Hexágono'}
        /* O id do hexágono NÃO entra abreviado aqui. H3 é hierárquico: vizinhos dividem o
           prefixo, então `87a8c0ce…` é o mesmo texto para hexágonos diferentes — piorava
           exatamente o que se quer resolver, que é saber qual é qual. A coordenada
           distingue de imediato; o id inteiro fica no corpo da ficha. */
        subtitulo={
          hexSelecionado
            ? [
                // O MUNICIPIO entra aqui quando o titulo virou bairro — senao "Aracaré"
                // sozinho nao diz em que cidade fica. Quando o titulo JA' e' o municipio
                // (visao de UF, ou hexagono fora da malha de bairros), nao se repete.
                hexSelecionado.bairro ? hexSelecionado.mun : null,
                dados?.uf,
                coord(hexSelecionado.lat, hexSelecionado.lng),
              ]
                .filter(Boolean)
                .join(' · ')
            : undefined
        }
        onFechar={() => setSelecionado(null)}
        recuoInferior={96}
      >
        {hexSelecionado && (
          <FichaHex
            hex={hexSelecionado}
            cres={cresMunDoHex}
            /* `comparar` já põe na lista E liga o modo cenário — sem isso o hexágono
               entraria marcado e o painel de comparação ficaria escondido. */
            onComparar={() => comparar(hexSelecionado.id)}
            imoveis={imoveisDoHex}
            onVerImovel={setImovelAberto}
          />
        )}
      </JanelaFicha>

      {/* ---------------- Janela do IMÓVEL (detalhe da oportunidade) ----------------
          Aberta pelo pin da camada imobiliária ou pela seção "Imóveis disponíveis
          aqui" da ficha do hexágono. Nasce à DIREITA: a ficha do hexágono usa a
          âncora padrão (esquerda) e o fluxo natural é ler as duas lado a lado. */}
      <JanelaFicha
        aberta={imovelAberto != null}
        ancora="direita"
        titulo={imovelAberto?.titulo ?? 'Imóvel'}
        subtitulo={
          imovelAberto
            ? [imovelAberto.bairro, imovelAberto.municipio, imovelAberto.uf]
                .filter(Boolean)
                .join(' · ')
            : undefined
        }
        onFechar={() => setImovelAberto(null)}
        recuoInferior={96}
      >
        {imovelAberto && (
          <FichaImovel
            op={imovelAberto}
            onVerNaAba={onVerImovelNaAba ? () => onVerImovelNaAba(imovelAberto) : undefined}
          />
        )}
      </JanelaFicha>

      {/* ---------------- Janela da COMPARAÇÃO ----------------
          À ESQUERDA de propósito: a ficha do hexágono nasce à direita, e duas janelas no
          mesmo canto abririam uma sobre a outra. Arrastar continua livre para as duas. */}
      <JanelaFicha
        aberta={modoCenario}
        titulo="Comparando hexágonos"
        subtitulo={`${cenario.length} de ${MAX_COMPARADOS} selecionados`}
        onFechar={() => {
          setModoCenario(false)
          setCenario([])
        }}
        recuoInferior={96}
      >
        {hexesComparacao ? (
          <PainelComparacao
            hexes={hexesComparacao}
            onLimpar={() => setCenario([])}
            /* `selecionarDaLista` já é o caminho de "clicou na lista, leve-me lá": ele
               seleciona e pede o voo. Clicar no mapa continua sem voo, porque lá o
               hexágono já está sob o cursor. */
            onIrPara={selecionarDaLista}
            onRelatorio={pedirDeck}
            gerandoRelatorio={gerandoDeck}
          />
        ) : (
          <div>
            <div style={{ font: '700 12px/1 var(--f-ui)', color: 'var(--tx-max)' }}>
              Cenário multi-hex · {resumoCenario?.n ?? 0} hex
            </div>
            {resumoCenario ? (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 5 }}>
                <LinhaC rotulo="Residual somado" valor={`${alunos(resumoCenario.residual)} alunos`} forte />
                <LinhaC rotulo="População" valor={num(resumoCenario.pop)} />
                <LinhaC rotulo="Score censo médio" valor={num(resumoCenario.scoreMedio, 1)} />
                <LinhaC rotulo="Concorrentes 2 km" valor={num(resumoCenario.conc)} />
              </div>
            ) : (
              <p style={{ margin: '8px 0 0', font: '400 11.5px/1.5 var(--f-ui)', color: 'var(--tx-muted)' }}>
                Clique nos hexágonos do mapa — ou no <strong style={{ color: 'var(--tx-soft)' }}>+</strong>{' '}
                dos itens da lista — para somar residual, população e score. De{' '}
                <strong style={{ color: 'var(--tx-soft)' }}>dois a {MAX_COMPARADOS}</strong>{' '}
                selecionados, esta janela compara e diz qual é o melhor.
              </p>
            )}
            {resumoCenario && (
              <div style={{ marginTop: 11, display: 'flex', gap: 8 }}>
                <button type="button" onClick={() => setCenario([])} style={botaoGhost}>
                  Limpar
                </button>
                <button type="button" onClick={copiarCenario} style={botaoGhost}>
                  {copiado ? 'Copiado ✓' : 'Copiar IDs'}
                </button>
              </div>
            )}
          </div>
        )}
      </JanelaFicha>

      <MethodologyPanel
        aberto={metodologiaAberta}
        onFechar={() => setMetodologiaAberta(false)}
        passoAtivo={passoN}
        escopo={nivelUf ? 'uf' : 'municipio'}
      />
    </div>
  )
}

/* ---------------- Passo 2 do modo de região: seletor de estado ----------------
   Isto JA FOI a porta de entrada do produto, com o hero "Por onde a Ultra deve crescer?".
   O hero migrou para a `InicioScreen`, que agora pergunta QUAL ANALISE antes de qualquer
   coisa; aqui sobrou a pergunta que sempre foi desta tela — qual estado —, e por isso o
   titulo encolheu de 44px para 26px. Manter os dois grandes deixava o operador diante de
   duas telas de abertura em sequencia, com o mesmo titulo. */

/**
 * O HERO de entrada de um modo: marcador, titulo, explicacao e UM controle.
 *
 * Exportado porque o modo de ponto usa o MESMO desenho com o proprio texto e a caixa de
 * colar no lugar do seletor de estado (pedido do Juan, 2026-08-12). Antes, entrar na
 * analise de ponto sem endereco mostrava este hero falando de "Explorar uma regiao" com a
 * caixa de colar flutuando por cima — dois assuntos disputando a mesma tela.
 */
export function Landing({
  marcador,
  titulo,
  explicacao,
  onInicio,
  children,
}: {
  marcador: string
  titulo: string
  explicacao: ReactNode
  onInicio: () => void
  /** O controle da tela: o seletor de estado, a caixa de colar, o que o modo pedir. */
  children: ReactNode
}) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background:
          'radial-gradient(120% 90% at 50% 30%, var(--bg-lift) 0%, var(--bg-base) 72%)',
      }}
    >
      {/* Mesma posicao do botao nas outras telas: canto superior esquerdo. */}
      <div style={{ position: 'absolute', top: 16, left: 16 }}>
        <BotaoInicio onInicio={onInicio} />
      </div>

      <div style={{ maxWidth: 560, textAlign: 'center' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            font: '600 11px/1 var(--f-ui)',
            letterSpacing: '.14em',
            textTransform: 'uppercase',
            color: 'var(--ac-text)',
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ac)' }} />
          {marcador}
        </span>

        <h1
          className="story"
          style={{
            font: '400 26px/1.15 var(--f-story)',
            color: 'var(--tx-max)',
            margin: '14px 0 0',
            letterSpacing: '.005em',
          }}
        >
          {titulo}
        </h1>

        <p
          style={{
            font: '400 15px/1.6 var(--f-ui)',
            color: 'var(--tx-narrative)',
            margin: '14px auto 0',
            maxWidth: 460,
          }}
        >
          {explicacao}
        </p>

        <div style={{ marginTop: 30 }}>{children}</div>

        <p
          style={{
            font: '400 11.5px/1.5 var(--f-ui)',
            color: 'var(--tx-sub)',
            margin: '18px 0 0',
          }}
        >
          27 estados · Censo 2022 (IBGE) + rede Ultra e concorrentes mapeados · camada visual read-only
        </p>
      </div>
    </div>
  )
}

const botaoGhost: React.CSSProperties = {
  flex: 1,
  padding: '7px 10px',
  borderRadius: 8,
  border: '1px solid var(--line-soft)',
  background: 'var(--surf-raised)',
  color: 'var(--tx-soft)',
  font: '600 11.5px/1 var(--f-ui)',
}

/** Linha do resumo do CENARIO multi-hex. O `forte` continua turquesa de proposito:
 *  o cenario e' o unico bloco que pertence ao modo turquesa (botao "◆ Comparando
 *  hexes" + contorno turquesa do hex no mapa). Fora dele o turquesa nao significa
 *  mais "numero importante" — ver --l1..--l4 em tokens.css. */
function LinhaC({ rotulo, valor, forte }: { rotulo: string; valor: string; forte?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14 }}>
      <span style={{ font: '400 11.5px/1 var(--f-ui)', color: 'var(--tx-label)' }}>{rotulo}</span>
      <span
        className="num"
        style={{
          font: `${forte ? 700 : 500} 12px/1 var(--f-num)`,
          color: forte ? 'var(--ac-text)' : 'var(--tx-soft)',
        }}
      >
        {valor}
      </span>
    </div>
  )
}

function Divisor() {
  return (
    <span
      aria-hidden
      style={{ width: 1, height: 20, background: 'var(--line-mid)', flexShrink: 0 }}
    />
  )
}

function Metrica({
  rotulo,
  valor,
  destaque,
}: {
  rotulo: string
  valor: string
  destaque?: boolean
}) {
  return (
    <div
      style={{
        // Largura igual nos três cards (o rótulo "espaço p/ academias" é o mais
        // largo; sem isto ele fica maior que os outros — pedido do Felipe).
        width: 116,
        flexShrink: 0,
        boxSizing: 'border-box',
        padding: '6px 8px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        // O destaque e' FORMA, nao matiz: fundo neutro + regra vertical. Em turquesa
        // este card usava a mesma familia do numero do funil (numero mono turquesa em
        // caixa turquesa fraca) para grandezas opostas — aqui um TOTAL fixo do
        // territorio, la' o CONTADOR da camada ativa. No passo 2, em que o funil
        // tambem fala de residual, o olho concluia que eram o mesmo numero em dois
        // lugares (relato de Juan, 2026-08-04: "leva o usuario a entender q sao as
        // mesmas coisas").
        //
        // A regra ja' foi `--ultra` (vermelho da marca) e `--info` (azul), e as duas
        // erraram pelo mesmo motivo: TODA matiz deste tema ja' significa outra coisa.
        // Vermelho e' alerta, e este numero e' oportunidade (Juan, 2026-08-05: "deixar
        // um azul para nao levar o usuario a entender q e' algo ruim"). Azul e' a
        // camada 1, e ai' o card passou a parecer parente do Potencial socioeconomico
        // (Juan, 2026-08-05: "o azul leva a entender q o potencial de socio e espaco
        // sao a mesma coisa").
        //
        // Restam violeta (camada 2), ambar (camada 3), turquesa (acao e camada 4) e
        // verde (positivo, e ainda por cima e' o topo da rampa de score do mapa). Nao
        // ha' matiz livre — entao o destaque fica SEM matiz: regra clara e neutra.
        // Ausencia de cor nao afirma parentesco com camada nenhuma, que era o defeito
        // comum das duas tentativas. Quem diz "este e' o numero em destaque" continua
        // sendo o par regra + fundo levantado, e nao o hue.
        background: destaque ? 'var(--surf-pending)' : 'transparent',
        borderLeft: destaque ? '2px solid var(--tx-max)' : undefined,
      }}
    >
      <div
        className="num"
        style={{
          font: '700 18px/1 var(--f-num)',
          // Neutro tambem no destaque: --ultra da' 3,26:1, serve como regra
          // grafica e reprova como cor de texto (mais ainda no rotulo de 8px).
          color: 'var(--tx-max)',
        }}
      >
        {valor}
      </div>
      <div
        style={{
          font: '600 8px/1 var(--f-ui)',
          color: 'var(--tx-label)',
          textTransform: 'uppercase',
          letterSpacing: '.05em',
          whiteSpace: 'nowrap',
        }}
      >
        {rotulo}
      </div>
    </div>
  )
}

function MetricaDivisor() {
  return (
    <span
      aria-hidden
      style={{ width: 1, background: 'var(--line-soft)', alignSelf: 'stretch' }}
    />
  )
}

function PainelMensagem({ children }: { children: React.ReactNode }) {
  return (
    <aside
      style={{
        width: 394,
        padding: '22px 20px',
        background: 'var(--surf-panel)',
        border: '1px solid var(--line-soft)',
        borderRadius: 'var(--r-2xl)',
        backdropFilter: 'blur(18px)',
        font: '400 13px/1.6 var(--f-ui)',
        color: 'var(--tx-narrative)',
        alignSelf: 'flex-start',
      }}
    >
      {children}
    </aside>
  )
}

/* --- PROTOTIPO: pilula do raio de atuacao das concorrentes ------------------
   Substituiu um painel de texto que ficava embaixo das faixas: o Felipe pediu
   leitura VISUAL, no mapa, nao um bloco de numeros na lateral. Aqui fica so o
   liga/desliga; quem conta a historia sao os circulos de 1 km desenhados em volta
   de cada concorrente e a cor dos hexagonos que eles alcancam.

   Abre SEMPRE em 2 km — o piloto continua identico ao de hoje ate alguem clicar. */
function PilulaRaio({
  ligado,
  carregando,
  onToggle,
}: {
  ligado: boolean
  carregando: boolean
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      title={
        ligado
          ? 'Mostrando o raio de 1 km de cada concorrente e os hexágonos que ela alcança'
          : 'Modelo atual: peso linear até 2 km medido do centróide do hexágono'
      }
      style={{
        // O container da legenda e' um overlay com `pointerEvents: 'none'` (para nao
        // roubar o arraste do mapa). Sem devolver 'auto' AQUI, o clique atravessa o
        // botao e vai para o mapa: a pilula aparece, mas nao liga nada. Era esse o
        // motivo de "nenhuma mudanca" — a chave nunca chegava a ficar true.
        pointerEvents: 'auto',
        marginTop: 8,
        width: '100%',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 11,
        fontWeight: 600,
        padding: '7px 11px',
        borderRadius: 9,
        border: `1px solid ${ligado ? 'rgba(53,201,214,.45)' : 'rgba(255,255,255,.14)'}`,
        // Fundo PRETO (pedido do Felipe): o botao fica sobre o mapa, e um fundo
        // translucido deixava a legenda das faixas atravessar o texto.
        background: '#000',
        color: ligado ? '#7de3ec' : '#9aa7b5',
      }}
    >
      <span
        style={{
          width: 9,
          height: 9,
          borderRadius: '50%',
          background: carregando ? '#f2c230' : ligado ? '#4fd3df' : '#5a6472',
          flexShrink: 0,
        }}
      />
      {carregando
        ? 'Carregando raio…'
        : ligado
          ? 'Raio 1 km por concorrente'
          : 'Ver raio de 1 km das concorrentes'}
    </button>
  )
}


/* Chave dos pins das academias INDEPENDENTES (BLK-MA-15).

   O texto diz de QUEM e' o pin, e nao so' "academias": o mapa ja tem bandeiras de CADEIA, e os
   dois universos sao opostos — a cadeia e' quem disputa o mercado, a independente e' quem se
   compra. Confundi-los na tela seria pior que nao mostrar nenhum.

   O TETO E' DECLARADO quando morde: corte silencioso num municipio grande mentiria sobre a
   densidade, que e' o defeito que o teto de pins de concorrente ja registrou. */
function PilulaIndependentes({
  ligado,
  meta,
  onToggle,
}: {
  ligado: boolean
  meta: Independentes | null
  onToggle: () => void
}) {
  const n = meta?.itens.length ?? 0
  const total = meta?.total ?? 0
  return (
    <button
      onClick={onToggle}
      title={
        ligado
          ? 'Cada ponto e uma academia independente. Passe o mouse para ver o score, a pressao ' +
            'competitiva medida da coordenada dela e a nota do WellHub.'
          : `Ver as ${total} academias independentes deste recorte, com score`
      }
      style={{
        // Mesmo motivo do `PilulaRaio`: o container da legenda tem `pointerEvents: 'none'`.
        pointerEvents: 'auto',
        marginTop: 8,
        width: '100%',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 11,
        fontWeight: 600,
        padding: '7px 11px',
        borderRadius: 9,
        border: `1px solid ${ligado ? 'rgba(232,102,60,.5)' : 'rgba(255,255,255,.14)'}`,
        background: '#000',
        color: ligado ? '#f2a488' : '#9aa7b5',
      }}
    >
      <span
        style={{
          width: 9,
          height: 9,
          borderRadius: '50%',
          background: ligado ? '#e8663c' : '#5a6472',
          flexShrink: 0,
        }}
      />
      {ligado
        ? `${n} independentes${meta?.truncado ? ` de ${total} (teto)` : ''}`
        : 'Ver academias independentes'}
    </button>
  )
}

/* Chave dos pontinhos de OPORTUNIDADES IMOBILIARIAS (a oferta da aba, no territorio).

   Identidade MAGENTA — o acento da propria aba imobiliaria (lib/imovel), que nenhuma
   outra camada do mapa usa: turquesa e' acao/cenario, laranja e' das independentes, e
   o comentario do card de metricas ja registrou que quase toda matiz do tema significa
   algo. Os PONTOS em si saem na cor categorica do TIPO (a mesma da aba); o magenta e'
   so o "isto e' da camada imobiliaria" da pilula e da janela de detalhe. */
function PilulaImoveis({
  ligado,
  n,
  onToggle,
}: {
  ligado: boolean
  n: number
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      title={
        ligado
          ? 'Cada ponto é um imóvel coletado, na cor do tipo (galpão, comercial/loja, terreno). ' +
            'Passe o mouse para ver aluguel, custo de ocupação, projeção e área; clique para abrir o detalhe.'
          : `Ver os ${n} imóveis de locação coletados neste recorte`
      }
      style={{
        // Mesmo motivo das outras pilulas: o container da legenda tem `pointerEvents: 'none'`.
        pointerEvents: 'auto',
        marginTop: 8,
        width: '100%',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 11,
        fontWeight: 600,
        padding: '7px 11px',
        borderRadius: 9,
        border: `1px solid ${ligado ? ACC_50 : 'rgba(255,255,255,.14)'}`,
        background: '#000',
        color: ligado ? ACC_TX : '#9aa7b5',
      }}
    >
      <span
        style={{
          width: 9,
          height: 9,
          borderRadius: '50%',
          background: ligado ? ACC : '#5a6472',
          flexShrink: 0,
        }}
      />
      {ligado
        ? `${n} ${n === 1 ? 'imóvel no recorte' : 'imóveis no recorte'}`
        : 'Ver oportunidades imobiliárias'}
    </button>
  )
}
