import { useCallback, useEffect, useState } from 'react'

import Dock from './components/Dock'
import ExecutiveScreen from './screens/ExecutiveScreen'
import MapScreen from './screens/MapScreen'
import ViabilityScreen from './screens/ViabilityScreen'
import { api, ApiError } from './lib/api'
import { ESTADO_MAPA_VAZIO, type EstadoMapa } from './lib/mapa-estado'
import type { Hex, MunicipioItem, MunicipioPayload } from './lib/types'

export type Tela = 'mapa' | 'viabilidade' | 'executiva'

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
  const [tela, setTela] = useState<Tela>('mapa')

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
  const aoTrocarUf = useCallback((u: string) => {
    setUf(u)
    setMunicipio('')
  }, [])

  const irParaViabilidade = useCallback((p: PontoEscolhido) => {
    setPonto(p)
    setTela('viabilidade')
  }, [])

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
        {tela === 'mapa' ? (
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
          />
        ) : tela === 'executiva' ? (
          // A Executiva NÃO recebe `uf` nem `onUf` (DEC-023): ela abre com a rede do
          // Brasil inteiro e filtra por dentro. Herdar a UF do Mapa Territorial, além
          // de confundir dois produtos diferentes, disparava um refetch de
          // `/api/uf/{uf}` no Mapa toda vez que se trocava o estado aqui — leitura que
          // pode passar de 15 s.
          <ExecutiveScreen />
        ) : (
          <ViabilityScreen
            ponto={ponto}
            dados={dados}
            onVoltar={() => setTela('mapa')}
          />
        )}
      </main>
    </div>
  )
}
