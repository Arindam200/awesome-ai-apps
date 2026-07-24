// QaPanel.tsx — 划词追问浮窗 v2（issue #118 v2）。
//
// 触发链路（v2 双 hotkey）：
//   1) 用户按 Cmd+Shift+;（默认）→ 后端 toggle 浮窗可见性。
//      显示时发 `qa:state { kind: "idle", messages: [] }`。
//   2) 浮窗可见时，用户按 rightOption（主听写键的复用）→ 录音；
//      再按一次 → ASR + LLM；后端推 `qa:state { kind: "answer", messages: [...] }`。
//   3) 答案后用户可继续按 Option 多轮提问，messages 累积。
//
// 关闭：Esc / Close 按钮 / 再按 Cmd+Shift+; → qa_window_dismiss → 后端清历史 + 隐藏窗口。
// **不再自动关**（v1 的 blur / 30s 超时去掉）：用户多轮思考时浮窗保持。

import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { getSettings, isTauri, qaWindowDismiss, qaWindowPin } from '../lib/ipc';
import type { QaChatMessage, QaStatePayload, UserPreferences } from '../lib/types';
import { getHotkeyBindingLabel } from '../lib/hotkey';
import { renderQaMarkdown, renderQaPlainText } from '../lib/qaMarkdown';
import { Icon } from '../components/Icon';

const SELECTION_PREVIEW_MAX = 60;

type Status = 'idle' | 'recording' | 'thinking' | 'error';

