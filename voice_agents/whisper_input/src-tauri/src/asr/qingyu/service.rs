use std::path::Path;
use std::sync::Arc;

use anyhow::{anyhow, bail, Context, Result};
use parking_lot::Mutex;
use tauri::AppHandle;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use uuid::Uuid;

use super::paths::{preferred_model_location, vad_path_from_model_dir, PreferredModelLocation};
use super::types::{QingyuAsrModelState, QingyuAsrStatus, MODEL_DISPLAY_NAME, MODEL_ID};
use crate::qingyu_sidecar_protocol::{SidecarMethod, SidecarRequest, SidecarResponse};

const QINGYU_LOCAL_ASR_TIMEOUT_SECS: u64 = 15;

#[derive(Default)]
pub struct QingyuLocalAsrService {
    app: Mutex<Option<AppHandle>>,
    sidecar_running: Mutex<bool>,
}

impl QingyuLocalAsrService {
    pub fn bind_app(&self, app: AppHandle) {
        *self.app.lock() = Some(app);
    }

    pub fn status(&self) -> QingyuAsrStatus {
        status_from_model_location_result(self, preferred_model_location())
    }

    pub async fn restart_sidecar(&self) -> anyhow::Result<()> {
        *self.sidecar_running.lock() = true;
        Ok(())
    }

    pub async fn transcribe_wav(
        &self,
        wav_path: &Path,
    ) -> anyhow::Result<crate::asr::RawTranscript> {
        let model_dir = preferred_model_location()?.model_dir;
        let vad_path = vad_path_from_model_dir(&model_dir)
            .context("failed to resolve Qingyu VAD path from model directory")?;
        validate_transcribe_inputs(&model_dir, &vad_path, wav_path)?;

        let duration_ms = estimate_wav_duration_ms(wav_path)?;
        let timeout_duration = std::time::Duration::from_secs(QINGYU_LOCAL_ASR_TIMEOUT_SECS);
        let text = match tokio::time::timeout(
            timeout_duration,
            self.transcribe_wav_with_sidecar(&model_dir, &vad_path, wav_path),
        )
        .await
        {
            Ok(result) => result?,
            Err(_) => bail!(
                "Qingyu local ASR transcribe timed out after {} seconds",
                QINGYU_LOCAL_ASR_TIMEOUT_SECS
            ),
        };

        Ok(crate::asr::RawTranscript { text, duration_ms })
    }

    async fn transcribe_wav_with_sidecar(
        &self,
        model_dir: &Path,
        vad_path: &Path,
        wav_path: &Path,
    ) -> anyhow::Result<String> {
        let app = self
            .app
            .lock()
            .clone()
            .context("Qingyu local ASR service is not bound to a Tauri AppHandle")?;
        let sidecar_command = app
            .shell()
            .sidecar("qingyu-asr-sidecar")
            .context("failed to create Qingyu ASR sidecar command")?;
        let (mut rx, child) = sidecar_command
            .spawn()
            .context("failed to spawn Qingyu ASR sidecar")?;
        let mut sidecar = SidecarProcessGuard::new(&self.sidecar_running, child);

        let result = async {
            let prepare_id = format!("prepare-{}", Uuid::new_v4());
            let prepare = SidecarRequest {
                id: prepare_id.clone(),
                method: SidecarMethod::Prepare {
                    model_dir: model_dir.to_string_lossy().into_owned(),
                    vad_path: vad_path.to_string_lossy().into_owned(),
                },
            };
            write_sidecar_request(sidecar.child_mut()?, &prepare)
                .context("failed to send Qingyu ASR prepare request")?;
            let prepare_response = read_sidecar_response(&mut rx, &prepare_id).await?;
            ensure_ok_response(prepare_response).context("Qingyu ASR prepare failed")?;

            let transcribe_id = format!("transcribe-{}", Uuid::new_v4());
            let transcribe = SidecarRequest {
                id: transcribe_id.clone(),
                method: SidecarMethod::Transcribe {
                    model_dir: model_dir.to_string_lossy().into_owned(),
                    wav_path: wav_path.to_string_lossy().into_owned(),
                },
            };
            write_sidecar_request(sidecar.child_mut()?, &transcribe)
                .context("failed to send Qingyu ASR transcribe request")?;
            let transcribe_response = read_sidecar_response(&mut rx, &transcribe_id).await?;
            let response =
                ensure_ok_response(transcribe_response).context("Qingyu ASR transcribe failed")?;
            response
                .text
                .map(|text| text.trim().to_string())
                .ok_or_else(|| anyhow!("Qingyu ASR sidecar returned no transcript text"))
        }
        .await;

        let shutdown = SidecarRequest {
            id: format!("shutdown-{}", Uuid::new_v4()),
            method: SidecarMethod::Shutdown,
        };
        let shutdown_sent = if let Ok(child) = sidecar.child_mut() {
            write_sidecar_request(child, &shutdown).is_ok()
        } else {
            false
        };
        if shutdown_sent {
            sidecar.disarm_after_shutdown();
        }

        result
    }

