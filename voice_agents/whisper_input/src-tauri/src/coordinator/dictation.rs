use std::sync::atomic::Ordering;
use std::sync::Arc;

use crate::asr::volcengine::VolcengineDiagnosticSnapshot;
use crate::coordinator_state::request_stop_during_starting_state;
use crate::correction::apply_correction_rules;
use crate::diagnostics::{
    DiagnosticApp, DiagnosticAsr, DiagnosticInsertion, DiagnosticLlm, DiagnosticRecorderFacts,
    DiagnosticSession, DiagnosticTrace,
};
use crate::types::{HotkeyMode, OutputLanguagePreference, UserPreferences};

use super::qa::handle_qa_option_edge;
use super::resources::*;
use super::*;

/// 同一个 hotkey 边沿之间的最小间隔。低于此阈值的连按整体作为误触丢弃 ——
/// 避免微动开关回弹 / 用户手抖双击造成的空转写报错和 ASR session 抢资源。
const HOTKEY_DEBOUNCE: std::time::Duration = std::time::Duration::from_millis(250);
const SHORT_TRANSCRIPT_LLM_BYPASS_CHAR_THRESHOLD: usize = 8;

fn effective_transcript_char_count(text: &str) -> usize {
    text.chars()
        .filter(|ch| {
            !ch.is_whitespace()
                && !ch.is_ascii_punctuation()
                && !matches!(
                    ch,
                    '，' | '。'
                        | '、'
                        | '；'
                        | '：'
                        | '？'
                        | '！'
                        | '“'
                        | '”'
                        | '‘'
                        | '’'
                        | '（'
                        | '）'
                        | '《'
                        | '》'
                        | '【'
                        | '】'
                        | '…'
                        | '—'
                )
        })
        .count()
}

fn should_bypass_llm_for_short_transcript(
    text: &str,
    translation_active: bool,
    output_operation: DictationOutputOperation,
) -> bool {
    !translation_active
        && output_operation == DictationOutputOperation::Polish
        && effective_transcript_char_count(text) < SHORT_TRANSCRIPT_LLM_BYPASS_CHAR_THRESHOLD
}

fn diagnostic_insert_method(already_streamed: bool, focus_ready_for_paste: bool) -> &'static str {
    if already_streamed {
        "streaming-unicode"
    } else if focus_ready_for_paste {
        "clipboard-or-tsf"
    } else {
        "copy-fallback"
    }
}

fn diagnostic_char_count(text: &str) -> u32 {
    text.chars().count().min(u32::MAX as usize) as u32
}

fn new_dictation_trace(
    trace_id: String,
    mode: PolishMode,
    hotkey_mode: HotkeyMode,
    front_app: Option<String>,
    asr_provider_id: String,
    llm_provider_id: String,
) -> DiagnosticTrace {
    let now = Utc::now().to_rfc3339();
    DiagnosticTrace {
        schema_version: 1,
        trace_id,
        created_at: now.clone(),
        app: DiagnosticApp {
            version: env!("CARGO_PKG_VERSION").into(),
            platform: std::env::consts::OS.into(),
            arch: std::env::consts::ARCH.into(),
        },
        session: DiagnosticSession {
            mode: Some(format!("{mode:?}")),
            hotkey_mode: Some(format!("{hotkey_mode:?}")),
            front_app,
            pressed_at: None,
            released_at: None,
            cancelled: false,
        },
        recorder: DiagnosticRecorderFacts::default(),
        asr: DiagnosticAsr {
            provider: Some(asr_provider_id),
            ..Default::default()
        },
        llm: DiagnosticLlm {
            provider: Some(llm_provider_id),
            mode: Some(format!("{mode:?}")),
            ..Default::default()
        },
        insertion: DiagnosticInsertion::default(),
        flags: Vec::new(),
    }
}

fn complete_trace_texts(
    trace: &mut DiagnosticTrace,
    raw_text: &str,
    final_text: &str,
    status: InsertStatus,
) {
    trace.asr.raw_text = Some(raw_text.to_string());
    trace.asr.raw_chars = Some(diagnostic_char_count(raw_text));
    trace.llm.final_text = Some(final_text.to_string());
    trace.llm.final_chars = Some(diagnostic_char_count(final_text));
    trace.insertion.status = Some(format!("{status:?}"));
}

fn apply_volcengine_diagnostic_snapshot(
    trace: &mut DiagnosticTrace,
    snapshot: VolcengineDiagnosticSnapshot,
) {
    trace.asr.connected_at_ms = snapshot.connected_at_ms;
    trace.asr.first_server_message_at_ms = snapshot.first_server_message_at_ms;
    trace.asr.last_server_message_at_ms = snapshot.last_server_message_at_ms;
    trace.asr.server_audio_duration_ms = snapshot.server_audio_duration_ms;
    trace.asr.socket_closed_at_ms = snapshot.socket_closed_at_ms;
    trace.asr.socket_error = snapshot.socket_error;
    trace.asr.server_log_id = snapshot.server_log_id;
    trace.asr.frames_sent = snapshot.frames_sent;
    trace.asr.bytes_sent = snapshot.bytes_sent;
    trace.asr.pending_sends = snapshot.pending_sends;
    trace.asr.final_missing_partial_used = snapshot.final_missing_partial_used;
}

fn append_diagnostic_trace(inner: &Arc<Inner>, trace: DiagnosticTrace) {
    if let Err(error) = inner.diagnostics.append(trace) {
        log::warn!("[diagnostics] append dictation trace failed: {error}");
    }
}

fn append_asr_error_trace(inner: &Arc<Inner>, mut trace: DiagnosticTrace, error: String) {
    trace.asr.error = Some(error);
    trace.insertion.status = Some("notStarted".to_string());
    trace.insertion.method = Some("none".to_string());
    append_diagnostic_trace(inner, trace);
}

fn append_begin_asr_error_trace(
    inner: &Arc<Inner>,
    current_session_id: SessionId,
    asr_provider_id: &str,
    error: impl Into<String>,
) {
    let mut trace = new_begin_error_trace(inner, current_session_id, asr_provider_id);
    trace.asr.error = Some(error.into());
    trace.insertion.status = Some("notStarted".to_string());
    trace.insertion.method = Some("none".to_string());
    append_diagnostic_trace(inner, trace);
}

fn append_begin_recorder_error_trace(
    inner: &Arc<Inner>,
    current_session_id: SessionId,
    asr_provider_id: &str,
    error: impl Into<String>,
) {
    let mut trace = new_begin_error_trace(inner, current_session_id, asr_provider_id);
    trace.recorder.error = Some(error.into());
    trace.insertion.status = Some("notStarted".to_string());
    trace.insertion.method = Some("none".to_string());
    append_diagnostic_trace(inner, trace);
}

fn append_runtime_recorder_error_trace(
    inner: &Arc<Inner>,
    current_session_id: SessionId,
    error: impl Into<String>,
) {
    let active_asr = CredentialsVault::get_active_asr();
    let mut trace = new_begin_error_trace(inner, current_session_id, &active_asr);
    trace.session.released_at = Some(Utc::now().to_rfc3339());
    trace.recorder.error = Some(error.into());
    trace.insertion.status = Some("recorderError".to_string());
    trace.insertion.method = Some("none".to_string());
    append_diagnostic_trace(inner, trace);
}

fn new_begin_error_trace(
    inner: &Arc<Inner>,
    current_session_id: SessionId,
    asr_provider_id: &str,
) -> DiagnosticTrace {
    let prefs = inner.prefs.get();
    let (front_app, cancelled) = {
        let state = inner.state.lock();
        (state.front_app.clone(), state.cancelled)
    };
    let mut trace = new_dictation_trace(
        Uuid::new_v4().to_string(),
        prefs.default_mode,
        prefs.hotkey.mode,
        front_app,
        asr_provider_id.to_string(),
        CredentialsVault::get_active_llm(),
    );
    trace.trace_id = current_session_id.to_string();
    trace.session.cancelled = cancelled;
    if let Some(probe) = take_recorder_diagnostics_for_session(inner, current_session_id) {
        trace.recorder = probe.snapshot();
    }
    trace
}

#[cfg(test)]
fn diagnostic_trace_for_test(trace_id: &str) -> DiagnosticTrace {
    new_dictation_trace(
        trace_id.to_string(),
        PolishMode::Light,
        HotkeyMode::Hold,
        Some("Test App".into()),
        "doubao-streaming-asr-2".into(),
        "gemini".into(),
    )
}

fn asr_transcript_has_no_speech(text: &str) -> bool {
    let normalized = text.trim().to_ascii_lowercase();
    normalized.is_empty() || normalized == "<sil>"
}

struct PcmI16Stats {
    sample_count: usize,
    non_zero_sample_count: usize,
    rms: f32,
    peak: f32,
}

fn pcm_i16_stats(samples: &[i16]) -> PcmI16Stats {
    let mut sum_sq = 0.0f64;
    let mut peak = 0u16;
    let mut non_zero_sample_count = 0usize;
    for &sample in samples {
        let abs = sample.unsigned_abs();
        if abs > 0 {
            non_zero_sample_count += 1;
        }
        peak = peak.max(abs);
        let normalized = sample as f64 / i16::MAX as f64;
        sum_sq += normalized * normalized;
    }
    let rms = if samples.is_empty() {
        0.0
    } else {
        (sum_sq / samples.len() as f64).sqrt() as f32
    };
    PcmI16Stats {
        sample_count: samples.len(),
        non_zero_sample_count,
        rms,
        peak: peak as f32 / i16::MAX as f32,
    }
}

