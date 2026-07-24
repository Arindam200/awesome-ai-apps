// History.tsx — 接 Tauri 后端 list_history / delete_history_entry / clear_history。
// 真实数据来自 ~/Library/Application Support/OpenLess/history.json。

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { Icon } from '../components/Icon';
import {
  PreviewButton,
  PreviewCard,
  PreviewPageHeader,
  PreviewPill,
} from '../components/preview/PreviewPrimitives';
import { detectOS } from '../components/WindowChrome';
import { formatComboLabel } from '../lib/hotkey';
import { clearHistory, deleteHistoryEntry, listHistory } from '../lib/ipc';
import {
  DOUBAO_ASR_PROVIDER_ID,
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
  QWEN_REALTIME_ASR_PROVIDER_ID,
} from '../lib/product';
import type { DictationSession, InsertStatus, PolishMode } from '../lib/types';
import { useHotkeySettings } from '../state/HotkeySettingsContext';

function useFilters(): Array<{ id: 'all' | PolishMode; label: string }> {
  const { t } = useTranslation();
  return [
    { id: 'all', label: t('history.filterAll') },
    { id: 'raw', label: t('style.modes.raw.name') },
    { id: 'light', label: t('style.modes.light.name') },
    { id: 'structured', label: t('style.modes.structured.name') },
    { id: 'formal', label: t('style.modes.formal.name') },
  ];
}

function useModeLabel(): Record<PolishMode, string> {
  const { t } = useTranslation();
  return {
    raw: t('style.modes.raw.name'),
    light: t('style.modes.light.name'),
    structured: t('style.modes.structured.name'),
    formal: t('style.modes.formal.name'),
  };
}

function providerDisplayName(providerId: string, t: TFunction, kind: 'asr' | 'llm'): string {
  const normalizedProviderId = providerId.trim().toLowerCase();
  const isQwenAsrProvider =
    providerId === QWEN_REALTIME_ASR_PROVIDER_ID ||
    ['qwen', 'qwen-realtime', 'bailian'].includes(normalizedProviderId);
  const isDoubaoAsrProvider =
    providerId === DOUBAO_ASR_PROVIDER_ID ||
    ['volcengine', 'doubao', 'doubao-streaming'].includes(normalizedProviderId);

  if (kind === 'asr') {
    if (isQwenAsrProvider) {
      return t('history.providerQwenRealtime');
    }
    if (isDoubaoAsrProvider) {
      return t('history.providerDoubaoStreaming');
    }
    return t('history.providerCloudAsr');
  }

  if (providerId === GEMINI_PROVIDER_ID) {
    return t('history.providerGemini');
  }
  if (providerId === OPENAI_COMPATIBLE_PROVIDER_ID) {
    return t('history.providerOpenAICompatible');
  }
  if (providerId === QWEN_LLM_PROVIDER_ID) {
    return t('settings.providers.presets.qwenFlash');
  }
  if (providerId === DOUBAO_LLM_PROVIDER_ID || normalizedProviderId === 'doubao' || normalizedProviderId === 'volcengine') {
    return t('settings.providers.presets.doubaoSeed20Lite');
  }
  return '—';
}

function isAsrLookingProviderId(providerId: string): boolean {
  return (
    providerId === 'local' ||
    providerId === 'offline' ||
    providerId === 'local-asr' ||
    providerId.includes('asr') ||
    providerId.includes('whisper') ||
    providerId.includes('sherpa') ||
    providerId.includes('fired') ||
    providerId.includes('firered') ||
    providerId.includes('qingyu') ||
    providerId.includes('foundry') ||
    providerId.includes('sidecar') ||
    providerId.includes('local-qwen3')
  );
}

