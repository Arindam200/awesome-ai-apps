//! Streaming ASR providers.
//!
//! Mirrors the Swift `OpenLessASR` library. The Volcengine SAUC bigmodel
//! client is the reference implementation; the wire protocol lives in
//! `frame.rs` (binary frame codec) and the session lifecycle in
//! `volcengine.rs`.

pub mod bailian;
mod frame;
pub mod local;
pub mod qingyu;
pub mod qwen_realtime;
pub mod volcengine;
pub mod wav;
pub mod whisper;

pub use bailian::{BailianCredentials, BailianRealtimeASR};
pub use qwen_realtime::{QwenRealtimeASR, QwenRealtimeCredentials};
pub use volcengine::{VolcengineCredentials, VolcengineStreamingASR};
pub use whisper::WhisperBatchASR;

/// Sink for raw 16 kHz / 16-bit / mono PCM bytes coming off the recorder.
///
/// The Recorder pushes chunks here as soon as it has them; the ASR session
/// is free to batch internally before flushing to the network.
pub trait AudioConsumer: Send + Sync {
    fn consume_pcm_chunk(&self, pcm: &[u8]);
}

/// What the ASR session yielded once the stream closed.
#[derive(Debug, Clone)]
pub struct RawTranscript {
    pub text: String,
    pub duration_ms: u64,
}

/// User-defined hotword the ASR provider may use to bias decoding.
#[derive(Debug, Clone)]
pub struct DictionaryHotword {
    pub phrase: String,
    pub enabled: bool,
}
