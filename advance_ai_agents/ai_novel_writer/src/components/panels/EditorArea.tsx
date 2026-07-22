import { X, FileText, Settings, Users, ArrowLeftRight, MoreHorizontal, BookOpen, History, ClipboardCheck, Globe, Save, ChevronLeft, ChevronRight, PenTool } from 'lucide-react'
import { useEffect, useRef, useState, useCallback } from 'react'
import { ContextMenu, type ContextMenuEntry } from '../ui/ContextMenu'
import {
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from '../ui/Dialog'
import { Button } from '../ui/Button'
import CodeMirrorEditor from '../editor/CodeMirrorEditor'
import NovelConfigEditor from '../editor/NovelConfigEditor'
import CharacterEditor from '../editor/CharacterEditor'
import ChapterCardEditor from '../editor/ChapterCardEditor'
import WorldBuildingEditor from '../editor/WorldBuildingEditor'
import ArchFileViewer from '../editor/ArchFileViewer'
import DraftEditor from '../editor/DraftEditor'
import VersionHistory from '../editor/VersionHistory'
import ReviewReport from '../editor/ReviewReport'
import ThreeWayMerge from '../editor/ThreeWayMerge'  // 保留引用以防其他入口使用
import WelcomePage from '../pages/WelcomePage'
import KnowledgeOverview from '../pages/KnowledgeOverview'
import { useProjectStore } from '../../stores/project-store'
import { useEditorStore, type EditorTab } from '../../stores/editor-store'
import { useLayoutStore } from '../../stores/layout-store'
import { useLocaleStore } from '../../stores/locale-store'


import { ipc } from '../../services/ipc-client'
import { toast } from '../ui/Toast'

import { clearChapterTitleCache } from './Sidebar'
import '../editor/novel-editor.css'

// ─── 正文章节编辑器包装层（含字数信息栏） ─────────────────────────────────────────────
function ProseEditorWrapper({
  tab,
  onSave,
}: {
  tab: EditorTab
  onSave: (text: string) => Promise<void>
}) {
  const [wordCount, setWordCount] = useState(0)
  const [saving, setSaving] = useState(false)
  const fileName = tab.name
  // 追踪当前编辑器内容，供保存按钮使用（不触发重渲染）
  const currentContentRef = useRef(tab.content ?? '')
  const text = useLocaleStore(s => s.text)

  const handleSave = async (text: string) => {
    setSaving(true)
    try {
      await onSave(text)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 顶部信息栏（背景与编辑区一致） */}
      <div
        className="flex items-center justify-between px-3 h-9 flex-shrink-0"
        style={{
          borderBottom: '1px solid var(--color-border)',
          backgroundColor: 'var(--color-editor-bg)',
        }}
      >
        {/* 左侧：文件名 */}
        <span className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
          {fileName}
        </span>

        {/* 右侧：字数 + dirty 指示灯 + 保存按钮 */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {wordCount > 0 && (
            <span className="text-xs tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
              {text(`${wordCount.toLocaleString()} 字`, `${wordCount.toLocaleString()} words`)}
            </span>
          )}
          {/* 未保存圆点指示灯 */}
          {tab.dirty && (
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: 'var(--color-warning)' }}
              title={text('有未保存的修改', 'Unsaved changes')}
            />
          )}
          {/* 保存按钮（有改动时显示） */}
          {tab.dirty && (
            <button
              className="icon-btn"
              style={{ width: 24, height: 22 }}
              onClick={() => handleSave(currentContentRef.current)}
              disabled={saving}
              title={text('保存（⌘S）', 'Save (⌘S)')}
            >
              <Save size={13} strokeWidth={1.5} />
            </button>
          )}
        </div>
      </div>

      {/* 编辑器主体 */}
      <div className="flex-1 overflow-hidden">
        <CodeMirrorEditor
          key={tab.id}
          mode="prose"
          content={tab.content ?? ''}
          filePath={tab.filePath}
          hideStatusBar
          onCharCountChange={setWordCount}
          onChange={(text) => {
            // 同步 ref，供保存按钮使用
            currentContentRef.current = text
            // 标记 tab.dirty
            useEditorStore.getState().updateTabContent(tab.id, text)
          }}
          onSave={(text) => handleSave(text)}
        />
      </div>
    </div>
  )
}

