//! 划词语音问答（QA）专用的全局快捷键监听器。
//!
//! 与 `hotkey.rs`（modifier-only 听写热键）平行——QA 用的是组合键
//! `Cmd+Shift+;` / `Ctrl+Shift+;`，所以走 `global-hotkey` crate（macOS 内部
//! 用 Carbon `RegisterEventHotKey`，Windows 用 `RegisterHotKey`，Linux 用 X11）。
//!
//! 仅产出 `QaHotkeyEvent::Pressed` 边沿事件；toggle / 录音生命周期由
//! coordinator 解释（第一次按 → 开始问答；第二次按 → 结束）。
//!
//! 通过 `global_hotkey_runtime` 共享进程级 manager / event receiver。

use std::sync::mpsc::{Receiver, Sender};
use std::sync::Arc;

use global_hotkey::{GlobalHotKeyEvent, HotKeyState};
use parking_lot::Mutex;

use crate::global_hotkey_runtime::{GlobalHotkeyRuntime, RegisteredHotkey};
use crate::shortcut_binding::{parse_global_hotkey, ShortcutBindingError};
use crate::types::ShortcutBinding;

#[derive(Debug, Clone, Copy)]
pub enum QaHotkeyEvent {
    /// 用户按下了配置的 QA 组合键（toggle 模式：第一次开始，第二次结束）。
    Pressed,
}

#[derive(Debug, thiserror::Error)]
pub enum QaHotkeyError {
    #[error("不支持的修饰键: {0}")]
    UnsupportedModifier(String),
    #[error("不支持的主键: {0}")]
    UnsupportedKey(String),
    #[error("注册全局快捷键失败: {0}")]
    RegisterFailed(String),
    #[error("初始化全局快捷键管理器失败: {0}")]
    ManagerInitFailed(String),
}

/// QA 全局快捷键监听器。`Drop` 时反注册。
///
/// 内部用 `global-hotkey` crate；事件转发线程持有一个共享的 `Sender`。
pub struct QaHotkeyMonitor {
    inner: Arc<Inner>,
}

struct Inner {
    /// 当前注册的 hotkey 句柄；用于 unregister。
    registered: Mutex<Option<RegisteredHotkey>>,
    tx: Sender<QaHotkeyEvent>,
}

// global-hotkey 0.6 的 GlobalHotKeyManager 在 Windows 内部持有 HHOOK / window
// handle 等 `*mut c_void`，crate 没标 Send/Sync。但这些句柄实际是 OS 进程级
// 资源，跨线程读写是 OS 自己同步的；coordinator.rs 又需要把 `Arc<Inner>`（间接含
// QaHotkeyMonitor）放进 async_runtime::spawn 里，强制要求 Send。手动标记。
// macOS 上 GlobalHotKeyManager 内部用 Carbon EventHotKey，同理。
// 与 hotkey.rs::CallbackContext 已有的 unsafe impl Send/Sync 同款做法。
unsafe impl Send for Inner {}
unsafe impl Sync for Inner {}

impl QaHotkeyMonitor {
    /// 启动监听并注册一个 hotkey。`tx` 在每次按下边沿收到 `QaHotkeyEvent::Pressed`。
    ///
    /// **注意**：`global-hotkey` crate 在 macOS 要求 manager 在主线程构造。
    /// 调用方需要确保从主线程触发（coordinator 的 supervisor 线程会通过
    /// `AppHandle::run_on_main_thread` 跳到主线程后再 spawn 这个 monitor）。
    /// 本函数不强制断言主线程——单元 / 集成测试也跑不到 manager 创建那一行。
    pub fn start(
        binding: ShortcutBinding,
        tx: Sender<QaHotkeyEvent>,
    ) -> Result<Self, QaHotkeyError> {
        let runtime = GlobalHotkeyRuntime::shared()
            .map_err(|e| QaHotkeyError::ManagerInitFailed(e.to_string()))?;

        let hotkey = parse_binding(&binding)?;
        let (registered, rx) = runtime
            .register(hotkey)
            .map_err(|e| QaHotkeyError::RegisterFailed(e.to_string()))?;

        // 启动转发线程：runtime 已按 hotkey id 分发；这里保留 id 检查作为防线，
        // 避免未来误接回进程级事件流后串到其他快捷键。
        let hotkey_id = registered.hotkey().id();
        let tx_for_thread = tx.clone();
        std::thread::Builder::new()
            .name("openless-qa-hotkey-forward".into())
            .spawn(move || forward_loop(hotkey_id, rx, tx_for_thread))
            .map_err(|e| QaHotkeyError::RegisterFailed(format!("spawn forward thread: {e}")))?;

        Ok(Self {
            inner: Arc::new(Inner {
                registered: Mutex::new(Some(registered)),
                tx,
            }),
        })
    }

