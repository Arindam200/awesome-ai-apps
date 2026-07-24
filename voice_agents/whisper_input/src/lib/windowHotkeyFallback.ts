export function isWindowHotkeyKeyboardCandidate(event: KeyboardEvent): boolean {
  const code = event.code;
  if (event.key === 'Escape' || code === 'Escape') return true;
  if (SUPPORTED_WINDOW_HOTKEY_CODES.has(code)) return true;
  if (/^Key[A-Z]$/.test(code)) return true;
  if (/^Digit[0-9]$/.test(code)) return true;
  if (/^F([1-9]|1[0-9]|2[0-4])$/.test(code)) return true;
  if (/^Numpad[0-9]$/.test(code)) return true;
  return false;
}

export function windowMouseHotkeyCode(button: number): string | null {
  if (button === 3) return 'Mouse4';
  if (button === 4) return 'Mouse5';
  return null;
}

const SUPPORTED_WINDOW_HOTKEY_CODES = new Set([
  'ControlLeft', 'ControlRight', 'AltLeft', 'AltRight', 'ShiftLeft', 'ShiftRight',
  'MetaLeft', 'MetaRight', 'CapsLock', 'ScrollLock', 'Pause', 'PrintScreen',
  'Backspace', 'Tab', 'Enter', 'Space', 'Insert', 'Delete', 'Home', 'End',
  'PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
  'ContextMenu', 'NumpadAdd', 'NumpadSubtract', 'NumpadMultiply', 'NumpadDivide',
  'NumpadDecimal', 'NumpadEnter', 'Backquote', 'Minus', 'Equal', 'BracketLeft',
  'BracketRight', 'Backslash', 'Semicolon', 'Quote', 'Comma', 'Period', 'Slash',
  'Fn', 'FnLock',
]);
