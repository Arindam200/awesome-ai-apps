import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { detectOS, type OS } from './WindowChrome';
import {
  getCapsuleHostMetrics,
  getCapsuleMessageLayout,
  getCapsulePillMetrics,
} from '../lib/capsuleLayout';
import { Icon } from './Icon';
import { invokeOrMock, isTauri } from '../lib/ipc';
import type { CapsulePayload, CapsuleState } from '../lib/types';

interface AudioBarsProps {
  level: number;
}

function AudioBars({ level }: AudioBarsProps) {
  const envelope = [0.55, 0.85, 1.0, 0.85, 0.55];
  const base = 2;
  const max = 24;
  const voice = Math.min(1, Math.max(0, level));
  const silenceGate = 0.012;
  const responseCeiling = 0.34;
  const gatedVoice = Math.min(1, Math.max(0, (voice - silenceGate) / (responseCeiling - silenceGate)));
  const easedVoice = gatedVoice * gatedVoice * (3 - 2 * gatedVoice);
  const visualVoice = Math.pow(easedVoice, 0.42);
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 3,
        width: 42,
        height: max,
      }}
    >
      {envelope.map((env, i) => (
        <span
          key={i}
          style={{
            display: 'inline-block',
            width: 3,
            height: base + (max - base) * visualVoice * env,
            borderRadius: 999,
            background: 'var(--ol-blue)',
            opacity: 0.82,
            transformOrigin: 'center',
            // 0.08s 在 60Hz audio-level 更新下太快，每次 re-render 都重启 transition，
            // 视觉上是阶梯式跳变。延长到 0.18s 让多次 update 在曲线内平滑混合，
            // easeOutExpo-like 缓动让圆点→长条的形变自然顺滑（用户原话"圆形跳成矩形"）。
            transition: 'height 0.18s cubic-bezier(0.22, 1, 0.36, 1)',
          }}
        />
      ))}
    </div>
  );
}

interface CenterTextProps {
  os: OS;
  kind: 'default' | 'processing' | 'error';
  text: string;
  color?: string;
}

function CenterText({ os, kind, text, color = 'var(--ol-ink-3)' }: CenterTextProps) {
  const metrics = getCapsulePillMetrics(os);
  const layout = getCapsuleMessageLayout(os, kind);
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 500,
        color,
        width: '100%',
        maxWidth: metrics.textWidth,
        minWidth: 0,
        textAlign: 'center',
        lineHeight: layout.allowWrap ? 1.2 : 1,
        whiteSpace: layout.allowWrap ? 'normal' : 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        display: '-webkit-box',
        WebkitBoxOrient: 'vertical',
        WebkitLineClamp: layout.lineClamp,
      }}
    >
      {text}
    </span>
  );
}

interface CircleButtonProps {
  variant: 'cancel' | 'confirm';
  enabled: boolean;
  onClick: () => void;
}

function CircleButton({ variant, enabled, onClick }: CircleButtonProps) {
  const { t } = useTranslation();
  const isCancel = variant === 'cancel';
  const os = detectOS();
  const useBackdrop = os !== 'win' && isCancel;
  return (
    <button
      onClick={enabled ? onClick : undefined}
      aria-label={isCancel ? t('common.cancel') : t('settings.shortcuts.confirm')}
      disabled={!enabled}
      style={{
        width: 28,
        height: 28,
        borderRadius: 999,
        background: isCancel ? 'rgba(255, 255, 255, 0.55)' : 'rgba(255, 255, 255, 0.92)',
        backdropFilter: useBackdrop ? 'blur(12px) saturate(160%)' : 'none',
        WebkitBackdropFilter: useBackdrop ? 'blur(12px) saturate(160%)' : 'none',
        color: 'var(--ol-ink)',
        border: '0.8px solid rgba(0, 0, 0, 0.08)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: enabled ? 'default' : 'not-allowed',
        opacity: enabled ? 1 : 0.42,
        visibility: 'visible',
        flexShrink: 0,
        padding: 0,
        boxShadow: '0 1px 2px rgba(0, 0, 0, 0.06)',
        transition: 'opacity 0.18s var(--ol-motion-soft), background 0.16s var(--ol-motion-quick), transform 0.12s var(--ol-motion-quick)',
      }}
    >
      <Icon name={isCancel ? 'close' : 'check'} size={isCancel ? 12 : 14} strokeWidth={1.8} />
    </button>
  );
}

interface PillProps {
  os: OS;
  state: CapsuleState;
  level: number;
  insertedChars: number;
  message?: string;
  onCancel: () => void;
  onConfirm: () => void;
}

