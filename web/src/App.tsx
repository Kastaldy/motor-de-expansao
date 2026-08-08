import { useCallback, useEffect, useState } from 'react'

import Dock from './components/Dock'
import ExecutiveScreen from './screens/ExecutiveScreen'
import InicioScreen from './screens/InicioScreen'
import MapScreen from './screens/MapScreen'
import PontoScreen from './screens/PontoScreen'
import ViabilityScreen from './screens/ViabilityScreen'
import { api, ApiError } from './lib/api'
import { modoPorId, passoAlvoDoModo, type ModoInicio } from './lib/inicio'
import { ESTADO_MAPA_VAZIO, type EstadoMapa } from './lib/mapa-estado'
import type { Hex, MunicipioItem, MunicipioPayload } from './lib/types'

export type Tela = 'inicio' | 'ponto' | 'mapa' | 'viabilidade' | 'executiva'

/** O ponto que viaja do mapa para a Viabilidade — a costura entre as duas telas. */
export interface PontoEscolhido {
  hex: Hex
  rotulo: string
  municipio: string
  uf: string
  /**
   * Coordenada EXATA do imóvel, quando o ponto veio da busca (endereço geocodificado
   * ou lat/lng digitada). `hex.lat/hex.lng` NÃO servem para isso: são o centroide do
   * hexágono res-7 (h3.cell_to_latlng no pipeline), a até ~1,5 km do endereço — o
   * bastante para a foto de satélite (400 m) e o mapa de quadra (~300 m) do PDF
   * saírem de outro lugar, e para o ponto cair no mar na orla (400 na malha IBGE).
   * Ausente quando o ponto veio do clique num hexágono do ranking: ali o centroide
   * é mesmo a única coordenada que existe.
   */
  lat?: number
  lng?: number
}

