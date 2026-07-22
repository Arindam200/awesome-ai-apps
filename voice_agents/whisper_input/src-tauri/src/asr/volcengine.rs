//! Volcengine SAUC bigmodel streaming ASR client.
//!
//! Direct port of the Swift `VolcengineStreamingASR`. Battle-tested protocol
//! quirks are preserved verbatim — see comments tagged with `[asr]` for the
//! original learnings (especially the "definite=true is NOT stream end" bug).

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use futures_util::{SinkExt, StreamExt};
use parking_lot::Mutex as ParkingMutex;
use serde_json::{json, Value};
use tokio::net::TcpStream;
use tokio::runtime::Handle;
use tokio::sync::{mpsc, oneshot, Mutex as AsyncMutex, Notify};
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::header::HeaderValue;
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::{connect_async, MaybeTlsStream, WebSocketStream};
use uuid::Uuid;

use super::frame::{self, Flags, MessageType, Serialization};
use super::{AudioConsumer, DictionaryHotword, RawTranscript};

pub const DEFAULT_ENDPOINT: &str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async";
pub const DEFAULT_RESOURCE_ID: &str = "volc.seedasr.sauc.duration";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DoubaoStreamingPreset {
    pub endpoint: &'static str,
    pub resource_id: &'static str,
}

pub fn doubao_streaming_preset() -> DoubaoStreamingPreset {
    DoubaoStreamingPreset {
        endpoint: DEFAULT_ENDPOINT,
        resource_id: VolcengineCredentials::default_resource_id(),
    }
}

/// 200 ms of 16 kHz / 16-bit / mono PCM.
const TARGET_AUDIO_CHUNK_BYTES: usize = 6_400;
/// 16 kHz · 16-bit · mono = 32 000 bytes/sec → 32 bytes/ms.
const BYTES_PER_MS: f64 = 32.0;
const HOTWORD_CAP: usize = 80;
const FINAL_RESULT_TIMEOUT: Duration = Duration::from_secs(12);

#[derive(Clone, Debug)]
pub struct VolcengineCredentials {
    pub api_key: String,
    pub app_id: String,
    pub access_token: String,
    pub endpoint: String,
    pub resource_id: String,
}

impl VolcengineCredentials {
    pub fn default_resource_id() -> &'static str {
        DEFAULT_RESOURCE_ID
    }

    pub fn normalized_endpoint(&self) -> &str {
        let endpoint = self.endpoint.trim();
        if endpoint.is_empty() {
            DEFAULT_ENDPOINT
        } else {
            endpoint
        }
    }

    pub fn has_auth(&self) -> bool {
        !self.api_key.trim().is_empty()
            || (!self.app_id.trim().is_empty() && !self.access_token.trim().is_empty())
    }
}

#[derive(Debug, thiserror::Error)]
pub enum VolcengineASRError {
    #[error("credentials missing")]
    CredentialsMissing,
    #[error("connection failed: {0}")]
    ConnectionFailed(String),
    #[error("authentication failed")]
    AuthenticationFailed,
    #[error("no final result")]
    NoFinalResult,
    #[error("final result timed out")]
    FinalResultTimeout,
    #[error("decode failed: {0}")]
    DecodeFailed(String),
}

#[derive(Debug, Clone, Default)]
pub struct VolcengineDiagnosticSnapshot {
    pub connected_at_ms: Option<u64>,
    pub first_server_message_at_ms: Option<u64>,
    pub last_server_message_at_ms: Option<u64>,
    pub server_audio_duration_ms: Option<u64>,
    pub socket_closed_at_ms: Option<u64>,
    pub socket_error: Option<String>,
    pub server_log_id: Option<String>,
    pub frames_sent: Option<u64>,
    pub bytes_sent: Option<u64>,
    pub pending_sends: Option<u64>,
    pub final_missing_partial_used: bool,
}

type WsStream = WebSocketStream<MaybeTlsStream<TcpStream>>;
type WsSink = futures_util::stream::SplitSink<WsStream, Message>;
type SharedWriter = Arc<AsyncMutex<Option<WsSink>>>;

/// Sync state shared across the receive loop, the public API, and the
/// audio-consumer fast path.
#[derive(Default)]
struct SyncState {
    pending_audio: Vec<u8>,
    next_sequence: i32,
    bytes_sent: usize,
    frames_sent: usize,
    is_connected: bool,
    final_tx: Option<oneshot::Sender<Result<RawTranscript, VolcengineASRError>>>,
    runtime: Option<Handle>,
    start: Option<Instant>,
    diagnostic_origin: Option<Instant>,
    connected_at_ms: Option<u64>,
    first_server_message_at_ms: Option<u64>,
    last_server_message_at_ms: Option<u64>,
    last_server_audio_duration_ms: Option<u64>,
    last_server_log_id: Option<String>,
    socket_closed_at_ms: Option<u64>,
    last_socket_error: Option<String>,
    final_missing_partial_used: bool,
    /// 最近一次 partial（非 final）的累积 transcript。服务端在 final 帧到达前
    /// 关闭连接 / 网络中断时，作为 fallback 回给上层，避免「用户的话已经识别出来
    /// 但没拿到 final」就丢光。
    last_partial_text: String,
}

