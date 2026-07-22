/**
 * Agent 智能上下文构建器
 *
 * 采用三级注入策略管理 Token 消耗：
 * - L0 始终注入（~500 token）：项目名称/类型/进度/一句话大纲
 * - L1 编辑器感知（~800 token）：当前打开的 Tab 信息
 * - L2 按需获取：通过 Tool 调用获取详细数据
 *
 * 这是 Agent 理解用户上下文的核心模块。
 */

import { useProjectStore } from '../../stores/project-store'
import { useEditorStore } from '../../stores/editor-store'
import { useWorkflowStore } from '../../stores/workflow-store'
import type { AgentMode } from '../../stores/agent-store'
import { toolRegistry } from './tool-registry'

// ===== 上下文构建 =====

/**
 * 构建 Agent 系统提示词（含上下文和 Tool 描述）
 *
 * 这是 Agent 每次对话时的系统提示词入口。
 * 将项目上下文、编辑器状态、可用 Tool 列表整合为一份完整的系统提示。
 */
export function buildAgentSystemPrompt(mode: AgentMode): string {
  const sections: string[] = []

  // 1. Agent 身份与行为指导
  sections.push(buildIdentityPrompt(mode))

  // 2. L0 — 始终注入的项目上下文
  const l0 = buildL0ProjectContext()
  if (l0) sections.push(l0)

  // 3. L1 — 编辑器感知上下文
  const l1 = buildL1EditorContext()
  if (l1) sections.push(l1)

  // 4. Tool 系统提示词
  const toolPrompt = toolRegistry.generateToolPrompt()
  if (toolPrompt) sections.push(toolPrompt)

  return sections.join('\n\n---\n\n')
}

// ===== 内部构建方法 =====

/** Agent 身份提示词 */
function buildIdentityPrompt(mode: AgentMode): string {
  const modeDesc = mode === 'planning'
    ? '当前处于 Planning 模式：你可以先规划再执行，适合复杂的多步骤任务。请先分析需求，制定方案，再逐步执行。'
    : '当前处于 Fast 模式：你直接高效地完成任务，适合简单快速的操作。'

  return `# AI小说作家 AI 创作助手

你是 AI小说作家智能创作助手，专注于帮助作家进行长篇小说创作。

${modeDesc}

## 核心能力
- 📖 深入理解小说项目的架构、人物、情节，提供专业的创作建议
- 🔍 通过工具调用主动获取项目数据（架构文件、角色卡、蓝图、草稿等）
- ✏️ 通过工具触发创作工作流（写稿、修稿、审计、定稿）
- 🧠 结合知识库做检索增强生成（RAG）

## 行为规范
- 使用中文回复
- 回答应当专业、具体、富有创意
- 主动使用工具获取所需信息，而非要求用户提供
- 对于写入型操作（修改文件、触发工作流），先说明你要做什么，再调用工具
- 如果需要多步操作，可以逐步调用多个工具`
}

/**
 * L0 — 始终注入的项目上下文
 * 约 300-500 token，每次对话都注入
 */
function buildL0ProjectContext(): string | null {
  const project = useProjectStore.getState().currentProject
  if (!project) return null

  const cfg = project.novelConfig
  const parts: string[] = [
    `## 当前项目上下文`,
    `项目名称：《${project.name}》`,
  ]

  if (cfg.genre) {
    parts.push(`类型：${cfg.genre}${cfg.subGenre ? ' · ' + cfg.subGenre : ''}`)
  }
  if (cfg.targetAudience) {
    parts.push(`目标读者：${cfg.targetAudience}`)
  }
  if (cfg.totalChapters) {
    parts.push(`计划章节数：${cfg.totalChapters} 章`)
  }
  if (cfg.wordsPerChapter) {
    parts.push(`每章字数：约 ${cfg.wordsPerChapter} 字`)
  }
  if (cfg.narrativePOV) {
    const povMap: Record<string, string> = {
      'third_limited': '第三人称有限',
      'first_person': '第一人称',
      'third_omniscient': '第三人称全知',
      'multi_pov': '多视角',
    }
    parts.push(`叙事视角：${povMap[cfg.narrativePOV] ?? cfg.narrativePOV}`)
  }
  if (cfg.coreOutline) {
    // 截取前 300 字符，避免 Token 爆炸
    const outline = cfg.coreOutline.length > 300
      ? cfg.coreOutline.slice(0, 300) + '…'
      : cfg.coreOutline
    parts.push(`核心大纲：${outline}`)
  }
  if (cfg.writingStyle) {
    const style = cfg.writingStyle.length > 150
      ? cfg.writingStyle.slice(0, 150) + '…'
      : cfg.writingStyle
    parts.push(`写作风格：${style}`)
  }

  return parts.join('\n')
}

/**
 * L1 — 编辑器感知上下文
 * 约 200-500 token，注入当前打开的 Tab 信息和工作流状态
 */
function buildL1EditorContext(): string | null {
  const parts: string[] = []

  // 当前打开的编辑器 Tab
  const editorState = useEditorStore.getState()
  if (editorState.tabs.length > 0) {
    const activeTab = editorState.tabs.find(t => t.id === editorState.activeTabId)
    const tabSummaries = editorState.tabs.map(t => {
      const active = t.id === editorState.activeTabId ? ' [当前活跃]' : ''
      const dirty = t.dirty ? ' [未保存]' : ''
      return `  - ${t.name} (${t.type})${active}${dirty}`
    }).join('\n')

    parts.push(`## 编辑器状态\n打开的文件：\n${tabSummaries}`)

    // 如果当前活跃 Tab 有内容且不太长，注入内容摘要
    if (activeTab?.content && activeTab.content.length > 0) {
      const preview = activeTab.content.length > 500
        ? activeTab.content.slice(0, 500) + '\n…（内容过长已截断，可通过 read_file 工具获取完整内容）'
        : activeTab.content
      parts.push(`### 当前活跃文件内容\n文件名：${activeTab.name}\n\`\`\`\n${preview}\n\`\`\``)
    }
  }

  // 当前工作流状态
  const workflowState = useWorkflowStore.getState()
  if (workflowState.hasActiveRun()) {
    const run = workflowState.currentRun
    if (run) {
      parts.push(`## 工作流状态\n当前有工作流正在运行：${run.title}（进度：${run.currentStepIndex + 1}/${run.steps.length}）`)
    }
  }

  return parts.length > 0 ? parts.join('\n\n') : null
}
