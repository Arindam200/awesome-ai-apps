import { describe, expect, it } from 'vitest'
import { extractFrontmatter } from '../frontmatter'

describe('extractFrontmatter', () => {
  it('parses LF frontmatter followed by body', () => {
    const content = '---\nstatus: draft\n---\n\n正文内容'
    const result = extractFrontmatter(content)
    expect(result.frontmatter).toBe('---\nstatus: draft\n---\n\n')
    expect(result.body).toBe('正文内容')
  })

  it('parses CRLF frontmatter followed by body', () => {
    const content = '---\r\nstatus: draft\r\n---\r\n\r\nbody'
    const result = extractFrontmatter(content)
    expect(result.frontmatter).toBe('---\r\nstatus: draft\r\n---\r\n\r\n')
    expect(result.body).toBe('body')
  })

  it('supports frontmatter-only content ending at EOF', () => {
    const content = '---\nstatus: draft\n---'
    const result = extractFrontmatter(content)
    expect(result.frontmatter).toBe('---\nstatus: draft\n---')
    expect(result.body).toBe('')
  })

  it('keeps indented YAML block with --- inside frontmatter', () => {
    const content = '---\nnote: |\n  line with ---\n  still yaml\n---\n\nbody'
    const result = extractFrontmatter(content)
    expect(result.frontmatter).toContain('line with ---')
    expect(result.body).toBe('body')
  })

  it('does not treat mid-line --- as a closing delimiter', () => {
    const content = '---\nvalue: a---b\n---\n\nbody'
    const result = extractFrontmatter(content)
    expect(result.frontmatter).toContain('a---b')
    expect(result.body).toBe('body')
  })
})
