import { ipcRenderer, contextBridge, webFrame } from 'electron'

/**
 * Vela Preload Script — 安全地暴露 IPC 通信能力到渲染进程
 *
 * 通过 contextBridge 暴露类型安全的 API，避免直接暴露 ipcRenderer
 */
contextBridge.exposeInMainWorld('velaAPI', {
  // ===== 双向请求/响应（invoke/handle） =====
  /** 调用主进程并等待结果 */
  invoke: (channel: string, ...args: unknown[]) => {
    return ipcRenderer.invoke(channel, ...args)
  },

  // ===== 主进程 → 渲染进程事件 =====
  /** 监听主进程推送的事件 */
  on: (channel: string, callback: (...args: unknown[]) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, ...args: unknown[]) => callback(...args)
    ipcRenderer.on(channel, listener)
    // 返回取消订阅函数
    return () => {
      ipcRenderer.removeListener(channel, listener)
    }
  },

  /** 一次性监听 */
  once: (channel: string, callback: (...args: unknown[]) => void) => {
    ipcRenderer.once(channel, (_event, ...args) => callback(...args))
  },

  // ===== 渲染进程 → 主进程单向发送 =====
  /** 单向发送消息（无返回值） */
  send: (channel: string, ...args: unknown[]) => {
    ipcRenderer.send(channel, ...args)
  },

  // ===== UI 控制 =====
  /** 设置窗口缩放级别 (Electron WebFrame) */
  setZoomLevel: (level: number) => {
    webFrame.setZoomLevel(level)
  },
  /** 设置绝对缩放比例 */
  setZoomFactor: (factor: number) => {
    webFrame.setZoomFactor(factor)
  },
  /** 等级获取 */
  getZoomLevel: () => {
    return webFrame.getZoomLevel()
  }
})
