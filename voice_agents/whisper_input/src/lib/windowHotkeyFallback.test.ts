import {
  isWindowHotkeyKeyboardCandidate,
  windowMouseHotkeyCode,
} from './windowHotkeyFallback';

function assertEqual<T>(actual: T, expected: T, name: string) {
  if (actual !== expected) {
    throw new Error(`${name}: expected ${expected}, got ${actual}`);
  }
}

function keyboardEvent(code: string, key = code): KeyboardEvent {
  return { code, key } as KeyboardEvent;
}

assertEqual(
  isWindowHotkeyKeyboardCandidate(keyboardEvent('KeyK', 'k')),
  true,
  'fallback forwards letter hotkeys',
);

assertEqual(
  isWindowHotkeyKeyboardCandidate(keyboardEvent('CapsLock')),
  true,
  'fallback forwards CapsLock hotkeys',
);

assertEqual(
  isWindowHotkeyKeyboardCandidate(keyboardEvent('F12')),
  true,
  'fallback forwards function key hotkeys',
);

assertEqual(
  isWindowHotkeyKeyboardCandidate(keyboardEvent('Numpad7')),
  true,
  'fallback forwards numpad digit hotkeys',
);

assertEqual(windowMouseHotkeyCode(3), 'Mouse4', 'fallback maps Mouse4');
assertEqual(windowMouseHotkeyCode(4), 'Mouse5', 'fallback maps Mouse5');
assertEqual(windowMouseHotkeyCode(0), null, 'fallback ignores primary mouse button');
