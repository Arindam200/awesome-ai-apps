import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const pkg = JSON.parse(readFileSync('package.json', 'utf8')) as {
  packageManager?: string
  optionalDependencies?: Record<string, string>
  scripts?: Record<string, string>
}

describe('release dependency contract', () => {
  it('uses one pinned package manager and exposes the Windows LanceDB binding', () => {
    expect(pkg.packageManager).toBe('pnpm@11.11.0')
    expect(pkg.optionalDependencies?.['@lancedb/lancedb-win32-x64-msvc']).toBe('0.27.2')
    expect(existsSync('package-lock.json')).toBe(false)
  })

  it('runs clean, native verification, and executable smoke gates for Windows builds', () => {
    expect(pkg.scripts?.['build:win-dir']).toContain('pnpm run clean:build')
    expect(pkg.scripts?.['build:win-dir']).toContain('pnpm run verify:win-package')
    expect(pkg.scripts?.['verify:win-package']).toBe('node scripts/verify-win-package.mjs')
    expect(pkg.scripts?.['smoke:win-app']).toContain('scripts/smoke-win-app.ps1')

    const builder = readFileSync('electron-builder.json5', 'utf8')
    expect(builder).toContain('node_modules/@lancedb/lancedb/**/*')
    expect(builder).toContain('node_modules/@lancedb/lancedb-win32-x64-msvc/**/*')
  })
})
