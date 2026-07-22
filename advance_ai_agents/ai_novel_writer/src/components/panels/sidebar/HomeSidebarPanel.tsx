/**
 * HomeSidebarPanel — 主页侧边栏：项目管理入口 + 最近项目列表
 */

import { FolderOpen, Trash2 } from 'lucide-react'
import { useProjectStore } from '../../../stores/project-store'
import { useLayoutStore } from '../../../stores/layout-store'
import { ipc } from '../../../services/ipc-client'
import { Button } from '../../ui/Button'
import { confirm } from '../../ui/Confirm'
import { toast } from '../../ui/Toast'
import { useLocaleStore } from '../../../stores/locale-store'

export default function HomeSidebarPanel() {
  const currentProject = useProjectStore(s => s.currentProject)
  const recentProjects = useProjectStore(s => s.recentProjects)
  const openProject = useProjectStore(s => s.openProject)
  const deleteProject = useProjectStore(s => s.deleteProject)
  const text = useLocaleStore(s => s.text)

  const handleDeleteProject = async (project: { name: string; path: string }) => {
    const ok = await confirm(
      text(`确认删除项目「${project.name}」？\n此操作会删除该项目目录下的小说正文、故事架构、角色、蓝图、知识库和所有项目数据。`, `Delete project “${project.name}”?\nThis removes its manuscripts, architecture, characters, blueprints, knowledge base, and all project data.`),
      {
        title: text('删除项目', 'Delete project'),
        confirmText: text('删除项目', 'Delete project'),
        danger: true,
      },
    )
    if (!ok) return

    const success = await deleteProject(project.path)
    if (success) {
      toast.success(text(`项目「${project.name}」已删除`, `Project “${project.name}” deleted`))
    }
  }

  return (
    <div className="px-3 py-2 text-sm">
      {/* 当前项目信息 */}
      {currentProject && (
        <div
          className="mb-3 px-3 py-2.5 rounded-lg"
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
            <button
              type="button"
              title={text('删除项目', 'Delete project')}
              className="writer-command-button"
              style={{ minHeight: 24, minWidth: 28, padding: 0, color: 'var(--color-danger)' }}
              onClick={(e) => {
                e.stopPropagation()
                handleDeleteProject(currentProject)
              }}
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex flex-col gap-1.5 mb-3">
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
              openProject(folder)
            }
          }}
        >
          {text('打开项目', 'Open project')}
        </Button>
      </div>

      {/* 最近项目列表 */}
      {recentProjects.length > 0 && (
        <div>
          <div
            className="flex items-center gap-1.5 mb-2 pt-2"
            style={{ borderTop: '1px solid var(--color-border)' }}
          >
            <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
        {text('最近项目', 'Recent projects')}
            </span>
          </div>
          <div className="space-y-0.5">
            {recentProjects
              .filter(p => p.path !== currentProject?.path)
              .slice(0, 10)
              .map((p, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-colors"
                  style={{ backgroundColor: 'transparent' }}
                  onMouseEnter={e => e.currentTarget.style.backgroundColor = 'var(--color-hover)'}
                  onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                  onClick={() => openProject(p.path)}
                >
                  <FolderOpen size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs truncate" style={{ color: 'var(--color-text)' }}>
                      {p.name}
                    </p>
                    <p className="text-[0.65rem] truncate" style={{ color: 'var(--color-text-muted)' }}>
                      {p.path}
                    </p>
                  </div>
                  <button
                    type="button"
                  title={text('删除项目', 'Delete project')}
                    className="writer-command-button opacity-70 hover:opacity-100"
                    style={{ minHeight: 24, minWidth: 28, padding: 0, color: 'var(--color-danger)' }}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteProject(p)
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            {recentProjects.filter(p => p.path !== currentProject?.path).length === 0 && (
              <p className="text-xs px-2 py-1 opacity-50" style={{ color: 'var(--color-text-muted)' }}>
          {text('暂无其他最近项目', 'No other recent projects')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
