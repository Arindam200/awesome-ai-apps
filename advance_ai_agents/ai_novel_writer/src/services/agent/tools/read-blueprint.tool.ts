/**
 * read_blueprint — 读取章节蓝图
 */
import { buildAgentTool } from '../tool-registry'
import { ipc } from '../../ipc-client'
import { useProjectStore } from '../../../stores/project-store'


export const readBlueprintTool = buildAgentTool({
  name: 'read_blueprint',
  description: '读取指定章节的蓝图（剧情大纲、场景分配、角色出场计划等）。蓝图是写稿前的详细规划。',
  source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      chapter_number: {
        type: 'number',
        description: '章节号（可选）。不填则列出所有蓝图文件。',
      },
    },
  },
  requiresConfirmation: false,
  execute: async (args) => {
    const project = useProjectStore.getState().currentProject
    if (!project) {
      return { success: false, content: '', error: '没有打开的项目' }
    }

    const chapterNum = args.chapter_number as number | undefined

    if (chapterNum !== undefined) {
      // 读取指定章节蓝图
      const bp = await ipc.invoke('db:blueprint-get', chapterNum)
      if (!bp) {
        return { success: false, content: '', error: `第 ${chapterNum} 章蓝图不存在或读取失败` }
      }
      return { success: true, content: `📋 第 ${chapterNum} 章蓝图\n\n标题: ${bp.title}\n作用: ${bp.role}\n目的: ${bp.purpose}\n关键事件: ${bp.keyEvents}\n角色: ${bp.characters.join(', ')}\n悬念: ${bp.suspenseHook}\n备注: ${bp.notes}\n用户指引: ${bp.userGuidance}` }
    }

    // 列出所有蓝图文件
    try {
      const bps = await ipc.invoke('db:blueprint-get-all')
      if (!bps || bps.length === 0) {
        return { success: true, content: '⚠️ 蓝图为空。建议先通过工作流生成章节蓝图。' }
      }

      const list = bps.map((b: unknown) => `  - 第 ${(b as { chapterNumber?: number }).chapterNumber} 章: ${(b as { title?: string }).title || '无标题'}`).join('\n')
      return { success: true, content: `📋 蓝图列表（${bps.length} 个）\n${list}\n\n使用 chapter_number 参数可以读取具体章节蓝图的内容。` }
    } catch (error) {
      return { success: false, content: '', error: `读取蓝图失败：${String(error)}` }
    }
  },
})
