//! 录音快捷键的自定义组合键监听器。
//!
//! 与 `hotkey.rs`（modifier-only 听写热键）平行——当用户选择自定义组合键
//! （如 `Cmd+Shift+D`）时，用 `global-hotkey` crate 注册。
//!
//! 与 `qa_hotkey.rs` 的关键区别：**同时产出 Pressed 和 Released 边沿事件**，
//! 以支持 Hold（按住说话）模式。`global-hotkey` crate 的 `HotKeyState::Released`
//! 在 macOS (Carbon) 和 Windows 上均可用于检测松开。
//!
//! 通过 `global_hotkey_runtime` 与 QA 快捷键共享进程级 manager / event receiver。

use std::sync::mpsc::{Receiver, Sender};
use std::sync::Arc;

use global_hotkey::{GlobalHotKeyEvent, HotKeyState};
use parking_lot::Mutex;

use crate::global_hotkey_runtime::{GlobalHotkeyRuntime, RegisteredHotkey};
use crate::shortcut_binding::{parse_global_hotkey, ShortcutBindingError};
use crate::types::ShortcutBinding;

#[derive(Debug, Clone, Copy)]
pub enum ComboHotkeyEvent {
    /// 用户按下了配置的组合键。
    Pressed,
    /// 用户松开了配置的组合键（用于 Hold 模式结束录音）。
    Released,
}

#[derive(Debug, thiserror::Error)]
pub enum ComboHotkeyError {
    #[error("不支持的修饰键: {0}")]
    UnsupportedModifier(String),
    #[error("不支持的主键: {0}")]
    UnsupportedKey(String),
    #[error("注册全局快捷键失败: {0}")]
    RegisterFailed(String),
    #[error("初始化全局快捷键管理器失败: {0}")]
    ManagerInitFailed(String),
}

/// 自定义组合键全局快捷键监听器。`Drop` 时反注册。
///
/// 内部用 `global-hotkey` crate；事件转发线程持有一个共享的 `Sender`。
/// 与 `QaHotkeyMonitor` 的区别：转发 Pressed **和** Released 事件。
pub struct ComboHotkeyMonitor {
    inner: Arc<Inner>,
}

struct Inner {
    registered: Mutex<Option<RegisteredHotkey>>,
    tx: Sender<ComboHotkeyEvent>,
}

// global-hotkey 0.6 的 GlobalHotKeyManager 在 Windows 内部持有 HHOOK / window
// handle 等 `*mut c_void`，crate 没标 Send/Sync。与 qa_hotkey.rs 同理。
unsafe impl Send for Inner {}
unsafe impl Sync for Inner {}

impl ComboHotkeyMonitor {
    /// 启动监听并注册一个组合键。`tx` 在每次按下/松开边沿收到事件。
    ///
    /// **注意**：`global-hotkey` crate 在 macOS 要求 manager 在主线程构造。
    /// 调用方需要确保从主线程触发。
    pub fn start(
        binding: ShortcutBinding,
        tx: Sender<ComboHotkeyEvent>,
    ) -> Result<Self, ComboHotkeyError> {
        let runtime = GlobalHotkeyRuntime::shared()
            .map_err(|e| ComboHotkeyError::ManagerInitFailed(e.to_string()))?;

        let hotkey = parse_binding(&binding)?;
        let (registered, rx) = runtime
            .register(hotkey)
            .map_err(|e| ComboHotkeyError::RegisterFailed(e.to_string()))?;

        // runtime 已按 hotkey id 分发；这里保留 id 检查作为防线，
        // 避免未来误接回进程级事件流后串到其他快捷键。
        let hotkey_id = registered.hotkey().id();
        let tx_for_thread = tx.clone();
        std::thread::Builder::new()
            .name("openless-combo-hotkey-forward".into())
            .spawn(move || forward_loop(hotkey_id, rx, tx_for_thread))
            .map_err(|e| ComboHotkeyError::RegisterFailed(format!("spawn forward thread: {e}")))?;

        Ok(Self {
            inner: Arc::new(Inner {
                registered: Mutex::new(Some(registered)),
                tx,
            }),
        })
    }

    /// 替换当前注册的组合键（用户在设置里改了组合键时）。
    pub fn update_binding(&self, binding: ShortcutBinding) -> Result<(), ComboHotkeyError> {
        let next = parse_binding(&binding)?;
        let mut current = self.inner.registered.lock();
        if let Some(prev) = current.as_ref() {
            if prev.hotkey() == next {
                return Ok(());
            }
        }
        let runtime = GlobalHotkeyRuntime::shared()
            .map_err(|e| ComboHotkeyError::ManagerInitFailed(e.to_string()))?;
        let (registered, rx) = runtime
            .register(next)
            .map_err(|e| ComboHotkeyError::RegisterFailed(e.to_string()))?;
        let hotkey_id = registered.hotkey().id();
        std::thread::Builder::new()
            .name("openless-combo-hotkey-forward".into())
            .spawn({
                let tx = self.inner.tx.clone();
                move || forward_loop(hotkey_id, rx, tx)
            })
            .map_err(|e| ComboHotkeyError::RegisterFailed(format!("spawn forward thread: {e}")))?;
        *current = Some(registered);
        Ok(())
    }
}

