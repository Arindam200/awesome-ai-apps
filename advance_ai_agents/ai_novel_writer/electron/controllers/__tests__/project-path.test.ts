import path from 'node:path'
import { describe, expect, it } from 'vitest'

import { resolveProjectDir } from '../project-path'

describe('resolveProjectDir', () => {
  it('does not append a Windows absolute path as a child project name', () => {
    const projectDir = resolveProjectDir('C:\\SoftWare\\FUN\\Taven', 'C:\\Users\\EthanQ\\OneDrive\\Desktop\\蓝天航空公司的空姐')

    expect(projectDir).toBe(path.join('C:\\SoftWare\\FUN\\Taven', '蓝天航空公司的空姐'))
  })
})
