import { FinanceDataService } from '../nebius-ai/FinanceDataService';
import { NebiusAIService } from '../nebius-ai/NebiusAIService';
import { WebSearchService } from './WebSearchService';
import { StateService, IStateOperations } from './StateService';
import { ConfigService } from './ConfigService';

export class ServiceFactory {
  private static financeDataService: FinanceDataService | undefined;
  private static webSearchService: WebSearchService | undefined;
  private static nebiusAIService: NebiusAIService | undefined;

  public static getFinanceDataService(configService?: ConfigService): FinanceDataService {
    if (!this.financeDataService) {
      this.financeDataService = new FinanceDataService(configService);
    }
    return this.financeDataService;
  }

  public static getWebSearchService(apiKey?: string, searchUrl?: string): WebSearchService {
    if (!this.webSearchService) {
      this.webSearchService = new WebSearchService(apiKey, searchUrl);
    }
    return this.webSearchService;
  }

  public static getNebiusAIService(apiKey?: string, baseURL?: string, model?: string): NebiusAIService {
    if (!this.nebiusAIService) {
      this.nebiusAIService = new NebiusAIService(apiKey, baseURL, model);
    }
    return this.nebiusAIService;
  }

  public static createStateService(state: IStateOperations, defaultScope: string): StateService {
    return new StateService(state, defaultScope);
  }

  public static reset(): void {
    this.financeDataService = undefined;
    this.webSearchService = undefined;
    this.nebiusAIService = undefined;
  }
} 