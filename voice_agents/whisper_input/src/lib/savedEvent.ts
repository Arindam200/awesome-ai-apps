// savedEvent.ts — 跨组件的"已保存 / 失败"统一事件通道。
//
// 触发：任意组件保存成功 / 失败时调用 emitSaved(...)。
// 监听：根容器（Settings / Translation / SelectionAsk）通过 useSavedToastListener 订阅，
//   状态喂给 <SavedToast>，pill 浮在右上角。
//
// 用 DOM CustomEvent（而不是 React Context）是为了让 CredentialField / ProviderTools
// 这类深层叶子组件不必沿 props 链传 dispatcher，跟 NAVIGATE_LOCAL_ASR_EVENT 同惯例。

import { useEffect, useState } from 'react';

export const SAVED_TOAST_EVENT = 'openless:saved-toast';

export type SavedToastEventState = 'saving' | 'saved' | 'failed';

export interface SavedToastDetail {
  state: SavedToastEventState;
  message: string;
}

export function emitSaved(state: SavedToastEventState, message: string): void {
  window.dispatchEvent(
    new CustomEvent<SavedToastDetail>(SAVED_TOAST_EVENT, { detail: { state, message } }),
  );
}

interface ToastSnapshot {
  state: 'idle' | SavedToastEventState;
  message: string;
}

const IDLE_SNAPSHOT: ToastSnapshot = { state: 'idle', message: '' };

/**
 * 订阅 saved-toast 事件，自动管理"非 saving 状态 1.6s 后回 idle"逻辑。
 * saving 状态保持显示直到下一条事件覆盖（避免长任务里 saving 中途消失）。
 */
export function useSavedToastListener(): ToastSnapshot {
  const [snapshot, setSnapshot] = useState<ToastSnapshot>(IDLE_SNAPSHOT);
  useEffect(() => {
    let timer: number | null = null;
    const handle = (event: Event) => {
      const detail = (event as CustomEvent<SavedToastDetail>).detail;
      if (!detail) return;
      if (timer !== null) {
        window.clearTimeout(timer);
        timer = null;
      }
      setSnapshot({ state: detail.state, message: detail.message });
      if (detail.state !== 'saving') {
        timer = window.setTimeout(() => {
          setSnapshot(IDLE_SNAPSHOT);
          timer = null;
        }, 1600);
      }
    };
    window.addEventListener(SAVED_TOAST_EVENT, handle);
    return () => {
      window.removeEventListener(SAVED_TOAST_EVENT, handle);
      if (timer !== null) window.clearTimeout(timer);
    };
  }, []);
  return snapshot;
}
