import { BaseWorkflowCommand, CommandExecuteParams } from './base-command'
import { useProjectStore } from '../../../stores/project-store'
import { getPromptTemplate } from '../../prompt-templates'
import { ChapterPromptBuilder } from '../../prompts/prompt-builder'
import { ipc } from '../../ipc-client'
import { searchKB } from '../../knowledge-service'
import {
  DIR_PROMPTS
} from '../../../shared/project-paths'
import type { ChapterInfo } from '../chapter-workflow'

const CONTINUE_PROMPT_MAX_CHARS = 1600
const MIN_TARGET_COMPLETION_RATIO = 0.82
const MAX_AUTO_CONTINUE_ROUNDS = 7

export function countChineseDraftChars(text: string): number {
  return text.replace(/\s+/g, '').length
}

export function sanitizeDraftText(text: string): string {
  const cleaned = text
    .replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '')
    .replace(/^\s*[\s\S]{0,300}<\/think>\s*/i, '')
    .replace(/<\/?think>/gi, '')
    .replace(/^\s*(?:点我继续生成后续内容|继续生成后续内容|请点击继续|未完待续)\s*$/gmi, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  const paragraphs = cleaned.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
  const seen = new Set<string>()
  const deduped: string[] = []
  for (const paragraph of paragraphs) {
    const key = paragraph.replace(/\s+/g, '')
    if (key.length >= 40 && seen.has(key)) continue
    if (key.length >= 40) seen.add(key)
    deduped.push(paragraph)
  }
  return deduped.join('\n\n').trim()
}

export class GenerateDraftCommand extends BaseWorkflowCommand {

  constructor(private chapterInfo: ChapterInfo) {
    super()
  }

