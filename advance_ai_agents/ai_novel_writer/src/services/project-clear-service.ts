import { ipc } from './ipc-client'
import { useDraftStore } from '../stores/draft-store'
import { useEditorStore, type EditorTab } from '../stores/editor-store'
import { useProjectStore } from '../stores/project-store'
import { useWorkflowStore } from '../stores/workflow-store'
import type { ProjectClearScope } from '../shared/ipc-channels'

export interface ClearProjectDataOptions {
  creativeFields?: boolean
  blueprints?: boolean
  generatedText?: boolean
}

export interface ClearProjectDataResult {
  cleared: ProjectClearScope[]
}

const AFFECTED_TAB_TYPES: Record<ProjectClearScope, EditorTab['type'][]> = {
  creativeFields: ['config', 'world-building', 'arch-file'],
  blueprints: ['chapter-card'],
  generatedText: ['chapter', 'diff', 'version-history', 'review-report'],
}

function normalizeOptions(options: ClearProjectDataOptions): Required<ClearProjectDataOptions> {
  return {
    creativeFields: !!options.creativeFields,
    blueprints: !!options.blueprints,
    generatedText: !!options.generatedText,
  }
}

function selectedScopes(options: Required<ClearProjectDataOptions>): ProjectClearScope[] {
  const scopes: ProjectClearScope[] = []
  if (options.generatedText) scopes.push('generatedText')
  if (options.blueprints) scopes.push('blueprints')
  if (options.creativeFields) scopes.push('creativeFields')
  return scopes
}

function affectedTabs(scopes: ProjectClearScope[], tabs: EditorTab[]): EditorTab[] {
  const affectedTypes = new Set(scopes.flatMap(scope => AFFECTED_TAB_TYPES[scope]))
  return tabs.filter(tab => affectedTypes.has(tab.type))
}

function assertResult(result: { success: boolean; error?: string }, label: string): void {
  if (!result.success) {
    throw new Error(result.error || `${label}失败`)
  }
}

export async function clearProjectData(options: ClearProjectDataOptions): Promise<ClearProjectDataResult> {
  const normalized = normalizeOptions(options)
  const scopes = selectedScopes(normalized)
  if (scopes.length === 0) return { cleared: [] }

  const project = useProjectStore.getState().currentProject
  if (!project) throw new Error('未打开项目')

  if (useWorkflowStore.getState().hasActiveRun()) {
    throw new Error('当前仍有工作流运行中，请先等待完成或取消工作流后再清除。')
  }

  const editorState = useEditorStore.getState()
  const tabsToClose = affectedTabs(scopes, editorState.tabs)
  const dirtyTabs = tabsToClose.filter(tab => tab.dirty)
  if (dirtyTabs.length > 0) {
    throw new Error(`以下内容有未保存修改，请先保存或关闭后再清除：${dirtyTabs.map(tab => tab.name).join('、')}`)
  }

  const result = await ipc.invoke('db:project-clear-generated-data', normalized)
  assertResult(result, '清除项目生成内容')

  for (const tab of tabsToClose) {
    editorState.closeTab(tab.id)
  }

  if (normalized.generatedText) {
    useDraftStore.getState().reset()
  }

  const reopened = await useProjectStore.getState().openProject(project.path)
  if (!reopened) {
    await useProjectStore.getState().refreshFileTree()
    if (normalized.generatedText) await useDraftStore.getState().loadAllDrafts()
  }

  return { cleared: result.cleared ?? scopes }
}
