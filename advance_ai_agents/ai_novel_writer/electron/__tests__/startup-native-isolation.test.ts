import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function source(file: string) {
  return readFileSync(resolve(process.cwd(), file), 'utf8')
}

describe('Electron startup native dependency isolation', () => {
  it('does not statically load the knowledge-base module while registering IPC', () => {
    const controller = source('electron/controllers/kb-controller.ts')

    expect(controller).not.toMatch(/from\s+['"]\.\.\/knowledge-base['"]/)
    expect(controller).toContain('knowledgeBaseLoader')
  })
})
