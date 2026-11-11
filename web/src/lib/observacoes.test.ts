import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  apenasDigitos,
  camposDoFormulario,
  estrelas,
  chavesDosPinos,
  DIGITOS_MAXIMOS,
  formularioDe,
  iniciais,
  lerNumero,
  linhasDaObservacao,
  mediaDaNota,
  metragemMaisRecente,
  NOTA_MAXIMA,
  NUMERICOS,
  numeroDoRotulo,
  TEXTO_MAXIMO,
} from './observacoes'
import type { Observacao } from './types'

function obs(p: Partial<Observacao>): Observacao {
  return {
    id: 1,
    autor_rotulo: 'Pessoa 1',
    autor_nome: 'Diego Ramos',
    minha: false,
    metragem_m2: null,
    equipamentos: null,
    vagas: null,
    comodidades: null,
    nota_conservacao: null,
    nota_fachada: null,
    nota_atendimento: null,
    alunos_estimados: null,
    comentario: 'x',
    criada_em: '2026-10-21T10:00:00Z',
    atualizada_em: '2026-10-21T10:00:00Z',
    editada: false,
    versao: 1,
    pode_editar: false,
    pode_apagar: false,
    ...p,
  }
}

describe('formulário de anotação', () => {
  it('lê o número como o brasileiro escreve', () => {
    expect(lerNumero('1.500')).toBe(1500)
    expect(lerNumero('1500,5')).toBe(1500.5)
    expect(lerNumero('  ')).toBeNull()
    expect(Number.isNaN(lerNumero('muito') as number)).toBe(true)
  })

  it('aplica as regras dos CHECK da 023 antes de ir ao servidor', () => {
    const base = formularioDe(null)
    expect(camposDoFormulario(base)).toMatch(/Preencha ao menos um campo/)
    expect(camposDoFormulario({ ...base, metragem_m2: '40' })).toMatch(/Metragem fora da faixa/)
    expect(camposDoFormulario({ ...base, metragem_m2: '20.001' })).toMatch(/Metragem fora da faixa/)
    expect(camposDoFormulario({ ...base, vagas: '-1' })).toMatch(/Vagas/)
    expect(camposDoFormulario({ ...base, alunos_estimados: '0' })).toMatch(/Alunos estimados/)
  })

  it('manda todos os campos, com texto vazio como null', () => {
    const f = {
      ...formularioDe(null),
      metragem_m2: '1.450',
      vagas: '0',
      alunos_estimados: '2.400',
      nota_fachada: 4,
      comodidades: '  Spinning  ',
      comentario: '  ok  ',
    }
    expect(camposDoFormulario(f)).toEqual({
      metragem_m2: 1450,
      equipamentos: null,
      vagas: 0,
      comodidades: 'Spinning',
      nota_conservacao: null,
      nota_fachada: 4,
      nota_atendimento: null,
      alunos_estimados: 2400,
      comentario: 'ok',
    })
  })

  it('uma nota sozinha já é anotação', () => {
    expect(camposDoFormulario({ ...formularioDe(null), nota_atendimento: 3 })).toMatchObject({
      nota_atendimento: 3,
    })
  })

  it('edição parte da versão que a pessoa viu (concorrência otimista)', () => {
    const f = formularioDe(obs({ id: 7, versao: 3, metragem_m2: 1200, vagas: 20, nota_conservacao: 3 }))
    expect(f).toMatchObject({ id: 7, versao: 3, metragem_m2: '1200', vagas: '20', nota_conservacao: 3 })
  })
})