pub struct VolcengineStreamingASR {
    credentials: VolcengineCredentials,
    hotwords: Vec<DictionaryHotword>,
    state: ParkingMutex<SyncState>,
    /// Guards the WebSocket write half so concurrent `send` calls serialize.
    /// Stored as Arc so spawned send tasks can hold their own clone — independent
    /// of the lifetime of any particular `&self` borrow.
    writer: SharedWriter,
    final_rx: ParkingMutex<Option<oneshot::Receiver<Result<RawTranscript, VolcengineASRError>>>>,
    /// 单 worker 模式：consume_pcm_chunk 把 (seq, chunk) 入队这个 channel，
    /// open_session 里 spawn 出的唯一 worker 串行 recv + send_binary，
    /// 保证 seq 顺序严格等于实际发送顺序。session 结束时 take() 掉这个 sender，
    /// worker 的 recv() 返回 None 自动退出。
    audio_tx: ParkingMutex<Option<mpsc::UnboundedSender<(i32, Vec<u8>)>>>,
    /// 队列里 + worker 在飞的 audio 帧总数。consume +N，worker send 完一帧 -1。
    /// send_last_frame 必须等它降到 0 才能安全发末帧，否则末帧可能被服务端先收到
    /// 而把后续 chunk 当成「stream 已结束」之后的多余数据丢弃 → 尾句丢失。
    pending_sends: Arc<AtomicUsize>,
    send_done: Arc<Notify>,
}

impl VolcengineStreamingASR {
    pub fn new(credentials: VolcengineCredentials, hotwords: Vec<DictionaryHotword>) -> Self {
        Self {
            credentials,
            hotwords,
            state: ParkingMutex::new(SyncState::default()),
            writer: Arc::new(AsyncMutex::new(None)),
            final_rx: ParkingMutex::new(None),
            audio_tx: ParkingMutex::new(None),
            pending_sends: Arc::new(AtomicUsize::new(0)),
            send_done: Arc::new(Notify::new()),
        }
    }

    pub fn is_connected(&self) -> bool {
        self.state.lock().is_connected
    }

