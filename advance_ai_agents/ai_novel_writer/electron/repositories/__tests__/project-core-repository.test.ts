import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getProjectDb } from '../../database'
import { ProjectCoreRepository } from '../project-core-repository'

vi.mock('../../database', () => ({
  getProjectDb: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(getProjectDb).mockReturnValue(null)
})

describe('ProjectCoreRepository without an opened project DB', () => {
  it('throws when updating project core data', () => {
    expect(() => ProjectCoreRepository.update({ writingStyle: '冷峻紧凑' })).toThrow(/项目数据库未打开/)
  })
})
