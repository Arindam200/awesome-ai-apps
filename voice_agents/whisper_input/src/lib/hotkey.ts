import i18n from '../i18n';
import type { ComboBinding, HotkeyBinding, HotkeyTrigger, QaHotkeyBinding, ShortcutBinding } from './types';

export function defaultQaShortcut(): ShortcutBinding {
  return {
    primary: ';',
    modifiers: defaultAppShortcutModifiers(),
  };
}

export function defaultAppShortcutModifiers(): string[] {
  return currentPlatform().isMac ? ['cmd', 'shift'] : ['ctrl', 'shift'];
}

export function getHotkeyTriggerLabel(trigger: HotkeyTrigger | null | undefined): string {
  if (!trigger) return i18n.t('hotkey.fallback');
  if (trigger === 'custom') return i18n.t('hotkey.triggers.custom');
  return i18n.t(`hotkey.triggers.${trigger}`);
}

export function getHotkeyStartStopLabel(
  binding: HotkeyBinding | null | undefined,
  comboBinding?: ComboBinding | null,
  shortcutBinding?: ShortcutBinding | null,
): string {
  if (shortcutBinding) {
    const suffix = binding?.mode === 'hold'
      ? i18n.t('hotkey.modeHoldSuffix')
      : i18n.t('hotkey.modeToggleSuffix');
    return `${formatComboLabel(shortcutBinding)}${suffix}`;
  }
  if (binding?.trigger === 'custom' && comboBinding) {
    const combo = formatComboLabel(comboBinding);
    const suffix = binding.mode === 'hold'
      ? i18n.t('hotkey.modeHoldSuffix')
      : i18n.t('hotkey.modeToggleSuffix');
    return `${combo}${suffix}`;
  }
  const trigger = getHotkeyTriggerLabel(binding?.trigger);
  const suffix = binding?.mode === 'hold'
    ? i18n.t('hotkey.modeHoldSuffix')
    : binding?.mode === 'doubleClick'
      ? i18n.t('hotkey.modeDoubleClickSuffix')
      : i18n.t('hotkey.modeToggleSuffix');
  return `${trigger}${suffix}`;
}

export function getHotkeyUsageHint(
  binding: HotkeyBinding | null | undefined,
  comboBinding?: ComboBinding | null,
  shortcutBinding?: ShortcutBinding | null,
): string {
  if (shortcutBinding) {
    const combo = formatComboLabel(shortcutBinding);
    return binding?.mode === 'hold'
      ? i18n.t('hotkey.usageHold', { trigger: combo })
      : i18n.t('hotkey.usageToggle', { trigger: combo });
  }
  if (binding?.trigger === 'custom' && comboBinding) {
    const combo = formatComboLabel(comboBinding);
    return binding.mode === 'hold'
      ? i18n.t('hotkey.usageHold', { trigger: combo })
      : i18n.t('hotkey.usageToggle', { trigger: combo });
  }
  const trigger = getHotkeyTriggerLabel(binding?.trigger);
  return binding?.mode === 'hold'
    ? i18n.t('hotkey.usageHold', { trigger })
    : binding?.mode === 'doubleClick'
      ? i18n.t('hotkey.usageDoubleClick', { trigger })
    : i18n.t('hotkey.usageToggle', { trigger });
}

export function getHotkeyBindingCodes(binding: HotkeyBinding | null | undefined): string[] {
  if (!binding) return [];
  if (Array.isArray(binding.keys)) {
    return binding.keys.map(key => key.code.trim()).filter(Boolean);
  }
  const legacy = legacyTriggerCode(binding.trigger);
  return legacy ? [legacy] : [];
}

export function getHotkeyBindingLabel(binding: HotkeyBinding | null | undefined): string {
  const codes = getHotkeyBindingCodes(binding);
  if (codes.length === 0) return i18n.t('hotkey.unset');
  return codes.map(getHotkeyCodeLabel).join('+');
}

