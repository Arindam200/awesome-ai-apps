import { useRef, useState, useEffect, useCallback } from 'react'
import {
  Plus,
  ChevronDown,
  ArrowRight,
  Square,
  Image,
  AtSign,
  Workflow,
} from 'lucide-react'
import { useAgentStore, type AgentMode } from '../../../stores/agent-store'
import { useLLMStore } from '../../../stores/llm-store'
import type { ModelProfile } from '../../../shared/ipc-channels'
import { useOutsideClick } from '../../../hooks/useOutsideClick'
import SlashCommandMenu from './SlashCommandMenu'
import MentionMenu from './MentionMenu'
import type { SlashCommand, MentionTarget } from '../../../services/agent/intent-router'

/** 输入框最大高度（px），超出后框内滚动 */
const MAX_HEIGHT = 200

/**
 * Agent 输入框组件（参考 agent1.html 第 69-155 行）
 * 卡片式圆角容器，底部工具栏含模式/模型/发送
 */
export default function AgentInputBox() {
  const [inputText, setInputText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { generating, sendMessage, cancelGeneration, getActiveConversation, setMode, setModelId } = useAgentStore()
  const models = useLLMStore(s => s.models)
  const defaultModelId = useLLMStore(s => s.defaultModelId)

  // 过滤出非仅限 embedding 专用的模型
  const chatModels = models.filter(m => !(m.purposes.length === 1 && m.purposes[0] === 'embedding'))

  const activeConv = getActiveConversation()
  const currentMode = activeConv?.mode ?? 'planning'
  const currentModelId = activeConv?.modelId ?? defaultModelId

  // 找到当前模型信息
  const currentModel = models.find(m => m.id === currentModelId)

  // 下拉菜单状态
  const [showContextMenu, setShowContextMenu] = useState(false)
  const [showModeMenu, setShowModeMenu] = useState(false)
  const [showModelMenu, setShowModelMenu] = useState(false)

  // / 命令和 @ 提及菜单状态
  const [showSlashMenu, setShowSlashMenu] = useState(false)
  const [slashQuery, setSlashQuery] = useState('')
  const [showMentionMenu, setShowMentionMenu] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')

  // 检测输入是否触发 / 或 @ 菜单
  const handleInputChange = useCallback((value: string) => {
    setInputText(value)

    // 检测 / 命令
    if (value.startsWith('/')) {
      const q = value.slice(1).split(' ')[0] ?? ''
      setSlashQuery(q)
      setShowSlashMenu(true)
      setShowMentionMenu(false)
    } else {
      setShowSlashMenu(false)
    }

    // 检测 @ 提及（在光标位置前面找 @）
    const lastAt = value.lastIndexOf('@')
    if (lastAt >= 0) {
      const afterAt = value.slice(lastAt + 1)
      // 如果 @ 后面没有空格，视为正在输入提及
      if (!afterAt.includes(' ')) {
        setMentionQuery(afterAt)
        setShowMentionMenu(true)
        setShowSlashMenu(false)
      } else {
        setShowMentionMenu(false)
      }
    } else {
      setShowMentionMenu(false)
    }
  }, [])

  // 选择 / 命令
  const handleSlashSelect = useCallback((cmd: SlashCommand) => {
    setShowSlashMenu(false)
    if (cmd.source === 'skill') {
      // Skill 命令：替换为 /skill-name 后面可以加参数
      setInputText(`/${cmd.name} `)
    } else {
      // 内置命令：直接发送
      setInputText('')
      sendMessage(`/${cmd.name}`)
    }
    textareaRef.current?.focus()
  }, [sendMessage])

  // 选择 @ 提及
  const handleMentionSelect = useCallback((target: MentionTarget) => {
    setShowMentionMenu(false)
    // 替换最后一个 @ 及其后面的文字为 @displayName
    const lastAt = inputText.lastIndexOf('@')
    if (lastAt >= 0) {
      const before = inputText.slice(0, lastAt)
      setInputText(`${before}@${target.displayName} `)
    }
    textareaRef.current?.focus()
  }, [inputText])

  const contextRef = useRef<HTMLDivElement>(null)
  const modeRef = useRef<HTMLDivElement>(null)
  const modelRef = useRef<HTMLDivElement>(null)

  // 调整文本框高度的通用函数
  const adjustHeight = useCallback(() => {
    const ta = textareaRef.current
    if (!ta) return
    // 先重置为 0px，让 scrollHeight 正确反映内容高度，避免 flex 布局拉伸导致计算出很大的初始高度
    ta.style.height = '0px'
    const next = Math.min(Math.max(ta.scrollHeight, 36), MAX_HEIGHT)
    ta.style.height = next + 'px'
    // 超出最大高度时框内滚动，否则隐藏滚动条
    ta.style.overflowY = ta.scrollHeight > MAX_HEIGHT ? 'auto' : 'hidden'
  }, [])

  // 监听尺寸变化以重新计算高度，避免刚挂载时宽度未稳定导致的 placeholder 异常换行撑起高度
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) {
      adjustHeight()
      return
    }
    const ro = new ResizeObserver(() => {
      adjustHeight()
    })
    ro.observe(ta)

    // 初始化调用一次即可
    adjustHeight()

    return () => ro.disconnect()
  }, [adjustHeight])

  // 内容变化时重新调整高度
  useEffect(() => {
    adjustHeight()
  }, [inputText, adjustHeight])

  // 点击外部关闭下拉（用 useOutsideClick 统一管理三个 ref）
  useOutsideClick(contextRef, () => setShowContextMenu(false), showContextMenu)
  useOutsideClick(modeRef, () => setShowModeMenu(false), showModeMenu)
  useOutsideClick(modelRef, () => setShowModelMenu(false), showModelMenu)

  /** 发送或停止 */
  const handleSendOrStop = useCallback(async () => {
    if (generating) {
      await cancelGeneration()
      return
    }
    if (!inputText.trim()) return
    const text = inputText
    setInputText('')
    await sendMessage(text)
  }, [generating, inputText, sendMessage, cancelGeneration])

  /** 键盘事件：Enter 发送，Shift+Enter 换行 */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // / 或 @ 菜单打开时，由菜单组件处理键盘事件
    if (showSlashMenu || showMentionMenu) {
      if (['ArrowUp', 'ArrowDown', 'Enter'].includes(e.key)) {
        return // 让菜单组件通过 window 事件处理
      }
      if (e.key === 'Escape') {
        setShowSlashMenu(false)
        setShowMentionMenu(false)
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendOrStop()
    }
  }

  const canSend = !generating && inputText.trim().length > 0

  return (
    <div
      className="relative flex flex-col gap-0 p-1.5"
      style={{
        backgroundColor: 'var(--color-hover)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',  /* 4px 方正风格 */
      }}
    >
      {/* / 命令菜单 */}
      {showSlashMenu && (
        <SlashCommandMenu
          query={slashQuery}
          onSelect={handleSlashSelect}
          onClose={() => setShowSlashMenu(false)}
        />
      )}

      {/* @ 提及菜单 */}
      {showMentionMenu && (
        <MentionMenu
          query={mentionQuery}
          onSelect={handleMentionSelect}
          onClose={() => setShowMentionMenu(false)}
        />
      )}

      {/* 上下文菜单（+ 按钮弹出） */}
      {showContextMenu && (
        <div
          className="absolute bottom-[calc(100%+8px)] left-0 z-50 py-1 rounded-lg shadow-lg"
          style={{
            width: 180,
            backgroundColor: 'var(--color-sidebar)',
            border: '1px solid var(--color-border)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
          }}
        >
          <div className="text-[0.7rem] px-3 pb-1 pt-1" style={{ color: 'var(--color-text-muted)' }}>
            添加上下文
          </div>
          <ContextMenuItem icon={<Image size={13} />} label="媒体文件" onClick={() => setShowContextMenu(false)} disabled />
          <ContextMenuItem icon={<AtSign size={13} />} label="@提及" onClick={() => {
            setShowContextMenu(false)
            // 插入 @ 字符并触发 MentionMenu
            setInputText(prev => prev + '@')
            handleInputChange(inputText + '@')
            textareaRef.current?.focus()
          }} />
          <ContextMenuItem icon={<Workflow size={13} />} label="工作流命令" onClick={() => {
            setShowContextMenu(false)
            // 插入 / 字符并触发 SlashCommandMenu
            setInputText('/')
            handleInputChange('/')
            textareaRef.current?.focus()
          }} />
        </div>
      )}

      {/* 输入区域 */}
      <div className="relative w-full">
          <textarea
            ref={textareaRef}
            value={inputText}
            onChange={e => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息，@ 提及，/ 使用工作流..."
            rows={1}
            className="w-full resize-none outline-none bg-transparent text-xs leading-relaxed px-2 py-2"
            style={{
              color: 'var(--color-text)',
              minHeight: 36,
              maxHeight: MAX_HEIGHT,
              overflowY: 'hidden',
              display: 'block',
            }}
          />
        {/* 占位文字颜色已通过 tailwind placeholder 设置 */}
      </div>

      {/* 底部工具栏 */}
      <div className="flex items-center justify-between gap-1 px-1 mt-0.5">

        {/* 左侧工具按钮组 */}
        <div className="flex items-center gap-0.5 min-w-0 flex-1">

          {/* + 添加上下文 */}
          <div ref={contextRef}>
            <ToolbarIconBtn
              title="添加上下文"
              onClick={() => {
                setShowModeMenu(false)
                setShowModelMenu(false)
                setShowContextMenu(v => !v)
              }}
            >
              <Plus size={14} />
            </ToolbarIconBtn>
          </div>

          {/* 模式选择 */}
          <div ref={modeRef} className="relative">
            <button
              onClick={() => {
                setShowContextMenu(false)
                setShowModelMenu(false)
                setShowModeMenu(v => !v)
              }}
              className="flex items-center gap-0.5 py-1 pl-1 pr-1.5 rounded-md text-xs transition-colors"
              style={{
                color: 'var(--color-text-secondary)',
                opacity: 0.75,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.backgroundColor = 'var(--color-hover)'
                e.currentTarget.style.opacity = '1'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.backgroundColor = 'transparent'
                e.currentTarget.style.opacity = '0.75'
              }}
            >
              <ChevronDown size={13} strokeWidth={1.5} />
              <span className="select-none">{currentMode === 'planning' ? '深度' : '快速'}</span>
            </button>

            {/* 模式选择下拉 */}
            {showModeMenu && (
              <div
                className="absolute bottom-full left-0 mb-1 z-50 py-1 rounded-lg shadow-lg"
                style={{
                  width: 240,
                  backgroundColor: 'var(--color-sidebar)',
                  border: '1px solid var(--color-border)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
                }}
              >
                <div className="text-[0.7rem] px-3 py-1" style={{ color: 'var(--color-text-muted)' }}>
                  对话模式
                </div>
                <ModeMenuItem
                  mode="planning"
                  currentMode={currentMode}
                  label="深度模式"
                  desc="先规划后执行，适合深度研究、复杂任务和协同创作"
                  onClick={() => { setMode('planning'); setShowModeMenu(false) }}
                />
                <ModeMenuItem
                  mode="fast"
                  currentMode={currentMode}
                  label="快速模式"
                  desc="直接执行，适合简单快速任务"
                  onClick={() => { setMode('fast'); setShowModeMenu(false) }}
                />
              </div>
            )}
          </div>

          {/* 模型选择 */}
          <div ref={modelRef} className="relative min-w-0">
            <button
              onClick={() => {
                setShowContextMenu(false)
                setShowModeMenu(false)
                setShowModelMenu(v => !v)
              }}
              className="flex items-center gap-0.5 py-1 pl-0.5 pr-1.5 rounded-md text-xs min-w-0 transition-colors"
              style={{
                color: 'var(--color-text-secondary)',
                opacity: 0.75,
                maxWidth: 140,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.backgroundColor = 'var(--color-hover)'
                e.currentTarget.style.opacity = '1'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.backgroundColor = 'transparent'
                e.currentTarget.style.opacity = '0.75'
              }}
            >
              <ChevronDown size={13} strokeWidth={1.5} className="flex-shrink-0" />
              <span className="truncate select-none">
                {currentModel?.name ?? (chatModels.length === 0 ? '未配置模型' : '选择模型')}
              </span>
            </button>

            {/* 模型选择下拉 */}
            {showModelMenu && (
              <div
                className="absolute bottom-full left-0 mb-1 z-50 py-1 rounded-lg shadow-lg"
                style={{
                  width: 220,
                  backgroundColor: 'var(--color-sidebar)',
                  border: '1px solid var(--color-border)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
                  maxHeight: 280,
                  overflowY: 'auto',
                }}
              >
                <div className="text-[0.7rem] px-3 py-1" style={{ color: 'var(--color-text-muted)' }}>
                  选择模型
                </div>
                {chatModels.length === 0 ? (
                  <div className="px-3 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    请先在设置中配置模型
                  </div>
                ) : (
                  chatModels.map(model => (
                    <ModelMenuItem
                      key={model.id}
                      model={model}
                      isActive={model.id === currentModelId}
                      onClick={() => {
                        setModelId(model.id)
                        setShowModelMenu(false)
                      }}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* 右侧：发送/停止 */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={handleSendOrStop}
            disabled={!generating && !canSend}
            className="flex items-center justify-center w-6 h-6 transition-all duration-150"
            style={{
              borderRadius: 'var(--radius-md)',
              backgroundColor: generating
                ? 'var(--color-text-secondary)'
                : canSend
                ? 'var(--color-accent)'
                : 'rgba(128,128,128,0.3)',
              color: '#ffffff',
              cursor: !generating && !canSend ? 'not-allowed' : 'pointer',
              opacity: !generating && !canSend ? 0.5 : 1,
            }}
            title={generating ? '停止生成' : '发送消息'}
          >
            {generating ? (
              <Square size={10} fill="currentColor" />
            ) : (
              <ArrowRight size={13} strokeWidth={2.5} />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ===== 子组件 =====

/** 工具栏图标按钮 */
function ToolbarIconBtn({
  children,
  title,
  onClick,
}: {
  children: React.ReactNode
  title: string
  onClick?: () => void
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className="flex items-center justify-center p-1 rounded-full transition-colors"
      style={{ color: 'var(--color-text-secondary)', opacity: 0.75 }}
      onMouseEnter={e => {
        e.currentTarget.style.backgroundColor = 'var(--color-hover)'
        e.currentTarget.style.opacity = '1'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.backgroundColor = 'transparent'
        e.currentTarget.style.opacity = '0.75'
      }}
    >
      {children}
    </button>
  )
}

/** 上下文菜单项 */
function ContextMenuItem({
  icon,
  label,
  onClick,
  disabled,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      onClick={!disabled ? onClick : undefined}
      disabled={disabled}
      className="w-full flex items-center gap-2 px-3 py-1.5 text-xs transition-colors"
      style={{
        color: disabled ? 'var(--color-text-muted)' : 'var(--color-text)',
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
      onMouseEnter={e => {
        if (!disabled) e.currentTarget.style.backgroundColor = 'var(--color-hover)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.backgroundColor = 'transparent'
      }}
    >
      <span style={{ color: 'var(--color-text-secondary)' }}>{icon}</span>
      {label}
      {disabled && <span className="ml-auto text-[0.7rem] opacity-40">即将</span>}
    </button>
  )
}

/** 模式菜单项 */
function ModeMenuItem({
  mode,
  currentMode,
  label,
  desc,
  onClick,
}: {
  mode: AgentMode
  currentMode: AgentMode
  label: string
  desc: string
  onClick: () => void
}) {
  const isActive = mode === currentMode

  return (
    <button
      onClick={onClick}
      className="w-full flex flex-col items-start gap-0.5 px-3 py-2 text-left text-xs transition-colors rounded-md mx-1"
      style={{
        width: 'calc(100% - 8px)',
        backgroundColor: isActive ? 'var(--color-hover)' : 'transparent',
      }}
      onMouseEnter={e => {
        if (!isActive) e.currentTarget.style.backgroundColor = 'var(--color-hover)'
      }}
      onMouseLeave={e => {
        if (!isActive) e.currentTarget.style.backgroundColor = 'transparent'
      }}
    >
      <div className="font-medium" style={{ color: 'var(--color-text)' }}>{label}</div>
      <div className="text-left leading-relaxed" style={{ color: 'var(--color-text-muted)', fontSize: "0.75rem" }}>{desc}</div>
    </button>
  )
}

/** 模型菜单项 */
function ModelMenuItem({
  model,
  isActive,
  onClick,
}: {
  model: ModelProfile
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between px-3 py-1.5 text-xs transition-colors"
      style={{
        backgroundColor: isActive ? 'var(--color-hover)' : 'transparent',
      }}
      onMouseEnter={e => {
        if (!isActive) e.currentTarget.style.backgroundColor = 'var(--color-hover)'
      }}
      onMouseLeave={e => {
        if (!isActive) e.currentTarget.style.backgroundColor = 'transparent'
      }}
    >
      <span
        className="font-medium truncate"
        style={{ color: 'var(--color-text)' }}
      >
        {model.name}
      </span>
      {model.provider && (
        <span
          className="ml-2 text-[0.7rem] px-1.5 py-0.5 rounded-full flex-shrink-0"
          style={{
            backgroundColor: 'var(--color-border)',
            color: 'var(--color-text-muted)',
          }}
        >
          {model.provider}
        </span>
      )}
    </button>
  )
}
