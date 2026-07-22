import type { EventPayloadMap } from '../../shared/event-bus'

export function shouldRefreshBlueprints(resources: EventPayloadMap['REFRESH_RESOURCE']['resources']): boolean {
  return resources.includes('all') || resources.includes('blueprints')
}