export function getHotkeyCodeLabel(code: string): string {
  const zh = i18n.language.toLowerCase().startsWith('zh');
  const isMac = currentPlatform().isMac;
  // Alt 在 macOS 是 Option（⌥），Meta 在 macOS 是 Command（⌘），Linux 上 Meta 是 Super。
  // 之前对所有平台一律返回 "Alt" / "Win"，QA 浮窗里 macOS 用户的"右 Option" 被显示成
  // "右 Alt"，"左 Cmd" 被显示成 "左 Win"——平台错配。下面按平台分流。
  // 用 ⌥/⌘ 与 formatPrimary 的输出（"Right ⌥" 等）保持一致。
  const labels: Record<string, string> = {
    ControlLeft: zh ? '左Ctrl' : 'Left Ctrl',
    ControlRight: zh ? '右Ctrl' : 'Right Ctrl',
    AltLeft: isMac ? (zh ? '左 ⌥' : 'Left ⌥') : (zh ? '左Alt' : 'Left Alt'),
    AltRight: isMac ? (zh ? '右 ⌥' : 'Right ⌥') : (zh ? '右Alt' : 'Right Alt'),
    ShiftLeft: zh ? '左Shift' : 'Left Shift',
    ShiftRight: zh ? '右Shift' : 'Right Shift',
    MetaLeft: isMac ? (zh ? '左 ⌘' : 'Left ⌘') : (zh ? '左Win' : 'Left Win'),
    MetaRight: isMac ? (zh ? '右 ⌘' : 'Right ⌘') : (zh ? '右Win' : 'Right Win'),
    OSLeft: isMac ? (zh ? '左 ⌘' : 'Left ⌘') : (zh ? '左Win' : 'Left Win'),
    OSRight: isMac ? (zh ? '右 ⌘' : 'Right ⌘') : (zh ? '右Win' : 'Right Win'),
    Fn: 'Fn',
    FnLock: 'FnLock',
    CapsLock: 'CapsLock',
    ScrollLock: 'ScrLock',
    Pause: 'Pause',
    PrintScreen: 'PrtSc',
    Backspace: 'Backspace',
    Tab: 'Tab',
    Enter: 'Enter',
    Space: 'Space',
    Insert: 'Insert',
    Delete: 'Delete',
    Home: 'Home',
    End: 'End',
    PageUp: 'PageUp',
    PageDown: 'PageDown',
    ArrowUp: 'Up',
    ArrowDown: 'Down',
    ArrowLeft: 'Left',
    ArrowRight: 'Right',
    ContextMenu: 'Menu',
    NumpadAdd: 'Num+',
    NumpadSubtract: 'Num-',
    NumpadMultiply: 'Num*',
    NumpadDivide: 'Num/',
    NumpadDecimal: 'Num.',
    NumpadEnter: 'NumEnter',
    Mouse4: 'Mouse4',
    Mouse5: 'Mouse5',
    Backquote: '`',
    Minus: '-',
    Equal: '=',
    BracketLeft: '[',
    BracketRight: ']',
    Backslash: '\\',
    Semicolon: ';',
    Quote: "'",
    Comma: ',',
    Period: '.',
    Slash: '/',
  };
  if (labels[code]) return labels[code];
  const letter = code.match(/^Key([A-Z])$/);
  if (letter) return letter[1];
  const digit = code.match(/^Digit([0-9])$/);
  if (digit) return digit[1];
  const numpad = code.match(/^Numpad([0-9])$/);
  if (numpad) return `Num${numpad[1]}`;
  return code;
}

function legacyTriggerCode(trigger: HotkeyTrigger | null | undefined): string | null {
  switch (trigger) {
    case 'rightOption':
    case 'rightAlt':
      return 'AltRight';
    case 'leftOption':
      return 'AltLeft';
    case 'rightControl':
      return 'ControlRight';
    case 'leftControl':
      return 'ControlLeft';
    case 'rightCommand':
      return 'MetaRight';
    case 'fn':
      return 'Fn';
    default:
      return null;
  }
}

