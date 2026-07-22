//! 跨平台 Unicode keystroke 合成（流式输入用）。
//!
//! 公开 API 三件套：
//! - `type_unicode_chunk(text)` —— 阻塞地把一段文字逐 codepoint 当作键盘事件发出去，
//!   不动剪贴板。各平台用各自的原语。
//! - `switch_to_ascii(app)` —— 仅 macOS 有效；切到 ABC 输入源以绕过 CJK / 日文 IME
//!   对 Unicode 字符串事件的拦截。Windows / Linux 上是 no-op。
//! - `restore_input_source(app, prev)` —— 配对调用，恢复 macOS 上的原输入源。
//!
//! ## 平台差异
//!
//! - **macOS**：手写 CGEvent FFI（与 `insertion.rs::macos` 的 Cmd+V 同源）。
//!   `CGEventKeyboardSetUnicodeString` 在 CJK / 日文 IME 激活时被拦截 ——
//!   必须 `switch_to_ascii` 切到 ABC，session 结束再 `restore_input_source` 切回。
//! - **Windows**：`SendInput(KEYEVENTF_UNICODE)` 直接发 UTF-16 scancode。TSF 不拦
//!   Unicode 事件（与 keyboard layout / IME 解耦），所以不需要切输入法。
//! - **Linux**：enigo `Keyboard::text(...)`。X11 走 XTest 稳定；Wayland 看 compositor
//!   是否给 libei 权限，stock GNOME-Wayland 经常拒绝，调用方应当容忍失败回落到一次性。
//!   不切输入法 —— Linux 的 fcitx / ibus 与 enigo 的交互非常碎，v1 不尝试。
//!
//! ## 已知坑（macOS）
//!
//! - Secure Event Input（密码框、1Password 等）下 CGEventPost 静默失败；
//!   `type_unicode_chunk` 开头先用 `IsSecureEventInputEnabled` 探测，命中即返
//!   `TypeError::SecureInputActive`。
//! - Modifier 状态继承 —— 用户按着 Shift 不清零会被映射成大写，每个事件显式
//!   `CGEventSetFlags(_, 0)`。
//! - Chromium / Electron / Tauri 自身在 keyDown/keyUp 之间无延迟时会丢字，每 codepoint
//!   sleep 1ms。
//!
//! ## 线程安全（macOS）
//!
//! - `type_unicode_chunk`（CGEventPost）任意线程可调，对齐 `insertion.rs::macos::
//!   simulate_paste` 现状。
//! - TIS（`switch_to_ascii` / `restore_input_source`）调度到主线程，规避 macOS 14+
//!   对 TSM/TIS 主线程的 `dispatch_assert_queue_fail` SIGTRAP（与
//!   `feedback_rdev_macos_trap.md` 同款风险类别）。

#[allow(unused_imports)]
use tauri::{AppHandle, Runtime};

#[derive(Debug, thiserror::Error)]
pub enum TypeError {
    #[cfg(target_os = "macos")]
    #[error("CGEventSourceCreate returned null")]
    SourceAllocFailed,
    #[cfg(target_os = "macos")]
    #[error("CGEventCreateKeyboardEvent returned null")]
    EventAllocFailed,
    #[cfg(target_os = "macos")]
    #[error("Secure Event Input is enabled — synthetic keystrokes will be silently dropped")]
    SecureInputActive,
    #[cfg(target_os = "windows")]
    #[error("Windows SendInput failed: {0}")]
    SendInputFailed(String),
    #[cfg(target_os = "linux")]
    #[error("enigo init failed: {0}")]
    EnigoInit(String),
    #[cfg(target_os = "linux")]
    #[error("enigo text input failed: {0}")]
    EnigoText(String),
}

#[derive(Debug, thiserror::Error)]
pub enum TisError {
    #[error("dispatch to main thread failed: {0}")]
    MainThreadDispatch(String),
    #[error("TISCopyInputSourceForLanguage(\"en\") returned null — ABC source not installed?")]
    AbcSourceNotFound,
    #[error("TISSelectInputSource failed: OSStatus={0}")]
    SelectFailed(i32),
}

