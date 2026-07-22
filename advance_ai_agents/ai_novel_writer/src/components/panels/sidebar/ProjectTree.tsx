/**
 * ProjectTree — 项目导航树（侧边栏核心视图）
 *
 * 包含：小说配置、故事架构、章节蓝图、草稿箱、正文章节、全局摘要
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { ChevronRight, ChevronDown, RefreshCw, CheckCircle2, Circle, FolderOpen, Copy, FolderTree, Trash2 } from 'lucide-react'
import { useProjectStore } from '../../../stores/project-store'
import { useWorkflowStore } from '../../../stores/workflow-store'
import { useDraftStore } from '../../../stores/draft-store'
import { useEditorStore } from '../../../stores/editor-store'
import { useLayoutStore } from '../../../stores/layout-store'
import { ipc } from '../../../services/ipc-client'
import { Button } from '../../ui/Button'
import { EmptyState } from '../../ui/EmptyState'
import { confirm } from '../../ui/Confirm'
import { toast } from '../../ui/Toast'
import ClearProjectDataDialog from '../../dialogs/ClearProjectDataDialog'



import {
  ARCH_FILES, LeafItem, renderIcon, showSidebarMenu,
  openArchFile, openBuiltinEditor,
} from './SidebarShared'
import DraftBoxGroup from './DraftBoxGroup'
import ManuscriptGroup from './ManuscriptGroup'
import { useLocaleStore } from '../../../stores/locale-store'

const ARCH_FILE_EN: Record<string, { label: string; desc: string }> = {
  premise: { label: 'Premise', desc: 'Core premise and conflict' },
  characters: { label: 'Character map', desc: 'Character arcs and relationships' },
  worldbuilding: { label: 'World building', desc: 'World rules and systems' },
  synopsis: { label: 'Plot synopsis', desc: 'Overall plot structure' },
}

export default function ProjectTree() {
  const currentProject = useProjectStore(s => s.currentProject)
  const text = useLocaleStore(s => s.text)

  // refreshFileTree / loadAllDrafts 在 refreshAll 内通过 getState() 调用
  // 只订阅 activeRuns
  const activeRuns = useWorkflowStore(s => s.activeRuns)
  // 精确订阅，避免 loadAllDrafts 执行后引用变化触发 useCallback/useEffect 循环
  const draftsByChapter = useDraftStore(s => s.draftsByChapter)

  // 存储各架构文件是否有实际内容（已生成）
  const [archStatus, setArchStatus] = useState<Record<string, boolean>>({})
  // 章节蓝图数量
  const [blueprintCount, setBlueprintCount] = useState<number>(-1)
  const [clearDialogOpen, setClearDialogOpen] = useState(false)

  /** 统一刷新：文件树 + 架构状态 + 草稿列表 + 蓝图数量 */
  // 用 getState() 获取最新的 action，不作为依赖项，避免重建导致 useEffect 循环
  const refreshAll = useCallback(async () => {

    useProjectStore.getState().refreshFileTree()
    useDraftStore.getState().loadAllDrafts()
    // 通过 Service 层获取架构状态和蓝图数量（避免直接 IPC）
    const { checkArchStatus, getBlueprintCount } = await import('../../../services/architecture-service')
    const [status, count] = await Promise.all([
      checkArchStatus(),
      getBlueprintCount(),
    ])
    setArchStatus(status)
    setBlueprintCount(count)
  }, [])  // 空依赖：内部用 getState() 获取最新 action，不依赖闭包

  // 项目切换时刷新
  useEffect(() => {
    if (currentProject) refreshAll()
  }, [currentProject?.path, refreshAll]) // eslint-disable-line react-hooks/exhaustive-deps -- currentProject 对象引用变化不每次都需重跑

  // 工作流步骤状态或整体状态变化时刷新侧边栏（适配多任务）
  // 合并为单一 effect + 防抖，避免一次步骤完成同时触发多次刷新
  const workflowKey = activeRuns.map(r => `${r.id}:${r.status}|${r.steps.map(s => s.status).join(',')}`).join(';')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (!currentProject) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      refreshAll()
    }, 80)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // 依赖 path 字符串而非 currentProject 对象引用
    //    避免 updateNovelConfig 改变对象引用后触发不必要的 refreshAll
  }, [workflowKey, currentProject?.path, refreshAll]) // eslint-disable-line react-hooks/exhaustive-deps -- currentProject 对象引用变化不触发，仅 path 变化需响应

  if (!currentProject) {
    return (
      <div className="writer-project-tree h-full">
        <EmptyState
          icon={<span className="text-4xl opacity-60" style={{ color: 'var(--color-text-muted)' }}><FolderOpen size={36} /></span>}
          message={text('未打开项目', 'No project open')}
          className="p-4 pb-[15vh]"
          opacity={1}
        >
          <span
            className="text-xs text-center mt-0.5"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {text('新建或打开一个小说项目开始创作', 'Create or open a novel project to begin.')}
          </span>
          {/* 操作按钮 */}
          <div className="flex flex-col gap-2 mt-3 w-full">
            <Button
              variant="default"
              className="w-full"
              onClick={() => useLayoutStore.getState().openNewProject()}
            >
              {text('新建项目', 'New project')}
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={async () => {
                const folder = await ipc.invoke('dialog:select-folder')
                if (folder) {
                  useProjectStore.getState().openProject(folder)
                }
              }}
            >
              {text('打开项目', 'Open project')}
            </Button>
          </div>
        </EmptyState>
      </div>
    )
  }

  const p = currentProject.path
  // 改为彻底的数据驱动：从内存的全部草稿中提取 status='finalized' 的草稿
  const manuscriptFiles = Object.values(draftsByChapter)
    .map(drafts => drafts.find(d => d.status === 'finalized'))
    .filter(Boolean)
    .sort((a, b) => a!.chapterNumber - b!.chapterNumber)
    .map(draft => ({
      path: `vela://manuscript/${draft!.id}`, // 诸如 vela://manuscript/42
      name: `chapter_${draft!.chapterNumber}.md`, // 提供格式化的伪文件名供组件适配解析
      isDir: false,
    })) as Array<{ path: string; name: string; isDir: boolean }>

  // 小说配置是否已完成（核心大纲非空视为已完成）
  const nc = currentProject.novelConfig
  const configDone = !!(nc.coreOutline?.trim() || nc.protagonistProfile?.trim())

  // 故事架构进度
  const archDone = ARCH_FILES.filter(f => archStatus[f.key]).length
  const clearDisabled = activeRuns.length > 0

  return (
    <div className="writer-project-tree min-h-full text-sm py-1">
      {/* 项目名 + 刷新 */}
      <div className="flex items-center justify-between gap-1 px-3 py-1.5 mb-0.5">
        <span className="font-semibold text-xs truncate" style={{ color: 'var(--color-text)' }}>
          {currentProject.name}
        </span>
        <div className="flex flex-shrink-0 items-center gap-0.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setClearDialogOpen(true)}
            disabled={clearDisabled}
            title={clearDisabled ? '工作流运行中，暂不能清除' : '清除项目生成内容'}
          >
            <Trash2 size={12} />
            {text('清除全部', 'Clear all')}
          </Button>
          <Button variant="ghost" size="icon" onClick={() => refreshAll()} title={text('刷新', 'Refresh')}>
            <RefreshCw size={12} />
          </Button>
        </div>
      </div>

      <ClearProjectDataDialog
        open={clearDialogOpen}
        onClose={() => setClearDialogOpen(false)}
        onCleared={refreshAll}
      />

      {/* 1. 小说配置 */}
      <LeafItem
        iconName="book-open"
        label={text('小说配置', 'Novel configuration')}
        desc={text('基础参数与写作要求', 'Core parameters and writing guidance')}
        badge={configDone ? text('已完成', 'Complete') : text('待配置', 'Pending')}
        badgeDone={configDone}
        onClick={() => {
          const state = useEditorStore.getState()
          const configTab = state.tabs.find(t => t.type === 'config')
          if (configTab) {
            state.setActiveTab(configTab.id)
          } else {
            state.openFile({ id: 'config', name: '小说配置', type: 'config' })
          }
        }}
        onContextMenu={e => showSidebarMenu([
          {
            key: 'open',
            label: '打开小说配置',
            icon: <FolderOpen size={13} />,
            onClick: () => {
              const state = useEditorStore.getState()
              const configTab = state.tabs.find(t => t.type === 'config')
              if (configTab) state.setActiveTab(configTab.id)
              else state.openFile({ id: 'config', name: '小说配置', type: 'config' })
            },
          },
        ], e)}
      />

      {/* 2. 故事架构 — 点击标题行打开编辑器，子文件仍可单独点开 */}
      <WorldBuildingGroup archStatus={archStatus} archDone={archDone} onCleared={refreshAll} />

      {/* 3. 章节蓝图 — 点击打开编辑器页 */}
      <LeafItem
        iconName="layout-list"
        label={text('章节蓝图', 'Chapter blueprints')}
        desc={text('AI 生成的章节目录，可编辑', 'Editable AI-generated chapter plans')}
        badge={blueprintCount > 0 ? text(`${blueprintCount}/${nc.totalChapters} 章`, `${blueprintCount}/${nc.totalChapters} chapters`) : text('待生成', 'Pending')}
        badgeColor={
          blueprintCount >= nc.totalChapters
            ? 'var(--color-success)'
            : blueprintCount > 0
              ? 'var(--color-warning, #eab308)'
              : undefined
        }
        badgeDone={blueprintCount >= nc.totalChapters}
        onClick={() => openBuiltinEditor('chapter-card-editor', '章节蓝图', 'chapter-card')}
        onContextMenu={e => showSidebarMenu([
          {
            key: 'open',
            label: '打开章节蓝图',
            icon: <FolderOpen size={13} />,
            onClick: () => openBuiltinEditor('chapter-card-editor', '章节蓝图', 'chapter-card'),
          },
        ], e)}
      />

      {/* 4. 草稿箱 — 独立分区，按章节分组展示草稿 */}
      <DraftBoxGroup draftsByChapter={draftsByChapter} />

      {/* 5. 正文章节 — 仅显示已定稿 */}
      <ManuscriptGroup files={manuscriptFiles} projectPath={p} />
    </div>
  )
}