describe('resumo do painel', () => {
  it('a metragem do resumo é a da anotação mais recente que a informa', () => {
    const ativas = [
      obs({ id: 1, metragem_m2: 1200, atualizada_em: '2026-10-21T10:00:00Z' }),
      obs({ id: 2, metragem_m2: 1450, atualizada_em: '2026-10-30T11:05:00Z' }),
      obs({ id: 3, metragem_m2: null, atualizada_em: '2026-11-02T18:20:00Z' }),
    ]
    expect(metragemMaisRecente(ativas)?.id).toBe(2)
    expect(metragemMaisRecente([obs({})])).toBeNull()
  })

  it('a nota do resumo é a média de quem deu nota, com a contagem à vista', () => {
    const ativas = [obs({ nota_fachada: 4 }), obs({ nota_fachada: 5 }), obs({ nota_fachada: null })]
    expect(mediaDaNota(ativas, 'nota_fachada')).toEqual({ media: 4.5, n: 2 })
    expect(mediaDaNota(ativas, 'nota_atendimento')).toBeNull()
  })

  it('o cartão mostra cada campo preenchido, e zero vagas como "sem estacionamento"', () => {
    const linhas = linhasDaObservacao(
      obs({ vagas: 0, nota_conservacao: 4, nota_atendimento: 2, alunos_estimados: 2400, comentario: null }),
    )
    expect(linhas).toEqual([
      ['Vagas', 'Sem estacionamento', false],
      ['Alunos est.', '~2.400', false],
      ['Notas', 'Conservação ★★★★☆ · Atendimento ★★☆☆☆', false],
    ])
  })

  it('o número da pessoa vem do rótulo, para a cor do avatar ficar estável', () => {
    expect(numeroDoRotulo('Pessoa 3')).toBe(3)
    expect(numeroDoRotulo('???')).toBe(1)
  })

  it('o avatar mostra as iniciais de quem escreveu, para todos (emenda 1 da DEC-084)', () => {
    expect(iniciais('Diego Ramos')).toBe('DR')
    expect(iniciais('  carla   de souza mendes ')).toBe('CM')
    expect(iniciais('Ícaro')).toBe('Í')
    // Sem nome utilizável, volta vazio e o cartão usa o número da pessoa.
    expect(iniciais('(sem cadastro)')).toBe('SC')
    expect(iniciais('')).toBe('')
    expect(iniciais(undefined)).toBe('')
  })

  it('a contagem pede cada chave uma vez e ignora pino sem âncora', () => {
    expect(chavesDosPinos([{ chave: 'a' }, { chave: 'a' }, { chave: null }, {}, { chave: 'b' }])).toEqual([
      'a',
      'b',
    ])
  })
})

describe('número só aceita dígito (prévia de 10/11: dava para digitar letra)', () => {
  it('o filtro do input deixa só os dígitos', () => {
    expect(apenasDigitos('12a3')).toBe('123')
    expect(apenasDigitos('1.500')).toBe('1500')
    expect(apenasDigitos('abc')).toBe('')
    expect(apenasDigitos('')).toBe('')
  })

  it('número com letra diz que precisa ser número, não "fora da faixa"', () => {
    const base = formularioDe(null)
    expect(camposDoFormulario({ ...base, vagas: '12a' })).toBe(
      'Vagas de estacionamento precisa ser um número inteiro.',
    )
    expect(camposDoFormulario({ ...base, metragem_m2: '1500,5' })).toBe(
      'Metragem precisa ser um número inteiro.',
    )
  })

  it('metragem, vagas e alunos estimados passam pelo filtro ao digitar', () => {
    const fonte = readFileSync(new URL('../components/PainelObservacoes.tsx', import.meta.url), 'utf8')
    expect(fonte.match(/apenasDigitos\(e\.target\.value\)/g)?.length).toBe(3)
  })
})

