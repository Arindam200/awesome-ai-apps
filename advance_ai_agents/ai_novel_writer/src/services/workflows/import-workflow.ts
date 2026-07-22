/**
 * 导入小说工作流定义
 *
 * 逆向推演全流程：
 * 步骤1: 写入正文 + 构建知识库
 * 步骤2: 向量采样 + AI 推演全局配置/架构/角色
 * 步骤3: AI 从导入正文提取文风
 * 步骤4: AI 按章推演精准蓝图 + 蓝图入向量库 + 拼装轻量全局摘要
 * 步骤5: 完成后处理（刷新 UI 状态）
 */

import type { WorkflowDefinition } from '../../stores/workflow-store'
import type { ImportedChapter } from './commands/import-novel.command'

export interface ImportWorkflowParams {
  /** 拆分后的章节数据 */
  chapters: ImportedChapter[]
}

/**
 * 创建导入小说工作流
 */
export function createImportWorkflow(params: ImportWorkflowParams): WorkflowDefinition {
  return {
    type: 'novel_import',
    title: `小说拆解与仿写（${params.chapters.length} 章）`,
    steps: [
      // ===== 步骤 1: 写入正文 + 构建知识库 =====
      {
        name: '写入正文与构建知识库',
        description: `将 ${params.chapters.length} 章正文写入 manuscript/ 并灌入向量知识库`,
        executor: async (step, context, callbacks) => {
          const { ImportInitializeCommand } = await import('./commands/import-novel.command')
          const cmd = new ImportInitializeCommand(params.chapters)
          return cmd.execute({ step, context, callbacks })
        },
      },

      // ===== 步骤 2: 向量采样 + AI 推演全局设定 =====
      {
        name: 'AI 推演全局配置与架构',
        description: '通过向量检索关键片段，AI 推演小说配置、故事架构、角色卡',
        executor: async (step, context, callbacks) => {
          const { InferGlobalSettingsCommand } = await import('./commands/import-novel.command')
          const cmd = new InferGlobalSettingsCommand()
          return cmd.execute({ step, context, callbacks })
        },
      },

      // ===== 步骤 3: 从导入正文拆解文风与仿写约束 =====
      {
        name: 'AI 拆解文风与仿写指南',
        description: '从导入 TXT/Markdown 正文中提取风格档案和仿写约束，写入小说配置供后续写稿调用',
        executor: async (step, context, callbacks) => {
          const { AnalyzeWritingStyleCommand } = await import('./commands/analyze-style.command')
          const cmd = new AnalyzeWritingStyleCommand({ chapters: params.chapters })
          const style = await cmd.execute({ step, context, callbacks })
          if (!style?.trim()) {
            throw new Error('未提取到可用文风，无法继续建立仿写约束')
          }
          return '已提取并保存风格档案与仿写指南'
        },
      },

      // ===== 步骤 4: AI 按章推演蓝图 + 蓝图入向量库 + 拼装摘要 =====
      {
        name: 'AI 逐章推演蓝图',
        description: `逐章推演蓝图 + 蓝图要点入向量库 + 拼装全局摘要（共 ${params.chapters.length} 章）`,
        executor: async (step, context, callbacks) => {
          const { InferBlueprintsPerChapterCommand } = await import('./commands/import-novel.command')
          const cmd = new InferBlueprintsPerChapterCommand()
          return cmd.execute({ step, context, callbacks })
        },
      },

      // ===== 步骤 5: 完成后处理 =====
      {
        name: '完成后处理',
        description: '刷新项目状态，加载角色卡与蓝图数据',
        executor: async (_step, _context, callbacks) => {
          callbacks.log('正在刷新项目数据...')
          callbacks.setProgress(30)

          // 刷新文件树
          const { useProjectStore } = await import('../../stores/project-store')
          await useProjectStore.getState().refreshFileTree()

          // 加载角色卡
          try {
            const { useCharacterStore } = await import('../../stores/character-store')
            const project = useProjectStore.getState().currentProject
            if (project) {
              await useCharacterStore.getState().loadCharacters(project.path)
            }
          } catch { /* 忽略 */ }

          // 加载草稿索引
          try {
            const { useDraftStore } = await import('../../stores/draft-store')
            await useDraftStore.getState().loadAllDrafts()
          } catch { /* 忽略 */ }

          callbacks.log('小说拆解与仿写准备完成，结构化数据已就位。')
          callbacks.setProgress(100)
        },
      },
    ],
    onComplete: {
      mode: 'silent',
      message: '小说拆解与仿写准备完成，全部结构化数据已生成，可以开始续写。',
    },
  }
}

/**
 * 预估导入的 Token 消耗
 * @param totalWords 总字数
 * @param chapterCount 章节数
 * @returns 预估信息
 */
export function estimateImportCost(_totalWords: number, chapterCount: number): {
  estimatedTokens: number
  estimatedMinutes: number
  breakdown: string
} {
  // 粗略预估（偏保守）：
  // 1. 全局推演：首章+末章(约6000字) × 2(输入+输出) ≈ 12000 tokens
  // 2. 按章蓝图：每章正文(平址3000字) + 蓝图输出(约500字) ≈ 3500 tokens/章
  // 3. 全局摘要：从蓝图拼装，零 LLM 调用
  // 4. 知识库向量化不计入 LLM Token

  const globalInferTokens = 15000
  const blueprintTokensPerChapter = 4000
  const totalBlueprintTokens = blueprintTokensPerChapter * chapterCount

  const estimatedTokens = globalInferTokens + totalBlueprintTokens

  // 预估时间（假设每次 LLM 调用约 8-15 秒，并发 3）
  const llmCallCount = 1 + Math.ceil(chapterCount / 3) // 全局推演 + 蓝图批次
  const estimatedMinutes = Math.ceil(llmCallCount * 12 / 60) // 按每次 12 秒计算

  const breakdown = [
    `· 全局推演：~${(globalInferTokens / 1000).toFixed(0)}K tokens`,
    `· 蓝图推演：~${(totalBlueprintTokens / 1000).toFixed(0)}K tokens（${chapterCount} 章 × ${(blueprintTokensPerChapter / 1000).toFixed(1)}K）`,
    `· 全局摘要：零消耗（从蓝图拼装）`,
    `· 总计：~${(estimatedTokens / 1000).toFixed(0)}K tokens`,
  ].join('\n')

  return { estimatedTokens, estimatedMinutes, breakdown }
}
