import { useEffect, type RefObject } from 'react'

/**
 * 点击目标元素外部时触发 handler
 *
 * @param ref     需要检测的目标元素 ref
 * @param handler 点击外部时的回调
 * @param enabled 是否启用（默认 true）。可传入 showMenu 状态，菜单关闭时暂停监听以减少 document 事件开销
 *
 * 使用示例：
 * ```tsx
 * const menuRef = useRef<HTMLDivElement>(null)
 * const [open, setOpen] = useState(false)
 * useOutsideClick(menuRef, () => setOpen(false), open)
 * ```
 */
export function useOutsideClick<T extends HTMLElement>(
  ref: RefObject<T | null>,
  handler: () => void,
  enabled = true,
): void {
  useEffect(() => {
    if (!enabled) return
    const listener = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        handler()
      }
    }
    document.addEventListener('mousedown', listener)
    return () => document.removeEventListener('mousedown', listener)
  }, [ref, handler, enabled])
}