  async execute({ context, callbacks }: CommandExecuteParams): Promise<string> {
    const project = useProjectStore.getState().currentProject
    if (!project) throw new Error('未打开项目')

    callbacks.log('拼装章节上下文 (强类型注入中)...')

    const architecture = await this.readArchitecture(project.path)
    const projectPrompts = await this.readProjectPrompts(project.path)
    const mergedGuidance = [project.novelConfig.globalGuidance || '', projectPrompts].filter(Boolean).join('\n\n')

    const characterState = await this.readCharacterStates(project.path)
    let futureBlueprintsStr = '（无后续蓝图）'
    try {
      const { loadDirectoryBlueprints } = await import('../directory-workflow')
      const allBlueprints = await loadDirectoryBlueprints()
      const futureBlueprintsArr = allBlueprints.filter(
        b => b.chapterNumber > this.chapterInfo.chapterNumber && b.chapterNumber <= this.chapterInfo.chapterNumber + 5
      )
      if (futureBlueprintsArr.length > 0) {
        futureBlueprintsStr = futureBlueprintsArr.map(b => `第${b.chapterNumber}章 ${b.title}：${b.keyEvents}`).join('\n')
      }
    } catch { /* 忽略 */ }

    const isFirstChapter = this.chapterInfo.chapterNumber === 1
    const templateKey = isFirstChapter ? 'first_chapter_draft' : 'next_chapter_draft'
    const template = getPromptTemplate(templateKey)
    if (!template) throw new Error(`未找到模板: ${templateKey}`)

    // ==========================================
    // Prompt 构建——按「稳定前缀 → 可变后缀」排列
    // 以最大化 LLM 上下文缓存命中率
    // ==========================================
    const promptBuilder = new ChapterPromptBuilder(template)
      // ---- 缓存命中区（跨章稳定，前缀对齐）----
      .withArchitecture(architecture)
      .withGlobalGuidance(mergedGuidance)
      .withWritingStyle(project.novelConfig.writingStyle || '')
      .withNovelConfig(project.novelConfig)
      .withWordNumber(project.novelConfig.wordsPerChapter)

    if (!isFirstChapter) {
      // 从蓝图 JSON 的 notes 字段读取章节要点时间线（按序拼装，利于前缀缓存）
      const chapterTimeline = await this.readChapterNotesTimeline(project.path, this.chapterInfo.chapterNumber)
      callbacks.log(`  📋 已加载章节要点时间线（${chapterTimeline.length} 字）`)

      let previousEnding = ''
      try {
        const prevNum = this.chapterInfo.chapterNumber - 1
        const meta = await ipc.invoke('db:draft-get-finalized', prevNum)
        if (meta) {
          const full = await ipc.invoke('db:draft-get-full', meta.id)
          if (full?.content) previousEnding = full.content.slice(-1000)
        }
      } catch { /* 忽略 */ }

      let filteredContext = ''
      try {
        callbacks.log('  🔍 检索知识库相关片段...')
        let searchQuery = `${this.chapterInfo.title} ${this.chapterInfo.keyEvents} ${this.chapterInfo.characters.join(' ')}`
        if (this.chapterInfo.knowledgeQueryHint?.trim()) {
          searchQuery += ` ${this.chapterInfo.knowledgeQueryHint.trim()}`
          callbacks.log(`  📌 追加用户检索关键词：${this.chapterInfo.knowledgeQueryHint.trim()}`)
        }
        const results = await searchKB(searchQuery, 5)
        filteredContext = results.length > 0
          ? results.map((r: { fileName: string; score: number; text: string }, i: number) => `[${i + 1}] (${r.fileName}, 相关度 ${(r.score * 100).toFixed(0)}%)\n${r.text}`).join('\n\n')
          : '（知识库中无相关内容）'
      } catch {
        filteredContext = '（知识库检索不可用）'
      }

      promptBuilder
        // ---- 缓存命中区续（要点时间线按序追加，前缀对齐）----
        .withGlobalSummary(chapterTimeline)
        .withCharacterStates(characterState)
        // ---- 缓存失效区（逐章变化）----
        .withPreviousEnding(previousEnding || '（无前文）')
        .withChapterInfo(this.chapterInfo)
        .withFutureBlueprints(futureBlueprintsStr)
        .withFilteredContext(filteredContext)
        .withShortSummary('')
        .withUserGuidance(this.chapterInfo.userGuidance?.trim() || '（无微操指导）')
    }

    // Token 预算管控：中文约 1.5 字符/token，预留 4K 给输出
    const prompt = promptBuilder.build()
    const estimatedTokens = Math.ceil(prompt.length / 1.5)
    const TOKEN_BUDGET = 28000
    if (estimatedTokens > TOKEN_BUDGET) {
      callbacks.log(`⚠️ Prompt 预估 ${estimatedTokens} tokens，超出预算 ${TOKEN_BUDGET}，请考虑精简上下文`)
    }

    callbacks.log('调用 AI 生成章节草稿...')

    const targetChars = Math.max(0, Number(project.novelConfig.wordsPerChapter) || 0)
    const draftText = await this.callLLMWithBuilder(promptBuilder, callbacks, {
      maxTokens: this.getDraftMaxTokens(targetChars),
      temperature: 0.88,
      thinking: false,
    })
    const cleanDraftText = await this.extendDraftIfNeeded({
      initialDraft: sanitizeDraftText(this.stripThinkingTags(draftText)),
      targetChars,
      callbacks,
      context,
      systemRole: promptBuilder.getSystemRole(),
      chapterInfo: this.chapterInfo,
      futureBlueprints: futureBlueprintsStr,
      globalGuidance: mergedGuidance,
      writingStyle: project.novelConfig.writingStyle || '',
    })

    // 落于数据库
    const nextVersion: number = await ipc.invoke('db:draft-next-version', this.chapterInfo.chapterNumber)
    const createResult = await ipc.invoke('db:draft-create', {
      chapterNumber: this.chapterInfo.chapterNumber,
      version: nextVersion,
      source: 'write',
      content: cleanDraftText,
      wordCount: cleanDraftText.length,
    })

    const pseudoPath = createResult.id ? `vela://draft/${createResult.id}` : `vela://draft/ch${this.chapterInfo.chapterNumber}/v${nextVersion}`

    context.data.draft = cleanDraftText
    context.data.draftContent = cleanDraftText
    context.data.draftPath = pseudoPath
    context.data.chapterNumber = this.chapterInfo.chapterNumber
    context.data.chapterInfo = this.chapterInfo
    context.data.mergedGuidance = mergedGuidance
    context.data.shortSummary = ''

    useProjectStore.getState().refreshFileTree()
    try {
      const { useDraftStore } = await import('../../../stores/draft-store')
      await useDraftStore.getState().loadAllDrafts()
    } catch { /* 忽略 */ }

    try {
      const { useEditorStore } = await import('../../../stores/editor-store')
      useEditorStore.getState().openFile({
        id: pseudoPath,
        name: `第${this.chapterInfo.chapterNumber}章 ${this.chapterInfo.title} v${nextVersion}`,
        type: 'chapter',
        filePath: pseudoPath,
        content: cleanDraftText,
      })
    } catch { /* 忽略 */ }

    callbacks.log(`✅ 草稿已自动入库保存为版本 v${nextVersion}（${cleanDraftText.length} 字）`)
    return cleanDraftText
  }

