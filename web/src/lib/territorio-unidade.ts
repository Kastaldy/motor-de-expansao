/**
 * O TERRITORIO de uma unidade Ultra escolhida no mapa (pedido do Vinicius, 21/10/2026):
 * "ao selecionar uma unidade, o municipio da unidade deve ser selecionado junto".
 *
 * Antes, escolher uma unidade (seletor UNIDADES do cabecalho ou clique no pin da Ultra)
 * abria a ficha e levava a camera ate' ela, mas o cabecalho continuava no territorio
 * anterior: a visao do estado inteiro, ou OUTRA cidade -- e o painel, o funil e o ranking
 * falavam de um lugar que nao era o da unidade aberta.
 *
 * DE ONDE VEM O MUNICIPIO DA UNIDADE. O payload da rede (`RedeUnidade`,
 * `RedeUnidadeSemRede`) traz `uf` e `cidade` -- a cidade e' TEXTO LIVRE do cadastro
 * (`dashboard/rede_cadastro.py`, semeado de planilha mantida a mao). Nao ha' codigo IBGE
 * nem no cadastro nem na lista de municipios (`/api/municipios/{uf}` devolve so' `nome`),
 * e o municipio do app inteiro e' a chave (UF, nome): `api.municipio(uf, nome)`. Por isso
 * a resolucao e' SEMPRE dentro da lista da UF DA UNIDADE -- os 232 nomes que se repetem
 * entre UFs nao colidem aqui, porque nunca se procura um nome fora da UF dele (e dentro de
 * uma UF o nome de municipio e' unico).
 *
 * A ORDEM, do mais ao menos declarado:
 *  1. o nome do cadastro, sem acento/caixa/pontuacao, contra a lista da UF (com e sem um
 *     sufixo de UF, "Goiania - GO");
 *  2. UF de UM municipio so' (o DF: a cidade no cadastro e' a regiao administrativa,
 *     "Taguatinga", e o municipio e' Brasilia);
 *  3. o municipio do HEXAGONO da unidade no payload ja' carregado (o `nome_municipio` do
 *     proprio M1), quando ele esta' la';
 *  4. nada -- e entao o mapa vai a' visao da UF (municipio vazio), que contem a unidade.
 *     Ficar na cidade anterior seria repetir o defeito: o cabecalho afirmando um municipio
 *     que nao e' o da unidade.
 */

/** UF + municipio do cabecalho do mapa. `municipio` vazio = visao da UF inteira. */
export interface Territorio {
  uf: string
  municipio: string
}

/** O que a resolucao le da unidade: as duas bases (rede e cadastro) trazem os dois. */
export interface UnidadeComTerritorio {
  uf?: string | null
  cidade?: string | null
}

/** Chave de comparacao de nome de municipio: sem acento, sem caixa, pontuacao vira espaco. */
export function normalizarNomeMunicipio(nome: string): string {
  return nome
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[-'’`´.,/()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** A UF da unidade, em caixa alta; sem UF no registro, a UF aberta. */
export function ufDaUnidade(unidade: UnidadeComTerritorio, ufAtual: string): string {
  const u = (unidade.uf ?? '').trim().toUpperCase()
  return u || ufAtual.trim().toUpperCase()
}

/** As grafias a tentar: a cidade como veio e, se terminar na sigla da UF, sem ela. */
function variantesDaCidade(cidade: string, uf: string): string[] {
  const variantes = [normalizarNomeMunicipio(cidade)]
  const sufixo = cidade.match(/^(.*?)(?:\s*[-–/,]\s*|\s*\(\s*)([A-Za-z]{2})\s*\)?\s*$/)
  if (sufixo && uf && sufixo[2].toUpperCase() === uf) variantes.push(normalizarNomeMunicipio(sufixo[1]))
  return variantes.filter(Boolean)
}

/**
 * O municipio da unidade, ESCRITO COMO A LISTA DA UF O ESCREVE (e' esse nome que o seletor
 * e a API usam). `null` = nao resolvido.
 *
 * `municipiosDaUf` TEM de ser a lista da UF da unidade -- quem chama garante (ver o
 * `MapScreen`). `munDoHexagono` so' quando o payload carregado e' da MESMA UF.
 */
export function municipioDaUnidade(
  unidade: UnidadeComTerritorio,
  municipiosDaUf: readonly { nome: string }[],
  munDoHexagono: string | null = null,
): string | null {
  const nomes = municipiosDaUf.map((m) => m.nome).filter((n) => n && n.trim())
  const porChave = new Map(nomes.map((n) => [normalizarNomeMunicipio(n), n] as const))
  const uf = (unidade.uf ?? '').trim().toUpperCase()

  const cidade = (unidade.cidade ?? '').trim()
  if (cidade) {
    for (const chave of variantesDaCidade(cidade, uf)) {
      const achado = porChave.get(chave)
      if (achado) return achado
    }
  }
  if (nomes.length === 1) return nomes[0]
  const mun = (munDoHexagono ?? '').trim()
  if (mun) {
    // Sem lista (a busca falhou), o nome do hexagono ja' e' o do M1 -- o mesmo dominio.
    if (nomes.length === 0) return mun
    const achado = porChave.get(normalizarNomeMunicipio(mun))
    if (achado) return achado
  }
  return null
}

/** O territorio que o cabecalho deve mostrar com a unidade aberta. */
export function territorioDaUnidade(
  unidade: UnidadeComTerritorio,
  ufAtual: string,
  municipiosDaUf: readonly { nome: string }[],
  munDoHexagono: string | null = null,
): Territorio {
  return {
    uf: ufDaUnidade(unidade, ufAtual),
    municipio: municipioDaUnidade(unidade, municipiosDaUf, munDoHexagono) ?? '',
  }
}

/**
 * O que o mapa precisa chamar para chegar ao territorio da unidade -- os MESMOS
 * `onUf`/`onMunicipio` do cabecalho, para o efeito ser o de o operador ter escolhido.
 *
 * Trocar a UF ja' zera o municipio (`aoTrocarUf` no App), entao com UF nova o municipio so'
 * e' pedido quando ha' um; na mesma UF, pede-se mesmo vazio (volta a' visao da UF).
 * `null` nos dois = nada muda (a unidade ja' esta' no territorio aberto).
 */
export function planoDeTroca(
  atual: Territorio,
  alvo: Territorio,
): { uf: string | null; municipio: string | null } {
  const ufAtual = atual.uf.trim().toUpperCase()
  if (alvo.uf && alvo.uf !== ufAtual) {
    return { uf: alvo.uf, municipio: alvo.municipio ? alvo.municipio : null }
  }
  if (alvo.municipio !== atual.municipio) return { uf: null, municipio: alvo.municipio }
  return { uf: null, municipio: null }
}
