import { BaseWorkflowCommand, CommandExecuteParams } from './base-command'
import { useProjectStore } from '../../../stores/project-store'
import type { NovelConfig } from '../../../shared/ipc-channels'

/**
 * 支持的单字段生成 Key
 * 每个 key 对应 NovelConfig 中的一个文本字段
 */
export type GeneratableField =
  | 'coreOutline'
  | 'worldSetting'
  | 'goldenFinger'
  | 'protagonistProfile'
  | 'globalGuidance'
  | 'writingStyle'

/** 字段中文标签映射 */
const FIELD_LABELS: Record<GeneratableField, string> = {
  coreOutline: '核心大纲',
  worldSetting: '世界观设定',
  goldenFinger: '金手指/核心卖点',
  protagonistProfile: '主角人设',
  globalGuidance: '全局写作要求',
  writingStyle: '文风配置',
}

/**
 * 单字段 AI 生成命令
 * 根据已有的 NovelConfig 上下文，只生成指定字段的内容
 */
export class GenerateFieldCommand extends BaseWorkflowCommand<string> {
  constructor(private fieldKey: GeneratableField) {
    super()
  }

  async execute({ callbacks }: CommandExecuteParams): Promise<string> {
    const project = useProjectStore.getState().currentProject
    if (!project) throw new Error('未打开项目')

    const config = project.novelConfig
    const label = FIELD_LABELS[this.fieldKey]

    callbacks.log(`🧠 正在为「${label}」生成内容...`)

    // 构建上下文摘要（已填写的字段作为参考）
    const context = this.buildContext(config)
    // 构建针对性 prompt
    const prompt = this.buildPrompt(config, context)
    const systemPrompt = '你是一位入行十年的顶尖网文主编与白金大神作家，擅长精准设计小说的各项核心配置。'

    const result = await this.callLLM(prompt, systemPrompt, callbacks)
    const cleanResult = this.stripThinkingTags(result).trim()

    if (!cleanResult) {
      callbacks.log(`⚠️ 「${label}」生成返回空结果`)
      return ''
    }

    // 写入 NovelConfig
    const { updateNovelConfig, saveProject } = useProjectStore.getState()
    updateNovelConfig({ [this.fieldKey]: cleanResult })
    await saveProject()
    callbacks.log(`✅ 「${label}」已生成并保存`)

    return cleanResult
  }

  /** 构建已有配置的上下文摘要 */
  private buildContext(config: NovelConfig): string {
    const parts: string[] = []
    if (config.genre) parts.push(`- 类型：${config.genre}`)
    if (config.subGenre) parts.push(`- 细分类型：${config.subGenre}`)
    if (config.targetAudience) parts.push(`- 目标受众：${config.targetAudience}`)
    if (config.totalChapters) parts.push(`- 总章数：${config.totalChapters} 章`)
    if (config.wordsPerChapter) parts.push(`- 每章字数：${config.wordsPerChapter} 字`)
    if (config.coreOutline?.trim() && this.fieldKey !== 'coreOutline')
      parts.push(`- 核心大纲：${config.coreOutline.slice(0, 500)}`)
    if (config.worldSetting?.trim() && this.fieldKey !== 'worldSetting')
      parts.push(`- 世界观设定：${config.worldSetting.slice(0, 500)}`)
    if (config.goldenFinger?.trim() && this.fieldKey !== 'goldenFinger')
      parts.push(`- 金手指体系：${config.goldenFinger.slice(0, 500)}`)
    if (config.protagonistProfile?.trim() && this.fieldKey !== 'protagonistProfile')
      parts.push(`- 主角人设：${config.protagonistProfile.slice(0, 500)}`)
    if (config.globalGuidance?.trim() && this.fieldKey !== 'globalGuidance')
      parts.push(`- 全局写作要求：${config.globalGuidance.slice(0, 500)}`)
    if (config.referenceWorks?.trim())
      parts.push(`- 参考作品：${config.referenceWorks}`)
    if (config.writingStyle?.trim() && this.fieldKey !== 'writingStyle')
      parts.push(`- 文风描述：${config.writingStyle.slice(0, 300)}`)
    return parts.length > 0 ? parts.join('\n') : '（尚未填写任何配置）'
  }

  /** 根据 fieldKey 构建针对性 prompt */
  private buildPrompt(config: NovelConfig, context: string): string {
    const fieldPrompts: Record<GeneratableField, string> = {
      coreOutline: `请为这部小说生成一份【核心大纲】。
要求：不少于150字，包含主角的致命危机/开局困境、必须完成的核心目标、终极大危机、主要爽点起伏。
大纲应具有强烈的戏剧张力和商业吸引力，让编辑一看就知道这本书的核心卖点。`,

      worldSetting: `请为这部小说生成一份【世界观/初始设定】。
要求：描述故事发生的背景、时代、力量体系、社会结构。
包含：物理维度特征、权力结构与断层、核心资源争夺机制。
所有设定必须自带冲突点，能直接驱动情节发展。`,

      goldenFinger: `请为这部小说生成一份【金手指/核心卖点体系】。
要求：详细描述主角的差异化优势。
包含：获取方式、具体功能与核心机制、进阶成长路径、副作用/限制/代价。
金手指必须与世界观规则产生有趣的交互，而非万能型。`,

      protagonistProfile: `请为这部小说生成一份【主角人设档案】。
要求：包含表面伪装标签与真实性格、极具反差的性格弱点。
核心驱动力需要区分物质目标（显性）和深层灵魂渴望（隐性）。
主角必须有清晰的成长弧光起点和终点。`,

      globalGuidance: `请为这部小说生成一份【全局写作要求】。
要求：严格基于${config.totalChapters || 100}章的实际规模推算。
包含：前/中/后期各占多少章、小/中/大高潮的具体章节频率。
明确写作风格要求、核心禁忌/毒点、节奏控制策略。`,

      writingStyle: `请为这部小说设计一份【文风配置指南】。
要求：不少于100字，这份指南将指导 AI 写稿和修稿时的文风遵循。
请从以下维度给出具体、可操作的风格要求：
1. 叙述节奏：整体快慢偏好、场景切换频率、段落长短
2. 描写密度：环境/动作/心理描写的比重偏好
3. 对话风格：对话比例、口语化程度、是否使用方言
4. 用词偏好：古风/现代/专业术语的倾向
5. 情感基调：热血/冷峻/诙谐/沉重/轻松
6. 标志性手法：推荐的修辞手法、过渡技巧
请根据本书的类型（${config.genre || '未指定'}）和受众（${config.targetAudience || '未指定'}）推荐最匹配的写作风格。`,
    }

    return `以下是这部小说的已有配置信息：
${context}

${fieldPrompts[this.fieldKey]}

【输出要求】
- 直接输出纯文本内容，不要使用 JSON 格式
- 不要添加任何前导语、解释或客套话
- 不要使用 Markdown 标题（#），可以使用换行分段`
  }
}