  private getDraftMaxTokens(targetChars: number): number {
    if (targetChars >= 5000) return 2600
    return 2600
  }

  private shouldAutoContinue(currentText: string, targetChars: number, rounds: number): boolean {
    if (targetChars < 4500) return false
    if (rounds >= MAX_AUTO_CONTINUE_ROUNDS) return false
    return countChineseDraftChars(currentText) < Math.floor(targetChars * MIN_TARGET_COMPLETION_RATIO)
  }

  private async extendDraftIfNeeded(params: {
    initialDraft: string
    targetChars: number
    callbacks: CommandExecuteParams['callbacks']
    context: CommandExecuteParams['context']
    systemRole: string
    chapterInfo: ChapterInfo
    futureBlueprints: string
    globalGuidance: string
    writingStyle: string
  }): Promise<string> {
    let draft = params.initialDraft
    let rounds = 0

    while (this.shouldAutoContinue(draft, params.targetChars, rounds)) {
      if (params.context.cancelled) break
      rounds += 1
      const currentChars = countChineseDraftChars(draft)
      params.callbacks.log(`  自动续写第 ${rounds} 段：当前约 ${currentChars}/${params.targetChars} 字`)

      const remaining = Math.max(1200, params.targetChars - currentChars)
      const continuationPrompt = `请无缝续写当前章节正文。

【硬性要求】
- 只输出新增正文，不要复述已写内容。
- 从“已写正文末尾”自然接下去，保持同一场景逻辑或合理转场。
- 本次续写约 ${Math.min(2600, remaining)} 字；如果无法达到，停在自然段落末尾。
- 不要输出标题、解释、总结、Markdown、思考过程或“点我继续”。
- 避免重复已写正文中的整句、整段、动作链和意象。
- 不提前写后续章节，只完成本章蓝图允许的内容。

【本章蓝图】
${JSON.stringify(params.chapterInfo, null, 2)}

【后续章节大纲预告】
${params.futureBlueprints}

【全局写作要求】
${params.globalGuidance}

【文风要求】
${params.writingStyle || '（无）'}

【已写正文末尾】
${draft.slice(-CONTINUE_PROMPT_MAX_CHARS)}`

      const addition = await this.callLLM(
        continuationPrompt,
        params.systemRole,
        params.callbacks,
        { maxTokens: this.getDraftMaxTokens(params.targetChars), temperature: 0.88, thinking: false },
        params.context
      )
      const beforeChars = countChineseDraftChars(draft)
      draft = sanitizeDraftText(`${draft}\n\n${sanitizeDraftText(this.stripThinkingTags(addition))}`)
      const afterChars = countChineseDraftChars(draft)
      if (afterChars - beforeChars < 300) {
        params.callbacks.log('  自动续写增量过短，停止继续请求')
        break
      }
    }

    return draft
  }

