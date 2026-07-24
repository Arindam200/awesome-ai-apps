import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('README language variants', () => {
  it('keeps Chinese README as the repository default with a Chinese hero', () => {
    const readme = readFileSync('README.md', 'utf8')
    expect(readme).toContain('hero-zh-v2.png')
    expect(readme).toMatch(/\[English README\]\(README_en\.md\)\s*\|\s*\*\*中文\*\*/)
  })

  it('uses an independent English hero for the English README', () => {
    const readme = readFileSync('README_en.md', 'utf8')
    expect(readme).toContain('hero-en-v2.png')
    expect(readme).not.toContain('hero-zh-v2.png')
    expect(readme).toMatch(/\*\*English\*\*\s*\|\s*\[中文 README\]\(README\.md\)/)
  })
})
