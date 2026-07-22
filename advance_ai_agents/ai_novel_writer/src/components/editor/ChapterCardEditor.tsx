import { useState, useEffect, useCallback } from 'react'
import {
  Save, BookOpen, RefreshCw, Plus, Trash2,
  Sparkles, PenLine
} from 'lucide-react'
import { useProjectStore } from '../../stores/project-store'
import { useWorkflowStore } from '../../stores/workflow-store'
import { useLayoutStore } from '../../stores/layout-store'
import { ipc } from '../../services/ipc-client'
import {
  loadDirectoryBlueprints,
  saveChapterBlueprint,
  saveAllBlueprints,
  createDirectoryWorkflow,
  type ChapterBlueprint,
  type DirectoryWorkflowParams,
} from '../../services/workflows/directory-workflow'
import { guardDirectoryGeneration } from '../../services/workflow-guards'
import DirectoryConfigDialog from '../dialogs/DirectoryConfigDialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Textarea } from '../ui/Textarea'
import { Label } from '../ui/Label'
import { NativeSelect } from '../ui/NativeSelect'
import { cn } from '../../lib/utils'
import { toast } from '../ui/Toast'
import { confirm } from '../ui/Confirm'
import { globalEventBus } from '../../shared/event-bus'
import { shouldRefreshBlueprints } from './blueprint-refresh'

const ROLES = ['建置', '铺垫', '发展', '冲突', '高潮', '转折', '收尾']

const ROLE_COLORS: Record<string, string> = {
  高潮: 'bg-red-500/20 text-red-400',
  冲突: 'bg-orange-500/20 text-orange-400',
  转折: 'bg-purple-500/20 text-purple-400',
  建置: 'bg-blue-500/20 text-blue-400',
  收尾: 'bg-green-500/20 text-green-400',
}

