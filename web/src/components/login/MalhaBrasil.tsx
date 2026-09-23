import { BRILHO, MALHA_BRASIL, PONTOS_REDE, RAIO_MALHA } from './malha-dados'

/**
 * O Brasil em hexágonos do painel da tela de entrar.
 *
 * Vem do mockup "Login · cartão flutuante" e reproduz a geometria dele; o que mudou na
 * portagem foi só a cor, que virou token. Cor cravada não tem par no tema claro, e esta
 * arte aparece nos dois — no claro ela ficaria como uma mancha escura sobre o gelo.
 *
 * `id` do gradiente: o mockup usava `"glow"` fixo, e a MESMA arte aparece duas vezes na
 * tela (fundo esvaecido e painel). Dois `<defs>` com o mesmo id no documento é id
 * duplicado — o segundo é ignorado e o brilho de um dos dois some. Por isso o id entra
 * por prop, e quem desenha duas vezes passa dois.
 */
export default function MalhaBrasil({ idBrilho }: { idBrilho: string }) {
  const meiaLargura = (Math.sqrt(3) / 2) * RAIO_MALHA
  const meiaAltura = RAIO_MALHA / 2

  return (
    <svg
      width="100%"
      height="100%"
      viewBox="40 -4 160 158"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden
      style={{ display: 'block' }}
    >
      <defs>
        <radialGradient id={idBrilho}>
          <stop offset="0%" stopColor="var(--ac)" stopOpacity="0.22" />
          <stop offset="55%" stopColor="var(--ac)" stopOpacity="0.07" />
          <stop offset="100%" stopColor="var(--ac)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <circle cx={BRILHO.cx} cy={BRILHO.cy} r={BRILHO.r} fill={`url(#${idBrilho})`} />

      {MALHA_BRASIL.map((h, i) => (
        <polygon
          key={i}
          points={[
            [h.cx + meiaLargura, h.cy - meiaAltura],
            [h.cx, h.cy - RAIO_MALHA],
            [h.cx - meiaLargura, h.cy - meiaAltura],
            [h.cx - meiaLargura, h.cy + meiaAltura],
            [h.cx, h.cy + RAIO_MALHA],
            [h.cx + meiaLargura, h.cy + meiaAltura],
          ]
            .map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`)
            .join(' ')}
          fill="var(--ac)"
          fillOpacity={h.alfa}
          stroke="var(--ac)"
          strokeOpacity={0.14}
          strokeWidth={0.6}
        />
      ))}

      {/* Os pontos são a REDE que já existe, e por isso levam o acento de operações —
          a mesma separação do Início: turquesa é território, rosa é rede.

          A arte é a MESMA nos dois temas. O mockup claro invertia os dois acentos
          (malha rosa, pontos turquesa) e a inversão chegou a ser implementada; posta
          lado a lado com esta, em 2026-09-22, o Felipe escolheu manter o turquesa —
          "combinou mais com o tema claro". Fica registrado para ninguém reabrir a
          diferença contra o mockup achando que é esquecimento. */}
      {PONTOS_REDE.map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={1.3} fill="var(--ops)" />
      ))}
    </svg>
  )
}
