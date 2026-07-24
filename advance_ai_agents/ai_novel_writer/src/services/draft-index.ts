/**
 * 草稿元数据管理（原 index.json 封装层）
 *
 * 全量 DB 化后，这里不再读写 index.json，而是直接桥接到 db:* IPC 通道。
 * 保留原有函数名和数据接口结构，以便减少对 UI 层 (DraftEditor) 的破坏性修改。
 */
import { ipc } from './ipc-client'
import type { DraftStatus } from '../shared/draft-status'

// 导入后端的类型定义
import type { DraftMeta as DB_DraftMeta } from '../../electron/repositories/draft-repository'
import type { RevisionMeta as DB_RevisionMeta } from '../../electron/repositories/revision-repository'
import type { ReviewMeta as DB_ReviewMeta } from '../../electron/repositories/review-repository'

// ===== DraftMeta 兼容类型 =====
export interface DraftMeta {
  id: number
  chapterNumber: number
  chapterTitle?: string       // 为了兼容保留（UI极少直接从draft拿），实际上可不填
  version: number
  status: DraftStatus
  wordCount?: number
  createdAt: string
  updatedAt?: string
  source: 'write' | 'rewrite'

  // 为了尽量不改 UI，我们伪造这两个字段
  filePath: string
  fileName: string
}

// ===== RevisionEntry 兼容类型 =====
export interface RevisionEntry {
  id: number
  baseDraftId: number
  baseVersion: number         // 为了 UI 需要保留关联版本号
  revisionIndex: number
  type: 'refine' | 'review-fix'
  status: 'pending' | 'merged' | 'discarded'
  createdAt: string
  mergedToDraftId?: number

  // 虚拟文件路径字段，供 UI 展示或查内容使用
  fileName: string
  baseDraft: string
}

// ===== ReviewEntry 兼容类型 =====
export interface ReviewEntry {
  id: number
  baseDraftId: number
  baseVersion: number
  reviewIndex: number
  createdAt: string

  fileName: string
  baseDraft: string
}

// ==========================================
// 辅助映射函数
// ==========================================

function mapDraftMeta(dbMeta: DB_DraftMeta): DraftMeta {
  return {
    ...dbMeta,
    status: dbMeta.status as DraftStatus,
    source: dbMeta.source as 'write' | 'rewrite',
    // 虚拟字段，UI通过 parse 得到版本号或者展示
    fileName: `draft_v${dbMeta.version}.md`,
    filePath: `vela://draft/${dbMeta.id}`, // 特殊的伪协议路径，用于 editor-store
  }
}

function mapRevisionEntry(dbMeta: DB_RevisionMeta, baseVersion: number): RevisionEntry {
  return {
    ...dbMeta,
    type: dbMeta.revisionType as 'refine' | 'review-fix',
    status: dbMeta.status as 'pending' | 'merged' | 'discarded',
    mergedToDraftId: dbMeta.mergedToDraftId ?? undefined,
    baseVersion,
    fileName: `v${baseVersion}_r${dbMeta.revisionIndex}.md`,
    baseDraft: `draft_v${baseVersion}.md`,
  }
}

function mapReviewEntry(dbMeta: DB_ReviewMeta, baseVersion: number): ReviewEntry {
  return {
    ...dbMeta,
    baseVersion,
    fileName: `v${baseVersion}_review_${dbMeta.reviewIndex}.md`,
    baseDraft: `draft_v${baseVersion}.md`,
  }
}

// Helper: 查出 draftId
async function getDraftId(chapterNumber: number, version: number): Promise<number | null> {
  const drafts = await ipc.invoke('db:draft-list', chapterNumber)
  const match = drafts.find((d: DB_DraftMeta) => d.version === version)
  return match?.id ?? null
}

// ==========================================
// 草稿操作
// ==========================================

export async function addDraft(): Promise<void> {
  // 原本是保存 index.json，现改为新建到数据库
  // 由于这里调用方往往传入包含全字段的虚拟 draft 对象，所以需抽取必要信息
  // 注意：旧逻辑是在 command 中自己写入了 content，再调用这里。
  // 我们需要重写相关 command 才能正确衔接，但为了当前类型的完备，这里先搭起架子：
  throw new Error('Please migrate command calls to ipc.invoke("db:draft-create") directly.')
}

export async function updateDraftStatus(
  chapterDir: string,
  version: number,
  status: DraftStatus,
  wordCount?: number,
): Promise<void> {
  // 从 chapterDir 倒推 chapterNumber（假设格式为 .../chNNN）
  const match = chapterDir.match(/ch(\d+)$/)
  if (!match) return
  const chapterNumber = parseInt(match[1])

  const draftId = await getDraftId(chapterNumber, version)
  if (!draftId) return

  await ipc.invoke('db:draft-update-status', draftId, status, wordCount)

  if (status === 'finalized') {
    // DB 并没有自动把其他草稿归档，这里我们可以手动查出其他同章并归档
    const list = await ipc.invoke('db:draft-list', chapterNumber)
    for (const d of list as DB_DraftMeta[]) {
      if (d.version !== version && (d.status === 'draft' || d.status === 'revised')) {
        await ipc.invoke('db:draft-update-status', d.id, 'archived')
      }
    }
  }
}

export async function getNextDraftVersion(chapterDir: string): Promise<number> {
  const match = chapterDir.match(/ch(\d+)$/)
  if (!match) return 1
  const chapterNumber = parseInt(match[1])

  return await ipc.invoke('db:draft-next-version', chapterNumber)
}

