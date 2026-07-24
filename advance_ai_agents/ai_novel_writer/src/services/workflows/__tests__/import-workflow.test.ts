import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createImportWorkflow } from '../import-workflow'
import type { StepCallbacks, WorkflowContext } from '../../../stores/workflow-store'

const styleMocks = vi.hoisted(() => ({
  execute: vi.fn(),
}))

vi.mock('../commands/analyze-style.command', () => ({
  AnalyzeWritingStyleCommand: vi.fn(function AnalyzeWritingStyleCommandMock() {
    return {
    execute: styleMocks.execute,
    }
  }),
}))

const callbacks: StepCallbacks = {
  log: vi.fn(),
  setProgress: vi.fn(),
  appendText: vi.fn(),
}

const context: WorkflowContext = {
  data: {},
  cancelled: false,
}

function source(file: string) {
  return readFileSync(resolve(process.cwd(), file), 'utf8')
}

const pseudoIconPattern = new RegExp([
  '[\\u2600-\\u27BF]',
  '[\\u{1F300}-\\u{1FAFF}]',
  '\\uFE0F',
].join('|'), 'u')

beforeEach(() => {
  vi.clearAllMocks()
})

describe('createImportWorkflow', () => {
  it('extracts writing style from imported chapters before inferring blueprints', () => {
    const workflow = createImportWorkflow({
      chapters: [
        {
          number: 1,
          title: '启程',
          content: '雨声很急。主角推门而入。',
          wordCount: 13,
        },
      ],
    })

    const stepNames = workflow.steps.map((step) => step.name)

    expect(stepNames).toContain('AI 拆解文风与仿写指南')
    expect(stepNames.indexOf('AI 拆解文风与仿写指南')).toBeLessThan(stepNames.indexOf('AI 逐章推演蓝图'))
  })

  it('fails the workflow when style imitation extraction fails', async () => {
    styleMocks.execute.mockRejectedValue(new Error('style failed'))
    const workflow = createImportWorkflow({
      chapters: [{ number: 1, title: '启程', content: '雨声很急。', wordCount: 5 }],
    })

    const step = workflow.steps.find(item => item.name === 'AI 拆解文风与仿写指南')
    await expect(step?.executor({} as never, context, callbacks)).rejects.toThrow('style failed')
  })

  it('fails the workflow when style imitation extraction returns empty output', async () => {
    styleMocks.execute.mockResolvedValue('')
    const workflow = createImportWorkflow({
      chapters: [{ number: 1, title: '启程', content: '雨声很急。', wordCount: 5 }],
    })

    const step = workflow.steps.find(item => item.name === 'AI 拆解文风与仿写指南')
    await expect(step?.executor({} as never, context, callbacks)).rejects.toThrow('未提取到可用')
  })

  it('keeps the import and imitation workflow free of pseudo icon text', () => {
    const combined = [
      'src/services/workflows/import-workflow.ts',
      'src/services/workflows/commands/analyze-style.command.ts',
      'src/services/workflows/commands/import-novel.command.ts',
    ].map(source).join('\n')

    expect(combined).not.toMatch(pseudoIconPattern)
  })
})
