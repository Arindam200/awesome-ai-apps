import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { resolveBuildTargets } from '../clean-build-output.mjs'

describe('release cleanup paths', () => {
  it('resolves only generated directories inside the repository', () => {
    const root = path.resolve('C:/workspace/ai-novel-writer')
    const targets = resolveBuildTargets(root, '0.2.0')

    expect(targets).toEqual([
      path.join(root, 'dist'),
      path.join(root, 'dist-electron'),
      path.join(root, 'release', '0.2.0'),
    ])
    for (const target of targets) {
      expect(target.startsWith(`${root}${path.sep}`)).toBe(true)
    }
  })

  it.each(['', '.', '..', '../outside', '0.2.0/../../outside'])('rejects unsafe version %j', (version) => {
    expect(() => resolveBuildTargets(path.resolve('C:/workspace/ai-novel-writer'), version)).toThrow()
  })
})