export async function getDraftMeta(chapterDir: string, version: number): Promise<DraftMeta | null> {
  const match = chapterDir.match(/ch(\d+)$/)
  if (!match) return null
  const chapterNumber = parseInt(match[1])

  const draftId = await getDraftId(chapterNumber, version)
  if (!draftId) return null

  const dbMeta: DB_DraftMeta | null = await ipc.invoke('db:draft-get-meta', draftId)
  if (!dbMeta) return null
  return mapDraftMeta(dbMeta)
}

// ==========================================
// 修稿操作
// ==========================================

export async function getNextRevisionIndex(chapterDir: string, baseVersion: number): Promise<number> {
  const match = chapterDir.match(/ch(\d+)$/)
  if (!match) return 1
  const chapterNumber = parseInt(match[1])

  const draftId = await getDraftId(chapterNumber, baseVersion)
  if (!draftId) return 1

  return await ipc.invoke('db:revision-next-index', draftId)
}

export async function getPendingRevisions(
  chapterDir: string,
  baseVersion: number,
): Promise<RevisionEntry[]> {
  const match = chapterDir.match(/ch(\d+)$/)
  if (!match) return []
  const chapterNumber = parseInt(match[1])

  const draftId = await getDraftId(chapterNumber, baseVersion)
  if (!draftId) return []

  const list: DB_RevisionMeta[] = await ipc.invoke('db:revision-get-pending', draftId)
  return list.map(m => mapRevisionEntry(m, baseVersion))
}

export async function markRevisionMerged(
  chapterDir: string,
  revisionFileName: string, // "v1_r1.md" 或 pura db id (如 "42")
  mergedToFileName: string, // "draft_v1.md" (旧/新) 或 pure db id (如 "15")
): Promise<void> {

  const revIdMatch = revisionFileName.match(/^\d+$/)
  const targetIdMatch = mergedToFileName.match(/^\d+$/)

  if (revIdMatch && targetIdMatch) {
    // 全新 DB 化路径传来的纯数字 ID
    await ipc.invoke('db:revision-mark-merged', parseInt(revIdMatch[0]), parseInt(targetIdMatch[0]))
    return
  }

  const matchCh = chapterDir.match(/ch(\d+)$/)
  if (!matchCh) return
  const chapterNumber = parseInt(matchCh[1])

  // 从 revisionFileName 解析 baseVersion 和 index
  const matchRev = revisionFileName.match(/v(\d+)_r(\d+)/)
  if (!matchRev) return
  const baseVersion = parseInt(matchRev[1])
  const revisionIndex = parseInt(matchRev[2])

  const baseDraftId = await getDraftId(chapterNumber, baseVersion)
  if (!baseDraftId) return

  const list: DB_RevisionMeta[] = await ipc.invoke('db:revision-list', baseDraftId)
  const rev = list.find(r => r.revisionIndex === revisionIndex)
  if (!rev) return

  // 从 mergedTo 找到 target draft
  let targetDraftId = baseDraftId
  const matchDraft = mergedToFileName.match(/v(\d+)/)
  if (matchDraft) {
    const mergedVersion = parseInt(matchDraft[1])
    targetDraftId = await getDraftId(chapterNumber, mergedVersion) ?? baseDraftId
  }

  await ipc.invoke('db:revision-mark-merged', rev.id, targetDraftId)
}

// ==========================================
// 审稿操作
// ==========================================

export async function getNextReviewIndex(chapterDir: string, baseVersion: number): Promise<number> {
  const matchCh = chapterDir.match(/ch(\d+)$/)
  if (!matchCh) return 1
  const chapterNumber = parseInt(matchCh[1])

  const baseDraftId = await getDraftId(chapterNumber, baseVersion)
  if (!baseDraftId) return 1

  return await ipc.invoke('db:review-next-index', baseDraftId)
}

export async function getLatestReview(
  chapterDir: string,
  baseVersion: number,
): Promise<ReviewEntry | null> {
  const matchCh = chapterDir.match(/ch(\d+)$/)
  if (!matchCh) return null
  const chapterNumber = parseInt(matchCh[1])

  const baseDraftId = await getDraftId(chapterNumber, baseVersion)
  if (!baseDraftId) return null

  const review: DB_ReviewMeta | null = await ipc.invoke('db:review-get-latest', baseDraftId)
  if (!review) return null

  return mapReviewEntry(review, baseVersion)
}

export async function getReviewsForVersion(
  chapterDir: string,
  baseVersion: number,
): Promise<ReviewEntry[]> {
  const matchCh = chapterDir.match(/ch(\d+)$/)
  if (!matchCh) return []
  const chapterNumber = parseInt(matchCh[1])

  const baseDraftId = await getDraftId(chapterNumber, baseVersion)
  if (!baseDraftId) return []

  const list: DB_ReviewMeta[] = await ipc.invoke('db:review-list', baseDraftId)
  return list.map(m => mapReviewEntry(m, baseVersion)).sort((a, b) => a.reviewIndex - b.reviewIndex)
}

// ==========================================
// 被旧接口或 UI 其他地方需要兼容的方法
// ==========================================

export async function readDraftIndex() {
  // 返回空结构，因为调用者现在应该是直接查 draftsByChapter 而不是读 index
  return { chapterNumber: 0, chapterTitle: '', drafts: [], revisions: [], reviews: [] }
}

export function toDraftMeta() {
  throw new Error('toDraftMeta is deprecated.')
}
