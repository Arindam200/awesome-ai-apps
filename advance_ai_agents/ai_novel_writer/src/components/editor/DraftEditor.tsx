import { useState, useRef, useEffect, useCallback } from 'react'
import { Sparkles, Search, BadgeCheck, Save, FileStack, FileText, Wrench } from 'lucide-react'

import { useProjectStore } from '../../stores/project-store'
import { useEditorStore } from '../../stores/editor-store'
import { useWorkflowStore } from '../../stores/workflow-store'
import CodeMirrorEditor from './CodeMirrorEditor'
import ThreeWayMerge from './ThreeWayMerge'
import { Button } from '../ui/Button'
import { toast } from '../ui/Toast'
import { confirm } from '../ui/Confirm'
import {
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from '../ui/Dialog'
import {
  parseDraftMeta,
  type DraftMeta,
  type DraftStatus,
} from '../../services/workflows/chapter-workflow'
import { getPendingRevisions, getReviewsForVersion, type RevisionEntry } from '../../services/draft-index'
import { readDraftBody } from '../../stores/draft-store'
import { ipc } from '../../services/ipc-client'

import { DRAFT_STATUS_LABEL, DRAFT_STATUS_COLOR } from '../../shared/draft-status'
import { PostProcessStatusPanel } from '../ui/PostProcessStatusPanel'
import { getChapterFinalizeScope } from '../../services/workflows/workflow-utils'
import { guardRepairPostProcess } from '../../services/workflow-guards'

interface Props {
  filePath: string
  content: string
}

/**
 * 草稿编辑器
 * — 顶部工具栏：草稿状态 + 待合并修稿 + AI 修稿(含自定义提示词) / AI 审稿 / 定稿
 * — 正文：CodeMirrorEditor（prose 模式）
 */
export default function DraftEditor({ filePath, content }: Props) {
  // 从系统读取草稿元数据与章节标题
  const [meta, setMeta] = useState<(DraftMeta & { chapterTitle?: string; filePath?: string }) | null>(null)
  const [pendingRevisions, setPendingRevisions] = useState<RevisionEntry[]>([])
  const [reviewCount, setReviewCount] = useState(0)

  // 【BUG1&2 修复】合并视图弹窗数据（不再占用 Tab）
  const [mergeData, setMergeData] = useState<{
    originalContent: string
    modifiedContent: string
    revisionPath: string
  } | null>(null)

  // 后处理失败状态（用于控制是否展示修复按钮）
  const [hasProcessFailure, setHasProcessFailure] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const m = await parseDraftMeta(filePath)
      if (cancelled || !m) return
      const { ipc } = await import('../../services/ipc-client')
      const bps = await ipc.invoke('db:blueprint-get-all')
      const bp = Array.isArray(bps) ? bps.find((b: unknown) => (b as { chapterNumber?: number }).chapterNumber === m.chapterNumber) : null
      setMeta({ ...m, chapterTitle: bp ? (bp as { title?: string }).title : '未知标题', filePath, fileName: `v${m.version}`, createdAt: m.updatedAt ?? m.createdAt })
      // 使用 DB 化的虚拟 chapterDir（用于 draft-index 兼容层解析章节号）
      const chapterDir = `vela://draft/ch${m.chapterNumber}`
      // 检查待合并修稿
      const pending = await getPendingRevisions(chapterDir, m.version)
      if (!cancelled) setPendingRevisions(pending)
      // 检查审稿报告
      const reviews = await getReviewsForVersion(chapterDir, m.version)
      if (!cancelled) setReviewCount(reviews.length)
    }
    load()

    // 数据刷新由 ProjectService 统一处理（FINALIZE_COMPLETE 事件驱动 Store 更新后组件自动重渲染）

    return () => {
      cancelled = true
    }
  }, [filePath])

  const status: DraftStatus = meta?.status ?? 'draft'
  const isReadonly = status === 'finalized' || status === 'archived'

  // 检查是否有相关章节工作流正在运行
  // ✅ 只订阅 activeRuns，不订阅 globalLogs 等高频更新字段
  const activeRuns = useWorkflowStore(s => s.activeRuns)
  const activeChapterRun = activeRuns.find(r =>
    r.type === 'chapter_creation' && meta && (r.title.includes(`第${meta.chapterNumber}章`) || r.title.includes(`第 ${meta.chapterNumber} 章`))
  )
  const isChapterBusy = !!activeChapterRun

  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState<'refine' | 'review' | null>(null)
  const [userRefinePrompt, setUserRefinePrompt] = useState('')
  // 审稿维度多选
  const REVIEW_DIMS = [
    { key: 'continuity', label: '剧情连贯性', desc: '与前文是否矛盾' },
    { key: 'logic', label: '剧情合理性', desc: '因果逻辑、动机、常识' },
    { key: 'character', label: '角色状态', desc: '能力/位置/情感一致性' },
    { key: 'foreshadow', label: '前后章节串联', desc: '伏笔、悬念连贯' },
  ]
  const [reviewDims, setReviewDims] = useState<Record<string, boolean>>(
    Object.fromEntries(REVIEW_DIMS.map(d => [d.key, true]))
  )
  const [charCount, setCharCount] = useState(0)
  const isDirty = useEditorStore(s => s.tabs.find(t => t.filePath === filePath)?.dirty ?? false)
  const currentBodyRef = useRef(content)

  const currentProject = useProjectStore(s => s.currentProject)

  /** 保存（vela://draft/ 走 DB，其他走 FS） */
  const doSave = async (text: string) => {
    setSaving(true)
    try {
      if (filePath.startsWith('vela://draft/') || filePath.startsWith('vela://manuscript/')) {
        const prefix = filePath.startsWith('vela://draft/') ? 'vela://draft/' : 'vela://manuscript/'
        const draftId = parseInt(filePath.replace(prefix, ''))
        await ipc.invoke('db:draft-update-content', draftId, text, text.length)
      } else {
        await ipc.invoke('fs:write-file', filePath, text)
      }
      const tabs = useEditorStore.getState().tabs
      const targetTab = tabs.find(t => t.filePath === filePath)
      if (targetTab) {
        useEditorStore.getState().markTabSaved(targetTab.id)
        useEditorStore.getState().syncTabContent(targetTab.id, text)
      }
    } finally {
      setSaving(false)
    }
  }

  /** 执行 AI 修稿（含用户自定义提示词） */
  const doRefine = async () => {
    if (!currentProject || !meta) return
    try {
      const { useWorkflowStore } = await import('../../stores/workflow-store')
      const { createRefineOnlyWorkflow } = await import('../../services/workflows/chapter-workflow')

      const body = await readDraftBody(filePath)

      useWorkflowStore.getState().startWorkflow(createRefineOnlyWorkflow({
        chapterNumber: meta.chapterNumber,
        chapterTitle: meta.chapterTitle ?? '未知标题',
        draftPath: filePath,
        draftContent: body,
        userRefinePrompt: userRefinePrompt.trim() || undefined,
      }), false)
    } catch (e) {
      toast.error(`修稿启动失败：${e}`)
    }
  }

  /** 执行 AI 审稿 */
  const doReview = async () => {
    if (!currentProject || !meta) return
    try {
      const { useWorkflowStore } = await import('../../stores/workflow-store')
      const { createReviewOnlyWorkflow } = await import('../../services/workflows/chapter-workflow')

      const body = await readDraftBody(filePath)

      useWorkflowStore.getState().startWorkflow(createReviewOnlyWorkflow({
        chapterNumber: meta.chapterNumber,
        chapterTitle: meta.chapterTitle ?? '未知标题',
        draftPath: filePath,
        draftContent: body,
        reviewFocus: REVIEW_DIMS.filter(d => reviewDims[d.key]).map(d => d.label).join('、') || undefined,
      }), false)
    } catch (e) {
      toast.error(`审稿启动失败：${e}`)
    }
  }

  /** 定稿 */
  const doFinalize = async () => {
    if (!meta || isChapterBusy) return
    const ok = await confirm(
      `确定要将第 ${meta.chapterNumber} 章定稿吗？\n\n定稿后章节将标记为完成，不再支持修改和重新后处理。`,
      {
        title: '确认定稿',
        confirmText: '确认定稿',
      }
    )
    if (!ok) return
    try {
      const { useWorkflowStore } = await import('../../stores/workflow-store')
      const { createFinalizeWorkflow } = await import('../../services/workflows/chapter-workflow')

      const body = await readDraftBody(filePath)

      useWorkflowStore.getState().startWorkflow(createFinalizeWorkflow({
        chapterNumber: meta.chapterNumber,
        chapterTitle: meta.chapterTitle ?? '未知标题',
        draftPath: filePath,
        draftContent: body,
      }), false)
    } catch (e) {
      toast.error(`定稿启动失败：${e}`)
    }
  }

  /** 修复定稿后处理 — 只重跑失败的步骤 */
  const doRepairFinalize = useCallback(async () => {
    if (!meta || isChapterBusy) return
    try {
      const guard = await guardRepairPostProcess(meta.chapterNumber)
      if (!guard.ok) {
        toast.error(guard.message || '无法执行修复')
        return
      }
      const { useWorkflowStore } = await import('../../stores/workflow-store')
      const { createRepairFinalizeWorkflow } = await import('../../services/workflows/chapter-workflow')
      useWorkflowStore.getState().startWorkflow(createRepairFinalizeWorkflow(meta.chapterNumber), false)
    } catch (e) {
      toast.error(`修复启动失败：${e}`)
    }
  }, [meta, isChapterBusy])

  /** 打开待合并修稿 —— 弹出式合并视图，不占用原草稿 Tab */
  const openPendingRevision = async (rev: RevisionEntry) => {
    if (!meta) return
    // 使用 vela://revision/{id} 协议路径读取修稿内容
    const revPath = `vela://revision/${rev.id}`

    // 读取原稿和修稿
    const [origContent, revContent] = await Promise.all([
      readDraftBody(filePath),
      readDraftBody(revPath),
    ])
    if (!origContent && !revContent) return

    // 设置弹窗数据，不再打开新 Tab
    setMergeData({
      originalContent: origContent,
      modifiedContent: revContent,
      revisionPath: revPath,
    })
  }

  /** 合并完成回调 —— 就地覆写原草稿（不新建版本，仅蓝图写稿时才产生新版本） */
  const handleMergeComplete = async (mergedText: string) => {
    if (!meta || !mergeData) return
    const chapterDir = `vela://draft/ch${meta.chapterNumber}`

    try {
      const { useDraftStore } = await import('../../stores/draft-store')
      const result = await useDraftStore.getState().applyMergedRevision(
        chapterDir,
        meta.chapterNumber,
        filePath,
        mergeData.revisionPath,
        mergedText
      )

      if (result.success) {
        // 关闭弹窗 + 刷新待合并列表 + 更新本地元数据
        setMergeData(null)
        setMeta(prev => prev ? { ...prev, status: 'revised' } : prev)
        toast.success('✅ 合并完成，草稿已更新')
        const { getPendingRevisions } = await import('../../services/draft-index')
        const pending = await getPendingRevisions(chapterDir, meta.version)
        setPendingRevisions(pending)
      } else {
        toast.error(`合并失败：${result.error}`)
      }
    } catch (e) {
      toast.error(`合并出错：${e}`)
    }
  }

  /** 打开最新的审稿报告 */
  const openLatestReview = async () => {
    if (!meta) return
    const chapterDir = `vela://draft/ch${meta.chapterNumber}`
    const { getLatestReview } = await import('../../services/draft-index')
    const latest = await getLatestReview(chapterDir, meta.version)
    if (!latest) return

    // 使用 review 的数据库 ID 读取审稿报告内容
    const reportContent = await readDraftBody(`vela://review/${latest.id}`)
    if (!reportContent) return

    useEditorStore.getState().openFile({
      id: `review-report-${meta.chapterNumber}-${latest.id}`,
      name: `审稿报告 v${meta.version}`,
      type: 'review-report',
      content: reportContent,
      filePath,
      reviewReport: reportContent,
      chapterNumber: meta.chapterNumber,
      chapterDir,
    })
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 顶部工具栏 */}
      <div
        className="flex items-center justify-between gap-2 px-3 h-9 flex-shrink-0"
        style={{
          borderBottom: '1px solid var(--color-border)',
          backgroundColor: 'var(--color-editor-bg)',
        }}
      >
        {/* 左侧：章节标题 + 版本 */}
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-xs font-medium truncate" style={{ color: 'var(--color-text-secondary)' }}>
            {meta ? `第 ${meta.chapterNumber} 章 — ${meta.chapterTitle}` : '草稿'}
          </span>
          {meta && (
            <span className="text-[0.7rem] flex-shrink-0" style={{ color: 'var(--color-text-muted)' }}>
              v{meta.version}
            </span>
          )}
        </div>

        {/* 右侧：字数 + 状态 + 待合并 + AI操作 + 定稿 */}
        {!isReadonly && (
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {/* 字数 */}
            {charCount > 0 && (
              <span className="text-xs tabular-nums mr-1" style={{ color: 'var(--color-text-muted)' }}>
                {charCount.toLocaleString()} 字
              </span>
            )}

            {/* 未保存指示灯 */}
            {isDirty && (
              <span
                className="w-1.5 h-1.5 rounded-full flex-shrink-0 mr-0.5"
                style={{ backgroundColor: 'var(--color-warning)' }}
                title="有未保存的修改"
              />
            )}

            {/* 保存按钮 */}
            {isDirty && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => doSave(currentBodyRef.current)}
                disabled={saving}
                title="保存（⌘S）"
              >
                <Save size={12} />
                {saving ? '保存中...' : '保存'}
              </Button>
            )}

            {/* 状态标签 */}
            <span
              className="text-[0.7rem] px-1.5 py-0.5 rounded flex-shrink-0"
              style={{
                backgroundColor: 'var(--color-hover)',
                color: DRAFT_STATUS_COLOR[status] ?? 'var(--color-text-muted)',
              }}
            >
              {DRAFT_STATUS_LABEL[status] ?? status}
            </span>

            {/* 📋 待合并修稿 */}
            {pendingRevisions.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => openPendingRevision(pendingRevisions[0])}
                title="有待合并的修稿，点击打开三栏合并视图"
              >
                <FileStack size={12} />
                待合并({pendingRevisions.length})
              </Button>
            )}

            {/* 📝 审稿报告 */}
            {reviewCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={openLatestReview}
                title="查看最新审稿报告"
              >
                <FileText size={12} />
                审稿报告({reviewCount})
              </Button>
            )}

            {/* AI 修稿 */}
            <Button
              variant="ai"
              size="sm"
              onClick={() => { setUserRefinePrompt(''); setConfirmAction('refine') }}
              disabled={isChapterBusy}
              title="AI 修稿 — 大神级润色，生成修稿并打开合并视图"
            >
              <Sparkles size={12} />
              AI 修稿
            </Button>

            {/* AI 审稿 */}
            <Button
              variant="ai"
              size="sm"
              onClick={() => setConfirmAction('review')}
              disabled={isChapterBusy}
              title="AI 审稿 — 一致性检查，生成审稿报告"
            >
              <Search size={12} />
              AI 审稿
            </Button>

            {/* 定稿 */}
            <Button
              variant="success"
              size="sm"
              onClick={doFinalize}
              disabled={isChapterBusy}
              title="定稿 — 确认终稿并写入正文章节"
            >
              <BadgeCheck size={12} />
              定稿
            </Button>
          </div>
        )}

        {/* 已定稿/归档显示只读提示 */}
        {isReadonly && (
          <div className="flex items-center gap-2 flex-shrink-0">
            {charCount > 0 && (
              <span className="text-xs tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                {charCount.toLocaleString()} 字
              </span>
            )}
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {status === 'finalized' ? '已定稿（只读）' : '已归档（只读）'}
            </span>
            {/* 已定稿 → 有失败项时显示修复定稿按钮 */}
            {status === 'finalized' && meta && hasProcessFailure && (
              <Button
                variant="outline"
                size="sm"
                onClick={doRepairFinalize}
                disabled={isChapterBusy}
                title="重新执行失败的后处理步骤（角色卡、知识库等）"
              >
                <Wrench size={11} />
                修复定稿
              </Button>
            )}
          </div>
        )}
      </div>

      {/* 后处理状态面板（仅定稿草稿显示） */}
      {status === 'finalized' && meta && (
        <div className="px-3 py-1.5" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <PostProcessStatusPanel
            scope={getChapterFinalizeScope(meta.chapterNumber)}
            onRetry={() => doRepairFinalize()}
            onStatusLoad={setHasProcessFailure}
          />
        </div>
      )}

      {/* 正文区 */}
      <div className="flex-1 overflow-hidden relative">
        <CodeMirrorEditor
          mode="prose"
          content={content}
          filePath={filePath}
          editable={!isReadonly && !isChapterBusy}
          hideStatusBar
          onCharCountChange={setCharCount}
          onChange={(text) => {
            currentBodyRef.current = text
            useEditorStore.getState().updateTabContent(filePath, text)
          }}
          onSave={(text) => doSave(text)}
        />


      </div>

      {/* AI 操作确认弹窗（修稿含自定义提示词输入框） */}
      <Dialog open={confirmAction !== null} onOpenChange={(v) => !v && setConfirmAction(null)}>
        <DialogContent className="max-w-[440px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles size={15} className="text-[var(--color-accent)]" />
              {confirmAction === 'refine' ? 'AI 修稿确认' : 'AI 审稿确认'}
            </DialogTitle>
            <DialogDescription>
              对象：{meta ? `${meta.chapterTitle} v${meta.version}` : '当前草稿'}
            </DialogDescription>
          </DialogHeader>
          <div className="px-5 py-2 text-sm space-y-1.5" style={{ color: 'var(--color-text-secondary)' }}>
            {confirmAction === 'refine' ? (
              <>
                <div className="font-medium text-[var(--color-text)]">本次【直接修稿】范围：</div>
                <div>1. 全文基础润色、词汇优化，增强画面与表现力。</div>
                <div>2. 可在下方指定的额外修稿要求。</div>
              </>
            ) : (
              <>
                <div>将调用 AI 对本章草稿进行一致性检查，并生成审稿报告。</div>
                <div className="mt-3">
                  <div className="text-xs font-medium mb-2" style={{ color: 'var(--color-text)' }}>重点检查维度：</div>
                  <div className="flex flex-wrap gap-2">
                    {REVIEW_DIMS.map(d => (
                      <label
                        key={d.key}
                        className="flex items-center gap-1.5 cursor-pointer select-none px-2 py-1 rounded-md text-xs"
                        style={{
                          border: `1px solid ${reviewDims[d.key] ? 'var(--color-accent)' : 'var(--color-border)'}`,
                          backgroundColor: reviewDims[d.key] ? 'rgba(var(--color-accent-rgb),0.1)' : 'transparent',
                          color: reviewDims[d.key] ? 'var(--color-accent)' : 'var(--color-text-muted)',
                        }}
                        onClick={() => setReviewDims(prev => ({ ...prev, [d.key]: !prev[d.key] }))}
                      >
                        <div
                          className="w-3 h-3 rounded flex items-center justify-center flex-shrink-0"
                          style={{
                            backgroundColor: reviewDims[d.key] ? 'var(--color-accent)' : 'transparent',
                            border: `1.5px solid ${reviewDims[d.key] ? 'var(--color-accent)' : 'var(--color-border)'}`,
                          }}
                        >
                          {reviewDims[d.key] && (
                            <svg width="7" height="5" viewBox="0 0 9 7" fill="none"><path d="M1 3L3.5 5.5L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                          )}
                        </div>
                        {d.label}
                      </label>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* 修稿时显示自定义提示词输入框 */}
          {confirmAction === 'refine' && (
            <div className="px-5 pb-2">
              <label className="text-xs font-medium block mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                附加修稿要求（可选）：
              </label>
              <textarea
                className="w-full px-3 py-2 rounded-md text-sm"
                style={{
                  background: 'var(--color-bg-elevated)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text)',
                  minHeight: 72,
                  resize: 'vertical',
                  outline: 'none',
                }}
                placeholder="例如：加强打斗场面的画面感；把结尾的伏笔改为更隐晦的暗示；对白太书面化，改为口语化风格..."
                value={userRefinePrompt}
                onChange={e => setUserRefinePrompt(e.target.value)}
              />
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmAction(null)}>取消</Button>
            <Button
              variant="ai"
              onClick={() => {
                const act = confirmAction
                setConfirmAction(null)
                if (act === 'refine') doRefine()
                else if (act === 'review') doReview()
              }}
            >
              确认执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 弹出式三栏合并视图 —— 使用统一 Dialog 组件 */}
      <Dialog open={mergeData !== null} onOpenChange={(v) => !v && setMergeData(null)}>
        <DialogContent
          className="p-0"
          style={{
            width: '90vw',
            maxWidth: '90vw',
            height: '85vh',
            maxHeight: '85vh',
            overflow: 'hidden',
          }}
          /* 阻止点击遮罩关闭，防止误触丢失合并进度 */
          onPointerDownOutside={(e) => e.preventDefault()}
          onEscapeKeyDown={(e) => e.preventDefault()}
        >
          <DialogHeader className="px-4 py-0" style={{ height: 38, display: 'flex', alignItems: 'center' }}>
            <DialogTitle className="flex items-center gap-2 text-[0.8rem]">
              修稿合并 — 第{meta?.chapterNumber}章 {meta?.chapterTitle}
            </DialogTitle>
          </DialogHeader>
          {/* 合并视图主体 */}
          <div className="flex-1 overflow-hidden" style={{ height: 'calc(85vh - 38px - 1px)' }}>
            {mergeData && (
              <ThreeWayMerge
                originalContent={mergeData.originalContent}
                modifiedContent={mergeData.modifiedContent}
                onComplete={handleMergeComplete}
                onCancel={() => setMergeData(null)}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
