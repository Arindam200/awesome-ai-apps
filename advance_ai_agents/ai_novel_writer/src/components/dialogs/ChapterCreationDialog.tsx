import { useState, useEffect, useCallback } from 'react'
import { Sparkles, Play, AlertCircle, Loader2 } from 'lucide-react'
import { useProjectStore } from '../../stores/project-store'
import { useLLMStore } from '../../stores/llm-store'
import { useWorkflowStore } from '../../stores/workflow-store'

import { createChapterWorkflow } from '../../services/workflows/chapter-workflow'
import { guardChapterWriting } from '../../services/workflow-guards'
import { ipc } from '../../services/ipc-client'
import { toast } from '../ui/Toast'
import {
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Textarea } from '../ui/Textarea'
import { Label } from '../ui/Label'
import { NativeSelect } from '../ui/NativeSelect'
import { useLocaleStore } from '../../stores/locale-store'

const CHAPTER_ROLES = [
  { value: '开篇', en: 'Opening' },
  { value: '铺垫', en: 'Setup' },
  { value: '发展', en: 'Development' },
  { value: '冲突', en: 'Conflict' },
  { value: '高潮', en: 'Climax' },
  { value: '转折', en: 'Turning point' },
  { value: '收尾', en: 'Resolution' },
]

interface Props {
  isOpen: boolean
  onClose: () => void
  /** 从章节蓝图「写作此章」传入的预填参数，优先级高于历史记录 */
  prefill?: Record<string, unknown> | null
}

/** 章节创作参数持久化路径（相对于项目路径） */
const CREATION_LOG_REL = '.vela/chapter_creation_log.json'

