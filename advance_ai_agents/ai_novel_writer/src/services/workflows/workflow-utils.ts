/**
 * 工作流共享工具函数
 *
 * 供 architecture-workflow / chapter-workflow 等多个工作流复用的通用逻辑
 *
 * 核心组件：
 * 1. withRetry — 通用异步重试包装器
 * 2. PostProcessPipeline — 后处理流水线（注册 → 执行 → 持久化 → 修复）
 */

import type { StepCallbacks } from '../../stores/workflow-store'
import { ipc } from '../ipc-client'

// ===== 文本处理通用工具 =====

/**
 * 剥除文本中可能包含的 <think>...</think> 思维链标签
 * 用于清洗大模型在生成正文时输出的思维链，避免其被持久化写入磁盘文件
 */
export function stripThinkingTags(text: string): string {
  if (!text) return text
  // 支持只有 <think> 没有闭合标签的情况
  return text.replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '').trim()
}

// ===== 通用重试包装器 =====

/**
 * 带重试的异步操作包装器
 * @param fn 要执行的异步函数
 * @param maxRetries 最大重试次数（不含首次执行）
 * @param label 操作标签（用于日志）
 * @param callbacks 步骤回调（用于输出日志）
 * @returns 成功返回 { ok: true }，全部失败返回 { ok: false, error }
 */
export async function withRetry(
  fn: () => Promise<void>,
  maxRetries: number,
  label: string,
  callbacks: StepCallbacks,
): Promise<{ ok: boolean; error?: string; attempts: number }> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      await fn()
      return { ok: true, attempts: attempt + 1 }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err)
      if (attempt < maxRetries) {
        callbacks.log(`  ⚠️ ${label} 第${attempt + 1}次失败，正在重试...（${errMsg}）`)
      } else {
        return { ok: false, error: errMsg, attempts: attempt + 1 }
      }
    }
  }
  return { ok: false, error: '未知错误', attempts: maxRetries + 1 }
}

// ===== 后处理流水线 =====

/** 单个后处理步骤定义 */
export interface PostProcessStep {
  /** 唯一标识，如 'chapter_notes' */
  key: string
  /** 展示名称，如 '📋 章节要点' */
  label: string
  /** 关键步骤（失败阻断下游工作流） */
  critical: boolean
  /** 步骤执行器 */
  executor: (callbacks: StepCallbacks) => Promise<void>
}

/** 单步后处理执行结果（持久化到状态文件） */
export interface PostProcessStepResult {
  label: string
  critical: boolean
  ok: boolean
  completedAt?: string
  error?: string
  lastAttemptAt: string
  attemptCount: number
}

/** 后处理状态（持久化到 .vela/post_process/{scope}.json） */
export interface PostProcessStatus {
  /** 唯一标识，如 'chapter_1_finalize' */
  scope: string
  /** 来源描述，如 '第1章定稿' */
  sourceLabel: string
  /** 首次执行时间 */
  createdAt: string
  /** 最后更新时间 */
  updatedAt: string
  /** 各步骤执行结果 */
  steps: Record<string, PostProcessStepResult>
  /** 所有关键步骤是否通过 */
  allCriticalPassed: boolean
}

/** 解析原有 scope 字符串为 sourceType 和 sourceId */
function parseScope(scope: string): { sourceType: string; sourceId: string } {
  const match = scope.match(/^chapter_(\d+)_finalize$/)
  if (match) return { sourceType: 'chapter_finalize', sourceId: match[1] }
  return { sourceType: 'unknown', sourceId: scope }
}

/** 读取后处理状态 (向后兼容 UI) */
export async function readPostProcessStatus(
  _projectPath: string,
  scope: string,
): Promise<PostProcessStatus | null> {
  try {
    const { sourceType, sourceId } = parseScope(scope)
    const run = await ipc.invoke('db:post-process-get-latest-run', sourceType, sourceId)
    if (!run) return null

    const steps = await ipc.invoke('db:post-process-get-steps', run.id)

    const status: PostProcessStatus = {
      scope,
      sourceLabel: run.sourceLabel,
      createdAt: run.createdAt,
      updatedAt: run.updatedAt,
      allCriticalPassed: run.allCriticalPassed,
      steps: {}
    }

    for (const s of steps) {
      status.steps[s.stepKey] = {
        label: s.label,
        critical: s.critical,
        ok: s.ok,
        completedAt: s.completedAt || undefined,
        error: s.errorMsg || undefined,
        lastAttemptAt: s.lastAttemptAt || '',
        attemptCount: s.attemptCount
      }
    }

    return status
  } catch {
    return null
  }
}