    pub async fn open_session(self: &Arc<Self>) -> Result<(), VolcengineASRError> {
        let diagnostic_origin = Instant::now();
        {
            let mut st = self.state.lock();
            st.diagnostic_origin = Some(diagnostic_origin);
            st.connected_at_ms = None;
            st.first_server_message_at_ms = None;
            st.last_server_message_at_ms = None;
            st.last_server_audio_duration_ms = None;
            st.last_server_log_id = None;
            st.socket_closed_at_ms = None;
            st.last_socket_error = None;
            st.final_missing_partial_used = false;
        }
        if !self.credentials.has_auth() || self.credentials.resource_id.trim().is_empty() {
            return Err(VolcengineASRError::CredentialsMissing);
        }

        let connect_id = Uuid::new_v4().to_string();
        let mut request = self
            .credentials
            .normalized_endpoint()
            .into_client_request()
            .map_err(|e| VolcengineASRError::ConnectionFailed(e.to_string()))?;
        let headers = request.headers_mut();
        if !self.credentials.api_key.trim().is_empty() {
            headers.insert(
                "X-Api-Key",
                HeaderValue::from_str(self.credentials.api_key.trim())
                    .map_err(|e| VolcengineASRError::ConnectionFailed(e.to_string()))?,
            );
        } else {
            headers.insert(
                "X-Api-App-Key",
                HeaderValue::from_str(self.credentials.app_id.trim())
                    .map_err(|e| VolcengineASRError::ConnectionFailed(e.to_string()))?,
            );
            headers.insert(
                "X-Api-Access-Key",
                HeaderValue::from_str(self.credentials.access_token.trim())
                    .map_err(|e| VolcengineASRError::ConnectionFailed(e.to_string()))?,
            );
        }
        headers.insert(
            "X-Api-Resource-Id",
            HeaderValue::from_str(self.credentials.resource_id.trim())
                .map_err(|e| VolcengineASRError::ConnectionFailed(e.to_string()))?,
        );
        headers.insert(
            "X-Api-Connect-Id",
            HeaderValue::from_str(&connect_id)
                .map_err(|e| VolcengineASRError::ConnectionFailed(e.to_string()))?,
        );

        let (ws, _resp) = match connect_async(request).await {
            Ok(ws) => ws,
            Err(e) => {
                self.record_socket_error(e.to_string());
                return Err(VolcengineASRError::ConnectionFailed(e.to_string()));
            }
        };
        let (write, read) = ws.split();

        let (tx, rx) = oneshot::channel();

        // Reset sync state for the new session.
        {
            let mut st = self.state.lock();
            st.pending_audio.clear();
            st.next_sequence = 1;
            st.bytes_sent = 0;
            st.frames_sent = 0;
            st.is_connected = true;
            st.final_tx = Some(tx);
            st.runtime = Some(Handle::current());
            st.start = Some(Instant::now());
            st.diagnostic_origin = Some(diagnostic_origin);
            st.connected_at_ms = Some(diagnostic_origin.elapsed().as_millis() as u64);
            st.first_server_message_at_ms = None;
            st.last_server_message_at_ms = None;
            st.last_server_audio_duration_ms = None;
            st.last_server_log_id = None;
            st.socket_closed_at_ms = None;
            st.last_socket_error = None;
            st.final_missing_partial_used = false;
            st.last_partial_text.clear();
        }
        self.pending_sends.store(0, Ordering::SeqCst);
        *self.final_rx.lock() = Some(rx);
        *self.writer.lock().await = Some(write);

        // 起一个唯一的 audio worker：consume_pcm_chunk 把 (seq, chunk) 推到 audio_tx，
        // worker 这边 FIFO recv 然后串行 send_binary。session 结束后调用方
        // (cancel / handle_frame error / fallback_to_partial_or_error) 会 take 掉
        // self.audio_tx，channel 关闭，worker 自然退出。
        let (audio_tx, mut audio_rx) = mpsc::unbounded_channel::<(i32, Vec<u8>)>();
        *self.audio_tx.lock() = Some(audio_tx);
        let writer_for_worker = Arc::clone(&self.writer);
        let pending_for_worker = Arc::clone(&self.pending_sends);
        let notify_for_worker = Arc::clone(&self.send_done);
        tokio::spawn(async move {
            while let Some((seq, chunk)) = audio_rx.recv().await {
                let frame = frame::build(
                    MessageType::AudioOnlyRequest,
                    Flags::PositiveSequence,
                    Serialization::None,
                    &chunk,
                    Some(seq),
                );
                if let Err(e) = send_binary(&writer_for_worker, frame).await {
                    log::error!("[asr] audio frame seq={} send 失败: {}", seq, e);
                }
                if pending_for_worker.fetch_sub(1, Ordering::SeqCst) == 1 {
                    notify_for_worker.notify_waiters();
                }
            }
        });

        // Send the first frame: full client request with seq=1.
        let payload_json = self.build_first_frame_payload(&connect_id);
        let payload_bytes = serde_json::to_vec(&payload_json)
            .map_err(|e| VolcengineASRError::DecodeFailed(e.to_string()))?;
        let first_seq = self.allocate_positive_seq();
        let frame = frame::build(
            MessageType::FullClientRequest,
            Flags::PositiveSequence,
            Serialization::Json,
            &payload_bytes,
            Some(first_seq),
        );
        self.send_binary_with_diagnostics(frame).await?;

        // Spawn the receive loop. Holds a Weak<Self> so it doesn't keep
        // the struct alive forever if callers drop their Arcs.
        let weak_self = Arc::downgrade(self);
        tokio::spawn(async move {
            let mut read = read;
            while let Some(msg) = read.next().await {
                let Some(this) = weak_self.upgrade() else {
                    break;
                };
                match msg {
                    Ok(Message::Binary(data)) => {
                        if !this.handle_frame(&data) {
                            break;
                        }
                    }
                    Ok(Message::Close(_)) => {
                        this.record_socket_close();
                        // 服务端没发 final 就关连接 → 用最近一次 partial 兜底，不丢已识别的文字。
                        this.fallback_to_partial_or_error(VolcengineASRError::NoFinalResult);
                        break;
                    }
                    Ok(_) => { /* ignore text/ping/pong */ }
                    Err(e) => {
                        log::error!("[asr] receive loop error: {}", e);
                        this.record_socket_error(e.to_string());
                        // 网络中断同样回退到 partial，让用户至少拿到已经识别的部分。
                        this.fallback_to_partial_or_error(VolcengineASRError::ConnectionFailed(
                            e.to_string(),
                        ));
                        break;
                    }
                }
                if !this.state.lock().is_connected {
                    break;
                }
            }
        });

        Ok(())
    }

    pub async fn send_last_frame(&self) -> Result<(), VolcengineASRError> {
        // 等所有 fire-and-forget 发送完成。否则末帧（NegativeSequence）可能比尾部
        // chunk 先到服务端，被识别为「流已结束」之后再到的 chunk 全部丢弃 = 尾句吞掉。
        // 给一个 800ms 上限避免极端网络下永远等。
        let drain_deadline = Instant::now() + std::time::Duration::from_millis(800);
        while self.pending_sends.load(Ordering::SeqCst) > 0 {
            let remaining = drain_deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                log::warn!(
                    "[asr] send_last_frame: pending {} 帧未发送完，超时强制继续",
                    self.pending_sends.load(Ordering::SeqCst)
                );
                break;
            }
            // notified() 返回 future，被 timeout 包住 → 等待发送完成或超时
            let _ = tokio::time::timeout(remaining, self.send_done.notified()).await;
        }

        // Drain leftover audio (if any) into one final positive-sequence frame.
        let leftover = {
            let mut st = self.state.lock();
            if st.pending_audio.is_empty() {
                None
            } else {
                Some(std::mem::take(&mut st.pending_audio))
            }
        };