/** 章节创作对话框 — 配置并启动章节创作工作流（步进式，每步等待用户确认） */
export default function ChapterCreationDialog({ isOpen, onClose, prefill }: Props) {
  const text = useLocaleStore(s => s.text)
  const currentProject = useProjectStore(s => s.currentProject)
  const defaultModelId = useLLMStore(s => s.defaultModelId)
  // ✅ action 用 getState() 获取，不订阅 workflow store 高频更新
  const startWorkflow = useWorkflowStore.getState().startWorkflow
  const addLog = useWorkflowStore.getState().addLog
  const [chapterNumber, setChapterNumber] = useState<number | ''>(1)
  const [title, setTitle] = useState('')
  const [role, setRole] = useState('发展')
  const [purpose, setPurpose] = useState('')
  const [keyEvents, setKeyEvents] = useState('')
  const [characters, setCharacters] = useState('')
  const [userGuidance, setUserGuidance] = useState('')
  const [knowledgeHint, setKnowledgeHint] = useState('')
  const [wordsTarget, setWordsTarget] = useState<number | ''>(3000)
  const [loadedFromHistory, setLoadedFromHistory] = useState(false)
  const [loadedFromBlueprint, setLoadedFromBlueprint] = useState(false)
  const [guardError, setGuardError] = useState<string | null>(null)
  const isChapterRunning = useWorkflowStore(s => s.isTypeRunning('chapter_creation'))


  // 如果是在这弹窗里发起的任务，一旦跑完，isChapterRunning 会变成 false，此时自动关闭弹窗
  useEffect(() => {
    let prevRunning = useWorkflowStore.getState().isTypeRunning('chapter_creation')
    const unsub = useWorkflowStore.subscribe((state) => {
      const running = state.isTypeRunning('chapter_creation')
      if (prevRunning && !running && isOpen) {
        onClose()
      }
      prevRunning = running
    })
    return unsub
  }, [isOpen, onClose])

  /** 从项目本地 .vela/chapter_creation_log.json 读取上次参数 */
  const loadLastParams = useCallback(async () => {
    if (!currentProject) return
    try {
      const result = await ipc.invoke('fs:read-json', `${currentProject.path}/${CREATION_LOG_REL}`)
      if (result.success && result.data) {
        const log = result.data as {
          lastUsed?: {
            chapterNumber: number; title?: string; role: string
            purpose?: string; keyEvents?: string; characters?: string
            userGuidance?: string; wordsTarget?: number
          }
        }
        if (log.lastUsed) {
          const last = log.lastUsed
          // 章节号自动 +1
          setChapterNumber((last.chapterNumber || 0) + 1)
          setTitle('') // 标题不继承，让用户自填
          setRole(last.role || '发展')
          setPurpose(last.purpose || '')
          setKeyEvents(last.keyEvents || '')
          setCharacters(last.characters || '')
          setUserGuidance(last.userGuidance || '')
          setWordsTarget(last.wordsTarget || currentProject.novelConfig.wordsPerChapter || 3000)
          setLoadedFromHistory(true)
          return
        }
      }
    } catch { /* 文件不存在，使用默认值 */ }
    // 默认值：根据已有稿件数量推断下一章节号
    setWordsTarget(currentProject.novelConfig.wordsPerChapter || 3000)
    setChapterNumber(1)
    setLoadedFromHistory(false)
  }, [currentProject])

  // 每次打开时：prefill 优先，其次尝试从历史恢复
  useEffect(() => {
    if (!isOpen || !currentProject) return
    let mounted = true
    Promise.resolve().then(() => {
      if (!mounted) return
      if (prefill) {
        // 使用章节蓝图预填数据
        setChapterNumber(Number(prefill.chapterNumber) || 1)
        setTitle(String(prefill.title || ''))
        setRole(String(prefill.role || '发展'))
        setPurpose(String(prefill.purpose || ''))
        setKeyEvents(String(prefill.keyEvents || ''))
        setCharacters(String(prefill.characters || ''))
        setUserGuidance(String(prefill.userGuidance || ''))
        setWordsTarget(currentProject.novelConfig.wordsPerChapter || 3000)
        setLoadedFromBlueprint(true)
        setLoadedFromHistory(false)
      } else {
        setLoadedFromBlueprint(false)
        loadLastParams()
      }
    })
    return () => { mounted = false }
  }, [isOpen, currentProject, prefill, loadLastParams])



  /** 保存当前参数到持久化文件 */
  const saveParams = async () => {
    if (!currentProject) return
    try {
      // 读取已有 log
      let log: { lastUsed?: object; history?: object[] } = {}
      const existing = await ipc.invoke('fs:read-json', `${currentProject.path}/${CREATION_LOG_REL}`)
      if (existing.success && existing.data) {
        log = existing.data as typeof log
      }

      const params = { chapterNumber, title, role, purpose, keyEvents, characters, userGuidance, wordsTarget }
      log.lastUsed = params
      log.history = [
        { ...params, createdAt: new Date().toISOString() },
        ...((log.history || []) as object[]).slice(0, 49), // 最多保留 50 条历史
      ]

      await ipc.invoke('fs:write-json', `${currentProject.path}/${CREATION_LOG_REL}`, log)
    } catch (e) {
      console.warn('[ChapterCreation] 参数持久化失败:', e)
    }
  }

  const handleStart = async () => {
    if (!defaultModelId) {
      addLog('error', text('请先配置 AI 模型', 'Configure an AI model first.'))
      return
    }
    if (!currentProject) return

    // 防重复：同类型工作流正在运行
    if (isChapterRunning) {
      toast.warning(text('已有章节创作任务正在执行，请等待完成后再试', 'A chapter writing task is already running. Please wait for it to finish.'))
      return
    }

    // 前置校验：章节蓝图是否已生成，以及（若篇章>1）前一章是否已定稿
    const targetChapter = Number(chapterNumber) || 1
    const guard = await guardChapterWriting(targetChapter)
    if (!guard.ok) {
      setGuardError(guard.message || text('前置条件未满足', 'Prerequisites are not met.'))
      return
    }
    setGuardError(null)

    // 持久化本次参数
    await saveParams()

    const workflow = createChapterWorkflow({
      chapterNumber: Number(chapterNumber) || 1,
      title: title || `第${chapterNumber || 1}章`,
      role,
      purpose,
      characters: characters.split(/[、,，]/).map(s => s.trim()).filter(Boolean),
      keyEvents,
      userGuidance,
      knowledgeQueryHint: knowledgeHint.trim() || undefined,
    })

    // 启动任务后关闭设定弹窗，由全局 Overlay 接管展示
    startWorkflow(workflow, false)
    onClose()
  }

  const handleOpenChange = (open: boolean) => {
    // 如果正在生成中，禁止通过点击外部或 ESC 关闭
    if (!open && !isChapterRunning) onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-[540px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles size={16} className="text-[var(--color-accent)]" />
            {text('创作新章节', 'Write a new chapter')}
          </DialogTitle>
          <DialogDescription>
            {text('配置章节参数后启动 AI 创作流水线', 'Configure the chapter, then start the AI writing pipeline.')}
            {loadedFromBlueprint && (
              <span className="ml-2 text-[0.7rem] px-1.5 py-0.5 rounded-full bg-green-500/15 text-green-600 dark:text-green-400">
                {text('已从章节蓝图预填', 'Filled from chapter blueprint')}
              </span>
            )}
            {loadedFromHistory && !loadedFromBlueprint && (
              <span className="ml-2 text-[0.7rem] px-1.5 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(var(--color-accent-rgb), 0.15)', color: 'var(--color-accent)' }}>
                {text('已自动填入上次参数', 'Last-used settings restored')}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        {/* 表单 */}
        <div className="px-5 py-4 space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label>{text('章节号', 'Chapter number')}</Label>
                  <Input
                    type="number"
                    value={chapterNumber}
                    onChange={(e) => setChapterNumber(e.target.value === '' ? '' : parseInt(e.target.value))}
                    onBlur={() => {
                      const v = Number(chapterNumber)
                      if (!v || v < 1) setChapterNumber(1)
                    }}
                    placeholder="1"
                    min={1}
                  />
                </div>
                <div>
                  <Label>{text('章节标题', 'Chapter title')}</Label>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={text('留空自动生成', 'Leave blank to generate')} />
                </div>
                <div>
                  <Label>{text('目标字数', 'Target words')}</Label>
                  <Input
                    type="number"
                    value={wordsTarget}
                    onChange={(e) => setWordsTarget(e.target.value === '' ? '' : parseInt(e.target.value))}
                    onBlur={() => {
                      const v = Number(wordsTarget)
                      if (!v || v < 100) setWordsTarget(3000)
                    }}
                    placeholder="3000"
                    min={100}
                    step={500}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>{text('章节定位', 'Chapter role')}</Label>
                  <NativeSelect value={role} onChange={(e) => setRole(e.target.value)}>
                    {CHAPTER_ROLES.map(({ value, en }) => (
                      <option key={value} value={value}>{text(value, en)}</option>
                    ))}
                  </NativeSelect>
                </div>
                <div>
                  <Label>{text('出场角色', 'Characters')}</Label>
                  <Input value={characters} onChange={(e) => setCharacters(e.target.value)} placeholder={text('用逗号或顿号分隔', 'Separate names with commas')} />
                </div>
              </div>

              <div>
                <Label>{text('章节目的', 'Chapter purpose')}</Label>
                <Textarea
                  value={purpose}
                  onChange={(e) => setPurpose(e.target.value)}
                  placeholder={text('这一章要推进什么（剧情/角色/伏笔）...', 'What should this chapter advance: plot, character, or foreshadowing?')}
                  rows={2}
                />
              </div>

              <div>
                <Label>{text('关键事件', 'Key events')}</Label>
                <Textarea
                  value={keyEvents}
                  onChange={(e) => setKeyEvents(e.target.value)}
                  placeholder={text('本章需要发生的关键事件...', 'Events that must happen in this chapter...')}
                  rows={2}
                />
              </div>

              <div>
                <Label>{text('作者微操指导', 'Author guidance')} <span className="text-[0.7rem] opacity-50">{text('（可选，写稿时最高优先级）', '(optional, highest writing priority)')}</span></Label>
                <Textarea
                  value={userGuidance}
                  onChange={(e) => setUserGuidance(e.target.value)}
                  placeholder={text('特殊要求：开头氛围、结尾方式、某个细节处理方式...', 'Special requirements for the opening, ending, or a specific detail...')}
                  rows={2}
                />
              </div>

              <div>
                <Label>{text('知识库检索关键词', 'Knowledge search terms')} <span className="text-[0.7rem] opacity-50">{text('（可选，追加到向量搜索 query）', '(optional, appended to the vector search query)')}</span></Label>
                <Input
                  value={knowledgeHint}
                  onChange={(e) => setKnowledgeHint(e.target.value)}
                  placeholder={text('如：「剑法传承」「草原地貌」（帮助 AI 检索相关设定）', 'e.g. “sword inheritance”, “grassland terrain”')}
                />
              </div>
            </div>

            <DialogFooter className="sm:justify-between items-center">
              <span className="text-xs mt-2 sm:mt-0" style={{ color: 'var(--color-text-muted)' }}>
                {text('流程：一键写稿（修稿/审稿后续在工具栏处理）', 'Flow: write the draft now; revise and review from the editor toolbar.')}
              </span>
              <div className="flex items-center gap-2">
                <Button variant="outline" onClick={onClose}>{text('取消', 'Cancel')}</Button>
                <Button variant="ai" size="lg" onClick={handleStart} disabled={isChapterRunning}>
                  {isChapterRunning ? (
                    <span className="flex items-center gap-2">
                      <Loader2 size={13} className="animate-spin" />
                      {text('章节创作中...', 'Writing chapter...')}
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <Play size={13} />
                      {text('开始创作', 'Start writing')}
                    </span>
                  )}
                </Button>
              </div>
            </DialogFooter>
            {/* 前置校验失败提示（呈现在 Footer 下方） */}
            {guardError && (
              <div className="mx-5 mb-4 flex items-start gap-2 px-3 py-2.5 rounded-lg text-xs bg-yellow-500/10 border border-yellow-500/30 text-yellow-600 dark:text-yellow-400">
                <AlertCircle size={13} className="flex-shrink-0 mt-0.5 text-yellow-500" />
                <span className="whitespace-pre-line">{guardError}</span>
              </div>
            )}
      </DialogContent>
    </Dialog>
  )
}
