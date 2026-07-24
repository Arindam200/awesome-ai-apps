//! OpenLess Tauri backend.
//!
//! Modules mirror the original Swift libraries (one purpose per file):
//! - hotkey: global hotkey monitor
//! - recorder: microphone capture (16 kHz mono Int16 PCM)
//! - asr: streaming ASR providers (Volcengine SAUC bigmodel)
//! - polish: OpenAI-compatible chat completions client
//! - insertion: cursor-position text insertion (AX / paste)
//! - persistence: history + preferences + credentials vault
//! - coordinator: dictation state machine glue
//! - commands: Tauri IPC surface

mod asr;
mod audio_mute;
mod autostart;
mod combo_hotkey;
mod commands;
mod coordinator;
mod coordinator_state;
mod correction;
mod diagnostics;
mod global_hotkey_runtime;
mod hotkey;
mod insertion;
mod llm_gemini;
mod permissions;
mod persistence;
mod polish;
mod product;
#[cfg(test)]
mod provider_latency_smoke;
mod qa_hotkey;
#[path = "asr/qingyu_sidecar_protocol.rs"]
pub mod qingyu_sidecar_protocol;
mod recorder;
mod selection;
mod shortcut_binding;
mod types;
mod unicode_keystroke;
mod windows_hotkey_core;
mod windows_ime_ipc;
mod windows_ime_profile;
mod windows_ime_protocol;
mod windows_ime_session;

use std::sync::atomic::{AtomicBool, Ordering};
#[cfg(target_os = "macos")]
use std::sync::mpsc;
use std::sync::Arc;
use std::time::Duration;

const LOG_ROTATE_LIMIT_BYTES: u64 = 10 * 1024 * 1024;

/// 第一次 show 时把 QA 浮窗摆到屏幕底部居中；之后的 show 不再 reposition，
/// 让用户拖动后的位置在 hide → show 之间得以保持。详见 issue #118 v2。
static QA_WINDOW_POSITIONED: AtomicBool = AtomicBool::new(false);
static TRAY_MICROPHONE_WATCHER_STOPPING: AtomicBool = AtomicBool::new(false);
use tauri::menu::{
    CheckMenuItemBuilder, Menu, MenuBuilder, MenuItemBuilder, Submenu, SubmenuBuilder,
};
use tauri::tray::{MouseButton, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, LogicalPosition, LogicalSize, Manager, RunEvent, Runtime};

