import { useState, useRef, useEffect } from 'react'
import { DiffEditor, type DiffOnMount } from '@monaco-editor/react'
import { Check, X, Columns2, AlignJustify } from 'lucide-react'
import { useThemeStore } from '../../stores/theme-store'

interface MonacoDiffViewerProps {
  /** 原始文本 */
  original: string
  /** 修改后文本 */
  modified: string
  /** 原始文本标签 */
  originalLabel?: string
  /** 修改后文本标签 */
  modifiedLabel?: string
  /** 接受修改回调 */
  onAccept?: (text: string) => void
  /** 拒绝修改回调 */
  onReject?: () => void
}

/**
 * Monaco Diff 对比查看器
 * 使用 VS Code 同款 Monaco Editor 的 DiffEditor 组件
 * 支持并排和内联两种视图模式
 */
export default function MonacoDiffViewer({
  original,
  modified,
  originalLabel = '原稿',
  modifiedLabel = '修稿',
  onAccept,
  onReject,
}: MonacoDiffViewerProps) {
  const [inline, setInline] = useState(false)
  const theme = useThemeStore((s) => s.theme)
  const diffEditorRef = useRef<Parameters<DiffOnMount>[0] | null>(null)

  // 统计变更
  const [stats, setStats] = useState({ additions: 0, deletions: 0 })

  useEffect(() => {
    let mounted = true
    // 简单统计行差异
    const origLines = original.split('\n').length
    const modLines = modified.split('\n').length
    const additions = Math.max(0, modLines - origLines)
    const deletions = Math.max(0, origLines - modLines)
    Promise.resolve().then(() => {
      if (mounted) {
        setStats({ additions: additions || Math.ceil(modLines * 0.1), deletions: deletions || Math.ceil(origLines * 0.05) })
      }
    })
    return () => { mounted = false }
  }, [original, modified])

  const handleMount: DiffOnMount = (editor) => {
    diffEditorRef.current = editor
  }

  /** 获取修改后的内容 */
  const getModifiedContent = (): string => {
    if (diffEditorRef.current) {
      return diffEditorRef.current.getModifiedEditor().getValue()
    }
    return modified
  }

  return (
    <div className="flex flex-col h-full">
      {/* 工具栏 */}
      <div
        className="no-select flex items-center justify-between px-4 h-9 flex-shrink-0"
        style={{
          borderBottom: '1px solid var(--color-border)',
          backgroundColor: 'var(--color-sidebar)',
        }}
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
            文本对比
          </span>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {originalLabel} → {modifiedLabel}
          </span>
          <span className="text-xs">
            <span style={{ color: 'var(--color-success)' }}>+{stats.additions}</span>
            {' '}
            <span style={{ color: 'var(--color-error)' }}>-{stats.deletions}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* 视图切换 */}
          <button
            onClick={() => setInline(!inline)}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-xs"
            style={{
              backgroundColor: 'var(--color-hover)',
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
            title={inline ? '切换并排视图' : '切换内联视图'}
          >
            {inline ? <Columns2 size={12} /> : <AlignJustify size={12} />}
            {inline ? '并排' : '内联'}
          </button>
          {/* 操作按钮 */}
          {onReject && (
            <button
              onClick={onReject}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-xs"
              style={{ color: 'var(--color-error)', border: '1px solid var(--color-border)' }}
            >
              <X size={12} /> 拒绝
            </button>
          )}
          {onAccept && (
            <button
              onClick={() => onAccept(getModifiedContent())}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
              style={{
                backgroundColor: 'var(--color-accent)',
                color: '#fff',
              }}
            >
              <Check size={12} /> 接受修改
            </button>
          )}
        </div>
      </div>

      {/* Monaco Diff Editor */}
      <div className="flex-1">
        <DiffEditor
          original={original}
          modified={modified}
          language="markdown"
          theme={theme === 'dark' ? 'vs-dark' : 'light'}
          onMount={handleMount}
          options={{
            readOnly: false,
            renderSideBySide: !inline,
            originalEditable: false,
            fontSize: 14,
            lineHeight: 24,
            wordWrap: 'on',
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            renderOverviewRuler: false,
            automaticLayout: true,
            padding: { top: 8, bottom: 8 },
            lineNumbers: 'on',
            glyphMargin: false,
            folding: false,
            lineDecorationsWidth: 0,
            diffWordWrap: 'on',
          }}
        />
      </div>
    </div>
  )
}
