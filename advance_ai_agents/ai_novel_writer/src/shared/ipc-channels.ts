/**
 * IPC 频道定义 — 渲染进程与主进程的类型安全通信契约
 * 所有 IPC 调用都通过此文件定义频道名和参数/返回值类型
 */
import type { Locale } from '../i18n/types'

// ===== 全局配置 =====
export interface ConfigChannels {
  'config:get': {
    args: []
    return: GlobalConfig
  }
  'config:set': {
    args: [config: Partial<GlobalConfig>]
    return: { success: boolean; error?: string }
  }
  'config:get-vela-home': {
    args: []
    return: string
  }
}

// ===== 窗口控制 =====
export interface WindowChannels {
  'window:minimize': {
    args: []
    return: { success: boolean }
  }
  'window:toggle-maximize': {
    args: []
    return: { success: boolean; maximized?: boolean }
  }
  'window:close': {
    args: []
    return: { success: boolean }
  }
}

export interface GlobalConfig {
  theme: string
  locale?: Locale
  defaultModelId: string | null
  defaultEmbeddingModelId?: string | null
  editorFontSize: number
  editorFontFamily: string
  autoSaveInterval: number
  proxy?: {
    enabled: boolean
    type: 'http' | 'socks5'
    host: string
    port: number
  }
}

export type AppErrorCode =
  | 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE'
  | 'PROJECT_NOT_OPEN'
  | 'EMBEDDING_MODEL_NOT_CONFIGURED'

export interface AppFailure {
  success: false
  errorCode: AppErrorCode
  error?: string
}

export type AppResult<T> = T | AppFailure

// ===== 项目管理 =====
export interface ProjectChannels {
  'project:create': {
    args: [config: { name: string; path: string; genre: string; targetAudience: string }]
    return: { success: boolean; projectId: string; projectPath?: string; error?: string }
  }
  'project:open': {
    args: [projectPath: string]
    return: { success: boolean; project: ProjectData | null; error?: string }
  }
  'project:save': {
    args: [projectId: string, data: Partial<ProjectData>]
    return: { success: boolean; error?: string }
  }
  'project:update-config': {
    args: [projectId: string, data: Partial<ProjectData>]
    return: { success: boolean; error?: string }
  }
  'project:recent-list': {
    args: []
    return: Array<{ name: string; path: string; updatedAt: string }>
  }
  'project:delete': {
    args: [projectPath: string]
    return: { success: boolean; error?: string }
  }
  'dialog:select-folder': {
    args: []
    return: string | null
  }
}

// ===== 文件系统 =====
export interface FileChannels {
  'fs:read-file': {
    args: [filePath: string]
    return: { success: boolean; content: string; error?: string }
  }
  'fs:write-file': {
    args: [filePath: string, content: string]
    return: { success: boolean; error?: string }
  }
  'fs:list-dir': {
    args: [dirPath: string]
    return: FileNode[]
  }
  'fs:mkdir': {
    args: [dirPath: string]
    return: { success: boolean; error?: string }
  }
  'fs:check-exists': {
    args: [filePath: string]
    return: boolean
  }
  'fs:read-json': {
    args: [filePath: string]
    return: { success: boolean; data: unknown; error?: string }
  }
  'fs:write-json': {
    args: [filePath: string, data: unknown]
    return: { success: boolean; error?: string }
  }
}

// ===== LLM 调用 =====
export interface LLMChannels {
  'llm:generate': {
    args: [request: LLMRequest]
    return: LLMResponse
  }
  'llm:generate-stream': {
    args: [requestId: string, request: LLMRequest]
    return: { requestId: string; started: boolean }
  }
  'llm:cancel': {
    args: [requestId: string]
    return: { success: boolean }
  }
  'llm:list-models': {
    args: []
    return: ModelProfile[]
  }
  'llm:save-model': {
    args: [model: ModelProfile]
    return: { success: boolean }
  }
  'llm:delete-model': {
    args: [modelId: string]
    return: { success: boolean }
  }
  'llm:set-default-model': {
    args: [modelId: string | null]
    return: { success: boolean; error?: string }
  }
  'llm:get-default-model': {
    args: []
    return: string | null
  }
  'llm:set-default-embedding-model': {
    args: [modelId: string | null]
    return: { success: boolean; error?: string }
  }
  'llm:get-default-embedding-model': {
    args: []
    return: string | null
  }
  'llm:test-connection': {
    args: [model: ModelProfile]
    return: { success: boolean; error?: string }
  }
}

