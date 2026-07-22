/**
 * CharactersView — 角色管理列表视图
 */

import { Users, RefreshCw, Plus } from 'lucide-react'
import { useProjectStore } from '../../../stores/project-store'
import { useCharacterStore, ROLE_LABELS } from '../../../stores/character-store'
import { Button } from '../../ui/Button'
import { EmptyState } from '../../ui/EmptyState'
import { cn } from '../../../lib/utils'
import { useLocaleStore } from '../../../stores/locale-store'

export default function CharactersView() {
  const currentProject = useProjectStore(s => s.currentProject)
  const characters = useCharacterStore(s => s.characters)
  const selectedName = useCharacterStore(s => s.selectedName)
  const load = useCharacterStore(s => s.load)
  const setSelectedName = useCharacterStore(s => s.setSelectedName)
  const addCharacter = useCharacterStore(s => s.addCharacter)
  const text = useLocaleStore(s => s.text)

  // 角色数据由 ProjectService 统一加载，组件只消费 store 数据

  if (!currentProject) {
    return (
      <EmptyState
        icon={<Users size={36} />}
        message={text('请先打开项目', 'Open a project first')}
        className="pb-[15vh]"
        opacity={0.4}
      />
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between px-3 h-9 flex-shrink-0 border-b border-[var(--color-border)]">
        <span className="text-xs font-medium text-[var(--color-text)] flex items-center gap-1">
          <Users size={13} />
          {text(`角色列表（${characters.length}）`, `Characters (${characters.length})`)}
        </span>
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => load()} title={text('刷新列表', 'Refresh list')}>
            <RefreshCw size={14} strokeWidth={2} />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={addCharacter} title={text('新建角色', 'New character')}>
            <Plus size={14} strokeWidth={2} />
          </Button>
        </div>
      </div>
      {/* 角色列表 */}
      <div className="flex-1 overflow-y-auto p-1">
        {characters.map((c) => (
          <div
            key={c.name}
            className={cn(
              'px-2.5 py-1.5 rounded-md text-xs cursor-pointer mb-0.5',
              selectedName === c.name
                ? 'bg-[var(--color-active)] text-[var(--color-text)]'
                : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)]'
            )}
            onClick={() => setSelectedName(c.name)}
          >
            <div className="font-medium">{c.name || text('未命名', 'Untitled')}</div>
            <div className="text-[0.7rem] mt-0.5 opacity-60">{ROLE_LABELS[c.role]}</div>
            {c.currentState && (
              <div className="text-[0.65rem] mt-0.5 opacity-50">
                {text(`第${c.currentState.updatedAtChapter}章更新`, `Updated in chapter ${c.currentState.updatedAtChapter}`)}
              </div>
            )}
          </div>
        ))}
        {characters.length === 0 && (
          <div className="text-center py-6 opacity-30 text-xs">{text('暂无角色', 'No characters')}</div>
        )}
      </div>
    </div>
  )
}
