import { ILLMProvider, LLMGenerateOptions, LLMResponse, LLMStreamOptions } from './provider.interface'
import { ModelProfile } from '../../src/shared/ipc-channels'

export class OpenAIProvider implements ILLMProvider {
  private stripThinking(content: string): string {
    return content
      .replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '')
      .replace(/^[\s\S]*?<\/think>\s*/i, '')
      .replace(/<\/?think>/gi, '')
      .trim()
  }

  private buildUrl(baseUrl: string): string {
    const base = baseUrl.replace(/\/$/, '')
    if (base.endsWith('/v1/chat/completions')) {
      return base
    }
    // 如果 baseUrl 已经带了完整 /v1/chat 路径，直接用
    if (base.endsWith('/v1/chat')) {
      return `${base}/completions`
    }
    if (base.endsWith('/v1')) {
      return `${base}/chat/completions`
    }
    // 否则补全完整路径
    return `${base}/v1/chat/completions`
  }

  async generate(model: ModelProfile, messages: Array<{ role: string; content: string }>, opts: LLMGenerateOptions): Promise<LLMResponse> {
    try {
      const url = this.buildUrl(model.baseUrl)

      const body: Record<string, unknown> = {
        model: model.modelName,
        messages,
        max_tokens: opts.maxTokens ?? model.maxTokens,
        stream: false,
      }

      // 思考模式下 temperature/top_p 等参数不生效（DeepSeek 会静默忽略），仅在非思考模式下传递
      if (opts.thinking) {
        // thinking 参数直接放在请求体顶层（非 extra_body，那是 OpenAI SDK 层概念）
        body.thinking = { type: 'enabled' }
      } else {
        body.temperature = opts.temperature ?? model.temperature
      }

      if (opts.responseFormat) body.response_format = opts.responseFormat

      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${model.apiKey}`,
        },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const text = await res.text()
        return { success: false, content: '', error: `API 调用失败 (${res.status}): ${text}` }
      }

      const data = await res.json() as {
        choices: Array<{ message: { content: string; reasoning_content?: string } }>
        usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
      }

      const finalContent = this.stripThinking(data.choices?.[0]?.message?.content ?? '')

      return {
        success: true,
        content: finalContent,
        usage: data.usage ? {
          promptTokens: data.usage.prompt_tokens,
          completionTokens: data.usage.completion_tokens,
          totalTokens: data.usage.total_tokens,
        } : undefined,
      }
    } catch (error) {
      return { success: false, content: '', error: String(error) }
    }
  }

  async generateStream(model: ModelProfile, messages: Array<{ role: string; content: string }>, opts: LLMStreamOptions): Promise<void> {
    try {
      const url = this.buildUrl(model.baseUrl)

      const body: Record<string, unknown> = {
        model: model.modelName,
        messages,
        max_tokens: opts.maxTokens ?? model.maxTokens,
        stream: true,
      }

      // 思考模式下 temperature/top_p 等参数不生效（DeepSeek 会静默忽略），仅在非思考模式下传递
      if (opts.thinking) {
        body.thinking = { type: 'enabled' }
      } else {
        body.temperature = opts.temperature ?? model.temperature
      }

      if (opts.responseFormat) body.response_format = opts.responseFormat

      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${model.apiKey}`,
        },
        body: JSON.stringify(body),
        signal: opts.signal,
      })

      if (!res.ok) {
        const text = await res.text()
        opts.onError(`API 调用失败 (${res.status}): ${text}`)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        opts.onError('无法读取响应流')
        return
      }

      const decoder = new TextDecoder()
      let fullText = ''
      let isThinking = false
      let buffer = ''

      const hasMore = true
      while (hasMore) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const segments = buffer.split('\n')
        buffer = segments.pop() ?? ''
        const lines = segments.filter((l) => l.startsWith('data: '))

        for (const line of lines) {
          const json = line.slice(6).trim()
          if (json === '[DONE]') continue
          try {
            const parsed = JSON.parse(json) as {
              choices: Array<{ delta: { content?: string, reasoning_content?: string } }>
            }
            const delta = parsed.choices?.[0]?.delta

            let emitChunk = ''

            // 如果存在思维链内容
            if (delta?.reasoning_content) {
              if (!isThinking) {
                isThinking = true
                emitChunk += '<think>\n'
              }
              emitChunk += delta.reasoning_content
            } 
            
            // 如果开始输出正文
            if (delta?.content !== undefined && delta?.content !== null) {
              if (isThinking) {
                isThinking = false
                emitChunk += '\n</think>\n\n'
              }
              if (delta?.content) {
                emitChunk += delta.content
              }
            }

            if (emitChunk) {
              fullText += emitChunk
              opts.onChunk(emitChunk)
            }
          } catch {
            // ignore
          }
        }
      }

      if (isThinking) {
        const closeTag = '\n</think>\n\n'
        fullText += closeTag
        opts.onChunk(closeTag)
      }

      opts.onDone(this.stripThinking(fullText))
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        opts.onError('已取消生成')
      } else {
        opts.onError(String(error))
      }
    }
  }
}
