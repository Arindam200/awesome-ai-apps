/**
 * ManuscriptGroup — 正文章节折叠组（已定稿章节列表）
 */

import { useState, useEffect } from 'react'
import { ChevronRight, ChevronDown, FileText, FolderOpen, Copy, PenTool, Trash2 } from 'lucide-react'
import type { FileNode } from '../../../shared/ipc-channels'
import { ipc } from '../../../services/ipc-client'
import { useProjectStore } from '../../../stores/project-store'
import { useDraftStore } from '../../../stores/draft-store'
import { useEditorStore } from '../../../stores/editor-store'
import { confirm } from '../../ui/Confirm'
import { toast } from '../../ui/Toast'
import { globalEventBus } from '../../../shared/event-bus'
import { useLocaleStore } from '../../../stores/locale-store'

import { showSidebarMenu, openChapterFile } from './SidebarShared'

// ===== 章节标题缓存 =====

/** 章节标题内存缓存：path → 显示名（进程内常驻，避免大量重复 IPC 读取） */
export const chapterTitleCache = new Map<string, string>()

/** 清除特定文件的章节标题缓存 */
export function clearChapterTitleCache(filePath?: string) {
  if (filePath) {
    chapterTitleCache.delete(filePath)
  } else {
    chapterTitleCache.clear()
  }
}

/**
 * 优先从蓝图 JSON 读取章节标题，fallback 到文件首行
 *
 * @param filePath    manuscript 文件路径
 * @param fallback    兜底显示名（如 "第1章"）
 * @param chapterNumber 章节号（用于定位蓝图文件）
 */
