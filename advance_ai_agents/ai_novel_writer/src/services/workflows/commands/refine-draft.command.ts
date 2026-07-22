import { BaseWorkflowCommand, CommandExecuteParams } from './base-command'
import { useProjectStore } from '../../../stores/project-store'
import { getPromptTemplate } from '../../prompt-templates'
import { ChapterPromptBuilder } from '../../prompts/prompt-builder'
import { ipc } from '../../ipc-client'

import type { ChapterInfo } from '../chapter-workflow'

export interface RefineDraftParams {
  draftPath: string
  draftContent: string
  chapterNumber: number
  chapterInfo: ChapterInfo
  mergedGuidance?: string
  userRefinePrompt?: string
  shortSummary?: string
}

export class RefineDraftCommand extends BaseWorkflowCommand<string> {
  constructor(private params: RefineDraftParams) {
    super()
  }

  async execute({ context, callbacks }: CommandExecuteParams): Promise<string> {
    const project = useProjectStore.getState().currentProject
    if (!project) throw new Error('未打开项目')

    const draft = this.params.draftContent
    if (!draft) throw new Error('无草稿内容')

    callbacks.log('正在进行大神级修稿...')

    const template = getPromptTemplate('refine_chapter')
    if (!template) throw new Error('未找到修稿模板')

    const mergedGuidance = this.params.mergedGuidance || project.novelConfig.globalGuidance || ''
    const userPromptBlock = this.params.userRefinePrompt?.trim()
      ? `★【用户额外修稿指导（绝对优先级）】★：\n${this.params.userRefinePrompt}`
      : ''

    const promptBuilder = new ChapterPromptBuilder(template)
      .withDraftContent(draft)
      .withChapterInfo(this.params.chapterInfo)
      .withGlobalGuidance(mergedGuidance)
      .withGlobalSummary(this.params.shortSummary || '')
      .withShortSummary(this.params.shortSummary || '')
      .withWordNumber(project.novelConfig.wordsPerChapter)
      .withUserRefinePrompt(userPromptBlock)

    const refined = await this.callLLMWithBuilder(promptBuilder, callbacks)
    const cleanRefined = this.stripThinkingTags(refined)

    const { parseDraftMeta } = await import('../chapter-workflow')
    const baseDraft = await parseDraftMeta(this.params.draftPath)
    if (!baseDraft) throw new Error('找不到基准草稿版本')

    const revIndex = await ipc.invoke('db:revision-next-index', baseDraft.id)

    // 清理该草稿下已有的 pending 状态修稿，保证只保留最新的一条
    const pendingRevs = await ipc.invoke('db:revision-get-pending', baseDraft.id)
    for (const rev of pendingRevs) {
      await ipc.invoke('db:revision-mark-discarded', rev.id)
    }

    const createRes = await ipc.invoke('db:revision-create', {
      baseDraftId: baseDraft.id,
      revisionIndex: revIndex,
      revisionType: 'refine',
      content: cleanRefined,
      wordCount: cleanRefined.length,
    }) as { success: boolean; id: number }

    const { useEditorStore } = await import('../../../stores/editor-store')
    useEditorStore.getState().openFile({
      id: `diff-${this.params.draftPath}-${createRes.id}`,
      name: `修稿合并：第${this.params.chapterNumber}章`,
      type: 'diff',
      filePath: this.params.draftPath,
      originalContent: this.params.draftContent,
      content: cleanRefined,
      revisionPath: String(createRes.id),
      chapterNumber: this.params.chapterNumber,
      chapterDir: `vela://draft/ch${this.params.chapterNumber}`,
    })

    context.data.refined = cleanRefined
    context.data.refinedPath = this.params.draftPath
    callbacks.log(`✅ 修稿完成（${cleanRefined.length} 字），已生成修订稿版本 r${revIndex}`)
    return refined
  }
}
