export type KnowledgeBaseModule = typeof import('../knowledge-base')

type KnowledgeBaseImporter = () => Promise<KnowledgeBaseModule>

export interface KnowledgeBaseUnavailableResult {
  success: false
  errorCode: 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE'
}

export class KnowledgeBaseUnavailableError extends Error {
  readonly code = 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE' as const

  constructor(readonly cause: unknown) {
    super('Knowledge base native module is unavailable')
    this.name = 'KnowledgeBaseUnavailableError'
  }
}

export function createKnowledgeBaseLoader(
  importer: KnowledgeBaseImporter = () => import('../knowledge-base'),
) {
  let cachedLoad: Promise<KnowledgeBaseModule> | null = null

  const load = (): Promise<KnowledgeBaseModule> => {
    cachedLoad ??= importer().catch((error: unknown) => {
      console.error('[KnowledgeBase] native module load failed', error)
      throw new KnowledgeBaseUnavailableError(error)
    })
    return cachedLoad
  }

  return {
    load,
    async run<T>(
      operation: (module: KnowledgeBaseModule) => Promise<T> | T,
    ): Promise<T | KnowledgeBaseUnavailableResult> {
      try {
        return await operation(await load())
      } catch (error) {
        if (error instanceof KnowledgeBaseUnavailableError) {
          return {
            success: false,
            errorCode: 'KNOWLEDGE_BASE_NATIVE_UNAVAILABLE',
          }
        }
        throw error
      }
    },
  }
}

export const knowledgeBaseLoader = createKnowledgeBaseLoader()
