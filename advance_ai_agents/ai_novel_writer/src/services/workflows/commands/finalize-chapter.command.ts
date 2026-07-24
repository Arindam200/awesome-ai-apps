import { BaseWorkflowCommand, CommandExecuteParams } from './base-command'
import { useProjectStore } from '../../../stores/project-store'
import { useLLMStore } from '../../../stores/llm-store'
import { getPromptTemplate } from '../../prompt-templates'
import { PostProcessPromptBuilder } from '../../prompts/prompt-builder'
import { ipc } from '../../ipc-client'

import {
  runPostProcessPipeline,
  getChapterFinalizeScope,
  stripThinkingTags,
  type PostProcessStep,
} from '../workflow-utils'
import type { ChapterInfo } from '../chapter-workflow'

export interface FinalizeChapterParams {
  draftPath: string
  draftContent: string
  chapterNumber: number
  chapterInfo: ChapterInfo
}

// ===== 工具函数：流式调用大模型并返回完整文本 =====

/**
 * 使用 PromptBuilder 调用 LLM（不依赖 BaseWorkflowCommand 实例）
 * 独立函数，可被 PostProcessStep 的 executor 直接调用
 */
async function callLLMForPostProcess(
  builder: { build: () => string; getSystemRole: () => string },
  callbacks: { appendText: (text: string) => void },
  options?: { responseFormat?: { type: string } },
): Promise<string> {
  const llmStore = useLLMStore.getState()
  if (!llmStore.defaultModelId) throw new Error('未配置默认 AI 模型')

  return new Promise<string>((resolve, reject) => {
    let fullContent = ''
    llmStore.generateStream(
      [
        { role: 'system', content: builder.getSystemRole() },
        { role: 'user', content: builder.build() },
      ],
      {
        onChunk: (chunk) => { fullContent += chunk; callbacks.appendText(chunk) },
        onDone: (text) => {
          const raw = text || fullContent
          resolve(stripThinkingTags(raw))
        },
        onError: (err) => reject(new Error(err || '流式生成失败')),
      },
      undefined,
      options,
    )
  })
}

/** 容错 JSON 解析（剥离 Markdown 代码块 + 自动截取有效 JSON 边界） */
function parseJSON<T>(text: string): T {
  let cleanText = text.replace(/```json?\n?/gi, '').replace(/```\n?/gi, '').trim()
  const firstBrace = cleanText.indexOf('{')
  const lastBrace = cleanText.lastIndexOf('}')
  if (firstBrace !== -1 && lastBrace !== -1) {
    cleanText = cleanText.substring(firstBrace, lastBrace + 1)
  }
  return JSON.parse(cleanText) as T
}

// ===== 后处理步骤构建器 =====

/**
 * 构建章节定稿后处理步骤列表
 *
 * 每个步骤都是独立的 PostProcessStep，由 runPostProcessPipeline
 * 统一调度执行、持久化状态、支持单步重试。
 * 导出供 createRepairFinalizeWorkflow 复用。
 *
 * @param project       当前项目信息
 * @param chapterNumber 章节号
 * @param chapterTitle  章节标题
 * @param draftContent  定稿正文内容
 */
