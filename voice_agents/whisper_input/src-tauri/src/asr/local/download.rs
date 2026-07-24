//! Qwen3-ASR 模型下载管理 —— 并发分块 + 断点续传。
//!
//! 设计要点（与 huggingface_hub / aria2 / hf_transfer 同款）：
//! - **HTTP Range 分块**：32 MB 一块，避免长连接被 CDN 中途踢
//! - **N 并发**：4 个 worker 同时下不同 range，绕过 HF CDN 单连接限速
//! - **sparse 文件 + seek+write**：每块知道自己的 offset 直接写到位
//! - **`.partial.idx` 哨兵**：每完成一块原子追加索引；下次只下未完成的块
//! - **per-chunk retry**：4 次指数退避（1s/4s/16s）
//! - **服务端忽略 Range 返回 200 防御**：检测到非 206 直接 fail，让 retry 处理
//! - **取消尊重**：每块边界 + 每流块边界检查 AtomicBool

use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;

use anyhow::{Context, Result};
use futures_util::StreamExt;
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncSeekExt, AsyncWriteExt};

use super::models::{model_dir, ModelId, READY_SENTINEL};

/// 下载源镜像。
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Mirror {
    Huggingface,
    HfMirror,
}

impl Default for Mirror {
    fn default() -> Self {
        Mirror::Huggingface
    }
}

