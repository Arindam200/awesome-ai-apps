use serde::{Deserialize, Serialize};

pub const MODEL_ID: &str = "sherpa-onnx-fire-red-asr2-ctc-zh_en-int8-2026-02-25";
pub const MODEL_DISPLAY_NAME: &str = "FireRedASR2 CTC zh_en int8";
pub const VAD_FILE_NAME: &str = "silero_vad.onnx";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelManifest {
    pub model_id: String,
    pub version: String,
    pub files: Vec<ModelManifestFile>,
    pub sources: Vec<ModelDownloadSource>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelManifestFile {
    pub path: String,
    pub size: u64,
    pub sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelDownloadSource {
    pub id: String,
    pub label: String,
    pub base_url: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum QingyuAsrModelState {
    Installed,
    Missing,
    Downloading,
    Corrupted,
    NeedsRepair,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum QingyuAsrModelSource {
    Production,
    Development,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct QingyuAsrStatus {
    pub provider_id: String,
    pub display_name: String,
    pub model_id: String,
    pub model_state: QingyuAsrModelState,
    pub model_source: QingyuAsrModelSource,
    pub model_dir: Option<String>,
    pub model_size_bytes: Option<u64>,
    pub sidecar_running: bool,
    pub vad_available: bool,
    pub error: Option<String>,
}

impl QingyuAsrStatus {
    pub fn missing(model_dir: Option<String>) -> Self {
        Self {
            provider_id: crate::product::LOCAL_ASR_PROVIDER_ID.into(),
            display_name: MODEL_DISPLAY_NAME.into(),
            model_id: MODEL_ID.into(),
            model_state: QingyuAsrModelState::Missing,
            model_source: QingyuAsrModelSource::Production,
            model_dir,
            model_size_bytes: None,
            sidecar_running: false,
            vad_available: false,
            error: None,
        }
    }
}
