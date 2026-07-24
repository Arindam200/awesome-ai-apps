//! 麦克风采集：cpal 拉流 → 16 kHz 单声道 Int16 PCM → 喂给 `AudioConsumer`。
//!
//! 与 Swift 版 `OpenLessRecorder/Recorder.swift` 行为对齐：
//! - 输出格式固定为 16 kHz 单声道小端 Int16，方便 ASR 直接消费。
//! - 多声道输入 → 算术平均下混到单声道；非 16 kHz → 线性插值重采样。
//! - 每个 buffer 计算 RMS 归一化到 0..1（再乘以 4 并 clamp），用于胶囊电平动画。
//! - 每 ~50 个回调打一行诊断日志，包含峰值 RMS。
//!
//! 线程模型：
//! - cpal `Stream` 是 `!Send`，所以独立线程持有它。
//! - 主线程通过 `AtomicBool` 通知"该停了"，并 `join` 线程；线程内 `drop` Stream。

use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::Arc;
use std::thread::{self, JoinHandle};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, StreamConfig};
use parking_lot::Mutex;
use serde::Serialize;
use thiserror::Error;

/// 目标采样率（与 Swift 端常量一致；不要改）。
const TARGET_SAMPLE_RATE: u32 = 16_000;
/// 每多少个回调打一次诊断日志。
const LOG_EVERY_N_CALLBACKS: usize = 50;
/// RMS → UI 电平的放大系数，与 Swift 端 `min(1.0, rms * 4)` 一致。
const LEVEL_RMS_GAIN: f32 = 4.0;

/// 接收已重采样 Int16 PCM 字节流（小端）的下游。
pub trait AudioConsumer: Send + Sync {
    /// 每次拿到的是若干 Int16 样本拼成的 little-endian 字节序列。
    /// 长度一定是 2 的倍数。
    fn consume_pcm_chunk(&self, pcm: &[u8]);
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MicrophoneDevice {
    pub name: String,
    pub is_default: bool,
}

/// 采集器错误。
#[derive(Debug, Error)]
pub enum RecorderError {
    #[error("microphone permission denied")]
    PermissionDenied,
    #[error("audio engine failed: {0}")]
    EngineFailed(String),
}

/// 采集器句柄。Drop 时不会自动停止——必须显式调用 `stop`。
pub struct Recorder {
    stop_flag: Arc<AtomicBool>,
    join_handle: Mutex<Option<JoinHandle<()>>>,
}

impl Recorder {
    /// 启动采集。`consumer` 收到 16 kHz/Mono/Int16-LE 的 PCM；
    /// `level_handler` 收到 0..1 的 RMS 电平。
    ///
    /// 实际的 cpal Stream 在独立线程里构造、播放、最终析构——因为它 `!Send`。
    pub fn start(
        microphone_device_name: Option<String>,
        consumer: Arc<dyn AudioConsumer>,
        level_handler: Arc<dyn Fn(f32) + Send + Sync>,
    ) -> Result<(Self, Receiver<RecorderError>), RecorderError> {
        // 启动信号：子线程构造 Stream 完成后通过 startup_tx 报告结果。
        let (startup_tx, startup_rx) = channel::<Result<(), RecorderError>>();
        // 运行期错误：Stream 已成功启动后，cpal 通过 err_cb 异步上报。
        let (runtime_error_tx, runtime_error_rx) = channel::<RecorderError>();
        let stop_flag = Arc::new(AtomicBool::new(false));
        let stop_for_thread = Arc::clone(&stop_flag);

        let join_handle = thread::Builder::new()
            .name("openless-recorder".into())
            .spawn(move || {
                run_audio_thread(
                    microphone_device_name,
                    consumer,
                    level_handler,
                    stop_for_thread,
                    startup_tx,
                    runtime_error_tx,
                );
            })
            .map_err(|e| RecorderError::EngineFailed(format!("spawn audio thread: {e}")))?;

        // 等待子线程报告启动结果。子线程要么 Send Ok 后继续 park，
        // 要么 Send Err 后立即退出——两种情况都保证 recv 能解锁。
        let startup_result = startup_rx
            .recv()
            .map_err(|e| RecorderError::EngineFailed(format!("audio thread vanished: {e}")))?;
        startup_result?;

        Ok((
            Self {
                stop_flag,
                join_handle: Mutex::new(Some(join_handle)),
            },
            runtime_error_rx,
        ))
    }

