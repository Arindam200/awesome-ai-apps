/**
 * 导出服务 — 将小说项目导出为多种格式
 *
 * 支持：
 * - 合并 Markdown（全书合并为单个 .md）
 * - 分章 Markdown（每章一个 .md）
 * - 纯文本 TXT
 */
import { ipc } from './ipc-client'
import { useProjectStore } from '../stores/project-store'
import { useWorkflowStore } from '../stores/workflow-store'


export type ExportFormat = 'merged-md' | 'split-md' | 'txt'

interface ExportOptions {
  format: ExportFormat
  outputDir: string
  includeOutline?: boolean
  includeCharacters?: boolean
}

/** 导出全书 */
export async function exportNovel(options: ExportOptions): Promise<{ success: boolean; path?: string; error?: string }> {
  const project = useProjectStore.getState().currentProject
  if (!project) return { success: false, error: '未打开项目' }

  const addLog = useWorkflowStore.getState().addLog
  addLog('info', `📦 开始导出（${formatLabel(options.format)}）...`)

  try {
    // 遍历所有章节蓝图，取定稿内容
    const chapterContents: Array<{ name: string; content: string }> = []
    const blueprints = (await ipc.invoke('db:blueprint-get-all')) as unknown as Array<Record<string, unknown>>
    const sortedBps = blueprints ? blueprints.sort((a, b) => (a.chapterNumber as number) - (b.chapterNumber as number)) : []

    for (const bp of sortedBps) {
      const meta = await ipc.invoke('db:draft-get-finalized', bp.chapterNumber as number)
      if (meta && (meta as { id: number }).id !== undefined) {
        const full = await ipc.invoke('db:draft-get-full', (meta as { id: number }).id)
        if (full && (full as { content?: string }).content) {
          chapterContents.push({
            name: `chapter_${bp.chapterNumber}.md`,
            content: (full as { content: string }).content,
          })
        }
      }
    }

    if (chapterContents.length === 0) {
      return { success: false, error: '无可导出的章节（无定稿章节）' }
    }

    addLog('info', `找到 ${chapterContents.length} 个已定稿章节`)

    // 确保输出目录存在
    await ipc.invoke('fs:mkdir', options.outputDir)

    let outputPath = ''

    switch (options.format) {
      case 'merged-md': {
        // 合并为单个 Markdown
        let content = `# ${project.name}\n\n`
        content += `> ${project.novelConfig.genre} · ${project.novelConfig.targetAudience}\n\n---\n\n`

        // 可选：包含大纲
        if (options.includeOutline) {
          const core = await ipc.invoke('db:project-core-get')
          if (core?.synopsis) {
            content += core.synopsis + '\n\n---\n\n'
          }
        }

        // 章节内容
        for (const ch of chapterContents) {
          content += ch.content + '\n\n---\n\n'
        }

        outputPath = `${options.outputDir}/${project.name}.md`
        await ipc.invoke('fs:write-file', outputPath, content)
        break
      }

      case 'split-md': {
        // 每章一个 Markdown
        const splitDir = `${options.outputDir}/${project.name}`
        await ipc.invoke('fs:mkdir', splitDir)

        for (const ch of chapterContents) {
          await ipc.invoke('fs:write-file', `${splitDir}/${ch.name}`, ch.content)
        }

        outputPath = splitDir
        break
      }

      case 'txt': {
        // 纯文本（去除 Markdown 格式）
        let content = `${project.name}\n${'='.repeat(project.name.length * 2)}\n\n`

        for (const ch of chapterContents) {
          // 简单去除 Markdown 标记
          const plainText = ch.content
            .replace(/^#{1,6}\s+/gm, '')  // 去掉标题标记
            .replace(/\*\*(.*?)\*\*/g, '$1')  // 去掉加粗
            .replace(/\*(.*?)\*/g, '$1')  // 去掉斜体
            .replace(/`(.*?)`/g, '$1')  // 去掉代码标记
            .replace(/---+/g, '\n')  // 分隔线
            .trim()

          content += plainText + '\n\n'
        }

        outputPath = `${options.outputDir}/${project.name}.txt`
        await ipc.invoke('fs:write-file', outputPath, content)
        break
      }
    }

    addLog('info', `✅ 导出完成: ${outputPath}`)
    return { success: true, path: outputPath }
  } catch (error) {
    addLog('error', `❌ 导出失败: ${error}`)
    return { success: false, error: String(error) }
  }
}

function formatLabel(format: ExportFormat): string {
  const labels: Record<ExportFormat, string> = {
    'merged-md': '合并 Markdown',
    'split-md': '分章 Markdown',
    'txt': '纯文本 TXT',
  }
  return labels[format]
}
