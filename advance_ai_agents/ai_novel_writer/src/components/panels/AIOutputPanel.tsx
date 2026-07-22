import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Loader2, Circle, Sparkles, X, ChevronRight, StopCircle } from 'lucide-react'
import { useWorkflowStore, type WorkflowRun, type WorkflowStep } from '../../stores/workflow-store'
import { useLayoutStore } from '../../stores/layout-store'
import MarkdownContent from '../ui/MarkdownContent'

/**
 * 右侧面板「AI 输出」视图
 * 参考 Cursor Agent 风格：扁平化、极简文字驱动、可折叠思考区
 */
export default function AIOutputPanel() {
  // 使用 selector 精确订阅，避免 globalLogs 高频更新导致整个面板重渲染
  const activeRuns = useWorkflowStore(s => s.activeRuns)
  const history = useWorkflowStore(s => s.history)
  const getActiveStreamingRun = useWorkflowStore(s => s.getActiveStreamingRun)
  const activeRun = getActiveStreamingRun()
  const [viewRunId, setViewRunId] = useState<string | null>(null)

  console.log('[AIOutputPanel] render: viewRunId=', viewRunId, 'activeRun=', activeRun?.id, activeRun?.status, 'activeRuns.len=', activeRuns.length)

  // 自动跟随最新活跃任务
  useEffect(() => {
    if (activeRun) {
      console.log('[AIOutputPanel] mount/useEffect activeRun:', activeRun.id, activeRun.status, 'steps:', activeRun.steps.map(s => s.status))
      setViewRunId(prev => prev === activeRun.id ? prev : activeRun.id)
    } else {
      console.log('[AIOutputPanel] mount/useEffect: no activeRun, activeRuns=', activeRuns.map(r => r.id + ':' + r.status), 'history=', history.slice(0, 2).map(r => r.id + ':' + r.status))
    }
    // 只依赖 id 字符串，不依赖 activeRun 对象引用
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRun?.id])

  const viewRun: WorkflowRun | undefined =
    activeRuns.find(r => r.id === viewRunId) ||
    history.find(r => r.id === viewRunId) ||
    activeRun ||
    undefined

  // DEBUG: 面板切换时追踪状态
  if (viewRun?.status === 'failed' && viewRun.steps.some(s => s.status === 'pending' || s.status === 'running')) {
    console.log('[AIOutputPanel] viewRun out of sync! run.status=', viewRun.status, 'steps=', viewRun.steps.map(s => s.status))
  }

  const recentHistory = history.slice(0, 10)

  return (
    <div
      className="writer-ai-panel flex flex-col h-full overflow-hidden"
    >
      {/* 面板头部 */}
      <div
        className="no-select flex items-center justify-between gap-1.5 px-2 flex-shrink-0"
        style={{
          height: 'var(--height-panel-header)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <span
          className="text-xs font-medium uppercase tracking-widest"
          style={{ color: 'var(--color-text-muted)' }}
        >
          AI 输出
        </span>
        <button
          onClick={() => useLayoutStore.getState().setRightView('agent')}
          title="切换回 Agent"
          className="icon-btn"
          style={{ width: 20, height: 20 }}
        >
          <X size={13} strokeWidth={1.5} />
        </button>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-hidden">
        {viewRun ? (
          <ActiveRunView
            run={viewRun}
            activeRuns={activeRuns}
            onSwitchRun={setViewRunId}
          />
        ) : (
          <div className="h-full overflow-y-auto">
            {recentHistory.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="px-3 py-3">
                <HistoryList items={recentHistory} onSelect={setViewRunId} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}


// ===== 空状态 =====

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-2 px-6" style={{ color: 'var(--color-text-muted)' }}>
      <Sparkles size={20} style={{ opacity: 0.2 }} />
      <span className="text-xs opacity-60">暂无输出</span>
    </div>
  )
}


// ===== 活跃任务视图（Cursor 风格） =====

function ActiveRunView({
  run,
  activeRuns,
  onSwitchRun,
}: {
  run: WorkflowRun
  activeRuns: WorkflowRun[]
  onSwitchRun: (id: string) => void
}) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const isActive = run.status === 'running' || run.status === 'waiting'
  const cancelWorkflow = useWorkflowStore.getState().cancelWorkflow
  const prevLenRef = useRef(0)

  // 提取当前步骤 + 内容
  const currentStep = run.steps[run.currentStepIndex] || run.steps[0]
  const rawText = currentStep?.result || ''

  let content = rawText
  const segments = rawText.split(/<think>/)
  if (segments.length > 1) {
    const lastSegment = segments[segments.length - 1]
    const end = lastSegment.indexOf('</think>')
    if (end !== -1) {
      content = lastSegment.substring(end + 8)
    } else {
      content = ''
    }
  }

  // 节流自动滚动：仅在正文内容长度变化时触发，思考区不自动滚动
  const contentLen = content.length
  useEffect(() => {
    if (!autoScroll || !scrollRef.current) return
    if (contentLen !== prevLenRef.current) {
      prevLenRef.current = contentLen
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
      })
    }
  }, [contentLen, autoScroll, run.currentStepIndex])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    setAutoScroll(el.scrollHeight - el.scrollTop - el.clientHeight < 60)
  }

  // 整体进度百分比
  const completedCount = run.steps.filter(s => s.status === 'completed').length
  const overallProgress = run.steps.length > 0
    ? Math.round(((completedCount + (currentStep?.progress || 0) / 100) / run.steps.length) * 100)
    : 0

  return (
    <div className="flex flex-col h-full overflow-hidden relative">
      {/* 多任务切换（多于1个任务时显示） */}
      {activeRuns.length > 1 && (
        <div
          className="flex items-center gap-1 px-2 py-1.5 flex-shrink-0 overflow-x-auto"
          style={{ borderBottom: '1px solid var(--color-border)' }}
        >
          {activeRuns.map(r => (
            <button
              key={r.id}
              onClick={() => onSwitchRun(r.id)}
              className="text-[0.68rem] px-2 py-0.5 rounded transition-all flex-shrink-0"
              style={{
                backgroundColor: r.id === run.id ? 'var(--color-hover)' : 'transparent',
                color: r.id === run.id ? 'var(--color-text)' : 'var(--color-text-muted)',
              }}
            >
              {r.title.replace(/^[^\s]+\s/, '')}
            </button>
          ))}
        </div>
      )}

      {/* 整体进度条（细线） */}
      <div className="flex-shrink-0" style={{ height: 2, backgroundColor: 'var(--color-border)' }}>
        <div
          style={{
            height: '100%',
            width: `${Math.max(isActive ? 3 : 0, overallProgress)}%`,
            backgroundColor: run.status === 'completed' ? 'var(--color-success)' : 'var(--color-accent)',
            borderRadius: 1,
            transition: 'width 0.6s ease',
          }}
        />
      </div>

      {/* 滚动内容区 */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        {/* 步骤进度区及独立输出流 */}
        <div className="px-2 pt-2 pb-4">
          {run.steps.map((step, i) => (
            <StepOutputBlock
              key={step.id}
              step={step}
              index={i}
              total={run.steps.length}
              isActiveRun={isActive}
              isCurrentStep={i === run.currentStepIndex}
            />
          ))}

          {/* 全局完成状态（所有步骤走完之后展示） */}
          {!isActive && run.status === 'completed' && (
            <div
              className="flex items-center justify-center gap-1.5 pt-4 pb-2 mb-2 text-xs"
              style={{ color: 'var(--color-success)', borderTop: '1px dashed var(--color-border)' }}
            >
              <CheckCircle2 size={12} />
              整个工作流已全部完成
            </div>
          )}
        </div>

        {/* 底部操作占位符，避免滚动到底部被遮挡 */}
        {isActive && <div className="h-10 w-full flex-shrink-0" />}
      </div>

      {/* 固定在底部的操作悬浮区 */}
      {isActive && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10">
          <button
            onClick={() => cancelWorkflow(run.id)}
            className="flex items-center justify-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition-all shadow-md backdrop-blur-md"
            style={{
              color: 'var(--color-text)',
              backgroundColor: 'var(--color-hover)',
              border: '1px solid var(--color-border)'
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = '#fff'
              e.currentTarget.style.backgroundColor = 'var(--color-error)'
              e.currentTarget.style.borderColor = 'var(--color-error)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'var(--color-text)'
              e.currentTarget.style.backgroundColor = 'var(--color-hover)'
              e.currentTarget.style.borderColor = 'var(--color-border)'
            }}
          >
            <StopCircle size={13} />
            <span className="font-medium tracking-wide">中止生成</span>
          </button>
        </div>
      )}
    </div>
  )
}


