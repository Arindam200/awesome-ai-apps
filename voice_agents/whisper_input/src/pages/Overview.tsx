// Overview.tsx — 真实指标，从 listHistory + getCredentials 派生。

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from '../components/Icon';
import { PreviewButton, PreviewCard, PreviewPageHeader, PreviewPill } from '../components/preview/PreviewPrimitives';
import { detectOS } from '../components/WindowChrome';
import { formatComboLabel } from '../lib/hotkey';
import { getCredentials, getUsageStats, listHistory } from '../lib/ipc';
import { buildOverviewMetrics, buildWeeklyUsage } from '../lib/overviewMetrics';
import type { WeeklyUsageDay } from '../lib/overviewMetrics';
import { providerLogoSrc } from '../lib/providerBrand';
import {
  DEFAULT_ASR_PROVIDER_ID,
  DEFAULT_LLM_PROVIDER_ID,
  DOUBAO_ASR_PROVIDER_ID,
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
  QWEN_REALTIME_ASR_PROVIDER_ID,
} from '../lib/product';
import type { CredentialsStatus, DictationSession, PolishMode, UsageStats } from '../lib/types';
import { useHotkeySettings } from '../state/HotkeySettingsContext';

function useModeLabels(): Record<PolishMode, string> {
  const { t } = useTranslation();
  return {
    raw: t('style.modes.raw.name'),
    light: t('style.modes.light.name'),
    structured: t('style.modes.structured.name'),
    formal: t('style.modes.formal.name'),
  };
}

interface OverviewProps {
  onOpenHistory?: () => void;
  onOpenSettings?: () => void;
}

const ASR_NAME_KEY_BY_ID: Record<string, string> = {
  [QWEN_REALTIME_ASR_PROVIDER_ID]: 'asrQwenRealtime',
  [DOUBAO_ASR_PROVIDER_ID]: 'asrDoubaoStreaming',
};

const LLM_NAME_KEY_BY_ID: Record<string, string> = {
  [QWEN_LLM_PROVIDER_ID]: 'qwenFlash',
  [DOUBAO_LLM_PROVIDER_ID]: 'doubaoSeed20Lite',
  [OPENAI_COMPATIBLE_PROVIDER_ID]: 'openaiCompatible',
  [GEMINI_PROVIDER_ID]: 'gemini',
  ark: 'ark',
  deepseek: 'deepseek',
  siliconflow: 'siliconflow',
  openai: 'openai',
  codex_oauth: 'codexOAuth',
  mimo: 'mimo',
  cometapi: 'cometapi',
  openrouterFree: 'openrouterFree',
  alibabaCoding: 'alibabaCoding',
  codingPlanX: 'codingPlanX',
  custom: 'custom',
};

