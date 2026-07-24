export const APP_TABS = ['overview', 'history', 'vocab', 'style', 'settings'] as const;

export type AppTab = (typeof APP_TABS)[number];

export function normalizeAppTab(value: string | null | undefined): AppTab {
  return APP_TABS.includes(value as AppTab) ? (value as AppTab) : 'overview';
}
