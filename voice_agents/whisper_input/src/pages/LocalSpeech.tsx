import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import {
  downloadQingyuAsr,
  getQingyuAsrManifest,
  getQingyuAsrStatus,
  repairQingyuAsr,
  type ModelManifest,
  type QingyuAsrStatus,
} from '../lib/qingyuAsr';
import { PRODUCT_FEATURES } from '../lib/productMode';
import { Btn, Card, PageHeader, Pill } from './_atoms';

type BusyAction = 'refresh' | 'download' | 'repair' | null;

const inputStyle: CSSProperties = {
  width: '100%',
  height: 32,
  borderRadius: 8,
  border: '0.5px solid var(--ol-line-strong)',
  background: 'var(--ol-surface)',
  color: 'var(--ol-ink)',
  fontFamily: 'inherit',
  fontSize: 12.5,
  padding: '0 10px',
  outline: 'none',
  boxSizing: 'border-box',
};

export function LocalSpeech() {
  if (!PRODUCT_FEATURES.showLocalAsrExperiments) {
    return <LocalAsrExperimentUnavailable />;
  }
  return <LocalSpeechExperiment />;
}

// Deprecated non-product local ASR experiment. Standard product mode must render
// LocalAsrExperimentUnavailable above so these hooks never trigger local ASR IPC.
function LocalSpeechExperiment() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<QingyuAsrStatus | null>(null);
  const [manifest, setManifest] = useState<ModelManifest | null>(null);
  const [busy, setBusy] = useState<BusyAction>('refresh');
  const [error, setError] = useState<string | null>(null);
  const [customBaseUrl, setCustomBaseUrl] = useState('');
  const mountedRef = useRef(false);
  const requestSeqRef = useRef(0);

  const load = useCallback(async (options: { silent?: boolean } = {}) => {
    const seq = ++requestSeqRef.current;
    if (!options.silent) {
      setBusy('refresh');
    }
    setError(null);
    try {
      const [nextStatus, nextManifest] = await Promise.all([
        getQingyuAsrStatus(),
        getQingyuAsrManifest(),
      ]);
      if (!mountedRef.current || seq !== requestSeqRef.current) return;
      setStatus(nextStatus);
      setManifest(nextManifest);
    } catch (err) {
      if (!mountedRef.current || seq !== requestSeqRef.current) return;
      setError(errorMessage(err));
    } finally {
      if (mountedRef.current && seq === requestSeqRef.current && !options.silent) {
        setBusy(null);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void load();
    return () => {
      mountedRef.current = false;
      requestSeqRef.current += 1;
    };
  }, [load]);

  const manifestSize = useMemo(
    () => manifest?.files.reduce((sum, file) => sum + file.size, 0) ?? null,
    [manifest],
  );
  const totalSize = status?.modelSizeBytes ?? manifestSize;
  const primarySource = manifest?.sources.find(source => source.id === 'github-release') ?? manifest?.sources[0];
  const trimmedBaseUrl = customBaseUrl.trim();
  const disabled = busy !== null;

  const runDownload = async () => {
    if (disabled) return;
    const seq = ++requestSeqRef.current;
    setBusy('download');
    setError(null);
    try {
      const nextStatus = await downloadQingyuAsr('github-release', trimmedBaseUrl || undefined);
      if (!mountedRef.current || seq !== requestSeqRef.current) return;
      setStatus(nextStatus);
      const [nextRefreshedStatus, nextManifest] = await Promise.all([
        getQingyuAsrStatus(),
        getQingyuAsrManifest(),
      ]);
      if (!mountedRef.current || seq !== requestSeqRef.current) return;
      setStatus(nextRefreshedStatus);
      setManifest(nextManifest);
    } catch (err) {
      if (!mountedRef.current || seq !== requestSeqRef.current) return;
      setError(errorMessage(err));
    } finally {
      if (mountedRef.current && seq === requestSeqRef.current) {
        setBusy(null);
      }
    }
  };

  const runRepair = async () => {
    if (disabled) return;
    const seq = ++requestSeqRef.current;
    setBusy('repair');
    setError(null);
    try {
      const nextStatus = await repairQingyuAsr(trimmedBaseUrl || undefined);
      if (!mountedRef.current || seq !== requestSeqRef.current) return;
      setStatus(nextStatus);
      const [nextRefreshedStatus, nextManifest] = await Promise.all([
        getQingyuAsrStatus(),
        getQingyuAsrManifest(),
      ]);
      if (!mountedRef.current || seq !== requestSeqRef.current) return;
      setStatus(nextRefreshedStatus);
      setManifest(nextManifest);
    } catch (err) {
      if (!mountedRef.current || seq !== requestSeqRef.current) return;
      setError(errorMessage(err));
    } finally {
      if (mountedRef.current && seq === requestSeqRef.current) {
        setBusy(null);
      }
    }
  };

  const statusTone = status?.modelState === 'installed'
    ? 'ok'
    : status?.modelState === 'downloading'
      ? 'blue'
      : 'outline';
  const modelStateLabel = status
    ? status.modelSource === 'development' && status.modelState === 'installed'
      ? t('localSpeech.developmentModelAvailable')
      : t(`localSpeech.modelStates.${status.modelState}`)
    : t('common.loading');
  const modelSourceLabel = status
    ? t(`localSpeech.modelSources.${status.modelSource}`)
    : t('common.loading');

  return (
    <>
      <PageHeader
        kicker={t('localSpeech.kicker')}
        title={t('localSpeech.title')}
        desc={t('localSpeech.desc')}
        right={(
          <Btn
            variant="ghost"
            size="sm"
            icon="refresh"
            disabled={disabled}
            onClick={() => void load()}
          >
            {busy === 'refresh' ? t('localSpeech.refreshing') : t('localSpeech.refresh')}
          </Btn>
        )}
      />

      <Card>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 12, alignItems: 'start' }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ol-ink)' }}>
                {t('localSpeech.currentAsr')}
              </div>
              <div style={{ fontSize: 12, color: 'var(--ol-ink-3)', marginTop: 4 }}>
                {status?.displayName || t('localSpeech.localSpeechName')}
              </div>
            </div>
            <Pill tone={statusTone}>
              {modelStateLabel}
            </Pill>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
            <InfoCell label={t('localSpeech.modelId')} value={status?.modelId || manifest?.modelId || t('common.loading')} mono />
            <InfoCell
              label={t('localSpeech.modelSource')}
              value={modelSourceLabel}
              tone={status?.modelSource === 'development' ? 'blue' : 'outline'}
            />
            <InfoCell label={t('localSpeech.totalSize')} value={totalSize == null ? t('localSpeech.sizeUnknown') : formatBytes(totalSize)} />
            <InfoCell
              label={t('localSpeech.vad')}
              value={status?.vadAvailable ? t('localSpeech.available') : t('localSpeech.missing')}
              tone={status?.vadAvailable ? 'ok' : 'outline'}
            />
            <InfoCell
              label={t('localSpeech.downloadSource')}
              value={primarySource ? `${primarySource.label} · ${primarySource.baseUrl}` : t('localSpeech.sourceDefault')}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--ol-ink-2)', marginBottom: 6 }}>
              {t('localSpeech.customSource')}
            </label>
            <input
              value={customBaseUrl}
              onChange={event => setCustomBaseUrl(event.target.value)}
              placeholder={primarySource?.baseUrl ?? t('localSpeech.sourcePlaceholder')}
              style={inputStyle}
            />
            <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginTop: 6, lineHeight: 1.5 }}>
              {t('localSpeech.customSourceDesc')}
            </div>
          </div>

          {(error || status?.error) && (
            <div
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                background: 'rgba(239,68,68,0.08)',
                color: 'var(--ol-red, #ef4444)',
                fontSize: 12,
                lineHeight: 1.5,
              }}
            >
              {t('localSpeech.error')}: {error || status?.error}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            <Btn variant="ghost" disabled={disabled} onClick={() => void runRepair()}>
              {busy === 'repair' ? t('localSpeech.repairing') : t('localSpeech.repair')}
            </Btn>
            <Btn variant="primary" disabled={disabled} onClick={() => void runDownload()}>
              {busy === 'download' ? t('localSpeech.downloading') : t('localSpeech.download')}
            </Btn>
          </div>
        </div>
      </Card>
    </>
  );
}

function LocalAsrExperimentUnavailable() {
  return (
    <>
      <PageHeader
        kicker="Cloud-first"
        title="Local ASR experiment unavailable"
        desc="The standard product uses cloud ASR by default. Local ASR is a deprecated non-product experiment."
      />
      <Card>
        <div style={{ fontSize: 12.5, color: 'var(--ol-ink-3)', lineHeight: 1.6 }}>
          This page is not available in standard product mode.
        </div>
      </Card>
    </>
  );
}

function InfoCell({
  label,
  value,
  mono = false,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: 'ok' | 'blue' | 'outline';
}) {
  return (
    <div
      style={{
        minWidth: 0,
        padding: '10px 12px',
        borderRadius: 8,
        background: 'var(--ol-surface-2)',
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--ol-ink-4)', marginBottom: 4 }}>{label}</div>
      {tone ? (
        <Pill tone={tone} size="sm">{value}</Pill>
      ) : (
        <div
          style={{
            fontSize: 12.5,
            color: 'var(--ol-ink-2)',
            lineHeight: 1.45,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontFamily: mono ? 'var(--ol-font-mono)' : 'inherit',
          }}
          title={value}
        >
          {value}
        </div>
      )}
    </div>
  );
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(0)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
