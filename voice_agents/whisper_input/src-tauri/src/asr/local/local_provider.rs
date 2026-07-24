//! 本地 Qwen3-ASR 在 dictation 路径上的适配器。
//!
//! 与 `WhisperBatchASR` 形状对齐：实现 `AudioConsumer` 缓冲 PCM，stop 时
//! 调 `transcribe_stream`，期间每个稳定 token 通过 Tauri 事件
//! `local-asr-token` 推到前端胶囊做实时显示。
//!
//! engine 现在由 `LocalAsrCache` 提供——Coordinator 在 build_local_qwen3 里
//! 取已缓存的引擎再传进来，避免每次会话都重加载 1.2GB+ 模型。

#[cfg(target_os = "macos")]
use std::sync::Arc;

#[cfg(target_os = "macos")]
use anyhow::{Context, Result};
#[cfg(target_os = "macos")]
use parking_lot::Mutex;
#[cfg(target_os = "macos")]
use tauri::{AppHandle, Emitter};

#[cfg(target_os = "macos")]
use super::QwenAsrEngine;
#[cfg(target_os = "macos")]
use crate::asr::RawTranscript;

#[cfg(target_os = "macos")]
pub struct LocalQwenAsr {
    engine: Arc<QwenAsrEngine>,
    /// 16-bit LE PCM 字节缓冲（recorder 推什么我们存什么），在 transcribe 时再
    /// 转 f32 喂给 C 端。一次会话最多几 MB，clone 一次成本可接受。
    buffer: Mutex<Vec<u8>>,
    app: AppHandle,
}

#[cfg(target_os = "macos")]
impl LocalQwenAsr {
    pub fn new(app: AppHandle, engine: Arc<QwenAsrEngine>) -> Self {
        Self {
            engine,
            buffer: Mutex::new(Vec::new()),
            app,
        }
    }

    /// stop 时调用：把 buffer 的 i16 PCM 转 f32，跑流式转写，token 实时
    /// 通过事件吐到前端胶囊；最终文本一起返回供 polish/insert。
    pub async fn transcribe(self: Arc<Self>) -> Result<RawTranscript> {
        let pcm_bytes = std::mem::take(&mut *self.buffer.lock());
        if pcm_bytes.is_empty() {
            return Ok(RawTranscript {
                text: String::new(),
                duration_ms: 0,
            });
        }
        let duration_ms = (pcm_bytes.len() as u64 / 2) * 1000 / 16_000;
        let samples_f32 = i16_le_bytes_to_f32(&pcm_bytes);

        // 注册 token 回调：每个稳定 token 抛 `local-asr-token` 事件。
        // capsule 前端按 sessionId 累积显示。
        let app = self.app.clone();
        self.engine.set_token_handler(Some(move |piece: &str| {
            if let Err(e) = app.emit("local-asr-token", piece.to_string()) {
                log::warn!("[local-asr] emit token failed: {e}");
            }
        }));

        // qwen_transcribe_stream 是阻塞调用；用 spawn_blocking 防止占住 tokio runtime。
        // 用 tauri::async_runtime::spawn_blocking 而非 tokio 的 —— 同 download.rs 注释，
        // 走 Tauri 持有的 runtime handle，不依赖调用方上下文（虽然这里目前都在 async 路径上调，
        // 但保持一致更稳）。
        let engine = Arc::clone(&self.engine);
        let text =
            tauri::async_runtime::spawn_blocking(move || engine.transcribe_stream(&samples_f32))
                .await
                .context("transcribe spawn_blocking join 失败")?
                .context("qwen_transcribe_stream 失败")?;

        // 解绑回调，避免 idle 期 C 端任何后续触发。
        self.engine.set_token_handler::<fn(&str)>(None);

        Ok(RawTranscript { text, duration_ms })
    }

    pub fn cancel(&self) {
        self.buffer.lock().clear();
    }
}

#[cfg(target_os = "macos")]
impl crate::recorder::AudioConsumer for LocalQwenAsr {
    fn consume_pcm_chunk(&self, pcm: &[u8]) {
        self.buffer.lock().extend_from_slice(pcm);
    }
}

#[cfg(target_os = "macos")]
fn i16_le_bytes_to_f32(bytes: &[u8]) -> Vec<f32> {
    bytes
        .chunks_exact(2)
        .map(|c| {
            let v = i16::from_le_bytes([c[0], c[1]]);
            v as f32 / 32768.0
        })
        .collect()
}
