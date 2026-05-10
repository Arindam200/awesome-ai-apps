import { ApiRouteConfig, Handlers } from 'motia';

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'finance-result-api',
  description: 'Retrieves the results of a financial analysis by trace ID',
  path: '/finance-result/:traceId',
  method: 'GET',
  virtualSubscribes: ['flow.started', 'result.ready.for.api'],
  emits: [{
    topic: 'result.retrieved',
    label: 'Result retrieved'
  }],
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['finance-result-api'] = async (req, { logger, state, traceId, emit  }) => {

  const requestTraceId = req.pathParams.traceId;  
  if (!requestTraceId || !String(requestTraceId).trim()) {  
    return { status: 400, body: { error: 'traceId path parameter is required' } };  
  }
  try {
    logger.info('Attempting to retrieve results', { requestTraceId, contextTraceId: traceId });

    const [  
      queryResult,  
      responseData,  
      comprehensiveAnalysis,  
      comprehensiveResults,  
      apiResult  
    ] = await Promise.all([  
      state.get(requestTraceId, 'query.result'),  
      state.get(requestTraceId, 'response.data'),  
      state.get(requestTraceId, 'comprehensive.analysis'),  
      state.get(requestTraceId, 'comprehensive.results'),  
      state.get(requestTraceId, 'api.result')  
    ]);  

    const storedResult =  
      apiResult || comprehensiveResults || queryResult || responseData || comprehensiveAnalysis;
    
    if (!storedResult) {
      logger.warn('No results found for traceId', { requestTraceId });
      return { 
        status: 404, 
        body: { 
          error: 'No results found',
          message: 'No analysis results found for the provided trace ID'
        }
      };
    }
  
    const result = {
      traceId: requestTraceId,
      status: 'completed',
      comprehensiveReport: storedResult,
    };
    
    logger.info('Results retrieved successfully', { requestTraceId });
    
    return { 
      status: 200, 
      body: result
    };
    
  } catch (error) {
    logger.error('Result retrieval failed', { error, requestTraceId });
    
    return { 
      status: 500, 
      body: { 
        error: 'Failed to retrieve results for traceId: ' + requestTraceId,
        message: 'Unable to retrieve results for trace ID: ${requestTraceId}'
      }
    };
  }
}; 