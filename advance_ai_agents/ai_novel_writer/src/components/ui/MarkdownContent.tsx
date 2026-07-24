import React, { useRef, useState } from 'react'
import { Brain, ChevronRight } from 'lucide-react'

interface MarkdownContentProps {
  content: string
  streaming?: boolean
}

/**
 * Markdown 渲染组件（含 <think> 思考过程折叠支持）
 * 用于 Agent 对话、AI 输出面板的正文格式化显示
 */
export default function MarkdownContent({ content, streaming }: MarkdownContentProps) {
  // 解析 <think> 标签：将内容拆分为 [thinking?, ...markdownSegments]
  const segments = parseThinkSegments(content)

  return (
    <div className="assistant-content w-full">
      {segments.map((seg, i) =>
        seg.type === 'think' ? (
          <ThinkingBlock key={`think-${i}`} content={seg.content} streaming={streaming && i === segments.length - 1} />
        ) : (
          <React.Fragment key={`md-${i}`}>
            {renderLines(seg.content.split('\n'))}
          </React.Fragment>
        )
      )}
      {streaming && <StreamingCursor />}
    </div>
  )
}

/** 渲染行列表为 React 元素 */
function renderLines(lines: string[]): React.ReactNode {
  const elements: React.ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // 代码块
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      elements.push(
        <CodeBlock key={i} lang={lang} code={codeLines.join('\n')} />
      )
      i++ // 跳过结束的 ```
      continue
    }

    // H1 ~ H3 标题
    if (line.startsWith('### ')) {
      elements.push(
        <div key={i} className="font-semibold mt-3 mb-1 text-sm"
          style={{ color: 'var(--color-text)' }}>
          {renderInline(line.slice(4))}
        </div>
      )
    } else if (line.startsWith('## ')) {
      elements.push(
        <div key={i} className="font-semibold mt-3 mb-1 text-sm"
          style={{ color: 'var(--color-text)' }}>
          {renderInline(line.slice(3))}
        </div>
      )
    } else if (line.startsWith('# ')) {
      elements.push(
        <div key={i} className="font-bold mt-3 mb-1 text-base"
          style={{ color: 'var(--color-text)' }}>
          {renderInline(line.slice(2))}
        </div>
      )
    }
    // 无序列表
    else if (line.match(/^[-*+] /)) {
      elements.push(
        <div key={i} className="flex gap-1.5 my-0.5">
          <span style={{ color: 'var(--color-text-muted)' }} className="flex-shrink-0 mt-[1px]">•</span>
          <span>{renderInline(line.slice(2))}</span>
        </div>
      )
    }
    // 有序列表
    else if (line.match(/^\d+\. /)) {
      const match = line.match(/^(\d+)\. (.*)$/)
      if (match) {
        elements.push(
          <div key={i} className="flex gap-1.5 my-0.5">
            <span style={{ color: 'var(--color-text-muted)' }} className="flex-shrink-0 min-w-[16px]">
              {match[1]}.
            </span>
            <span>{renderInline(match[2])}</span>
          </div>
        )
      }
    }
    // 分隔线
    else if (line.match(/^---+$/) || line.match(/^===+$/)) {
      elements.push(
        <hr key={i} className="my-2" style={{ borderColor: 'var(--color-border)' }} />
      )
    }
    // 引用块
    else if (line.startsWith('> ')) {
      elements.push(
        <div
          key={i}
          className="pl-3 py-0.5 my-1 text-xs italic"
          style={{
            borderLeft: '3px solid var(--color-accent)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {renderInline(line.slice(2))}
        </div>
      )
    }
    // Markdown 表格（以 | 开头的连续行）
    else if (line.trimStart().startsWith('|')) {
      const tableLines: string[] = [line]
      while (i + 1 < lines.length && lines[i + 1].trimStart().startsWith('|')) {
        i++
        tableLines.push(lines[i])
      }
      elements.push(<MarkdownTable key={i} lines={tableLines} />)
    }
    // 空行
    else if (line.trim() === '') {
      elements.push(<div key={i} className="h-2" />)
    }
    // 普通段落
    else {
      elements.push(
        <p key={i} className="my-0.5 leading-relaxed">
          {renderInline(line)}
        </p>
      )
    }

    i++
  }

  return elements
}

