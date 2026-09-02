/* ---------------------------------------------------------------------------
   Perfil do PAIS da instancia, do lado do cliente (Bloco A / DEC-047).

   NAO entra rota nova: o front ja pede `GET /api/me` na abertura, e o payload dessa
   rota ganhou um campo `perfil` com exatamente o que este arquivo declara — nem um
   campo a mais.

   QUANDO e seguro ler, que e a parte que engana
   ---------------------------------------------
   Ha duas classes de leitura, e elas NAO tem a mesma solucao:

   (1) Leitura sob INPUT do operador — `noBrasil` em `coord.ts`, a validacao de
       `entrada-ponto.ts`, todo `format.ts`. Essas funcoes so rodam quando alguem digita,
       sempre depois do bootstrap. Aqui um getter resolve, e o custo e um acesso a objeto.

   (2) Leitura na PRIMEIRA RENDERIZACAO — o inicializador preguicoso de `useState` em
       `HexMap.tsx` e o `VISTA_PADRAO` lido no corpo de `MapaPonto.tsx`. Inicializador de
       `useState` roda ANTES de qualquer efeito. Aqui getter NAO resolve: por mais tardia
       que a leitura seja escrita, ela acontece cedo demais, e o resultado e a camera
       nascendo em Brasilia numa instancia argentina.

   A solucao da classe (2) e ESTRUTURAL e vive no `main.tsx`: o perfil e resolvido, e so
   ENTAO o modulo da arvore e importado dinamicamente. Como `import` de ES module avalia
   o grafo inteiro na hora, importar `App` no topo faria todo `export const` derivado do
   perfil ser avaliado ANTES do fetch — o import dinamico e o que garante que nao.

   Isso tambem e o que permite a `export const CAPACIDADE_UNIDADE_ALUNOS = ...` continuar
   sendo uma constante, em vez de virar funcao e arrastar todos os call sites.
   --------------------------------------------------------------------------- */

import { PERFIL_BR } from './perfil-br'

export interface Bbox {
  lat_min: number
  lat_max: number
  lng_min: number
  lng_max: number
}

export interface PerfilCliente {
  /** Sigla ISO do pais da instancia. IDENTIFICADOR — nunca exibido cru: o Dock o usa
   *  para escolher a bandeira e o `rodape-base.ts` para escolher o vocabulario de
   *  unidade federativa. Ate 2026-09-02 esta resposta era DEDUZIDA da lista de UFs
   *  (`pais-da-base.ts`), por disjuncao binaria BR/AR — que acerta com dois paises e
   *  erra no terceiro. */
  pais: string
  /** Nome do pais, para as mensagens ("Essa coordenada esta fora de X"). */
  nome: string
  /** Tag BCP-47 UNICA — vai direto para `Intl.NumberFormat`. */
  locale: string
  moeda: { codigo: string; simbolo: string }
  bbox: Bbox
  vista_padrao: { lat: number; lng: number; zoom: number }
  reguas: { pop_min_acionavel: number; capacidade_unidade_alunos: number }
}

/**
 * Estado do modulo. Nasce no BR compilado para que os modulos puros — testados pelo
 * Vitest sem servidor — tenham numero valido desde o import.
 */
let atual: PerfilCliente = PERFIL_BR

/** Perfil vigente. Barato: e um acesso a variavel de modulo, sem alocacao. */
export function perfilDoCliente(): PerfilCliente {
  return atual
}

/** Simbolo da moeda. Atalho de conveniencia — `format.ts` o usa em oito lugares. */
export function moeda(): string {
  return atual.moeda.simbolo
}

/**
 * Instala o perfil vindo do `/api/me`. Chamado UMA vez, pelo `main.tsx`, ANTES de a
 * arvore ser importada.
 *
 * Payload ausente ou malformado NAO derruba o app e NAO substitui o default: um
 * backend velho (sem o campo) tem de continuar servindo o Brasil, que e o unico pais
 * em producao hoje. Quem falha alto e o BACKEND, no boot, quando o perfil falta —
 * la o fail-closed e barato e a mensagem nomeia o campo; aqui, derrubar a SPA por
 * causa de um campo ausente trocaria uma degradacao por uma tela branca.
 */
export function definirPerfil(p: unknown): void {
  if (!p || typeof p !== 'object') return
  const c = p as Partial<PerfilCliente>
  if (
    typeof c.pais !== 'string' ||
    typeof c.nome !== 'string' ||
    typeof c.locale !== 'string' ||
    !c.moeda ||
    typeof c.moeda.simbolo !== 'string' ||
    !c.bbox ||
    typeof c.bbox.lat_min !== 'number' ||
    typeof c.bbox.lat_max !== 'number' ||
    typeof c.bbox.lng_min !== 'number' ||
    typeof c.bbox.lng_max !== 'number' ||
    !c.vista_padrao ||
    typeof c.vista_padrao.lat !== 'number' ||
    !c.reguas ||
    typeof c.reguas.pop_min_acionavel !== 'number' ||
    typeof c.reguas.capacidade_unidade_alunos !== 'number'
  ) {
    return
  }
  atual = c as PerfilCliente
}

/** SO para teste: devolve o modulo ao default compilado. */
export function _resetarPerfilParaTeste(): void {
  atual = PERFIL_BR
}
