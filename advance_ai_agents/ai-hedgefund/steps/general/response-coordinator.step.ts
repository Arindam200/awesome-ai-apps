import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { formatCombinedResponse } from '../../services/utils/helper-functions';
import { ResponseCompletionData } from '../../services/types';

export const config: EventConfig = {
  type: 'event',
  name: 'response-coordinator',
  description: 'Coordinates and combines results from web search and financial data',
  subscribes: ['web.search.completed', 'finance.data.completed'],
  emits: ['response.completed'],
  input: z.object({
    query: z.string(),
    resultCount: z.number().optional(),
    symbols: z.array(z.string()).optional(),
    resultSummary: z.string().optional(),
    error: z.string().optional(),
    message: z.string().optional()
  }),
  flows: ['aihedgefund-workflow']
};
    
export const handler: Handlers['response-coordinator'] = async (input, { logger, emit, state, traceId }) => {
  
  try {
    // Check if both web search and finance data are available
    const webSearchResults = await state.get(traceId, 'web.search.results'); 
    const financeData = await state.get(traceId, 'finance.data'); 
    
    // Check if coordination has already been completed
    const coordinationCompleted = await state.get(traceId, 'response.coordination.completed');
    if (coordinationCompleted) {
      logger.info('Response coordination already completed, skipping duplicate processing');
      return;
    }
    
    // Only proceed if we have both web search and finance data
    if (!webSearchResults && !financeData) {
      logger.warn('Neither web search nor finance data available, skipping coordination');
      return;
    }
    
    const formattedResponse = formatCombinedResponse(input.query, webSearchResults as any, financeData as any);
    
    const responseData: ResponseCompletionData = {
      query: input.query,
      timestamp: new Date().toISOString(),
      response: formattedResponse
    };
    
    // Mark coordination as completed to prevent duplicate processing
    await state.set(traceId, 'response.data', responseData);  
    await state.set(traceId, 'response.coordination.completed', true);  
    
    await emit({  
      topic: 'response.completed',  
      data: responseData  
    });
    
  } catch (error) {
    logger.error('Response coordination failed', { error });
    await emit({
      topic: 'response.completed',
      data: {
        query: input.query,
        timestamp: new Date().toISOString(),
        response: null
      }
    });
  }
};