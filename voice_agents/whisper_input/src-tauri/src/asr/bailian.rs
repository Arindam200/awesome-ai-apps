//! Alibaba Cloud Bailian / DashScope realtime ASR client.
//!
//! Uses the classic DashScope realtime recognition WebSocket protocol
//! (`/api-ws/v1/inference`) because it accepts raw 16 kHz mono PCM frames and
//! matches OpenLess' recorder output directly. The Qwen OpenAI Realtime line is
//! a different protocol and is intentionally left for a follow-up provider.

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

use super::{AudioConsumer, RawTranscript};

pub const PROVIDER_ID: &str = "bailian";
pub const DEFAULT_ENDPOINT: &str = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/";
pub const DEFAULT_MODEL: &str = "fun-asr-realtime";

/// 100 ms of 16 kHz / 16-bit / mono PCM.
pub const TARGET_AUDIO_CHUNK_BYTES: usize = 3_200;
const BYTES_PER_MS: u64 = 32;
const FINAL_RESULT_TIMEOUT: Duration = Duration::from_secs(12);

type WsStream = WebSocketStream<MaybeTlsStream<TcpStream>>;
type WsSink = futures_util::stream::SplitSink<WsStream, Message>;
type SharedWriter = Arc<AsyncMutex<Option<WsSink>>>;

#[derive(Clone, Debug)]
pub struct BailianCredentials {
    pub api_key: String,
    pub endpoint: String,
    pub model: String,
    pub vocabulary_id: Option<String>,
}

impl BailianCredentials {
    pub fn normalized_endpoint(&self) -> String {
        if self.endpoint.trim().is_empty() {
            return DEFAULT_ENDPOINT.to_string();
        }
        self.endpoint.trim().to_string()
    }

