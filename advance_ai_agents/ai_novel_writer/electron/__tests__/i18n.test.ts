import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { mainText, resolveStoredOrSystemLocale } from '../i18n'

describe('main-process locale selection', () => {
  it('uses a stored locale when present', () => {
    expect(resolveStoredOrSystemLocale('en-US', 'zh-CN')).toBe('en-US')
  })

  it('maps Chinese system locales to Simplified Chinese', () => {
    expect(resolveStoredOrSystemLocale(undefined, 'zh-HK')).toBe('zh-CN')
  })

  it('defaults other system locales to English', () => {
    expect(resolveStoredOrSystemLocale(undefined, 'de-DE')).toBe('en-US')
  })

  it('localizes colocated main-process dialog copy', () => {
    expect(mainText('zh-CN', '选择文件', 'Choose files')).toBe('选择文件')
    expect(mainText('en-US', '选择文件', 'Choose files')).toBe('Choose files')
  })

  it('initializes the renderer locale and localizes the window title', () => {
    const main = readFileSync('electron/main.ts', 'utf8')
    const app = readFileSync('src/App.tsx', 'utf8')

    expect(main).toContain("mainT(app.getLocale(), 'app.windowTitle')")
    expect(app).toContain('initLocale()')
  })
})