    /// 停止采集并等待音频线程退出。
    ///
    /// 用 `self`（消费）签名，与 Swift API 语义一致——一次性资源。
    pub fn stop(self) {
        self.stop_flag.store(true, Ordering::SeqCst);
        if let Some(handle) = self.join_handle.lock().take() {
            if let Err(err) = handle.join() {
                log::warn!("recorder 线程 join 失败: {:?}", err);
            }
        }
    }
}

pub fn list_input_devices() -> Result<Vec<MicrophoneDevice>, RecorderError> {
    let host = cpal::default_host();
    let default_name = host
        .default_input_device()
        .and_then(|device| device.name().ok());
    let devices = host
        .input_devices()
        .map_err(|e| RecorderError::EngineFailed(format!("input_devices: {e}")))?;

    let mut result = Vec::new();
    for device in devices {
        let name = match device.name() {
            Ok(name) => name,
            Err(err) => {
                log::warn!("[recorder] failed to read input device name: {err}");
                continue;
            }
        };
        result.push(MicrophoneDevice {
            is_default: default_name.as_deref() == Some(name.as_str()),
            name,
        });
    }
    Ok(result)
}

/// 音频线程主体：构造 Stream → 通过 startup_tx 报告 → 循环到 stop_flag。
fn run_audio_thread(
    microphone_device_name: Option<String>,
    consumer: Arc<dyn AudioConsumer>,
    level_handler: Arc<dyn Fn(f32) + Send + Sync>,
    stop_flag: Arc<AtomicBool>,
    startup_tx: Sender<Result<(), RecorderError>>,
    runtime_error_tx: Sender<RecorderError>,
) {
    let (stream, state) = match build_input_stream(
        microphone_device_name,
        consumer,
        level_handler,
        runtime_error_tx.clone(),
    ) {
        Ok(s) => s,
        Err(err) => {
            // 启动失败：通知主线程后即退出。
            let _ = startup_tx.send(Err(err));
            return;
        }
    };

    if let Err(err) = stream.play() {
        let _ = startup_tx.send(Err(RecorderError::EngineFailed(format!("play: {err}"))));
        return;
    }

    // 启动成功。
    let _ = startup_tx.send(Ok(()));

    // 启动 liveness watchdog 线程：检测录音回调是否静默停止
    const WATCHDOG_CHECK_INTERVAL_MS: u64 = 1000; // 每秒检查一次
    const CALLBACK_TIMEOUT_SECS: u64 = 3; // 3 秒没有回调视为异常
    const FIRST_CALLBACK_DEADLINE_SECS: u64 = 5; // 5 秒内必须收到首次回调

    let stop_flag_for_watchdog = Arc::clone(&stop_flag);
    let state_for_watchdog = Arc::clone(&state);
    let runtime_error_tx_for_watchdog = runtime_error_tx.clone();

    let watchdog_handle = thread::Builder::new()
        .name("openless-recorder-watchdog".into())
        .spawn(move || {
            // 记录 watchdog 启动时间，确保首次回调截止时间从播放真正开始时计时
            let watchdog_start_time = std::time::Instant::now();

            while !stop_flag_for_watchdog.load(Ordering::SeqCst) {
                thread::sleep(std::time::Duration::from_millis(WATCHDOG_CHECK_INTERVAL_MS));

                // 关键：sleep 醒来后必须重新检查 stop_flag，再去看 elapsed。
                //
                // 否则会与 hotkey-release 停采路径产生竞态：
                //   1. 用户松开 hotkey → end_session 调 rec.stop() → 设置 stop_flag
                //      → audio 线程 pause 了 cpal Stream → 回调真的静默
                //   2. 但 watchdog 此时正卡在上面的 1 秒 sleep 里
                //   3. sleep 结束后，若不重新检查 stop_flag，
                //      就会读到 last_callback_time 已经"老 4 秒"，
                //      把"我们主动停掉的录音"错报成 EngineFailed("录音回调静默停止 N 秒")，
                //      coordinator 收到错误后会终止 session、胶囊弹错。
                //
                // 修复方式是 sleep 后立即再 load 一次：进入 stop 流程后 watchdog 静默退出，
                // 不影响 watchdog 在真正活动期捕获 CoreAudio 设备掉线等真故障。
                if stop_flag_for_watchdog.load(Ordering::SeqCst) {
                    break;
                }

                let last_callback = *state_for_watchdog.last_callback_time.lock();
                match last_callback {
                    Some(last_time) => {
                        // 已收到首次回调，检查是否停止
                        let elapsed = last_time.elapsed();
                        if elapsed.as_secs() > CALLBACK_TIMEOUT_SECS {
                            log::error!(
                                "[recorder] watchdog: 录音回调已停止 {} 秒，触发错误恢复",
                                elapsed.as_secs()
                            );
                            let _ =
                                runtime_error_tx_for_watchdog.send(RecorderError::EngineFailed(
                                    format!("录音回调静默停止 {} 秒", elapsed.as_secs()),
                                ));
                            break; // 只报告一次
                        }
                    }
                    None => {
                        // 尚未收到首次回调，检查是否超过截止时间
                        let elapsed = watchdog_start_time.elapsed();
                        if elapsed.as_secs() > FIRST_CALLBACK_DEADLINE_SECS {
                            log::error!(
                                "[recorder] watchdog: {} 秒内未收到首次回调，触发错误恢复",
                                elapsed.as_secs()
                            );
                            let _ =
                                runtime_error_tx_for_watchdog.send(RecorderError::EngineFailed(
                                    format!("录音启动后 {} 秒内未收到回调", elapsed.as_secs()),
                                ));
                            break; // 只报告一次
                        }
                    }
                }
            }
        })
        .ok();

    // 自旋等待停止信号——cpal 自身没有 wait API，sleep 50ms 完全够用。
    while !stop_flag.load(Ordering::SeqCst) {
        thread::sleep(std::time::Duration::from_millis(50));
    }

    // 显式 pause 再 drop。
    // 实测 cpal 0.15 在 macOS coreaudio 上单纯 drop(Stream) 不会同步调用
    // AudioOutputUnitStop，AudioUnit 的 render callback 会继续被系统调，
    // process_callback 仍然以 ~5 ms / 帧的速率打 cb# 日志，macOS 一直认为
    // 我们在用 mic（橙点不灭）。pause() 走的是 StreamTrait::pause —— 在
    // coreaudio backend 里直接 AudioOutputUnitStop，同步终止 callback。
    // 之后 drop 处理 dispose / 资源释放。pause 失败时仅 warn，不阻塞 drop。
    if let Err(err) = stream.pause() {
        log::warn!("[recorder] cpal Stream pause before drop failed: {err}");
    }
    drop(stream);
    log::info!("[recorder] cpal Stream dropped (mic released)");

    // 等待 watchdog 线程退出
    if let Some(handle) = watchdog_handle {
        let _ = handle.join();
    }
}

/// 选默认输入设备 + 默认配置 + 构造 Stream。
fn build_input_stream(
    microphone_device_name: Option<String>,
    consumer: Arc<dyn AudioConsumer>,
    level_handler: Arc<dyn Fn(f32) + Send + Sync>,
    runtime_error_tx: Sender<RecorderError>,
) -> Result<(cpal::Stream, Arc<StreamState>), RecorderError> {
    let host = cpal::default_host();
    let device = select_input_device(&host, microphone_device_name.as_deref())?;

    let supported = device
        .default_input_config()
        .map_err(|e| classify_default_config_err(e.to_string()))?;

    let sample_format = supported.sample_format();
    let config: StreamConfig = supported.config();
    let input_sr = config.sample_rate.0;
    let channels = config.channels as usize;

    log::info!(
        "[recorder] inputDevice={} inputFormat sampleRate={} channels={} fmt={:?}",
        device.name().unwrap_or_else(|_| "<unknown>".into()),
        input_sr,
        channels,
        sample_format
    );

    let state = Arc::new(StreamState::new());
    let stream = build_stream_for_format(
        &device,
        &config,
        sample_format,
        consumer,
        level_handler,
        Arc::clone(&state),
        input_sr,
        channels,
        runtime_error_tx,
    )?;
    Ok((stream, state))
}

fn select_input_device(
    host: &cpal::Host,
    microphone_device_name: Option<&str>,
) -> Result<cpal::Device, RecorderError> {
    let preferred = microphone_device_name
        .map(str::trim)
        .filter(|name| !name.is_empty());
    if let Some(preferred) = preferred {
        let devices = host
            .input_devices()
            .map_err(|e| RecorderError::EngineFailed(format!("input_devices: {e}")))?;
        for device in devices {
            if device.name().ok().as_deref() == Some(preferred) {
                return Ok(device);
            }
        }
        log::warn!(
            "[recorder] preferred input device not found; falling back to default: {preferred}"
        );
    }

    host.default_input_device()
        .ok_or_else(|| RecorderError::EngineFailed("no default input device".into()))
}

/// 启动期 default_input_config 失败：依靠错误字符串关键字粗判权限问题。
/// cpal 在 macOS 没拿到 mic 授权时通常返回 `BackendSpecific`，我们尽力识别。
fn classify_default_config_err(msg: String) -> RecorderError {
    let lower = msg.to_lowercase();
    if lower.contains("permission") || lower.contains("denied") || lower.contains("authoriz") {
        RecorderError::PermissionDenied
    } else {
        RecorderError::EngineFailed(format!("default_input_config: {msg}"))
    }
}

/// 启动期 build_stream 失败：同上，可能是权限问题。
fn classify_build_stream_err(err: cpal::BuildStreamError) -> RecorderError {
    let msg = err.to_string();
    let lower = msg.to_lowercase();
    if lower.contains("permission") || lower.contains("denied") || lower.contains("authoriz") {
        RecorderError::PermissionDenied
    } else {
        RecorderError::EngineFailed(format!("build_input_stream: {msg}"))
    }
}

/// `SupportedStreamConfig` → 对应 SampleFormat 的具体 build 调用。
/// 只支持 cpal 常见的浮点和整型格式；其它格式 fallback 报错。
#[allow(clippy::too_many_arguments)]
fn build_stream_for_format(
    device: &cpal::Device,
    config: &StreamConfig,
    sample_format: SampleFormat,
    consumer: Arc<dyn AudioConsumer>,
    level_handler: Arc<dyn Fn(f32) + Send + Sync>,
    state: Arc<StreamState>,
    input_sr: u32,
    channels: usize,
    runtime_error_tx: Sender<RecorderError>,
) -> Result<cpal::Stream, RecorderError> {
    macro_rules! make_stream {
        ($t:ty, $to_f32:expr) => {{
            let consumer = Arc::clone(&consumer);
            let level_handler = Arc::clone(&level_handler);
            let state = Arc::clone(&state);
            let runtime_error_tx = runtime_error_tx.clone();
            let err_cb = move |err| {
                log::error!("[recorder] stream error: {err}");
                let _ =
                    runtime_error_tx.send(RecorderError::EngineFailed(format!("stream: {err}")));
            };
            device
                .build_input_stream::<$t, _, _>(
                    config,
                    move |data: &[$t], _info| {
                        let mut floats = Vec::with_capacity(data.len());
                        for s in data {
                            floats.push($to_f32(*s));
                        }
                        process_callback(
                            &floats,
                            channels,
                            input_sr,
                            consumer.as_ref(),
                            level_handler.as_ref(),
                            &state,
                        );
                    },
                    err_cb,
                    None,
                )
                .map_err(classify_build_stream_err)
        }};
    }

    match sample_format {
        SampleFormat::F32 => make_stream!(f32, |s: f32| s),
        SampleFormat::I16 => make_stream!(i16, |s: i16| s as f32 / i16::MAX as f32),
        SampleFormat::U16 => {
            make_stream!(u16, |s: u16| (s as f32 - 32768.0) / 32768.0)
        }
        SampleFormat::I32 => {
            make_stream!(i32, |s: i32| s as f32 / i32::MAX as f32)
        }
        SampleFormat::I8 => make_stream!(i8, |s: i8| s as f32 / i8::MAX as f32),
        SampleFormat::U8 => {
            make_stream!(u8, |s: u8| (s as f32 - 128.0) / 128.0)
        }
        other => Err(RecorderError::EngineFailed(format!(
            "unsupported sample format: {other:?}"
        ))),
    }
}

/// 跨回调维持的状态：上一帧残留（重采样），诊断计数与峰值。
struct StreamState {
    /// 上一回调没被消费完的"小数位置"。线性插值重采样会跨 buffer。
    resample_phase: Mutex<f64>,
    /// 上一回调最后一帧（单声道下混后），下一回调插值起点。
    last_sample: Mutex<f32>,
    callback_count: AtomicUsize,
    peak_input_rms_milli: AtomicUsize,
    peak_output_rms_milli: AtomicUsize,
    /// 最后一次成功调用 consumer 的时间戳（用于 liveness 检测）
    last_callback_time: Mutex<Option<std::time::Instant>>,
}

impl StreamState {
    fn new() -> Self {
        Self {
            resample_phase: Mutex::new(0.0),
            last_sample: Mutex::new(0.0),
            callback_count: AtomicUsize::new(0),
            peak_input_rms_milli: AtomicUsize::new(0),
            peak_output_rms_milli: AtomicUsize::new(0),
            // 初始化为 None，只有在第一次回调后才开始计时，避免误报慢启动设备
            last_callback_time: Mutex::new(None),
        }
    }
}

/// 单次回调：下混 → 重采样 → 量化为 i16 → 算 RMS → 喂下游。
fn process_callback(
    interleaved: &[f32],
    channels: usize,
    input_sr: u32,
    consumer: &dyn AudioConsumer,
    level_handler: &(dyn Fn(f32) + Send + Sync),
    state: &StreamState,
) {
    if interleaved.is_empty() || channels == 0 {
        return;
    }

    let mono = downmix_to_mono(interleaved, channels);
    let input_rms = rms(&mono);

    let resampled = resample_to_target(&mono, input_sr, TARGET_SAMPLE_RATE, state);
    if resampled.is_empty() {
        return;
    }

    let (pcm_bytes, output_rms) = quantize_to_i16_le(&resampled);
    let level = (output_rms * LEVEL_RMS_GAIN).clamp(0.0, 1.0);

    consumer.consume_pcm_chunk(&pcm_bytes);
    level_handler(level);

    // 更新最后一次成功调用的时间戳（用于 liveness 检测）
    *state.last_callback_time.lock() = Some(std::time::Instant::now());

    // 诊断：峰值 + 周期性日志。
    let count = state.callback_count.fetch_add(1, Ordering::Relaxed) + 1;
    update_peak(&state.peak_input_rms_milli, input_rms);
    update_peak(&state.peak_output_rms_milli, output_rms);
    if count == 1 || count % LOG_EVERY_N_CALLBACKS == 0 {
        let pk_in = state.peak_input_rms_milli.load(Ordering::Relaxed) as f32 / 1000.0;
        let pk_out = state.peak_output_rms_milli.load(Ordering::Relaxed) as f32 / 1000.0;
        log::info!(
            "[recorder] cb#{count} inLen={} outLen={} inRMS={:.5} outRMS={:.5} peakIn={:.5} peakOut={:.5}",
            mono.len(),
            resampled.len(),
            input_rms,
            output_rms,
            pk_in,
            pk_out
        );
    }
}

/// 多声道交错样本 → 单声道（算术平均）。
fn downmix_to_mono(interleaved: &[f32], channels: usize) -> Vec<f32> {
    if channels == 1 {
        return interleaved.to_vec();
    }
    let frames = interleaved.len() / channels;
    let mut out = Vec::with_capacity(frames);
    for i in 0..frames {
        let base = i * channels;
        let mut sum = 0.0f32;
        for c in 0..channels {
            sum += interleaved[base + c];
        }
        out.push(sum / channels as f32);
    }
    out
}

/// 线性插值重采样到目标采样率，状态跨 buffer 保留。
///
/// 算法说明：把上一回调的尾样本作为本回调起点，避免缝隙；用浮点
/// `phase` 记录"已经走到上一帧的多少位置"，每输出一个目标样本前进
/// `step = src_sr / dst_sr`。
fn resample_to_target(samples: &[f32], src_sr: u32, dst_sr: u32, state: &StreamState) -> Vec<f32> {
    if samples.is_empty() {
        return Vec::new();
    }
    if src_sr == dst_sr {
        // 直通——但仍需更新 last_sample，便于切换设备时不抖。
        if let Some(&last) = samples.last() {
            *state.last_sample.lock() = last;
        }
        return samples.to_vec();
    }

    let step = src_sr as f64 / dst_sr as f64;
    let mut phase = *state.resample_phase.lock();
    let prev = *state.last_sample.lock();

    // 估容量：dst_len ≈ src_len / step。
    let estimated = ((samples.len() as f64) / step).ceil() as usize + 1;
    let mut out = Vec::with_capacity(estimated);

    // 把 prev 作为虚拟索引 -1 的样本。
    // phase 表示"距离当前段起点还差多少"，区间 [0, 1)。
    while phase < samples.len() as f64 {
        let idx_floor = phase.floor() as isize;
        let frac = (phase - phase.floor()) as f32;
        let a = if idx_floor < 0 {
            prev
        } else {
            samples[idx_floor as usize]
        };
        let b_index = (idx_floor + 1) as usize;
        if b_index >= samples.len() {
            // 没有下一帧可插值——把当前帧填进去并退出，让下一回调接力。
            out.push(a);
            phase += step;
            break;
        }
        let b = samples[b_index];
        out.push(a + (b - a) * frac);
        phase += step;
    }

    // 把 phase 折回到"相对于下一回调起点"——减去当前 buffer 长度。
    let new_phase = phase - samples.len() as f64;
    *state.resample_phase.lock() = new_phase.max(0.0);
    *state.last_sample.lock() = *samples.last().unwrap_or(&0.0);

    out
}

/// f32 → i16 little-endian 字节流，并顺手算 RMS（归一化到 0..1）。
fn quantize_to_i16_le(samples: &[f32]) -> (Vec<u8>, f32) {
    let mut bytes = Vec::with_capacity(samples.len() * 2);
    let mut sum_sq = 0.0f64;
    for &s in samples {
        let clamped = s.clamp(-1.0, 1.0);
        let q = (clamped * 32767.0) as i16;
        bytes.extend_from_slice(&q.to_le_bytes());
        let n = clamped as f64;
        sum_sq += n * n;
    }
    let rms = if samples.is_empty() {
        0.0
    } else {
        (sum_sq / samples.len() as f64).sqrt() as f32
    };
    (bytes, rms)
}

/// f32 切片 RMS（归一化到 0..1，假设输入已在 [-1, 1]）。
fn rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let mut sum_sq = 0.0f64;
    for &s in samples {
        let n = s as f64;
        sum_sq += n * n;
    }
    (sum_sq / samples.len() as f64).sqrt() as f32
}

