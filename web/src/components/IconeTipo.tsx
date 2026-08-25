/**
 * Icone por TIPO de imovel (SVG do design da aba imobiliaria). Extraido da
 * `OportunidadesImobiliariasScreen` quando a camada passou a aparecer tambem no
 * Mapa Territorial (ficha do hexagono + janela de detalhe do imovel).
 *
 * `stroke: currentColor` de proposito: quem escolhe a cor e' o container (via
 * `color`), normalmente a cor categorica do tipo (`corTipo` em lib/imovel).
 */
export default function IconeTipo({ tipo, tamanho }: { tipo: string; tamanho: number }) {
  const comum = {
    width: tamanho, height: tamanho, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const,
  }
  if (tipo === 'terreno') {
    return (
      <svg {...comum} aria-hidden>
        <path d="M4 8h16v12H4z" strokeDasharray="3 3" />
        <path d="M4 8 8 4h12l-4 4" />
      </svg>
    )
  }
  if (tipo === 'galpao') {
    return (
      <svg {...comum} aria-hidden>
        <path d="M3 10 12 5l9 5" />
        <path d="M4.5 10v9h15v-9" />
        <path d="M9.5 19v-5h5v5" />
      </svg>
    )
  }
  return (
    <svg {...comum} aria-hidden>
      <path d="M3 9h18l-2-4H5L3 9z" />
      <path d="M5 9v11h14V9" />
      <path d="M9 20v-6h6v6" />
    </svg>
  )
}