export function Overview({ onOpenHistory, onOpenSettings }: OverviewProps) {
  const { t } = useTranslation();
  const os = detectOS();
  const modeLabel = useModeLabels();
  const [history, setHistory] = useState<DictationSession[]>([]);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [historyError, setHistoryError] = useState(false);
  const [credsError, setCredsError] = useState(false);
  const [creds, setCreds] = useState<CredentialsStatus>({
    activeAsrProvider: DEFAULT_ASR_PROVIDER_ID,
    activeLlmProvider: DEFAULT_LLM_PROVIDER_ID,
    asrConfigured: false,
    llmConfigured: false,
    volcengineConfigured: false,
    arkConfigured: false,
  });
  const { prefs } = useHotkeySettings();

  const refreshHistory = useCallback(() => {
    setHistoryError(false);
    Promise.all([listHistory(), getUsageStats()])
      .then(([historyItems, stats]) => {
        setHistory(historyItems);
        setUsageStats(stats);
      })
      .catch(error => {
        console.error('[overview] failed to load history', error);
        setHistoryError(true);
        setUsageStats(null);
      });
  }, []);

  useEffect(() => {
    refreshHistory();
    getCredentials()
      .then(status => {
        setCreds(status);
        setCredsError(false);
      })
      .catch(error => {
        console.error('[overview] failed to load credentials status', error);
        setCredsError(true);
      });
  }, [refreshHistory]);

  const metrics = useMemo(() => buildOverviewMetrics(history, new Date(), usageStats), [history, usageStats]);
  const weekly = useMemo(() => buildWeeklyUsage(history), [history]);
  const weeklyTotals = useMemo(() => {
    const sessions = weekly.reduce((sum, day) => sum + day.sessions, 0);
    const chars = weekly.reduce((sum, day) => sum + day.chars, 0);
    const activeDays = weekly.filter(day => day.sessions > 0).length;
    return { sessions, chars, activeDays };
  }, [weekly]);

  const asrProviderId = creds.activeAsrProvider || DEFAULT_ASR_PROVIDER_ID;
  const llmProviderId = creds.activeLlmProvider || DEFAULT_LLM_PROVIDER_ID;
  const asrNameKey = ASR_NAME_KEY_BY_ID[asrProviderId];
  const llmNameKey = LLM_NAME_KEY_BY_ID[llmProviderId];
  const asrProviderName = asrNameKey
    ? t(`settings.providers.presets.${asrNameKey}`)
    : t('settings.providers.presets.asrQwenRealtime');
  const asrProviderSubname =
    asrProviderId === QWEN_REALTIME_ASR_PROVIDER_ID
      ? 'Qwen realtime'
      : asrProviderId === DOUBAO_ASR_PROVIDER_ID
        ? 'Doubao backup'
        : 'Qwen realtime';
  const llmProviderName = llmNameKey
    ? t(`settings.providers.presets.${llmNameKey}`)
    : llmProviderId;
  const asrLogoSrc = providerLogoSrc(asrProviderId);
  const llmLogoSrc = providerLogoSrc(llmProviderId);

  return (
    <div className="wi-overview-page">
      <PreviewPageHeader className="wi-overview-page-head" title={t('overview.title')} desc={t('overview.desc')} />

      <div className="wi-model-grid">
        <ProviderCard
          logoSrc={asrLogoSrc}
          kind={t('overview.asrKind')}
          name={asrProviderName}
          subname={asrProviderSubname}
          status={credsError ? 'error' : creds.asrConfigured ? 'configured' : 'notConfigured'}
          onOpenSettings={onOpenSettings}
        />
        <ProviderCard
          logoSrc={llmLogoSrc}
          kind={t('overview.llmKind')}
          name={llmProviderName}
          subname={llmProviderId}
          status={credsError ? 'error' : creds.llmConfigured ? 'configured' : 'notConfigured'}
          onOpenSettings={onOpenSettings}
        />
      </div>

      <div className="wi-metric-grid">
        <Metric iconName="hash" label={t('overview.metricChars')} value={historyError ? '—' : metrics.charsToday.toLocaleString()} trend={historyError ? t('overview.historyLoadError') : t('overview.metricSegments', { count: metrics.segmentsToday })} />
        <Metric iconName="mic" label={t('overview.metricDuration')} value={historyError ? '—' : formatVoiceInputDuration(metrics.totalDurationMs, t)} trend={historyError ? t('overview.historyLoadError') : t('overview.metricTotalTrend')} accent />
        <Metric iconName="clock" label={t('overview.metricAvg')} value={historyError ? '—' : formatDuration(metrics.avgLatencyMs, t)} trend={historyError ? t('overview.historyLoadError') : metrics.segmentsToday > 0 ? t('overview.metricAvgTrend') : t('overview.metricNoData')} tone="purple" />
        <Metric iconName="doc" label={t('overview.metricTotal')} value={historyError ? '—' : metrics.totalChars.toLocaleString()} trend={historyError ? t('overview.historyLoadError') : t('overview.metricTotalTrend')} />
      </div>

      <div className="wi-overview-bottom">
        <PreviewCard className="wi-week-card">
          <div className="wi-overview-card-head">
            <span className="wi-overview-card-title">
              {t('overview.weekTitle')}
              <Icon name="help" size={16} strokeWidth={1.9} />
            </span>
            <span className="wi-overview-card-unit">{t('overview.weekUnit')}</span>
          </div>
          {historyError ? (
            <div className="wi-overview-empty">
              {t('overview.historyLoadError')}
            </div>
          ) : (
            <WeekChart days={weekly} />
          )}
          <div className="wi-chart-note">
            {weeklyTotals.sessions > 0
              ? t('overview.weekNote', {
                  count: weeklyTotals.sessions,
                  chars: weeklyTotals.chars.toLocaleString(),
                  days: weeklyTotals.activeDays,
                })
              : t('overview.weekNoteEmpty')}
          </div>
        </PreviewCard>

        <PreviewCard className="wi-recent-card">
          <div className="wi-overview-card-head wi-recent-head">
            <span>{t('overview.recentTitle')}</span>
            <PreviewButton onClick={onOpenHistory}>{t('overview.recentAll')}</PreviewButton>
          </div>
          <div className="wi-scroll wi-recent-list">
            {historyError ? (
              <div className="wi-overview-empty wi-recent-empty">
                <span>{t('overview.recentLoadFailed')}</span>
                <PreviewButton onClick={refreshHistory}>{t('overview.historyRetry')}</PreviewButton>
              </div>
            ) : (
              <>
                {history.length === 0 && (
                  <div className="wi-overview-empty wi-recent-empty">
                    {t('overview.recentEmpty', { trigger: prefs ? formatComboLabel(prefs.dictationHotkey) : '' })}
                  </div>
                )}
                {history.slice(0, 5).map(s => (
                  <RecentRow key={s.id} session={s} modeLabel={modeLabel} os={os} />
                ))}
              </>
            )}
          </div>
        </PreviewCard>
      </div>
    </div>
  );
}

