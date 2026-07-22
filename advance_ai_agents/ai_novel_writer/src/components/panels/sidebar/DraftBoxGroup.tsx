/**
 * DraftBoxGroup — 草稿箱折叠组（含章节分组和单条草稿条目）
 */

import { useState, useEffect } from 'react'
import { ChevronRight, ChevronDown, CheckCircle2, Circle, FileText, FolderOpen, Copy, Trash2, FilePen } from 'lucide-react'
import type { DraftMeta } from '../../../stores/draft-store'
import { useDraftStore, readDraftBody } from '../../../stores/draft-store'
import { useEditorStore } from '../../../stores/editor-store'
import { confirm } from '../../ui/Confirm'
import { DRAFT_STATUS_LABEL, DRAFT_STATUS_COLOR } from '../../../shared/draft-status'
import { showSidebarMenu } from './SidebarShared'
import { ipc } from '../../../services/ipc-client'
import { toast } from '../../ui/Toast'
import { globalEventBus } from '../../../shared/event-bus'
import { useLocaleStore } from '../../../stores/locale-store'

const DRAFT_STATUS_EN: Record<string, string> = {
  draft: 'Draft', revising: 'Revising', reviewed: 'Reviewed', finalized: 'Finalized', archived: 'Archived',
}

// ===== 草稿箱折叠组 =====

