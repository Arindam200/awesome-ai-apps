import { useEffect, useRef, useState } from 'react'
import { ArrowDown, Trash2, Workflow } from 'lucide-react'
import { useAgentStore } from '../../../stores/agent-store'
import { useLayoutStore } from '../../../stores/layout-store'
import { APP_BRAND } from '../../../shared/brand'
import AgentMessage from './AgentMessage'
import AgentInputBox from './AgentInputBox'
import { formatRelativeTime } from '../../../utils/time'

/**
 * 对话区域主组件
 * - 空状态：居中显示欢迎词 + 输入框 + 最近会话（参考 agent1.html pt-[30vh] 设计）
 * - 有会话：消息列表 + 底部固定输入框
 */
export default function AgentConversation() {
  const { getActiveConversation, showHistory } = useAgentStore()
  const activeConv = getActiveConversation()

  // 历史面板模式
  if (showHistory) {
    return <AgentHistoryPanel />
  }

  // 空状态（无活跃会话）
  if (!activeConv || activeConv.messages.length === 0) {
    return <EmptyState />
  }

  // 有消息的对话视图
  return <ActiveConversation />
}

// ===== 空状态视图 =====

function EmptyState() {
  const { conversations, selectConversation } = useAgentStore()
  // 取最近 3 条历史会话（不包含当前空会话）
  const recentConvs = conversations
    .filter(c => c && c.messages.length > 0)
    .slice(0, 3)



  return (
    <div className="h-full overflow-y-auto">
      <div
        className="px-4"
        style={{ paddingTop: 'max(22vh, 48px)', paddingBottom: 24 }}
      >
        {/* 标题 */}
        <div className="mb-1 pl-1 text-base font-semibold" style={{ color: 'var(--color-text)' }}>
          {APP_BRAND.zhName}
        </div>
        {/* 副标题 */}
        <div className="mb-3 pl-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          你的 AI 创作助手 — 支持 <code className="px-1 py-0.5 rounded text-[0.68rem]" style={{ backgroundColor: 'var(--color-hover)', color: 'var(--color-accent)' }}>/</code> 命令和 <code className="px-1 py-0.5 rounded text-[0.68rem]" style={{ backgroundColor: 'var(--color-hover)', color: 'var(--color-accent)' }}>@</code> 引用
        </div>

        {/* 输入框 */}
        <AgentInputBox />



        {/* 最近会话（如有） */}
        {recentConvs.length > 0 && (
          <div className="mt-6">
            <div className="flex flex-col gap-0">
              {recentConvs.map(conv => (
                <RecentConversationItem
                  key={conv.id}
                  title={conv.title}
                  updatedAt={conv.updatedAt}
                  onClick={() => selectConversation(conv.id)}
                  onDelete={() => useAgentStore.getState().deleteConversation(conv.id)}
                />
              ))}
            </div>
            {conversations.filter(c => c.messages.length > 0).length > 3 && (
              <button
                onClick={() => useAgentStore.getState().setShowHistory(true)}
                className="mt-4 text-left text-xs transition-all hover:underline"
                style={{ color: 'var(--color-text-muted)' }}
                onMouseEnter={e => (e.currentTarget.style.opacity = '0.8')}
                onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
              >
                查看全部对话
              </button>
            )}
          </div>
        )}

        {/* 底部提示 */}
        <div className="pt-8 text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
          AI 生成内容仅供参考，重要信息请自行核实。
        </div>
      </div>
    </div>
  )
}

// ===== 活跃对话视图 =====

function ActiveConversation() {
  const { getActiveConversation, generating } = useAgentStore()
  const activeConv = getActiveConversation()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [isAtBottom, setIsAtBottom] = useState(true)

  // 消息变化时自动滚动到底部
  useEffect(() => {
    if (isAtBottom && scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }
  }, [activeConv?.messages, generating, isAtBottom])

  // 监听滚动位置判断是否在底部
  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    setIsAtBottom(distanceFromBottom < 60)
  }

  /** 跳转到底部 */
  const scrollToBottom = () => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }

  if (!activeConv) return null

  return (
    <div className="flex flex-col h-full relative">
      {/* 消息列表滚动区 */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-4"
      >
        <div className="flex flex-col">
          {activeConv.messages
            .filter(m => m.role !== 'system')
            .map(msg => (
              <AgentMessage key={msg.id} message={msg} />
            ))}
        </div>
        {/* 底部空间 */}
        <div className="h-4" />
      </div>

      {/* 跳到底部浮动按钮 */}
      {!isAtBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute z-10 flex items-center justify-center w-7 h-7 rounded-full shadow-md transition-all"
          style={{
            right: 16,
            bottom: 100,
            backgroundColor: 'var(--color-sidebar)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)',
          }}
          title="回到底部"
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = 'var(--color-accent)'
            e.currentTarget.style.color = 'var(--color-accent)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = 'var(--color-border)'
            e.currentTarget.style.color = 'var(--color-text-secondary)'
          }}
        >
          <ArrowDown size={13} strokeWidth={2.25} />
        </button>
      )}

      {/* 底部工具栏 + 输入区 */}
      <div
        className="flex-shrink-0 px-3 pb-3 pt-2"
        style={{ borderTop: '1px solid var(--color-border)' }}
      >
        <AgentToolbar />
        <AgentInputBox />
      </div>
    </div>
  )
}

