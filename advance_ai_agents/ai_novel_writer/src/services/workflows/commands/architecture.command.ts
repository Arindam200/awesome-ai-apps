import { BaseWorkflowCommand, CommandExecuteParams } from './base-command'
import { useProjectStore } from '../../../stores/project-store'
import { getPromptTemplate } from '../../prompt-templates'
import { ArchitecturePromptBuilder } from '../../prompts/prompt-builder'
import { ipc } from '../../ipc-client'

import type { NovelConfig } from '../../../shared/ipc-channels'

// --- 基础工具库 ---

interface PartialArchData {
  premise_result?: string
  character_dynamics_result?: string
  character_state_result?: string
  world_building_result?: string
  synopsis_result?: string
}

async function loadPartialData(projectPath: string): Promise<PartialArchData> {
  const result = await ipc.invoke('fs:read-json', `${projectPath}/.vela/partial_arch.json`)
  if (result.success && result.data) return result.data as PartialArchData
  return {}
}

async function savePartialData(projectPath: string, data: PartialArchData): Promise<void> {
  await ipc.invoke('fs:write-json', `${projectPath}/.vela/partial_arch.json`, data)
}

function getNovelConfig(): { project: NonNullable<ReturnType<typeof useProjectStore.getState>['currentProject']>; config: NovelConfig } {
  const project = useProjectStore.getState().currentProject
  if (!project) throw new Error('未打开项目')
  return { project, config: project.novelConfig }
}

function stripThinkingTags(text: string): string {
  return text.replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '').trim()
}

async function writeArchToDb(key: 'premise' | 'charactersArch' | 'worldbuilding' | 'synopsis', content: string): Promise<void> {
  const cleanContent = stripThinkingTags(content)
  await ipc.invoke('db:project-core-update', { [key]: cleanContent })

  // 通知 UI 层实时刷新架构完成状态
  const { globalEventBus } = await import('../../../shared/event-bus')
  globalEventBus.emit('ARCH_FILE_UPDATED', { fileName: `${key}.md` })
}

// --- 独立命令类 ---

export class GenerateConfigCommand extends BaseWorkflowCommand<string> {
  constructor(private idea: string, private totalChapters: number, private wordsPerChapter: number, private onGenerated: (config: Partial<NovelConfig>) => void) {
    super()
  }

  async execute({ callbacks }: CommandExecuteParams): Promise<string> {
    callbacks.log('正在调度配置专家 AI，准备解析您的脑洞...')

    const template = getPromptTemplate('generate_global_config')
    if (!template) throw new Error('未找到 generate_global_config 模板')

    const promptBuilder = new ArchitecturePromptBuilder(template)
      .withUserIdea(this.idea)
      .withNumberOfChapters(this.totalChapters)
      .withWordNumber(this.wordsPerChapter)

    const resultRaw = await this.callLLMWithBuilder(
      promptBuilder,
      callbacks,
      { responseFormat: { type: 'json_object' }, thinking: false, maxTokens: 4096, temperature: 0.75 }
    )

    callbacks.log('解析完成，正在应用到项目配置...')
    try {
      const parsed = this.parseJSON<Partial<NovelConfig>>(resultRaw)

      // 防御：LLM 常常将长文本字段错误地生成为对象或数组
      const stringifyField = (val: unknown) => {
        if (!val) return ''
        if (typeof val === 'string') return val
        if (Array.isArray(val)) return val.join('\n')
        if (typeof val === 'object') return JSON.stringify(val, null, 2)
        return String(val)
      }

      if (parsed.coreOutline !== undefined) parsed.coreOutline = stringifyField(parsed.coreOutline)
      if (parsed.worldSetting !== undefined) parsed.worldSetting = stringifyField(parsed.worldSetting)
      if (parsed.goldenFinger !== undefined) parsed.goldenFinger = stringifyField(parsed.goldenFinger)
      if (parsed.protagonistProfile !== undefined) parsed.protagonistProfile = stringifyField(parsed.protagonistProfile)
      if (parsed.globalGuidance !== undefined) parsed.globalGuidance = stringifyField(parsed.globalGuidance)
      if (parsed.referenceWorks !== undefined) parsed.referenceWorks = stringifyField(parsed.referenceWorks)
      if (parsed.writingStyle !== undefined) parsed.writingStyle = stringifyField(parsed.writingStyle)

      if (parsed.totalChapters !== undefined) parsed.totalChapters = parseInt(String(parsed.totalChapters)) || 100
      if (parsed.wordsPerChapter !== undefined) parsed.wordsPerChapter = parseInt(String(parsed.wordsPerChapter)) || 3000

      this.onGenerated(parsed)
      const saved = await useProjectStore.getState().saveProject()

      if (saved) {
        callbacks.log('✅ AI 配置生成并保存成功，请检查各字段后点击「生成架构」')
      } else {
        callbacks.log('✅ AI 配置生成成功，请检查各字段后点击「立即保存」')
      }
    } catch (e) {
      throw new Error('AI 返回的内容无法解析为 JSON，请重试或缩短输入。详细信息: ' + String(e))
    }
    callbacks.setProgress(100)
    return '生成的配置已成功应用！'
  }
}

