/**
 * 写作风格预设包
 *
 * 预定义的写作风格模板，应用后自动填充 NovelConfig 相关字段
 */
import type { NovelConfig } from '../shared/ipc-channels'

/** 风格预设 */
export interface StylePreset {
  id: string
  name: string
  emoji: string
  description: string
  /** 覆盖的字段 */
  overrides: Partial<NovelConfig>
}

/** 内置风格预设 */
export const STYLE_PRESETS: StylePreset[] = [
  {
    id: 'male-hot-blood',
    name: '男频热血',
    emoji: '🔥',
    description: '爽快升级、打脸装逼、逆袭崛起',
    overrides: {
      genre: '玄幻',
      subGenre: '东方玄幻',
      targetAudience: '男性读者',
      wordsPerChapter: 3000,
      globalGuidance: `【写作风格指导】
- 节奏明快，每章至少一个爽点或反转
- 战斗场面要热血震撼，不吝笔墨描写
- 对话干脆利落，主角金句频出
- 每章结尾留悬念/钩子，引导翻页
- 修炼体系层次分明，实力对比清晰
- 装逼打脸情节要合理铺垫，爽感自然
- 适当使用"震惊体"烘托氛围，但不要过度`,
    },
  },
  {
    id: 'female-romance',
    name: '女频言情',
    emoji: '💕',
    description: '甜宠暧昧、双向奔赴、情感细腻',
    overrides: {
      genre: '言情',
      subGenre: '现代言情',
      targetAudience: '女性读者',
      wordsPerChapter: 2500,
      globalGuidance: `【写作风格指导】
- 感情线为主线，事业线为辅
- 男女主互动要有化学反应，暧昧甜蜜
- 心理描写细腻丰富，内心独白有代入感
- 适度制造误会和虐心桥段，但要及时给糖
- 配角立体有趣，不纯粹工具人
- 情感递进自然，每一步心动都有铺垫
- 日常片段温馨有趣，生活气息浓厚`,
    },
  },
  {
    id: 'ancient-xianxia',
    name: '古风仙侠',
    emoji: '⚔️',
    description: '修仙问道、古韵悠长、仙凡羁绊',
    overrides: {
      genre: '仙侠',
      subGenre: '修真文明',
      targetAudience: '通用读者',
      wordsPerChapter: 3000,
      globalGuidance: `【写作风格指导】
- 文风古朴典雅，适当使用文言句式
- 场景描写要有水墨画意境
- 修仙体系严谨，功法/丹药/法器要有逻辑
- 人物对话带有古风韵味但不晦涩
- 道心、因果、轮回等概念贯穿始终
- 战斗场面超凡脱俗，仙术华丽
- 师徒/同门/道侣关系要细腻真实`,
    },
  },
  {
    id: 'modern-urban',
    name: '现代都市',
    emoji: '🏙️',
    description: '商战职场、都市生活、现实质感',
    overrides: {
      genre: '都市',
      subGenre: '都市生活',
      targetAudience: '通用读者',
      wordsPerChapter: 2500,
      globalGuidance: `【写作风格指导】
- 现代都市背景，注重生活质感和细节真实
- 人物性格鲜明，对话富有生活气息
- 职场/商战场景要专业可信
- 情感描写接地气，不悬浮
- 适当融入社会热点和生活痛点
- 节奏张弛有度，不要全程高能
- 配角群像丰满，展现都市众生相`,
    },
  },
  {
    id: 'hard-scifi',
    name: '硬核科幻',
    emoji: '🚀',
    description: '星际探索、科技硬核、未来文明',
    overrides: {
      genre: '科幻',
      subGenre: '星际文明',
      targetAudience: '科幻爱好者',
      wordsPerChapter: 3500,
      globalGuidance: `【写作风格指导】
- 科技设定要有合理基础，不要魔法式科幻
- 太空/星际场景的物理细节要准确
- 人物面对未知时的心理描写要深刻
- 文明冲突和伦理困境是核心驱动
- 保持科幻感的同时注重人文情怀
- 术语使用适度，给非硬核读者留有理解空间
- 宏大叙事与个人命运交织`,
    },
  },
  {
    id: 'suspense-mystery',
    name: '悬疑推理',
    emoji: '🔍',
    description: '层层反转、逻辑缜密、智商在线',
    overrides: {
      genre: '悬疑',
      subGenre: '推理悬疑',
      targetAudience: '通用读者',
      wordsPerChapter: 2500,
      globalGuidance: `【写作风格指导】
- 每章制造至少一个悬念或线索
- 伏笔埋设要隐蔽自然，回收要令人恍然大悟
- 推理过程逻辑严密，不要出现逻辑硬伤
- 氛围描写注重营造紧张感和压迫感
- 真凶/真相不要太早暴露，层层剥茧
- 红鲱鱼（误导线索）适度使用
- 主角智商在线，推理有说服力`,
    },
  },
]

/** 获取所有预设 */
export function getPresets(): StylePreset[] {
  return STYLE_PRESETS
}

/** 应用预设到当前配置（只注入 globalGuidance，不覆盖其他元数据） */
export function applyPreset(presetId: string, config: NovelConfig): NovelConfig {
  const preset = STYLE_PRESETS.find((p) => p.id === presetId)
  if (!preset) return config
  return {
    ...config,
    globalGuidance: preset.overrides.globalGuidance ?? config.globalGuidance,
  }
}

/** 获取预设覆盖的字段名 */
export function getOverrideFields(presetId: string): string[] {
  const preset = STYLE_PRESETS.find((p) => p.id === presetId)
  if (!preset) return []
  return Object.keys(preset.overrides)
}
