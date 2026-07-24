import type { WorkflowDefinition } from '../../stores/workflow-store'
import { useProjectStore } from '../../stores/project-store'
import { ipc } from '../ipc-client'
import type { BlueprintData } from '../../../electron/repositories/blueprint-repository'
import { stripThinkingTags } from './workflow-utils'

// ==========================================
// 1. 结构与类型导出 (保留对外的向后兼容)
// ==========================================

export type ChapterBlueprint = BlueprintData

const EMPTY_BLUEPRINT: ChapterBlueprint = {
  chapterNumber: 0,
  title: '',
  role: '发展',
  purpose: '',
  keyEvents: '',
  characters: [],
  suspenseHook: '',
  userGuidance: '',
  notes: '',
  notesUpdatedAt: '',
}

export interface DirectoryWorkflowParams {
  mode: 'full' | 'append'
  startChapter?: number
  count?: number
  /** 节奏/风格指导（可选） */
  pacingGuidance?: string
}

// ==========================================
// 2. 蓝图文件访问与工具函数
// ==========================================

function extractJsonPayload(content: string): string | null {
  const cleanContent = stripThinkingTags(content)
  const jsonStr = cleanContent.replace(/```json?\n?/gi, '').replace(/```\n?/g, '').trim()

  const firstBrace = jsonStr.indexOf('{')
  const firstBracket = jsonStr.indexOf('[')
  const lastBrace = jsonStr.lastIndexOf('}')
  const lastBracket = jsonStr.lastIndexOf(']')

  if (firstBrace === -1 && firstBracket === -1) return null

  if (firstBracket !== -1 && (firstBrace === -1 || firstBracket < firstBrace)) {
    if (lastBracket === -1) return null
    return jsonStr.substring(firstBracket, lastBracket + 1)
  }

  if (lastBrace === -1) return null
  return jsonStr.substring(firstBrace, lastBrace + 1)
}

function normalizeBlueprints(parsed: unknown, startNum: number, endNum: number): ChapterBlueprint[] {
  let blueprintList = parsed
  if (blueprintList && typeof blueprintList === 'object' && !Array.isArray(blueprintList) && 'blueprints' in blueprintList) {
    blueprintList = (blueprintList as { blueprints: unknown }).blueprints
  }
  if (!Array.isArray(blueprintList)) return []

  const result = blueprintList
    .filter((p: Record<string, unknown>) => {
      const n = Number(p.chapterNumber || p.chapter_number)
      return n >= startNum && n <= endNum
    })
    .map((p: Record<string, unknown>) => {
      const chapterNumber = Number(p.chapterNumber || p.chapter_number || 0)
      return {
        ...EMPTY_BLUEPRINT,
        chapterNumber,
        title: String(p.title || `第${chapterNumber}章`),
        role: String(p.role || '发展'),
        purpose: String(p.purpose || ''),
        keyEvents: String(p.keyEvents || p.key_events || ''),
        characters: Array.isArray(p.characters) ? p.characters : [],
        suspenseHook: String(p.suspenseHook || p.suspense_hook || ''),
        userGuidance: '',
      }
    })

  const distinctMap = new Map<number, ChapterBlueprint>()
  for (const item of result) {
    if (!distinctMap.has(item.chapterNumber)) distinctMap.set(item.chapterNumber, item)
  }

  return Array.from(distinctMap.values()).sort((a, b) => a.chapterNumber - b.chapterNumber)
}

export function parseTextBlueprints(content: string, startNum: number, endNum: number): ChapterBlueprint[] {
  try {
    const payload = extractJsonPayload(content)
    if (!payload) return []

    return normalizeBlueprints(JSON.parse(payload), startNum, endNum)
  } catch {
    console.error('Failed to parse blueprint JSON', content)
  }

  return []
}

export function parseTextBlueprintsStrict(content: string, startNum: number, endNum: number): ChapterBlueprint[] {
  const payload = extractJsonPayload(content)
  if (!payload) {
    throw new Error(`蓝图 JSON 解析失败：未找到有效 JSON 内容（目标章节 ${startNum}–${endNum}）`)
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(payload)
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    throw new Error(`蓝图 JSON 解析失败：${detail}`)
  }

  const blueprints = normalizeBlueprints(parsed, startNum, endNum)
  if (blueprints.length === 0) {
    throw new Error(`未解析到第 ${startNum}–${endNum} 章范围内的蓝图`)
  }

  return blueprints
}

export function assertBlueprintCoverage(
  blueprints: ChapterBlueprint[],
  startChapter: number,
  endChapter: number,
): void {
  const chapterSet = new Set(blueprints.map((item) => item.chapterNumber))
  const missing: number[] = []
  for (let chapter = startChapter; chapter <= endChapter; chapter++) {
    if (!chapterSet.has(chapter)) missing.push(chapter)
  }

  if (missing.length > 0) {
    throw new Error(`蓝图生成缺少目标章节：第 ${missing.join('、')} 章`)
  }
}

export async function loadDirectoryBlueprints(): Promise<ChapterBlueprint[]> {
  try {
    const blueprints = await ipc.invoke('db:blueprint-get-all')
    return blueprints.sort((a, b) => a.chapterNumber - b.chapterNumber)
  } catch {
    return []
  }
}

function assertIpcSuccess(result: { success: boolean; error?: string }, action: string): void {
  if (!result.success) {
    throw new Error(result.error || `${action}失败`)
  }
}

