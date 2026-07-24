/**
 * MCP（Model Context Protocol）连接管理器
 *
 * 运行在 Electron 主进程，通过 stdio/SSE 管理与外部 MCP Server 的连接。
 * 兼容 Claude Desktop 的配置格式 (claude_desktop_config.json)。
 *
 * 架构：
 * - 主进程负责 MCP 连接的生命周期（启动子进程 / 建立 SSE）
 * - 通过 IPC 将可用 Tool 列表暴露给渲染进程
 * - 渲染进程通过 IPC 调用 MCP Tool
 */

import { spawn, type ChildProcess } from 'child_process'
import { readFile } from 'fs/promises'
import { join } from 'path'
import { app } from 'electron'

// ===== 类型定义 =====

/** MCP 服务器配置（兼容 Claude Desktop 格式） */
export interface MCPServerConfig {
  /** 服务器唯一 ID */
  id: string
  /** 显示名称 */
  name: string
  /** 传输协议 */
  transport: 'stdio' | 'sse'
  /** stdio 模式：要执行的命令 */
  command?: string
  /** stdio 模式：命令参数 */
  args?: string[]
  /** stdio 模式：环境变量 */
  env?: Record<string, string>
  /** SSE 模式：服务器 URL */
  url?: string
}

/** MCP 配置文件格式（兼容 Claude Desktop） */
export interface MCPConfig {
  mcpServers: Record<string, {
    command?: string
    args?: string[]
    env?: Record<string, string>
    url?: string
  }>
}

/** MCP Tool 描述 */
export interface MCPToolDesc {
  /** 工具名（MCP 原始名称） */
  name: string
  /** 描述 */
  description: string
  /** 输入 JSON Schema */
  inputSchema: Record<string, unknown>
  /** 所属服务器 ID */
  serverId: string
}

/** MCP 资源描述 */
export interface MCPResourceDesc {
  uri: string
  name: string
  description?: string
  mimeType?: string
  serverId: string
}

/** 服务器连接状态 */
export type MCPConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

/** 服务器运行时状态 */
interface MCPServerRuntime {
  config: MCPServerConfig
  status: MCPConnectionStatus
  process?: ChildProcess
  tools: MCPToolDesc[]
  resources: MCPResourceDesc[]
  error?: string
  /** 消息缓冲区（用于解析 JSON-RPC） */
  buffer: string
  /** 请求 ID 计数器 */
  nextRequestId: number
  /** 待响应的请求回调 */
  pendingRequests: Map<number, {
    resolve: (result: unknown) => void
    reject: (error: Error) => void
  }>
}

// ===== MCP Manager 实现 =====

class MCPManagerImpl {
  private servers: Map<string, MCPServerRuntime> = new Map()

  /** 状态变更通知回调（通知渲染进程） */
  private onStatusChange?: (serverId: string, status: MCPConnectionStatus, error?: string) => void
  /** Tool 列表变更回调 */
  private onToolsChange?: (tools: MCPToolDesc[]) => void

  /** 设置状态变更回调 */
  setCallbacks(callbacks: {
    onStatusChange?: (serverId: string, status: MCPConnectionStatus, error?: string) => void
    onToolsChange?: (tools: MCPToolDesc[]) => void
  }) {
    this.onStatusChange = callbacks.onStatusChange
    this.onToolsChange = callbacks.onToolsChange
  }

  /** 获取 MCP 配置文件默认路径 */
  getDefaultConfigPath(): string {
    return join(app.getPath('home'), '.vela', 'mcp_config.json')
  }

  /**
   * 加载 MCP 配置文件
   * 兼容 Claude Desktop 格式
   */
  async loadConfig(configPath?: string): Promise<MCPServerConfig[]> {
    const path = configPath ?? this.getDefaultConfigPath()


    try {
      const raw = await readFile(path, 'utf-8')
      const config: MCPConfig = JSON.parse(raw)

      if (!config.mcpServers || typeof config.mcpServers !== 'object') {
        return []
      }

      return Object.entries(config.mcpServers).map(([id, cfg]) => ({
        id,
        name: id,
        transport: cfg.url ? 'sse' as const : 'stdio' as const,
        command: cfg.command,
        args: cfg.args,
        env: cfg.env,
        url: cfg.url,
      }))
    } catch {
      // 配置文件不存在或格式错误，静默处理
      return []
    }
  }

