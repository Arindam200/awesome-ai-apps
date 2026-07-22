/**
 * MentionMenu — @ 提及选择菜单
 *
 * 用户输入 @ 时弹出的上下文资源选择面板。
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { searchMentionTargets, type MentionTarget } from '../../../services/agent/intent-router'

interface Props {
  /** 搜索关键词（@ 后面的文字） */
  query: string
  /** 选择提及目标的回调 */
  onSelect: (target: MentionTarget) => void
  /** 关闭菜单 */
  onClose: () => void
  /** 菜单位置 */
  position?: { bottom: number; left: number }
}

export default function MentionMenu({ query, onSelect, onClose, position }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const menuRef = useRef<HTMLDivElement>(null)

  const results = searchMentionTargets(query)

  const [prevQuery, setPrevQuery] = useState(query)

  if (query !== prevQuery) {
    setSelectedIndex(0)
    setPrevQuery(query)
  }

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (results[selectedIndex]) {
        onSelect(results[selectedIndex])
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }, [results, selectedIndex, onSelect, onClose])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  if (results.length === 0) return null

  return (
    <div
      ref={menuRef}
      className="absolute z-50 py-1 rounded-lg shadow-lg"
      style={{
        bottom: position?.bottom ?? 'calc(100% + 4px)',
        left: position?.left ?? 0,
        width: 240,
        maxHeight: 260,
        overflowY: 'auto',
        backgroundColor: 'var(--color-sidebar)',
        border: '1px solid var(--color-border)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
      }}
    >
      <div className="text-[0.68rem] px-3 py-1" style={{ color: 'var(--color-text-muted)' }}>
        引用上下文
      </div>
      {results.map((target, i) => (
        <button
          key={target.value}
          onClick={() => onSelect(target)}
          className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-left transition-colors"
          style={{
            backgroundColor: i === selectedIndex ? 'var(--color-hover)' : 'transparent',
            color: 'var(--color-text)',
          }}
          onMouseEnter={() => setSelectedIndex(i)}
        >
          <span className="text-sm">{target.icon}</span>
          <span className="font-medium">{target.displayName}</span>
        </button>
      ))}
    </div>
  )
}
