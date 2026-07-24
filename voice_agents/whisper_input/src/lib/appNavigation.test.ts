import { APP_TABS, normalizeAppTab } from './appNavigation';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

assert(
  APP_TABS.join(',') === 'overview,history,vocab,style,settings',
  `main navigation should expose overview,history,vocab,style,settings, got ${APP_TABS.join(',')}`,
);

assert(
  normalizeAppTab('settings') === 'settings',
  'settings must normalize as a first-class tab',
);

assert(
  normalizeAppTab('unknown') === 'overview',
  'unknown tabs should fall back to overview',
);
