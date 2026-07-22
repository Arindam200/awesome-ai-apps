/**
 * 工作流前置校验工具
 *
 * 每个生成步骤启动前需要校验上游数据是否就绪，
 * 以防用户在配置不完整的状态下浪费 AI Token。
 *
 * 校验失败时返回 GuardResult { ok: false, message }，
 * 由调用方选择展示方式（弹窗提示 / 日志输出）。
 */

import { useProjectStore } from '../stores/project-store'
import { ipc } from './ipc-client'

import { readPostProcessStatus, getChapterFinalizeScope, getFailedStepLabels } from './workflows/workflow-utils'

export interface GuardResult {
  ok: boolean
  /** 失败时的提示语（给用户看） */
  message?: string
  /** 用于跳转引导的目标动作标识 */
  action?: 'open-config' | 'open-world-building' | 'open-blueprint'
}

// ===== Guard 1：生成故事架构前 → 校验小说配置 =====

/**
 * 生成故事架构（架构文件）前的前置校验：
 * 要求「核心大纲」或「主角人设」至少填写其中之一。
 */
export function guardArchitectureGeneration(): GuardResult {
  const project = useProjectStore.getState().currentProject
  if (!project) {
    return { ok: false, message: '请先打开或新建一个项目。' }
  }

  const { coreOutline, protagonistProfile, worldSetting, genre } = project.novelConfig

  // 校验：小说配置是否有实质内容
  const hasConfig = !!(
    coreOutline?.trim() ||
    protagonistProfile?.trim() ||
    worldSetting?.trim()
  )

  if (!hasConfig) {
    return {
      ok: false,
      message: `请先填写「小说配置」中的核心大纲或主角人设，AI 才能据此生成故事架构。\n\n当前类型：${genre || '未设置'}`,
      action: 'open-config',
    }
  }

  return { ok: true }
}

// ===== Guard 2：生成章节蓝图前 → 校验故事架构完成度 =====

/**
 * 生成章节蓝图前的前置校验：
 * 要求至少有 1 个架构信息（故事前提）已生成，
 * 建议 4 个都完成，但允许继续（仅提示警告）。
 */
export async function guardDirectoryGeneration(): Promise<GuardResult> {
  const project = useProjectStore.getState().currentProject
  if (!project) {
    return { ok: false, message: '请先打开或新建一个项目。' }
  }

  const core = await ipc.invoke('db:project-core-get')
  const missing: string[] = []

  const checkHasContent = (text: string | null | undefined) => text && text.length > 50 && !text.includes('> 待生成')

  if (!core || !checkHasContent(core.premise)) missing.push('故事前提')
  if (!core || !checkHasContent(core.charactersArch)) missing.push('角色图谱')
  if (!core || !checkHasContent(core.worldbuilding)) missing.push('世界观')
  if (!core || !checkHasContent(core.synopsis)) missing.push('情节大纲')

  // 故事前提是必须的（第一个大块）
  if (missing.includes('故事前提')) {
    return {
      ok: false,
      message: `「故事前提」尚未生成，它是章节蓝图的基础。\n\n请先在「故事架构」中点击「AI 生成架构」，生成故事前提后再来生成章节蓝图。`,
      action: 'open-world-building',
    }
  }

  // 其他部分缺失：警告但允许继续
  if (missing.length > 0) {
    return {
      ok: true, // 允许继续，但携带警告信息
      message: `注意：以下架构信息尚未生成，蓝图质量可能受影响：\n${missing.map(m => `• ${m}`).join('\n')}\n\n建议先生成完整架构，或继续使用现有内容。`,
    }
  }

  // 检查角色卡是否存在（不变量 1 的反向约束）
  const chars = await ipc.invoke('db:character-get-all')
  if (chars.length === 0) {
    return {
      ok: false,
      message: `角色卡不存在（数据库中没有角色记录）。\n\n请先在「故事架构」中生成角色图谱（会自动创建角色卡），或在「角色管理」中手动创建角色卡。`,
    }
  }

  return { ok: true }
}

// ===== Guard 3：章节写稿前 → 校验章节蓝图存在 =====

/**
 * 章节写稿前的前置校验：
 * 1. 要求 blueprints/ 目录中存在至少一个章节蓝图 JSON 文件。
 * 2. 如果指定了章节号且 > 1，要求前一章已定稿（存在于 manuscript/ 中），否则上下文会断裂。
 */
