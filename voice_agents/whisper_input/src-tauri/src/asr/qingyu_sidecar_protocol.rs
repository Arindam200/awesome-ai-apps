use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SidecarRequest {
    pub id: String,
    pub method: SidecarMethod,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    tag = "type",
    rename_all = "camelCase",
    rename_all_fields = "camelCase"
)]
pub enum SidecarMethod {
    Health { model_dir: String, vad_path: String },
    Prepare { model_dir: String, vad_path: String },
    Transcribe { model_dir: String, wav_path: String },
    Shutdown,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SidecarResponse {
    pub id: String,
    pub ok: bool,
    pub text: Option<String>,
    pub error: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::{SidecarMethod, SidecarRequest, SidecarResponse};

    #[test]
    fn request_method_uses_internal_camel_case_tagged_shape() {
        let request = SidecarRequest {
            id: "req-1".into(),
            method: SidecarMethod::Health {
                model_dir: "C:\\models\\qingyu".into(),
                vad_path: "C:\\models\\silero_vad.onnx".into(),
            },
        };

        let value = serde_json::to_value(request).unwrap();

        assert_eq!(
            value,
            serde_json::json!({
                "id": "req-1",
                "method": {
                    "type": "health",
                    "modelDir": "C:\\models\\qingyu",
                    "vadPath": "C:\\models\\silero_vad.onnx"
                }
            })
        );
    }

    #[test]
    fn response_fields_use_camel_case_and_nullable_text_error() {
        let response = SidecarResponse {
            id: "req-2".into(),
            ok: false,
            text: None,
            error: Some("model dir missing".into()),
        };

        let value = serde_json::to_value(response).unwrap();

        assert_eq!(
            value,
            serde_json::json!({
                "id": "req-2",
                "ok": false,
                "text": null,
                "error": "model dir missing"
            })
        );
    }

    #[test]
    fn transcribe_request_includes_model_dir_and_wav_path() {
        let request = SidecarRequest {
            id: "req-3".into(),
            method: SidecarMethod::Transcribe {
                model_dir: "C:\\models\\qingyu".into(),
                wav_path: "C:\\audio\\sample.wav".into(),
            },
        };

        let value = serde_json::to_value(request).unwrap();

        assert_eq!(
            value,
            serde_json::json!({
                "id": "req-3",
                "method": {
                    "type": "transcribe",
                    "modelDir": "C:\\models\\qingyu",
                    "wavPath": "C:\\audio\\sample.wav"
                }
            })
        );
    }
}