export class GenerateCoreSeedCommand extends BaseWorkflowCommand<string> {
  async execute({ context, callbacks }: CommandExecuteParams): Promise<string> {
    const { project, config } = getNovelConfig()
    callbacks.log('生成故事前提...')

    const template = getPromptTemplate('premise')
    if (!template) throw new Error('未找到 premise 模板')

    const promptBuilder = new ArchitecturePromptBuilder(template)
      .withGenre(config.genre)
      .withSubGenre(config.subGenre || config.genre)
      .withTopic(config.coreOutline || '（未填写）')
      .withTargetAudience(config.targetAudience)
      .withNumberOfChapters(config.totalChapters)
      .withWordNumber(config.wordsPerChapter)
      .withCoreSetting(config.worldSetting || '（未填写）')
      .withGoldenFinger(config.goldenFinger || '（未填写）')
      .withProtagonistProfile(config.protagonistProfile || '（未填写）')
      .withGlobalGuidance(config.globalGuidance || '（未填写）')
      .withStepGuidance(((context.data.stepGuidance as Record<string, string>) || {}).premise || '')
      .withReferenceWorks(config.referenceWorks || '')

    const result = await this.callLLMWithBuilder(promptBuilder, callbacks, undefined, context)
    if (!result.trim()) throw new Error('故事前提生成失败，AI 返回空内容')
    if (context.cancelled) throw new Error('工作流已取消')

    const content = `# 故事前提\n\n${result}\n`
    await writeArchToDb('premise', content)

    const partial = (context.data.partial as PartialArchData) || await loadPartialData(project.path)
    partial.premise_result = result
    await savePartialData(project.path, partial)
    context.data.partial = partial

    callbacks.log(`✅ 故事前提已生成并写入数据库`)
    return result
  }
}

export class GenerateCharactersCommand extends BaseWorkflowCommand<string> {
  async execute({ context, callbacks }: CommandExecuteParams): Promise<string> {
    const { project, config } = getNovelConfig()

    const core = await ipc.invoke('db:project-core-get')
    const premise_result = core?.premise || ''

    if (!premise_result || premise_result.includes('待生成') || premise_result.length < 50) {
      throw new Error('故事前提尚未生成或内容不完整，请返回勾选生成')
    }

    callbacks.log('生成角色图谱...')
    const template = getPromptTemplate('character_dynamics')
    if (!template) throw new Error('未找到 character_dynamics 模板')

    const promptBuilder = new ArchitecturePromptBuilder(template)
      .withCoreSeed(premise_result)
      .withGenre(config.genre)
      .withProtagonistProfile(config.protagonistProfile || '（未填写）')
      .withGoldenFinger(config.goldenFinger || '（未填写）')
      .withWorldBuilding(config.worldSetting || '（未填写）')
      .withNumberOfChapters(config.totalChapters)
      .withGlobalGuidance(config.globalGuidance || '（未填写）')
      .withStepGuidance(((context.data.stepGuidance as Record<string, string>) || {}).characters || '')
      .withReferenceWorks(config.referenceWorks || '')

    const result = await this.callLLMWithBuilder(promptBuilder, callbacks, undefined, context)
    if (!result.trim()) throw new Error('角色图谱生成失败')
    if (context.cancelled) throw new Error('工作流已取消')

    await writeArchToDb('charactersArch', `# 角色图谱\n\n${result}\n`)

    callbacks.log('📇 正在启动角色卡自动提取流水线...')
    const { runArchCharacterExtract } = await import('../architecture-workflow')
    runArchCharacterExtract(project.path, result, config.genre)

    const partial = (context.data.partial as PartialArchData) || await loadPartialData(project.path)
    partial.character_dynamics_result = result
    await savePartialData(project.path, partial)
    context.data.partial = partial

    callbacks.log(`✅ 角色图谱已生成并写入数据库`)
    return result
  }
}

