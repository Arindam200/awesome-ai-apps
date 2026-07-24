// localAsr.ts — IPC + 事件类型 for 本地 ASR 引擎与模型管理。
//
// 后端命令定义：openless-all/app/src-tauri/src/commands.rs `local_asr_*`
// 事件：local-asr-download-progress / local-asr-token
//
// 注意：模型文件清单与尺寸不在此处硬编码 —— 通过
// `fetchLocalAsrRemoteInfo()` 实时从 HuggingFace tree API 拉取。

import { invokeOrMock } from './ipc';

export type LocalAsrMirror = 'huggingface' | 'hf-mirror';

export interface LocalAsrSettings {
  providerId: string;
  activeModel: string;
  mirror: string;
  /** macOS 才编入 antirez/qwen-asr 引擎；Win 端 UI 据此把"开始"按钮灰掉。 */
  engineAvailable: boolean;
}

export interface LocalAsrModelStatus {
  id: string;
  hfRepo: string;
  downloadedBytes: number;
  isDownloaded: boolean;
}

export interface LocalAsrRemoteFile {
  path: string;
  size: number;
}

export interface LocalAsrRemoteInfo {
  modelId: string;
  mirror: string;
  files: LocalAsrRemoteFile[];
  totalBytes: number;
}

export type LocalAsrDownloadPhase =
  | 'started'
  | 'progress'
  | 'finished'
  | 'cancelled'
  | 'failed';

export interface LocalAsrDownloadProgress {
  modelId: string;
  file: string;
  fileIndex: number;
  fileCount: number;
  bytesDownloaded: number;
  bytesTotal: number;
  phase: LocalAsrDownloadPhase;
  error: string | null;
}

export interface FoundryLocalAsrStatus {
  providerId: string;
  available: boolean;
  runtimeReady: boolean;
  runtimeSource: FoundryRuntimeSource;
  activeModel: string;
  loadedModelId: string | null;
  endpoint: string | null;
  error: string | null;
}

export type FoundryLocalAsrModelAlias = 'whisper-small' | 'whisper-base' | 'whisper-tiny';
export type FoundryLocalAsrLanguageHint = '' | 'zh' | 'en';
export type FoundryRuntimeSource = 'auto' | 'nuget' | 'ort-nightly';

export interface FoundryLocalAsrCatalogModel {
  alias: FoundryLocalAsrModelAlias;
  displayName: string;
  cached: boolean;
  fileSizeMb: number | null;
}

export type FoundryPreparePhase =
  | 'runtime'
  | 'model'
  | 'load'
  | 'finished'
  | 'failed';

export interface FoundryPrepareProgress {
  phase: FoundryPreparePhase;
  modelAlias: string;
  label: string;
  percent: number | null;
  error: string | null;
}

export interface FoundryLocalAsrModelOption {
  alias: FoundryLocalAsrModelAlias;
  labelKey: string;
  descKey: string;
}

export const FOUNDRY_LOCAL_ASR_MODELS: FoundryLocalAsrModelOption[] = [
  {
    alias: 'whisper-small',
    labelKey: 'localAsr.foundryModelSmall',
    descKey: 'localAsr.foundryModelSmallDesc',
  },
  {
    alias: 'whisper-base',
    labelKey: 'localAsr.foundryModelBase',
    descKey: 'localAsr.foundryModelBaseDesc',
  },
  {
    alias: 'whisper-tiny',
    labelKey: 'localAsr.foundryModelTiny',
    descKey: 'localAsr.foundryModelTinyDesc',
  },
];

const MOCK_FOUNDRY_CATALOG: FoundryLocalAsrCatalogModel[] = [
  {
    alias: 'whisper-small',
    displayName: 'Whisper Small',
    cached: false,
    fileSizeMb: 967,
  },
  {
    alias: 'whisper-base',
    displayName: 'Whisper Base',
    cached: true,
    fileSizeMb: 291,
  },
  {
    alias: 'whisper-tiny',
    displayName: 'Whisper Tiny',
    cached: false,
    fileSizeMb: 151,
  },
];

const MOCK_SETTINGS: LocalAsrSettings = {
  providerId: 'local-qwen3',
  activeModel: 'qwen3-asr-0.6b',
  mirror: 'huggingface',
  engineAvailable: false,
};

const MOCK_MODELS: LocalAsrModelStatus[] = [
  {
    id: 'qwen3-asr-0.6b',
    hfRepo: 'Qwen/Qwen3-ASR-0.6B',
    downloadedBytes: 0,
    isDownloaded: false,
  },
  {
    id: 'qwen3-asr-1.7b',
    hfRepo: 'Qwen/Qwen3-ASR-1.7B',
    downloadedBytes: 0,
    isDownloaded: false,
  },
];

export function getLocalAsrSettings(): Promise<LocalAsrSettings> {
  return invokeOrMock('local_asr_get_settings', undefined, () => MOCK_SETTINGS);
}

