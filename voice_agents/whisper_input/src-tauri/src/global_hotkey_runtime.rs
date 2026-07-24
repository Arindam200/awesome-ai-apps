//! Shared `global-hotkey` runtime.
//!
//! `global-hotkey` installs a process-level Carbon event handler on macOS and
//! exposes one process-level event receiver. OpenLess has two logical users of
//! that crate (QA and custom dictation combos), so they must share one manager
//! and one dispatcher instead of racing on `GlobalHotKeyEvent::receiver()`.

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::Arc;
use std::time::Duration;

use global_hotkey::hotkey::HotKey;
use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager};
use once_cell::sync::OnceCell;
use parking_lot::Mutex;

static RUNTIME: OnceCell<Arc<GlobalHotkeyRuntime>> = OnceCell::new();

pub struct GlobalHotkeyRuntime {
    manager: GlobalHotKeyManager,
    routes: Mutex<HashMap<u32, Sender<GlobalHotKeyEvent>>>,
    /// 用于 dispatcher loop 的退出信号。process-singleton 在生产路径里不会被
    /// drop，但 integration test / future RunEvent::Exit 钩子可以调用
    /// `request_shutdown` 让 dispatcher 退出。审计 3.4.4。
    shutdown: AtomicBool,
}

// global-hotkey 0.6 does not mark its manager Send/Sync on all platforms even
// though it wraps OS-level handles. Coordinator stores monitors across threads,
// matching the existing qa/combo monitor safety model.
unsafe impl Send for GlobalHotkeyRuntime {}
unsafe impl Sync for GlobalHotkeyRuntime {}

pub struct RegisteredHotkey {
    runtime: Arc<GlobalHotkeyRuntime>,
    hotkey: HotKey,
}

impl GlobalHotkeyRuntime {
    pub fn shared() -> Result<Arc<Self>, String> {
        RUNTIME
            .get_or_try_init(|| {
                let manager = GlobalHotKeyManager::new().map_err(|e| e.to_string())?;
                let runtime = Arc::new(Self {
                    manager,
                    routes: Mutex::new(HashMap::new()),
                    shutdown: AtomicBool::new(false),
                });
                start_dispatcher(Arc::clone(&runtime));
                Ok(runtime)
            })
            .cloned()
    }

    /// Signal the dispatcher loop to exit at its next 250 ms tick. Idempotent.
    /// Currently called only from tests; production app shutdown lets the OS
    /// reap the process. Audit 3.4.4.
    #[allow(dead_code)]
    pub fn request_shutdown(&self) {
        self.shutdown.store(true, Ordering::SeqCst);
    }

    pub fn register(
        self: &Arc<Self>,
        hotkey: HotKey,
    ) -> Result<(RegisteredHotkey, Receiver<GlobalHotKeyEvent>), String> {
        self.manager.register(hotkey).map_err(|e| e.to_string())?;
        let (tx, rx) = mpsc::channel();
        self.routes.lock().insert(hotkey.id(), tx);
        Ok((
            RegisteredHotkey {
                runtime: Arc::clone(self),
                hotkey,
            },
            rx,
        ))
    }

    fn unregister(&self, hotkey: HotKey) {
        self.routes.lock().remove(&hotkey.id());
        if let Err(e) = self.manager.unregister(hotkey) {
            log::warn!("[global-hotkey] unregister 失败: {e}");
        }
    }

    fn dispatch(&self, event: GlobalHotKeyEvent) {
        let tx = self.routes.lock().get(&event.id()).cloned();
        if let Some(tx) = tx {
            let _ = tx.send(event);
        }
    }
}

impl Drop for RegisteredHotkey {
    fn drop(&mut self) {
        self.runtime.unregister(self.hotkey);
    }
}

impl RegisteredHotkey {
    pub fn hotkey(&self) -> HotKey {
        self.hotkey
    }
}

fn start_dispatcher(runtime: Arc<GlobalHotkeyRuntime>) {
    std::thread::Builder::new()
        .name("openless-global-hotkey-dispatch".into())
        .spawn(move || {
            let receiver = GlobalHotKeyEvent::receiver();
            loop {
                if runtime.shutdown.load(Ordering::SeqCst) {
                    return;
                }
                match receiver.recv_timeout(Duration::from_millis(250)) {
                    Ok(event) => runtime.dispatch(event),
                    Err(_) => continue,
                }
            }
        })
        .expect("spawn global hotkey dispatcher");
}
