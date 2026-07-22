//! 本地 Qwen3-ASR 一键"加载 + 测试"实现。
//!
//! 流程：
//!   1. 用 antirez 项目自带的 `samples/test_speech.wav` 作输入（编进二进制）
//!   2. WAV 解析（16kHz mono 16-bit PCM，但 fmt 后面可能有 LIST/INFO 等
//!      非 data chunk，必须按 RIFF 标准走 chunk 链找 "data"，不能 +44 硬偏移）
//!   3. 加载模型，跑 transcribe_audio，分别记录 load_ms / transcribe_ms
//!   4. 给前端用：用户点击「加载并测试」按钮立即知道模型是否能跑、有多快、识别什么

#[cfg(target_os = "macos")]
use std::path::Path;
#[cfg(target_os = "macos")]
use std::sync::Arc;
#[cfg(target_os = "macos")]
use std::time::Instant;

use anyhow::Result;
use serde::Serialize;

use super::models::{model_dir, ModelId};

/// 内嵌测试音频。原始文件 `vendor/qwen-asr/samples/test_speech.wav`
/// 内容："Hello. This is a test of the Voxtrail speech-to-text system."
#[cfg(target_os = "macos")]
const TEST_WAV: &[u8] = include_bytes!("../../../vendor/qwen-asr/samples/test_speech.wav");

/// 测试结果给前端展示。
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TestResult {
    pub backend: String,
    pub model_id: String,
    pub expected_text: String,
    pub transcribed_text: String,
    pub audio_ms: u64,
    pub load_ms: u64,
    pub transcribe_ms: u64,
}

#[cfg(target_os = "macos")]
pub async fn run_test(model_id: ModelId) -> Result<TestResult> {
    let dir = model_dir(model_id)?;
    if !dir.exists() {
        anyhow::bail!("模型目录不存在：{}（请先下载）", dir.display());
    }

    let samples = decode_wav_16k_mono(TEST_WAV)?;
    let audio_ms = (samples.len() as u64) * 1000 / 16_000;

    // qwen_load 是同步阻塞调用且较慢（数秒）；扔到 spawn_blocking 不阻塞 tokio runtime。
    let load_start = Instant::now();
    let dir_for_blocking = dir.clone();
    let engine = tauri::async_runtime::spawn_blocking(move || load_engine(&dir_for_blocking))
        .await
        .map_err(|e| anyhow::anyhow!("spawn_blocking join failed: {e:#}"))??;
    let load_ms = load_start.elapsed().as_millis() as u64;

    // transcribe_audio 也是阻塞 + 重活，同样扔到 blocking pool。
    let trans_start = Instant::now();
    let engine_clone = Arc::clone(&engine);
    let text =
        tauri::async_runtime::spawn_blocking(move || engine_clone.transcribe_audio(&samples))
            .await
            .map_err(|e| anyhow::anyhow!("spawn_blocking join failed: {e:#}"))??;
    let transcribe_ms = trans_start.elapsed().as_millis() as u64;

    Ok(TestResult {
        backend: "Apple Accelerate (AMX/NEON, CPU)".into(),
        model_id: model_id.as_str().into(),
        expected_text: "Hello. This is a test of the Voxtrail speech-to-text system.".into(),
        transcribed_text: text,
        audio_ms,
        load_ms,
        transcribe_ms,
    })
}

#[cfg(not(target_os = "macos"))]
pub async fn run_test(_model_id: ModelId) -> Result<TestResult> {
    anyhow::bail!("本地 ASR 引擎本期仅 macOS 可用（见 issue #256）")
}

#[cfg(target_os = "macos")]
fn load_engine(dir: &Path) -> Result<Arc<super::QwenAsrEngine>> {
    let engine = super::QwenAsrEngine::load(dir)?;
    Ok(Arc::new(engine))
}

/// 严格按 RIFF 走 chunk 链找 "data" —— jfk.wav / test_speech.wav 都在
/// fmt chunk 后面带了 LIST/INFO 元数据，硬编码 +44 会读到垃圾。
fn decode_wav_16k_mono(bytes: &[u8]) -> Result<Vec<f32>> {
    if bytes.len() < 44 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        anyhow::bail!("不是有效的 RIFF/WAVE 文件");
    }

    let mut cursor = 12usize;
    let mut sample_rate: u32 = 0;
    let mut channels: u16 = 0;
    let mut bits_per_sample: u16 = 0;
    let mut data_offset: usize = 0;
    let mut data_size: usize = 0;

    while cursor + 8 <= bytes.len() {
        let id = &bytes[cursor..cursor + 4];
        let size = u32::from_le_bytes(bytes[cursor + 4..cursor + 8].try_into().unwrap()) as usize;
        let body_start = cursor + 8;

        match id {
            b"fmt " => {
                if body_start + 16 > bytes.len() {
                    anyhow::bail!("fmt chunk 越界");
                }
                let format =
                    u16::from_le_bytes(bytes[body_start..body_start + 2].try_into().unwrap());
                if format != 1 {
                    anyhow::bail!("只支持 PCM（format=1），当前 format={format}");
                }
                channels =
                    u16::from_le_bytes(bytes[body_start + 2..body_start + 4].try_into().unwrap());
                sample_rate =
                    u32::from_le_bytes(bytes[body_start + 4..body_start + 8].try_into().unwrap());
                bits_per_sample =
                    u16::from_le_bytes(bytes[body_start + 14..body_start + 16].try_into().unwrap());
            }
            b"data" => {
                data_offset = body_start;
                data_size = size;
                break;
            }
            _ => { /* LIST / INFO / 其它 metadata —— 跳过 */ }
        }
        // chunk 体长度需按偶数对齐
        let advance = size + (size & 1);
        cursor = body_start + advance;
    }

    if data_offset == 0 || data_size == 0 {
        anyhow::bail!("未找到 data chunk");
    }
    if sample_rate != 16_000 || channels != 1 || bits_per_sample != 16 {
        anyhow::bail!(
            "测试 WAV 必须是 16kHz mono 16-bit；实际 {sample_rate}Hz / {channels}ch / {bits_per_sample}bit"
        );
    }

    let data_end = (data_offset + data_size).min(bytes.len());
    let samples_i16 = &bytes[data_offset..data_end];
    let samples: Vec<f32> = samples_i16
        .chunks_exact(2)
        .map(|c| i16::from_le_bytes([c[0], c[1]]) as f32 / 32768.0)
        .collect();
    Ok(samples)
}