export class GenerateWorldBuildingCommand extends BaseWorkflowCommand<string> {
  async execute({ context, callbacks }: CommandExecuteParams): Promise<string> {
    const { project, config } = getNovelConfig()

    const core = await ipc.invoke('db:project-core-get')
    const premise_result = core?.premise || ''

    if (!premise_result || premise_result.includes('待生成') || premise_result.length < 50) {
      throw new Error('故事前提尚未生成或内容不完整，请返回勾选生成')
    }

    callbacks.log('生成世界观...')
    const template = getPromptTemplate('world_building')
    if (!template) throw new Error('模板丢失')

    const promptBuilder = new ArchitecturePromptBuilder(template)
      .withCoreSeed(premise_result)
      .withGenre(config.genre)
      .withCoreSetting(config.worldSetting || '（未填写）')
      .withGoldenFinger(config.goldenFinger || '（未填写）')
      .withProtagonistProfile(config.protagonistProfile || '（未填写）')
      .withGlobalGuidance(config.globalGuidance || '（未填写）')
      .withStepGuidance(((context.data.stepGuidance as Record<string, string>) || {}).worldbuilding || '')

    const result = await this.callLLMWithBuilder(promptBuilder, callbacks, undefined, context)
    if (context.cancelled) throw new Error('工作流已取消')

    await writeArchToDb('worldbuilding', `# 世界观\n\n${result}\n`)

    const partial = (context.data.partial as PartialArchData) || await loadPartialData(project.path)
    partial.world_building_result = result
    await savePartialData(project.path, partial)
    context.data.partial = partial

    callbacks.log(`✅ 世界观已生成并写入数据库`)
    return result
  }
}

export class GeneratePlotArchitectureCommand extends BaseWorkflowCommand<string> {
  constructor(private selectedSteps: string[]) {
    super()
  }

  async execute({ context, callbacks }: CommandExecuteParams): Promise<string> {
    const { project, config } = getNovelConfig()

    const core = await ipc.invoke('db:project-core-get')
    const premise = core?.premise || ''
    const char_dyn = core?.charactersArch || ''
    const world_b = core?.worldbuilding || ''

    if (!premise || premise.includes('待生成')) throw new Error('故事前提未生成')
    if (!char_dyn || char_dyn.includes('待生成')) throw new Error('角色图谱未生成')
    if (!world_b || world_b.includes('待生成')) throw new Error('世界观未生成')

    callbacks.log('生成情节大纲...')
    const template = getPromptTemplate('synopsis')
    if (!template) throw new Error('模板丢失')

    const { getPlotStructureGuide, getNarrativePOVLabel } = await import('../architecture-workflow')
    const guide = getPlotStructureGuide(config.plotStructure || 'three_act', config.totalChapters)
    const pov = getNarrativePOVLabel(config.narrativePOV || 'third_limited')

    const promptBuilder = new ArchitecturePromptBuilder(template)
      .withCoreSeed(premise)
      .withCharacterDynamics(char_dyn)
      .withWorldBuilding(world_b)
      .withGenre(config.genre)
      .withNumberOfChapters(config.totalChapters)
      .withWordNumber(config.wordsPerChapter)
      .withPlotStructureGuide(guide)
      .withNarrativePov(pov)
      .withGlobalGuidance(config.globalGuidance || '（未填写）')
      .withStepGuidance(((context.data.stepGuidance as Record<string, string>) || {}).synopsis || '')

    const result = await this.callLLMWithBuilder(promptBuilder, callbacks, undefined, context)
    if (context.cancelled) throw new Error('工作流已取消')

    await writeArchToDb('synopsis', `# 情节大纲\n\n${result}\n`)

    const partial = (context.data.partial as PartialArchData) || await loadPartialData(project.path)
    partial.synopsis_result = result
    context.data.partial = partial

    if (this.selectedSteps.includes('premise') && this.selectedSteps.includes('characters') &&
      this.selectedSteps.includes('worldbuilding') && this.selectedSteps.includes('synopsis')) {
      await ipc.invoke('fs:write-file', `${project.path}/.vela/partial_arch.json`, '{}')
    }

    callbacks.log(`✅ 情节大纲已生成并写入数据库`)
    return result
  }
}
