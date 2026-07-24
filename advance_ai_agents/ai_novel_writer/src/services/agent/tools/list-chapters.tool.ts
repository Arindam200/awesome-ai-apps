/**
 * list_chapters — 列出所有章节状态概览
 */
import { buildAgentTool } from '../tool-registry'
import { ipc } from '../../ipc-client'
import { useProjectStore } from '../../../stores/project-store'


export const listChaptersTool = buildAgentTool({
  name: 'list_chapters',
  description: '列出项目中所有章节的状态概览，包括哪些章节有蓝图、有草稿、已定稿等信息。用于了解项目整体进度。',
  source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {},
  },
  requiresConfirmation: false,
  execute: async () => {
    const project = useProjectStore.getState().currentProject
    if (!project) {
      return { success: false, content: '', error: '没有打开的项目' }
    }

    try {
      const blueprints = await ipc.invoke('db:blueprint-get-all')
      const bpNums = new Set<number>((Array.isArray(blueprints) ? blueprints : []).map((b: unknown) => (b as { chapterNumber?: number }).chapterNumber).filter((n): n is number => n !== undefined))
      const { useDraftStore } = await import('../../../stores/draft-store')
      const draftsByChapter = useDraftStore.getState().draftsByChapter
      const draftNums = new Set<number>(Object.keys(draftsByChapter).map(k => parseInt(k, 10)))

      // 定稿状态从 DB 查询而非 FS 扫描
      const msNums = new Set<number>()
      for (const bp of (Array.isArray(blueprints) ? blueprints : [])) {
        const finalized = await ipc.invoke('db:draft-get-finalized', bp.chapterNumber)
        if (finalized) msNums.add(bp.chapterNumber)
      }

      // 合并所有出现过的章节号
      const allNums = new Set([...bpNums, ...draftNums, ...msNums])
      if (allNums.size === 0) {
        return { success: true, content: '📊 项目中暂无任何章节数据。建议先生成故事架构和章节蓝图。' }
      }

      const sortedNums = Array.from(allNums).sort((a, b) => a - b)

      const rows = sortedNums.map(num => {
        const hasBp = bpNums.has(num) ? '✅' : '❌'
        const hasDraft = draftNums.has(num) ? '✅' : '❌'
        const hasMs = msNums.has(num) ? '✅' : '❌'
        return `| ${num} | ${hasBp} | ${hasDraft} | ${hasMs} |`
      })

      const table = `| 章节 | 蓝图 | 草稿 | 定稿 |\n| --- | --- | --- | --- |\n${rows.join('\n')}`

      return {
        success: true,
        content: `📊 章节进度概览\n\n${table}\n\n总计：${sortedNums.length} 个章节，${bpNums.size} 个蓝图，${draftNums.size} 个草稿，${msNums.size} 个定稿`,
      }
    } catch (e: unknown) {
      return { success: false, content: '', error: `获取失败: ${e instanceof Error ? e.message : String(e)}` }
    }
  },
})
