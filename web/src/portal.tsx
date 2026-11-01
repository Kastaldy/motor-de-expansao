import { StrictMode, useCallback, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'

import LoginScreen from './screens/LoginScreen'
import SelecaoPais from './screens/SelecaoPais'
import { api, ApiError } from './lib/api'
import { falhaDoStatus, type FalhaLogin } from './lib/login'
import { MAX_TENTATIVAS } from './lib/login-motor'
import './styles/global.css'

/**
 * Ponto de entrada do PORTAL DO APEX (`ultra-expansao.tech`), que substitui o portal
 * estatico (template de texto) servido antes.
 *
 * O APEX E' O SELETOR DE PAIS, e e' PAIS-NEUTRO: ele nao serve dado de pais nenhum, nao
 * tem base, nao tem cache de pais — decide um destino e sai da frente (DEC-047). Cada
 * pais continua com seu processo, seu cache e seu `perfil.json`; aqui so' se escolhe por
 * qual porta entrar.
 *
 * O QUE ESTA PAGINA FAZ, no carregamento, lendo `GET /api/me`:
 *   - sem sessao (401) -> mostra o formulario de login, o MESMO `LoginScreen` da tela de
 *     entrar. No sucesso, NAO navega para `destinoSeguro`: o apex fica no apex. Re-consulta
 *     o `/api/me` (que `api.entrar` acabou de desmemoizar) e segue para a selecao.
 *   - `paises` nao-vazio -> a tela de SELECAO, um cartao por pais (`SelecaoPais`).
 *   - `paises` vazio (`[]`) -> "sem acesso": autenticada, mas sem pais liberado.
 *   - `paises` AUSENTE (nao da' para saber: sem banco/erro) ou falha de rede -> estado de
 *     erro discreto, com "tentar de novo". Nunca afirma "sem acesso" sem ter certeza.
 *
 * A lista de `paises` vem de `GET /api/me` (`resposta.paises`), NAO de
 * `resposta.perfil.pais` — aquele e' o pais do PROCESSO (um so'), este e' a lista de
 * paises DA PESSOA. O backend ja' esta' pronto; aqui so' se le o campo defensivamente,
 * no mesmo espirito de `abasDoPayload`.
 *
 * POR QUE CONTINUA UM BUNDLE SEPARADO (como a tela de entrar): quem esta' no apex ou nao
 * entrou, ou so' vai escolher um pais — em nenhum dos casos precisa dos ~1,5 MB da SPA do
 * piloto, que carregam o mapa inteiro e o nome de cada rota interna da API. O `fetch`
 * continua RELATIVO: mesma origem que o backend do apex, cookie aceito, sem CORS.
 */

/** As fases do portal. `carregando` e' o estado inicial, enquanto o 1o `/api/me` corre. */
type Fase =
  | { t: 'carregando' }
  | { t: 'login' }
  | { t: 'selecao'; paises: string[] }
  | { t: 'sem-acesso' }
  | { t: 'erro' }

/**
 * A lista de paises do payload do `/api/me`, defensiva (molde de `abasDoPayload`):
 *   - `null` quando o campo esta' AUSENTE ou nao e' lista -> "nao da' para saber" -> erro;
 *   - a lista de siglas (texto) quando presente, inclusive VAZIA -> "sem acesso".
 *
 * A diferenca entre AUSENTE e VAZIA e' deliberada: ausente e' falta de informacao (sem
 * banco, erro no servidor), vazia e' um fato (a pessoa nao tem pais liberado).
 */
function lerPaises(resp: unknown): string[] | null {
  if (typeof resp !== 'object' || resp === null) return null
  const bruto = (resp as { paises?: unknown }).paises
  if (!Array.isArray(bruto)) return null
  return bruto.filter((s): s is string => typeof s === 'string')
}

function Portal() {
  const [fase, setFase] = useState<Fase>({ t: 'carregando' })

  /* Contador de falhas DESTA carga, pelo MESMO motivo de `entrar.tsx`: a trava de
     tentativas do servidor responde o MESMO 401 de uma senha errada, de proposito —
     dizer "conta bloqueada" avisaria a quem varre nomes que acertou um. Contar aqui e' a
     unica forma de a tela nomear o bloqueio a partir de `MAX_TENTATIVAS`. `useRef` porque
     e' lido no envio e nao deve provocar redesenho. */
  const falhas = useRef(0)

  /* Guarda contra escrever estado depois de a tela sair (StrictMode remonta em dev; uma
     resposta tardia nao deve cair numa arvore ja' desmontada). */
  const montado = useRef(true)

  const carregar = useCallback(async () => {
    setFase({ t: 'carregando' })
    try {
      const resp = await api.me()
      if (!montado.current) return
      const paises = lerPaises(resp)
      if (paises === null) {
        // Campo ausente: nao da' para saber -> erro discreto, nunca "sem acesso".
        setFase({ t: 'erro' })
      } else if (paises.length === 0) {
        setFase({ t: 'sem-acesso' })
      } else {
        setFase({ t: 'selecao', paises })
      }
    } catch (erro) {
      if (!montado.current) return
      // 401 = sem sessao -> login. Qualquer outra coisa (rede, 5xx, timeout, 503) -> erro
      // discreto com "tentar de novo", que tambem cobre o banco ocupado.
      setFase(erro instanceof ApiError && erro.status === 401 ? { t: 'login' } : { t: 'erro' })
    }
  }, [])

  useEffect(() => {
    montado.current = true
    void carregar()
    return () => {
      montado.current = false
    }
  }, [carregar])

  async function aoEntrar(
    usuario: string,
    senha: string,
    manter: boolean,
  ): Promise<FalhaLogin | null> {
    try {
      await api.entrar(usuario, senha, manter)
    } catch (erro) {
      if (!(erro instanceof ApiError)) {
        // Rede caiu ou o timeout estourou. NUNCA "credencial": afirmar que a senha esta'
        // errada porque o servidor nao respondeu e' mentir para a pessoa.
        return 'indisponivel'
      }
      falhas.current += 1
      if (erro.status === 401 && falhas.current >= MAX_TENTATIVAS) return 'bloqueado'
      return falhaDoStatus(erro.status)
    }
    falhas.current = 0
    /* Entrou: o apex fica no apex. NAO navega para `destinoSeguro` — re-consulta o
       `/api/me` (que `api.entrar` acabou de desmemoizar) e segue para a selecao. */
    void carregar()
    /* Nao resolve: `carregar` troca a fase e desmonta a tela de login; sem isto o botao
       voltaria a 'Entrar' e convidaria um segundo envio nesse intervalo (mesmo motivo de
       `entrar.tsx`). */
    return await new Promise<FalhaLogin | null>(() => {})
  }

  if (fase.t === 'carregando') {
    // Momentaneo: o fundo ja' esta' pintado pelo CSS. Nada de spinner para um piscar.
    return null
  }

  if (fase.t === 'login') {
    // O MESMO componente da tela de entrar, servido sem `BaseProvider` (quem esta' aqui
    // ainda nao entrou): `useUfsDaBase` cai no default vazio e a tela degrada para neutro.
    return <LoginScreen onEntrar={aoEntrar} />
  }

  return (
    <div className="portal-pagina" style={PAGINA}>
      <style>{PORTAL_CSS}</style>

      <header style={BLOCO}>
        <div className="portal-marca" style={MARCA}>
          <span style={MARCA_TXT}>Ultra Academia</span>
        </div>
        <h1 style={H1}>Motor de Expansão</h1>
        {fase.t === 'selecao' && (
          <p style={SUB}>
            Escolha o país que você quer abrir. Cada país tem sua própria base, seu próprio
            mapa e sua própria carteira.
          </p>
        )}
      </header>

      <main style={BLOCO}>
        {fase.t === 'selecao' && <SelecaoPais paises={fase.paises} />}
        {fase.t === 'sem-acesso' && <SemAcesso />}
        {fase.t === 'erro' && <Erro aoTentarDeNovo={() => void carregar()} />}
      </main>

      {/* O rodape so' aparece na escolha (ou sem pais); no erro, so' o cartao de nova
          tentativa, porque nao sabemos a situacao da pessoa. */}
      {fase.t !== 'erro' && (
        <footer style={FOOTER}>
          <p style={{ margin: '0 0 6px' }}>
            Cada país tem a sua própria plataforma, e você entra em cada uma com o mesmo login e
            senha. A liberação de países é por pessoa.
          </p>
          <p style={{ margin: 0 }}>Precisa de acesso a mais algum país? Fale com o Felipe.</p>
        </footer>
      )}
    </div>
  )
}

/** "Sem acesso": autenticada, porém sem país liberado. Texto reaproveitado do portal
 *  estatico anterior, sem citar liberação por grupo — a liberação é por país. */
function SemAcesso() {
  return (
    <section style={AVISO}>
      <h2 style={AVISO_H2}>Você ainda não tem acesso a nenhum país</h2>
      <p style={AVISO_P}>
        Seu login está válido — o que falta é a liberação de um país específico. O acesso é
        concedido por país, não de uma vez só.
      </p>
      <p style={{ ...AVISO_P, marginBottom: 0 }}>Fale com o Felipe — leva minutos.</p>
    </section>
  )
}

/** Erro discreto: não deu para ler o acesso agora (rede, servidor, banco ocupado). Não
 *  afirma "sem acesso" — oferece tentar de novo. */
function Erro({ aoTentarDeNovo }: { aoTentarDeNovo: () => void }) {
  return (
    <section style={AVISO}>
      <h2 style={AVISO_H2}>Não foi possível carregar o seu acesso agora</h2>
      <p style={AVISO_P}>
        Pode ter sido uma instabilidade de rede ou do servidor. Tente de novo em instantes.
      </p>
      <button type="button" onClick={aoTentarDeNovo} style={BOTAO} className="portal-botao">
        Tentar de novo
      </button>
    </section>
  )
}

/* ---------------------------------------------------------------------------
   Estilos — tokens de `styles/tokens.css` (os mesmos papeis do produto), via inline como
   em `LoginScreen`. A moldura e' a do portal estatico anterior; as poucas regras que
   dependem de `:hover`/`:focus-visible` e os halos ficam no `<style>` abaixo.
   --------------------------------------------------------------------------- */

const PAGINA: React.CSSProperties = {
  // `position: absolute; inset: 0; overflow: auto` como no `LoginScreen`: o `body` do app
  // e' `overflow: hidden` e o `#root` tem altura fixa, entao a propria pagina gerencia o
  // scroll em telas baixas.
  position: 'absolute',
  inset: 0,
  overflow: 'auto',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 34,
  padding: '40px 20px',
  boxSizing: 'border-box',
}

const BLOCO: React.CSSProperties = { position: 'relative', zIndex: 1, width: '100%', maxWidth: 680 }

const MARCA: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  marginBottom: 18,
}

