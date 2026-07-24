import { beforeEach, describe, expect, it, vi } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { getCurrentProjectPath, getProjectDb } from '../../database'
import { BlueprintRepository } from '../blueprint-repository'
import { DraftRepository } from '../draft-repository'
import { ProjectClearRepository } from '../project-clear-repository'
import { ProjectCoreRepository } from '../project-core-repository'

vi.mock('../../database', () => ({
  getCurrentProjectPath: vi.fn(),
  getProjectDb: vi.fn(),
}))

function createMockDb() {
  const run = vi.fn()
  const prepare = vi.fn((sql: string) => ({ sql, run }))
  const transaction = vi.fn((fn: () => void) => () => fn())
  return { prepare, transaction, run }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('project clear repositories', () => {
  it('clears all blueprints in one call', () => {
    const db = createMockDb()
    vi.mocked(getProjectDb).mockReturnValue(db as never)

    BlueprintRepository.clearAll()

    expect(db.prepare).toHaveBeenCalledWith('DELETE FROM blueprints')
    expect(db.run).toHaveBeenCalledOnce()
  })

  it('clears generated drafts, review artifacts, summaries, and content in dependency order', () => {
    const db = createMockDb()
    vi.mocked(getProjectDb).mockReturnValue(db as never)

    DraftRepository.clearAll()

    const statements = db.prepare.mock.calls.map(([sql]) => sql)
    expect(statements).toEqual([
      'DELETE FROM post_process_steps',
      'DELETE FROM post_process_runs',
      'DELETE FROM reviews',
      'DELETE FROM revisions',
      'DELETE FROM drafts',
      'DELETE FROM contents',
      'DELETE FROM summary_snapshots',
    ])
    expect(db.run).toHaveBeenCalledTimes(7)
  })

  it('resets generated architecture fields without clearing project identity or sizing fields', () => {
    const db = createMockDb()
    vi.mocked(getProjectDb).mockReturnValue(db as never)

    ProjectCoreRepository.resetCreativeFields()

    const sql = db.prepare.mock.calls[0]?.[0]
    expect(sql).toContain('writing_style =')
    expect(sql).toContain('synopsis =')
    expect(sql).toContain('character_states =')
    expect(sql).not.toContain('project_name')
    expect(sql).not.toContain('genre')
    expect(sql).not.toContain('target_audience')
    expect(sql).not.toContain('total_chapters')
    expect(sql).not.toContain('words_per_chapter')
    expect(db.run).toHaveBeenCalledOnce()
  })

  it('clears selected generated project data in one database transaction', () => {
    const db = createMockDb()
    vi.mocked(getProjectDb).mockReturnValue(db as never)
    vi.mocked(getCurrentProjectPath).mockReturnValue(null)

    const result = ProjectClearRepository.clearGeneratedData({
      creativeFields: true,
      blueprints: true,
      generatedText: false,
    })

    expect(db.transaction).toHaveBeenCalledOnce()
    const statements = db.prepare.mock.calls.map(([sql]) => sql)
    expect(statements).toEqual([
      'DELETE FROM blueprints',
      expect.stringContaining('UPDATE project_core') as unknown as string,
    ])
    expect(result.cleared).toEqual(['blueprints', 'creativeFields'])
  })

  it('removes generated root chapter txt files when generated text is cleared', () => {
    const db = createMockDb()
    const projectPath = fs.mkdtempSync(path.join(os.tmpdir(), 'writer-clear-'))
    fs.mkdirSync(path.join(projectPath, '.vela'), { recursive: true })
    const generatedFile = path.join(projectPath, '第1章 夜航.txt')
    const generatedFileWithoutTitle = path.join(projectPath, '第2章.txt')
    const userFile = path.join(projectPath, '参考小说.txt')
    fs.writeFileSync(generatedFile, 'chapter one')
    fs.writeFileSync(generatedFileWithoutTitle, 'chapter two')
    fs.writeFileSync(userFile, 'reference')
    vi.mocked(getProjectDb).mockReturnValue(db as never)
    vi.mocked(getCurrentProjectPath).mockReturnValue(projectPath)

    try {
      const result = ProjectClearRepository.clearGeneratedData({ generatedText: true })

      expect(fs.existsSync(generatedFile)).toBe(false)
      expect(fs.existsSync(generatedFileWithoutTitle)).toBe(false)
      expect(fs.existsSync(userFile)).toBe(true)
      expect(fs.existsSync(path.join(projectPath, '.vela', 'trash'))).toBe(true)
      expect(result.physicalFilesDeleted).toBe(2)
    } finally {
      fs.rmSync(projectPath, { recursive: true, force: true })
    }
  })

  it('restores moved chapter txt files if database clear fails', () => {
    const run = vi.fn()
    const db = {
      prepare: vi.fn((sql: string) => ({ sql, run })),
      transaction: vi.fn(() => () => { throw new Error('db failed') }),
    }
    const projectPath = fs.mkdtempSync(path.join(os.tmpdir(), 'writer-clear-rollback-'))
    fs.mkdirSync(path.join(projectPath, '.vela'), { recursive: true })
    const generatedFile = path.join(projectPath, '第3章 回滚.txt')
    fs.writeFileSync(generatedFile, 'chapter three')
    vi.mocked(getProjectDb).mockReturnValue(db as never)
    vi.mocked(getCurrentProjectPath).mockReturnValue(projectPath)

    try {
      expect(() => ProjectClearRepository.clearGeneratedData({ generatedText: true })).toThrow('db failed')
      expect(fs.existsSync(generatedFile)).toBe(true)
    } finally {
      fs.rmSync(projectPath, { recursive: true, force: true })
    }
  })
})