export function buildFinalizePostProcessSteps(
  _project: { path: string },
  chapterNumber: number,
  chapterTitle: string,
  draftContent: string,
): PostProcessStep[] {
  const steps: PostProcessStep[] = []

  // ─── 步骤 1: 导入知识库 ───────────────────────────────────────────
  steps.push({
    key: 'kb_import',
    label: '📚 导入知识库',
    critical: true,
    executor: async (callbacks) => {
      const contentFileName = chapterTitle
        ? `第${chapterNumber}章 ${chapterTitle}.txt`
        : `chapter_${chapterNumber}.txt`
      const result = await ipc.invoke('kb:import-text', draftContent, contentFileName, _project.path) as { success: boolean; error?: string; chunkCount?: number }
      if (result.success) {
        callbacks.log(`✅ 正文章节已导入知识库（${result.chunkCount} 块）`)
      } else {
        throw new Error(`导入知识库失败: ${result.error}`)
      }
    },
  })

  // ─── 步骤 2: 本章剧情要点提取 ─────────────────────────────────────
  const notesTemplate = getPromptTemplate('generate_chapter_notes')
  if (notesTemplate) {
    steps.push({
      key: 'chapter_notes',
      label: '📋 章节剧情要点',
      critical: true,
      executor: async (callbacks) => {
        const notesBuilder = new PostProcessPromptBuilder(notesTemplate)
          .withChapterContent(draftContent)
          .withChapterNumber(chapterNumber)
          .withChapterTitle(chapterTitle)

        const cleanNotes = await callLLMForPostProcess(notesBuilder, callbacks)

        // 写入蓝图 JSON 的 notes 字段
        await ipc.invoke('db:blueprint-update-notes', chapterNumber, cleanNotes)
        callbacks.log('✅ 本章剧情要点提取完成（已写入蓝图）')
      },
    })
  }

  // ─── 步骤 3: 角色状态更新 ────────────────────────────────────────
  const cardTemplate = getPromptTemplate('update_character_cards')
  if (cardTemplate) {
    steps.push({
      key: 'character_cards',
      label: '🎭 角色状态更新',
      critical: false,
      executor: async (callbacks) => {
        // 读取现有角色卡
        const allChars = (await ipc.invoke('db:character-get-all')) as unknown as Array<Record<string, unknown>>
        const simpleCards = allChars.map((c) => ({ name: c.name, role: c.role }))

        const cardBuilder = new PostProcessPromptBuilder(cardTemplate)
          .withChapterContent(draftContent.slice(0, 5000))
          .withChapterNumber(chapterNumber)
          .withExistingCardsJson(simpleCards)

        const cardsResult = await callLLMForPostProcess(cardBuilder, callbacks, { responseFormat: { type: 'json_object' } })
        type LLMUpdateState = {
          location?: string
          powerLevel?: string
          physicalState?: string
          mentalState?: string
          keyItems?: string
          recentEvents?: string
        }

        const cardUpdates = parseJSON<{
          updates?: Array<{ name: string; currentState: LLMUpdateState }>
          newCharacters?: Array<{ name: string; role: string; currentState: LLMUpdateState }>
        }>(cardsResult)

        if (cardUpdates.updates && Array.isArray(cardUpdates.updates)) {
          for (const upd of cardUpdates.updates) {
            const dbChar = allChars.find((c) => c.name === upd.name)
            if (dbChar && upd.currentState) {
              const cs = upd.currentState
              const dbCharState = (dbChar.currentState as Record<string, unknown>) || {}
              const newState = {
                location: cs.location || (dbCharState.location as string) || '',
                powerLevel: cs.powerLevel || (dbCharState.powerLevel as string) || '',
                physicalState: cs.physicalState || (dbCharState.physicalState as string) || '',
                mentalState: cs.mentalState || (dbCharState.mentalState as string) || '',
                keyItems: cs.keyItems || (dbCharState.keyItems as string) || '',
                recentEvents: cs.recentEvents || '',
                updatedAtChapter: chapterNumber,
              }
              await ipc.invoke('db:character-update-state', upd.name, newState)
              callbacks.log(`✅ 更新角色动态状态: ${dbChar.name}`)
            }
          }
        }

        if (cardUpdates.newCharacters && Array.isArray(cardUpdates.newCharacters)) {
          let newCharCount = 0
          for (const newChar of cardUpdates.newCharacters) {
            if (allChars.some((c) => c.name === newChar.name)) continue
            newCharCount++
            const cs = newChar.currentState || {}
            await ipc.invoke('db:character-upsert', {
              name: newChar.name,
              role: newChar.role || 'supporting',
              gender: '', age: '', appearance: '', personality: '', background: '',
              abilities: '', motivation: '', relationships: '', arc: '', notes: '',
              currentState: {
                location: cs.location || '',
                powerLevel: cs.powerLevel || '',
                physicalState: cs.physicalState || '',
                mentalState: cs.mentalState || '',
                keyItems: cs.keyItems || '',
                recentEvents: cs.recentEvents || '',
                updatedAtChapter: chapterNumber,
              }
            })
          }
          if (newCharCount > 0) {
            callbacks.log(`✅ 自动提取并登记 ${newCharCount} 名新出场角色`)
          }
        }
      },
    })
  }

  // ─── 步骤 4: 文风自动学习（每5章触发一次）─────────────────────────
  if (chapterNumber % 5 === 0) {
    steps.push({
      key: 'style_analysis',
      label: '🎨 文风自动学习',
      critical: false,
      executor: async (callbacks) => {
        callbacks.log('🎨 触发文风自动学习（每5章一次）...')
        const { AnalyzeWritingStyleCommand } = await import('./analyze-style.command')
        await new AnalyzeWritingStyleCommand().execute({
          step: {} as unknown,
          context: { data: {}, cancelled: false },
          callbacks,
        })
        callbacks.log('✅ 文风分析完成，已更新配置')
      },
    })
  }

  return steps
}

