import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { currentPlatform, formatComboLabel } from '../lib/hotkey';
import { setShortcutRecordingActive, validateShortcutBinding } from '../lib/ipc';
import type { ShortcutBinding } from '../lib/types';

export function ShortcutRecorder({
  value,
  onSave,
  alignRecordButton = false,
  disabled = false,
}: {
  value: ShortcutBinding;
  onSave: (binding: ShortcutBinding) => Promise<void>;
  alignRecordButton?: boolean;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pendingModifier = useRef<ShortcutBinding | null>(null);
  const pendingTimer = useRef<number | null>(null);

  const clearPendingModifier = () => {
    if (pendingTimer.current !== null) {
      window.clearTimeout(pendingTimer.current);
      pendingTimer.current = null;
    }
    pendingModifier.current = null;
  };

  const startRecording = () => {
    if (disabled || recording) return;
    setError(null);
    clearPendingModifier();
    setRecording(true);
  };

  useEffect(() => () => {
    clearPendingModifier();
    void setShortcutRecordingActive(false);
  }, []);

  useEffect(() => {
    if (!disabled || !recording) return;
    setRecording(false);
    clearPendingModifier();
  }, [disabled, recording]);

  const finish = async (binding: ShortcutBinding) => {
    try {
      await validateShortcutBinding(binding);
      await onSave(binding);
      clearPendingModifier();
      setRecording(false);
      setError(null);
    } catch {
      setError(t('settings.recording.comboConflict'));
    }
  };

  const handleKeyDown = (e: KeyboardLikeEvent, stopEvent: () => void) => {
    if (!recording || disabled) return;
    stopEvent();
    if (e.key === 'Escape') {
      setRecording(false);
      setError(null);
      clearPendingModifier();
      return;
    }
    if (isShortcutModifierKey(e.key)) {
      const primary = modifierPrimaryFromCode(e.code, e.key);
      if (!primary || pendingModifier.current?.primary === primary) return;
      clearPendingModifier();
      const binding = { primary, modifiers: [] };
      pendingModifier.current = binding;
      pendingTimer.current = window.setTimeout(() => {
        if (pendingModifier.current?.primary === primary) {
          void finish(binding);
        }
      }, 650);
      return;
    }
    clearPendingModifier();
    const primary = primaryFromKeyboardLikeEvent(e);
    if (primary) void finish({ primary, modifiers: modifiersFromKeyboardLikeEvent(e) });
  };

  const handleKeyUp = (e: KeyboardLikeEvent, stopEvent: () => void) => {
    if (!recording || disabled || !isShortcutModifierKey(e.key)) return;
    stopEvent();
    const primary = modifierPrimaryFromCode(e.code, e.key);
    if (primary && pendingModifier.current?.primary === primary) {
      const binding = pendingModifier.current;
      clearPendingModifier();
      void finish(binding);
    }
  };

  useEffect(() => {
    if (!recording || disabled) return undefined;

    let unlistenNative: (() => void) | null = null;
    let cancelled = false;
    const stopEvent = (event: Event) => {
      event.preventDefault();
      event.stopPropagation();
    };
    const onWindowKeyDown = (event: globalThis.KeyboardEvent) => {
      handleKeyDown(event, () => stopEvent(event));
    };
    const onWindowKeyUp = (event: globalThis.KeyboardEvent) => {
      handleKeyUp(event, () => stopEvent(event));
    };

    void import('@tauri-apps/api/event')
      .then(async ({ listen }) => {
        const unlisten = await listen<ShortcutRecorderNativeHotkeyEvent>('shortcut-recorder:key', event => {
          const keyboardEvent = keyboardLikeEventFromNativeHotkeyCode(event.payload.code);
          if (!keyboardEvent) return;
          if (event.payload.pressed) {
            handleKeyDown(keyboardEvent, () => {});
          } else {
            handleKeyUp(keyboardEvent, () => {});
          }
        });
        if (cancelled) {
          unlisten();
        } else {
          unlistenNative = unlisten;
          void setShortcutRecordingActive(true);
        }
      })
      .catch(() => {});

    window.addEventListener('keydown', onWindowKeyDown, true);
    window.addEventListener('keyup', onWindowKeyUp, true);
    return () => {
      cancelled = true;
      if (unlistenNative) unlistenNative();
      void setShortcutRecordingActive(false);
      window.removeEventListener('keydown', onWindowKeyDown, true);
      window.removeEventListener('keyup', onWindowKeyUp, true);
    };
  }, [recording, disabled]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    handleKeyDown(e, () => {
      e.preventDefault();
      e.stopPropagation();
    });
  };

  const onKeyUp = (e: KeyboardEvent<HTMLDivElement>) => {
    handleKeyUp(e, () => {
      e.preventDefault();
      e.stopPropagation();
    });
  };

  const rootStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    width: alignRecordButton ? '100%' : undefined,
  };
  const recorderRowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    width: alignRecordButton ? '100%' : undefined,
  };
  const recordButtonStyle: CSSProperties = {
    fontSize: 12,
    padding: '5px 14px',
    background: recording ? 'rgba(37,99,235,0.12)' : 'var(--ol-blue)',
    color: recording ? 'var(--ol-blue)' : '#fff',
    border: 0,
    borderRadius: 6,
    fontFamily: 'inherit',
    fontWeight: 500,
    cursor: recording || disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.68 : 1,
    marginLeft: alignRecordButton ? 'auto' : undefined,
  };

  return (
    <div style={rootStyle}>
      <div style={recorderRowStyle}>
        <span style={{ padding: '4px 10px', borderRadius: 6, background: 'rgba(0,0,0,0.06)', fontSize: 13, fontFamily: 'var(--ol-font-mono)', fontWeight: 500, color: 'var(--ol-ink)' }}>
          {formatComboLabel(value)}
        </span>
        <button
          onClick={startRecording}
          disabled={recording || disabled}
          style={recordButtonStyle}
        >
          {recording ? t('settings.recording.comboRecordHint') : t('settings.recording.comboRecordBtn')}
        </button>
      </div>
      {recording && (
        <div
          tabIndex={-1}
          onKeyDown={onKeyDown}
          onKeyUp={onKeyUp}
          style={{ padding: '8px 12px', borderRadius: 8, background: 'rgba(37,99,235,0.06)', border: '1px solid rgba(37,99,235,0.2)', fontSize: 12, color: 'var(--ol-blue)', outline: 'none' }}
          ref={el => el?.focus()}
        >
          {t('settings.recording.comboRecordHint')}
          <div style={{ fontSize: 11, color: 'var(--ol-ink-4)', marginTop: 4 }}>Esc 取消</div>
        </div>
      )}
      {error && <div style={{ fontSize: 11, color: 'var(--ol-red, #ef4444)' }}>{error}</div>}
    </div>
  );
}

