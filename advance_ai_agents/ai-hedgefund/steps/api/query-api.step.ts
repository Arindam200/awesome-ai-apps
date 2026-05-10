import { ApiRouteConfig, Handlers } from 'motia';
import { z } from 'zod';

export const config: ApiRouteConfig = {
  type: 'api',
  name: 'finance-query-api',
  description: 'Accepts stock analysis queries and initiates the financial analysis workflow',
  path: '/finance-query',
  method: 'POST',
  virtualSubscribes: ['flow.started'],
  emits: [
    {
      topic: 'query.received',
      label: 'Query received'
    }
  ],
  bodySchema: z.object({
    query: z.string().min(1, "Query must not be empty")
  }).strict(),
  flows: ['aihedgefund-workflow']
};

export const handler: Handlers['finance-query-api'] = async (req, { logger, emit, traceId }) => {

  try {
    
    await emit({
      topic: 'query.received',
      data: { query: req.body.query }
    });

    logger.info('Query received; analysis workflow initiated'); 
    return {
      status: 200,
      body: {
        query: req.body.query,
        message: 'Analysis workflow initiated successfully',
        traceId,
      }
    };
  } catch (error) {
    logger.error('Error processing query', { error });
    return {
      status: 500,
      body: {
        error: 'Failed to process query'
      }
    };
  }
};