impl Mirror {
    pub fn base_url(self) -> &'static str {
        match self {
            Mirror::Huggingface => "https://huggingface.co",
            Mirror::HfMirror => "https://hf-mirror.com",
        }
    }

    pub fn from_str(s: &str) -> Self {
        match s {
            "hf-mirror" => Mirror::HfMirror,
            _ => Mirror::Huggingface,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Mirror::Huggingface => "huggingface",
            Mirror::HfMirror => "hf-mirror",
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RemoteFile {
    pub path: String,
    pub size: u64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RemoteInfo {
    pub model_id: String,
    pub mirror: String,
    pub files: Vec<RemoteFile>,
    pub total_bytes: u64,
}

#[derive(Debug, Deserialize)]
struct HfTreeEntry {
    #[serde(rename = "type")]
    entry_type: String,
    path: String,
    #[serde(default)]
    size: Option<u64>,
}

pub async fn fetch_remote_info(model_id: ModelId, mirror: Mirror) -> Result<RemoteInfo> {
    let client = build_client()?;
    let files = fetch_file_list(&client, model_id.hf_repo(), mirror).await?;
    let total_bytes = files.iter().map(|f| f.size).sum();
    Ok(RemoteInfo {
        model_id: model_id.as_str().into(),
        mirror: mirror.as_str().into(),
        files,
        total_bytes,
    })
}

async fn fetch_file_list(
    client: &reqwest::Client,
    repo: &str,
    mirror: Mirror,
) -> Result<Vec<RemoteFile>> {
    let url = format!("{}/api/models/{}/tree/main", mirror.base_url(), repo);
    let resp = client
        .get(&url)
        .send()
        .await
        .with_context(|| format!("HF tree API GET 失败: {url}"))?;
    if !resp.status().is_success() {
        anyhow::bail!("HF tree API HTTP {}: {url}", resp.status());
    }
    let entries: Vec<HfTreeEntry> = resp
        .json()
        .await
        .with_context(|| format!("HF tree JSON 解码失败: {url}"))?;
    let files: Vec<RemoteFile> = entries
        .into_iter()
        .filter(|e| e.entry_type == "file" && keep_file(&e.path))
        .map(|e| RemoteFile {
            path: e.path,
            size: e.size.unwrap_or(0),
        })
        .collect();
    if files.is_empty() {
        anyhow::bail!("HF tree 返回空文件列表 (repo={repo})");
    }
    Ok(files)
}

fn keep_file(path: &str) -> bool {
    if path.starts_with('.') {
        return false;
    }
    let lower = path.to_ascii_lowercase();
    if lower.ends_with(".md")
        || lower.ends_with(".png")
        || lower.ends_with(".jpg")
        || lower.ends_with(".jpeg")
        || lower.ends_with(".gif")
        || lower.ends_with(".svg")
    {
        return false;
    }
    let ext = lower.rsplit('.').next().unwrap_or("");
    matches!(
        ext,
        "json" | "safetensors" | "txt" | "bin" | "model" | "tiktoken"
    )
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadProgress {
    pub model_id: String,
    pub file: String,
    pub file_index: usize,
    pub file_count: usize,
    pub bytes_downloaded: u64,
    pub bytes_total: u64,
    pub phase: DownloadPhase,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum DownloadPhase {
    Started,
    Progress,
    Finished,
    Cancelled,
    Failed,
}

#[derive(Default)]
pub struct DownloadManager {
    cancel_flags: Mutex<std::collections::HashMap<String, Arc<AtomicBool>>>,
}

impl DownloadManager {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn start(self: &Arc<Self>, app: AppHandle, model_id: ModelId, mirror: Mirror) {
        let key = model_id.as_str().to_string();
        let flag = {
            let mut flags = self.cancel_flags.lock();
            if flags.contains_key(&key) {
                log::info!("[local-asr] download already in progress: {key}");
                return;
            }
            let f = Arc::new(AtomicBool::new(false));
            flags.insert(key.clone(), Arc::clone(&f));
            f
        };

        let manager = Arc::clone(self);
        tauri::async_runtime::spawn(async move {
            let result = run_download(&app, model_id, mirror, Arc::clone(&flag)).await;
            manager.cancel_flags.lock().remove(&key);
            match result {
                Ok(()) => log::info!("[local-asr] download finished: {key}"),
                Err(e) => log::error!("[local-asr] download failed: {key}: {e:#}"),
            }
        });
    }

    pub fn cancel(&self, model_id: ModelId) {
        if let Some(flag) = self.cancel_flags.lock().get(model_id.as_str()) {
            flag.store(true, Ordering::SeqCst);
            log::info!("[local-asr] cancel requested for {}", model_id.as_str());
        } else {
            log::info!(
                "[local-asr] cancel requested for {} but no active download",
                model_id.as_str()
            );
        }
    }

    pub fn is_active(&self, model_id: ModelId) -> bool {
        self.cancel_flags.lock().contains_key(model_id.as_str())
    }
}

fn build_client() -> Result<reqwest::Client> {
    // native-tls (macOS=SecureTransport) 不像 rustls 那样把 CDN unclean close
    // 当致命错误。
    //
    // User-Agent 用 aria2 的——hfd（hf-mirror 官方推荐）就是 aria2 包装，
    // 实测 aria2 UA 在 HF 反滥用规则里走白名单不挨 throttle；自定义 UA
    // (`openless/x`) 在 sustained 传输后会被 mirror 主动切流。
    reqwest::Client::builder()
        .use_native_tls()
        .user_agent("aria2/1.36.0")
        .connect_timeout(std::time::Duration::from_secs(30))
        .pool_idle_timeout(std::time::Duration::from_secs(60))
        .build()
        .context("build reqwest client failed")
}

async fn run_download(
    app: &AppHandle,
    model_id: ModelId,
    mirror: Mirror,
    cancel: Arc<AtomicBool>,
) -> Result<()> {
    let dir = model_dir(model_id)?;
    std::fs::create_dir_all(&dir)
        .with_context(|| format!("create model dir failed: {}", dir.display()))?;

    let client = build_client()?;
    let info = match fetch_remote_info(model_id, mirror).await {
        Ok(i) => i,
        Err(e) => {
            emit(
                app,
                DownloadProgress {
                    model_id: model_id.as_str().into(),
                    file: String::new(),
                    file_index: 0,
                    file_count: 0,
                    bytes_downloaded: 0,
                    bytes_total: 0,
                    phase: DownloadPhase::Failed,
                    error: Some(format!("拉文件清单失败: {e:#}")),
                },
            );
            return Err(e);
        }
    };
    let total_bytes = info.total_bytes;
    let file_count = info.files.len();

    emit(
        app,
        DownloadProgress {
            model_id: model_id.as_str().into(),
            file: String::new(),
            file_index: 0,
            file_count,
            bytes_downloaded: super::models::downloaded_bytes(model_id),
            bytes_total: total_bytes,
            phase: DownloadPhase::Started,
            error: None,
        },
    );

    // 多文件并发（aria2 -j 5 同款思路）：每个文件已下字节用 AtomicU64 累加，
    // 总进度 = 各文件已下字节之和 + 历史已完成文件大小。让小文件不阻塞大文件，
    // 也让大文件下半段（CDN throttle 时）剩余带宽喂别的文件。
    {
        std::fs::create_dir_all(&dir).ok();
        for file in &info.files {
            if let Some(parent) = dir.join(&file.path).parent() {
                let _ = std::fs::create_dir_all(parent);
            }
        }
    }

    let in_flight_bytes: Arc<Vec<AtomicU64>> =
        Arc::new(info.files.iter().map(|_| AtomicU64::new(0)).collect());
    let already_done_bytes: u64 = info
        .files
        .iter()
        .map(|f| {
            let d = dir.join(&f.path);
            if d.exists() {
                f.size
            } else {
                0
            }
        })
        .sum();

    let semaphore = Arc::new(tokio::sync::Semaphore::new(PARALLEL_FILES));
    let mut futs = futures_util::stream::FuturesUnordered::new();

    for (idx, file) in info.files.iter().enumerate() {
        let dest = dir.join(&file.path);
        if dest.exists() {
            // 已经下完的（目录里直接存在 dest 文件）跳过；前面 already_done_bytes 已计入
            continue;
        }
        let url = format!(
            "{}/{}/resolve/main/{}",
            mirror.base_url(),
            model_id.hf_repo(),
            file.path
        );
        let semaphore = Arc::clone(&semaphore);
        let client = client.clone();
        let cancel = Arc::clone(&cancel);
        let app = app.clone();
        let in_flight_bytes = Arc::clone(&in_flight_bytes);
        let model_id_str = model_id.as_str().to_string();
        let file_path = file.path.clone();
        let file_size = file.size;
        let _model_id = model_id; // copy of Copy for closure use
        let total_bytes_cap = total_bytes;
        let already_done = already_done_bytes;

        futs.push(tauri::async_runtime::spawn(async move {
            let _permit = match semaphore.acquire_owned().await {
                Ok(p) => p,
                Err(_) => return Err(anyhow::anyhow!("semaphore closed")),
            };
            if cancel.load(Ordering::SeqCst) {
                return Ok(());
            }
            // 进度回调：把该文件实时已下字节写到 in_flight_bytes[idx]，
            // 然后求所有 in_flight 之和 + already_done = 全模型总进度。
            let app_emit = app.clone();
            let model_id_emit = model_id_str.clone();
            let file_path_emit = file_path.clone();
            let in_flight_for_cb = Arc::clone(&in_flight_bytes);
            let on_progress: Arc<dyn Fn(u64) + Send + Sync> = Arc::new(move |bytes_in_file| {
                in_flight_for_cb[idx].store(bytes_in_file, Ordering::Relaxed);
                let total_in_flight: u64 = in_flight_for_cb
                    .iter()
                    .map(|a| a.load(Ordering::Relaxed))
                    .sum();
                let _ = app_emit.emit(
                    "local-asr-download-progress",
                    DownloadProgress {
                        model_id: model_id_emit.clone(),
                        file: file_path_emit.clone(),
                        file_index: idx,
                        file_count,
                        bytes_downloaded: already_done + total_in_flight,
                        bytes_total: total_bytes_cap,
                        phase: DownloadPhase::Progress,
                        error: None,
                    },
                );
            });

            let result = download_one(
                &client,
                &url,
                &dest,
                file_size,
                Arc::clone(&cancel),
                on_progress,
            )
            .await;
            // 文件下完 → 该 in_flight 永久 = file_size（避免 race 在 emit 时漏算）
            if result.is_ok() {
                in_flight_bytes[idx].store(file_size, Ordering::Relaxed);
            }
            result.with_context(|| format!("file {file_path}"))
        }));
    }

    // 区分"用户主动取消" vs "我们因为某个 worker 失败了主动 abort 其它 worker"：
    // 都共用同一个 cancel AtomicBool（worker 端只看一个 flag 就够），但外层用
    // `self_aborted` 记是哪种情况，决定最后 emit Cancelled 还是 Failed。
    let mut first_err: Option<anyhow::Error> = None;
    let mut self_aborted = false;
    while let Some(joined) = futs.next().await {
        match joined {
            Ok(Ok(())) => {}
            Ok(Err(e)) => {
                if first_err.is_none() {
                    first_err = Some(e);
                }
                // 一个 worker 失败 → 让其它 worker 立即停，免得它们继续吃带宽
                // 然后用户还得等到所有任务完成才看到失败。
                if !cancel.load(Ordering::SeqCst) {
                    log::warn!("[local-asr] one file failed; aborting other workers");
                    cancel.store(true, Ordering::SeqCst);
                    self_aborted = true;
                }
            }
            Err(e) => {
                if first_err.is_none() {
                    first_err = Some(anyhow::anyhow!("join: {e}"));
                }
            }
        }
    }

    // 用户主动 cancel（不是我们因为错误自己 set 的）→ Cancelled
    if cancel.load(Ordering::SeqCst) && !self_aborted {
        emit_cancelled(app, model_id, "", 0, file_count, total_bytes);
        return Ok(());
    }
    if let Some(e) = first_err {
        emit(
            app,
            DownloadProgress {
                model_id: model_id.as_str().into(),
                file: String::new(),
                file_index: 0,
                file_count,
                bytes_downloaded: super::models::downloaded_bytes(model_id),
                bytes_total: total_bytes,
                phase: DownloadPhase::Failed,
                error: Some(format!("{e:#}")),
            },
        );
        return Err(e);
    }

    let sentinel = dir.join(READY_SENTINEL);
    std::fs::write(&sentinel, b"")
        .with_context(|| format!("write sentinel failed: {}", sentinel.display()))?;

    emit(
        app,
        DownloadProgress {
            model_id: model_id.as_str().into(),
            file: String::new(),
            file_index: file_count,
            file_count,
            bytes_downloaded: super::models::downloaded_bytes(model_id),
            bytes_total: total_bytes,
            phase: DownloadPhase::Finished,
            error: None,
        },
    );
    Ok(())
}

// 这三个数贴合 aria2 / hf_xet 实测：8MB chunk 让单连接寿命 5–20s（CDN 容易 throttle 的临界点之下），
// 单文件 8 并发跟 hf_xet 默认基本对齐；多文件并发 3 个填满带宽且不超过 hf-mirror 的 per-IP 阈值。
const CHUNK_SIZE: u64 = 8 * 1024 * 1024;
const PARALLEL: usize = 8;
const PER_CHUNK_ATTEMPTS: u32 = 4;
const PARALLEL_FILES: usize = 3;

/// `.partial` 文件的真实已下字节（不是 sparse 逻辑大小）。
/// 有 `.partial.idx` → chunked 模式，按 idx 里 chunk 数还原；
/// 没有 → append/single-stream 模式，partial 是 dense，meta.len() 即真实字节。
pub fn partial_actual_size(partial: &Path) -> u64 {
    let total_size = match std::fs::metadata(partial) {
        Ok(m) => m.len(),
        Err(e) => {
            eprintln!(
                "[local-asr] partial_actual_size: stat partial failed ({}): {}",
                partial.display(),
                e
            );
            return 0;
        }
    };
    if total_size == 0 {
        return 0;
    }
    let idx_path = partial.with_extension("partial.idx");
    if !idx_path.exists() {
        return total_size;
    }
    let content = match std::fs::read_to_string(&idx_path) {
        Ok(s) => s,
        Err(e) => {
            // idx 不可读 → 不知道哪些 chunk 已落盘，sparse 全长不可信，只能回 0。
            // 但日志要留，否则进度条无故归零没法排查。
            eprintln!(
                "[local-asr] partial_actual_size: read idx failed ({}): {}",
                idx_path.display(),
                e
            );
            return 0;
        }
    };
    let mut seen: HashSet<usize> = HashSet::new();
    let mut total: u64 = 0;
    for line in content.lines() {
        let Ok(idx) = line.trim().parse::<usize>() else {
            continue;
        };
        if !seen.insert(idx) {
            continue;
        }
        let start = (idx as u64).saturating_mul(CHUNK_SIZE);
        if start >= total_size {
            continue;
        }
        // 最后一块可能不到 CHUNK_SIZE
        let end = (start + CHUNK_SIZE).min(total_size);
        total += end - start;
    }
    total
}

async fn download_one(
    client: &reqwest::Client,
    url: &str,
    dest: &Path,
    total_size: u64,
    cancel: Arc<AtomicBool>,
    on_progress: Arc<dyn Fn(u64) + Send + Sync>,
) -> Result<()> {
    let partial = dest.with_extension("partial");
    let idx_path = partial.with_extension("partial.idx");

    // 文件大小未知（HF 没给 size）→ 退化为单连接整文件下，行为同最早的实现
    if total_size == 0 {
        return single_stream_download(client, url, dest, cancel, on_progress).await;
    }

    // 远端文件 ≤ 一个 chunk 大小：直接单 chunk，不走 sparse + idx
    if total_size <= CHUNK_SIZE {
        let result = chunk_with_retry(
            client,
            url,
            &partial,
            0,
            total_size - 1,
            &cancel,
            &on_progress,
        )
        .await;
        if cancel.load(Ordering::SeqCst) {
            anyhow::bail!("cancelled");
        }
        result?;
        finalize(&partial, dest, &idx_path).await?;
        return Ok(());
    }

    // 1. 计算 chunk 计划
    let chunks: Vec<(usize, u64, u64)> = chunk_plan(total_size);
    let total_chunks = chunks.len();

    // 2. 读已完成的 chunk 索引
    let done_set = read_idx(&idx_path);

    // 3. 预先把 .partial 撑到最终大小（sparse 文件，holes = 零字节）
    if !partial.exists() || std::fs::metadata(&partial).map(|m| m.len()).unwrap_or(0) != total_size
    {
        let f = std::fs::OpenOptions::new()
            .write(true)
            .create(true)
            .open(&partial)
            .with_context(|| format!("create partial failed: {}", partial.display()))?;
        f.set_len(total_size)
            .with_context(|| format!("set_len partial failed: {}", partial.display()))?;
    }
    // 模式标记：sparse partial 必须配对 .partial.idx（哪怕空），
    // 否则 walk_files 看到 partial 有但 idx 无，会把 sparse 全长当成已下完。
    if !idx_path.exists() {
        std::fs::write(&idx_path, b"")
            .with_context(|| format!("touch partial.idx failed: {}", idx_path.display()))?;
    }

    // 4. 总计已下字节（用于初始化进度）
    let initial_done: u64 = chunks
        .iter()
        .filter(|(i, _, _)| done_set.contains(i))
        .map(|(_, s, e)| e - s + 1)
        .sum();
    let bytes_in_file = Arc::new(AtomicU64::new(initial_done));
    on_progress(initial_done);

    // 5. 调度 N 并发 worker
    let remaining: Vec<(usize, u64, u64)> = chunks
        .into_iter()
        .filter(|(i, _, _)| !done_set.contains(i))
        .collect();

    if remaining.is_empty() {
        finalize(&partial, dest, &idx_path).await?;
        return Ok(());
    }

    let semaphore = Arc::new(tokio::sync::Semaphore::new(PARALLEL));
    let idx_path_arc = Arc::new(idx_path.clone());
    let partial_arc = Arc::new(partial.clone());
    let url_arc: Arc<str> = Arc::from(url);
    let client = client.clone();
    let mut futs = futures_util::stream::FuturesUnordered::new();

    for (chunk_idx, start, end) in remaining {
        let permit_owned = Arc::clone(&semaphore);
        let client = client.clone();
        let url_arc = Arc::clone(&url_arc);
        let partial_arc = Arc::clone(&partial_arc);
        let idx_path_arc = Arc::clone(&idx_path_arc);
        let cancel = Arc::clone(&cancel);
        let bytes_in_file = Arc::clone(&bytes_in_file);
        let on_progress = Arc::clone(&on_progress);

        futs.push(tauri::async_runtime::spawn(async move {
            let _permit = match permit_owned.acquire_owned().await {
                Ok(p) => p,
                Err(_) => return Err(anyhow::anyhow!("semaphore closed")),
            };
            let result = chunk_with_retry_seek(
                &client,
                &url_arc,
                &partial_arc,
                start,
                end,
                &cancel,
                &bytes_in_file,
                &on_progress,
            )
            .await;
            if result.is_ok() {
                if let Err(e) = append_idx(&idx_path_arc, chunk_idx) {
                    log::warn!("[local-asr] append .partial.idx failed: {e:#}");
                }
            }
            result
        }));
    }

    let mut first_err: Option<anyhow::Error> = None;
    while let Some(joined) = futs.next().await {
        match joined {
            Ok(Ok(())) => {}
            Ok(Err(e)) => {
                if first_err.is_none() {
                    first_err = Some(e);
                }
            }
            Err(e) => {
                if first_err.is_none() {
                    first_err = Some(anyhow::anyhow!("join: {e}"));
                }
            }
        }
    }

    if cancel.load(Ordering::SeqCst) {
        anyhow::bail!("cancelled");
    }
    if let Some(e) = first_err {
        return Err(e);
    }

    // 6. 校验 + 落盘
    let actual = std::fs::metadata(&partial).map(|m| m.len()).unwrap_or(0);
    if actual != total_size {
        anyhow::bail!("downloaded size {actual} != expected {total_size}");
    }
    finalize(&partial, dest, &idx_path).await?;
    Ok(())
}

fn chunk_plan(total: u64) -> Vec<(usize, u64, u64)> {
    let mut v = Vec::new();
    let mut s = 0u64;
    let mut idx = 0usize;
    while s < total {
        let e = (s + CHUNK_SIZE - 1).min(total - 1);
        v.push((idx, s, e));
        s = e + 1;
        idx += 1;
    }
    v
}

fn read_idx(path: &Path) -> HashSet<usize> {
    let content = match std::fs::read_to_string(path) {
        Ok(s) => s,
        Err(_) => return HashSet::new(),
    };
    content
        .lines()
        .filter_map(|l| l.trim().parse::<usize>().ok())
        .collect()
}

fn append_idx(path: &Path, idx: usize) -> std::io::Result<()> {
    use std::io::Write;
    let mut f = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    writeln!(f, "{idx}")
}

async fn finalize(partial: &Path, dest: &Path, idx_path: &Path) -> Result<()> {
    tokio::fs::rename(partial, dest)
        .await
        .with_context(|| format!("rename partial → final failed: {}", dest.display()))?;
    let _ = std::fs::remove_file(idx_path);
    Ok(())
}

/// 单 chunk + per-chunk retry。append 模式（一次性写到底，给小文件路径）。
async fn chunk_with_retry(
    client: &reqwest::Client,
    url: &str,
    partial: &Path,
    range_start: u64,
    range_end: u64,
    cancel: &AtomicBool,
    on_progress: &Arc<dyn Fn(u64) + Send + Sync>,
) -> Result<()> {
    let mut last_err: Option<anyhow::Error> = None;
    for attempt in 1..=PER_CHUNK_ATTEMPTS {
        if cancel.load(Ordering::SeqCst) {
            anyhow::bail!("cancelled");
        }
        match try_download_range_append(
            client,
            url,
            partial,
            range_start,
            range_end,
            cancel,
            on_progress,
        )
        .await
        {
            Ok(()) => return Ok(()),
            Err(e) => {
                let msg = format!("{e:#}");
                last_err = Some(e);
                if attempt < PER_CHUNK_ATTEMPTS && !cancel.load(Ordering::SeqCst) {
                    let backoff = std::time::Duration::from_secs(1u64 << (2 * (attempt - 1)));
                    log::warn!(
                        "[local-asr] small-file chunk attempt {attempt}/{PER_CHUNK_ATTEMPTS} failed: {msg}; sleep {:?}",
                        backoff
                    );
                    tokio::time::sleep(backoff).await;
                }
            }
        }
    }
    Err(last_err
        .unwrap_or_else(|| anyhow::anyhow!("chunk failed after {PER_CHUNK_ATTEMPTS} attempts")))
}

async fn try_download_range_append(
    client: &reqwest::Client,
    url: &str,
    partial: &Path,
    range_start: u64,
    range_end: u64,
    cancel: &AtomicBool,
    on_progress: &Arc<dyn Fn(u64) + Send + Sync>,
) -> Result<()> {
    let mut req = client.get(url);
    req = req.header("Range", format!("bytes={range_start}-{range_end}"));
    let resp = req
        .send()
        .await
        .with_context(|| format!("HTTP GET {url} failed"))?;
    let status = resp.status();
    if status.as_u16() != 200 && status.as_u16() != 206 {
        anyhow::bail!("HTTP {status} for {url}");
    }
    let effective_start = if status.as_u16() == 200 {
        0
    } else {
        range_start
    };

    // 截断 partial 到本次 attempt 的起点，再 seek 写入。
    // 老 append 实现的 bug：若上一次 attempt 已写了部分字节后失败，retry 拿到的还是
    // 完整 chunk → append → 文件比应有大小多 N 字节 → 永久损坏。
    // 小文件路径每个 chunk 是整个文件（≤ 32MB），用 truncate 重写最直白。
    let mut file = tokio::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .open(partial)
        .await
        .with_context(|| format!("open partial failed: {}", partial.display()))?;
    file.set_len(effective_start)
        .await
        .with_context(|| format!("truncate partial failed: {}", partial.display()))?;
    file.seek(std::io::SeekFrom::Start(effective_start))
        .await
        .with_context(|| format!("seek partial failed: {}", partial.display()))?;

    let mut stream = resp.bytes_stream();
    let mut written: u64 = 0;
    while let Some(chunk) = stream.next().await {
        if cancel.load(Ordering::SeqCst) {
            file.flush().await.ok();
            anyhow::bail!("cancelled");
        }
        let bytes = chunk.context("read stream chunk failed")?;
        file.write_all(&bytes).await.context("write chunk failed")?;
        written += bytes.len() as u64;
        on_progress(effective_start + written);
    }
    file.flush().await.ok();
    Ok(())
}

/// 大文件并发版：seek 到 chunk 起点写入，**不**append。`bytes_in_file`
/// 是跨所有并发任务累加的总进度。
async fn chunk_with_retry_seek(
    client: &reqwest::Client,
    url: &str,
    partial: &Path,
    range_start: u64,
    range_end: u64,
    cancel: &AtomicBool,
    bytes_in_file: &Arc<AtomicU64>,
    on_progress: &Arc<dyn Fn(u64) + Send + Sync>,
) -> Result<()> {
    let mut last_err: Option<anyhow::Error> = None;
    for attempt in 1..=PER_CHUNK_ATTEMPTS {
        if cancel.load(Ordering::SeqCst) {
            anyhow::bail!("cancelled");
        }
        match try_download_range_seek(
            client,
            url,
            partial,
            range_start,
            range_end,
            cancel,
            bytes_in_file,
            on_progress,
        )
        .await
        {
            Ok(()) => return Ok(()),
            Err(e) => {
                let msg = format!("{e:#}");
                last_err = Some(e);
                if attempt < PER_CHUNK_ATTEMPTS && !cancel.load(Ordering::SeqCst) {
                    let backoff = std::time::Duration::from_secs(1u64 << (2 * (attempt - 1)));
                    log::warn!(
                        "[local-asr] chunk [{range_start}-{range_end}] attempt {attempt}/{PER_CHUNK_ATTEMPTS} failed: {msg}; sleep {:?}",
                        backoff
                    );
                    tokio::time::sleep(backoff).await;
                }
            }
        }
    }
    Err(last_err.unwrap_or_else(|| {
        anyhow::anyhow!(
            "chunk [{range_start}-{range_end}] failed after {PER_CHUNK_ATTEMPTS} attempts"
        )
    }))
}

async fn try_download_range_seek(
    client: &reqwest::Client,
    url: &str,
    partial: &Path,
    range_start: u64,
    range_end: u64,
    cancel: &AtomicBool,
    bytes_in_file: &Arc<AtomicU64>,
    on_progress: &Arc<dyn Fn(u64) + Send + Sync>,
) -> Result<()> {
    let resp = client
        .get(url)
        .header("Range", format!("bytes={range_start}-{range_end}"))
        .send()
        .await
        .with_context(|| format!("HTTP GET {url} failed"))?;

    let status = resp.status();
    // 并发 seek 模式严格要求 206。服务端忽略 Range 返回 200 + 全文件会
    // 把整个文件写到 range_start 偏移导致灾难性后果，此时直接 fail，
    // 让外层 retry 再试一次。
    if status.as_u16() != 206 {
        anyhow::bail!("expected HTTP 206 Partial Content for ranged GET, got {status}");
    }

    let mut file = tokio::fs::OpenOptions::new()
        .write(true)
        .create(false) // 文件已经被 set_len 创建好了，这里仅写入
        .open(partial)
        .await
        .with_context(|| format!("open partial for seek failed: {}", partial.display()))?;
    file.seek(std::io::SeekFrom::Start(range_start))
        .await
        .with_context(|| format!("seek to {range_start} failed"))?;

    let mut stream = resp.bytes_stream();
    while let Some(chunk) = stream.next().await {
        if cancel.load(Ordering::SeqCst) {
            file.flush().await.ok();
            anyhow::bail!("cancelled");
        }
        let bytes = chunk.context("read stream chunk failed")?;
        file.write_all(&bytes).await.context("write chunk failed")?;
        let new_total =
            bytes_in_file.fetch_add(bytes.len() as u64, Ordering::Relaxed) + bytes.len() as u64;
        on_progress(new_total);
    }
    file.flush().await.ok();
    Ok(())
}

/// total_size 未知时的退化路径：单 GET 整文件。HF 给的 size 几乎总是有，
/// 这条只是保险。
async fn single_stream_download(
    client: &reqwest::Client,
    url: &str,
    dest: &Path,
    cancel: Arc<AtomicBool>,
    on_progress: Arc<dyn Fn(u64) + Send + Sync>,
) -> Result<()> {
    let partial = PathBuf::from(dest).with_extension("partial");
    let resp = client.get(url).send().await?;
    let status = resp.status();
    if !status.is_success() {
        anyhow::bail!("HTTP {status} for {url}");
    }
    let mut file = tokio::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(&partial)
        .await?;
    let mut stream = resp.bytes_stream();
    let mut total: u64 = 0;
    while let Some(chunk) = stream.next().await {
        if cancel.load(Ordering::SeqCst) {
            anyhow::bail!("cancelled");
        }
        let bytes = chunk?;
        file.write_all(&bytes).await?;
        total += bytes.len() as u64;
        on_progress(total);
    }
    file.flush().await.ok();
    drop(file);
    tokio::fs::rename(&partial, dest).await?;
    Ok(())
}

fn emit(app: &AppHandle, payload: DownloadProgress) {
    if let Err(e) = app.emit("local-asr-download-progress", payload) {
        log::warn!("[local-asr] emit progress failed: {e}");
    }
}

fn emit_cancelled(
    app: &AppHandle,
    model_id: ModelId,
    fname: &str,
    idx: usize,
    file_count: usize,
    total: u64,
) {
    emit(
        app,
        DownloadProgress {
            model_id: model_id.as_str().into(),
            file: fname.into(),
            file_index: idx,
            file_count,
            bytes_downloaded: super::models::downloaded_bytes(model_id),
            bytes_total: total,
            phase: DownloadPhase::Cancelled,
            error: None,
        },
    );
}
