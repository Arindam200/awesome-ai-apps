import { DEFAULT_VOCAB_PRESETS, vocabPresetsEqual } from './vocabPresets';

function assertEqual(actual: boolean, expected: boolean, name: string) {
  if (actual !== expected) {
    throw new Error(`${name}: expected ${expected}, got ${actual}`);
  }
}

const base = DEFAULT_VOCAB_PRESETS[0];
if (!base) {
  throw new Error('expected a builtin vocabulary preset');
}

const reordered = {
  phrases: [...base.phrases],
  name: base.name,
  id: base.id,
};

assertEqual(
  vocabPresetsEqual(base, reordered),
  true,
  'same preset values compare equal despite object key order',
);

assertEqual(
  vocabPresetsEqual(base, { ...base, phrases: [...base.phrases, 'new phrase'] }),
  false,
  'additional phrase requires a persisted override',
);

assertEqual(
  vocabPresetsEqual(base, { ...base, name: `${base.name} custom` }),
  false,
  'renamed preset requires a persisted override',
);
