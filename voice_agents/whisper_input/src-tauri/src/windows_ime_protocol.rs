use serde::{Deserialize, Serialize};

pub const OPENLESS_IME_PROTOCOL_VERSION: u32 = 1;
pub const OPENLESS_IME_PIPE_NAME_PREFIX: &str = r"\\.\pipe\OpenLessImeSubmit";

pub fn ime_pipe_name_for_target(process_id: u32, thread_id: u32) -> String {
    format!("{OPENLESS_IME_PIPE_NAME_PREFIX}-{process_id}-{thread_id}")
}

pub fn ime_pipe_candidate_names_for_target<I>(
    process_id: u32,
    thread_id: u32,
    available_pipe_names: I,
) -> Vec<String>
where
    I: IntoIterator<Item = String>,
{
    let exact_pipe_name = ime_pipe_name_for_target(process_id, thread_id);
    let process_pipe_prefix = format!("{OPENLESS_IME_PIPE_NAME_PREFIX}-{process_id}-");
    let mut candidates = vec![exact_pipe_name.clone()];
    let mut same_process_pipe_names = available_pipe_names
        .into_iter()
        .filter(|pipe_name| pipe_name != &exact_pipe_name)
        .filter(|pipe_name| {
            pipe_name
                .strip_prefix(&process_pipe_prefix)
                .is_some_and(|thread_suffix| {
                    !thread_suffix.is_empty()
                        && thread_suffix.bytes().all(|byte| byte.is_ascii_digit())
                })
        })
        .collect::<Vec<_>>();

    same_process_pipe_names.sort();
    same_process_pipe_names.dedup();
    candidates.extend(same_process_pipe_names);
    candidates
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(
    tag = "type",
    rename_all = "camelCase",
    rename_all_fields = "camelCase"
)]
pub enum ImePipeMessage {
    ClientReady {
        protocol_version: u32,
        client_id: String,
        process_id: u32,
        thread_id: u32,
    },
    SubmitText {
        protocol_version: u32,
        session_id: String,
        text: String,
        created_at: String,
    },
    SubmitResult {
        protocol_version: u32,
        session_id: String,
        status: ImeSubmitStatus,
        error_code: Option<String>,
    },
    CancelSession {
        protocol_version: u32,
        session_id: String,
    },
    Ping {
        protocol_version: u32,
    },
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub enum ImeSubmitStatus {
    Committed,
    Rejected,
    Failed,
}

pub fn encode_message(message: &ImePipeMessage) -> Result<String, serde_json::Error> {
    let mut line = serde_json::to_string(message)?;
    line.push('\n');
    Ok(line)
}

pub fn decode_message(line: &str) -> Result<ImePipeMessage, serde_json::Error> {
    serde_json::from_str(line)
}

pub fn is_result_for_pending_session(
    message: &ImePipeMessage,
    pending_session_id: &str,
) -> Result<(), &'static str> {
    match message {
        ImePipeMessage::SubmitResult { session_id, .. } if session_id == pending_session_id => {
            Ok(())
        }
        ImePipeMessage::SubmitResult { .. } => Err("submit result belongs to a different session"),
        _ => Err("message is not a submit result"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn submit_text_roundtrips_as_camel_case_json() {
        let message = ImePipeMessage::SubmitText {
            protocol_version: OPENLESS_IME_PROTOCOL_VERSION,
            session_id: "session-1".to_string(),
            text: "\u{4f60}\u{597d} OpenLess".to_string(),
            created_at: "2026-05-01T12:00:00Z".to_string(),
        };

        let json = encode_message(&message).expect("encode");
        assert!(json.contains("\"submitText\""));
        assert!(json.contains("\"sessionId\""));
        assert!(json.contains("\"createdAt\""));
        assert!(!json.contains("\"session_id\""));
        assert!(!json.contains("\"created_at\""));
        assert!(json.ends_with('\n'));

        let decoded = decode_message(json.trim_end()).expect("decode");
        assert_eq!(decoded, message);
    }

    #[test]
    fn ime_pipe_name_includes_target_process_and_thread() {
        assert_eq!(
            ime_pipe_name_for_target(1234, 5678),
            r"\\.\pipe\OpenLessImeSubmit-1234-5678"
        );
    }

    #[test]
    fn ime_pipe_candidates_include_same_process_clients_after_exact_target() {
        let available = vec![
            r"\\.\pipe\OtherPipe".to_string(),
            r"\\.\pipe\OpenLessImeSubmit-4321-1111".to_string(),
            r"\\.\pipe\OpenLessImeSubmit-1234-9999".to_string(),
            r"\\.\pipe\OpenLessImeSubmit-1234-5678".to_string(),
            r"\\.\pipe\OpenLessImeSubmit-1234-bad".to_string(),
        ];

        assert_eq!(
            ime_pipe_candidate_names_for_target(1234, 5678, available),
            vec![
                r"\\.\pipe\OpenLessImeSubmit-1234-5678".to_string(),
                r"\\.\pipe\OpenLessImeSubmit-1234-9999".to_string(),
            ]
        );
    }

    #[test]
    fn stale_submit_result_is_rejected() {
        let result = ImePipeMessage::SubmitResult {
            protocol_version: OPENLESS_IME_PROTOCOL_VERSION,
            session_id: "old-session".to_string(),
            status: ImeSubmitStatus::Committed,
            error_code: Some("ime-busy".to_string()),
        };

        let json = encode_message(&result).expect("encode");
        assert!(json.contains("\"errorCode\""));
        assert!(!json.contains("\"error_code\""));

        assert!(is_result_for_pending_session(&result, "current-session").is_err());
        assert!(is_result_for_pending_session(&result, "old-session").is_ok());
    }
}
