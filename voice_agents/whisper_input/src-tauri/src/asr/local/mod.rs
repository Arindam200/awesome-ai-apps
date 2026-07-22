//! 本地 ASR 引擎入口。
//!
//! 当前只在 macOS 编入 antirez/qwen-asr (纯 C + Accelerate)；Windows 端
//! 的本地推理路径见 issue #256，本期不实现。

pub mod cache;
pub mod download;
pub mod foundry;
pub mod foundry_native;
pub mod foundry_provider;
pub mod foundry_runtime;
mod local_provider;
pub mod models;
pub mod test_run;

pub use cache::LocalAsrCache;
#[allow(unused_imports)]
pub use foundry_provider::FoundryLocalWhisperAsr;
#[allow(unused_imports)]
pub use foundry_runtime::FoundryLocalRuntime;

#[cfg(target_os = "macos")]
mod qwen_engine;
#[cfg(target_os = "macos")]
mod qwen_ffi;

#[cfg(target_os = "macos")]
pub use local_provider::LocalQwenAsr;
#[cfg(target_os = "macos")]
pub use qwen_engine::QwenAsrEngine;

pub use download::{DownloadManager, Mirror};
pub use models::{ModelId, ModelStatus};

/// 本地 Qwen3-ASR 在 active_asr 字段里的标识；与前端 ASR_PRESETS 的 id 对齐。
pub const PROVIDER_ID: &str = "local-qwen3";

pub fn is_local_qwen3(id: &str) -> bool {
    id == PROVIDER_ID
}
