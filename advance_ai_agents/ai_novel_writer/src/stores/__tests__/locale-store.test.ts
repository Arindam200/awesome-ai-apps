import { createStore } from 'zustand/vanilla'
import { describe, expect, it, vi } from 'vitest'
import { createLocaleState } from '../locale-store'

describe('locale store', () => {
  it('prefers a saved locale over the operating-system locale', async () => {
    const state = createStore(createLocaleState({
      loadConfig: async () => ({ locale: 'zh-CN' }),
      saveLocale: vi.fn(),
      systemLocale: () => 'en-US',
      setDocumentLanguage: vi.fn(),
    }))

    await state.getState().init()

    expect(state.getState()).toMatchObject({ locale: 'zh-CN', initialized: true })
  })

  it('uses the operating-system locale without persisting it on first launch', async () => {
    const saveLocale = vi.fn()
    const state = createStore(createLocaleState({
      loadConfig: async () => ({}),
      saveLocale,
      systemLocale: () => 'zh-TW',
      setDocumentLanguage: vi.fn(),
    }))

    await state.getState().init()

    expect(state.getState().locale).toBe('zh-CN')
    expect(saveLocale).not.toHaveBeenCalled()
  })

  it('persists a manual choice and updates the document language', async () => {
    const saveLocale = vi.fn().mockResolvedValue(undefined)
    const setDocumentLanguage = vi.fn()
    const state = createStore(createLocaleState({
      loadConfig: async () => ({}),
      saveLocale,
      systemLocale: () => 'zh-CN',
      setDocumentLanguage,
    }))

    await state.getState().setLocale('en-US')

    expect(saveLocale).toHaveBeenCalledWith('en-US')
    expect(setDocumentLanguage).toHaveBeenCalledWith('en-US')
    expect(state.getState().locale).toBe('en-US')
  })

  it('localizes colocated component copy with the active locale', async () => {
    const state = createStore(createLocaleState({
      loadConfig: async () => ({}),
      saveLocale: vi.fn(),
      systemLocale: () => 'en-US',
      setDocumentLanguage: vi.fn(),
    }))

    expect(state.getState().text('中文', 'English')).toBe('English')
    await state.getState().setLocale('zh-CN')
    expect(state.getState().text('中文', 'English')).toBe('中文')
  })
})
