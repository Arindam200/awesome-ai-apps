/* eslint-disable react-refresh/only-export-components */
/**
 * Vela ActionToast — 带操作按钮的增强通知
 *
 * 用于 AI 工作流完成后弹出带操作按钮的通知（如「打开查看」「忽略」）。
 * 基于独立的 React Portal 渲染，不依赖 Toast.tsx 的容器。
 *
 * 使用 CSS 动画类（action-toast-enter / action-toast-exit）统一进出场效果。
 *
 * 用法：
 *   import { actionToast } from '@/components/ui/ActionToast'
 *   actionToast.show({
 *     type: 'success',
 *     message: '✅ 草稿已生成',
 *     actions: [
 *       { label: '打开查看', onClick: () => openDraft() },
 *     ],
 *   })
 */

import { createRoot } from 'react-dom/client'
import { useEffect, useState, useCallback } from 'react'
import { X, CheckCircle2, AlertTriangle, Info, Sparkles } from 'lucide-react'
import { useLocaleStore } from '../../stores/locale-store'

// ===== 类型定义 =====

export type ActionToastType = 'success' | 'info' | 'warning' | 'ai'

export interface ActionToastAction {
  /** 按钮文案 */
  label: string
  /** 点击回调（点击后 Toast 自动关闭） */
  onClick?: () => void | Promise<void>
  /** 按钮风格：主色('primary') 或灰色('ghost') */
  variant?: 'primary' | 'ghost'
}

export interface ActionToastOptions {
  /** 通知类型（决定图标和左边框颜色） */
  type?: ActionToastType
  /** 通知消息 */
  message: string
  /** 操作按钮列表（最多 2 个） */
  actions?: ActionToastAction[]
  /** 自动消失时间（毫秒），设 0 表示不自动消失。默认 8000 */
  duration?: number
}

interface ActionToastItem extends ActionToastOptions {
  id: number
}

// ===== 全局状态 =====

let _counter = 0
let _addItem: ((item: ActionToastItem) => void) | null = null

/** 挂载 ActionToast 容器到 DOM */
function ensureContainer() {
  if (document.getElementById('vela-action-toast-root')) return
  const container = document.createElement('div')
  container.id = 'vela-action-toast-root'
  document.body.appendChild(container)
  createRoot(container).render(<ActionToastContainer />)
}

// ===== 容器组件 =====

function ActionToastContainer() {
  const [items, setItems] = useState<ActionToastItem[]>([])

  useEffect(() => {
    _addItem = (item) => {
      setItems(prev => [...prev, item])
    }
    return () => { _addItem = null }
  }, [])

  const remove = useCallback((id: number) => {
    setItems(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 48,
        right: 20,
        zIndex: 9998,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        pointerEvents: 'none',
      }}
    >
      {items.map(item => (
        <ActionToastCard key={item.id} item={item} onRemove={remove} />
      ))}
    </div>
  )
}

// ===== 单条 ActionToast =====

/** 类型→视觉映射 */
const TYPE_STYLE: Record<ActionToastType, { border: string; icon: React.ReactNode }> = {
  success: {
    border: 'var(--color-success)',
    icon: <CheckCircle2 size={16} style={{ color: 'var(--color-success)', flexShrink: 0 }} />,
  },
  info: {
    border: 'var(--color-info)',
    icon: <Info size={16} style={{ color: 'var(--color-info)', flexShrink: 0 }} />,
  },
  warning: {
    border: 'var(--color-warning)',
    icon: <AlertTriangle size={16} style={{ color: 'var(--color-warning)', flexShrink: 0 }} />,
  },
  ai: {
    border: 'var(--color-accent)',
    icon: <Sparkles size={16} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />,
  },
}