type PlatformInfo = ReturnType<typeof currentPlatform>;

type KeyboardLikeEvent = Pick<
  KeyboardEvent,
  'key' | 'code' | 'metaKey' | 'ctrlKey' | 'altKey' | 'shiftKey'
>;

type ShortcutRecorderNativeHotkeyEvent = {
  code: string;
  pressed: boolean;
};

export function keyboardLikeEventFromNativeHotkeyCode(code: string): KeyboardLikeEvent | null {
  const codeToKey: Record<string, string> = {
    AltRight: 'AltGraph',
    AltLeft: 'Alt',
    ControlRight: 'Control',
    ControlLeft: 'Control',
    ShiftRight: 'Shift',
    ShiftLeft: 'Shift',
    MetaRight: 'Meta',
    MetaLeft: 'Meta',
  };
  const key = codeToKey[code];
  if (!key) return null;
  return {
    key,
    code,
    metaKey: false,
    ctrlKey: false,
    altKey: false,
    shiftKey: false,
  };
}

export function modifiersFromKeyboardLikeEvent(
  e: KeyboardLikeEvent,
  platform: PlatformInfo = currentPlatform(),
): string[] {
  const modifiers: string[] = [];
  if (isShortcutModifierKey(e.key)) return modifiers;
  if (e.metaKey && e.key !== 'Meta') modifiers.push(platform.isMac ? 'cmd' : 'super');
  if (e.ctrlKey && e.key !== 'Control') modifiers.push('ctrl');
  if (e.altKey && e.key !== 'Alt') modifiers.push('alt');
  if (e.shiftKey && e.key !== 'Shift') modifiers.push('shift');
  return modifiers;
}

export function isShortcutModifierKey(key: string): boolean {
  return (
    key === 'Control' ||
    key === 'Alt' ||
    key === 'AltGraph' ||
    key === 'Shift' ||
    key === 'Meta'
  );
}

export function modifierPrimaryFromCode(
  code: string,
  key: string,
  platform: PlatformInfo = currentPlatform(),
): string {
  if (key === 'Shift') return 'Shift';
  if (code === 'ControlRight') return 'RightControl';
  if (code === 'ControlLeft') return 'LeftControl';
  if (code === 'AltRight') return platform.isMac ? 'RightOption' : 'RightAlt';
  if (code === 'AltLeft') return 'LeftOption';
  if (code === 'MetaRight' || code === 'MetaLeft') return 'RightCommand';
  return '';
}

export function primaryFromKeyboardLikeEvent(e: KeyboardLikeEvent): string {
  if (isShortcutModifierKey(e.key)) return '';
  const printable = primaryFromPrintableCode(e.code);
  if (printable) return printable;
  if (e.key.length === 1) return e.key;
  const codeToName: Record<string, string> = {
    Space: 'Space',
    Enter: 'Enter',
    Tab: 'Tab',
    Backspace: 'Backspace',
    Delete: 'Delete',
    ArrowUp: 'ArrowUp',
    ArrowDown: 'ArrowDown',
    ArrowLeft: 'ArrowLeft',
    ArrowRight: 'ArrowRight',
    Home: 'Home',
    End: 'End',
    PageUp: 'PageUp',
    PageDown: 'PageDown',
  };
  if (/^F\d{1,2}$/.test(e.key)) return e.key;
  return codeToName[e.code] || e.key;
}

function primaryFromPrintableCode(code: string): string {
  if (/^Key[A-Z]$/.test(code)) return code.slice(3);
  if (/^Digit[0-9]$/.test(code)) return code.slice(5);
  const codeToPrimary: Record<string, string> = {
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
    IntlBackslash: '\\',
  };
  return codeToPrimary[code] || '';
}
