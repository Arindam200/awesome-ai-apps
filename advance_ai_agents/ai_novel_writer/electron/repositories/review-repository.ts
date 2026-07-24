/**
 * ReviewRepository — 审稿 (reviews 表 + contents 联动)
 *
 * 审稿是对某版草稿的评审反馈报告。
 */
import { getProjectDb } from '../database'
import { ContentRepository } from './content-repository'

/** 审稿元数据 */
export interface ReviewMeta {
    id: number
    baseDraftId: number
    reviewIndex: number
    contentId: number
    createdAt: string
}

/** 审稿完整数据（含报告正文） */
export interface ReviewFull extends ReviewMeta {
    content: string
}

function rowToMeta(row: Record<string, unknown>): ReviewMeta {
    return {
        id: row.id as number,
        baseDraftId: row.base_draft_id as number,
        reviewIndex: row.review_index as number,
        contentId: row.content_id as number,
        createdAt: row.created_at as string,
    }
}

export class ReviewRepository {
    /** 创建审稿（事务：先入内容池再建元数据） */
    static create(params: {
        baseDraftId: number
        reviewIndex?: number
        content: string
    }): number {
        const db = getProjectDb()
        if (!db) throw new Error('[ReviewRepository] 数据库未连接')

        // 事务内原子分配 review_index，避免 getNextIndex + create 竞态
        const tx = db.transaction(() => {
            const row = db.prepare(`
        SELECT MAX(review_index) as maxIdx FROM reviews WHERE base_draft_id = ?
      `).get(params.baseDraftId) as { maxIdx: number | null }
            const reviewIndex = (row.maxIdx ?? 0) + 1

            const contentId = ContentRepository.create(params.content)
            const result = db.prepare(`
        INSERT INTO reviews (base_draft_id, review_index, content_id)
        VALUES (?, ?, ?)
      `).run(params.baseDraftId, reviewIndex, contentId)
            return Number(result.lastInsertRowid)
        })

        return tx()
    }

    /** 列出某草稿的所有审稿 */
    static listByDraft(baseDraftId: number): ReviewMeta[] {
        const db = getProjectDb()
        if (!db) return []

        const rows = db.prepare(`
      SELECT * FROM reviews
      WHERE base_draft_id = ?
      ORDER BY review_index ASC
    `).all(baseDraftId) as Record<string, unknown>[]

        return rows.map(rowToMeta)
    }

    /** 获取某草稿的最新审稿 */
    static getLatestByDraft(baseDraftId: number): ReviewFull | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(`
      SELECT * FROM reviews
      WHERE base_draft_id = ?
      ORDER BY review_index DESC LIMIT 1
    `).get(baseDraftId) as Record<string, unknown> | undefined

        if (!row) return null
        const meta = rowToMeta(row)
        const body = ContentRepository.getBody(meta.contentId)
        return { ...meta, content: body ?? '' }
    }

    /** 获取审稿完整数据 */
    static getFull(id: number): ReviewFull | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(
            'SELECT * FROM reviews WHERE id = ?'
        ).get(id) as Record<string, unknown> | undefined

        if (!row) return null
        const meta = rowToMeta(row)
        const body = ContentRepository.getBody(meta.contentId)
        return { ...meta, content: body ?? '' }
    }

    /** 获取下一个审稿序号 */
    static getNextIndex(baseDraftId: number): number {
        const db = getProjectDb()
        if (!db) return 1

        const row = db.prepare(`
      SELECT MAX(review_index) as maxIdx FROM reviews WHERE base_draft_id = ?
    `).get(baseDraftId) as { maxIdx: number | null }

        return (row.maxIdx ?? 0) + 1
    }
}
