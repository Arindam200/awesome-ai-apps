import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearProjectData } from '../project-clear-service'
import { ipc } from '../ipc-client'
import { useDraftStore } from '../../stores/draft-store'
import { useEditorStore } from '../../stores/editor-store'
import { useProjectStore } from '../../stores/project-store'
import { useWorkflowStore } from '../../stores/workflow-store'

vi.mock('../ipc-client', () => ({
  ipc: {
    invoke: vi.fn(),
  },
}))

const openProject = vi.fn()
const refreshFileTree = vi.fn()
const draftReset = vi.fn()
const loadAllDrafts = vi.fn()
const clearTabs = vi.fn()
const closeTab = vi.fn()
const hasActiveRun = vi.fn()

vi.mock('../../stores/project-store', () => ({
  useProjectStore: {
    getState: vi.fn(() => ({
      currentProject: { path: 'C:/novels/project-a' },
      openProject,
      refreshFileTree,
    })),
  },
}))

vi.mock('../../stores/draft-store', () => ({
  useDraftStore: {
    getState: vi.fn(() => ({
      reset: draftReset,
      loadAllDrafts,
    })),
  },
}))

vi.mock('../../stores/editor-store', () => ({
  useEditorStore: {
    getState: vi.fn(() => ({
      tabs: [],
      clearTabs,
      closeTab,
    })),
  },
}))

vi.mock('../../stores/workflow-store', () => ({
  useWorkflowStore: {
    getState: vi.fn(() => ({
      hasActiveRun,
    })),
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
  hasActiveRun.mockReturnValue(false)
  vi.mocked(ipc.invoke).mockResolvedValue({ success: true } as never)
  vi.mocked(useProjectStore.getState).mockReturnValue({
    currentProject: { path: 'C:/novels/project-a' },
    openProject,
    refreshFileTree,
  } as never)
  vi.mocked(useDraftStore.getState).mockReturnValue({
    reset: draftReset,
    loadAllDrafts,
  } as never)
  vi.mocked(useEditorStore.getState).mockReturnValue({
    tabs: [],
    clearTabs,
    closeTab,
  } as never)
  vi.mocked(useWorkflowStore.getState).mockReturnValue({
    hasActiveRun,
  } as never)
})

describe('clearProjectData', () => {
  it('clears selected generated project data through one transactional IPC and reloads the project', async () => {
    await clearProjectData({
      creativeFields: true,
      blueprints: true,
      generatedText: true,
    })

    expect(ipc.invoke).toHaveBeenCalledOnce()
    expect(ipc.invoke).toHaveBeenCalledWith('db:project-clear-generated-data', {
      creativeFields: true,
      blueprints: true,
      generatedText: true,
    })
    expect(clearTabs).not.toHaveBeenCalled()
    expect(draftReset).toHaveBeenCalledOnce()
    expect(openProject).toHaveBeenCalledWith('C:/novels/project-a')
  })

  it('does not clear draft stores when only architecture fields are selected', async () => {
    await clearProjectData({
      creativeFields: true,
      blueprints: false,
      generatedText: false,
    })

    expect(ipc.invoke).toHaveBeenCalledOnce()
    expect(ipc.invoke).toHaveBeenCalledWith('db:project-clear-generated-data', {
      creativeFields: true,
      blueprints: false,
      generatedText: false,
    })
    expect(clearTabs).not.toHaveBeenCalled()
    expect(draftReset).not.toHaveBeenCalled()
    expect(openProject).toHaveBeenCalledWith('C:/novels/project-a')
  })

  it('surfaces failed clear operations', async () => {
    vi.mocked(ipc.invoke).mockResolvedValueOnce({ success: false, error: '数据库忙' } as never)

    await expect(clearProjectData({ generatedText: true })).rejects.toThrow('数据库忙')
    expect(openProject).not.toHaveBeenCalled()
  })

  it('blocks clear while workflows are active', async () => {
    hasActiveRun.mockReturnValue(true)

    await expect(clearProjectData({ generatedText: true })).rejects.toThrow('工作流')
    expect(ipc.invoke).not.toHaveBeenCalled()
  })

  it('blocks clear when affected tabs have unsaved edits', async () => {
    vi.mocked(useEditorStore.getState).mockReturnValue({
      tabs: [
        { id: 'config', name: '小说配置', type: 'config', dirty: true },
        { id: 'character-a', name: '角色A', type: 'character', dirty: true },
      ],
      clearTabs,
      closeTab,
    } as never)

    await expect(clearProjectData({ creativeFields: true })).rejects.toThrow('未保存')
    expect(ipc.invoke).not.toHaveBeenCalled()
  })

  it('closes only affected clean tabs after clear', async () => {
    vi.mocked(useEditorStore.getState).mockReturnValue({
      tabs: [
        { id: 'chapter-card-editor', name: '章节蓝图', type: 'chapter-card' },
        { id: 'character-a', name: '角色A', type: 'character', dirty: true },
      ],
      clearTabs,
      closeTab,
    } as never)

    await clearProjectData({ blueprints: true })

    expect(closeTab).toHaveBeenCalledWith('chapter-card-editor')
    expect(closeTab).not.toHaveBeenCalledWith('character-a')
  })
})