export default function DraftBoxGroup({
  draftsByChapter,
}: {
  draftsByChapter: Record<number, DraftMeta[]>
}) {
  const [open, setOpen] = useState(true)
  const text = useLocaleStore(s => s.text)

  // 所有章节号排序
  const chapterNums = Object.keys(draftsByChapter)
    .map(Number)
    .sort((a, b) => a - b)

  // 筛选出包含非保留（活跃）草稿的实际章节数
  const activeChapterCount = chapterNums.filter(n =>
    (draftsByChapter[n] || []).some(d => d.status !== 'archived')
  ).length

  return (
    <div>
      {/* 草稿箱标题行 */}
      <div
        className="tree-item gap-1.5 cursor-pointer select-none"
        style={{ paddingLeft: 10 }}
        onClick={() => setOpen(v => !v)}
        title={text('草稿箱：AI 生成后的章节草稿在此管理，定稿后进入正文章节', 'Draft box: manage AI-generated drafts here. Finalized drafts move to the manuscript.')}
      >
        {open
          ? <ChevronDown size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
          : <ChevronRight size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        }
        <FilePen size={14} style={{ color: 'var(--color-text-muted)' }} />
        <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{text('草稿箱', 'Draft box')}</span>
        {activeChapterCount > 0 && (
          <span className="ml-auto text-[0.7rem]" style={{ color: 'var(--color-text-muted)' }}>
            {text(`${activeChapterCount} 章`, `${activeChapterCount} chapters`)}
          </span>
        )}
      </div>

      {open && (
        <div>
          {chapterNums.length === 0 ? (
            <div
              className="text-xs py-1"
              style={{ paddingLeft: 34, color: 'var(--color-text-muted)' }}
            >
              {text('暂无草稿（从章节蓝图点击「写作此章」创作）', 'No drafts. Use “Write chapter” from a chapter blueprint.')}
            </div>
          ) : (
            chapterNums.map(chNum => (
              <DraftChapterGroup
                key={chNum}
                chapterNumber={chNum}
                drafts={draftsByChapter[chNum] || []}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ===== 单章草稿分组 =====

function DraftChapterGroup({
  chapterNumber,
  drafts,
}: {
  chapterNumber: number
  drafts: DraftMeta[]
}) {
  const text = useLocaleStore(s => s.text)
  const [open, setOpen] = useState(true)

  // 将 archived 草稿折叠，只显示活跃草稿（非 archived）
  const activeDrafts = drafts.filter(d => d.status !== 'archived')
  const archivedDrafts = drafts.filter(d => d.status === 'archived')
  const [showArchived, setShowArchived] = useState(false)
  const [bpTitle, setBpTitle] = useState<string>('')

  useEffect(() => {
    let cancelled = false
    ipc.invoke('db:blueprint-get', chapterNumber).then(bp => {
      if (!cancelled && bp?.title) {
        setBpTitle(bp.title)
      }
    }).catch(() => { })
    return () => { cancelled = true }
  }, [chapterNumber])

  // 已定稿的草稿存在时，章节显示绿色标记
  const hasFinalized = drafts.some(d => d.status === 'finalized')
  const baseTitle = bpTitle || drafts[0]?.chapterTitle || ''
  const displayTitle = baseTitle.startsWith(`第${chapterNumber}章`)
    ? baseTitle
    : text(baseTitle ? `第${chapterNumber}章 ${baseTitle}` : `第${chapterNumber}章`, baseTitle ? `Chapter ${chapterNumber} ${baseTitle}` : `Chapter ${chapterNumber}`)

  return (
    <div>
      {/* 章节行 */}
      <div
        className="tree-item gap-1.5 cursor-pointer select-none"
        style={{ paddingLeft: 26 }}
        onClick={() => setOpen(v => !v)}
        title={displayTitle}
      >
        {open
          ? <ChevronDown size={10} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
          : <ChevronRight size={10} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        }
        {hasFinalized
          ? <CheckCircle2 size={10} style={{ flexShrink: 0, color: 'var(--color-success)' }} />
          : <Circle size={6} style={{ flexShrink: 0, fill: 'transparent', stroke: 'var(--color-text-muted)' }} />
        }
        <span className="text-sm flex-1 truncate" style={{ color: 'var(--color-text-secondary)' }}>
          {displayTitle}
        </span>
        <span className="ml-auto text-[0.7rem] flex-shrink-0" style={{ color: 'var(--color-text-muted)' }}>
          {text(`${activeDrafts.length} 稿`, `${activeDrafts.length} drafts`)}
        </span>
      </div>

      {/* 草稿列表 */}
      {open && (
        <div>
          {activeDrafts.map(draft => (
            <DraftItem
              key={draft.filePath}
              draft={draft}
              chapterTitleText={displayTitle}
            />
          ))}

          {/* 显示归档草稿的切换按钮 */}
          {archivedDrafts.length > 0 && (
            <div
              className="flex items-center gap-1 cursor-pointer select-none"
              style={{ paddingLeft: 54 }}
              onClick={() => setShowArchived(v => !v)}
            >
              <span className="text-[0.7rem]" style={{ color: 'var(--color-text-muted)', opacity: 0.6 }}>
                {showArchived ? <><ChevronDown size={10} className="inline" /> {text('隐藏', 'Hide')}</> : <><ChevronRight size={10} className="inline" /> {text(`${archivedDrafts.length} 个已归档`, `${archivedDrafts.length} archived`)}</>}
              </span>
            </div>
          )}
          {showArchived && archivedDrafts.map(draft => (
            <DraftItem
              key={draft.filePath}
              draft={draft}
              chapterTitleText={displayTitle}
              archived
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ===== 单条草稿条目 =====

function DraftItem({
  draft,
  chapterTitleText,
  archived = false,
}: {
  draft: DraftMeta
  chapterTitleText: string
  archived?: boolean
}) {
  const text = useLocaleStore(s => s.text)
  const statusLabel = text(DRAFT_STATUS_LABEL[draft.status] || draft.status, DRAFT_STATUS_EN[draft.status] || draft.status)
  /** 打开草稿到编辑器 */
  const openDraft = async () => {
    const content = await readDraftBody(draft.filePath)
    useEditorStore.getState().openFile({
      id: draft.filePath,
      name: `${chapterTitleText} v${draft.version}`,
      type: 'chapter',
      filePath: draft.filePath,
      content,
    })
  }

  /** 删除草稿 */
  const deleteDraft = async () => {
    const ok = await confirm(
      text(`确认删除 "${chapterTitleText} v${draft.version}"？\n此操作会删除该稿正文记录及关联的审稿/修稿产物，不可撤销。`, `Delete “${chapterTitleText} v${draft.version}”?\nThis permanently removes the draft and related review/revision artifacts.`),
      { title: text('删除这一稿', 'Delete draft'), confirmText: text('删除', 'Delete'), danger: true }
    )
    if (!ok) return
    const result = await ipc.invoke('db:draft-delete', draft.id)
    if (!result.success) {
      toast.error(text(`删除失败\n\n${result.error ?? '未知错误'}`, `Delete failed\n\n${result.error ?? 'Unknown error'}`))
      return
    }
    const editor = useEditorStore.getState()
    const tab = editor.tabs.find(t => t.id === draft.filePath || t.filePath === draft.filePath)
    if (tab) editor.closeTab(tab.id)
    await useDraftStore.getState().loadChapterDrafts(draft.chapterNumber)
    globalEventBus.emit('REFRESH_RESOURCE', { resources: ['drafts', 'fileTree'] })
    toast.success(text(`已删除 ${chapterTitleText} v${draft.version}`, `Deleted ${chapterTitleText} v${draft.version}`))
  }

  const isFinalized = draft.status === 'finalized'

  return (
    <div
      className="relative flex items-center gap-1.5 cursor-pointer hover:bg-[var(--color-hover)]"
      style={{
        paddingLeft: 50,
        paddingRight: 8,
        paddingTop: 3,
        paddingBottom: 3,
        opacity: archived ? 0.45 : 1,
      }}
      onClick={openDraft}
      onContextMenu={e => showSidebarMenu([
        {
          key: 'open',
          label: text('打开草稿', 'Open draft'),
          icon: <FolderOpen size={13} />,
          onClick: openDraft,
        },
        { key: 'div1', type: 'divider' as const },
        {
          key: 'copy-path',
          label: text('复制文件路径', 'Copy file path'),
          icon: <Copy size={13} />,
          onClick: () => navigator.clipboard.writeText(draft.filePath).catch(() => { }),
        },
        { key: 'div2', type: 'divider' as const },
        {
          key: 'delete',
          label: text('删除这一稿', 'Delete draft'),
          icon: <Trash2 size={13} />,
          danger: true,
          onClick: deleteDraft,
        },
      ], e)}
      title={text(`点击打开 — ${chapterTitleText} v${draft.version}（${DRAFT_STATUS_LABEL[draft.status] || draft.status}）`, `Open — ${chapterTitleText} v${draft.version} (${statusLabel})`)}
    >
      <FileText size={10} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
      <span className="text-xs flex-1 truncate" style={{ color: 'var(--color-text-secondary)' }}>
        {text(`草稿_v${draft.version}`, `Draft_v${draft.version}`)}
      </span>
      {/* 状态标签（始终显示） */}
      <span
        className="text-[0.7rem] flex-shrink-0"
        style={{ color: DRAFT_STATUS_COLOR[draft.status] || 'var(--color-text-muted)' }}
      >
        {statusLabel}
      </span>
      {/* 已定稿图标 */}
      {isFinalized && (
        <CheckCircle2 size={10} style={{ color: 'var(--color-success)', flexShrink: 0 }} />
      )}
      <button
        type="button"
        className="opacity-70 hover:opacity-100 rounded p-0.5"
        title={text('删除这一稿', 'Delete draft')}
        onClick={(e) => {
          e.stopPropagation()
          deleteDraft()
        }}
        style={{ color: 'var(--color-text-muted)' }}
      >
        <Trash2 size={10} />
      </button>
    </div>
  )
}
