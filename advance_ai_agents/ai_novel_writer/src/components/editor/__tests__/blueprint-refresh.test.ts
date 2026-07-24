import { describe, expect, it } from 'vitest'

import { shouldRefreshBlueprints } from '../blueprint-refresh'

describe('shouldRefreshBlueprints', () => {
  it('refreshes for blueprint resource updates', () => {
    expect(shouldRefreshBlueprints(['blueprints'])).toBe(true)
  })

  it('refreshes for all resource updates', () => {
    expect(shouldRefreshBlueprints(['all'])).toBe(true)
  })

  it('does not refresh for unrelated resource updates', () => {
    expect(shouldRefreshBlueprints(['fileTree', 'drafts'])).toBe(false)
  })
})