export function History() {
  const { t } = useTranslation();
  const os = detectOS();
  const FILTERS = useFilters();
  const MODE_LABEL = useModeLabel();
  const [filter, setFilter] = useState<'all' | PolishMode>('all');
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<DictationSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const refreshSeqRef = useRef(0);
  const { prefs } = useHotkeySettings();

  const refresh = useCallback(async () => {
    const seq = refreshSeqRef.current + 1;
    refreshSeqRef.current = seq;
    setLoading(true);
    setLoadError(null);
    try {
      const data = await listHistory();
      if (refreshSeqRef.current !== seq) return;
      setItems(data);
      setActionError(null);
    } catch (error) {
      if (refreshSeqRef.current !== seq) return;
      console.error('[history] failed to load history', error);
      setLoadError(errorMessage(error));
    } finally {
      if (refreshSeqRef.current === seq) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const normalizedQuery = query.trim().toLowerCase();
  const filtered = useMemo(
    () => items.filter((session) => {
      if (filter !== 'all' && session.mode !== filter) return false;
      if (!normalizedQuery) return true;

      const searchable = [
        session.finalText,
        session.rawTranscript,
        session.appName,
        session.appBundleId,
        session.asrProviderId,
        session.llmProviderId,
        MODE_LABEL[session.mode],
      ]
        .filter(Boolean)
        .join('\n')
        .toLowerCase();

      return searchable.includes(normalizedQuery);
    }),
    [filter, items, MODE_LABEL, normalizedQuery],
  );

  const onClear = async () => {
    if (items.length === 0 || loading || clearing) return;
    if (!confirm(t('history.confirmClear', { count: items.length }))) return;
    const seq = refreshSeqRef.current + 1;
    refreshSeqRef.current = seq;
    setClearing(true);
    setLoading(false);
    setActionError(null);
    try {
      await clearHistory();
      if (refreshSeqRef.current !== seq) return;
      setItems([]);
      setLoadError(null);
    } catch (error) {
      if (refreshSeqRef.current !== seq) return;
      console.error('[history] failed to clear history', error);
      setActionError(t('history.clearFailed', { err: errorMessage(error) }));
    } finally {
      if (refreshSeqRef.current === seq) {
        setClearing(false);
        setLoading(false);
      }
    }
  };

  const onDelete = async (session: DictationSession) => {
    setActionError(null);
    try {
      await deleteHistoryEntry(session.id);
      setItems(prev => prev.filter(s => s.id !== session.id));
    } catch (error) {
      console.error('[history] failed to delete history entry', error);
      setActionError(t('history.deleteFailed', { err: errorMessage(error) }));
    }
  };

  const onCopy = async (session: DictationSession) => {
    setActionError(null);
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error(t('common.operationFailed'));
      }
      await navigator.clipboard.writeText(session.finalText);
    } catch (error) {
      console.error('[history] failed to copy history entry', error);
      setActionError(t('history.copyFailed', { err: errorMessage(error) }));
    }
  };

  return (
    <div className="wi-history-page">
      <PreviewPageHeader
        title={t('history.title')}
        desc={t('history.desc')}
        actions={<span className="wi-history-summary">{t('history.summary', { total: items.length, shown: filtered.length })}</span>}
      />

      <div className="wi-history-toolbar">
        <div className="wi-history-search">
          <Icon name="search" size={14} />
          <input
            className="wi-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('history.searchPlaceholder')}
            aria-label={t('history.searchPlaceholder')}
          />
        </div>
        <select
          className="wi-select"
          value={filter}
          onChange={(event) => setFilter(event.target.value as 'all' | PolishMode)}
          aria-label={t('history.filterLabel')}
        >
          {FILTERS.map(f => (
            <option key={f.id} value={f.id}>{f.label}</option>
          ))}
        </select>
        <PreviewButton onClick={() => void refresh()} disabled={loading || clearing}>{t('common.refresh')}</PreviewButton>
        <PreviewButton variant="danger" onClick={onClear} disabled={items.length === 0 || loading || clearing}>{t('common.clear')}</PreviewButton>
      </div>

      {actionError && <div className="wi-history-error">{actionError}</div>}

      <PreviewCard className="wi-table-card">
        <table className="wi-table">
          <colgroup>
            <col className="wi-history-col-time" />
            <col className="wi-history-col-raw" />
            <col className="wi-history-col-final" />
            <col className="wi-history-col-providers" />
            <col className="wi-history-col-status" />
            <col className="wi-history-col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th>{t('history.columnTime')}</th>
              <th>{t('history.columnRaw')}</th>
              <th>{t('history.columnFinal')}</th>
              <th>{t('history.columnProviders')}</th>
              <th>{t('history.columnStatus')}</th>
              <th>{t('history.columnActions')}</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="wi-history-state">{t('common.loading')}</td>
              </tr>
            )}
            {!loading && loadError && (
              <tr>
                <td colSpan={6} className="wi-history-state">
                  <span>{t('history.loadFailed', { err: loadError })}</span>
                  <PreviewButton onClick={() => void refresh()}>{t('history.retry')}</PreviewButton>
                </td>
              </tr>
            )}
            {!loading && !loadError && filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="wi-history-state">
                  {items.length > 0
                    ? t('history.noMatches')
                    : t('history.empty', { trigger: prefs ? formatComboLabel(prefs.dictationHotkey) : '' })}
                </td>
              </tr>
            )}
            {!loading && !loadError && filtered.map(session => (
              <tr key={session.id}>
                <td>
                  <div className="wi-history-time">{formatTime(session.createdAt)}</div>
                  <div className="wi-history-duration">{formatDuration(session.durationMs, t)}</div>
                </td>
                <td>
                  <div className="wi-history-cell-text wi-clamp-2">
                    {session.rawTranscript || t('history.rawEmpty')}
                  </div>
                </td>
                <td>
                  <div className="wi-history-cell-text wi-clamp-2">{session.finalText}</div>
                  <div className="wi-history-meta">
                    <PreviewPill tone={session.mode === 'raw' ? 'default' : 'blue'}>{MODE_LABEL[session.mode]}</PreviewPill>
                    {session.appName && <span className="wi-ellipsis">{session.appName}</span>}
                  </div>
                </td>
                <td>
                  <div className="wi-history-provider-stack">
                    <span className="wi-ellipsis">{t('history.asrProvider', { provider: providerDisplayName(session.asrProviderId ?? QWEN_REALTIME_ASR_PROVIDER_ID, t, 'asr') })}</span>
                    <span className="wi-ellipsis">{t('history.llmProvider', { provider: providerDisplayName(session.llmProviderId ?? '', t, 'llm') })}</span>
                  </div>
                </td>
                <td>
                  <PreviewPill tone={statusTone(session.insertStatus)}>
                    {insertStatusLabel(session.insertStatus, t, os)}
                  </PreviewPill>
                </td>
                <td>
                  <div className="wi-history-actions">
                    <PreviewButton onClick={() => void onCopy(session)}>{t('common.copy')}</PreviewButton>
                    <PreviewButton variant="danger" onClick={() => void onDelete(session)}>{t('common.delete')}</PreviewButton>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </PreviewCard>
    </div>
  );
}

function errorMessage(error: unknown): string {
  if (typeof error === 'string') return error;
  if (error instanceof Error) return error.message;
  return String(error);
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const pad = (n: number) => String(n).padStart(2, '0');
  if (sameDay) return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatDuration(ms: number | null, t: ReturnType<typeof useTranslation>['t']): string {
  if (ms == null || ms <= 0) return '-';
  const sec = ms / 1000;
  if (sec < 60) return t('common.durationSeconds', { value: sec.toFixed(1) });
  return t('common.durationMinutes', { value: (sec / 60).toFixed(1) });
}

function insertStatusLabel(
  status: DictationSession['insertStatus'],
  t: TFunction,
  os: ReturnType<typeof detectOS>,
): string {
  if (status === 'inserted') return t('history.inserted');
  if (status === 'pasteSent') return t('history.pasteSent');
  if (status === 'copiedFallback') {
    return t('history.copiedFallback', { shortcut: os === 'mac' ? '⌘V' : 'Ctrl+V' });
  }
  return t('history.insertFailed');
}

function statusTone(status: InsertStatus): 'default' | 'green' | 'blue' | 'orange' {
  if (status === 'inserted') return 'green';
  if (status === 'failed') return 'orange';
  return 'blue';
}
