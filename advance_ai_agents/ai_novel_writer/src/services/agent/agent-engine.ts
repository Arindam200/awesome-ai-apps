/**
 * Agent 核心引擎 — ReAct（Reasoning + Acting）循环
 *
 * 这是 Agent 的大脑，负责：
 * 1. 将用户消息、系统提示、Tool 描述组装为 LLM 输入
 * 2. 解析 LLM 输出中的 <tool_call> 标签
 * 3. 执行 Tool 并将结果注入为 observation
 * 4. 循环直到 LLM 不再调用 Tool 或达到最大循环次数
 *
 * 参考 Claude Code 的 query.ts 和 QueryEngine 设计，
 * 但简化为 Vela 的 Electron + React 架构。
 */

import { toolRegistry, type ToolResult, type ToolArtifact } from './tool-registry'

// ===== 常量 =====

/** ReAct 循环最大次数（防止死循环） */
const MAX_TOOL_ROUNDS = 8

/** Tool 执行超时（毫秒） */
const TOOL_TIMEOUT_MS = 30_000

/** Tool 返回内容最大长度（字符） */
const TOOL_RESULT_MAX_CHARS = 3000

// ===== 类型 =====

/** Tool 调用信息 */
export interface ToolCallInfo {
  id: string
  toolName: string
  arguments: Record<string, unknown>
  status: 'pending' | 'running' | 'completed' | 'failed' | 'waiting_confirm'
  result?: string
  error?: string
  /** Tool 来源标记 */
  source?: string
}

/** Agent Engine 回调 */
export interface AgentEngineCallbacks {
  /** 流式文本片段 */
  onTextChunk: (chunk: string) => void
  /** Tool 调用开始 */
  onToolCallStart: (toolCall: ToolCallInfo) => void
  /** Tool 调用完成 */
  onToolCallComplete: (toolCall: ToolCallInfo) => void
  /** Tool 需要用户确认 */
  onToolCallConfirmRequired: (toolCall: ToolCallInfo) => Promise<boolean>
  /** 全部完成 */
  onDone: (fullText: string, toolCalls: ToolCallInfo[], artifacts: ToolArtifact[]) => void
  /** 错误 */
  onError: (error: string) => void
}

/** LLM 消息格式 */
export interface LLMMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

/** LLM 生成函数签名（由 agent-store 提供实际实现） */
export type LLMGenerateFn = (
  messages: LLMMessage[],
  modelId: string,
) => Promise<string>

// ===== 核心引擎 =====

/**
 * 执行 Agent ReAct 循环
 *
 * 流程：
 * 1. 将系统提示（含 Tool 描述）+ 历史消息 + 用户消息发送给 LLM
 * 2. 解析 LLM 回复中的 <tool_call> 标签
 * 3. 如果有 tool_call → 执行 Tool → 将结果作为 observation 追加到消息历史 → 重新调用 LLM
 * 4. 循环直到 LLM 不再调用 Tool 或达到 MAX_TOOL_ROUNDS
 * 5. 返回最终文本回复
 */
