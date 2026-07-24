/**
 * PostProcessRepository — 后处理跑批 (post_process_runs + post_process_steps)
 *
 * 每次后处理产生一个 Run（UUID 主键），下属多个 Step。
 * 通过 trigger_source_type + trigger_source_id 溯源到业务实体。
 */
import { getProjectDb } from '../database'
import { randomUUID } from 'node:crypto'

/** 跑批实例 */
export interface PostProcessRunData {
    id: string
    triggerSourceType: string
    triggerSourceId: string
    sourceLabel: string
    allCriticalPassed: boolean
    createdAt: string
    updatedAt: string
}

/** 步骤明细 */
export interface PostProcessStepData {
    id: number
    runId: string
    stepKey: string
    label: string
    critical: boolean
    ok: boolean
    errorMsg: string
    attemptCount: number
    completedAt: string
    lastAttemptAt: string
}

export class PostProcessRepository {
    /**
     * 创建一个新的跑批实例 + 初始化步骤列表
     * 返回新建的 run ID
     */
    static createRun(params: {
        triggerSourceType: string
        triggerSourceId: string
        sourceLabel: string
        steps: Array<{ key: string; label: string; critical: boolean }>
    }): string {
        const db = getProjectDb()
        if (!db) throw new Error('[PostProcessRepository] 数据库未连接')

        const runId = randomUUID()

        const tx = db.transaction(() => {
            db.prepare(`
        INSERT INTO post_process_runs (id, trigger_source_type, trigger_source_id, source_label)
        VALUES (?, ?, ?, ?)
      `).run(runId, params.triggerSourceType, params.triggerSourceId, params.sourceLabel)

            const insertStep = db.prepare(`
        INSERT INTO post_process_steps (run_id, step_key, label, critical)
        VALUES (?, ?, ?, ?)
      `)

            for (const step of params.steps) {
                insertStep.run(runId, step.key, step.label, step.critical ? 1 : 0)
            }
        })

        tx()
        return runId
    }

    /** 获取最新的跑批实例（按 sourceType + sourceId 查询） */
    static getLatestRun(sourceType: string, sourceId: string): PostProcessRunData | null {
        const db = getProjectDb()
        if (!db) return null

        const row = db.prepare(`
      SELECT * FROM post_process_runs
      WHERE trigger_source_type = ? AND trigger_source_id = ?
      ORDER BY created_at DESC LIMIT 1
    `).get(sourceType, sourceId) as Record<string, unknown> | undefined

        if (!row) return null
        return {
            id: row.id as string,
            triggerSourceType: row.trigger_source_type as string,
            triggerSourceId: row.trigger_source_id as string,
            sourceLabel: row.source_label as string,
            allCriticalPassed: (row.all_critical_passed as number) === 1,
            createdAt: row.created_at as string,
            updatedAt: row.updated_at as string,
        }
    }

    /** 获取跑批实例的所有步骤 */
    static getSteps(runId: string): PostProcessStepData[] {
        const db = getProjectDb()
        if (!db) return []

        const rows = db.prepare(`
      SELECT * FROM post_process_steps WHERE run_id = ? ORDER BY id ASC
    `).all(runId) as Record<string, unknown>[]

        return rows.map(row => ({
            id: row.id as number,
            runId: row.run_id as string,
            stepKey: row.step_key as string,
            label: (row.label as string) ?? '',
            critical: (row.critical as number) === 1,
            ok: (row.ok as number) === 1,
            errorMsg: (row.error_msg as string) ?? '',
            attemptCount: row.attempt_count as number,
            completedAt: (row.completed_at as string) ?? '',
            lastAttemptAt: (row.last_attempt_at as string) ?? '',
        }))
    }

    /** 标记步骤为成功 */
    static markStepOk(runId: string, stepKey: string): void {
        const db = getProjectDb()
        if (!db) return

        db.prepare(`
      UPDATE post_process_steps
      SET ok = 1, completed_at = datetime('now'), last_attempt_at = datetime('now'),
          attempt_count = attempt_count + 1
      WHERE run_id = ? AND step_key = ?
    `).run(runId, stepKey)

        // 检查是否所有关键步骤都已通过
        PostProcessRepository._refreshCriticalStatus(runId)
    }

    /** 标记步骤为失败 */
    static markStepFailed(runId: string, stepKey: string, errorMsg: string): void {
        const db = getProjectDb()
        if (!db) return

        db.prepare(`
      UPDATE post_process_steps
      SET ok = 0, error_msg = ?, last_attempt_at = datetime('now'),
          attempt_count = attempt_count + 1
      WHERE run_id = ? AND step_key = ?
    `).run(errorMsg, runId, stepKey)
    }

    /** 重新检查并更新 all_critical_passed 状态 */
    private static _refreshCriticalStatus(runId: string): void {
        const db = getProjectDb()
        if (!db) return

        // 检查是否存在未完成的关键步骤
        const failedCritical = db.prepare(`
      SELECT COUNT(*) as cnt FROM post_process_steps
      WHERE run_id = ? AND critical = 1 AND ok = 0
    `).get(runId) as { cnt: number }

        const allPassed = failedCritical.cnt === 0 ? 1 : 0
        db.prepare(`
      UPDATE post_process_runs
      SET all_critical_passed = ?, updated_at = datetime('now')
      WHERE id = ?
    `).run(allPassed, runId)
    }

    /** 获取跑批的失败步骤标签列表 */
    static getFailedStepLabels(runId: string): string[] {
        const db = getProjectDb()
        if (!db) return []

        const rows = db.prepare(`
      SELECT label FROM post_process_steps
      WHERE run_id = ? AND critical = 1 AND ok = 0
    `).all(runId) as Array<{ label: string }>

        return rows.map(r => r.label)
    }

    /** 检查某业务实体的最新跑批是否全部关键步骤通过 */
    static isAllCriticalPassed(sourceType: string, sourceId: string): boolean {
        const run = PostProcessRepository.getLatestRun(sourceType, sourceId)
        return run?.allCriticalPassed ?? false
    }
}
