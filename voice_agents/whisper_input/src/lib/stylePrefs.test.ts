import {
  applyStylePreferencesNotification,
  isStyleMasterEnabled,
  rollbackDefaultAndEnabledChange,
  persistStylePreferenceChange,
  rollbackStyleEnabledChange,
  rollbackWholeStylePreferences,
  styleDefaultModePreferences,
  styleMasterFallbackModes,
  styleMasterOffPreferences,
} from './stylePrefs';
import type { UserPreferences } from './types';
import { zhCN } from '../i18n/zh-CN';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

const previousPrefs: UserPreferences = {
  hotkey: { trigger: 'rightOption', mode: 'toggle' },
  dictationHotkey: { primary: 'RightOption', modifiers: [] },
  defaultMode: 'light',
  enabledModes: ['raw', 'light', 'structured'],
  launchAtLogin: false,
  showCapsule: true,
  muteDuringRecording: false,
  microphoneDeviceName: '',
  activeAsrProvider: 'volcengine',
  activeLlmProvider: 'ark',
  llmThinkingEnabled: false,
  restoreClipboardAfterPaste: true,
  pasteShortcut: 'ctrlV',
  allowNonTsfInsertionFallback: true,
  workingLanguages: ['简体中文'],
  translationTargetLanguage: '',
  chineseScriptPreference: 'auto',
  outputLanguagePreference: 'auto',
  outputLanguagePreferenceExplicit: false,
  qaHotkey: null,
  historyEnabled: true,
  qaSaveHistory: false,
  customComboHotkey: null,
  translationHotkey: { primary: 'Shift', modifiers: [] },
  switchStyleHotkey: { primary: 'S', modifiers: ['alt'] },
  openAppHotkey: { primary: 'O', modifiers: ['alt'] },
  localAsrActiveModel: '',
  localAsrMirror: 'huggingface',
  localAsrKeepLoadedSecs: 300,
  foundryLocalAsrModel: '',
  foundryLocalRuntimeSource: 'auto',
  foundryLocalAsrLanguageHint: '',
  foundryLocalAsrKeepLoadedSecs: 300,
  historyRetentionDays: 7,
  polishContextWindowMinutes: 5,
  startMinimized: false,
  updateChannel: 'stable',
  streamingInsert: false,
  streamingInsertSaveClipboard: true,
  rightAltHotkeyMigrationVersion: 1,
};

const nextPrefs: UserPreferences = {
  ...previousPrefs,
  enabledModes: [],
};

const states: UserPreferences[] = [];
const errors: string[] = [];
let firstCurrentPrefs: UserPreferences | null = previousPrefs;
const saved = await persistStylePreferenceChange(
  nextPrefs,
  async () => {
    throw 'disk full';
  },
  update => {
    firstCurrentPrefs = typeof update === 'function' ? update(firstCurrentPrefs) : update;
    if (firstCurrentPrefs) states.push(firstCurrentPrefs);
  },
  message => errors.push(message),
  rollbackWholeStylePreferences(previousPrefs, nextPrefs),
);

assert(saved === false, 'setSettings reject should report save failure');
assert(states.length === 2, `expected optimistic state then rollback, got ${states.length} updates`);
assert(states[0] === nextPrefs, 'first state update should be the optimistic next prefs');
assert(
  states[1].enabledModes.join(',') === previousPrefs.enabledModes.join(','),
  'second state update should roll back enabled modes to previous prefs',
);
assert(errors[0] === 'disk full', `expected backend error message, got ${errors[0]}`);

let currentPrefs: UserPreferences | null = previousPrefs;
const disableLightPrefs: UserPreferences = {
  ...previousPrefs,
  enabledModes: ['raw', 'structured'],
};
const disableStructuredAfterLightPrefs: UserPreferences = {
  ...previousPrefs,
  enabledModes: ['raw'],
};
const overlapSaved = await persistStylePreferenceChange(
  disableLightPrefs,
  async () => {
    currentPrefs = disableStructuredAfterLightPrefs;
    throw 'slow failure';
  },
  update => {
    currentPrefs = typeof update === 'function' ? update(currentPrefs) : update;
  },
  () => undefined,
  rollbackStyleEnabledChange('light', previousPrefs, disableLightPrefs),
);

assert(overlapSaved === false, 'overlapped style save should still report failure');
assert(
  currentPrefs?.enabledModes.includes('light') === true,
  'failed light toggle should roll back only the light mode',
);
assert(
  currentPrefs?.enabledModes.includes('structured') === false,
  'failed light toggle should preserve newer structured edit',
);

const notifiedPrefs: UserPreferences = {
  ...previousPrefs,
  defaultMode: 'formal',
  enabledModes: ['raw', 'formal'],
};
const syncedPrefs = applyStylePreferencesNotification(previousPrefs, notifiedPrefs);
assert(syncedPrefs === notifiedPrefs, 'prefs notification should replace stale style page prefs');

const masterOffPrefs = styleMasterOffPreferences(previousPrefs);
assert(
  masterOffPrefs.enabledModes.join(',') === 'raw,light',
  `master toggle off should persist raw and current default, got ${masterOffPrefs.enabledModes.join(',')}`,
);

