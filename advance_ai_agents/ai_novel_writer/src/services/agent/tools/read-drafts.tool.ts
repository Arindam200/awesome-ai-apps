/**
 * read_drafts — 读取草稿内容及状态
 */
import { buildAgentTool } from '../tool-registry'
import { ipc } from '../../ipc-client'
import { useProjectStore } from '../../../stores/project-store'


export const readDraftsTool = buildAgentTool({
  name: 'read_drafts',
  description: '读取指定章节的草稿内容。可以获取初稿、修订稿等不同版本。',
  source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      chapter_number: {
        type: 'number',
        description: '章节号（必填）',
      },
      draft_type: {
        type: 'string',
        description: '草稿类型',
        enum: ['draft_v1', 'revised', 'latest'],
        default: 'latest',
      },
    },
    required: ['chapter_number'],
  },
  requiresConfirmation: false,
  execute: async (args) => {
    const project = useProjectStore.getState().currentProject
    if (!project) {
      return { success: false, content: '', error: '没有打开的项目' }
    }

    const chapterNum = args.chapter_number as number
    const draftType = (args.draft_type as string) ?? 'latest'

    try {
      // 从数据库获取章节的草稿列表
      const draftsResult = await ipc.invoke('db:draft-list', chapterNum)
      const drafts = (Array.isArray(draftsResult) ? draftsResult : []) as unknown as Array<Record<string, unknown>>
      if (!drafts || drafts.length === 0) {
        return { success: true, content: `第 ${chapterNum} 章暂无草稿。` }
      }

      let targetId: number | null = null
      let targetName = ''

      if (draftType === 'latest') {
        const latest = drafts[0] // 默认查询回来是按 version 倒序排列的
        targetId = latest.id as number
        targetName = `v${latest.version as number}`
      } else {
        // 查找指定类型的草稿
        const target = drafts.find(d => {
          if (draftType === 'draft_v1') return (d.version as number) === 1
          if (draftType === 'revised') return (d.version as number) > 1
          return false
        })

        if (!target) {
          const available = drafts.map(d => `v${d.version as number}`).join('、')
          return { success: false, content: '', error: `未找到 "${draftType}" 类型的草稿。可用版本：${available}` }
        }
        targetId = target.id as number
        targetName = `v${target.version as number}`
      }

      const fullDraft = await ipc.invoke('db:draft-get-full', targetId as number) as { content?: string } | null
      if (!fullDraft) {
        return { success: false, content: '', error: `读取草稿内容失败：id ${targetId}` }
      }
      return { success: true, content: `📝 第 ${chapterNum} 章草稿（${targetName}）\n\n${fullDraft.content}` }
    } catch (error) {
      return { success: false, content: '', error: `读取草稿失败：${String(error)}` }
    }
  },
})
