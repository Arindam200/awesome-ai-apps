/**
 * architecture-service — 架构文件状态检查服务
 *
 * 全量 DB 化后，这里直接查 project_core 和 blueprints 表，不再读取文件。
 * 使用场景：Sidebar、WorldBuildingEditor
 */

import { ipc } from './ipc-client'

export type ArchStepKey = 'premise' | 'characters' | 'worldbuilding' | 'synopsis'

export const ARCH_FILES: Array<{
  key: ArchStepKey
  label: string
  emoji: string
  desc: string
}> = [
    { key: 'premise', label: '故事前提', emoji: '🎯', desc: 'Logline · 核心冲突链 · 金手指定位 · 悬念骨架' },
    { key: 'characters', label: '角色图谱', emoji: '👥', desc: '角色弧光 · 关系网络 · 矛盾交织' },
    { key: 'worldbuilding', label: '世界观', emoji: '🌍', desc: '核心规则 · 阶层断层 · 深层危机' },
    { key: 'synopsis', label: '情节大纲', emoji: '🗺️', desc: '三幕结构 · 拐点节奏 · 伏笔闭环' },
  ]

/**
 * 检查所有架构块的生成状态
 * @returns key → boolean 映射，true 表示该块已有有效内容
 */
export async function checkArchStatus(): Promise<Record<string, boolean>> {
  const status: Record<string, boolean> = {
    premise: false,
    characters: false,
    worldbuilding: false,
    synopsis: false,
  }

  const core = await ipc.invoke('db:project-core-get')
  if (!core) return status

  // 长度 > 50 才算真正已生成，前端可以直接用长度判断
  status.premise = (core.premise?.length ?? 0) > 50
  status.characters = (core.charactersArch?.length ?? 0) > 50
  status.worldbuilding = (core.worldbuilding?.length ?? 0) > 50
  status.synopsis = (core.synopsis?.length ?? 0) > 50

  return status
}

/**
 * 检查架构状态（包含字数统计）
 */
export async function checkArchStatusWithWordCount(): Promise<{
  status: Record<string, boolean>
  wordCounts: Record<string, number>
}> {
  const status: Record<string, boolean> = { premise: false, characters: false, worldbuilding: false, synopsis: false }
  const wordCounts: Record<string, number> = { premise: 0, characters: 0, worldbuilding: 0, synopsis: 0 }

  const core = await ipc.invoke('db:project-core-get')
  if (!core) return { status, wordCounts }

  const check = (key: ArchStepKey, content: string | undefined | null) => {
    const len = content?.length ?? 0
    const hasContent = len > 50
    status[key] = hasContent
    wordCounts[key] = hasContent ? len : 0
  }

  check('premise', core.premise)
  check('characters', core.charactersArch)
  check('worldbuilding', core.worldbuilding)
  check('synopsis', core.synopsis)

  return { status, wordCounts }
}

/**
 * 获取蓝图数量
 */
export async function getBlueprintCount(): Promise<number> {
  try {
    const blueprints = await ipc.invoke('db:blueprint-get-all')
    return blueprints.length
  } catch {
    return 0
  }
}

/**
 * 获取具体架构块的内容
 */
export async function readArchFile(key: ArchStepKey): Promise<{ success: boolean; content: string }> {
  try {
    const core = await ipc.invoke('db:project-core-get')
    if (!core) return { success: false, content: '' }

    let content = ''
    switch (key) {
      case 'premise': content = core.premise; break
      case 'characters': content = core.charactersArch; break
      case 'worldbuilding': content = core.worldbuilding; break
      case 'synopsis': content = core.synopsis; break
    }
    return { success: true, content: content ?? '' }
  } catch {
    return { success: false, content: '' }
  }
}