// ===== 新版渲染单步结果（支持查看所有历史步骤数据） =====
function StepOutputBlock({ step, index, total, isActiveRun, isCurrentStep }: { step: WorkflowStep; index: number; total: number; isActiveRun: boolean; isCurrentStep: boolean }) {
  const isRunning = step.status === 'running'
  const isCompleted = step.status === 'completed'
  const isFailed = step.status === 'failed'

  // 防御：step.result 可能不是字符串（如 Command 返回了数组/对象），强制转为字符串
  const rawText = typeof step.result === 'string' ? step.result : (step.result ? JSON.stringify(step.result) : '')
  let thinking = ''
  let content = rawText

  const segments = rawText.split(/<think>/)
  if (segments.length > 1) {
    const lastSegment = segments[segments.length - 1]
    const end = lastSegment.indexOf('</think>')
    if (end !== -1) {
      thinking = lastSegment.substring(0, end)
      content = lastSegment.substring(end + 8)
    } else {
      thinking = lastSegment
      content = ''
    }
  }

  // 当前激活的步骤默认展开，过去/未来的默认折叠（只有产生了内容的步骤才允许展开）
  const [expanded, setExpanded] = useState(isCurrentStep)

  // 监听如果步骤被激活，则自动展开
  useEffect(() => {
    let mounted = true
    if (isCurrentStep) {
      Promise.resolve().then(() => {
        if (mounted) setExpanded(true)
      })
    }
    return () => { mounted = false }
  }, [isCurrentStep])

  return (
    <div className="mb-1.5">
      {/* 头部摘要项，点击折叠/展开 */}
      <div
        onClick={() => { if (rawText) setExpanded(!expanded) }}
        className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-colors"
        style={{
          cursor: rawText ? 'pointer' : 'default',
          backgroundColor: isRunning ? 'var(--color-hover)' : 'transparent',
          color: isRunning ? 'var(--color-text)' :
                 isCompleted ? 'var(--color-text-secondary)' :
                 isFailed ? 'var(--color-error)' :
                 'var(--color-text-muted)',
        }}
        title={rawText ? '点击查看该步骤的历史输出' : undefined}
      >
        {/* 状态图标 */}
        <span className="flex-shrink-0 w-4 flex justify-center">
          {isCompleted && <CheckCircle2 size={11} style={{ color: 'var(--color-success)' }} />}
          {isRunning && <Loader2 size={11} className="animate-spin" style={{ color: 'var(--color-accent)' }} />}
          {isFailed && <Circle size={11} style={{ color: 'var(--color-error)', fill: 'var(--color-error)' }} />}
          {(step.status === 'pending' || step.status === 'skipped') && (
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: 'var(--color-border)' }}
            />
          )}
        </span>

        {/* 步骤名 */}
        <span className="truncate flex-1" style={{ fontWeight: isRunning ? 500 : 400 }}>
          {step.name}
        </span>

        {/* 进度 */}
        {isRunning && step.progress !== undefined && (
          <span className="font-mono text-[0.62rem] flex-shrink-0 opacity-60">
            {step.progress}%
          </span>
        )}

        {/* 展开角标或序号 */}
        {(rawText && !isRunning) ? (
          <ChevronRight
            size={11}
            style={{
              transition: 'transform 0.2s',
              transform: expanded ? 'rotate(90deg)' : 'none',
              opacity: 0.4,
            }}
          />
        ) : (
          <span className="font-mono text-[0.6rem] flex-shrink-0 opacity-30">
            {index + 1}/{total}
          </span>
        )}
      </div>

      {/* 展开的对应输出数据 */}
      {expanded && rawText && (
        <div className="pl-[4px] pr-1 pt-1 pb-3 text-xs w-full max-w-full break-words">
          {/* 思维链区域 */}
          {thinking && (
            <ThinkingBlock
              thinking={thinking}
              showCursor={isRunning && isActiveRun && !content}
              hasContent={!!content}
            />
          )}

          {/* 实际正文区域 */}
          {content && (
            <div className="mt-1">
              <MarkdownContent content={content} streaming={isRunning && isActiveRun} />
            </div>
          )}
        </div>
      )}

      {/* 如果是单一正在执行等待，则显示一个等待骨架 */}
      {!rawText && isRunning && isActiveRun && (
        <div className="pl-[4px] pr-1 pt-1 pb-3 text-xs text-center" style={{ color: 'var(--color-text-muted)', opacity: 0.7 }}>
          等待指令响应...
        </div>
      )}
    </div>
  )
}


