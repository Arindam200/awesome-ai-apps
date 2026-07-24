import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { ipc } from '../services/ipc-client'

export type Theme = 'light' | 'galaxy' | 'paper' | 'dark'

// ─── 共享字体库 ─────────────────────────────────────────────────────────────

/** 内置字体 ID（界面字体和写作字体共享同一张清单） */
export type FontId = 'inter' | 'noto-sans-sc' | 'lxgw-wenkai' | 'noto-serif-sc' | 'system'

export interface FontOption {
  id: FontId
  label: string
  labelEn: string
  desc: string
  /** 实际 CSS font-family 字符串 */
  family: string
  /** 预览文字（用该字体渲染，展示中英文效果） */
  preview: string
}

/** 所有内置字体（界面 + 写作共用） */
export const FONT_OPTIONS: FontOption[] = [
  {
    id: 'inter',
    label: 'Inter',
    labelEn: 'Inter',
    desc: '精心设计的现代 UI 字体，英文排版优秀，界面首选',
    family: "'Inter', system-ui, sans-serif",
    preview: 'Aa Bb 文字 123',
  },
  {
    id: 'noto-sans-sc',
    label: '思源黑体',
    labelEn: 'Noto Sans SC',
    desc: '黑体风格，中英文兼顾，简洁现代，科幻都市题材适用',
    family: "'Noto Sans SC', sans-serif",
    preview: '思源黑体 Sans',
  },
  {
    id: 'lxgw-wenkai',
    label: '霞鹜文楷',
    labelEn: 'LXGW WenKai',
    desc: '楷体风格，温润典雅，最适合中文小说写作',
    family: "'LXGW WenKai', serif",
    preview: '春花秋月何时了',
  },
  {
    id: 'noto-serif-sc',
    label: '思源宋体',
    labelEn: 'Noto Serif SC',
    desc: '宋体风格，字形端正，印刷质感强，正式文稿首选',
    family: "'Noto Serif SC', serif",
    preview: '往事如云烟，归零',
  },
  {
    id: 'system',
    label: '系统默认',
    labelEn: 'System UI',
    desc: 'macOS 使用苹方/SF Pro，原生手感，无需字体文件',
    family: 'system-ui, -apple-system, sans-serif',
    preview: 'Aa Bb 苹方 123',
  },
]

// ─── 向后兼容：旧版 WRITING_FONT_OPTIONS 别名 ──────────────────────────────
/** @deprecated 请使用 FONT_OPTIONS */
export const WRITING_FONT_OPTIONS = FONT_OPTIONS
/** @deprecated 请使用 FontId */
export type WritingFont = FontId

// ─── 缩放常量 ─────────────────────────────────────────────────────────────

const ZOOM_STEP = 0.05
const ZOOM_MIN = 0.7
const ZOOM_MAX = 1.5
/** 基准 font-size（未缩放时 html 的字号，px） */
const BASE_FONT_SIZE = 14 as const

// ─── Store 类型 ──────────────────────────────────────────────────────────

interface ThemeState {
  /** 用户选择的主题 */
  theme: Theme
  /** 实际应用的主题（解析 system 后） */
  resolvedTheme: 'light' | 'galaxy' | 'paper' | 'dark'
  /** 当前缩放级别（1.0 = 100%） */
  zoom: number
  /** 当前写作字体（正文编辑区 → --font-writing） */
  writingFont: FontId
  /** 当前界面字体（UI 全局 → --font-sans） */
  uiFont: FontId
  /** 设置主题 */
  setTheme: (theme: Theme) => void
  /** 初始化主题监听 */
  initTheme: () => void
  /** 放大 */
  zoomIn: () => void
  /** 缩小 */
  zoomOut: () => void
  /** 重置缩放到 100% */
  zoomReset: () => void
  /** 直接设置缩放级别 */
  setZoom: (zoom: number) => void
  /** 设置写作字体 */
  setWritingFont: (font: FontId) => void
  /** 设置界面字体 */
  setUiFont: (font: FontId) => void
}