export interface LLMStreamEvents {
  'llm:stream-chunk': { requestId: string; chunk: string }
  'llm:stream-done': { requestId: string; fullText: string; usage?: TokenUsage }
  'llm:stream-error': { requestId: string; error: string }
}

// ===== 公共数据类型 =====
export interface ProjectData {
  id: string
  name: string
  path: string
  novelConfig: NovelConfig
  characterStates: string
  createdAt: string
  updatedAt: string
}

export interface NovelConfig {
  genre: string
  subGenre: string
  targetAudience: string
  totalChapters: number
  wordsPerChapter: number
  plotStructure: 'three_act' | 'heros_journey' | 'save_the_cat' | 'kishotenketsu' | 'multi_thread' | 'freeform'
  narrativePOV: 'third_limited' | 'first_person' | 'third_omniscient' | 'multi_pov'
  coreOutline: string
  worldSetting: string
  goldenFinger: string
  protagonistProfile: string
  globalGuidance: string
  writingStyle?: string
  referenceWorks?: string
}

export interface FileNode {
  name: string
  path: string
  isDir: boolean
  children?: FileNode[]
}

export interface LLMRequest {
  modelId: string
  messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>
  temperature?: number
  maxTokens?: number
  stream?: boolean
  responseFormat?: { type: 'json_object' | 'text' }
  thinking?: boolean
}

export interface LLMResponse {
  success: boolean
  content: string
  usage?: TokenUsage
  error?: string
}

export interface TokenUsage {
  promptTokens: number
  completionTokens: number
  totalTokens: number
}

export interface ModelProfile {
  id: string
  name: string
  provider: 'openai' | 'gemini' | 'deepseek' | 'ollama' | 'bigmodel' | 'custom'
  protocol: 'openai' | 'gemini'
  modelName: string
  apiKey: string
  baseUrl: string
  temperature: number
  maxTokens: number
  purposes: Array<'generation' | 'refinement' | 'summary' | 'embedding'>
}

export interface ProjectClearOptions {
  creativeFields?: boolean
  blueprints?: boolean
  generatedText?: boolean
}

export type ProjectClearScope = 'creativeFields' | 'blueprints' | 'generatedText'

// ===== 引入 DB 类型 =====
import type { ProjectCoreData } from '../../electron/repositories/project-core-repository'
import type { BlueprintData } from '../../electron/repositories/blueprint-repository'
import type { CharacterData, CharacterStateData } from '../../electron/repositories/character-repository'
import type { DraftMeta, DraftFull } from '../../electron/repositories/draft-repository'
import type { RevisionMeta, RevisionFull } from '../../electron/repositories/revision-repository'
import type { ReviewMeta, ReviewFull } from '../../electron/repositories/review-repository'
import type { PostProcessRunData, PostProcessStepData } from '../../electron/repositories/post-process-repository'

// ===== 数据库操作 =====
export interface DatabaseChannels {
  'db:close': { args: []; return: { success: boolean } }

  // 1. project_core
  'db:project-core-get': { args: []; return: ProjectCoreData | null }
  'db:project-core-update': { args: [data: Partial<ProjectCoreData>]; return: { success: boolean; error?: string } }
  'db:project-clear-generated-data': { args: [options: ProjectClearOptions]; return: { success: boolean; cleared?: ProjectClearScope[]; physicalFilesDeleted?: number; error?: string } }

