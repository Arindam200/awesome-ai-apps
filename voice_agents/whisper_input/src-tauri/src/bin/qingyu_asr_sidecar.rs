use std::io::{self, BufRead, Write};
use std::path::{Path, PathBuf};
use std::process::Command;

use openless_lib::qingyu_sidecar_protocol::{SidecarMethod, SidecarRequest, SidecarResponse};

const SHERPA_OFFLINE_EXE: &str = "sherpa-onnx-offline.exe";

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::BufWriter::new(io::stdout().lock());

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(line) => line,
            Err(error) => {
                let response = error_response(
                    "read-error".into(),
                    format!("failed to read request from stdin: {error}"),
                );
                let _ = write_response(&mut stdout, &response);
                break;
            }
        };

        let request = match serde_json::from_str::<SidecarRequest>(&line) {
            Ok(request) => request,
            Err(error) => {
                let response = error_response(
                    extract_request_id_for_parse_error(&line),
                    format!("failed to parse sidecar request: {error}"),
                );
                if write_response(&mut stdout, &response).is_err() {
                    break;
                }
                continue;
            }
        };

        let should_shutdown = matches!(&request.method, SidecarMethod::Shutdown);
        let response = handle_request(request);
        if write_response(&mut stdout, &response).is_err() {
            break;
        }
        if should_shutdown {
            break;
        }
    }
}

fn extract_request_id_for_parse_error(raw: &str) -> String {
    serde_json::from_str::<serde_json::Value>(raw)
        .ok()
        .and_then(|value| {
            value
                .get("id")
                .and_then(serde_json::Value::as_str)
                .map(str::to_owned)
        })
        .unwrap_or_else(|| "parse-error".into())
}

fn handle_request(request: SidecarRequest) -> SidecarResponse {
    match request.method {
        SidecarMethod::Health {
            model_dir,
            vad_path,
        } => match validate_assets(&model_dir, &vad_path) {
            Ok(()) => ok_response(request.id, None),
            Err(error) => error_response(request.id, error),
        },
        SidecarMethod::Prepare {
            model_dir,
            vad_path,
        } => match validate_assets(&model_dir, &vad_path) {
            Ok(()) => match sherpa_offline_path().and_then(|path| {
                validate_sherpa_offline_executable(&path)?;
                Ok(path)
            }) {
                Ok(_) => ok_response(request.id, None),
                Err(error) => error_response(request.id, error),
            },
            Err(error) => error_response(request.id, error),
        },
        SidecarMethod::Transcribe {
            model_dir,
            wav_path,
        } => match transcribe(&model_dir, &wav_path) {
            Ok(text) => ok_response(request.id, Some(text)),
            Err(error) => error_response(request.id, error),
        },
        SidecarMethod::Shutdown => ok_response(request.id, None),
    }
}

fn sidecar_exe_dir() -> Result<PathBuf, String> {
    let current_exe = std::env::current_exe()
        .map_err(|error| format!("failed to resolve sidecar executable path: {error}"))?;
    current_exe.parent().map(Path::to_path_buf).ok_or_else(|| {
        format!(
            "failed to resolve parent directory for sidecar executable: {}",
            current_exe.to_string_lossy()
        )
    })
}

fn sherpa_offline_path() -> Result<PathBuf, String> {
    Ok(sidecar_exe_dir()?.join(SHERPA_OFFLINE_EXE))
}

fn sherpa_args(model_dir: &Path, wav_path: &Path) -> Vec<String> {
    vec![
        "--num-threads=4".to_string(),
        format!(
            "--fire-red-asr-ctc={}",
            model_dir.join("model.int8.onnx").to_string_lossy()
        ),
        format!(
            "--tokens={}",
            model_dir.join("tokens.txt").to_string_lossy()
        ),
        wav_path.to_string_lossy().into_owned(),
    ]
}

fn validate_sherpa_offline_executable(path: &Path) -> Result<(), String> {
    if path.is_file() {
        Ok(())
    } else {
        Err(format!(
            "{SHERPA_OFFLINE_EXE} is not a file beside the ASR sidecar: {}",
            path.to_string_lossy()
        ))
    }
}

