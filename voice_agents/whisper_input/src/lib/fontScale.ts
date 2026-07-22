// 全局字体大小档位 — 通过 documentElement.style.zoom 整体缩放（WebKit/Tauri 支持）。
// localStorage 是单一事实源；窗口启动时读一次应用，Settings 的"个性化"里改了就直接覆盖。

export type FontScaleId = 'small' | 'medium' | 'large';

export const FONT_SCALE_VALUES: Record<FontScaleId, number> = {
  small: 0.9,
  medium: 1.0,
  large: 1.1,
};

const FONT_SCALE_KEY = 'ol-font-scale';

export function readFontScale(): FontScaleId {
  try {
    const v = window.localStorage.getItem(FONT_SCALE_KEY);
    if (v === 'small' || v === 'medium' || v === 'large') return v;
  } catch { /* localStorage 不可用：忽略，落回默认 */ }
  return 'medium';
}

export function applyFontScale(id: FontScaleId): void {
  const scale = FONT_SCALE_VALUES[id];
  // CSS zoom 不在 W3C 标准里但 WebKit/Blink 都支持；Tauri 桌面端走 Wry/WebKit，没问题。
  (document.documentElement.style as CSSStyleDeclaration & { zoom?: string }).zoom = String(scale);
}

export function setFontScale(id: FontScaleId): void {
  applyFontScale(id);
  try { window.localStorage.setItem(FONT_SCALE_KEY, id); } catch { /* 忽略 */ }
}