use crate::types::PolishMode;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let foundry_local_runtime = Arc::new(asr::local::FoundryLocalRuntime::new());
    let qingyu_local_asr = Arc::new(asr::qingyu::QingyuLocalAsrService::default());
    let diagnostic_store =
        diagnostics::DiagnosticStore::new().expect("error while initializing diagnostic store");
    #[cfg(target_os = "windows")]
    let coordinator = Arc::new(
        coordinator::Coordinator::new_with_foundry_runtime_and_qingyu(
            Arc::clone(&foundry_local_runtime),
            Arc::clone(&qingyu_local_asr),
            diagnostic_store.clone(),
        ),
    );
    #[cfg(not(target_os = "windows"))]
    let coordinator = Arc::new(coordinator::Coordinator::new_with_qingyu_local_asr(
        Arc::clone(&qingyu_local_asr),
        diagnostic_store.clone(),
    ));
    let local_asr_download_manager = Arc::new(asr::local::DownloadManager::new());

    tauri::Builder::default()
        // 单实例锁：第二个进程启动时立即退出，激活信号转给已运行实例的主窗口。
        // 否则两份 OpenLess（如 /Applications/ + dev build）会各自抓全局热键，
        // 导致按一次键、两个进程同时跑流水线、文本被插入两遍。见 issue #50。
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            log::info!(
                "[single-instance] another instance launched, focusing existing main window"
            );
            show_main_window(app);
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        // 跨平台开机自启：mac 写 LaunchAgent plist，linux 写 ~/.config/autostart/*.desktop，
        // windows 写 HKCU\Software\Microsoft\Windows\CurrentVersion\Run。前端 toggle 直接
        // 调插件 isEnabled / enable / disable，不维持本地 prefs，让 OS 当唯一真相。issue #194。
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .manage(coordinator.clone())
        .manage(diagnostic_store.clone())
        .manage(local_asr_download_manager.clone())
        .manage(foundry_local_runtime.clone())
        .manage(qingyu_local_asr.clone())
        .manage(commands::MicrophoneMonitorState::new(None))
        .manage(commands::TrayMicrophoneMenuState::new(Vec::new()))
        .setup(move |app| {
            init_file_logger();
            log::info!("=== {} 启动 ===", crate::product::PRODUCT_NAME);
            crate::autostart::repair_stale_autostart_entry();
            qingyu_local_asr.bind_app(app.handle().clone());

            // Capsule 启动时定位到屏幕底部居中并隐藏；coordinator 按需显示。
            // 与 Swift `CapsuleWindowController.repositionToBottomCenter` 同语义。
            if let Some(capsule) = app.get_webview_window("capsule") {
                if let Err(e) = position_capsule_bottom_center(&capsule, false) {
                    log::warn!("[capsule] position failed: {e}");
                }
                #[cfg(target_os = "windows")]
                if let Err(e) = capsule.set_ignore_cursor_events(true) {
                    log::warn!("[capsule] initial cursor passthrough failed: {e}");
                }
                let _ = capsule.hide();
            }

            // QA 浮窗（issue #118）：紧贴胶囊上方 8pt、屏幕底部居中、380×440。
            // 启动时 hide()，等 coordinator 在 open_qa_panel 时再 show + 首次定位。
            // tauri.conf.json 里需要声明 label="qa" 的窗口（前端 agent 负责）；
            // 这里 get_webview_window 返回 None 时直接跳过，不影响主流程。
            if let Some(qa) = app.get_webview_window("qa") {
                if let Err(e) = position_qa_window(&qa) {
                    log::warn!("[qa] position failed: {e}");
                }
                #[cfg(target_os = "macos")]
                make_qa_window_draggable_macos(&qa);
                let _ = qa.hide();
            } else {
                log::info!("[qa] qa 窗口未在 tauri.conf.json 中声明，前端 agent 会补上");
            }

            // 主窗口磨砂：macOS 用 NSVisualEffectView，Windows 用 Mica。
            // 没这一层的话 transparent: true 让窗口透明 → 背后只是空，不是磨砂。
            //
            // decorations 留给运行时分平台决定：macOS 默认 true 用系统红黄绿；
            // Windows 这里关掉 native chrome 让 React 端 WinTitleBar 接管。
            if let Some(main) = app.get_webview_window("main") {
                let app_for_close = app.handle().clone();
                main.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        hide_main_window(&app_for_close);
                    }
                });

                #[cfg(target_os = "macos")]
                {
                    use window_vibrancy::{
                        apply_vibrancy, NSVisualEffectMaterial, NSVisualEffectState,
                    };
                    if let Err(e) = main.set_decorations(true) {
                        log::warn!("[main] enable native decorations failed: {e}");
                    }
                    if let Err(e) = apply_vibrancy(
                        &main,
                        NSVisualEffectMaterial::HudWindow,
                        Some(NSVisualEffectState::Active),
                        Some(20.0),
                    ) {
                        log::warn!("[main] vibrancy failed: {e}");
                    }
                }
                #[cfg(target_os = "windows")]
                {
                    use window_vibrancy::apply_mica;
                    // The window starts hidden so Windows native chrome can be disabled before
                    // the first show; doing this after the native frame is visible is unreliable.
                    if let Err(e) = main.set_decorations(false) {
                        log::warn!("[main] disable native decorations failed: {e}");
                    }
                    if let Err(e) = apply_mica(&main, None) {
                        log::warn!("[main] mica failed: {e}");
                    }
                    apply_windows_rounded_frame(&main);
                }
                // 静默启动开关：prefs.start_minimized = true → 不弹主窗口，
                // 用户从菜单栏 / 托盘点击访问。开机自启时尤其有用，避免每次
                // 登录都被主窗口打扰。OPENLESS_SHOW_MAIN_ON_START=1 仍保留
                // 老的强制 show 路径（手动 dispatch 测试 / dev 用），优先级高
                // 于 prefs。
                let force_show =
                    std::env::var("OPENLESS_SHOW_MAIN_ON_START").ok().as_deref() == Some("1");
                let suppress_show = !force_show && coordinator.prefs().get().start_minimized;
                if suppress_show {
                    log::info!("[main] start_minimized=true → 跳过初始 show，等用户点托盘");
                } else if let Err(e) = main.show() {
                    log::warn!("[main] initial show failed: {e}");
                }
            }

            // 启动时主动弹 Accessibility 授权框（与 Swift `AppDelegate` 行为一致）。
            // 用户首次必看到系统提示；已授权则静默返回。
            #[cfg(target_os = "macos")]
            {
                let status = permissions::request_accessibility();
                log::info!("[startup] Accessibility status = {:?}", status);
            }

            // 菜单栏图标 — 与 Swift `MenuBarController` 同语义：
            // 左键点 → 显示/聚焦主窗口；菜单含「显示主窗口」「退出」。
            let tray_menu = build_tray_menu(app, &coordinator)?;
            let menu = tray_menu.menu;

            // 与 Swift `StatusBarIcon.swift` 行为一致：用全彩 AppIcon，**不**走 template 模式
            // （走 template 会被 macOS 染成单色 → 看起来像个黑方块）。
            if let Some(icon) = app.default_window_icon() {
                {
                    let state = app.state::<commands::TrayMicrophoneMenuState>();
                    *state.lock() = tray_menu.microphone_items;
                }
                let _tray = TrayIconBuilder::with_id("main-tray")
                    .icon(icon.clone())
                    .icon_as_template(false)
                    .menu(&menu)
                    .show_menu_on_left_click(false)
                    .on_menu_event(move |app, event| match event.id.as_ref() {
                        "toggle" => show_main_window(app),
                        "quit" => app.exit(0),
                        id => {
                            if handle_style_tray_menu_event(app, id) {
                                return;
                            }
                            handle_microphone_tray_menu_event(app, id);
                        }
                    })
                    .on_tray_icon_event(move |tray, event| match event {
                        TrayIconEvent::Enter { .. } => {
                            if let Err(err) = refresh_tray_microphone_menu(tray.app_handle()) {
                                log::warn!("[tray] refresh microphone menu on hover failed: {err}");
                            }
                        }
                        TrayIconEvent::Click {
                            button: MouseButton::Left,
                            ..
                        } => show_main_window(tray.app_handle()),
                        _ => {}
                    })
                    .build(app)?;
                start_tray_microphone_watcher(app.handle().clone());
            } else {
                log::warn!("[startup] default window icon missing; tray icon disabled");
            }

            // Spin up hotkey listener; coordinator owns the lifecycle.
            let app_handle = app.handle().clone();
            coordinator.bind_app(app_handle);
            coordinator.start_hotkey_listener();
            // QA / custom combo hotkeys use `global-hotkey` (Carbon on macOS).
            // Start those after RunEvent::Ready, when the AppKit event loop is live.
            if std::env::var("OPENLESS_SHOW_MAIN_ON_START").ok().as_deref() == Some("1") {
                show_main_window(app.handle());
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::get_settings,
            commands::set_settings,
            commands::get_update_channel,
            commands::set_update_channel,
            commands::fetch_latest_beta_release,
            autostart::get_autostart_status,
            autostart::set_autostart_enabled,
            commands::get_hotkey_status,
            commands::get_hotkey_capability,
            commands::set_shortcut_recording_active,
            commands::get_windows_ime_status,
            commands::list_microphone_devices,
            commands::start_microphone_level_monitor,
            commands::stop_microphone_level_monitor,
            commands::get_credentials,
            commands::set_credential,
            commands::list_history,
            commands::get_usage_stats,
            commands::delete_history_entry,
            commands::clear_history,
            commands::clear_local_cache,
            commands::clear_provider_configuration,
            commands::delete_qingyu_asr_model,
            commands::list_vocab,
            commands::clear_vocab,
            commands::add_vocab,
            commands::remove_vocab,
            commands::set_vocab_enabled,
            commands::list_correction_rules,
            commands::add_correction_rule,
            commands::remove_correction_rule,
            commands::set_correction_rule_enabled,
            commands::list_vocab_presets,
            commands::save_vocab_presets,
            commands::start_dictation,
            commands::stop_dictation,
            commands::cancel_dictation,
            commands::handle_window_hotkey_event,
            #[cfg(debug_assertions)]
            commands::inject_hotkey_click_for_dev,
            commands::repolish,
            commands::set_default_polish_mode,
            commands::set_style_enabled,
            commands::check_accessibility_permission,
            commands::request_accessibility_permission,
            commands::check_microphone_permission,
            commands::request_microphone_permission,
            commands::open_system_settings,
            commands::trigger_microphone_prompt,
            commands::read_credential,
            commands::set_active_asr_provider,
            commands::set_active_llm_provider,
            commands::get_qa_hotkey_label,
            commands::set_qa_hotkey,
            commands::validate_shortcut_binding,
            commands::set_dictation_hotkey,
            commands::set_translation_hotkey,
            commands::set_switch_style_hotkey,
            commands::set_open_app_hotkey,
            commands::qa_window_dismiss,
            commands::qa_window_pin,
            commands::validate_combo_hotkey,
            commands::set_combo_hotkey,
            commands::validate_provider_credentials,
            commands::list_provider_models,
            commands::qingyu_asr_status,
            commands::qingyu_asr_manifest,
            commands::qingyu_asr_download,
            commands::qingyu_asr_repair,
            commands::local_asr_get_settings,
            commands::local_asr_set_active_model,
            commands::local_asr_set_mirror,
            commands::local_asr_list_models,
            commands::local_asr_fetch_remote_info,
            commands::local_asr_download_model,
            commands::local_asr_cancel_download,
            commands::local_asr_delete_model,
            commands::local_asr_test_model,
            commands::local_asr_engine_status,
            commands::local_asr_release_engine,
            commands::local_asr_preload,
            commands::local_asr_set_keep_loaded_secs,
            commands::foundry_local_asr_status,
            commands::foundry_local_asr_catalog,
            commands::foundry_local_asr_set_model,
            commands::foundry_local_asr_set_language_hint,
            commands::foundry_local_asr_set_runtime_source,
            commands::foundry_local_asr_prepare,
            commands::foundry_local_asr_cancel_prepare,
            commands::foundry_local_asr_release,
            commands::export_error_log,
            commands::export_diagnostic_bundle,
            restart_app,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| match event {
            RunEvent::Ready => {
                let coordinator = app.state::<Arc<coordinator::Coordinator>>();
                // 同步启动 QA hotkey listener。和 dictation hotkey 平行，互不抢状态。
                if crate::product::SHOW_SELECTION_ASK {
                    coordinator.start_qa_hotkey_listener();
                }
                // 启动自定义组合键监听器。当 trigger == Custom 时替代 modifier-only 监听器。
                coordinator.start_combo_hotkey_listener();
                if crate::product::SHOW_TRANSLATION {
                    coordinator.start_translation_hotkey_listener();
                }
                coordinator.start_switch_style_hotkey_listener();
                coordinator.start_open_app_hotkey_listener();
            }
            #[cfg(target_os = "macos")]
            RunEvent::Reopen { .. } => show_main_window(app),
            RunEvent::WindowEvent { label, event, .. } => {
                if label == "main" {
                    if let tauri::WindowEvent::CloseRequested { ref api, .. } = event {
                        api.prevent_close();
                        hide_main_window(app);
                    }
                    #[cfg(target_os = "windows")]
                    if matches!(
                        event,
                        tauri::WindowEvent::Resized(_)
                            | tauri::WindowEvent::ScaleFactorChanged { .. }
                    ) {
                        if let Some(main) = app.get_webview_window("main") {
                            apply_windows_rounded_frame(&main);
                        }
                    }
                }
            }
            RunEvent::Exit => {
                TRAY_MICROPHONE_WATCHER_STOPPING.store(true, Ordering::Relaxed);
                let coordinator = app.state::<Arc<coordinator::Coordinator>>();
                coordinator.stop_hotkey_listener();
                coordinator.stop_qa_hotkey_listener();
                coordinator.stop_combo_hotkey_listener();
                coordinator.stop_translation_hotkey_listener();
                coordinator.stop_switch_style_hotkey_listener();
                coordinator.stop_open_app_hotkey_listener();
            }
            _ => {}
        });
}