export function setLocalAsrActiveModel(modelId: string): Promise<void> {
  return invokeOrMock('local_asr_set_active_model', { modelId }, () => undefined);
}

export function setLocalAsrMirror(mirror: string): Promise<void> {
  return invokeOrMock('local_asr_set_mirror', { mirror }, () => undefined);
}

export function listLocalAsrModels(): Promise<LocalAsrModelStatus[]> {
  return invokeOrMock('local_asr_list_models', undefined, () => MOCK_MODELS);
}

export function fetchLocalAsrRemoteInfo(
  modelId: string,
  mirror?: string,
): Promise<LocalAsrRemoteInfo> {
  return invokeOrMock(
    'local_asr_fetch_remote_info',
    { modelId, mirror },
    () => ({
      modelId,
      mirror: mirror ?? 'huggingface',
      files: [],
      totalBytes: 0,
    }),
  );
}

export function downloadLocalAsrModel(
  modelId: string,
  mirror?: string,
): Promise<void> {
  return invokeOrMock('local_asr_download_model', { modelId, mirror }, () => undefined);
}

export function cancelLocalAsrDownload(modelId: string): Promise<void> {
  return invokeOrMock('local_asr_cancel_download', { modelId }, () => undefined);
}

export function deleteLocalAsrModel(modelId: string): Promise<void> {
  return invokeOrMock('local_asr_delete_model', { modelId }, () => undefined);
}

export interface LocalAsrTestResult {
  backend: string;
  modelId: string;
  expectedText: string;
  transcribedText: string;
  audioMs: number;
  loadMs: number;
  transcribeMs: number;
}

export function testLocalAsrModel(modelId: string): Promise<LocalAsrTestResult> {
  return invokeOrMock(
    'local_asr_test_model',
    { modelId },
    () => ({
      backend: 'mock',
      modelId,
      expectedText: 'Hello. This is a test of the Voxtrail speech-to-text system.',
      transcribedText: '(浏览器 dev mock，实际推理需要在 Tauri 应用内)',
      audioMs: 3000,
      loadMs: 0,
      transcribeMs: 0,
    }),
  );
}

export interface LocalAsrEngineStatus {
  loaded: boolean;
  modelId: string | null;
  keepLoadedSecs: number;
}

export function getLocalAsrEngineStatus(): Promise<LocalAsrEngineStatus> {
  return invokeOrMock('local_asr_engine_status', undefined, () => ({
    loaded: false,
    modelId: null,
    keepLoadedSecs: 300,
  }));
}

export function releaseLocalAsrEngine(): Promise<void> {
  return invokeOrMock('local_asr_release_engine', undefined, () => undefined);
}

export function preloadLocalAsr(): Promise<void> {
  return invokeOrMock('local_asr_preload', undefined, () => undefined);
}

export function setLocalAsrKeepLoadedSecs(seconds: number): Promise<void> {
  return invokeOrMock('local_asr_set_keep_loaded_secs', { seconds }, () => undefined);
}

export function getFoundryLocalAsrStatus(): Promise<FoundryLocalAsrStatus> {
  return invokeOrMock('foundry_local_asr_status', undefined, () => ({
    providerId: 'foundry-local-whisper',
    available: true,
    runtimeReady: false,
    runtimeSource: 'auto',
    activeModel: 'whisper-small',
    loadedModelId: null,
    endpoint: null,
    error: null,
  }));
}

export function getFoundryLocalAsrCatalog(): Promise<FoundryLocalAsrCatalogModel[]> {
  return invokeOrMock('foundry_local_asr_catalog', undefined, () => MOCK_FOUNDRY_CATALOG);
}

export function setFoundryLocalAsrModel(modelAlias: string): Promise<void> {
  return invokeOrMock('foundry_local_asr_set_model', { modelAlias }, () => undefined);
}

export function setFoundryLocalAsrLanguageHint(languageHint: string): Promise<void> {
  return invokeOrMock(
    'foundry_local_asr_set_language_hint',
    { languageHint },
    () => undefined,
  );
}

export function setFoundryLocalRuntimeSource(source: string): Promise<void> {
  return invokeOrMock(
    'foundry_local_asr_set_runtime_source',
    { source },
    () => undefined,
  );
}

export function prepareFoundryLocalAsr(modelAlias: string): Promise<string> {
  return invokeOrMock('foundry_local_asr_prepare', { modelAlias }, () => `mock-${modelAlias}`);
}

export function cancelFoundryLocalAsrPrepare(): Promise<void> {
  return invokeOrMock('foundry_local_asr_cancel_prepare', undefined, () => undefined);
}

export function releaseFoundryLocalAsr(): Promise<void> {
  return invokeOrMock('foundry_local_asr_release', undefined, () => undefined);
}
