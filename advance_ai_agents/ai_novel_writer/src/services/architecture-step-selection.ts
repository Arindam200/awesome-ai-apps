export type ArchStepKey = 'premise' | 'characters' | 'worldbuilding' | 'synopsis'

const ARCH_STEP_ORDER: ArchStepKey[] = ['premise', 'characters', 'worldbuilding', 'synopsis']

export function createDefaultArchitectureSelection(
  archStatus: Record<string, boolean>,
  initialSelectedSteps?: ArchStepKey[],
): Record<ArchStepKey, boolean> {
  const selected = new Set<ArchStepKey>()

  for (const step of ARCH_STEP_ORDER) {
    if (!archStatus[step]) selected.add(step)
  }

  if (initialSelectedSteps) {
    for (const step of initialSelectedSteps) {
      selected.add(step)
    }
  }

  return {
    premise: selected.has('premise'),
    characters: selected.has('characters'),
    worldbuilding: selected.has('worldbuilding'),
    synopsis: selected.has('synopsis'),
  }
}
