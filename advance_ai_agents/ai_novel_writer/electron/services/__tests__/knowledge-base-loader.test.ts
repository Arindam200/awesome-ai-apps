import { describe, expect, it, vi } from 'vitest'
import {
  createKnowledgeBaseLoader,
  KnowledgeBaseUnavailableError,
  type KnowledgeBaseModule,
} from '../knowledge-base-loader'

describe('knowledge-base loader', () => {
  it('loads once and reuses the resolved module', async () => {
    const module = { searchKnowledgeFTS: vi.fn() } as unknown as KnowledgeBaseModule
    const importer = vi.fn().mockResolvedValue(module)
    const loader = createKnowledgeBaseLoader(importer)

    expect(await loader.load()).toBe(module)
    expect(await loader.load()).toBe(module)
    expect(importer).toHaveBeenCalledTimes(1)
  })

  it('normalizes and caches native binding failures', async () => {
    const importer = vi.fn().mockRejectedValue(new Error('Cannot find native binding'))
    const loader = createKnowledgeBaseLoader(importer)

    await expect(loader.load()).rejects.toMatchObject({
      code: 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE',
    })
    await expect(loader.load()).rejects.toBeInstanceOf(KnowledgeBaseUnavailableError)
    expect(importer).toHaveBeenCalledTimes(1)
  })

  it('returns a structured unavailable result when an operation cannot load', async () => {
    const loader = createKnowledgeBaseLoader(async () => {
      throw new Error('Cannot find native binding')
    })

    await expect(loader.run(() => 'unreachable')).resolves.toEqual({
      success: false,
      errorCode: 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE',
    })
  })
})