    pub fn mark_sidecar_running_for_tests(&self, running: bool) {
        *self.sidecar_running.lock() = running;
    }
}

pub type SharedQingyuLocalAsrService = Arc<QingyuLocalAsrService>;

fn status_from_model_location_result(
    service: &QingyuLocalAsrService,
    location: Result<PreferredModelLocation>,
) -> QingyuAsrStatus {
    let sidecar_running = *service.sidecar_running.lock();
    let location = match location {
        Ok(location) => location,
        Err(error) => {
            let mut status = QingyuAsrStatus::missing(None);
            status.sidecar_running = sidecar_running;
            status.error = Some(error.to_string());
            return status;
        }
    };
    let model_dir = location.model_dir;

    let model_state = model_state_for_dir(&model_dir);
    let vad_available = vad_path_from_model_dir(&model_dir)
        .map(|vad_path| vad_path.exists())
        .unwrap_or(false);

    QingyuAsrStatus {
        provider_id: crate::product::LOCAL_ASR_PROVIDER_ID.into(),
        display_name: MODEL_DISPLAY_NAME.into(),
        model_id: MODEL_ID.into(),
        model_state,
        model_source: location.source,
        model_dir: Some(model_dir.to_string_lossy().into_owned()),
        model_size_bytes: None,
        sidecar_running,
        vad_available,
        error: None,
    }
}

fn model_state_for_dir(dir: &Path) -> QingyuAsrModelState {
    if dir.join("model.int8.onnx").exists() && dir.join("tokens.txt").exists() {
        return QingyuAsrModelState::Installed;
    }

    if dir.exists() {
        QingyuAsrModelState::NeedsRepair
    } else {
        QingyuAsrModelState::Missing
    }
}

struct SidecarProcessGuard<'a> {
    running: &'a Mutex<bool>,
    child: Option<CommandChild>,
}

impl<'a> SidecarProcessGuard<'a> {
    fn new(running: &'a Mutex<bool>, child: CommandChild) -> Self {
        *running.lock() = true;
        Self {
            running,
            child: Some(child),
        }
    }

    fn child_mut(&mut self) -> Result<&mut CommandChild> {
        self.child
            .as_mut()
            .ok_or_else(|| anyhow!("Qingyu ASR sidecar child is no longer available"))
    }

    fn disarm_after_shutdown(&mut self) {
        self.child.take();
        *self.running.lock() = false;
    }
}

impl Drop for SidecarProcessGuard<'_> {
    fn drop(&mut self) {
        *self.running.lock() = false;
        if let Some(child) = self.child.take() {
            if let Err(error) = child.kill() {
                log::warn!("[qingyu-asr] failed to kill sidecar during cleanup: {error}");
            }
        }
    }
}

fn validate_transcribe_inputs(model_dir: &Path, vad_path: &Path, wav_path: &Path) -> Result<()> {
    if !model_dir.is_dir() {
        bail!(
            "Qingyu ASR model directory is missing: {}",
            model_dir.display()
        );
    }
    for file_name in ["model.int8.onnx", "tokens.txt"] {
        let path = model_dir.join(file_name);
        if !path.is_file() {
            bail!("Qingyu ASR model asset is missing: {}", path.display());
        }
    }
    if !vad_path.is_file() {
        bail!("Qingyu ASR VAD model is missing: {}", vad_path.display());
    }
    if !wav_path.is_file() {
        bail!("Qingyu ASR WAV input is missing: {}", wav_path.display());
    }
    Ok(())
}

fn estimate_wav_duration_ms(wav_path: &Path) -> Result<u64> {
    let len = std::fs::metadata(wav_path)
        .with_context(|| format!("failed to stat WAV file {}", wav_path.display()))?
        .len();
    Ok(duration_ms_from_wav_file_len(len))
}

fn duration_ms_from_wav_file_len(len: u64) -> u64 {
    let data_len = len.saturating_sub(44);
    let samples = data_len / 2;
    samples.saturating_mul(1000) / 16_000
}

fn write_sidecar_request(
    child: &mut tauri_plugin_shell::process::CommandChild,
    request: &SidecarRequest,
) -> Result<()> {
    let line = serde_json::to_string(request)?;
    child.write(format!("{line}\n").as_bytes())?;
    Ok(())
}

async fn read_sidecar_response(
    rx: &mut tauri::async_runtime::Receiver<CommandEvent>,
    expected_id: &str,
) -> Result<SidecarResponse> {
    while let Some(event) = rx.recv().await {
        match event {
            CommandEvent::Stdout(line_bytes) => {
                let line = String::from_utf8_lossy(&line_bytes);
                for candidate in line.lines().map(str::trim).filter(|line| !line.is_empty()) {
                    let response: SidecarResponse =
                        serde_json::from_str(candidate).with_context(|| {
                            format!("failed to parse Qingyu sidecar response: {candidate}")
                        })?;
                    if response.id == expected_id {
                        return Ok(response);
                    }
                    log::debug!(
                        "[qingyu-asr] ignoring sidecar response for unexpected id {}",
                        response.id
                    );
                }
            }
            CommandEvent::Stderr(line_bytes) => {
                let line = String::from_utf8_lossy(&line_bytes);
                if !line.trim().is_empty() {
                    log::warn!("[qingyu-asr] sidecar stderr: {}", line.trim());
                }
            }
            CommandEvent::Error(error) => {
                bail!("Qingyu ASR sidecar process error: {error}");
            }
            CommandEvent::Terminated(payload) => {
                bail!(
                    "Qingyu ASR sidecar terminated before response {expected_id}: {:?}",
                    payload
                );
            }
            _ => {}
        }
    }

    bail!("Qingyu ASR sidecar exited before response {expected_id}");
}

