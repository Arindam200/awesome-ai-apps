/**
 * 渲染进程的 IPC 客户端 — 类型安全的主进程通信封装
 *
 * 用法：
 *   import { ipc } from '@/services/ipc-client'
 *   const result = await ipc.invoke('project:create', { name: '...' })
 */
import type {
  AllInvokeChannels,
  AllEventChannels,
  InvokeChannel,
  EventChannel,
} from '../shared/ipc-channels'

/** 从 preload 暴露的 velaAPI */
interface VelaAPI {
  invoke: (channel: string, ...args: unknown[]) => Promise<unknown>
  on: (channel: string, callback: (...args: unknown[]) => void) => () => void
  once: (channel: string, callback: (...args: unknown[]) => void) => void
  send: (channel: string, ...args: unknown[]) => void
  setZoomLevel: (level: number) => void
  setZoomFactor: (factor: number) => void
  getZoomLevel: () => number
}

/** 获取 velaAPI（由 preload 注入到 window） */
function getAPI(): VelaAPI {
  const api = (window as unknown as { velaAPI: VelaAPI }).velaAPI
  if (!api) {
    // 浏览器模式下的降级处理（开发时直接浏览器打开的情况）
    console.warn('[Vela IPC] velaAPI 未注入，可能不在 Electron 环境中运行')
    return {
      invoke: async () => { throw new Error('不在 Electron 环境中') },
      on: () => () => {},
      once: () => {},
      send: () => {},
      setZoomLevel: () => {},
      setZoomFactor: () => {},
      getZoomLevel: () => 0,
    }
  }
  return api
}

/** 类型安全的 IPC 客户端 */
export const ipc = {
  /**
   * 调用主进程并等待返回值（类型安全）
   *
   * @example
   * const result = await ipc.invoke('project:create', { name: '我的小说', path: '/path', genre: '玄幻', targetAudience: '男频' })
   */
  invoke: async <C extends InvokeChannel>(
    channel: C,
    ...args: AllInvokeChannels[C]['args']
  ): Promise<AllInvokeChannels[C]['return']> => {
    console.log('[ipc-client.invoke] 调用通道:', channel, '参数数量:', args.length)
    const result = await getAPI().invoke(channel, ...args) as Promise<AllInvokeChannels[C]['return']>
    console.log('[ipc-client.invoke] 调用完成:', channel)
    return result
  },

  /**
   * 监听主进程推送的事件（返回取消订阅函数）
   *
   * @example
   * const unsub = ipc.on('llm:stream-chunk', (data) => console.log(data.chunk))
   * // 组件卸载时取消
   * unsub()
   */
  on: <C extends EventChannel>(
    channel: C,
    callback: (data: AllEventChannels[C]) => void,
  ): (() => void) => {
    return getAPI().on(channel, callback as (...args: unknown[]) => void)
  },

  /** 一次性监听 */
  once: <C extends EventChannel>(
    channel: C,
    callback: (data: AllEventChannels[C]) => void,
  ) => {
    getAPI().once(channel, callback as (...args: unknown[]) => void)
  },

  /** 单向发送（无返回值） */
  send: (channel: string, ...args: unknown[]) => {
    getAPI().send(channel, ...args)
  },

  /** 是否在 Electron 环境中 */
  get isElectron(): boolean {
    return !!(window as unknown as { velaAPI: VelaAPI }).velaAPI
  },

  /** 设置窗口缩放级别 */
  setZoomLevel: (level: number) => {
    getAPI().setZoomLevel(level)
  },

  /** 设置绝对缩放比例 */
  setZoomFactor: (factor: number) => {
    getAPI().setZoomFactor(factor)
  },

  /** 获取当前缩放级别 */
  getZoomLevel: () => {
    return getAPI().getZoomLevel()
  }
}
