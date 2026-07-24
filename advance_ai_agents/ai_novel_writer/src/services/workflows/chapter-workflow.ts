import type { WorkflowDefinition } from '../../stores/workflow-store'
import type { DraftMeta } from '../draft-index'

import type { DraftStatus } from '../../shared/draft-status'

// ==========================================
// 1. 结构与类型导出 (保留对外的向后兼容)
// ==========================================
export type { DraftStatus, DraftMeta }

export interface ChapterInfo {
  chapterNumber: number
  title: string
  role: string
  purpose: string
  characters: string[]
  keyEvents: string
  suspenseHook?: string
  userGuidance?: string
  /** 用户自定义知识库检索关键词（追加到向量搜索 query） */
  knowledgeQueryHint?: string
}

export interface RefineOnlyParams {
  chapterNumber: number
  chapterTitle: string
  draftPath: string
  draftContent: string
  userRefinePrompt?: string
}

export interface RefineFromReviewParams {
  chapterNumber: number
  chapterTitle: string
  draftPath: string
  draftContent: string
  reviewReport: string
  reviewFileName: string
  userRefinePrompt?: string
}

export interface ReviewOnlyParams {
  chapterNumber: number
  chapterTitle: string
  draftPath: string
  draftContent: string
  /** 审稿维度侧重点（可选） */
  reviewFocus?: string
}

export interface FinalizeOnlyParams {
  chapterNumber: number
  chapterTitle: string
  draftPath: string
  draftContent: string
}

// ==========================================
// 2. 草稿文件工具函数 (供前端 UI 侧调用)
// ==========================================

export function getDraftDir(_projectPath: string, chapterNumber: number): string {
  return `vela://draft/ch${chapterNumber}`
}

export function getDraftPath(_projectPath: string, chapterNumber: number, version: number): string {
  return `vela://draft/ch${chapterNumber}/v${version}`
}

export async function parseDraftMeta(filePath: string): Promise<DraftMeta | null> {
  const { ipc } = await import('../ipc-client')

  // 优先处理 vela://draft/{id} 纯数字 ID 格式（DB 化后的标准路径）
  const idMatch = filePath.match(/^vela:\/\/(?:draft|manuscript)\/(\d+)$/)
  if (idMatch) {
    const draftId = parseInt(idMatch[1])
    const dbMeta = await ipc.invoke('db:draft-get-meta', draftId)
    if (!dbMeta) return null
    return {
      ...dbMeta,
      status: dbMeta.status as DraftStatus,
      source: dbMeta.source as 'write' | 'rewrite',
      fileName: `draft_v${dbMeta.version}.md`,
      filePath: `vela://draft/${dbMeta.id}`,
    } as unknown as DraftMeta
  }

  // 兼容旧格式 draft_v(\d+).md 和 vela://draft/ch{N}/v{V}
  const versionMatch = filePath.match(/v(\d+)(?:\.md)?$/)
  if (!versionMatch) return null
  const version = parseInt(versionMatch[1])

  // 提取章节号
  const chMatch = filePath.match(/ch(\d+)/)
  if (!chMatch) return null
  const chapterNumber = parseInt(chMatch[1])

  const drafts = await ipc.invoke('db:draft-list', chapterNumber)
  const d = (drafts as unknown as Array<Record<string, unknown>>).find((d) => d.version === version)
  return d ? (d as unknown as DraftMeta) : null
}

export async function updateDraftStatus(filePath: string, newStatus: DraftStatus): Promise<void> {
  const meta = await parseDraftMeta(filePath)
  if (meta) {
    const { ipc } = await import('../ipc-client')
    await ipc.invoke('db:draft-update-status', meta.id, newStatus)
  }
}

// ==========================================
// 3. 工作流定义映射工厂 (Command 调度层)
// 将原有的 1500 多行核心面条代码剥离为微内核执行器。
// ==========================================

