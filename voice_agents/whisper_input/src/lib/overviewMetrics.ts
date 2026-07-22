import type { DictationSession, UsageStats } from './types';

export interface OverviewMetrics {
  charsToday: number;
  segmentsToday: number;
  totalChars: number;
  totalDurationMs: number;
  avgLatencyMs: number;
}

export interface WeeklyUsageDay {
  key: string;
  label: string;
  shortLabel: string;
  sessions: number;
  chars: number;
  durationMs: number;
  isToday: boolean;
}

export function buildOverviewMetrics(
  history: DictationSession[],
  referenceDate = new Date(),
  usageStats: UsageStats | null = null,
): OverviewMetrics {
  const todayStart = new Date(referenceDate);
  todayStart.setHours(0, 0, 0, 0);
  const tomorrowStart = new Date(todayStart);
  tomorrowStart.setDate(todayStart.getDate() + 1);

  let charsToday = 0;
  let segmentsToday = 0;
  let todayDurationMs = 0;
  let totalChars = 0;
  let totalDurationMs = 0;

  for (const session of history) {
    const finalTextLength = session.finalText.length;
    const durationMs = session.durationMs ?? 0;
    const createdAt = new Date(session.createdAt);
    const isToday =
      !Number.isNaN(createdAt.getTime()) &&
      createdAt >= todayStart &&
      createdAt < tomorrowStart;

    totalChars += finalTextLength;
    totalDurationMs += durationMs;

    if (isToday) {
      charsToday += finalTextLength;
      segmentsToday += 1;
      todayDurationMs += durationMs;
    }
  }

  return {
    charsToday,
    segmentsToday,
    totalChars: usageStats?.totalChars ?? totalChars,
    totalDurationMs: usageStats?.totalDurationMs ?? totalDurationMs,
    avgLatencyMs: segmentsToday > 0 ? todayDurationMs / segmentsToday : 0,
  };
}

export function buildWeeklyUsage(
  history: DictationSession[],
  referenceDate = new Date(),
): WeeklyUsageDay[] {
  const todayStart = startOfLocalDay(referenceDate);
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(todayStart);
    date.setDate(todayStart.getDate() - (6 - index));
    return {
      key: localDateKey(date),
      label: `${date.getMonth() + 1}/${date.getDate()}`,
      shortLabel: weekdayLabel(date),
      sessions: 0,
      chars: 0,
      durationMs: 0,
      isToday: index === 6,
    };
  });
  const dayByKey = new Map(days.map(day => [day.key, day]));

  for (const session of history) {
    const createdAt = new Date(session.createdAt);
    if (Number.isNaN(createdAt.getTime())) continue;
    const day = dayByKey.get(localDateKey(createdAt));
    if (!day) continue;
    day.sessions += 1;
    day.chars += session.finalText.length;
    day.durationMs += session.durationMs ?? 0;
  }

  return days;
}

function startOfLocalDay(date: Date): Date {
  const start = new Date(date);
  start.setHours(0, 0, 0, 0);
  return start;
}

function localDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function weekdayLabel(date: Date): string {
  return ['日', '一', '二', '三', '四', '五', '六'][date.getDay()];
}