export async function runAgentLoop(
  systemPrompt: string,
  historyMessages: LLMMessage[],
  userMessage: string,
  modelId: string,
  generateFn: LLMGenerateFn,
  callbacks: AgentEngineCallbacks,
  abortSignal?: AbortSignal,
): Promise<void> {
  const allToolCalls: ToolCallInfo[] = []
  const allArtifacts: ToolArtifact[] = []

  // 构建消息列表
  const messages: LLMMessage[] = [
    { role: 'system', content: systemPrompt },
    ...historyMessages,
    { role: 'user', content: userMessage },
  ]

  let rounds = 0
  let fullAssistantText = ''

  while (rounds < MAX_TOOL_ROUNDS) {
    // 检查中止信号
    if (abortSignal?.aborted) {
      callbacks.onDone(fullAssistantText + '\n\n_（已停止生成）_', allToolCalls, allArtifacts)
      return
    }

    rounds++

    // 调用 LLM
    let llmResponse: string
    try {
      llmResponse = await generateFn(messages, modelId)
    } catch (error) {
      callbacks.onError(`LLM 调用失败：${String(error)}`)
      return
    }

    // 检查中止
    if (abortSignal?.aborted) {
      callbacks.onDone(fullAssistantText + '\n\n_（已停止生成）_', allToolCalls, allArtifacts)
      return
    }

    // 解析 LLM 回复：分离文本和 tool_call
    const { textParts, toolCalls } = parseToolCalls(llmResponse)

    // 输出文本部分（清理可能残留的 tool_call/tool_result 标记）
    let textContent = textParts.join('')
    textContent = textContent
      .replace(/<tool_call>[\s\S]*?<\/tool_call>/g, '')
      .replace(/<tool_result[\s\S]*?<\/tool_result>/g, '')
      .replace(/<\/?tool_call>/g, '')      // 清理孤立的开/闭标签
      .replace(/<\/?tool_result>/g, '')     // 清理孤立的 result 标签
      .replace(/\n{3,}/g, '\n\n')
      .trim()
    if (textContent) {
      callbacks.onTextChunk(textContent)
      fullAssistantText += textContent
    }

    // 如果没有 tool_call，循环结束
    if (toolCalls.length === 0) {
      callbacks.onDone(fullAssistantText, allToolCalls, allArtifacts)
      return
    }

    // 将 LLM 的完整回复加入历史（包含 tool_call 标签）
    messages.push({ role: 'assistant', content: llmResponse })

    // 依次执行每个 tool_call
    const observationParts: string[] = []

    for (const tc of toolCalls) {
      const toolCallInfo: ToolCallInfo = {
        id: crypto.randomUUID(),
        toolName: tc.name,
        arguments: tc.arguments,
        status: 'pending',
      }
      allToolCalls.push(toolCallInfo)

      // 查找 Tool
      const tool = toolRegistry.get(tc.name)
      if (!tool) {
        toolCallInfo.status = 'failed'
        toolCallInfo.error = `未知工具：${tc.name}`
        callbacks.onToolCallComplete(toolCallInfo)
        observationParts.push(`<tool_result name="${tc.name}" error="true">\n未知工具：${tc.name}。可用工具：${toolRegistry.listAll().map(t => t.name).join(', ')}\n</tool_result>`)
        continue
      }

      // 记录来源
      toolCallInfo.source = tool.source

      // 需要用户确认的 Tool
      if (tool.requiresConfirmation) {
        toolCallInfo.status = 'waiting_confirm'
        callbacks.onToolCallStart(toolCallInfo)

        const confirmed = await callbacks.onToolCallConfirmRequired(toolCallInfo)
        if (!confirmed) {
          toolCallInfo.status = 'failed'
          toolCallInfo.error = '用户拒绝执行'
          callbacks.onToolCallComplete(toolCallInfo)
          observationParts.push(`<tool_result name="${tc.name}" error="true">\n用户拒绝了此操作\n</tool_result>`)
          continue
        }
      }

      // 执行 Tool
      toolCallInfo.status = 'running'
      callbacks.onToolCallStart(toolCallInfo)

      try {
        const result = await executeToolWithTimeout(tool.execute, tc.arguments, TOOL_TIMEOUT_MS)

        // 截断过长的结果
        const truncatedContent = truncateResult(result.content, TOOL_RESULT_MAX_CHARS)

        toolCallInfo.status = result.success ? 'completed' : 'failed'
        toolCallInfo.result = truncatedContent
        if (result.error) toolCallInfo.error = result.error
        if (result.artifacts) allArtifacts.push(...result.artifacts)

        callbacks.onToolCallComplete(toolCallInfo)

        if (result.success) {
          observationParts.push(`<tool_result name="${tc.name}">\n${truncatedContent}\n</tool_result>`)
        } else {
          observationParts.push(`<tool_result name="${tc.name}" error="true">\n${result.error ?? truncatedContent}\n</tool_result>`)
        }
      } catch (error) {
        toolCallInfo.status = 'failed'
        toolCallInfo.error = `执行异常：${String(error)}`
        callbacks.onToolCallComplete(toolCallInfo)
        observationParts.push(`<tool_result name="${tc.name}" error="true">\n执行异常：${String(error)}\n</tool_result>`)
      }
    }

    // 将所有 tool 结果作为 user role 的 observation 注入
    // 加上明确提示，防止 LLM 误以为这是用户新发言
    const observation = `[以下是工具执行结果，请根据结果继续回答用户的问题]\n\n${observationParts.join('\n\n')}\n\n[请根据上面的工具结果，继续回答用户的原始问题。如果需要更多信息可以继续调用工具。]`
    messages.push({ role: 'user', content: observation })
  }

  // 达到最大循环次数
  if (rounds >= MAX_TOOL_ROUNDS) {
    fullAssistantText += '\n\n⚠️ 已达到最大工具调用次数限制，自动停止。'
  }

  callbacks.onDone(fullAssistantText, allToolCalls, allArtifacts)
}