// ═══════════════════════════════════════════════════════════════════════════
// macOS 实现
// ═══════════════════════════════════════════════════════════════════════════
#[cfg(target_os = "macos")]
mod macos_impl {
    use super::{TisError, TypeError};
    use std::ffi::c_void;
    use std::time::Duration;
    use tauri::{AppHandle, Runtime};

    const INTER_KEYSTROKE_DELAY: Duration = Duration::from_millis(1);

    /// 之前激活的 input source 引用 token。携带 raw ptr 的 usize 表示，所有解引用都
    /// 通过 `restore_input_source` 调度到主线程执行；手动 `Send + Sync`。
    pub struct PreviousInputSource {
        raw: usize,
    }
    unsafe impl Send for PreviousInputSource {}
    unsafe impl Sync for PreviousInputSource {}

    pub fn type_unicode_chunk(text: &str) -> Result<(), TypeError> {
        if text.is_empty() {
            return Ok(());
        }
        if is_secure_input_enabled() {
            return Err(TypeError::SecureInputActive);
        }
        for ch in text.chars() {
            send_one_codepoint(ch)?;
            std::thread::sleep(INTER_KEYSTROKE_DELAY);
        }
        Ok(())
    }

    fn send_one_codepoint(ch: char) -> Result<(), TypeError> {
        let mut buf = [0u16; 2];
        let utf16 = ch.encode_utf16(&mut buf);
        let len = utf16.len();
        unsafe {
            let src = CGEventSourceCreate(KCG_EVENT_SOURCE_STATE_HID_SYSTEM_STATE);
            if src.is_null() {
                return Err(TypeError::SourceAllocFailed);
            }
            let down = CGEventCreateKeyboardEvent(src, 0, true);
            let up = CGEventCreateKeyboardEvent(src, 0, false);
            if down.is_null() || up.is_null() {
                if !down.is_null() {
                    CFRelease(down as _);
                }
                if !up.is_null() {
                    CFRelease(up as _);
                }
                CFRelease(src as _);
                return Err(TypeError::EventAllocFailed);
            }
            CGEventSetFlags(down, 0);
            CGEventSetFlags(up, 0);
            CGEventKeyboardSetUnicodeString(down, len, utf16.as_ptr());
            CGEventKeyboardSetUnicodeString(up, len, utf16.as_ptr());
            CGEventPost(KCG_HID_EVENT_TAP, down);
            CGEventPost(KCG_HID_EVENT_TAP, up);
            CFRelease(down as _);
            CFRelease(up as _);
            CFRelease(src as _);
        }
        Ok(())
    }

    fn is_secure_input_enabled() -> bool {
        unsafe { IsSecureEventInputEnabled() != 0 }
    }

    pub async fn switch_to_ascii<R: Runtime>(
        app: &AppHandle<R>,
    ) -> Result<Option<PreviousInputSource>, TisError> {
        let (tx, rx) = tokio::sync::oneshot::channel();
        app.run_on_main_thread(move || {
            let result = unsafe { switch_to_ascii_on_main() };
            let _ = tx.send(result);
        })
        .map_err(|e| TisError::MainThreadDispatch(e.to_string()))?;
        rx.await
            .map_err(|e| TisError::MainThreadDispatch(e.to_string()))?
    }

    unsafe fn switch_to_ascii_on_main() -> Result<Option<PreviousInputSource>, TisError> {
        let prev = TISCopyCurrentKeyboardInputSource();
        let prev_token = if prev.is_null() {
            None
        } else {
            Some(PreviousInputSource { raw: prev as usize })
        };
        let lang_bytes = b"en\0";
        let lang = CFStringCreateWithCString(
            std::ptr::null(),
            lang_bytes.as_ptr() as *const i8,
            K_CF_STRING_ENCODING_ASCII,
        );
        if lang.is_null() {
            if let Some(p) = prev_token {
                CFRelease(p.raw as *const _);
            }
            return Err(TisError::AbcSourceNotFound);
        }
        let abc = TISCopyInputSourceForLanguage(lang);
        CFRelease(lang as _);
        if abc.is_null() {
            if let Some(p) = prev_token {
                CFRelease(p.raw as *const _);
            }
            return Err(TisError::AbcSourceNotFound);
        }
        let status = TISSelectInputSource(abc);
        CFRelease(abc as _);
        if status != 0 {
            if let Some(p) = prev_token {
                CFRelease(p.raw as *const _);
            }
            return Err(TisError::SelectFailed(status));
        }
        Ok(prev_token)
    }

