import { BaseWorkflowCommand, CommandExecuteParams } from './base-command'
import { useProjectStore } from '../../../stores/project-store'
import { getPromptTemplate } from '../../prompt-templates'
import { DirectoryPromptBuilder } from '../../prompts/prompt-builder'
import {
  DirectoryWorkflowParams,
  ChapterBlueprint,
  assertBlueprintCoverage,
  parseTextBlueprintsStrict,
  saveAllBlueprints,
  verifyBlueprintsPersisted,
} from '../directory-workflow'

export class GenerateDirectoryCommand extends BaseWorkflowCommand<ChapterBlueprint[]> {
  constructor(private params: DirectoryWorkflowParams) {
    super()
  }

  async execute({ context, callbacks }: CommandExecuteParams): Promise<ChapterBlueprint[]> {
    const project = useProjectStore.getState().currentProject
    if (!project) throw new Error('未打开项目')

    const architecture = context.data.architecture as string
    const existingBlueprints = (context.data.existingBlueprints || []) as ChapterBlueprint[]

    const totalChapters = project.novelConfig.totalChapters
    const globalGuidance = project.novelConfig.globalGuidance || ''
    const genre = project.novelConfig.genre || ''

    let startChapter = 1
    let endChapter = totalChapters

    if (this.params.mode === 'append') {
      startChapter = this.params.startChapter || (existingBlueprints.length + 1)
      if (this.params.count && this.params.count > 0) {
        endChapter = startChapter + this.params.count - 1
      }
    } else if (this.params.count && this.params.count > 0) {
      endChapter = Math.min(this.params.count, totalChapters)
    }

    callbacks.log(`生成第 ${startChapter}–${endChapter} 章蓝图...`)

    // 从当前默认模型获取 maxTokens，动态计算每批次章节数
    const llmStore = (await import('../../../stores/llm-store')).useLLMStore.getState()
    const defaultModel = llmStore.models.find(m => m.id === llmStore.defaultModelId)
    const modelMaxTokens = defaultModel?.maxTokens || 4096
    const outputBudget = Math.floor(modelMaxTokens * 0.6)  // 预留 40% 给 prompt + 思考
    const tokensPerChapter = 200
    const batchSize = Math.min(50, Math.max(5, Math.floor(outputBudget / tokensPerChapter)))

    const newBlueprints: ChapterBlueprint[] = []
    // 使用游标追踪生成进度，支持 AI 超额返回时智能跳过后续批次
    let cursor = startChapter

    while (cursor <= endChapter) {
      if (context.cancelled) { callbacks.log('已取消'); break }

      const batchEnd = Math.min(cursor + batchSize - 1, endChapter)
      callbacks.log(`  正在生成第 ${cursor}–${batchEnd} 章...`)

      let prompt: string
      if (cursor === 1 && this.params.mode === 'full') {
        const template = getPromptTemplate('chapter_blueprint')
        if (!template) throw new Error('模板丢失')
        prompt = new DirectoryPromptBuilder(template)
          .withNovelArchitecture(architecture)
          .withNumberOfChapters(endChapter)
          .withGlobalGuidance(globalGuidance)
          .withGenre(genre)
          .withPacingGuidance((context.data.pacingGuidance as string) || '')
          .build()
      } else {
        const template = getPromptTemplate('chapter_blueprint_chunk')
        if (!template) throw new Error('模板丢失')

        const prevAll = [...existingBlueprints, ...newBlueprints]
        const chapterList = prevAll.slice(-100).map(c => `第${c.chapterNumber}章 ${c.title}：${c.keyEvents}`).join('\n')

        prompt = new DirectoryPromptBuilder(template)
          .withNovelArchitecture(architecture)
          .withChapterList(chapterList || '（首批生成）')
          .withNumberOfChapters(totalChapters)
          .withN(cursor)
          .withM(batchEnd)
          .withGlobalGuidance(globalGuidance)
          .withGenre(genre)
          .withPacingGuidance((context.data.pacingGuidance as string) || '')
          .build()
      }

      callbacks.setProgress(Math.round(((cursor - startChapter) / (endChapter - startChapter + 1)) * 90))

      // systemRole 由模板定义，不再硬编码
      const systemRole = getPromptTemplate('chapter_blueprint')?.systemRole || '你是一位经验丰富的网文架构师。'
      const resultText = await this.callLLM(prompt, systemRole, callbacks, {
        responseFormat: { type: 'json_object' },
        thinking: false,
        maxTokens: Math.min(modelMaxTokens, 4096),
        temperature: 0.78,
      })

      // ★ 关键修复：接受 AI 返回的从 cursor 到 endChapter 范围内的所有有效章节
      // AI 可能一次性返回超出本批次（batchEnd）的章节，全部保留，避免浪费和重复 LLM 请求
      const parsed = parseTextBlueprintsStrict(resultText, cursor, endChapter)
      const actualMaxChapter = Math.max(...parsed.map(p => p.chapterNumber))
      assertBlueprintCoverage(parsed, cursor, actualMaxChapter)
      newBlueprints.push(...parsed)

      // ==== 批次入库 ====
      if (parsed.length > 0) {
        await saveAllBlueprints(parsed)
        await verifyBlueprintsPersisted(parsed, { startChapter: cursor, endChapter: actualMaxChapter })
        useProjectStore.getState().refreshFileTree()
      }

      // 计算本次实际生成到的最大章节号，推进游标到已生成的最后一章之后
      callbacks.log(`  ✅ 第 ${cursor}–${actualMaxChapter} 章完成（${parsed.length} 章）并已保存入库`)

      cursor = actualMaxChapter + 1
    }

    context.data.newBlueprints = newBlueprints
    context.data.existingBlueprints = existingBlueprints

    callbacks.log(`✅ 共生成 ${newBlueprints.length} 章蓝图`)
    return newBlueprints
  }
}
