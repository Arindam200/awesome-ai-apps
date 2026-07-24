import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const agentPanelFiles = [
  'src/components/panels/agent/AgentHeader.tsx',
  'src/components/panels/agent/AgentConversation.tsx',
]

describe('agent panel icon hygiene', () => {
  it('uses the shared icon library instead of inline SVG paths', () => {
    for (const file of agentPanelFiles) {
      const source = readFileSync(resolve(process.cwd(), file), 'utf8')

      expect(source, file).not.toMatch(/<svg\b/)
      expect(source, file).not.toMatch(/<path\b/)
    }
  })
})
