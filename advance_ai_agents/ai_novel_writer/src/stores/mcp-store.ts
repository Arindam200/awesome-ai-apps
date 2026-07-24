/**
 * MCP Store — 前端 MCP 状态管理
 *
 * 管理 MCP 服务器的连接状态、可用 Tool 列表、配置加载等。
 * 通过 IPC 与主进程的 mcpManager 通信。
 */

import { create } from 'zustand'
import { ipc } from '../services/ipc-client'
import { toolRegistry } from '../services/agent/tool-registry'
import type {
  MCPServerConfig,
  MCPConnectionStatus,
  MCPToolDesc,
  MCPResourceDesc,
} from '../../electron/mcp/mcp-manager'

interface MCPServerStatus {
  id: string
  name: string
  status: MCPConnectionStatus
  toolCount: number
  error?: string
}

type MCPServerConfigData = MCPServerConfig
type MCPToolData = MCPToolDesc
type MCPResourceData = MCPResourceDesc
import type { AgentTool } from '../services/agent/tool-registry'

// ===== Store 状态 =====

interface MCPState {
  /** 服务器状态列表 */
  servers: MCPServerStatus[]
  /** 所有 MCP Tool */
  tools: MCPToolData[]
  /** 所有 MCP 资源 */
  resources: MCPResourceData[]
  /** 配置文件路径 */
  configPath: string | null
  /** 加载中 */
  loading: boolean
  /** 错误 */
  error: string | null

  // ===== Actions =====
  /** 初始化（加载配置 + 自动连接） */
  init: () => Promise<void>
  /** 刷新服务器状态 */
  refreshStatus: () => Promise<void>
  /** 连接单个服务器 */
  connectServer: (config: MCPServerConfigData) => Promise<void>
  /** 断开单个服务器 */
  disconnectServer: (serverId: string) => Promise<void>
  /** 断开所有服务器 */
  disconnectAll: () => Promise<void>
  /** 刷新 Tool 列表 */
  refreshTools: () => Promise<void>
  /** 将 MCP Tool 注册到 ToolRegistry */
  registerMCPToolsToRegistry: () => void
}

export const useMCPStore = create<MCPState>()((set, get) => ({
  servers: [],
  tools: [],
  resources: [],
  configPath: null,
  loading: false,
  error: null,

  init: async () => {
    set({ loading: true, error: null })
    try {
      // 获取配置文件路径
      const configPath = await ipc.invoke('mcp:get-config-path')
      set({ configPath })

      // 加载配置
      const result = await ipc.invoke('mcp:load-config')
      if (!result.success) {
        set({ loading: false })
        return // 配置文件不存在不是错误
      }

      // 自动连接所有配置的服务器
      for (const config of result.configs as Array<Record<string, unknown>>) {
        try {
          await ipc.invoke('mcp:connect', config)
        } catch (e) {
          console.warn(`[MCP] 连接 ${config.id} 失败:`, e)
        }
      }

      // 刷新状态
      await get().refreshStatus()
      await get().refreshTools()

      // 注册到 ToolRegistry
      get().registerMCPToolsToRegistry()

      set({ loading: false })
    } catch (error) {
      set({ loading: false, error: String(error) })
    }
  },

  refreshStatus: async () => {
    try {
      const servers = await ipc.invoke('mcp:get-servers-status')
      set({ servers: servers as unknown as MCPServerStatus[] })
    } catch (error) {
      console.error('[MCP] 刷新状态失败:', error)
    }
  },

  connectServer: async (config) => {
    const result = await ipc.invoke('mcp:connect', config as unknown as Record<string, unknown>)
    if (!result.success) {
      set({ error: result.error ?? '连接失败' })
      return
    }
    await get().refreshStatus()
    await get().refreshTools()
    get().registerMCPToolsToRegistry()
  },

  disconnectServer: async (serverId) => {
    await ipc.invoke('mcp:disconnect', serverId)
    // 从 ToolRegistry 注销该服务器的 Tool
    toolRegistry.unregisterBySource('mcp')
    await get().refreshStatus()
    await get().refreshTools()
    get().registerMCPToolsToRegistry()
  },

  disconnectAll: async () => {
    await ipc.invoke('mcp:disconnect-all')
    toolRegistry.unregisterBySource('mcp')
    set({ servers: [], tools: [], resources: [] })
  },

  refreshTools: async () => {
    try {
      const tools = await ipc.invoke('mcp:list-tools') as unknown[]
      const resources = await ipc.invoke('mcp:list-resources') as unknown[]
      set({ tools: tools as MCPToolData[], resources: resources as MCPResourceData[] })
    } catch {
      // 静默处理
    }
  },

  registerMCPToolsToRegistry: () => {
    const { tools } = get()

    // 先清理旧的 MCP Tool
    toolRegistry.unregisterBySource('mcp')

    // 将每个 MCP Tool 注册为 AgentTool
    for (const mcpTool of tools) {
      const agentTool: AgentTool = {
        name: `mcp__${mcpTool.serverId}__${mcpTool.name}`,
        description: mcpTool.description || `MCP Tool: ${mcpTool.name}`,
        source: 'mcp',
        inputSchema: {
          type: 'object',
          properties: (mcpTool.inputSchema as { properties?: Record<string, unknown> })?.properties as Record<string, { type: string; description: string }> ?? {},
          required: (mcpTool.inputSchema as { required?: string[] })?.required,
        },
        requiresConfirmation: true, // MCP Tool 默认需要确认（保守策略）
        isReadOnly: false,
        userFacingName: `${mcpTool.name} (${mcpTool.serverId})`,
        execute: async (args) => {
          const result = await ipc.invoke('mcp:call-tool', mcpTool.serverId, mcpTool.name, args)
          return {
            success: result.success,
            content: result.content,
            error: result.error,
          }
        },
      }
      toolRegistry.register(agentTool)
    }

    if (tools.length > 0) {
      console.log(`[MCP] 已注册 ${tools.length} 个 MCP Tool 到 ToolRegistry`)
    }
  },
}))