function Pill({ os, state, level, insertedChars, message, onCancel, onConfirm }: PillProps) {
  const { t } = useTranslation();
  const metrics = getCapsulePillMetrics(os);
  const processingLayout = getCapsuleMessageLayout(os, 'processing');
  const enabled = state === 'recording';
  const processingText = message || t('capsule.thinking');

  // "thinking" 扫光速度：进入 transcribing/polishing 的头 2 秒走快速（0.9s/cycle，提示
  // 「流式刚开始」），之后切回慢速（2.4s）作为稳态。切回 idle / done / 其他 state 也复位
  // 为 fast，下次进入时从头开始 burst。
  const [shineFast, setShineFast] = useState(true);
  useEffect(() => {
    if (state === 'transcribing' || state === 'polishing') {
      setShineFast(true);
      const t = setTimeout(() => setShineFast(false), 2000);
      return () => clearTimeout(t);
    }
    setShineFast(true);
    return undefined;
  }, [state]);

  let center: JSX.Element;
  switch (state) {
    case 'recording':
      center = <AudioBars level={level} />;
      break;
    case 'transcribing':
    case 'polishing':
      center = (
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            // 左右 4px 内边距 + 外层 gap 已经让 "thinking" ↔ ✗/✓ 视觉间距落在 ~4-5px。
            padding: '0 4px',
            width: '100%',
            maxWidth: metrics.textWidth,
            minWidth: 0,
            justifyContent: 'center',
            // state 进入动画 —— 用户从 recording 切到 polishing 时多一道淡入提示，
            // 比纯切换 center 内容更容易被感知。
            animation: 'cap-state-enter 220ms var(--ol-motion-soft) both',
          }}
        >
          <span
            style={{
              // 放大 11 → 14 让 thinking 在胶囊里更显眼。
              fontSize: 14,
              // 字重 500：用户反馈 700 太粗。500 是 medium 视觉重量，扫光更稳。
              fontWeight: 500,
              letterSpacing: 0.5,
              // 字号 14 + 字重 500 时小写 g/y/p 等下伸字符在 line-height: 1 下会被
              // clip。给 line-height 一点冗余 + 上下 1px padding，descender 不再被切。
              paddingBlock: 1,
              // 扫光：渐变中段用更饱和的 ol-blue（不靠透明度），尾段保留 ink-3 作收尾，
              // 整条 stripe 比之前更醒目（用户反馈"扫光不够明显"）。
              color: 'var(--ol-ink-2)',
              backgroundImage:
                'linear-gradient(100deg, var(--ol-ink-3) 0%, var(--ol-ink-3) 35%, var(--ol-blue) 50%, var(--ol-ink-3) 65%, var(--ol-ink-3) 100%)',
              backgroundSize: '220% auto',
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              // 进入流式的头 ~2 秒用 0.9s 高速扫光（视觉提示「刚开始」），之后 React 副作用
              // 切到 2.4s 慢速。duration 变化时浏览器不重启动画，会平滑减速。
              animation: `cap-shine ${shineFast ? '0.9s' : '2.4s'} linear infinite`,
              minWidth: 0,
              textAlign: 'center',
              lineHeight: processingLayout.allowWrap ? 1.3 : 1.25,
              whiteSpace: processingLayout.allowWrap ? 'normal' : 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitBoxOrient: 'vertical',
              WebkitLineClamp: processingLayout.lineClamp,
            }}
          >
            {processingText}
          </span>
        </div>
      );
      break;
    case 'done':
      center = <CenterText os={os} kind="default" text={message || t('capsule.inserted', { count: insertedChars })} />;
      break;
    case 'cancelled':
      center = <CenterText os={os} kind="default" text={t('capsule.cancelled')} />;
      break;
    case 'error':
      center = <CenterText os={os} kind="error" text={message || t('capsule.error')} color="var(--ol-err)" />;
      break;
    default:
      center = <AudioBars level={0} />;
  }

  const ambient = state === 'recording' ? Math.min(1, Math.max(0, level)) : 0;
  const scale = os === 'win' ? 1 : 1 + ambient * 0.018;
  const shadowAlpha = 0.20 + ambient * 0.10;
  const useBackdrop = os !== 'win';

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 4,
        padding: '0 8px',
        width: metrics.width,
        height: metrics.height,
        boxSizing: metrics.boxSizing,
        borderRadius: 999,
        background: 'rgba(255, 255, 255, 0.62)',
        backdropFilter: useBackdrop ? 'blur(28px) saturate(180%)' : 'none',
        WebkitBackdropFilter: useBackdrop ? 'blur(28px) saturate(180%)' : 'none',
        border: '1px solid rgba(255, 255, 255, 0.55)',
        boxShadow: os === 'win'
          ? `0 10px 24px -14px rgba(0, 0, 0, ${(0.24 + ambient * 0.06).toFixed(3)}), 0 0 0 0.5px rgba(0, 0, 0, 0.08), inset 0 0.5px 0 rgba(255, 255, 255, 0.55)`
          : `0 18px 50px -10px rgba(0, 0, 0, ${shadowAlpha.toFixed(3)}), 0 0 0 0.5px rgba(0, 0, 0, 0.08), inset 0 0.5px 0 rgba(255, 255, 255, 0.55)`,
        color: 'var(--ol-ink)',
        fontFamily: 'var(--ol-font-sans)',
        transform: `scale(${scale.toFixed(4)})`,
        transformOrigin: 'center',
        transition: 'transform 0.08s var(--ol-motion-quick), box-shadow 0.08s var(--ol-motion-quick)',
        willChange: 'transform, box-shadow',
      }}
    >
      <CircleButton variant="cancel" enabled={enabled} onClick={onCancel} />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {center}
      </div>
      <CircleButton variant="confirm" enabled={enabled} onClick={onConfirm} />
    </div>
  );
}

