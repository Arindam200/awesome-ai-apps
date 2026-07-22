import type { CharacterData, CharacterStateData } from '../../../electron/repositories/character-repository'

type RawCard = Record<string, unknown>
type RelationshipEdge = { target: string; relation: string }

const ROLE_MAP: Record<string, string> = {
  protagonist: 'protagonist',
  main: 'protagonist',
  主角: 'protagonist',
  男主: 'protagonist',
  女主: 'protagonist',
  核心主角: 'protagonist',
  antagonist: 'antagonist',
  villain: 'antagonist',
  反派: 'antagonist',
  对手: 'antagonist',
  敌人: 'antagonist',
  supporting: 'supporting',
  support: 'supporting',
  配角: 'supporting',
  重要配角: 'supporting',
  核心配角: 'supporting',
  minor: 'minor',
  龙套: 'minor',
  次要角色: 'minor',
}

const CHARACTER_ARRAY_KEYS = [
  'characters',
  'characterCards',
  'character_cards',
  'cards',
  '角色',
  '角色卡',
  '角色列表',
  '人物',
  '人物列表',
]

const NON_CHARACTER_OBJECT_KEYS = new Set([
  'characters',
  'characterCards',
  'character_cards',
  'cards',
  '角色',
  '角色卡',
  '角色列表',
  '人物',
  '人物列表',
  'relationships',
  'relations',
  '关系',
  '关系网',
  'meta',
  'metadata',
  '说明',
])

function readField(card: RawCard, keys: string[]): unknown {
  for (const key of keys) {
    if (card[key] !== undefined && card[key] !== null) return card[key]
  }
  return undefined
}

function stringifyValue(value: unknown): string {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') return String(value)
  if (Array.isArray(value)) {
    return value
      .map((item) => stringifyValue(item))
      .filter(Boolean)
      .join('；')
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, entryValue]) => `${key}: ${stringifyValue(entryValue)}`)
      .filter((line) => !line.endsWith(': '))
      .join('；')
  }
  return ''
}

function cleanModelText(text: string): string {
  return text
    .replace(/<think>[\s\S]*?<\/think>/gi, '\n')
    .replace(/^[\s\S]*?<\/think>/i, '\n')
    .replace(/<\/?think>/gi, '\n')
    .replace(/```(?:json)?/gi, '')
    .replace(/```/g, '')
    .trim()
}

