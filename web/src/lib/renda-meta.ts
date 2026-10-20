/* ---------------------------------------------------------------------------
   Proveniência da renda exibida (E0 da renda): de que versão de fatores e de quando é a
   renda que a tela mostra.

   Chega UMA vez, no `/api/me` (chave `renda_meta`, top-level — não é campo do perfil do
   país, é da versão de fatores vigente no servidor). O `main.tsx` instala aqui antes de
   montar a árvore; o ícone `InfoRenda` lê o `rotulo` para o `title`/`aria-label`.

   Módulo PURO de propósito, no molde de `viabilidade-demanda.ts`: o vitest deste repo
   roda em node, sem jsdom, então a regra mora onde ele alcança.
   --------------------------------------------------------------------------- */

/** Recorte do `renda_meta` que o front usa. O payload traz mais (ano-base, exceções). */
export interface RendaMeta {
  /** Identificador cru da versão de fatores (ex.: `2026-08_caged_v0`). NÃO acentuar. */
  versao_fator: string
  /** Texto de referência para exibir (ex.: `06/2026 (CAGED; Censo jul/2022 x 1.1641)`). */
  rotulo: string
  /** Versão fixada por variável de ambiente (rollback), fora do vigente. */
  fixada_por_env: boolean
}

/** Estado do módulo: nasce ausente (backend anterior à E0 não manda a chave). */
let meta: RendaMeta | null = null

/** Proveniência vigente, ou `null` quando o servidor não a mandou. */
export function rendaMeta(): RendaMeta | null {
  return meta
}

/**
 * Frase do ícone de informação ao lado de cada renda, ou `null` sem proveniência. É o
 * `rotulo` do servidor, com um prefixo só para o leitor de tela não anunciar a data solta.
 */
export function textoInfoRenda(): string | null {
  if (!meta) return null
  return `Referência da renda: ${meta.rotulo}`
}

/**
 * Instala o `renda_meta` vindo do `/api/me`. Chamado UMA vez, pelo `main.tsx`. Payload
 * ausente ou malformado não instala nada e não derruba o app — o ícone simplesmente não
 * aparece.
 */
export function definirRendaMeta(p: unknown): void {
  meta = null
  if (!p || typeof p !== 'object') return
  const c = p as Partial<RendaMeta>
  if (typeof c.rotulo !== 'string' || !c.rotulo.trim()) return
  if (typeof c.versao_fator !== 'string' || !c.versao_fator.trim()) return
  meta = { rotulo: c.rotulo, versao_fator: c.versao_fator, fixada_por_env: c.fixada_por_env === true }
}

/** SÓ para teste: devolve o módulo ao estado de import. */
export function _resetarRendaMetaParaTeste(): void {
  meta = null
}