  /**
   * 连接到 MCP 服务器
   */
  async connect(config: MCPServerConfig): Promise<void> {
    if (this.servers.has(config.id)) {
      await this.disconnect(config.id)
    }

    const runtime: MCPServerRuntime = {
      config,
      status: 'connecting',
      tools: [],
      resources: [],
      buffer: '',
      nextRequestId: 1,
      pendingRequests: new Map(),
    }
    this.servers.set(config.id, runtime)
    this.notifyStatusChange(config.id, 'connecting')

    try {
      if (config.transport === 'stdio') {
        await this.connectStdio(runtime)
      } else {
        // SSE 暂时跳过，标记为错误
        runtime.status = 'error'
        runtime.error = 'SSE 传输暂未实现'
        this.notifyStatusChange(config.id, 'error', runtime.error)
        return
      }

      // 初始化 MCP 会话
      await this.initializeSession(runtime)

      // 发现工具
      await this.discoverTools(runtime)

      // 发现资源
      await this.discoverResources(runtime)

      runtime.status = 'connected'
      this.notifyStatusChange(config.id, 'connected')
      this.notifyToolsChange()
    } catch (error) {
      runtime.status = 'error'
      runtime.error = String(error)
      this.notifyStatusChange(config.id, 'error', runtime.error)
    }
  }

  /** stdio 模式连接 */
  private async connectStdio(runtime: MCPServerRuntime): Promise<void> {
    const { command, args = [], env } = runtime.config
    if (!command) {
      throw new Error('stdio 模式需要 command 参数')
    }

    const proc = spawn(command, args, {
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe'],
    })

    runtime.process = proc

    // 监听 stdout（JSON-RPC 消息）
    proc.stdout?.on('data', (data: Buffer) => {
      runtime.buffer += data.toString()
      this.processBuffer(runtime)
    })

    // 监听 stderr（调试日志）
    proc.stderr?.on('data', (data: Buffer) => {
      console.warn(`[MCP:${runtime.config.id}] stderr:`, data.toString())
    })

    // 监听进程退出
    proc.on('exit', (code) => {
      console.log(`[MCP:${runtime.config.id}] 进程退出，code=${code}`)
      runtime.status = 'disconnected'
      this.notifyStatusChange(runtime.config.id, 'disconnected')
    })

    proc.on('error', (error) => {
      runtime.status = 'error'
      runtime.error = `进程启动失败：${error.message}`
      this.notifyStatusChange(runtime.config.id, 'error', runtime.error)
    })
  }