fn ensure_ok_response(response: SidecarResponse) -> Result<SidecarResponse> {
    if response.ok {
        Ok(response)
    } else {
        Err(anyhow!(
            "{}",
            response
                .error
                .unwrap_or_else(|| "Qingyu ASR sidecar returned an unknown error".into())
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::{
        duration_ms_from_wav_file_len, model_state_for_dir, status_from_model_location_result,
        validate_transcribe_inputs,
    };
    use crate::asr::qingyu::paths::{model_dir_from_root, PreferredModelLocation};
    use crate::asr::qingyu::types::VAD_FILE_NAME;
    use crate::asr::qingyu::{QingyuAsrModelSource, QingyuAsrModelState};

    #[test]
    fn missing_model_dir_reports_missing() {
        let dir = std::env::temp_dir()
            .join("qingyu-asr-missing-model-test")
            .join(std::process::id().to_string());
        let _ = std::fs::remove_dir_all(&dir);

        assert_eq!(model_state_for_dir(&dir), QingyuAsrModelState::Missing);
    }

    #[test]
    fn path_resolution_error_reports_missing_without_model_dir() {
        let service = super::QingyuLocalAsrService::default();

        let status =
            status_from_model_location_result(&service, Err(anyhow::anyhow!("APPDATA not set")));

        assert_eq!(status.model_state, QingyuAsrModelState::Missing);
        assert_eq!(status.model_dir, None);
        assert_eq!(status.error.as_deref(), Some("APPDATA not set"));
    }

    #[test]
    fn root_vad_file_reports_available() {
        let root =
            std::env::temp_dir().join(format!("qingyu-asr-vad-present-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        let model_dir = model_dir_from_root(&root);
        std::fs::create_dir_all(&model_dir).unwrap();
        std::fs::write(root.join(VAD_FILE_NAME), b"vad").unwrap();
        let service = super::QingyuLocalAsrService::default();

        let status = status_from_model_location_result(
            &service,
            Ok(PreferredModelLocation {
                model_dir,
                source: QingyuAsrModelSource::Production,
            }),
        );

        assert!(status.vad_available);
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn missing_root_vad_file_reports_unavailable() {
        let root =
            std::env::temp_dir().join(format!("qingyu-asr-vad-missing-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        let model_dir = model_dir_from_root(&root);
        std::fs::create_dir_all(&model_dir).unwrap();
        let service = super::QingyuLocalAsrService::default();

        let status = status_from_model_location_result(
            &service,
            Ok(PreferredModelLocation {
                model_dir,
                source: QingyuAsrModelSource::Production,
            }),
        );

        assert!(!status.vad_available);
        let _ = std::fs::remove_dir_all(&root);
    }

    #[tokio::test]
    async fn restart_sidecar_marks_sidecar_running() {
        let service = super::QingyuLocalAsrService::default();

        service.restart_sidecar().await.unwrap();
        let status =
            status_from_model_location_result(&service, Err(anyhow::anyhow!("APPDATA not set")));

        assert!(status.sidecar_running);
    }

    #[test]
    fn wav_duration_estimate_uses_16k_mono_i16_data_size() {
        assert_eq!(duration_ms_from_wav_file_len(44 + 32_000), 1000);
        assert_eq!(duration_ms_from_wav_file_len(44 + 16_000), 500);
        assert_eq!(duration_ms_from_wav_file_len(12), 0);
    }

    #[test]
    fn transcribe_input_validation_requires_model_vad_and_wav() {
        let root = std::env::temp_dir().join(format!("qingyu-asr-validate-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        let model_dir = root.join("model");
        let vad_path = root.join(VAD_FILE_NAME);
        let wav_path = root.join("input.wav");
        std::fs::create_dir_all(&model_dir).unwrap();
        std::fs::write(model_dir.join("model.int8.onnx"), b"model").unwrap();
        std::fs::write(model_dir.join("tokens.txt"), b"tokens").unwrap();
        std::fs::write(&vad_path, b"vad").unwrap();
        std::fs::write(&wav_path, b"wav").unwrap();

        validate_transcribe_inputs(&model_dir, &vad_path, &wav_path).unwrap();

        let _ = std::fs::remove_file(&vad_path);
        let error = validate_transcribe_inputs(&model_dir, &vad_path, &wav_path).unwrap_err();
        assert!(error.to_string().contains("VAD"), "{error}");

        let _ = std::fs::remove_dir_all(&root);
    }
}
