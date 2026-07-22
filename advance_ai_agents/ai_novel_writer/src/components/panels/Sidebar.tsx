/**
 * Sidebar — 左侧导航面板容器
 *
 * 纯路由容器，根据 sidebarView 切换子视图。
 * 所有子视图已拆分到 sidebar/ 子目录。
 */

import { useState, useEffect } from 'react'
import { useLayoutStore } from '../../stores/layout-store'
import { ContextMenu } from '../ui/ContextMenu'
import KnowledgePanel from './KnowledgePanel'
import HomeSidebarPanel from './sidebar/HomeSidebarPanel'
import ProjectTree from './sidebar/ProjectTree'
import CharactersView from './sidebar/CharactersView'
import {
  registerMenuSetter, unregisterMenuSetter,
  type SidebarMenuState,
} from './sidebar/SidebarShared'
import { useLocaleStore } from '../../stores/locale-store'

/** 左侧面板 */
export default function Sidebar() {
  const sidebarView = useLayoutStore(s => s.sidebarView)
  const text = useLocaleStore(s => s.text)
  // 全局右键菜单状态
  const [sidebarMenu, setSidebarMenu] = useState<SidebarMenuState | null>(null)

  // 注册 / 注销右键菜单 setter
  useEffect(() => {
    registerMenuSetter(setSidebarMenu)
    return () => { unregisterMenuSetter() }
  }, [])

  const viewTitles: Record<string, string> = {
    home:       text('主页', 'Home'),
    project:    text('项目结构', 'Project'),
    knowledge:  text('知识库', 'Knowledge'),
    characters: text('角色管理', 'Characters'),
  }

  return (
    <div
      className="w-full h-full flex flex-col overflow-hidden"
      style={{
        backgroundColor: 'var(--color-sidebar)',
        borderRight: '1px solid var(--color-border)',
      }}
    >
      <div className="panel-header">
        <span>{viewTitles[sidebarView]}</span>
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {sidebarView === 'home'       && <HomeSidebarPanel />}
        {sidebarView === 'project'    && <ProjectTree />}
        {sidebarView === 'knowledge'  && <KnowledgePanel />}
        {sidebarView === 'characters' && <CharactersView />}
      </div>

      {/* 动态右键菜单 */}
      {sidebarMenu && (
        <ContextMenu
          items={sidebarMenu.items}
          position={sidebarMenu.position}
          onClose={() => setSidebarMenu(null)}
        />
      )}
    </div>
  )
}

// 保持向后兼容的 re-export（外部引用了 chapterTitleCache）
export { chapterTitleCache, clearChapterTitleCache } from './sidebar/ManuscriptGroup'
