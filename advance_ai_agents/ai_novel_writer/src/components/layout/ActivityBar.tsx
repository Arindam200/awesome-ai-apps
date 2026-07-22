import { useState, useRef } from 'react'
import {
  FolderOpen,
  BookOpen,
  Users,
  Settings,
  Plus,
  Clock,
  X,
  Home,
  ChevronRight,
} from 'lucide-react'
import { useLayoutStore, type SidebarView } from '../../stores/layout-store'
import { useProjectStore } from '../../stores/project-store'
import { useEditorStore } from '../../stores/editor-store'
import { ipc } from '../../services/ipc-client'
import { confirm } from '../../components/ui/Confirm'
import { MenuItem } from '../../components/ui/MenuItem'
import { useOutsideClick } from '../../hooks/useOutsideClick'
import { useLocaleStore } from '../../stores/locale-store'

/** 活动栏按钮配置 */
const activities: Array<{ id: SidebarView; icon: typeof FolderOpen; zh: string; en: string }> = [
  { id: 'project', icon: FolderOpen, zh: '项目结构', en: 'Project' },
  { id: 'knowledge', icon: BookOpen, zh: '知识库', en: 'Knowledge' },
  { id: 'characters', icon: Users, zh: '角色管理', en: 'Characters' },
]

export default function ActivityBar() {
  const sidebarView = useLayoutStore(s => s.sidebarView)
  const sidebarOpen = useLayoutStore(s => s.sidebarOpen)
  const setSidebarView = useLayoutStore(s => s.setSidebarView)
  // ✅ 精确订阅，避免 fileTree 等高频字段导致不必要重渲染
  const currentProject = useProjectStore(s => s.currentProject)
  const recentProjects = useProjectStore(s => s.recentProjects)
  const loadRecentProjects = useProjectStore(s => s.loadRecentProjects)
  const closeProject = useProjectStore(s => s.closeProject)
  const [showProjectMenu, setShowProjectMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const text = useLocaleStore(s => s.text)

  /** 点击 Home 按钮：切换到主页视图 */
  const handleHomeClick = () => {
    setSidebarView('home')
  }

  /** 右键始终弹出菜单 */
  const handleToggleMenu = () => {
    if (!showProjectMenu) loadRecentProjects()
    setShowProjectMenu(v => !v)
  }

  // 点击外部关闭菜单
  useOutsideClick(menuRef, () => setShowProjectMenu(false), showProjectMenu)

  /** 新建项目 */
  const handleNewProject = () => {
    setShowProjectMenu(false)
    useLayoutStore.getState().openNewProject()
  }

  /** 打开项目 */
  const handleOpenProject = async () => {
    setShowProjectMenu(false)
    const folder = await ipc.invoke('dialog:select-folder')
    if (folder) {
      useProjectStore.getState().openProject(folder)
    }
  }

  /** 打开最近项目 */
  const handleOpenRecent = async (path: string) => {
    setShowProjectMenu(false)
    await useProjectStore.getState().openProject(path)
  }

  /** 关闭当前项目 */
  const handleCloseProject = async () => {
    setShowProjectMenu(false)
    const { tabs } = useEditorStore.getState()
    const dirtyTabs = tabs.filter((t: { dirty?: boolean }) => t.dirty)
    if (dirtyTabs.length > 0) {
      const names = dirtyTabs.map((t: { name: string }) => t.name).join('、')
      const ok = await confirm(
        text(
          `以下文件有未保存的修改：\n${names}\n\n确定要关闭项目吗？未保存的内容将丢失。`,
          `The following files have unsaved changes:\n${names}\n\nClose the project anyway? Unsaved changes will be lost.`,
        ),
        { title: text('关闭项目', 'Close project'), confirmText: text('放弃并关闭', 'Discard and close'), danger: true }
      )
      if (!ok) return
    }
    useEditorStore.getState().clearTabs()
    closeProject()
  }

  return (
    <div
      className="no-select flex flex-col items-center justify-between h-full py-1"
      style={{
        width: 40,
        backgroundColor: 'var(--color-activity-bar)',
        borderRight: '1px solid var(--color-border)',
        position: 'relative',
      }}
    >
      {/* ===== 顶部区域 ===== */}
      <div className="flex flex-col items-center gap-0.5 w-full">

        {/* Home 按钮 — 项目管理入口 */}
        <div className="relative w-full flex justify-center" ref={menuRef}>
          <button
            onClick={handleHomeClick}
            onContextMenu={e => { e.preventDefault(); handleToggleMenu() }}
            title={currentProject
              ? text(`${currentProject.name}（右键管理项目）`, `${currentProject.name} (right-click to manage)`)
              : text('项目管理', 'Project management')}
            className="relative flex items-center justify-center w-[36px] h-[36px] rounded-md transition-all"
            style={{
              color: (showProjectMenu || (sidebarOpen && sidebarView === 'home'))
                ? 'var(--color-activity-icon-active)'
                : 'var(--color-activity-icon)',
              backgroundColor: showProjectMenu ? 'var(--color-hover)' : 'transparent',
              marginBottom: 4,
            }}
          >
            <Home size={20} strokeWidth={(showProjectMenu || (sidebarOpen && sidebarView === 'home')) ? 2 : 1.5} />
            {currentProject && (
              <span
                className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: 'var(--color-accent)' }}
              />
            )}
          </button>

          {/* 项目管理 Popover */}
          {showProjectMenu && (
            <div
              className="absolute z-50 flex flex-col py-1 rounded-xl shadow-2xl"
              style={{
                left: 44,
                top: 0,
                width: 260,
                backgroundColor: 'var(--color-sidebar)',
                border: '1px solid var(--color-border)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
              }}
            >
              {/* 顶部标题 */}
              <div
                className="flex items-center justify-between px-3 py-2 mb-1"
                style={{ borderBottom: '1px solid var(--color-border)' }}
              >
                <span className="text-xs font-semibold" style={{ color: 'var(--color-text-muted)' }}>
                  {text('项目管理', 'Project management')}
                </span>
                <button
                  onClick={() => setShowProjectMenu(false)}
                  className="opacity-50 hover:opacity-100 transition-opacity"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  <X size={12} />
                </button>
              </div>

              {/* 当前项目信息 */}
              {currentProject && (
                <div
                  className="mx-2 mb-1 px-3 py-2 rounded-lg"
                  style={{ backgroundColor: 'var(--color-hover)' }}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="flex-shrink-0 w-2 h-2 rounded-full"
                      style={{ backgroundColor: 'var(--color-accent)' }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate" style={{ color: 'var(--color-text)' }}>
                        {currentProject.name}
                      </p>
                      <p className="text-[0.7rem] truncate mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                        {text('当前项目', 'Current project')}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* 操作按钮组 */}
              <div className="px-1">
                <MenuItem
                  icon={<Plus size={13} />}
                  label={text('新建项目', 'New project')}
                  shortcut="⌘N"
                  onClick={handleNewProject}
                />
                <MenuItem
                  icon={<FolderOpen size={13} />}
                  label={text('打开项目...', 'Open project...')}
                  shortcut="⌘O"
                  onClick={handleOpenProject}
                />
                {currentProject && (
                  <MenuItem
                    icon={<X size={13} />}
                    label={text('关闭当前项目', 'Close current project')}
                    onClick={handleCloseProject}
                    danger
                  />
                )}
              </div>

              {/* 最近项目列表 */}
              {recentProjects.length > 0 && (
                <>
                  <div
                    className="flex items-center gap-1.5 px-3 mt-2 mb-1"
                    style={{ borderTop: '1px solid var(--color-border)', paddingTop: 8 }}
                  >
                    <Clock size={11} style={{ color: 'var(--color-text-muted)' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                      {text('最近项目', 'Recent projects')}
                    </span>
                  </div>
                  <div className="px-1 max-h-[180px] overflow-y-auto">
                    {recentProjects
                      .filter(p => p.path !== currentProject?.path)
                      .slice(0, 8)
                      .map((p, i) => (
                        <button
                          key={i}
                          onClick={() => handleOpenRecent(p.path)}
                          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors hover:bg-[var(--color-hover)] group"
                        >
                          <BookOpen size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm truncate" style={{ color: 'var(--color-text)' }}>
                              {p.name}
                            </p>
                            <p className="text-[0.7rem] truncate" style={{ color: 'var(--color-text-muted)' }}>
                              {p.path}
                            </p>
                          </div>
                          <ChevronRight size={11} className="opacity-0 group-hover:opacity-50 flex-shrink-0" />
                        </button>
                      ))}
                    {recentProjects.filter(p => p.path !== currentProject?.path).length === 0 && (
                      <p className="text-xs px-2 py-1.5 opacity-50" style={{ color: 'var(--color-text-muted)' }}>
                        {text('暂无其他最近项目', 'No other recent projects')}
                      </p>
                    )}
                  </div>
                </>
              )}

              <div className="h-1" />
            </div>
          )}
        </div>

        {/* 分割线 */}
        <div
          className="w-5 mb-1"
          style={{ height: 1, backgroundColor: 'var(--color-border)' }}
        />

        {/* 视图切换按钮 */}
        {activities.map(({ id, icon: Icon, zh, en }) => {
          const label = text(zh, en)
          const isActive = sidebarOpen && sidebarView === id
          return (
            <button
              key={id}
              onClick={() => setSidebarView(id)}
              title={label}
              className="relative flex items-center justify-center w-[36px] h-[36px] rounded-md transition-colors"
              style={{
                color: isActive
                  ? 'var(--color-activity-icon-active)'
                  : 'var(--color-activity-icon)',
              }}
            >
              {isActive && (
                <div
                  className="absolute left-0 top-[8px] bottom-[8px] w-[2px] rounded-r"
                  style={{ backgroundColor: 'var(--color-activity-indicator)' }}
                />
              )}
              <Icon size={22} strokeWidth={isActive ? 2 : 1.5} />
            </button>
          )
        })}
      </div>

      {/* ===== 下部：设置 ===== */}
      <div className="flex flex-col items-center gap-0.5 pb-1">
        <button
          onClick={() => useLayoutStore.getState().openSettings()}
          title={text('设置', 'Settings')}
          className="flex items-center justify-center w-[36px] h-[36px] rounded-md transition-colors"
          style={{ color: 'var(--color-activity-icon)' }}
        >
          <Settings size={22} strokeWidth={1.5} />
        </button>
      </div>
    </div>
  )
}
