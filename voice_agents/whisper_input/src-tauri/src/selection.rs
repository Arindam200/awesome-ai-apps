//! 跨平台「划词捕获」工具：在用户触发 QA 快捷键时尝试拿到当前前台 app 的选区文本。
//!
//! 三级 fallback：
//! 1. **macOS** AX：`AXUIElementCopyAttributeValue(focused, kAXSelectedTextAttribute)`
//!    走辅助功能 API 直读焦点元素的选区，**不**触碰剪贴板。
//! 2. **macOS / Windows** Cmd+C / Ctrl+C：snapshot 用户原剪贴板 → 模拟复制 → 80ms
//!    后读出新内容 → 还原原剪贴板。
//! 3. **Linux**：返回 `None`（X11/Wayland AX 模式不统一，留作 best-effort 后续）。
//!
//! 截断策略：超过 4000 字符的选区只保留首 2000 + 尾 2000 + `[…truncated…]` 标记，
//! 避免给 LLM 灌过长 context。
//!
//! 模块依赖：仅 `arboard`（跨平台剪贴板）+ libc + 平台 native 框架；不依赖其它
//! Rust 模块（与 CLAUDE.md 对齐）。

use std::time::Duration;

const SELECTION_MAX_CHARS: usize = 4000;
const SELECTION_TRUNCATE_HEAD: usize = 2000;
const SELECTION_TRUNCATE_TAIL: usize = 2000;
const SELECTION_TRUNCATED_MARKER: &str = "\n[…truncated…]\n";

/// 从前台 app 读到的选区上下文。
/// `text` 已经过截断处理；`source_app` 是前台 app 的人类可读标签（可空）。
#[derive(Debug, Clone)]
pub struct SelectionContext {
    pub text: String,
    pub source_app: Option<String>,
}

/// 尝试捕获当前选区文本。所有 IO 都在调用线程完成（短小、阻塞但 < 200ms）。
///
/// 返回 `None` 表示真的没拿到东西（用户没选 / 平台不支持 / 权限缺失）。
/// 返回 `Some(ctx)` 时 `ctx.text` **保证非空**。
pub fn capture_selection() -> Option<SelectionContext> {
    let source_app = current_front_app();

    // 1. macOS AX 直读
    #[cfg(target_os = "macos")]
    if let Some(text) = macos_ax::read_selected_text() {
        let trimmed = text.trim();
        if !trimmed.is_empty() {
            log::info!(
                "[selection] AX read OK ({} chars){}",
                trimmed.chars().count(),
                source_app
                    .as_deref()
                    .map(|a| format!(" front_app={a}"))
                    .unwrap_or_default()
            );
            return Some(SelectionContext {
                text: truncate_selection(trimmed),
                source_app,
            });
        }
    }

    // 2. 模拟复制 fallback（macOS / Windows）
    #[cfg(any(target_os = "macos", target_os = "windows"))]
    if let Some(text) = simulate_copy_and_read() {
        let trimmed = text.trim();
        if !trimmed.is_empty() {
            log::info!(
                "[selection] simulate-copy fallback OK ({} chars){}",
                trimmed.chars().count(),
                source_app
                    .as_deref()
                    .map(|a| format!(" front_app={a}"))
                    .unwrap_or_default()
            );
            return Some(SelectionContext {
                text: truncate_selection(trimmed),
                source_app,
            });
        }
    }

    // 3. Linux：best-effort 读 PRIMARY selection（wl-paste / xclip / xsel）。
    #[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
    if let Some(text) = linux_selection::read_selected_text() {
        let trimmed = text.trim();
        if !trimmed.is_empty() {
            log::info!(
                "[selection] linux primary selection OK ({} chars){}",
                trimmed.chars().count(),
                source_app
                    .as_deref()
                    .map(|a| format!(" front_app={a}"))
                    .unwrap_or_default()
            );
            return Some(SelectionContext {
                text: truncate_selection(trimmed),
                source_app,
            });
        }
    }

    None
}