/** 把 ComboBinding 或 QaHotkeyBinding 格式化为可读标签，如 "⌘⇧D" / "Ctrl+Shift+D"。 */
export function formatComboLabel(binding: ComboBinding | QaHotkeyBinding | ShortcutBinding): string {
  const parts: string[] = [];
  const platform = currentPlatform();

  // 固定输出顺序：Ctrl/Cmd → Alt/Option → Shift → Super
  const modifierOrder = ['cmd', 'ctrl', 'alt', 'shift', 'super'] as const;
  for (const tag of modifierOrder) {
    if (binding.modifiers.some(m => m.toLowerCase() === tag)) {
      parts.push(modifierDisplayName(tag, platform));
    }
  }

  parts.push(formatPrimary(binding.primary));
  return parts.join(platform.isMac ? '' : '+');
}

export function currentPlatform(): { isMac: boolean; isWindows: boolean } {
  const nav = typeof navigator === 'undefined' ? null : navigator;
  const platform = nav?.platform || '';
  const userAgent = nav?.userAgent || '';
  return {
    isMac: platform.includes('Mac') || userAgent.includes('Mac'),
    isWindows: platform.includes('Win') || userAgent.includes('Windows'),
  };
}

function modifierDisplayName(tag: string, platform: { isMac: boolean; isWindows: boolean }): string {
  if (platform.isMac) {
    switch (tag) {
      case 'cmd': return '\u2318';
      case 'ctrl': return '\u2303';
      case 'alt': return '\u2325';
      case 'shift': return '\u21E7';
      case 'super': return '\u2318';
    }
  } else {
    switch (tag) {
      case 'cmd': return platform.isWindows ? 'Ctrl' : 'Super';
      case 'ctrl': return 'Ctrl';
      case 'alt': return 'Alt';
      case 'shift': return 'Shift';
      case 'super': return platform.isWindows ? 'Win' : 'Super';
    }
  }
  return tag;
}

function formatPrimary(primary: string): string {
  const trimmed = primary.trim();
  if (!trimmed) return '?';
  // 单字母归大写
  if (trimmed.length === 1 && /[a-zA-Z]/.test(trimmed)) {
    return trimmed.toUpperCase();
  }
  // 常见命名键的 macOS 符号
  const isMac = currentPlatform().isMac;
  if (isMac) {
    switch (trimmed.toLowerCase()) {
      case 'space': return '\u2423';
      case 'enter':
      case 'return': return '\u21A9';
      case 'tab': return '\u21E5';
      case 'escape':
      case 'esc': return '\u238B';
      case 'backspace': return '\u232B';
      case 'delete':
      case 'del': return '\u2326';
      case 'arrowup':
      case 'up': return '\u2191';
      case 'arrowdown':
      case 'down': return '\u2193';
      case 'arrowleft':
      case 'left': return '\u2190';
      case 'arrowright':
      case 'right': return '\u2192';
    }
  }
  switch (trimmed.toLowerCase()) {
    case 'rightoption': return isMac ? 'Right ⌥' : 'Right Alt';
    case 'rightalt': return 'Right Alt';
    case 'leftoption': return isMac ? 'Left ⌥' : 'Left Alt';
    case 'leftalt': return 'Left Alt';
    case 'rightcontrol': return isMac ? 'Right ⌃' : 'Right Ctrl';
    case 'leftcontrol': return isMac ? 'Left ⌃' : 'Left Ctrl';
    case 'rightcommand': return isMac ? 'Right ⌘' : (currentPlatform().isWindows ? 'Right Win' : 'Right Super');
    case 'fn': return 'Fn';
    case 'shift': return isMac ? '⇧' : 'Shift';
  }
  return trimmed;
}
