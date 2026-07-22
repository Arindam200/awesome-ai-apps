import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useLLMStore } from '../../../../stores/llm-store'
import { useProjectStore } from '../../../../stores/project-store'
import type { StepCallbacks, WorkflowContext } from '../../../../stores/workflow-store'
import { GenerateDirectoryCommand } from '../directory.command'

const callbacks: StepCallbacks = {
  log: vi.fn(),
  setProgress: vi.fn(),
  appendText: vi.fn(),
}

const context: WorkflowContext = {
  data: {
    architecture: '故事前提'.repeat(30),
  },
  cancelled: false,
}

function stubIpcInvoke(handler: (channel: string, ...args: unknown[]) => unknown) {
  const invoke = vi.fn((channel: string, ...args: unknown[]) => Promise.resolve(handler(channel, ...args)))
  vi.stubGlobal('window', {
    velaAPI: {
      invoke,
      on: vi.fn(),
      once: vi.fn(),
      send: vi.fn(),
      setZoomLevel: vi.fn(),
      setZoomFactor: vi.fn(),
      getZoomLevel: vi.fn(),
    },
  })
  return invoke
}

beforeEach(() => {
  vi.clearAllMocks()
  useProjectStore.setState({
    currentProject: {
      id: 'project-1',
      name: '测试项目',
      path: 'C:\\tmp\\vela-test',
      novelConfig: {
        genre: '玄幻',
        subGenre: '',
        targetAudience: '男频',
        totalChapters: 3,
        wordsPerChapter: 3000,
        plotStructure: 'three_act',
        narrativePOV: 'third_limited',
        coreOutline: '',
        worldSetting: '',
        goldenFinger: '',
        protagonistProfile: '',
        globalGuidance: '',
      },
      characterStates: '',
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-01-01T00:00:00.000Z',
    },
  })
  useLLMStore.setState({
    defaultModelId: 'model-1',
    models: [{
      id: 'model-1',
      name: '测试模型',
      provider: 'custom',
      protocol: 'openai',
      modelName: 'test',
      apiKey: '',
      baseUrl: '',
      temperature: 0.7,
      maxTokens: 4096,
      purposes: ['generation'],
    }],
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  useProjectStore.setState({ currentProject: null })
  useLLMStore.setState({ defaultModelId: null, models: [] })
})

describe('GenerateDirectoryCommand', () => {
  it('fails when a generated batch parses to no blueprints', async () => {
    stubIpcInvoke(() => ({ success: true }))
    const command = new GenerateDirectoryCommand({ mode: 'full', count: 1 })
    vi.spyOn(command as unknown as { callLLM: () => Promise<string> }, 'callLLM').mockResolvedValue('[]')

    await expect(command.execute({ step: {}, context, callbacks })).rejects.toThrow(/未解析到/)
  })

  it('fails when a saved blueprint cannot be read back from the DB', async () => {
    const invoke = stubIpcInvoke((channel) => {
      if (channel === 'db:blueprint-upsert-many') return { success: true }
      if (channel === 'db:blueprint-get') return null
      return { success: true }
    })
    const command = new GenerateDirectoryCommand({ mode: 'full', count: 1 })
    vi.spyOn(command as unknown as { callLLM: () => Promise<string> }, 'callLLM').mockResolvedValue(
      '[{"chapterNumber":1,"title":"启程","keyEvents":"主角发现异常"}]',
    )

    await expect(command.execute({ step: {}, context, callbacks })).rejects.toThrow(/保存后验证/)
    expect(invoke).toHaveBeenCalledWith('db:blueprint-get', 1)
  })

  it('fails when generated blueprints skip required target chapters', async () => {
    const invoke = stubIpcInvoke(() => ({ success: true }))
    const command = new GenerateDirectoryCommand({ mode: 'full', count: 3 })
    vi.spyOn(command as unknown as { callLLM: () => Promise<string> }, 'callLLM').mockResolvedValue(
      '[{"chapterNumber":3,"title":"错位","keyEvents":"只返回第三章"}]',
    )

    await expect(command.execute({ step: {}, context, callbacks })).rejects.toThrow(/缺少目标章节/)
    expect(invoke).not.toHaveBeenCalledWith('db:blueprint-upsert-many', expect.anything())
  })
})
