/* Progresso dos downloads (11/11/2026): o Estudo pontual levava minutos numa conexão lenta e
   a pessoa recarregava a página achando que travou, cortando o download no meio. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { textoDoProgresso } from '../components/ProgressoDownload'
import { api, assinarProgressoDownload, type ProgressoDownload } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('textoDoProgresso', () => {
  it('antes do primeiro byte, o servidor ainda está gerando', () => {
    expect(textoDoProgresso({ recebidos: 0, total: null })).toContain('Gerando o arquivo')
  })

  it('com o tamanho, mostra a porcentagem e os MB', () => {
    const mb = 1024 * 1024
    expect(textoDoProgresso({ recebidos: 3 * mb, total: 6 * mb })).toBe(
      'Baixando o arquivo… 50% (3 de 6 MB).',
    )
  })

  it('sem o tamanho, mostra só o que já chegou', () => {
    expect(textoDoProgresso({ recebidos: 1024 * 1024, total: null })).toBe(
      'Baixando o arquivo… 1 MB recebidos.',
    )
  })
})

describe('pedirArquivo publica o progresso', () => {
  it('gerando -> partes recebidas -> fim, e o arquivo chega inteiro', async () => {
    const partes = [new Uint8Array([1, 2, 3]), new Uint8Array([4, 5])]
    const corpo = new ReadableStream<Uint8Array>({
      start(c) {
        for (const p of partes) c.enqueue(p)
        c.close()
      },
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(corpo, {
          status: 200,
          headers: {
            'Content-Length': '5',
            'Content-Type': 'application/pdf',
            'Content-Disposition': 'attachment; filename="estudo.pdf"',
          },
        }),
      ),
    )
    const vistos: Array<ProgressoDownload | null> = []
    const parar = assinarProgressoDownload((p) => vistos.push(p))
    try {
      const { blob, filename } = await api.mapaUnidadeConcorrenciaPdf('u1')
      expect(filename).toBe('estudo.pdf')
      expect(blob.size).toBe(5)
    } finally {
      parar()
    }
    expect(vistos[0]).toEqual({ recebidos: 0, total: null })
    expect(vistos).toContainEqual({ recebidos: 3, total: 5 })
    expect(vistos).toContainEqual({ recebidos: 5, total: 5 })
    expect(vistos.at(-1)).toBeNull()
  })
})
