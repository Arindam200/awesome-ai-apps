import { useState } from 'react'
import { AlertTriangle, CheckCircle, Info, Sparkles, HelpCircle, Quote } from 'lucide-react'
import { cn } from '../../lib/utils'
import { Button } from '../ui/Button'
import {
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from '../ui/Dialog'

/** 审稿问题条目（JSON 格式） */
interface ReviewIssue {
  category: string
  severity: 'error' | 'warning' | 'pass'
  description: string
  /** 引用的原文片段（有问题时提供） */
  quote?: string
}

/** AI 返回的 JSON 审稿结构 */
interface ReviewJSON {
  items: Array<{
    category: string
    severity: string
    description: string
    quote?: string
  }>
  summary: string
}

interface ReviewReportProps {
  /** 原始审稿报告文本（JSON 或旧版 markdown） */
  reportText: string
  /** 审稿报告关联的草稿路径（用于触发修稿） */
  draftPath?: string
  /** 章节号 */
  chapterNumber?: number
  /** 章节目录 */
  chapterDir?: string
}

// ===== 解析器 =====

/** 标准化 severity 值 */
function normalizeSeverity(raw: string): ReviewIssue['severity'] {
  const s = raw.toLowerCase().trim()
  if (s === 'error' || s === 'critical' || s === 'severe') return 'error'
  if (s === 'warning' || s === 'warn' || s === 'minor') return 'warning'
  return 'pass'
}

/** 尝试从文本中提取 JSON（兼容 ```json 包裹） */
function extractJSON(text: string): string | null {
  // 先尝试直接解析
  const trimmed = text.trim()
  if (trimmed.startsWith('{')) return trimmed

  // 尝试从 ```json ... ``` 中提取
  const codeBlockMatch = trimmed.match(/```(?:json)?\s*\n?([\s\S]*?)```/)
  if (codeBlockMatch) return codeBlockMatch[1].trim()

  // 尝试找第一个 { 和最后一个 }
  const firstBrace = trimmed.indexOf('{')
  const lastBrace = trimmed.lastIndexOf('}')
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    return trimmed.slice(firstBrace, lastBrace + 1)
  }

  return null
}

/** 解析审稿报告（优先 JSON，回退到旧版文本解析） */
function parseReport(text: string): { issues: ReviewIssue[]; summary: string } {
  const jsonStr = extractJSON(text)
  if (jsonStr) {
    try {
      const data = JSON.parse(jsonStr) as ReviewJSON
      if (data.items && Array.isArray(data.items)) {
        const issues: ReviewIssue[] = data.items.map(item => ({
          category: item.category || '综合检查',
          severity: normalizeSeverity(item.severity),
          description: item.description || '',
          quote: item.quote || undefined,
        }))
        return { issues, summary: data.summary || '' }
      }
    } catch {
      // JSON 解析失败，回退到文本解析
    }
  }

  // 回退：旧版 markdown 文本解析（兼容历史数据）
  return parseLegacyReport(text)
}

/** 旧版文本解析器（兼容历史审稿报告） */
function parseLegacyReport(text: string): { issues: ReviewIssue[]; summary: string } {
  const issues: ReviewIssue[] = []
  const lines = text.split('\n')
  let currentCategory = '综合检查'
  const summaryLines: string[] = []
  let inSummary = false

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue

    // 匹配标题行
    const headingMatch = trimmed.match(/^#{2,3}\s+(.+)/)
    if (headingMatch) {
      const heading = headingMatch[1].replace(/[*_]/g, '')
      if (/总体评价|总结|总评/.test(heading)) {
        inSummary = true
      } else {
        inSummary = false
        currentCategory = heading
      }
      continue
    }

    if (inSummary) {
      summaryLines.push(trimmed.replace(/^[-*]\s*/, ''))
      continue
    }

    // 检测 emoji 严重级别
    let severity: ReviewIssue['severity'] = 'pass'
    if (trimmed.includes('🔴')) severity = 'error'
    else if (trimmed.includes('🟡')) severity = 'warning'
    else if (trimmed.includes('🟢') || trimmed.includes('✅')) severity = 'pass'
    else if (trimmed.startsWith('-') || trimmed.startsWith('*')) severity = 'warning'
    else continue

    const cleanDesc = trimmed
      .replace(/^[-*]\s*/, '')
      .replace(/[🔴🟡🟢✅]\s*/u, '')
      .replace(/\*\*/g, '')

    if (cleanDesc) {
      issues.push({ category: currentCategory, severity, description: cleanDesc })
    }
  }

  return { issues, summary: summaryLines.join(' ') }
}

// ===== 视觉配置 =====