interface ProviderCardProps {
  logoSrc: string;
  kind: string;
  name: string;
  subname: string;
  status: 'configured' | 'notConfigured' | 'error';
  onOpenSettings?: () => void;
}

function ProviderCard({ logoSrc, kind, name, subname, status, onOpenSettings }: ProviderCardProps) {
  const { t } = useTranslation();
  const isAsr = kind === t('overview.asrKind');
  return (
    <PreviewCard className={`wi-provider-card ${isAsr ? 'wi-provider-card-asr' : 'wi-provider-card-llm'}`}>
      <img className="wi-model-logo" src={logoSrc} alt="" />
      <div className="wi-provider-main">
        <div className="wi-provider-meta">
          <span>{kind}</span>
          {status === 'configured' && (
            <PreviewPill tone="green">
              <span className="wi-status-dot" />
              {t('overview.statusConfigured')}
            </PreviewPill>
          )}
          {status === 'notConfigured' && (
            <PreviewPill>{t('overview.statusNotConfigured')}</PreviewPill>
          )}
          {status === 'error' && (
            <PreviewPill className="wi-pill-error">{t('overview.statusUnknown')}</PreviewPill>
          )}
        </div>
        <div className="wi-provider-name">{name}</div>
        <div className={`wi-provider-subname ${status === 'error' ? 'wi-provider-subname-error' : ''}`}>
          {status === 'error' ? t('overview.credentialsLoadError') : subname}
        </div>
      </div>
      <div className="wi-provider-actions">
        <PreviewButton onClick={onOpenSettings}>{t('overview.changeModel')}</PreviewButton>
      </div>
    </PreviewCard>
  );
}

interface MetricProps {
  iconName: string;
  label: string;
  value: string;
  trend: string;
  accent?: boolean;
  tone?: 'blue' | 'purple';
}

