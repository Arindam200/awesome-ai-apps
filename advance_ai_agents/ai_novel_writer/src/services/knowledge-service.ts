/**
 * knowledge-service — 知识库数据访问服务
 *
 * 封装 KnowledgeOverview 和 KnowledgePanel 中的 IPC 调用，
 * 避免组件直接与 IPC 通信。
 */

import { ipc } from './ipc-client'
import type { AppErrorCode, AppFailure } from '../shared/ipc-channels'

export class KnowledgeBaseServiceError extends Error {
  constructor(public readonly code: AppErrorCode, message?: string) {
    super(message ?? code)
    this.name = 'KnowledgeBaseServiceError'
  }
}

export function unwrapKnowledgeValue<T>(result: T | AppFailure): T {
  if (
    typeof result === 'object' &&
    result !== null &&
    'success' in result &&
    result.success === false &&
    'errorCode' in result
  ) {
    throw new KnowledgeBaseServiceError(result.errorCode, result.error)
  }
  return result as T
}

/** 已导入文档 */
export interface KBDocument {
  id: string
  fileName: string
  importedAt: string
  chunkCount: number
  filePath: string
}

/** 检索结果 */
export interface SearchResult {
  text: string
  score: number
  fileName: string
}

/** 知识库统计 */
export interface KBStatsData {
  documentCount: number
  totalChunks: number
  vectorDimension: number
}

/** 加载文档列表 */
export async function listDocuments(): Promise<KBDocument[]> {
  return unwrapKnowledgeValue(await ipc.invoke('kb:list-documents'))
}

/** 获取知识库统计 */
export async function getStats(): Promise<KBStatsData> {
  return unwrapKnowledgeValue(await ipc.invoke('kb:stats'))
}

/** 同时加载文档列表和统计（常用组合） */
export async function loadKBData(): Promise<{ documents: KBDocument[]; stats: KBStatsData }> {
  const [documentsResult, statsResult] = await Promise.all([
    ipc.invoke('kb:list-documents'),
    ipc.invoke('kb:stats'),
  ])
  return {
    documents: unwrapKnowledgeValue(documentsResult),
    stats: unwrapKnowledgeValue(statsResult),
  }
}

/** 获取缺失向量的文档块数量 */
export async function getVectorlessCount(): Promise<number> {
  const result = unwrapKnowledgeValue(await ipc.invoke('kb:get-vectorless-count'))
  return result.count
}

/** 执行语义检索 */
export async function searchKB(query: string, topK: number): Promise<SearchResult[]> {
  return unwrapKnowledgeValue(await ipc.invoke('kb:search', query, topK))
}

/** 执行向量回填 */
export async function backfillVectors(): Promise<{ success: boolean; processed: number; failed: number; error?: string }> {
  return ipc.invoke('kb:backfill-vectors') as Promise<{ success: boolean; processed: number; failed: number; error?: string }>
}

/** 清空当前项目知识库 */
export async function clearKnowledgeBase(): Promise<{ success: boolean; error?: string }> {
  return ipc.invoke('kb:clear-all')
}