// ===== 故事架构折叠组 =====

function WorldBuildingGroup({
  archStatus,
  archDone,
  onCleared,
}: {
  archStatus: Record<string, boolean>
  archDone: number
  onCleared: () => void | Promise<void>
}) {
  const [open, setOpen] = useState(true)
  const text = useLocaleStore(s => s.text)

  const allDone = archDone === ARCH_FILES.length

  return (
    <div>
      {/* 组标题行 — 点击打开故事架构编辑器，双击展开/折叠子文件 */}
      <div
        className="tree-item gap-1.5 cursor-pointer select-none"
        style={{ paddingLeft: 10 }}
        onClick={() => openBuiltinEditor('world-building-editor', text('故事架构', 'Story architecture'), 'world-building')}
        title={text('打开故事架构编辑器（可生成架构文档）', 'Open the story architecture editor')}
      >
        <span
          style={{ width: 12, flexShrink: 0, display: 'flex', alignItems: 'center', cursor: 'pointer' }}
          onClick={(e) => { e.stopPropagation(); setOpen(v => !v) }}
        >
          {open
            ? <ChevronDown size={12} style={{ color: 'var(--color-text-muted)' }} />
            : <ChevronRight size={12} style={{ color: 'var(--color-text-muted)' }} />
          }
        </span>
        <FolderTree size={14} style={{ color: 'var(--color-text-muted)' }} />
        <span className="text-sm font-medium flex-1 min-w-0 truncate" style={{ color: 'var(--color-text)' }}>{text('故事架构', 'Story architecture')}</span>
        {/* 进度徽章 */}
        <span
          className="text-[0.7rem] flex-shrink-0 ml-1"
          style={{
            color: allDone
              ? 'var(--color-success)'
              : archDone > 0
                ? 'var(--color-warning, #eab308)'
                : 'var(--color-text-muted)'
          }}
        >
          {archDone}/{ARCH_FILES.length}
        </span>
      </div>

      {/* 子文件列表（点击直接在 Markdown 编辑器打开） */}
      {open && (
        <div>
          {ARCH_FILES.map(f => {
            const isGenerated = archStatus[f.key]
            const filePath = `vela://core/${f.key}`
            return (
              <ArchFileRow
                key={f.key}
                f={f}
                filePath={filePath}
                isGenerated={isGenerated}
                onCleared={onCleared}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}

/** 单个架构文件行 */
function ArchFileRow({
  f,
  filePath,
  isGenerated,
  onCleared,
}: {
  f: { key: string; iconName: string; label: string; desc: string }
  filePath: string
  isGenerated: boolean
  onCleared: () => void | Promise<void>
}) {
  const text = useLocaleStore(s => s.text)
  const english = ARCH_FILE_EN[f.key] ?? { label: f.label, desc: f.desc }
  const label = text(f.label, english.label)
  const clearArchFile = async () => {
    const ok = await confirm(text(`确认清空「${f.label}」内容？\n此操作会删除该项故事架构文本，不影响其他架构项、蓝图或正文。`, `Clear “${english.label}”?\nThis removes only this architecture section and preserves the other sections, blueprints, and manuscript.`), {
      title: text('清空故事架构项', 'Clear architecture section'),
      confirmText: text('清空', 'Clear'),
      danger: true,
    })
    if (!ok) return

    const { writeCoreContent } = await import('../../../services/vela-protocol')
    const success = await writeCoreContent(filePath, '')
    if (!success) {
      toast.error(text(`清空「${f.label}」失败`, `Could not clear “${english.label}”`))
      return
    }

    const store = useEditorStore.getState()
    store.syncTabContent(filePath, '')
    store.markTabSaved(filePath)
    toast.success(text(`已清空「${f.label}」`, `Cleared “${english.label}”`))
    await onCleared()
  }

  return (
    <div
      className="tree-item gap-1.5 cursor-pointer select-none"
      style={{ paddingLeft: 26 }}
      onClick={() => openArchFile(filePath, label)}
      onContextMenu={e => showSidebarMenu([
        {
          key: 'open',
          label: text('打开文件', 'Open file'),
          icon: <FolderOpen size={13} />,
          onClick: () => openArchFile(filePath, label),
        },
        { key: 'div1', type: 'divider' as const },
        {
          key: 'copy-path',
          label: text('复制文件路径', 'Copy file path'),
          icon: <Copy size={13} />,
          onClick: () => navigator.clipboard.writeText(filePath).catch(() => { }),
        },
        { key: 'div2', type: 'divider' as const },
        {
          key: 'delete',
          label: text(`清空${f.label}`, `Clear ${english.label}`),
          icon: <Trash2 size={13} />,
          danger: true,
          disabled: !isGenerated,
          onClick: clearArchFile,
        },
      ], e)}
      title={text(f.desc, english.desc)}
    >
      {isGenerated
        ? <CheckCircle2 size={10} style={{ flexShrink: 0, color: 'var(--color-success)' }} />
        : <Circle size={6} style={{ flexShrink: 0, fill: 'transparent', stroke: 'var(--color-text-muted)' }} />
      }
      <span className="flex-shrink-0" style={{ color: 'var(--color-text-muted)' }}>{renderIcon(f.iconName, 13)}</span>
      <span
        className="text-sm flex-1 truncate"
        style={{ color: isGenerated ? 'var(--color-text)' : 'var(--color-text-secondary)' }}
      >
        {label}
      </span>
      {!isGenerated && (
        <span className="text-[0.7rem] flex-shrink-0" style={{ color: 'var(--color-text-muted)' }}>
          {text('待生成', 'Pending')}
        </span>
      )}
      {isGenerated && (
        <button
          type="button"
          className="opacity-70 hover:opacity-100 rounded p-0.5"
          title={text(`清空${f.label}`, `Clear ${english.label}`)}
          onClick={(e) => {
            e.stopPropagation()
            clearArchFile()
          }}
          style={{ color: 'var(--color-text-muted)' }}
        >
          <Trash2 size={11} />
        </button>
      )}
    </div>
  )
}
