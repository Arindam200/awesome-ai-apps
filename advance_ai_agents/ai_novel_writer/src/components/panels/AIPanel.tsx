import { useEffect } from 'react'
import { useLLMStore } from '../../stores/llm-store'
import AgentHeader from './agent/AgentHeader'
import AgentConversation from './agent/AgentConversation'

/**
 * 右侧 AI Agent 面板
 * 重构后采用多会话管理架构，参考 Antigravity agent-side-panel 设计
 * - 顶部：AgentHeader（新建/历史/更多/关闭）
 * - 主体：AgentConversation（空状态/对话/历史三态）
 */
export default function AIPanel() {
  // 确保 LLM store 已初始化
  const init = useLLMStore(s => s.init)
  const loaded = useLLMStore(s => s.loaded)
  useEffect(() => {
    if (!loaded) init()
  }, [init, loaded])

  return (
    <div className="writer-ai-panel w-full h-full flex flex-col overflow-hidden">
      {/* 顶部工具栏 */}
      <AgentHeader />

      {/* 主对话区：占满剩余高度 */}
      <div className="flex-1 overflow-hidden">
        <AgentConversation />
      </div>
    </div>
  )
}