export function QaPanel() {
  const { t, i18n } = useTranslation();
  const [messages, setMessages] = useState<QaChatMessage[]>([]);
  const [status, setStatus] = useState<Status>('idle');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [selectionPreview, setSelectionPreview] = useState<string>('');
  const [pinned, setPinned] = useState(false);
  /** 流式 LLM 答案：answer_delta 累积、answer 事件来时清空（最终内容已落到 messages）。 */
  const [streamingAnswer, setStreamingAnswer] = useState<string>('');
  /** 录音电平：0..1。后端每帧 33ms 通过 qa:level emit。详见 issue #162。 */
  const [level, setLevel] = useState<number>(0);
  /** 用户当前的录音热键 label（如 "右 Option" / "Right Alt"）。issue #205：
   *  原版硬编码 "Option"，Windows 用户没这个键，文案失真。读 prefs 后由 i18n
   *  插值动态显示，平台与用户配置都能跟上。 */
  const [recordHotkeyLabel, setRecordHotkeyLabel] = useState<string>(() =>
    i18n.t('hotkey.fallback'),
  );
  const tRef = useRef(t);
  tRef.current = t;

  // ── 后端事件订阅（mount 时订阅一次，永不重订阅）──────────────────
  useEffect(() => {
    if (!isTauri) return;
    let unlistenState: (() => void) | undefined;
    let unlistenDismiss: (() => void) | undefined;
    let unlistenLevel: (() => void) | undefined;
    let unlistenPrefs: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      try {
        const { listen } = await import('@tauri-apps/api/event');
        const stateHandle = await listen<QaStatePayload>('qa:state', event => {
          const payload = event.payload;
          if (payload.messages) {
            setMessages(payload.messages);
          }
          switch (payload.kind) {
            case 'idle':
              setStatus('idle');
              setSelectionPreview('');
              setErrorMsg('');
              setStreamingAnswer('');
              setLevel(0);
              break;
            case 'recording':
              setStatus('recording');
              setSelectionPreview(payload.selection_preview ?? '');
              setErrorMsg('');
              setStreamingAnswer('');
              break;
            case 'loading':
              // ASR 在 finalize、user message 还没 push 的过渡帧。提前切到 thinking
              // 视图避免 UI 卡 recording 几百 ms 反馈缺失。详见 issue #161。
              setStatus('thinking');
              setSelectionPreview('');
              setErrorMsg('');
              setStreamingAnswer('');
              setLevel(0);
              break;
            case 'thinking':
              setStatus('thinking');
              setSelectionPreview('');
              setErrorMsg('');
              setStreamingAnswer('');
              setLevel(0);
              break;
            case 'answer_delta':
              // 流式增量。仍保持 thinking 状态——直到 answer 事件落定后才回 idle。
              if (payload.chunk) {
                setStreamingAnswer(prev => prev + payload.chunk);
              }
              break;
            case 'answer':
              setStatus('idle');
              setSelectionPreview('');
              setErrorMsg('');
              // messages 已被上面的 setMessages 落定，清掉流式 buffer 避免和最终气泡重影。
              setStreamingAnswer('');
              setLevel(0);
              break;
            case 'error':
              setStatus('error');
              setErrorMsg(payload.error ?? tRef.current('qa.error'));
              setStreamingAnswer('');
              setLevel(0);
              break;
          }
        });
        const dismissHandle = await listen<unknown>('qa:dismiss', () => {
          setPinned(false);
          void qaWindowDismiss();
        });
        // qa:level — 录音电平，节流 ~33ms/帧。详见 issue #162。
        const levelHandle = await listen<{ level: number }>('qa:level', event => {
          setLevel(event.payload.level ?? 0);
        });
        // prefs:changed — 后端在 set_settings 后广播。issue #205：QA 浮窗在独立
        // webview，没有 HotkeySettingsContext；如果用户在主窗口改了录音键，
        // 浮窗里的 "{recordHotkey}" 文案必须立刻跟上，否则会一直停在旧值。
        const prefsHandle = await listen<UserPreferences>('prefs:changed', event => {
          setRecordHotkeyLabel(getHotkeyBindingLabel(event.payload?.hotkey));
        });
        if (cancelled) {
          stateHandle();
          dismissHandle();
          levelHandle();
          prefsHandle();
        } else {
          unlistenState = stateHandle;
          unlistenDismiss = dismissHandle;
          unlistenLevel = levelHandle;
          unlistenPrefs = prefsHandle;
        }
      } catch (error) {
        console.error('[QaPanel] listener setup failed', error);
      }
    })();
    return () => {
      cancelled = true;
      unlistenState?.();
      unlistenDismiss?.();
      unlistenLevel?.();
      unlistenPrefs?.();
    };
  }, []);

  // ── Esc 关闭 ────────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        void qaWindowDismiss();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, []);

  // ── 读取用户当前的录音热键 label，给 i18n 插值用（issue #205）。
  // QaPanel 跑在独立 webview（label="qa"），没有 HotkeySettingsContext
  // 注入，所以直接走 IPC 拿一次 prefs。语言切换时 i18n.t('hotkey.fallback')
  // 也要跟着重算，所以 i18n.language 入依赖。
  useEffect(() => {
    if (!isTauri) {
      setRecordHotkeyLabel(i18n.t('hotkey.fallback'));
      return;
    }
    let cancelled = false;
    void getSettings()
      .then(prefs => {
        if (cancelled) return;
        setRecordHotkeyLabel(getHotkeyBindingLabel(prefs.hotkey));
      })
      .catch(err => {
        console.warn('[QaPanel] load hotkey label failed', err);
      });
    return () => {
      cancelled = true;
    };
  }, [i18n.language]);

  const onTogglePin = () => {
    const next = !pinned;
    setPinned(next);
    void qaWindowPin(next);
  };

  const onClose = () => {
    void qaWindowDismiss();
  };

  // ── 自动滚动到底（新消息进来时）────────────────────────────────────
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, status]);

  return (
    <div style={shellStyle}>
      <Toolbar pinned={pinned} onTogglePin={onTogglePin} onClose={onClose} />
      <div ref={scrollRef} style={contentStyle}>
        {messages.length === 0 && status === 'idle' && (
          <EmptyHint t={t} recordHotkey={recordHotkeyLabel} />
        )}
        {messages.length === 0 && status === 'recording' && (
          <RecordingHeader
            preview={selectionPreview}
            t={t}
            level={level}
            recordHotkey={recordHotkeyLabel}
          />
        )}
        <MessageList messages={messages} />
        {status === 'recording' && messages.length > 0 && (
          <TurnIndicator
            kind="recording"
            t={t}
            preview={selectionPreview}
            level={level}
            recordHotkey={recordHotkeyLabel}
          />
        )}
        {streamingAnswer && (
          <StreamingAssistantBubble markdown={streamingAnswer} />
        )}
        {status === 'thinking' && !streamingAnswer && (
          <TurnIndicator kind="thinking" t={t} />
        )}
        {status === 'error' && (
          <ErrorRow message={errorMsg} t={t} recordHotkey={recordHotkeyLabel} />
        )}
      </div>
      <StatusBar status={status} t={t} recordHotkey={recordHotkeyLabel} />
    </div>
  );
}

