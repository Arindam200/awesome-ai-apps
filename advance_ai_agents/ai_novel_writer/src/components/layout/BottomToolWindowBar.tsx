import { Zap, ScrollText, Cpu } from 'lucide-react'
import { useLayoutStore, type BottomTab } from '../../stores/layout-store'
import { useWorkflowStore } from '../../stores/workflow-store'
import { useLocaleStore } from '../../stores/locale-store'

/** 底部工具窗口每个 Tab 对应的按钮配置 */
const bottomTabs: Array<{ id: BottomTab; icon: typeof Zap; zh: string; en: string }> = [
  { id: 'tasks',  icon: Zap,        zh: '任务', en: 'Tasks' },
  { id: 'log',    icon: ScrollText, zh: '日志', en: 'Logs' },
  { id: 'models', icon: Cpu,        zh: '模型', en: 'Models' },
]

/**
 * 底部工具窗口左侧按钮栏（BottomToolWindowBar）
 * JetBrains 风格：28px 宽，纯图标 + title tooltip，激活时右侧 2px 竖线
 * 对应截图左下角红框区域
 */
export default function BottomToolWindowBar() {
  const bottomTab = useLayoutStore(s => s.bottomTab)
  const setBottomTab = useLayoutStore(s => s.setBottomTab)
  const activeRuns = useWorkflowStore(s => s.activeRuns)
  const text = useLocaleStore(s => s.text)

  return (
    <div
      className="no-select flex flex-col items-center justify-start h-full py-0.5"
      style={{
        width: 'var(--width-bottom-bar)',  /* 28px */
        backgroundColor: 'var(--color-activity-bar)',
        borderRight: '1px solid var(--color-border)',
        flexShrink: 0,
      }}
    >
      {bottomTabs.map(({ id, icon: Icon, zh, en }) => {
        const label = text(zh, en)
        const isActive = bottomTab === id
        // 任务Tab：任何工作流运行中时显示脉冲小点
        const hasRunning = activeRuns.some(r => r.status === 'running')
        const hasWaiting = activeRuns.some(r => r.status === 'waiting')
        const showPulse = id === 'tasks' && (hasRunning || hasWaiting)

        return (
          <div key={id} className="relative w-full">
            <button
              onClick={() => setBottomTab(id)}
              title={label}
              className="bottom-tool-btn"
              style={{
                boxShadow: isActive
                  ? 'inset -2px 0 0 var(--color-accent)'
                  : 'none',
                color: isActive
                  ? 'var(--color-accent)'
                  : 'var(--color-activity-icon)',
              }}
            >
              <Icon size={13} strokeWidth={isActive ? 2 : 1.5} />
            </button>
            {/* 状态脉冲点（工作流运行中） */}
            {showPulse && (
              <span
                className="absolute top-[3px] right-[3px] w-[5px] h-[5px] rounded-full animate-pulse pointer-events-none"
                style={{
                  backgroundColor: hasWaiting && !hasRunning
                    ? 'var(--color-warning)'
                    : 'var(--color-accent)',
                }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