// ===== Agent 底部工具栏（小说创作场景） =====

/**
 * 重构后的工具栏：贴合小说创作场景
 * 左侧：快速引用按钮（架构、角色、蓝图）
 * 右侧：打开 AI 输出面板按钮
 */
function AgentToolbar() {
  const openRightPanel = useLayoutStore(s => s.openRightPanel)

  return (
    <div className="flex items-center justify-end mb-1.5">

      {/* 右侧：打开 AI 输出面板 */}
      <button
        onClick={() => openRightPanel('ai-output')}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all select-none"
        style={{
          color: 'var(--color-text-muted)',
          border: '1px solid var(--color-border)',
        }}
        title="切换到 AI 输出面板"
        onMouseEnter={e => {
          e.currentTarget.style.backgroundColor = 'var(--color-hover)'
          e.currentTarget.style.color = 'var(--color-text)'
        }}
        onMouseLeave={e => {
          e.currentTarget.style.backgroundColor = 'transparent'
          e.currentTarget.style.color = 'var(--color-text-muted)'
        }}
      >
        <Workflow size={12} strokeWidth={1.75} />
        AI 工作流
      </button>
    </div>
  )
}

// ===== 历史面板 =====

function AgentHistoryPanel() {
  const { conversations, activeConversationId, selectConversation, deleteConversation, setShowHistory } = useAgentStore()

  // 按更新时间倒序排列
  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt)

  return (
    <div className="flex flex-col h-full">
      {/* 面板标题 */}
      <div
        className="flex items-center justify-between px-3 py-2 flex-shrink-0"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <span className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
          全部对话
        </span>
        <button
          onClick={() => setShowHistory(false)}
          className="text-xs px-2 py-0.5 rounded transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-hover)')}
          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
        >
          关闭
        </button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {sorted.length === 0 ? (
          <div className="flex items-center justify-center h-24 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            暂无对话记录
          </div>
        ) : (
          sorted.map(conv => (
            <RecentConversationItem
              key={conv.id}
              title={conv.title}
              updatedAt={conv.updatedAt}
              isActive={conv.id === activeConversationId}
              onClick={() => selectConversation(conv.id)}
              onDelete={() => deleteConversation(conv.id)}
            />
          ))
        )}
      </div>
    </div>
  )
}

// ===== 最近会话列表项 =====

function RecentConversationItem({
  title,
  updatedAt,
  isActive,
  onClick,
  onDelete,
}: {
  title: string
  updatedAt: number
  isActive?: boolean
  onClick: () => void
  onDelete: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="group w-full flex flex-row items-center justify-between overflow-hidden rounded py-1.5 text-left px-2 box-border transition-colors"
      style={{ backgroundColor: isActive ? 'var(--color-hover)' : 'transparent' }}
      onMouseEnter={e => { if (!isActive) e.currentTarget.style.backgroundColor = 'var(--color-hover)' }}
      onMouseLeave={e => { if (!isActive) e.currentTarget.style.backgroundColor = 'transparent' }}
    >
      {/* 标题 */}
      <div className="flex items-center gap-x-1 overflow-hidden flex-1 min-w-0">
        <div
          className="truncate text-xs"
          style={{ color: 'var(--color-text)', opacity: isActive ? 1 : 0.65 }}
        >
          {title}
        </div>
      </div>

      {/* 右侧：时间 or 删除（纯 CSS group-hover 控制） */}
      <div className="flex-shrink-0 ml-2">
        <button
          onClick={e => {
            e.stopPropagation()
            onDelete()
          }}
          className="hidden group-hover:flex items-center justify-center w-4 h-4 rounded opacity-50 hover:opacity-100 transition-opacity"
          style={{ color: 'var(--color-text-secondary)' }}
          title="删除对话"
        >
          <Trash2 size={12} />
        </button>
        <span
          className="group-hover:hidden text-[0.7rem] whitespace-nowrap"
          style={{ color: 'var(--color-text-muted)', opacity: 0.6 }}
        >
          {formatRelativeTime(updatedAt)}
        </span>
      </div>
    </button>
  )
}