export async function guardChapterWriting(targetChapterNumber?: number): Promise<GuardResult> {
  const project = useProjectStore.getState().currentProject
  if (!project) {
    return { ok: false, message: '请先打开或新建一个项目。' }
  }

  const blueprints = await ipc.invoke('db:blueprint-get-all')
  if (blueprints.length === 0) {
    return {
      ok: false,
      message: `尚未生成章节蓝图（数据库为空）。\n\n请先在「章节蓝图」中点击「AI 生成蓝图」，让 AI 规划每章内容后，再回来写稿。`,
      action: 'open-blueprint',
    }
  }

  // 检查角色卡是否存在（不变量 1 的反向约束：无角色卡则阻断写稿）
  const chars = await ipc.invoke('db:character-get-all')
  if (chars.length === 0) {
    return {
      ok: false,
      message: `角色卡不存在（数据库中没有角色记录）。\n\nAI 写稿需要角色状态作为上下文，请先在「故事架构」中生成角色图谱，或在「角色管理」中手动创建角色卡。`,
    }
  }

  // 如果指定了且不是第一章，则必须保证前一章已经存在正文库（定稿状态）
  if (targetChapterNumber && targetChapterNumber > 1) {
    const prevChapter = targetChapterNumber - 1
    const prevDraftMeta = await ipc.invoke('db:draft-get-finalized', prevChapter)
    if (!prevDraftMeta) {
      return {
        ok: false,
        message: `上下文缺失：第 ${prevChapter} 章尚未定稿！\n\n为了保证 AI 写稿时能读取到连贯的上下文（前章结尾和剧情要点），请必须先前往草稿箱完成第 ${prevChapter} 章的定稿操作。`,
      }
    }

    // 不变量 2 的反向约束：前一章定稿后处理必须全部通过
    const prevScope = getChapterFinalizeScope(prevChapter)
    const prevStatus = await readPostProcessStatus(project.path, prevScope)
    if (prevStatus && !prevStatus.allCriticalPassed) {
      const failedLabels = getFailedStepLabels(prevStatus)
      return {
        ok: false,
        message: `第 ${prevChapter} 章的定稿后处理未完成！\n\n以下关键步骤失败：\n${failedLabels.map(f => `• ${f}`).join('\n')}\n\n请先在草稿箱中点击「修复定稿」按钮补全数据，否则后续章节的 AI 上下文将不完整。`,
      }
    }
    // 如果状态文件不存在（旧版定稿）→ 兼容放行
  }

  return { ok: true }
}

// ===== Guard 4：角色卡重新生成前 → 检查蓝图是否为空 =====

/**
 * 角色卡重新生成/补齐的前置校验：
 * 不变量 1：角色卡仅允许在蓝图目录为空时重新生成，
 * 否则会破坏已有蓝图/章节的角色状态链。
 */
export async function guardCharacterRegeneration(): Promise<GuardResult> {
  const project = useProjectStore.getState().currentProject
  if (!project) {
    return { ok: false, message: '请先打开或新建一个项目。' }
  }

  const blueprints = await ipc.invoke('db:blueprint-get-all')
  if (blueprints.length > 0) {
    return {
      ok: false,
      message: `已有章节蓝图，角色卡不可重新生成。\n\n蓝图生成已依赖角色数据，重新生成角色卡会导致现有蓝图和已写章节全部失效。\n如需修改角色，请手动编辑现有角色卡。`,
    }
  }

  return { ok: true }
}

// ===== Guard 5：修复定稿后处理前 → 检查是否为最新定稿章节 =====

/**
 * 修复定稿后处理的前置校验：
 * 不变量 2：后处理只允许在最新定稿章节上执行，
 * 回溯重跑历史章节会覆盖后续章节的角色状态。
 */
export async function guardRepairPostProcess(chapterNumber: number): Promise<GuardResult> {
  const project = useProjectStore.getState().currentProject
  if (!project) {
    return { ok: false, message: '请先打开或新建一个项目。' }
  }

  // 从数据库获取最大的定稿章节号
  const maxFinalized = await ipc.invoke('db:draft-get-max-finalized-chapter')

  if (maxFinalized === 0) {
    return { ok: false, message: '尚无已定稿章节，无法执行修复操作。' }
  }

  if (chapterNumber !== maxFinalized) {
    return {
      ok: false,
      message: `只允许修复最新定稿章节（第 ${maxFinalized} 章）的后处理。\n\n回溯修复第 ${chapterNumber} 章会破坏角色状态的线性演化链。`,
    }
  }

  return { ok: true }
}