struct MicrophoneTrayMenu {
    submenu: Submenu<tauri::Wry>,
    items: Vec<commands::TrayMicrophoneMenuItem>,
}

struct StyleTrayMenu {
    submenu: Submenu<tauri::Wry>,
}

struct TrayMenu {
    menu: Menu<tauri::Wry>,
    microphone_items: Vec<commands::TrayMicrophoneMenuItem>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct TrayPolishModeMenuEntry {
    id: String,
    label: &'static str,
    mode: PolishMode,
    checked: bool,
}

fn tray_style_menu_enabled() -> bool {
    cfg!(target_os = "windows")
}

fn tray_polish_mode_menu_entries(selected: PolishMode) -> Vec<TrayPolishModeMenuEntry> {
    [
        (PolishMode::Raw, "style-raw"),
        (PolishMode::Light, "style-light"),
        (PolishMode::Structured, "style-structured"),
        (PolishMode::Formal, "style-formal"),
    ]
    .into_iter()
    .map(|(mode, id)| TrayPolishModeMenuEntry {
        id: id.to_string(),
        label: mode.display_name(),
        mode,
        checked: mode == selected,
    })
    .collect()
}

fn parse_tray_polish_mode_id(id: &str) -> Option<PolishMode> {
    match id {
        "style-raw" => Some(PolishMode::Raw),
        "style-light" => Some(PolishMode::Light),
        "style-structured" => Some(PolishMode::Structured),
        "style-formal" => Some(PolishMode::Formal),
        _ => None,
    }
}

fn build_tray_menu<M: Manager<tauri::Wry>>(
    app: &M,
    coordinator: &Arc<coordinator::Coordinator>,
) -> tauri::Result<TrayMenu> {
    let toggle = MenuItemBuilder::with_id("toggle", "显示主窗口").build(app)?;
    let microphone_menu = build_microphone_tray_menu(app, coordinator)?;
    let quit =
        MenuItemBuilder::with_id("quit", format!("退出 {}", crate::product::PRODUCT_NAME_ZH))
            .build(app)?;
    let mut builder = MenuBuilder::new(app);
    let style_menu = if tray_style_menu_enabled() {
        Some(build_style_tray_menu(app, coordinator)?)
    } else {
        None
    };
    if let Some(style_menu) = &style_menu {
        builder = builder.item(&style_menu.submenu);
    }
    let menu = builder
        .items(&[&toggle, &microphone_menu.submenu, &quit])
        .build()?;
    Ok(TrayMenu {
        menu,
        microphone_items: microphone_menu.items,
    })
}

fn build_style_tray_menu<M: Manager<tauri::Wry>>(
    app: &M,
    coordinator: &Arc<coordinator::Coordinator>,
) -> tauri::Result<StyleTrayMenu> {
    let selected = coordinator.prefs().get().default_mode;
    let mut submenu = SubmenuBuilder::with_id(app, "style", "输出风格");
    for entry in tray_polish_mode_menu_entries(selected) {
        let item = CheckMenuItemBuilder::with_id(&entry.id, entry.label)
            .checked(entry.checked)
            .build(app)?;
        submenu = submenu.item(&item);
    }
    Ok(StyleTrayMenu {
        submenu: submenu.build()?,
    })
}

fn build_microphone_tray_menu<M: Manager<tauri::Wry>>(
    app: &M,
    coordinator: &Arc<coordinator::Coordinator>,
) -> tauri::Result<MicrophoneTrayMenu> {
    let selected = coordinator.prefs().get().microphone_device_name;
    let mut items = Vec::new();
    let mut submenu = SubmenuBuilder::with_id(app, "microphone", "选择麦克风");
    let devices = match recorder::list_input_devices() {
        Ok(devices) => devices,
        Err(err) => {
            log::warn!("[tray] list microphone devices failed: {err}");
            Vec::new()
        }
    };
    let selected_available =
        selected.trim().is_empty() || devices.iter().any(|device| device.name == selected);

    let default_item = CheckMenuItemBuilder::with_id("mic-default", "系统默认麦克风")
        .checked(selected.trim().is_empty() || !selected_available)
        .build(app)?;
    submenu = submenu.item(&default_item);
    items.push(commands::TrayMicrophoneMenuItem {
        id: "mic-default".to_string(),
        device_name: String::new(),
        item: default_item,
    });

    if devices.is_empty() {
        let empty = MenuItemBuilder::with_id("mic-empty", "未发现麦克风")
            .enabled(false)
            .build(app)?;
        submenu = submenu.item(&empty);
    } else {
        for (index, device) in devices.into_iter().enumerate() {
            let id = format!("mic-device-{index}");
            let label = if device.is_default {
                format!("{}（系统默认）", device.name)
            } else {
                device.name.clone()
            };
            let item = CheckMenuItemBuilder::with_id(&id, label)
                .checked(selected == device.name)
                .build(app)?;
            submenu = submenu.item(&item);
            items.push(commands::TrayMicrophoneMenuItem {
                id,
                device_name: device.name,
                item,
            });
        }
    }

    Ok(MicrophoneTrayMenu {
        submenu: submenu.build()?,
        items,
    })
}

pub(crate) fn refresh_tray_microphone_menu(app: &AppHandle) -> tauri::Result<()> {
    let coordinator = app.state::<Arc<coordinator::Coordinator>>();
    let tray_menu = build_tray_menu(app, &coordinator)?;
    if let Some(tray) = app.tray_by_id("main-tray") {
        tray.set_menu(Some(tray_menu.menu))?;
    }
    let state = app.state::<commands::TrayMicrophoneMenuState>();
    *state.lock() = tray_menu.microphone_items;
    Ok(())
}

fn microphone_device_signature() -> Option<Vec<(String, bool)>> {
    match recorder::list_input_devices() {
        Ok(devices) => Some(
            devices
                .into_iter()
                .map(|device| (device.name, device.is_default))
                .collect(),
        ),
        Err(err) => {
            log::warn!("[tray] watch microphone devices failed: {err}");
            None
        }
    }
}

fn start_tray_microphone_watcher(app: AppHandle) {
    TRAY_MICROPHONE_WATCHER_STOPPING.store(false, Ordering::Relaxed);
    if let Err(err) = std::thread::Builder::new()
        .name("openless-tray-mic-watch".into())
        .spawn(move || {
            let mut last_signature = microphone_device_signature();
            while !TRAY_MICROPHONE_WATCHER_STOPPING.load(Ordering::Relaxed) {
                std::thread::sleep(Duration::from_millis(1500));
                if TRAY_MICROPHONE_WATCHER_STOPPING.load(Ordering::Relaxed) {
                    break;
                }
                let signature = microphone_device_signature();
                if signature == last_signature {
                    continue;
                }
                last_signature = signature;
                let app = app.clone();
                let refresh_app = app.clone();
                let _ = app.run_on_main_thread(move || {
                    if let Err(err) = refresh_tray_microphone_menu(&refresh_app) {
                        log::warn!(
                            "[tray] refresh microphone menu after device change failed: {err}"
                        );
                    }
                    let _ = refresh_app.emit("microphone:devices-changed", serde_json::json!({}));
                });
            }
        })
    {
        log::warn!("[tray] start microphone watcher failed: {err}");
    }
}

fn handle_microphone_tray_menu_event(app: &AppHandle, id: &str) {
    let tray_items = app.state::<commands::TrayMicrophoneMenuState>();
    let items = tray_items.lock();
    let Some(selected) = items.iter().find(|item| item.id == id) else {
        return;
    };

    let coord = app.state::<Arc<coordinator::Coordinator>>();
    let mut prefs = coord.prefs().get();
    prefs.microphone_device_name = selected.device_name.clone();
    if let Err(err) = coord.prefs().set(prefs.clone()) {
        log::warn!("[tray] save microphone preference failed: {err}");
        return;
    }
    let _ = app.emit("prefs:changed", &prefs);

    commands::sync_tray_microphone_selection(&items, &selected.device_name);
}

fn handle_style_tray_menu_event(app: &AppHandle, id: &str) -> bool {
    let Some(mode) = parse_tray_polish_mode_id(id) else {
        return false;
    };
    let coord = app.state::<Arc<coordinator::Coordinator>>();
    let mut prefs = coord.prefs().get();
    prefs.default_mode = mode;
    if let Err(err) = coord.prefs().set(prefs.clone()) {
        log::warn!("[tray] save polish mode preference failed: {err}");
        return true;
    }
    let _ = app.emit("prefs:changed", &prefs);
    let _ = app.emit_to("main", "prefs:changed", &prefs);
    if let Err(err) = refresh_tray_microphone_menu(app) {
        log::warn!("[tray] refresh style menu after polish mode change failed: {err}");
    }
    true
}

#[cfg(target_os = "windows")]
fn apply_windows_rounded_frame<R: Runtime>(window: &tauri::WebviewWindow<R>) {
    use raw_window_handle::{HasWindowHandle, RawWindowHandle};
    use windows::Win32::Foundation::{BOOL, HWND, RECT};
    use windows::Win32::Graphics::Dwm::{
        DwmSetWindowAttribute, DWMWA_BORDER_COLOR, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND,
    };
    use windows::Win32::Graphics::Gdi::{CreateRoundRectRgn, SetWindowRgn, HRGN};
    use windows::Win32::UI::WindowsAndMessaging::{
        GetWindowLongW, GetWindowRect, SetWindowLongW, SetWindowPos, GWL_STYLE, SWP_FRAMECHANGED,
        SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, WS_CAPTION, WS_THICKFRAME,
    };

    let handle = match window.window_handle().map(|h| h.as_raw()) {
        Ok(RawWindowHandle::Win32(handle)) => handle,
        Ok(other) => {
            log::warn!("[main] unexpected raw window handle for DWM frame: {other:?}");
            return;
        }
        Err(e) => {
            log::warn!("[main] read raw window handle failed: {e}");
            return;
        }
    };
    let hwnd = HWND(handle.hwnd.get() as *mut core::ffi::c_void);

    unsafe {
        let style = GetWindowLongW(hwnd, GWL_STYLE);
        let desired_style = (style | WS_THICKFRAME.0 as i32) & !(WS_CAPTION.0 as i32);
        if style != desired_style {
            SetWindowLongW(hwnd, GWL_STYLE, desired_style);
            if let Err(e) = SetWindowPos(
                hwnd,
                HWND::default(),
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            ) {
                log::warn!("[main] refresh native frame after style update failed: {e}");
            }
        }

        if window.is_maximized().unwrap_or(false) {
            let _ = SetWindowRgn(hwnd, HRGN::default(), BOOL(1));
            return;
        }

        let corner_preference = DWMWCP_ROUND;
        if let Err(e) = DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            &corner_preference as *const _ as *const core::ffi::c_void,
            std::mem::size_of_val(&corner_preference) as u32,
        ) {
            log::warn!("[main] set DWM rounded corners failed: {e}");
        }

        // Remove DWM's fallback 1px light border; the React shell draws the visual stroke.
        let border_color_none: u32 = 0xFFFFFFFE;
        if let Err(e) = DwmSetWindowAttribute(
            hwnd,
            DWMWA_BORDER_COLOR,
            &border_color_none as *const _ as *const core::ffi::c_void,
            std::mem::size_of_val(&border_color_none) as u32,
        ) {
            log::warn!("[main] remove DWM border color failed: {e}");
        }

        let mut rect = RECT::default();
        if let Err(e) = GetWindowRect(hwnd, &mut rect) {
            log::warn!("[main] read window rect for rounded region failed: {e}");
            return;
        }
        let width = rect.right - rect.left;
        let height = rect.bottom - rect.top;
        if width <= 0 || height <= 0 {
            return;
        }
        let region = CreateRoundRectRgn(0, 0, width + 1, height + 1, 18, 18);
        if region.is_invalid() {
            log::warn!("[main] create rounded window region failed");
            return;
        }
        if SetWindowRgn(hwnd, region, BOOL(1)) == 0 {
            log::warn!("[main] apply rounded window region failed");
        }
    }
}

