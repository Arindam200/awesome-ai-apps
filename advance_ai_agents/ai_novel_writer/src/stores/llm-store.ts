import { create } from 'zustand'
import { ipc } from '../services/ipc-client'
import type { ModelProfile, LLMResponse, TokenUsage } from '../shared/ipc-channels'

/** 流式生成的回调 */
interface StreamCallbacks {
  onChunk?: (chunk: string) => void
  onDone?: (fullText: string, usage?: TokenUsage) => void
  onError?: (error: string) => void
}

interface LLMState {
  /** 已配置的模型列表 */
  models: ModelProfile[]
  /** 当前默认生成模型 ID */
  defaultModelId: string | null
  /** 当前默认向量模型 ID */
  defaultEmbeddingModelId: string | null
  /** 正在进行的活跃请求 */
  activeRequests: Map<string, { status: 'running' | 'done' | 'error'; text: string }>
  /** 是否已加载模型配置 */
  loaded: boolean

  // ===== Actions =====
  /** 初始化（加载模型列表 + 默认模型 ID） */
  init: () => Promise<void>
  /** 加载模型列表 */
  loadModels: () => Promise<void>
  /** 保存模型 */
  saveModel: (model: ModelProfile) => Promise<boolean>
  /** 删除模型 */
  deleteModel: (modelId: string) => Promise<boolean>
  /** 设置默认生成模型（持久化到 ~/.vela/config.json） */
  setDefaultModel: (modelId: string) => void
  /** 设置默认向量模型（持久化到 ~/.vela/config.json） */
  setDefaultEmbeddingModel: (modelId: string) => void
  /** 非流式生成 */
  generate: (
    messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>,
    modelId?: string,
    options?: { responseFormat?: { type: string }; thinking?: boolean; maxTokens?: number; temperature?: number }
  ) => Promise<LLMResponse>
  /** 流式生成 */
  generateStream: (
    messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>,
    callbacks: StreamCallbacks,
    modelId?: string,
    options?: { responseFormat?: { type: string }; thinking?: boolean; maxTokens?: number; temperature?: number }
  ) => Promise<string>
  /** 取消生成 */
  cancelGeneration: (requestId: string) => Promise<void>
  /** 测试模型连接 */
  testConnection: (model: ModelProfile) => Promise<{ success: boolean; error?: string }>
}

export const useLLMStore = create<LLMState>()((set, get) => ({
  models: [],
  defaultModelId: null,
  defaultEmbeddingModelId: null,
  activeRequests: new Map(),
  loaded: false,

  init: async () => {
    if (get().loaded) return
    // 从 ~/.vela/ 加载模型列表和默认模型 ID
    await get().loadModels()
    if (ipc.isElectron) {
      const [defaultId, defaultEmbeddingId] = await Promise.all([
        ipc.invoke('llm:get-default-model'),
        ipc.invoke('llm:get-default-embedding-model'),
      ])
      set({ defaultModelId: defaultId, defaultEmbeddingModelId: defaultEmbeddingId, loaded: true })
    } else {
      set({ loaded: true })
    }
  },

  loadModels: async () => {
    if (!ipc.isElectron) return
    const models = await ipc.invoke('llm:list-models')
    set({ models, loaded: true })
  },

  saveModel: async (model) => {
    const result = await ipc.invoke('llm:save-model', model)
    if (result.success) {
      await get().loadModels()
    }
    return result.success
  },

  deleteModel: async (modelId) => {
    const result = await ipc.invoke('llm:delete-model', modelId)
    if (result.success) {
      await get().loadModels()
      // 如果删除的是默认生成模型，清空默认
      if (get().defaultModelId === modelId) {
        set({ defaultModelId: null })
        ipc.invoke('llm:set-default-model', null)
      }
      // 如果删除的是默认向量模型，清空默认
      if (get().defaultEmbeddingModelId === modelId) {
        set({ defaultEmbeddingModelId: null })
        ipc.invoke('llm:set-default-embedding-model', null)
      }
    }
    return result.success
  },

  setDefaultModel: (modelId) => {
    set({ defaultModelId: modelId })
    ipc.invoke('llm:set-default-model', modelId)
  },

  setDefaultEmbeddingModel: (modelId) => {
    set({ defaultEmbeddingModelId: modelId })
    ipc.invoke('llm:set-default-embedding-model', modelId)
  },

  generate: async (messages, modelId, options) => {
    const mid = modelId ?? get().defaultModelId
    if (!mid) return { success: false, content: '', error: '未配置默认模型' }
    return ipc.invoke('llm:generate', {
      modelId: mid,
      messages,
      responseFormat: options?.responseFormat as { type: 'json_object' | 'text' } | undefined,
      thinking: options?.thinking,
      maxTokens: options?.maxTokens,
      temperature: options?.temperature,
    })
  },

  generateStream: async (messages, callbacks, modelId, options) => {
    const mid = modelId ?? get().defaultModelId
    if (!mid) {
      callbacks.onError?.('未配置默认模型')
      return ''
    }

    const requestId = crypto.randomUUID()

    // 注册流式事件监听
    const unsubChunk = ipc.on('llm:stream-chunk', (data) => {
      if (data.requestId === requestId) {
        callbacks.onChunk?.(data.chunk)
      }
    })

    const unsubDone = ipc.on('llm:stream-done', (data) => {
      if (data.requestId === requestId) {
        callbacks.onDone?.(data.fullText, data.usage)
        cleanup()
      }
    })

    const unsubError = ipc.on('llm:stream-error', (data) => {
      if (data.requestId === requestId) {
        callbacks.onError?.(data.error)
        cleanup()
      }
    })

    const cleanup = () => {
      unsubChunk()
      unsubDone()
      unsubError()
      const reqs = new Map(get().activeRequests)
      reqs.delete(requestId)
      set({ activeRequests: reqs })
    }

    // 标记活跃请求
    const reqs = new Map(get().activeRequests)
    reqs.set(requestId, { status: 'running', text: '' })
    set({ activeRequests: reqs })

    // 发起流式请求
    await ipc.invoke('llm:generate-stream', requestId, {
      modelId: mid,
      messages,
      stream: true,
      responseFormat: options?.responseFormat as { type: 'json_object' | 'text' } | undefined,
      thinking: options?.thinking,
      maxTokens: options?.maxTokens,
      temperature: options?.temperature,
    })

    return requestId
  },

  cancelGeneration: async (requestId) => {
    await ipc.invoke('llm:cancel', requestId)
  },

  testConnection: async (model) => {
    return ipc.invoke('llm:test-connection', model)
  },
}))
