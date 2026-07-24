/**
 * ProjectService — 项目生命周期与跨 Store 协调的单例调度层
 *
 * 职责：
 * 1. 项目打开/关闭时统一初始化/清空 Layer 2 Store（character、draft）
 * 2. 监听 EventBus 事件，驱动 Store 数据刷新
 * 3. 同步 editor-store 中已打开 Tab 的内容（定稿后磁盘文件已变更的场景）
 *
 * 设计原则：
 * - 组件不再自行 useEffect 加载数据、不再监听 window 事件
 * - 所有跨 Store 联动都经过此 Service
 * - Store 只暴露纯数据 + 操作方法，不包含生命周期逻辑
 */

import { globalEventBus } from '../shared/event-bus'
import { useProjectStore } from '../stores/project-store'
import { useCharacterStore } from '../stores/character-store'
import { useDraftStore } from '../stores/draft-store'
import { ipc } from './ipc-client'

/** 存放解绑函数，用于 dispose 时清理 */
let disposers: Array<() => void> = []

/**
 * 初始化 ProjectService — 注册所有事件监听
 * 应在 App 挂载时调用一次
 */
export function initProjectService(): void {
  // 防止重复初始化
  if (disposers.length > 0) return

  // === 监听 EventBus 事件 ===

  // 工作流完成 → 刷新文件树 + 草稿（覆盖所有工作流类型）
  disposers.push(
    globalEventBus.on('WORKFLOW_COMPLETE', async (payload) => {
      console.log('[ProjectService] WORKFLOW_COMPLETE 事件触发:', payload.type)
      const project = useProjectStore.getState().currentProject
      if (!project) return

      // config_generation 类型只需要轻量刷新（避免不必要的文件扫描）
      if (payload.type === 'config_generation') {
        console.log('[ProjectService] config_generation 完成，跳过资源刷新')
        return
      }

      // 刷新文件树（所有工作流完成后都需要）
      console.log('[ProjectService] 开始刷新文件树...')
      await useProjectStore.getState().refreshFileTree()
      console.log('[ProjectService] 文件树刷新完成')

      // 根据工作流类型精准刷新
      if (payload.type === 'chapter_creation') {
        // 章节创作完成 → 刷新草稿 + 角色卡（定稿后处理会更新角色状态）
        console.log('[ProjectService] 刷新草稿和角色卡...')
        await Promise.all([
          useDraftStore.getState().loadAllDrafts(),
          useCharacterStore.getState().load(),
        ])
        console.log('[ProjectService] 草稿和角色卡刷新完成')
      } else if (payload.type === 'architecture_generation') {
        // 架构生成完成 → 角色卡可能被提取
        console.log('[ProjectService] 刷新角色卡...')
        await useCharacterStore.getState().load()
        console.log('[ProjectService] 角色卡刷新完成')
      }
    })
  )

  // 定稿完成 → 刷新草稿 + 角色 + 文件树 + 同步编辑器 Tab
  disposers.push(
    globalEventBus.on('FINALIZE_COMPLETE', async (payload) => {
      const project = useProjectStore.getState().currentProject
      if (!project) return

      await Promise.all([
        useDraftStore.getState().loadChapterDrafts(payload.chapterNumber),
        useCharacterStore.getState().load(),
        useProjectStore.getState().refreshFileTree(),
      ])

      // 同步编辑器中已打开的相关 Tab 内容（草稿文件可能已被定稿流程修改）
      syncEditorTabsForChapter(payload.chapterNumber)
    })
  )

  // 架构后处理完成 → 刷新角色卡
  disposers.push(
    globalEventBus.on('ARCH_POSTPROCESS_UPDATED', async () => {
      await useCharacterStore.getState().load()
    })
  )

  // 角色卡提取失败 → 也刷新角色卡（确保 UI 状态一致）
  disposers.push(
    globalEventBus.on('CHARACTER_EXTRACT_FAILED', async () => {
      await useCharacterStore.getState().load()
    })
  )

  // 资源刷新请求（由知识库等模块触发）
  disposers.push(
    globalEventBus.on('REFRESH_RESOURCE', async (payload) => {
      const resources = payload.resources
      if (resources.includes('all') || resources.includes('characterCards')) {
        await useCharacterStore.getState().load()
      }
      if (resources.includes('all') || resources.includes('drafts')) {
        await useDraftStore.getState().loadAllDrafts()
      }
      if (resources.includes('all') || resources.includes('fileTree')) {
        await useProjectStore.getState().refreshFileTree()
      }
    })
  )

  console.log('[ProjectService] 已初始化，事件监听已注册')
}

/**
 * 项目打开后的初始化 — 并行加载所有 Layer 2 数据
 * 由 project-store.openProject 成功后调用
 */
export async function onProjectOpened(): Promise<void> {
  const project = useProjectStore.getState().currentProject
  if (!project) return

  // 并行加载角色卡和草稿列表
  await Promise.all([
    useCharacterStore.getState().load(),
    useDraftStore.getState().loadAllDrafts(),
  ])

  // 广播项目已就绪事件
  globalEventBus.emit('PROJECT_CHANGED', { projectPath: project.path })

  console.log('[ProjectService] 项目数据加载完成:', project.path)
}

/**
 * 项目关闭时的清理 — 重置所有 Layer 2 Store
 * 由 project-store.closeProject 调用
 */
export function onProjectClosed(): void {
  // 清空编辑器 Tab
  import('../stores/editor-store').then(m => {
    m.useEditorStore.getState().clearTabs()
  }).catch(() => { })

  // 重置 Layer 2 Store
  useCharacterStore.getState().reset()
  useDraftStore.getState().reset()

  console.log('[ProjectService] 项目已关闭，Layer 2 Store 已重置')
}

/**
 * 同步编辑器中某章节相关 Tab 的内容
 * 当定稿/修稿完成后，磁盘文件已变更，需要把最新内容同步到编辑器
 */
async function syncEditorTabsForChapter(chapterNumber: number): Promise<void> {
  try {
    const { useEditorStore } = await import('../stores/editor-store')
    const tabs = useEditorStore.getState().tabs

    // 找到与该章节相关的已打开 Tab（草稿文件路径包含 ch{N}）
    const chapterPattern = new RegExp(`/ch${chapterNumber}/`)
    const relatedTabs = tabs.filter(t => t.filePath && chapterPattern.test(t.filePath))

    for (const tab of relatedTabs) {
      if (!tab.filePath) continue
      let content = ''
      if (tab.filePath.startsWith('vela://')) {
        const { readDraftBody } = await import('../stores/draft-store')
        content = await readDraftBody(tab.filePath)
      } else {
        const result = await ipc.invoke('fs:read-file', tab.filePath)
        if (result.success) content = result.content
      }
      if (content) {
        useEditorStore.getState().syncTabContent(tab.id, content)
      }
    }
  } catch {
    // 编辑器模块可能未加载，忽略
  }
}

/**
 * 销毁 ProjectService — 清理所有事件监听
 * 通常在 App 卸载时调用
 */
export function disposeProjectService(): void {
  for (const dispose of disposers) {
    dispose()
  }
  disposers = []
  console.log('[ProjectService] 已销毁')
}
