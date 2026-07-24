//! 本地 Qwen3-ASR 引擎缓存。
//!
//! 用途：避免每次 dictation 都重加载 1.2GB+ 模型。引擎一次 load 后驻留在内存，
//! 跨多次会话复用；用户在设置里决定"说完话即释放" / "保持 N 秒后释放" /
//! "不释放"。
//!
//! 调度规则：每次会话结束后 spawn 一个 sleep+check 任务；任务在到点时检查
//! `last_used`——如果中间又被使用过则不释放，否则 drop 引擎让 OS 回收 RAM。

use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::Result;
use parking_lot::Mutex;

#[cfg(target_os = "macos")]
use super::QwenAsrEngine;

pub struct LocalAsrCache {
    #[cfg(target_os = "macos")]
    inner: Mutex<Option<CachedEngine>>,
    #[cfg(not(target_os = "macos"))]
    _phantom: (),
}

#[cfg(target_os = "macos")]
struct CachedEngine {
    model_id: String,
    engine: Arc<QwenAsrEngine>,
    last_used: Instant,
}

impl Default for LocalAsrCache {
    fn default() -> Self {
        Self::new()
    }
}

impl LocalAsrCache {
    pub fn new() -> Self {
        Self {
            #[cfg(target_os = "macos")]
            inner: Mutex::new(None),
            #[cfg(not(target_os = "macos"))]
            _phantom: (),
        }
    }

    /// 取已缓存的同 id 引擎，没有就加载（**阻塞、可能数秒**——调用方应放
    /// `spawn_blocking`）。模型 id 不同则把旧的 drop 再加载新的。
    #[cfg(target_os = "macos")]
    pub fn get_or_load(&self, model_id: &str, model_dir: &Path) -> Result<Arc<QwenAsrEngine>> {
        {
            let mut slot = self.inner.lock();
            if let Some(cached) = slot.as_mut() {
                if cached.model_id == model_id {
                    cached.last_used = Instant::now();
                    log::info!("[local-asr cache] reuse engine: {model_id}");
                    return Ok(Arc::clone(&cached.engine));
                }
                log::info!(
                    "[local-asr cache] active model changed {} -> {}, drop old",
                    cached.model_id,
                    model_id
                );
                slot.take();
            }
        }
        log::info!(
            "[local-asr cache] loading {model_id} from {}",
            model_dir.display()
        );
        let engine = Arc::new(QwenAsrEngine::load(model_dir)?);
        let mut slot = self.inner.lock();
        *slot = Some(CachedEngine {
            model_id: model_id.to_string(),
            engine: Arc::clone(&engine),
            last_used: Instant::now(),
        });
        log::info!("[local-asr cache] loaded {model_id}");
        Ok(engine)
    }

    /// 标记最近使用时间——end_session 在调过 transcribe 之后调一下，
    /// 让 release 计时器从这一刻重新算。
    pub fn touch(&self) {
        #[cfg(target_os = "macos")]
        {
            if let Some(cached) = self.inner.lock().as_mut() {
                cached.last_used = Instant::now();
            }
        }
    }

    /// 如果空闲时长 ≥ threshold，释放引擎。返回是否真释放了。
    pub fn release_if_idle(&self, idle_threshold: Duration) -> bool {
        #[cfg(target_os = "macos")]
        {
            let taken = {
                let mut slot = self.inner.lock();
                match slot.as_ref() {
                    Some(c) if c.last_used.elapsed() >= idle_threshold => {
                        log::info!(
                            "[local-asr cache] release engine {} after idle {:?}",
                            c.model_id,
                            c.last_used.elapsed()
                        );
                        slot.take()
                    }
                    _ => None,
                }
            };
            if let Some(cached) = taken {
                drop(cached);
                pressure_relief_macos();
                return true;
            }
        }
        let _ = idle_threshold;
        false
    }

    /// 立刻释放（用户点"立即释放"、切走 provider、删模型时调）。
    pub fn release_now(&self) {
        #[cfg(target_os = "macos")]
        {
            let taken = self.inner.lock().take();
            if let Some(cached) = taken {
                log::info!(
                    "[local-asr cache] release engine {} on demand",
                    cached.model_id
                );
                drop(cached);
                pressure_relief_macos();
            }
        }
    }

    pub fn loaded_model_id(&self) -> Option<String> {
        #[cfg(target_os = "macos")]
        {
            return self.inner.lock().as_ref().map(|c| c.model_id.clone());
        }
        #[cfg(not(target_os = "macos"))]
        None
    }
}

/// drop QwenAsrEngine 后调一次：让 macOS libmalloc 把 freelist 上的物理页归还内核。
/// 不调的话，encoder f32 weights 那 ~几百 MB 的 free 不会立刻反映到 RSS，活动监视器
/// 看起来"释放按钮没生效"。decoder bf16 走 mmap，munmap 时已立即生效，不依赖这个调用。
#[cfg(target_os = "macos")]
fn pressure_relief_macos() {
    // SAFETY: 系统 API；NULL zone + goal=0 = 对所有 zone 尽量多地归还，无内存安全风险。
    let freed = unsafe { malloc_zone_pressure_relief(std::ptr::null_mut(), 0) };
    log::info!(
        "[local-asr cache] malloc_zone_pressure_relief freed ~{} bytes",
        freed
    );
}

#[cfg(target_os = "macos")]
extern "C" {
    fn malloc_zone_pressure_relief(zone: *mut libc::c_void, goal: libc::size_t) -> libc::size_t;
}
