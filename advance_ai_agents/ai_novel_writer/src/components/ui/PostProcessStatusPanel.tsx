/**
 * 后处理状态面板 — 通用可内嵌组件
 *
 * 展示后处理流水线各步骤的成功/失败状态，
 * 并提供单步重试和全部重试入口。
 *
 * 使用场景：
 * - 草稿箱章节卡片（定稿后处理状态）
 * - 故事架构页（角色卡提取状态）
 */

import { useEffect, useState, useCallback } from 'react'
import { RefreshCw, CheckCircle2, XCircle, AlertTriangle, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '../ui/Button'
import { useProjectStore } from '../../stores/project-store'
import { readPostProcessStatus, type PostProcessStatus } from '../../services/workflows/workflow-utils'
import { cn } from '../../lib/utils'
import { globalEventBus } from '../../shared/event-bus'

interface PostProcessStatusPanelProps {
  /** 状态文件 scope 标识，如 'chapter_1_finalize' */
  scope: string
  /** 重试回调（传 stepKey 则单步重试，不传则全部重试） */
  onRetry?: (stepKey?: string) => void
  /** 是否默认展开（默认 false，折叠显示摘要） */
  defaultExpanded?: boolean
  /** 加载状态后的回调，通知父组件是否有失败项 */
  onStatusLoad?: (hasFailure: boolean) => void
  /** 额外 CSS 类名 */
  className?: string
}

export function PostProcessStatusPanel({
  scope,
  onRetry,
  defaultExpanded = false,
  onStatusLoad,
  className,
}: PostProcessStatusPanelProps) {
  const [status, setStatus] = useState<PostProcessStatus | null>(null)
  const [expanded, setExpanded] = useState(defaultExpanded)
  const [loading, setLoading] = useState(true)
  const project = useProjectStore(s => s.currentProject)

  // 加载状态文件
  const loadStatus = useCallback(async () => {
    if (!project) return
    const s = await readPostProcessStatus(project.path, scope)
    setStatus(s)
    setLoading(false)
  }, [project, scope])

  // Initial load
  useEffect(() => {
    let mounted = true
    const init = async () => {
      if (!project) return
      setLoading(true)
      const s = await readPostProcessStatus(project.path, scope)
      if (mounted) {
        setStatus(s)
        setLoading(false)
      }
    }
    init()
    return () => { mounted = false }
  }, [project, scope])

  // 监听 EventBus 事件，自动刷新后处理状态
  useEffect(() => {
    const unsub1 = globalEventBus.on('FINALIZE_COMPLETE', () => { loadStatus() })
    const unsub2 = globalEventBus.on('WORKFLOW_COMPLETE', () => { loadStatus() })
    return () => { unsub1(); unsub2() }
  }, [loadStatus])

  // 状态变化时回调给父组件
  useEffect(() => {
    if (!status) return
    const isFailed = Object.values(status.steps).some(s => !s.ok)
    if (onStatusLoad) {
      onStatusLoad(isFailed)
    }
  }, [status, onStatusLoad])

  // 无状态文件 → 不渲染
  if (loading || !status) return null

  const steps = Object.entries(status.steps)
  const failedSteps = steps.filter(([, s]) => !s.ok)
  const successCount = steps.filter(([, s]) => s.ok).length
  const totalCount = steps.length
  const hasFailure = failedSteps.length > 0
  const hasCriticalFailure = failedSteps.some(([, s]) => s.critical)

  if (!hasFailure) {
    return (
      <div className={cn(
        'flex items-center gap-1.5 px-2 py-1 rounded text-[10px] text-[var(--color-success,#22c55e)]',
        'bg-green-500/8',
        className,
      )}>
        <CheckCircle2 size={12} />
        <span>{status.sourceLabel} 完成（{successCount}/{totalCount}）</span>
      </div>
    )
  }

  // 有失败 → 显示带折叠的详情面板
  return (
    <div className={cn(
      'rounded-md border overflow-hidden',
      hasCriticalFailure
        ? 'border-red-500 bg-red-500/8'
        : 'border-amber-500 bg-amber-500/8',
      className,
    )}>
      {/* 折叠头部 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-left cursor-pointer hover:opacity-80 transition-opacity"
      >
        <div className="flex items-center gap-1.5">
          <AlertTriangle size={13} className={
            hasCriticalFailure
              ? 'text-[var(--color-error,#ef4444)]'
              : 'text-[var(--color-warning,#f59e0b)]'
          } />
          <span className="text-[11px] font-medium text-[var(--color-text)]">
            {status.sourceLabel} — {failedSteps.length} 个步骤失败
          </span>
          <span className="text-[10px] text-[var(--color-text-muted)]">
            ({successCount}/{totalCount})
          </span>
        </div>
        {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      {/* 展开详情 */}
      {expanded && (
        <div className="px-3 pb-2.5 space-y-1">
          {steps.map(([key, step]) => (
            <div
              key={key}
              className="flex items-center justify-between gap-2 py-1 text-[11px]"
            >
              <div className="flex items-center gap-1.5 min-w-0">
                {step.ok ? (
                  <CheckCircle2 size={12} className="text-[var(--color-success,#22c55e)] shrink-0" />
                ) : (
                  <XCircle size={12} className="text-[var(--color-error,#ef4444)] shrink-0" />
                )}
                <span className={cn(
                  'truncate',
                  step.ok ? 'text-[var(--color-text-secondary)]' : 'text-[var(--color-text)]',
                )}>
                  {step.label}
                </span>
                {step.critical && !step.ok && (
                  <span className="shrink-0 px-1 py-0.5 rounded text-[9px] bg-red-500/15 text-red-400">
                    关键
                  </span>
                )}
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {step.ok ? (
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    {step.completedAt ? new Date(step.completedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                ) : (
                  <>
                    <span className="text-[10px] text-[var(--color-error,#ef4444)] max-w-[120px] truncate" title={step.error}>
                      {step.error || '失败'}
                    </span>
                    {onRetry && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onRetry(key) }}
                        className="p-0.5 rounded hover:bg-[var(--color-hover)] transition-colors cursor-pointer"
                        title="重试此步骤"
                      >
                        <RefreshCw size={11} className="text-[var(--color-accent)]" />
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}

          {/* 底部操作栏 */}
          <div className="flex items-center justify-between pt-1.5 border-t border-[var(--color-border)]">
            <div className="flex items-center gap-1 text-[10px] text-[var(--color-text-muted)]">
              <Clock size={10} />
              <span>
                上次尝试 {new Date(status.updatedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            {onRetry && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onRetry()}
                className="gap-1"
              >
                <RefreshCw size={10} />
                重试失败步骤
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