function parseJson(text: string): unknown | null {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function matchingClose(open: string): string {
  return open === '{' ? '}' : ']'
}

function extractBalancedJsonCandidates(text: string): string[] {
  const candidates: string[] = []

  for (let start = 0; start < text.length; start++) {
    const first = text[start]
    if (first !== '{' && first !== '[') continue

    const stack: string[] = []
    let inString = false
    let escaped = false

    for (let i = start; i < text.length; i++) {
      const char = text[i]

      if (inString) {
        if (escaped) {
          escaped = false
        } else if (char === '\\') {
          escaped = true
        } else if (char === '"') {
          inString = false
        }
        continue
      }

      if (char === '"') {
        inString = true
        continue
      }

      if (char === '{' || char === '[') {
        stack.push(matchingClose(char))
        continue
      }

      if ((char === '}' || char === ']') && stack.length > 0) {
        const expected = stack.pop()
        if (char !== expected) break
        if (stack.length === 0) {
          candidates.push(text.slice(start, i + 1))
          break
        }
      }
    }
  }

  return candidates
}

function parseLooseJson(text: string): unknown | null {
  const cleaned = cleanModelText(text)
  if (!cleaned) return null

  const direct = parseJson(cleaned)
  if (direct !== null) return direct

  for (const candidate of extractBalancedJsonCandidates(cleaned)) {
    const parsed = parseJson(candidate)
    if (parsed !== null) return parsed
  }

  return null
}

function isRawCard(value: unknown): value is RawCard {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function objectEntriesToCards(value: RawCard): RawCard[] {
  const cards: RawCard[] = []

  for (const [name, entry] of Object.entries(value)) {
    if (NON_CHARACTER_OBJECT_KEYS.has(name)) continue
    if (!isRawCard(entry)) continue
    cards.push({ name, ...entry })
  }

  return cards
}

function rawCardsFromParsedJson(parsed: unknown): RawCard[] {
  if (Array.isArray(parsed)) {
    return parsed.filter(isRawCard)
  }

  if (!isRawCard(parsed)) return []

  for (const key of CHARACTER_ARRAY_KEYS) {
    const value = parsed[key]
    if (Array.isArray(value)) return value.filter(isRawCard)
  }

  if (stringifyValue(readField(parsed, ['name', '姓名', '角色名', '名字']))) {
    return [parsed]
  }

  return objectEntriesToCards(parsed)
}

function normalizeRole(value: unknown): string {
  const roleText = stringifyValue(value)
  if (!roleText) return 'supporting'
  return ROLE_MAP[roleText] ?? ROLE_MAP[roleText.toLowerCase()] ?? 'supporting'
}

function toNumber(value: unknown, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function normalizeCurrentState(value: unknown): CharacterStateData | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const state = value as RawCard
  return {
    location: stringifyValue(readField(state, ['location', '当前位置', '初始位置', '位置'])),
    powerLevel: stringifyValue(readField(state, ['powerLevel', 'power_level', '能力等级', '境界', '初始境界'])),
    physicalState: stringifyValue(readField(state, ['physicalState', 'physical_state', '身体状态', '初始身体状态'])),
    mentalState: stringifyValue(readField(state, ['mentalState', 'mental_state', '心理状态', '初始心理状态'])),
    keyItems: stringifyValue(readField(state, ['keyItems', 'key_items', '关键道具', '持有道具', '初始持有道具'])),
    recentEvents: stringifyValue(readField(state, ['recentEvents', 'recent_events', '最近事件', '背景事件', '故事开始前的背景事件'])),
    updatedAtChapter: toNumber(readField(state, ['updatedAtChapter', 'updated_at_chapter', '更新章节', '最后更新章节']), 0),
  }
}

function normalizeRelationshipObject(value: RawCard, names: Set<string>): RelationshipEdge | null {
  const target = stringifyValue(readField(value, ['target', 'name', 'to', 'character', '角色', '对象', '目标']))
  if (!target || !names.has(target)) return null
  const relation = stringifyValue(readField(value, ['relation', 'label', 'type', '关系', '关系类型', '描述'])) || '相关'
  return { target, relation }
}

function parseRelationshipJsonText(text: string, names: Set<string>): RelationshipEdge[] | null {
  try {
    const parsed = JSON.parse(text)
    return normalizeRelationshipEdges(parsed, names)
  } catch {
    return null
  }
}

function normalizeRelationshipEdges(value: unknown, names: Set<string>, selfName?: string): RelationshipEdge[] {
  const edges: RelationshipEdge[] = []
  const seen = new Set<string>()

  const addEdge = (edge: RelationshipEdge | null) => {
    if (!edge || edge.target === selfName) return
    const key = `${edge.target}\u0000${edge.relation}`
    if (seen.has(key)) return
    seen.add(key)
    edges.push(edge)
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      if (typeof item === 'string') {
        for (const edge of normalizeRelationshipText(item, names, selfName)) addEdge(edge)
      } else if (item && typeof item === 'object') {
        addEdge(normalizeRelationshipObject(item as RawCard, names))
      }
    }
    return edges
  }

  if (value && typeof value === 'object') {
    for (const [target, relation] of Object.entries(value as RawCard)) {
      if (names.has(target)) addEdge({ target, relation: stringifyValue(relation) || '相关' })
    }
    return edges
  }

  if (typeof value === 'string') {
    const fromJson = parseRelationshipJsonText(value, names)
    if (fromJson) return fromJson
    return normalizeRelationshipText(value, names, selfName)
  }

  return edges
}

function normalizeRelationshipText(text: string, names: Set<string>, selfName?: string): RelationshipEdge[] {
  const edges: RelationshipEdge[] = []
  const seen = new Set<string>()
  const lines = text.split(/[,;，；\n]/).map((line) => line.trim()).filter(Boolean)

  for (const line of lines) {
    const explicit = line.match(/^(.+?)[：:—-]\s*(.+)$/)
    if (explicit) {
      const target = explicit[1].trim()
      const relation = explicit[2].trim()
      if (target !== selfName && names.has(target)) {
        const key = `${target}\u0000${relation}`
        if (!seen.has(key)) {
          seen.add(key)
          edges.push({ target, relation })
        }
      }
      continue
    }

    for (const target of names) {
      if (target === selfName || !line.includes(target)) continue
      const key = `${target}\u0000${line}`
      if (!seen.has(key)) {
        seen.add(key)
        edges.push({ target, relation: line })
      }
    }
  }

  return edges
}

function normalizeRelationships(value: unknown, names: Set<string>, selfName: string): string {
  const edges = normalizeRelationshipEdges(value, names, selfName)
  if (edges.length > 0) return JSON.stringify(edges)
  return stringifyValue(value)
}

export function normalizeCharacterCardsForPersistence(rawCards: RawCard[]): CharacterData[] {
  const rawWithNames = rawCards
    .map((card) => ({
      card,
      name: stringifyValue(readField(card, ['name', '姓名', '角色名', '名字'])),
    }))
    .filter((item) => item.name)

  const names = new Set(rawWithNames.map((item) => item.name))

  return rawWithNames.map(({ card, name }) => ({
    name,
    role: normalizeRole(readField(card, ['role', '定位', '角色定位', '类型'])),
    gender: stringifyValue(readField(card, ['gender', '性别'])),
    age: stringifyValue(readField(card, ['age', '年龄', '年龄段'])),
    appearance: stringifyValue(readField(card, ['appearance', '外貌', '外貌特征', '外貌描写'])),
    personality: stringifyValue(readField(card, ['personality', '性格', '性格特点', '性格特征'])),
    background: stringifyValue(readField(card, ['background', '背景', '背景故事', '身世'])),
    abilities: stringifyValue(readField(card, ['abilities', 'ability', '能力', '技能', '能力/技能', '能力技能'])),
    motivation: stringifyValue(readField(card, ['motivation', '动机', '动力', '核心动机', '核心动机与渴望'])),
    relationships: normalizeRelationships(readField(card, ['relationships', 'relations', '关系网', '角色关系', '关系']), names, name),
    arc: stringifyValue(readField(card, ['arc', '角色弧光', '成长轨迹', '成长线'])),
    notes: stringifyValue(readField(card, ['notes', '备注', '其他补充说明', '补充'])),
    currentState: normalizeCurrentState(readField(card, ['currentState', 'current_state', '当前状态', '状态'])),
  }))
}

export function parseCharacterCardsFromModelOrSource(modelText: string, sourceText: string): CharacterData[] {
  const parsedModel = parseLooseJson(modelText)
  if (parsedModel !== null) {
    const modelCards = normalizeCharacterCardsForPersistence(rawCardsFromParsedJson(parsedModel))
    if (modelCards.length > 0) return modelCards
  }

  const parsedSource = parseLooseJson(sourceText)
  if (parsedSource !== null) {
    return normalizeCharacterCardsForPersistence(rawCardsFromParsedJson(parsedSource))
  }

  return []
}
