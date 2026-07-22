/**
 * Vela 知识库管理 — 主进程使用
 *
 * 管理文档导入、向量化和检索
 * 底层存储已从 vectors.json 迁移至 LanceDB（{projectPath}/.vela/lancedb/）
 *
 * 检索模式：
 * - 默认：BM25 全文检索（FTS），零配置即可用
 * - 增强：FTS + 向量近邻混合检索（需配置 Embedding 模型）
 */
import fs from 'node:fs'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import * as lancedb from '@lancedb/lancedb'
import { Field, FixedSizeList as ArrowFixedSizeList, Float32, Int32, Utf8, Schema as ArrowSchema } from 'apache-arrow'
import { chunkText, generateEmbeddings } from './embedding'
import {
  addChunks,
  removeDocument as removeDocFromStore,
  clearAll as clearKnowledgeStore,
  searchWithScope as storeSearchWithScope,
  listDocuments as storeListDocuments,
  getStats as storeGetStats,
  migrateFromJSON,
  getChunksWithoutVectors as storeGetChunksWithoutVectors,
} from './vector-store'

// ===== 迁移状态跟踪 =====

/** 已执行过迁移检查的项目路径集合 */
const migratedProjects = new Set<string>()

/** 确保旧数据已迁移 */
async function ensureMigration(projectPath: string): Promise<void> {
  if (migratedProjects.has(projectPath)) return
  migratedProjects.add(projectPath)

  const jsonPath = path.join(projectPath, '.vela', 'vectors.json')
  if (fs.existsSync(jsonPath)) {
    await migrateFromJSON(projectPath)
  }
}

// ===== 导出函数（保持旧签名，IPC 层零改动） =====

/**
 * 导入文档到知识库（单文件，从磁盘读取）
 * 始终建立 FTS 索引；有 Embedding 配置时额外生成向量
 */
