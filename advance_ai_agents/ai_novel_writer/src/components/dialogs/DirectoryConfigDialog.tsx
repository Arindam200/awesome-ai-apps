import { useState } from 'react'
import { FileText } from 'lucide-react'
import { useProjectStore } from '../../stores/project-store'
import { useWorkflowStore } from '../../stores/workflow-store'
import { toast } from '../ui/Toast'
import { useLocaleStore } from '../../stores/locale-store'
import {
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Label } from '../ui/Label'
import { Textarea } from '../ui/Textarea'
import type { DirectoryWorkflowParams } from '../../services/workflows/directory-workflow'

interface Props {
  isOpen: boolean
  onClose: () => void
  /** 已有蓝图章节数（影响「追加」模式的默认值） */
  existingCount: number
  onConfirm: (params: DirectoryWorkflowParams) => void
}

/** 蓝图生成配置弹框 — 选择生成范围和模式 */
export default function DirectoryConfigDialog({ isOpen, onClose, existingCount, onConfirm }: Props) {
  const text = useLocaleStore(s => s.text)
  const currentProject = useProjectStore(s => s.currentProject)

  // 范围选择
  const [rangeMode, setRangeMode] = useState<'front' | 'range' | 'full'>('front')
  // 覆盖/追加模式选择 (仅当 existingCount > 0 时有效)
  const [overwriteMode, setOverwriteMode] = useState<'append' | 'full'>('append')

  const [frontN, setFrontN] = useState<number | ''>(50)
  const [rangeStart, setRangeStart] = useState<number | ''>(existingCount + 1)
  const [rangeEnd, setRangeEnd] = useState<number | ''>(existingCount + 50)
  // 节奏指导
  const [pacingGuidance, setPacingGuidance] = useState('')

  const isBatchRunning = useWorkflowStore(s => s.isTypeRunning('batch_generate'))

  if (!currentProject) return null
  const total = currentProject.novelConfig.totalChapters

  const handleConfirm = () => {
    // 防重复：同类型工作流正在运行
    if (isBatchRunning) {
      toast.warning(text('已有蓝图生成任务正在执行，请等待完成后再试', 'A blueprint generation task is already running. Please wait for it to finish.'))
      return
    }

    let params: DirectoryWorkflowParams

    if (rangeMode === 'full') {
      params = { mode: overwriteMode === 'full' ? 'full' : 'append', count: 0 }
    } else if (rangeMode === 'front') {
      if (existingCount > 0 && overwriteMode === 'append') {
        params = { mode: 'append', startChapter: existingCount + 1, count: Number(frontN) || 50 }
      } else {
        params = { mode: 'full', count: Number(frontN) || 50 }
      }
    } else {
      const start = Number(rangeStart) || 1
      const end = Math.max(start, Number(rangeEnd) || start)
      params = { mode: 'append', startChapter: start, count: Math.max(1, end - start + 1) }
    }

    onConfirm({ ...params, pacingGuidance: pacingGuidance.trim() || undefined })
    onClose()
    toast.info(text('已提交：正在生成章节蓝图...', 'Submitted: generating chapter blueprints...'))
  }

  return (
    <Dialog open={isOpen} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText size={16} className="text-[var(--color-accent)]" />
            {text('生成章节蓝图', 'Generate chapter blueprints')}
          </DialogTitle>
          <DialogDescription>
            {existingCount > 0
              ? text(`当前已存在 ${existingCount} 章蓝图，选择下一步操作：`, `${existingCount} chapter blueprints already exist. Choose what to do next:`)
              : text(`项目共 ${total} 章，请选择生成范围：`, `The project has ${total} chapters. Choose a generation range:`)}
          </DialogDescription>
        </DialogHeader>

        <div className="px-5 py-4 space-y-4">
          <div>
            <Label className="text-xs font-semibold mb-2 block" style={{ color: 'var(--color-text)' }}>
              {text('生成数量 / 范围', 'Quantity / range')}
            </Label>
            <div className="space-y-3 mt-2">
              <RadioOption
                checked={rangeMode === 'front'}
                onChange={() => setRangeMode('front')}
                label={
                  <span className="flex items-center gap-2">
                    {text('批量连续生成', 'Generate next')}
                    <Input
                      type="number"
                      value={frontN}
                      onChange={e => setFrontN(e.target.value === '' ? '' : parseInt(e.target.value))}
                      onBlur={() => {
                        const v = Number(frontN)
                        if (!v || v < 1) setFrontN(50)
                        else setFrontN(Math.min(total, v))
                      }}
                      className="w-16 h-6 text-xs px-2 py-0"
                      onClick={e => e.stopPropagation()}
                    />
                    {text('章', 'chapters')}
                  </span>
                }
              />
              <RadioOption
                checked={rangeMode === 'range'}
                onChange={() => setRangeMode('range')}
                label={
                  <span className="flex items-center gap-2">
                    {text('指定生成：第', 'Generate range:')}
                    <Input
                      type="number"
                      value={rangeStart}
                      onChange={e => setRangeStart(e.target.value === '' ? '' : parseInt(e.target.value))}
                      onBlur={() => {
                        const v = Number(rangeStart)
                        if (!v || v < 1) setRangeStart(1)
                        else if (v > existingCount + 1) setRangeStart(existingCount + 1)
                      }}
                      className="w-16 h-6 text-xs px-2 py-0"
                      onClick={e => e.stopPropagation()}
                    />
                    {text('到 第', 'to')}
                    <Input
                      type="number"
                      value={rangeEnd}
                      onChange={e => setRangeEnd(e.target.value === '' ? '' : parseInt(e.target.value))}
                      onBlur={() => {
                        const v = Number(rangeEnd)
                        const start = Number(rangeStart) || 1
                        if (!v || v < start) setRangeEnd(start)
                      }}
                      className="w-16 h-6 text-xs px-2 py-0"
                      onClick={e => e.stopPropagation()}
                    />
                    {text('章', 'chapter')}
                  </span>
                }
              />
              <RadioOption
                checked={rangeMode === 'full'}
                onChange={() => setRangeMode('full')}
                label={text(`全量生成（共 ${total} 章）`, `Generate all ${total} chapters`)}
              />
            </div>
          </div>

          {existingCount > 0 && (
            <div
              className="rounded-lg p-3 space-y-2 mt-4"
              style={{ backgroundColor: 'var(--color-panel)', border: '1px solid var(--color-border)' }}
            >
              <p className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                {text('针对已有数据的处理方式：', 'Existing blueprint handling:')}
              </p>
              <div className="space-y-3 mt-2">
                <RadioOption
                  checked={overwriteMode === 'append'}
                  onChange={() => setOverwriteMode('append')}
                  label={text(`追加模式：保留现有蓝图，从第 ${existingCount + 1} 章起往后生成`, `Append: keep existing blueprints and continue from chapter ${existingCount + 1}`)}
                />
                <RadioOption
                  checked={overwriteMode === 'full'}
                  onChange={() => setOverwriteMode('full')}
                  label={text('覆盖模式：无视现有蓝图，从第 1 章起强制覆盖生成', 'Overwrite: regenerate from chapter 1 and replace existing blueprints')}
                />
              </div>
            </div>
          )}

          {/* 节奏/风格指导（可选） */}
          <div>
            <Label className="text-xs font-semibold mb-2 block" style={{ color: 'var(--color-text)' }}>
              {text('节奏/风格指导（可选）', 'Pacing / style guidance (optional)')}
            </Label>
            <Textarea
              value={pacingGuidance}
              onChange={e => setPacingGuidance(e.target.value)}
              placeholder={text('如：“前30章快节奏，每章安排一个爽点。中期适当铺设伏笔和角色成长。”', 'e.g. Keep the first 30 chapters fast-paced, then add foreshadowing and character growth.')}
              rows={2}
              className="text-xs"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{text('取消', 'Cancel')}</Button>
          <Button variant="default" onClick={handleConfirm}>
            <FileText size={13} />
            {text('开始生成', 'Generate')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** 单选按钮选项 */
function RadioOption({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: () => void
  label: React.ReactNode
}) {
  return (
    <label
      className="flex items-center gap-2 text-xs cursor-pointer select-none"
      style={{ color: 'var(--color-text-secondary)' }}
      onClick={onChange}
    >
      <div
        className="w-3.5 h-3.5 rounded-full border flex items-center justify-center flex-shrink-0"
        style={{
          borderColor: checked ? 'var(--color-accent)' : 'var(--color-border)',
          backgroundColor: checked ? 'var(--color-accent)' : 'transparent',
        }}
      >
        {checked && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
      </div>
      {label}
    </label>
  )
}
