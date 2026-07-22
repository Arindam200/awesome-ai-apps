/**
 * 内置 Tool 汇总注册
 *
 * 将所有内置 Tool 注册到 ToolRegistry。
 * 在 Agent 初始化时调用 registerBuiltinTools()。
 */

import { toolRegistry } from '../tool-registry'
import { readFileTool } from './read-file.tool'
import { searchKnowledgeTool } from './search-knowledge.tool'
import { readArchitectureTool } from './read-architecture.tool'
import { readBlueprintTool } from './read-blueprint.tool'
import { readCharactersTool } from './read-characters.tool'
import { readProjectStateTool } from './read-project-state.tool'
import { readDraftsTool } from './read-drafts.tool'
import { listChaptersTool } from './list-chapters.tool'
import { writeFileTool } from './write-file.tool'
import { openEditorTool } from './open-editor.tool'
import { startWorkflowTool } from './start-workflow.tool'
import { updateConfigTool } from './update-config.tool'

/** 所有内置 Tool（供外部引用） */
export const builtinTools = [
  // 只读 Tool（自动执行）
  readFileTool,
  searchKnowledgeTool,
  readArchitectureTool,
  readBlueprintTool,
  readCharactersTool,
  readProjectStateTool,
  readDraftsTool,
  listChaptersTool,
  // 行动 Tool（需确认）
  writeFileTool,
  openEditorTool,
  startWorkflowTool,
  updateConfigTool,
]

/**
 * 注册所有内置 Tool
 * 在 Agent 模块初始化时调用
 */
export function registerBuiltinTools(): void {
  toolRegistry.registerAll(builtinTools)
  console.log(`[Agent] 已注册 ${builtinTools.length} 个内置 Tool`)
}
