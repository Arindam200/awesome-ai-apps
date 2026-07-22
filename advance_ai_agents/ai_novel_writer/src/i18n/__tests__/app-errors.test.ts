import { describe, expect, it } from 'vitest'
import { appErrorMessage } from '../app-errors'

describe('localized application errors', () => {
  it('maps stable error codes to localized messages', () => {
    expect(appErrorMessage('en-US', { code: 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE' }))
      .toContain('Windows native component')
    expect(appErrorMessage('zh-CN', { code: 'PROJECT_NOT_OPEN' }))
      .toBe('请先打开项目。')
  })

  it('preserves an unknown error as localized diagnostic text', () => {
    expect(appErrorMessage('en-US', new Error('disk full'))).toBe('Something went wrong: disk full')
  })
})
