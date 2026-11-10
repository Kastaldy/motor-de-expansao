import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  camposDoFormulario,
  chavesDosPinos,
  formularioDe,
  lerNumero,
  linhasDaObservacao,
  mediaDaNota,
  metragemMaisRecente,
  numeroDoRotulo,
} from './observacoes'
import type { Observacao } from './types'

function obs(p: Partial<Observacao>): Observacao {
  return {
    id: 1,
    autor_rotulo: 'Pessoa 1',
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

  it('aplica as regras dos CHECK da 022 antes de ir ao servidor', () => {
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
      nota_fachada: 8,
      comodidades: '  Spinning  ',
      comentario: '  ok  ',
    }
    expect(camposDoFormulario(f)).toEqual({
      metragem_m2: 1450,
      equipamentos: null,
      vagas: 0,
      comodidades: 'Spinning',
      nota_conservacao: null,
      nota_fachada: 8,
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
    const f = formularioDe(obs({ id: 7, versao: 3, metragem_m2: 1200, vagas: 20, nota_conservacao: 6 }))
    expect(f).toMatchObject({ id: 7, versao: 3, metragem_m2: '1200', vagas: '20', nota_conservacao: 6 })
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
    const ativas = [obs({ nota_fachada: 8 }), obs({ nota_fachada: 5 }), obs({ nota_fachada: null })]
    expect(mediaDaNota(ativas, 'nota_fachada')).toEqual({ media: 6.5, n: 2 })
    expect(mediaDaNota(ativas, 'nota_atendimento')).toBeNull()
  })

  it('o cartão mostra cada campo preenchido, e zero vagas como "sem estacionamento"', () => {
    const linhas = linhasDaObservacao(
      obs({ vagas: 0, nota_conservacao: 7, nota_atendimento: 9, alunos_estimados: 2400, comentario: null }),
    )
    expect(linhas).toEqual([
      ['Vagas', 'Sem estacionamento', false],
      ['Alunos est.', '~2.400', false],
      ['Notas', 'Conservação 7/10 · Atendimento 9/10', false],
    ])
  })

  it('o número da pessoa vem do rótulo, para a cor do avatar ficar estável', () => {
    expect(numeroDoRotulo('Pessoa 3')).toBe(3)
    expect(numeroDoRotulo('???')).toBe(1)
  })

  it('a contagem pede cada chave uma vez e ignora pino sem âncora', () => {
    expect(chavesDosPinos([{ chave: 'a' }, { chave: 'a' }, { chave: null }, {}, { chave: 'b' }])).toEqual([
      'a',
      'b',
    ])
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
