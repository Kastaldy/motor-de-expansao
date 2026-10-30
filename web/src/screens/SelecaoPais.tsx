import type { ReactNode } from 'react'

/**
 * Os cartoes do portal do apex: um por pais que a pessoa pode abrir.
 *
 * ESTE ARQUIVO E' O FIO DE ALARME DA DEC-047, e por isso ele e' uma TABELA, nunca um
 * ramo por pais. A decisao recusou o pais virar caminho de execucao no codigo: nada de
 * `if` por sigla, nada de ternario escolhendo host ou nome. Um pais e' uma ENTRADA na
 * tabela `PAISES` — acrescentar a Colombia e' acrescentar uma linha aqui, nunca um galho
 * novo de `if`. O teste de contrato (`tests/unit/test_portal_paises.py`) reprova literal
 * de pais em condicional, e ha' teste vitest que renderiza a selecao para provar que uma
 * sigla fora da tabela e' simplesmente ignorada.
 *
 * O componente NAO decide QUAIS paises mostrar — ele recebe a lista ja' pronta (vinda de
 * `GET /api/me`, resolvida em `portal.tsx`) e desenha o que sabe desenhar. Quem manda a
 * lista e' o backend; aqui so' se traduz sigla -> cartao.
 */

/** O que o portal sabe de um pais: como chama-lo, para onde levar e que bandeira pintar. */
interface Pais {
  /** Nome exibido, acentuado (texto de usuario). */
  nome: string
  /** Host do piloto daquele pais, SEM esquema — o `href` monta `https://<host>/`. E'
   *  tambem o endereco que o cartao mostra em mono, para a pessoa conferir/guardar. */
  host: string
  /** Desenho da bandeira em SVG inline, os mesmos paths de `components/Dock.tsx`
   *  (const BANDEIRAS) e do portal estatico anterior. SVG e nao PNG: entra no bundle,
   *  sobrevive offline, nao borra em tela 2x e nao pede uma requisicao a mais. */
  bandeira: ReactNode
}

/**
 * A TABELA de paises, indexada por sigla. Iterar a lista de `paises` e buscar aqui e' o
 * unico jeito permitido de ir de sigla a cartao (DEC-047).
 *
 * Os desenhos das bandeiras sao copia fiel de `components/Dock.tsx` — o mesmo viewBox
 * `0 0 24 17` e os mesmos `fill`.
 */
export const PAISES: Record<string, Pais> = {
  BR: {
    nome: 'Brasil',
    host: 'piloto.ultra-expansao.tech',
    bandeira: (
      <>
        <rect width="24" height="17" rx="2" fill="#009b3a" />
        <path d="M12 2.2 21.4 8.5 12 14.8 2.6 8.5Z" fill="#ffdf00" />
        <circle cx="12" cy="8.5" r="3.4" fill="#002776" />
      </>
    ),
  },
  AR: {
    nome: 'Argentina',
    host: 'piloto-ar.ultra-expansao.tech',
    bandeira: (
      <>
        <rect width="24" height="17" rx="2" fill="#74acdf" />
        <rect y="5.7" width="24" height="5.6" fill="#fff" />
        <circle cx="12" cy="8.5" r="1.9" fill="#f6b40e" />
      </>
    ),
  },
}

const GRADE: React.CSSProperties = {
  listStyle: 'none',
  margin: 0,
  padding: 0,
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
  gap: 14,
}

// Aviso quando a pessoa tem paises mas nenhum tem cartao nesta build (ver o componente).
const SEM_CARTAO: React.CSSProperties = {
  margin: 0,
  padding: 18,
  border: '1px solid var(--line)',
  borderRadius: 'var(--r-2xl)',
  background: 'var(--surf-card)',
  color: 'var(--tx-narrative)',
}

const CARTAO: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 14,
  height: '100%',
  padding: 18,
  border: '1px solid var(--line)',
  borderRadius: 'var(--r-2xl)',
  background: 'var(--surf-card)',
  textDecoration: 'none',
  color: 'inherit',
}