export async function importDocument(
  filePath: string,
  projectPath: string,
  protocol: 'openai' | 'gemini',
  model: { baseUrl: string; apiKey: string },
  onProgress?: (progress: number, message: string) => void,
): Promise<{ success: boolean; docId?: string; chunkCount?: number; error?: string }> {
  try {
    await ensureMigration(projectPath)

    // 1. 读取文件
    const fileName = path.basename(filePath)
    const ext = path.extname(filePath).toLowerCase()
    if (!['.txt', '.md', '.markdown'].includes(ext)) {
      return { success: false, error: `不支持的文件类型: ${ext}，仅支持 .txt / .md` }
    }

    onProgress?.(5, `正在读取 ${fileName}...`)
    const content = fs.readFileSync(filePath, 'utf-8')
    if (!content.trim()) {
      return { success: false, error: '文件内容为空' }
    }

    // 2. 分块
    onProgress?.(10, '正在分块...')
    const chunks = chunkText(content, 500, 50)
    const docId = randomUUID()

    // 3. 可选：生成向量（如果有 Embedding 配置）
    let vectors: number[][] | undefined
    if (model.apiKey) {
      try {
        onProgress?.(20, `正在向量化 ${chunks.length} 个块...`)
        vectors = await generateEmbeddings(chunks, protocol, model)
      } catch (e) {
        console.warn('[Vela KB] Embedding 调用失败，降级为 FTS-only:', e)
        // 不影响导入，仅 FTS
      }
    }

    // 4. 写入 LanceDB（text + 元数据 + 可选向量）
    onProgress?.(80, '正在保存...')
    const result = await addChunks(projectPath, docId, fileName, chunks, vectors, filePath)

    if (!result.success) {
      return { success: false, error: result.error }
    }

    onProgress?.(100, `✅ 已导入 ${fileName}（${chunks.length} 个块）`)
    return { success: true, docId, chunkCount: chunks.length }
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 检索知识库
 * 有 Embedding 配置时 → 混合检索（FTS + 向量）
 * 无 Embedding 配置时 → 纯 FTS 检索
 */
export async function searchKnowledge(
  query: string,
  projectPath: string,
  protocol: 'openai' | 'gemini',
  model: { baseUrl: string; apiKey: string },
  topK: number = 5,
  chapterScope?: [number, number],
): Promise<Array<{ text: string; score: number; fileName: string }>> {
  await ensureMigration(projectPath)

  // 可选：生成查询向量
  let queryVector: number[] | undefined
  if (model.apiKey && query.trim()) {
    try {
      const [vec] = await generateEmbeddings([query], protocol, model)
      if (vec && vec.length > 0) {
        queryVector = vec
      }
    } catch {
      // Embedding 不可用，降级为 FTS
    }
  }

  return storeSearchWithScope(projectPath, query, queryVector, topK, chapterScope)
}

/**
 * 列出已导入文档
 */
export function listDocuments(projectPath: string) {
  return storeListDocuments(projectPath)
}

/**
 * 删除文档
 */
export async function removeDocument(docId: string, projectPath: string): Promise<boolean> {
  return removeDocFromStore(projectPath, docId)
}

/**
 * 清空项目知识库。
 */
export async function clearKnowledgeBase(projectPath: string): Promise<boolean> {
  return clearKnowledgeStore(projectPath)
}

/**
 * 获取知识库统计
 */
export async function getKnowledgeStats(projectPath: string): Promise<{
  documentCount: number
  totalChunks: number
  vectorDimension: number
}> {
  const stats = await storeGetStats(projectPath)
  return {
    documentCount: stats.documentCount,
    totalChunks: stats.totalChunks,
    vectorDimension: stats.vectorDimension,
  }
}

/**
 * 批量导入文件夹到知识库（递归扫描所有 .txt / .md 文件）
 */
export async function importFolder(
  folderPath: string,
  projectPath: string,
  protocol: 'openai' | 'gemini',
  model: { baseUrl: string; apiKey: string },
  onProgress?: (current: number, total: number, fileName: string) => void,
): Promise<{
  success: boolean
  importedCount: number
  failedFiles: string[]
  error?: string
}> {
  try {
    // 递归收集所有 .txt / .md 文件
    const collectFiles = (dir: string): string[] => {
      const result: string[] = []
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fullPath = path.join(dir, entry.name)
        if (entry.isDirectory()) {
          result.push(...collectFiles(fullPath))
        } else if (/\.(txt|md|markdown)$/i.test(entry.name)) {
          result.push(fullPath)
        }
      }
      return result
    }

    const files = collectFiles(folderPath)
    if (files.length === 0) return { success: true, importedCount: 0, failedFiles: [] }

    const failedFiles: string[] = []
    let importedCount = 0

    for (let i = 0; i < files.length; i++) {
      const filePath = files[i]
      const fileName = path.basename(filePath)
      onProgress?.(i + 1, files.length, fileName)

      const result = await importDocument(filePath, projectPath, protocol, model)
      if (result.success) {
        importedCount++
      } else {
        failedFiles.push(fileName)
      }
    }

    return { success: true, importedCount, failedFiles }
  } catch (error) {
    return { success: false, importedCount: 0, failedFiles: [], error: String(error) }
  }
}

/**
 * 直接将文本字符串内容导入知识库
 * 用于定稿后自动导入、按章推演等无文件场景
 */
/**
 * 从文件名解析章节元数据
 * 支持格式：第{N}章 {title} xxx.md
 */
function parseChapterMetaFromFileName(fileName: string): { chapterNumber?: number; chapterTitle?: string } | undefined {
  const match = fileName.match(/^第(\d+)章\s+(.+?)\s+(正文|要点|蓝图)\.md$/)
  if (match) {
    return {
      chapterNumber: parseInt(match[1]),
      chapterTitle: match[2],
    }
  }
  return undefined
}

export async function importText(
  text: string,
  fileName: string,
  projectPath: string,
  protocol: 'openai' | 'gemini',
  model: { baseUrl: string; apiKey: string },
): Promise<{ success: boolean; docId?: string; chunkCount?: number; error?: string }> {
  try {
    if (!text.trim()) return { success: false, error: '文本内容为空' }

    await ensureMigration(projectPath)

    // 分块
    const chunks = chunkText(text)
    const docId = randomUUID()

    // 解析章节元数据（从文件名提取）
    const chapterMeta = parseChapterMetaFromFileName(fileName)

    // 可选：生成向量
    let vectors: number[][] | undefined
    if (model.apiKey) {
      try {
        vectors = await generateEmbeddings(chunks, protocol, model)
      } catch (e) {
        console.warn('[Vela KB] importText Embedding 失败，降级 FTS-only:', e)
      }
    }

    // 先删除同名旧文档（幂等性由 vector-store 的 addChunks 内部处理 documents 表）
    // 但 chunks 表需要手动清理旧的同名文档块
    const existingDocs = await storeListDocuments(projectPath)
    const existingDoc = existingDocs.find(d => d.fileName === fileName)
    if (existingDoc) {
      await removeDocFromStore(projectPath, existingDoc.id)
    }

    const result = await addChunks(projectPath, docId, fileName, chunks, vectors, undefined, chapterMeta)
    if (!result.success) {
      return { success: false, error: result.error }
    }

    return { success: true, docId, chunkCount: chunks.length }
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

// ===== 向量回填相关 =====

/**
 * 获取缺少向量的块数量
 */
export async function getVectorlessCount(projectPath: string): Promise<{ count: number }> {
  return storeGetChunksWithoutVectors(projectPath)
}

/**
 * 批量回填向量（为无向量的块生成 Embedding 并写回）
 * 单次全量加载→生成→写回，避免循环中的 schema 状态问题
 */
export async function backfillVectors(
  projectPath: string,
  protocol: 'openai' | 'gemini',
  model: { baseUrl: string; apiKey: string },
): Promise<{ success: boolean; processed: number; failed: number; error?: string }> {
  try {
    const { count: total } = await storeGetChunksWithoutVectors(projectPath)
    if (total === 0) return { success: true, processed: 0, failed: 0 }

    // 全量加载所有需要向量的块
    const { getConnection } = await import('./vector-store')
    const db = await getConnection(projectPath)
    const tableNames = await db.tableNames()
    if (!tableNames.includes('chunks')) {
      return { success: false, processed: 0, failed: total, error: 'chunks 表不存在' }
    }

    const table = await db.openTable('chunks')
    const schema = await table.schema()
    const hasVectorCol = schema.fields.some(f => f.name === 'vector')

    let allRecords: Array<{ id: string; text: string; vector?: number[] }> = []
    if (hasVectorCol) {
      const rows = await table.query().select(['id', 'text', 'vector']).toArray()
      allRecords = rows.filter((r: { id: string; text: string; vector?: number[] }) =>
        !r.vector || !Array.isArray(r.vector) || r.vector.length === 0
      )
    } else {
      const rows = await table.query().select(['id', 'text']).toArray()
      allRecords = rows.map((r: { id: string; text: string }) => ({ id: r.id, text: r.text }))
    }

    if (allRecords.length === 0) {
      return { success: true, processed: 0, failed: 0 }
    }

    // 批量生成向量
    const texts = allRecords.map(r => r.text)
    const vectors = await generateEmbeddings(texts, protocol, model)

    // 构建更新后的完整数据
    const idToVector = new Map<string, number[]>()
    allRecords.forEach((r, i) => {
      if (vectors[i] && vectors[i].length > 0) {
        idToVector.set(r.id, vectors[i])
      }
    })

    // 全量读出 + 合并更新
    const fullTable = await db.openTable('chunks')
    const allRows = await fullTable.query().toArray()
    const updatedRows = allRows.map((r: { [key: string]: unknown }) => {
      const v = idToVector.get(r.id as string)
      return v ? { ...r, vector: v } : r
    })

    // 使用显式 Arrow Schema 确保 vector 列正确持久化
    // LanceDB 自动推断无法正确识别 number[] 为 FixedSizeList 向量类型
    const VECTOR_DIM = 2048
    const vectorField = new Field('vector', new ArrowFixedSizeList(VECTOR_DIM, new Field('item', new Float32())), true)
    const arrowSchema = new ArrowSchema([
      new Field('id', new Utf8()),
      new Field('docId', new Utf8()),
      new Field('fileName', new Utf8()),
      new Field('chapterNumber', new Int32(), true),
      new Field('chapterTitle', new Utf8(), true),
      new Field('text', new Utf8()),
      vectorField,
      new Field('chunkIndex', new Int32()),
      new Field('totalChunks', new Int32()),
      new Field('importedAt', new Utf8()),
    ])

    // 删除旧表，用带显式 schema 的 createTable 重新写入
    await db.dropTable('chunks')
    await db.createTable('chunks', updatedRows, { schema: arrowSchema })
    // 重建 FTS 索引
    const newTable = await db.openTable('chunks')
    try {
      await newTable.createIndex('text', { config: lancedb.Index.fts() })
    } catch { /* 索引可能已存在 */ }

    // 验证
    const verifyRows = await newTable.query().select(['id', 'vector']).limit(5).toArray()
    const withVectors = verifyRows.filter((r: { vector?: unknown }) => {
      if (!r.vector) return false
      const vec = r.vector as { length?: number; toArray?: () => unknown[] }
      if (typeof vec.toArray === 'function') return vec.toArray().length > 0
      return (vec.length ?? 0) > 0
    }).length
    if (withVectors === 0) {
      return { success: false, processed: 0, failed: total, error: '回填后记录向量为空，可能是 LanceDB schema 写入失败' }
    }

    return { success: true, processed: idToVector.size, failed: total - idToVector.size }
  } catch (error) {
    console.error('[Vela KB] 向量回填异常:', error)
    return { success: false, processed: 0, failed: 0, error: String(error) }
  }
}

/**
 * FTS-only 检索（不需要 Embedding 配置）
 * 用于 IPC 层在无 Embedding 模型时直接调用
 */
export async function searchKnowledgeFTS(
  query: string,
  projectPath: string,
  topK: number = 5,
  chapterScope?: [number, number],
): Promise<Array<{ text: string; score: number; fileName: string }>> {
  await ensureMigration(projectPath)
  return storeSearchWithScope(projectPath, query, undefined, topK, chapterScope)
}