  // --- 抽取自原文件的辅助方法 ---
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private async readArchitecture(_projectPath: string): Promise<string> {
    const core = await ipc.invoke('db:project-core-get')
    const parts: string[] = []
    if (core?.premise) parts.push(core.premise.trim())
    if (core?.charactersArch) parts.push(core.charactersArch.trim())
    if (core?.worldbuilding) parts.push(core.worldbuilding.trim())
    if (core?.synopsis) parts.push(core.synopsis.trim())
    return parts.join('\n\n---\n\n')
  }

  private async readProjectPrompts(projectPath: string): Promise<string> {
    try {
      const files = await ipc.invoke('fs:list-dir', `${projectPath}/${DIR_PROMPTS}`)
      const mdFiles = files.filter((f: { isDir: boolean; name: string }) => !f.isDir && f.name.endsWith('.md'))
      if (mdFiles.length === 0) return ''
      const parts: string[] = []
      for (const f of mdFiles) {
        const result = await ipc.invoke('fs:read-file', f.path)
        if (result.success && result.content.trim()) {
          parts.push(`## 项目专属指导（${f.name.replace(/\.md$/, '')}）\n${result.content.trim()}`)
        }
      }
      return parts.join('\n\n')
    } catch { return '' }
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private async readCharacterStates(_projectPath: string): Promise<string> {
    try {
      const allChars = await ipc.invoke('db:character-get-all')
      const states: string[] = []
      for (const card of allChars) {
        if (card.name && card.currentState) {
          const cs = card.currentState
          states.push(
            `${card.name}（${card.role || '未知'}）| ` +
            `境界：${cs.powerLevel || '未知'} | ` +
            `位置：${cs.location || '未知'} | ` +
            `身体：${cs.physicalState || '正常'} | ` +
            `心理：${cs.mentalState || '正常'} | ` +
            `道具：${cs.keyItems || '无'} | ` +
            `最近：第${cs.updatedAtChapter || 0}章 ${cs.recentEvents || ''}`
          )
        }
      }
      return states.length > 0 ? `【角色状态档案】\n${states.join('\n')}` : '（暂无角色状态档案）'
    } catch { return '（角色状态档案读取失败）' }
  }

  /**
   * 从蓝图 JSON 的 notes 字段读取章节要点时间线。
   * 近 5 章完整收录；更早期仅保留标题行，控制总量 ≤ 3000 字。
   * 按序拼装保证前缀稳定，最大化 LLM 上下文缓存命中。
   */
  private async readChapterNotesTimeline(_projectPath: string, currentChapter: number): Promise<string> {
    const FULL_WINDOW = 5  // 近 N 章完整收录
    const MAX_CHARS = 3000 // 总量上限
    const lines: string[] = []

    for (let i = 1; i < currentChapter; i++) {
      try {
        const bp = await ipc.invoke('db:blueprint-get', i)
        if (!bp) continue
        const isRecent = i >= currentChapter - FULL_WINDOW

        if (isRecent && bp.notes?.trim()) {
          // 近 N 章：完整收录要点
          lines.push(`【第${i}章 ${bp.title || ''}】\n${bp.notes.trim()}`)
        } else {
          // 远期章节：仅保留标题行（节省 Token）
          lines.push(`【第${i}章 ${bp.title || ''}】`)
        }
      } catch { /* 忽略单章读取失败 */ }
    }

    // Token 预算控制：超限时从最早的完整要点开始精简
    let result = lines.join('\n\n')
    if (result.length > MAX_CHARS) {
      // 保留近章完整内容，远期章节已经是标题行了
      result = result.slice(-MAX_CHARS)
    }

    return result || '（无章节要点）'
  }
}