// ── 子组件 ────────────────────────────────────────────────────────────

interface ToolbarProps {
  pinned: boolean;
  onTogglePin: () => void;
  onClose: () => void;
}

function Toolbar({ pinned, onTogglePin, onClose }: ToolbarProps) {
  const { t } = useTranslation();
  // 拖动 (issue #205)：
  // - macOS: lib.rs::make_qa_window_draggable_macos 在 NSWindow 层把整窗口设
  //   movableByWindowBackground=YES，所以 macOS 上整片背景都可拖。
  // - Windows: NSWindow 走不了；用 Tauri 标准 data-tauri-drag-region —— mousedown
  //   走 startDragging() → WM_NCLBUTTONDOWN(HTCAPTION)，在 focus:false 浮窗上也能用。
  // 两条路径并存不冲突；data-tauri-drag-region 放在 toolbar 的空白 spacer 上，IconBtn
  // 作为 button 子元素仍然正常 click。
  return (
    <div style={toolbarStyle}>
      <div data-tauri-drag-region style={{ flex: 1, height: '100%' }} />
      <IconBtn
        label={pinned ? t('qa.unpinTooltip') : t('qa.pinTooltip')}
        active={pinned}
        onClick={onTogglePin}
      >
        <Icon name="pin" size={13} strokeWidth={1.7} fill={pinned ? 'currentColor' : 'none'} />
      </IconBtn>
      <IconBtn label={t('qa.closeTooltip')} onClick={onClose}>
        <Icon name="close" size={12} strokeWidth={1.8} />
      </IconBtn>
    </div>
  );
}

interface IconBtnProps {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function IconBtn({ label, active, onClick, children }: IconBtnProps) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      style={{
        ...iconBtnBaseStyle,
        color: active ? 'var(--ol-blue)' : 'var(--ol-ink-3)',
        background: active ? 'rgba(37,99,235,0.12)' : 'transparent',
      }}
    >
      {children}
    </button>
  );
}

function EmptyHint({
  t,
  recordHotkey,
}: {
  t: ReturnType<typeof useTranslation>['t'];
  recordHotkey: string;
}) {
  return (
    <div style={emptyHintStyle}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, color: 'var(--ol-ink)' }}>
        {t('qa.emptyTitle', { recordHotkey })}
      </div>
      <div style={{ fontSize: 12, color: 'var(--ol-ink-3)', lineHeight: 1.6 }}>
        {t('qa.emptyDesc', { recordHotkey })}
      </div>
    </div>
  );
}