  // 2. blueprints
  'db:blueprint-get-all': { args: []; return: BlueprintData[] }
  'db:blueprint-get': { args: [chapterNumber: number]; return: BlueprintData | null }
  'db:blueprint-upsert': { args: [data: BlueprintData]; return: { success: boolean; error?: string } }
  'db:blueprint-upsert-many': { args: [items: BlueprintData[]]; return: { success: boolean; error?: string } }
  'db:blueprint-update-notes': { args: [chapterNumber: number, notes: string]; return: { success: boolean; error?: string } }
  'db:blueprint-delete': { args: [chapterNumber: number]; return: { success: boolean; error?: string } }
  'db:blueprint-clear-all': { args: []; return: { success: boolean; error?: string } }

  // 3. characters
  'db:character-get-all': { args: []; return: CharacterData[] }
  'db:character-upsert': { args: [data: CharacterData]; return: { success: boolean; error?: string } }
  'db:character-save-all': { args: [items: CharacterData[]]; return: { success: boolean; error?: string } }
  'db:character-delete': { args: [name: string]; return: { success: boolean; error?: string } }
  'db:character-update-state': { args: [name: string, state: CharacterStateData]; return: { success: boolean; error?: string } }

  // 4. drafts
  'db:draft-create': { args: [params: { chapterNumber: number; version: number; source: 'write' | 'rewrite'; content: string; wordCount: number }]; return: { success: boolean; id?: number; error?: string } }
  'db:draft-list': { args: [chapterNumber: number]; return: DraftMeta[] }
  'db:draft-get-meta': { args: [id: number]; return: DraftMeta | null }
  'db:draft-get-full': { args: [id: number]; return: DraftFull | null }
  'db:draft-get-latest': { args: [chapterNumber: number]; return: DraftMeta | null }
  'db:draft-get-finalized': { args: [chapterNumber: number]; return: DraftMeta | null }
  'db:draft-get-max-finalized-chapter': { args: []; return: number }
  'db:draft-next-version': { args: [chapterNumber: number]; return: number }
  'db:draft-update-status': { args: [id: number, status: string, wordCount?: number]; return: { success: boolean; error?: string } }
  'db:draft-update-content': { args: [id: number, content: string, wordCount: number]; return: { success: boolean; error?: string } }
  'db:draft-delete': { args: [id: number]; return: { success: boolean; error?: string } }

  // 5. revisions
  'db:revision-create': { args: [params: { baseDraftId: number; revisionIndex: number; revisionType: 'refine' | 'review-fix'; userPrompt?: string; reviewSourceId?: number; content: string; wordCount: number }]; return: { success: boolean; id?: number; error?: string } }
  'db:revision-list': { args: [baseDraftId: number]; return: RevisionMeta[] }
  'db:revision-get-pending': { args: [baseDraftId: number]; return: RevisionMeta[] }
  'db:revision-get-full': { args: [id: number]; return: RevisionFull | null }
  'db:revision-next-index': { args: [baseDraftId: number]; return: number }
  'db:revision-mark-merged': { args: [id: number, mergedToDraftId: number]; return: { success: boolean; error?: string } }
  'db:revision-mark-discarded': { args: [id: number]; return: { success: boolean; error?: string } }

  // 6. reviews
  'db:review-create': { args: [params: { baseDraftId: number; reviewIndex: number; content: string }]; return: { success: boolean; id?: number; error?: string } }
  'db:review-list': { args: [baseDraftId: number]; return: ReviewMeta[] }
  'db:review-get-latest': { args: [baseDraftId: number]; return: ReviewFull | null }
  'db:review-get-full': { args: [id: number]; return: ReviewFull | null }
  'db:review-next-index': { args: [baseDraftId: number]; return: number }

  // 7. post_process
  'db:post-process-create-run': { args: [params: { triggerSourceType: string; triggerSourceId: string; sourceLabel: string; steps: Array<{ key: string; label: string; critical: boolean }> }]; return: { success: boolean; id?: string; error?: string } }
  'db:post-process-get-latest-run': { args: [sourceType: string, sourceId: string]; return: PostProcessRunData | null }
  'db:post-process-get-steps': { args: [runId: string]; return: PostProcessStepData[] }
  'db:post-process-mark-step-ok': { args: [runId: string, stepKey: string]; return: { success: boolean; error?: string } }
  'db:post-process-mark-step-failed': { args: [runId: string, stepKey: string, errorMsg: string]; return: { success: boolean; error?: string } }
  'db:post-process-is-all-passed': { args: [sourceType: string, sourceId: string]; return: boolean }