/// 长度截断到首 + 尾 + 标记。
fn truncate_selection(text: &str) -> String {
    let total: usize = text.chars().count();
    if total <= SELECTION_MAX_CHARS {
        return text.to_string();
    }
    let head: String = text.chars().take(SELECTION_TRUNCATE_HEAD).collect();
    let tail_start = total.saturating_sub(SELECTION_TRUNCATE_TAIL);
    let tail: String = text.chars().skip(tail_start).collect();
    format!("{head}{SELECTION_TRUNCATED_MARKER}{tail}")
}

// ─────────────────────────── 模拟复制 fallback (mac/win) ───────────────────────────

#[cfg(any(target_os = "macos", target_os = "windows"))]
fn simulate_copy_and_read() -> Option<String> {
    // a) snapshot 当前剪贴板（用作还原原状态的备份）
    let mut clipboard = match arboard::Clipboard::new() {
        Ok(c) => c,
        Err(e) => {
            log::warn!("[selection] clipboard init failed: {e}");
            return None;
        }
    };
    let original = match clipboard.get_text() {
        Ok(t) => Some(t),
        Err(e) => {
            log::info!("[selection] clipboard get_text returned err (likely empty): {e}");
            None
        }
    };

    // b) 写一个 sentinel 进剪贴板 — 之后用来检查模拟复制是否真的有覆盖（如果还是
    //    sentinel 说明 Cmd+C 没生效或目标 app 没选区）。
    let sentinel = format!("__openless_qa_sentinel_{}__", uuid_like_token());
    if let Err(e) = clipboard.set_text(sentinel.clone()) {
        log::warn!("[selection] clipboard set_text(sentinel) failed: {e}");
        // 即使设置 sentinel 失败，也尝试发 Cmd+C 看能不能直接拿到东西
    }

    // c) 模拟 Cmd+C / Ctrl+C
    let post_ok = post_copy_shortcut();
    if !post_ok {
        log::warn!("[selection] post_copy_shortcut failed");
        // 不立刻 return：剪贴板可能已经被某些路径污染，按下方还原流程恢复。
    }

    // d) 等剪贴板更新（macOS / Windows 都需要少量时间让目标 app 把数据 put 进去）
    std::thread::sleep(Duration::from_millis(80));

    // e) 读新值
    let captured = clipboard.get_text().ok();

    // f) 还原原剪贴板
    if let Some(prev) = original {
        if let Err(e) = clipboard.set_text(prev) {
            log::warn!("[selection] clipboard restore failed: {e}");
        }
    } else {
        // 用户原剪贴板就是空 → 把 sentinel / 选区清掉，避免污染。
        if let Err(e) = clipboard.set_text("") {
            log::warn!("[selection] clipboard clear failed: {e}");
        }
    }

    let captured = captured?;
    if captured == sentinel || captured.is_empty() {
        return None;
    }
    Some(captured)
}

#[cfg(any(target_os = "macos", target_os = "windows"))]
fn uuid_like_token() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    format!("{nanos:x}")
}

#[cfg(target_os = "macos")]
fn post_copy_shortcut() -> bool {
    macos_paste::post_cmd_c().is_ok()
}

#[cfg(target_os = "windows")]
fn post_copy_shortcut() -> bool {
    windows_paste::send_ctrl_c().is_ok()
}

#[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
mod linux_selection {
    use std::process::Command;

    const PRIMARY_SELECTION_COMMANDS: &[(&str, &[&str])] = &[
        ("wl-paste", &["--primary", "--no-newline"]),
        ("xclip", &["-o", "-selection", "primary"]),
        ("xsel", &["--primary", "--output"]),
    ];

    pub fn read_selected_text() -> Option<String> {
        for (bin, args) in PRIMARY_SELECTION_COMMANDS {
            if let Some(text) = run_capture(bin, args) {
                return Some(text);
            }
        }
        log::info!(
            "[selection] linux primary selection unavailable (wl-paste/xclip/xsel all failed)"
        );
        None
    }

    fn run_capture(bin: &str, args: &[&str]) -> Option<String> {
        let output = Command::new(bin).args(args).output().ok()?;
        if !output.status.success() {
            return None;
        }
        let text = String::from_utf8(output.stdout).ok()?;
        let trimmed = text.trim();
        if trimmed.is_empty() {
            return None;
        }
        Some(trimmed.to_string())
    }
}

