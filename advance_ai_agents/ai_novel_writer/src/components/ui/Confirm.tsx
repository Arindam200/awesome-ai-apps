/* eslint-disable react-refresh/only-export-components */
/**
 * Vela 异步确认对话框
 *
 * 替代所有 window.confirm() 调用，返回 Promise<boolean>
 * 使用 CSS 动画（dialog-enter / dialog-exit / backdrop-enter）统一进出场效果。
 *
 * 用法：
 *   import { confirm } from '@/components/ui/Confirm'
 *   const ok = await confirm('确定要归档吗？', '归档后可在列表中恢复查看。')
 *   if (ok) { ... }
 */

import { createRoot } from 'react-dom/client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { Button } from './Button'
import { useLocaleStore } from '../../stores/locale-store'

// ===== 内部组件 =====

interface ConfirmOptions {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

interface ConfirmDialogProps extends ConfirmOptions {
  onResolve: (value: boolean) => void
}

function ConfirmDialog({
  title,
  message,
  confirmText,
  cancelText,
  danger = false,
  onResolve,
}: ConfirmDialogProps) {
  const text = useLocaleStore(s => s.text)
  const resolvedTitle = title ?? text('确认操作', 'Confirm action')
  const resolvedConfirmText = confirmText ?? text('确认', 'Confirm')
  const resolvedCancelText = cancelText ?? text('取消', 'Cancel')
  const [isExiting, setIsExiting] = useState(false)
  const confirmBtnRef = useRef<HTMLButtonElement>(null)

  const handleConfirm = () => {
    setIsExiting(true)
    setTimeout(() => onResolve(true), 200)
  }

  const handleCancel = useCallback(() => {
    setIsExiting(true)
    setTimeout(() => onResolve(false), 200)
  }, [onResolve])

  // 进场聚焦确认按钮
  useEffect(() => {
    confirmBtnRef.current?.focus()
  }, [])

  // ESC 关闭（等同取消）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handleCancel])

  return (
    /* 遮罩层 — 统一 CSS 变量和动画 */
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9998,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--color-backdrop)',
        backdropFilter: 'blur(8px)',
        pointerEvents: 'auto',
        /* 为遮罩层的进场同样加入 both 属性防闪烁 */
        animation: isExiting
          ? 'backdrop-exit 0.15s ease-out both'
          : 'backdrop-enter 0.25s ease-out both',
      }}
      onClick={handleCancel}
    >
      {/* 弹窗主体 */}
      <div
        role="dialog"
        aria-modal="true"
        style={{
          backgroundColor: 'var(--color-sidebar)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-2xl)',
          boxShadow: 'var(--shadow-popover)',
          padding: '20px 24px',
          minWidth: 320,
          maxWidth: 460,
          /* CSS 动画，使用 both 从而提前应用 0% 关键帧，彻底杜绝闪烁现象 */
          animation: isExiting
            ? 'dialog-exit 0.15s ease-out both'
            : 'dialog-enter 0.25s var(--transition-spring) both',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* 标题 */}
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)', marginBottom: 10 }}>
          {resolvedTitle}
        </div>

        {/* 消息体 */}
        <div
          style={{
            fontSize: 12,
            color: 'var(--color-text-secondary)',
            lineHeight: 1.65,
            whiteSpace: 'pre-wrap',
            marginBottom: 20,
          }}
        >
          {message}
        </div>

        {/* 按钮区 */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button variant="ghost" size="sm" onClick={handleCancel}>
            {resolvedCancelText}
          </Button>
          <Button
            ref={confirmBtnRef}
            variant={danger ? 'destructive' : 'default'}
            size="sm"
            onClick={handleConfirm}
          >
            {resolvedConfirmText}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ===== 公共 API =====

/**
 * 显示确认对话框，返回 Promise<boolean>
 *
 * @example
 * const ok = await confirm('确定要删除此草稿吗？', { danger: true })
 */
export function confirm(
  message: string,
  options?: Partial<Omit<ConfirmOptions, 'message'>>,
): Promise<boolean> {
  return new Promise(resolve => {
    const container = document.createElement('div')
    document.body.appendChild(container)

    const root = createRoot(container)
    const cleanup = (value: boolean) => {
      root.unmount()
      document.body.removeChild(container)
      resolve(value)
    }

    root.render(
      <ConfirmDialog
        message={message}
        title={options?.title}
        confirmText={options?.confirmText}
        cancelText={options?.cancelText}
        danger={options?.danger}
        onResolve={cleanup}
      />
    )
  })
}