#[tauri::command]
fn restart_app(app: AppHandle) {
    // macOS：自动更新会让新装的 .app 带 com.apple.quarantine（无论 Tauri updater
    // 怎么解包，下载流由 LaunchServices 接管，输出物可能仍带 xattr）。如果不
    // strip，重启后 Gatekeeper 会拦着说"OpenLess 已损坏 / 来自未识别开发者"，
    // 用户必须自己开终端跑 xattr -cr 才能继续用 — 违反了"自动更新对用户应该零摩擦"。
    //
    // 在 restart 前阻塞地清一次 xattr。失败容忍（PATH 异常、xattr 不存在、磁盘
    // 只读等边角情况），不让它阻塞重启本身。
    #[cfg(target_os = "macos")]
    if let Ok(exe) = std::env::current_exe() {
        if let Some(bundle) = exe
            .ancestors()
            .find(|p| p.extension().map(|e| e == "app").unwrap_or(false))
        {
            let _ = std::process::Command::new("/usr/bin/xattr")
                .arg("-cr")
                .arg(bundle)
                .status();
            log::info!("[updater] stripped xattr on {:?} before restart", bundle);
        }
    }
    app.restart();
}

/// 把日志同时写到 stderr + ~/Library/Logs/OpenLess/openless.log（match Swift `Log.swift`）。
fn init_file_logger() {
    use simplelog::{
        ColorChoice, CombinedLogger, ConfigBuilder, LevelFilter, TermLogger, TerminalMode,
        WriteLogger,
    };
    let log_dir = log_dir_path();
    let _ = std::fs::create_dir_all(&log_dir);
    let log_file = log_dir.join("openless.log");
    if let Err(e) = rotate_log_if_too_large(&log_file) {
        eprintln!("[logger] WARN 日志轮转失败: {e}");
    }
    let config = ConfigBuilder::new().set_time_format_rfc3339().build();
    let mut loggers: Vec<Box<dyn simplelog::SharedLogger>> = vec![TermLogger::new(
        LevelFilter::Info,
        config.clone(),
        TerminalMode::Mixed,
        ColorChoice::Auto,
    )];
    if let Ok(file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_file)
    {
        loggers.push(WriteLogger::new(LevelFilter::Info, config, file));
    }
    let _ = CombinedLogger::init(loggers);
}

