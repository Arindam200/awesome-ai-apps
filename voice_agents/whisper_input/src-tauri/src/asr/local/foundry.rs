use serde::Serialize;

pub const PROVIDER_ID: &str = "foundry-local-whisper";
pub const DEFAULT_MODEL_ALIAS: &str = "whisper-small";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
#[allow(dead_code)]
pub struct FoundryWhisperModel {
    pub alias: &'static str,
    pub display_name: &'static str,
    pub quality_tier: &'static str,
}

#[allow(dead_code)]
pub const MODELS: &[FoundryWhisperModel] = &[
    FoundryWhisperModel {
        alias: "whisper-small",
        display_name: "Whisper Small",
        quality_tier: "balanced",
    },
    FoundryWhisperModel {
        alias: "whisper-base",
        display_name: "Whisper Base",
        quality_tier: "low-resource",
    },
    FoundryWhisperModel {
        alias: "whisper-tiny",
        display_name: "Whisper Tiny",
        quality_tier: "smoke-test",
    },
];

#[allow(dead_code)]
pub fn is_foundry_local_whisper(id: &str) -> bool {
    id == PROVIDER_ID
}

#[allow(dead_code)]
pub fn model_alias_is_known(alias: &str) -> bool {
    MODELS.iter().any(|model| model.alias == alias)
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
#[allow(dead_code)]
pub struct FoundryCatalogModel {
    pub alias: String,
    pub display_name: String,
    pub cached: bool,
    pub file_size_mb: Option<u64>,
}

impl FoundryCatalogModel {
    #[allow(dead_code)]
    pub fn from_static(model: &FoundryWhisperModel) -> Self {
        Self {
            alias: model.alias.to_string(),
            display_name: model.display_name.to_string(),
            cached: false,
            file_size_mb: None,
        }
    }
}

#[allow(dead_code)]
pub fn static_catalog_models() -> Vec<FoundryCatalogModel> {
    MODELS
        .iter()
        .map(FoundryCatalogModel::from_static)
        .collect()
}

#[allow(dead_code)]
pub fn default_language_hint() -> Option<String> {
    None
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
#[allow(dead_code)]
pub enum FoundryPreparePhase {
    Runtime,
    Model,
    Load,
    Finished,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
#[allow(dead_code)]
pub struct FoundryPrepareProgressPayload {
    pub phase: FoundryPreparePhase,
    pub model_alias: String,
    pub label: String,
    pub percent: Option<f64>,
    pub error: Option<String>,
}

impl FoundryPrepareProgressPayload {
    #[allow(dead_code)]
    pub fn new(
        phase: FoundryPreparePhase,
        model_alias: impl Into<String>,
        label: impl Into<String>,
        percent: Option<f64>,
        error: Option<String>,
    ) -> Self {
        Self {
            phase,
            model_alias: model_alias.into(),
            label: label.into(),
            percent: percent.map(|value| value.clamp(0.0, 100.0)),
            error,
        }
    }

    #[allow(dead_code)]
    pub fn runtime(model_alias: impl Into<String>, label: impl Into<String>, percent: f64) -> Self {
        Self::new(
            FoundryPreparePhase::Runtime,
            model_alias,
            label,
            Some(percent),
            None,
        )
    }

    #[allow(dead_code)]
    pub fn model(model_alias: impl Into<String>, label: impl Into<String>, percent: f64) -> Self {
        Self::new(
            FoundryPreparePhase::Model,
            model_alias,
            label,
            Some(percent),
            None,
        )
    }

    #[allow(dead_code)]
    pub fn load(model_alias: impl Into<String>, label: impl Into<String>, percent: f64) -> Self {
        Self::new(
            FoundryPreparePhase::Load,
            model_alias,
            label,
            Some(percent),
            None,
        )
    }

    #[allow(dead_code)]
    pub fn finished(model_alias: impl Into<String>, label: impl Into<String>) -> Self {
        Self::new(
            FoundryPreparePhase::Finished,
            model_alias,
            label,
            Some(100.0),
            None,
        )
    }

    #[allow(dead_code)]
    pub fn failed(
        model_alias: impl Into<String>,
        label: impl Into<String>,
        error: impl Into<String>,
    ) -> Self {
        Self::new(
            FoundryPreparePhase::Failed,
            model_alias,
            label,
            None,
            Some(error.into()),
        )
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
#[allow(dead_code)]
pub struct FoundryRuntimeStatus {
    pub provider_id: String,
    pub available: bool,
    pub runtime_ready: bool,
    pub runtime_source: String,
    pub active_model: String,
    pub loaded_model_id: Option<String>,
    pub endpoint: Option<String>,
    pub error: Option<String>,
}

impl FoundryRuntimeStatus {
    #[allow(dead_code)]
    pub fn unavailable(active_model: String, error: impl Into<String>) -> Self {
        Self {
            provider_id: PROVIDER_ID.into(),
            available: false,
            runtime_ready: false,
            runtime_source: "auto".into(),
            active_model,
            loaded_model_id: None,
            endpoint: None,
            error: Some(error.into()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn provider_id_is_stable() {
        assert!(is_foundry_local_whisper("foundry-local-whisper"));
        assert!(!is_foundry_local_whisper("local-qwen3"));
    }

    #[test]
    fn default_model_is_registered() {
        assert!(model_alias_is_known(DEFAULT_MODEL_ALIAS));
    }

    #[test]
    fn unavailable_runtime_status_uses_native_audio_shape() {
        let status = FoundryRuntimeStatus::unavailable("whisper-base".to_string(), "not ready");

        assert_eq!(status.provider_id, PROVIDER_ID);
        assert!(!status.available);
        assert!(!status.runtime_ready);
        assert_eq!(status.runtime_source, "auto");
        assert_eq!(status.active_model, "whisper-base");
        assert_eq!(status.loaded_model_id, None);
        assert_eq!(status.endpoint, None);
        assert_eq!(status.error.as_deref(), Some("not ready"));
    }

    #[test]
    fn static_foundry_catalog_preserves_ui_order() {
        let catalog = static_catalog_models();

        assert_eq!(
            catalog
                .iter()
                .map(|model| model.alias.as_str())
                .collect::<Vec<_>>(),
            vec!["whisper-small", "whisper-base", "whisper-tiny"]
        );
        assert!(catalog.iter().all(|model| !model.cached));
    }

    #[test]
    fn foundry_prepare_progress_payload_uses_expected_event_shape() {
        let payload = FoundryPrepareProgressPayload::new(
            FoundryPreparePhase::Model,
            "whisper-small",
            "download model",
            Some(42.4),
            None,
        );
        let value = serde_json::to_value(payload).unwrap();

        assert_eq!(value["phase"], "model");
        assert_eq!(value["modelAlias"], "whisper-small");
        assert_eq!(value["label"], "download model");
        assert_eq!(value["percent"], 42.4);
        assert_eq!(value["error"], serde_json::Value::Null);
    }
}