    /// 替换当前注册的 hotkey（用户在设置里改了组合键时）。
    pub fn update_binding(&self, binding: ShortcutBinding) -> Result<(), QaHotkeyError> {
        let next = parse_binding(&binding)?;
        let mut current = self.inner.registered.lock();
        if let Some(prev) = current.as_ref() {
            if prev.hotkey() == next {
                return Ok(());
            }
        }
        let runtime = GlobalHotkeyRuntime::shared()
            .map_err(|e| QaHotkeyError::ManagerInitFailed(e.to_string()))?;
        let (registered, rx) = runtime
            .register(next)
            .map_err(|e| QaHotkeyError::RegisterFailed(e.to_string()))?;
        let hotkey_id = registered.hotkey().id();
        // Keep event forwarding alive for the replacement registration.
        std::thread::Builder::new()
            .name("openless-qa-hotkey-forward".into())
            .spawn({
                let tx = self.inner.tx.clone();
                move || forward_loop(hotkey_id, rx, tx)
            })
            .map_err(|e| QaHotkeyError::RegisterFailed(format!("spawn forward thread: {e}")))?;
        *current = Some(registered);
        Ok(())
    }
}

impl Drop for QaHotkeyMonitor {
    fn drop(&mut self) {
        self.inner.registered.lock().take();
    }
}

fn forward_loop(hotkey_id: u32, rx: Receiver<GlobalHotKeyEvent>, tx: Sender<QaHotkeyEvent>) {
    while let Ok(event) = rx.recv() {
        if event.id() != hotkey_id {
            continue;
        }
        if !matches!(event.state(), HotKeyState::Pressed) {
            continue;
        }
        if let Err(e) = tx.send(QaHotkeyEvent::Pressed) {
            log::warn!("[qa-hotkey] 事件投递失败: {e}");
            break;
        }
    }
    log::info!("[qa-hotkey] 转发线程退出");
}

fn parse_binding(
    binding: &ShortcutBinding,
) -> Result<global_hotkey::hotkey::HotKey, QaHotkeyError> {
    parse_global_hotkey(binding).map_err(|e| match e {
        ShortcutBindingError::UnsupportedModifier(m) => QaHotkeyError::UnsupportedModifier(m),
        ShortcutBindingError::UnsupportedKey(k) => QaHotkeyError::UnsupportedKey(k),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use global_hotkey::hotkey::{Code, Modifiers};

    #[test]
    fn parse_default_binding() {
        let binding = ShortcutBinding::default_qa();
        let parsed = parse_binding(&binding).expect("default binding parses");
        assert!(parsed.mods.contains(Modifiers::SHIFT));
        assert_eq!(parsed.key, Code::Semicolon);
    }

    #[test]
    fn parse_letter_binding() {
        let binding = ShortcutBinding {
            primary: "k".into(),
            modifiers: vec!["cmd".into(), "alt".into()],
        };
        let parsed = parse_binding(&binding).expect("letter binding parses");
        assert_eq!(parsed.key, Code::KeyK);
        #[cfg(target_os = "windows")]
        assert!(parsed.mods.contains(Modifiers::CONTROL));
        #[cfg(not(target_os = "windows"))]
        assert!(parsed.mods.contains(Modifiers::SUPER));
        assert!(parsed.mods.contains(Modifiers::ALT));
    }

    #[test]
    fn unsupported_modifier_rejected() {
        let binding = ShortcutBinding {
            primary: ";".into(),
            modifiers: vec!["hyper".into()],
        };
        assert!(matches!(
            parse_binding(&binding),
            Err(QaHotkeyError::UnsupportedModifier(_))
        ));
    }

    #[test]
    fn empty_primary_rejected() {
        let binding = ShortcutBinding {
            primary: "".into(),
            modifiers: vec!["cmd".into()],
        };
        assert!(matches!(
            parse_binding(&binding),
            Err(QaHotkeyError::UnsupportedKey(_))
        ));
    }

    #[test]
    fn cmd_modifier_normalizes_per_platform() {
        let binding = ShortcutBinding {
            primary: ";".into(),
            modifiers: vec!["cmd".into(), "shift".into()],
        };
        let parsed = parse_binding(&binding).expect("binding parses");

        #[cfg(target_os = "windows")]
        {
            assert!(parsed.mods.contains(Modifiers::CONTROL));
            assert!(!parsed.mods.contains(Modifiers::SUPER));
        }

        #[cfg(not(target_os = "windows"))]
        {
            assert!(parsed.mods.contains(Modifiers::SUPER));
        }
    }

    #[test]
    fn forward_loop_ignores_unrelated_hotkey_ids() {
        let (event_tx, event_rx) = std::sync::mpsc::channel();
        let (out_tx, out_rx) = std::sync::mpsc::channel();

        event_tx
            .send(GlobalHotKeyEvent {
                id: 41,
                state: HotKeyState::Pressed,
            })
            .unwrap();
        event_tx
            .send(GlobalHotKeyEvent {
                id: 42,
                state: HotKeyState::Released,
            })
            .unwrap();
        event_tx
            .send(GlobalHotKeyEvent {
                id: 42,
                state: HotKeyState::Pressed,
            })
            .unwrap();
        drop(event_tx);

        forward_loop(42, event_rx, out_tx);

        assert!(matches!(out_rx.recv().unwrap(), QaHotkeyEvent::Pressed));
        assert!(out_rx.try_recv().is_err());
    }
}
