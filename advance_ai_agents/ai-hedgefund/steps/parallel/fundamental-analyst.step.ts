import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { ServiceFactory } from '../../services/utils/ServiceFactory';
import { AnalysisInput } from '../../services/types';

export const config: EventConfig = {
  type: 'event',
  name: 'fundamental-analyst',
  description: 'Performs fundamental analysis on financial data',
  subscribes: ['parallel.analyses.started'],
  emits: [{
    topic: 'fundamental.analysis.completed',
    label: 'Fundamental analysis completed'
  }],
  input: z.object({
    query: z.string().optional(),
    timestamp: z.string(),
    response: z.any(),
    analysisInput: z.any().optional(),
    generalAnalysis: z.any().optional(),
    traceId: z.string().optional()
  }),
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['fundamental-analyst'] = async (input, { logger, emit, state, traceId }) => {
  logger.info('Starting fundamental analysis', { traceId });
  
  try {
    const stateService = ServiceFactory.createStateService(state, traceId);
    
    const { query, analysisInput } = input;
    
    if (!analysisInput) {
      logger.warn('No analysis input available for fundamental analysis');
      
      await emit({
        topic: 'fundamental.analysis.completed',
        data: {
          query: input.query,
          timestamp: input.timestamp,
          analysis: null,
          error: 'No analysis input available',
        }
      });
      return;
    }
    
    const nebiusService = ServiceFactory.getNebiusAIService();
    
    const fundamentalAnalysis = await nebiusService.performFundamentalAnalysis(analysisInput as AnalysisInput);
    
    await stateService.set('fundamental.analysis', fundamentalAnalysis);
    
    logger.info('Fundamental analysis completed');
    await emit({
      topic: 'fundamental.analysis.completed',
      data: {
        query: query,
        timestamp: input.timestamp,
        analysis: {
          ...fundamentalAnalysis,
          type: 'fundamental'
        },
      }
    });
    
  } catch (error) {
    logger.error('Fundamental analysis failed', { error });
    await emit({
      topic: 'fundamental.analysis.completed',
      data: {
        query: input.query,
        timestamp: input.timestamp,
        analysis: null
      }
    });
  }
}; 