/** 章节蓝图编辑器 — 读写 directory.json */
export default function ChapterCardEditor() {
  const currentProject = useProjectStore(s => s.currentProject)
  // ✅ action 用 getState() 获取，不订阅 workflow store 高频更新
  const startWorkflow = useWorkflowStore.getState().startWorkflow
  const addLog = useWorkflowStore.getState().addLog
  const [blueprints, setBlueprints] = useState<ChapterBlueprint[]>([])
  const [selectedIdx, setSelectedIdx] = useState<number>(0)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [dirty, setDirty] = useState(false)
  // 下一个可写的章节号
  const [nextWriteChapter, setNextWriteChapter] = useState<number | null>(null)

  // 蓝图生成弹窗（替代原 inline 批量面板）
  const [showBlueprintDialog, setShowBlueprintDialog] = useState(false)

  const loadBlueprints = useCallback(async () => {
    if (!currentProject) return
    setLoading(true)
    try {
      const data = await loadDirectoryBlueprints()
      setBlueprints(data)
      if (data.length > 0) setSelectedIdx(0)
      // 获取下一个待写章节号
      const maxFinalized = await ipc.invoke('db:draft-get-max-finalized-chapter')
      setNextWriteChapter(maxFinalized !== null ? maxFinalized + 1 : 1)
    } catch {
      addLog('error', '读取章节蓝图失败')
    }
    setLoading(false)
    setDirty(false)
  }, [currentProject, addLog])

  useEffect(() => {
    let mounted = true
    Promise.resolve().then(() => { if (mounted) loadBlueprints() })
    return () => { mounted = false }
  }, [loadBlueprints])

  // 监听工作流完成事件，如果蓝图生成完毕则自动刷新
  useEffect(() => {
    return globalEventBus.on('WORKFLOW_COMPLETE', (payload) => {
      if (payload.type === 'directory') {
        loadBlueprints()
      }
    })
  }, [loadBlueprints])

  useEffect(() => {
    return globalEventBus.on('REFRESH_RESOURCE', (payload) => {
      if (shouldRefreshBlueprints(payload.resources)) {
        loadBlueprints()
      }
    })
  }, [loadBlueprints])

  const selected = blueprints[selectedIdx] ?? null

  /** 更新选中章节蓝图的字段 */
  const updateField = <K extends keyof ChapterBlueprint>(key: K, value: ChapterBlueprint[K]) => {
    setBlueprints(prev =>
      prev.map((b, i) => (i === selectedIdx ? { ...b, [key]: value } : b))
    )
    setDirty(true)
  }

  /** 保存当前章节蓝图 */
  const handleSaveOne = async () => {
    if (!currentProject || !selected) return
    setSaving(true)
    try {
      await saveChapterBlueprint(selected)
      setDirty(false)
      addLog('info', `✅ 第 ${selected.chapterNumber} 章蓝图已保存`)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      addLog('error', `保存第 ${selected.chapterNumber} 章蓝图失败：${message}`)
      toast.error(`保存失败\n\n${message}`)
    } finally {
      setSaving(false)
    }
  }

  /** 全量保存到 SQLite */
  const handleSaveAll = async () => {
    if (!currentProject) return
    setSaving(true)
    try {
      await saveAllBlueprints(blueprints)
      setDirty(false)
      addLog('info', `✅ 已保存全部 ${blueprints.length} 章蓝图`)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      addLog('error', `保存全部蓝图失败：${message}`)
      toast.error(`保存失败\n\n${message}`)
    } finally {
      setSaving(false)
    }
  }

  /** 新建空章节 */
  const handleAddChapter = () => {
    const maxNum = blueprints.reduce((m, b) => Math.max(m, b.chapterNumber), 0)
    const newBlueprint: ChapterBlueprint = {
      chapterNumber: maxNum + 1,
      title: '',
      role: '发展',
      purpose: '',
      keyEvents: '',
      characters: [],
      suspenseHook: '',
      userGuidance: '',
      notes: '',
      notesUpdatedAt: '',
    }
    setBlueprints(prev => [...prev, newBlueprint])
    setSelectedIdx(blueprints.length)
    setDirty(true)
  }

  /** 删除选中章节 */
  const handleDeleteChapter = async () => {
    if (!selected) return
    const ok = await confirm(`确认删除第 ${selected.chapterNumber} 章蓝图？\n此操作不可撤销。`, {
      title: '删除章节蓝图',
      confirmText: '删除',
      danger: true,
    })
    if (!ok) return
    const result = await ipc.invoke('db:blueprint-delete', selected.chapterNumber)
    if (!result.success) {
      toast.error(`删除失败\n\n${result.error ?? '未知错误'}`)
      return
    }
    const nextList = blueprints.filter((_, i) => i !== selectedIdx)
    setBlueprints(nextList)
    setSelectedIdx(Math.max(0, Math.min(selectedIdx, nextList.length - 1)))
    setDirty(false)
    globalEventBus.emit('REFRESH_RESOURCE', { resources: ['blueprints', 'fileTree'] })
    toast.success(`已删除第 ${selected.chapterNumber} 章蓝图`)
  }

  /** 清空全部章节蓝图 */
  const handleClearAllBlueprints = async () => {
    if (blueprints.length === 0) return
    const ok = await confirm(`确认清空全部 ${blueprints.length} 章蓝图？\n此操作不可撤销，但不会删除草稿或正文章节。`, {
      title: '清空全部蓝图',
      confirmText: '清空全部',
      danger: true,
    })
    if (!ok) return

    const result = await ipc.invoke('db:blueprint-clear-all')
    if (!result.success) {
      toast.error(`清空失败\n\n${result.error ?? '未知错误'}`)
      return
    }
    setBlueprints([])
    setSelectedIdx(0)
    setDirty(false)
    globalEventBus.emit('REFRESH_RESOURCE', { resources: ['blueprints', 'fileTree'] })
    toast.success('已清空全部蓝图')
  }

  /** 触发蓝图批量生成（来自 DirectoryConfigDialog 的确认回调） */
  const handleBatchGenerate = async (params: DirectoryWorkflowParams) => {
    if (!currentProject) return

    // 前置校验：故事架构是否就绪
    const guard = await guardDirectoryGeneration()
    if (!guard.ok) {
      // 校验失败：阻断并提示
      addLog('error', `⚠️ 前置条件未满足：${guard.message}`)
      toast.warning(`无法出发\n\n${guard.message}`)
      return
    }
    if (guard.message) {
      // 有警告但允许继续：弹出确认
      const yes = await confirm(`${guard.message}\n\n是否仍要继续生成？`, {
        title: '前置条件警告',
        confirmText: '继续生成',
      })
      if (!yes) return
    }

    startWorkflow(createDirectoryWorkflow(params))
    addLog('info', '🚀 已启动章节蓝图生成')
  }

  /**
   * 写作此章 — 将当前蓝图信息注入创作弹窗
   * 支持指定章节（默认为当前选中章）
   */
  const handleWriteChapter = (bp: ChapterBlueprint) => {
    // 通过 layout-store openChapterCreation 传递预填参数，替代 window.dispatchEvent
    useLayoutStore.getState().openChapterCreation({
      chapterNumber: bp.chapterNumber,
      title: bp.title,
      role: bp.role,
      purpose: bp.purpose,
      keyEvents: bp.keyEvents,
      characters: bp.characters.join('、'),
      userGuidance: bp.userGuidance || '',
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full gap-2" style={{ color: 'var(--color-text-muted)' }}>
        <RefreshCw size={16} className="animate-spin" /> 加载章节蓝图...
      </div>
    )
  }

  if (!currentProject) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40">
        <BookOpen size={36} />
        <span className="text-sm">请先打开项目</span>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 顶部工具栏 */}
      <div
        className="flex items-center justify-between gap-2 px-3 h-10 flex-shrink-0 border-b"
        style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-sidebar)' }}
      >
        <div className="flex items-center gap-1.5">
          <BookOpen size={13} style={{ color: 'var(--color-text-muted)' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            章节蓝图
            {blueprints.length > 0 && (
              <span style={{ color: 'var(--color-text-muted)' }} className="ml-1 font-normal">
                ({blueprints.length} 章)
              </span>
            )}
          </span>
          {dirty && <span className="text-[0.7rem]" style={{ color: 'var(--color-accent)' }}>● 未保存</span>}
        </div>
        <div className="flex items-center gap-1">
          {/* 写作入口 — 仅下一章可写时显示 */}
          {nextWriteChapter !== null && (
            <Button
              variant="ai"
              size="sm"
              onClick={() => {
                const bp = blueprints.find(b => b.chapterNumber === nextWriteChapter)
                if (bp) handleWriteChapter(bp)
              }}
            >
              <PenLine size={12} />
              写作第{nextWriteChapter}章
            </Button>
          )}
          {/* AI 生成蓝图 → 弹出 DirectoryConfigDialog */}
          <Button
            variant="ai"
            size="sm"
            onClick={() => setShowBlueprintDialog(true)}
            title="AI 生成章节蓝图（选择范围和模式）"
          >
            <Sparkles size={12} />
            AI 生成蓝图
          </Button>
          <Button variant="ghost" size="icon" onClick={() => loadBlueprints()} title="重新加载" disabled={loading}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </Button>
          <Button variant="ghost" size="icon" onClick={handleAddChapter} title="新建章节">
            <Plus size={14} />
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleClearAllBlueprints}
            disabled={saving || blueprints.length === 0}
            title="清空全部章节蓝图"
          >
            <Trash2 size={12} />
            清空全部蓝图
          </Button>
          {dirty && (
            <Button variant="outline" size="sm" onClick={handleSaveAll} disabled={saving}>
              <Save size={12} /> {saving ? '保存中...' : '保存全部'}
            </Button>
          )}
        </div>
      </div>

      {/* 蓝图生成配置弹窗 */}
      <DirectoryConfigDialog
        isOpen={showBlueprintDialog}
        onClose={() => setShowBlueprintDialog(false)}
        existingCount={blueprints.length}
        onConfirm={handleBatchGenerate}
      />

      {/* 主区域：左侧列表 + 右侧编辑 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧章节列表 */}
        <div
          className="flex flex-col flex-shrink-0 w-[200px] border-r overflow-hidden"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-sidebar)' }}
        >
          {blueprints.length === 0 ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-3 opacity-40 p-4">
              <BookOpen size={28} />
              <span className="text-xs text-center">暂无蓝图，点击「AI 生成」开始</span>
            </div>
          ) : (
          <div className="flex-1 overflow-y-auto p-1">
            {blueprints.map((bp, idx) => (
              <div
                key={bp.chapterNumber}
                className={cn(
                  'group relative px-2.5 py-2 rounded-md text-xs cursor-pointer mb-0.5 transition-colors',
                  selectedIdx === idx
                    ? 'bg-[var(--color-active)] text-[var(--color-text)]'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)]'
                )}
                onClick={() => setSelectedIdx(idx)}
              >
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-[0.7rem] opacity-40 flex-shrink-0">
                    {bp.chapterNumber}
                  </span>
                  <span className="font-medium truncate flex-1">{bp.title || '未命名'}</span>
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className={cn(
                    'text-[0.7rem] px-1 py-0.5 rounded',
                    ROLE_COLORS[bp.role] || 'bg-[var(--color-hover)] text-[var(--color-text-muted)]'
                  )}>
                    {bp.role}
                  </span>
                  {bp.userGuidance && (
                    <span
                      className="text-[0.7rem] px-1 py-0.5 rounded"
                      style={{ backgroundColor: 'rgba(var(--accent-rgb), 0.15)', color: 'var(--color-accent)' }}
                      title="已有作者微操指导"
                    >
                      有指导
                    </span>
                  )}
                  {bp.notes && (
                    <span
                      className="text-[0.7rem] px-1 py-0.5 rounded"
                      style={{ backgroundColor: 'rgba(34,197,94,0.15)', color: 'rgb(34,197,94)' }}
                      title="已生成章节要点"
                    >
                      有要点
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
          )}
        </div>

        {/* 右侧编辑区 */}
        <div className="flex-1 overflow-y-auto">
          {selected ? (
            <div className="max-w-2xl mx-auto px-5 py-4">
              {/* 编辑区头部 */}
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold" style={{ color: 'var(--color-text)' }}>
                  第 {selected.chapterNumber} 章：{selected.title || '未命名'}
                </h3>
                <div className="flex items-center gap-1.5">
                  {/* 仅下一章允许写作 */}
                  {nextWriteChapter !== null && selected.chapterNumber === nextWriteChapter && (
                    <Button
                      variant="ai"
                      size="sm"
                      onClick={() => handleWriteChapter(selected)}
                      title="以当前蓝图信息生成草稿"
                    >
                      <PenLine size={12} /> 写作此章
                    </Button>
                  )}
                  <Button variant="destructive" size="sm" onClick={handleDeleteChapter} title="删除此章">
                    <Trash2 size={12} />
                    删除此章
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleSaveOne} disabled={saving}>
                    <Save size={12} /> {saving ? '保存中...' : '保存'}
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                {/* 基本信息 */}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <Label>章节号</Label>
                    <Input
                      type="number"
                      value={selected.chapterNumber}
                      onChange={e => updateField('chapterNumber', (e.target.value === '' ? '' : parseInt(e.target.value)) as number)}
                      onBlur={() => {
                        const v = Number(selected.chapterNumber);
                        if (!v || v < 1) updateField('chapterNumber', 1)
                      }}
                    />
                  </div>
                  <div className="col-span-2">
                    <Label>章节标题</Label>
                    <Input
                      value={selected.title}
                      onChange={e => updateField('title', e.target.value)}
                      placeholder="引人入胜的章节标题"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>章节定位</Label>
                    <NativeSelect value={selected.role} onChange={e => updateField('role', e.target.value)}>
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </NativeSelect>
                  </div>
                  <div>
                    <Label>出场关键人（逗号分隔）</Label>
                    <Input
                      value={selected.characters.join('、')}
                      onChange={e => updateField('characters', e.target.value.split(/[,，、\s]+/).filter(Boolean))}
                      placeholder="如：主角、反派A"
                    />
                  </div>
                </div>

                <div>
                  <Label>主角小目标（本章最想解决的事）</Label>
                  <Textarea
                    value={selected.purpose}
                    onChange={e => updateField('purpose', e.target.value)}
                    placeholder="本章主角最迫切要解决的一件事..."
                    rows={2}
                  />
                </div>

                <div>
                  <Label>实质冲突与转折</Label>
                  <Textarea
                    value={selected.keyEvents}
                    onChange={e => updateField('keyEvents', e.target.value)}
                    placeholder="主角做了什么，遭遇了什么反转，金手指怎么用的..."
                    rows={4}
                  />
                </div>

                <div>
                  <Label>末尾悬念钩子</Label>
                  <Textarea
                    value={selected.suspenseHook}
                    onChange={e => updateField('suspenseHook', e.target.value)}
                    placeholder="一句话说明结尾留了什么悬念..."
                    rows={2}
                  />
                </div>

                {/* 作者微操指导 — 特别标注，写稿时注入为最高优先级 */}
                <div
                  className="p-3 rounded-lg border"
                  style={{
                    borderColor: 'var(--color-accent)',
                    backgroundColor: 'rgba(var(--accent-rgb, 99 102 241), 0.06)',
                  }}
                >
                  <Label className="flex items-center gap-1.5">
                    <span>作者微操指导</span>
                    <span
                      className="text-[0.7rem] font-normal"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      （写稿时会作为最高优先级注入 AI — 可覆盖蓝图）
                    </span>
                  </Label>
                  <Textarea
                    value={selected.userGuidance}
                    onChange={e => updateField('userGuidance', e.target.value)}
                    placeholder="我想在这章加入一个意外的背叛...&#10;让反派在这章露出破绽...&#10;（不填则完全按蓝图走）"
                    rows={3}
                    style={{ marginTop: 6 }}
                  />
                </div>
                {/* 章节要点（定稿后自动生成，也可手动编辑） */}
                <div
                  className="p-3 rounded-lg border"
                  style={{
                    borderColor: 'var(--color-border)',
                    backgroundColor: 'rgba(34,197,94,0.04)',
                  }}
                >
                  <Label className="flex items-center gap-1.5">
                    <span>章节要点</span>
                    <span
                      className="text-[0.7rem] font-normal"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      {selected.notesUpdatedAt
                        ? `（定稿后自动生成 — ${new Date(selected.notesUpdatedAt).toLocaleDateString('zh-CN')}）`
                        : '（定稿后自动生成，也可手动填写）'
                      }
                    </span>
                  </Label>
                  <Textarea
                    value={selected.notes || ''}
                    onChange={e => updateField('notes', e.target.value)}
                    placeholder="定稿后 AI 会自动填充本章要点（事件进展/角色变化/伏笔埋点）…＊也可以提前手动输入给 AI 作参考"
                    rows={4}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-3 opacity-30">
              <BookOpen size={36} />
              <span className="text-sm">在左侧选择一章开始编辑</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
