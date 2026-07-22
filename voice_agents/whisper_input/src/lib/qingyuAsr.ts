import { invokeOrMock } from './ipc';
import { LOCAL_ASR_PROVIDER_ID } from './product';

export type QingyuAsrModelState =
  | 'installed'
  | 'missing'
  | 'downloading'
  | 'corrupted'
  | 'needsRepair';

export type QingyuAsrModelSource = 'production' | 'development';

export interface QingyuAsrStatus {
  providerId: string;
  displayName: string;
  modelId: string;
  modelState: QingyuAsrModelState;
  modelSource: QingyuAsrModelSource;
  modelDir: string | null;
  modelSizeBytes: number | null;
  sidecarRunning: boolean;
  vadAvailable: boolean;
  error: string | null;
}

export interface ModelManifestFile {
  path: string;
  size: number;
  sha256: string;
}

export interface ModelDownloadSource {
  id: string;
  label: string;
  baseUrl: string;
}

export interface ModelManifest {
  modelId: string;
  version: string;
  files: ModelManifestFile[];
  sources: ModelDownloadSource[];
}

const MODEL_ID = 'sherpa-onnx-fire-red-asr2-ctc-zh_en-int8-2026-02-25';
const MODEL_DISPLAY_NAME = 'FireRedASR2 CTC zh_en int8';

const MOCK_QINGYU_ASR_STATUS: QingyuAsrStatus = {
  providerId: LOCAL_ASR_PROVIDER_ID,
  displayName: MODEL_DISPLAY_NAME,
  modelId: MODEL_ID,
  modelState: 'installed',
  modelSource: 'production',
  modelDir: null,
  modelSizeBytes: 776000000,
  sidecarRunning: false,
  vadAvailable: true,
  error: null,
};

const MOCK_QINGYU_ASR_MANIFEST: ModelManifest = {
  modelId: MODEL_ID,
  version: '2026-02-25',
  files: [
    {
      path: `${MODEL_ID}/${MODEL_ID}/model.int8.onnx`,
      size: 775861420,
      sha256: 'ca3dbabd82170110cc0b343c2890866d449984bc9cd92b9a18371ff80a81bb99',
    },
    {
      path: `${MODEL_ID}/${MODEL_ID}/tokens.txt`,
      size: 79172,
      sha256: '1bc613de2112d257e61a349c3e72d1b1a9cf19c33d3ca954197ad2171e5ea07b',
    },
    {
      path: 'silero_vad.onnx',
      size: 643854,
      sha256: '9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6',
    },
  ],
  sources: [
    {
      id: 'github-release',
      label: '官方 GitHub 源',
      baseUrl: 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models',
    },
  ],
};

export function getQingyuAsrStatus(): Promise<QingyuAsrStatus> {
  return invokeOrMock('qingyu_asr_status', undefined, () => MOCK_QINGYU_ASR_STATUS);
}

export function getQingyuAsrManifest(): Promise<ModelManifest> {
  return invokeOrMock('qingyu_asr_manifest', undefined, () => MOCK_QINGYU_ASR_MANIFEST);
}

export function downloadQingyuAsr(
  sourceId?: string,
  customBaseUrl?: string,
): Promise<QingyuAsrStatus> {
  return invokeOrMock(
    'qingyu_asr_download',
    { sourceId, customBaseUrl },
    () => MOCK_QINGYU_ASR_STATUS,
  );
}

export function repairQingyuAsr(customBaseUrl?: string): Promise<QingyuAsrStatus> {
  return invokeOrMock(
    'qingyu_asr_repair',
    { customBaseUrl },
    () => MOCK_QINGYU_ASR_STATUS,
  );
}
