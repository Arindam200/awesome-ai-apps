/**
 * search_knowledge — 语义搜索知识库
 */
import { buildAgentTool } from '../tool-registry'
import { searchKB } from '../../knowledge-service'

export const searchKnowledgeTool = buildAgentTool({
  name: 'search_knowledge',
  description: '在知识库中进行语义搜索，查找与查询相关的参考资料、设定文档等。适用于查找世界观设定、角色背景、故事素材等。',
  source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: '搜索查询语句，例如 "主角的金手指设定"',
      },
      top_k: {
        type: 'number',
        description: '返回结果数量',
        default: 5,
      },
    },
    required: ['query'],
  },
  requiresConfirmation: false,
  execute: async (args) => {
    const query = args.query as string
    const topK = (args.top_k as number) ?? 5

    if (!query) {
      return { success: false, content: '', error: '缺少 query 参数' }
    }

    const results = await searchKB(query, topK)
    if (!results || results.length === 0) {
      return { success: true, content: '未找到相关结果。请尝试使用不同的关键词搜索，或尝试使用 read_architecture、read_characters 等工具直接读取项目数据。' }
    }

    const formatted = results.map((r, i) =>
      `### 结果 ${i + 1} (相似度: ${r.score.toFixed(2)})\n来源: ${r.fileName}\n\n${r.text}`
    ).join('\n\n---\n\n')

    return { success: true, content: `找到 ${results.length} 条相关结果：\n\n${formatted}` }
  },
})
