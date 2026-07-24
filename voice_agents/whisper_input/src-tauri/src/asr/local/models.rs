//! 本地 Qwen3-ASR 模型注册表（仅 id / 仓库名 / 显示名）。
//!
//! **文件清单与尺寸不再硬编码** —— 由 `download.rs` 在下载时从
//! `huggingface.co/api/models/<repo>/tree/main` 拉真实清单和大小。
//! 增加新模型 = 这里加一条枚举 + 仓库名。

use std::path::PathBuf;

use anyhow::Result;
use serde::Serialize;

use crate::persistence;

/// 下载完成后落在模型目录里的哨兵文件名；存在 = 完整、可加载。
pub(super) const READY_SENTINEL: &str = ".openless-asr-ready";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModelId {
    Small06b,
    Large17b,
}

impl ModelId {
    pub fn as_str(self) -> &'static str {
        match self {
            ModelId::Small06b => "qwen3-asr-0.6b",
            ModelId::Large17b => "qwen3-asr-1.7b",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "qwen3-asr-0.6b" => Some(ModelId::Small06b),
            "qwen3-asr-1.7b" => Some(ModelId::Large17b),
            _ => None,
        }
    }

    pub fn all() -> &'static [ModelId] {
        &[ModelId::Small06b, ModelId::Large17b]
    }

    /// HuggingFace repo id（用于拼 API + 下载 URL）。
    pub fn hf_repo(self) -> &'static str {
        match self {
            ModelId::Small06b => "Qwen/Qwen3-ASR-0.6B",
            ModelId::Large17b => "Qwen/Qwen3-ASR-1.7B",
        }
    }
}

/// 模型在本地的根目录（可能不存在）。
pub fn model_dir(id: ModelId) -> Result<PathBuf> {
    Ok(persistence::local_models_root()?.join(id.as_str()))
}

/// 完整且可加载？= 哨兵存在。
/// 比"枚举所有应有文件"稳：HF 仓库改文件名 / 加新文件时不会误报缺失。
pub fn is_downloaded(id: ModelId) -> bool {
    let dir = match model_dir(id) {
        Ok(d) => d,
        Err(_) => return false,
    };
    dir.join(READY_SENTINEL).exists()
}

/// 已落盘的字节数（walk_dir 求和）。下载中也能显示真实进度。
pub fn downloaded_bytes(id: ModelId) -> u64 {
    let dir = match model_dir(id) {
        Ok(d) => d,
        Err(_) => return 0,
    };
    let mut total: u64 = 0;
    walk_files(&dir, &mut |size| total += size);
    total
}

fn walk_files<F: FnMut(u64)>(dir: &std::path::Path, on_size: &mut F) {
    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name_os = entry.file_name();
        let name = name_os.to_string_lossy();
        if name == READY_SENTINEL {
            continue;
        }
        // .partial.idx 是 chunk 完成索引，不算下载字节
        if name.ends_with(".partial.idx") {
            continue;
        }
        match entry.file_type() {
            Ok(ft) if ft.is_dir() => walk_files(&path, on_size),
            Ok(ft) if ft.is_file() => {
                // .partial 在 chunked 模式下是 sparse 全长，meta.len() 不是真实字节
                if name.ends_with(".partial") {
                    on_size(super::download::partial_actual_size(&path));
                } else if let Ok(meta) = entry.metadata() {
                    on_size(meta.len());
                }
            }
            _ => {}
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelStatus {
    pub id: String,
    pub hf_repo: String,
    pub downloaded_bytes: u64,
    pub is_downloaded: bool,
}

pub fn list_status() -> Vec<ModelStatus> {
    ModelId::all()
        .iter()
        .map(|&id| ModelStatus {
            id: id.as_str().to_string(),
            hf_repo: id.hf_repo().to_string(),
            downloaded_bytes: downloaded_bytes(id),
            is_downloaded: is_downloaded(id),
        })
        .collect()
}

/// 删除本地模型目录（用户在 UI 主动删）。
pub fn delete_model(id: ModelId) -> Result<()> {
    let dir = model_dir(id)?;
    if dir.exists() {
        std::fs::remove_dir_all(&dir)?;
    }
    Ok(())
}