function RecordingHeader({
  preview,
  t,
  level,
  recordHotkey,
}: {
  preview: string;
  t: ReturnType<typeof useTranslation>['t'];
  level: number;
  recordHotkey: string;
}) {
  const truncated = useMemo(() => truncate(preview, SELECTION_PREVIEW_MAX), [preview]);
  return (
    <div style={recordingHeaderStyle}>
      {truncated && (
        <div style={previewStyle}>
          <span style={{ color: 'var(--ol-ink-4)', marginRight: 4 }}>
            {t('qa.selectionPreview')}
          </span>
          <span style={{ color: 'var(--ol-ink-2)' }}>{truncated}</span>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ol-ink-2)' }}>
        <span style={recordingDotStyle} />
        {t('qa.recordingHint', { recordHotkey })}
      </div>
      <LevelBar level={level} />
    </div>
  );
}

/** QA 录音电平条。后端 qa:level 每帧 ~33ms 推一次 0..1。详见 issue #162。 */
function LevelBar({ level }: { level: number }) {
  const pct = Math.min(100, Math.max(0, level * 100));
  return (
    <div
      style={{
        height: 4,
        width: '100%',
        background: 'rgba(0,0,0,0.06)',
        borderRadius: 2,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: '100%',
          width: `${pct}%`,
          background: 'var(--ol-blue)',
          transition: 'width 0.08s var(--ol-motion-quick)',
        }}
      />
    </div>
  );
}

function MessageList({ messages }: { messages: QaChatMessage[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {messages.map((m, i) => (
        <MessageRow key={i} message={m} />
      ))}
    </div>
  );
}

function MessageRow({ message }: { message: QaChatMessage }) {
  // 钩子顺序与 message.role 无关：先无条件 useMemo（user 消息时 html 不渲染但计算无害）。
  const html = useMemo(() => {
    if (message.role !== 'assistant') return '';
    try {
      return renderQaMarkdown(message.content);
    } catch (error) {
      console.error('[qa] failed to render markdown', error);
      return renderQaPlainText(String(message.content ?? ''));
    }
  }, [message.content, message.role]);

  if (message.role === 'user') {
    // 第一轮可能含 "# 选区原文 ... # 我的问题 ..." → 抽出问题部分单独显示，
    // 选区作为引用块淡显在上面。
    const { selection, question } = splitFirstTurnUser(message.content);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
        {selection && (
          <div style={selectionQuoteStyle}>
            <span style={{ color: 'var(--ol-ink-4)', marginRight: 4 }}>“</span>
            {truncate(selection, 120)}
            <span style={{ color: 'var(--ol-ink-4)', marginLeft: 4 }}>”</span>
          </div>
        )}
        <div style={userBubbleStyle}>{question}</div>
      </div>
    );
  }
  return (
    <div
      className="qa-answer"
      style={assistantBubbleStyle}
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** 流式 LLM 答案的 in-progress 气泡。跟 assistant 最终气泡同款样式，结尾加一颗
 *  闪烁的 caret 让用户看出还在生成。markdown 边到边渲染，未闭合的代码块不会炸 —
 *  marked 在不完整输入上是宽容的（开 token 没找到闭 token 就当 inline）。 */
function StreamingAssistantBubble({ markdown }: { markdown: string }) {
  const html = useMemo(() => {
    try {
      return renderQaMarkdown(markdown);
    } catch (error) {
      console.error('[qa] failed to render streaming markdown', error);
      return renderQaPlainText(String(markdown ?? ''));
    }
  }, [markdown]);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
      <div
        className="qa-answer"
        style={assistantBubbleStyle}
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <span
        style={{
          display: 'inline-block',
          width: 6,
          height: 12,
          background: 'var(--ol-blue)',
          marginLeft: 12,
          animation: 'qa-pulse 0.9s var(--ol-motion-soft) infinite',
          borderRadius: 1,
        }}
      />
    </div>
  );
}

function splitFirstTurnUser(content: string): { selection: string; question: string } {
  // 后端拼法：`# 选区原文\n{sel}\n\n# 我的问题\n{q}`。简单 split，对齐 coordinator.rs 的写法。
  const m = content.match(/^# 选区原文\n([\s\S]*?)\n\n# 我的问题\n([\s\S]+)$/);
  if (!m) return { selection: '', question: content };
  return { selection: m[1].trim(), question: m[2].trim() };
}

function TurnIndicator({
  kind,
  preview,
  t,
  level,
  recordHotkey,
}: {
  kind: 'recording' | 'thinking';
  preview?: string;
  t: ReturnType<typeof useTranslation>['t'];
  level?: number;
  recordHotkey?: string;
}) {
  if (kind === 'recording') {
    const truncated = preview ? truncate(preview, SELECTION_PREVIEW_MAX) : '';
    return (
      <div style={turnIndicatorStyle}>
        {truncated && (
          <div style={previewInlineStyle}>
            <span style={{ color: 'var(--ol-ink-4)', marginRight: 4 }}>
              {t('qa.selectionPreview')}
            </span>
            <span style={{ color: 'var(--ol-ink-2)' }}>{truncated}</span>
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ol-ink-2)' }}>
          <span style={recordingDotStyle} />
          {t('qa.recordingHint', { recordHotkey: recordHotkey ?? '' })}
        </div>
        <LevelBar level={level ?? 0} />
      </div>
    );
  }
  return (
    <div style={turnIndicatorStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ol-ink-3)' }}>
        <SkeletonLine width="60%" />
      </div>
      <div style={{ fontSize: 12, color: 'var(--ol-ink-3)', fontWeight: 500 }}>
        {t('qa.thinking')}
      </div>
    </div>
  );
}

function ErrorRow({
  message,
  t,
  recordHotkey,
}: {
  message: string;
  t: ReturnType<typeof useTranslation>['t'];
  recordHotkey: string;
}) {
  return (
    <div style={errorRowStyle}>
      <div style={{ fontSize: 12.5, color: 'var(--ol-err)', lineHeight: 1.55 }}>{message}</div>
      <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)' }}>
        {t('qa.errorRetryHint', { recordHotkey })}
      </div>
    </div>
  );
}

function StatusBar({
  status,
  t,
  recordHotkey,
}: {
  status: Status;
  t: ReturnType<typeof useTranslation>['t'];
  recordHotkey: string;
}) {
  let label = '';
  let dotColor = 'transparent';
  switch (status) {
    case 'idle':
      label = t('qa.statusIdle', { recordHotkey });
      dotColor = 'rgba(0,0,0,0.18)';
      break;
    case 'recording':
      label = t('qa.statusRecording');
      dotColor = 'var(--ol-err)';
      break;
    case 'thinking':
      label = t('qa.statusThinking');
      dotColor = 'var(--ol-blue)';
      break;
    case 'error':
      label = t('qa.statusError');
      dotColor = 'var(--ol-err)';
      break;
  }
  return (
    <div style={statusBarStyle}>
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: dotColor,
          flexShrink: 0,
        }}
      />
      <span style={{ fontSize: 11.5, color: 'var(--ol-ink-3)', fontWeight: 500 }}>{label}</span>
    </div>
  );
}

function SkeletonLine({ width }: { width: string }) {
  return (
    <div
      style={{
        height: 8,
        width,
        borderRadius: 4,
        background:
          'linear-gradient(90deg, rgba(0,0,0,0.06) 0%, rgba(0,0,0,0.12) 50%, rgba(0,0,0,0.06) 100%)',
        backgroundSize: '200% 100%',
        animation: 'qa-skeleton 1.4s var(--ol-motion-soft) infinite',
      }}
    />
  );
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

// ── 样式 ──────────────────────────────────────────────────────────────

const shellStyle: CSSProperties = {
  width: '100%',
  height: '100vh',
  display: 'flex',
  flexDirection: 'column',
  borderRadius: 14,
  overflow: 'hidden',
  // 浮窗 focus:false 在 macOS 上会让 backdrop-filter 不工作（透到桌面文字），所以
  // 改成接近不透明的实色背景。blur 仅作锦上添花，不再依赖它保证可读性。
  background: 'rgba(255, 255, 255, 0.97)',
  backdropFilter: 'blur(24px) saturate(180%)',
  WebkitBackdropFilter: 'blur(24px) saturate(180%)',
  border: '0.5px solid rgba(0, 0, 0, 0.08)',
  boxShadow: 'var(--ol-shadow-lg)',
  fontFamily: 'var(--ol-font-sans)',
  color: 'var(--ol-ink)',
};

const toolbarStyle: CSSProperties = {
  height: 32,
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  padding: '0 8px',
  borderBottom: '0.5px solid rgba(0, 0, 0, 0.06)',
  flexShrink: 0,
  cursor: 'grab',
};

const iconBtnBaseStyle: CSSProperties = {
  width: 22,
  height: 22,
  border: 0,
  borderRadius: 6,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'default',
  padding: 0,
  transition: 'background 0.16s var(--ol-motion-quick), color 0.16s var(--ol-motion-quick)',
};

const contentStyle: CSSProperties = {
  flex: 1,
  minHeight: 0,
  overflow: 'auto',
  padding: '14px 16px',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
};

const emptyHintStyle: CSSProperties = {
  margin: 'auto 0',
  textAlign: 'center',
  padding: '0 8px',
};

const recordingHeaderStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
};

const previewStyle: CSSProperties = {
  fontSize: 11.5,
  lineHeight: 1.5,
  padding: '8px 10px',
  borderRadius: 8,
  background: 'rgba(0, 0, 0, 0.035)',
  border: '0.5px solid rgba(0, 0, 0, 0.06)',
};

const previewInlineStyle: CSSProperties = {
  ...previewStyle,
  marginBottom: 4,
};

const turnIndicatorStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
};