// ===== 思考区块（Cursor "Worked for" 风格） =====

function ThinkingBlock({ thinking, showCursor, hasContent }: { thinking: string; showCursor: boolean; hasContent: boolean }) {
  // 正文未开始时默认展开，正文开始后默认关闭
  const [expanded, setExpanded] = useState(!hasContent)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let mounted = true
    if (hasContent) {
      Promise.resolve().then(() => {
        if (mounted) setExpanded(false)
      })
    }
    return () => { mounted = false }
  }, [hasContent])

  useEffect(() => {
    if (expanded && scrollRef.current) {
      const el = scrollRef.current
      // 只有在用户没有往上滚拉太多时，才自动贴近底部
      if (el.scrollHeight - el.scrollTop - el.clientHeight < 80) {
        // 使用 requestAnimationFrame 确保在 DOM 更新后执行
        requestAnimationFrame(() => {
          if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
          }
        })
      }
    }
  }, [thinking, expanded])

  return (
    <div className="mb-0.5">
      {/* 可折叠标题按钮 — 参考 Cursor 的 "Worked for Xm" */}
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="group flex items-center gap-1.5 w-full text-left text-xs min-h-6 py-1 select-none transition-colors"
        style={{ color: 'var(--color-text-muted)', opacity: 0.8 }}
        onMouseEnter={e => { e.currentTarget.style.color = 'var(--color-text)' }}
        onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-text-muted)' }}
      >
        <ChevronRight
          size={12}
          style={{
            transition: 'transform 0.2s',
            transform: expanded ? 'rotate(90deg)' : 'none',
          }}
        />
        <span>
          {showCursor ? '思考中...' : '思考过程'}
        </span>
        {showCursor && !expanded && (
          <span className="ai-stream-cursor" style={{ height: 11, width: 3 }} />
        )}
      </button>

      {/* 展开的思考内容 */}
      {expanded && (
        <div
          ref={scrollRef}
          className="ml-0.5 pl-3 border-l-2 py-0.5 mb-2 mt-1 text-xs leading-relaxed whitespace-pre-wrap overflow-y-auto"
          style={{
            borderColor: 'var(--color-border)',
            color: 'var(--color-text-muted)',
            maxHeight: 250,
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
            lineHeight: 1.6,
          }}
        >
          {thinking}
          {showCursor && <span className="ai-stream-cursor" style={{ height: 12, width: 3 }} />}
        </div>
      )}
    </div>
  )
}


// ===== 历史列表 =====

function HistoryList({ items, onSelect }: { items: WorkflowRun[]; onSelect: (id: string) => void }) {
  return (
    <div>
      <p
        className="text-[0.68rem] font-medium mb-2 px-1 uppercase tracking-widest"
        style={{ color: 'var(--color-text-muted)', opacity: 0.7 }}
      >
        历史
      </p>
      <div className="flex flex-col gap-0.5">
        {items.map(run => (
          <button
            key={run.id}
            onClick={() => onSelect(run.id)}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left transition-colors"
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'var(--color-hover)' }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent' }}
          >
            {run.status === 'completed'
              ? <CheckCircle2 size={10} style={{ color: 'var(--color-success)', flexShrink: 0, opacity: 0.6 }} />
              : <Circle size={10} style={{ color: 'var(--color-error)', flexShrink: 0, opacity: 0.6 }} />
            }
            <span className="text-xs truncate flex-1" style={{ color: 'var(--color-text-secondary)' }}>
              {run.title.replace(/^[^\s]+\s/, '')}
            </span>
            <span className="text-[0.6rem] flex-shrink-0 font-mono opacity-30">
              {new Date(run.createdAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
