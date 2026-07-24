import { BaseWorkflowCommand, CommandExecuteParams } from './base-command'
import { useProjectStore } from '../../../stores/project-store'
import { getPromptTemplate } from '../../prompt-templates'
import { BasePromptBuilder } from '../../prompts/prompt-builder'
import { ipc } from '../../ipc-client'
import type { ImportedChapter } from './import-novel.command'

export interface AnalyzeWritingStyleOptions {
  sampleText?: string
  sampleTexts?: string[]
  chapters?: ImportedChapter[]
}

/**
 * 文风分析命令
 * 从已写章节中采样正文，调用 AI 提炼作者文风特征，
 * 结果写入 NovelConfig.writingStyle 以锚定后续生成/修稿。
 */
export class AnalyzeWritingStyleCommand extends BaseWorkflowCommand<string> {
  constructor(private options: AnalyzeWritingStyleOptions = {}) {
    super()
  }

  async execute({ callbacks }: CommandExecuteParams): Promise<string> {
    const project = useProjectStore.getState().currentProject
    if (!project) throw new Error('未打开项目')

    const sampleTexts = this.collectProvidedSamples()

    if (sampleTexts.length > 0) {
      callbacks.log(`正在分析导入文本样本文风（${sampleTexts.length} 段）...`)
    } else {
      callbacks.log('正在采样已有章节正文...')

      // 采样策略：取最近 5 章的正文（从数据库查询）
      try {
        const maxChap = await ipc.invoke('db:draft-get-max-finalized-chapter')
        if (maxChap <= 0) {
          callbacks.log('无已写章节，无法分析文风')
          return ''
        }

        const startChap = Math.max(1, maxChap - 4)
        for (let c = maxChap; c >= startChap; c--) {
          const meta = await ipc.invoke('db:draft-get-finalized', c)
          if (meta) {
            const full = await ipc.invoke('db:draft-get-full', meta.id)
            if (full?.content?.trim()) {
              sampleTexts.push(full.content.trim().slice(0, 2000))
            }
          }
        }
        callbacks.log(`  已采样 ${sampleTexts.length} 章正文`)
      } catch {
        callbacks.log('提取定稿内容失败')
        return ''
      }
    }

    if (sampleTexts.length === 0) {
      callbacks.log('采样文本为空，跳过文风分析')
      return ''
    }

    const template = getPromptTemplate('analyze_writing_style')
    if (!template) throw new Error('未找到文风分析模板')

    const sampleText = sampleTexts.join('\n\n---\n\n')
    const prompt = new BasePromptBuilder(template)
      // 使用 protected variables 需要通过子类或反射，这里使用 build 前手动设置
      ; (prompt as unknown as { variables: { sample_text: string } }).variables = { sample_text: sampleText }
    const finalPrompt = prompt.build()

    callbacks.log('调用 AI 分析文风特征...')
    const result = await this.callLLM(
      finalPrompt,
      template.systemRole || '你是一位资深的文学评论家和网文研究者。',
      callbacks,
    )

    const cleanResult = this.stripThinkingTags(result).trim()
    if (!cleanResult) {
      callbacks.log('文风分析返回空结果')
      return ''
    }

    // 先持久化，成功后再更新内存态，避免 DB 保存失败时 UI 残留未落库的文风。
    const saveResult = await ipc.invoke('db:project-core-update', { writingStyle: cleanResult })
    if (!saveResult.success) {
      throw new Error(saveResult.error || '文风特征保存失败')
    }
    const { updateNovelConfig } = useProjectStore.getState()
    updateNovelConfig({ writingStyle: cleanResult })
    callbacks.log('文风特征已保存到小说配置')

    return cleanResult
  }

  private collectProvidedSamples(): string[] {
    const samples: string[] = []
    if (this.options.sampleText?.trim()) {
      samples.push(this.options.sampleText.trim().slice(0, 4000))
    }
    if (this.options.sampleTexts) {
      for (const sample of this.options.sampleTexts) {
        if (sample.trim()) samples.push(sample.trim().slice(0, 4000))
      }
    }
    if (this.options.chapters) {
      const selected = this.pickRepresentativeChapters(this.options.chapters)
      for (const chapter of selected) {
        if (chapter.content.trim()) {
          samples.push(`第${chapter.number}章 ${chapter.title}\n${chapter.content.trim().slice(0, 2000)}`)
        }
      }
    }
    return samples
  }

  private pickRepresentativeChapters(chapters: ImportedChapter[]): ImportedChapter[] {
    if (chapters.length <= 5) return chapters
    const picked = new Map<number, ImportedChapter>()
    for (const chapter of chapters.slice(0, 3)) picked.set(chapter.number, chapter)
    for (const chapter of chapters.slice(-2)) picked.set(chapter.number, chapter)
    return Array.from(picked.values()).sort((a, b) => a.number - b.number)
  }
}