export default function App() {
  // O app abre no MENU, nao no mapa: a primeira pergunta e' "qual analise?", nao
  // "qual estado?". A escolha de UF continua existindo, como passo 2 do modo de regiao.
  const [tela, setTela] = useState<Tela>('inicio')

  const [ufs, setUfs] = useState<string[]>([])
  // Começa SEM estado: o app abre na porta de entrada (escolha de UF).
  const [uf, setUf] = useState('')
  const [municipios, setMunicipios] = useState<MunicipioItem[]>([])
  // Vazio = visão da UF inteira; preenchido = drill-down no município.
  const [municipio, setMunicipio] = useState('')

  const [dados, setDados] = useState<MunicipioPayload | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const [ponto, setPonto] = useState<PontoEscolhido | null>(null)

  // Foto do Mapa Territorial (ver lib/mapa-estado): vive AQUI porque o App nao desmonta
  // ao trocar de tela — e' o que devolve o mapa como estava na volta da Viabilidade.
  const [estadoMapa, setEstadoMapa] = useState<EstadoMapa>(ESTADO_MAPA_VAZIO)

  /**
   * Modo escolhido no menu que ainda nao pode ser aplicado porque falta a UF.
   *
   * POR QUE PRECISA EXISTIR. O card "melhores oportunidades" quer abrir o mapa direto no
   * passo 5, mas no instante do clique nao ha UF nenhuma — e semear a foto com
   * `uf: ''` seria inutil: `fotoAplicavel` (lib/mapa-estado) DESCARTA por desenho toda
   * foto sem contexto, justamente para nao restaurar pin/camera de outro municipio.
   * Entao a intencao fica pendurada aqui e e' convertida em foto no momento em que a UF
   * aparece — ai o contexto casa e o passo sobrevive.
   */
  const [modoPendente, setModoPendente] = useState<ModoInicio | null>(null)

  // Catálogo de UFs, uma vez.
  useEffect(() => {
    api
      .ufs()
      .then((r) => setUfs(r.ufs))
      .catch((e: ApiError) => setErro(e.message))
  }, [])

  // Municípios da UF corrente (alimenta o seletor do cabeçalho no drill-down).
  useEffect(() => {
    if (!uf) {
      setMunicipios([])
      return
    }
    let vivo = true
    api
      .municipios(uf)
      .then((r) => {
        if (vivo) setMunicipios(r.municipios)
      })
      .catch(() => {
        /* o seletor de município degrada gracioso */
      })
    return () => {
      vivo = false
    }
  }, [uf])

  // Carga dos dados: UF inteira (sem município) ou drill-down do município.
  useEffect(() => {
    if (!uf) {
      setDados(null)
      return
    }
    let vivo = true
    setCarregando(true)
    setErro(null)
    const pedido = municipio ? api.municipio(uf, municipio) : api.ufView(uf)
    pedido
      .then((d) => {
        if (vivo) setDados(d)
      })
      .catch((e: ApiError) => {
        if (vivo) {
          setErro(e.message)
          setDados(null)
        }
      })
      .finally(() => {
        if (vivo) setCarregando(false)
      })
    return () => {
      vivo = false
    }
  }, [uf, municipio])

  // Trocar de estado recomeça na visão da UF inteira. Não é preciso limpar a foto aqui:
  // ela carrega o contexto em que foi tirada e `fotoAplicavel` a descarta sozinha se a
  // UF/município não bater (lib/mapa-estado).
  const aoTrocarUf = useCallback(
    (u: string) => {
      setUf(u)
      setMunicipio('')

      // Agora que existe UF, a intenção guardada no menu vira foto — com o contexto
      // certo, senão `fotoAplicavel` a jogaria fora. Consumimos a intenção aqui: ela
      // vale para a PRIMEIRA entrada no mapa, não para toda troca de estado seguinte.
      if (!modoPendente) return
      const passo = passoAlvoDoModo(modoPendente)
      setModoPendente(null)
      if (passo === null) return
      setEstadoMapa({ ...ESTADO_MAPA_VAZIO, uf: u, municipio: '', passoN: passo })
    },
    [modoPendente],
  )

  /**
   * De qual tela o ponto veio. A Viabilidade e' alcancavel por DOIS caminhos (clique
   * num hexagono do mapa, e "Mais detalhes" na ficha do modo de ponto), e sem isto o
   * botao de volta devolvia sempre ao mapa — tirando do modo de ponto quem nunca
   * esteve no mapa.
   */
  const [origemViab, setOrigemViab] = useState<Tela>('mapa')

  const irParaViabilidade = useCallback(
    (p: PontoEscolhido) => {
      setPonto(p)
      setOrigemViab(tela === 'ponto' ? 'ponto' : 'mapa')
      setTela('viabilidade')
    },
    [tela],
  )

  /** Um card do menu foi escolhido: guarda a intenção e abre a tela que a atende hoje. */
  const escolherModo = useCallback(
    (modo: ModoInicio) => {
      const def = modoPorId(modo)
      if (!def) return
      // Só faz sentido guardar a intenção enquanto ela ainda não pôde ser aplicada.
      // Com UF já escolhida, aplicamos na hora — o operador que volta ao menu e pede a
      // fila não deveria ter de trocar de estado para ela aparecer.
      const passo = passoAlvoDoModo(modo)
      if (passo !== null && uf) {
        setEstadoMapa({ ...ESTADO_MAPA_VAZIO, uf, municipio, passoN: passo })
        setModoPendente(null)
      } else {
        setModoPendente(passo !== null ? modo : null)
      }
      setTela(def.destino)
    },
    [uf, municipio],
  )

  const voltarAoInicio = useCallback(() => setTela('inicio'), [])

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        background: 'var(--bg-base)',
        overflow: 'hidden',
      }}
    >
      <Dock tela={tela} onTela={setTela} />

      <main style={{ flex: 1, position: 'relative', minWidth: 0 }}>
        {tela === 'inicio' ? (
          <InicioScreen onEscolher={escolherModo} />
        ) : tela === 'ponto' ? (
          <PontoScreen onInicio={voltarAoInicio} onAnalisarPonto={irParaViabilidade} />
        ) : tela === 'mapa' ? (
          <MapScreen
            ufs={ufs}
            uf={uf}
            onUf={aoTrocarUf}
            municipios={municipios}
            municipio={municipio}
            onMunicipio={setMunicipio}
            dados={dados}
            carregando={carregando}
            erro={erro}
            onAnalisarPonto={irParaViabilidade}
            estadoInicial={estadoMapa}
            onEstado={setEstadoMapa}
            onInicio={voltarAoInicio}
          />
        ) : tela === 'executiva' ? (
          // A Executiva NÃO recebe `uf` nem `onUf` (DEC-023): ela abre com a rede do
          // Brasil inteiro e filtra por dentro. Herdar a UF do Mapa Territorial, além
          // de confundir dois produtos diferentes, disparava um refetch de
          // `/api/uf/{uf}` no Mapa toda vez que se trocava o estado aqui — leitura que
          // pode passar de 15 s.
          <ExecutiveScreen onInicio={voltarAoInicio} />
        ) : (
          <ViabilityScreen
            ponto={ponto}
            dados={dados}
            onVoltar={() => setTela(origemViab)}
            onInicio={voltarAoInicio}
            origemRotulo={origemViab === 'ponto' ? 'da análise de ponto' : 'do mapa'}
          />
        )}
      </main>
    </div>
  )
}
