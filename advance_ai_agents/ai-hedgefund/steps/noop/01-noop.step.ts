import { NoopConfig } from 'motia'
export const config: NoopConfig = {
  type: 'noop',
  name: 'Result Viewer',
  description: 'View comprehensive analysis results from the workflow',
  virtualSubscribes: ['response.completed', 'comprehensive.analysis.completed', 'result.retrieved'],  
  virtualEmits: [],
  flows: ['aihedgefund-workflow'],
} 