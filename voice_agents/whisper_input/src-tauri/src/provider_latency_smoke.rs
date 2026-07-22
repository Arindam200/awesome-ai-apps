use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::Serialize;

use crate::asr::{AudioConsumer, QwenRealtimeASR, QwenRealtimeCredentials};
use crate::llm_gemini::{GeminiConfig, GeminiProvider, GEMINI_DEFAULT_BASE_URL};
use crate::persistence::{CredentialAccount, CredentialsVault};
use crate::polish::{
    llm_config_for_preset, OpenAICompatibleLLMProvider, DOUBAO_LLM_DEFAULT_MODEL,
    QWEN_LLM_DEFAULT_MODEL,
};
use crate::types::{ChineseScriptPreference, OutputLanguagePreference, PolishMode};

const SAMPLE_TEXT: &str =
    "确认核心合作医院名单及进度：1. 确定齐鲁医院和青医为重点合作对象。2. 需要跟进门诊开通、双通道准入和下周责任人。3. 会后形成行动清单。";

#[derive(Debug, Serialize)]
struct SmokeReport {
    rounds: usize,
    thresholds: SmokeThresholds,
    asr: Vec<AsrSmokeResult>,
    llm: Vec<LlmSmokeResult>,
}

#[derive(Debug, Serialize)]
struct SmokeThresholds {
    llm_ttft_limit_ms: u128,
    call_timeout_ms: u64,
}

