// 保留能力：词条添加/删除/启停。
// Vocab.tsx — 接 Tauri 后端 list_vocab / add_vocab / remove_vocab / set_vocab_enabled。
// 数据落地到 ~/Library/Application Support/OpenLess/dictionary.json（与 Swift 同名）。

import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from '../components/Icon';
import { PreviewButton, PreviewCard, PreviewPageHeader } from '../components/preview/PreviewPrimitives';
import {
  addVocab,
  isTauri,
  listVocab,
  removeVocab,
  setVocabEnabled,
} from '../lib/ipc';
import type { DictionaryEntry } from '../lib/types';

export function Vocab() {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<DictionaryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  const [error, setError] = useState<string | null>(null);
  const [pendingVocabToggleIds, setPendingVocabToggleIds] = useState<Set<string>>(() => new Set());
  const pendingVocabToggleIdsRef = useRef<Set<string>>(new Set());

  const refresh = async () => {
    try {
      setError(null);
      const data = await listVocab();
      setEntries(data);
    } catch (e) {
      // 之前没 try/catch,后端 decode 失败时 spinner 永久卡死。
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const refreshAll = () => {
    void refresh();
  };

  useEffect(() => {
    refreshAll();
    // 订阅后端 vocab:updated：每段口述结束、record_hits 触发后由 coordinator 推送。
    // Vocab 页面打开期间能即时看到命中数累加，无需切到其他 tab 再切回。
    if (!isTauri) return;
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      const { listen } = await import('@tauri-apps/api/event');
      const handle = await listen('vocab:updated', () => {
        void refresh();
      });
      if (cancelled) handle();
      else unlisten = handle;
    })();
    return () => {
      cancelled = true;
      if (unlisten) unlisten();
    };
  }, []);

  const onAdd = async () => {
    const phrase = inputRef.current?.value.trim();
    if (!phrase) return;
    try {
      setError(null);
      await addVocab(phrase);
      if (inputRef.current) inputRef.current.value = '';
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      void onAdd();
    }
  };

  const onRemove = async (id: string) => {
    try {
      setError(null);
      await removeVocab(id);
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onToggle = async (entry: DictionaryEntry) => {
    if (pendingVocabToggleIdsRef.current.has(entry.id)) return;
    const next = !entry.enabled;
    pendingVocabToggleIdsRef.current.add(entry.id);
    setPendingVocabToggleIds(prev => new Set(prev).add(entry.id));
    // 乐观更新 UI；后端失败时回滚 + 让用户看到错误，避免 UI 显示「已禁用」但 ASR/polish
    // 仍在注入此词条造成的诡异状态。issue #60。
    setEntries(prev => prev.map(e => (e.id === entry.id ? { ...e, enabled: next } : e)));
    try {
      await setVocabEnabled(entry.id, next);
    } catch (err) {
      setEntries(prev => prev.map(e => (e.id === entry.id ? { ...e, enabled: entry.enabled } : e)));
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      pendingVocabToggleIdsRef.current.delete(entry.id);
      setPendingVocabToggleIds(prev => {
        const nextPending = new Set(prev);
        nextPending.delete(entry.id);
        return nextPending;
      });
    }
  };

  return (
    <div className="wi-vocab-page">
      <PreviewPageHeader
        title={t('vocab.title')}
        desc={t('vocab.desc')}
      />

      <div className="wi-vocab-layout">
        <PreviewCard className="wi-vocab-main wi-vocab-main-only">
          <div className="wi-vocab-card-head">
            <div>
              <h2>{t('vocab.sectionTitle')}</h2>
              <p>{t('vocab.tip')}</p>
            </div>
          </div>

          <div className="wi-toolbar wi-vocab-toolbar">
            <input
              className="wi-input"
              ref={inputRef}
              aria-label={t('vocab.placeholder')}
              placeholder={t('vocab.placeholder')}
              onKeyDown={onKeyDown}
            />
            <PreviewButton variant="primary" onClick={() => void onAdd()}>{t('common.add')}</PreviewButton>
          </div>

          {error && <div className="wi-vocab-error">{t('vocab.loadFailed', { err: error })}</div>}

          <div className="wi-chip-list wi-scroll">
            {loading && <div className="wi-vocab-empty">{t('common.loading')}</div>}
            {!loading && !error && entries.length === 0 && (
              <div className="wi-vocab-empty">{t('vocab.empty')}</div>
            )}
            {!error && entries.map(e => (
              <VocabChip
                key={e.id}
                entry={e}
                pending={pendingVocabToggleIds.has(e.id)}
                onRemove={() => void onRemove(e.id)}
                onToggle={() => void onToggle(e)}
              />
            ))}
          </div>
        </PreviewCard>
      </div>
    </div>
  );
}

interface VocabChipProps {
  entry: DictionaryEntry;
  pending: boolean;
  onRemove: () => void;
  onToggle: () => void;
}

function VocabChip({ entry, pending, onRemove, onToggle }: VocabChipProps) {
  const { t } = useTranslation();
  const enabled = entry.enabled;
  return (
    <span className={`${enabled ? 'wi-chip' : 'wi-chip disabled'}${entry.hits > 0 && enabled ? ' active' : ''}`}>
      <button
        type="button"
        onClick={onToggle}
        disabled={pending}
        title={enabled ? t('vocab.tipDisabled') : t('vocab.tipEnabled')}
        className="wi-chip-toggle"
      >
        <span className="wi-chip-text">{entry.phrase}</span>
      </button>
      <span className="wi-chip-count">{entry.hits}</span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={t('vocab.removeAria')}
        className="wi-chip-remove"
      >
        <Icon name="x" size={12} strokeWidth={1.8} />
      </button>
    </span>
  );
}
