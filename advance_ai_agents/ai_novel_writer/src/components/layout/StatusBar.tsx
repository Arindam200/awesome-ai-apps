import { useState, useEffect } from 'react'
import { Wifi, BookOpen, CheckCircle2, FolderOpen } from 'lucide-react'
import { useProjectStore } from '../../stores/project-store'
import { useLLMStore } from '../../stores/llm-store'
import { useLayoutStore } from '../../stores/layout-store'
import { useWorkflowStore } from '../../stores/workflow-store'
import { APP_BRAND } from '../../shared/brand'
import { useLocaleStore } from '../../stores/locale-store'

/** 底部状态栏 — JetBrains 风格：22px、深灰底、多分段、hover 可点击感 */
export default function StatusBar() {
  const currentProject = useProjectStore((s) => s.currentProject)
  const models = useLLMStore(s => s.models)
  const defaultModelId = useLLMStore(s => s.defaultModelId)
  const openSettings = useLayoutStore(s => s.openSettings)
  const defaultModel = models.find(
    (m) => m.id === defaultModelId && m.purposes?.some((p) => p !== 'embedding')
  )
  const text = useLocaleStore(s => s.text)

  return (
    <div
      className="writer-statusbar no-select flex items-center justify-between"
      style={{
        height: 'var(--height-statusbar)',
        fontSize: "0.75rem",
        flexShrink: 0,
      }}
    >
      {/* 左侧 */}
      <div className="flex items-center h-full">
        <StatusBarSegment title={text(APP_BRAND.zhName, APP_BRAND.enName)}>
          <BookOpen size={11} />
          <span className="font-medium brand-gradient">{APP_BRAND.shortName}</span>
          <span className="opacity-80 brand-gradient">v{__APP_VERSION__}</span>
        </StatusBarSegment>

        {currentProject && (
          <>
            <StatusBarDivider />
            <StatusBarSegment title={currentProject.path}>
              <FolderOpen size={11} style={{ opacity: 0.7 }} />
              <span className="opacity-80 max-w-[180px] truncate">{currentProject.name}</span>
            </StatusBarSegment>
          </>
        )}

      </div>

      {/* 右侧：AI 胶囊 + 模型名 */}
      <div className="flex items-center h-full">
        {/* AI 任务胶囊指示器（右下角） */}
        <AITaskCapsule />

        {defaultModel ? (
          <StatusBarSegment
            title={text(`当前模型：${defaultModel.name}`, `Current model: ${defaultModel.name}`)}
            onClick={openSettings}
          >
            <Wifi size={11} />
            <span className="opacity-80 max-w-[120px] truncate">{defaultModel.name}</span>
          </StatusBarSegment>
        ) : (
          <StatusBarSegment
            title={text('点击配置模型', 'Click to configure a model')}
            onClick={openSettings}
          >
            <span className="opacity-50">{text('未配置模型', 'No model configured')}</span>
          </StatusBarSegment>
        )}
      </div>
    </div>
  )
}


// ===== AI 任务胶囊指示器（Layer 1）=====

/**
 * StatusBar 中心区域的 AI 工作流胶囊
 * - 无任务时不渲染
 * - 有任务时显示步骤名 + 微型进度条 + 百分比
 * - 多任务时显示 "N个任务运行中"
 * - 完成后短暂显示完成态然后淡出
 */
