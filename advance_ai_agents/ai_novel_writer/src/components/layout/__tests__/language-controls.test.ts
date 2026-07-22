import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('language controls', () => {
  it('provides a Lucide quick toggle in the title bar', () => {
    const source = readFileSync('src/components/layout/TitleBar.tsx', 'utf8')

    expect(source).toMatch(/import[\s\S]*Languages[\s\S]*from 'lucide-react'/)
    expect(source).toContain('toggleLocale')
    expect(source).toContain("t('language.switch')")
  })

  it('provides explicit locale choices in settings', () => {
    const source = readFileSync('src/components/settings/SettingsModal.tsx', 'utf8')

    expect(source).toContain('setLocale')
    expect(source).toContain('<option value="zh-CN">')
    expect(source).toContain('<option value="en-US">')
  })
})
