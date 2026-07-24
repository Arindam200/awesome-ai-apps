import { useState } from 'react';
import { normalizeAppTab, type AppTab } from '../lib/appNavigation';

export type { AppTab };

export interface AppState {
  currentTab: AppTab;
  setCurrentTab: (tab: AppTab) => void;
}

export function useAppState(initialTab: string | null = 'overview'): AppState {
  const [currentTab, setCurrentTab] = useState<AppTab>(() => normalizeAppTab(initialTab));
  return { currentTab, setCurrentTab };
}
