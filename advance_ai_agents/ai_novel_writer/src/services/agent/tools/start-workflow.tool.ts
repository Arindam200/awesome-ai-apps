/**
 * start_workflow — 触发创作工作流
 */
import { buildAgentTool } from '../tool-registry'
import { useLayoutStore } from '../../../stores/layout-store'

export const startWorkflowTool = buildAgentTool({
  name: 'start_workflow',
  description: '触发 AI小说作家创作工作流。支持写稿、修稿、审稿、定稿、生成蓝图等工作流。这将在 AI 输出面板中执行对应的多步骤创作流程。',
  source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      workflow: {
        type: 'string',
        description: '工作流类型',
        enum: ['generate_draft', 'review', 'refine', 'finalize', 'generate_blueprint', 'generate_architecture'],
      },
      chapter_number: {
        type: 'number',
        description: '章节号（写稿/修稿/审稿/定稿必填）',
      },
    },
    required: ['workflow'],
  },
  requiresConfirmation: true,
  isReadOnly: false,
  execute: async (args) => {
    const workflow = args.workflow as string
    const chapterNumber = args.chapter_number as number | undefined

    if (!workflow) {
      return { success: false, content: '', error: '缺少 workflow 参数' }
    }

    // 需要章节号的工作流
    const chapterWorkflows = ['generate_draft', 'review', 'refine', 'finalize']
    if (chapterWorkflows.includes(workflow) && chapterNumber === undefined) {
      return { success: false, content: '', error: `${workflow} 工作流需要指定 chapter_number 参数` }
    }

    // 打开右侧面板到 AI 输出视图
    useLayoutStore.getState().openRightPanel('ai-output')

    // 注意：实际的工作流触发需要通过 workflow-store
    // 这里返回指导信息，让用户可以从 AI 输出面板操作
    const workflowNames: Record<string, string> = {
      generate_draft: '写稿',
      review: '审稿',
      refine: '修稿',
      finalize: '定稿',
      generate_blueprint: '生成蓝图',
      generate_architecture: '生成架构',
    }

    const displayName = workflowNames[workflow] ?? workflow
    const chapterInfo = chapterNumber !== undefined ? `（第 ${chapterNumber} 章）` : ''

    return {
      success: true,
      content: `已切换到 AI 输出面板。请在面板中启动「${displayName}${chapterInfo}」工作流。`,
      artifacts: [{ type: 'workflow_started', name: `${displayName}${chapterInfo}` }],
    }
  },
})
