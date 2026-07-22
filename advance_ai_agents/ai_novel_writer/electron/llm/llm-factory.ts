import { ILLMProvider } from './provider.interface'
import { ModelProfile } from '../../src/shared/ipc-channels'
import { OpenAIProvider } from './openai-provider'
import { GeminiProvider } from './gemini-provider'

export class LLMFactory {
  static getProvider(model: ModelProfile): ILLMProvider {
    if (model.protocol === 'gemini') {
      return new GeminiProvider()
    }
    return new OpenAIProvider()
  }
}