/// 用毫单位整数原子值近似存储 f32 峰值（避免引入额外锁）。
fn update_peak(slot: &AtomicUsize, current: f32) {
    let scaled = (current * 1000.0).round().max(0.0) as usize;
    let mut prev = slot.load(Ordering::Relaxed);
    while scaled > prev {
        match slot.compare_exchange_weak(prev, scaled, Ordering::Relaxed, Ordering::Relaxed) {
            Ok(_) => break,
            Err(observed) => prev = observed,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex as StdMutex};

    #[derive(Default)]
    struct RecordingConsumer {
        chunks: StdMutex<Vec<Vec<u8>>>,
    }

    impl AudioConsumer for RecordingConsumer {
        fn consume_pcm_chunk(&self, pcm: &[u8]) {
            self.chunks.lock().unwrap().push(pcm.to_vec());
        }
    }

    fn decode_i16_le(bytes: &[u8]) -> Vec<i16> {
        bytes
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect()
    }

    #[test]
    fn downmix_to_mono_averages_complete_interleaved_frames() {
        let mono = downmix_to_mono(&[1.0, -1.0, 0.5, 0.25, 0.0], 2);

        assert_eq!(mono, vec![0.0, 0.375]);
    }

    #[test]
    fn quantize_to_i16_le_clamps_and_reports_rms() {
        let (bytes, rms) = quantize_to_i16_le(&[-2.0, 0.0, 0.5, 2.0]);
        let samples = bytes
            .chunks_exact(2)
            .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
            .collect::<Vec<_>>();

        assert_eq!(samples, vec![-32767, 0, 16383, 32767]);
        assert!((rms - 0.75).abs() < 0.0001);
    }

    #[test]
    fn resample_passthrough_updates_tail_sample_without_phase_drift() {
        let state = StreamState::new();
        *state.resample_phase.lock() = 0.5;

        let out = resample_to_target(
            &[0.1, -0.2, 0.3],
            TARGET_SAMPLE_RATE,
            TARGET_SAMPLE_RATE,
            &state,
        );

        assert_eq!(out, vec![0.1, -0.2, 0.3]);
        assert_eq!(*state.last_sample.lock(), 0.3);
        assert_eq!(*state.resample_phase.lock(), 0.5);
    }

    #[test]
    fn resample_upsamples_with_linear_interpolation_and_tail_state() {
        let state = StreamState::new();

        let out = resample_to_target(&[0.0, 1.0], 8_000, TARGET_SAMPLE_RATE, &state);

        assert_eq!(out, vec![0.0, 0.5, 1.0]);
        assert_eq!(*state.last_sample.lock(), 1.0);
        assert_eq!(*state.resample_phase.lock(), 0.0);
    }

    #[test]
    fn process_callback_resamples_non_target_input_before_emitting_pcm() {
        let consumer = RecordingConsumer::default();
        let levels = Arc::new(StdMutex::new(Vec::new()));
        let levels_for_handler = Arc::clone(&levels);
        let state = StreamState::new();

        process_callback(
            &[0.0, 1.0],
            1,
            8_000,
            &consumer,
            &move |level| levels_for_handler.lock().unwrap().push(level),
            &state,
        );

        let chunks = consumer.chunks.lock().unwrap();
        assert_eq!(chunks.len(), 1);
        assert_eq!(decode_i16_le(&chunks[0]), vec![0, 16383, 32767]);
        assert_eq!(*levels.lock().unwrap(), vec![1.0]);
        assert_eq!(state.callback_count.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn process_callback_reports_scaled_rms_level_and_peaks() {
        let consumer = RecordingConsumer::default();
        let levels = Arc::new(StdMutex::new(Vec::new()));
        let levels_for_handler = Arc::clone(&levels);
        let state = StreamState::new();

        process_callback(
            &[0.125, -0.125],
            1,
            TARGET_SAMPLE_RATE,
            &consumer,
            &move |level| levels_for_handler.lock().unwrap().push(level),
            &state,
        );

        let levels = levels.lock().unwrap();
        assert_eq!(levels.len(), 1);
        assert!((levels[0] - 0.5).abs() < 0.0001);
        assert_eq!(state.peak_input_rms_milli.load(Ordering::Relaxed), 125);
        assert_eq!(state.peak_output_rms_milli.load(Ordering::Relaxed), 125);
    }

    #[test]
    fn process_callback_emits_pcm_level_and_liveness_marker() {
        let consumer = RecordingConsumer::default();
        let levels = Arc::new(StdMutex::new(Vec::new()));
        let levels_for_handler = Arc::clone(&levels);
        let state = StreamState::new();

        process_callback(
            &[0.25, -0.25],
            1,
            TARGET_SAMPLE_RATE,
            &consumer,
            &move |level| levels_for_handler.lock().unwrap().push(level),
            &state,
        );

        let chunks = consumer.chunks.lock().unwrap();
        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0].len(), 4);
        assert_eq!(*levels.lock().unwrap(), vec![1.0]);
        assert!(state.last_callback_time.lock().is_some());
        assert_eq!(state.callback_count.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn process_callback_ignores_empty_or_zero_channel_input_without_liveness_marker() {
        let consumer = RecordingConsumer::default();
        let levels = Arc::new(StdMutex::new(Vec::new()));
        let levels_for_handler = Arc::clone(&levels);
        let state = StreamState::new();

        process_callback(
            &[],
            1,
            TARGET_SAMPLE_RATE,
            &consumer,
            &move |level| levels_for_handler.lock().unwrap().push(level),
            &state,
        );
        process_callback(
            &[0.25, -0.25],
            0,
            TARGET_SAMPLE_RATE,
            &consumer,
            &move |level| levels.lock().unwrap().push(level),
            &state,
        );

        assert!(consumer.chunks.lock().unwrap().is_empty());
        assert!(state.last_callback_time.lock().is_none());
        assert_eq!(state.callback_count.load(Ordering::Relaxed), 0);
    }
}