  // 沿用旧表
  'db:log-llm-call': { args: [call: Record<string, unknown>]; return: { success: boolean } }
  'db:get-llm-stats': { args: []; return: { totalCalls: number; totalTokens: number; totalPromptTokens: number; totalCompletionTokens: number } }
  'db:get-llm-history': { args: [limit?: number]; return: unknown[] }
  'db:save-summary-snapshot': { args: [chapterNumber: number, characterStates: string]; return: { success: boolean } }
  'db:get-latest-summary': { args: []; return: { characterStates: string; chapterNumber: number } | null }
}

// ===== 知识库频道 =====
export interface KnowledgeBaseChannels {
  'kb:import-document': { args: [filePath: string]; return: { success: boolean; docId?: string; chunkCount?: number; error?: string } }
  'kb:import-folder': { args: [folderPath: string]; return: { success: boolean; importedCount: number; failedFiles: string[]; error?: string } }
  'kb:import-text': { args: [text: string, fileName: string, projectPath: string]; return: { success: boolean; docId?: string; chunkCount?: number; error?: string } }
  'kb:search': { args: [query: string, topK?: number]; return: AppResult<Array<{ text: string; score: number; fileName: string }>> }
  'kb:search-with-scope': { args: [query: string, fromChapter: number, toChapter: number, topK?: number]; return: AppResult<Array<{ text: string; score: number; fileName: string }>> }
  'kb:list-documents': { args: []; return: AppResult<Array<{ id: string; fileName: string; importedAt: string; chunkCount: number; filePath: string }>> }
  'kb:remove-document': { args: [docId: string]; return: { success: boolean } }
  'kb:clear-all': { args: []; return: { success: boolean; error?: string } }
  'kb:stats': { args: []; return: AppResult<{ documentCount: number; totalChunks: number; vectorDimension: number }> }
  'dialog:select-files': { args: []; return: string[] | null }
  'dialog:select-import-folder': { args: []; return: string | null }
  'kb:get-vectorless-count': { args: []; return: AppResult<{ count: number }> }
  'kb:backfill-vectors': { args: []; return: { success: boolean; processed: number; failed: number; error?: string } }
}

// ===== 导入小说 =====
export interface ImportChannels {
  'dialog:select-novel-files': { args: []; return: string[] | null }
  'import:split-chapters': {
    args: [filePaths: string[], options?: { separator?: string }]
    return: {
      success: boolean
      chapters: Array<{ number: number; title: string; content: string; wordCount: number }>
      totalWords: number
      error?: string
    }
  }
}

// ===== MCP =====
export interface MCPChannels {
  'mcp:load-config': { args: [configPath?: string]; return: { success: boolean; configs: unknown[]; error?: string } }
  'mcp:connect': { args: [config: Record<string, unknown>]; return: { success: boolean; error?: string } }
  'mcp:disconnect': { args: [serverId: string]; return: { success: boolean; error?: string } }
  'mcp:disconnect-all': { args: []; return: { success: boolean; error?: string } }
  'mcp:list-tools': { args: []; return: unknown[] }
  'mcp:list-resources': { args: []; return: unknown[] }
  'mcp:call-tool': { args: [serverId: string, toolName: string, args: Record<string, unknown>]; return: { success: boolean; content: string; error?: string } }
  'mcp:get-servers-status': { args: []; return: unknown[] }
  'mcp:get-config-path': { args: []; return: string }
}

// ===== 合并所有频道 =====
export type AllInvokeChannels = WindowChannels & ConfigChannels & ProjectChannels & FileChannels & LLMChannels & DatabaseChannels & KnowledgeBaseChannels & ImportChannels & MCPChannels
export type AllEventChannels = LLMStreamEvents

/** 提取 invoke 频道名 */
export type InvokeChannel = keyof AllInvokeChannels

/** 提取 event 频道名 */
export type EventChannel = keyof AllEventChannels