const userBubbleStyle: CSSProperties = {
  maxWidth: '80%',
  padding: '8px 12px',
  borderRadius: 14,
  borderBottomRightRadius: 4,
  background: 'var(--ol-blue)',
  color: '#fff',
  fontSize: 13,
  lineHeight: 1.55,
  wordBreak: 'break-word',
};

const selectionQuoteStyle: CSSProperties = {
  maxWidth: '80%',
  padding: '6px 10px',
  borderRadius: 10,
  background: 'rgba(0,0,0,0.04)',
  border: '0.5px solid rgba(0,0,0,0.06)',
  fontSize: 11.5,
  color: 'var(--ol-ink-3)',
  fontStyle: 'italic',
  lineHeight: 1.5,
};

const assistantBubbleStyle: CSSProperties = {
  maxWidth: '92%',
  padding: '8px 12px',
  borderRadius: 14,
  borderBottomLeftRadius: 4,
  background: 'rgba(0,0,0,0.04)',
  fontSize: 13,
  lineHeight: 1.6,
  color: 'var(--ol-ink)',
  wordBreak: 'break-word',
  alignSelf: 'flex-start',
};

const errorRowStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  padding: '8px 12px',
  borderRadius: 10,
  background: 'rgba(220,38,38,0.06)',
  border: '0.5px solid rgba(220,38,38,0.18)',
};

