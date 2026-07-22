import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function source(file: string) {
  return readFileSync(resolve(process.cwd(), file), 'utf8')
}

describe('Electron main window chrome contract', () => {
  it('uses the custom writer title bar instead of the native system title bar', () => {
    const main = source('electron/main.ts')

    expect(main).toMatch(/frame:\s*false/)
    expect(main).not.toMatch(/titleBarStyle:\s*'hiddenInset'/)
  })

  it('registers window control IPC for frameless minimize maximize and close buttons', () => {
    const ipcHandlers = source('electron/ipc-handlers.ts')
    const ipcChannels = source('src/shared/ipc-channels.ts')
    const titleBar = source('src/components/layout/TitleBar.tsx')

    expect(ipcHandlers).toContain('registerWindowController')
    for (const channel of ['window:minimize', 'window:toggle-maximize', 'window:close']) {
      expect(ipcChannels).toContain(`'${channel}'`)
      expect(titleBar).toContain(`'${channel}'`)
    }
    expect(titleBar).not.toContain('最小化窗口由系统标题栏控制')
  })
})
