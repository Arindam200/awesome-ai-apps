import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { ServiceFactory } from '../../services/utils/ServiceFactory';
import { WebSearchCompletionData } from '../../services/types';

export const config: EventConfig = {
  type: 'event',
  name: 'WebSearchAgent',
  description: 'Searches the web for information related to financial queries',
  subscribes: ['query.received'],
  emits: ['web.search.completed'],
  input: z.object({
    query: z.string()
  }),
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['WebSearchAgent'] = async (input, { logger, emit, state, traceId }) => {
  
  try {
    const stateService = ServiceFactory.createStateService(state, traceId);
    
    await stateService.set('original.query', input.query);
    const webSearchService = ServiceFactory.getWebSearchService();
    const searchResponse = await webSearchService.search(input.query);
    
    await stateService.set('web.search.results', searchResponse);
    
    const completionData: WebSearchCompletionData = {
      query: input.query,
      resultCount: searchResponse.results.length,
      resultSummary: searchResponse.results.map((result: WebSearchCompletionData['results'][number]) => result.title).join(', '),
      results: searchResponse.results
    };
    
    await emit({
      topic: 'web.search.completed',
      data: completionData
    });
    
  } catch (error) {
    logger.error('Web search failed', { error });
    await emit({
      topic: 'web.search.completed',
      data: {
        query: input.query,
        resultCount: 0,
        resultSummary: 'Search failed',
        results: []
      } as WebSearchCompletionData
    });
  }
}; 