    pub async fn restore_input_source<R: Runtime>(
        app: &AppHandle<R>,
        prev: Option<PreviousInputSource>,
    ) -> Result<(), TisError> {
        let Some(prev) = prev else {
            return Ok(());
        };
        let (tx, rx) = tokio::sync::oneshot::channel();
        app.run_on_main_thread(move || {
            let result = unsafe { restore_input_source_on_main(prev) };
            let _ = tx.send(result);
        })
        .map_err(|e| TisError::MainThreadDispatch(e.to_string()))?;
        rx.await
            .map_err(|e| TisError::MainThreadDispatch(e.to_string()))?
    }

    unsafe fn restore_input_source_on_main(prev: PreviousInputSource) -> Result<(), TisError> {
        let raw = prev.raw as *mut c_void;
        let status = TISSelectInputSource(raw);
        CFRelease(raw as _);
        if status != 0 {
            return Err(TisError::SelectFailed(status));
        }
        Ok(())
    }

    // ─── FFI ───
    type CGEventTapLocation = u32;
    type CGEventSourceStateID = i32;
    type CGKeyCode = u16;
    type CGEventFlags = u64;
    type CFStringEncoding = u32;
    type CFAllocatorRef = *const c_void;
    type CFStringRef = *const c_void;
    type TISInputSourceRef = *mut c_void;

    const KCG_HID_EVENT_TAP: CGEventTapLocation = 0;
    const KCG_EVENT_SOURCE_STATE_HID_SYSTEM_STATE: CGEventSourceStateID = 1;
    const K_CF_STRING_ENCODING_ASCII: CFStringEncoding = 0x0600;

    #[repr(C)]
    struct OpaqueCGEvent(c_void);
    type CGEventRef = *mut OpaqueCGEvent;
    #[repr(C)]
    struct OpaqueCGEventSource(c_void);
    type CGEventSourceRef = *mut OpaqueCGEventSource;

    #[link(name = "CoreGraphics", kind = "framework")]
    extern "C" {
        fn CGEventSourceCreate(state_id: CGEventSourceStateID) -> CGEventSourceRef;
        fn CGEventCreateKeyboardEvent(
            source: CGEventSourceRef,
            virtual_key: CGKeyCode,
            key_down: bool,
        ) -> CGEventRef;
        fn CGEventSetFlags(event: CGEventRef, flags: CGEventFlags);
        fn CGEventKeyboardSetUnicodeString(
            event: CGEventRef,
            string_length: usize,
            unicode_string: *const u16,
        );
        fn CGEventPost(tap: CGEventTapLocation, event: CGEventRef);
    }

    #[link(name = "CoreFoundation", kind = "framework")]
    extern "C" {
        fn CFRelease(cf: *const c_void);
        fn CFStringCreateWithCString(
            alloc: CFAllocatorRef,
            c_str: *const i8,
            encoding: CFStringEncoding,
        ) -> CFStringRef;
    }

