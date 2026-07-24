import { getProjectDb } from '../database'

export class LLMHistoryRepository {
  /** 记录一次 LLM 调用 */
  static logCall(call: {
    modelId: string
    modelName: string
    purpose: string
    promptTokens: number
    completionTokens: number
    totalTokens: number
    durationMs: number
    success: boolean
    errorMessage?: string
  }): void {
    const db = getProjectDb()
    if (!db) return

    db.prepare(`
      INSERT INTO llm_calls (model_id, model_name, purpose, prompt_tokens, completion_tokens, total_tokens, duration_ms, success, error_message)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      call.modelId, call.modelName, call.purpose,
      call.promptTokens, call.completionTokens, call.totalTokens,
      call.durationMs, call.success ? 1 : 0, call.errorMessage ?? ''
    )
  }

  /** 获取调用统计 */
  static getStats(): {
    totalCalls: number
    totalTokens: number
    totalPromptTokens: number
    totalCompletionTokens: number
  } {
    const db = getProjectDb()
    if (!db) return { totalCalls: 0, totalTokens: 0, totalPromptTokens: 0, totalCompletionTokens: 0 }

    const row = db.prepare(`
      SELECT
        COUNT(*) as totalCalls,
        COALESCE(SUM(total_tokens), 0) as totalTokens,
        COALESCE(SUM(prompt_tokens), 0) as totalPromptTokens,
        COALESCE(SUM(completion_tokens), 0) as totalCompletionTokens
      FROM llm_calls WHERE success = 1
    `).get() as { totalCalls: number; totalTokens: number; totalPromptTokens: number; totalCompletionTokens: number }

    return row
  }

  /** 获取最近 LLM 调用记录 */
  static getHistory(limit: number = 50): unknown[] {
    const db = getProjectDb()
    if (!db) return []
    return db.prepare(`
      SELECT id, model_name as modelName, purpose,
        prompt_tokens as promptTokens, completion_tokens as completionTokens,
        total_tokens as totalTokens, duration_ms as durationMs,
        success, created_at as createdAt
      FROM llm_calls ORDER BY id DESC LIMIT ?
    `).all(limit)
  }
}