function Metric({ iconName, label, value, trend, accent, tone = 'blue' }: MetricProps) {
  return (
    <PreviewCard className="wi-metric-card">
      <div className={`wi-metric-icon ${accent ? 'wi-metric-icon-accent' : ''} ${tone === 'purple' ? 'wi-metric-icon-purple' : ''}`}>
        <Icon name={iconName} size={22} strokeWidth={1.75} />
      </div>
      <div className="wi-metric-copy">
        <span>{label}</span>
        <b className={accent ? 'wi-metric-accent' : undefined}>{value}</b>
        <small>{trend || '\u00a0'}</small>
      </div>
    </PreviewCard>
  );
}

function WeekChart({ days }: { days: WeeklyUsageDay[] }) {
  const { t } = useTranslation();
  const maxChars = Math.max(1, ...days.map(day => day.chars));
  const axisMax = niceAxisMax(maxChars);
  const hasData = days.some(day => day.sessions > 0);
  const chartWidth = 320;
  const chartHeight = 118;
  const padX = 12;
  const padY = 18;
  const innerWidth = chartWidth - padX * 2;
  const innerHeight = chartHeight - padY * 2;
  const points = days.map((day, index) => {
    const x = padX + (innerWidth / Math.max(1, days.length - 1)) * index;
    const y = padY + (1 - day.chars / axisMax) * innerHeight;
    return { day, x, y };
  });
  const linePath = points.map((point, index) => {
    if (index === 0) return `M ${point.x} ${point.y}`;
    const previous = points[index - 1];
    const dx = (point.x - previous.x) / 2;
    return `C ${previous.x + dx} ${previous.y}, ${point.x - dx} ${point.y}, ${point.x} ${point.y}`;
  }).join(' ');
  const areaPath = points.length > 0
    ? `${linePath} L ${points[points.length - 1].x} ${chartHeight - padY} L ${points[0].x} ${chartHeight - padY} Z`
    : '';

  return (
    <div className="wi-week-chart">
      {!hasData && <div className="wi-week-empty">{t('overview.weekEmpty')}</div>}
      <div className="wi-week-line-chart" aria-label={t('overview.weekTitle')}>
        <div className="wi-week-y-axis" aria-hidden>
          <span>{axisMax.toLocaleString()}</span>
          <span>{Math.round(axisMax / 2).toLocaleString()}</span>
          <span>0</span>
        </div>
        <div className="wi-week-line-plot">
          <svg className="wi-week-line-svg" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none">
            <line className="wi-week-grid-line" x1="0" y1={padY} x2={chartWidth} y2={padY} />
            <line className="wi-week-grid-line" x1="0" y1={chartHeight / 2} x2={chartWidth} y2={chartHeight / 2} />
            <line className="wi-week-grid-line" x1="0" y1={chartHeight - padY} x2={chartWidth} y2={chartHeight - padY} />
            {hasData && <path className="wi-week-area" d={areaPath} />}
            {hasData && <path className="wi-week-line" d={linePath} />}
          </svg>
          {points.map(point => (
            <div
              className={`wi-week-point ${point.day.isToday ? 'wi-week-point-today' : ''}`}
              key={point.day.key}
              style={{
                left: `${(point.x / chartWidth) * 100}%`,
                top: `${(point.y / chartHeight) * 100}%`,
              }}
              title={`${point.day.label}: ${t('overview.metricSegments', { count: point.day.sessions })} · ${point.day.chars.toLocaleString()} ${t('overview.metricChars')}`}
            >
              <span className="wi-week-point-value">{point.day.chars.toLocaleString()}</span>
              <span className="wi-week-point-dot" />
            </div>
          ))}
        </div>
        <div className="wi-week-axis">
          {days.map(day => (
            <div className={`wi-week-axis-day ${day.isToday ? 'wi-week-axis-day-today' : ''}`} key={day.key}>
              <span className="wi-week-date">{day.label}</span>
              <span className="wi-week-label">{day.shortLabel}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function niceAxisMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const nice = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return nice * magnitude;
}

function RecentRow({
  session,
  modeLabel,
  os,
}: {
  session: DictationSession;
  modeLabel: Record<PolishMode, string>;
  os: ReturnType<typeof detectOS>;
}) {
  const { t } = useTranslation();
  return (
    <div className="wi-recent-row">
      <div className="wi-recent-time">
        <span>
          {formatTime(session.createdAt)}
        </span>
        <PreviewPill>{modeLabel[session.mode]}</PreviewPill>
      </div>
      <div className="wi-recent-main">
        <div className="wi-recent-text wi-clamp-2">
          {session.finalText.split('\n')[0]}
        </div>
        <div className="wi-recent-tags">
          <PreviewPill>{providerSummary(session, t)}</PreviewPill>
          <PreviewPill tone={session.insertStatus === 'failed' ? 'orange' : 'green'}>
            {insertStatusLabel(session.insertStatus, t, os)}
          </PreviewPill>
        </div>
      </div>
      <span className="wi-recent-duration">
        {formatDuration(session.durationMs ?? 0, t)}
      </span>
    </div>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const pad = (n: number) => String(n).padStart(2, '0');
  if (sameDay) return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatDuration(ms: number, t: ReturnType<typeof useTranslation>['t']): string {
  if (ms <= 0) return '—';
  const sec = ms / 1000;
  if (sec < 60) return t('common.durationSeconds', { value: sec.toFixed(1) });
  return `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;
}

function formatVoiceInputDuration(ms: number, t: ReturnType<typeof useTranslation>['t']): string {
  if (ms <= 0) return '—';
  const totalMinutes = Math.round(ms / 60000);
  if (totalMinutes < 60) {
    return t('common.durationMinutes', { value: Math.max(totalMinutes, 1) });
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return t('overview.metricVoiceInputHours', { hours, minutes });
}

function providerSummary(session: DictationSession, t: ReturnType<typeof useTranslation>['t']): string {
  const asr = session.asrProviderId ? asrProviderDisplayName(session.asrProviderId, t) : '—';
  const llm = session.llmProviderId ? llmProviderDisplayName(session.llmProviderId, t) : '—';
  return `${t('history.asrProvider', { provider: asr })} · ${t('history.llmProvider', { provider: llm })}`;
}

function asrProviderDisplayName(providerId: string, t: ReturnType<typeof useTranslation>['t']): string {
  if (providerId === QWEN_REALTIME_ASR_PROVIDER_ID) return t('history.providerQwenRealtime');
  if (providerId === DOUBAO_ASR_PROVIDER_ID) return t('history.providerDoubaoStreaming');
  return t('history.providerQwenRealtime');
}

function llmProviderDisplayName(providerId: string, t: ReturnType<typeof useTranslation>['t']): string {
  if (providerId === GEMINI_PROVIDER_ID) return t('history.providerGemini');
  if (providerId === OPENAI_COMPATIBLE_PROVIDER_ID) return t('history.providerOpenAICompatible');
  if (providerId === QWEN_LLM_PROVIDER_ID) return t('settings.providers.presets.qwenFlash');
  if (providerId === DOUBAO_LLM_PROVIDER_ID) return t('settings.providers.presets.doubaoSeed20Lite');
  if (providerId === QWEN_REALTIME_ASR_PROVIDER_ID || providerId === DOUBAO_ASR_PROVIDER_ID || isLocalAsrProviderId(providerId)) {
    return t('settings.providers.presets.qwenFlash');
  }
  return providerId;
}

function isLocalAsrProviderId(providerId: string): boolean {
  const normalized = providerId.toLowerCase();
  return normalized.includes('asr') || normalized.includes('sherpa') || normalized.includes('fired') || normalized.includes('firered') || normalized.includes('qingyu');
}

function insertStatusLabel(
  status: DictationSession['insertStatus'],
  t: ReturnType<typeof useTranslation>['t'],
  os: ReturnType<typeof detectOS>,
): string {
  if (status === 'inserted') return t('history.inserted');
  if (status === 'pasteSent') return t('history.pasteSent');
  if (status === 'copiedFallback') {
    return t('history.copiedFallback', { shortcut: os === 'mac' ? '⌘V' : 'Ctrl+V' });
  }
  return t('history.insertFailed');
}