#[derive(Debug, Serialize)]
struct AsrSmokeResult {
    round: usize,
    provider: &'static str,
    model: String,
    endpoint: String,
    status: String,
    audio_ms: u64,
    open_ms: Option<u128>,
    finish_send_ms: Option<u128>,
    final_after_finish_ms: Option<u128>,
    total_ms: Option<u128>,
    transcript_chars: usize,
    transcript_preview: String,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
struct LlmSmokeResult {
    round: usize,
    provider: &'static str,
    model: &'static str,
    status: String,
    thinking_enabled: bool,
    ttft_ms: Option<u128>,
    ttft_limit_ms: u128,
    ttft_pass: Option<bool>,
    call_timeout_ms: u64,
    total_ms: Option<u128>,
    output_chars: usize,
    output_preview: String,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
struct CurlProbeResult {
    endpoint: &'static str,
    model: &'static str,
    status: String,
    stdout: String,
    stderr: String,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
struct ReqwestProbeResult {
    model: &'static str,
    status: String,
    http_status: Option<u16>,
    send_ms: Option<u128>,
    first_chunk_ms: Option<u128>,
    total_ms: Option<u128>,
    chunk_preview: String,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
struct NonStreamingPolishResult {
    provider: &'static str,
    model: &'static str,
    status: String,
    total_ms: Option<u128>,
    output_chars: usize,
    output_preview: String,
    error: Option<String>,
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
#[ignore]
async fn provider_latency_smoke_real_credentials() {
    let wav_path = std::env::var("WHISPER_INPUT_SMOKE_WAV").ok();
    let rounds = smoke_rounds();
    let thresholds = SmokeThresholds {
        llm_ttft_limit_ms: smoke_ttft_limit_ms(),
        call_timeout_ms: smoke_call_timeout_ms(),
    };

    let mut asr = Vec::new();
    let mut llm = Vec::new();
    for round in 1..=rounds {
        let asr_result = match wav_path.as_deref() {
            Some(path) => smoke_qwen_asr(round, Path::new(path)).await,
            None => AsrSmokeResult {
                round,
                provider: "qwen-asr",
                model: crate::asr::qwen_realtime::DEFAULT_MODEL.to_string(),
                endpoint: crate::asr::qwen_realtime::DEFAULT_ENDPOINT.to_string(),
                status: "skipped".into(),
                audio_ms: 0,
                open_ms: None,
                finish_send_ms: None,
                final_after_finish_ms: None,
                total_ms: None,
                transcript_chars: 0,
                transcript_preview: String::new(),
                error: Some("WHISPER_INPUT_SMOKE_WAV not set".into()),
            },
        };
        print_smoke_line("SMOKE_ASR_RESULT_JSON", &asr_result);
        asr.push(asr_result);

        for target in llm_targets() {
            print_smoke_line(
                "SMOKE_LLM_START_JSON",
                &serde_json::json!({
                    "round": round,
                    "provider": target.provider,
                    "model": target.model,
                    "call_timeout_ms": thresholds.call_timeout_ms,
                    "ttft_limit_ms": thresholds.llm_ttft_limit_ms,
                }),
            );
            let llm_result = smoke_llm(round, &thresholds, target).await;
            print_smoke_line("SMOKE_LLM_RESULT_JSON", &llm_result);
            llm.push(llm_result);
        }
    }

    let report = SmokeReport {
        rounds,
        thresholds,
        asr,
        llm,
    };
    println!(
        "SMOKE_RESULT_JSON={}",
        serde_json::to_string_pretty(&report).expect("serialize smoke report")
    );
}

#[test]
#[ignore]
fn qwen_curl_latency_probe_real_credentials() {
    let Some(api_key) = qwen_api_key() else {
        let result = CurlProbeResult {
            endpoint: "qwen-cn",
            model: QWEN_LLM_DEFAULT_MODEL,
            status: "skipped".into(),
            stdout: String::new(),
            stderr: String::new(),
            error: Some("API key missing".into()),
        };
        print_smoke_line("QWEN_CURL_RESULT_JSON", &result);
        return;
    };

    for (endpoint, base_url) in [
        (
            "qwen-cn",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        ),
        (
            "qwen-intl",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        ),
    ] {
        for model in [QWEN_LLM_DEFAULT_MODEL, "qwen3.6-plus"] {
            let result = run_qwen_curl_probe(endpoint, base_url, model, &api_key);
            print_smoke_line("QWEN_CURL_RESULT_JSON", &result);
        }
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
#[ignore]
async fn qwen_reqwest_latency_probe_real_credentials() {
    let Some(api_key) = qwen_api_key() else {
        let result = ReqwestProbeResult {
            model: QWEN_LLM_DEFAULT_MODEL,
            status: "skipped".into(),
            http_status: None,
            send_ms: None,
            first_chunk_ms: None,
            total_ms: None,
            chunk_preview: String::new(),
            error: Some("API key missing".into()),
        };
        print_smoke_line("QWEN_REQWEST_RESULT_JSON", &result);
        return;
    };

    for model in [QWEN_LLM_DEFAULT_MODEL, "qwen3.6-plus"] {
        let result = run_qwen_reqwest_probe(model, &api_key).await;
        print_smoke_line("QWEN_REQWEST_RESULT_JSON", &result);
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
#[ignore]
async fn qwen_non_streaming_polish_probe_real_credentials() {
    let Some(api_key) = qwen_api_key() else {
        print_smoke_line(
            "QWEN_NON_STREAM_POLISH_RESULT_JSON",
            &NonStreamingPolishResult {
                provider: "qwen-llm",
                model: QWEN_LLM_DEFAULT_MODEL,
                status: "skipped".into(),
                total_ms: None,
                output_chars: 0,
                output_preview: String::new(),
                error: Some("API key missing".into()),
            },
        );
        return;
    };

    for model in [QWEN_LLM_DEFAULT_MODEL, "qwen3.6-plus"] {
        let started = Instant::now();
        let result =
            match llm_config_for_preset(crate::product::QWEN_LLM_PROVIDER_ID, model, &api_key) {
                Ok(config) => {
                    let provider = OpenAICompatibleLLMProvider::new(config);
                    match tokio::time::timeout(
                        Duration::from_secs(30),
                        provider.polish(
                            SAMPLE_TEXT,
                            PolishMode::Structured,
                            &[],
                            &[],
                            ChineseScriptPreference::Auto,
                            OutputLanguagePreference::Auto,
                            None,
                            &[],
                        ),
                    )
                    .await
                    {
                        Ok(Ok(output)) => NonStreamingPolishResult {
                            provider: "qwen-llm",
                            model,
                            status: "ok".into(),
                            total_ms: Some(started.elapsed().as_millis()),
                            output_chars: output.chars().count(),
                            output_preview: preview(&output, 120),
                            error: None,
                        },
                        Ok(Err(err)) => NonStreamingPolishResult {
                            provider: "qwen-llm",
                            model,
                            status: "error".into(),
                            total_ms: Some(started.elapsed().as_millis()),
                            output_chars: 0,
                            output_preview: String::new(),
                            error: Some(err.to_string()),
                        },
                        Err(_) => NonStreamingPolishResult {
                            provider: "qwen-llm",
                            model,
                            status: "timeout".into(),
                            total_ms: Some(started.elapsed().as_millis()),
                            output_chars: 0,
                            output_preview: String::new(),
                            error: Some("timeout after 30s".into()),
                        },
                    }
                }
                Err(err) => NonStreamingPolishResult {
                    provider: "qwen-llm",
                    model,
                    status: "error".into(),
                    total_ms: Some(started.elapsed().as_millis()),
                    output_chars: 0,
                    output_preview: String::new(),
                    error: Some(err),
                },
            };
        print_smoke_line("QWEN_NON_STREAM_POLISH_RESULT_JSON", &result);
    }
}

fn llm_targets() -> Vec<LlmTarget> {
    vec![
        LlmTarget::openai("qwen-llm", QWEN_LLM_DEFAULT_MODEL, qwen_api_key()),
        LlmTarget::openai(
            "doubao-llm",
            DOUBAO_LLM_DEFAULT_MODEL,
            provider_llm_api_key(crate::product::DOUBAO_LLM_PROVIDER_ID)
                .or_else(|| credential(CredentialAccount::ArkApiKey)),
        ),
        LlmTarget::gemini("gemini-2.5-flash", gemini_api_key()),
        LlmTarget::gemini("gemini-3.1-flash-lite", gemini_api_key()),
    ]
}

struct LlmTarget {
    provider: &'static str,
    model: &'static str,
    api_key: Option<String>,
    native: LlmNative,
}

enum LlmNative {
    OpenAiCompatible,
    Gemini,
}

impl LlmTarget {
    fn openai(provider: &'static str, model: &'static str, api_key: Option<String>) -> Self {
        Self {
            provider,
            model,
            api_key,
            native: LlmNative::OpenAiCompatible,
        }
    }

    fn gemini(model: &'static str, api_key: Option<String>) -> Self {
        Self {
            provider: "gemini",
            model,
            api_key,
            native: LlmNative::Gemini,
        }
    }
}

async fn smoke_llm(
    round: usize,
    thresholds: &SmokeThresholds,
    target: LlmTarget,
) -> LlmSmokeResult {
    let Some(api_key) = target
        .api_key
        .as_ref()
        .filter(|key| !key.trim().is_empty())
        .cloned()
    else {
        return LlmSmokeResult {
            round,
            provider: target.provider,
            model: target.model,
            status: "skipped".into(),
            thinking_enabled: false,
            ttft_ms: None,
            ttft_limit_ms: thresholds.llm_ttft_limit_ms,
            ttft_pass: None,
            call_timeout_ms: thresholds.call_timeout_ms,
            total_ms: None,
            output_chars: 0,
            output_preview: String::new(),
            error: Some("API key missing".into()),
        };
    };

    let started = Instant::now();
    let first_delta = Arc::new(Mutex::new(None::<u128>));
    let first_delta_for_cb = Arc::clone(&first_delta);
    let cancel_started = started;
    let call_timeout_ms = thresholds.call_timeout_ms as u128;
    let on_delta = move |delta: &str| {
        if delta.is_empty() {
            return;
        }
        let mut first = first_delta_for_cb.lock().expect("first delta lock");
        if first.is_none() {
            *first = Some(started.elapsed().as_millis());
        }
    };
    let should_cancel = move || cancel_started.elapsed().as_millis() > call_timeout_ms;

    let result =
        match tokio::time::timeout(Duration::from_millis(thresholds.call_timeout_ms), async {
            print_llm_stage(
                round,
                &target,
                "before-dispatch",
                started.elapsed().as_millis(),
            );
            match target.native {
                LlmNative::OpenAiCompatible => {
                    let provider_id = match target.provider {
                        "qwen-llm" => crate::product::QWEN_LLM_PROVIDER_ID,
                        "doubao-llm" => crate::product::DOUBAO_LLM_PROVIDER_ID,
                        other => other,
                    };
                    print_llm_stage(
                        round,
                        &target,
                        "before-config",
                        started.elapsed().as_millis(),
                    );
                    match llm_config_for_preset(provider_id, target.model, &api_key) {
                        Ok(config) => {
                            print_llm_stage(
                                round,
                                &target,
                                "before-client",
                                started.elapsed().as_millis(),
                            );
                            let provider = OpenAICompatibleLLMProvider::new(config);
                            print_llm_stage(
                                round,
                                &target,
                                "before-polish",
                                started.elapsed().as_millis(),
                            );
                            provider
                                .polish(
                                    SAMPLE_TEXT,
                                    PolishMode::Structured,
                                    &[],
                                    &[],
                                    ChineseScriptPreference::Auto,
                                    OutputLanguagePreference::Auto,
                                    None,
                                    &[],
                                )
                                .await
                        }
                        Err(err) => Err(crate::polish::LLMError::Network(err)),
                    }
                }
                LlmNative::Gemini => {
                    print_llm_stage(
                        round,
                        &target,
                        "before-client",
                        started.elapsed().as_millis(),
                    );
                    let provider = GeminiProvider::new(
                        GeminiConfig::new(api_key, target.model, GEMINI_DEFAULT_BASE_URL)
                            .with_thinking_enabled(false),
                    );
                    print_llm_stage(
                        round,
                        &target,
                        "before-polish",
                        started.elapsed().as_millis(),
                    );
                    provider
                        .polish_streaming(
                            SAMPLE_TEXT,
                            PolishMode::Structured,
                            &[],
                            &[],
                            ChineseScriptPreference::Auto,
                            OutputLanguagePreference::Auto,
                            None,
                            &[],
                            on_delta,
                            should_cancel,
                        )
                        .await
                }
            }
        })
        .await
        {
            Ok(result) => result,
            Err(_) => Err(crate::polish::LLMError::Network(format!(
                "smoke call timeout after {} ms",
                thresholds.call_timeout_ms
            ))),
        };

    match result {
        Ok(output) => {
            let total_ms = started.elapsed().as_millis();
            let first_output_ms = first_delta
                .lock()
                .expect("first delta lock")
                .unwrap_or(total_ms);
            LlmSmokeResult {
                round,
                provider: target.provider,
                model: target.model,
                status: "ok".into(),
                thinking_enabled: false,
                ttft_ms: Some(first_output_ms),
                ttft_limit_ms: thresholds.llm_ttft_limit_ms,
                ttft_pass: Some(first_output_ms <= thresholds.llm_ttft_limit_ms),
                call_timeout_ms: thresholds.call_timeout_ms,
                total_ms: Some(total_ms),
                output_chars: output.chars().count(),
                output_preview: preview(&output, 120),
                error: None,
            }
        }
        Err(err) => LlmSmokeResult {
            round,
            provider: target.provider,
            model: target.model,
            status: "error".into(),
            thinking_enabled: false,
            ttft_ms: *first_delta.lock().expect("first delta lock"),
            ttft_limit_ms: thresholds.llm_ttft_limit_ms,
            ttft_pass: Some(false),
            call_timeout_ms: thresholds.call_timeout_ms,
            total_ms: Some(started.elapsed().as_millis()),
            output_chars: 0,
            output_preview: String::new(),
            error: Some(err.to_string()),
        },
    }
}

async fn smoke_qwen_asr(round: usize, path: &Path) -> AsrSmokeResult {
    let credentials = QwenRealtimeCredentials {
        api_key: qwen_api_key().unwrap_or_default(),
        endpoint: crate::asr::qwen_realtime::DEFAULT_ENDPOINT.to_string(),
        model: crate::asr::qwen_realtime::DEFAULT_MODEL.to_string(),
    };
    let endpoint = credentials.normalized_endpoint();
    let model = credentials.normalized_model();
    if credentials.api_key.trim().is_empty() {
        return AsrSmokeResult {
            round,
            provider: "qwen-asr",
            model,
            endpoint,
            status: "skipped".into(),
            audio_ms: 0,
            open_ms: None,
            finish_send_ms: None,
            final_after_finish_ms: None,
            total_ms: None,
            transcript_chars: 0,
            transcript_preview: String::new(),
            error: Some("API key missing".into()),
        };
    }

    let pcm = match read_wav_pcm16_mono_16k(path) {
        Ok(pcm) => pcm,
        Err(err) => {
            return AsrSmokeResult {
                round,
                provider: "qwen-asr",
                model,
                endpoint,
                status: "error".into(),
                audio_ms: 0,
                open_ms: None,
                finish_send_ms: None,
                final_after_finish_ms: None,
                total_ms: None,
                transcript_chars: 0,
                transcript_preview: String::new(),
                error: Some(err),
            };
        }
    };

    let audio_ms = (pcm.len() as u64) / 32;
    let asr = Arc::new(QwenRealtimeASR::new(credentials));
    let started = Instant::now();

    if let Err(err) = asr.open_session().await {
        return AsrSmokeResult {
            round,
            provider: "qwen-asr",
            model,
            endpoint,
            status: "error".into(),
            audio_ms,
            open_ms: Some(started.elapsed().as_millis()),
            finish_send_ms: None,
            final_after_finish_ms: None,
            total_ms: Some(started.elapsed().as_millis()),
            transcript_chars: 0,
            transcript_preview: String::new(),
            error: Some(err.to_string()),
        };
    }

    let open_ms = started.elapsed().as_millis();
    for chunk in pcm.chunks(crate::asr::qwen_realtime::TARGET_AUDIO_CHUNK_BYTES) {
        asr.consume_pcm_chunk(chunk);
    }

    let finish_started = Instant::now();
    if let Err(err) = asr.send_last_frame().await {
        asr.cancel();
        return AsrSmokeResult {
            round,
            provider: "qwen-asr",
            model,
            endpoint,
            status: "error".into(),
            audio_ms,
            open_ms: Some(open_ms),
            finish_send_ms: Some(finish_started.elapsed().as_millis()),
            final_after_finish_ms: None,
            total_ms: Some(started.elapsed().as_millis()),
            transcript_chars: 0,
            transcript_preview: String::new(),
            error: Some(err.to_string()),
        };
    }
    let finish_send_ms = finish_started.elapsed().as_millis();

    let final_started = Instant::now();
    let final_result = asr.await_final_result().await;
    asr.cancel();

    match final_result {
        Ok(raw) => AsrSmokeResult {
            round,
            provider: "qwen-asr",
            model,
            endpoint,
            status: "ok".into(),
            audio_ms,
            open_ms: Some(open_ms),
            finish_send_ms: Some(finish_send_ms),
            final_after_finish_ms: Some(final_started.elapsed().as_millis()),
            total_ms: Some(started.elapsed().as_millis()),
            transcript_chars: raw.text.chars().count(),
            transcript_preview: preview(&raw.text, 120),
            error: None,
        },
        Err(err) => AsrSmokeResult {
            round,
            provider: "qwen-asr",
            model,
            endpoint,
            status: "error".into(),
            audio_ms,
            open_ms: Some(open_ms),
            finish_send_ms: Some(finish_send_ms),
            final_after_finish_ms: Some(final_started.elapsed().as_millis()),
            total_ms: Some(started.elapsed().as_millis()),
            transcript_chars: 0,
            transcript_preview: String::new(),
            error: Some(err.to_string()),
        },
    }
}

fn smoke_rounds() -> usize {
    std::env::var("WHISPER_INPUT_SMOKE_ROUNDS")
        .ok()
        .and_then(|value| value.trim().parse::<usize>().ok())
        .filter(|rounds| (1..=10).contains(rounds))
        .unwrap_or(3)
}

fn smoke_ttft_limit_ms() -> u128 {
    std::env::var("WHISPER_INPUT_SMOKE_TTFT_LIMIT_MS")
        .ok()
        .and_then(|value| value.trim().parse::<u128>().ok())
        .filter(|limit| *limit > 0)
        .unwrap_or(3000)
}

fn smoke_call_timeout_ms() -> u64 {
    std::env::var("WHISPER_INPUT_SMOKE_CALL_TIMEOUT_MS")
        .ok()
        .and_then(|value| value.trim().parse::<u64>().ok())
        .filter(|limit| (1000..=120_000).contains(limit))
        .unwrap_or(30_000)
}

fn print_smoke_line<T: Serialize>(prefix: &str, value: &T) {
    println!(
        "{prefix}={}",
        serde_json::to_string(value).expect("serialize smoke line")
    );
}

fn print_llm_stage(round: usize, target: &LlmTarget, stage: &'static str, elapsed_ms: u128) {
    print_smoke_line(
        "SMOKE_LLM_STAGE_JSON",
        &serde_json::json!({
            "round": round,
            "provider": target.provider,
            "model": target.model,
            "stage": stage,
            "elapsed_ms": elapsed_ms,
        }),
    );
}

fn run_qwen_curl_probe(
    endpoint: &'static str,
    url: &str,
    model: &'static str,
    api_key: &str,
) -> CurlProbeResult {
    let body = serde_json::json!({
        "model": model,
        "messages": [{"role": "user", "content": "请用一句话回复：测试"}],
        "stream": true,
        "enable_thinking": false,
        "temperature": 0.2,
    });
    let config = format!(
        "url = {}\nrequest = \"POST\"\nheader = {}\nheader = {}\ndata = {}\n",
        curl_config_quote(url),
        curl_config_quote(&format!("Authorization: Bearer {api_key}")),
        curl_config_quote("Content-Type: application/json"),
        curl_config_quote(&body.to_string()),
    );

    let mut child = match Command::new("curl.exe")
        .args([
            "-sS",
            "-o",
            "NUL",
            "-w",
            "connect=%{time_connect} tls=%{time_appconnect} first=%{time_starttransfer} total=%{time_total} code=%{http_code}",
            "--connect-timeout",
            "5",
            "--max-time",
            "15",
            "--config",
            "-",
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(child) => child,
        Err(err) => {
            return CurlProbeResult {
                endpoint,
                model,
                status: "error".into(),
                stdout: String::new(),
                stderr: String::new(),
                error: Some(format!("spawn curl failed: {err}")),
            };
        }
    };

    if let Some(stdin) = child.stdin.as_mut() {
        if let Err(err) = stdin.write_all(config.as_bytes()) {
            return CurlProbeResult {
                endpoint,
                model,
                status: "error".into(),
                stdout: String::new(),
                stderr: String::new(),
                error: Some(format!("write curl config failed: {err}")),
            };
        }
    }

    match child.wait_with_output() {
        Ok(output) => CurlProbeResult {
            endpoint,
            model,
            status: if output.status.success() {
                "ok".into()
            } else {
                "error".into()
            },
            stdout: String::from_utf8_lossy(&output.stdout).trim().to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).trim().to_string(),
            error: None,
        },
        Err(err) => CurlProbeResult {
            endpoint,
            model,
            status: "error".into(),
            stdout: String::new(),
            stderr: String::new(),
            error: Some(format!("wait curl failed: {err}")),
        },
    }
}

async fn run_qwen_reqwest_probe(model: &'static str, api_key: &str) -> ReqwestProbeResult {
    let started = Instant::now();
    let client =
        match crate::polish::http_client_builder(crate::polish::QWEN_LLM_BASE_URL_CN, 15).build() {
            Ok(client) => client,
            Err(err) => {
                return ReqwestProbeResult {
                    model,
                    status: "error".into(),
                    http_status: None,
                    send_ms: None,
                    first_chunk_ms: None,
                    total_ms: Some(started.elapsed().as_millis()),
                    chunk_preview: String::new(),
                    error: Some(format!("build reqwest client failed: {err}")),
                };
            }
        };
    let body = serde_json::json!({
        "model": model,
        "messages": [{"role": "user", "content": "请用一句话回复：测试"}],
        "stream": true,
        "enable_thinking": false,
        "temperature": 0.2,
    });
    let request = client
        .post(format!(
            "{}/chat/completions",
            crate::polish::QWEN_LLM_BASE_URL_CN
        ))
        .header("Content-Type", "application/json")
        .header("Accept", "text/event-stream")
        .bearer_auth(api_key)
        .json(&body);

    let mut response = match tokio::time::timeout(Duration::from_secs(20), request.send()).await {
        Ok(Ok(response)) => response,
        Ok(Err(err)) => {
            return ReqwestProbeResult {
                model,
                status: "error".into(),
                http_status: None,
                send_ms: Some(started.elapsed().as_millis()),
                first_chunk_ms: None,
                total_ms: Some(started.elapsed().as_millis()),
                chunk_preview: String::new(),
                error: Some(format!("send failed: {err}")),
            };
        }
        Err(_) => {
            return ReqwestProbeResult {
                model,
                status: "timeout".into(),
                http_status: None,
                send_ms: Some(started.elapsed().as_millis()),
                first_chunk_ms: None,
                total_ms: Some(started.elapsed().as_millis()),
                chunk_preview: String::new(),
                error: Some("send timeout after 20s".into()),
            };
        }
    };
    let send_ms = started.elapsed().as_millis();
    let status = response.status();
    if !status.is_success() {
        let body = response.text().await.unwrap_or_default();
        return ReqwestProbeResult {
            model,
            status: "error".into(),
            http_status: Some(status.as_u16()),
            send_ms: Some(send_ms),
            first_chunk_ms: None,
            total_ms: Some(started.elapsed().as_millis()),
            chunk_preview: preview(&body, 120),
            error: Some(format!("HTTP {}", status.as_u16())),
        };
    }

    match tokio::time::timeout(Duration::from_secs(20), response.chunk()).await {
        Ok(Ok(Some(chunk))) => ReqwestProbeResult {
            model,
            status: "ok".into(),
            http_status: Some(status.as_u16()),
            send_ms: Some(send_ms),
            first_chunk_ms: Some(started.elapsed().as_millis()),
            total_ms: Some(started.elapsed().as_millis()),
            chunk_preview: preview(&String::from_utf8_lossy(&chunk), 120),
            error: None,
        },
        Ok(Ok(None)) => ReqwestProbeResult {
            model,
            status: "error".into(),
            http_status: Some(status.as_u16()),
            send_ms: Some(send_ms),
            first_chunk_ms: None,
            total_ms: Some(started.elapsed().as_millis()),
            chunk_preview: String::new(),
            error: Some("stream ended before first chunk".into()),
        },
        Ok(Err(err)) => ReqwestProbeResult {
            model,
            status: "error".into(),
            http_status: Some(status.as_u16()),
            send_ms: Some(send_ms),
            first_chunk_ms: None,
            total_ms: Some(started.elapsed().as_millis()),
            chunk_preview: String::new(),
            error: Some(format!("read chunk failed: {err}")),
        },
        Err(_) => ReqwestProbeResult {
            model,
            status: "timeout".into(),
            http_status: Some(status.as_u16()),
            send_ms: Some(send_ms),
            first_chunk_ms: None,
            total_ms: Some(started.elapsed().as_millis()),
            chunk_preview: String::new(),
            error: Some("first chunk timeout after 20s".into()),
        },
    }
}

fn curl_config_quote(value: &str) -> String {
    format!(
        "\"{}\"",
        value
            .replace('\\', "\\\\")
            .replace('"', "\\\"")
            .replace('\n', "\\n")
    )
}

fn qwen_api_key() -> Option<String> {
    first_non_blank(&[
        CredentialAccount::AsrQwenApiKey,
        CredentialAccount::LlmQwenApiKey,
        CredentialAccount::ArkApiKey,
    ])
}

fn gemini_api_key() -> Option<String> {
    provider_llm_api_key(crate::product::GEMINI_PROVIDER_ID).or_else(|| {
        first_non_blank(&[
            CredentialAccount::LlmGeminiApiKey,
            CredentialAccount::ArkApiKey,
        ])
    })
}

fn first_non_blank(accounts: &[CredentialAccount]) -> Option<String> {
    accounts.iter().find_map(|account| credential(*account))
}

fn credential(account: CredentialAccount) -> Option<String> {
    CredentialsVault::get(account)
        .ok()
        .flatten()
        .filter(|value| !value.trim().is_empty())
}

fn provider_llm_api_key(provider_id: &str) -> Option<String> {
    CredentialsVault::get_llm_provider_api_key_for_smoke(provider_id)
        .ok()
        .flatten()
}

fn preview(value: &str, max_chars: usize) -> String {
    value.chars().take(max_chars).collect()
}

fn read_wav_pcm16_mono_16k(path: &Path) -> Result<Vec<u8>, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("read wav failed: {e}"))?;
    if bytes.len() < 44 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return Err("not a RIFF/WAVE file".into());
    }

    let mut cursor = 12usize;
    let mut fmt_ok = false;
    let mut data = None;
    while cursor + 8 <= bytes.len() {
        let id = &bytes[cursor..cursor + 4];
        let size = u32::from_le_bytes(
            bytes[cursor + 4..cursor + 8]
                .try_into()
                .map_err(|_| "invalid chunk size")?,
        ) as usize;
        cursor += 8;
        if cursor + size > bytes.len() {
            return Err("wav chunk exceeds file length".into());
        }
        match id {
            b"fmt " => {
                if size < 16 {
                    return Err("fmt chunk too short".into());
                }
                let audio_format =
                    u16::from_le_bytes(bytes[cursor..cursor + 2].try_into().unwrap());
                let channels =
                    u16::from_le_bytes(bytes[cursor + 2..cursor + 4].try_into().unwrap());
                let sample_rate =
                    u32::from_le_bytes(bytes[cursor + 4..cursor + 8].try_into().unwrap());
                let bits_per_sample =
                    u16::from_le_bytes(bytes[cursor + 14..cursor + 16].try_into().unwrap());
                fmt_ok = audio_format == 1
                    && channels == 1
                    && sample_rate == 16_000
                    && bits_per_sample == 16;
            }
            b"data" => data = Some(bytes[cursor..cursor + size].to_vec()),
            _ => {}
        }
        cursor += size + (size % 2);
    }

    if !fmt_ok {
        return Err("wav must be PCM16 mono 16 kHz".into());
    }
    data.ok_or_else(|| "missing data chunk".into())
}