export function Capsule() {
  const { t } = useTranslation();
  const os = detectOS();
  const metrics = getCapsulePillMetrics(os);
  const [state, setState] = useState<CapsuleState>(isTauri ? 'idle' : 'recording');
  const [level, setLevel] = useState<number>(isTauri ? 0 : 0.6);
  const [insertedChars, setInsertedChars] = useState<number>(0);
  const [message, setMessage] = useState<string | undefined>();
  const [translation, setTranslation] = useState<boolean>(false);
  // Windows 端 host 在翻译模式从 84 长到 118；macOS / Linux 上 capsuleLayout 已固定 42 忽略此参数。
  const hostMetrics = getCapsuleHostMetrics(os, translation);

  useEffect(() => {
    if (!isTauri) return;
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      const { listen } = await import('@tauri-apps/api/event');
      const handle = await listen<CapsulePayload>('capsule:state', event => {
        const p = event.payload;
        setState(p.state);
        setLevel(p.level ?? 0);
        setMessage(p.message ?? undefined);
        if (p.insertedChars != null) setInsertedChars(p.insertedChars);
        setTranslation(p.translation === true);
      });
      if (cancelled) handle();
      else unlisten = handle;
    })();
    return () => {
      cancelled = true;
      if (unlisten) unlisten();
    };
  }, []);


  const onCancel = () => {
    void invokeOrMock<void>('cancel_dictation', undefined, () => undefined);
  };

  const onConfirm = () => {
    void invokeOrMock<void>('stop_dictation', undefined, () => undefined);
  };

  if (state === 'idle') {
    return <div style={{ width: 0, height: 0 }} />;
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        paddingLeft: hostMetrics.horizontalInset,
        paddingRight: hostMetrics.horizontalInset,
        boxSizing: hostMetrics.boxSizing,
        paddingTop: os === 'win'
          ? Math.max(0, hostMetrics.height - metrics.height - hostMetrics.bottomInset)
          : 0,
        paddingBottom: os === 'win' ? hostMetrics.bottomInset : 0,
        background: 'transparent',
        animation: os === 'win' ? 'none' : 'capsule-in .22s cubic-bezier(.2,.9,.3,1.1)',
      }}
    >
      {/* "正在翻译" 徽章 — 嵌套两层：
          外层只负责"绝对定位 + 水平居中（translateX(-50%)）"，不参与动画；
          内层只负责"垂直位移 + 渐变透明度"——这样不会跟 translateX(-50%) 冲突，
          也不存在 keyframe 与 inline transform 互相覆盖导致的视觉跳变。 */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          // macOS / Linux：胶囊窗口 220×110、pill 居中，badge 锚到 pill 中线上方 21+8。
          // Windows：host 比 pill 多出左右 12px / 底部 12px 的阴影空间，pill 仍保持居中。
          bottom: os === 'win'
            ? `${hostMetrics.bottomInset + metrics.height + hostMetrics.badgeGap}px`
            : 'calc(50% + 21px + 8px)',
          transform: 'translateX(-50%)',
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            padding: '3px 10px',
            borderRadius: 999,
            fontSize: 10.5,
            fontWeight: 600,
            color: 'var(--ol-blue)',
            background: 'rgba(255, 255, 255, 0.78)',
            backdropFilter: 'blur(20px) saturate(180%)',
            WebkitBackdropFilter: 'blur(20px) saturate(180%)',
            border: '0.5px solid rgba(37, 99, 235, 0.25)',
            boxShadow: '0 4px 12px -4px rgba(37, 99, 235, 0.25), 0 0 0 0.5px rgba(0,0,0,0.04)',
            letterSpacing: '0.02em',
            whiteSpace: 'nowrap',
            // 隐藏：从 pill 中线偏下出发；显示：归位到 wrapper（pill 上方 25px）
            opacity: translation ? 1 : 0,
            transform: translation ? 'translateY(0) scale(1)' : 'translateY(40px) scale(.88)',
            transformOrigin: 'center bottom',
            transition: 'opacity .24s ease-out, transform .34s cubic-bezier(.2,.9,.3,1.1)',
            willChange: 'opacity, transform',
          }}
        >
          <span style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--ol-blue)' }} />
          {t('capsule.translating')}
        </div>
      </div>
      <Pill
        os={os}
        state={state}
        level={level}
        insertedChars={insertedChars}
        message={message}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />
      <style>{`
        @keyframes capsule-in {
          from { opacity: 0; transform: translateY(6px) scale(.96); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes cap-shine {
          0%   { background-position: 200% center; }
          100% { background-position: -200% center; }
        }
        @keyframes cap-state-enter {
          from { opacity: 0; transform: translateY(2px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
