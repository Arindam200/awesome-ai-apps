/**
 * 项目模板 — 新建项目时可从预置模板快速创建
 */
import type { NovelConfig } from '../shared/ipc-channels'

/** 项目模板 */
export interface ProjectTemplate {
  id: string
  name: string
  emoji: string
  description: string
  /** 预填充的小说配置 */
  config: Partial<NovelConfig>
}

/** 内置项目模板 */
export const PROJECT_TEMPLATES: ProjectTemplate[] = [
  {
    id: 'blank',
    name: '空白项目',
    emoji: '📄',
    description: '从零开始，自由发挥',
    config: {
      genre: '玄幻',
      subGenre: '',
      targetAudience: '男频',
      totalChapters: 100,
      wordsPerChapter: 3000,
      coreOutline: '',
      worldSetting: '',
      goldenFinger: '',
      protagonistProfile: '',
      globalGuidance: '',
    },
  },
  {
    id: 'xuanhuan',
    name: '玄幻小说',
    emoji: '🐉',
    description: '修炼体系、宗门江湖、逆天改命',
    config: {
      genre: '玄幻',
      subGenre: '东方玄幻',
      targetAudience: '男频',
      totalChapters: 200,
      wordsPerChapter: 3000,
      coreOutline: '少年天才遭遇变故沦为废材，机缘巧合获得上古传承，踏上逆袭之路，一步步从小城走向大陆巅峰。',
      worldSetting: '以斗气/灵力为修炼体系的大陆世界，分为多个帝国和势力。修炼者可操纵天地元力战斗。',
      goldenFinger: '上古残魂/神器/血脉觉醒',
      protagonistProfile: '十六岁少年，原为天才少年却因变故实力大减，性格隐忍坚韧，有仇必报但不滥杀。',
      globalGuidance: '每章保持爽感，节奏明快，升级打脸要有铺垫，不要无脑碾压。',
    },
  },
  {
    id: 'romance',
    name: '都市言情',
    emoji: '💝',
    description: '甜宠暧昧、职场商战、感情纠葛',
    config: {
      genre: '言情',
      subGenre: '现代言情',
      targetAudience: '女频',
      totalChapters: 120,
      wordsPerChapter: 2500,
      coreOutline: '普通女孩误入豪门世界，与傲娇总裁从欢喜冤家到真心相爱，经历家族阻力和事业挑战。',
      worldSetting: '现代都市背景，涉及商业帝国和上流社会。',
      goldenFinger: '无',
      protagonistProfile: '二十四岁职场新人，性格开朗独立，对感情认真但不盲目。',
      globalGuidance: '甜虐适度，感情线自然推进，心理描写细腻。',
    },
  },
  {
    id: 'mystery',
    name: '悬疑推理',
    emoji: '🔍',
    description: '迷雾重重、层层反转、真相大白',
    config: {
      genre: '悬疑',
      subGenre: '推理悬疑',
      targetAudience: '全龄',
      totalChapters: 80,
      wordsPerChapter: 2500,
      coreOutline: '一桩看似普通的失踪案牵出多年前的旧案，随着调查深入，真相远比想象中更加骇人。',
      worldSetting: '当代城市背景，涉及警方和民间调查。',
      goldenFinger: '超强推理能力和犯罪心理学知识',
      protagonistProfile: '三十岁刑警队长，冷静睿智，有一段不为人知的过去。',
      globalGuidance: '悬念层层递进，每章一个新线索，推理过程严密可信。',
    },
  },
  {
    id: 'scifi',
    name: '科幻星际',
    emoji: '🚀',
    description: '星际探索、AI觉醒、文明冲突',
    config: {
      genre: '科幻',
      subGenre: '星际文明',
      targetAudience: '全龄',
      totalChapters: 150,
      wordsPerChapter: 3500,
      coreOutline: '人类踏出太阳系探索银河，在一颗未知星球上发现了远古文明遗迹，这一发现将改变人类命运。',
      worldSetting: '公元2350年，人类已殖民火星和木卫二，FTL超光速技术刚被发明。',
      goldenFinger: '远古文明的遗产科技',
      protagonistProfile: '三十五岁星际探险家，理性冷静但内心热忱，有强烈的探索欲。',
      globalGuidance: '科技设定要有合理逻辑基础，人物面对宇宙的渺小感和宏大叙事交织。',
    },
  },
]

/** 获取所有模板 */
export function getTemplates(): ProjectTemplate[] {
  return PROJECT_TEMPLATES
}

/** 获取模板的 NovelConfig */
export function getTemplateConfig(templateId: string): Partial<NovelConfig> {
  const template = PROJECT_TEMPLATES.find((t) => t.id === templateId)
  return template?.config ?? {}
}