const SEVERITY_META: Record<ReviewIssue['severity'], {
  label: string
  emoji: string
  actionLabel: string
  colorClass: string
  bgClass: string
  borderClass: string
}> = {
  error: {
    label: '严重问题',
    emoji: '🔴',
    actionLabel: '强烈建议修复',
    colorClass: 'text-red-400',
    bgClass: 'bg-red-500/10',
    borderClass: 'border-red-500/30',
  },
  warning: {
    label: '改进建议',
    emoji: '🟡',
    actionLabel: '建议酌情修复',
    colorClass: 'text-yellow-400',
    bgClass: 'bg-yellow-500/10',
    borderClass: 'border-yellow-500/30',
  },
  pass: {
    label: '检查通过',
    emoji: '🟢',
    actionLabel: '无需处理',
    colorClass: 'text-green-400',
    bgClass: 'bg-green-500/10',
    borderClass: 'border-green-500/30',
  },
}

/** 审稿报告查看器 */
export default function ReviewReport({ reportText, draftPath, chapterNumber, chapterDir }: ReviewReportProps) {
  const { issues, summary } = parseReport(reportText)
  const [showRefineDialog, setShowRefineDialog] = useState(false)
  const [userRefinePrompt, setUserRefinePrompt] = useState('')
  const [processing, setProcessing] = useState(false)
  const [showLegend, setShowLegend] = useState(false)

  // 按分类分组
  const categories = new Map<string, ReviewIssue[]>()
  for (const issue of issues) {
    const list = categories.get(issue.category) || []
    list.push(issue)
    categories.set(issue.category, list)
  }

  // 统计
  const errorCount = issues.filter((i) => i.severity === 'error').length
  const warningCount = issues.filter((i) => i.severity === 'warning').length
  const passCount = issues.filter((i) => i.severity === 'pass').length

  /** 根据审稿意见修稿 */
  const doRefineFromReview = async () => {
    if (!draftPath || !chapterDir) return
    setProcessing(true)
    setShowRefineDialog(false)
    try {
      const { useWorkflowStore } = await import('../../stores/workflow-store')

      const { createRefineFromReviewWorkflow } = await import('../../services/workflows/chapter-workflow')
      const { getLatestReview } = await import('../../services/draft-index')
      const { readDraftBody } = await import('../../stores/draft-store')

      const draftContent = await readDraftBody(draftPath)
      if (!draftContent) return

      // 提取版本信息
      const versionMatch = draftPath.match(/draft_v(\d+)\.md$/)
      const baseVersion = versionMatch ? parseInt(versionMatch[1]) : 1
      const chapterNum = chapterNumber || 0

      // 获取最新审稿文件名（用于关联）
      const latestReview = await getLatestReview(chapterDir, baseVersion)
      const reviewFileName = latestReview?.fileName || ''

      // 从 index.json 读取章节标题
      const { readDraftIndex } = await import('../../services/draft-index')
      const index = await readDraftIndex()
      const chapterTitle = index.chapterTitle || `第${chapterNum}章`

      useWorkflowStore.getState().startWorkflow(createRefineFromReviewWorkflow({
        chapterNumber: chapterNum,
        chapterTitle,
        draftPath,
        draftContent,
        reviewReport: reportText,
        reviewFileName,
        userRefinePrompt: userRefinePrompt.trim() || undefined,
      }), false)
    } finally {
      setProcessing(false)
    }
  }

  const SeverityIcon = ({ severity }: { severity: string }) => {
    if (severity === 'error') return <AlertTriangle size={14} className="text-red-400 flex-shrink-0" />
    if (severity === 'warning') return <AlertTriangle size={14} className="text-yellow-400 flex-shrink-0" />
    return <CheckCircle size={14} className="text-green-400 flex-shrink-0" />
  }

  // 是否可以触发修稿（有草稿路径和章节信息时）
  const canRefine = !!(draftPath && chapterDir)

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-4">
        {/* 统计栏 */}
        <div className="flex items-center gap-4 mb-4 pb-3 border-b border-[var(--color-border)]">
          <h3 className="text-base font-bold text-[var(--color-text)]"> 审稿报告</h3>
          <div className="flex items-center gap-3 text-xs ml-auto">
            {errorCount > 0 && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-red-500/20 text-red-400">
                🔴 {errorCount} 严重
              </span>
            )}
            {warningCount > 0 && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                🟡 {warningCount} 建议
              </span>
            )}
            <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-green-500/20 text-green-400">
              🟢 {passCount} 通过
            </span>
            {/* 图例帮助按钮 */}
            <button
              className="flex items-center justify-center rounded-full hover:bg-[var(--color-hover)] transition-colors"
              style={{ width: 22, height: 22 }}
              onClick={() => setShowLegend(!showLegend)}
              title="颜色说明"
            >
              <HelpCircle size={14} style={{ color: 'var(--color-text-muted)' }} />
            </button>
          </div>
        </div>

        {/* 颜色图例说明 */}
        {showLegend && (
          <div
            className="mb-4 rounded-lg border p-3 text-xs space-y-2"
            style={{
              backgroundColor: 'var(--color-bg-elevated)',
              borderColor: 'var(--color-border)',
            }}
          >
            <div className="font-medium text-[var(--color-text)] mb-1.5">颜色标记说明</div>
            {(['error', 'warning', 'pass'] as const).map(sev => {
              const meta = SEVERITY_META[sev]
              return (
                <div key={sev} className="flex items-center gap-2">
                  <span className={cn(
                    'inline-flex items-center gap-1 px-2 py-0.5 rounded',
                    meta.bgClass, meta.colorClass
                  )}>
                    {meta.emoji} {meta.label}
                  </span>
                  <span style={{ color: 'var(--color-text-secondary)' }}>
                    — {meta.actionLabel}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {/* 总体评价（如有） */}
        {summary && (
          <div
            className="mb-4 px-4 py-3 rounded-lg border text-sm"
            style={{
              backgroundColor: 'var(--color-bg-elevated)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-text)',
            }}
          >
            <span className="font-medium">总体评价：</span>
            <span style={{ color: 'var(--color-text-secondary)' }}>{summary}</span>
          </div>
        )}

        {/* 分类展示 */}
        {issues.length === 0 ? (
          <div className="text-center py-8 text-[var(--color-text-muted)] text-sm">
            <CheckCircle size={32} className="mx-auto mb-2 text-green-400" />
            审稿通过，未发现问题
          </div>
        ) : (
          <div className="space-y-4">
            {Array.from(categories.entries()).map(([category, items]) => (
              <div key={category}>
                <h4 className="text-sm font-semibold text-[var(--color-text)] mb-2 flex items-center gap-1.5">
                  <Info size={14} className="text-[var(--color-text-muted)]" />
                  {category}
                </h4>
                <div className="space-y-1.5 pl-1">
                  {items.map((item, i) => {
                    const meta = SEVERITY_META[item.severity]
                    return (
                      <div
                        key={i}
                        className={cn(
                          'px-3 py-2 rounded-md border text-xs leading-relaxed',
                          meta.borderClass, meta.bgClass
                        )}
                      >
                        <div className="flex items-start gap-2">
                          <SeverityIcon severity={item.severity} />
                          <div className="flex-1 min-w-0">
                            <span className="text-[var(--color-text-secondary)]">{item.description}</span>
                            <span
                              className={cn('ml-2 text-[0.65rem] opacity-70', meta.colorClass)}
                            >
                              [{meta.actionLabel}]
                            </span>
                          </div>
                        </div>
                        {/* 引用原文（如有） */}
                        {item.quote && (
                          <div
                            className="mt-1.5 ml-5 pl-2 text-[0.7rem] italic"
                            style={{
                              borderLeft: '2px solid var(--color-border)',
                              color: 'var(--color-text-muted)',
                            }}
                          >
                            <Quote size={10} className="inline mr-1 opacity-60" />
                            {item.quote}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 原始文本折叠 */}
        <details className="mt-6">
          <summary className="text-xs text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-text)]">
            查看原始审稿文本
          </summary>
          <pre className="mt-2 text-xs whitespace-pre-wrap font-mono leading-5 text-[var(--color-text-secondary)] bg-[var(--color-sidebar)] rounded-md p-3 border border-[var(--color-border)]">
            {reportText}
          </pre>
        </details>

        {/* 🔧 根据审稿意见修稿 — 核心循环入口 */}
        {canRefine && (
          <div className="mt-6 pt-6 border-t border-[var(--color-border)] flex flex-col items-center">
            <Button
              variant="ai"
              className="px-8"
              onClick={() => { setUserRefinePrompt(''); setShowRefineDialog(true) }}
              disabled={processing}
            >
              <Sparkles size={14} className="mr-1" />
              AI 一键修稿
            </Button>
            <p className="text-[0.7rem] text-center mt-3" style={{ color: 'var(--color-text-muted)' }}>
              AI 将根据上方审稿报告中发现的问题精准修复草稿，并为您生成对比视图
            </p>
          </div>
        )}
      </div>

      {/* 修稿确认弹窗（含自定义提示词） */}
      <Dialog open={showRefineDialog} onOpenChange={(v) => !v && setShowRefineDialog(false)}>
        <DialogContent className="max-w-[440px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles size={15} className="text-[var(--color-accent)]" />
              根据审稿意见修稿
            </DialogTitle>
            <DialogDescription>
              AI 将根据审稿报告中的问题精准修复草稿
            </DialogDescription>
          </DialogHeader>
          <div className="px-5 py-2 text-sm space-y-1.5" style={{ color: 'var(--color-text-secondary)' }}>
            <div className="font-medium text-[var(--color-text)]">本次【审稿修稿】范围：</div>
            <div>1. 重点修复审稿报告中指出的「严重问题」与「改进建议」。</div>
            <div>2. 可在下方指定的额外修稿要求。</div>
          </div>
          <div className="px-5 pb-2">
            <label className="text-xs font-medium block mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>
              额外修稿指导（可选）：
            </label>
            <textarea
              className="w-full px-3 py-2 rounded-md text-sm"
              style={{
                background: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text)',
                minHeight: 72,
                resize: 'vertical',
                outline: 'none',
              }}
              placeholder="例如：优先修复角色对白不一致的问题；忽略报告中关于节奏的建议，保持原有节奏..."
              value={userRefinePrompt}
              onChange={e => setUserRefinePrompt(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowRefineDialog(false)}>取消</Button>
            <Button variant="ai" onClick={doRefineFromReview}>
              确认修稿
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
