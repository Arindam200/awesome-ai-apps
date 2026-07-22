import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useProjectStore } from '../../../../stores/project-store'
import type { StepCallbacks, WorkflowContext } from '../../../../stores/workflow-store'
import { AnalyzeWritingStyleCommand } from '../analyze-style.command'

const callbacks: StepCallbacks = {
  log: vi.fn(),
  setProgress: vi.fn(),
  appendText: vi.fn(),
}

const context: WorkflowContext = {
  data: {},
  cancelled: false,
}

function stubIpcInvoke(updateResult: { success: boolean; error?: string } = { success: true }) {
  const invoke = vi.fn((channel: string) => {
    if (channel === 'db:project-core-update') return Promise.resolve(updateResult)
    return Promise.resolve(null)
  })
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
      path: 'C:\\tmp\\vela-style-test',
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
        writingStyle: '',
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

describe('AnalyzeWritingStyleCommand with imported samples', () => {
  it('writes analyzed sample text style to DB and novelConfig', async () => {
    const invoke = stubIpcInvoke()
    const command = new AnalyzeWritingStyleCommand({
      sampleTexts: ['短句密集，动作推进快，对话有压迫感。'],
    })
    vi.spyOn(command as unknown as { callLLM: () => Promise<string> }, 'callLLM').mockResolvedValue(
      '节奏偏快，动作描写密集，对话短促有压迫感。',
    )

    const result = await command.execute({ step: {}, context, callbacks })

    expect(result).toBe('节奏偏快，动作描写密集，对话短促有压迫感。')
    expect(useProjectStore.getState().currentProject?.novelConfig.writingStyle).toBe(result)
    expect(invoke).toHaveBeenCalledWith('db:project-core-update', { writingStyle: result })
  })

  it('uses imported chapters as style samples without reading finalized drafts', async () => {
    const invoke = stubIpcInvoke()
    const command = new AnalyzeWritingStyleCommand({
      chapters: [
        {
          number: 1,
          title: '启程',
          content: '雨声很急。主角推门而入，所有人同时沉默。',
          wordCount: 24,
        },
      ],
    })
    const callLLM = vi
      .spyOn(command as unknown as { callLLM: (prompt: string) => Promise<string> }, 'callLLM')
      .mockResolvedValue('冷峻紧凑，场景切换迅速。')

    await command.execute({ step: {}, context, callbacks })

    expect(callLLM.mock.calls[0][0]).toContain('雨声很急')
    expect(invoke).not.toHaveBeenCalledWith('db:draft-get-max-finalized-chapter')
  })

  it('does not update in-memory writing style when DB persistence fails', async () => {
    stubIpcInvoke({ success: false, error: '项目数据库未打开' })
    const command = new AnalyzeWritingStyleCommand({
      sampleTexts: ['短句密集，动作推进快，对话有压迫感。'],
    })
    vi.spyOn(command as unknown as { callLLM: () => Promise<string> }, 'callLLM').mockResolvedValue(
      '节奏偏快，动作描写密集，对话短促有压迫感。',
    )

    await expect(command.execute({ step: {}, context, callbacks })).rejects.toThrow('项目数据库未打开')
    expect(useProjectStore.getState().currentProject?.novelConfig.writingStyle).toBe('')
  })
})