// ===== 工具函数 =====

/** 解析的 Tool 调用 */
interface ParsedToolCall {
  name: string
  arguments: Record<string, unknown>
}

/**
 * 从 LLM 输出中解析 <tool_call>...</tool_call> 标签
 *
 * 返回分离后的文本片段和 tool 调用列表。
 * 增强版：支持 JSON 前后有多余文字的容错解析。
 */
export function parseToolCalls(text: string): {
  textParts: string[]
  toolCalls: ParsedToolCall[]
} {
  const toolCalls: ParsedToolCall[] = []
  const textParts: string[] = []

  // 匹配 <tool_call>...</tool_call> 标签
  const regex = /<tool_call>\s*([\s\S]*?)\s*<\/tool_call>/g
  let lastIndex = 0
  let match: RegExpExecArray | null = null

  while ((match = regex.exec(text)) !== null) {
    // 收集标签前的文本
    if (match.index > lastIndex) {
      const before = text.slice(lastIndex, match.index).trim()
      if (before) textParts.push(before)
    }
    lastIndex = regex.lastIndex

    // 解析 JSON（增强容错）
    const rawContent = match[1].trim()
    let parsed = false

    // 策略 1：直接解析整个内容
    try {
      const data = JSON.parse(rawContent)
      if (data.name && typeof data.name === 'string') {
        toolCalls.push({ name: data.name, arguments: data.arguments ?? {} })
        parsed = true
      }
    } catch { /* 尝试容错解析 */ }

    // 策略 2：从内容中提取 JSON 对象（LLM 可能在 JSON 前后加了额外文字）
    if (!parsed) {
      const jsonMatch = rawContent.match(/\{[\s\S]*\}/)
      if (jsonMatch) {
        try {
          const data = JSON.parse(jsonMatch[0])
          if (data.name && typeof data.name === 'string') {
            toolCalls.push({ name: data.name, arguments: data.arguments ?? {} })
            parsed = true
          }
        } catch {
          console.warn('[AgentEngine] tool_call JSON 容错解析也失败:', rawContent)
        }
      }
    }

    // 完全解析失败，丢弃该标签（不再打回 textParts，避免泄露 XML）
    if (!parsed) {
      console.warn('[AgentEngine] tool_call 标签解析失败，已丢弃:', rawContent)
    }
  }

  // 收集最后一个标签后的文本
  if (lastIndex < text.length) {
    const after = text.slice(lastIndex).trim()
    if (after) textParts.push(after)
  }

  // 如果没有匹配到任何标签，整个文本都是 textParts
  if (toolCalls.length === 0 && textParts.length === 0) {
    textParts.push(text)
  }

  return { textParts, toolCalls }
}

/**
 * 带超时的 Tool 执行
 */
async function executeToolWithTimeout(
  executeFn: (args: Record<string, unknown>) => Promise<ToolResult>,
  args: Record<string, unknown>,
  timeoutMs: number,
): Promise<ToolResult> {
  return Promise.race([
    executeFn(args),
    new Promise<ToolResult>((_, reject) =>
      setTimeout(() => reject(new Error(`工具执行超时（${timeoutMs / 1000}s）`)), timeoutMs)
    ),
  ])
}

/**
 * 截断过长的 Tool 结果
 */
function truncateResult(content: string, maxChars: number): string {
  if (content.length <= maxChars) return content
  return content.slice(0, maxChars) + `\n\n…（内容已截断，完整内容共 ${content.length} 字符。可使用 read_file 工具获取完整文件内容）`
}
