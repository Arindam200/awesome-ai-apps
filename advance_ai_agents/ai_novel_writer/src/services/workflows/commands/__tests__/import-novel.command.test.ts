import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useProjectStore } from '../../../../stores/project-store'
import type { StepCallbacks, WorkflowContext } from '../../../../stores/workflow-store'
import { InferBlueprintsPerChapterCommand } from '../import-novel.command'

const callbacks: StepCallbacks = {
  log: vi.fn(),
  setProgress: vi.fn(),
  appendText: vi.fn(),
}

function createContext(): WorkflowContext {
  return {
    data: {
      novelConfigSummary: '类型: 玄幻',
      chapters: [
        {
          number: 1,
          title: '启程',
          content: '主角在雨夜发现异常，并踏上旅程。',
          wordCount: 18,
        },
      ],
    },
    cancelled: false,
  }
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
      name: '导入项目',
      path: 'C:\\tmp\\vela-import-test',
      novelConfig: {
        genre: '玄幻',
        subGenre: '',
        targetAudience: '男频',
        totalChapters: 1,
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
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  useProjectStore.setState({ currentProject: null })
})

describe('InferBlueprintsPerChapterCommand', () => {
  it('throws after db:blueprint-upsert reports failure', async () => {
    stubIpcInvoke((channel) => {
      if (channel === 'db:blueprint-upsert') return { success: false, error: 'DB 写入失败' }
      return { success: true }
    })
    const command = new InferBlueprintsPerChapterCommand()
    vi.spyOn(command as unknown as { callLLM: () => Promise<string> }, 'callLLM').mockResolvedValue(
      '{"title":"启程","role":"建置","purpose":"引出主角目标","keyEvents":"主角发现异常","characters":["主角"],"suspenseHook":"门外有人"}',
    )

    await expect(command.execute({ step: {}, context: createContext(), callbacks })).rejects.toThrow(/DB 写入失败/)
  })
})
