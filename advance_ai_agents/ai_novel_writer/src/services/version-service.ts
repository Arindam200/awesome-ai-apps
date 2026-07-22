/**
 * version-service — 版本历史数据访问服务
 *
 * 封装 VersionHistory 中的所有 IPC 调用，
 * 避免组件直接与 IPC 通信。
 */

import { ipc } from './ipc-client'

/** 章节元数据（从数据库返回） */
export interface ChapterRecord {
  chapter_id: string
  file_path: string
  file_name: string
  updated_at: string
  chapter_number: number
  status: string
}

/** 版本记录 */
export interface VersionRecord {
  id: number
  version: number
  type: string
  word_count: number
  created_at: string
}

/** 获取项目的所有章节 (现在从蓝图获取) */
export async function getChapters(): Promise<ChapterRecord[]> {
  const blueprints = (await ipc.invoke('db:blueprint-get-all')) as unknown as Array<Record<string, unknown>>
  return blueprints.map(bp => ({
    chapter_id: String(bp.chapterNumber),
    file_path: '',
    file_name: String(bp.title || `第 ${bp.chapterNumber} 章`),
    updated_at: '',
    chapter_number: bp.chapterNumber as number,
    status: 'draft',
  }))
}

/** 获取章节的版本列表 (草稿列表) */
export async function getChapterVersions(chapterId: string): Promise<VersionRecord[]> {
  const chapterNumber = parseInt(chapterId)
  if (isNaN(chapterNumber)) return []
  const drafts = (await ipc.invoke('db:draft-list', chapterNumber)) as unknown as Array<Record<string, unknown>>
  return drafts.map(d => ({
    id: d.id as number,
    version: d.version as number,
    type: d.status === 'finalized' ? 'final' : (d.status === 'revised' ? 'refined' : 'draft'),
    word_count: (d.wordCount as number) || 0,
    created_at: String(d.createdAt),
  }))
}

/** 获取版本内容 */
export async function getVersionContent(versionId: number): Promise<string | null> {
  const draft = (await ipc.invoke('db:draft-get-full', versionId)) as { content?: string } | null
  return draft?.content || null
}

/** 获取章节最新内容（取代之前的文件读取） */
export async function getChapterLatestContent(chapterNumber: number): Promise<string> {
  const draft = (await ipc.invoke('db:draft-get-latest', chapterNumber)) as { id?: number } | null
  if (!draft || draft.id === undefined) return '（章节尚无内容）'
  const full = (await ipc.invoke('db:draft-get-full', draft.id)) as { content?: string } | null
  return full?.content || '（内容被错误截断）'
}

/** 回退到某个历史版本，创建新草稿 */
export async function revertToVersion(chapterNumber: number, content: string): Promise<boolean> {
  const nextVer: number = await ipc.invoke('db:draft-next-version', chapterNumber)
  const res = await ipc.invoke('db:draft-create', {
    chapterNumber,
    version: nextVer,
    source: 'rewrite',
    content,
    wordCount: content.length,
  })
  return res.success
}