    pub fn normalized_model(&self) -> String {
        let model = self.model.trim();
        if model.is_empty() {
            DEFAULT_MODEL.to_string()
        } else {
            model.to_string()
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum BailianASRError {
    #[error("credentials missing")]
    CredentialsMissing,
    #[error("connection failed: {0}")]
    ConnectionFailed(String),
    #[error("send failed: {0}")]
    SendFailed(String),
    #[error("task failed: {0}")]
    TaskFailed(String),
    #[error("no final result")]
    NoFinalResult,
    #[error("final result timed out")]
    FinalResultTimeout,
}

enum SendItem {
    Audio(Vec<u8>),
    Finish(oneshot::Sender<Result<(), BailianASRError>>),
}

#[derive(Default)]
struct SyncState {
    task_id: String,
    pending_audio: Vec<u8>,
    audio_scratch: Vec<u8>,
    bytes_received: u64,
    task_started: bool,
    task_finished: bool,
    runtime: Option<Handle>,
    start: Option<Instant>,
    final_tx: Option<oneshot::Sender<Result<RawTranscript, BailianASRError>>>,
    send_tx: Option<mpsc::UnboundedSender<SendItem>>,
    final_segments: Vec<String>,
    last_result_text: String,
}

pub struct BailianRealtimeASR {
    credentials: BailianCredentials,
    state: ParkingMutex<SyncState>,
    writer: SharedWriter,
    final_rx: ParkingMutex<Option<oneshot::Receiver<Result<RawTranscript, BailianASRError>>>>,
    task_started: Arc<Notify>,
}

impl BailianRealtimeASR {
    pub fn new(credentials: BailianCredentials) -> Self {
        Self {
            credentials,
            state: ParkingMutex::new(SyncState::default()),
            writer: Arc::new(AsyncMutex::new(None)),
            final_rx: ParkingMutex::new(None),
            task_started: Arc::new(Notify::new()),
        }
    }

    pub async fn open_session(self: &Arc<Self>) -> Result<(), BailianASRError> {
        if self.credentials.api_key.trim().is_empty() {
            return Err(BailianASRError::CredentialsMissing);
        }

        let task_id = Uuid::new_v4().simple().to_string();
        let endpoint = self.credentials.normalized_endpoint();
        let mut request = endpoint
            .into_client_request()
            .map_err(|e| BailianASRError::ConnectionFailed(e.to_string()))?;
        request.headers_mut().insert(
            "Authorization",
            HeaderValue::from_str(&format!("bearer {}", self.credentials.api_key.trim()))
                .map_err(|e| BailianASRError::ConnectionFailed(e.to_string()))?,
        );

        let (ws, _resp) = connect_async(request)
            .await
            .map_err(|e| BailianASRError::ConnectionFailed(e.to_string()))?;
        let (write, read) = ws.split();
        *self.writer.lock().await = Some(write);

        let (final_tx, final_rx) = oneshot::channel();
        let (send_tx, mut send_rx) = mpsc::unbounded_channel::<SendItem>();
        {
            let mut st = self.state.lock();
            *st = SyncState::default();
            st.task_id = task_id.clone();
            st.runtime = Some(Handle::current());
            st.start = Some(Instant::now());
            st.final_tx = Some(final_tx);
            st.send_tx = Some(send_tx);
        }
        *self.final_rx.lock() = Some(final_rx);

        let writer_for_worker = Arc::clone(&self.writer);
        let task_id_for_worker = task_id.clone();
        tokio::spawn(async move {
            while let Some(item) = send_rx.recv().await {
                match item {
                    SendItem::Audio(chunk) => {
                        if let Err(e) = send_binary(&writer_for_worker, chunk).await {
                            log::error!("[bailian-asr] audio frame send failed: {e}");
                        }
                    }
                    SendItem::Finish(done) => {
                        let result =
                            send_text(&writer_for_worker, finish_task_message(&task_id_for_worker))
                                .await
                                .map_err(|e| BailianASRError::SendFailed(e.to_string()));
                        let _ = done.send(result);
                    }
                }
            }
        });

        send_text(
            &self.writer,
            run_task_message(
                &task_id,
                &self.credentials.normalized_model(),
                self.credentials.vocabulary_id.as_deref(),
            ),
        )
        .await?;

        let weak_self = Arc::downgrade(self);
        tokio::spawn(async move {
            let mut read = read;
            while let Some(msg) = read.next().await {
                let Some(this) = weak_self.upgrade() else {
                    break;
                };
                match msg {
                    Ok(Message::Text(text)) => {
                        if !this.handle_text_message(&text) {
                            break;
                        }
                    }
                    Ok(Message::Close(_)) => {
                        this.finish_with_partial_or_error(BailianASRError::NoFinalResult);
                        break;
                    }
                    Ok(_) => {}
                    Err(e) => {
                        log::error!("[bailian-asr] receive loop error: {e}");
                        this.finish_with_partial_or_error(BailianASRError::ConnectionFailed(
                            e.to_string(),
                        ));
                        break;
                    }
                }
            }
        });

        Ok(())
    }

    pub async fn send_last_frame(&self) -> Result<(), BailianASRError> {
        let started = self.task_started.notified();
        tokio::pin!(started);
        started.as_mut().enable();
        let ready = {
            let st = self.state.lock();
            st.task_started || st.task_finished
        };
        if !ready {
            tokio::time::timeout(Duration::from_secs(5), started)
                .await
                .map_err(|_| BailianASRError::FinalResultTimeout)?;
        }
        let (send_tx, tail_chunks) = {
            let mut st = self.state.lock();
            let send_tx = st.send_tx.clone();
            if !st.pending_audio.is_empty() {
                let pending = std::mem::take(&mut st.pending_audio);
                st.audio_scratch.extend_from_slice(&pending);
            }
            let tail = if st.audio_scratch.is_empty() {
                Vec::new()
            } else {
                vec![std::mem::take(&mut st.audio_scratch)]
            };
            (send_tx, tail)
        };
        let Some(send_tx) = send_tx else {
            return Ok(());
        };
        for chunk in tail_chunks {
            let _ = send_tx.send(SendItem::Audio(chunk));
        }
        let (done_tx, done_rx) = oneshot::channel();
        send_tx
            .send(SendItem::Finish(done_tx))
            .map_err(|_| BailianASRError::SendFailed("send worker closed".to_string()))?;
        done_rx
            .await
            .map_err(|_| BailianASRError::SendFailed("finish ack dropped".to_string()))?
    }

    pub async fn await_final_result(&self) -> Result<RawTranscript, BailianASRError> {
        let rx = self.final_rx.lock().take();
        let Some(rx) = rx else {
            return Err(BailianASRError::NoFinalResult);
        };
        tokio::time::timeout(FINAL_RESULT_TIMEOUT, rx)
            .await
            .map_err(|_| BailianASRError::FinalResultTimeout)?
            .map_err(|_| BailianASRError::NoFinalResult)?
    }

    pub fn cancel(&self) {
        let mut st = self.state.lock();
        st.pending_audio.clear();
        st.audio_scratch.clear();
        st.send_tx.take();
        st.final_tx.take();
        st.task_finished = true;
        drop(st);
        let writer = Arc::clone(&self.writer);
        if let Ok(handle) = Handle::try_current() {
            handle.spawn(async move {
                let _ = close_writer(&writer).await;
            });
        } else {
            std::thread::spawn(move || {
                if let Ok(rt) = tokio::runtime::Runtime::new() {
                    rt.block_on(async move {
                        let _ = close_writer(&writer).await;
                    });
                }
            });
        }
    }

    fn handle_text_message(&self, text: &str) -> bool {
        let value: Value = match serde_json::from_str(text) {
            Ok(v) => v,
            Err(e) => {
                log::warn!("[bailian-asr] invalid json event: {e}");
                return true;
            }
        };
        let event = value
            .get("header")
            .and_then(|h| h.get("event"))
            .and_then(Value::as_str)
            .unwrap_or_default();
        match event {
            "task-started" => {
                self.mark_task_started();
                true
            }
            "result-generated" => {
                self.record_result(&value);
                true
            }
            "task-finished" => {
                self.finish_success();
                false
            }
            "task-failed" => {
                let message = value
                    .get("header")
                    .and_then(|h| h.get("error_message"))
                    .and_then(Value::as_str)
                    .unwrap_or("task failed")
                    .to_string();
                self.finish_error(BailianASRError::TaskFailed(message));
                false
            }
            _ => true,
        }
    }

    fn mark_task_started(&self) {
        let (send_tx, chunks) = {
            let mut st = self.state.lock();
            st.task_started = true;
            if !st.pending_audio.is_empty() {
                let pending = std::mem::take(&mut st.pending_audio);
                st.audio_scratch.extend_from_slice(&pending);
            }
            let send_tx = st.send_tx.clone();
            let chunks = drain_audio_chunks(&mut st.audio_scratch);
            (send_tx, chunks)
        };
        if let Some(tx) = send_tx {
            for chunk in chunks {
                let _ = tx.send(SendItem::Audio(chunk));
            }
        }
        self.task_started.notify_waiters();
    }

    fn record_result(&self, value: &Value) {
        let sentence = value
            .get("payload")
            .and_then(|p| p.get("output"))
            .and_then(|o| o.get("sentence"));
        let Some(sentence) = sentence else {
            return;
        };
        let Some(text) = sentence.get("text").and_then(Value::as_str) else {
            return;
        };
        let trimmed = text.trim();
        if trimmed.is_empty() {
            return;
        }
        let is_sentence_final = sentence.get("end_time").is_some();
        let mut st = self.state.lock();
        st.last_result_text = trimmed.to_string();
        if is_sentence_final && st.final_segments.last().map(|s| s.as_str()) != Some(trimmed) {
            st.final_segments.push(trimmed.to_string());
        }
    }

    fn finish_success(&self) {
        let (tx, text, duration_ms) = {
            let mut st = self.state.lock();
            if st.task_finished {
                return;
            }
            st.task_finished = true;
            st.send_tx.take();
            let text = if st.final_segments.is_empty() {
                st.last_result_text.clone()
            } else {
                st.final_segments.join("")
            };
            let duration_ms = if st.bytes_received > 0 {
                st.bytes_received / BYTES_PER_MS
            } else {
                st.start
                    .map(|start| start.elapsed().as_millis() as u64)
                    .unwrap_or_default()
            };
            (st.final_tx.take(), text, duration_ms)
        };
        if let Some(tx) = tx {
            let _ = tx.send(Ok(RawTranscript { text, duration_ms }));
        }
        self.close_on_runtime();
    }

    fn finish_with_partial_or_error(&self, error: BailianASRError) {
        let has_partial = {
            let st = self.state.lock();
            !st.last_result_text.trim().is_empty() || !st.final_segments.is_empty()
        };
        if has_partial {
            // 与 Volcengine 保持一致：连接异常但已有 partial 时优先兜底返回，避免丢失用户已识别出的内容。
            self.finish_success();
        } else {
            self.finish_error(error);
        }
    }

    fn finish_error(&self, error: BailianASRError) {
        let tx = {
            let mut st = self.state.lock();
            if st.task_finished {
                return;
            }
            st.task_finished = true;
            st.send_tx.take();
            st.final_tx.take()
        };
        if let Some(tx) = tx {
            let _ = tx.send(Err(error));
        }
        self.close_on_runtime();
    }

    fn close_on_runtime(&self) {
        let writer = Arc::clone(&self.writer);
        if let Some(handle) = self.state.lock().runtime.clone() {
            handle.spawn(async move {
                let _ = close_writer(&writer).await;
            });
        }
    }
}

impl AudioConsumer for BailianRealtimeASR {
    fn consume_pcm_chunk(&self, pcm: &[u8]) {
        if pcm.is_empty() {
            return;
        }
        let (send_tx, chunks) = {
            let mut st = self.state.lock();
            st.bytes_received = st.bytes_received.saturating_add(pcm.len() as u64);
            if !st.task_started {
                st.pending_audio.extend_from_slice(pcm);
                return;
            }
            st.audio_scratch.extend_from_slice(pcm);
            let chunks = drain_audio_chunks(&mut st.audio_scratch);
            (st.send_tx.clone(), chunks)
        };
        if let Some(tx) = send_tx {
            for chunk in chunks {
                let _ = tx.send(SendItem::Audio(chunk));
            }
        }
    }
}

fn drain_audio_chunks(buffer: &mut Vec<u8>) -> Vec<Vec<u8>> {
    let mut chunks = Vec::new();
    while buffer.len() >= TARGET_AUDIO_CHUNK_BYTES {
        chunks.push(buffer.drain(..TARGET_AUDIO_CHUNK_BYTES).collect());
    }
    chunks
}

fn run_task_message(task_id: &str, model: &str, vocabulary_id: Option<&str>) -> String {
    let mut parameters = json!({
        "sample_rate": 16000,
        "format": "pcm"
    });
    if let Some(vocabulary_id) = vocabulary_id.map(str::trim).filter(|id| !id.is_empty()) {
        parameters["vocabulary_id"] = Value::String(vocabulary_id.to_string());
    }

    json!({
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex"
        },
        "payload": {
            "task_group": "audio",
            "task": "asr",
            "function": "recognition",
            "model": model,
            "parameters": parameters,
            "input": {}
        }
    })
    .to_string()
}

fn finish_task_message(task_id: &str) -> String {
    json!({
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex"
        },
        "payload": { "input": {} }
    })
    .to_string()
}

async fn send_text(writer: &SharedWriter, text: String) -> Result<(), BailianASRError> {
    let mut guard = writer.lock().await;
    let Some(ws) = guard.as_mut() else {
        return Err(BailianASRError::ConnectionFailed(
            "websocket writer not available".to_string(),
        ));
    };
    ws.send(Message::Text(text))
        .await
        .map_err(|e| BailianASRError::SendFailed(e.to_string()))
}

async fn send_binary(writer: &SharedWriter, data: Vec<u8>) -> Result<(), BailianASRError> {
    let mut guard = writer.lock().await;
    let Some(ws) = guard.as_mut() else {
        return Err(BailianASRError::ConnectionFailed(
            "websocket writer not available".to_string(),
        ));
    };
    ws.send(Message::Binary(data))
        .await
        .map_err(|e| BailianASRError::SendFailed(e.to_string()))
}

async fn close_writer(writer: &SharedWriter) -> Result<(), BailianASRError> {
    let mut guard = writer.lock().await;
    if let Some(mut ws) = guard.take() {
        let _ = ws.close().await;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn credentials_apply_default_endpoint_and_model() {
        let creds = BailianCredentials {
            api_key: "sk-test".to_string(),
            endpoint: "".to_string(),
            model: "".to_string(),
            vocabulary_id: None,
        };
        assert_eq!(creds.normalized_endpoint(), DEFAULT_ENDPOINT);
        assert_eq!(creds.normalized_model(), DEFAULT_MODEL);
    }

    #[test]
    fn run_task_message_uses_pcm_16k() {
        let value: Value =
            serde_json::from_str(&run_task_message("abc", DEFAULT_MODEL, None)).unwrap();
        assert_eq!(value["header"]["action"], "run-task");
        assert_eq!(value["payload"]["model"], DEFAULT_MODEL);
        assert_eq!(value["payload"]["parameters"]["sample_rate"], 16000);
        assert_eq!(value["payload"]["parameters"]["format"], "pcm");
        assert!(value["payload"]["parameters"]["vocabulary_id"].is_null());
    }

    #[test]
    fn run_task_message_includes_optional_vocabulary_id() {
        let value: Value =
            serde_json::from_str(&run_task_message("abc", DEFAULT_MODEL, Some(" vocab-123 ")))
                .unwrap();
        assert_eq!(value["payload"]["parameters"]["vocabulary_id"], "vocab-123");
    }

    #[test]
    fn drain_audio_chunks_keeps_tail_buffered() {
        let mut buffer = vec![1u8; TARGET_AUDIO_CHUNK_BYTES * 2 + 17];
        let chunks = drain_audio_chunks(&mut buffer);
        assert_eq!(chunks.len(), 2);
        assert_eq!(chunks[0].len(), TARGET_AUDIO_CHUNK_BYTES);
        assert_eq!(chunks[1].len(), TARGET_AUDIO_CHUNK_BYTES);
        assert_eq!(buffer.len(), 17);
    }
}
