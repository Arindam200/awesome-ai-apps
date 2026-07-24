import { useEffect, useRef } from 'react'

/** 单条菜单项定义 */
export interface ContextMenuItem {
  /** 唯一 key */
  key: string
  /** 显示标签 */
  label: string
  /** 左侧图标（可选） */
  icon?: React.ReactNode
  /** 右侧快捷键提示（可选） */
  shortcut?: string
  /** 是否禁用 */
  disabled?: boolean
  /** 是否显示为危险操作（红色） */
  danger?: boolean
  /** 点击回调 */
  onClick?: () => void
}

/** 分割线 */
export interface ContextMenuDivider {
  key: string
  type: 'divider'
}

export type ContextMenuEntry = ContextMenuItem | ContextMenuDivider

interface ContextMenuProps {
  /** 菜单项列表 */
  items: ContextMenuEntry[]
  /** 像素位置（clientX / clientY） */
  position: { x: number; y: number }
  /** 请求关闭菜单 */
  onClose: () => void
}

/**
 * 通用右键菜单组件
 * - 自动检测边界、防止溢出屏幕
 * - 点击外部或按 Esc 关闭
 */
export function ContextMenu({ items, position, onClose }: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

  /** 点击外部关闭 */
  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleMouseDown, true)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown, true)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose])

  /** 计算防溢出的最终位置 */
  const MENU_W = 200
  const APPROX_ITEM_H = 28
  const MENU_H = items.length * APPROX_ITEM_H + 16 // 粗略估算菜单高度

  const left = Math.min(position.x, window.innerWidth - MENU_W - 8)
  const top = Math.min(position.y, window.innerHeight - MENU_H - 8)

  return (
    <div
      ref={menuRef}
      className="fixed z-[9999] py-1 select-none"
      style={{
        left,
        top,
        minWidth: MENU_W,
        backgroundColor: 'var(--color-sidebar)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-popover)',
      }}
      onContextMenu={e => e.preventDefault()}
    >
      {items.map(entry => {
        /* 分割线 */
        if ('type' in entry && entry.type === 'divider') {
          return (
            <div
              key={entry.key}
              style={{
                height: 1,
                margin: '4px 8px',
                backgroundColor: 'var(--color-border)',
              }}
            />
          )
        }

        /* 菜单项 */
        const item = entry as ContextMenuItem
        return (
          <button
            key={item.key}
            disabled={item.disabled}
            onClick={() => {
              if (item.disabled) return
              onClose()
              item.onClick?.()
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors"
            style={{
              color: item.disabled
                ? 'var(--color-text-muted)'
                : item.danger
                  ? 'var(--color-error)'
                  : 'var(--color-text)',
              opacity: item.disabled ? 0.45 : 1,
              cursor: item.disabled ? 'not-allowed' : 'pointer',
              backgroundColor: 'transparent',
              fontSize: 12,
            }}
            onMouseEnter={e => {
              if (!item.disabled) {
                e.currentTarget.style.backgroundColor = item.danger
                  ? 'color-mix(in srgb, var(--color-error) 12%, transparent)'
                  : 'var(--color-hover)'
              }
            }}
            onMouseLeave={e => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
          >
            {/* 图标 */}
            {item.icon && (
              <span
                style={{
                  color: item.disabled
                    ? 'var(--color-text-muted)'
                    : item.danger
                      ? 'var(--color-error)'
                      : 'var(--color-text-secondary)',
                  width: 14,
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {item.icon}
              </span>
            )}
            {/* 标签 */}
            <span className="flex-1">{item.label}</span>
            {/* 快捷键 */}
            {item.shortcut && (
              <span
                className="font-mono text-[10px] opacity-40 ml-2 flex-shrink-0"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {item.shortcut}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
