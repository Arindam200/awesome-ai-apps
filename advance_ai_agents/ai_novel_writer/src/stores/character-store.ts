import { create } from 'zustand'
import { ipc } from '../services/ipc-client'
import type { CharacterData, CharacterStateData } from '../../electron/repositories/character-repository'

export type CharacterCurrentState = CharacterStateData
export type CharacterCard = CharacterData

export const EMPTY_CARD: CharacterCard = {
  name: '', role: 'supporting', gender: '', age: '',
  appearance: '', personality: '', background: '', abilities: '',
  motivation: '', relationships: '', arc: '', notes: '',
}

export const EMPTY_STATE: CharacterCurrentState = {
  location: '', powerLevel: '', physicalState: '', mentalState: '',
  keyItems: '', recentEvents: '', updatedAtChapter: 0,
}

export const ROLE_LABELS: Record<CharacterCard['role'], string> = {
  protagonist: '🌟 主角',
  antagonist: '🔥 反派',
  supporting: '👥 配角',
  minor: '📌 龙套',
}

interface CharacterState {
  characters: CharacterCard[]
  selectedName: string | null
  saving: boolean
  loaded: boolean

  load: () => Promise<void>
  reset: () => void
  setSelectedName: (name: string | null) => void
  addCharacter: () => void
  deleteCharacter: (name: string, projectPath?: string) => Promise<void>
  updateField: <K extends keyof CharacterCard>(name: string, key: K, value: CharacterCard[K]) => void
  saveAll: (projectPath?: string) => Promise<void>

  // 兼容旧接口
  loadCharacters: (projectPath: string) => Promise<void>
}

export const useCharacterStore = create<CharacterState>()((set, get) => ({
  characters: [],
  selectedName: null,
  saving: false,
  loaded: false,

  load: async () => {
    try {
      const cards = await ipc.invoke('db:character-get-all')

      const { selectedName } = get()
      set({
        characters: cards,
        loaded: true,
        selectedName: cards.find(c => c.name === selectedName)
          ? selectedName
          : (cards.length > 0 ? cards[0].name : null),
      })
    } catch {
      set({ characters: [], selectedName: null, loaded: true })
    }
  },

  loadCharacters: async () => {
    await get().load()
  },

  reset: () => {
    set({ characters: [], selectedName: null, saving: false, loaded: false })
  },

  setSelectedName: (name) => set({ selectedName: name }),

  addCharacter: () => {
    const newCard: CharacterCard = {
      ...EMPTY_CARD,
      name: `新角色_${Math.random().toString(36).slice(2, 6)}`,
    }
    set((s) => ({
      characters: [...s.characters, newCard],
      selectedName: newCard.name,
    }))
  },

  deleteCharacter: async (name) => {
    const { characters } = get()
    const card = characters.find(c => c.name === name)
    if (!card) return

    // SQLite 删除
    try { await ipc.invoke('db:character-delete', name) } catch { /* 忽略 */ }

    const remaining = characters.filter(c => c.name !== name)
    set({
      characters: remaining,
      selectedName: remaining.length > 0 ? remaining[0].name : null,
    })
  },

  updateField: (name, key, value) => {
    set((s) => {
      const newChars = s.characters.map(c =>
        c.name === name ? { ...c, [key]: value } : c
      )

      let newSelected = s.selectedName
      if (key === 'name' && s.selectedName === name) {
        newSelected = value as string
      }

      return { characters: newChars, selectedName: newSelected }
    })
  },

  saveAll: async () => {
    set({ saving: true })
    const { characters } = get()

    try {
      // 提交到 DB 批量保存
      await ipc.invoke('db:character-save-all', characters)

      // 注意：从 UI 上因为我们只持有内存中的列表，所以没问题，
      // 如果有改名的情况，我们在 UI 保存时，实际上会作为新记录插入……
      // (TODO: 真正的改名处理需要比较 name 的变化，目前旧逻辑也是直接覆盖文件而已)
    } finally {
      set({ saving: false })
    }
  },
}))