// ─── Store ───────────────────────────────────────────────────────────────

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'paper',
      resolvedTheme: 'paper',
      zoom: 1.0,
      writingFont: 'lxgw-wenkai',
      uiFont: 'inter',

      setTheme: (theme: Theme) => {
        const resolved = resolveTheme(theme)
        set({ theme, resolvedTheme: resolved })
        applyTheme(resolved)
      },

      initTheme: () => {
        const { zoom, writingFont, uiFont } = get()
        let { theme } = get()

        // --- 迁移并兼容历史数据版本 ---
        // 兼容旧版系统设定的 localStorage
        if ((theme as string) === 'system') {
          theme = resolveTheme(theme)
          set({ theme })
        }
        // 如果读到旧版的 'night'，迁移为真的 'dark'
        if ((theme as string) === 'night') {
          theme = 'dark'
          set({ theme })
        }
        // 由于这里我们需要将以前的暗色变为 galaxy，如果用户之前就在用旧版 dark（此时不具备 night 属性），我们在上一个版本已经加过了 night。
        // 为了安全起见这里不再强转 dark -> galaxy，如果是直接跳版的用户，就把旧版的 dark 继承成新的黑夜 dark 也合情合理。
        // 但根据需求：“原本的深蓝色改叫 galaxy”，如果用户之前存的是旧版 'dark' (深蓝)，最好迁移。
        // 如何判断？如果 localStorage 中没有存到某处特征，我们可以直接迁移：
        if ((theme as string) === 'dark' && localStorage.getItem('ai-novel-writer-theme-migrated') !== '1') {
          theme = 'galaxy'
          set({ theme })
          localStorage.setItem('ai-novel-writer-theme-migrated', '1')
        }

        const resolved = resolveTheme(theme)
        set({ resolvedTheme: resolved })
        applyTheme(resolved)
        applyZoom(zoom)
        applyWritingFont(writingFont)
        applyUiFont(uiFont)
      },

      zoomIn: () => {
        const next = Math.min(ZOOM_MAX, +(get().zoom + ZOOM_STEP).toFixed(2))
        set({ zoom: next })
        applyZoom(next)
      },

      zoomOut: () => {
        const next = Math.max(ZOOM_MIN, +(get().zoom - ZOOM_STEP).toFixed(2))
        set({ zoom: next })
        applyZoom(next)
      },

      zoomReset: () => {
        set({ zoom: 1.0 })
        applyZoom(1.0)
      },

      setZoom: (zoom: number) => {
        const clamped = +Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom)).toFixed(2)
        set({ zoom: clamped })
        applyZoom(clamped)
      },

      setWritingFont: (font: FontId) => {
        set({ writingFont: font })
        applyWritingFont(font)
      },

      setUiFont: (font: FontId) => {
        set({ uiFont: font })
        applyUiFont(font)
      },
    }),
    {
      name: 'ai-novel-writer-theme',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        theme: state.theme,
        zoom: state.zoom,
        writingFont: state.writingFont,
        uiFont: state.uiFont,
      }),
    }
  )
)

// ─── 内部工具函数 ─────────────────────────────────────────────────────────

/** 解析主题：直接返回实际值，保留对 localStorage 旧版 system 设定的向下兼容 */
function resolveTheme(theme: Theme): 'light' | 'galaxy' | 'paper' | 'dark' {
  if ((theme as string) === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return theme
}

/** 应用主题到 DOM — 支持互斥的主题 */
function applyTheme(theme: 'light' | 'galaxy' | 'paper' | 'dark') {
  const root = document.documentElement
  root.classList.remove('galaxy', 'paper', 'dark')
  if (theme === 'galaxy') {
    root.classList.add('galaxy')
  } else if (theme === 'paper') {
    root.classList.add('paper')
  } else if (theme === 'dark') {
    root.classList.add('dark')
  }
}

/**
 * 将缩放比例应用到整个窗口。
 * Electron 环境使用 native zoomFactor；否则降级到 html root font-size。
 */
function applyZoom(zoom: number) {
  if (ipc.isElectron) {
    ipc.setZoomFactor(zoom)
  } else {
    document.documentElement.style.fontSize = `${(BASE_FONT_SIZE * zoom).toFixed(2)}px`
  }
}

/** 将写作字体应用到 --font-writing，正文编辑器通过 CSS 变量引用 */
function applyWritingFont(font: FontId) {
  const opt = FONT_OPTIONS.find((o) => o.id === font)
  if (opt) {
    document.documentElement.style.setProperty('--font-writing', opt.family)
  }
}

/** 将界面字体应用到 --font-sans，body/html 通过 font-family: var(--font-sans) 引用 */
function applyUiFont(font: FontId) {
  const opt = FONT_OPTIONS.find((o) => o.id === font)
  if (opt) {
    document.documentElement.style.setProperty('--font-sans', opt.family)
  }
}
