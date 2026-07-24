/**
 * update_config — 更新小说配置
 */
import { buildAgentTool } from '../tool-registry'
import { ipc } from '../../ipc-client'
import { useProjectStore } from '../../../stores/project-store'

export const updateConfigTool = buildAgentTool({
  name: 'update_config',
  description: '更新小说项目的配置信息，如类型、目标读者、大纲、写作风格等。这会修改项目核心设定，需要用户确认。',
  source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      field: {
        type: 'string',
        description: '要更新的字段名',
        enum: ['genre', 'subGenre', 'targetAudience', 'totalChapters', 'wordsPerChapter',
               'coreOutline', 'worldSetting', 'goldenFinger', 'protagonistProfile',
               'globalGuidance', 'writingStyle', 'referenceWorks'],
      },
      value: {
        type: 'string',
        description: '新值',
      },
    },
    required: ['field', 'value'],
  },
  requiresConfirmation: true,
  isReadOnly: false,
  execute: async (args) => {
    const field = args.field as string
    const value = args.value as string

    if (!field || value === undefined) {
      return { success: false, content: '', error: '缺少 field 或 value 参数' }
    }

    const project = useProjectStore.getState().currentProject
    if (!project) {
      return { success: false, content: '', error: '没有打开的项目' }
    }

    // 构造更新数据
    const updateData = {
      novelConfig: { ...project.novelConfig, [field]: value },
    }

    const result = await ipc.invoke('project:update-config', project.id, updateData)
    if (!result.success) {
      return { success: false, content: '', error: result.error ?? '配置更新失败' }
    }

    return {
      success: true,
      content: `✅ 配置已更新：${field} = "${typeof value === 'string' && value.length > 50 ? value.slice(0, 50) + '…' : value}"`,
    }
  },
})
