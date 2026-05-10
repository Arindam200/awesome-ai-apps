import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { ServiceFactory } from '../../services/utils/ServiceFactory';
import { FinanceDataCompletionData } from '../../services/types';


export const config: EventConfig = {
  type: 'event',
  name: 'finance-data',
  description: 'Retrieves financial data related to stocks and companies',
  subscribes: ['query.received'],
  emits: ['finance.data.completed'],
  input: z.object({
    query: z.string().trim().min(1, 'Query must not be empty')
  }),
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['finance-data'] = async (input, { emit, logger, state, traceId }) => {
  
  try {
    const financeDataService = ServiceFactory.getFinanceDataService();
    
    const stateService = ServiceFactory.createStateService(state, traceId);
    
    const symbols = await financeDataService.extractPotentialSymbols(input.query);
    
    if (symbols.length === 0) {
      logger.info('No stock symbols found in query', { query: input.query });
      
      const noResultsData: FinanceDataCompletionData = {
        query: input.query,
        symbols: [],
        resultCount: 0,
        resultSummary: 'No stock symbols identified in the query',
      };
      
      await emit({
        topic: 'finance.data.completed',
        data: noResultsData
      });
      
      return;
    }
    
    const results = await Promise.allSettled(  
      symbols.map(symbol => financeDataService.getFinancialData(symbol))  
    );  
    
    const financialData = results  
      .filter((result): result is PromiseFulfilledResult<any> => result.status === 'fulfilled')  
      .map(result => result.value);  
    
    const failedSymbols = symbols.filter((_, index) => results[index].status === 'rejected');  
    if (failedSymbols.length > 0) {  
      logger.warn('Failed to retrieve data for some symbols', { failedSymbols });  
    }
    
    await stateService.set('finance.data', financialData);
    
    const completionData: FinanceDataCompletionData = {
      query: input.query,
      symbols,
      resultCount: financialData.length,
      resultSummary: `Retrieved data for ${symbols.join(', ')}`
    };
    
    await emit({
      topic: 'finance.data.completed',
      data: completionData
    });
    
  } catch (error) {
    logger.error('Finance data retrieval failed', { error });
    await emit({
      topic: 'finance.data.completed',
      data: {
        query: input.query,
        symbols: [],
        resultCount: 0,
        resultSummary: 'Failed to retrieve finance data',
      }
    });
  }
};
