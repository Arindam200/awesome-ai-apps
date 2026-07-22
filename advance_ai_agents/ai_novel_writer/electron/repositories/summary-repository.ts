import { getProjectDb } from '../database'

export class SummaryRepository {
  /** 保存角色状态快照 */
  static saveSnapshot(chapterNumber: number, characterStates: string): void {
    const db = getProjectDb()
    if (!db) return
    db.prepare(`
      INSERT INTO summary_snapshots (chapter_number, character_states)
      VALUES (?, ?)
    `).run(chapterNumber, characterStates)
  }

  /** 获取最新角色状态快照 */
  static getLatestSnapshot(): { characterStates: string; chapterNumber: number } | null {
    const db = getProjectDb()
    if (!db) return null
    const row = db.prepare(
      'SELECT character_states as characterStates, chapter_number as chapterNumber FROM summary_snapshots ORDER BY id DESC LIMIT 1'
    ).get() as { characterStates: string; chapterNumber: number } | undefined
    return row ?? null
  }
}
