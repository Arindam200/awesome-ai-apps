import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getProjectDb } from '../../database'
import { BlueprintRepository, type BlueprintData } from '../blueprint-repository'

vi.mock('../../database', () => ({
  getProjectDb: vi.fn(),
}))

const blueprint: BlueprintData = {
  chapterNumber: 1,
  title: '启程',
  role: '建置',
  purpose: '引出主角目标',
  keyEvents: '主角发现异常',
  characters: ['主角'],
  suspenseHook: '门外传来敲门声',
  userGuidance: '',
  notes: '',
  notesUpdatedAt: '',
}

beforeEach(() => {
  vi.mocked(getProjectDb).mockReturnValue(null)
})

describe('BlueprintRepository without an opened project DB', () => {
  it('throws for getAll', () => {
    expect(() => BlueprintRepository.getAll()).toThrow(/项目数据库未打开/)
  })

  it('throws for getByChapter', () => {
    expect(() => BlueprintRepository.getByChapter(1)).toThrow(/项目数据库未打开/)
  })

  it('throws for count', () => {
    expect(() => BlueprintRepository.count()).toThrow(/项目数据库未打开/)
  })

  it('throws for upsert', () => {
    expect(() => BlueprintRepository.upsert(blueprint)).toThrow(/项目数据库未打开/)
  })

  it('throws for upsertMany', () => {
    expect(() => BlueprintRepository.upsertMany([blueprint])).toThrow(/项目数据库未打开/)
  })
})