async function readChapterTitle(filePath: string, fallback: string, chapterNumber?: number): Promise<string> {
  if (chapterTitleCache.has(filePath)) return chapterTitleCache.get(filePath)!

  // 优先从蓝图 JSON 读取标题
  if (chapterNumber) {
    try {
      const project = useProjectStore.getState().currentProject
      if (project) {
        const bpResult = await ipc.invoke('db:blueprint-get', chapterNumber)
        if (bpResult) {
          const display = `第${chapterNumber}章 ${bpResult.title}`
          chapterTitleCache.set(filePath, display)
          return display
        }
      }
    } catch { /* 蓝图读取失败时 fallback 到文件首行 */ }
  }

  // fallback: 读取正文首行
  let fileContent = ''
  if (filePath.startsWith('vela://')) {
    const { readVelaContent } = await import('../../../services/vela-protocol')
    fileContent = await readVelaContent(filePath)
  } else {
    const result = await ipc.invoke('fs:read-file', filePath)
    if (result.success) fileContent = result.content
  }

  if (!fileContent) return fallback
  const firstLine = fileContent.split('\n').find((l: string) => l.trim())
  if (!firstLine) return fallback
  const title = firstLine.replace(/^#+\s*/, '').trim()
  const display = title || fallback
  chapterTitleCache.set(filePath, display)
  return display
}

// ===== 正文章节组件 =====

export default function ManuscriptGroup({ files }: { files: FileNode[]; projectPath: string }) {
  const [open, setOpen] = useState(true)
  const text = useLocaleStore(s => s.text)
  // 文件路径 → 显示名称的映射（异步加载）
  const [titleMap, setTitleMap] = useState<Record<string, string>>({})

  // 每次 files 变化时异步读取各文件标题（命中缓存的路径直接跳过 IPC）
  const filesDep = files.map(f => f.path).join(',')
  useEffect(() => {
    if (files.length === 0) return
    let cancelled = false
    const load = async () => {
      // 只读取当前 state 中还没有的路径（增量更新，避免重复 IPC 调用）
      const missing = files.filter(f => !f.name.includes('_notes') && !titleMap[f.path])
      if (missing.length === 0) return
      const entries: Record<string, string> = {}
      await Promise.all(
        missing.map(async (f) => {
          const rawName = f.name.replace(/\.[^.]+$/, '')
          const chMatch = rawName.match(/^chapter_(\d+)$/)
          const fallback = chMatch ? text(`第${parseInt(chMatch[1], 10)}章`, `Chapter ${parseInt(chMatch[1], 10)}`) : rawName
          const chNum = chMatch ? parseInt(chMatch[1], 10) : undefined
          entries[f.path] = await readChapterTitle(f.path, fallback, chNum)
        })
      )
      if (!cancelled) setTitleMap(prev => ({ ...prev, ...entries }))
    }
    load()
    return () => { cancelled = true }
  }, [files, filesDep, titleMap, text])

  const getDisplay = (f: FileNode) => {
    if (titleMap[f.path]) return titleMap[f.path]
    const rawName = f.name.replace(/\.[^.]+$/, '')
    const chMatch = rawName.match(/^chapter_(\d+)$/)
    return chMatch ? text(`第${parseInt(chMatch[1], 10)}章`, `Chapter ${parseInt(chMatch[1], 10)}`) : rawName
  }

  // 只显示正文章节（过滤掉旧的 _notes 文件）
  const chapterFiles = files.filter(f => !f.name.includes('_notes'))

  const deleteManuscriptChapter = async (filePath: string, displayName: string) => {
    const match = filePath.match(/^vela:\/\/manuscript\/(\d+)$/)
    if (!match) {
      toast.error(text('当前章节路径不支持直接删除', 'This chapter path cannot be deleted directly.'))
      return
    }

    const ok = await confirm(text(`确认删除正文「${displayName}」？\n此操作会删除该定稿正文记录及关联的审稿/修稿产物，不会删除蓝图。`, `Delete manuscript “${displayName}”?\nThis removes the finalized draft and related review/revision artifacts, but preserves the blueprint.`), {
      title: text('删除正文', 'Delete manuscript'),
      confirmText: text('删除', 'Delete'),
      danger: true,
    })
    if (!ok) return

    const result = await ipc.invoke('db:draft-delete', Number(match[1]))
    if (!result.success) {
      toast.error(text(`删除失败\n\n${result.error ?? '未知错误'}`, `Delete failed\n\n${result.error ?? 'Unknown error'}`))
      return
    }

    const editor = useEditorStore.getState()
    const tab = editor.tabs.find(t => t.id === filePath || t.filePath === filePath)
    if (tab) editor.closeTab(tab.id)
    clearChapterTitleCache(filePath)
    await useDraftStore.getState().loadAllDrafts()
    globalEventBus.emit('REFRESH_RESOURCE', { resources: ['drafts', 'fileTree'] })
    toast.success(text(`已删除正文「${displayName}」`, `Deleted manuscript “${displayName}”`))
  }

  return (
    <div>
      <div
        className="tree-item gap-1.5 cursor-pointer select-none"
        style={{ paddingLeft: 10 }}
        onClick={() => setOpen(v => !v)}
      >
        {open
          ? <ChevronDown size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
          : <ChevronRight size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        }
        <PenTool size={14} style={{ color: 'var(--color-text-muted)' }} />
        <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{text('正文章节', 'Manuscript chapters')}</span>
        {chapterFiles.length > 0 && (
          <span className="ml-auto text-[0.7rem]" style={{ color: 'var(--color-text-muted)' }}>
            {text(`${chapterFiles.length} 章`, `${chapterFiles.length} chapters`)}
          </span>
        )}
      </div>
      {open && (
        <div>
          {chapterFiles.length === 0 ? (
            <div className="text-xs py-1" style={{ paddingLeft: 34, color: 'var(--color-text-muted)' }}>
              {text('暂无定稿章节', 'No finalized chapters')}
            </div>
          ) : (
            chapterFiles.map(f => {
              const displayName = getDisplay(f)
              return (
                <div
                  key={f.path}
                  className="tree-item gap-1.5 cursor-pointer"
                  style={{ paddingLeft: 30 }}
                  onClick={() => openChapterFile(f.path, displayName)}
                  onContextMenu={e => showSidebarMenu([
                    {
                      key: 'open',
                      label: text('打开章节', 'Open chapter'),
                      icon: <FolderOpen size={13} />,
                      onClick: () => openChapterFile(f.path, displayName),
                    },
                    { key: 'div1', type: 'divider' as const },
                    {
                      key: 'copy-path',
                      label: text('复制文件路径', 'Copy file path'),
                      icon: <Copy size={13} />,
                      onClick: () => navigator.clipboard.writeText(f.path).catch(() => { }),
                    },
                    { key: 'div2', type: 'divider' as const },
                    {
                      key: 'delete',
                      label: text('删除正文', 'Delete manuscript'),
                      icon: <Trash2 size={13} />,
                      danger: true,
                      onClick: () => deleteManuscriptChapter(f.path, displayName),
                    },
                  ], e)}
                  title={text(`点击打开 — ${displayName}`, `Open — ${displayName}`)}
                >
                  <FileText size={11} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
                  <span className="text-sm truncate flex-1" style={{ color: 'var(--color-text-secondary)' }}>
                    {displayName}
                  </span>
                  <button
                    type="button"
                    className="opacity-70 hover:opacity-100 rounded p-0.5"
                    title={text('删除正文', 'Delete manuscript')}
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteManuscriptChapter(f.path, displayName)
                    }}
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    <Trash2 size={10} />
                  </button>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}