describe('caixas com teto (pedido de 11/11: 5 dígitos nos números, 250 caracteres nos textos)', () => {
  const fonte = readFileSync(new URL('../components/PainelObservacoes.tsx', import.meta.url), 'utf8')

  it('os tetos são 5 dígitos e 250 caracteres', () => {
    expect(DIGITOS_MAXIMOS).toBe(5)
    expect(TEXTO_MAXIMO).toBe(250)
  })

  it('o teto de dígitos nunca barra um valor que a faixa aceita', () => {
    for (const [, , , max] of NUMERICOS) expect(String(max).length).toBeLessThanOrEqual(DIGITOS_MAXIMOS)
  })

  it('o filtro do número corta no 5º dígito, também ao colar', () => {
    expect(apenasDigitos('1234567')).toBe('12345')
    expect(apenasDigitos('1.234.567')).toBe('12345')
    expect(apenasDigitos('12345')).toBe('12345')
  })

  it('texto acima de 250 caracteres é recusado com a frase do servidor', () => {
    // A anotação antiga maior que 250 abre no formulário: o maxLength não corta o que já existe.
    const base = formularioDe(null)
    const longo = 'x'.repeat(251)
    expect(camposDoFormulario({ ...base, equipamentos: longo })).toBe(
      'O campo de equipamentos passa de 250 caracteres.',
    )
    expect(camposDoFormulario({ ...base, comodidades: longo })).toBe(
      'O campo de comodidades e aulas coletivas passa de 250 caracteres.',
    )
    expect(camposDoFormulario({ ...base, comentario: longo })).toBe('O comentário passa de 250 caracteres.')
  })

  it('250 caracteres passam, contados depois de tirar os espaços das pontas, como no servidor', () => {
    const base = formularioDe(null)
    expect(camposDoFormulario({ ...base, comentario: 'x'.repeat(250) })).toMatchObject({ comentario: 'x'.repeat(250) })
    expect(camposDoFormulario({ ...base, comentario: `  ${'x'.repeat(250)}  ` })).toMatchObject({
      comentario: 'x'.repeat(250),
    })
  })

  it('as caixas usam os tetos do lib, sem número solto', () => {
    expect(fonte.match(/maxLength=\{DIGITOS_MAXIMOS\}/g)?.length).toBe(3)
    expect(fonte.match(/maxLength=\{TEXTO_MAXIMO\}/g)?.length).toBe(3)
    expect(fonte).not.toMatch(/maxLength=\{\d/)
  })
})

describe('notas em estrelas de 1 a 5 (prévia de 10/11; eram notas de 1 a 10)', () => {
  it('a escala vai até 5', () => {
    expect(NOTA_MAXIMA).toBe(5)
  })

  it('estrelas cheias até a nota, vazias no resto; média arredonda para a estrela inteira', () => {
    expect(estrelas(3)).toBe('★★★☆☆')
    expect(estrelas(5)).toBe('★★★★★')
    expect(estrelas(1)).toBe('★☆☆☆☆')
    expect(estrelas(4.2)).toBe('★★★★☆')
    expect(estrelas(4.5)).toBe('★★★★★')
  })

  it('o painel não fala mais em nota de 1 a 10', () => {
    const fonte = readFileSync(new URL('../components/PainelObservacoes.tsx', import.meta.url), 'utf8')
    expect(fonte).not.toMatch(/1 a 10|\/10\b|length: 10/)
    expect(fonte).toMatch(/NOTA_MAXIMA/)
  })
})

describe('o painel não esconde o nome do autor por conta própria', () => {
  // A regra mora no SERVIDOR (web/server/observacoes.py): quem não é Growth nem recebe o nome.
  // Se o front passar a "esconder" com CSS ou condicional, é sinal de que o nome voltou ao JSON.
  const fonte = readFileSync(new URL('../components/PainelObservacoes.tsx', import.meta.url), 'utf8')

  it('não decide visibilidade por perfil no front', () => {
    expect(fonte).not.toMatch(/['"]growth['"]/)
    expect(fonte).not.toMatch(/display:\s*['"]?none/)
  })

  it('não usa diálogo do navegador para confirmar (trava o mapa)', () => {
    expect(fonte).not.toMatch(/window\.(confirm|alert|prompt)/)
  })
})
