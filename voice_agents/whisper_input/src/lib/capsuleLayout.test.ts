import {
  getCapsuleHostMetrics,
  getCapsuleMessageLayout,
  getCapsulePillMetrics,
} from './capsuleLayout.ts';

function assertEqual<T>(actual: T, expected: T, name: string) {
  if (actual !== expected) {
    throw new Error(`${name}: expected ${expected}, got ${actual}`);
  }
}

const winMetrics = getCapsulePillMetrics('win');
assertEqual(winMetrics.width, 196, 'windows capsule widens pill');
assertEqual(winMetrics.height, 52, 'windows capsule increases pill height');
assertEqual(winMetrics.textWidth, 104, 'windows capsule keeps side controls clear');
assertEqual(winMetrics.boxSizing, 'border-box', 'windows capsule pill width is an outer border-box metric');

const winHost = getCapsuleHostMetrics('win', false);
assertEqual(winHost.width, 220, 'windows capsule host keeps the current outer hitbox width');
assertEqual(winHost.height, 84, 'windows capsule host keeps regular height');
assertEqual(winHost.horizontalInset, 12, 'windows capsule host keeps symmetric shadow insets');
assertEqual(winHost.boxSizing, 'border-box', 'windows capsule host inset is reserved inside the native width');
assertEqual(
  winHost.width,
  winMetrics.width + winHost.horizontalInset * 2,
  'windows capsule host width derives from pill width plus symmetric side insets',
);
assertEqual(
  winHost.width - winHost.horizontalInset * 2,
  winMetrics.width,
  'windows capsule host keeps the visible pill width after reserving side insets',
);

const winHostWithTranslation = getCapsuleHostMetrics('win', true);
assertEqual(winHostWithTranslation.width, 220, 'windows translation capsule keeps the same outer width');
assertEqual(winHostWithTranslation.height, 118, 'windows translation capsule grows vertically only');
assertEqual(winHostWithTranslation.horizontalInset, 12, 'windows translation capsule keeps symmetric side insets');
assertEqual(winHostWithTranslation.boxSizing, 'border-box', 'windows translation host keeps the same inset-reserving box model');

const macMetrics = getCapsulePillMetrics('mac');
assertEqual(macMetrics.width, 176, 'mac capsule keeps existing pill width');
assertEqual(macMetrics.height, 42, 'mac capsule keeps existing pill height');
assertEqual(macMetrics.textWidth, 84, 'mac capsule keeps existing text slot');
assertEqual(macMetrics.boxSizing, 'border-box', 'mac capsule keeps the existing border-box pill model');

const macHost = getCapsuleHostMetrics('mac', false);
assertEqual(macHost.boxSizing, 'border-box', 'mac capsule host keeps the existing border-box box model');

const winErrorLayout = getCapsuleMessageLayout('win', 'error');
assertEqual(winErrorLayout.lineClamp, 2, 'windows error message allows two lines');
assertEqual(winErrorLayout.allowWrap, true, 'windows error message wraps');

const winProcessingLayout = getCapsuleMessageLayout('win', 'processing');
assertEqual(winProcessingLayout.lineClamp, 2, 'windows processing label allows two lines');
assertEqual(winProcessingLayout.allowWrap, true, 'windows processing label wraps');

const macErrorLayout = getCapsuleMessageLayout('mac', 'error');
assertEqual(macErrorLayout.lineClamp, 1, 'mac error message stays single-line');
assertEqual(macErrorLayout.allowWrap, false, 'mac error message stays nowrap');
