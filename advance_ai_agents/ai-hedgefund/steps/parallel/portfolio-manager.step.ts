import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { ServiceFactory } from '../../services/utils/ServiceFactory';
import { AnalysisInput } from '../../services/types';

export const config: EventConfig = {
  type: 'event',
  name: 'portfolio-manager',
  description: 'Performs portfolio management analysis on financial data',
  subscribes: ['parallel.analyses.started'],
  emits: [{
    topic: 'portfolio.analysis.completed',
    label: 'Portfolio analysis completed'
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

export const handler: Handlers['portfolio-manager'] = async (input, { logger, emit, state, traceId }) => {
  logger.info('Starting portfolio analysis', { traceId });
  
  try {
    const stateService = ServiceFactory.createStateService(state, traceId);
    
    const { analysisInput } = input;
    
    if (!analysisInput) {
      logger.warn('No analysis input available for portfolio analysis', { traceId });
      
      await emit({
        topic: 'portfolio.analysis.completed',
        data: {
          query: input.query,
          timestamp: input.timestamp,
          analysis: null
        }
      });
      return;
    }
    
    const nebiusService = ServiceFactory.getNebiusAIService();  
   
    const portfolioAnalysis = await nebiusService.performPortfolioAnalysis(analysisInput as AnalysisInput);
    
    await stateService.set('portfolio.analysis', portfolioAnalysis);
    
    
    await emit({
      topic: 'portfolio.analysis.completed',
      data: {
        query: input.query,
        timestamp: input.timestamp,
        analysis: {
          ...portfolioAnalysis,
          type: 'portfolio'
        }
      }
    });
    
  } catch (error) {
    logger.error('Portfolio analysis failed', { error });
    await emit({
      topic: 'portfolio.analysis.completed',
      data: {
        query: input.query,
        timestamp: input.timestamp,
        analysis: null
      }
    });
  }
}; 