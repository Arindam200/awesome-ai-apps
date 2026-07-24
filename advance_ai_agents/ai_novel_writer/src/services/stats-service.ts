/**
 * stats-service — LLM 调用统计数据访问服务
 *
 * 封装 BottomPanel ModelsView 中的 IPC 调用。
 */

import { ipc } from './ipc-client'

/** LLM 调用统计 */
export interface LLMStats {
  totalCalls: number
  totalTokens: number
  totalPromptTokens: number
  totalCompletionTokens: number
}

/** LLM 调用记录 */
export interface LLMCallRecord {
  id: number
  modelName: string
  purpose: string
  promptTokens: number
  completionTokens: number
  totalTokens: number
  durationMs: number
  success: boolean
  createdAt: string
}

/** 获取 LLM 调用统计 */
export async function getLLMStats(): Promise<LLMStats> {
  return ipc.invoke('db:get-llm-stats')
}

/** 获取最近 LLM 调用记录 */
export async function getLLMHistory(limit = 30): Promise<LLMCallRecord[]> {
  return (await ipc.invoke('db:get-llm-history', limit)) as unknown as LLMCallRecord[]
}

/** 同时加载统计和历史（常用组合） */
export async function loadLLMData(limit = 30): Promise<{ stats: LLMStats; history: LLMCallRecord[] }> {
  const [stats, history] = await Promise.all([
    getLLMStats(),
    getLLMHistory(limit),
  ])
  return { stats, history }
}