const recordingDotStyle: CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: '50%',
  background: 'var(--ol-err)',
  animation: 'qa-pulse 1.2s var(--ol-motion-soft) infinite',
};

const statusBarStyle: CSSProperties = {
  height: 28,
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '0 14px',
  borderTop: '0.5px solid rgba(0, 0, 0, 0.06)',
  background: 'rgba(255,255,255,0.4)',
};

const globalCss = `
@keyframes qa-skeleton {
  0%   { background-position: 200% 0; filter: blur(.2px); }
  50%  { filter: blur(0); }
  100% { background-position: -200% 0; filter: blur(.2px); }
}
@keyframes qa-pulse {
  0%, 100% { opacity: 1; filter: blur(0); transform: scale(1); }
  50%      { opacity: 0.35; filter: blur(.7px); transform: scale(.94); }
}
.qa-answer p        { margin: 0 0 6px; }
.qa-answer p:last-child { margin-bottom: 0; }
.qa-answer h1,
.qa-answer h2,
.qa-answer h3       { margin: 10px 0 5px; font-weight: 600; line-height: 1.35; }
.qa-answer h1       { font-size: 15px; }
.qa-answer h2       { font-size: 14px; }
.qa-answer h3       { font-size: 13px; }
.qa-answer ul,
.qa-answer ol       { margin: 0 0 6px; padding-left: 18px; }
.qa-answer li       { margin: 2px 0; }
.qa-answer code     { font-family: var(--ol-font-mono); font-size: 12px;
                      padding: 1px 5px; border-radius: 4px;
                      background: rgba(0,0,0,0.05); }
.qa-answer pre      { margin: 0 0 6px; padding: 8px 10px;
                      border-radius: 8px; background: rgba(0,0,0,0.05);
                      overflow-x: auto; }
.qa-answer pre code { padding: 0; background: transparent; }
.qa-answer a        { color: var(--ol-blue); text-decoration: none; }
.qa-answer a:hover  { text-decoration: underline; }
.qa-answer blockquote { margin: 0 0 6px; padding: 4px 0 4px 8px;
                        border-left: 2px solid rgba(0,0,0,0.15);
                        color: var(--ol-ink-3); }
.qa-answer hr       { border: 0; border-top: 0.5px solid rgba(0,0,0,0.10);
                      margin: 8px 0; }
`;

if (typeof document !== 'undefined' && !document.getElementById('qa-panel-style')) {
  const tag = document.createElement('style');
  tag.id = 'qa-panel-style';
  tag.textContent = globalCss;
  document.head.appendChild(tag);
}
