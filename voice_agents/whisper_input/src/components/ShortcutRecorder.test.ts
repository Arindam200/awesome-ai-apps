import {
  isShortcutModifierKey,
  keyboardLikeEventFromNativeHotkeyCode,
  modifierPrimaryFromCode,
  modifiersFromKeyboardLikeEvent,
  primaryFromKeyboardLikeEvent,
} from './ShortcutRecorder';
// @ts-ignore This repo does not install Node type declarations, but the contract test runs under tsx.
import { readFileSync } from 'node:fs';

function assertEqual<T>(actual: T, expected: T, name: string) {
  if (actual !== expected) {
    throw new Error(`${name}: expected ${expected}, got ${actual}`);
  }
}

function assertDeepEqual(actual: unknown, expected: unknown, name: string) {
  const actualJson = JSON.stringify(actual);
  const expectedJson = JSON.stringify(expected);
  if (actualJson !== expectedJson) {
    throw new Error(`${name}: expected ${expectedJson}, got ${actualJson}`);
  }
}

{
  assertEqual(
    isShortcutModifierKey('AltGraph'),
    true,
    'Windows right Alt / AltGr is treated as a modifier during recording',
  );
  assertEqual(
    modifierPrimaryFromCode('AltRight', 'AltGraph', { isMac: false, isWindows: true }),
    'RightAlt',
    'AltGraph on the physical right Alt key records RightAlt on Windows',
  );
  assertEqual(
    primaryFromKeyboardLikeEvent({
      key: 'AltGraph',
      code: 'AltRight',
      metaKey: false,
      ctrlKey: true,
      altKey: true,
      shiftKey: false,
    }),
    '',
    'AltGraph is not recorded as a plain primary key',
  );
  assertDeepEqual(
    modifiersFromKeyboardLikeEvent({
      key: 'AltGraph',
      code: 'AltRight',
      metaKey: false,
      ctrlKey: true,
      altKey: true,
      shiftKey: false,
    }, { isMac: false, isWindows: true }),
    [],
    'AltGraph does not add synthetic ctrl/alt modifiers to a single-key shortcut',
  );
  const nativeRightAlt = keyboardLikeEventFromNativeHotkeyCode('AltRight');
  assertDeepEqual(
    nativeRightAlt,
    {
      key: 'AltGraph',
      code: 'AltRight',
      metaKey: false,
      ctrlKey: false,
      altKey: false,
      shiftKey: false,
    },
    'Native Windows recorder event for physical right Alt maps to an AltGraph keyboard-like event',
  );
  assertEqual(
    modifierPrimaryFromCode(nativeRightAlt?.code ?? '', nativeRightAlt?.key ?? '', { isMac: false, isWindows: true }),
    'RightAlt',
    'Native Windows recorder event records RightAlt',
  );
}

{
  const source = readFileSync(new URL('./ShortcutRecorder.tsx', import.meta.url), 'utf8');
  const listenerIndex = source.indexOf("listen<ShortcutRecorderNativeHotkeyEvent>('shortcut-recorder:key'");
  const activationIndex = source.indexOf('void setShortcutRecordingActive(true);');

  assertEqual(
    source.includes('await setShortcutRecordingActive(true);'),
    false,
    'ShortcutRecorder must not enable native capture before React installs the native key listener',
  );
  assertEqual(
    listenerIndex >= 0 && activationIndex > listenerIndex,
    true,
    'ShortcutRecorder enables native capture only after registering shortcut-recorder:key listener',
  );
}
