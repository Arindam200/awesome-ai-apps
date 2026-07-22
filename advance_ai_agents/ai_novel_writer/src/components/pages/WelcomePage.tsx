import { Sparkles, FolderOpen, Clock, BookOpen, FileUp } from 'lucide-react'
import { useProjectStore } from '../../stores/project-store'
import { APP_BRAND } from '../../shared/brand'
import { useLocaleStore } from '../../stores/locale-store'

interface WelcomePageProps {
  onNewProject: () => void
  onOpenProject: () => void
  onImportNovel?: () => void
}

/** 欢迎页面 — 无项目打开时显示 */
export default function WelcomePage({ onNewProject, onOpenProject, onImportNovel }: WelcomePageProps) {
  const recentProjects = useProjectStore(s => s.recentProjects)
  const openProject = useProjectStore(s => s.openProject)
  const currentProject = useProjectStore(s => s.currentProject)
  const text = useLocaleStore(s => s.text)

  return (
    <div
      className="writer-shell-surface w-full h-full overflow-y-auto"
    >
      <div className="max-w-lg w-full mx-auto px-8 py-16">
        {/* Logo 区域 — 品牌极光光环 */}
        <div className="text-center mb-12">
          <div
            className="writer-primary-button inline-flex items-center justify-center w-20 h-20 rounded-2xl mb-5"
            style={{
              boxShadow: '0 8px 28px rgba(82, 52, 22, 0.18)',
            }}
          >
            <BookOpen size={36} color="#fff" style={{ position: 'relative', zIndex: 1 }} />
          </div>
          <h1 className="text-2xl font-bold mb-2" style={{ color: 'var(--color-text)' }}>
            {currentProject ? currentProject.name : text(`欢迎使用 ${APP_BRAND.zhName}`, `Welcome to ${APP_BRAND.enName}`)}
          </h1>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            {currentProject ? currentProject.path : APP_BRAND.tagline}
          </p>
        </div>

        {/* 操作按钮 */}
        <div className="grid grid-cols-3 gap-3 mb-10">
          <button
            onClick={onNewProject}
            className="writer-panel-card group flex flex-col items-center gap-2.5 p-5 transition-all hover:scale-[1.02]"
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'rgba(138, 91, 46, 0.42)'
              e.currentTarget.style.boxShadow = '0 4px 20px rgba(82, 52, 22, 0.10)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = '#d6c09f'
              e.currentTarget.style.boxShadow = 'none'
            }}
          >
            <div
              className="writer-primary-button flex items-center justify-center w-10 h-10 rounded-xl transition-transform group-hover:scale-105"
            >
              <Sparkles size={20} />
            </div>
            <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              {text('新建项目', 'New project')}
            </span>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {text('创建一部新的小说', 'Start a new novel')}
            </span>
          </button>

          <button
            onClick={onOpenProject}
            className="writer-panel-card group flex flex-col items-center gap-2.5 p-5 transition-all hover:scale-[1.02]"
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'rgba(201, 167, 108, 0.4)'
              e.currentTarget.style.boxShadow = '0 4px 20px rgba(201, 167, 108, 0.08)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = '#d6c09f'
              e.currentTarget.style.boxShadow = 'none'
            }}
          >
            <div
              className="flex items-center justify-center w-10 h-10 rounded-xl transition-transform group-hover:scale-105"
              style={{ backgroundColor: 'var(--color-hover)', color: 'var(--color-text)' }}
            >
              <FolderOpen size={20} />
            </div>
            <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              {text('打开项目', 'Open project')}
            </span>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {text('打开已有小说项目', 'Open an existing novel')}
            </span>
          </button>

          <button
            onClick={onImportNovel}
            className="writer-panel-card group flex flex-col items-center gap-2.5 p-5 transition-all hover:scale-[1.02]"
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'rgba(134, 193, 120, 0.4)'
              e.currentTarget.style.boxShadow = '0 4px 20px rgba(134, 193, 120, 0.10)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = '#d6c09f'
              e.currentTarget.style.boxShadow = 'none'
            }}
          >
            <div
              className="flex items-center justify-center w-10 h-10 rounded-xl transition-transform group-hover:scale-105"
              style={{ backgroundColor: 'rgba(134, 193, 120, 0.12)', color: 'rgb(134, 193, 120)' }}
            >
              <FileUp size={20} />
            </div>
            <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              {text('拆解仿写', 'Style study')}
            </span>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {text('上传参考小说生成风格约束', 'Analyze a reference novel')}
            </span>
          </button>
        </div>

        {/* 最近项目 */}
        {recentProjects.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-3">
              <Clock size={14} style={{ color: 'var(--color-text-muted)' }} />
              <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                {text('最近项目', 'Recent projects')}
              </span>
            </div>
            <div className="space-y-1">
              {recentProjects.map((p, i) => (
                <div
                  key={i}
                  className="group flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all"
                  style={{ backgroundColor: 'transparent', borderLeft: '2px solid transparent' }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--color-hover)'
                    e.currentTarget.style.borderLeftColor = 'var(--color-accent)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent'
                    e.currentTarget.style.borderLeftColor = 'transparent'
                  }}
                  onClick={() => openProject(p.path)}
                >
                  <BookOpen size={14} style={{ color: 'var(--color-accent)', opacity: 0.6 }} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm block truncate" style={{ color: 'var(--color-text)' }}>
                      {p.name}
                    </span>
                    <span className="text-xs block truncate" style={{ color: 'var(--color-text-muted)' }}>
                      {p.path}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="text-center mt-12">
          <p className="text-xs" style={{ color: 'var(--color-text-muted)', opacity: 0.7 }}>
            {text(
              `${APP_BRAND.zhName} · 七阶段 AI 驱动创作流水线 · 本地数据安全`,
              `${APP_BRAND.enName} · Seven-stage AI writing pipeline · Local data control`,
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
