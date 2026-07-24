/**
 * BlueprintRepository — 章节蓝图 (blueprints 表)
 *
 * 取代旧的 chapter-repository.ts，管理章节的规划元数据。
 */
import { getProjectDb } from '../database'

/** 蓝图行类型（DB 蛇形命名） */
export interface BlueprintRow {
    chapter_number: number
    title: string
    role: string
    purpose: string
    key_events: string
    characters: string
    suspense_hook: string
    user_guidance: string
    notes: string
    notes_updated_at: string
    created_at: string
    updated_at: string
}

/** 前端使用的驼峰接口 */
export interface BlueprintData {
    chapterNumber: number
    title: string
    role: string
    purpose: string
    keyEvents: string
    characters: string[]
    suspenseHook: string
    userGuidance: string
    notes: string
    notesUpdatedAt: string
}

function rowToData(row: BlueprintRow): BlueprintData {
    let chars: string[] = []
    try { chars = JSON.parse(row.characters) } catch { /* 容错 */ }
    return {
        chapterNumber: row.chapter_number,
        title: row.title,
        role: row.role,
        purpose: row.purpose,
        keyEvents: row.key_events,
        characters: chars,
        suspenseHook: row.suspense_hook,
        userGuidance: row.user_guidance,
        notes: row.notes,
        notesUpdatedAt: row.notes_updated_at,
    }
}

function requireProjectDb(): NonNullable<ReturnType<typeof getProjectDb>> {
    const db = getProjectDb()
    if (!db) throw new Error('项目数据库未打开')
    return db
}

export class BlueprintRepository {
    /** 获取所有蓝图（按章节号排序） */
    static getAll(): BlueprintData[] {
        const db = requireProjectDb()

        const rows = db.prepare(
            'SELECT * FROM blueprints ORDER BY chapter_number ASC'
        ).all() as BlueprintRow[]

        return rows.map(rowToData)
    }

    /** 获取单个蓝图 */
    static getByChapter(chapterNumber: number): BlueprintData | null {
        const db = requireProjectDb()

        const row = db.prepare(
            'SELECT * FROM blueprints WHERE chapter_number = ?'
        ).get(chapterNumber) as BlueprintRow | undefined

        return row ? rowToData(row) : null
    }

    /** 获取蓝图总数 */
    static count(): number {
        const db = requireProjectDb()

        const row = db.prepare(
            'SELECT COUNT(*) as cnt FROM blueprints'
        ).get() as { cnt: number }

        return row.cnt
    }

    /** 插入或更新蓝图 */
    static upsert(data: BlueprintData): void {
        const db = requireProjectDb()

        db.prepare(`
      INSERT INTO blueprints (
        chapter_number, title, role, purpose, key_events, characters,
        suspense_hook, user_guidance, notes, notes_updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(chapter_number) DO UPDATE SET
        title = excluded.title,
        role = excluded.role,
        purpose = excluded.purpose,
        key_events = excluded.key_events,
        characters = excluded.characters,
        suspense_hook = excluded.suspense_hook,
        user_guidance = excluded.user_guidance,
        notes = excluded.notes,
        notes_updated_at = excluded.notes_updated_at,
        updated_at = datetime('now')
    `).run(
            data.chapterNumber,
            data.title,
            data.role,
            data.purpose,
            data.keyEvents,
            JSON.stringify(data.characters),
            data.suspenseHook,
            data.userGuidance,
            data.notes,
            data.notesUpdatedAt,
        )
    }

    /** 批量插入/更新蓝图（事务） */
    static upsertMany(items: BlueprintData[]): void {
        const db = requireProjectDb()

        const tx = db.transaction(() => {
            for (const item of items) {
                BlueprintRepository.upsert(item)
            }
        })
        tx()
    }

    /** 删除蓝图 */
    static delete(chapterNumber: number): void {
        const db = requireProjectDb()

        db.prepare('DELETE FROM blueprints WHERE chapter_number = ?').run(chapterNumber)
    }

    /** 删除所有章节蓝图 */
    static clearAll(): void {
        const db = requireProjectDb()

        db.prepare('DELETE FROM blueprints').run()
    }

    /** 仅更新 notes 字段 */
    static updateNotes(chapterNumber: number, notes: string): void {
        const db = requireProjectDb()

        db.prepare(`
      UPDATE blueprints
      SET notes = ?, notes_updated_at = datetime('now'), updated_at = datetime('now')
      WHERE chapter_number = ?
    `).run(notes, chapterNumber)
    }
}