fn rotate_log_if_too_large(path: &std::path::Path) -> std::io::Result<()> {
    let Ok(metadata) = std::fs::metadata(path) else {
        return Ok(());
    };
    if metadata.len() <= LOG_ROTATE_LIMIT_BYTES {
        return Ok(());
    }

    let archive = path.with_file_name("openless.log.1");
    match std::fs::remove_file(&archive) {
        Ok(()) => {}
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
        Err(e) => return Err(e),
    }
    std::fs::rename(path, archive)
}

pub fn log_dir_path() -> std::path::PathBuf {
    #[cfg(target_os = "macos")]
    {
        if let Ok(home) = std::env::var("HOME") {
            return std::path::PathBuf::from(home)
                .join("Library")
                .join("Logs")
                .join(crate::product::LOG_DIR_NAME);
        }
    }
    #[cfg(target_os = "windows")]
    {
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            return std::path::PathBuf::from(local)
                .join(crate::product::LOG_DIR_NAME)
                .join("Logs");
        }
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        if let Ok(home) = std::env::var("HOME") {
            return std::path::PathBuf::from(home)
                .join(".local")
                .join("share")
                .join(crate::product::LOG_DIR_NAME)
                .join("logs");
        }
    }
    std::env::temp_dir().join(crate::product::LOG_DIR_NAME)
}

pub(crate) fn show_main_window<R: Runtime>(app: &AppHandle<R>) {
    activate_window_mode(app);
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
    activate_app(app);
}

