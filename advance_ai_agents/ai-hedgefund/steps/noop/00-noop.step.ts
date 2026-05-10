import { NoopConfig } from 'motia'

export const config: NoopConfig = {
  type: 'noop',
  name: 'Finance Query Starter',
  description: 'Start the finance analysis workflow with a query input',
  virtualSubscribes: ['flow.started'],
  virtualEmits: ['query.received'],
  flows: ['aihedgefund-workflow'],
}
