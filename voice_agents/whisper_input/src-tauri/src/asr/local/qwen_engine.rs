//! antirez/qwen-asr 的安全 Rust 包装。
//!
//! 当前只暴露**最小可用面**：`load` / `transcribe_audio` / `transcribe_stream`
//! + token 回调。后续接 coordinator 时再扩 prompt/language 设置。

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_void};
use std::path::Path;
use std::ptr;
use std::sync::Mutex;

use anyhow::{Context, Result};

use super::qwen_ffi::{
    qwen_free, qwen_load, qwen_set_token_callback, qwen_transcribe_audio, qwen_transcribe_stream,
    QwenCtx,
};

/// FnMut 闭包是 fat pointer，不能直接塞进 `*mut c_void`，所以包一层 Box。
type TokenHandler = dyn FnMut(&str) + Send + 'static;
type TokenHandlerBox = Box<Box<TokenHandler>>;

pub struct QwenAsrEngine {
    ctx: *mut QwenCtx,
    /// 持有 token 回调的所有权；C 端拿到的是 `&**handler` 派生出来的 raw ptr，
    /// 只要这个 Box 还活着，那个 raw ptr 就有效。Mutex 防止并发 set。
    token_handler: Mutex<Option<TokenHandlerBox>>,
}

/// SAFETY: `qwen_ctx_t` 内部的 pthread/buffer 仅在单次 transcribe 期间被 C 端
/// 自己用；外层不会从两个 Rust 线程并发调进同一个 ctx（由 coordinator 串行
/// 化保证）。Send/Sync 在这一约束下成立。
unsafe impl Send for QwenAsrEngine {}
unsafe impl Sync for QwenAsrEngine {}

impl QwenAsrEngine {
    /// 从模型目录加载（目录里需含 `config.json` / `model.safetensors*` /
    /// `vocab.json` / `merges.txt`，结构见 antirez `download_model.sh`）。
    pub fn load(model_dir: &Path) -> Result<Self> {
        let dir_str = model_dir
            .to_str()
            .with_context(|| format!("model dir 不是合法 UTF-8: {model_dir:?}"))?;
        let c_dir = CString::new(dir_str).context("model dir 含 NUL 字节")?;

        // SAFETY: `c_dir` 在调用期间存活；返回 NULL 表示加载失败。
        let ctx = unsafe { qwen_load(c_dir.as_ptr()) };
        if ctx.is_null() {
            anyhow::bail!("qwen_load 失败：{model_dir:?}");
        }

        Ok(Self {
            ctx,
            token_handler: Mutex::new(None),
        })
    }

    /// 注册流式 token 回调；传 `None` 清空。重新注册会先解绑再装新回调。
    pub fn set_token_handler<F>(&self, handler: Option<F>)
    where
        F: FnMut(&str) + Send + 'static,
    {
        let mut slot = self.token_handler.lock().expect("token_handler poisoned");

        // 先把 C 端那一侧切干净，再 drop 旧 Box，避免 C 在替换瞬间还持有旧指针。
        unsafe { qwen_set_token_callback(self.ctx, None, ptr::null_mut()) };
        *slot = None;

        if let Some(f) = handler {
            let boxed: TokenHandlerBox = Box::new(Box::new(f));
            // boxed 的内部 `Box<TokenHandler>` 在堆上有稳定地址；取它的 &mut 转 raw。
            let userdata = boxed.as_ref() as *const Box<TokenHandler> as *mut c_void;
            unsafe {
                qwen_set_token_callback(self.ctx, Some(token_trampoline), userdata);
            }
            *slot = Some(boxed);
        }
    }

    /// 批式转写：一次性给完整音频（mono f32 16kHz）。
    pub fn transcribe_audio(&self, samples: &[f32]) -> Result<String> {
        // SAFETY: samples 在调用期间存活；返回是 C `malloc` 出的字符串。
        let raw =
            unsafe { qwen_transcribe_audio(self.ctx, samples.as_ptr(), samples.len() as i32) };
        if raw.is_null() {
            anyhow::bail!("qwen_transcribe_audio 返回 NULL");
        }
        let text = unsafe { CStr::from_ptr(raw) }
            .to_string_lossy()
            .into_owned();
        unsafe { libc::free(raw as *mut c_void) };
        Ok(text)
    }

    /// 流式转写：内部按 2s chunk 切片，token 通过 `set_token_handler` 注册的
    /// 回调实时吐出；返回值是最终完整文本。
    pub fn transcribe_stream(&self, samples: &[f32]) -> Result<String> {
        let raw =
            unsafe { qwen_transcribe_stream(self.ctx, samples.as_ptr(), samples.len() as i32) };
        if raw.is_null() {
            anyhow::bail!("qwen_transcribe_stream 返回 NULL");
        }
        let text = unsafe { CStr::from_ptr(raw) }
            .to_string_lossy()
            .into_owned();
        unsafe { libc::free(raw as *mut c_void) };
        Ok(text)
    }
}

impl Drop for QwenAsrEngine {
    fn drop(&mut self) {
        if !self.ctx.is_null() {
            // 先解绑回调，避免 C 端在 free 后还持有 userdata 指针。
            unsafe {
                qwen_set_token_callback(self.ctx, None, ptr::null_mut());
                qwen_free(self.ctx);
            }
            self.ctx = ptr::null_mut();
        }
        // token_handler 的 Box 由 Mutex 析构时释放。
    }
}

/// C 蹦床：把 `userdata` 解回 `&mut Box<TokenHandler>` 并转发字符串。
unsafe extern "C" fn token_trampoline(piece: *const c_char, userdata: *mut c_void) {
    if userdata.is_null() || piece.is_null() {
        return;
    }
    // SAFETY: userdata 是 set_token_handler 注册的 `*Box<TokenHandler>`。
    let handler: &mut Box<TokenHandler> = unsafe { &mut *(userdata as *mut Box<TokenHandler>) };
    let text = unsafe { CStr::from_ptr(piece) }.to_string_lossy();
    handler(&text);
}