impl Drop for ComboHotkeyMonitor {
    fn drop(&mut self) {
        self.inner.registered.lock().take();
    }
}

fn forward_loop(hotkey_id: u32, rx: Receiver<GlobalHotKeyEvent>, tx: Sender<ComboHotkeyEvent>) {
    while let Ok(event) = rx.recv() {
        if event.id() != hotkey_id {
            continue;
        }
        let combo_event = match event.state() {
            HotKeyState::Pressed => ComboHotkeyEvent::Pressed,
            HotKeyState::Released => ComboHotkeyEvent::Released,
        };
        if let Err(e) = tx.send(combo_event) {
            log::warn!("[combo-hotkey] 事件投递失败: {e}");
            break;
        }
    }
    log::info!("[combo-hotkey] 转发线程退出");
}

/// 测试一个组合键是否可以注册（不实际注册，仅验证格式）。
pub fn validate_binding(binding: &ShortcutBinding) -> Result<(), ComboHotkeyError> {
    parse_binding(binding)?;
    Ok(())
}

fn parse_binding(
    binding: &ShortcutBinding,
) -> Result<global_hotkey::hotkey::HotKey, ComboHotkeyError> {
    parse_global_hotkey(binding).map_err(|e| match e {
        ShortcutBindingError::UnsupportedModifier(m) => ComboHotkeyError::UnsupportedModifier(m),
        ShortcutBindingError::UnsupportedKey(k) => ComboHotkeyError::UnsupportedKey(k),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use global_hotkey::hotkey::{Code, Modifiers};

    #[test]
    fn parse_cmd_shift_d() {
        let binding = ShortcutBinding {
            primary: "D".into(),
            modifiers: vec!["cmd".into(), "shift".into()],
        };
        let parsed = parse_binding(&binding).expect("binding parses");
        #[cfg(target_os = "windows")]
        assert!(parsed.mods.contains(Modifiers::CONTROL));
        #[cfg(not(target_os = "windows"))]
        assert!(parsed.mods.contains(Modifiers::SUPER));
        assert!(parsed.mods.contains(Modifiers::SHIFT));
        assert_eq!(parsed.key, Code::KeyD);
    }

    #[test]
    fn parse_ctrl_shift_space() {
        let binding = ShortcutBinding {
            primary: "Space".into(),
            modifiers: vec!["ctrl".into(), "shift".into()],
        };
        let parsed = parse_binding(&binding).expect("binding parses");
        assert!(parsed.mods.contains(Modifiers::CONTROL));
        assert!(parsed.mods.contains(Modifiers::SHIFT));
        assert_eq!(parsed.key, Code::Space);
    }

    #[test]
    fn unsupported_modifier_rejected() {
        let binding = ShortcutBinding {
            primary: "D".into(),
            modifiers: vec!["hyper".into()],
        };
        assert!(matches!(
            parse_binding(&binding),
            Err(ComboHotkeyError::UnsupportedModifier(_))
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
            Err(ComboHotkeyError::UnsupportedKey(_))
        ));
    }

    #[test]
    fn bare_shift_is_rejected_for_combo_hotkey() {
        let binding = ShortcutBinding {
            primary: "Shift".into(),
            modifiers: vec![],
        };
        assert!(matches!(
            validate_binding(&binding),
            Err(ComboHotkeyError::UnsupportedKey(_))
        ));
    }

    #[test]
    fn legacy_modifier_only_is_rejected_for_combo_hotkey() {
        let binding = ShortcutBinding {
            primary: "RightOption".into(),
            modifiers: vec![],
        };
        assert!(matches!(
            validate_binding(&binding),
            Err(ComboHotkeyError::UnsupportedKey(_))
        ));
    }

    #[test]
    fn forward_loop_ignores_unrelated_hotkey_ids() {
        let (event_tx, event_rx) = std::sync::mpsc::channel();
        let (out_tx, out_rx) = std::sync::mpsc::channel();

        event_tx
            .send(GlobalHotKeyEvent {
                id: 7,
                state: HotKeyState::Pressed,
            })
            .unwrap();
        event_tx
            .send(GlobalHotKeyEvent {
                id: 8,
                state: HotKeyState::Released,
            })
            .unwrap();
        event_tx
            .send(GlobalHotKeyEvent {
                id: 8,
                state: HotKeyState::Pressed,
            })
            .unwrap();
        drop(event_tx);

        forward_loop(8, event_rx, out_tx);

        assert!(matches!(out_rx.recv().unwrap(), ComboHotkeyEvent::Released));
        assert!(matches!(out_rx.recv().unwrap(), ComboHotkeyEvent::Pressed));
        assert!(out_rx.try_recv().is_err());
    }
}
