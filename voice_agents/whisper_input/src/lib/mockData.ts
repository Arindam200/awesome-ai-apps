// mockData.ts — typed mirror of design_handoff_openless/data.js.
// Values must remain identical to the source so the dev UI matches the
// design canvas pixel-for-pixel.

export interface MockProvider {
  name: string;
  subname: string;
  status: 'ok' | 'warn' | 'err';
}

export interface MockMetrics {
  duration: string;
  words: string;
  perMin: string;
  saved: string;
  speedup: string;
  vocabActive: number;
  today: number;
}

export interface MockStyle {
  id: string;
  name: string;
  desc: string;
  active: boolean;
  sample: string;
}

export interface MockVocabItem {
  word: string;
  count: number;
}

export interface MockHistoryItem {
  time: string;
  style: string;
  dur: string;
  preview: string;
  tag?: string;
}

export interface MockData {
  metrics: MockMetrics;
  weekly: number[];
  providers: { asr: MockProvider; llm: MockProvider };
  styles: MockStyle[];
  vocab: MockVocabItem[];
  history: MockHistoryItem[];
}

export const OL_DATA: MockData = {
  metrics: {
    duration: '37.6 分钟',
    words: '7,484',
    perMin: '199 字',
    saved: '45.5 分钟',
    speedup: '2.2×',
    vocabActive: 28,
    today: 100,
  },
  // Last 7 days (Mon..Sun)
  weekly: [42, 28, 65, 38, 72, 88, 54],
  providers: {
    asr: { name: '火山引擎', subname: 'Volcengine · 实时流式', status: 'ok' },
    llm: { name: 'DeepSeek', subname: 'deepseek-v4-flash · 0.40 temp', status: 'ok' },
  },
  styles: [
    { id: 'raw',    name: '原文',     desc: '忠实转写',     active: false, sample: '嗯那个我刚刚看了下新出的电影预告片，挺有意思的你有空也看看。' },
    { id: 'light',  name: '轻度润色', desc: '去口癖保语气', active: false, sample: '我刚刚看了一下新出的电影预告片，挺有意思的，你有空也看看。' },
    { id: 'clear',  name: '清晰结构', desc: '结构化整理',   active: true,  sample: '刚看了新电影预告片，挺有意思。建议有空看一下，反馈下你的想法。' },
    { id: 'formal', name: '正式表达', desc: '正式书面',     active: false, sample: '我刚刚观看了新电影的预告片，内容颇具新意。如有时间，建议你也观看，并分享你的看法。' },
  ],
  vocab: [
    { word: 'LLM', count: 8 },     { word: 'macOS', count: 8 }, { word: 'openless', count: 4 },
    { word: 'iOS', count: 3 },     { word: 'GitHub', count: 3 }, { word: 'Codex', count: 2 },
    { word: 'Cloud', count: 2 },   { word: 'Hello.', count: 1 }, { word: 'A1003', count: 1 },
    { word: 'SVG', count: 1 },     { word: 'TTC', count: 0 },    { word: 'Swift', count: 0 },
    { word: 'LLMAPI', count: 0 },  { word: 'TypeLazyWordsForm', count: 0 }, { word: 'Meta', count: 0 },
    { word: 'Beta', count: 0 },    { word: 'How', count: 0 },    { word: 'Request', count: 0 },
    { word: 'Pull', count: 0 },    { word: 'Table', count: 0 },  { word: 'README', count: 0 },
    { word: 'issue', count: 0 },   { word: 'PNG', count: 0 },    { word: 'coding', count: 0 },
    { word: 'Web', count: 0 },     { word: 'QQ', count: 0 },     { word: 'Claude', count: 0 },
  ],
  history: [
    { time: '13:30', style: '清晰结构', dur: '24″', preview: '1. 删除 Windows 部分\n  1) 删除 Windows 部分的代码。\n  2) 删除 Windows 的构建缓存。', tag: '后期模型已参考 28 个词汇表词条进行语义判断' },
    { time: '13:25', style: '清晰结构', dur: '23″', preview: '1. 第一点\n  1) 删除 DOS 文件中的 VIP 等内容。\n  2) 仓库目录方案。' },
    { time: '13:24', style: '原文',     dur: '31″', preview: '嗯，DOS 文件移到文件里面，然后 Windows 这个直接删除，Windows 没有共享代码，同步更新 cloud 点 MD，Windows 直接删除。' },
    { time: '13:23', style: '清晰结构', dur: '18″', preview: '1. 代码发布\n  1) 将更改的代码提交到云端。\n  2) 构建新版本。' },
    { time: '13:21', style: '清晰结构', dur: '12″', preview: '现在整理一下整体的项目逻辑和结构，把项目结构化梳理，并将不需要的部分移入归档。' },
    { time: '12:50', style: '清晰结构', dur: '20″', preview: '1. 整体结构\n  1) 将 ASR 和 LLM 的配置合并到一个「配置」页面。' },
    { time: '12:31', style: '轻度润色', dur: '14″', preview: '把这两个 tab 合并到一起，名字就叫「设置」，把帮助中心收到右上角问号入口。' },
    { time: '11:48', style: '清晰结构', dur: '28″', preview: '设计新版本结构：本地语音交互桌面端，跨平台（Mac OS + Windows），重新设计界面，重新梳理逻辑。' },
  ],
};