interface EditorAreaProps {
  onNewProject: () => void
}

/** 中间主编辑区 */
export default function EditorArea({ onNewProject }: EditorAreaProps) {
  const text = useLocaleStore(s => s.text)
  const currentProject = useProjectStore((s) => s.currentProject)
  const tabs = useEditorStore(s => s.tabs)
  const activeTabId = useEditorStore(s => s.activeTabId)
  const openFile = useEditorStore(s => s.openFile)
  const closeTab = useEditorStore(s => s.closeTab)
  const setActiveTab = useEditorStore(s => s.setActiveTab)
  const sidebarView = useLayoutStore((s) => s.sidebarView)



  // ===== 所有 Hooks 必须在条件 return 之前 =====

  // 打开项目后自动打开配置 Tab
  // 依赖 currentProject?.id + tabs.length：
  //   - id 变化（切换项目）时触发
  //   - tabs 被清空（clearTabs）时触发
  useEffect(() => {
    if (currentProject && tabs.length === 0) {
      // 从 store 直接取最新值，避免闭包陈旧
      const latestTabs = useEditorStore.getState().tabs
      if (latestTabs.length === 0) {
        openFile({ id: 'config', name: text('小说配置', 'Novel configuration'), type: 'config' })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?.id, tabs.length])

  // 防御性兜底：tabs 有内容但 activeTabId 无效时，激活第一个 tab
  const activeTab = tabs.find((t) => t.id === activeTabId)
  useEffect(() => {
    if (tabs.length > 0 && !activeTab) {
      setActiveTab(tabs[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabs.length, activeTab])

  // Tab 条自动滚动到当前活跃 Tab
  const tabBarRef = useRef<HTMLDivElement>(null)
  const activeTabRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (activeTabRef.current && tabBarRef.current) {
      activeTabRef.current.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
    }
  }, [activeTabId])

  /** 点击左右箭头时切换到上/下一个 Tab */
  const switchTab = useCallback((direction: 'left' | 'right') => {
    if (tabs.length === 0) return
    const currentIndex = tabs.findIndex(t => t.id === activeTabId)
    let nextIndex: number
    if (direction === 'left') {
      nextIndex = currentIndex <= 0 ? tabs.length - 1 : currentIndex - 1
    } else {
      nextIndex = currentIndex >= tabs.length - 1 ? 0 : currentIndex + 1
    }
    setActiveTab(tabs[nextIndex].id)
  }, [tabs, activeTabId, setActiveTab])

  // ===== 三个点菜单状态 =====
  const [moreMenuOpen, setMoreMenuOpen] = useState(false)
  const moreButtonRef = useRef<HTMLButtonElement>(null)

  // 绑定 ⌘W 快捷键：关闭当前 Tab（带 dirty 检查）
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'w' || e.key === 'W')) {
        e.preventDefault()
        const { activeTabId: aid, tabs: ts } = useEditorStore.getState()
        if (aid) {
          const t = ts.find(x => x.id === aid)
          if (t && !t.pinned) {
            if (t.dirty) {
              setCloseConfirm(aid)
            } else {
              useEditorStore.getState().closeTab(aid)
            }
          }
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // ===== Tab 右键菜单状态 =====
  const [tabMenu, setTabMenu] = useState<{
    tabId: string
    position: { x: number; y: number }
  } | null>(null)

  // ===== 关闭确认弹窗状态 =====
  const [closeConfirm, setCloseConfirm] = useState<string | null>(null) // 单个待关闭的 tabId
  // 批量关闭确认：待关闭的 tabId 列表（含 dirty 的）
  const [batchCloseConfirm, setBatchCloseConfirm] = useState<string[] | null>(null)

  /** 尝试关闭 Tab：如果有未保存修改则弹确认对话框 */
  const tryCloseTab = useCallback((tabId: string) => {
    const tab = tabs.find(t => t.id === tabId)
    if (!tab) return
    if (tab.pinned) return
    if (tab.dirty) {
      // 有未保存修改，弹确认弹窗
      setCloseConfirm(tabId)
    } else {
      closeTab(tabId)
    }
  }, [tabs, closeTab])

  /** 尝试批量关闭 Tab：收集待关闭列表，若其中有 dirty tab 则弹确认弹窗 */
  const tryBatchClose = useCallback((tabIds: string[]) => {
    const cleanIds = tabIds.filter(id => {
      const t = tabs.find(t => t.id === id)
      return t && !t.pinned
    })
    const dirtyIds = cleanIds.filter(id => tabs.find(t => t.id === id)?.dirty)
    if (dirtyIds.length > 0) {
      // 待关闭列表都放入批量确认弹窗中，一次性关闭
      setBatchCloseConfirm(cleanIds)
    } else {
      cleanIds.forEach(id => closeTab(id))
    }
  }, [tabs, closeTab])

  /** 构建 Tab 右键菜单项 */
  const buildTabMenuItems = useCallback(
    (tabId: string): ContextMenuEntry[] => {
      const tab = tabs.find(t => t.id === tabId)
      const tabIndex = tabs.findIndex(t => t.id === tabId)
      const hasOthers = tabs.length > 1
      const hasRight = tabIndex < tabs.length - 1

      return [
        {
          key: 'close',
          label: text('关闭', 'Close'),
          shortcut: '⌘W',
          disabled: tab?.pinned,
          onClick: () => tryCloseTab(tabId),
        },
        {
          key: 'close-others',
          label: text('关闭其他', 'Close others'),
          disabled: !hasOthers || tab?.pinned,
          onClick: () => {
            const others = tabs
              .filter(t => t.id !== tabId && !t.pinned)
              .map(t => t.id)
            tryBatchClose(others)
          },
        },
        {
          key: 'close-right',
          label: text('关闭右侧所有', 'Close all to the right'),
          disabled: !hasRight,
          onClick: () => {
            const right = tabs
              .slice(tabIndex + 1)
              .filter(t => !t.pinned)
              .map(t => t.id)
            tryBatchClose(right)
          },
        },
        { key: 'div1', type: 'divider' as const },
        {
          key: 'close-all',
          label: text('关闭所有', 'Close all'),
          danger: true,
          onClick: () => {
            const all = tabs.filter(t => !t.pinned).map(t => t.id)
            tryBatchClose(all)
          },
        },
      ]
    },
    [tabs, tryCloseTab, tryBatchClose, text]
  )

  /** 构建三个点菜单项（Tab 操作 + 已打开 Tab 列表） */
  const buildMoreMenuItems = useCallback((): ContextMenuEntry[] => {
    const hasActive = !!activeTabId
    const activeTab = tabs.find(t => t.id === activeTabId)
    const activeIndex = tabs.findIndex(t => t.id === activeTabId)
    const hasOthers = tabs.length > 1
    const hasRight = activeIndex < tabs.length - 1

    return [
      {
        key: 'close-current',
        label: text('关闭', 'Close'),
        shortcut: '⌘W',
        disabled: !hasActive || activeTab?.pinned,
        onClick: () => { if (activeTabId) tryCloseTab(activeTabId) },
      },
      {
        key: 'close-others',
        label: text('关闭其他', 'Close others'),
        disabled: !hasActive || !hasOthers,
        onClick: () => {
          const others = tabs
            .filter(t => t.id !== activeTabId && !t.pinned)
            .map(t => t.id)
          tryBatchClose(others)
        },
      },
      {
        key: 'close-right',
        label: text('关闭右侧所有', 'Close all to the right'),
        disabled: !hasActive || !hasRight,
        onClick: () => {
          const right = tabs
            .slice(activeIndex + 1)
            .filter(t => !t.pinned)
            .map(t => t.id)
          tryBatchClose(right)
        },
      },
      { key: 'div-close', type: 'divider' as const },
      {
        key: 'close-all',
        label: text('关闭所有', 'Close all'),
        danger: true,
        onClick: () => {
          const all = tabs.filter(t => !t.pinned).map(t => t.id)
          tryBatchClose(all)
        },
      },
      // 已打开的 Tab 列表
      ...(tabs.length > 0 ? [
        { key: 'div-list', type: 'divider' as const } as ContextMenuEntry,
        ...tabs.map(t => ({
          key: `goto-${t.id}`,
          label: t.name,
          icon: t.id === activeTabId
            ? <span style={{ color: 'var(--color-accent)', fontWeight: 'bold' }}>●</span>
            : undefined,
          onClick: () => setActiveTab(t.id),
        })),
      ] : []),
    ]
  }, [tabs, activeTabId, tryCloseTab, tryBatchClose, setActiveTab, text])

  // ===== 条件渲染 =====

  // 侧栏为「主页」时，中间区域显示欢迎页
  if (sidebarView === 'home') {
    return (
      <WelcomePage
        onNewProject={() => {
          useLayoutStore.getState().openNewProject()
        }}
        onOpenProject={async () => {
          const folder = await ipc.invoke('dialog:select-folder')
          if (folder) {
            useProjectStore.getState().openProject(folder)
          }
        }}
        onImportNovel={() => {
          useLayoutStore.getState().openImportNovel()
        }}
      />
    )
  }

  // 侧栏为「角色管理」时，中间区域固定展示角色编辑器（跳过 Tab 系统）
  if (sidebarView === 'characters') {
    return (
      <div
        className="w-full h-full flex flex-col overflow-hidden"
        style={{ backgroundColor: 'var(--color-editor-bg)' }}
      >
        <CharacterEditor />
      </div>
    )
  }

  // 侧栏为「知识库」时，中间区域固定展示向量数据库查询界面（跳过 Tab 系统）
  if (sidebarView === 'knowledge') {
    return <KnowledgeOverview />
  }

  // 未打开项目时显示欢迎页
  if (!currentProject) {
    return (
      <WelcomePage
        onNewProject={onNewProject}
        onOpenProject={async () => {
          const folder = await ipc.invoke('dialog:select-folder')
          if (folder) {
            useProjectStore.getState().openProject(folder)
          }
        }}
        onImportNovel={() => {
          useLayoutStore.getState().openImportNovel()
        }}
      />
    )
  }

  // 有项目但没有打开的 Tab
  if (tabs.length === 0) {
    return (
      <div
        className="w-full h-full flex flex-col overflow-hidden"
        style={{ backgroundColor: 'var(--color-editor-bg)' }}
      >
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center opacity-40">
            <PenTool size={36} style={{ color: 'var(--color-text-muted)', opacity: 0.5, display: 'block', margin: '0 auto 12px' }} />
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {text('在左侧项目树中单击文件开始编辑', 'Select a file in the project tree to start editing.')}
            </span>
          </div>
        </div>
      </div>
    )
  }

  /** Tab 图标 */
  const TabIcon = ({ type }: { type: EditorTab['type'] }) => {
    if (type === 'config') return <Settings size={14} />
    if (type === 'character') return <Users size={14} />
    if (type === 'diff') return <ArrowLeftRight size={14} />
    if (type === 'chapter-card') return <BookOpen size={14} />
    if (type === 'world-building') return <Globe size={14} />
    if (type === 'version-history') return <History size={14} />
    if (type === 'review-report') return <ClipboardCheck size={14} />
    return <FileText size={14} />
  }

  return (
    <div
      className="w-full h-full flex flex-col overflow-hidden"
      style={{ backgroundColor: 'var(--color-editor-bg)' }}
    >
      {/* Tab 条：左右箭头 + 可横向滚动区域 + 三个点菜单 */}
      <div
        className="no-select flex items-center flex-shrink-0"
        style={{
          height: 'var(--height-tab)',
          backgroundColor: 'var(--color-tab-bg)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        {/* Tab 列表可滚动区域 */}
        <div
          ref={tabBarRef}
          className="flex items-center flex-1 h-full overflow-x-auto"
          style={{ scrollbarWidth: 'none' }}
        >
          {tabs.map((tab) => (
            <div
              key={tab.id}
              ref={tab.id === activeTabId ? activeTabRef : undefined}
              className="flex items-center gap-1.5 px-3 h-full text-sm cursor-pointer group flex-shrink-0 relative transition-colors"
              style={{
                backgroundColor: activeTabId === tab.id
                  ? 'var(--color-tab-active)'
                  : 'transparent',
                /* JetBrains 激活 Tab：顶部 2px 葵紫色指示线 */
                boxShadow: activeTabId === tab.id
                  ? 'inset 0 2px 0 var(--color-tab-indicator)'
                  : 'none',
                /* 无竖分割线 */
                borderRight: 'none',
                color: activeTabId === tab.id
                  ? 'var(--color-text)'
                  : 'var(--color-text-secondary)',
              }}
              onClick={() => setActiveTab(tab.id)}
              onContextMenu={e => {
                e.preventDefault()
                setActiveTab(tab.id)
                setTabMenu({ tabId: tab.id, position: { x: e.clientX, y: e.clientY } })
              }}
              onMouseEnter={e => {
                if (tab.id !== activeTabId) {
                  e.currentTarget.style.backgroundColor = 'var(--color-hover)'
                  e.currentTarget.style.color = 'var(--color-text)'
                }
              }}
              onMouseLeave={e => {
                if (tab.id !== activeTabId) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'var(--color-text-secondary)'
                }
              }}
            >
              <TabIcon type={tab.type} />
              <span className="max-w-[120px] truncate">{tab.name}</span>

              {/* 关闭按钮区域：dirty 时显示实心圆点（英文黑点），鼠标悬停展示关闭按钮 */}
              {tab.dirty ? (
                <span
                  className="relative w-3.5 h-3.5 flex items-center justify-center ml-0.5 flex-shrink-0 rounded group/close hover:bg-[var(--color-hover)] cursor-pointer transition-colors"
                  onClick={e => { e.stopPropagation(); tryCloseTab(tab.id) }}
                  title={text('有未保存的修改，点击关闭', 'Unsaved changes; click to close')}
                >
                  {/* 默认显示实心圆点，颜色与标题栏警示灯一致 */}
                  <span
                    className="w-1.5 h-1.5 rounded-full group-hover/close:hidden"
                    style={{ backgroundColor: 'var(--color-warning)' }}
                  />
                  {/* hover 时显示 X */}
                  <X size={10} className="hidden group-hover/close:block" style={{ color: 'var(--color-text-muted)' }} />
                </span>
              ) : (
                <button
                  className="opacity-0 group-hover:opacity-100 ml-0.5 p-0.5 rounded transition-opacity"
                  style={{ color: 'var(--color-text-muted)' }}
                  onClick={e => { e.stopPropagation(); tryCloseTab(tab.id) }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <X size={11} />
                </button>
              )}
            </div>
          ))}
        </div>

        {/* 右侧操作区：左箭头 + 右箭头 + 三个点菜单（始终显示，类似 VSCode） */}
        <div
          className="flex items-center flex-shrink-0 h-full"
          style={{ borderLeft: '1px solid var(--color-border)' }}
        >
          <button
            className="icon-btn flex-shrink-0"
            onClick={() => switchTab('left')}
            title={text('上一个编辑器', 'Previous editor')}
          >
            <ChevronLeft size={14} />
          </button>
          <button
            className="icon-btn flex-shrink-0"
            onClick={() => switchTab('right')}
            title={text('下一个编辑器', 'Next editor')}
          >
            <ChevronRight size={14} />
          </button>
          <button
            ref={moreButtonRef}
            className="icon-btn flex-shrink-0"
            title={text('已打开的编辑器', 'Open editors')}
            onClick={() => setMoreMenuOpen(prev => !prev)}
          >
            <MoreHorizontal size={14} />
          </button>
        </div>
      </div>



      {/* 编辑区主体 */}
      <div className="flex-1 overflow-hidden">
        {activeTab?.type === 'chapter' && activeTab.filePath?.startsWith('vela://draft/') && (
          // 草稿文件：使用 DraftEditor（工具栏含修稿/审稿/定稿按鈕）
          <DraftEditor
            key={activeTab.id}
            filePath={activeTab.filePath}
            content={activeTab.content ?? ''}
          />
        )}
        {activeTab?.type === 'chapter' && !activeTab.filePath?.startsWith('vela://draft/') && (
          // 【DB 迁移备注】：终稿目前作为物理文件保存在 manuscript/ 目录是合理的（用于外部阅读器或最终打包编译导出）
          // 终稿文件（manuscript/）：用 ProseEditorWrapper（含字数信息栏）
          <ProseEditorWrapper
            key={activeTab.id}
            tab={activeTab}
            onSave={async (text) => {
              if (!activeTab.filePath) return
              await ipc.invoke('fs:write-file', activeTab.filePath, text)
              // 清除 dirty 标记 + 同步内容 + 刷新章节名缓存
              useEditorStore.getState().markTabSaved(activeTab.id)
              useEditorStore.getState().syncTabContent(activeTab.id, text)
              clearChapterTitleCache(activeTab.filePath)
            }}
          />
        )}
        {activeTab?.type === 'config' && (
          <NovelConfigEditor />
        )}
        {activeTab?.type === 'outline' && (
          <div className="h-full overflow-y-auto p-6">
            <pre
              className="text-sm whitespace-pre-wrap font-mono leading-6"
              style={{ color: 'var(--color-text)' }}
            >
              {activeTab.content || text('加载中...', 'Loading...')}
            </pre>
          </div>
        )}
        {activeTab?.type === 'character' && (
          <CharacterEditor />
        )}
        {activeTab?.type === 'chapter-card' && (
          <ChapterCardEditor />
        )}
        {activeTab?.type === 'world-building' && (
          <WorldBuildingEditor />
        )}
        {activeTab?.type === 'arch-file' && activeTab.filePath && (
          <ArchFileViewer
            key={activeTab.id}
            filePath={activeTab.filePath}
            content={activeTab.content ?? ''}
          />
        )}
        {activeTab?.type === 'version-history' && (
          <VersionHistory />
        )}
        {activeTab?.type === 'review-report' && activeTab.content && (
          <ReviewReport
            reportText={activeTab.content}
            draftPath={activeTab.filePath}
            chapterNumber={activeTab.chapterNumber}
            chapterDir={activeTab.chapterDir}
          />
        )}
        {/* diff 合并视图 — 统一使用弹出式 Dialog（与 DraftEditor 一致） */}
        <Dialog
          open={activeTab?.type === 'diff' && !!activeTab.originalContent && !!activeTab.content}
          onOpenChange={(v) => {
            if (!v && activeTab?.type === 'diff') {
              useEditorStore.getState().closeTab(activeTab.id)
            }
          }}
        >
          <DialogContent
            className="p-0"
            style={{
              width: '90vw',
              maxWidth: '90vw',
              height: '85vh',
              maxHeight: '85vh',
              overflow: 'hidden',
            }}
            onPointerDownOutside={(e) => e.preventDefault()}
            onEscapeKeyDown={(e) => e.preventDefault()}
          >
            <DialogHeader className="px-4 py-0" style={{ height: 38, display: 'flex', alignItems: 'center' }}>
              <DialogTitle className="flex items-center gap-2 text-[0.8rem]">
                {text(`修稿合并 — ${activeTab?.name ?? '对比视图'}`, `Revision merge — ${activeTab?.name ?? 'Comparison'}`)}
              </DialogTitle>
            </DialogHeader>
            <div className="flex-1 overflow-hidden" style={{ height: 'calc(85vh - 38px - 1px)' }}>
              {activeTab?.type === 'diff' && activeTab.originalContent && activeTab.content && (
                <ThreeWayMerge
                  originalContent={activeTab.originalContent}
                  modifiedContent={activeTab.content}
                  onComplete={async (mergedText) => {
                    try {
                      const chapterDir = activeTab.chapterDir
                      const filePath = activeTab.filePath
                      const revPath = activeTab.revisionPath
                      const chapterNum = activeTab.chapterNumber

                      if (chapterDir && filePath && revPath) {
                        const { useDraftStore } = await import('../../stores/draft-store')
                        const result = await useDraftStore.getState().applyMergedRevision(
                          chapterDir,
                          chapterNum,
                          filePath,
                          revPath,
                          mergedText
                        )


                        if (result.success) {
                          toast.success(text('合并完成，草稿已更新', 'Merge complete; draft updated'))
                        } else {
                          toast.error(text(`合并失败：${result.error}`, `Merge failed: ${result.error}`))
                        }
                      }
                    } catch (e) {

                      toast.error(text(`合并出错：${e}`, `Merge error: ${e}`))
                    } finally {
                      useEditorStore.getState().closeTab(activeTab.id)
                    }
                  }}
                  onCancel={() => useEditorStore.getState().closeTab(activeTab.id)}
                />
              )}
            </div>
          </DialogContent>
        </Dialog>

      </div>

      {/* Tab 右键菜单 */}
      {tabMenu && (
        <ContextMenu
          items={buildTabMenuItems(tabMenu.tabId)}
          position={tabMenu.position}
          onClose={() => setTabMenu(null)}
        />
      )}

      {/* 三个点菜单（已打开的编辑器列表 + Tab 操作） */}
      {moreMenuOpen && moreButtonRef.current && (() => {
        const rect = moreButtonRef.current!.getBoundingClientRect()
        return (
          <ContextMenu
            items={buildMoreMenuItems()}
            position={{ x: rect.right - 200, y: rect.bottom + 4 }}
            onClose={() => setMoreMenuOpen(false)}
          />
        )
      })()}

      {/* 关闭未保存 Tab 确认弹窗 */}
      <Dialog
        open={closeConfirm !== null}
        onOpenChange={v => !v && setCloseConfirm(null)}
      >
        <DialogContent className="max-w-[380px]">
          <DialogHeader>
            <DialogTitle>{text('关闭未保存的文件', 'Close unsaved file')}</DialogTitle>
            <DialogDescription>
              {text(`「${tabs.find(t => t.id === closeConfirm)?.name ?? '该文件'}」有未保存的修改。是否放弃修改并关闭？`, `“${tabs.find(t => t.id === closeConfirm)?.name ?? 'This file'}” has unsaved changes. Discard them and close?`)}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="ghost" onClick={() => setCloseConfirm(null)}>
              {text('取消', 'Cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (closeConfirm) closeTab(closeConfirm)
                setCloseConfirm(null)
              }}
            >
              {text('放弃修改', 'Discard changes')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 批量关闭未保存 Tab 确认弹窗 */}
      <Dialog
        open={batchCloseConfirm !== null}
        onOpenChange={v => !v && setBatchCloseConfirm(null)}
      >
        <DialogContent className="max-w-[400px]">
          <DialogHeader>
            <DialogTitle>{text('关闭多个文件', 'Close multiple files')}</DialogTitle>
            <DialogDescription>
              {(() => {
                const dirtyCount = (batchCloseConfirm ?? []).filter(
                  id => tabs.find(t => t.id === id)?.dirty
                ).length
                const total = (batchCloseConfirm ?? []).length
                return dirtyCount > 0
                  ? text(`即将关闭 ${total} 个文件，其中 ${dirtyCount} 个有未保存的修改。是否放弃修改并全部关闭？`, `Close ${total} files? ${dirtyCount} have unsaved changes that will be discarded.`)
                  : text(`即将关闭 ${total} 个文件。`, `Close ${total} files.`)
              })()}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="ghost" onClick={() => setBatchCloseConfirm(null)}>
              {text('取消', 'Cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (batchCloseConfirm) {
                  batchCloseConfirm.forEach(id => closeTab(id))
                }
                setBatchCloseConfirm(null)
              }}
            >
              {text('放弃修改并关闭', 'Discard and close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
