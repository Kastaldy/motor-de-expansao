import { useCallback, useEffect, useState } from 'react'

import Dock from './components/Dock'
import MapScreen from './screens/MapScreen'
import ViabilityScreen from './screens/ViabilityScreen'
import { api, ApiError } from './lib/api'
import type { Hex, MunicipioItem, MunicipioPayload } from './lib/types'

export type Tela = 'mapa' | 'viabilidade'

/** O ponto que viaja do mapa para a Viabilidade — a costura entre as duas telas. */
export interface PontoEscolhido {
  hex: Hex
  rotulo: string
  municipio: string
  uf: string
}

export default function App() {
  const [tela, setTela] = useState<Tela>('mapa')

  const [ufs, setUfs] = useState<string[]>([])
  const [uf, setUf] = useState('DF')
  const [municipios, setMunicipios] = useState<MunicipioItem[]>([])
  const [municipio, setMunicipio] = useState('Brasília')

  const [dados, setDados] = useState<MunicipioPayload | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const [ponto, setPonto] = useState<PontoEscolhido | null>(null)

  // Catalogo de UFs, uma vez.
  useEffect(() => {
    api
      .ufs()
      .then((r) => setUfs(r.ufs))
      .catch((e: ApiError) => setErro(e.message))
  }, [])

  // Municipios da UF corrente.
  useEffect(() => {
    let vivo = true
    api
      .municipios(uf)
      .then((r) => {
        if (!vivo) return
        setMunicipios(r.municipios)
        // Mantem o municipio se ele existir na nova UF; senao pega o de maior residual.
        const existe = r.municipios.some(
          (m) => m.nome.toLowerCase() === municipio.toLowerCase(),
        )
        if (!existe && r.municipios.length) setMunicipio(r.municipios[0].nome)
      })
      .catch((e: ApiError) => setErro(e.message))
    return () => {
      vivo = false
    }
    // `municipio` de proposito fora: so reage a troca de UF.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uf])

  // Carga do municipio selecionado.
  useEffect(() => {
    if (!municipio) return
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .municipio(uf, municipio)
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

  const irParaViabilidade = useCallback(
    (p: PontoEscolhido) => {
      setPonto(p)
      setTela('viabilidade')
    },
    [],
  )

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
            onUf={setUf}
            municipios={municipios}
            municipio={municipio}
            onMunicipio={setMunicipio}
            dados={dados}
            carregando={carregando}
            erro={erro}
            onAnalisarPonto={irParaViabilidade}
          />
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
