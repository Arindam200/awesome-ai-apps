export const REQUIRED_APP_TABS = ['overview', 'history', 'vocab', 'style', 'settings'] as const;
export const TOP_TOOL_LABELS = ['帮助', '主题切换', '中 / EN'] as const;

export const REQUIRED_SETTINGS_SECTIONS = [
  'models',
  'recording',
  'privacy',
  'output',
  'about',
] as const;

export const HISTORY_ROW_ACTION_LABELS = ['复制', '删除'] as const;
export const FORBIDDEN_HISTORY_ACTIONS = ['重新润色'] as const;
export const FORBIDDEN_RECORDING_LABELS = ['启用提示音', '录音状态浮窗'] as const;
export const FORBIDDEN_ABOUT_LABELS = ['开发者', '隐私政策'] as const;
export const ABOUT_REQUIRED_COPY = '如果喜欢这个项目，请前往 GitHub 点亮 Star，支持继续迭代。';
export const ABOUT_REQUIRED_PRIMARY_ACTION = '去 GitHub 点亮 Star';

export const PREVIEW_NAV_ICON_PATHS = {
  overview: [
    'M3 11.5 12 4l9 7.5',
    'M6 10.5V20h12v-9.5',
    'M10 20v-6h4v6',
  ],
  history: [
    'M3 12a9 9 0 1 0 3-6.7',
    'M3 4v5h5',
    'M12 7v6l4 2',
  ],
  vocab: [
    'M5 4h10a3 3 0 0 1 3 3v14H7a2 2 0 0 1-2-2z',
    'M8 8h6M8 12h5',
  ],
  style: [
    'M4 20c4-1 7-3 9-7',
    'M12 13 20 5l-1-1-8 8',
    'M14 5l5 5',
  ],
  settings: [
    'M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5z',
    'M19.4 15a7.6 7.6 0 0 0 .1-1.2 7.6 7.6 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a7.5 7.5 0 0 0-2-1.2L14.7 5h-4l-.4 2.5a7.5 7.5 0 0 0-2 1.2l-2.4-1-2 3.5 2 1.5a7.6 7.6 0 0 0-.1 1.2c0 .4 0 .8.1 1.2l-2 1.5 2 3.5 2.4-1a7.5 7.5 0 0 0 2 1.2l.4 2.5h4l.4-2.5a7.5 7.5 0 0 0 2-1.2l2.4 1 2-3.5-2-1.5z',
  ],
} as const;

export const PREVIEW_VISUAL_TOKENS = {
  winTitlebarHeight: '56',
  mainPadding: '31px 34px 32px',
  sidebarPadding: '28px 10px 22px',
  navButtonHeight: '52px',
  navIconSize: '24',
  navFont: '500 17px/1',
  topToolsTop: '27px',
  topToolHeight: '38px',
  modelCardColumns: '86px 1fr auto',
  modelLogoClass: 'wi-model-logo',
} as const;
