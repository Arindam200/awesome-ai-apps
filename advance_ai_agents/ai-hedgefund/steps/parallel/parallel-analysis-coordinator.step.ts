import { EventConfig, Handlers } from 'motia';
import { z } from 'zod';
import { ServiceFactory } from '../../services/utils/ServiceFactory';
import { createComprehensiveReport } from '../../services/utils/helper-functions';

// Configuration for analysis types
interface AnalysisConfig {
  key: string;
  stateKey: string;
  analysisKey: string;
  topic: string;
}

const ANALYSIS_CONFIGS: AnalysisConfig[] = [
  { key: 'general', stateKey: 'ai.analysis', analysisKey: 'generalAnalysis', topic: 'general.analysis.completed' },
  { key: 'fundamental', stateKey: 'fundamental.analysis', analysisKey: 'fundamentalAnalysis', topic: 'fundamental.analysis.completed' },
  { key: 'portfolio', stateKey: 'portfolio.analysis', analysisKey: 'portfolioAnalysis', topic: 'portfolio.analysis.completed' },
  { key: 'risk', stateKey: 'risk.analysis', analysisKey: 'riskAnalysis', topic: 'risk.analysis.completed' },
  { key: 'technical', stateKey: 'technical.analysis', analysisKey: 'technicalAnalysis', topic: 'technical.analysis.completed' }
];

export const config: EventConfig = {
  type: 'event',
  name: 'parallel-analysis-coordinator',
  description: 'Coordinates all parallel analyses and creates comprehensive report',
  subscribes: ANALYSIS_CONFIGS.map(config => config.topic),
  emits: ['comprehensive.analysis.completed'],
  input: z.object({}),
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['parallel-analysis-coordinator'] = async (input: any, { logger, emit, state, traceId }: any) => {
  
  try {
    const stateService = ServiceFactory.createStateService(state, traceId);
    
    const originalQuery = await stateService.get('original.query');
    const timestamp = new Date().toISOString();
    
    // Use configuration to gather analyses dynamically
    const analyses: Record<string, any> = {};
    const completedAnalyses: string[] = [];
    
    for (const config of ANALYSIS_CONFIGS) {
      const analysis = await stateService.get(config.stateKey);
      if (analysis) {
        analyses[config.analysisKey] = analysis;
        completedAnalyses.push(config.key);
      }
    }
    
    if (completedAnalyses.length === 0) {  
      logger.error('No analyses completed, cannot create comprehensive report');  
      return;  
    }  

    const coordinationCompleted = await stateService.get('coordination.completed');  
    if (coordinationCompleted) {  
      logger.info('Coordination already completed, skipping duplicate processing');  
      return;  
    }  

    const expectedAnalyses = ANALYSIS_CONFIGS.map(config => config.key);
    
    if (completedAnalyses.length < expectedAnalyses.length) {  
      return;  
    }  

    logger.info('All parallel analyses complete, gathering results and creating comprehensive report');
    
    // Store analyses using configuration
    for (const config of ANALYSIS_CONFIGS) {
      if (analyses[config.analysisKey]) {
        await stateService.set(`analysis.${config.key}`, analyses[config.analysisKey]);
      }
    }
    
    const comprehensiveReport = createComprehensiveReport(analyses);
    
    await stateService.set('comprehensive.analysis', comprehensiveReport);
    await stateService.set('comprehensive.results', {
      query: originalQuery,
      timestamp,
      comprehensiveReport,
      ...analyses,
      status: 'completed',
      completedAt: new Date().toISOString()
    });
    
    await stateService.set('query.result', {
      query: originalQuery,
      timestamp,
      comprehensiveReport,
      status: 'completed'
    });
    
    await stateService.set('coordination.completed', true);
    
    logger.info('Comprehensive analysis completed successfully');
    
    await emit({
      topic: 'comprehensive.analysis.completed',
      data: {
        query: originalQuery,
        comprehensiveReport,
        status: 'success'
      }
    });
    
  } catch (error) {
    logger.error('Parallel analysis coordination failed', { error });
    await emit({
      topic: 'comprehensive.analysis.completed',
      data: {
        status: 'error'
      }
    });
  }
}; 