/** 内联格式渲染（加粗、斜体、行内代码） */
function renderInline(text: string): React.ReactNode {
  // 将文本按 **bold**、*italic*、`code` 分割渲染
  const parts: React.ReactNode[] = []
  // 简单的正则分割处理
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(text)) !== null) {
    // 文字前的普通文本
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }

    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={match.index} className="font-semibold"
          style={{ color: 'var(--color-text)' }}>
          {token.slice(2, -2)}
        </strong>
      )
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(<em key={match.index}>{token.slice(1, -1)}</em>)
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={match.index}
          className="px-1 py-0.5 rounded text-xs font-mono"
          style={{
            backgroundColor: 'var(--color-hover)',
            color: 'var(--color-accent)',
            border: '1px solid var(--color-border)',
          }}
        >
          {token.slice(1, -1)}
        </code>
      )
    }

    lastIndex = match.index + token.length
  }

  // 剩余文本
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }

  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : parts
}

// ===== 代码块组件 =====

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const codeRef = useRef<HTMLElement>(null)

  const handleCopy = () => {
    navigator.clipboard.writeText(code).catch(() => {})
  }

  return (
    <div
      className="my-2 rounded-lg overflow-hidden"
      style={{ border: '1px solid var(--color-border)' }}
    >
      {/* 代码块标题栏 */}
      <div
        className="flex items-center justify-between px-3 py-1.5"
        style={{
          backgroundColor: 'var(--color-hover)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <span className="text-[0.7rem] font-mono" style={{ color: 'var(--color-text-muted)' }}>
          {lang || 'text'}
        </span>
        <button
          onClick={handleCopy}
          className="text-[0.7rem] px-2 py-0.5 rounded transition-opacity hover:opacity-100 opacity-60"
          style={{ color: 'var(--color-text-secondary)' }}
          onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-border)')}
          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
        >
          复制
        </button>
      </div>
      {/* 代码内容 */}
      <pre
        className="p-3 text-xs leading-relaxed font-mono whitespace-pre-wrap break-all"
        style={{
          backgroundColor: 'var(--color-editor-bg)',
          color: 'var(--color-text)',
          margin: 0,
        }}
      >
        <code ref={codeRef}>{code}</code>
      </pre>
    </div>
  )
}

// ===== 流式光标 =====

/** 流式生成时末尾显示的闪烁光标 */
export function StreamingCursor() {
  return (
    <span
      className="inline-block w-[3px] h-3 ml-0.5 rounded-sm align-middle"
      style={{
        backgroundColor: 'var(--color-accent)',
        animation: 'agent-cursor-blink 0.8s ease-in-out infinite',
      }}
    />
  )
}

// ===== ThinkingBlock — 可折叠的思考过程区块 =====