const masterFallback = styleMasterFallbackModes('light');
assert(
  masterFallback.join(',') === 'raw,light',
  `master toggle off should preserve raw and current default, got ${masterFallback.join(',')}`,
);
assert(
  isStyleMasterEnabled({ ...previousPrefs, enabledModes: masterFallback }) === false,
  'master toggle should render off when only raw and default remain enabled',
);
assert(
  isStyleMasterEnabled(previousPrefs) === true,
  'master toggle should render on when extra styles remain enabled',
);
const rawFallback = styleMasterFallbackModes('raw');
assert(
  rawFallback.join(',') === 'raw',
  `raw default fallback should not duplicate raw, got ${rawFallback.join(',')}`,
);


const defaultAfterMasterOff = styleDefaultModePreferences(
  { ...previousPrefs, enabledModes: ['raw', 'light'] },
  'formal',
);
assert(
  defaultAfterMasterOff.defaultMode === 'formal' && defaultAfterMasterOff.enabledModes.join(',') === 'raw,formal',
  `default change while master is off should refresh fallback modes, got ${defaultAfterMasterOff.defaultMode}/${defaultAfterMasterOff.enabledModes.join(',')}`,
);
assert(
  isStyleMasterEnabled(defaultAfterMasterOff) === false,
  'master toggle should stay off after changing default while off',
);

const defaultFromDisabledMode = styleDefaultModePreferences(
  { ...previousPrefs, enabledModes: ['raw', 'light', 'structured'] },
  'formal',
);
assert(
  defaultFromDisabledMode.defaultMode === 'formal' &&
    defaultFromDisabledMode.enabledModes.includes('formal'),
  `defaulting a disabled mode should enable it atomically, got ${defaultFromDisabledMode.defaultMode}/${defaultFromDisabledMode.enabledModes.join(',')}`,
);

let rolledBackDefaultAndEnabled: UserPreferences | null = defaultAfterMasterOff;
const rollbackDefaultAndEnabled = rollbackDefaultAndEnabledChange(
  { ...previousPrefs, enabledModes: ['raw', 'light'] },
  defaultAfterMasterOff,
);
rolledBackDefaultAndEnabled = rollbackDefaultAndEnabled(rolledBackDefaultAndEnabled);
assert(
  rolledBackDefaultAndEnabled?.defaultMode === 'light' && rolledBackDefaultAndEnabled.enabledModes.join(',') === 'raw,light',
  'failed off-state default save should roll back both default mode and enabled modes',
);

const zhStyleModes = zhCN.style.modes;
assert(
  zhStyleModes.raw.desc.includes('基础断句') &&
    zhStyleModes.raw.desc.includes('标点') &&
    zhStyleModes.raw.desc.includes('不润色') &&
    zhStyleModes.raw.desc.includes('不总结') &&
    zhStyleModes.raw.desc.includes('不扩写') &&
    zhStyleModes.raw.desc.includes('不结构化'),
  `raw desc must constrain minimal punctuation-only behavior, got: ${zhStyleModes.raw.desc}`,
);
assert(
  zhStyleModes.light.desc.includes('删除明确口癖') &&
    zhStyleModes.light.desc.includes('合并连续重复词') &&
    zhStyleModes.light.desc.includes('不改结构') &&
    zhStyleModes.light.desc.includes('不总结') &&
    zhStyleModes.light.desc.includes('不扩写'),
  `light desc must constrain cleanup-only behavior, got: ${zhStyleModes.light.desc}`,
);
assert(
  zhStyleModes.structured.desc.includes('编号结构') &&
    zhStyleModes.structured.desc.includes('1.1') &&
    zhStyleModes.structured.desc.includes('1.2') &&
    zhStyleModes.structured.desc.includes('2.1'),
  `structured desc must require numbered hierarchy, got: ${zhStyleModes.structured.desc}`,
);
assert(
  zhStyleModes.formal.desc.includes('正式邮件') &&
    zhStyleModes.formal.desc.includes('公文表达') &&
    zhStyleModes.formal.desc.includes('称呼') &&
    zhStyleModes.formal.desc.includes('正文') &&
    zhStyleModes.formal.desc.includes('结束语'),
  `formal desc must require message/document shape, got: ${zhStyleModes.formal.desc}`,
);

for (const mode of ['raw', 'light', 'structured', 'formal'] as const) {
  assert(
    zhStyleModes[mode].sample.includes('老板') &&
      zhStyleModes[mode].sample.includes('项目验收') &&
      !zhStyleModes[mode].sample.includes('王经理'),
    `${mode} sample should use the same long project-acceptance source scenario, got: ${zhStyleModes[mode].sample}`,
  );
}
assert(
  zhStyleModes.structured.sample.includes('1.') &&
    zhStyleModes.structured.sample.includes('1.1') &&
    zhStyleModes.structured.sample.includes('2.1'),
  `structured sample must show hierarchical numbering, got: ${zhStyleModes.structured.sample}`,
);
for (const mode of ['light', 'structured'] as const) {
  assert(
    !zhStyleModes[mode].sample.includes('不是周二') &&
      zhStyleModes[mode].sample.includes('周三下午两点'),
    `${mode} sample should resolve spoken self-correction to the final value, got: ${zhStyleModes[mode].sample}`,
  );
}
assert(
  zhStyleModes.formal.sample.includes('老板您好：') &&
    zhStyleModes.formal.sample.includes('谢谢。') &&
    !zhStyleModes.formal.sample.includes('此致') &&
    !zhStyleModes.formal.sample.includes('敬礼'),
  `formal sample must look like a formal email, got: ${zhStyleModes.formal.sample}`,
);
