import defaultPresetsJson from './vocab-presets.json';
import { listVocabPresets, saveVocabPresets } from './ipc';
import type { VocabPreset, VocabPresetStore } from './types';

export const DEFAULT_VOCAB_PRESETS: VocabPreset[] = defaultPresetsJson as VocabPreset[];

export async function loadVocabPresets(): Promise<VocabPreset[]> {
  const store = await listVocabPresets();
  const builtin = new Map(DEFAULT_VOCAB_PRESETS.map(p => [p.id, p] as const));
  for (const id of store.disabledBuiltinPresetIds || []) {
    builtin.delete(id);
  }
  for (const preset of store.overrides || []) {
    if (!preset || !preset.id) continue;
    if (builtin.has(preset.id)) builtin.set(preset.id, preset);
  }
  const custom = (store.custom || []).filter(p => p && p.id);
  return [...builtin.values(), ...custom];
}

export async function persistVocabPresets(presets: VocabPreset[]) {
  const builtinMap = new Map(DEFAULT_VOCAB_PRESETS.map(p => [p.id, p] as const));
  const store: VocabPresetStore = {
    custom: [],
    overrides: [],
    disabledBuiltinPresetIds: [],
  };
  const seenBuiltin = new Set<string>();
  for (const preset of presets) {
    const base = builtinMap.get(preset.id);
    if (!base) {
      store.custom.push(preset);
      continue;
    }
    seenBuiltin.add(preset.id);
    if (JSON.stringify(base) !== JSON.stringify(preset)) {
      store.overrides.push(preset);
    }
  }
  for (const id of builtinMap.keys()) {
    if (!seenBuiltin.has(id)) {
      store.disabledBuiltinPresetIds.push(id);
    }
  }
  await saveVocabPresets(store);
}
