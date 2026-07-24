import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import type { GlobalConfig } from '../../src/shared/ipc-channels'

const configUtils = vi.hoisted(() => ({
  readJsonFile: vi.fn(),
}))

vi.mock('../utils/config-utils', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../utils/config-utils')>()
  return { ...actual, readJsonFile: configUtils.readJsonFile }
})

import { mainText, resolveStoredOrSystemLocale } from '../i18n'
import { DEFAULT_GLOBAL_CONFIG } from '../utils/config-utils'

describe('main-process locale selection', () => {
  beforeEach(() => {
    configUtils.readJsonFile.mockImplementation(
      (_filePath: string, defaultConfig: GlobalConfig) => defaultConfig,
    )
  })

  afterEach(() => {
    configUtils.readJsonFile.mockReset()
  })

  it('uses a stored locale when present', () => {
    expect(resolveStoredOrSystemLocale('en-US', 'zh-CN')).toBe('en-US')
  })

  it('maps Chinese system locales to Simplified Chinese', () => {
    expect(resolveStoredOrSystemLocale(undefined, 'zh-HK')).toBe('zh-CN')
  })

  it('defaults other system locales to English', () => {
    expect(resolveStoredOrSystemLocale(undefined, 'de-DE')).toBe('en-US')
  })

  it('localizes colocated main-process dialog copy from the system locale when no preference is stored', () => {
    expect(mainText('zh-CN', '选择文件', 'Choose files')).toBe('选择文件')
    expect(mainText('en-US', '选择文件', 'Choose files')).toBe('Choose files')
  })

  it('keeps a stored locale ahead of the system locale for dialog copy', () => {
    configUtils.readJsonFile.mockReturnValue({ ...DEFAULT_GLOBAL_CONFIG, locale: 'zh-CN' })

    expect(mainText('en-US', '选择文件', 'Choose files')).toBe('选择文件')
  })

  it('initializes the renderer locale and localizes the window title', () => {
    const main = readFileSync('electron/main.ts', 'utf8')
    const app = readFileSync('src/App.tsx', 'utf8')

    expect(main).toContain("mainT(app.getLocale(), 'app.windowTitle')")
    expect(app).toContain('initLocale()')
  })
})