// ─────────────────────────── macOS AX read ───────────────────────────

#[cfg(target_os = "macos")]
mod macos_ax {
    use std::ffi::{c_void, CStr};
    use std::os::raw::c_char;

    #[repr(C)]
    struct OpaqueAxRef(c_void);
    type AxUiElementRef = *mut OpaqueAxRef;
    type CFStringRef = *const c_void;
    type CFTypeRef = *const c_void;
    type CFAllocatorRef = *const c_void;
    type AxError = i32;

    const AX_ERROR_SUCCESS: AxError = 0;

    #[link(name = "ApplicationServices", kind = "framework")]
    extern "C" {
        fn AXUIElementCreateSystemWide() -> AxUiElementRef;
        fn AXUIElementCopyAttributeValue(
            element: AxUiElementRef,
            attribute: CFStringRef,
            value: *mut CFTypeRef,
        ) -> AxError;
    }

    #[link(name = "CoreFoundation", kind = "framework")]
    extern "C" {
        fn CFRelease(cf: CFTypeRef);
        fn CFStringCreateWithCString(
            allocator: CFAllocatorRef,
            cstr: *const c_char,
            encoding: u32,
        ) -> CFStringRef;
        fn CFStringGetCStringPtr(s: CFStringRef, encoding: u32) -> *const c_char;
        fn CFStringGetCString(
            s: CFStringRef,
            buffer: *mut c_char,
            buffer_size: isize,
            encoding: u32,
        ) -> bool;
        fn CFStringGetLength(s: CFStringRef) -> isize;
        fn CFStringGetMaximumSizeForEncoding(length: isize, encoding: u32) -> isize;
    }

    const K_CF_STRING_ENCODING_UTF8: u32 = 0x0800_0100;

    /// 调 system-wide AX 树拿 focused element，再读它的 selected text。
    /// 失败（权限缺失 / 没焦点 / 该控件不支持选区属性）时返回 None。
    pub fn read_selected_text() -> Option<String> {
        unsafe {
            let system = AXUIElementCreateSystemWide();
            if system.is_null() {
                return None;
            }
            // 注意：这里不能直接用 CFSTR 宏（Rust 没有），改用 CFStringCreateWithCString
            // 临时构造 attribute key。
            let focused_attr =
                cfstring_from_static(b"AXFocusedUIElement\0").unwrap_or(std::ptr::null());
            let selected_attr =
                cfstring_from_static(b"AXSelectedText\0").unwrap_or(std::ptr::null());
            if focused_attr.is_null() || selected_attr.is_null() {
                if !system.is_null() {
                    CFRelease(system as CFTypeRef);
                }
                if !focused_attr.is_null() {
                    CFRelease(focused_attr);
                }
                if !selected_attr.is_null() {
                    CFRelease(selected_attr);
                }
                return None;
            }

            let mut focused: CFTypeRef = std::ptr::null();
            let err = AXUIElementCopyAttributeValue(system, focused_attr, &mut focused);
            CFRelease(system as CFTypeRef);
            CFRelease(focused_attr);
            if err != AX_ERROR_SUCCESS || focused.is_null() {
                CFRelease(selected_attr);
                return None;
            }

            let mut selected: CFTypeRef = std::ptr::null();
            let err2 = AXUIElementCopyAttributeValue(
                focused as AxUiElementRef,
                selected_attr,
                &mut selected,
            );
            CFRelease(focused);
            CFRelease(selected_attr);
            if err2 != AX_ERROR_SUCCESS || selected.is_null() {
                return None;
            }

            let result = cfstring_to_rust(selected);
            CFRelease(selected);
            result
        }
    }

    unsafe fn cfstring_from_static(bytes_with_nul: &[u8]) -> Option<CFStringRef> {
        let cstr = CStr::from_bytes_with_nul(bytes_with_nul).ok()?;
        let s =
            CFStringCreateWithCString(std::ptr::null(), cstr.as_ptr(), K_CF_STRING_ENCODING_UTF8);
        if s.is_null() {
            None
        } else {
            Some(s)
        }
    }