        if let Some(buf) = leftover {
            let seq = self.allocate_positive_seq();
            let len = buf.len();
            let frame = frame::build(
                MessageType::AudioOnlyRequest,
                Flags::PositiveSequence,
                Serialization::None,
                &buf,
                Some(seq),
            );
            {
                let mut st = self.state.lock();
                st.bytes_sent += len;
                st.frames_sent += 1;
            }
            self.send_binary_with_diagnostics(frame).await?;
        }

        // Final frame: negativeSequence + negative seq number signals stream end.
        // 末帧用 negativeSequence + 负序号收尾，告诉服务端"流到此结束"。
        let final_seq = {
            let mut st = self.state.lock();
            let s = -st.next_sequence;
            st.next_sequence += 1;
            s
        };
        let frame = frame::build(
            MessageType::AudioOnlyRequest,
            Flags::NegativeSequence,
            Serialization::None,
            &[],
            Some(final_seq),
        );
        self.send_binary_with_diagnostics(frame).await?;

        let (total_bytes, total_frames) = {
            let st = self.state.lock();
            (st.bytes_sent, st.frames_sent)
        };
        let duration_ms = (total_bytes as f64 / BYTES_PER_MS) as u64;
        log::info!(
            "[asr] 发送总结：{} audio frames, {} bytes (~{} ms)",
            total_frames,
            total_bytes,
            duration_ms
        );
        Ok(())
    }

    pub async fn await_final_result(&self) -> Result<RawTranscript, VolcengineASRError> {
        self.await_final_result_with_timeout(FINAL_RESULT_TIMEOUT)
            .await
    }

    pub fn diagnostic_snapshot(&self) -> VolcengineDiagnosticSnapshot {
        let st = self.state.lock();
        VolcengineDiagnosticSnapshot {
            connected_at_ms: st.connected_at_ms,
            first_server_message_at_ms: st.first_server_message_at_ms,
            last_server_message_at_ms: st.last_server_message_at_ms,
            server_audio_duration_ms: st.last_server_audio_duration_ms,
            socket_closed_at_ms: st.socket_closed_at_ms,
            socket_error: st.last_socket_error.clone(),
            server_log_id: st.last_server_log_id.clone(),
            frames_sent: Some(st.frames_sent as u64),
            bytes_sent: Some(st.bytes_sent as u64),
            pending_sends: Some(self.pending_sends.load(Ordering::SeqCst) as u64),
            final_missing_partial_used: st.final_missing_partial_used,
        }
    }

    pub async fn await_final_result_with_timeout(
        &self,
        timeout: Duration,
    ) -> Result<RawTranscript, VolcengineASRError> {
        let rx = self.final_rx.lock().take();
        let Some(rx) = rx else {
            return Err(VolcengineASRError::NoFinalResult);
        };
        match tokio::time::timeout(timeout, rx).await {
            Ok(Ok(result)) => result,
            Ok(Err(_)) => Err(VolcengineASRError::NoFinalResult),
            Err(_) => {
                log::error!(
                    "[asr] final result timed out after {} ms",
                    timeout.as_millis()
                );
                self.cancel();
                Err(VolcengineASRError::FinalResultTimeout)
            }
        }
    }

    pub fn cancel(&self) {
        let runtime = {
            let mut st = self.state.lock();
            st.is_connected = false;
            st.pending_audio.clear();
            st.runtime.clone()
        };
        // Drop audio sender → worker.recv() 返回 None → worker 退出，不再 hold writer。
        *self.audio_tx.lock() = None;
        if let Some(runtime) = runtime {
            // Close the writer asynchronously so the receive loop sees EOF.
            let writer = Arc::clone(&self.writer);
            runtime.spawn(async move {
                if let Some(mut w) = writer.lock().await.take() {
                    let _ = w.close().await;
                }
            });
        }
        self.signal_error(VolcengineASRError::NoFinalResult);
    }

    // ---- internals ----

    fn diagnostic_elapsed_ms(st: &SyncState) -> u64 {
        st.diagnostic_origin
            .map(|origin| origin.elapsed().as_millis() as u64)
            .unwrap_or(0)
    }

    fn record_socket_close(&self) {
        let mut st = self.state.lock();
        if st.socket_closed_at_ms.is_none() {
            st.socket_closed_at_ms = Some(Self::diagnostic_elapsed_ms(&st));
        }
    }

    fn record_socket_error(&self, error: impl Into<String>) {
        let mut st = self.state.lock();
        st.last_socket_error = Some(error.into());
    }

    fn record_server_json_facts(&self, facts: VolcengineDiagnosticSnapshot) {
        let mut st = self.state.lock();
        let elapsed = Self::diagnostic_elapsed_ms(&st);
        if st.first_server_message_at_ms.is_none() {
            st.first_server_message_at_ms = Some(elapsed);
        }
        st.last_server_message_at_ms = Some(elapsed);
        if facts.server_audio_duration_ms.is_some() {
            st.last_server_audio_duration_ms = facts.server_audio_duration_ms;
        }
        if facts.server_log_id.is_some() {
            st.last_server_log_id = facts.server_log_id;
        }
    }

    async fn send_binary_with_diagnostics(&self, data: Vec<u8>) -> Result<(), VolcengineASRError> {
        match send_binary(&self.writer, data).await {
            Ok(()) => Ok(()),
            Err(error) => {
                self.record_socket_error(error.to_string());
                Err(error)
            }
        }
    }

    fn build_first_frame_payload(&self, connect_id: &str) -> Value {
        let mut request = json!({
            "model_name": "bigmodel",
            "enable_itn": true,
            "enable_punc": true,
            "show_utterances": true,
        });
        if let Some(context) = hotword_context(&self.hotwords) {
            request["context"] = Value::String(context);
            let enabled_count = self.hotwords.iter().filter(|h| h.enabled).count();
            log::info!("[asr] hotwords injected: {}", enabled_count);
        }
        json!({
            "user": { "uid": connect_id },
            "audio": {
                "format": "pcm",
                "rate": 16000,
                "bits": 16,
                "channel": 1,
                "codec": "raw",
            },
            "request": request,
        })
    }

    fn allocate_positive_seq(&self) -> i32 {
        let mut st = self.state.lock();
        let s = st.next_sequence;
        st.next_sequence += 1;
        s
    }

    /// Returns `false` once the session has terminated (caller should stop reading).
    fn handle_frame(&self, data: &[u8]) -> bool {
        let Some(parsed) = frame::parse(data) else {
            log::error!("[asr] 帧解析失败 raw={}", hex_prefix(data, 32));
            return true;
        };

        if parsed.message_type == Some(MessageType::ErrorMessage) {
            let body = String::from_utf8_lossy(&parsed.payload).to_string();
            let code = parsed.error_code.unwrap_or(0);
            if let Ok(json) = serde_json::from_str::<Value>(&body) {
                self.record_server_json_facts(diagnostic_facts_from_server_json(&json));
            }
            log::error!(
                "[asr] error frame code={} body={}",
                code,
                body.chars().take(200).collect::<String>()
            );
            let error = format!("ASR error {}: {}", code, body);
            self.record_socket_error(error.clone());
            self.signal_error(VolcengineASRError::ConnectionFailed(error));
            self.state.lock().is_connected = false;
            *self.audio_tx.lock() = None;
            return false;
        }

        if parsed.message_type != Some(MessageType::FullServerResponse) {
            return true;
        }

        if let Ok(payload_str) = std::str::from_utf8(&parsed.payload) {
            log::info!(
                "[asr] server JSON: {}",
                payload_str.chars().take(400).collect::<String>()
            );
        }

        let json: Value = match serde_json::from_slice(&parsed.payload) {
            Ok(v) => v,
            Err(_) => return true,
        };
        self.record_server_json_facts(diagnostic_facts_from_server_json(&json));
        let Some(result) = normalized_result(&json) else {
            return true;
        };

        // 流结束信号只信帧头 flags（lastPacket / negativeSequence）。
        // 之前误把 utterance.definite=true 当成流结束——但那只代表"这一段语音已固化"，
        // 用户可能还在继续说。结果一收到第一个 definite=true 就关掉接收，
        // 后面用户讲的内容全部丢失（实测丢了 9 秒）。
        let has_final = parsed.is_final();
        let full_text = transcript_text_from_result(result);

        // 缓存最新的 partial transcript：服务端在 final 帧前断连时 fallback 用。
        // 仅在非空且不是 final 时更新（final 走另一条路径）。
        if !has_final && !full_text.is_empty() {
            self.state.lock().last_partial_text = full_text.clone();
        }

        if has_final {
            let duration_ms = self
                .state
                .lock()
                .start
                .map(|s| s.elapsed().as_millis() as u64)
                .unwrap_or(0);
            let transcript = RawTranscript {
                text: full_text,
                duration_ms,
            };
            self.signal_success(transcript);
            self.state.lock().is_connected = false;
            *self.audio_tx.lock() = None;
            return false;
        }
        true
    }

    fn signal_success(&self, transcript: RawTranscript) {
        let tx = self.state.lock().final_tx.take();
        if let Some(tx) = tx {
            let _ = tx.send(Ok(transcript));
        }
    }

    fn signal_error(&self, err: VolcengineASRError) {
        let tx = self.state.lock().final_tx.take();
        if let Some(tx) = tx {
            let _ = tx.send(Err(err));
        }
    }

    /// 服务端 close / 网络中断时调用：如果有缓存的 partial 文本，作为 transcript
    /// 兜底返回；否则才报错。配合 `last_partial_text` 实现「至少不丢用户已识别出的话」。
    fn fallback_to_partial_or_error(&self, err: VolcengineASRError) {
        let (partial, duration_ms) = {
            let st = self.state.lock();
            (
                st.last_partial_text.clone(),
                st.start
                    .map(|s| s.elapsed().as_millis() as u64)
                    .unwrap_or(0),
            )
        };
        if !partial.is_empty() {
            log::warn!(
                "[asr] {}; 使用 partial 兜底（{} 字）",
                err,
                partial.chars().count()
            );
            self.state.lock().final_missing_partial_used = true;
            self.signal_success(RawTranscript {
                text: partial,
                duration_ms,
            });
        } else {
            self.signal_error(err);
        }
        self.state.lock().is_connected = false;
        *self.audio_tx.lock() = None;
    }
}

