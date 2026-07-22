/**
 * Vela 嵌入服务 — 主进程使用
 *
 * 提供文本向量化能力（调用远程 Embedding API）
 * 支持 OpenAI 和 Gemini 两种 Embedding API
 *
 * 注意：向量存储和检索能力已迁移至 vector-store.ts (LanceDB)
 * 本模块仅保留 Embedding API 调用和文本分块功能
 */

// ===== Embedding API 调用 =====

/** OpenAI Embedding API */
export async function embedOpenAI(
  texts: string[],
  model: { baseUrl: string; apiKey: string; modelName?: string },
): Promise<number[][]> {
  const embeddingModel = model.modelName || 'text-embedding-3-small'
  const url = model.baseUrl.replace(/\/$/, '') + '/embeddings'
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${model.apiKey}`,
    },
    body: JSON.stringify({
      model: embeddingModel,
      input: texts,
    }),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`OpenAI Embedding 调用失败 (${res.status}): ${text}`)
  }

  const data = await res.json() as {
    data: Array<{ embedding: number[]; index: number }>
  }

  // 按 index 排序确保顺序一致
  return data.data
    .sort((a, b) => a.index - b.index)
    .map((d) => d.embedding)
}

/** Gemini Embedding API */
export async function embedGemini(
  texts: string[],
  model: { baseUrl: string; apiKey: string; modelName?: string },
): Promise<number[][]> {
  const embeddingModel = model.modelName || 'text-embedding-004'
  const baseUrl = model.baseUrl.replace(/\/$/, '')

  // Gemini batchEmbedContents 支持批量
  const url = `${baseUrl}/v1beta/models/${embeddingModel}:batchEmbedContents`
  const requests = texts.map((text) => ({
    model: `models/${embeddingModel}`,
    content: { parts: [{ text }] },
    taskType: 'RETRIEVAL_DOCUMENT',
  }))

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-goog-api-key': model.apiKey,
    },
    body: JSON.stringify({ requests }),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Gemini Embedding 调用失败 (${res.status}): ${text}`)
  }

  const data = await res.json() as {
    embeddings: Array<{ values: number[] }>
  }

  return data.embeddings.map((e) => e.values)
}

/** 统一的 Embedding 调用接口 */
export async function generateEmbeddings(
  texts: string[],
  protocol: 'openai' | 'gemini',
  model: { baseUrl: string; apiKey: string; modelName?: string },
): Promise<number[][]> {
  // 空文本处理
  if (texts.length === 0) return []

  // 批量限制：每次最多 50 条
  const batchSize = protocol === 'gemini' ? 100 : 50
  const results: number[][] = []

  for (let i = 0; i < texts.length; i += batchSize) {
    const batch = texts.slice(i, i + batchSize)
    const embeddings = protocol === 'gemini'
      ? await embedGemini(batch, model)
      : await embedOpenAI(batch, model)
    results.push(...embeddings)
  }

  return results
}

// ===== 文本分块 =====

/** 将文本按段落分块，每块约 maxChars 字符 */
export function chunkText(
  text: string,
  maxChars: number = 500,
  overlap: number = 50,
): string[] {
  // 先按段落分割
  const paragraphs = text.split(/\n\s*\n/).filter((p) => p.trim().length > 0)

  const chunks: string[] = []
  let currentChunk = ''

  for (const para of paragraphs) {
    // 如果段落本身就超过 maxChars，按句号分割
    if (para.length > maxChars) {
      if (currentChunk) {
        chunks.push(currentChunk.trim())
        currentChunk = ''
      }
      // 按句号分割长段落
      const sentences = para.split(/(?<=[。！？.!?])\s*/)
      let sentenceChunk = ''
      for (const sentence of sentences) {
        if (sentenceChunk.length + sentence.length > maxChars && sentenceChunk.length > 0) {
          chunks.push(sentenceChunk.trim())
          // 保留 overlap
          sentenceChunk = sentenceChunk.slice(-overlap) + sentence
        } else {
          sentenceChunk += sentence
        }
      }
      if (sentenceChunk.trim()) {
        currentChunk = sentenceChunk
      }
      continue
    }

    // 累积段落
    if (currentChunk.length + para.length > maxChars && currentChunk.length > 0) {
      chunks.push(currentChunk.trim())
      // 保留 overlap
      currentChunk = currentChunk.slice(-overlap) + '\n\n' + para
    } else {
      currentChunk += (currentChunk ? '\n\n' : '') + para
    }
  }

  if (currentChunk.trim()) {
    chunks.push(currentChunk.trim())
  }

  return chunks.length > 0 ? chunks : [text.trim()]
}
