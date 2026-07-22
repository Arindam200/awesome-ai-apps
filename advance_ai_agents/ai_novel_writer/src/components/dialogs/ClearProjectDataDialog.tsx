import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, FileText, FolderTree, Loader2, Map, Trash2 } from 'lucide-react'

import { clearProjectData, type ClearProjectDataOptions } from '../../services/project-clear-service'
import { alertError } from '../ui/AlertDialog'
import { Button } from '../ui/Button'
import { useLocaleStore } from '../../stores/locale-store'

interface ClearProjectDataDialogProps {
  open: boolean
  onClose: () => void
  onCleared?: () => void | Promise<void>
}

type ClearKey = keyof ClearProjectDataOptions

const OPTIONS: Array<{
  key: ClearKey
  labelZh: string
  labelEn: string
  descZh: string
  descEn: string
  Icon: typeof FolderTree
}> = [
  {
    key: 'creativeFields',
    labelZh: '故事架构与大纲',
    labelEn: 'Story architecture and outline',
    descZh: '清空前提、世界观、角色架构、情节大纲、文风分析与全局创作指导。',
    descEn: 'Clear premise, world building, character architecture, plot outline, style analysis, and global guidance.',
    Icon: FolderTree,
  },
  {
    key: 'blueprints',
    labelZh: '章节蓝图',
    labelEn: 'Chapter blueprints',
    descZh: '清空所有章节蓝图与章节级规划，后续可重新生成。',
    descEn: 'Clear every chapter blueprint and chapter-level plan. You can generate them again later.',
    Icon: Map,
  },
  {
    key: 'generatedText',
    labelZh: '草稿、定稿与审稿产物',
    labelEn: 'Drafts, manuscripts, and reviews',
    descZh: '清空草稿、定稿正文、修订、审稿报告、后处理记录与全局摘要快照。',
    descEn: 'Clear drafts, final manuscript text, revisions, review reports, post-processing records, and summary snapshots.',
    Icon: FileText,
  },
]

export default function ClearProjectDataDialog({
  open,
  onClose,
  onCleared,
}: ClearProjectDataDialogProps) {
  const [selected, setSelected] = useState<Record<ClearKey, boolean>>({
    creativeFields: true,
    blueprints: true,
    generatedText: true,
  })
  const [clearing, setClearing] = useState(false)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const text = useLocaleStore(s => s.text)

  const selectedCount = useMemo(
    () => OPTIONS.filter(option => selected[option.key]).length,
    [selected],
  )

  useEffect(() => {
    if (open) {
      setSelected({ creativeFields: true, blueprints: true, generatedText: true })
      setClearing(false)
      setTimeout(() => cancelRef.current?.focus(), 0)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !clearing) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [clearing, onClose, open])

  if (!open) return null

  const handleClear = async () => {
    if (selectedCount === 0) return
    setClearing(true)
    try {
      await clearProjectData(selected)
      await onCleared?.()
      onClose()
    } catch (error) {
      await alertError(String(error), { title: text('清除失败', 'Clear failed') })
      setClearing(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[9998] flex items-center justify-center"
      style={{
        backgroundColor: 'var(--color-backdrop)',
        backdropFilter: 'blur(8px)',
      }}
      onClick={() => {
        if (!clearing) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="clear-project-data-title"
        className="w-[min(92vw,520px)] overflow-hidden"
        style={{
          backgroundColor: 'var(--color-sidebar)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-popover)',
        }}
        onClick={event => event.stopPropagation()}
      >
        <div
          className="flex items-center gap-2 px-4 py-3"
          style={{ borderBottom: '1px solid var(--color-border)' }}
        >
          <Trash2 size={16} style={{ color: 'var(--color-error)' }} />
          <div className="min-w-0 flex-1">
            <div
              id="clear-project-data-title"
              className="text-sm font-semibold"
              style={{ color: 'var(--color-text)' }}
            >
              {text('清除项目生成内容', 'Clear generated project data')}
            </div>
            <div className="mt-0.5 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {text('此操作只清除所选生成数据，不删除项目目录、角色卡或模型配置。', 'Only the selected generated data will be removed. The project folder, character cards, and model settings are preserved.')}
            </div>
          </div>
        </div>

        <div className="space-y-2 p-4">
          {OPTIONS.map(({ key, labelZh, labelEn, descZh, descEn, Icon }) => (
            <label
              key={key}
              className="flex cursor-pointer gap-3 rounded-[var(--radius-md)] px-3 py-2.5"
              style={{
                border: '1px solid var(--color-border)',
                backgroundColor: selected[key] ? 'var(--color-hover)' : 'transparent',
              }}
            >
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]"
                checked={selected[key]}
                disabled={clearing}
                onChange={event => setSelected(current => ({ ...current, [key]: event.target.checked }))}
              />
              <Icon size={15} className="mt-0.5 flex-shrink-0" style={{ color: 'var(--color-text-muted)' }} />
              <span className="min-w-0">
                <span className="block text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                  {text(labelZh, labelEn)}
                </span>
                <span className="mt-1 block text-xs leading-5" style={{ color: 'var(--color-text-secondary)' }}>
                  {text(descZh, descEn)}
                </span>
              </span>
            </label>
          ))}

          <div
            className="flex gap-2 rounded-[var(--radius-md)] px-3 py-2.5 text-xs leading-5"
            style={{
              border: '1px solid color-mix(in srgb, var(--color-error) 36%, var(--color-border))',
              color: 'var(--color-text-secondary)',
              backgroundColor: 'color-mix(in srgb, var(--color-error) 8%, transparent)',
            }}
          >
            <AlertTriangle size={15} className="mt-0.5 flex-shrink-0" style={{ color: 'var(--color-error)' }} />
            <span>
              {text('清除后不会自动恢复。若需要保留当前内容，请先复制到外部文件或导出项目备份。', 'Cleared data is not restored automatically. Copy important content elsewhere or export a backup first.')}
            </span>
          </div>
        </div>

        <div
          className="flex justify-end gap-2 px-4 py-3"
          style={{ borderTop: '1px solid var(--color-border)' }}
        >
          <Button
            ref={cancelRef}
            variant="ghost"
            size="sm"
            disabled={clearing}
            onClick={onClose}
          >
            {text('取消', 'Cancel')}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={clearing || selectedCount === 0}
            onClick={handleClear}
          >
            {clearing ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
            {text('清除所选', 'Clear selected')}
          </Button>
        </div>
      </div>
    </div>
  )
}
