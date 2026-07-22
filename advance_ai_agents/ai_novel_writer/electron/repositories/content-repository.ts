/**
 * ContentRepository — 文本内容池 (contents 表)
 *
 * 所有长文本（草稿正文、修稿内容、审稿报告）的统一存储池。
 * 元数据表（drafts/revisions/reviews）仅通过 content_id 外键引用。
 */
import { getProjectDb } from '../database'

export class ContentRepository {
    /** 创建一条内容记录，返回自增 ID */
    static create(body: string): number {
        const db = getProjectDb()
        if (!db) throw new Error('[ContentRepository] 数据库未连接')

        const result = db.prepare(`
      INSERT INTO contents (body) VALUES (?)
    `).run(body)

        return Number(result.lastInsertRowid)
    }

    /** 按 ID 读取正文 */
    static getBody(id: number): string | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(`
      SELECT body FROM contents WHERE id = ?
    `).get(id) as { body: string } | undefined

        return row?.body ?? null
    }

    /** 更新正文内容 */
    static updateBody(id: number, body: string): void {
        const db = getProjectDb()
        if (!db) return

        db.prepare(`
      UPDATE contents SET body = ? WHERE id = ?
    `).run(body, id)
    }

    /** 删除内容（仅在确认无外键引用时调用） */
    static delete(id: number): void {
        const db = getProjectDb()
        if (!db) return

        db.prepare('DELETE FROM contents WHERE id = ?').run(id)
    }
}
