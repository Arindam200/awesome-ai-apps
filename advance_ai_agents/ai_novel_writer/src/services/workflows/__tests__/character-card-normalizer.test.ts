import { describe, expect, it } from 'vitest'

import {
  normalizeCharacterCardsForPersistence,
  parseCharacterCardsFromModelOrSource,
} from '../character-card-normalizer'

describe('character card normalizer', () => {
  it('preserves extracted cards that use Chinese field names', () => {
    const cards = normalizeCharacterCardsForPersistence([
      {
        姓名: '林晓薇',
        定位: '主角',
        性别: '女',
        年龄: '27',
        外貌特征: '穿灰色职业套装，神情克制。',
        性格特点: '谨慎、压抑、观察力强',
        背景故事: '航司管理层候选人。',
        能力: '数据分析与谈判',
        核心动机: '保住职业上升通道',
        关系网: [{ name: 'Ethan', relation: '上级/压迫者' }],
        成长轨迹: '从被动忍耐到主动反制',
      },
      {
        name: 'Ethan',
        role: 'antagonist',
        relationships: '林晓薇：下属/被操控对象',
      },
    ])

    expect(cards).toHaveLength(2)
    expect(cards[0]).toMatchObject({
      name: '林晓薇',
      role: 'protagonist',
      gender: '女',
      age: '27',
      appearance: '穿灰色职业套装，神情克制。',
      motivation: '保住职业上升通道',
      arc: '从被动忍耐到主动反制',
    })
    expect(JSON.parse(cards[0].relationships)).toEqual([
      { target: 'Ethan', relation: '上级/压迫者' },
    ])
  })

  it('converts relationship text into graph-readable edges when target names are known', () => {
    const cards = normalizeCharacterCardsForPersistence([
      {
        name: '林晓薇',
        role: 'protagonist',
        relationships: '她与Ethan是表面合作实则被压制；和周砚互相试探但共享线索。',
      },
      { name: 'Ethan', role: 'antagonist', relationships: '' },
      { name: '周砚', role: 'supporting', relationships: '' },
    ])

    expect(JSON.parse(cards[0].relationships)).toEqual([
      { target: 'Ethan', relation: '她与Ethan是表面合作实则被压制' },
      { target: '周砚', relation: '和周砚互相试探但共享线索。' },
    ])
  })

  it('filters nameless cards and stringifies persistence fields', () => {
    const cards = normalizeCharacterCardsForPersistence([
      { role: '主角', relationships: [{ target: '无人', relation: '无名卡' }] },
      { name: '周砚', role: '重要配角', abilities: ['调查', '推理'], relationships: [] },
    ])

    expect(cards).toHaveLength(1)
    expect(cards[0].name).toBe('周砚')
    expect(cards[0].role).toBe('supporting')
    expect(cards[0].abilities).toBe('调查；推理')
    expect(cards[0].relationships).toBe('')
  })

  it('falls back to source character objects when the local model returns prose instead of JSON', () => {
    const source = JSON.stringify({
      燕云: { 关系: ['父亲燕九鼎', '爷爷燕怀山'], 动力: '证明自己' },
      陈杰波: { 关系: ['刘丽'], 动力: '维持灰色利益链' },
    })

    const cards = parseCharacterCardsFromModelOrSource(
      '张力\n</think>\n\n段落一：燕云是核心角色，陈杰波是对手角色。',
      source,
    )

    expect(cards.map((card) => card.name)).toEqual(['燕云', '陈杰波'])
    expect(cards[0].motivation).toBe('证明自己')
    expect(cards[0].relationships).toContain('燕九鼎')
  })

  it('extracts fenced or prefixed JSON from local model output before normalizing', () => {
    const cards = parseCharacterCardsFromModelOrSource(
      [
        '以下是结构化结果：',
        '```json',
        '{"characters":[{"姓名":"林晓薇","定位":"主角","关系网":[{"target":"周砚","relation":"盟友"}]},{"姓名":"周砚","定位":"重要配角"}]}',
        '```',
      ].join('\n'),
      '',
    )

    expect(cards).toHaveLength(2)
    expect(cards[0].name).toBe('林晓薇')
    expect(JSON.parse(cards[0].relationships)).toEqual([{ target: '周砚', relation: '盟友' }])
  })
})
