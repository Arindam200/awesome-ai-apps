export interface HotkeyRecorderState {
  pressedCodes: string[];
  draftCodes: string[];
}

export interface HotkeyRecorderUpdate {
  state: HotkeyRecorderState;
  commitCodes: string[] | null;
}

export function createHotkeyRecorderState(): HotkeyRecorderState {
  return {
    pressedCodes: [],
    draftCodes: [],
  };
}

export function updateHotkeyRecorderState(
  state: HotkeyRecorderState,
  code: string,
  pressed: boolean,
): HotkeyRecorderUpdate {
  const active = new Set(state.pressedCodes);
  if (pressed) {
    active.add(code);
  } else {
    active.delete(code);
  }

  const pressedCodes = orderHotkeyCodes([...active]);
  const draftCodes = pressed ? pressedCodes : state.draftCodes;
  const shouldCommit = !pressed && pressedCodes.length === 0 && draftCodes.length > 0;

  return {
    state: shouldCommit ? createHotkeyRecorderState() : { pressedCodes, draftCodes },
    commitCodes: shouldCommit ? draftCodes : null,
  };
}

export function orderHotkeyCodes(codes: string[]): string[] {
  const seen = new Set<string>();
  return codes
    .filter(code => {
      if (!code || seen.has(code)) return false;
      seen.add(code);
      return true;
    })
    .sort((a, b) => hotkeyCodeRank(a) - hotkeyCodeRank(b));
}

function hotkeyCodeRank(code: string): number {
  const index = HOTKEY_CODE_ORDER.indexOf(code);
  if (index >= 0) return index;
  if (/^Key[A-Z]$/.test(code)) return 100 + code.charCodeAt(3);
  if (/^Digit[0-9]$/.test(code)) return 200 + Number(code.slice(5));
  if (/^F([1-9]|1[0-9]|2[0-4])$/.test(code)) return 300 + Number(code.slice(1));
  if (/^Numpad[0-9]$/.test(code)) return 400 + Number(code.slice(6));
  return 1000;
}

const HOTKEY_CODE_ORDER = [
  'ControlLeft', 'ControlRight', 'AltLeft', 'AltRight', 'ShiftLeft', 'ShiftRight',
  'MetaLeft', 'MetaRight', 'Fn', 'FnLock', 'CapsLock', 'ScrollLock', 'Pause',
  'PrintScreen', 'Backspace', 'Tab', 'Enter', 'Space', 'Insert', 'Delete', 'Home',
  'End', 'PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
  'ContextMenu', 'Backquote', 'Minus', 'Equal', 'BracketLeft', 'BracketRight',
  'Backslash', 'Semicolon', 'Quote', 'Comma', 'Period', 'Slash', 'NumpadAdd',
  'NumpadSubtract', 'NumpadMultiply', 'NumpadDivide', 'NumpadDecimal', 'NumpadEnter',
  'Mouse4', 'Mouse5',
];
