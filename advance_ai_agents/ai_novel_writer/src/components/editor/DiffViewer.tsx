import { useState, useMemo } from 'react'
import { ArrowLeftRight, Check, X } from 'lucide-react'

interface DiffViewerProps {
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

interface DiffLine {
  type: 'same' | 'add' | 'remove'
  content: string
  lineOld?: number
  lineNew?: number
}

/**
 * 文本对比查看器 — 并排显示原文和修改后的差异
 * 类似 VS Code 的 diff 视图
 */
export default function DiffViewer({
  original,
  modified,
  originalLabel = '原稿',
  modifiedLabel = '修稿',
  onAccept,
  onReject,
}: DiffViewerProps) {
  const [mode, setMode] = useState<'side' | 'inline'>('side')

  // 计算差异
  const diffLines = useMemo(() => computeDiff(original, modified), [original, modified])

  // 统计
  const addCount = diffLines.filter((d) => d.type === 'add').length
  const removeCount = diffLines.filter((d) => d.type === 'remove').length

  return (
    <div className="flex flex-col h-full">
      {/* 头部工具栏 */}
      <div
        className="no-select flex items-center justify-between px-4 h-9 flex-shrink-0"
        style={{
          borderBottom: '1px solid var(--color-border)',
          backgroundColor: 'var(--color-sidebar)',
        }}
      >
        <div className="flex items-center gap-3">
          <ArrowLeftRight size={14} style={{ color: 'var(--color-accent)' }} />
          <span className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
            文本对比
          </span>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            <span style={{ color: 'var(--color-success)' }}>+{addCount}</span>
            {' '}
            <span style={{ color: 'var(--color-error)' }}>-{removeCount}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* 视图切换 */}
          <button
            onClick={() => setMode(mode === 'side' ? 'inline' : 'side')}
            className="px-2 py-0.5 rounded text-xs"
            style={{
              backgroundColor: 'var(--color-hover)',
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
          >
            {mode === 'side' ? '并排视图' : '内联视图'}
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
              onClick={() => onAccept(modified)}
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

      {/* Diff 内容 */}
      {mode === 'side' ? (
        <SideBySideView diffLines={diffLines} originalLabel={originalLabel} modifiedLabel={modifiedLabel} />
      ) : (
        <InlineView diffLines={diffLines} />
      )}
    </div>
  )
}

/** 并排视图 */
function SideBySideView({ diffLines, originalLabel, modifiedLabel }: {
  diffLines: DiffLine[]; originalLabel: string; modifiedLabel: string
}) {
  return (
    <div className="flex flex-1 overflow-hidden">
      {/* 左侧：原文 */}
      <div className="flex-1 flex flex-col" style={{ borderRight: '1px solid var(--color-border)' }}>
        <div
          className="px-3 py-1 text-xs font-medium flex-shrink-0"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--color-error) 6%, transparent)',
            color: 'var(--color-error)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          {originalLabel}
        </div>
        <div className="flex-1 overflow-y-auto font-mono text-xs leading-5">
          {diffLines
            .filter((d) => d.type !== 'add')
            .map((d, i) => (
              <div
                key={i}
                className="px-3 py-0.5"
                style={{
                  backgroundColor: d.type === 'remove' ? 'color-mix(in srgb, var(--color-error) 8%, transparent)' : 'transparent',
                  color: d.type === 'remove' ? 'var(--color-error)' : 'var(--color-text)',
                }}
              >
                <span className="inline-block w-8 text-right mr-2 opacity-30">{d.lineOld ?? ''}</span>
                {d.type === 'remove' && <span className="mr-1">-</span>}
                {d.content}
              </div>
            ))}
        </div>
      </div>

      {/* 右侧：修改后 */}
      <div className="flex-1 flex flex-col">
        <div
          className="px-3 py-1 text-xs font-medium flex-shrink-0"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--color-success) 6%, transparent)',
            color: 'var(--color-success)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          {modifiedLabel}
        </div>
        <div className="flex-1 overflow-y-auto font-mono text-xs leading-5">
          {diffLines
            .filter((d) => d.type !== 'remove')
            .map((d, i) => (
              <div
                key={i}
                className="px-3 py-0.5"
                style={{
                  backgroundColor: d.type === 'add' ? 'color-mix(in srgb, var(--color-success) 8%, transparent)' : 'transparent',
                  color: d.type === 'add' ? 'var(--color-success)' : 'var(--color-text)',
                }}
              >
                <span className="inline-block w-8 text-right mr-2 opacity-30">{d.lineNew ?? ''}</span>
                {d.type === 'add' && <span className="mr-1">+</span>}
                {d.content}
              </div>
            ))}
        </div>
      </div>
    </div>
  )
}

