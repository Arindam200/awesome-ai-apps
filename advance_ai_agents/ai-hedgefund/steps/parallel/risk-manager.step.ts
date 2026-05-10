import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { ServiceFactory } from '../../services/utils/ServiceFactory';
import { AnalysisInput } from '../../services/types';

export const config: EventConfig = {
  type: 'event',
  name: 'risk-manager',
  description: 'Performs risk assessment and management analysis on financial data',
  subscribes: ['parallel.analyses.started'],
  emits: [{
    topic: 'risk.analysis.completed',
    label: 'Risk analysis completed'
  }],
  input: z.object({
    query: z.string().optional(),
    timestamp: z.string().datetime(),
    response: z.any(),
    analysisInput: z.any().optional(),
    generalAnalysis: z.any().optional(),
    traceId: z.string().optional()
  }),
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['risk-manager'] = async (input, { logger, emit, state, traceId }) => {
  logger.info('Starting risk analysis', { traceId });
  
  try {
    const stateService = ServiceFactory.createStateService(state, traceId);
    
    const { analysisInput } = input;
    
    if (!analysisInput) {
      await emit({
        topic: 'risk.analysis.completed',
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
    
    const riskAnalysis = await nebiusService.performRiskAnalysis(analysisInput as AnalysisInput);
    
    await stateService.set('risk.analysis', riskAnalysis);
    
    logger.info('Risk analysis completed', { traceId });
    
    await emit({
      topic: 'risk.analysis.completed',
      data: {
        timestamp: input.timestamp,
        analysis: {
          ...riskAnalysis,
          type: 'risk'
        },
        traceId: traceId
      }
    });
    
  } catch (error) {
    logger.error('Risk analysis failed', { error });
    await emit({
      topic: 'risk.analysis.completed',
      data: {
        query: input.query,
        timestamp: input.timestamp,
        analysis: null
      }
    });
  }
}; 