pub(crate) fn request_microphone_from_foreground<R: Runtime>(
    app: &AppHandle<R>,
) -> permissions::PermissionStatus {
    show_main_window(app);
    wait_for_app_activation(app);
    permissions::request_microphone()
}

fn hide_main_window<R: Runtime>(app: &AppHandle<R>) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.hide();
    }
    activate_menu_bar_mode(app);
}

#[cfg(target_os = "macos")]
fn activate_window_mode<R: Runtime>(app: &AppHandle<R>) {
    let _ = app.set_activation_policy(tauri::ActivationPolicy::Regular);
    let _ = app.set_dock_visibility(true);
    let _ = app.show();
}

#[cfg(not(target_os = "macos"))]
fn activate_window_mode<R: Runtime>(_app: &AppHandle<R>) {}

#[cfg(target_os = "macos")]
fn activate_menu_bar_mode<R: Runtime>(app: &AppHandle<R>) {
    let _ = app.set_activation_policy(tauri::ActivationPolicy::Accessory);
    let _ = app.set_dock_visibility(false);
}

#[cfg(not(target_os = "macos"))]
fn activate_menu_bar_mode<R: Runtime>(_app: &AppHandle<R>) {}

#[cfg(target_os = "macos")]
fn activate_app<R: Runtime>(app: &AppHandle<R>) {
    let _ = app.run_on_main_thread(|| {
        use objc2::msg_send;
        use objc2::runtime::{AnyClass, AnyObject, Bool};

        unsafe {
            let Some(cls) = AnyClass::get("NSApplication") else {
                return;
            };
            let ns_app: *mut AnyObject = msg_send![cls, sharedApplication];
            if !ns_app.is_null() {
                let _: () = msg_send![ns_app, activateIgnoringOtherApps: Bool::YES];
            }
        }
    });
}

#[cfg(not(target_os = "macos"))]
fn activate_app<R: Runtime>(_app: &AppHandle<R>) {}

/// 展示胶囊后调用：若 OpenLess 已是前台 app，用 makeKeyWindow 还原主窗口焦点。
/// 不调 NSApp.activate，不抢其他 app 焦点，符合 CLAUDE.md 约束。
#[cfg(target_os = "macos")]
pub(crate) fn restore_main_window_key_if_active<R: Runtime>(app: &AppHandle<R>) {
    let main = app.get_webview_window("main");
    let _ = app.run_on_main_thread(move || {
        use objc2::msg_send;
        use objc2::runtime::{AnyClass, AnyObject, Bool};
        unsafe {
            let Some(cls) = AnyClass::get("NSApplication") else {
                return;
            };
            let ns_app: *mut AnyObject = msg_send![cls, sharedApplication];
            if ns_app.is_null() {
                return;
            }
            let is_active: Bool = msg_send![ns_app, isActive];
            if !is_active.as_bool() {
                return;
            }
            let Some(main) = main else {
                return;
            };
            match main.ns_window() {
                Ok(handle) => {
                    let main_win = handle as *mut AnyObject;
                    if !main_win.is_null() {
                        let _: () = msg_send![main_win, makeKeyWindow];
                    }
                }
                Err(e) => log::warn!("[main] ns_window unavailable for key restore: {e}"),
            };
        }
    });
}

#[cfg(target_os = "macos")]
fn wait_for_app_activation<R: Runtime>(app: &AppHandle<R>) {
    let (tx, rx) = mpsc::channel();
    let _ = app.run_on_main_thread(move || {
        use objc2::msg_send;
        use objc2::runtime::{AnyClass, AnyObject, Bool};

        unsafe {
            let Some(cls) = AnyClass::get("NSApplication") else {
                let _ = tx.send(());
                return;
            };
            let ns_app: *mut AnyObject = msg_send![cls, sharedApplication];
            if !ns_app.is_null() {
                let _: () = msg_send![ns_app, activateIgnoringOtherApps: Bool::YES];
            }
        }
        let _ = tx.send(());
    });
    let _ = rx.recv_timeout(Duration::from_millis(800));
    std::thread::sleep(Duration::from_millis(150));
}

#[cfg(not(target_os = "macos"))]
fn wait_for_app_activation<R: Runtime>(_app: &AppHandle<R>) {}

/// QA 浮窗的目标尺寸（issue #118）。胶囊默认 220×96 + Dock 80pt + 8pt gap，
/// 算下来 QA 窗口顶部坐标 = h - 80 - 96 - 8 - 280。
const QA_WINDOW_WIDTH: f64 = 380.0;
const QA_WINDOW_HEIGHT: f64 = 440.0;
/// 胶囊与 QA 窗口的间距，与设计稿一致。
const QA_WINDOW_GAP_TO_CAPSULE: f64 = 8.0;
/// 给 macOS Dock 留的下边距（与 capsule 同源）。
const DOCK_BOTTOM_PADDING_FOR_QA: f64 = 80.0;

/// 把 QA 浮窗放到屏幕底部居中、紧贴胶囊上方。tauri 启动期 + show 之前都会调一次，
/// 防止用户切换显示器后位置错乱。
fn position_qa_window<R: tauri::Runtime>(window: &tauri::WebviewWindow<R>) -> tauri::Result<()> {
    let monitor = match window.current_monitor()? {
        Some(m) => m,
        None => return Ok(()),
    };
    let scale = monitor.scale_factor();
    let size = monitor.size();
    let logical_w = size.width as f64 / scale;
    let logical_h = size.height as f64 / scale;
    let capsule_height = capsule_height_for_qa();
    let x = ((logical_w - QA_WINDOW_WIDTH) / 2.0).max(0.0);
    let y = (logical_h
        - DOCK_BOTTOM_PADDING_FOR_QA
        - capsule_height
        - QA_WINDOW_GAP_TO_CAPSULE
        - QA_WINDOW_HEIGHT)
        .max(0.0);
    window.set_size(tauri::LogicalSize::new(QA_WINDOW_WIDTH, QA_WINDOW_HEIGHT))?;
    window.set_position(LogicalPosition::new(x, y))?;
    Ok(())
}

