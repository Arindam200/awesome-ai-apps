/* eslint-disable react-refresh/only-export-components */
/**
 * Vela 弹窗报错组件 — JetBrains / VSCode 风格
 *
 * 用于需要用户明确知晓的关键错误（如项目加载失败、文件读写错误等）。
 * 完全使用项目 CSS 变量，自动适配深色 / 浅色主题。
 *
 * 使用 CSS 动画（dialog-enter / dialog-exit / backdrop-enter）统一进出场效果。
 *
 * 用法：
 *   import { alertError } from '@/components/ui/AlertDialog'
 *   alertError('不是有效的 Vela 项目目录', { title: '打开项目失败' })
 */

import { createRoot } from 'react-dom/client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from './Button'
import { useLocaleStore } from '../../stores/locale-store'

// ===== 类型定义 =====

interface AlertOptions {
  /** 弹窗标题，默认「发生错误」 */
  title?: string
  /** 确认按钮文字，默认「确定」 */
  confirmText?: string
}

interface AlertDialogProps extends AlertOptions {
  message: string
  onClose: () => void
}

// ===== 弹窗组件 =====

function AlertDialog({
  title,
  message,
  confirmText,
  onClose,
}: AlertDialogProps) {
  const text = useLocaleStore(s => s.text)
  const resolvedTitle = title ?? text('发生错误', 'Error')
  const resolvedConfirmText = confirmText ?? text('确定', 'OK')
  const [isExiting, setIsExiting] = useState(false)
  const btnRef = useRef<HTMLButtonElement>(null)

  const handleClose = useCallback(() => {
    setIsExiting(true)
    setTimeout(onClose, 200)
  }, [onClose])

  // 进场聚焦确认按钮
  useEffect(() => {
    btnRef.current?.focus()
  }, [])

  // ESC 关闭
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handleClose])

  return (
    /* 遮罩 — 使用统一 CSS 变量和动画 */
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--color-backdrop)',
        backdropFilter: 'blur(8px)',
        pointerEvents: 'auto',
        /* 使用 both 填充模式，让 0% 关键帧在动画前就应用，杜绝闪烁 */
        animation: isExiting
          ? 'backdrop-exit 0.15s ease-out both'
          : 'backdrop-enter 0.25s ease-out both',
      }}
      onClick={handleClose}
    >
      {/* 弹窗主体 */}
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="alert-title"
        aria-describedby="alert-message"
        style={{
          /* 基础样式 */
          backgroundColor: 'var(--color-bg)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-2xl)',
          boxShadow: 'var(--shadow-popover)',
          minWidth: 360,
          maxWidth: 460,
          width: '90vw',
          /* CSS 动画，使用 both 从而提前应用 0% 关键帧，彻底杜绝闪烁现象 */
          animation: isExiting
            ? 'dialog-exit 0.15s ease-out both'
            : 'dialog-enter 0.3s var(--transition-spring) both',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── 标题区 ── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '12px 16px 10px',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          <AlertCircle
            size={15}
            style={{ color: 'var(--color-error)', flexShrink: 0 }}
          />
          <span
            id="alert-title"
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--color-text)',
              lineHeight: 1.3,
              flex: 1,
            }}
          >
          {resolvedTitle}
          </span>
        </div>

        {/* ── 消息体 ── */}
        <div
          id="alert-message"
          style={{
            padding: '14px 16px 16px',
            fontSize: 12,
            lineHeight: 1.7,
            color: 'var(--color-text-secondary)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {message}
        </div>

        {/* ── 按钮区 —— 右对齐，VSCode 风格 ── */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            padding: '0 16px 14px',
          }}
        >
          <Button
            ref={btnRef}
            variant="default"
            size="sm"
            onClick={handleClose}
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
 * 显示弹窗报错，返回 Promise（用户确认后 resolve）。
 * 也可以不 await，fire-and-forget。
 *
 * @example
 * await alertError('不是有效的 Vela 项目目录', { title: '打开项目失败' })
 * alertError('写入失败，请检查磁盘权限。')
 */
export function alertError(
  message: string,
  options?: AlertOptions,
): Promise<void> {
  return new Promise(resolve => {
    const container = document.createElement('div')
    document.body.appendChild(container)

    const root = createRoot(container)
    const cleanup = () => {
      root.unmount()
      document.body.removeChild(container)
      resolve()
    }

    root.render(
      <AlertDialog
        message={message}
        title={options?.title}
        confirmText={options?.confirmText}
        onClose={cleanup}
      />
    )
  })
}