    #[link(name = "Carbon", kind = "framework")]
    extern "C" {
        fn IsSecureEventInputEnabled() -> i32;
        fn TISCopyCurrentKeyboardInputSource() -> TISInputSourceRef;
        fn TISCopyInputSourceForLanguage(lang: CFStringRef) -> TISInputSourceRef;
        fn TISSelectInputSource(source: TISInputSourceRef) -> i32;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Windows 实现
// ═══════════════════════════════════════════════════════════════════════════
#[cfg(target_os = "windows")]
mod windows_impl {
    use super::{TisError, TypeError};
    use std::time::Duration;
    use tauri::{AppHandle, Runtime};
    use windows::Win32::UI::Input::KeyboardAndMouse::{
        SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYBD_EVENT_FLAGS, KEYEVENTF_KEYUP,
        KEYEVENTF_UNICODE, VIRTUAL_KEY,
    };

    /// Windows / Linux 上没有 input source 概念，token 留空。Send/Sync 自动派生。
    pub struct PreviousInputSource;

    /// 同一个会话内 keyDown/keyUp 之间的微延迟。Windows SendInput Unicode 在大多数
    /// 应用上不需要延迟，但 Chromium 系（Edge / VSCode）观察到偶尔丢字，保留 1ms
    /// 兜底跟 macOS 对齐。
    const INTER_KEYSTROKE_DELAY: Duration = Duration::from_millis(1);

    pub fn type_unicode_chunk(text: &str) -> Result<(), TypeError> {
        if text.is_empty() {
            return Ok(());
        }
        for unit in text.encode_utf16() {
            send_utf16_unit(unit, false)?;
            send_utf16_unit(unit, true)?;
            std::thread::sleep(INTER_KEYSTROKE_DELAY);
        }
        Ok(())
    }

    fn send_utf16_unit(unit: u16, key_up: bool) -> Result<(), TypeError> {
        let flags = if key_up {
            KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        } else {
            KEYEVENTF_UNICODE
        };
        let input = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VIRTUAL_KEY(0),
                    wScan: unit,
                    dwFlags: KEYBD_EVENT_FLAGS(flags.0),
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let sent = unsafe { SendInput(&[input], std::mem::size_of::<INPUT>() as i32) };
        if sent == 1 {
            Ok(())
        } else {
            Err(TypeError::SendInputFailed(
                std::io::Error::last_os_error().to_string(),
            ))
        }
    }

    /// Windows SendInput Unicode 绕过 TSF 与 IME，无需切换输入法。返回 `Ok(None)`，
    /// `restore_input_source` 也是 no-op。
    pub async fn switch_to_ascii<R: Runtime>(
        _app: &AppHandle<R>,
    ) -> Result<Option<PreviousInputSource>, TisError> {
        Ok(None)
    }

    pub async fn restore_input_source<R: Runtime>(
        _app: &AppHandle<R>,
        _prev: Option<PreviousInputSource>,
    ) -> Result<(), TisError> {
        Ok(())
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Linux 实现（实验性）
// ═══════════════════════════════════════════════════════════════════════════
#[cfg(target_os = "linux")]
mod linux_impl {
    use super::{TisError, TypeError};
    use enigo::{Enigo, Keyboard, Settings};
    use tauri::{AppHandle, Runtime};

    pub struct PreviousInputSource;

    /// 用 enigo 一次 `text()` 把整段 chunk 发出去。X11 上走 XTest 稳定；Wayland 上
    /// 看 compositor 是否给 libei 权限，stock GNOME-Wayland 通常拒绝 —— 此处
    /// 失败返回 `EnigoInit` / `EnigoText`，调用方应回落到一次性。
    ///
    /// 不处理 fcitx / ibus 输入法切换 —— Linux 输入法栈与 X11 合成事件的交互非常
    /// 碎片化，v1 实验阶段直接交给用户保证当前输入源是英文键盘。
    pub fn type_unicode_chunk(text: &str) -> Result<(), TypeError> {
        if text.is_empty() {
            return Ok(());
        }
        let mut enigo =
            Enigo::new(&Settings::default()).map_err(|e| TypeError::EnigoInit(e.to_string()))?;
        enigo
            .text(text)
            .map_err(|e| TypeError::EnigoText(e.to_string()))
    }

    pub async fn switch_to_ascii<R: Runtime>(
        _app: &AppHandle<R>,
    ) -> Result<Option<PreviousInputSource>, TisError> {
        Ok(None)
    }

    pub async fn restore_input_source<R: Runtime>(
        _app: &AppHandle<R>,
        _prev: Option<PreviousInputSource>,
    ) -> Result<(), TisError> {
        Ok(())
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// 公共导出（按 cfg 分发到对应实现）
// ═══════════════════════════════════════════════════════════════════════════
#[cfg(target_os = "macos")]
#[allow(unused_imports)]
pub use macos_impl::{
    restore_input_source, switch_to_ascii, type_unicode_chunk, PreviousInputSource,
};

#[cfg(target_os = "windows")]
#[allow(unused_imports)]
pub use windows_impl::{
    restore_input_source, switch_to_ascii, type_unicode_chunk, PreviousInputSource,
};

#[cfg(target_os = "linux")]
#[allow(unused_imports)]
pub use linux_impl::{
    restore_input_source, switch_to_ascii, type_unicode_chunk, PreviousInputSource,
};
