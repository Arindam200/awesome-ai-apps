import { describe, expect, it } from 'vitest'
import { tokens } from '../index'

describe('paper theme writer-studio tokens', () => {
  it('uses the accepted warm paper palette', () => {
    expect(tokens.paper.color.bg).toBe('#F8F1E7')
    expect(tokens.paper.color.editorBg).toBe('#FFF9EF')
    expect(tokens.paper.color.sidebar).toBe('#EEE2D0')
    expect(tokens.paper.color.activityBar).toBe('#DDC8AA')
    expect(tokens.paper.color.accent).toBe('#7A5732')
    expect(tokens.paper.color.gold).toBe('#B68A4A')
    expect(tokens.paper.color.success).toBe('#5D8A67')
    expect(tokens.paper.color.warning).toBe('#C68A3A')
    expect(tokens.paper.color.accent).not.toBe('#9B8EC8')
  })
})
