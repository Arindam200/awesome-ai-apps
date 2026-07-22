import { create } from 'zustand'

/** 编辑器 Tab 数据 */
export interface EditorTab {
  id: string
  name: string
  type: 'chapter' | 'outline' | 'character' | 'config' | 'diff' | 'chapter-card' | 'world-building' | 'arch-file' | 'version-history' | 'review-report'
  filePath?: string
  content?: string
  /** diff 视图的原始内容 */
  originalContent?: string
  dirty?: boolean
  /** 固定 Tab，不可关闭 */
  pinned?: boolean
  /** 修稿文件路径（三栏合并用） */
  revisionPath?: string
  /** 审稿报告内容（供「根据意见修稿」使用） */
  reviewReport?: string
  /** 草稿所属章节号 */
  chapterNumber?: number
  /** 草稿所在章节目录 */
  chapterDir?: string
  /** 审稿报告存放路径 */
  reportPath?: string
}

interface EditorState {
  /** 打开的 Tab 列表 */
  tabs: EditorTab[]
  /** 当前活跃的 Tab ID */
  activeTabId: string | null

  // ===== Actions =====
  /** 打开文件（如果已打开则激活） */
  openFile: (tab: EditorTab) => void
  /** 关闭 Tab */
  closeTab: (tabId: string) => void
  /** 激活 Tab */
  setActiveTab: (tabId: string) => void
  /**
   * 更新 Tab 内容（标记 dirty）
   * 仅在「用户修改」时调用，会亮起未保存指示灯。
   */
  updateTabContent: (tabId: string, content: string) => void
  /**
   * 静默同步 Tab 内容（不标记 dirty，也不清除 dirty）
   * 用于「AI 生成完成后刷新」、「打开文件刷新」等非用户编辑场景。
   */
  syncTabContent: (tabId: string, content: string) => void
  /**
   * 标记 Tab 已保存（清除 dirty 标记）
   * 在保存成功后调用，使警示灯、Tab 圆点消失。
   */
  markTabSaved: (tabId: string) => void
  /** 清空所有 Tab */
  clearTabs: () => void
}

export const useEditorStore = create<EditorState>()((set, get) => ({
  tabs: [],
  activeTabId: null,

  openFile: (tab) => {
    // diff 类型每次内容不同，只按 id 精确匹配（不走 filePath 去重）
    // 其他类型（含 review-report）按 filePath + type 去重
    const idOnly = tab.type === 'diff'
    const existing = get().tabs.find((t) =>
      t.id === tab.id ||
      (!idOnly && tab.filePath !== undefined && t.filePath === tab.filePath && t.type === tab.type)
    )
    if (existing) {
      // diff / review-report 每次内容不同，强制更新内容后激活
      if (tab.type === 'diff' || tab.type === 'review-report') {
        set((s) => ({
          tabs: s.tabs.map((t) => t.id === existing.id ? { ...t, ...tab, id: tab.id } : t),
          activeTabId: tab.id,
        }))
      } else {
        // 其他类型 Tab：已打开，更新名称并直接激活
        set((s) => ({
          tabs: s.tabs.map((t) => t.id === existing.id ? { ...t, name: tab.name } : t),
          activeTabId: existing.id,
        }))
      }
    } else {
      // 新开 Tab
      set((s) => ({
        tabs: [...s.tabs, tab],
        activeTabId: tab.id,
      }))
    }
  },

  closeTab: (tabId) => {
    const { tabs, activeTabId } = get()
    // pinned Tab 不可关闭
    const target = tabs.find((t) => t.id === tabId)
    if (target?.pinned) return
    const newTabs = tabs.filter((t) => t.id !== tabId)
    set({
      tabs: newTabs,
      activeTabId: activeTabId === tabId
        ? (newTabs.length > 0 ? newTabs[newTabs.length - 1].id : null)
        : activeTabId,
    })
  },

  setActiveTab: (tabId) => {
    set({ activeTabId: tabId })
  },

  updateTabContent: (tabId, content) => {
    set((s) => ({
      tabs: s.tabs.map((t) => t.id === tabId ? { ...t, content, dirty: true } : t),
    }))
  },

  // 静默刷新内容（不改变 dirty 标记，用于 AI 生成后刷新、打开文件同步等场景）
  syncTabContent: (tabId, content) => {
    set((s) => ({
      tabs: s.tabs.map((t) => t.id === tabId ? { ...t, content } : t),
    }))
  },

  // 标记 Tab 已保存 —— 清除 dirty 标记，使标题栏警示灯和 Tab 圆点消失
  markTabSaved: (tabId) => {
    set((s) => ({
      tabs: s.tabs.map((t) => t.id === tabId ? { ...t, dirty: false } : t),
    }))
  },

  clearTabs: () => {
    set({ tabs: [], activeTabId: null })
  },
}))