/** 内联视图 */
function InlineView({ diffLines }: { diffLines: DiffLine[] }) {
  return (
    <div className="flex-1 overflow-y-auto font-mono text-xs leading-5 p-0">
      {diffLines.map((d, i) => (
        <div
          key={i}
          className="px-4 py-0.5"
          style={{
            backgroundColor:
              d.type === 'add' ? 'color-mix(in srgb, var(--color-success) 8%, transparent)'
              : d.type === 'remove' ? 'color-mix(in srgb, var(--color-error) 8%, transparent)'
              : 'transparent',
            color:
              d.type === 'add' ? 'var(--color-success)'
              : d.type === 'remove' ? 'var(--color-error)'
              : 'var(--color-text)',
          }}
        >
          <span className="inline-block w-8 text-right mr-1 opacity-30">{d.lineOld ?? ''}</span>
          <span className="inline-block w-8 text-right mr-2 opacity-30">{d.lineNew ?? ''}</span>
          <span className="mr-1">{d.type === 'add' ? '+' : d.type === 'remove' ? '-' : ' '}</span>
          {d.content}
        </div>
      ))}
    </div>
  )
}

/**
 * 简单行级 diff 算法（LCS-based）
 * 生产环境建议替换为 diff-match-patch 或类似库
 */
function computeDiff(original: string, modified: string): DiffLine[] {
  const oldLines = original.split('\n')
  const newLines = modified.split('\n')

  // 简化实现：逐行对比，使用 LCS 找出公共子序列
  const lcs = longestCommonSubsequence(oldLines, newLines)
  const result: DiffLine[] = []

  let oldIdx = 0
  let newIdx = 0
  let oldLineNum = 1
  let newLineNum = 1

  for (const common of lcs) {
    // 输出 old 中在 common 之前的删除行
    while (oldIdx < oldLines.length && oldLines[oldIdx] !== common) {
      result.push({ type: 'remove', content: oldLines[oldIdx], lineOld: oldLineNum++ })
      oldIdx++
    }
    // 输出 new 中在 common 之前的新增行
    while (newIdx < newLines.length && newLines[newIdx] !== common) {
      result.push({ type: 'add', content: newLines[newIdx], lineNew: newLineNum++ })
      newIdx++
    }
    // 公共行
    result.push({ type: 'same', content: common, lineOld: oldLineNum++, lineNew: newLineNum++ })
    oldIdx++
    newIdx++
  }

  // 处理尾部
  while (oldIdx < oldLines.length) {
    result.push({ type: 'remove', content: oldLines[oldIdx++], lineOld: oldLineNum++ })
  }
  while (newIdx < newLines.length) {
    result.push({ type: 'add', content: newLines[newIdx++], lineNew: newLineNum++ })
  }

  return result
}

/** 最长公共子序列（行级） */
function longestCommonSubsequence(a: string[], b: string[]): string[] {
  const m = a.length
  const n = b.length

  // 优化：对于大文本只取前后各 500 行
  if (m > 1000 || n > 1000) {
    return simpleFallback(a, b)
  }

  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }

  // 回溯
  const result: string[] = []
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      result.unshift(a[i - 1])
      i--
      j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }

  return result
}

/** 大文本降级：只保留完全相同的行 */
function simpleFallback(a: string[], b: string[]): string[] {
  const bSet = new Set(b)
  return a.filter((line) => bSet.has(line))
}