export function createChapterWorkflow(chapterInfo: ChapterInfo): WorkflowDefinition {
  return {
    type: 'chapter_creation',
    title: `✍️ 写稿 — 第 ${chapterInfo.chapterNumber} 章 · ${chapterInfo.title}`,
    steps: [
      {
        name: '写稿',
        description: '基于架构 + 蓝图 + 上下文调用 Command 生成草稿',
        executor: async (step, context, callbacks) => {
          const { GenerateDraftCommand } = await import('./commands/generate-draft.command')
          const cmd = new GenerateDraftCommand(chapterInfo)
          return cmd.execute({ step, context, callbacks })
        },
      },
    ],
    onComplete: { mode: 'open', message: `✅ 第${chapterInfo.chapterNumber}章草稿已生成` },
  }
}

export function createRefineOnlyWorkflow(params: RefineOnlyParams): WorkflowDefinition {
  return {
    type: 'chapter_creation',
    title: `🔧 修稿 — 第${params.chapterNumber}章 ${params.chapterTitle}`,
    steps: [
      {
        name: '修稿',
        description: '将草稿提升到大神级质量，保存修稿并打开合并视图',
        executor: async (step, context, callbacks) => {
          const { RefineDraftCommand } = await import('./commands/refine-draft.command')
          const cmd = new RefineDraftCommand({
            draftPath: params.draftPath,
            draftContent: params.draftContent,
            chapterNumber: params.chapterNumber,
            chapterInfo: { chapterNumber: params.chapterNumber, title: params.chapterTitle, role: '', purpose: '', characters: [], keyEvents: '' },
            userRefinePrompt: params.userRefinePrompt,
          })
          return cmd.execute({ step, context, callbacks })
        },
      },
    ],
    onComplete: { mode: 'open', openResult: async () => { } },
  }
}

export function createRefineFromReviewWorkflow(params: RefineFromReviewParams): WorkflowDefinition {
  return {
    type: 'chapter_creation',
    title: `🔧 审稿修复 — 第${params.chapterNumber}章 ${params.chapterTitle}`,
    steps: [
      {
        name: '审稿驱动修稿',
        description: '根据审稿报告精准修复问题调用 Command',
        executor: async (step, context, callbacks) => {
          const { RefineFromReviewCommand } = await import('./commands/refine-from-review.command')
          const cmd = new RefineFromReviewCommand({
            draftPath: params.draftPath,
            draftContent: params.draftContent,
            reviewReport: params.reviewReport,
            reviewFileName: params.reviewFileName,
            chapterNumber: params.chapterNumber,
            userRefinePrompt: params.userRefinePrompt,
          })
          return cmd.execute({ step, context, callbacks })
        },
      },
    ],
    onComplete: { mode: 'open', openResult: async () => { } },
  }
}

export function createReviewOnlyWorkflow(params: ReviewOnlyParams): WorkflowDefinition {
  return {
    type: 'chapter_creation',
    title: `🔍 审稿 — 第${params.chapterNumber}章 ${params.chapterTitle}`,
    steps: [
      {
        name: '审稿',
        description: '一致性检查（角色/剧情/世界观），生成审稿报告',
        executor: async (step, context, callbacks) => {
          const { ReviewChapterCommand } = await import('./commands/review-chapter.command')
          const cmd = new ReviewChapterCommand({
            draftPath: params.draftPath,
            draftContent: params.draftContent,
            chapterNumber: params.chapterNumber,
            reviewFocus: params.reviewFocus,
          })
          return cmd.execute({ step, context, callbacks })
        },
      },
    ],
    onComplete: { mode: 'open', message: `✅ 第${params.chapterNumber}章审稿完成` },
  }
}