    unsafe fn cfstring_to_rust(s: CFStringRef) -> Option<String> {
        let direct = CFStringGetCStringPtr(s, K_CF_STRING_ENCODING_UTF8);
        if !direct.is_null() {
            let cstr = CStr::from_ptr(direct);
            return cstr.to_str().ok().map(|s| s.to_string());
        }
        let length = CFStringGetLength(s);
        if length <= 0 {
            return Some(String::new());
        }
        let max_bytes = CFStringGetMaximumSizeForEncoding(length, K_CF_STRING_ENCODING_UTF8) + 1;
        let mut buf: Vec<u8> = vec![0; max_bytes as usize];
        let ok = CFStringGetCString(
            s,
            buf.as_mut_ptr() as *mut c_char,
            max_bytes,
            K_CF_STRING_ENCODING_UTF8,
        );
        if !ok {
            return None;
        }
        let cstr = CStr::from_ptr(buf.as_ptr() as *const c_char);
        cstr.to_str().ok().map(|s| s.to_string())
    }
}

// ─────────────────────────── macOS Cmd+C post ───────────────────────────

#[cfg(target_os = "macos")]
mod macos_paste {
    use std::ffi::c_void;

    #[repr(C)]
    struct OpaqueCGEvent(c_void);
    type CGEventRef = *mut OpaqueCGEvent;

    #[repr(C)]
    struct OpaqueCGEventSource(c_void);
    type CGEventSourceRef = *mut OpaqueCGEventSource;

    type CGEventTapLocation = u32;
    type CGEventSourceStateID = i32;
    type CGKeyCode = u16;
    type CGEventFlags = u64;

    const KCG_HID_EVENT_TAP: CGEventTapLocation = 0;
    const KCG_EVENT_SOURCE_STATE_HID_SYSTEM_STATE: CGEventSourceStateID = 1;
    const KCG_EVENT_FLAG_MASK_COMMAND: CGEventFlags = 0x0010_0000;
    /// kVK_ANSI_C
    const KEY_C: CGKeyCode = 8;

    #[link(name = "CoreGraphics", kind = "framework")]
    extern "C" {
        fn CGEventSourceCreate(state_id: CGEventSourceStateID) -> CGEventSourceRef;
        fn CGEventCreateKeyboardEvent(
            source: CGEventSourceRef,
            virtual_key: CGKeyCode,
            key_down: bool,
        ) -> CGEventRef;
        fn CGEventSetFlags(event: CGEventRef, flags: CGEventFlags);
        fn CGEventPost(tap: CGEventTapLocation, event: CGEventRef);
    }

    #[link(name = "CoreFoundation", kind = "framework")]
    extern "C" {
        fn CFRelease(cf: *const c_void);
    }

    pub fn post_cmd_c() -> Result<(), String> {
        unsafe {
            let source = CGEventSourceCreate(KCG_EVENT_SOURCE_STATE_HID_SYSTEM_STATE);
            let down = CGEventCreateKeyboardEvent(source, KEY_C, true);
            let up = CGEventCreateKeyboardEvent(source, KEY_C, false);
            if down.is_null() || up.is_null() {
                if !source.is_null() {
                    CFRelease(source as *const c_void);
                }
                if !down.is_null() {
                    CFRelease(down as *const c_void);
                }
                if !up.is_null() {
                    CFRelease(up as *const c_void);
                }
                return Err("CGEventCreateKeyboardEvent returned null".into());
            }
            CGEventSetFlags(down, KCG_EVENT_FLAG_MASK_COMMAND);
            CGEventSetFlags(up, KCG_EVENT_FLAG_MASK_COMMAND);
            CGEventPost(KCG_HID_EVENT_TAP, down);
            CGEventPost(KCG_HID_EVENT_TAP, up);
            CFRelease(down as *const c_void);
            CFRelease(up as *const c_void);
            if !source.is_null() {
                CFRelease(source as *const c_void);
            }
        }
        Ok(())
    }
}

// ─────────────────────────── Windows Ctrl+C send ───────────────────────────

#[cfg(target_os = "windows")]
mod windows_paste {
    use windows::Win32::UI::Input::KeyboardAndMouse::{
        SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYBD_EVENT_FLAGS, KEYEVENTF_KEYUP,
        VIRTUAL_KEY, VK_C, VK_CONTROL,
    };