function ActionToastCard({ item, onRemove }: { item: ActionToastItem; onRemove: (id: number) => void }) {
  const [isExiting, setIsExiting] = useState(false)
  const duration = item.duration ?? 8000

  useEffect(() => {
    let t2: ReturnType<typeof setTimeout>
    let t3: ReturnType<typeof setTimeout>
    if (duration > 0) {
      // 退场动画
      t2 = setTimeout(() => setIsExiting(true), duration - 300)
      t3 = setTimeout(() => onRemove(item.id), duration)
    }
    return () => {
      if (t2) clearTimeout(t2)
      if (t3) clearTimeout(t3)
    }
  }, [item.id, duration, onRemove])

  const dismiss = () => {
    setIsExiting(true)
    setTimeout(() => onRemove(item.id), 250)
  }

  const handleAction = async (action: ActionToastAction) => {
    if (action.onClick) {
      await action.onClick()
    }
    dismiss()
  }

  const { border, icon } = TYPE_STYLE[item.type || 'info']

  return (
    <div
      style={{
        pointerEvents: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '12px 14px',
        borderRadius: 'var(--radius-xl)',
        backgroundColor: 'var(--color-sidebar)',
        border: '1px solid var(--color-border)',
        borderLeft: `3px solid ${border}`,
        boxShadow: 'var(--shadow-popover)',
        maxWidth: 400,
        minWidth: 260,
        /* 使用 both 填充模式，让 0% 关键帧在动画前就应用，杜绝闪烁 */
        animation: isExiting
          ? 'action-toast-exit 0.25s ease-out both'
          : 'action-toast-enter 0.3s ease-out both',
      }}
    >
      {/* 第一行：图标 + 消息 + 关闭 */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        {icon}
        <span
          style={{
            flex: 1,
            fontSize: 12,
            lineHeight: 1.6,
            color: 'var(--color-text)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {item.message}
        </span>
        <button
          onClick={dismiss}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 2,
            flexShrink: 0,
            color: 'var(--color-text-muted)',
            lineHeight: 1,
            borderRadius: 'var(--radius-sm)',
            transition: 'color var(--transition-fast)',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--color-text)' }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--color-text-muted)' }}
        >
          <X size={12} />
        </button>
      </div>

      {/* 第二行：操作按钮 */}
      {item.actions && item.actions.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
          {item.actions.map((action, i) => (
            <button
              key={i}
              onClick={() => handleAction(action)}
              style={{
                padding: '4px 12px',
                borderRadius: 'var(--radius-md)',
                fontSize: 11,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
                border: action.variant === 'ghost'
                  ? '1px solid var(--color-border)'
                  : '1px solid transparent',
                backgroundColor: action.variant === 'ghost'
                  ? 'transparent'
                  : 'var(--color-accent)',
                color: action.variant === 'ghost'
                  ? 'var(--color-text-secondary)'
                  : '#fff',
              }}
              onMouseEnter={e => {
                if (action.variant === 'ghost') {
                  e.currentTarget.style.backgroundColor = 'var(--color-hover)'
                } else {
                  e.currentTarget.style.filter = 'brightness(1.1)'
                }
              }}
              onMouseLeave={e => {
                if (action.variant === 'ghost') {
                  e.currentTarget.style.backgroundColor = 'transparent'
                } else {
                  e.currentTarget.style.filter = 'none'
                }
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ===== 公共 API =====

export const actionToast = {
  /**
   * 显示带操作按钮的 Toast 通知
   */
  show: (options: ActionToastOptions) => {
    ensureContainer()
    const item: ActionToastItem = { id: ++_counter, ...options }
    requestAnimationFrame(() => _addItem?.(item))
  },

  /** 工作流完成快捷方法 */
  workflowComplete: (message: string, openAction?: () => void | Promise<void>) => {
    ensureContainer()
    const actions: ActionToastAction[] = []
    if (openAction) {
      const text = useLocaleStore.getState().text
      actions.push({ label: text('打开查看', 'Open'), onClick: openAction })
      actions.push({ label: text('忽略', 'Dismiss'), variant: 'ghost' })
    }
    const item: ActionToastItem = {
      id: ++_counter,
      type: 'ai',
      message,
      actions,
      duration: openAction ? 10000 : 6000,
    }
    requestAnimationFrame(() => _addItem?.(item))
  },
}