export function createFinalizeWorkflow(params: FinalizeOnlyParams): WorkflowDefinition {
  const chapterInfo = { chapterNumber: params.chapterNumber, title: params.chapterTitle, role: '', purpose: '', characters: [], keyEvents: '' }
  return {
    type: 'chapter_creation',
    title: `✅ 定稿 — 第${params.chapterNumber}章 ${params.chapterTitle}`,
    steps: [
      {
        name: '定稿',
        description: '写入 manuscript/，开启后处理 Command 更新三路大纲',
        executor: async (step, context, callbacks) => {
          const { FinalizeChapterCommand } = await import('./commands/finalize-chapter.command')
          const cmd = new FinalizeChapterCommand({
            draftPath: params.draftPath,
            draftContent: params.draftContent,
            chapterNumber: params.chapterNumber,
            chapterInfo,
          })
          return cmd.execute({ step, context, callbacks })
        },
      },
    ],
    onComplete: {
      mode: 'open', message: `🎉 第${params.chapterNumber}章已定稿！`, openResult: async () => {
        const { useEditorStore } = await import('../../stores/editor-store')
        const { useProjectStore } = await import('../../stores/project-store')
        const project = useProjectStore.getState().currentProject
        if (!project) return
        const { ipc } = await import('../ipc-client')
        const draftMeta = await ipc.invoke('db:draft-get-finalized', params.chapterNumber)
        if (draftMeta) {
          const fullContent = await ipc.invoke('db:draft-get-full', draftMeta.id)
          // 从数据库蓝图读取正式标题
          let displayTitle = params.chapterTitle
          try {
            const bp = await ipc.invoke('db:blueprint-get', params.chapterNumber)
            if (bp?.title) displayTitle = bp.title
          } catch { /* 蓝图读取失败时回退到 params */ }
          const dbPath = `vela://manuscript/${draftMeta.id}`
          useEditorStore.getState().openFile({
            id: dbPath,
            name: `第${params.chapterNumber}章 ${displayTitle}`,
            type: 'chapter',
            filePath: dbPath,
            content: fullContent?.content || '',
          })
        }
      }
    },
  }
}

/**
 * 修复定稿后处理工作流 — 当定稿后的三路推演失败时可重跑
 * 从 manuscript/ 读取已定稿内容，重新执行 FinalizeChapterCommand 的后处理部分
 */
export function createRepairFinalizeWorkflow(chapterNumber: number): WorkflowDefinition {
  return {
    type: 'chapter_creation',
    title: `🔧 修复后处理 — 第${chapterNumber}章`,
    steps: [
      {
        name: '重跑失败步骤',
        description: '仅重新执行失败的后处理步骤（章节要点/角色卡更新等）',
        executor: async (_step, _context, callbacks) => {
          const { useProjectStore } = await import('../../stores/project-store')
          const { ipc } = await import('../ipc-client')
          const project = useProjectStore.getState().currentProject
          if (!project) throw new Error('未打开项目')

          // 使用数据库定稿源
          const draftMeta = await ipc.invoke('db:draft-get-finalized', chapterNumber)
          if (!draftMeta) throw new Error(`第 ${chapterNumber} 章的定稿记录未获取到`)
          const full = await ipc.invoke('db:draft-get-full', draftMeta.id)
          if (!full) throw new Error(`正文提取失败: ID=${draftMeta.id}`)

          // 从数据库蓝图读取正式标题
          let chapterTitle = `第${chapterNumber}章`
          try {
            const bp = await ipc.invoke('db:blueprint-get', chapterNumber)
            if (bp?.title) chapterTitle = bp.title
          } catch { /* 蓝图读取失败时使用默认标题 */ }

          // 构建后处理步骤并以修复模式执行（跳过已成功的步骤）
          const { buildFinalizePostProcessSteps } = await import('./commands/finalize-chapter.command')
          const { runPostProcessPipeline, getChapterFinalizeScope } = await import('./workflow-utils')
          const scope = getChapterFinalizeScope(chapterNumber)
          const steps = buildFinalizePostProcessSteps(project, chapterNumber, chapterTitle, full.content)

          await runPostProcessPipeline(project.path, scope, `第${chapterNumber}章定稿`, steps, callbacks, { onlyFailed: true })

          // 通知刷新
          const { globalEventBus } = await import('../../shared/event-bus')
          globalEventBus.emit('FINALIZE_COMPLETE', { chapterNumber })
        },
      },
    ],
    onComplete: { mode: 'open', message: `✅ 第${chapterNumber}章后处理修复完成` },
  }
}