export async function saveChapterBlueprint(blueprint: ChapterBlueprint): Promise<void> {
  const result = await ipc.invoke('db:blueprint-upsert', blueprint)
  assertIpcSuccess(result, '保存章节蓝图')
}

export async function saveAllBlueprints(blueprints: ChapterBlueprint[]): Promise<void> {
  const result = await ipc.invoke('db:blueprint-upsert-many', blueprints)
  assertIpcSuccess(result, '保存章节蓝图')
}

export async function verifyBlueprintsPersisted(
  blueprints: ChapterBlueprint[],
  expectedRange?: { startChapter: number; endChapter: number },
): Promise<void> {
  if (expectedRange) {
    assertBlueprintCoverage(blueprints, expectedRange.startChapter, expectedRange.endChapter)
  }

  for (const blueprint of blueprints) {
    const saved = await ipc.invoke('db:blueprint-get', blueprint.chapterNumber)
    if (!saved) {
      throw new Error(`蓝图保存后验证失败：第 ${blueprint.chapterNumber} 章未写入数据库`)
    }
    if (
      saved.title !== blueprint.title ||
      saved.role !== blueprint.role ||
      saved.purpose !== blueprint.purpose ||
      saved.keyEvents !== blueprint.keyEvents ||
      saved.suspenseHook !== blueprint.suspenseHook
    ) {
      throw new Error(`蓝图保存后验证失败：第 ${blueprint.chapterNumber} 章内容与本次生成结果不一致`)
    }
  }
}

export async function getBlueprintCount(): Promise<number> {
  try {
    const blueprints = await ipc.invoke('db:blueprint-get-all')
    return blueprints.length
  } catch {
    return 0
  }
}

// ==========================================
// 3. 工作流定义映射工厂 (Command 调度层)
// ==========================================

export function createDirectoryWorkflow(params: DirectoryWorkflowParams = { mode: 'full' }): WorkflowDefinition {
  return {
    type: 'directory',
    title: params.mode === 'append' ? `📋 续写章节蓝图${params.startChapter ? `（从第 ${params.startChapter} 章）` : ''}` : '📋 生成章节蓝图（全量）',
    steps: [
      {
        name: '读取架构',
        description: `从 SQLite 加载项目架构信息`,
        executor: async (_step, context, callbacks) => {
          const project = useProjectStore.getState().currentProject
          if (!project) throw new Error('未打开项目')

          callbacks.log('读取项目架构信息...')
          const core = await ipc.invoke('db:project-core-get')
          if (!core) throw new Error('项目核心数据未初始化')

          const parts: string[] = []
          if (core.premise && core.premise.length > 50) parts.push(core.premise)
          if (core.charactersArch && core.charactersArch.length > 50) parts.push(core.charactersArch)
          if (core.worldbuilding && core.worldbuilding.length > 50) parts.push(core.worldbuilding)
          if (core.synopsis && core.synopsis.length > 50) parts.push(core.synopsis)

          if (parts.length === 0) throw new Error('项目主要架构均未生成')

          context.data.architecture = parts.join('\n\n---\n\n')
          // 注入节奏指导到 context，供 Command 读取
          if (params.pacingGuidance) context.data.pacingGuidance = params.pacingGuidance
          if (params.mode === 'append') {
            const existing = await loadDirectoryBlueprints()
            context.data.existingBlueprints = existing
            callbacks.log(`已加载 ${existing.length} 章已有蓝图`)
          }
          return `架构加载完成（${parts.length} 段）`
        },
      },
      {
        name: '生成蓝图',
        description: '基于架构文件生成全书章节蓝图',
        executor: async (_step, context, callbacks) => {
          const { GenerateDirectoryCommand } = await import('./commands/directory.command')
          const cmd = new GenerateDirectoryCommand(params)
          const blueprints = await cmd.execute({ step: _step, context, callbacks })
          // 返回可读摘要字符串（step.result 必须是 string，否则 AIOutputPanel 渲染会崩溃）
          return `已生成 ${blueprints.length} 章蓝图`
        },
      },
      {
        name: '保存蓝图',
        description: `将章节蓝图批量写入 SQLite 数据库`,
        executor: async (_step, context, callbacks) => {
          const project = useProjectStore.getState().currentProject
          if (!project) throw new Error('未打开项目')

          const newBlueprints = context.data.newBlueprints as ChapterBlueprint[]
          const existingBlueprints = context.data.existingBlueprints as ChapterBlueprint[]

          callbacks.log('保存蓝图到数据库...')

          let merged: ChapterBlueprint[]
          if (params.mode === 'full') {
            merged = newBlueprints
            // TODO: 若需要清理冗余蓝图，可考虑添加 db:blueprint-delete-all 以严格符合全量替换的意图。
            // 在当前 upsert-many 中，仅覆盖更新
          } else {
            const existingMap = new Map(existingBlueprints.map(b => [b.chapterNumber, b]))
            for (const nb of newBlueprints) existingMap.set(nb.chapterNumber, nb)
            merged = Array.from(existingMap.values()).sort((a, b) => a.chapterNumber - b.chapterNumber)
          }

          await saveAllBlueprints(merged)
          useProjectStore.getState().refreshFileTree()
          return '已保存蓝图'
        },
      },
    ],
    onComplete: {
      mode: 'silent',
      message: params.mode === 'append' ? '✅ 续写蓝图生成完成' : '✅ 全书章节蓝图已生成完成！',
    },
  }
}