impl AudioConsumer for VolcengineStreamingASR {
    fn consume_pcm_chunk(&self, pcm: &[u8]) {
        // 单 worker 串行 send 模式：在 state 锁内 drain 并分配 seq（seq 单调），
        // 然后把 (seq, chunk) push 进 mpsc。worker 端按入队顺序 send，
        // 哪怕跨多个 consume 调用、多个 spawn 也不会再有 writer 锁竞争。
        let chunks: Vec<(i32, Vec<u8>)> = {
            let mut st = self.state.lock();
            if !st.is_connected {
                return;
            }
            st.pending_audio.extend_from_slice(pcm);

            let mut out: Vec<(i32, Vec<u8>)> = Vec::new();
            while st.pending_audio.len() >= TARGET_AUDIO_CHUNK_BYTES {
                let chunk: Vec<u8> = st.pending_audio.drain(..TARGET_AUDIO_CHUNK_BYTES).collect();
                let seq = st.next_sequence;
                st.next_sequence += 1;
                st.bytes_sent += chunk.len();
                st.frames_sent += 1;
                out.push((seq, chunk));
            }
            out
        };

        if chunks.is_empty() {
            return;
        }
        let Some(tx) = self.audio_tx.lock().as_ref().cloned() else {
            return;
        };

        for entry in chunks {
            // pending_sends 必须在 tx.send 之前 +1：否则 worker 可能先 recv + 发送 +
            // 减 1，把 usize 计数器 underflow。
            self.pending_sends.fetch_add(1, Ordering::SeqCst);
            if tx.send(entry).is_err() {
                // worker 已退出（cancel / 错误路径里 audio_tx 被 take）。
                // 撤销刚才的 +1，避免 send_last_frame 的 wait 永远等不到 0。
                if self.pending_sends.fetch_sub(1, Ordering::SeqCst) == 1 {
                    self.send_done.notify_waiters();
                }
                log::warn!("[asr] audio queue closed; dropping subsequent frames");
                return;
            }
        }
    }
}

