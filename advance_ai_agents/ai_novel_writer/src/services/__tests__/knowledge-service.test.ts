import { describe, expect, it } from 'vitest'
import { KnowledgeBaseServiceError, unwrapKnowledgeValue } from '../knowledge-service'

describe('knowledge service native failure normalization', () => {
  it('returns successful knowledge values unchanged', () => {
    const value = [{ text: 'sample', score: 0.9, fileName: 'novel.txt' }]
    expect(unwrapKnowledgeValue(value)).toBe(value)
  })

  it('turns a native loader failure into a stable renderer error', () => {
    expect(() => unwrapKnowledgeValue({
      success: false,
      errorCode: 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE',
      error: 'Cannot find native binding',
    })).toThrowError(KnowledgeBaseServiceError)

    try {
      unwrapKnowledgeValue({ success: false, errorCode: 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE' })
    } catch (error) {
      expect(error).toMatchObject({ code: 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE' })
    }
  })
})