    pub fn send_ctrl_c() -> Result<(), String> {
        let mut inputs = [
            keyboard_event(VK_CONTROL, false),
            keyboard_event(VK_C, false),
            keyboard_event(VK_C, true),
            keyboard_event(VK_CONTROL, true),
        ];

        let sent = unsafe { SendInput(&mut inputs, std::mem::size_of::<INPUT>() as i32) };
        if (sent as usize) != inputs.len() {
            return Err(format!("SendInput sent {sent}/{}", inputs.len()));
        }
        Ok(())
    }

    fn keyboard_event(vk: VIRTUAL_KEY, key_up: bool) -> INPUT {
        let mut flags = KEYBD_EVENT_FLAGS(0);
        if key_up {
            flags |= KEYEVENTF_KEYUP;
        }
        INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: vk,
                    wScan: 0,
                    dwFlags: flags,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        }
    }
}

// ─────────────────────────── front-app label ───────────────────────────

#[cfg(target_os = "macos")]
fn current_front_app() -> Option<String> {
    use objc2::msg_send;
    use objc2::runtime::{AnyClass, AnyObject};

    unsafe {
        let cls = AnyClass::get("NSWorkspace")?;
        let workspace: *mut AnyObject = msg_send![cls, sharedWorkspace];
        if workspace.is_null() {
            return None;
        }
        let app: *mut AnyObject = msg_send![workspace, frontmostApplication];
        if app.is_null() {
            return None;
        }
        let name_obj: *mut AnyObject = msg_send![app, localizedName];
        let name = ns_string_to_rust(name_obj);
        let bundle_obj: *mut AnyObject = msg_send![app, bundleIdentifier];
        let bundle = ns_string_to_rust(bundle_obj);
        match (name, bundle) {
            (Some(n), Some(b)) => Some(format!("{n} ({b})")),
            (Some(n), None) => Some(n),
            (None, Some(b)) => Some(b),
            (None, None) => None,
        }
    }
}

#[cfg(target_os = "macos")]
unsafe fn ns_string_to_rust(ns_string: *mut objc2::runtime::AnyObject) -> Option<String> {
    use objc2::msg_send;
    if ns_string.is_null() {
        return None;
    }
    let utf8: *const std::os::raw::c_char = unsafe { msg_send![ns_string, UTF8String] };
    if utf8.is_null() {
        return None;
    }
    let cstr = unsafe { std::ffi::CStr::from_ptr(utf8) };
    let s = cstr.to_string_lossy().into_owned();
    if s.is_empty() {
        None
    } else {
        Some(s)
    }
}

#[cfg(target_os = "windows")]
fn current_front_app() -> Option<String> {
    use windows::Win32::UI::WindowsAndMessaging::{
        GetForegroundWindow, GetWindowTextLengthW, GetWindowTextW,
    };
    unsafe {
        let hwnd = GetForegroundWindow();
        if hwnd.0.is_null() {
            return None;
        }
        let len = GetWindowTextLengthW(hwnd);
        if len <= 0 {
            return None;
        }
        let mut buf = vec![0u16; (len + 1) as usize];
        let copied = GetWindowTextW(hwnd, &mut buf);
        if copied <= 0 {
            return None;
        }
        let title = String::from_utf16_lossy(&buf[..copied as usize]);
        if title.is_empty() {
            None
        } else {
            Some(title)
        }
    }
}

#[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
fn current_front_app() -> Option<String> {
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn truncate_short_passes_through() {
        let text = "hello world";
        assert_eq!(truncate_selection(text), text);
    }

    #[test]
    fn truncate_long_keeps_head_and_tail() {
        let head: String = "a".repeat(SELECTION_TRUNCATE_HEAD);
        let middle: String = "b".repeat(2_000);
        let tail: String = "c".repeat(SELECTION_TRUNCATE_TAIL);
        let combined = format!("{head}{middle}{tail}");
        let out = truncate_selection(&combined);
        assert!(out.contains("[…truncated…]"));
        assert!(out.starts_with(&"a".repeat(50)));
        assert!(out.ends_with(&"c".repeat(50)));
        // 中段 b 应被裁掉
        assert!(!out.contains(&"b".repeat(20)));
    }
}
