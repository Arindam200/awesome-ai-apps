import { describe, expect, it } from 'vitest'

import { createDefaultArchitectureSelection } from '../architecture-step-selection'

describe('createDefaultArchitectureSelection', () => {
  it('selects all missing architecture steps from the overview entry', () => {
    expect(createDefaultArchitectureSelection({
      premise: false,
      characters: true,
      worldbuilding: false,
      synopsis: false,
    })).toEqual({
      premise: true,
      characters: false,
      worldbuilding: true,
      synopsis: true,
    })
  })

  it('keeps a single-file entry selected and auto-adds missing architecture blocks', () => {
    expect(createDefaultArchitectureSelection({
      premise: false,
      characters: false,
      worldbuilding: false,
      synopsis: false,
    }, ['characters'])).toEqual({
      premise: true,
      characters: true,
      worldbuilding: true,
      synopsis: true,
    })
  })

  it('does not overwrite generated blocks unless they were explicitly selected', () => {
    expect(createDefaultArchitectureSelection({
      premise: true,
      characters: false,
      worldbuilding: true,
      synopsis: false,
    }, ['characters'])).toEqual({
      premise: false,
      characters: true,
      worldbuilding: false,
      synopsis: true,
    })
  })
})