/** 快捷检查：所有关键步骤是否通过 */
export async function isAllCriticalPassed(
  _projectPath: string,
  scope: string,
): Promise<boolean> {
  const { sourceType, sourceId } = parseScope(scope)
  return await ipc.invoke('db:post-process-is-all-passed', sourceType, sourceId)
}

/** 提取失败步骤的展示标签列表 */
export function getFailedStepLabels(status: PostProcessStatus): string[] {
  return Object.values(status.steps)
    .filter(s => !s.ok)
    .map(s => s.label)
}

/** 获取章节定稿后处理的 scope 标识 */
export function getChapterFinalizeScope(chapterNumber: number): string {
  return `chapter_${chapterNumber}_finalize`
}

// ===== 流水线执行器 =====

export interface PipelineOptions {
  /** 每步重试次数，默认 2 */
  retryCount?: number
  /** true = 只重跑失败步骤（修复模式） */
  onlyFailed?: boolean
}

/**
 * 执行后处理流水线
 *
 * @param projectPath 项目路径（用于状态文件读写）
 * @param scope 状态文件唯一标识
 * @param sourceLabel 来源描述（展示用）
 * @param steps 步骤列表
 * @param callbacks 工作流回调
 * @param options 可选配置
 * @returns 完整的后处理状态
 */
export async function runPostProcessPipeline(
  projectPath: string,
  scope: string,
  sourceLabel: string,
  steps: PostProcessStep[],
  callbacks: StepCallbacks,
  options?: PipelineOptions,
): Promise<PostProcessStatus> {
  const retryCount = options?.retryCount ?? 2
  const onlyFailed = options?.onlyFailed ?? false

  const { sourceType, sourceId } = parseScope(scope)

  // 判断是否存在已有 instance
  let run = await ipc.invoke('db:post-process-get-latest-run', sourceType, sourceId)

  if (!onlyFailed || !run) {
    // 新建跑批
    callbacks.log(`  初始化后处理跑批...`)
    const createRes = await ipc.invoke('db:post-process-create-run', {
      triggerSourceType: sourceType,
      triggerSourceId: sourceId,
      sourceLabel,
      steps: steps.map(s => ({ key: s.key, label: s.label, critical: s.critical }))
    })
    if (!createRes.success || !createRes.id) {
      throw new Error(`创建跑批失败: ${createRes.error}`)
    }
    run = await ipc.invoke('db:post-process-get-latest-run', sourceType, sourceId)
  }

  if (!run) throw new Error('跑批获取异常')

  const runId = run.id
  const runSteps = await ipc.invoke('db:post-process-get-steps', runId)
  const stepMap = new Map((runSteps as unknown as Array<Record<string, unknown>>).map((s) => [s.stepKey, s]))

  for (const step of steps) {
    const existingStep = stepMap.get(step.key)

    // 修复模式：跳过已成功的步骤
    if (onlyFailed && existingStep?.ok) {
      callbacks.log(`  ⏭️ ${step.label} — 已成功，跳过`)
      continue
    }

    const result = await withRetry(() => step.executor(callbacks), retryCount, step.label, callbacks)

    if (result.ok) {
      await ipc.invoke('db:post-process-mark-step-ok', runId, step.key)
    } else {
      await ipc.invoke('db:post-process-mark-step-failed', runId, step.key, result.error || '未知错误')
    }
  }

  // 返回最终状态汇总供 UI 展示
  const status = await readPostProcessStatus(projectPath, scope)
  if (!status) {
    throw new Error('汇总状态获取失败')
  }

  // 最终汇总
  const failedSteps = Object.values(status.steps).filter(s => !s.ok)
  const successSteps = Object.values(status.steps).filter(s => s.ok)

  callbacks.log('')
  callbacks.log(`━━━━━━━━━━ ${sourceLabel} 后处理汇总 ━━━━━━━━━━`)
  for (const [, r] of Object.entries(status.steps)) {
    callbacks.log(`  ${r.ok ? '✅' : '❌'} ${r.label}${r.ok ? '' : ` — ${r.error}`}`)
  }
  callbacks.log(`━━━━━━━━━━ ${successSteps.length}/${Object.keys(status.steps).length} 成功 ━━━━━━━━━━`)

  if (failedSteps.length > 0) {
    const failedLabels = failedSteps.map(r => r.label).join('、')
    callbacks.log(`⚠️ 以下后处理步骤失败：${failedLabels}`)
    if (failedSteps.some(s => s.critical)) {
      callbacks.log('💡 存在关键步骤失败，后续流程可能被阻断。请在对应页面使用「重试」功能修复')
    }
  }

  return status
}