/// 显示 QA 窗口并发一条状态事件（前端订阅 `qa:state`）。
/// `content_kind` 是不透明字符串（"loading" / "answer" / "idle" 等），
/// 让前端 React 视图自行决定渲染哪一种。**不**抢前台 app 焦点（保证 Cmd+C
/// fallback 仍能从原 app 拿到选区）。
pub(crate) fn show_qa_window<R: tauri::Runtime>(app: &AppHandle<R>, content_kind: &str) {
    let Some(window) = app.get_webview_window("qa") else {
        log::info!("[qa] show 跳过：qa 窗口不存在 (content_kind={content_kind})");
        return;
    };
    // 仅首次 show 时居中；之后保留用户拖动后的位置。
    if !QA_WINDOW_POSITIONED.load(Ordering::Relaxed) {
        if let Err(e) = position_qa_window(&window) {
            log::warn!("[qa] position before first show failed: {e}");
        }
        QA_WINDOW_POSITIONED.store(true, Ordering::Relaxed);
    }
    // macOS：不用 window.show()（它会 makeKeyAndOrderFront 把 OpenLess 推成 frontmost，
    // 之后 capture_selection 的 AX read / Cmd+C fallback 都跑在 OpenLess 自己的 webview 上
    // → 抓不到原 app 选区）。改用 orderFrontRegardless 让窗口可见但**不**成为 key window，
    // frontmost 仍是用户原 app，AX 还能读到选区。这是 Spotlight / Raycast 的标准做法。
    //
    // ⚠️ 关键：NSWindow 任何操作必须在主线程，macOS 26 是硬断言（违反直接 SIGTRAP）。
    // show_qa_window 经常从 tokio worker 调（qa_hotkey_bridge_loop），所以裸 ObjC msg_send
    // 必须用 `app.run_on_main_thread` dispatch 到主线程。详见 issue #118 v2。
    #[cfg(target_os = "macos")]
    {
        let window_clone = window.clone();
        let _ = app.run_on_main_thread(move || {
            use objc2::msg_send;
            use objc2::runtime::AnyObject;
            match window_clone.ns_window() {
                Ok(handle) => {
                    let ns = handle as *mut AnyObject;
                    if ns.is_null() {
                        log::warn!("[qa] ns_window null; falling back to window.show()");
                        let _ = window_clone.show();
                    } else {
                        unsafe {
                            let _: () = msg_send![ns, orderFrontRegardless];
                        }
                    }
                }
                Err(e) => {
                    log::warn!("[qa] ns_window unavailable: {e}; falling back to window.show()");
                    let _ = window_clone.show();
                }
            }
        });
    }
    #[cfg(target_os = "windows")]
    if !show_qa_window_no_activate(&window) {
        log::warn!("[qa] show_no_activate failed; falling back to window.show()");
        if let Err(e) = window.show() {
            log::warn!("[qa] show fallback failed: {e}");
        }
    }
    #[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
    if let Err(e) = window.show() {
        log::warn!("[qa] show failed: {e}");
    }
    let _ = app.emit_to(
        "qa",
        "qa:state",
        serde_json::json!({ "kind": content_kind }),
    );
}

/// QA 浮窗的拖动修复（macOS）。
///
/// 配置 `focus: false` 让 Tauri 把窗口创建为 nonactivating panel 风格（避免抢前台 app
/// 焦点）。代价是 AppKit 的 `performWindowDragWithEvent:` 在 nonactivating 窗口上无效，
/// 所以 `data-tauri-drag-region` 和 `WebviewWindow::start_dragging()` 都拖不动。
///
/// 解法是把 NSWindow 的 `movableByWindowBackground` 打开——这条路径不依赖窗口是否成为
/// key window，跟 Spotlight / Raycast 的浮窗是同一手法。设一次就够，整个生命周期保持。
#[cfg(target_os = "macos")]
fn make_qa_window_draggable_macos<R: tauri::Runtime>(window: &tauri::WebviewWindow<R>) {
    use objc2::msg_send;
    use objc2::runtime::{AnyObject, Bool};
    let Ok(handle) = window.ns_window() else {
        log::warn!("[qa] ns_window unavailable; drag fix skipped");
        return;
    };
    let ns_window = handle as *mut AnyObject;
    if ns_window.is_null() {
        log::warn!("[qa] ns_window null; drag fix skipped");
        return;
    }
    unsafe {
        let _: () = msg_send![ns_window, setMovableByWindowBackground: Bool::YES];
        let _: () = msg_send![ns_window, setMovable: Bool::YES];
    }
    log::info!("[qa] NSWindow movableByWindowBackground=YES");
}

/// 隐藏 QA 窗口。供 commands::qa_window_dismiss / coordinator session 收尾共用。
pub(crate) fn hide_qa_window<R: tauri::Runtime>(app: &AppHandle<R>) {
    if let Some(window) = app.get_webview_window("qa") {
        let _ = window.hide();
    }
}

#[cfg(target_os = "windows")]
fn show_qa_window_no_activate<R: tauri::Runtime>(window: &tauri::WebviewWindow<R>) -> bool {
    use raw_window_handle::{HasWindowHandle, RawWindowHandle};
    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{ShowWindow, SW_SHOWNOACTIVATE};

    let Ok(handle) = window.window_handle() else {
        return false;
    };
    let RawWindowHandle::Win32(raw) = handle.as_raw() else {
        return false;
    };
    let hwnd = HWND(raw.hwnd.get() as *mut _);
    if hwnd.0.is_null() {
        return false;
    }

    let _ = unsafe { ShowWindow(hwnd, SW_SHOWNOACTIVATE) };
    true
}

/// 把 capsule 窗口移到屏幕底部居中，与 Swift `CapsuleWindowController.repositionToBottomCenter` 同效。
/// 留 80pt 给 macOS Dock；Windows 任务栏一般在底部 48pt 以内，整体也合适。
pub(crate) fn position_capsule_bottom_center<R: tauri::Runtime>(
    window: &tauri::WebviewWindow<R>,
    translation_active: bool,
) -> tauri::Result<()> {
    let monitor = match window.current_monitor()? {
        Some(m) => m,
        None => return Ok(()),
    };
    let bounds = capsule_window_bounds(translation_active);
    window.set_size(LogicalSize::new(bounds.width, bounds.height))?;

    let scale = monitor.scale_factor();
    let size = monitor.size();
    let logical_w = size.width as f64 / scale;
    let logical_h = size.height as f64 / scale;
    let x = ((logical_w - bounds.width) / 2.0).max(0.0);
    let y = (logical_h - capsule_visual_height(translation_active) - 80.0 - bounds.bottom_inset)
        .max(0.0);
    window.set_position(LogicalPosition::new(x, y))?;
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq)]
struct CapsuleWindowBounds {
    width: f64,
    height: f64,
    bottom_inset: f64,
}

