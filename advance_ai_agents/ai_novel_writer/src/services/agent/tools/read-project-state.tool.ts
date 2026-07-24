/**
 * read_project_state — 读取项目全局状态
 */
import { buildAgentTool } from '../tool-registry'
import { useProjectStore } from '../../../stores/project-store'
import { ipc } from '../../ipc-client'


export const readProjectStateTool = buildAgentTool({
  name: 'read_project_state',
  description: '读取项目的全局状态信息，包括小说配置、近章要点等。用于了解项目的整体概况。',
  source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      include_config: {
        type: 'boolean',
        description: '是否包含完整的小说配置',
        default: true,
      },
      include_summary: {
        type: 'boolean',
        description: '是否包含近章要点',
        default: true,
      },
    },
  },
  requiresConfirmation: false,
  execute: async (args) => {
    const project = useProjectStore.getState().currentProject
    if (!project) {
      return { success: false, content: '', error: '没有打开的项目' }
    }

    const includeConfig = (args.include_config as boolean) !== false
    const includeSummary = (args.include_summary as boolean) !== false

    const parts: string[] = [`# 📊 项目状态：《${project.name}》\n`]

    if (includeConfig) {
      // 读取小说配置
      try {
        const core = await ipc.invoke('db:project-core-get')
        if (core) {
          parts.push(`## 小说配置\n\`\`\`json\n${JSON.stringify({
            projectName: core.projectName,
            genre: core.genre,
            subGenre: core.subGenre,
            targetAudience: core.targetAudience,
            totalChapters: core.totalChapters,
            wordsPerChapter: core.wordsPerChapter,
            plotStructure: core.plotStructure,
            narrativePov: core.narrativePov,
            writingStyle: core.writingStyle
          }, null, 2)}\n\`\`\``)
        }
      } catch {
        // Fallback
        parts.push(`## 小说配置\n⚠️ 获取配置失败`)
      }
    }

    if (includeSummary) {
      // 读取最近 5 章蓝图的 notes 字段作为进度摘要
      const notesParts: string[] = []
      try {
        const bps = await ipc.invoke('db:blueprint-get-all')
        if (bps && Array.isArray(bps)) {
          // 倒序遍历
          const sorted = bps.sort((a, b) => b.chapterNumber - a.chapterNumber)
          for (const bp of sorted) {
            if (bp.notes && bp.notes.trim()) {
              notesParts.unshift(`### 第${bp.chapterNumber}章 ${bp.title || ''}\n${bp.notes}`)
              if (notesParts.length >= 5) break
            }
          }
        }
      } catch { /* 忽略 */ }

      if (notesParts.length > 0) {
        parts.push(`## 近章要点\n${notesParts.join('\n\n')}`)
      } else {
        parts.push(`## 近章要点\n暂无章节要点。章节要点会在定稿后自动生成并写入蓝图。`)
      }
    }

    return { success: true, content: parts.join('\n\n') }
  },
})
