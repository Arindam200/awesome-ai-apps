use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::{Context, Result};
use chrono::{DateTime, Duration, Utc};
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use serde_json::Value;

const DIAGNOSTIC_CAP: usize = 200;
const DIAGNOSTIC_RETENTION_DAYS: i64 = 7;
const DIAGNOSTIC_FILE: &str = "diagnostics.jsonl";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticTrace {
    pub schema_version: u32,
    pub trace_id: String,
    pub created_at: String,
    pub app: DiagnosticApp,
    pub session: DiagnosticSession,
    pub recorder: DiagnosticRecorderFacts,
    pub asr: DiagnosticAsr,
    pub llm: DiagnosticLlm,
    pub insertion: DiagnosticInsertion,
    #[serde(default)]
    pub flags: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticApp {
    pub version: String,
    pub platform: String,
    pub arch: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticSession {
    pub mode: Option<String>,
    pub hotkey_mode: Option<String>,
    pub front_app: Option<String>,
    pub pressed_at: Option<String>,
    pub released_at: Option<String>,
    pub cancelled: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticRecorderFacts {
    pub device_name: Option<String>,
    pub error: Option<String>,
    pub input_sample_rate: Option<u32>,
    pub output_sample_rate: Option<u32>,
    pub pcm_bytes: Option<u64>,
    pub estimated_duration_ms: Option<u64>,
    pub last_rms: Option<f64>,
    pub peak_rms: Option<f64>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticAsr {
    pub provider: Option<String>,
    pub error: Option<String>,
    pub connected_at_ms: Option<u64>,
    pub first_server_message_at_ms: Option<u64>,
    pub last_server_message_at_ms: Option<u64>,
    pub server_audio_duration_ms: Option<u64>,
    pub socket_closed_at_ms: Option<u64>,
    pub socket_error: Option<String>,
    pub server_log_id: Option<String>,
    pub raw_text: Option<String>,
    pub raw_chars: Option<u32>,
    pub final_missing_partial_used: bool,
    pub frames_sent: Option<u64>,
    pub bytes_sent: Option<u64>,
    pub pending_sends: Option<u64>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticLlm {
    pub provider: Option<String>,
    pub mode: Option<String>,
    pub short_input_bypass: bool,
    pub streaming_insert_eligible: bool,
    pub started_at_ms: Option<u64>,
    pub finished_at_ms: Option<u64>,
    pub error: Option<String>,
    pub final_text: Option<String>,
    pub final_chars: Option<u32>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticInsertion {
    pub status: Option<String>,
    pub method: Option<String>,
    pub focus_restored: Option<bool>,
}

impl DiagnosticTrace {
    pub fn compute_flags(&mut self) {
        let mut flags = Vec::new();

        if let (Some(socket_ms), Some(local_ms)) = (
            self.asr.socket_closed_at_ms,
            self.recorder.estimated_duration_ms,
        ) {
            if self.asr.socket_error.is_some() && socket_ms.saturating_add(500) < local_ms {
                flags.push("asr_connection_reset_before_hotkey_release".to_string());
            }
            if local_ms > socket_ms.saturating_add(500) {
                flags.push("local_audio_continued_after_asr_disconnect".to_string());
            }
        }
        if let (Some(server_ms), Some(local_ms)) = (
            self.asr.server_audio_duration_ms,
            self.recorder.estimated_duration_ms,
        ) {
            if server_ms.saturating_add(1000) < local_ms {
                flags.push("server_audio_duration_shorter_than_local_recording".to_string());
            }
        }
        if self.asr.final_missing_partial_used {
            flags.push("asr_final_missing_partial_used".to_string());
        }
        if let (Some(raw_chars), Some(final_chars)) = (self.asr.raw_chars, self.llm.final_chars) {
            if raw_chars >= 30 && final_chars.saturating_mul(100) < raw_chars.saturating_mul(60) {
                flags.push("llm_output_much_shorter_than_raw".to_string());
            }
        }
        if matches!(
            self.insertion.status.as_deref(),
            Some("PasteSent" | "pasteSent")
        ) {
            flags.push("insert_unverified_paste_sent".to_string());
        }
        if self.insertion.focus_restored == Some(false) {
            flags.push("focus_not_ready_for_paste".to_string());
        }

        self.flags = flags;
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticBundle {
    diagnostics: Vec<DiagnosticTrace>,
    history: Vec<crate::types::DictationSession>,
    log_excerpt: String,
    settings_summary: Value,
    environment: Value,
}

impl DiagnosticBundle {
    pub fn new(
        diagnostics: Vec<DiagnosticTrace>,
        history: Vec<crate::types::DictationSession>,
        log_excerpt: String,
        settings_summary: Value,
    ) -> Self {
        Self {
            diagnostics: diagnostics
                .into_iter()
                .map(redact_diagnostic_trace)
                .collect(),
            history: history.into_iter().map(redact_history_session).collect(),
            log_excerpt: redact_secret_text(&log_excerpt),
            settings_summary: redact_secrets(settings_summary),
            environment: serde_json::json!({
                "version": env!("CARGO_PKG_VERSION"),
                "os": std::env::consts::OS,
                "arch": std::env::consts::ARCH,
            }),
        }
    }
}

fn redact_diagnostic_trace(mut trace: DiagnosticTrace) -> DiagnosticTrace {
    redact_optional_secret_text(&mut trace.session.front_app);
    redact_optional_secret_text(&mut trace.recorder.device_name);
    redact_optional_secret_text(&mut trace.recorder.error);
    redact_optional_secret_text(&mut trace.asr.error);
    redact_optional_secret_text(&mut trace.asr.socket_error);
    redact_optional_secret_text(&mut trace.asr.server_log_id);
    redact_optional_secret_text(&mut trace.asr.raw_text);
    redact_optional_secret_text(&mut trace.llm.error);
    redact_optional_secret_text(&mut trace.llm.final_text);
    trace
}

fn redact_history_session(
    mut session: crate::types::DictationSession,
) -> crate::types::DictationSession {
    session.raw_transcript = redact_secret_text(&session.raw_transcript);
    session.final_text = redact_secret_text(&session.final_text);
    if let Some(error_code) = session.error_code.as_mut() {
        *error_code = redact_secret_text(error_code);
    }
    session
}

fn redact_optional_secret_text(value: &mut Option<String>) {
    if let Some(text) = value.as_mut() {
        *text = redact_secret_text(text);
    }
}

pub fn write_diagnostic_bundle_zip(bundle: &DiagnosticBundle, target_path: &Path) -> Result<()> {
    if let Some(parent) = target_path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).context("create diagnostic bundle parent failed")?;
        }
    }

    let file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(target_path)
        .context("create diagnostic bundle zip failed")?;
    let mut zip = zip::ZipWriter::new(file);
    let options = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated);

    write_zip_json_entry(&mut zip, options, "bundle.json", bundle)?;
    write_zip_json_entry(&mut zip, options, "diagnostics.json", &bundle.diagnostics)?;
    write_zip_json_entry(&mut zip, options, "history.json", &bundle.history)?;
    write_zip_json_entry(
        &mut zip,
        options,
        "settings-summary.json",
        &bundle.settings_summary,
    )?;
    zip.start_file("log-tail.txt", options)
        .context("start log tail zip entry failed")?;
    zip.write_all(bundle.log_excerpt.as_bytes())
        .context("write log tail zip entry failed")?;
    zip.finish()
        .context("finish diagnostic bundle zip failed")?;
    Ok(())
}

fn write_zip_json_entry<T: Serialize>(
    zip: &mut zip::ZipWriter<fs::File>,
    options: zip::write::SimpleFileOptions,
    name: &str,
    value: &T,
) -> Result<()> {
    zip.start_file(name, options)
        .with_context(|| format!("start {name} zip entry failed"))?;
    serde_json::to_writer_pretty(zip, value)
        .with_context(|| format!("write {name} zip entry failed"))
}

#[derive(Debug, Clone)]
pub struct DiagnosticStore {
    inner: Arc<DiagnosticStoreInner>,
}

#[derive(Debug)]
struct DiagnosticStoreInner {
    path: PathBuf,
    lock: Mutex<()>,
}

impl DiagnosticStore {
    pub fn new() -> Result<Self> {
        let dir = crate::persistence::app_data_dir()?;
        fs::create_dir_all(&dir).context("create diagnostics data dir failed")?;
        Ok(Self::with_path(dir.join(DIAGNOSTIC_FILE)))
    }

    pub fn with_path(path: PathBuf) -> Self {
        Self {
            inner: Arc::new(DiagnosticStoreInner {
                path,
                lock: Mutex::new(()),
            }),
        }
    }

    pub fn append(&self, trace: DiagnosticTrace) -> Result<()> {
        self.append_with_now(trace, Utc::now())
    }

    pub fn append_with_now(&self, mut trace: DiagnosticTrace, now: DateTime<Utc>) -> Result<()> {
        trace.compute_flags();
        let _guard = self.inner.lock.lock();
        let DiagnosticRecords {
            mut traces,
            malformed_lines,
        } = self.read_records_locked()?;
        traces.insert(0, trace);

        let cutoff = now - Duration::days(DIAGNOSTIC_RETENTION_DAYS);
        traces.retain(|trace| {
            DateTime::parse_from_rfc3339(&trace.created_at)
                .map(|created_at| created_at.with_timezone(&Utc) >= cutoff)
                .unwrap_or(true)
        });
        traces.truncate(DIAGNOSTIC_CAP.min(traces.len()));

        self.write_records_locked(&traces, &malformed_lines)
    }

    pub fn list_recent(&self, limit: usize) -> Result<Vec<DiagnosticTrace>> {
        let _guard = self.inner.lock.lock();
        let mut traces = self.read_records_locked()?.traces;
        traces.truncate(limit.min(traces.len()));
        Ok(traces)
    }

    fn read_records_locked(&self) -> Result<DiagnosticRecords> {
        if !self.inner.path.exists() {
            return Ok(DiagnosticRecords::default());
        }

        let file = fs::File::open(&self.inner.path).context("open diagnostics file failed")?;
        let reader = BufReader::new(file);
        let mut traces = Vec::new();
        let mut malformed_lines = Vec::new();

        for line in reader.lines() {
            let line = line.context("read diagnostics line failed")?;
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<DiagnosticTrace>(&line) {
                Ok(trace) => traces.push(trace),
                Err(err) => {
                    log::warn!("[diagnostics] preserving malformed trace line: {err}");
                    malformed_lines.push(line);
                }
            }
        }

        Ok(DiagnosticRecords {
            traces,
            malformed_lines,
        })
    }

    fn write_records_locked(
        &self,
        traces: &[DiagnosticTrace],
        malformed_lines: &[String],
    ) -> Result<()> {
        if let Some(parent) = self.inner.path.parent() {
            fs::create_dir_all(parent).context("create diagnostics parent failed")?;
        }

        let tmp = self.inner.path.with_extension("jsonl.tmp");
        {
            let mut file = fs::File::create(&tmp).context("create diagnostics temp failed")?;
            for trace in traces {
                serde_json::to_writer(&mut file, trace)
                    .context("encode diagnostic trace failed")?;
                file.write_all(b"\n")
                    .context("write diagnostic newline failed")?;
            }
            for line in malformed_lines {
                file.write_all(line.as_bytes())
                    .context("write malformed diagnostic line failed")?;
                file.write_all(b"\n")
                    .context("write malformed diagnostic newline failed")?;
            }
            file.sync_all().context("sync diagnostics temp failed")?;
        }
        fs::rename(&tmp, &self.inner.path).context("replace diagnostics file failed")
    }
}

#[derive(Debug, Default)]
struct DiagnosticRecords {
    traces: Vec<DiagnosticTrace>,
    malformed_lines: Vec<String>,
}

pub fn redact_secrets(value: Value) -> Value {
    match value {
        Value::Object(map) => Value::Object(
            map.into_iter()
                .map(|(key, value)| {
                    let lower = key.to_ascii_lowercase();
                    if lower.contains("apikey")
                        || lower.contains("api_key")
                        || lower.contains("appkey")
                        || lower.contains("app_key")
                        || lower.contains("accesskey")
                        || lower.contains("access_key")
                        || lower.contains("token")
                        || lower.contains("secret")
                        || lower.contains("authorization")
                    {
                        (key, Value::String("[REDACTED]".into()))
                    } else {
                        (key, redact_secrets(value))
                    }
                })
                .collect(),
        ),
        Value::Array(items) => Value::Array(items.into_iter().map(redact_secrets).collect()),
        other => other,
    }
}

pub fn redact_secret_text(input: &str) -> String {
    input
        .lines()
        .map(|line| {
            if line_may_contain_secret(line) {
                "[REDACTED LINE]"
            } else {
                line
            }
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn line_may_contain_secret(line: &str) -> bool {
    let lower = line.to_ascii_lowercase();
    lower.contains("apikey")
        || lower.contains("api_key")
        || lower.contains("api-key")
        || lower.contains("appkey")
        || lower.contains("app_key")
        || lower.contains("app-key")
        || lower.contains("accesskey")
        || lower.contains("access_key")
        || lower.contains("access-key")
        || lower.contains("authorization")
        || lower.contains("bearer ")
        || lower.contains(" token")
        || lower.contains("\"token\"")
        || lower.contains("token=")
        || lower.contains("secret")
        || lower.contains("sk-")
}

pub fn read_log_tail(path: &Path, max_bytes: usize) -> Result<String> {
    if !path.exists() {
        return Ok(String::new());
    }

    let bytes = fs::read(path).context("read log file failed")?;
    let start = bytes.len().saturating_sub(max_bytes);
    Ok(String::from_utf8_lossy(&bytes[start..]).to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::io::Read;
    use tempfile::tempdir;

    fn sample_trace() -> DiagnosticTrace {
        DiagnosticTrace {
            schema_version: 1,
            trace_id: "trace-1".into(),
            created_at: "2026-05-21T00:00:00Z".into(),
            app: DiagnosticApp {
                version: "1.3.4".into(),
                platform: "windows".into(),
                arch: "x86_64".into(),
            },
            session: DiagnosticSession {
                mode: Some("Light".into()),
                hotkey_mode: Some("Hold".into()),
                front_app: Some("Google Chrome".into()),
                pressed_at: Some("2026-05-21T00:00:00Z".into()),
                released_at: Some("2026-05-21T00:00:33Z".into()),
                cancelled: false,
            },
            recorder: DiagnosticRecorderFacts {
                device_name: Some("Microphone".into()),
                error: None,
                input_sample_rate: Some(48000),
                output_sample_rate: Some(16000),
                pcm_bytes: Some(1_056_000),
                estimated_duration_ms: Some(33_000),
                last_rms: Some(0.007),
                peak_rms: Some(0.058),
            },
            asr: DiagnosticAsr {
                provider: Some("doubao-streaming-asr-2".into()),
                error: None,
                connected_at_ms: Some(1850),
                first_server_message_at_ms: Some(2310),
                last_server_message_at_ms: Some(8600),
                server_audio_duration_ms: Some(8600),
                socket_closed_at_ms: Some(28595),
                socket_error: Some("WSAECONNRESET 10054".into()),
                server_log_id: Some("server-log-id".into()),
                raw_text: Some("recognized text".into()),
                raw_chars: Some(30),
                final_missing_partial_used: true,
                frames_sent: Some(140),
                bytes_sent: Some(896000),
                pending_sends: Some(0),
            },
            llm: DiagnosticLlm {
                provider: Some("gemini".into()),
                mode: Some("Light".into()),
                short_input_bypass: false,
                streaming_insert_eligible: true,
                started_at_ms: Some(29200),
                finished_at_ms: Some(32900),
                error: None,
                final_text: Some("final".into()),
                final_chars: Some(5),
            },
            insertion: DiagnosticInsertion {
                status: Some("PasteSent".into()),
                method: Some("clipboard".into()),
                focus_restored: Some(true),
            },
            flags: Vec::new(),
        }
    }

    #[test]
    fn evidence_flags_are_factual_not_root_cause_claims() {
        let mut trace = sample_trace();
        trace.compute_flags();

        assert!(trace
            .flags
            .contains(&"asr_connection_reset_before_hotkey_release".to_string()));
        assert!(trace
            .flags
            .contains(&"local_audio_continued_after_asr_disconnect".to_string()));
        assert!(trace
            .flags
            .contains(&"server_audio_duration_shorter_than_local_recording".to_string()));
        assert!(trace
            .flags
            .contains(&"asr_final_missing_partial_used".to_string()));
        assert!(trace
            .flags
            .contains(&"llm_output_much_shorter_than_raw".to_string()));
        assert!(trace
            .flags
            .contains(&"insert_unverified_paste_sent".to_string()));
        assert!(!trace.flags.iter().any(|flag| flag.contains("root_cause")));
    }

    #[test]
    fn short_raw_input_does_not_trigger_llm_shorter_flag() {
        let mut trace = sample_trace();
        trace.asr.raw_chars = Some(2);
        trace.llm.final_chars = Some(1);

        trace.compute_flags();

        assert!(!trace
            .flags
            .contains(&"llm_output_much_shorter_than_raw".to_string()));
    }

    #[test]
    fn paste_sent_flag_accepts_camel_case_status() {
        let mut trace = sample_trace();
        trace.insertion.status = Some("pasteSent".into());

        trace.compute_flags();

        assert!(trace
            .flags
            .contains(&"insert_unverified_paste_sent".to_string()));
    }

    #[test]
    fn connection_reset_after_local_recording_is_not_flagged() {
        let mut trace = sample_trace();
        trace.asr.socket_error = Some("WSAECONNRESET 10054".into());
        trace.asr.socket_closed_at_ms = Some(33_700);
        trace.recorder.estimated_duration_ms = Some(33_000);

        trace.compute_flags();

        assert!(!trace
            .flags
            .contains(&"asr_connection_reset_before_hotkey_release".to_string()));
    }

    #[test]
    fn settings_summary_redacts_secret_like_values() {
        let value = json!({
            "activeAsrProvider": "doubao-streaming-asr-2",
            "apiKey": "sk-secret",
            "appKey": "app-secret",
            "accessKey": "access-secret",
            "accessToken": "token-secret",
            "nested": { "authorization": "Bearer abc" },
            "streamingInsert": true
        });

        let redacted = redact_secrets(value);

        assert_eq!(redacted["apiKey"], "[REDACTED]");
        assert_eq!(redacted["appKey"], "[REDACTED]");
        assert_eq!(redacted["accessKey"], "[REDACTED]");
        assert_eq!(redacted["accessToken"], "[REDACTED]");
        assert_eq!(redacted["nested"]["authorization"], "[REDACTED]");
        assert_eq!(redacted["activeAsrProvider"], "doubao-streaming-asr-2");
        assert_eq!(redacted["streamingInsert"], true);
    }

    #[test]
    fn diagnostic_store_retains_latest_200_and_drops_old_records() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("diagnostics.jsonl");
        let store = DiagnosticStore::with_path(path.clone());

        for i in 0..205 {
            let mut trace = sample_trace();
            trace.trace_id = format!("trace-{i}");
            trace.created_at = "2026-05-21T00:00:00Z".into();
            store
                .append_with_now(
                    trace,
                    chrono::DateTime::parse_from_rfc3339("2026-05-21T00:00:00Z")
                        .unwrap()
                        .with_timezone(&chrono::Utc),
                )
                .unwrap();
        }

        let traces = store.list_recent(250).unwrap();
        assert_eq!(traces.len(), 200);
        assert_eq!(traces[0].trace_id, "trace-204");
        assert_eq!(traces[199].trace_id, "trace-5");
    }

    #[test]
    fn append_preserves_preexisting_malformed_jsonl_lines() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("diagnostics.jsonl");
        fs::write(&path, "{not-valid-json}\n").unwrap();
        let store = DiagnosticStore::with_path(path.clone());

        let mut trace = sample_trace();
        trace.trace_id = "trace-valid".into();
        store
            .append_with_now(
                trace,
                chrono::DateTime::parse_from_rfc3339("2026-05-21T00:00:00Z")
                    .unwrap()
                    .with_timezone(&chrono::Utc),
            )
            .unwrap();

        let contents = fs::read_to_string(&path).unwrap();
        assert!(contents.lines().any(|line| line == "{not-valid-json}"));
        let traces = store.list_recent(10).unwrap();
        assert_eq!(traces.len(), 1);
        assert_eq!(traces[0].trace_id, "trace-valid");
    }

    #[test]
    fn export_bundle_contains_expected_sections() {
        let mut trace = sample_trace();
        trace.asr.error = Some("upstream rejected api_key=secret".into());
        trace.asr.raw_text = Some("normal speech\nAuthorization: Bearer secret".into());
        let traces = vec![trace];
        let history = vec![crate::types::DictationSession {
            id: "history-1".into(),
            created_at: "2026-05-21T00:00:00Z".into(),
            raw_transcript: "raw\nsk-secret".into(),
            final_text: "final".into(),
            mode: crate::types::PolishMode::Light,
            app_bundle_id: None,
            app_name: None,
            insert_status: crate::types::InsertStatus::Inserted,
            error_code: None,
            duration_ms: Some(1000),
            dictionary_entry_count: Some(0),
            asr_provider_id: Some("doubao-streaming-asr-2".into()),
            llm_provider_id: Some("gemini".into()),
        }];
        let bundle = DiagnosticBundle::new(
            traces,
            history,
            "log tail\nX-Api-Key: secret".into(),
            serde_json::json!({ "apiKey": "secret", "activeAsrProvider": "doubao-streaming-asr-2" }),
        );

        let json = serde_json::to_value(bundle).unwrap();
        assert_eq!(json["diagnostics"].as_array().unwrap().len(), 1);
        assert_eq!(json["history"].as_array().unwrap().len(), 1);
        assert_eq!(json["logExcerpt"], "log tail\n[REDACTED LINE]");
        assert_eq!(json["settingsSummary"]["apiKey"], "[REDACTED]");
        assert_eq!(json["diagnostics"][0]["asr"]["error"], "[REDACTED LINE]");
        assert_eq!(
            json["diagnostics"][0]["asr"]["rawText"],
            "normal speech\n[REDACTED LINE]"
        );
        assert_eq!(json["history"][0]["rawTranscript"], "raw\n[REDACTED LINE]");
    }

    #[test]
    fn redact_secret_text_redacts_sensitive_log_lines() {
        let text = "normal line\nAuthorization: Bearer abc\nserver JSON ok\napi_key=abc";

        assert_eq!(
            redact_secret_text(text),
            "normal line\n[REDACTED LINE]\nserver JSON ok\n[REDACTED LINE]"
        );
    }

    #[test]
    fn write_diagnostic_bundle_zip_creates_expected_entries() {
        let dir = tempdir().unwrap();
        let zip_path = dir.path().join("diagnostics.zip");
        let bundle = DiagnosticBundle::new(
            vec![sample_trace()],
            Vec::new(),
            "log tail\nAuthorization: Bearer secret".into(),
            serde_json::json!({ "apiKey": "secret", "activeAsrProvider": "doubao-streaming-asr-2" }),
        );

        write_diagnostic_bundle_zip(&bundle, &zip_path).unwrap();

        let file = fs::File::open(&zip_path).unwrap();
        let mut zip = zip::ZipArchive::new(file).unwrap();
        let names = (0..zip.len())
            .map(|index| zip.by_index(index).unwrap().name().to_string())
            .collect::<Vec<_>>();
        assert!(names.contains(&"bundle.json".to_string()));
        assert!(names.contains(&"diagnostics.json".to_string()));
        assert!(names.contains(&"history.json".to_string()));
        assert!(names.contains(&"settings-summary.json".to_string()));
        assert!(names.contains(&"log-tail.txt".to_string()));

        let mut bundle_json = String::new();
        zip.by_name("bundle.json")
            .unwrap()
            .read_to_string(&mut bundle_json)
            .unwrap();
        assert!(bundle_json.contains("doubao-streaming-asr-2"));
        assert!(!bundle_json.contains("secret"));

        let mut log_tail = String::new();
        zip.by_name("log-tail.txt")
            .unwrap()
            .read_to_string(&mut log_tail)
            .unwrap();
        assert_eq!(log_tail, "log tail\n[REDACTED LINE]");
    }
}
