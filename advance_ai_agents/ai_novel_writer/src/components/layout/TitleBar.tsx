import { useEffect, type CSSProperties, type MouseEvent } from 'react'
import {
  Archive,
  CheckCircle2,
  FilePlus2,
  FolderOpen,
  Import,
  Languages,
  Menu,
  Minus,
  Moon,
  ScrollText,
  Settings,
  Sparkles,
  Square,
  Sun,
  Upload,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { useProjectStore } from '../../stores/project-store'
import { useThemeStore, type Theme } from '../../stores/theme-store'
import { useEditorStore } from '../../stores/editor-store'
import { useLayoutStore } from '../../stores/layout-store'
import { APP_BRAND } from '../../shared/brand'
import { ipc } from '../../services/ipc-client'
import { useLocaleStore } from '../../stores/locale-store'
import type { MessageKey } from '../../i18n/core'

const isMac = navigator.userAgent.includes('Mac')

const themeIcons: Record<Theme, typeof Sun> = {
  light: Sun,
  galaxy: Sparkles,
  paper: ScrollText,
  dark: Moon,
}
const themeOrder: Theme[] = ['galaxy', 'dark', 'light', 'paper']
const themeLabelKeys: Record<Theme, MessageKey> = {
  light: 'theme.light',
  galaxy: 'theme.galaxy',
  paper: 'theme.paper',
  dark: 'theme.dark',
}

export default function TitleBar() {
  const currentProject = useProjectStore((s) => s.currentProject)
  const openProject = useProjectStore((s) => s.openProject)
  const { theme, setTheme } = useThemeStore()
  const { zoom, zoomIn, zoomOut, zoomReset } = useThemeStore()
  const hasDirty = useEditorStore((s) => s.tabs.some((t) => t.dirty))
  const openSettings = useLayoutStore(s => s.openSettings)
  const openNewProject = useLayoutStore(s => s.openNewProject)
  const openExport = useLayoutStore(s => s.openExport)
  const openImportNovel = useLayoutStore(s => s.openImportNovel)
  const { locale, toggleLocale, t } = useLocaleStore()

  const ThemeIcon = themeIcons[theme] || Sun
  const cycleTheme = (e: MouseEvent) => {
    const nextTheme = themeOrder[(themeOrder.indexOf(theme) + 1) % themeOrder.length]

    if (
      !('startViewTransition' in document) ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      setTheme(nextTheme)
      return
    }

    const x = e.clientX
    const y = e.clientY
    const endRadius = Math.hypot(
      Math.max(x, innerWidth - x),
      Math.max(y, innerHeight - y)
    )

    const transition = (document as Document & { startViewTransition?: (cb: () => void) => { ready: Promise<void> } }).startViewTransition!(() => {
      setTheme(nextTheme)
    })

    transition.ready.then(() => {
      const clipPath = [
        `circle(0px at ${x}px ${y}px)`,
        `circle(${endRadius}px at ${x}px ${y}px)`,
      ]

      document.documentElement.animate(
        { clipPath },
        {
          duration: 450,
          easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
          pseudoElement: '::view-transition-new(root)',
        }
      )
    })
  }

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey
      if (!mod) return
      if (e.key === '=' || e.key === '+') {
        e.preventDefault()
        zoomIn()
      } else if (e.key === '-') {
        e.preventDefault()
        zoomOut()
      } else if (e.key === '0') {
        e.preventDefault()
        zoomReset()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [zoomIn, zoomOut, zoomReset])

  const handleOpenProject = async () => {
    const folder = await ipc.invoke('dialog:select-folder')
    if (folder) {
      openProject(folder)
    }
  }

  const zoomLabel = `${Math.round(zoom * 100)}%`

  return (
    <div
      className="writer-topbar no-select flex items-center gap-2"
      style={{
        height: 'var(--height-titlebar)',
        paddingLeft: isMac ? 78 : 14,
        paddingRight: 10,
        WebkitAppRegion: 'drag',
      } as CSSProperties}
    >
      <div className="flex items-center gap-2 flex-shrink-0 min-w-0">
        <div
          className="flex h-8 w-8 items-center justify-center rounded-md"
          style={{
            background: 'linear-gradient(180deg, rgba(255, 239, 205, 0.22), rgba(160, 98, 39, 0.16))',
            border: '1px solid rgba(255, 236, 194, 0.18)',
          }}
        >
          <ScrollText size={18} strokeWidth={1.7} />
        </div>
        <div className="leading-tight min-w-[112px]">
          <div className="text-sm font-semibold brand-gradient">{APP_BRAND.zhName}</div>
          <div className="text-[0.68rem] opacity-75">{APP_BRAND.enName}</div>
        </div>
      </div>

      <div className="flex items-center gap-2 min-w-0 flex-1">
        <button className="writer-command-button" title={t('common.settings')} onClick={() => openSettings()}>
          <Menu size={17} strokeWidth={1.8} />
        </button>

        <span className="text-xs font-semibold opacity-90 whitespace-nowrap">{t('project.currentLabel')}</span>
        <button
          className="writer-command-button max-w-[280px]"
          title={t('project.switch')}
          onClick={handleOpenProject}
        >
          <span className="truncate">{currentProject?.name ?? t('project.none')}</span>
        </button>

        <span
          className="inline-flex items-center gap-1 text-xs font-medium whitespace-nowrap"
          title={hasDirty ? t('save.dirty') : t('save.saved')}
          style={{ color: hasDirty ? 'var(--color-warning)' : '#87d27d' }}
        >
          <CheckCircle2 size={14} strokeWidth={1.9} />
          {hasDirty ? t('save.modified') : t('save.saved')}
        </span>

        <div className="h-5 w-px bg-[rgba(255,244,223,0.24)]" />

        <button className="writer-command-button" title={t('project.backupUnavailable')} disabled>
          <Archive size={14} strokeWidth={1.75} />
          {t('common.backup')}
        </button>
        <button className="writer-command-button" title={t('project.imitation')} onClick={openImportNovel}>
          <Import size={14} strokeWidth={1.75} />
          {t('project.imitationShort')}
        </button>
        <button className="writer-command-button" title={t('project.export')} onClick={openExport}>
          <Upload size={14} strokeWidth={1.75} />
          {t('common.export')}
        </button>
        <button className="writer-command-button" title={t('project.new')} onClick={openNewProject}>
          <FilePlus2 size={14} strokeWidth={1.75} />
          {t('common.new')}
        </button>
        <button className="writer-command-button" title={t('project.open')} onClick={handleOpenProject}>
          <FolderOpen size={14} strokeWidth={1.75} />
          {t('common.open')}
        </button>
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          onClick={zoomOut}
          title={t('zoom.out')}
          className="writer-command-button"
          style={{ minHeight: 24, padding: '0 6px' }}
        >
          <ZoomOut size={13} strokeWidth={1.5} />
        </button>
        <button
          onClick={zoomReset}
          title={t('zoom.reset')}
          className="writer-command-button"
          style={{ minHeight: 24, minWidth: 42, padding: '0 6px', fontFamily: 'var(--font-mono)' }}
        >
          {zoomLabel}
        </button>
        <button
          onClick={zoomIn}
          title={t('zoom.in')}
          className="writer-command-button"
          style={{ minHeight: 24, padding: '0 6px' }}
        >
          <ZoomIn size={13} strokeWidth={1.5} />
        </button>
        <button
          onClick={cycleTheme}
          title={t('theme.label', { name: t(themeLabelKeys[theme]) })}
          className="writer-command-button"
          style={{ minHeight: 24, padding: '0 7px' }}
        >
          <ThemeIcon size={13} strokeWidth={1.5} />
        </button>
        <button
          onClick={() => void toggleLocale()}
          title={t('language.switch')}
          className="writer-command-button"
          style={{ minHeight: 24, padding: '0 7px' }}
        >
          <Languages size={13} strokeWidth={1.5} />
          <span>{locale === 'zh-CN' ? 'EN' : '中文'}</span>
        </button>
        <button
          onClick={() => openSettings()}
          title={t('common.settings')}
          className="writer-command-button"
          style={{ minHeight: 24, padding: '0 7px' }}
        >
          <Settings size={13} strokeWidth={1.5} />
        </button>
        <div className="h-5 w-px bg-[rgba(255,244,223,0.24)] mx-1" />
        <button
          className="writer-command-button"
          title={t('common.minimize')}
          onClick={() => ipc.invoke('window:minimize')}
          style={{ minHeight: 24, padding: '0 7px' }}
        >
          <Minus size={13} />
        </button>
        <button
          className="writer-command-button"
          title={t('common.maximizeRestore')}
          onClick={() => ipc.invoke('window:toggle-maximize')}
          style={{ minHeight: 24, padding: '0 7px' }}
        >
          <Square size={12} />
        </button>
        <button
          className="writer-command-button"
          title={t('common.close')}
          onClick={() => ipc.invoke('window:close')}
          style={{ minHeight: 24, padding: '0 7px' }}
        >
          <X size={14} />
        </button>
      </div>
    </div>
  )
}
