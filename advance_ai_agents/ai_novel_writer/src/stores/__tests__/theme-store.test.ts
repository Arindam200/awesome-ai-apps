import { beforeEach, describe, expect, it, vi } from 'vitest'

class MemoryStorage {
  private data = new Map<string, string>()

  getItem(key: string) {
    return this.data.get(key) ?? null
  }

  setItem(key: string, value: string) {
    this.data.set(key, value)
  }

  removeItem(key: string) {
    this.data.delete(key)
  }

  clear() {
    this.data.clear()
  }
}

function installDomStubs() {
  const classNames = new Set<string>()
  const styles = new Map<string, string>()

  Object.defineProperty(globalThis, 'localStorage', {
    value: new MemoryStorage(),
    configurable: true,
  })

  Object.defineProperty(globalThis, 'window', {
    value: {
      matchMedia: () => ({ matches: false }),
    },
    configurable: true,
  })

  Object.defineProperty(globalThis, 'document', {
    value: {
      documentElement: {
        classList: {
          add: (name: string) => classNames.add(name),
          remove: (...names: string[]) => names.forEach(name => classNames.delete(name)),
          contains: (name: string) => classNames.has(name),
        },
        style: {
          setProperty: (name: string, value: string) => styles.set(name, value),
        },
      },
    },
    configurable: true,
  })
}

describe('theme store branding defaults', () => {
  beforeEach(() => {
    vi.resetModules()
    installDomStubs()
  })

  it('defaults to the accepted warm paper theme', async () => {
    const { useThemeStore } = await import('../theme-store')

    expect(useThemeStore.getState().theme).toBe('paper')
    expect(useThemeStore.getState().resolvedTheme).toBe('paper')
  })

  it('persists theme state under the AI novel writer storage key', async () => {
    const { useThemeStore } = await import('../theme-store')

    useThemeStore.getState().setTheme('dark')

    expect(localStorage.getItem('ai-novel-writer-theme')).toContain('"dark"')
    expect(localStorage.getItem('ve' + 'la-theme')).toBeNull()
  })
})
