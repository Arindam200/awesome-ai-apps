import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { ServiceFactory } from '../../services/utils/ServiceFactory';

const SaveResultInputSchema = z.object({
  query: z.string().optional(),
  comprehensiveReport: z.any().optional(),
  status: z.string().optional()
});

export const config: EventConfig = {
  type: 'event',
  name: 'save-result',
  description: 'Saves comprehensive analysis results to state for UI and API access',
  subscribes: ['comprehensive.analysis.completed'],
  emits: ['result.saved', 'result.ready.for.api'],
  input: SaveResultInputSchema,
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['save-result'] = async (input, { logger, state, traceId, emit }) => {
  try {
    const stateService = ServiceFactory.createStateService(state, traceId);
    
    const resultsSaved = await stateService.get('results.saved');
    if (resultsSaved) {
      logger.info('Results already saved, skipping duplicate processing');
      return;
    }
    
    const comprehensiveResults = await stateService.get('comprehensive.results') as any;
    const comprehensiveAnalysis = await stateService.get('comprehensive.analysis');
    const queryResult = await stateService.get('query.result') as any;
    
    if (!comprehensiveResults && !comprehensiveAnalysis && !queryResult) {
      logger.warn('No comprehensive analysis results found in state');
      return;
    }
    
    const resultData = comprehensiveResults || {
      query: queryResult?.query || input?.query || 'Unknown query',
      timestamp: queryResult?.timestamp || new Date().toISOString(),
      comprehensiveReport: comprehensiveAnalysis || input?.comprehensiveReport,
      status: queryResult?.status || input?.status || 'completed',
      completedAt: new Date().toISOString()
    };
    
    await stateService.set('ui.result', resultData); 
    await stateService.set('api.result', resultData); 
    await stateService.set('workflow.status', {
      status: 'completed',
      completedAt: new Date().toISOString()
    });
    
    await stateService.set('results.saved', true);
    
    logger.info('Comprehensive analysis results saved successfully');
    
  } catch (error) {
    logger.error('Failed to save comprehensive analysis results', { error });
    
    const stateService = ServiceFactory.createStateService(state, traceId);
    await stateService.set('workflow.status', {
      status: 'failed',
      completedAt: new Date().toISOString(),
      error: 'Failed to save results'
    });
  }
}; 