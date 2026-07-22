/**
 * 草稿状态管理 — 管理各章节草稿列表、定稿操作等
 *
 * 数据来源：drafts/ch{N}/index.json（md+json 分离方案）
 * .md 文件保持纯正文，元数据全部由 index.json 管理
 */
import { create } from 'zustand'
import { ipc } from '../services/ipc-client'
import {
  updateDraftStatus as updateDraftStatusInIndex,
  type DraftMeta,
} from '../services/draft-index'
import type { DraftStatus } from '../shared/draft-status'
import { getDraftDir } from '../services/workflows/chapter-workflow'
import { useProjectStore } from './project-store'

// ===== 类型定义 =====

/** 单章下的草稿列表（key = chapterNumber） */
export type DraftsByChapter = Record<number, DraftMeta[]>

interface DraftState {
  /** 各章草稿列表（内存缓存），key = chapterNumber */
  draftsByChapter: DraftsByChapter
  /** 是否正在加载 */
  loading: boolean

  // ===== Actions =====
  /** 重置为初始状态（项目关闭时由 ProjectService 调用） */
  reset: () => void
  /** 加载某章的所有草稿 */
  loadChapterDrafts: (chapterNumber: number) => Promise<void>
  /** 加载全部章节草稿（扫描 drafts/ 目录下所有 ch{NNN} 子目录） */
  loadAllDrafts: () => Promise<void>

  /** 手动标记草稿状态（修稿/审稿后更新用） */
  markDraftStatus: (draftPath: string, chapterNumber: number, status: DraftStatus) => Promise<void>
  /** 清除指定章节的缓存（下次访问时重新加载） */
  invalidateChapter: (chapterNumber: number) => void
  /** 应用合并后的修稿，更新文件和各类状态 */
  applyMergedRevision: (
    chapterDir: string,
    chapterNumber: number | undefined,
    filePath: string,
    revPath: string,
    mergedText: string
  ) => Promise<{ success: boolean; error?: string }>
}

export const useDraftStore = create<DraftState>()((set, get) => ({
  draftsByChapter: {},
  loading: false,

  reset: () => {
    set({ draftsByChapter: {}, loading: false })
  },

  loadChapterDrafts: async (chapterNumber) => {
    const project = useProjectStore.getState().currentProject
    if (!project) return

    try {
      // 直接调用后端 DB 获取列表，返回的结构已经转换为兼容的 DraftMeta 格式
      const list = await ipc.invoke('db:draft-list', chapterNumber)
      const metas: DraftMeta[] = list.map((m) => ({
        ...m,
        status: m.status as DraftStatus,
        source: m.source as DraftMeta['source'],
        fileName: `draft_v${m.version}.md`,
        filePath: `vela://draft/${m.id}`
      }))

      // 按版本号排序（新 → 旧）
      metas.sort((a, b) => b.version - a.version)

      set(s => ({
        draftsByChapter: { ...s.draftsByChapter, [chapterNumber]: metas },
      }))
    } catch {
      // 出错或不存在时跳过
    }
  },

  loadAllDrafts: async () => {
    const project = useProjectStore.getState().currentProject
    if (!project) return

    set({ loading: true })
    try {
      const blueprints = await ipc.invoke('db:blueprint-get-all')
      const newDraftsByChapter: DraftsByChapter = {}

      for (const bp of blueprints) {
        const chNum = bp.chapterNumber
        const list = await ipc.invoke('db:draft-list', chNum)
        if (!list || list.length === 0) continue

        const metas: DraftMeta[] = list.map((m) => ({
          ...m,
          status: m.status as DraftStatus,
          source: m.source as DraftMeta['source'],
          fileName: `draft_v${m.version}.md`,
          filePath: `vela://draft/${m.id}`
        }))

        metas.sort((a, b) => b.version - a.version)
        newDraftsByChapter[chNum] = metas
      }

      set({ draftsByChapter: newDraftsByChapter })
    } finally {
      set({ loading: false })
    }
  },


  markDraftStatus: async (draftPath, chapterNumber, status) => {
    // 从路径提取版本号
    const versionMatch = draftPath.match(/draft_v(\d+)\.md$/)
    if (!versionMatch) return
    const version = parseInt(versionMatch[1])
    const project = useProjectStore.getState().currentProject
    if (!project) return
    const chapterDir = getDraftDir(project.path, chapterNumber)
    await updateDraftStatusInIndex(chapterDir, version, status)
    // 重新加载该章草稿以刷新缓存
    await get().loadChapterDrafts(chapterNumber)
  },

  invalidateChapter: (chapterNumber) => {
    set(s => {
      const next = { ...s.draftsByChapter }
      delete next[chapterNumber]
      return { draftsByChapter: next }
    })
  },

  applyMergedRevision: async (chapterDir, chapterNumber, filePath, revPath, mergedText) => {
    try {
      const { markRevisionMerged } = await import('../services/draft-index')

      const versionMatch = filePath.match(/v(\d+)/)
      const version = versionMatch ? parseInt(versionMatch[1]) : 1

      let targetDraftId: number | undefined
      // 统一通过 DB 更新草稿内容
      if (filePath.startsWith('vela://draft/') || filePath.startsWith('vela://manuscript/')) {
        const prefix = filePath.startsWith('vela://draft/') ? 'vela://draft/' : 'vela://manuscript/'
        targetDraftId = parseInt(filePath.replace(prefix, ''))
        await ipc.invoke('db:draft-update-content', targetDraftId, mergedText, mergedText.length)
      } else {
        // 从 filePath 解析 chapterNumber 和 version，查出 draftId 再更新
        const chMatch = filePath.match(/ch(\d+)/)
        const chNum = chMatch ? parseInt(chMatch[1]) : chapterNumber
        if (chNum !== undefined) {
          const drafts = await ipc.invoke('db:draft-list', chNum)
          const target = (drafts as unknown as Array<Record<string, unknown>>).find((d) => d.version === version)
          if (target) {
            targetDraftId = target.id as number
            await ipc.invoke('db:draft-update-content', targetDraftId, mergedText, mergedText.length)
          }
        }
      }

      // 更新草稿状态为 revised（直接调用 DB，不走 legacy index）
      if (targetDraftId && version) {
        await ipc.invoke('db:draft-update-status', targetDraftId, 'revised', mergedText.length)
      }

      // 标记修稿为已合并
      const revFileName = revPath.split('/').pop() || ''
      const origFileName = targetDraftId ? targetDraftId.toString() : (filePath.split('/').pop() || '')
      if (revFileName) {
        await markRevisionMerged(chapterDir, revFileName, origFileName)
      }

      // 同步到编辑器（需通过 filePath 查找对应 tab 的 id）
      const { useEditorStore } = await import('./editor-store')
      const editorState = useEditorStore.getState()
      const targetTab = editorState.tabs.find(t => t.filePath === filePath)
      if (targetTab) {
        editorState.syncTabContent(targetTab.id, mergedText)
        editorState.markTabSaved(targetTab.id)
      }

      if (chapterNumber !== undefined) {
        await get().loadChapterDrafts(chapterNumber)
      }
      useProjectStore.getState().refreshFileTree()

      return { success: true }
    } catch (e) {
      return { success: false, error: String(e) }
    }
  },
}))

// ===== 辅助工具导出 =====

/**
 * 读取草稿文件正文（委托给 vela-protocol 统一路由）
 * @deprecated 建议直接使用 readVelaContent()
 */
export async function readDraftBody(filePath: string): Promise<string> {
  const { readVelaContent } = await import('../services/vela-protocol')
  return readVelaContent(filePath)
}

export type { DraftMeta, DraftStatus }
