import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import {
  findLanceBinding,
  verifyPackagedLanceLoad,
  verifyWindowsPackage,
} from '../verify-win-package.mjs'

const fixtures: string[] = []

function fixture() {
  const root = mkdtempSync(path.join(tmpdir(), 'ai-novel-package-'))
  fixtures.push(root)
  return root
}

function write(root: string, relative: string) {
  const target = path.join(root, relative)
  mkdirSync(path.dirname(target), { recursive: true })
  writeFileSync(target, 'fixture')
}

afterEach(() => {
  for (const root of fixtures.splice(0)) rmSync(root, { recursive: true, force: true })
})

describe('Windows package verification', () => {
  it('rejects a package without the LanceDB native binding', () => {
    const root = fixture()
    write(root, 'resources/app.asar')
    write(root, 'AI小说作家.exe')

    expect(() => verifyWindowsPackage(root)).toThrow('Missing LanceDB Windows native binding')
  })

  it('finds and accepts the unpacked LanceDB binding', () => {
    const root = fixture()
    const relative = 'resources/app.asar.unpacked/node_modules/@lancedb/lancedb-win32-x64-msvc/lancedb.win32-x64-msvc.node'
    write(root, 'resources/app.asar')
    write(root, 'AI小说作家.exe')
    write(root, relative)

    expect(findLanceBinding(root)).toBe(path.join(root, relative))
    expect(verifyWindowsPackage(root)).toMatchObject({
      executable: path.join(root, 'AI小说作家.exe'),
      nativeBinding: path.join(root, relative),
    })
  })

  it('loads LanceDB with the packaged executable in Electron Node mode', () => {
    const root = fixture()
    write(root, 'resources/app.asar')
    write(root, 'AI小说作家.exe')
    const calls: Array<{ command: string; args: string[]; options: Record<string, unknown> }> = []
    const runner = (command: string, args: string[], options: Record<string, unknown>) => {
      calls.push({ command, args, options })
      return { status: 0, stdout: 'PACKAGED_LANCEDB_LOAD_OK', stderr: '' }
    }

    expect(verifyPackagedLanceLoad(root, runner)).toBe('PACKAGED_LANCEDB_LOAD_OK')
    expect(calls).toHaveLength(1)
    expect(calls[0].command).toBe(path.join(root, 'AI小说作家.exe'))
    expect(calls[0].args.join(' ')).toContain('@lancedb/lancedb')
    expect(calls[0].options).toMatchObject({
      cwd: root,
      env: expect.objectContaining({ ELECTRON_RUN_AS_NODE: '1' }),
    })
  })
})
