import { describe, expect, it } from 'vitest'

import { cn } from '../utils'

describe('cn', () => {
  it('filters conditional values and merges conflicting Tailwind classes', () => {
    expect(cn('p-2', false, 'text-sm', 'p-4')).toBe('text-sm p-4')
  })
})
