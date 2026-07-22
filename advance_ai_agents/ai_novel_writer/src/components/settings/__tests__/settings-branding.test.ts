import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const checkedSources = [
  'src/components/settings/SettingsModal.tsx',
  'electron/main.ts',
  'package.json',
  'pnpm-lock.yaml',
  'electron-builder.json5',
  'README.md',
]

const visibleBrandingSource = checkedSources
  .map((file) => readFileSync(resolve(process.cwd(), file), 'utf8'))
  .join('\n')

const forbiddenVisibleLegacy = [
  '"name": "vela"',
  '"productName": "Vela"',
  '"appId": "com.vela.ide"',
  'Vela IDE',
  'heider',
  'heider-x',
  '/buyme/',
  'public/buyme',
  'wepay',
  'alipay',
  'wechat.jpg',
  'group.png',
  '微信打赏',
  '支付宝打赏',
  '扫码赞助',
  '赞助与支持',
  'Donate QR',
  '商业合作与技术交流',
  'Crafted with',
  'Vela —',
]

const pseudoIconPattern = new RegExp([
  '[\\u2600-\\u27BF]',
  '[\\u{1F300}-\\u{1FAFF}]',
  '\\uFE0F',
].join('|'), 'u')

describe('settings visible branding', () => {
  it('does not expose legacy support, payment QR, or pseudo-icon branding', () => {
    for (const value of forbiddenVisibleLegacy) {
      expect(visibleBrandingSource).not.toContain(value)
    }

    expect(visibleBrandingSource).not.toMatch(pseudoIconPattern)
    expect(visibleBrandingSource).not.toMatch(/<svg\b|<path\b/)
  })

  it('does not keep legacy support image assets in the repository', () => {
    const buymeDir = resolve(process.cwd(), 'public/buyme')
    const legacyAssets = [
      'public/buyme/alipay.jpg',
      'public/buyme/group.png',
      'public/buyme/wechat.jpg',
      'public/buyme/wepay.jpg',
    ]

    expect(existsSync(buymeDir)).toBe(false)
    for (const asset of legacyAssets) {
      expect(existsSync(resolve(process.cwd(), asset)), asset).toBe(false)
    }
  })
})