fn raw_pcm_duration_ms(pcm: &[u8]) -> u64 {
    (pcm.len() as u64 / 2) * 1000 / 16_000
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DictationOutputOperation {
    Polish,
    TranslateToTraditionalChinese,
    TranslateToEnglish,
}

fn dictation_output_operation(prefs: &UserPreferences) -> DictationOutputOperation {
    match prefs.effective_output_language_preference() {
        OutputLanguagePreference::Auto | OutputLanguagePreference::ZhCn => {
            DictationOutputOperation::Polish
        }
        OutputLanguagePreference::ZhTw => DictationOutputOperation::TranslateToTraditionalChinese,
        OutputLanguagePreference::En => DictationOutputOperation::TranslateToEnglish,
        OutputLanguagePreference::Ja | OutputLanguagePreference::Ko => {
            DictationOutputOperation::Polish
        }
    }
}

fn should_stream_polish_insert(
    prefs: &UserPreferences,
    translation_active: bool,
    output_operation: DictationOutputOperation,
    mode: PolishMode,
) -> bool {
    prefs.streaming_insert
        && !translation_active
        && output_operation != DictationOutputOperation::TranslateToEnglish
        && mode == PolishMode::Light
}

#[cfg(target_os = "windows")]
fn tsf_experiment_enabled() -> bool {
    matches!(
        std::env::var("QINGYU_ENABLE_TSF_EXPERIMENT").as_deref(),
        Ok("1")
    )
}

/// 跑流式润色路径（opt-in，跨平台）。
///
/// 平台差异：
/// - **macOS**：`switch_to_ascii` 切到 ABC 输入源（规避 CJK / 日文 IME 拦截 Unicode 事件），
///   session 结束 `restore_input_source` 切回。`type_unicode_chunk` 走 CGEvent FFI。
/// - **Windows**：`switch_to_ascii` 是 no-op（SendInput Unicode 绕过 TSF）；
///   `type_unicode_chunk` 走 `SendInput(KEYEVENTF_UNICODE)`。
/// - **Linux（实验）**：`switch_to_ascii` 是 no-op；`type_unicode_chunk` 走 enigo
///   `Keyboard::text`。X11 / XTest 稳定，Wayland 看 compositor 给不给 libei 权限。
///
/// 通用流程：
/// 1. `switch_to_ascii`（macOS）/ no-op（其他）；失败则降级回一次性 `polish_or_passthrough`。
/// 2. 起一个 `spawn_blocking` 后台任务，从 mpsc 收 SSE delta，逐 delta 调
///    `type_unicode_chunk` 模拟键盘事件落到光标处。串行有序，无竞态。
/// 3. 调 `polish_or_passthrough_streaming`，`on_delta` 把 chunk 塞进 mpsc。
/// 4. 流结束 / 失败 / 取消 → drop mpsc 发送端 → typer 任务 drain 完剩余 delta 退出 →
///    `restore_input_source` 恢复用户原输入源（macOS 才有意义，其他平台 no-op）。
/// 5. 返回 `(polished, polish_error, already_streamed)`：
///    - 成功：`(text, None, true)` — 字符已经在屏幕上，调用方应当跳过 `inserter.insert`
///    - 失败：`(raw_text, Some(reason), false)` — 流式过程出错，调用方走 raw 一次性兜底
///    - 不支持：`run_streaming_polish` 内部直接调 `polish_or_passthrough` 透明降级
///
/// **不在流式路径里做**：`apply_chinese_script_preference` / `apply_correction_rules`
/// 这两步在 v1 跳过 —— 字符已经一边流一边落出去了，不好回退。需要的话只能关 toggle 走
/// 一次性路径。
#[allow(clippy::too_many_arguments)]
async fn run_streaming_polish(
    inner: &Arc<Inner>,
    raw: &RawTranscript,
    mode: PolishMode,
    hotwords: &[String],
    working_languages: &[String],
    chinese_script_preference: crate::types::ChineseScriptPreference,
    output_language_preference: crate::types::OutputLanguagePreference,
    llm_thinking_enabled: bool,
    front_app: Option<&str>,
    prior_turns: &[(String, String)],
) -> (String, Option<String>, bool) {
    log::info!(
        "[coord] streaming_insert path ENTER (raw_chars={})",
        raw.text.chars().count()
    );

    let app = inner.app.lock().clone();
    let Some(app) = app else {
        log::warn!("[coord] streaming_insert: no AppHandle in Inner; fall back to one-shot");
        let (p, e) = polish_or_passthrough(
            raw,
            mode,
            hotwords,
            working_languages,
            chinese_script_preference,
            output_language_preference,
            llm_thinking_enabled,
            front_app,
            prior_turns,
        )
        .await;
        return (p, e, false);
    };

    // 1. 切到 ABC 输入源。失败则降级 —— 流式路径上 CJK IME 拦截不是可恢复错误。
    log::info!("[coord] streaming_insert: switching input source to ABC");
    let prev_ime = match crate::unicode_keystroke::switch_to_ascii(&app).await {
        Ok(prev) => {
            log::info!(
                "[coord] streaming_insert: switched to ABC (had_previous={})",
                prev.is_some()
            );
            prev
        }
        Err(e) => {
            log::warn!(
                "[coord] streaming_insert: switch_to_ascii failed: {e}; fall back to one-shot"
            );
            let (p, err) = polish_or_passthrough(
                raw,
                mode,
                hotwords,
                working_languages,
                chinese_script_preference,
                output_language_preference,
                llm_thinking_enabled,
                front_app,
                prior_turns,
            )
            .await;
            return (p, err, false);
        }
    };

    // 2. 起 typer 后台任务：从 mpsc 收 delta，串行调 type_unicode_chunk。
    // 同时累积 typed_text：屏幕上真正落字的内容，用于（a）SSE 中途失败时让 history
    // 与用户实际看到的内容一致；（b）pr-agent #412 反馈 \"saved output diverges
    // from what the user actually sees\"。
    let (tx, rx) = tokio::sync::mpsc::unbounded_channel::<String>();
    let typer_handle = tokio::task::spawn_blocking(move || {
        let mut rx = rx;
        let mut typed_text = String::new();
        let mut first_failure: Option<String> = None;
        while let Some(delta) = rx.blocking_recv() {
            if first_failure.is_some() {
                // 一旦类型链路出错（如 Secure Input 启用），后续 delta 全部丢弃，但仍
                // 把 mpsc drain 完，避免发送端阻塞。
                continue;
            }
            match crate::unicode_keystroke::type_unicode_chunk(&delta) {
                Ok(()) => {
                    typed_text.push_str(&delta);
                }
                Err(e) => {
                    log::error!(
                        "[coord] streaming_insert: type_unicode_chunk failed at typed={} chars: {e}; \
                         dropping remaining deltas",
                        typed_text.chars().count()
                    );
                    first_failure = Some(e.to_string());
                }
            }
        }
        (typed_text, first_failure)
    });

    // 3. 调流式润色，on_delta 塞 mpsc；should_cancel 检查 dictation 取消旗。
    emit_capsule(
        inner,
        CapsuleState::Polishing,
        0.0,
        raw.duration_ms,
        Some("流式接收中".to_string()),
        None,
    );
    let inner_for_cancel = Arc::clone(inner);
    let should_cancel = move || inner_for_cancel.state.lock().cancelled;
    let outcome = super::polish_or_passthrough_streaming(
        raw,
        mode,
        hotwords,
        working_languages,
        chinese_script_preference,
        output_language_preference,
        llm_thinking_enabled,
        front_app,
        prior_turns,
        move |delta: &str| {
            let _ = tx.send(delta.to_string());
        },
        should_cancel,
    )
    .await;
    // tx 已经被 move 进 on_delta 闭包；闭包随 polish_or_passthrough_streaming 返回
    // 而 drop，typer 那侧 blocking_recv 拿到 None 自然退出。

    // 4. 等 typer 把缓冲 drain 完，拿到实际落字的全文 + 第一条失败原因。
    let (typed_text, typer_failure) = typer_handle.await.unwrap_or_else(|e| {
        log::error!("[coord] streaming_insert: typer task join failed: {e}");
        (String::new(), Some(format!("typer join: {e}")))
    });
    let typed_chars = typed_text.chars().count();
    log::info!("[coord] streaming_insert: typer drained, typed {typed_chars} chars");

    // 5. 无论流是否成功，都恢复用户原输入源。
    log::info!("[coord] streaming_insert: restoring input source");
    if let Err(e) = crate::unicode_keystroke::restore_input_source(&app, prev_ime).await {
        log::warn!("[coord] streaming_insert: restore_input_source failed: {e}");
    } else {
        log::info!("[coord] streaming_insert: input source restored");
    }

    // 6. 把 outcome 翻译成 (polished, polish_error, already_streamed)。
    match outcome {
        super::StreamingPolishOutcome::Streamed(text) => {
            log::info!(
                "[coord] streaming_insert SUCCESS: polished_chars={} typed_chars={} typer_err={:?}",
                text.chars().count(),
                typed_chars,
                typer_failure
            );
            // 边界 case：polish 成功但 typer 在第一字就失败（最常见：session 开始时
            // 已处于 Secure Input；或 SendInput / enigo 拒绝）。屏幕上一字未见，
            // already_streamed=true 会让上层跳过 inserter，最终用户看不到任何内容。
            // 这里显式回退到一次性兜底，让正常 inserter 路径写出 polish 结果。
            // pr-agent #412 反馈 \"Missing fallback\"。
            if typed_chars == 0 {
                if let Some(reason) = typer_failure {
                    log::warn!(
                        "[coord] streaming_insert: zero chars typed despite polish success ({reason}); falling back to one-shot inserter"
                    );
                    return (text, Some(reason), false);
                }
            }
            // 先确定 final_text —— typer 中途失败时屏幕只有 typed_text 这一段，
            // history 记完整 polish 反而会让用户复盘困惑。让 history / clipboard /
            // 后续逻辑统统用 final_text，三处保持一致。
            // pr-agent #412 反馈 \"Clipboard Mismatch\"：之前先写 text 到剪贴板再
            // 决定 typer 是否中途失败，导致 Cmd+V 粘出用户屏幕上没见过的内容。
            let (final_text, polish_err) = match typer_failure {
                Some(e) => (typed_text, Some(format!("typing partially failed: {e}"))),
                None => (text, None),
            };
            // 把 final_text 写回剪贴板（默认 on，可关）。一次性路径天然走剪贴板，
            // 开关默认对齐一次性行为，让 Cmd+V 重复粘贴可用。
            if inner.prefs.get().streaming_insert_save_clipboard {
                match arboard::Clipboard::new() {
                    Ok(mut cb) => match cb.set_text(final_text.clone()) {
                        Ok(()) => log::info!(
                            "[coord] streaming_insert: final text written to clipboard ({} chars)",
                            final_text.chars().count()
                        ),
                        Err(e) => {
                            log::warn!("[coord] streaming_insert: clipboard set_text failed: {e}")
                        }
                    },
                    Err(e) => {
                        log::warn!("[coord] streaming_insert: clipboard handle init failed: {e}")
                    }
                }
            } else {
                log::info!("[coord] streaming_insert: clipboard save skipped (pref off)");
            }
            (final_text, polish_err, true)
        }
        super::StreamingPolishOutcome::UnsupportedFallback => {
            log::info!(
                "[coord] streaming_insert: dispatch reported unsupported, fall back to one-shot"
            );
            let (p, e) = polish_or_passthrough(
                raw,
                mode,
                hotwords,
                working_languages,
                chinese_script_preference,
                output_language_preference,
                llm_thinking_enabled,
                front_app,
                prior_turns,
            )
            .await;
            (p, e, false)
        }
        super::StreamingPolishOutcome::Failed(reason) => {
            log::warn!(
                "[coord] streaming_insert FAILED: {reason}; typed {typed_chars} chars before failure"
            );
            // 流式失败但已经流了一部分 chars：用户屏幕上有半截 polish。history 应当
            // 跟屏幕一致 —— 记 typed_text 而不是 raw.text，否则保存内容跟用户看见的
            // 内容会分叉（pr-agent #412 \"Wrong final text\" 反馈）。
            // 一字都没流时 typed_text 是空串，回到 raw 一次性兜底。
            if typed_chars > 0 {
                (
                    typed_text,
                    Some(format!(
                        "streaming polish failed mid-stream after {typed_chars} chars: {reason}"
                    )),
                    true,
                )
            } else {
                (raw.text.clone(), Some(reason), false)
            }
        }
    }
}

pub(super) async fn handle_pressed_edge(inner: &Arc<Inner>) {
    let was_held = inner.hotkey_trigger_held.swap(true, Ordering::SeqCst);
    if !was_held {
        // 防抖：相邻 < HOTKEY_DEBOUNCE 的边沿直接丢弃，记到 log 方便排查。
        // 与 `hotkey_trigger_held` 互补：held 防 press-without-release，本检查防
        // press-release-press 三连过快。每个有效边沿都会更新时间戳。
        let now = std::time::Instant::now();
        let too_soon = {
            let mut last = inner.last_hotkey_dispatch_at.lock();
            let drop = matches!(*last, Some(t) if now.duration_since(t) < HOTKEY_DEBOUNCE);
            if !drop {
                *last = Some(now);
            }
            drop
        };
        if too_soon {
            log::info!(
                "[coord] hotkey pressed edge debounced (< {} ms since last dispatch)",
                HOTKEY_DEBOUNCE.as_millis()
            );
            return;
        }

        // 路由：QA 浮窗可见时，rightOption 边沿走 QA；否则走主听写。详见 issue #118 v2。
        // 例外：dictation session 已经在跑（Starting / Listening / Processing / Inserting），
        // 即使 QA 浮窗被打开了，这条边沿也必须先走 dictation。否则 begin_qa_session 会
        // 第二次抢同一个麦克风 device —— 在 Linux/PipeWire 上甚至会成功打开两路捕获，
        // dictation 的 recorder 没人停；在 macOS/Windows 上 cpal 会拒绝第二次 build_input_stream
        // 但 dictation session 仍在跑、用户找不到从 QA 面板停掉它的入口。审计 3.3.1。
        let dictation_active = !matches!(inner.state.lock().phase, SessionPhase::Idle);
        let panel_visible = inner.qa_state.lock().panel_visible;
        if panel_visible && !dictation_active {
            handle_qa_option_edge(inner).await;
        } else {
            handle_pressed(inner).await;
        }
    }
}

pub(super) async fn handle_pressed(inner: &Arc<Inner>) {
    let mode = inner.prefs.get().hotkey.mode;
    let phase = inner.state.lock().phase;
    log::info!("[coord] hotkey pressed (mode={mode:?}, phase={phase:?})");
    match (mode, phase) {
        (HotkeyMode::Toggle, SessionPhase::Idle) => {
            let _ = begin_session(inner).await;
        }
        (HotkeyMode::Toggle, SessionPhase::Listening) => {
            let _ = end_session(inner).await;
        }
        (HotkeyMode::Hold, SessionPhase::Idle) => {
            let _ = begin_session(inner).await;
        }
        // Toggle 模式 Starting 阶段第二次按 → 用户想停。
        // 不能直接 end_session（ASR session 还没建好），存边沿，握手完成后立即触发。
        (HotkeyMode::Toggle, SessionPhase::Starting) => {
            request_stop_during_starting(inner, "toggle stop edge");
        }
        _ => {}
    }
}

pub(super) async fn handle_released_edge(inner: &Arc<Inner>) {
    let was_held = inner.hotkey_trigger_held.swap(false, Ordering::SeqCst);
    if was_held {
        // QA 浮窗可见时，Option 行为是 press-toggle（不分 hold/release），release 边沿忽略。
        // 与 handle_pressed_edge 的路由对称：dictation session 在跑时 Pressed 已经被路由到
        // dictation，那 Released 必须也路由到 dictation —— 否则 Hold 模式松开热键时
        // end_session 不会触发，dictation 永远停不下来。审计 3.3.1。
        let dictation_active = !matches!(inner.state.lock().phase, SessionPhase::Idle);
        let panel_visible = inner.qa_state.lock().panel_visible;
        if panel_visible && !dictation_active {
            return;
        }
        handle_released(inner).await;
    }
}

pub(super) async fn handle_released(inner: &Arc<Inner>) {
    let mode = inner.prefs.get().hotkey.mode;
    let phase = inner.state.lock().phase;
    log::info!("[coord] hotkey released (mode={mode:?}, phase={phase:?})");
    if mode == HotkeyMode::Hold {
        match phase {
            SessionPhase::Listening => {
                let _ = end_session(inner).await;
            }
            // Hold 模式 Starting 阶段松开 → 用户想停。同上：握手完成后再 end。
            SessionPhase::Starting => {
                request_stop_during_starting(inner, "hold release edge");
            }
            _ => {}
        }
    }
}

pub(super) fn request_stop_during_starting(inner: &Arc<Inner>, reason: &str) {
    {
        let mut state = inner.state.lock();
        if !request_stop_during_starting_state(&mut state) {
            return;
        }
    }
    log::info!("[coord] {reason} during Starting — queued");
    stop_recorder_if_pending_start_stop(inner);
}

fn qingyu_local_asr_readiness_error(
    status: &crate::asr::qingyu::QingyuAsrStatus,
) -> Option<String> {
    if status.model_state != crate::asr::qingyu::QingyuAsrModelState::Installed {
        return Some(match status.error.as_deref() {
            Some(error) => format!("本地语音模型未就绪: {error}"),
            None => "本地语音模型未安装，请先在本地语音页面完成模型安装".to_string(),
        });
    }
    if !status.vad_available {
        return Some("本地语音 VAD 模型缺失，请修复或重新安装本地语音模型".to_string());
    }
    None
}

pub(super) async fn begin_session(inner: &Arc<Inner>) -> Result<(), String> {
    let current_session_id = {
        let mut state = inner.state.lock();
        let Some(session_id) =
            begin_session_state(&mut state, capture_focus_target(), capture_frontmost_app())
        else {
            return Ok(());
        };
        if let Some(label) = state.front_app.as_deref() {
            log::info!("[coord] front_app captured: {label}");
        }
        session_id
    };
    #[cfg(target_os = "windows")]
    {
        if tsf_experiment_enabled() {
            let prepared = inner.windows_ime.prepare_session();
            let mut slots = inner.prepared_windows_ime_session.lock();
            store_prepared_windows_ime_session(&mut slots, current_session_id, prepared);
        }
    }
    // 翻译模式标志重置；hotkey 监听器在 Shift down 时再 set true。
    inner
        .translation_modifier_seen
        .store(false, Ordering::SeqCst);

    #[cfg(any(debug_assertions, test))]
    if hotkey_injection_dry_run_enabled() {
        emit_capsule(inner, CapsuleState::Recording, 0.0, 0, None, None);
        inner.state.lock().phase = SessionPhase::Listening;
        log::info!("[coord] session started (hotkey-injection dry-run)");
        return Ok(());
    }

    let active_asr = CredentialsVault::get_active_asr();

    if let Err(message) = ensure_asr_credentials() {
        log::warn!("[coord] ASR credential gate failed: {message}");
        append_begin_asr_error_trace(inner, current_session_id, &active_asr, message.clone());
        emit_capsule(
            inner,
            CapsuleState::Error,
            0.0,
            0,
            Some(message.clone()),
            None,
        );
        restore_prepared_windows_ime_session(inner, current_session_id);
        inner.state.lock().phase = SessionPhase::Idle;
        return Err(message);
    }

    if let Err(message) = ensure_microphone_permission(inner) {
        log::warn!("[coord] microphone permission gate failed: {message}");
        append_begin_recorder_error_trace(inner, current_session_id, &active_asr, message.clone());
        emit_capsule(
            inner,
            CapsuleState::Error,
            0.0,
            0,
            Some(message.clone()),
            None,
        );
        restore_prepared_windows_ime_session(inner, current_session_id);
        inner.state.lock().phase = SessionPhase::Idle;
        schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
        return Err(message);
    }

    // 不在这里 emit Recording capsule —— 让 start_recorder_for_starting 在
    // Recorder::start 成功后再发，确保「用户看到录音条」时 mic 已经在 capture。
    // 之前在这一行就 emit 会让用户看到录音条后立刻开口，但 mic 还在 cpal init
    // 窗口（50-200ms）内 → 开头几个字物理上录不到。详见 issue 备注。
    if active_asr == crate::product::LOCAL_ASR_PROVIDER_ID {
        let status = inner.qingyu_local_asr.status();
        if let Some(message) = qingyu_local_asr_readiness_error(&status) {
            log::warn!("[coord] Qingyu local ASR readiness gate failed: {message}");
            append_begin_asr_error_trace(inner, current_session_id, &active_asr, message.clone());
            emit_capsule(
                inner,
                CapsuleState::Error,
                0.0,
                0,
                Some(message.clone()),
                None,
            );
            restore_prepared_windows_ime_session(inner, current_session_id);
            inner.state.lock().phase = SessionPhase::Idle;
            schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
            return Err(message);
        }

        let buffer = Arc::new(BufferedPcmConsumer::new());
        store_asr_for_session(
            inner,
            current_session_id,
            ActiveAsr::QingyuLocal(Arc::clone(&buffer)),
        );
        let consumer: Arc<dyn crate::recorder::AudioConsumer> = buffer;
        start_recorder_and_enter_listening(inner, current_session_id, &active_asr, consumer)
            .await
            .map_err(|error| {
                append_begin_recorder_error_trace(
                    inner,
                    current_session_id,
                    &active_asr,
                    error.clone(),
                );
                error
            })?;
        return Ok(());
    }

    #[cfg(target_os = "windows")]
    if foundry::is_foundry_local_whisper(&active_asr) {
        let prefs = inner.prefs.get();
        let model_alias = if foundry::model_alias_is_known(&prefs.foundry_local_asr_model) {
            prefs.foundry_local_asr_model.clone()
        } else {
            foundry::DEFAULT_MODEL_ALIAS.to_string()
        };
        let language_hint = prefs.foundry_local_asr_language_hint.trim().to_string();
        let language_hint = if language_hint.is_empty() {
            None
        } else {
            Some(language_hint)
        };
        let local = Arc::new(FoundryLocalWhisperAsr::new(
            Arc::clone(&inner.foundry_local_runtime),
            model_alias,
            prefs.foundry_local_runtime_source.clone(),
            language_hint,
        ));
        store_asr_for_session(
            inner,
            current_session_id,
            ActiveAsr::FoundryLocalWhisper(Arc::clone(&local)),
        );
        let consumer: Arc<dyn crate::recorder::AudioConsumer> = local;
        start_recorder_and_enter_listening(inner, current_session_id, &active_asr, consumer)
            .await
            .map_err(|error| {
                append_begin_recorder_error_trace(
                    inner,
                    current_session_id,
                    &active_asr,
                    error.clone(),
                );
                error
            })?;
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    if crate::asr::local::is_local_qwen3(&active_asr) {
        let local = match build_local_qwen3(inner).await {
            Ok(l) => l,
            Err(e) => {
                log::error!("[coord] 本地 Qwen3-ASR 初始化失败: {e:#}");
                append_begin_asr_error_trace(
                    inner,
                    current_session_id,
                    &active_asr,
                    format!("local ASR init failed: {e:#}"),
                );
                emit_capsule(
                    inner,
                    CapsuleState::Error,
                    0.0,
                    0,
                    Some(format!("本地模型初始化失败: {e}")),
                    None,
                );
                restore_prepared_windows_ime_session(inner, current_session_id);
                inner.state.lock().phase = SessionPhase::Idle;
                schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                return Err(format!("local ASR init failed: {e}"));
            }
        };
        store_asr_for_session(
            inner,
            current_session_id,
            ActiveAsr::Local(Arc::clone(&local)),
        );
        let consumer: Arc<dyn crate::recorder::AudioConsumer> = local;
        start_recorder_and_enter_listening(inner, current_session_id, &active_asr, consumer)
            .await
            .map_err(|error| {
                append_begin_recorder_error_trace(
                    inner,
                    current_session_id,
                    &active_asr,
                    error.clone(),
                );
                error
            })?;
        return Ok(());
    }

    if is_qwen_realtime_provider(&active_asr) {
        let asr = Arc::new(QwenRealtimeASR::new(read_qwen_realtime_credentials()));
        let bridge = Arc::new(DeferredAsrBridge::new());
        let consumer: Arc<dyn crate::recorder::AudioConsumer> = bridge.clone();
        store_asr_for_session(
            inner,
            current_session_id,
            ActiveAsr::QwenRealtime(Arc::clone(&asr)),
        );
        start_recorder_for_starting(inner, current_session_id, &active_asr, consumer)
            .await
            .map_err(|error| {
                append_begin_recorder_error_trace(
                    inner,
                    current_session_id,
                    &active_asr,
                    error.clone(),
                );
                error
            })?;

        if let Err(e) = asr.open_session().await {
            log::error!("[coord] open Qwen realtime ASR session failed: {e}");
            match startup_race_status_for_starting(inner, current_session_id) {
                StartupRaceStatus::StaleContinuation => {
                    log::info!(
                        "[coord] stale Qwen realtime ASR open_session error from session {current_session_id} — ignoring"
                    );
                    asr.cancel();
                    discard_startup_resources_for_session(inner, current_session_id);
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    return Ok(());
                }
                StartupRaceStatus::CancelRaced => {
                    asr.cancel();
                    discard_startup_resources_for_session(inner, current_session_id);
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    set_phase_idle_if_session_matches(inner, current_session_id);
                    return Ok(());
                }
                StartupRaceStatus::ActiveStarting => {
                    asr.cancel();
                }
            }
            append_begin_asr_error_trace(
                inner,
                current_session_id,
                &active_asr,
                format!("open Qwen realtime ASR session failed: {e}"),
            );
            discard_startup_resources_for_session(inner, current_session_id);
            emit_capsule(
                inner,
                CapsuleState::Error,
                0.0,
                0,
                Some(format!("ASR 连接失败: {e}")),
                None,
            );
            restore_prepared_windows_ime_session(inner, current_session_id);
            set_phase_idle_if_session_matches(inner, current_session_id);
            schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
            return Err(e.to_string());
        }
        match startup_race_status_for_starting(inner, current_session_id) {
            StartupRaceStatus::ActiveStarting => {}
            StartupRaceStatus::CancelRaced => {
                log::info!(
                    "[coord] cancel raced during Qwen realtime ASR open_session — aborting begin"
                );
                asr.cancel();
                discard_startup_resources_for_session(inner, current_session_id);
                restore_prepared_windows_ime_session(inner, current_session_id);
                set_phase_idle_if_session_matches(inner, current_session_id);
                return Ok(());
            }
            StartupRaceStatus::StaleContinuation => {
                log::info!(
                    "[coord] stale Qwen realtime ASR open_session continuation from session {current_session_id} — ignoring"
                );
                asr.cancel();
                discard_startup_resources_for_session(inner, current_session_id);
                restore_prepared_windows_ime_session(inner, current_session_id);
                return Ok(());
            }
        }
        let target: Arc<dyn crate::asr::AudioConsumer> = asr;
        let flushed_bytes = bridge.attach(target);
        log::info!(
            "[coord] Qwen realtime ASR connected; flushed {flushed_bytes} deferred audio bytes"
        );
        finish_starting_session(inner, current_session_id).await;
    } else if is_bailian_provider(&active_asr) {
        let asr = Arc::new(BailianRealtimeASR::new(read_bailian_credentials()));
        let bridge = Arc::new(DeferredAsrBridge::new());
        let consumer: Arc<dyn crate::recorder::AudioConsumer> = bridge.clone();
        store_asr_for_session(
            inner,
            current_session_id,
            ActiveAsr::Bailian(Arc::clone(&asr)),
        );
        start_recorder_for_starting(inner, current_session_id, &active_asr, consumer)
            .await
            .map_err(|error| {
                append_begin_recorder_error_trace(
                    inner,
                    current_session_id,
                    &active_asr,
                    error.clone(),
                );
                error
            })?;

        if let Err(e) = asr.open_session().await {
            log::error!("[coord] open Bailian ASR session failed: {e}");
            match startup_race_status_for_starting(inner, current_session_id) {
                StartupRaceStatus::StaleContinuation => {
                    log::info!(
                        "[coord] stale Bailian ASR open_session error from session {current_session_id} — ignoring"
                    );
                    asr.cancel();
                    discard_startup_resources_for_session(inner, current_session_id);
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    return Ok(());
                }
                StartupRaceStatus::CancelRaced => {
                    asr.cancel();
                    discard_startup_resources_for_session(inner, current_session_id);
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    set_phase_idle_if_session_matches(inner, current_session_id);
                    return Ok(());
                }
                StartupRaceStatus::ActiveStarting => {
                    asr.cancel();
                }
            }
            append_begin_asr_error_trace(
                inner,
                current_session_id,
                &active_asr,
                format!("open Bailian ASR session failed: {e}"),
            );
            discard_startup_resources_for_session(inner, current_session_id);
            emit_capsule(
                inner,
                CapsuleState::Error,
                0.0,
                0,
                Some(format!("ASR 连接失败: {e}")),
                None,
            );
            restore_prepared_windows_ime_session(inner, current_session_id);
            set_phase_idle_if_session_matches(inner, current_session_id);
            schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
            return Err(e.to_string());
        }
        match startup_race_status_for_starting(inner, current_session_id) {
            StartupRaceStatus::ActiveStarting => {}
            StartupRaceStatus::CancelRaced => {
                log::info!("[coord] cancel raced during Bailian ASR open_session — aborting begin");
                asr.cancel();
                discard_startup_resources_for_session(inner, current_session_id);
                restore_prepared_windows_ime_session(inner, current_session_id);
                set_phase_idle_if_session_matches(inner, current_session_id);
                return Ok(());
            }
            StartupRaceStatus::StaleContinuation => {
                log::info!(
                    "[coord] stale Bailian ASR open_session continuation from session {current_session_id} — ignoring"
                );
                asr.cancel();
                discard_startup_resources_for_session(inner, current_session_id);
                restore_prepared_windows_ime_session(inner, current_session_id);
                return Ok(());
            }
        }
        let target: Arc<dyn crate::asr::AudioConsumer> = asr;
        let flushed_bytes = bridge.attach(target);
        log::info!("[coord] Bailian ASR connected; flushed {flushed_bytes} deferred audio bytes");
        finish_starting_session(inner, current_session_id).await;
    } else if is_whisper_compatible_provider(&active_asr) {
        let (api_key, base_url, model) = read_whisper_credentials();
        // 用户辞書の有効フレーズを Whisper の `prompt` に流し込む。固有名詞や
        // 専門用語の同音・近形誤認識を ASR 段階で抑える。Polish LLM 側には
        // 既に system prompt として注入済みだが、Whisper 出力が大きく崩れる
        // と Polish でも救えない（特に CJK で顕著）。Volcengine ASR は元々
        // hotword を受け取っており、UI 説明文も「ASR ホットワードと後処理
        // モデルのコンテキスト両方に渡される」と明示しているので、Whisper
        // 互換プロバイダにも揃えるのが筋。
        let whisper_prompt =
            crate::asr::whisper::build_prompt_from_phrases(&enabled_phrases(inner));
        let whisper = Arc::new(WhisperBatchASR::new(
            api_key,
            base_url,
            model,
            whisper_prompt,
        ));
        store_asr_for_session(
            inner,
            current_session_id,
            ActiveAsr::Whisper(Arc::clone(&whisper)),
        );
        let consumer: Arc<dyn crate::recorder::AudioConsumer> = whisper;
        start_recorder_and_enter_listening(inner, current_session_id, &active_asr, consumer)
            .await
            .map_err(|error| {
                append_begin_recorder_error_trace(
                    inner,
                    current_session_id,
                    &active_asr,
                    error.clone(),
                );
                error
            })?;
    } else if active_asr == crate::product::DOUBAO_ASR_PROVIDER_ID {
        let hotwords = enabled_hotwords(inner);
        let creds = read_volc_credentials();
        let asr = Arc::new(VolcengineStreamingASR::new(creds, hotwords));
        let bridge = Arc::new(DeferredAsrBridge::new());
        let consumer: Arc<dyn crate::recorder::AudioConsumer> = bridge.clone();
        store_asr_for_session(
            inner,
            current_session_id,
            ActiveAsr::Volcengine(Arc::clone(&asr)),
        );
        start_recorder_for_starting(inner, current_session_id, &active_asr, consumer)
            .await
            .map_err(|error| {
                append_begin_recorder_error_trace(
                    inner,
                    current_session_id,
                    &active_asr,
                    error.clone(),
                );
                error
            })?;
        open_volcengine_after_recorder_started(inner, current_session_id, asr, bridge).await?;
    } else {
        let message = format!("Unsupported ASR provider: {active_asr}");
        append_begin_asr_error_trace(inner, current_session_id, &active_asr, message.clone());
        emit_capsule(
            inner,
            CapsuleState::Error,
            0.0,
            0,
            Some(message.clone()),
            None,
        );
        restore_prepared_windows_ime_session(inner, current_session_id);
        set_phase_idle_if_session_matches(inner, current_session_id);
        schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
        return Err(message);
    }

    Ok(())
}

async fn open_volcengine_after_recorder_started(
    inner: &Arc<Inner>,
    current_session_id: SessionId,
    asr: Arc<VolcengineStreamingASR>,
    bridge: Arc<DeferredAsrBridge>,
) -> Result<(), String> {
    if let Err(e) = asr.open_session().await {
        log::error!("[coord] open Doubao ASR session failed: {e}");
        match startup_race_status_for_starting(inner, current_session_id) {
            StartupRaceStatus::StaleContinuation => {
                log::info!(
                    "[coord] stale Doubao ASR open_session error from session {current_session_id} — ignoring"
                );
                asr.cancel();
                discard_startup_resources_for_session(inner, current_session_id);
                restore_prepared_windows_ime_session(inner, current_session_id);
                return Ok(());
            }
            StartupRaceStatus::CancelRaced => {
                asr.cancel();
                discard_startup_resources_for_session(inner, current_session_id);
                restore_prepared_windows_ime_session(inner, current_session_id);
                set_phase_idle_if_session_matches(inner, current_session_id);
                return Ok(());
            }
            StartupRaceStatus::ActiveStarting => {}
        }
        append_begin_asr_error_trace(
            inner,
            current_session_id,
            crate::product::DOUBAO_ASR_PROVIDER_ID,
            format!("open Doubao ASR session failed: {e}"),
        );
        discard_startup_resources_for_session(inner, current_session_id);
        emit_capsule(
            inner,
            CapsuleState::Error,
            0.0,
            0,
            Some(format!("ASR 连接失败: {e}")),
            None,
        );
        restore_prepared_windows_ime_session(inner, current_session_id);
        set_phase_idle_if_session_matches(inner, current_session_id);
        schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
        return Err(e.to_string());
    }
    // open_session.await 期间用户可能按了 Esc / 改变心意。如果 cancel_session
    // 已触发（cancelled=true 或 phase 被改回 Idle），别再装 ASR，直接善后。
    // audit HIGH #1。
    match startup_race_status_for_starting(inner, current_session_id) {
        StartupRaceStatus::ActiveStarting => {}
        StartupRaceStatus::CancelRaced => {
            log::info!("[coord] cancel raced during Doubao ASR open_session — aborting begin");
            asr.cancel();
            discard_startup_resources_for_session(inner, current_session_id);
            restore_prepared_windows_ime_session(inner, current_session_id);
            set_phase_idle_if_session_matches(inner, current_session_id);
            return Ok(());
        }
        StartupRaceStatus::StaleContinuation => {
            log::info!(
                "[coord] stale Doubao ASR open_session continuation from session {current_session_id} — ignoring"
            );
            asr.cancel();
            discard_startup_resources_for_session(inner, current_session_id);
            restore_prepared_windows_ime_session(inner, current_session_id);
            return Ok(());
        }
    }
    let target: Arc<dyn crate::asr::AudioConsumer> = asr;
    let flushed_bytes = bridge.attach(target);
    log::info!("[coord] Doubao ASR connected; flushed {flushed_bytes} deferred audio bytes");
    finish_starting_session(inner, current_session_id).await;
    Ok(())
}

pub(super) async fn start_recorder_for_starting(
    inner: &Arc<Inner>,
    session_id: SessionId,
    active_asr: &str,
    consumer: Arc<dyn crate::recorder::AudioConsumer>,
) -> Result<(), String> {
    let inner_for_level = Arc::clone(inner);
    // 节流：电平回调本身约 185 Hz（cpal 默认音频块），全部转发到前端会让 CSS
    // transition 互相覆盖、视觉上"被平均"成静止。限制为 ~30 Hz（33ms 最少间隔），
    // 配合 CSS 短 transition 让每次 emit 完整可见。
    let last_emit_at = Arc::new(Mutex::new(None::<Instant>));
    const LEVEL_EMIT_MIN_INTERVAL_MS: u64 = 33;
    let level_handler: Arc<dyn Fn(f32) + Send + Sync> = Arc::new(move |level| {
        let phase = inner_for_level.state.lock().phase;
        if phase != SessionPhase::Listening && phase != SessionPhase::Starting {
            return;
        }
        let now = Instant::now();
        {
            let mut last = last_emit_at.lock();
            if let Some(prev) = *last {
                if now.duration_since(prev).as_millis() < LEVEL_EMIT_MIN_INTERVAL_MS as u128 {
                    return;
                }
            }
            *last = Some(now);
        }
        let elapsed = inner_for_level
            .state
            .lock()
            .started_at
            .elapsed()
            .as_millis() as u64;
        emit_capsule(
            &inner_for_level,
            CapsuleState::Recording,
            level,
            elapsed,
            None,
            None,
        );
    });

    let microphone_device_name = selected_microphone_device_name(inner);
    stop_microphone_preview_monitor(inner, "dictation recorder");
    acquire_recording_mute(inner, "dictation").await;
    let recorder_probe = Arc::new(DiagnosticRecorderProbe::new(
        consumer,
        microphone_device_name.clone(),
    ));
    let recorder_consumer: Arc<dyn crate::recorder::AudioConsumer> = recorder_probe.clone();
    match Recorder::start(microphone_device_name, recorder_consumer, level_handler) {
        Ok((rec, runtime_errors)) => {
            store_recorder_for_session(inner, session_id, rec);
            store_recorder_diagnostics_for_session(inner, session_id, recorder_probe);
            spawn_recorder_error_monitor(inner, runtime_errors);
            // 不在这里 emit Recording capsule。
            // Recorder::start Ok 仅代表 cpal Stream::play 完成，不代表 audio
            // 线程已经在向 consumer 推 PCM —— macOS CoreAudio AudioUnit 启动到
            // 第一帧 process_callback 中间有 50–200 ms 间隙（Windows 类似）。
            // 之前在这里立即 emit Recording 会让用户「看到录音条」就开口，但前几个
            // 字落在 cpal init 窗口里被吞，反映为短录音漏首字（用户报告）。
            //
            // 现改为：level_handler 第一次被触发时才 emit Recording capsule。
            // recorder.rs::process_callback 的顺序是 consume_pcm_chunk → level_handler，
            // 所以 level_handler 第一次执行 == PCM 已经真实流到 consumer。从这一刻
            // 起用户说什么都被录到。capsule 自然就晚 50–200 ms 出现，但出现 ==
            // mic 真的在录，匹配「麦先录、UI 再弹」的预期。
            //
            // 原本的竞态保护交还给两条已有路径：
            //   - stop_recorder_if_pending_start_stop：短按时把 capsule 切到
            //     Transcribing；recorder 已 stop，level_handler 不会再发火。
            //   - level_handler 内部 phase 检查：cancel / 错误使 phase 不在
            //     {Starting, Listening} 时直接 return，不会在错误状态上盖
            //     Recording。
            stop_recorder_if_pending_start_stop(inner);
            log::info!("[coord] recorder started (asr={active_asr}, phase=Starting)");
        }
        Err(e) => {
            log::error!("[coord] recorder start failed: {e}");
            cancel_asr_for_session(inner, session_id);
            emit_capsule(
                inner,
                CapsuleState::Error,
                0.0,
                0,
                Some(format!("录音启动失败: {e}")),
                None,
            );
            restore_prepared_windows_ime_session(inner, session_id);
            release_recording_mute(inner, "dictation");
            inner.state.lock().phase = SessionPhase::Idle;
            schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
            return Err(e.to_string());
        }
    }

    Ok(())
}

pub(super) fn spawn_recorder_error_monitor(inner: &Arc<Inner>, rx: mpsc::Receiver<RecorderError>) {
    // 捕获当前 session_id：err 来时若 id 已经不一致说明是上一 session 的迟到事件，
    // 不能去 abort 当前 active 的新 session（它录得好好的）。
    let captured_session_id = inner.state.lock().session_id;
    let inner = Arc::clone(inner);
    std::thread::Builder::new()
        .name("openless-recorder-error-monitor".into())
        .spawn(move || {
            if let Ok(err) = rx.recv() {
                let current_session_id = inner.state.lock().session_id;
                if captured_session_id != current_session_id {
                    log::warn!(
                        "[coord] recorder error from stale session {} dropped (current={}, err={})",
                        captured_session_id,
                        current_session_id,
                        err
                    );
                    return;
                }
                log::error!("[coord] recorder runtime error: {err}");
                abort_recording_with_error(&inner, format!("录音中断: {err}"));
            }
        })
        .ok();
}

pub(super) fn abort_recording_with_error(inner: &Arc<Inner>, message: String) {
    let Some(abort) = ({
        let mut state = inner.state.lock();
        begin_recording_abort_before_restore(&mut state)
    }) else {
        return;
    };

    append_runtime_recorder_error_trace(inner, abort.session_id, message.clone());
    discard_startup_resources_for_session(inner, abort.session_id);
    restore_prepared_windows_ime_session(inner, abort.session_id);
    {
        let mut state = inner.state.lock();
        publish_abort_idle_after_restore(&mut state, abort.session_id);
    }

    emit_capsule(
        inner,
        CapsuleState::Error,
        0.0,
        abort.elapsed,
        Some(message),
        None,
    );
    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
}

pub(super) async fn start_recorder_and_enter_listening(
    inner: &Arc<Inner>,
    session_id: SessionId,
    active_asr: &str,
    consumer: Arc<dyn crate::recorder::AudioConsumer>,
) -> Result<(), String> {
    start_recorder_for_starting(inner, session_id, active_asr, consumer).await?;
    finish_starting_session(inner, session_id).await;
    Ok(())
}

pub(super) async fn finish_starting_session(inner: &Arc<Inner>, session_id: SessionId) {
    // audit HIGH #1：转 Listening 之前在同一 lock 内检查 cancel race。
    // 之前是无条件 phase=Listening，会把 cancel_session 在 await 期间设的 Idle
    // 反向覆盖回 Listening → 用户的 cancel 边沿被吞掉。
    let outcome = {
        let mut state = inner.state.lock();
        finish_starting_session_state(&mut state, session_id)
    };
    match outcome {
        BeginOutcome::StaleContinuation => {
            log::info!(
                "[coord] stale recorder/ASR startup continuation from session {session_id} — ignoring"
            );
            discard_startup_resources_for_session(inner, session_id);
            restore_prepared_windows_ime_session(inner, session_id);
        }
        BeginOutcome::CancelRaced => {
            log::info!("[coord] cancel raced during recorder/ASR startup — aborting begin");
            discard_startup_resources_for_session(inner, session_id);
            restore_prepared_windows_ime_session(inner, session_id);
            set_phase_idle_if_session_matches(inner, session_id);
        }
        BeginOutcome::Started | BeginOutcome::PendingStop => {
            log::info!("[coord] session started");
            if matches!(outcome, BeginOutcome::PendingStop) {
                log::info!("[coord] applying pending_stop edge → end_session immediately");
                let _ = end_session(inner).await;
            }
        }
    }
}

pub(super) async fn end_session(inner: &Arc<Inner>) -> Result<(), String> {
    let current_session_id = {
        let mut state = inner.state.lock();
        let Some(session_id) = start_processing_if_listening(&mut state) else {
            return Ok(());
        };
        session_id
    };

    let elapsed = inner.state.lock().started_at.elapsed().as_millis() as u64;
    let asr_provider_id = CredentialsVault::get_active_asr();
    let llm_provider_id = CredentialsVault::get_active_llm();
    let trace_prefs = inner.prefs.get();
    let trace_front_app = inner.state.lock().front_app.clone();
    let mut diagnostic_trace = new_dictation_trace(
        Uuid::new_v4().to_string(),
        trace_prefs.default_mode,
        trace_prefs.hotkey.mode,
        trace_front_app,
        asr_provider_id.clone(),
        llm_provider_id.clone(),
    );
    diagnostic_trace.session.released_at = Some(Utc::now().to_rfc3339());
    emit_capsule(
        inner,
        CapsuleState::Transcribing,
        0.0,
        elapsed,
        Some("正在识别".to_string()),
        None,
    );

    if let Some(rec) = take_recorder_for_session(inner, current_session_id) {
        rec.stop();
        release_recording_mute(inner, "dictation");
    }
    if let Some(probe) = take_recorder_diagnostics_for_session(inner, current_session_id) {
        diagnostic_trace.recorder = probe.snapshot();
    }

    let asr_opt = take_asr_for_session(inner, current_session_id);
    let asr = match asr_opt {
        Some(a) => a,
        None => {
            restore_prepared_windows_ime_session(inner, current_session_id);
            inner.state.lock().phase = SessionPhase::Idle;
            append_asr_error_trace(
                inner,
                diagnostic_trace,
                "missing active ASR session".to_string(),
            );
            return Ok(());
        }
    };

    let uses_global_timeout = asr_transcribe_uses_global_timeout(&asr);
    let raw = match asr {
        ActiveAsr::Volcengine(asr) => {
            debug_assert!(uses_global_timeout);
            if let Err(e) = asr.send_last_frame().await {
                log::error!("[coord] send last frame failed: {e}");
            }
            // 添加全局超时保护：防止 await_final_result() 永远挂起
            let timeout_duration = std::time::Duration::from_secs(COORDINATOR_GLOBAL_TIMEOUT_SECS);
            match tokio::time::timeout(timeout_duration, asr.await_final_result()).await {
                Ok(Ok(r)) => {
                    apply_volcengine_diagnostic_snapshot(
                        &mut diagnostic_trace,
                        asr.diagnostic_snapshot(),
                    );
                    r
                }
                Ok(Err(e)) => {
                    log::error!("[coord] await final failed: {e}");
                    apply_volcengine_diagnostic_snapshot(
                        &mut diagnostic_trace,
                        asr.diagnostic_snapshot(),
                    );
                    append_asr_error_trace(inner, diagnostic_trace, format!("asr failed: {e}"));
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some(format!("识别失败: {e}")),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err(e.to_string());
                }
                Err(_) => {
                    // 全局超时：最后的防线
                    log::error!(
                        "[coord] 全局超时 {} 秒 - 强制恢复",
                        COORDINATOR_GLOBAL_TIMEOUT_SECS
                    );
                    // 清理 ASR session，避免资源泄漏
                    asr.cancel();
                    apply_volcengine_diagnostic_snapshot(
                        &mut diagnostic_trace,
                        asr.diagnostic_snapshot(),
                    );
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        "asr global timeout".to_string(),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some("识别超时".to_string()),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err("global timeout".to_string());
                }
            }
        }
        ActiveAsr::Whisper(w) => {
            debug_assert!(uses_global_timeout);
            // Whisper 也添加类似的超时保护
            let timeout_duration = std::time::Duration::from_secs(COORDINATOR_GLOBAL_TIMEOUT_SECS);
            match tokio::time::timeout(timeout_duration, w.transcribe()).await {
                Ok(Ok(r)) => r,
                Ok(Err(e)) => {
                    log::error!("[coord] whisper transcribe failed: {e}");
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        format!("whisper transcribe failed: {e}"),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some(format!("识别失败: {e}")),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err(e.to_string());
                }
                Err(_) => {
                    log::error!(
                        "[coord] whisper 全局超时 {} 秒",
                        COORDINATOR_GLOBAL_TIMEOUT_SECS
                    );
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        "whisper global timeout".to_string(),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some("识别超时".to_string()),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err("whisper global timeout".to_string());
                }
            }
        }
        ActiveAsr::QwenRealtime(asr) => {
            debug_assert!(uses_global_timeout);
            if let Err(e) = asr.send_last_frame().await {
                log::error!("[coord] Qwen realtime send last frame failed: {e}");
            }
            let timeout_duration = std::time::Duration::from_secs(COORDINATOR_GLOBAL_TIMEOUT_SECS);
            match tokio::time::timeout(timeout_duration, asr.await_final_result()).await {
                Ok(Ok(r)) => r,
                Ok(Err(e)) => {
                    log::error!("[coord] Qwen realtime await final failed: {e}");
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        format!("qwen realtime await final failed: {e}"),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some(format!("识别失败: {e}")),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err(e.to_string());
                }
                Err(_) => {
                    log::error!(
                        "[coord] Qwen realtime 全局超时 {} 秒",
                        COORDINATOR_GLOBAL_TIMEOUT_SECS
                    );
                    asr.cancel();
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        "qwen realtime global timeout".to_string(),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some("识别超时".to_string()),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err("qwen realtime global timeout".to_string());
                }
            }
        }
        ActiveAsr::Bailian(asr) => {
            debug_assert!(uses_global_timeout);
            if let Err(e) = asr.send_last_frame().await {
                log::error!("[coord] Bailian send last frame failed: {e}");
            }
            let timeout_duration = std::time::Duration::from_secs(COORDINATOR_GLOBAL_TIMEOUT_SECS);
            match tokio::time::timeout(timeout_duration, asr.await_final_result()).await {
                Ok(Ok(r)) => r,
                Ok(Err(e)) => {
                    log::error!("[coord] Bailian await final failed: {e}");
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        format!("bailian await final failed: {e}"),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some(format!("识别失败: {e}")),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err(e.to_string());
                }
                Err(_) => {
                    log::error!(
                        "[coord] Bailian 全局超时 {} 秒",
                        COORDINATOR_GLOBAL_TIMEOUT_SECS
                    );
                    asr.cancel();
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        "bailian global timeout".to_string(),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some("识别超时".to_string()),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err("bailian global timeout".to_string());
                }
            }
        }
        ActiveAsr::QingyuLocal(buffer) => {
            let pcm = buffer.take();
            if pcm.is_empty() {
                RawTranscript {
                    text: String::new(),
                    duration_ms: 0,
                }
            } else {
                if pcm.len() % 2 != 0 {
                    log::warn!(
                        "[coord] Qingyu local ASR PCM buffer has odd byte length {}; trailing byte ignored",
                        pcm.len()
                    );
                }
                let samples = pcm_le_bytes_to_i16_samples(&pcm);
                let stats = pcm_i16_stats(&samples);
                log::info!(
                    "[coord] Qingyu local ASR PCM stats: bytes={} samples={} durationMs={} rms={:.5} peak={:.5} nonZeroSamples={}",
                    pcm.len(),
                    stats.sample_count,
                    raw_pcm_duration_ms(&pcm),
                    stats.rms,
                    stats.peak,
                    stats.non_zero_sample_count
                );
                let wav = crate::asr::wav::encode_wav_16k_mono(&samples);
                let tmp = match tempfile::Builder::new()
                    .prefix("qingyu-dictation-")
                    .suffix(".wav")
                    .tempfile()
                {
                    Ok(tmp) => tmp,
                    Err(e) => {
                        log::error!("[coord] create Qingyu local ASR temp WAV failed: {e}");
                        append_asr_error_trace(
                            inner,
                            diagnostic_trace,
                            format!("create Qingyu local ASR temp WAV failed: {e}"),
                        );
                        emit_capsule(
                            inner,
                            CapsuleState::Error,
                            0.0,
                            elapsed,
                            Some(format!("本地识别失败: {e}")),
                            None,
                        );
                        restore_prepared_windows_ime_session(inner, current_session_id);
                        inner.state.lock().phase = SessionPhase::Idle;
                        schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                        return Err(e.to_string());
                    }
                };
                if let Err(e) = std::fs::write(tmp.path(), wav) {
                    log::error!("[coord] write Qingyu local ASR temp WAV failed: {e}");
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        format!("write Qingyu local ASR temp WAV failed: {e}"),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some(format!("本地识别失败: {e}")),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err(e.to_string());
                }

                match inner.qingyu_local_asr.transcribe_wav(tmp.path()).await {
                    Ok(r) => r,
                    Err(e) => {
                        log::error!("[coord] Qingyu local ASR transcribe failed: {e:#}");
                        append_asr_error_trace(
                            inner,
                            diagnostic_trace,
                            format!("Qingyu local ASR transcribe failed: {e:#}"),
                        );
                        emit_capsule(
                            inner,
                            CapsuleState::Error,
                            0.0,
                            elapsed,
                            Some(format!("本地识别失败: {e}")),
                            None,
                        );
                        restore_prepared_windows_ime_session(inner, current_session_id);
                        inner.state.lock().phase = SessionPhase::Idle;
                        schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                        return Err(e.to_string());
                    }
                }
            }
        }
        #[cfg(target_os = "windows")]
        ActiveAsr::FoundryLocalWhisper(local) => {
            debug_assert!(!uses_global_timeout);
            match local
                .transcribe(foundry_audio_transcribe_timeout_duration())
                .await
            {
                Ok(r) => {
                    schedule_foundry_local_asr_release(inner, current_session_id);
                    r
                }
                Err(e) => {
                    if inner.state.lock().cancelled {
                        log::info!(
                            "[coord] Foundry Local Whisper transcribe cancelled — discarding transcript"
                        );
                        schedule_foundry_local_asr_release(inner, current_session_id);
                        restore_prepared_windows_ime_session(inner, current_session_id);
                        set_phase_idle_if_session_matches(inner, current_session_id);
                        diagnostic_trace.session.cancelled = true;
                        diagnostic_trace.insertion.status =
                            Some("cancelledDuringLocalAsr".to_string());
                        diagnostic_trace.insertion.method = Some("none".to_string());
                        append_diagnostic_trace(inner, diagnostic_trace);
                        return Ok(());
                    }
                    log::error!("[coord] Foundry Local Whisper transcribe failed: {e:#}");
                    schedule_foundry_local_asr_release(inner, current_session_id);
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        format!("Foundry Local Whisper transcribe failed: {e:#}"),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some(format!("本地识别失败: {e}")),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err(e.to_string());
                }
            }
        }
        #[cfg(target_os = "macos")]
        ActiveAsr::Local(local) => {
            debug_assert!(uses_global_timeout);
            // 与 Volcengine/Whisper 一致包一层 global timeout（来自 origin/main）。
            // 注：缓存命中时 transcribe 不含 load 时间；冷启动 load 已在 build_local_qwen3
            // 提前完成，所以 15s 给 transcribe 本身足够。
            let timeout_duration = std::time::Duration::from_secs(COORDINATOR_GLOBAL_TIMEOUT_SECS);
            let result = tokio::time::timeout(timeout_duration, local.transcribe()).await;
            inner.local_asr_cache.touch();
            schedule_local_asr_release(inner);
            match result {
                Ok(Ok(r)) => r,
                Ok(Err(e)) => {
                    log::error!("[coord] local Qwen3-ASR transcribe failed: {e:#}");
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        format!("local Qwen3-ASR transcribe failed: {e:#}"),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some(format!("本地识别失败: {e}")),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err(e.to_string());
                }
                Err(_) => {
                    log::error!(
                        "[coord] local Qwen3-ASR 全局超时 {} 秒",
                        COORDINATOR_GLOBAL_TIMEOUT_SECS
                    );
                    append_asr_error_trace(
                        inner,
                        diagnostic_trace,
                        "local Qwen3-ASR global timeout".to_string(),
                    );
                    emit_capsule(
                        inner,
                        CapsuleState::Error,
                        0.0,
                        elapsed,
                        Some("识别超时".to_string()),
                        None,
                    );
                    restore_prepared_windows_ime_session(inner, current_session_id);
                    inner.state.lock().phase = SessionPhase::Idle;
                    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
                    return Err("local global timeout".to_string());
                }
            }
        }
    };

    diagnostic_trace.recorder.estimated_duration_ms = Some(raw.duration_ms);
    diagnostic_trace.asr.raw_text = Some(raw.text.clone());
    diagnostic_trace.asr.raw_chars = Some(diagnostic_char_count(&raw.text));

    // ASR 完成后 cancel 检查：用户在 transcribe 进行中按 Esc 时，这里就会命中。
    // 优先级高于 empty 检查 — 用户取消 → 静默丢弃，不写失败历史也不弹错误胶囊。
    if inner.state.lock().cancelled {
        log::info!("[coord] cancel detected after ASR — discarding transcript");
        restore_prepared_windows_ime_session(inner, current_session_id);
        // PR #387 的「cancel 后清 focus_target」契约要在 Processing 路径上也成立。
        // cancel_session 在 Processing 阶段故意跳过 finish_cancel_session_state（让
        // 这里收尾），但此前的 end_session 没把 focus_target 清掉。logic-review
        // 2026-05-10 P3 (🚩) 把这条补完。
        {
            let mut state = inner.state.lock();
            state.phase = SessionPhase::Idle;
            state.focus_target = None;
        }
        diagnostic_trace.session.cancelled = true;
        diagnostic_trace.insertion.status = Some("cancelledAfterAsr".to_string());
        diagnostic_trace.insertion.method = Some("none".to_string());
        append_diagnostic_trace(inner, diagnostic_trace);
        return Ok(());
    }

    // ASR 返回空转写护栏（来自 PR #66）：写一条 emptyTranscript 失败历史 + 错误胶囊，
    // 与 main 上其它 error 路径保持一致（带 schedule_capsule_idle 让胶囊自动消失）。
    let mut raw = raw;

    #[cfg(any(debug_assertions, test))]
    if asr_transcript_has_no_speech(&raw.text) {
        if let Some(debug_text) = debug_transcript_override_text() {
            log::info!(
                "[coord] using debug transcript override (chars={})",
                debug_text.chars().count()
            );
            raw.text = debug_text;
            diagnostic_trace.asr.raw_text = Some(raw.text.clone());
            diagnostic_trace.asr.raw_chars = Some(diagnostic_char_count(&raw.text));
        }
    }

    if asr_transcript_has_no_speech(&raw.text) {
        log::info!(
            "[coord] ASR returned no-speech transcript marker: {:?}",
            raw.text
        );
        let prefs = inner.prefs.get();
        let session = DictationSession {
            id: Uuid::new_v4().to_string(),
            created_at: Utc::now().to_rfc3339(),
            raw_transcript: raw.text.clone(),
            final_text: String::new(),
            mode: prefs.default_mode,
            app_bundle_id: None,
            app_name: None,
            insert_status: InsertStatus::Failed,
            error_code: Some("emptyTranscript".to_string()),
            duration_ms: Some(raw.duration_ms),
            dictionary_entry_count: Some(enabled_phrases(inner).len() as u32),
            asr_provider_id: Some(asr_provider_id.clone()),
            llm_provider_id: Some(llm_provider_id.clone()),
        };
        if prefs.history_enabled {
            if let Err(e) = inner
                .history
                .append_with_retention(session, prefs.history_retention_days)
            {
                log::error!("[coord] history append failed: {e}");
            }
        }
        diagnostic_trace.session.mode = Some(format!("{:?}", prefs.default_mode));
        diagnostic_trace.llm.mode = Some(format!("{:?}", prefs.default_mode));
        diagnostic_trace.asr.error = Some("emptyTranscript".to_string());
        diagnostic_trace.llm.final_text = Some(String::new());
        diagnostic_trace.llm.final_chars = Some(0);
        diagnostic_trace.insertion.status = Some(format!("{:?}", InsertStatus::Failed));
        diagnostic_trace.insertion.method = Some("none".to_string());
        append_diagnostic_trace(inner, diagnostic_trace);
        emit_capsule(
            inner,
            CapsuleState::Error,
            0.0,
            elapsed,
            Some("没有识别到语音".to_string()),
            None,
        );
        restore_prepared_windows_ime_session(inner, current_session_id);
        inner.state.lock().phase = SessionPhase::Idle;
        schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
        return Err("ASR returned empty transcript".to_string());
    }

    let correction_rules = match inner.correction_rules.list() {
        Ok(rules) => rules,
        Err(e) => {
            log::warn!("[coord] load correction rules failed: {e}; continue without correction");
            Vec::new()
        }
    };
    if !correction_rules.is_empty() {
        let corrected = apply_correction_rules(&raw.text, &correction_rules);
        if corrected != raw.text {
            log::info!(
                "[coord] correction rules adjusted raw transcript ({} → {} chars)",
                raw.text.chars().count(),
                corrected.chars().count()
            );
            raw.text = corrected;
        }
    }

    let prefs = inner.prefs.get();
    let mode = prefs.default_mode;
    diagnostic_trace.session.mode = Some(format!("{mode:?}"));
    diagnostic_trace.session.hotkey_mode = Some(format!("{:?}", prefs.hotkey.mode));
    diagnostic_trace.llm.mode = Some(format!("{mode:?}"));
    let hotword_strs = enabled_phrases(inner);
    let working_languages = prefs.working_languages.clone();
    let chinese_script_preference = prefs.chinese_script_preference;
    let output_language_preference = prefs.effective_output_language_preference();
    let output_operation = dictation_output_operation(&prefs);
    let output_preference_translation_active =
        output_operation == DictationOutputOperation::TranslateToEnglish;
    let llm_thinking_enabled = prefs.llm_thinking_enabled;
    let front_app = inner.state.lock().front_app.clone();
    let translation_target = prefs.translation_target_language.trim().to_string();
    let translation_active = crate::product::SHOW_TRANSLATION
        && inner.translation_modifier_seen.load(Ordering::SeqCst)
        && !translation_target.is_empty();
    let short_transcript_llm_bypass =
        should_bypass_llm_for_short_transcript(&raw.text, translation_active, output_operation);

    emit_capsule(
        inner,
        CapsuleState::Polishing,
        0.0,
        elapsed,
        Some(
            if short_transcript_llm_bypass {
                "短文本直出"
            } else {
                "正在润色"
            }
            .to_string(),
        ),
        None,
    );

    // 对话感知 polish：拉最近 N 分钟的会话作为 LLM 上下文。仅在非翻译路径且非 Raw mode
    // 才有意义（Raw 只做本轮最小断句和标点，翻译走单轮独立 prompt）。窗口=0 时 prior_turns 是空 Vec，
    // polish 路径自动退化成单轮单消息——跟历史行为一致。
    let polish_context_window_minutes = prefs.polish_context_window_minutes;
    let prior_turns: Vec<(String, String)> = if !short_transcript_llm_bypass
        && !translation_active
        && !output_preference_translation_active
        && mode != PolishMode::Raw
        && polish_context_window_minutes > 0
    {
        match inner
            .history
            .recent_within_minutes(polish_context_window_minutes)
        {
            Ok(sessions) => sessions
                .into_iter()
                // 只取实际成功润色过的会话作为上下文：失败的会话 final_text 是 raw 兜底，
                // 喂回 LLM 会让模型以为"上一轮我什么都没做"——没意义且占 token。
                .filter(|s| s.error_code.is_none() && !s.final_text.trim().is_empty())
                .map(|s| (s.raw_transcript, s.final_text))
                .collect(),
            Err(e) => {
                log::warn!("[coord] fetch polish context failed: {e}; fall back to single-turn");
                Vec::new()
            }
        }
    } else {
        Vec::new()
    };
    // 流式插入 opt-in 路径：开关打开 + 非翻译 + 轻度润色 → 进入流式分支。
    // 清晰结构 / 正式表达需要完整文本后做编号和段落版式归一化；逐字 delta
    // 已经落到光标后无法可靠回填换行，因此这两种模式走一次性插入路径。
    // 任何不满足都走原一次性 polish_or_passthrough 路径，行为跟历史完全一致。
    let streaming_eligible =
        should_stream_polish_insert(&prefs, translation_active, output_operation, mode);
    log::info!(
        "[coord] polish dispatch: translation={translation_active} output_operation={output_operation:?} mode={mode:?} stream_enabled={} streaming_eligible={streaming_eligible} active_llm={}",
        prefs.streaming_insert,
        CredentialsVault::get_active_llm()
    );

    let focus_target = inner.state.lock().focus_target;
    let mut focus_ready_before_stream: Option<bool> = None;
    let llm_start = Instant::now();
    diagnostic_trace.llm.short_input_bypass = short_transcript_llm_bypass;
    diagnostic_trace.llm.streaming_insert_eligible = streaming_eligible;
    diagnostic_trace.llm.started_at_ms = Some(elapsed);

    let (polished, polish_error, already_streamed) = if translation_active {
        log::info!(
            "[coord] translation mode → target=\u{300C}{}\u{300D} working={:?} front_app={:?}",
            translation_target,
            working_languages,
            front_app
        );
        let (p, e) = translate_or_passthrough(
            &raw,
            &translation_target,
            &working_languages,
            chinese_script_preference,
            output_language_preference,
            llm_thinking_enabled,
            front_app.as_deref(),
        )
        .await;
        (p, e, false)
    } else if output_operation == DictationOutputOperation::TranslateToEnglish {
        log::info!(
            "[coord] output language preference translation → target=\u{300C}English\u{300D} working={:?} front_app={:?}",
            working_languages,
            front_app
        );
        let (p, e) = translate_or_passthrough(
            &raw,
            "English",
            &working_languages,
            chinese_script_preference,
            output_language_preference,
            llm_thinking_enabled,
            front_app.as_deref(),
        )
        .await;
        (p, e, false)
    } else if short_transcript_llm_bypass {
        log::info!(
            "[coord] short transcript bypass: effective_chars={} threshold={} mode={mode:?}",
            effective_transcript_char_count(&raw.text),
            SHORT_TRANSCRIPT_LLM_BYPASS_CHAR_THRESHOLD
        );
        (raw.text.clone(), None, false)
    } else if streaming_eligible {
        let focus_ready = restore_focus_target_if_possible(focus_target);
        focus_ready_before_stream = Some(focus_ready);
        if focus_ready {
            run_streaming_polish(
                inner,
                &raw,
                mode,
                &hotword_strs,
                &working_languages,
                chinese_script_preference,
                output_language_preference,
                llm_thinking_enabled,
                front_app.as_deref(),
                &prior_turns,
            )
            .await
        } else {
            log::warn!(
                "[coord] streaming_insert: original focus target not ready before stream; fall back to one-shot"
            );
            let (p, e) = polish_or_passthrough(
                &raw,
                mode,
                &hotword_strs,
                &working_languages,
                chinese_script_preference,
                output_language_preference,
                llm_thinking_enabled,
                front_app.as_deref(),
                &prior_turns,
            )
            .await;
            (p, e, false)
        }
    } else {
        let (p, e) = polish_or_passthrough(
            &raw,
            mode,
            &hotword_strs,
            &working_languages,
            chinese_script_preference,
            output_language_preference,
            llm_thinking_enabled,
            front_app.as_deref(),
            &prior_turns,
        )
        .await;
        (p, e, false)
    };

    // 仅在“ASR 直出文本”场景做强制简繁收敛，避免误伤成功的翻译/常规 LLM 输出：
    // - 非翻译模式：mode=Raw（只做最小整理）或润色失败回退 raw
    // - 翻译模式：仅翻译失败回退 raw 时才收敛
    let translation_path_active = translation_active || output_preference_translation_active;
    let should_force_script = if translation_path_active {
        polish_error.is_some()
    } else {
        short_transcript_llm_bypass || mode == PolishMode::Raw || polish_error.is_some()
    };
    let polished = if should_force_script {
        apply_chinese_script_preference(&polished, chinese_script_preference)
    } else {
        polished
    };
    let polished = if correction_rules.is_empty() {
        polished
    } else {
        let corrected = apply_correction_rules(&polished, &correction_rules);
        if corrected != polished {
            log::info!(
                "[coord] correction rules adjusted final text ({} → {} chars)",
                polished.chars().count(),
                corrected.chars().count()
            );
        }
        corrected
    };
    diagnostic_trace.llm.finished_at_ms =
        Some(elapsed.saturating_add(llm_start.elapsed().as_millis() as u64));
    diagnostic_trace.llm.error = polish_error.clone();
    diagnostic_trace.llm.final_text = Some(polished.clone());
    diagnostic_trace.llm.final_chars = Some(diagnostic_char_count(&polished));

    // 原子化最后一次 cancel 检查 + 转 Inserting：
    // 在同一 lock 内决定「丢弃」还是「进入 Inserting」。一旦设到 Inserting，
    // cancel_session 就拒绝介入（Cmd+V 已发出，撤销不掉）。这是 audit HIGH #2 的修复，
    // 之前 check 与 inserter.insert 之间有窗口期。
    //
    // 流式路径例外：`already_streamed = true` 表示字符已经一边流一边落到光标了，
    // 撤销不掉。即使 cancel 旗在中途被立起来，也只能尊重「已经发生」的事实，进入
    // Inserting 状态完成 history / vocab 等收尾工作。
    let proceed_to_insert = {
        let mut state = inner.state.lock();
        if state.cancelled && !already_streamed {
            state.phase = SessionPhase::Idle;
            false
        } else {
            state.phase = SessionPhase::Inserting;
            true
        }
    };
    if !proceed_to_insert {
        log::info!(
            "[coord] cancel detected before insert — discarding output (chars={})",
            polished.chars().count()
        );
        diagnostic_trace.session.cancelled = true;
        diagnostic_trace.insertion.status = Some("cancelledBeforeInsert".to_string());
        diagnostic_trace.insertion.method = Some("none".to_string());
        append_diagnostic_trace(inner, diagnostic_trace);
        restore_prepared_windows_ime_session(inner, current_session_id);
        return Ok(());
    }

    let focus_ready_for_paste = if already_streamed {
        focus_ready_before_stream.unwrap_or(true)
    } else {
        restore_focus_target_if_possible(focus_target)
    };
    let prefs = inner.prefs.get();
    let restore_clipboard = prefs.restore_clipboard_after_paste;
    let allow_non_tsf_insertion_fallback = prefs.allow_non_tsf_insertion_fallback;
    let paste_shortcut = prefs.paste_shortcut;
    // 流式路径下，字符已经通过 Unicode keystroke 落到光标处，跳过 inserter.insert。
    let status = if already_streamed {
        log::info!(
            "[coord] insertion skipped: {} chars already streamed via unicode_keystroke (polish_error={:?})",
            polished.chars().count(),
            polish_error
        );
        InsertStatus::Inserted
    } else if focus_ready_for_paste {
        #[cfg(target_os = "windows")]
        {
            if tsf_experiment_enabled() {
                let ime_target = capture_ime_submit_target();
                insert_with_windows_ime_first(
                    inner,
                    current_session_id,
                    &polished,
                    restore_clipboard,
                    allow_non_tsf_insertion_fallback,
                    paste_shortcut,
                    ime_target,
                )
                .await
            } else {
                insert_via_windows_default_path(
                    inner,
                    &polished,
                    restore_clipboard,
                    allow_non_tsf_insertion_fallback,
                    paste_shortcut,
                )
            }
        }
        #[cfg(not(target_os = "windows"))]
        {
            inner
                .inserter
                .insert(&polished, restore_clipboard, paste_shortcut)
        }
    } else {
        log::warn!(
            "[coord] original insertion target is not foreground; copied output without paste"
        );
        if allow_non_tsf_insertion_fallback {
            inner.inserter.copy_fallback(&polished)
        } else {
            InsertStatus::Failed
        }
    };
    restore_prepared_windows_ime_session(inner, current_session_id);
    let inserted_chars = polished.chars().count() as u32;

    // 累计每条 enabled 词条在最终文本中的命中次数。
    // 用 polished（最终插入的文本）扫描，与用户实际看到的输出一致。
    let total_hits: u64 = match inner.vocab.record_hits(&polished) {
        Ok(n) => n,
        Err(e) => {
            log::error!("[coord] record_hits failed: {e}");
            0
        }
    };
    // 词汇本页面在打开时通常需要立即看到 hits 增长，否则用户得手动切走再切回来才刷新。
    // 命中数 > 0 时通知前端：Vocab 页面订阅 vocab:updated 即时 listVocab() 重新加载。
    if total_hits > 0 {
        if let Some(app) = inner.app.lock().clone() {
            let _ = app.emit("vocab:updated", total_hits);
        }
    }

    // polish 失败时在 history 里标记 polishFailed，让用户能在历史详情看到为什么这次输出
    // 不是预期的 mode 风格。即使失败也不丢词 — final_text 仍是原文（保留"用户的话不丢"语义）。
    let error_code = dictation_error_code(
        status,
        polish_error.is_some(),
        focus_ready_for_paste,
        allow_non_tsf_insertion_fallback,
    )
    .map(str::to_string);
    let tsf_required_insert_failed = error_code.as_deref() == Some("windowsImeTsfRequired");

    let session = DictationSession {
        id: Uuid::new_v4().to_string(),
        created_at: Utc::now().to_rfc3339(),
        raw_transcript: raw.text.clone(),
        final_text: polished.clone(),
        mode,
        app_bundle_id: None,
        app_name: None,
        insert_status: status,
        error_code,
        duration_ms: Some(raw.duration_ms),
        // 历史详情页的"X 个热词"显示：用本次实际命中次数（每个匹配实例算一次），
        // 比"启用词条总数"更能反映本段口述命中了多少。u64 → u32 截断对单段听写足够。
        dictionary_entry_count: Some(total_hits.min(u32::MAX as u64) as u32),
        asr_provider_id: Some(asr_provider_id),
        llm_provider_id: Some(llm_provider_id),
    };
    if prefs.history_enabled {
        if let Err(e) = inner
            .history
            .append_with_retention(session, prefs.history_retention_days)
        {
            log::error!("[coord] history append failed: {e}");
        }
    }
    complete_trace_texts(&mut diagnostic_trace, &raw.text, &polished, status);
    diagnostic_trace.insertion.method =
        Some(diagnostic_insert_method(already_streamed, focus_ready_for_paste).to_string());
    diagnostic_trace.insertion.focus_restored = Some(focus_ready_for_paste);
    append_diagnostic_trace(inner, diagnostic_trace);

    let done_message = if tsf_required_insert_failed {
        Some("TSF 未上屏，已禁止非 TSF 兜底".to_string())
    } else if polish_error.is_some() {
        // polish 失败优先告知用户，即使 insert 成功也要让用户知道这版是原文
        Some("润色失败，已插入原文".to_string())
    } else {
        match status {
            InsertStatus::Inserted => None,
            InsertStatus::PasteSent => Some("已尝试粘贴".to_string()),
            InsertStatus::CopiedFallback => Some(if cfg!(target_os = "windows") {
                "已复制，请 Ctrl+V".to_string()
            } else {
                "已复制，请粘贴".to_string()
            }),
            InsertStatus::Failed => Some("插入失败".to_string()),
        }
    };

    emit_capsule(
        inner,
        CapsuleState::Done,
        0.0,
        elapsed,
        done_message,
        Some(inserted_chars),
    );

    {
        let mut state = inner.state.lock();
        state.phase = SessionPhase::Idle;
        state.focus_target = None;
    }
    let capsule_hide_delay_ms =
        capsule_hide_delay_for_insert_status(status, polish_error.is_some());
    log::info!(
        "[capsule] insert complete status={status:?} polish_failed={} hide_delay_ms={capsule_hide_delay_ms}",
        polish_error.is_some()
    );
    schedule_capsule_idle(inner, capsule_hide_delay_ms);

    Ok(())
}

pub(super) fn dictation_error_code(
    status: InsertStatus,
    polish_failed: bool,
    focus_ready_for_paste: bool,
    allow_non_tsf_insertion_fallback: bool,
) -> Option<&'static str> {
    if !focus_ready_for_paste && status == InsertStatus::Failed {
        Some("focusRestoreFailed")
    } else if cfg!(target_os = "windows")
        && focus_ready_for_paste
        && !allow_non_tsf_insertion_fallback
        && status == InsertStatus::Failed
    {
        Some("windowsImeTsfRequired")
    } else if polish_failed {
        Some("polishFailed")
    } else {
        None
    }
}

pub(super) fn cancel_session(inner: &Arc<Inner>) {
    let Some(decision) = ({
        let mut state = inner.state.lock();
        let phase = state.phase;
        let decision = begin_cancel_session_state(&mut state);
        if phase == SessionPhase::Inserting {
            log::info!("[coord] cancel ignored — already in Inserting phase, can't undo paste");
        }
        decision
    }) else {
        return;
    };

    stop_recorder_for_session(inner, decision.session_id);
    cancel_asr_for_session(inner, decision.session_id);
    restore_prepared_windows_ime_session(inner, decision.session_id);
    // Processing 阶段保持 phase=Processing 让 end_session 自己走完检查 + 收尾；
    // 其他阶段直接转 Idle。
    if decision.phase != SessionPhase::Processing {
        let mut state = inner.state.lock();
        finish_cancel_session_state(&mut state, decision);
    }
    emit_capsule(inner, CapsuleState::Cancelled, 0.0, 0, None, None);
    log::info!("[coord] session cancelled (was {:?})", decision.phase);
    schedule_capsule_idle(inner, CAPSULE_AUTO_HIDE_DELAY_MS);
}

#[cfg(test)]
mod tests {
    use super::{
        asr_transcript_has_no_speech, complete_trace_texts, diagnostic_insert_method,
        diagnostic_trace_for_test, dictation_output_operation, qingyu_local_asr_readiness_error,
        should_bypass_llm_for_short_transcript, should_stream_polish_insert,
        DictationOutputOperation, SHORT_TRANSCRIPT_LLM_BYPASS_CHAR_THRESHOLD,
    };
    use crate::types::{InsertStatus, OutputLanguagePreference, PolishMode, UserPreferences};

    #[test]
    fn diagnostic_insert_method_describes_streaming_and_clipboard_paths() {
        assert_eq!(diagnostic_insert_method(true, true), "streaming-unicode");
        assert_eq!(diagnostic_insert_method(false, true), "clipboard-or-tsf");
        assert_eq!(diagnostic_insert_method(false, false), "copy-fallback");
    }

    #[test]
    fn diagnostic_trace_records_raw_and_final_lengths() {
        let mut trace = diagnostic_trace_for_test("trace-test");
        complete_trace_texts(
            &mut trace,
            "这是原始识别文本",
            "这是最终文本",
            InsertStatus::PasteSent,
        );

        assert_eq!(trace.asr.raw_chars, Some(8));
        assert_eq!(trace.llm.final_chars, Some(6));
        assert_eq!(trace.insertion.status.as_deref(), Some("PasteSent"));
    }

    #[test]
    fn english_output_preference_routes_chinese_asr_text_to_translation() {
        let prefs = UserPreferences {
            output_language_preference: OutputLanguagePreference::En,
            output_language_preference_explicit: true,
            ..UserPreferences::default()
        };
        assert_eq!(
            dictation_output_operation(&prefs),
            DictationOutputOperation::TranslateToEnglish
        );
    }

    #[test]
    fn legacy_english_output_preference_without_explicit_marker_stays_polish() {
        let prefs = UserPreferences {
            output_language_preference: OutputLanguagePreference::En,
            output_language_preference_explicit: false,
            ..UserPreferences::default()
        };
        assert_eq!(
            dictation_output_operation(&prefs),
            DictationOutputOperation::Polish
        );
    }

    #[test]
    fn simplified_chinese_output_preference_stays_polish() {
        let prefs = UserPreferences {
            output_language_preference: OutputLanguagePreference::ZhCn,
            output_language_preference_explicit: true,
            ..UserPreferences::default()
        };
        assert_eq!(
            dictation_output_operation(&prefs),
            DictationOutputOperation::Polish
        );
    }

    #[test]
    fn streaming_insert_only_applies_to_light_polish() {
        let prefs = UserPreferences {
            streaming_insert: true,
            ..UserPreferences::default()
        };

        assert!(should_stream_polish_insert(
            &prefs,
            false,
            DictationOutputOperation::Polish,
            PolishMode::Light
        ));
        assert!(!should_stream_polish_insert(
            &prefs,
            false,
            DictationOutputOperation::Polish,
            PolishMode::Structured
        ));
        assert!(!should_stream_polish_insert(
            &prefs,
            false,
            DictationOutputOperation::Polish,
            PolishMode::Formal
        ));
        assert!(!should_stream_polish_insert(
            &prefs,
            false,
            DictationOutputOperation::Polish,
            PolishMode::Raw
        ));
    }

    #[test]
    fn streaming_insert_stays_disabled_for_translation_paths() {
        let prefs = UserPreferences {
            streaming_insert: true,
            ..UserPreferences::default()
        };

        assert!(!should_stream_polish_insert(
            &prefs,
            true,
            DictationOutputOperation::Polish,
            PolishMode::Light
        ));
        assert!(!should_stream_polish_insert(
            &prefs,
            false,
            DictationOutputOperation::TranslateToEnglish,
            PolishMode::Light
        ));
    }

    #[test]
    fn streaming_insert_restores_focus_before_streaming_polish() {
        let source = include_str!("dictation.rs");
        let dispatch_start = source
            .find("let (polished, polish_error, already_streamed) =")
            .expect("polish dispatch assignment should exist");
        let streaming_call = source[dispatch_start..]
            .find("run_streaming_polish(")
            .map(|idx| dispatch_start + idx)
            .expect("streaming polish call should exist");
        let focus_restore = source[dispatch_start..]
            .find("restore_focus_target_if_possible")
            .map(|idx| dispatch_start + idx)
            .expect("focus restore call should exist");

        assert!(
            focus_restore < streaming_call,
            "streaming insertion must restore the original target before the first LLM delta can be typed"
        );
    }

    #[test]
    fn short_transcripts_bypass_llm_on_polish_paths() {
        assert!(should_bypass_llm_for_short_transcript(
            "收到。",
            false,
            DictationOutputOperation::Polish
        ));
        assert!(should_bypass_llm_for_short_transcript(
            "明天见",
            false,
            DictationOutputOperation::Polish
        ));
    }

    #[test]
    fn short_transcript_bypass_ignores_punctuation_and_whitespace() {
        let short_with_punctuation = "  好的，收到。 ";
        assert!(should_bypass_llm_for_short_transcript(
            short_with_punctuation,
            false,
            DictationOutputOperation::Polish
        ));
    }

    #[test]
    fn short_transcript_bypass_does_not_apply_at_threshold_or_translation() {
        let at_threshold = "测".repeat(SHORT_TRANSCRIPT_LLM_BYPASS_CHAR_THRESHOLD);
        assert!(!should_bypass_llm_for_short_transcript(
            &at_threshold,
            false,
            DictationOutputOperation::Polish
        ));
        assert!(!should_bypass_llm_for_short_transcript(
            "收到",
            true,
            DictationOutputOperation::Polish
        ));
        assert!(!should_bypass_llm_for_short_transcript(
            "收到",
            false,
            DictationOutputOperation::TranslateToEnglish
        ));
    }

    #[test]
    fn asr_no_speech_detection_treats_sherpa_silence_token_as_empty() {
        assert!(asr_transcript_has_no_speech(""));
        assert!(asr_transcript_has_no_speech(" \n\t "));
        assert!(asr_transcript_has_no_speech("<sil>"));
        assert!(asr_transcript_has_no_speech(" <SIL> "));
        assert!(!asr_transcript_has_no_speech("hello"));
        assert!(!asr_transcript_has_no_speech("你好"));
    }

    fn qingyu_status(
        model_state: crate::asr::qingyu::QingyuAsrModelState,
        vad_available: bool,
    ) -> crate::asr::qingyu::QingyuAsrStatus {
        crate::asr::qingyu::QingyuAsrStatus {
            provider_id: crate::product::LOCAL_ASR_PROVIDER_ID.into(),
            display_name: "FireRedASR2".into(),
            model_id: "model".into(),
            model_state,
            model_source: crate::asr::qingyu::QingyuAsrModelSource::Production,
            model_dir: Some("model-dir".into()),
            model_size_bytes: None,
            sidecar_running: false,
            vad_available,
            error: None,
        }
    }

    #[test]
    fn qingyu_readiness_requires_installed_model_and_vad() {
        assert!(qingyu_local_asr_readiness_error(&qingyu_status(
            crate::asr::qingyu::QingyuAsrModelState::Missing,
            true
        ))
        .is_some());

        assert!(qingyu_local_asr_readiness_error(&qingyu_status(
            crate::asr::qingyu::QingyuAsrModelState::Installed,
            false
        ))
        .is_some());

        assert!(qingyu_local_asr_readiness_error(&qingyu_status(
            crate::asr::qingyu::QingyuAsrModelState::Installed,
            true
        ))
        .is_none());
    }
}