function AITaskCapsule() {
  const text = useLocaleStore(s => s.text)
  // 使用 selector 精确订阅，避免 globalLogs 等高频字段导致被动重渲染
  const activeRuns = useWorkflowStore(s => s.activeRuns)
  const getActiveStepInfo = useWorkflowStore(s => s.getActiveStepInfo)
  // 使用 string 而非 object，避免引用变化导致不必要的 effect 重触发
  const [completedTitle, setCompletedTitle] = useState<string | null>(null)

  // 监听任务从有到无的转换，短暂显示完成态
  useEffect(() => {
    if (activeRuns.length === 0 && completedTitle) {
      const timer = setTimeout(() => setCompletedTitle(null), 1800)
      return () => clearTimeout(timer)
    }
  }, [activeRuns.length, completedTitle])

  // 监听任务完成事件：当活跃列表刚变为空时触发（只依赖 activeRuns.length）
  useEffect(() => {
    if (activeRuns.length > 0) return // 还有活跃任务，不做操作
    const { history } = useWorkflowStore.getState()
    if (history.length > 0) {
      const latest = history[0]
      if (latest.status === 'completed') {
        // 使用函数式更新，只有值实际不同时才触发重渲染
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setCompletedTitle(prev => {
          const newTitle = latest.title
          return prev === newTitle ? prev : newTitle
        })
      }
    }
  }, [activeRuns.length])

  const stepInfo = getActiveStepInfo()

  // 完成态渲染
  if (!stepInfo && completedTitle) {
    return (
      <div
        className="ai-task-capsule ai-task-capsule--complete"
        onClick={() => useLayoutStore.getState().openRightPanel('ai-output')}
      >
        <CheckCircle2 size={10} />
        <span className="truncate">
          {text(`${completedTitle.replace(/^[^\s]+\s/, '')} 完成`, `${completedTitle.replace(/^[^\s]+\s/, '')} complete`)}
        </span>
      </div>
    )
  }

  // 无任务
  if (!stepInfo) return null

  const { stepName, progress, total, completed } = stepInfo

  // 多任务模式
  if (activeRuns.length > 1) {
    return (
      <div
        className="ai-task-capsule"
        onClick={() => useLayoutStore.getState().openRightPanel('ai-output')}
        title={text('点击查看任务进度', 'View task progress')}
      >
        {/* 脉冲圆点 */}
        <span
          className="w-[5px] h-[5px] rounded-full animate-pulse flex-shrink-0"
          style={{ backgroundColor: 'var(--color-accent)' }}
        />
        <span>{text(`${activeRuns.length}个任务运行中...`, `${activeRuns.length} tasks running...`)}</span>
      </div>
    )
  }

  // 单任务模式：步骤名 + 微型进度条 + 百分比
  const effectiveProgress = Math.max(5, progress)
  return (
    <div
      className="ai-task-capsule"
      onClick={() => useLayoutStore.getState().openRightPanel('ai-output')}
      title={text('点击查看 AI 输出详情', 'View AI output')}
    >
      {/* 脉冲圆点 */}
      <span
        className="w-[5px] h-[5px] rounded-full animate-pulse flex-shrink-0"
        style={{ backgroundColor: 'var(--color-accent)' }}
      />
      {/* 步骤名（截断） */}
      <span className="truncate max-w-[120px]">{stepName}</span>
      {/* 微型进度条 */}
      <div
        style={{
          width: 40,
          height: 2,
          borderRadius: 1,
          backgroundColor: 'rgba(var(--color-accent-rgb), 0.2)',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${effectiveProgress}%`,
            backgroundColor: 'var(--color-accent)',
            borderRadius: 1,
            transition: 'width 0.5s ease',
          }}
        />
      </div>
      {/* 进度百分比 */}
      <span className="font-mono text-[0.62rem] flex-shrink-0 opacity-80">
        {completed}/{total}
      </span>
    </div>
  )
}


/** 状态栏分段（可点击） */
function StatusBarSegment({
  children,
  title,
  onClick,
}: {
  children: React.ReactNode
  title?: string
  onClick?: () => void
}) {
  return (
    <div
      className="writer-statusbar-segment flex items-center gap-1 px-2 h-full cursor-default transition-colors"
      title={title}
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
      onMouseEnter={e => {
        if (onClick) {
          e.currentTarget.style.backgroundColor = 'rgba(255, 244, 223, 0.08)'
        }
      }}
      onMouseLeave={e => {
        e.currentTarget.style.backgroundColor = 'transparent'
      }}
    >
      {children}
    </div>
  )
}

/** 状态栏分隔符 */
function StatusBarDivider() {
  return (
    <span style={{ opacity: 0.25, fontSize: "0.75rem", userSelect: 'none' }}>|</span>
  )
}