  /** 处理 JSON-RPC 消息缓冲区 */
  private processBuffer(runtime: MCPServerRuntime): void {
    // MCP 使用 \n 分隔的 JSON-RPC 消息
    const lines = runtime.buffer.split('\n')
    runtime.buffer = lines.pop() ?? '' // 保留最后一行（可能不完整）

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue

      try {
        const msg = JSON.parse(trimmed)
        this.handleMessage(runtime, msg)
      } catch {
        // 非 JSON 行，忽略
      }
    }
  }

  /** 处理收到的 JSON-RPC 消息 */
  private handleMessage(runtime: MCPServerRuntime, msg: Record<string, unknown>): void {
    // 响应消息（有 id）
    if ('id' in msg && msg.id != null) {
      const pending = runtime.pendingRequests.get(msg.id as number)
      if (pending) {
        runtime.pendingRequests.delete(msg.id as number)
        if ('error' in msg) {
          const err = msg.error as { message?: string }
          pending.reject(new Error(err?.message ?? 'MCP error'))
        } else {
          pending.resolve(msg.result)
        }
      }
    }
    // 通知消息（无 id）— 暂时只记录日志
  }

  /** 发送 JSON-RPC 请求 */
  private sendRequest(runtime: MCPServerRuntime, method: string, params?: unknown): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const id = runtime.nextRequestId++
      runtime.pendingRequests.set(id, { resolve, reject })

      const msg = JSON.stringify({
        jsonrpc: '2.0',
        id,
        method,
        params: params ?? {},
      })

      runtime.process?.stdin?.write(msg + '\n')

      // 超时 10 秒
      setTimeout(() => {
        if (runtime.pendingRequests.has(id)) {
          runtime.pendingRequests.delete(id)
          reject(new Error(`MCP 请求超时: ${method}`))
        }
      }, 10000)
    })
  }

  /** 初始化 MCP 会话 */
  private async initializeSession(runtime: MCPServerRuntime): Promise<void> {
    await this.sendRequest(runtime, 'initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: {
        name: 'vela',
        version: '1.0.0',
      },
    })

    // 发送 initialized 通知
    const msg = JSON.stringify({
      jsonrpc: '2.0',
      method: 'notifications/initialized',
    })
    runtime.process?.stdin?.write(msg + '\n')
  }

  /** 发现可用工具 */
  private async discoverTools(runtime: MCPServerRuntime): Promise<void> {
    try {
      const result = await this.sendRequest(runtime, 'tools/list') as { tools?: MCPToolDesc[] }
      runtime.tools = (result?.tools ?? []).map(t => ({
        ...t,
        serverId: runtime.config.id,
      }))
    } catch {
      runtime.tools = []
    }
  }

  /** 发现可用资源 */
  private async discoverResources(runtime: MCPServerRuntime): Promise<void> {
    try {
      const result = await this.sendRequest(runtime, 'resources/list') as { resources?: MCPResourceDesc[] }
      runtime.resources = (result?.resources ?? []).map(r => ({
        ...r,
        serverId: runtime.config.id,
      }))
    } catch {
      runtime.resources = []
    }
  }

  /**
   * 调用 MCP Tool
   */
  async callTool(serverId: string, toolName: string, args: Record<string, unknown>): Promise<{
    success: boolean
    content: string
    error?: string
  }> {
    const runtime = this.servers.get(serverId)
    if (!runtime || runtime.status !== 'connected') {
      return { success: false, content: '', error: `服务器 ${serverId} 未连接` }
    }

    try {
      const result = await this.sendRequest(runtime, 'tools/call', {
        name: toolName,
        arguments: args,
      }) as { content?: Array<{ type: string; text?: string }> }

      const textParts = (result?.content ?? [])
        .filter(c => c.type === 'text')
        .map(c => c.text ?? '')
        .join('\n')

      return { success: true, content: textParts }
    } catch (error) {
      return { success: false, content: '', error: String(error) }
    }
  }

  /** 断开服务器连接 */
  async disconnect(serverId: string): Promise<void> {
    const runtime = this.servers.get(serverId)
    if (!runtime) return

    runtime.process?.kill()
    runtime.pendingRequests.forEach(p => p.reject(new Error('连接已断开')))
    runtime.pendingRequests.clear()
    this.servers.delete(serverId)
    this.notifyStatusChange(serverId, 'disconnected')
    this.notifyToolsChange()
  }

  /** 断开所有连接 */
  async disconnectAll(): Promise<void> {
    for (const id of this.servers.keys()) {
      await this.disconnect(id)
    }
  }

  /** 获取所有 MCP Tool */
  getAllTools(): MCPToolDesc[] {
    const tools: MCPToolDesc[] = []
    for (const runtime of this.servers.values()) {
      if (runtime.status === 'connected') {
        tools.push(...runtime.tools)
      }
    }
    return tools
  }

  /** 获取所有 MCP 资源 */
  getAllResources(): MCPResourceDesc[] {
    const resources: MCPResourceDesc[] = []
    for (const runtime of this.servers.values()) {
      if (runtime.status === 'connected') {
        resources.push(...runtime.resources)
      }
    }
    return resources
  }

  /** 获取所有服务器状态 */
  getServersStatus(): Array<{
    id: string
    name: string
    status: MCPConnectionStatus
    toolCount: number
    error?: string
  }> {
    return Array.from(this.servers.values()).map(r => ({
      id: r.config.id,
      name: r.config.name,
      status: r.status,
      toolCount: r.tools.length,
      error: r.error,
    }))
  }

  private notifyStatusChange(serverId: string, status: MCPConnectionStatus, error?: string) {
    this.onStatusChange?.(serverId, status, error)
  }

  private notifyToolsChange() {
    this.onToolsChange?.(this.getAllTools())
  }
}

/** 全局单例 MCP Manager */
export const mcpManager = new MCPManagerImpl()
