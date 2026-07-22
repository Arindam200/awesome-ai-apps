/**
 * DraftRepository — 草稿 (drafts 表 + contents 联动)
 *
 * 草稿是创作栈的主线。status='finalized' 代表定稿。
 * 正文统一存储在 contents 表中，drafts 只持有 content_id 外键。
 */
import { getProjectDb } from '../database'
import { ContentRepository } from './content-repository'

/** 草稿元数据（不含正文，适合列表查询） */
export interface DraftMeta {
    id: number
    chapterNumber: number
    version: number
    status: string
    source: string
    contentId: number
    wordCount: number
    createdAt: string
    updatedAt: string
}

/** 草稿完整数据（含正文） */
export interface DraftFull extends DraftMeta {
    content: string
}

/** DB 行 → DraftMeta */
function rowToMeta(row: Record<string, unknown>): DraftMeta {
    return {
        id: row.id as number,
        chapterNumber: row.chapter_number as number,
        version: row.version as number,
        status: row.status as string,
        source: row.source as string,
        contentId: row.content_id as number,
        wordCount: row.word_count as number,
        createdAt: row.created_at as string,
        updatedAt: row.updated_at as string,
    }
}

export class DraftRepository {
    /**
     * 创建草稿（先写 contents 再建 draft 记录）
     * 返回新建的 draft ID
     */
    static create(params: {
        chapterNumber: number
        version?: number
        source: 'write' | 'rewrite'
        content: string
        wordCount: number
    }): number {
        const db = getProjectDb()
        if (!db) throw new Error('[DraftRepository] 数据库未连接')

        // 事务内原子分配 version，避免 getNextVersion + create 竞态
        const tx = db.transaction(() => {
            const row = db.prepare(`
        SELECT MAX(version) as maxVer FROM drafts WHERE chapter_number = ?
      `).get(params.chapterNumber) as { maxVer: number | null }
            const version = (row.maxVer ?? 0) + 1

            const contentId = ContentRepository.create(params.content)
            const result = db.prepare(`
        INSERT INTO drafts (chapter_number, version, source, content_id, word_count)
        VALUES (?, ?, ?, ?, ?)
      `).run(
                params.chapterNumber,
                version,
                params.source,
                contentId,
                params.wordCount,
            )
            return Number(result.lastInsertRowid)
        })

        return tx()
    }

    /** 列出章节的所有草稿（不含正文，按版本升序） */
    static listByChapter(chapterNumber: number): DraftMeta[] {
        const db = getProjectDb()
        if (!db) return []

        const rows = db.prepare(`
      SELECT * FROM drafts WHERE chapter_number = ? ORDER BY version ASC
    `).all(chapterNumber) as Record<string, unknown>[]

        return rows.map(rowToMeta)
    }

    /** 获取草稿元数据 */
    static getMeta(id: number): DraftMeta | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(
            'SELECT * FROM drafts WHERE id = ?'
        ).get(id) as Record<string, unknown> | undefined

        return row ? rowToMeta(row) : null
    }

    /** 获取草稿完整数据（含正文） */
    static getFull(id: number): DraftFull | null {
        const meta = DraftRepository.getMeta(id)
        if (!meta) return null

        const body = ContentRepository.getBody(meta.contentId)
        return { ...meta, content: body ?? '' }
    }

    /** 获取章节最新版本的草稿 */
    static getLatestByChapter(chapterNumber: number): DraftMeta | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(`
      SELECT * FROM drafts
      WHERE chapter_number = ?
      ORDER BY version DESC LIMIT 1
    `).get(chapterNumber) as Record<string, unknown> | undefined

        return row ? rowToMeta(row) : null
    }

    /** 获取章节已定稿的草稿 */
    static getFinalizedByChapter(chapterNumber: number): DraftMeta | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(`
      SELECT * FROM drafts
      WHERE chapter_number = ? AND status = 'finalized'
      ORDER BY version DESC LIMIT 1
    `).get(chapterNumber) as Record<string, unknown> | undefined

        return row ? rowToMeta(row) : null
    }

    /** 获取下一个可用版本号 */
    static getNextVersion(chapterNumber: number): number {
        const db = getProjectDb()
        if (!db) return 1

        const row = db.prepare(`
      SELECT MAX(version) as maxVer FROM drafts WHERE chapter_number = ?
    `).get(chapterNumber) as { maxVer: number | null }

        return (row.maxVer ?? 0) + 1
    }

    /** 获取最大的已定稿章节号，如果没有则返回 0 */
    static getMaxFinalizedChapter(): number {
        const db = getProjectDb()
        if (!db) return 0
        const row = db.prepare(`
            SELECT MAX(chapter_number) as maxChapter
            FROM drafts
            WHERE status = 'finalized'
        `).get() as { maxChapter: number | null }
        return row?.maxChapter ?? 0
    }

    /** 更新草稿状态 */
    static updateStatus(id: number, status: string, wordCount?: number): void {
        const db = getProjectDb()
        if (!db) return

        if (wordCount !== undefined) {
            db.prepare(`
        UPDATE drafts SET status = ?, word_count = ?, updated_at = datetime('now')
        WHERE id = ?
      `).run(status, wordCount, id)
        } else {
            db.prepare(`
        UPDATE drafts SET status = ?, updated_at = datetime('now')
        WHERE id = ?
      `).run(status, id)
        }
    }

    /** 更新草稿正文（同时更新 contents 表） */
    static updateContent(id: number, content: string, wordCount: number): void {
        const meta = DraftRepository.getMeta(id)
        if (!meta) return

        ContentRepository.updateBody(meta.contentId, content)

        const db = getProjectDb()
        if (!db) return

        db.prepare(`
      UPDATE drafts SET word_count = ?, updated_at = datetime('now')
      WHERE id = ?
    `).run(wordCount, id)
    }

    /** 删除草稿（级联删除 revisions/reviews，但 contents 需手动清理） */
    static delete(id: number): void {
        const db = getProjectDb()
        if (!db) return

        // 先获取 contentId 以便清理
        const meta = DraftRepository.getMeta(id)
        db.prepare('DELETE FROM drafts WHERE id = ?').run(id)

        // 清理孤立的 content 记录
        if (meta) {
            // 【DB 迁移备注】：如果 contents。id 仍被 revision 或 review 引用，
            // SQLite外键约束会阻止删除（抛出异常）。捕获并吞掉异常是预期的，
            // 这会导致少量不再被草稿引用的内容记录残留，但长期风险极低。
            try { ContentRepository.delete(meta.contentId) } catch { /* 被外键保护 */ }
        }
    }

    /** 清空所有生成正文与派生产物，不删除角色卡或项目配置 */
    static clearAll(): void {
        const db = getProjectDb()
        if (!db) throw new Error('[DraftRepository] 数据库未连接')

        const tx = db.transaction(() => {
            db.prepare('DELETE FROM post_process_steps').run()
            db.prepare('DELETE FROM post_process_runs').run()
            db.prepare('DELETE FROM reviews').run()
            db.prepare('DELETE FROM revisions').run()
            db.prepare('DELETE FROM drafts').run()
            db.prepare('DELETE FROM contents').run()
            db.prepare('DELETE FROM summary_snapshots').run()
        })

        tx()
    }
}
