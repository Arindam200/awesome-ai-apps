/**
 * RevisionRepository — 修稿 (revisions 表 + contents 联动)
 *
 * 修稿是基于某一版草稿的探索分支。
 * 状态流转：pending → merged / discarded
 */
import { getProjectDb } from '../database'
import { ContentRepository } from './content-repository'

/** 修稿元数据（不含正文） */
export interface RevisionMeta {
    id: number
    baseDraftId: number
    revisionIndex: number
    revisionType: string
    status: string
    mergedToDraftId: number | null
    userPrompt: string
    reviewSourceId: number | null
    contentId: number
    wordCount: number
    createdAt: string
    updatedAt: string
}

/** 修稿完整数据（含正文） */
export interface RevisionFull extends RevisionMeta {
    content: string
}

function rowToMeta(row: Record<string, unknown>): RevisionMeta {
    return {
        id: row.id as number,
        baseDraftId: row.base_draft_id as number,
        revisionIndex: row.revision_index as number,
        revisionType: row.revision_type as string,
        status: row.status as string,
        mergedToDraftId: (row.merged_to_draft_id as number | null) ?? null,
        userPrompt: (row.user_prompt as string) ?? '',
        reviewSourceId: (row.review_source_id as number | null) ?? null,
        contentId: row.content_id as number,
        wordCount: row.word_count as number,
        createdAt: row.created_at as string,
        updatedAt: row.updated_at as string,
    }
}

export class RevisionRepository {
    /**
     * 创建修稿（事务内原子分配 revision_index，再入内容池 + 元数据）
     * 不接受调用方传入序号，避免与落库结果不一致。
     */
    static create(params: {
        baseDraftId: number
        revisionType: 'refine' | 'review-fix'
        userPrompt?: string
        reviewSourceId?: number
        content: string
        wordCount: number
    }): { id: number; revisionIndex: number } {
        const db = getProjectDb()
        if (!db) throw new Error('[RevisionRepository] 数据库未连接')

        const tx = db.transaction(() => {
            const row = db.prepare(`
        SELECT MAX(revision_index) as maxIdx FROM revisions WHERE base_draft_id = ?
      `).get(params.baseDraftId) as { maxIdx: number | null }
            const revisionIndex = (row.maxIdx ?? 0) + 1

            const contentId = ContentRepository.create(params.content)
            const result = db.prepare(`
        INSERT INTO revisions (
          base_draft_id, revision_index, revision_type,
          user_prompt, review_source_id, content_id, word_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `).run(
                params.baseDraftId,
                revisionIndex,
                params.revisionType,
                params.userPrompt ?? '',
                params.reviewSourceId ?? null,
                contentId,
                params.wordCount,
            )
            return { id: Number(result.lastInsertRowid), revisionIndex }
        })

        return tx()
    }

    /** 列出某草稿的所有修稿 */
    static listByDraft(baseDraftId: number): RevisionMeta[] {
        const db = getProjectDb()
        if (!db) return []

        const rows = db.prepare(`
      SELECT * FROM revisions
      WHERE base_draft_id = ?
      ORDER BY revision_index ASC
    `).all(baseDraftId) as Record<string, unknown>[]

        return rows.map(rowToMeta)
    }

    /** 获取某草稿的所有 pending 修稿 */
    static getPending(baseDraftId: number): RevisionMeta[] {
        const db = getProjectDb()
        if (!db) return []

        const rows = db.prepare(`
      SELECT * FROM revisions
      WHERE base_draft_id = ? AND status = 'pending'
      ORDER BY revision_index ASC
    `).all(baseDraftId) as Record<string, unknown>[]

        return rows.map(rowToMeta)
    }

    /** 获取修稿完整数据 */
    static getFull(id: number): RevisionFull | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(
            'SELECT * FROM revisions WHERE id = ?'
        ).get(id) as Record<string, unknown> | undefined

        if (!row) return null
        const meta = rowToMeta(row)
        const body = ContentRepository.getBody(meta.contentId)
        return { ...meta, content: body ?? '' }
    }

    /** 获取下一个修稿序号 */
    static getNextIndex(baseDraftId: number): number {
        const db = getProjectDb()
        if (!db) return 1

        const row = db.prepare(`
      SELECT MAX(revision_index) as maxIdx FROM revisions WHERE base_draft_id = ?
    `).get(baseDraftId) as { maxIdx: number | null }

        return (row.maxIdx ?? 0) + 1
    }

    /** 标记为已合并（仅 pending → merged） */
    static markMerged(id: number, mergedToDraftId: number): void {
        const db = getProjectDb()
        if (!db) throw new Error('[RevisionRepository] 数据库未连接')

        const result = db.prepare(`
      UPDATE revisions
      SET status = 'merged', merged_to_draft_id = ?, updated_at = datetime('now')
      WHERE id = ? AND status = 'pending'
    `).run(mergedToDraftId, id)

        if (result.changes === 0) {
            throw new Error(`[RevisionRepository] 无法合并修稿 #${id}：不存在或非 pending 状态`)
        }
    }

    /** 标记为已弃用（仅 pending → discarded） */
    static markDiscarded(id: number): void {
        const db = getProjectDb()
        if (!db) throw new Error('[RevisionRepository] 数据库未连接')

        const result = db.prepare(`
      UPDATE revisions SET status = 'discarded', updated_at = datetime('now')
      WHERE id = ? AND status = 'pending'
    `).run(id)

        if (result.changes === 0) {
            throw new Error(`[RevisionRepository] 无法弃用修稿 #${id}：不存在或非 pending 状态`)
        }
    }
}