fn transcribe(model_dir: &str, wav_path: &str) -> Result<String, String> {
    let wav_path = Path::new(wav_path);
    if !wav_path.is_file() {
        return Err(format!(
            "wavPath is not a file: {}",
            wav_path.to_string_lossy()
        ));
    }

    let sherpa_path = sherpa_offline_path()?;
    validate_sherpa_offline_executable(&sherpa_path)?;

    let output = Command::new(&sherpa_path)
        .args(sherpa_args(Path::new(model_dir), wav_path))
        .output()
        .map_err(|error| {
            format!(
                "failed to run {SHERPA_OFFLINE_EXE} at {}: {error}",
                sherpa_path.to_string_lossy()
            )
        })?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !output.status.success() {
        return Err(format!(
            "{SHERPA_OFFLINE_EXE} exited with {}; stderr: {}; stdout: {}",
            output.status,
            summarize_text(&stderr),
            summarize_text(&stdout)
        ));
    }

    parse_transcript_text(&stdout)
}

fn parse_transcript_text(stdout: &str) -> Result<String, String> {
    for line in stdout.lines() {
        let Ok(value) = serde_json::from_str::<serde_json::Value>(line.trim()) else {
            continue;
        };
        if let Some(text) = value.get("text").and_then(serde_json::Value::as_str) {
            let text = text.trim();
            if !text.is_empty() {
                return Ok(text.to_string());
            }
        }
    }

    Err(format!(
        "sherpa output contained no JSON transcript text; stdout: {}",
        summarize_text(stdout)
    ))
}

fn summarize_text(value: &str) -> String {
    let value = value.trim();
    const MAX_CHARS: usize = 800;
    if value.chars().count() <= MAX_CHARS {
        return value.to_string();
    }

    let mut summary: String = value.chars().take(MAX_CHARS).collect();
    summary.push_str("...");
    summary
}

fn validate_assets(model_dir: &str, vad_path: &str) -> Result<(), String> {
    let mut errors = Vec::new();
    let model_dir_path = Path::new(model_dir);
    if !model_dir_path.is_dir() {
        errors.push(format!("modelDir is not a directory: {model_dir}"));
    }
    for file_name in ["model.int8.onnx", "tokens.txt"] {
        let model_file = model_dir_path.join(file_name);
        if !model_file.is_file() {
            errors.push(format!(
                "{file_name} is not a file under modelDir: {}",
                model_file.to_string_lossy()
            ));
        }
    }
    if !Path::new(vad_path).is_file() {
        errors.push(format!("vadPath is not a file: {vad_path}"));
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors.join("; "))
    }
}

fn ok_response(id: String, text: Option<String>) -> SidecarResponse {
    SidecarResponse {
        id,
        ok: true,
        text,
        error: None,
    }
}

fn error_response(id: String, error: String) -> SidecarResponse {
    SidecarResponse {
        id,
        ok: false,
        text: None,
        error: Some(error),
    }
}

fn write_response<W: Write>(writer: &mut W, response: &SidecarResponse) -> io::Result<()> {
    let json = serde_json::to_string(response)
        .map_err(|error| io::Error::new(io::ErrorKind::Other, error))?;
    writeln!(writer, "{json}")?;
    writer.flush()
}

#[cfg(test)]
mod tests {
    use super::{
        extract_request_id_for_parse_error, handle_request, parse_transcript_text, sherpa_args,
        validate_sherpa_offline_executable,
    };
    use openless_lib::qingyu_sidecar_protocol::{SidecarMethod, SidecarRequest};
    use std::path::PathBuf;

    #[test]
    fn transcribe_rejects_missing_wav_path() {
        let response = handle_request(SidecarRequest {
            id: "tx-1".into(),
            method: SidecarMethod::Transcribe {
                model_dir: "model".into(),
                wav_path: "audio.wav".into(),
            },
        });

        assert_eq!(response.id, "tx-1");
        assert!(!response.ok);
        assert!(response.text.is_none());
        assert!(response.error.unwrap().contains("wavPath is not a file"));
    }

