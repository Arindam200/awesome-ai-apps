import { useState, useEffect, useCallback } from 'react'
import {
  Database, RefreshCw, BookOpen, AlertTriangle,
} from 'lucide-react'
import { ipc } from '../../services/ipc-client'
import { Button } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { useProjectStore } from '../../stores/project-store'
import { globalEventBus } from '../../shared/event-bus'
import { loadKBData, type KBDocument } from '../../services/knowledge-service'
import { useLocaleStore } from '../../stores/locale-store'
import { appErrorMessage } from '../../i18n/app-errors'



/** 知识库管理面板（侧栏）— 纯只读展示 + 搜索，数据由定稿自动驱动 */
export default function KnowledgePanel() {
  const [documents, setDocuments] = useState<KBDocument[]>([])
  const [stats, setStats] = useState({ documentCount: 0, totalChunks: 0 })
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 20
  const [titleMap, setTitleMap] = useState<Record<string, string>>({})
  const [loadError, setLoadError] = useState('')
  const { locale, text } = useLocaleStore()

  /** 加载文档列表 + 统计（通过 Service 层） */
  const loadData = useCallback(async () => {
    try {
      const { documents: docs, stats: s } = await loadKBData()
      setDocuments(docs)
      setStats(s)
      setLoadError('')
    } catch (error) {
      setLoadError(appErrorMessage(locale, error))
    }
  }, [locale])

  useEffect(() => {
    let mounted = true
    Promise.resolve().then(() => { if (mounted) loadData() })
    return () => { mounted = false }
  }, [loadData])

  // 通过 EventBus 监听资源刷新和定稿完成事件
  useEffect(() => {
    const unsub1 = globalEventBus.on('REFRESH_RESOURCE', () => { loadData() })
    const unsub2 = globalEventBus.on('FINALIZE_COMPLETE', () => { loadData() })
    return () => { unsub1(); unsub2() }
  }, [loadData])

  useEffect(() => {
    let cancelled = false
    const loadTitles = async () => {
      if (documents.length === 0) return
      const missing = documents.filter(d => d.filePath && !titleMap[d.id])
      if (missing.length === 0) return

      const newTitles: Record<string, string> = {}
      await Promise.all(
        missing.map(async (doc) => {
          let title = doc.fileName
          const rawName = doc.fileName.replace(/\.[^.]+$/, '')
          const chMatch = rawName.match(/^(?:chapter_(\d+)|第(\d+)章)\s*(.*)$/)
          if (chMatch) {
            const num = chMatch[1] ? parseInt(chMatch[1], 10) : parseInt(chMatch[2], 10)
            const rest = (chMatch[3] || '').trim()
            title = rest ? `第${num}章 ${rest}` : `第${num}章`
          }

          try {
            const res = await ipc.invoke('fs:read-file', doc.filePath)
            if (res.success && res.content) {
              const firstLine = res.content.split('\n').find((l: string) => l.trim())
              if (firstLine) {
                title = firstLine.replace(/^#+\s*/, '').trim() || title
              }
            }
          } catch { /* 忽略 */ }
          newTitles[doc.id] = title
        })
      )
      if (!cancelled) setTitleMap(prev => ({ ...prev, ...newTitles }))
    }
    loadTitles()
    return () => { cancelled = true }
  }, [documents]) // eslint-disable-line react-hooks/exhaustive-deps -- titleMap 不需要作为依赖：内部通过 prev => 合并即可获取最新值

  const currentProject = useProjectStore(s => s.currentProject)

  if (!currentProject) {
    return (
      <EmptyState
        icon={<BookOpen size={36} />}
        message={text('请先打开项目', 'Open a project first')}
        className="pb-[15vh]"
        opacity={0.4}
      />
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden text-sm">
      {/* 标题栏 */}
      <div className="flex items-center justify-between px-3 h-9 flex-shrink-0 border-b border-[var(--color-border)]">
        <span className="text-xs font-medium text-[var(--color-text)] flex items-center gap-1.5">
          <Database size={13} />
          {text('知识库', 'Knowledge base')}
          <span className="text-[0.7rem] text-[var(--color-text-muted)]">
            {text(`（${stats.documentCount} 文档 / ${stats.totalChunks} 块）`, `(${stats.documentCount} documents / ${stats.totalChunks} chunks)`)}
          </span>
        </span>
        <Button
          variant="ghost" size="icon"
          onClick={() => loadData()}
          title={text('刷新', 'Refresh')}
          className="h-6 w-6"
        >
          <RefreshCw size={11} />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">

        {loadError && (
          <div className="m-3 flex items-start gap-2 rounded-lg border border-red-500/25 bg-red-500/10 p-2 text-xs text-red-500">
            <AlertTriangle size={13} className="mt-0.5 flex-shrink-0" />
            <span>{loadError}</span>
          </div>
        )}

        {/* 已入库章节列表 */}
        <div className="px-3 py-1.5 text-[0.7rem] text-[var(--color-text-muted)] font-medium uppercase tracking-wide">
          {text('已入库章节', 'Indexed chapters')}
        </div>
        {documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 gap-2 opacity-40">
            <BookOpen size={28} />
            <span className="text-xs">{text('暂无数据', 'No data')}</span>
            <span className="text-[0.7rem] text-center px-4">{text('定稿后章节内容将自动入库', 'Finalized chapters are indexed automatically.')}</span>
          </div>
        ) : (
          <div className="pb-4">
            {documents
              .sort((a, b) => new Date(b.importedAt).getTime() - new Date(a.importedAt).getTime())
              .slice((currentPage - 1) * pageSize, currentPage * pageSize)
              .map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between px-3 py-2 hover:bg-[var(--color-hover)] transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-[var(--color-text)] truncate" title={doc.fileName}>
                      {titleMap[doc.id] || doc.fileName}
                    </div>
                    <div className="flex items-center gap-2 text-[0.7rem] text-[var(--color-text-muted)] mt-0.5">
                      <span>{text(`${doc.chunkCount} 块`, `${doc.chunkCount} chunks`)}</span>
                      <span>{new Date(doc.importedAt).toLocaleDateString(locale)}</span>
                    </div>
                  </div>
                </div>
              ))}

            {Math.ceil(documents.length / pageSize) > 1 && (
              <div className="flex items-center justify-between px-3 pt-3">
                <span className="text-[0.65rem] text-[var(--color-text-muted)]">
                  {currentPage} / {Math.ceil(documents.length / pageSize)}
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline" size="sm"
                    className="h-6 text-[0.65rem] px-2"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  >
                    {text('上一页', 'Previous')}
                  </Button>
                  <Button
                    variant="outline" size="sm"
                    className="h-6 text-[0.65rem] px-2"
                    disabled={currentPage === Math.ceil(documents.length / pageSize)}
                    onClick={() => setCurrentPage(p => Math.min(Math.ceil(documents.length / pageSize), p + 1))}
                  >
                    {text('下一页', 'Next')}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
