/**
 * CharacterRepository — 角色卡 (characters 表)
 *
 * currentState 子结构已拍平为 cs_* 前缀列，杜绝 JSON 大字段。
 */
import { getProjectDb } from '../database'

/** 角色卡动态状态 */
export interface CharacterStateData {
    location: string
    powerLevel: string
    physicalState: string
    mentalState: string
    keyItems: string
    recentEvents: string
    updatedAtChapter: number
}

/** 角色卡完整数据（前端驼峰接口） */
export interface CharacterData {
    name: string
    role: string
    gender: string
    age: string
    appearance: string
    personality: string
    background: string
    abilities: string
    motivation: string
    relationships: string
    arc: string
    notes: string
    currentState?: CharacterStateData
}

function rowToData(row: Record<string, unknown>): CharacterData {
    const data: CharacterData = {
        name: row.name as string,
        role: (row.role as string) || 'supporting',
        gender: (row.gender as string) || '',
        age: (row.age as string) || '',
        appearance: (row.appearance as string) || '',
        personality: (row.personality as string) || '',
        background: (row.background as string) || '',
        abilities: (row.abilities as string) || '',
        motivation: (row.motivation as string) || '',
        relationships: (row.relationships as string) || '',
        arc: (row.arc as string) || '',
        notes: (row.notes as string) || '',
    }

    // currentState 存在与否由列是否为 NULL 决定（chapter 0 为合法状态）
    const updatedChapter = row.cs_updated_at_chapter as number | null
    if (updatedChapter !== null && updatedChapter !== undefined) {
        data.currentState = {
            location: (row.cs_location as string) || '',
            powerLevel: (row.cs_power_level as string) || '',
            physicalState: (row.cs_physical_state as string) || '',
            mentalState: (row.cs_mental_state as string) || '',
            keyItems: (row.cs_key_items as string) || '',
            recentEvents: (row.cs_recent_events as string) || '',
            updatedAtChapter: updatedChapter,
        }
    }

    return data
}

export class CharacterRepository {
    /** 获取所有角色（按角色定位排序：主角→配角→反派→龙套） */
    static getAll(): CharacterData[] {
        const db = getProjectDb()
        if (!db) return []

        const rows = db.prepare(`
      SELECT * FROM characters
      ORDER BY
        CASE role
          WHEN 'protagonist' THEN 0
          WHEN 'supporting' THEN 1
          WHEN 'antagonist' THEN 2
          WHEN 'minor' THEN 3
          ELSE 9
        END ASC
    `).all() as Record<string, unknown>[]

        return rows.map(rowToData)
    }

    /** 获取单个角色 */
    static getByName(name: string): CharacterData | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(
            'SELECT * FROM characters WHERE name = ?'
        ).get(name) as Record<string, unknown> | undefined

        return row ? rowToData(row) : null
    }

    /** 获取角色数量 */
    static count(): number {
        const db = getProjectDb()
        if (!db) return 0

        const row = db.prepare(
            'SELECT COUNT(*) as cnt FROM characters'
        ).get() as { cnt: number }

        return row.cnt
    }

    /** 插入或更新角色 */
    static upsert(data: CharacterData): void {
        const db = getProjectDb()
        if (!db) return

        const cs = data.currentState
        db.prepare(`
      INSERT INTO characters (
        name, role, gender, age, appearance, personality, background,
        abilities, motivation, relationships, arc, notes,
        cs_location, cs_power_level, cs_physical_state, cs_mental_state,
        cs_key_items, cs_recent_events, cs_updated_at_chapter
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(name) DO UPDATE SET
        role = excluded.role,
        gender = excluded.gender,
        age = excluded.age,
        appearance = excluded.appearance,
        personality = excluded.personality,
        background = excluded.background,
        abilities = excluded.abilities,
        motivation = excluded.motivation,
        relationships = excluded.relationships,
        arc = excluded.arc,
        notes = excluded.notes,
        cs_location = excluded.cs_location,
        cs_power_level = excluded.cs_power_level,
        cs_physical_state = excluded.cs_physical_state,
        cs_mental_state = excluded.cs_mental_state,
        cs_key_items = excluded.cs_key_items,
        cs_recent_events = excluded.cs_recent_events,
        cs_updated_at_chapter = excluded.cs_updated_at_chapter,
        updated_at = datetime('now')
    `).run(
            data.name,
            data.role,
            data.gender,
            data.age,
            data.appearance,
            data.personality,
            data.background,
            data.abilities,
            data.motivation,
            data.relationships,
            data.arc,
            data.notes,
            cs?.location ?? '',
            cs?.powerLevel ?? '',
            cs?.physicalState ?? '',
            cs?.mentalState ?? '',
            cs?.keyItems ?? '',
            cs?.recentEvents ?? '',
            cs?.updatedAtChapter ?? null,
        )
    }

    /** 批量保存角色（事务） */
    static saveAll(characters: CharacterData[]): void {
        const db = getProjectDb()
        if (!db) return

        const tx = db.transaction(() => {
            for (const char of characters) {
                CharacterRepository.upsert(char)
            }
        })
        tx()
    }

    /** 删除角色 */
    static delete(name: string): void {
        const db = getProjectDb()
        if (!db) return

        db.prepare('DELETE FROM characters WHERE name = ?').run(name)
    }

    /** 仅更新角色动态状态（后处理时使用） */
    static updateState(name: string, state: CharacterStateData): void {
        const db = getProjectDb()
        if (!db) return

        db.prepare(`
      UPDATE characters SET
        cs_location = ?, cs_power_level = ?, cs_physical_state = ?,
        cs_mental_state = ?, cs_key_items = ?, cs_recent_events = ?,
        cs_updated_at_chapter = ?, updated_at = datetime('now')
      WHERE name = ?
    `).run(
            state.location,
            state.powerLevel,
            state.physicalState,
            state.mentalState,
            state.keyItems,
            state.recentEvents,
            state.updatedAtChapter,
            name,
        )
    }
}
