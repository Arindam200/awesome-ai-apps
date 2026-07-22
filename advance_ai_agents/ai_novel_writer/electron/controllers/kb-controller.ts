import { app, ipcMain, dialog } from 'electron'
import fs from 'node:fs'
import { readJsonFile, GLOBAL_CONFIG_PATH, DEFAULT_GLOBAL_CONFIG, MODELS_CONFIG_PATH, RECENT_PROJECTS_PATH } from '../utils/config-utils'
import { GlobalConfig, ModelProfile } from '../../src/shared/ipc-channels'
import { knowledgeBaseLoader } from '../services/knowledge-base-loader'
import { mainText } from '../i18n'

function text(zhCNText: string, enUSText: string): string {
  return mainText(app.getLocale(), zhCNText, enUSText)
}

function getEmbeddingConfig(): { protocol: 'openai' | 'gemini'; model: { baseUrl: string; apiKey: string; modelName: string } } | null {
  const config = readJsonFile<GlobalConfig>(GLOBAL_CONFIG_PATH, DEFAULT_GLOBAL_CONFIG)
  const targetModelId = config.defaultEmbeddingModelId || config.defaultModelId
  if (!targetModelId) return null

  const models = readJsonFile<ModelProfile[]>(MODELS_CONFIG_PATH, [])
  const model = models.find((m) => m.id === targetModelId)
  if (!model) return null
  return {
    protocol: model.protocol as 'openai' | 'gemini',
    model: { baseUrl: model.baseUrl, apiKey: model.apiKey, modelName: model.modelName },
  }
}

function getCurrentProjectPath(): string | null {
  try {
    const recent = JSON.parse(fs.readFileSync(RECENT_PROJECTS_PATH, 'utf-8')) as Array<{ path: string }>
    return recent[0]?.path ?? null
  } catch { return null }
}

export function registerKBController() {
  ipcMain.handle('kb:import-document', async (_event, filePath: string) => {
    const embConfig = getEmbeddingConfig()
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return { success: false, errorCode: 'PROJECT_NOT_OPEN', error: text('未打开项目', 'No project is open') }
    const protocol = embConfig?.protocol ?? 'openai'
    const model = embConfig?.model ?? { baseUrl: '', apiKey: '' }
    return knowledgeBaseLoader.run((kb) => kb.importDocument(filePath, projectPath, protocol, model))
  })

  ipcMain.handle('kb:import-folder', async (_event, folderPath: string) => {
    const embConfig = getEmbeddingConfig()
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return { success: false, errorCode: 'PROJECT_NOT_OPEN', error: text('未打开项目', 'No project is open') }
    const protocol = embConfig?.protocol ?? 'openai'
    const model = embConfig?.model ?? { baseUrl: '', apiKey: '' }
    return knowledgeBaseLoader.run((kb) => kb.importFolder(folderPath, projectPath, protocol, model))
  })

  ipcMain.handle('kb:import-text', async (_event, text: string, fileName: string, projectPath: string) => {
    const embConfig = getEmbeddingConfig()
    const protocol = embConfig?.protocol ?? 'openai'
    const model = embConfig?.model ?? { baseUrl: '', apiKey: '' }
    return knowledgeBaseLoader.run((kb) => kb.importText(text, fileName, projectPath, protocol, model))
  })

  ipcMain.handle('kb:search', async (_event, query: string, topK?: number) => {
    const embConfig = getEmbeddingConfig()
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return []

    return knowledgeBaseLoader.run((kb) => {
      if (embConfig) {
        return kb.searchKnowledge(query, projectPath, embConfig.protocol, embConfig.model, topK ?? 5)
      }
      return kb.searchKnowledgeFTS(query, projectPath, topK ?? 5)
    })
  })

  ipcMain.handle('kb:search-with-scope', async (_event, query: string, fromChapter: number, toChapter: number, topK?: number) => {
    const embConfig = getEmbeddingConfig()
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return []

    const scope: [number, number] = [fromChapter, toChapter]
    return knowledgeBaseLoader.run((kb) => {
      if (embConfig) {
        return kb.searchKnowledge(query, projectPath, embConfig.protocol, embConfig.model, topK ?? 5, scope)
      }
      return kb.searchKnowledgeFTS(query, projectPath, topK ?? 5, scope)
    })
  })

  ipcMain.handle('kb:list-documents', async () => {
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return []
    return knowledgeBaseLoader.run((kb) => kb.listDocuments(projectPath))
  })

  ipcMain.handle('kb:remove-document', async (_event, docId: string) => {
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return { success: false }
    return knowledgeBaseLoader.run((kb) => ({ success: kb.removeDocument(docId, projectPath) }))
  })

  ipcMain.handle('kb:clear-all', async () => {
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return { success: false, errorCode: 'PROJECT_NOT_OPEN', error: text('未打开项目', 'No project is open') }
    return knowledgeBaseLoader.run(async (kb) => {
      const success = await kb.clearKnowledgeBase(projectPath)
      return success ? { success: true } : { success: false, error: text('清空知识库失败', 'Could not clear the knowledge base') }
    })
  })

  ipcMain.handle('kb:stats', async () => {
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return { documentCount: 0, totalChunks: 0, vectorDimension: 0 }
    return knowledgeBaseLoader.run((kb) => kb.getKnowledgeStats(projectPath))
  })

  ipcMain.handle('kb:get-vectorless-count', async () => {
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return { count: 0 }
    return knowledgeBaseLoader.run((kb) => kb.getVectorlessCount(projectPath))
  })

  ipcMain.handle('kb:backfill-vectors', async () => {
    const embConfig = getEmbeddingConfig()
    if (!embConfig) return { success: false, processed: 0, failed: 0, errorCode: 'EMBEDDING_MODEL_NOT_CONFIGURED', error: text('未配置 Embedding 模型', 'No embedding model is configured') }
    const projectPath = getCurrentProjectPath()
    if (!projectPath) return { success: false, processed: 0, failed: 0, errorCode: 'PROJECT_NOT_OPEN', error: text('未打开项目', 'No project is open') }
    return knowledgeBaseLoader.run((kb) => kb.backfillVectors(projectPath, embConfig.protocol, embConfig.model))
  })

  ipcMain.handle('dialog:select-files', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile', 'multiSelections'],
      title: text('选择要导入的文档', 'Choose documents to import'),
      filters: [{ name: text('文本文件', 'Text files'), extensions: ['txt', 'md', 'markdown'] }],
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths
  })

  ipcMain.handle('dialog:select-import-folder', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory'],
      title: text('选择要批量导入的文件夹', 'Choose a folder to import'),
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })
}