    #[test]
    fn sherpa_args_points_to_model_assets_with_joined_paths() {
        let model_dir = PathBuf::from("models").join("qingyu");
        let wav_path = PathBuf::from("audio").join("sample.wav");

        let args = sherpa_args(&model_dir, &wav_path);

        assert_eq!(
            args,
            vec![
                "--num-threads=4".to_string(),
                format!(
                    "--fire-red-asr-ctc={}",
                    model_dir.join("model.int8.onnx").to_string_lossy()
                ),
                format!(
                    "--tokens={}",
                    model_dir.join("tokens.txt").to_string_lossy()
                ),
                wav_path.to_string_lossy().into_owned(),
            ]
        );
    }

    #[test]
    fn missing_sherpa_offline_executable_is_a_clear_error() {
        let missing = std::env::temp_dir().join(format!(
            "missing-sherpa-onnx-offline-{}.exe",
            std::process::id()
        ));
        let _ = std::fs::remove_file(&missing);

        let error = validate_sherpa_offline_executable(&missing).unwrap_err();

        assert!(error.contains("sherpa-onnx-offline.exe"), "{error}");
        assert!(error.contains("not a file"), "{error}");
    }

    #[test]
    fn transcript_parser_prefers_json_line_text_field() {
        let stdout = "startup log\n{\"text\":\"hello openless\"}\n";

        assert_eq!(parse_transcript_text(stdout).unwrap(), "hello openless");
    }

    #[test]
    fn transcript_parser_rejects_plain_stdout_without_json_text() {
        let error = parse_transcript_text(" plain transcript \n").unwrap_err();

        assert!(error.contains("no JSON transcript text"), "{error}");
    }

    #[test]
    fn transcript_parser_rejects_empty_stdout() {
        let error = parse_transcript_text("\n \t").unwrap_err();

        assert!(error.contains("no JSON transcript text"), "{error}");
    }

    #[test]
    fn health_requires_model_dir_and_vad_path() {
        let missing =
            std::env::temp_dir().join(format!("qingyu-sidecar-missing-{}", std::process::id()));
        let response = handle_request(SidecarRequest {
            id: "health-1".into(),
            method: SidecarMethod::Health {
                model_dir: missing.join("model").to_string_lossy().into_owned(),
                vad_path: missing.join("vad.onnx").to_string_lossy().into_owned(),
            },
        });

        assert_eq!(response.id, "health-1");
        assert!(!response.ok);
        assert!(response.text.is_none());
        assert!(response
            .error
            .unwrap()
            .contains("modelDir is not a directory"));
    }

    #[test]
    fn health_rejects_empty_model_dir() {
        let root =
            std::env::temp_dir().join(format!("qingyu-sidecar-empty-model-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        let model_dir = root.join("model");
        let vad_path = root.join("silero_vad.onnx");
        std::fs::create_dir_all(&model_dir).unwrap();
        std::fs::write(&vad_path, b"vad").unwrap();

        let response = handle_request(SidecarRequest {
            id: "health-empty".into(),
            method: SidecarMethod::Health {
                model_dir: model_dir.to_string_lossy().into_owned(),
                vad_path: vad_path.to_string_lossy().into_owned(),
            },
        });

        assert_eq!(response.id, "health-empty");
        assert!(!response.ok);
        let error = response.error.unwrap();
        assert!(error.contains("model.int8.onnx"), "{error}");
        assert!(error.contains("tokens.txt"), "{error}");

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn parse_error_id_falls_back_to_raw_request_id_when_available() {
        let raw = r#"{ "id": "abc", "method": { "type": "unknown" } }"#;

        assert_eq!(extract_request_id_for_parse_error(raw), "abc");
    }

    #[test]
    fn parse_error_id_uses_parse_error_when_raw_id_is_unavailable() {
        assert_eq!(
            extract_request_id_for_parse_error("{not json"),
            "parse-error"
        );
        assert_eq!(
            extract_request_id_for_parse_error(r#"{ "id": 123, "method": {} }"#),
            "parse-error"
        );
    }
}