const BANDEIRA: React.CSSProperties = {
  display: 'block',
  width: 34,
  height: 24,
  borderRadius: 3,
  flexShrink: 0,
  // Anel claro sob a bandeira: faixa clara encosta no fundo e perde a silhueta de
  // retangulo. Mesmo truque de `Dock.tsx` e do portal estatico anterior.
  boxShadow: '0 0 0 1px color-mix(in srgb, var(--tx-max) 20%, transparent)',
}

const NOME: React.CSSProperties = {
  display: 'block',
  font: '600 16px/1.25 var(--f-ui)',
  color: 'var(--tx-strong)',
}

// O endereco em mono porque e' literalmente um endereco para conferir — mesmo papel do
// `--f-num` no produto.
const HOST: React.CSSProperties = {
  display: 'block',
  marginTop: 3,
  font: '400 11.5px/1.3 var(--f-num)',
  color: 'var(--tx-muted)',
  overflowWrap: 'anywhere',
}

/**
 * A grade de cartoes de pais.
 *
 * `paises` e' a lista ORDENADA de siglas que a pessoa pode abrir (de `/api/me`). Cada
 * sigla vira cartao buscando a entrada na tabela `PAISES`; sigla sem entrada (um pais
 * que ainda nao desenhamos) e' ignorada, com aviso discreto no console — a tabela e'
 * dado, e desenhar um pais e' acrescentar uma linha a ela, nunca um ramo de codigo.
 */
export default function SelecaoPais({ paises }: { paises: readonly string[] }) {
  const cartoes = paises.flatMap((sigla) => {
    const pais = PAISES[sigla]
    if (!pais) {
      // Sem entrada na tabela: nao da' para desenhar um cartao honesto (nome, host,
      // bandeira), entao ignora. Aviso discreto para o dia em que `/api/me` mandar uma
      // sigla antes de o cartao dela existir.
      console.warn(`Portal: pais sem cartao desenhado, ignorado: ${sigla}`)
      return []
    }
    return [{ sigla, pais }]
  })

  if (cartoes.length === 0) {
    // A pessoa TEM paises (a lista chegou nao-vazia -- `portal.tsx` so' entra na selecao assim),
    // mas nenhum tem cartao desenhado nesta build: pode acontecer num rollout em que a sigla e'
    // liberada no banco antes de o cartao existir (`/api/me` devolve ['CO'] e CO ainda nao esta'
    // em PAISES). NAO e' "sem acesso" -- ela TEM acesso; e' um aviso, nunca uma <ul> vazia.
    return (
      <p style={SEM_CARTAO}>
        Os países liberados para você ainda não estão disponíveis nesta tela. Fale com o Felipe.
      </p>
    )
  }

  return (
    <ul style={GRADE}>
      {cartoes.map(({ sigla, pais }) => (
        <li key={sigla} style={{ display: 'block' }}>
          {/* Cartao e' <a> de verdade, nunca <div onClick>: assim o teclado alcanca, o
              "abrir em nova aba" funciona e o leitor de tela anuncia como link. */}
          <a className="portal-cartao" style={CARTAO} href={`https://${pais.host}/`}>
            {/* `aria-hidden` porque o nome do pais esta' escrito ao lado — a bandeira
                nao acrescenta informacao para quem usa leitor de tela. */}
            <svg
              viewBox="0 0 24 17"
              aria-hidden="true"
              focusable="false"
              style={BANDEIRA}
            >
              {pais.bandeira}
            </svg>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span style={NOME}>{pais.nome}</span>
              <span style={HOST}>{pais.host}</span>
            </span>
            <svg
              className="portal-seta"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              focusable="false"
              style={{ flexShrink: 0, color: 'var(--tx-sub)' }}
            >
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </a>
        </li>
      ))}
    </ul>
  )
}