fn capsule_window_bounds(translation_active: bool) -> CapsuleWindowBounds {
    #[cfg(target_os = "windows")]
    {
        const WINDOWS_CAPSULE_PILL_WIDTH: f64 = 196.0;
        const WINDOWS_CAPSULE_SIDE_INSET: f64 = 12.0;
        CapsuleWindowBounds {
            // Keep the existing Windows hitbox width, but express it as
            // pill width (196) + symmetric 12px side insets for shadow room.
            width: WINDOWS_CAPSULE_PILL_WIDTH + WINDOWS_CAPSULE_SIDE_INSET * 2.0,
            height: if translation_active { 118.0 } else { 84.0 },
            bottom_inset: 12.0,
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        // macOS / Linux：固定 220×110，与 1.2.11 行为一致 — 录音 / 翻译徽章
        // 共用同一个窗口尺寸，避免按 Shift 后窗口高度变化导致胶囊整体下移。
        let _ = translation_active;
        CapsuleWindowBounds {
            width: 220.0,
            height: 110.0,
            bottom_inset: 0.0,
        }
    }
}

fn capsule_visual_height(_translation_active: bool) -> f64 {
    #[cfg(target_os = "windows")]
    {
        52.0
    }

    #[cfg(not(target_os = "windows"))]
    {
        96.0
    }
}

fn capsule_height_for_qa() -> f64 {
    capsule_visual_height(false)
}

#[cfg(test)]
mod tests {
    use super::{
        capsule_height_for_qa, capsule_visual_height, capsule_window_bounds,
        parse_tray_polish_mode_id, rotate_log_if_too_large, tray_polish_mode_menu_entries,
        tray_style_menu_enabled, LOG_ROTATE_LIMIT_BYTES,
    };
    use crate::types::PolishMode;
    use std::io::Write;

    #[test]
    fn tray_style_menu_is_windows_only() {
        #[cfg(target_os = "windows")]
        assert!(tray_style_menu_enabled());

        #[cfg(not(target_os = "windows"))]
        assert!(!tray_style_menu_enabled());
    }

    #[test]
    fn tray_style_menu_lists_builtin_modes_in_expected_order() {
        let entries = tray_polish_mode_menu_entries(PolishMode::Structured);

        assert_eq!(
            entries
                .iter()
                .map(|entry| (entry.id.as_str(), entry.label, entry.mode, entry.checked))
                .collect::<Vec<_>>(),
            vec![
                ("style-raw", "原文", PolishMode::Raw, false),
                ("style-light", "轻度润色", PolishMode::Light, false),
                ("style-structured", "清晰结构", PolishMode::Structured, true),
                ("style-formal", "正式表达", PolishMode::Formal, false),
            ]
        );
    }

    #[test]
    fn tray_style_menu_id_parsing_accepts_only_style_items() {
        assert_eq!(
            parse_tray_polish_mode_id("style-raw"),
            Some(PolishMode::Raw)
        );
        assert_eq!(
            parse_tray_polish_mode_id("style-light"),
            Some(PolishMode::Light)
        );
        assert_eq!(
            parse_tray_polish_mode_id("style-structured"),
            Some(PolishMode::Structured)
        );
        assert_eq!(
            parse_tray_polish_mode_id("style-formal"),
            Some(PolishMode::Formal)
        );
        assert_eq!(parse_tray_polish_mode_id("toggle"), None);
        assert_eq!(parse_tray_polish_mode_id("mic-default"), None);
    }

    #[test]
    fn capsule_window_bounds_leave_room_for_windows_shadow() {
        let bounds = capsule_window_bounds(false);
        #[cfg(target_os = "windows")]
        assert_eq!(
            (bounds.width, bounds.height, bounds.bottom_inset),
            (220.0, 84.0, 12.0)
        );

        #[cfg(not(target_os = "windows"))]
        assert_eq!(
            (bounds.width, bounds.height, bounds.bottom_inset),
            (220.0, 110.0, 0.0)
        );
    }

    #[test]
    fn capsule_window_bounds_expand_for_translation_badge() {
        let bounds = capsule_window_bounds(true);
        #[cfg(target_os = "windows")]
        assert_eq!(
            (bounds.width, bounds.height, bounds.bottom_inset),
            (220.0, 118.0, 12.0)
        );

        #[cfg(not(target_os = "windows"))]
        assert_eq!(
            (bounds.width, bounds.height, bounds.bottom_inset),
            (220.0, 110.0, 0.0)
        );
    }

    #[test]
    fn capsule_visual_height_matches_frontend_pill() {
        #[cfg(target_os = "windows")]
        assert_eq!(capsule_visual_height(true), 52.0);

        #[cfg(not(target_os = "windows"))]
        assert_eq!(capsule_visual_height(true), 96.0);
    }

    #[test]
    fn qa_anchor_uses_normal_capsule_height_source() {
        #[cfg(target_os = "windows")]
        assert_eq!(capsule_height_for_qa(), 52.0);

        #[cfg(not(target_os = "windows"))]
        assert_eq!(capsule_height_for_qa(), 96.0);
    }

    #[test]
    fn oversized_log_rotates_to_single_archive() {
        let dir = std::env::temp_dir().join(format!("openless-log-rotate-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let log = dir.join("openless.log");
        let archive = dir.join("openless.log.1");

        {
            let mut file = std::fs::File::create(&log).unwrap();
            file.set_len(LOG_ROTATE_LIMIT_BYTES + 1).unwrap();
            file.write_all(b"x").unwrap();
        }
        std::fs::write(&archive, b"old").unwrap();

        rotate_log_if_too_large(&log).unwrap();

        assert!(!log.exists());
        assert!(archive.exists());
        assert!(std::fs::metadata(&archive).unwrap().len() > LOG_ROTATE_LIMIT_BYTES);

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn small_log_does_not_rotate() {
        let dir = std::env::temp_dir().join(format!("openless-log-small-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let log = dir.join("openless.log");
        let archive = dir.join("openless.log.1");
        std::fs::write(&log, b"small").unwrap();

        rotate_log_if_too_large(&log).unwrap();

        assert!(log.exists());
        assert!(!archive.exists());
        assert_eq!(std::fs::read(&log).unwrap(), b"small");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn missing_log_does_not_rotate() {
        let dir = std::env::temp_dir().join(format!("openless-log-missing-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let log = dir.join("openless.log");
        let archive = dir.join("openless.log.1");

        rotate_log_if_too_large(&log).unwrap();

        assert!(!log.exists());
        assert!(!archive.exists());

        let _ = std::fs::remove_dir_all(&dir);
    }
}