// ===== 定稿命令 =====

export class FinalizeChapterCommand extends BaseWorkflowCommand<void> {
  constructor(private params: FinalizeChapterParams) {
    super()
  }

  async execute({ callbacks }: CommandExecuteParams): Promise<void> {
    const project = useProjectStore.getState().currentProject
    if (!project) throw new Error('未打开项目')

    const refinedDraftText = this.params.draftContent
    if (!refinedDraftText) throw new Error('没有定稿内容')

    callbacks.log('\n===== 开始定稿与后处理分析 =====')

    // 1. 获取对应草稿并将库内状态变更为 finalized（同时同步定稿期可能微调过的正文）
    const { parseDraftMeta } = await import('../chapter-workflow')
    const dbDraft = await parseDraftMeta(this.params.draftPath)
    if (!dbDraft) throw new Error('内部状态流转异常：无法在数据库中定位该草稿源文件或解析路径版本')

    await ipc.invoke('db:draft-update-content', dbDraft.id, refinedDraftText, refinedDraftText.length)
    await ipc.invoke('db:draft-update-status', dbDraft.id, 'finalized', refinedDraftText.length)

    // 【重要】：除了写入 DB，对于已定稿的章节需要实体化为物理文件放在根目录，供外部系统读取或备份
    const safeTitle = this.params.chapterInfo.title ? ` ${this.params.chapterInfo.title.replace(/[/\\]/g, '_')}` : ''
    const physicalPath = `${project.path}/第${this.params.chapterNumber}章${safeTitle}.txt`
    try {
      const titleLine = this.params.chapterInfo.title ? `第${this.params.chapterNumber}章 ${this.params.chapterInfo.title}\n\n` : `第${this.params.chapterNumber}章\n\n`
      const contentToWrite = titleLine + refinedDraftText.replace(/^#+ .*\n*/, '')
      await ipc.invoke('fs:write-file', physicalPath, contentToWrite)
    } catch (e) {
      callbacks.log(`⚠️ 写入根目录物理文件失败: ${String(e)}`)
    }

    callbacks.log(`✅ 定稿内容已正式写入 SQLite 数据库并同步为根目录文件 (第${this.params.chapterNumber}章${safeTitle}.txt)`)

    // 3. 通过 PostProcessPipeline 执行后处理（状态持久化 + 支持重试）
    callbacks.log('🚀 正在启动后台大模型推演系统更新全书状态...')

    const scope = getChapterFinalizeScope(this.params.chapterNumber)
    const sourceLabel = `第${this.params.chapterNumber}章定稿`
    const steps = buildFinalizePostProcessSteps(
      project,
      this.params.chapterNumber,
      this.params.chapterInfo.title,
      refinedDraftText,
    )

    await runPostProcessPipeline(project.path, scope, sourceLabel, steps, callbacks)

    callbacks.log('\n🎉 第' + this.params.chapterNumber + '章创作全流程彻底完成！')
    useProjectStore.getState().refreshFileTree()

    // 通过 EventBus 通知 ProjectService 执行定稿后的统一刷新
    const { globalEventBus } = await import('../../../shared/event-bus')
    globalEventBus.emit('FINALIZE_COMPLETE', { chapterNumber: this.params.chapterNumber })
  }
}