const MARCA_TXT: React.CSSProperties = {
  font: '600 11px/1 var(--f-ui)',
  letterSpacing: '0.16em',
  textTransform: 'uppercase',
  color: 'var(--tx-muted)',
}

const H1: React.CSSProperties = {
  margin: '0 0 10px',
  font: '400 clamp(30px, 7vw, 44px)/1.1 var(--f-story)',
  letterSpacing: '0.005em',
  color: 'var(--tx-max)',
}

const SUB: React.CSSProperties = {
  margin: 0,
  maxWidth: '46ch',
  color: 'var(--tx-narrative)',
  fontSize: 15,
}

const AVISO: React.CSSProperties = {
  padding: 20,
  border: '1px solid var(--line-strong)',
  borderRadius: 'var(--r-2xl)',
  background: 'var(--surf-raised)',
}

const AVISO_H2: React.CSSProperties = {
  margin: '0 0 8px',
  font: '600 15px/1.3 var(--f-ui)',
  color: 'var(--tx-strong)',
}

const AVISO_P: React.CSSProperties = { margin: '0 0 8px', color: 'var(--tx-narrative)' }

const BOTAO: React.CSSProperties = {
  marginTop: 6,
  padding: '10px 16px',
  border: '1px solid var(--ac)',
  borderRadius: 'var(--r-md)',
  background: 'transparent',
  color: 'var(--ac-text)',
  font: '600 14px/1 var(--f-ui)',
  cursor: 'pointer',
}

