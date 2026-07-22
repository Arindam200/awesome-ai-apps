import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('README language variants', () => {
  it('keeps Chinese README as the repository default with a Chinese hero', () => {
    const readme = readFileSync('README.md', 'utf8')
    expect(readme).toContain('hero-zh-v2.png')
    expect(readme).toContain('[English README](README_en.md)')
    expect(readme).toContain('## v0.2.0 更新')
  })

  it('uses an independent English hero for the English README', () => {
    const readme = readFileSync('README_en.md', 'utf8')
    expect(readme).toContain('hero-en-v2.png')
    expect(readme).not.toContain('hero-zh-v2.png')
    expect(readme).toContain('[中文 README](README.md)')
  })
})
