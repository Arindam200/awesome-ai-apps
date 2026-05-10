import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { ServiceFactory } from '../../services/utils/ServiceFactory';
import { AnalysisInput } from '../../services/types';

const inputSchema = z.object({
  query: z.string().optional(),
  timestamp: z.string(),
  response: z.any(),
  analysisInput: z.any().optional(),
  generalAnalysis: z.any().optional(),
  traceId: z.string().optional()
});

export const config: EventConfig = {
  type: 'event',
  name: 'technical-analyst',
  description: 'Performs technical analysis on financial data',
  subscribes: ['parallel.analyses.started'],
  emits: [{
    topic: 'technical.analysis.completed',
    label: 'Technical analysis completed'
  }],
  input: inputSchema,
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['technical-analyst'] = async (input, { logger, emit, state, traceId }) => {
  logger.info('Starting technical analysis');
  
  try {
    const stateService = ServiceFactory.createStateService(state, traceId);
    
    const { query, analysisInput } = input;
    
    if (!analysisInput) {
      logger.warn('No analysis input available for technical analysis');
      
      await emit({
        topic: 'technical.analysis.completed',
        data: {
          query: input.query,
          timestamp: input.timestamp,
          analysis: null,
          error: 'No analysis input available'
        }
      });
      return;
    }
    
    const nebiusService = ServiceFactory.getNebiusAIService();
    
    const technicalAnalysis = await nebiusService.performTechnicalAnalysis(analysisInput as AnalysisInput);
    
    await stateService.set('technical.analysis', technicalAnalysis);
    
    logger.info('Technical analysis completed');
    
    await emit({
      topic: 'technical.analysis.completed',
      data: {
        query: query,
        timestamp: input.timestamp,
        analysis: {
          ...technicalAnalysis,
          type: 'technical'
        },
      }
    });
    
  } catch (error) {
    logger.error('Technical analysis failed', { error });
    await emit({
      topic: 'technical.analysis.completed',
      data: {
        query: input.query,
        timestamp: input.timestamp,
        analysis: null
      }
    });
  }
}; 