const FOOTER: React.CSSProperties = {
  position: 'relative',
  zIndex: 1,
  width: '100%',
  maxWidth: 680,
  borderTop: '1px solid var(--line-soft)',
  paddingTop: 16,
  color: 'var(--tx-muted)',
  fontSize: 12,
}

/* As poucas regras que inline nao alcanca (pseudo-elementos e pseudo-classes). Halo de
   fundo, barra vermelha da marca, e o realce de hover/foco dos cartoes e links. */
const PORTAL_CSS = `
.portal-pagina::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(60% 50% at 50% 0%, var(--ac-a12), transparent 70%);
  z-index: 0;
}
.portal-marca::before {
  content: '';
  width: 3px;
  height: 26px;
  border-radius: 2px;
  background: var(--ultra);
  flex-shrink: 0;
}
.portal-cartao {
  transition: border-color .15s ease, transform .15s ease, box-shadow .15s ease;
}
.portal-cartao:hover {
  border-color: var(--ac-a30);
  transform: translateY(-2px);
  box-shadow: var(--sh-pop);
}
.portal-cartao:focus-visible {
  outline: 2px solid var(--ac);
  outline-offset: 2px;
  border-color: var(--ac-a30);
}
.portal-seta { transition: color .15s ease, transform .15s ease; }
.portal-cartao:hover .portal-seta,
.portal-cartao:focus-visible .portal-seta {
  color: var(--ac-text);
  transform: translateX(2px);
}
.portal-botao:hover { border-color: var(--ac-text); color: var(--tx-max); }
.portal-botao:focus-visible { outline: 2px solid var(--ac); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) {
  .portal-cartao { transition: none; }
  .portal-cartao:hover { transform: none; }
  .portal-seta { transition: none; }
}
`

const el = document.getElementById('root')
if (!el) throw new Error('#root não encontrado no portal.html')
createRoot(el).render(
  <StrictMode>
    <Portal />
  </StrictMode>,
)
