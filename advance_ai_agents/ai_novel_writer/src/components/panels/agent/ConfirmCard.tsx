/**
 * ConfirmCard — 操作确认卡片
 *
 * 当 Agent 调用需要确认的 Tool 时显示此卡片。
 * 用户可以批准或拒绝操作。
 */
import { ShieldAlert } from 'lucide-react'
import type { ToolCallInfo } from '../../../services/agent/agent-engine'
import { useAgentStore } from '../../../stores/agent-store'

interface Props {
  toolCall: ToolCallInfo
}

export default function ConfirmCard({ toolCall }: Props) {
  const { resolveToolConfirmation } = useAgentStore()
  const { id, toolName, arguments: args } = toolCall

  // 生成操作描述
  const description = generateDescription(toolName, args)

  return (
    <div className="confirm-card">
      {/* 头部 */}
      <div className="confirm-card-header">
        <ShieldAlert size={14} />
        <span>需要确认操作</span>
      </div>

      {/* 内容 */}
      <div className="confirm-card-body">
        <div>{description}</div>
        {Object.keys(args).length > 0 && (
          <div
            style={{
              marginTop: 6,
              padding: '4px 8px',
              borderRadius: 4,
              backgroundColor: 'var(--color-hover)',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '0.68rem',
              color: 'var(--color-text-secondary)',
              whiteSpace: 'pre-wrap',
              maxHeight: 120,
              overflowY: 'auto',
            }}
          >
            {JSON.stringify(args, null, 2)}
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="confirm-card-actions">
        <button
          className="confirm-card-btn reject"
          onClick={() => resolveToolConfirmation(id, false)}
        >
          拒绝
        </button>
        <button
          className="confirm-card-btn approve"
          onClick={() => resolveToolConfirmation(id, true)}
        >
          批准执行
        </button>
      </div>
    </div>
  )
}

/** 根据 Tool 名称生成人类可读的操作描述 */
function generateDescription(toolName: string, args: Record<string, unknown>): string {
  switch (toolName) {
    case 'write_file':
      return `将写入文件：${args.file_path ?? '未知路径'}`
    case 'open_editor':
      return `将在编辑器中打开：${args.file_path ?? '未知文件'}`
    case 'start_workflow':
      return `将启动工作流：${args.workflow ?? '未知工作流'}${args.chapter_number ? `（第 ${args.chapter_number} 章）` : ''}`
    case 'update_config':
      return `将更新项目配置：${args.field ?? '未知字段'}`
    default:
      return `将执行操作：${toolName}`
  }
}