async fn send_binary(writer: &SharedWriter, data: Vec<u8>) -> Result<(), VolcengineASRError> {
    let mut guard = writer.lock().await;
    let Some(sink) = guard.as_mut() else {
        return Err(VolcengineASRError::ConnectionFailed(
            "websocket not open".into(),
        ));
    };
    sink.send(Message::Binary(data))
        .await
        .map_err(|e| VolcengineASRError::ConnectionFailed(e.to_string()))
}

fn hex_prefix(data: &[u8], n: usize) -> String {
    data.iter()
        .take(n)
        .map(|b| format!("{:02x}", b))
        .collect::<Vec<_>>()
        .join("")
}

fn normalized_result(json: &Value) -> Option<&Value> {
    if let Some(obj) = json.get("result") {
        if obj.is_object() {
            return Some(obj);
        }
        if let Some(arr) = obj.as_array() {
            if let Some(first) = arr.first() {
                return Some(first);
            }
        }
    }
    if json.get("text").and_then(|v| v.as_str()).is_some() {
        return Some(json);
    }
    None
}

fn transcript_text_from_result(result: &Value) -> String {
    if let Some(text) = result.get("text").and_then(|v| v.as_str()) {
        if !text.is_empty() {
            return text.to_string();
        }
    }

    result
        .get("utterances")
        .and_then(|v| v.as_array())
        .map(|utterances| {
            utterances
                .iter()
                .filter_map(|u| u.get("text").and_then(|t| t.as_str()))
                .collect::<Vec<_>>()
                .join("")
        })
        .unwrap_or_default()
}

fn diagnostic_facts_from_server_json(json: &Value) -> VolcengineDiagnosticSnapshot {
    let result = normalized_result(json);
    VolcengineDiagnosticSnapshot {
        server_audio_duration_ms: json
            .get("audio_info")
            .and_then(|v| v.get("duration"))
            .or_else(|| json.get("duration"))
            .or_else(|| result.and_then(|r| r.get("duration")))
            .and_then(value_as_u64),
        server_log_id: result
            .and_then(|r| r.get("additions"))
            .and_then(|v| v.get("log_id"))
            .or_else(|| json.get("additions").and_then(|v| v.get("log_id")))
            .or_else(|| json.get("log_id"))
            .and_then(|v| v.as_str())
            .map(str::to_string),
        ..Default::default()
    }
}

fn value_as_u64(value: &Value) -> Option<u64> {
    value
        .as_u64()
        .or_else(|| value.as_str().and_then(|s| s.parse::<u64>().ok()))
}