function ThinkingBlock({ content, streaming }: { content: string; streaming?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const trimmed = content.trim()
  if (!trimmed && !streaming) return null

  return (
    <div
      className="my-2 rounded-lg overflow-hidden transition-all duration-200"
      style={{
        border: '1px solid var(--color-border)',
        backgroundColor: 'rgba(var(--accent-rgb, 99, 102, 241), 0.03)',
      }}
    >
      {/* 头部：点击可展开/折叠 */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors"
        style={{ color: 'var(--color-text-muted)' }}
        onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-hover)')}
        onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
      >
        <Brain size={13} style={{ color: 'var(--color-accent)', opacity: 0.7 }} />
        <span className="font-medium" style={{ color: 'var(--color-text-secondary)' }}>
          {streaming ? '正在思考…' : '思考过程'}
        </span>
        {streaming && (
          <span
            className="inline-block w-1.5 h-1.5 rounded-full ml-1"
            style={{
              backgroundColor: 'var(--color-accent)',
              animation: 'tool-pulse 1.2s ease-in-out infinite',
            }}
          />
        )}
        <ChevronRight
          size={12}
          className="ml-auto transition-transform duration-200"
          style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}
        />
      </button>

      {/* 内容区（折叠/展开） */}
      {expanded && (
        <div
          className="px-3 pb-2 text-xs leading-relaxed"
          style={{
            color: 'var(--color-text-muted)',
            borderTop: '1px solid var(--color-border)',
            maxHeight: 300,
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {trimmed}
        </div>
      )}
    </div>
  )
}

// ===== Markdown 表格渲染 =====

/** 解析并渲染 Markdown 表格 */
function MarkdownTable({ lines }: { lines: string[] }) {
  // 解析表格单元格
  const parseRow = (line: string): string[] =>
    line.split('|').slice(1, -1).map(cell => cell.trim())

  if (lines.length < 2) {
    // 不足两行（至少表头 + 分隔线）
    return <p className="my-0.5 leading-relaxed">{lines.join('\n')}</p>
  }

  const headerCells = parseRow(lines[0])
  // 跳过分隔线（第二行通常是 |---|---|）
  const startRow = lines[1].includes('---') ? 2 : 1
  const bodyRows = lines.slice(startRow).map(parseRow)

  return (
    <div className="my-2 overflow-x-auto rounded-md" style={{ border: '1px solid var(--color-border)' }}>
      <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ backgroundColor: 'var(--color-hover)' }}>
            {headerCells.map((cell, j) => (
              <th
                key={j}
                className="px-3 py-1.5 text-left font-semibold"
                style={{
                  color: 'var(--color-text)',
                  borderBottom: '1px solid var(--color-border)',
                  whiteSpace: 'nowrap',
                }}
              >
                {renderInline(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, ri) => (
            <tr
              key={ri}
              style={{
                borderBottom: ri < bodyRows.length - 1 ? '1px solid var(--color-border)' : undefined,
              }}
              onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-hover)')}
              onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ===== <think> 标签解析 =====

interface ContentSegment {
  type: 'think' | 'markdown'
  content: string
}

/**
 * 将内容按 <think>...</think> 标签拆分为段落
 * 支持流式场景下未闭合的 <think> 标签
 */
function parseThinkSegments(content: string): ContentSegment[] {
  const segments: ContentSegment[] = []
  const thinkOpenRegex = /<think>/gi
  const thinkCloseRegex = /<\/think>/gi

  let lastIndex = 0
  let openMatch: RegExpExecArray | null

  while ((openMatch = thinkOpenRegex.exec(content)) !== null) {
    // 提取 <think> 之前的 markdown 内容
    if (openMatch.index > lastIndex) {
      const md = content.slice(lastIndex, openMatch.index).trim()
      if (md) segments.push({ type: 'markdown', content: md })
    }

    // 查找对应的 </think>
    thinkCloseRegex.lastIndex = openMatch.index + openMatch[0].length
    const closeMatch = thinkCloseRegex.exec(content)

    if (closeMatch) {
      // 找到闭合标签
      const thinkContent = content.slice(openMatch.index + openMatch[0].length, closeMatch.index)
      segments.push({ type: 'think', content: thinkContent })
      lastIndex = closeMatch.index + closeMatch[0].length
      thinkOpenRegex.lastIndex = lastIndex
    } else {
      // 未闭合（流式场景）—— 将剩余全部作为思考内容
      const thinkContent = content.slice(openMatch.index + openMatch[0].length)
      segments.push({ type: 'think', content: thinkContent })
      lastIndex = content.length
      break
    }
  }

  // 剩余的 markdown 内容
  if (lastIndex < content.length) {
    const md = content.slice(lastIndex).trim()
    if (md) segments.push({ type: 'markdown', content: md })
  }

  // 如果没有 <think> 标签，直接返回整体
  if (segments.length === 0) {
    segments.push({ type: 'markdown', content })
  }

  return segments
}