fn hotword_context(entries: &[DictionaryHotword]) -> Option<String> {
    let mut seen: Vec<String> = Vec::new();
    for entry in entries {
        if !entry.enabled {
            continue;
        }
        let trimmed = entry.phrase.trim();
        if trimmed.is_empty() {
            continue;
        }
        if seen.iter().any(|w| w.eq_ignore_ascii_case(trimmed)) {
            continue;
        }
        seen.push(trimmed.to_string());
        if seen.len() >= HOTWORD_CAP {
            break;
        }
    }
    if seen.is_empty() {
        return None;
    }
    let words: Vec<Value> = seen.into_iter().map(|w| json!({ "word": w })).collect();
    let payload = json!({ "hotwords": words });
    serde_json::to_string(&payload).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hotword_context_dedupes_case_insensitively_and_caps() {
        let mut entries = vec![
            DictionaryHotword {
                phrase: "Foo".into(),
                enabled: true,
            },
            DictionaryHotword {
                phrase: "foo".into(),
                enabled: true,
            },
            DictionaryHotword {
                phrase: "  ".into(),
                enabled: true,
            },
            DictionaryHotword {
                phrase: "Bar".into(),
                enabled: false,
            },
            DictionaryHotword {
                phrase: "Baz".into(),
                enabled: true,
            },
        ];
        for i in 0..200 {
            entries.push(DictionaryHotword {
                phrase: format!("w{}", i),
                enabled: true,
            });
        }
        let ctx = hotword_context(&entries).expect("should produce JSON");
        assert!(ctx.contains("\"hotwords\""));
        assert!(ctx.contains("Foo"));
        assert!(ctx.contains("Baz"));
        assert!(!ctx.contains("Bar"));
        let count = ctx.matches("\"word\"").count();
        assert!(count <= HOTWORD_CAP);
    }

    #[test]
    fn transcript_text_prefers_server_aggregate_over_utterance_stitching() {
        let result = json!({
            "text": "第一段。第二段。",
            "utterances": [
                { "text": "第一段。" },
                { "text": "二段。" }
            ]
        });

        assert_eq!(transcript_text_from_result(&result), "第一段。第二段。");
    }

    #[test]
    fn transcript_text_falls_back_to_utterances_when_aggregate_missing() {
        let result = json!({
            "text": "",
            "utterances": [
                { "text": "第一段。" },
                { "text": "第二段。" }
            ]
        });

        assert_eq!(transcript_text_from_result(&result), "第一段。第二段。");
    }

    #[test]
    fn hotword_context_returns_none_when_all_disabled() {
        let entries = vec![DictionaryHotword {
            phrase: "Foo".into(),
            enabled: false,
        }];
        assert!(hotword_context(&entries).is_none());
    }

    #[test]
    fn default_resource_id_is_sauc_duration() {
        assert_eq!(
            VolcengineCredentials::default_resource_id(),
            "volc.seedasr.sauc.duration"
        );
    }

    #[tokio::test]
    async fn await_final_result_returns_error_when_final_frame_never_arrives() {
        let asr = VolcengineStreamingASR::new(
            VolcengineCredentials {
                api_key: String::new(),
                app_id: "app".into(),
                access_token: "token".into(),
                endpoint: String::new(),
                resource_id: VolcengineCredentials::default_resource_id().into(),
            },
            Vec::new(),
        );
        let (tx, rx) = oneshot::channel();
        asr.state.lock().final_tx = Some(tx);
        *asr.final_rx.lock() = Some(rx);

        let result = asr
            .await_final_result_with_timeout(std::time::Duration::from_millis(10))
            .await;

        assert!(matches!(
            result,
            Err(VolcengineASRError::FinalResultTimeout)
        ));
    }

    #[test]
    fn diagnostic_facts_extract_log_id_and_audio_duration() {
        let payload = serde_json::json!({
            "audio_info": { "duration": 8600 },
            "result": {
                "additions": { "log_id": "202605210158088D7BA12160111239CBDF" },
                "text": "首先我不确定"
            }
        });

        let facts = diagnostic_facts_from_server_json(&payload);

        assert_eq!(facts.server_audio_duration_ms, Some(8600));
        assert_eq!(
            facts.server_log_id.as_deref(),
            Some("202605210158088D7BA12160111239CBDF")
        );
    }

    #[test]
    fn diagnostic_snapshot_reports_send_counters() {
        let asr = VolcengineStreamingASR::new(
            VolcengineCredentials {
                api_key: "key".into(),
                app_id: String::new(),
                access_token: String::new(),
                endpoint: DEFAULT_ENDPOINT.into(),
                resource_id: DEFAULT_RESOURCE_ID.into(),
            },
            Vec::new(),
        );

        let snapshot = asr.diagnostic_snapshot();

        assert_eq!(snapshot.frames_sent, Some(0));
        assert_eq!(snapshot.bytes_sent, Some(0));
        assert_eq!(snapshot.pending_sends, Some(0));
    }

    #[test]
    fn partial_fallback_marks_final_missing_partial_used() {
        let asr = VolcengineStreamingASR::new(
            VolcengineCredentials {
                api_key: "key".into(),
                app_id: String::new(),
                access_token: String::new(),
                endpoint: DEFAULT_ENDPOINT.into(),
                resource_id: DEFAULT_RESOURCE_ID.into(),
            },
            Vec::new(),
        );
        asr.state.lock().last_partial_text = "partial".into();

        asr.fallback_to_partial_or_error(VolcengineASRError::NoFinalResult);

        assert!(asr.diagnostic_snapshot().final_missing_partial_used);
    }

    #[test]
    fn diagnostic_snapshot_records_close_and_error_times() {
        let asr = VolcengineStreamingASR::new(
            VolcengineCredentials {
                api_key: "key".into(),
                app_id: String::new(),
                access_token: String::new(),
                endpoint: DEFAULT_ENDPOINT.into(),
                resource_id: DEFAULT_RESOURCE_ID.into(),
            },
            Vec::new(),
        );

        asr.record_socket_close();
        asr.record_socket_error("receive failed");

        let snapshot = asr.diagnostic_snapshot();
        assert!(snapshot.socket_closed_at_ms.is_some());
        assert_eq!(snapshot.socket_error.as_deref(), Some("receive failed"));
    }

    #[test]
    fn diagnostic_socket_error_does_not_imply_socket_close() {
        let asr = VolcengineStreamingASR::new(
            VolcengineCredentials {
                api_key: "key".into(),
                app_id: String::new(),
                access_token: String::new(),
                endpoint: DEFAULT_ENDPOINT.into(),
                resource_id: DEFAULT_RESOURCE_ID.into(),
            },
            Vec::new(),
        );

        asr.record_socket_error("send failed");

        let snapshot = asr.diagnostic_snapshot();
        assert!(snapshot.socket_closed_at_ms.is_none());
        assert_eq!(snapshot.socket_error.as_deref(), Some("send failed"));
    }

    #[test]
    fn server_json_frame_updates_message_timestamps_and_duration() {
        let asr = VolcengineStreamingASR::new(
            VolcengineCredentials {
                api_key: "key".into(),
                app_id: String::new(),
                access_token: String::new(),
                endpoint: DEFAULT_ENDPOINT.into(),
                resource_id: DEFAULT_RESOURCE_ID.into(),
            },
            Vec::new(),
        );
        asr.state.lock().diagnostic_origin = Some(Instant::now());
        let payload = serde_json::json!({
            "duration": "1200",
            "result": { "text": "partial" }
        });
        let frame = frame::build(
            MessageType::FullServerResponse,
            Flags::None,
            Serialization::Json,
            &serde_json::to_vec(&payload).unwrap(),
            None,
        );

        assert!(asr.handle_frame(&frame));

        let snapshot = asr.diagnostic_snapshot();
        assert_eq!(snapshot.first_server_message_at_ms, Some(0));
        assert_eq!(snapshot.last_server_message_at_ms, Some(0));
        assert_eq!(snapshot.server_audio_duration_ms, Some(1200));
    }

    #[test]
    fn error_frame_records_socket_error_and_log_id() {
        let asr = VolcengineStreamingASR::new(
            VolcengineCredentials {
                api_key: "key".into(),
                app_id: String::new(),
                access_token: String::new(),
                endpoint: DEFAULT_ENDPOINT.into(),
                resource_id: DEFAULT_RESOURCE_ID.into(),
            },
            Vec::new(),
        );
        asr.state.lock().diagnostic_origin = Some(Instant::now());
        let body = serde_json::json!({ "log_id": "error-log-id", "message": "boom" })
            .to_string()
            .into_bytes();
        let mut frame = Vec::new();
        frame.push(0x11);
        frame.push(((MessageType::ErrorMessage as u8) << 4) | (Flags::None as u8));
        frame.push(((Serialization::None as u8) << 4) | 0);
        frame.push(0x00);
        frame.extend_from_slice(&123u32.to_be_bytes());
        frame.extend_from_slice(&(body.len() as u32).to_be_bytes());
        frame.extend_from_slice(&body);

        assert!(!asr.handle_frame(&frame));

        let snapshot = asr.diagnostic_snapshot();
        assert!(snapshot.socket_closed_at_ms.is_none());
        assert!(snapshot
            .socket_error
            .as_deref()
            .unwrap_or_default()
            .contains("ASR error 123"));
        assert_eq!(snapshot.server_log_id.as_deref(), Some("error-log-id"));
    }
}

#[cfg(test)]
mod doubao_tests {
    use super::*;

    #[test]
    fn doubao_backup_uses_seed_asr_2_resource_id() {
        let preset = doubao_streaming_preset();

        assert_eq!(
            preset.endpoint,
            "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
        );
        assert_eq!(preset.resource_id, "volc.seedasr.sauc.duration");
    }

    #[test]
    fn default_resource_id_uses_seedasr_duration_resource() {
        assert_eq!(
            VolcengineCredentials::default_resource_id(),
            "volc.seedasr.sauc.duration"
        );
    }

    #[test]
    fn x_api_key_credentials_are_complete_without_legacy_split_keys() {
        let credentials = VolcengineCredentials {
            api_key: "secret".into(),
            app_id: String::new(),
            access_token: String::new(),
            endpoint: String::new(),
            resource_id: VolcengineCredentials::default_resource_id().into(),
        };

        assert!(credentials.has_auth());
        assert_eq!(credentials.normalized_endpoint(), DEFAULT_ENDPOINT);
    }

    #[test]
    fn legacy_split_keys_remain_complete_for_existing_users() {
        let credentials = VolcengineCredentials {
            api_key: String::new(),
            app_id: "app".into(),
            access_token: "access".into(),
            endpoint: String::new(),
            resource_id: VolcengineCredentials::default_resource_id().into(),
        };

        assert!(credentials.has_auth());
    }
}
