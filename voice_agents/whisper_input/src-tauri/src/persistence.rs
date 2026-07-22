//! Local persistence: history JSON, user preferences JSON, vocab JSON, and
//! platform-backed credentials vault.
//!
//! Storage roots:
//! - macOS:   `~/Library/Application Support/Qingyu Input`
//! - Windows: `%APPDATA%\Qingyu Input`
//! - Linux:   `$XDG_DATA_HOME/Qingyu Input` or `~/.local/share/Qingyu Input`
//!
//! Credential storage policy: provider credentials are stored in the OS
//! credential vault (macOS Keychain, Windows Credential Manager, Linux keyring).
//! A legacy plaintext JSON file is read once as a migration source and removed
//! after a successful vault write; new writes never persist plaintext secrets.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use anyhow::{anyhow, Context, Result};
use chrono::Utc;
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::types::{
    CorrectionRule, DictationSession, DictionaryEntry, UsageStats, UserPreferences,
    VocabPresetStore,
};

const HISTORY_CAP: usize = 200;
const HISTORY_FILE: &str = "history.json";
const USAGE_STATS_FILE: &str = "usage-stats.json";
const PREFERENCES_FILE: &str = "preferences.json";
/// 与 Swift `Sources/OpenLessPersistence/DictionaryStore.swift` 同名，
/// 让旧版词汇表在升级后无缝继承。**不要**改成 `vocab.json`，会丢用户数据。
const VOCAB_FILE: &str = "dictionary.json";
const CORRECTION_RULES_FILE: &str = "correction-rules.json";
const CORRECTION_NUM_TOKEN: &str = "{num}";
const VOCAB_PRESETS_FILE: &str = "vocab-presets.json";

/// 旧版 plaintext JSON 凭据路径。仅作为迁移来源；成功写入系统凭据库后会删除。
const LEGACY_CREDS_DIR: &str = ".openless";
const LEGACY_CREDS_FILE: &str = "credentials.json";

const KEYRING_CREDENTIALS_ACCOUNT: &str = "credentials.v1";
const KEYRING_CREDENTIALS_CHUNK_PREFIX: &str = "credentials.v1.chunk.";
const KEYRING_STABLE_GENERATION_A: &str = "stable-a";
const KEYRING_STABLE_GENERATION_B: &str = "stable-b";
// Credential payloads are normally only a handful of chunks. This fixed upper
// bound cleans stale chunks left in the inactive stable slot by a previous
// failed manifest write, without probing Keychain indefinitely.
const KEYRING_STALE_CHUNK_CLEANUP_LIMIT: usize = 64;
const LEGACY_ASR_PROVIDER_ID: &str = "volcengine";
// Windows Credential Manager caps one credential blob at 2560 bytes. keyring stores
// passwords as UTF-16 on Windows, so keep each JSON chunk comfortably below that.
const KEYRING_CHUNK_MAX_UTF16_UNITS: usize = 1000;

static CREDENTIALS_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

fn credentials_lock() -> &'static Mutex<()> {
    CREDENTIALS_LOCK.get_or_init(|| Mutex::new(()))
}

/// Process-wide credentials cache.
///
/// Without this cache every `CredentialsVault::get_*` / `snapshot` call hits
/// `load_credentials()` → `load_keyring_credentials()` which reads the
/// manifest entry plus every chunk entry from the OS keyring. On macOS each
/// distinct keychain entry has its own ACL — so an ad-hoc-signed binary (or
/// any binary whose ACL grants haven't been set up yet) prompts on every read
/// of every entry. A single dictation cycle reads credentials 5–10 times,
/// times (1 manifest + N chunks) entries → tens of "OpenLess wants to use
/// the keychain" prompts per recording.
///
/// With this cache the first read populates `Some(CredsRoot)` and every
/// subsequent read in the same process is silent. `save_credentials` keeps
/// the cache in sync after writes so Settings → Recording credential edits
/// take effect immediately.
///
/// Cross-process changes (e.g. user edits via `security` CLI, or another
/// instance of the app — single-instance is enforced but defense in depth)
/// will be invisible until the next process launch. Acceptable trade-off
/// per the credential vault contract: the keyring is owned by this app.
static CREDENTIALS_CACHE: OnceLock<Mutex<Option<CredsRoot>>> = OnceLock::new();

fn credentials_cache() -> &'static Mutex<Option<CredsRoot>> {
    CREDENTIALS_CACHE.get_or_init(|| Mutex::new(None))
}

fn store_credentials_cache(root: &CredsRoot) {
    *credentials_cache().lock() = Some(sanitize_credentials(root));
}

#[cfg(test)]
fn reset_credentials_cache_for_tests() {
    *credentials_cache().lock() = None;
}

// ───────────────────────── path helpers ─────────────────────────

fn data_dir() -> Result<PathBuf> {
    #[cfg(target_os = "macos")]
    {
        let home = std::env::var("HOME").context("HOME not set")?;
        Ok(PathBuf::from(home)
            .join("Library")
            .join("Application Support")
            .join(crate::product::DATA_DIR_NAME))
    }

    #[cfg(target_os = "windows")]
    {
        let appdata = std::env::var("APPDATA").context("APPDATA not set")?;
        Ok(PathBuf::from(appdata).join(crate::product::DATA_DIR_NAME))
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
            if !xdg.is_empty() {
                return Ok(PathBuf::from(xdg).join(crate::product::DATA_DIR_NAME));
            }
        }
        let home = std::env::var("HOME").context("HOME not set")?;
        Ok(PathBuf::from(home)
            .join(".local")
            .join("share")
            .join(crate::product::DATA_DIR_NAME))
    }
}

pub fn app_data_dir() -> Result<PathBuf> {
    data_dir()
}

fn legacy_data_dir() -> Result<PathBuf> {
    #[cfg(target_os = "windows")]
    {
        let appdata = std::env::var("APPDATA").context("APPDATA not set")?;
        return Ok(PathBuf::from(appdata).join(crate::product::LEGACY_DATA_DIR_NAME));
    }
    #[cfg(target_os = "macos")]
    {
        let home = std::env::var("HOME").context("HOME not set")?;
        return Ok(PathBuf::from(home)
            .join("Library")
            .join("Application Support")
            .join(crate::product::LEGACY_DATA_DIR_NAME));
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
            if !xdg.is_empty() {
                return Ok(PathBuf::from(xdg).join(crate::product::LEGACY_DATA_DIR_NAME));
            }
        }
        let home = std::env::var("HOME").context("HOME not set")?;
        Ok(PathBuf::from(home)
            .join(".local")
            .join("share")
            .join(crate::product::LEGACY_DATA_DIR_NAME))
    }
}

fn ensure_dir(dir: &Path) -> Result<()> {
    fs::create_dir_all(dir).with_context(|| format!("create dir failed: {}", dir.display()))?;
    Ok(())
}

fn migrate_low_risk_openless_data(target_dir: &Path) {
    let Ok(source_dir) = legacy_data_dir() else {
        return;
    };
    if source_dir == target_dir || !source_dir.exists() {
        return;
    }
    for file_name in [VOCAB_FILE, VOCAB_PRESETS_FILE, CORRECTION_RULES_FILE] {
        let source = source_dir.join(file_name);
        let target = target_dir.join(file_name);
        if target.exists() || !source.exists() {
            continue;
        }
        if let Err(error) = fs::copy(&source, &target) {
            log::warn!(
                "[migration] copy low-risk data {} -> {} failed: {error}",
                source.display(),
                target.display()
            );
        }
    }
}

/// 本地 ASR 模型根目录：`<data_dir>/models/qwen3-asr/`。
/// 子目录 = 模型 id（如 `qwen3-asr-0.6b`），存 antirez `download_model.sh`
/// 列出的 5–7 个文件。
pub fn local_models_root() -> Result<PathBuf> {
    let dir = data_dir()?.join("models").join("qwen3-asr");
    ensure_dir(&dir)?;
    Ok(dir)
}

/// Foundry Local 下载与缓存根目录。DLL 和模型都不打进安装包，和 Qwen3-ASR
/// 一样放在 OpenLess 的 models 目录下，卸载清理用户数据时可以一起删除。
#[cfg(target_os = "windows")]
pub fn foundry_local_root() -> Result<PathBuf> {
    let dir = data_dir()?.join("models").join("foundry-local");
    ensure_dir(&dir)?;
    Ok(dir)
}

#[cfg(target_os = "windows")]
pub fn foundry_native_runtime_root() -> Result<PathBuf> {
    let dir = foundry_local_root()?.join("runtime");
    ensure_dir(&dir)?;
    Ok(dir)
}

#[cfg(target_os = "windows")]
pub fn foundry_model_cache_root() -> Result<PathBuf> {
    let dir = foundry_local_root()?;
    ensure_dir(&dir)?;
    Ok(dir)
}

#[cfg(target_os = "windows")]
pub fn foundry_app_data_root() -> Result<PathBuf> {
    let dir = foundry_local_root()?.join("app-data");
    ensure_dir(&dir)?;
    Ok(dir)
}

#[cfg(target_os = "windows")]
pub fn foundry_logs_root() -> Result<PathBuf> {
    let dir = foundry_local_root()?.join("logs");
    ensure_dir(&dir)?;
    Ok(dir)
}

/// Atomic write: write to `*.tmp` first, then rename onto the target path.
fn atomic_write(path: &Path, contents: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        ensure_dir(parent)?;
    }
    let tmp_path = path.with_extension("tmp");
    fs::write(&tmp_path, contents)
        .with_context(|| format!("write tmp failed: {}", tmp_path.display()))?;
    fs::rename(&tmp_path, path).with_context(|| format!("rename failed: {}", path.display()))?;
    Ok(())
}

fn read_or_default<T: for<'de> Deserialize<'de> + Default>(path: &Path) -> Result<T> {
    if !path.exists() {
        return Ok(T::default());
    }
    let bytes = fs::read(path).with_context(|| format!("read failed: {}", path.display()))?;
    if bytes.is_empty() {
        return Ok(T::default());
    }
    serde_json::from_slice::<T>(&bytes)
        .with_context(|| format!("decode failed: {}", path.display()))
}

// ───────────────────────── credentials vault ─────────────────────────
//
// 正常读写走系统凭据库；旧 plaintext JSON 只作为迁移来源。为保持多 provider
// schema 与 active provider 状态，凭据库里保存一个 v2 JSON payload；payload 会按平台
// 凭据库限制拆成多个条目，避免 Windows 单条凭据 2560 bytes 限制。
//
// v2 schema：
//   {
//     "version": 2,
//     "active": { "asr": "<id>", "llm": "<id>" },
//     "providers": {
//       "asr": { "<id>": { "appKey", "accessKey", "resourceId", "apiKey", "baseURL", "model", "vocabularyId" } },
//       "llm": { "<id>": { "displayName", "apiKey", "baseURL", "model", "temperature", "extraHeaders" } }
//     }
//   }
//
// "ark.api_key"/"volcengine.app_key" 等账户名按 Swift 语义路由到 active provider。

use std::collections::HashMap;

#[derive(Debug, Serialize, Deserialize, Clone)]
#[allow(non_snake_case)]
struct CredsRoot {
    #[serde(default = "credsroot_default_version")]
    version: u32,
    #[serde(default)]
    active: CredsActive,
    #[serde(default)]
    providers: CredsProviders,
}

const CREDS_SCHEMA_VERSION: u32 = 2;

impl Default for CredsRoot {
    fn default() -> Self {
        Self {
            version: CREDS_SCHEMA_VERSION,
            active: CredsActive::default(),
            providers: CredsProviders::default(),
        }
    }
}

fn credsroot_default_version() -> u32 {
    CREDS_SCHEMA_VERSION
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct CredsActive {
    #[serde(default = "creds_default_asr")]
    asr: String,
    #[serde(default = "creds_default_llm")]
    llm: String,
}

impl Default for CredsActive {
    fn default() -> Self {
        Self {
            asr: creds_default_asr(),
            llm: creds_default_llm(),
        }
    }
}

fn creds_default_asr() -> String {
    crate::product::DEFAULT_ASR_PROVIDER_ID.into()
}
fn creds_default_llm() -> String {
    crate::product::DEFAULT_LLM_PROVIDER_ID.into()
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
struct CredsProviders {
    #[serde(default)]
    asr: HashMap<String, CredsAsrEntry>,
    #[serde(default)]
    llm: HashMap<String, CredsLlmEntry>,
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
#[allow(non_snake_case)]
struct CredsAsrEntry {
    #[serde(skip_serializing_if = "Option::is_none")]
    apiKey: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    baseURL: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    appKey: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    accessKey: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    resourceId: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    vocabularyId: Option<String>,
}

impl CredsAsrEntry {
    fn is_empty(&self) -> bool {
        self.apiKey.as_deref().unwrap_or("").is_empty()
            && self.baseURL.as_deref().unwrap_or("").is_empty()
            && self.model.as_deref().unwrap_or("").is_empty()
            && self.appKey.as_deref().unwrap_or("").is_empty()
            && self.accessKey.as_deref().unwrap_or("").is_empty()
            && self.resourceId.as_deref().unwrap_or("").is_empty()
            && self.vocabularyId.as_deref().unwrap_or("").is_empty()
    }
}

#[derive(Debug, Serialize, Deserialize, Default, Clone)]
#[allow(non_snake_case)]
struct CredsLlmEntry {
    #[serde(skip_serializing_if = "Option::is_none")]
    displayName: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    apiKey: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    baseURL: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    extraHeaders: Option<HashMap<String, String>>,
}

impl CredsLlmEntry {
    fn is_empty(&self) -> bool {
        self.displayName.as_deref().unwrap_or("").is_empty()
            && self.apiKey.as_deref().unwrap_or("").is_empty()
            && self.baseURL.as_deref().unwrap_or("").is_empty()
            && self.model.as_deref().unwrap_or("").is_empty()
            && self.temperature.is_none()
            && self
                .extraHeaders
                .as_ref()
                .map(|h| h.is_empty())
                .unwrap_or(true)
    }
}

fn credentials_path() -> Result<PathBuf> {
    // macOS / Linux: ~/.openless/credentials.json (与 Swift 同源)
    // Windows: %APPDATA%\OpenLess\credentials.json (Windows 没有标准 HOME 环境变量)
    #[cfg(target_os = "windows")]
    {
        let appdata = std::env::var("APPDATA").context("APPDATA not set")?;
        return Ok(PathBuf::from(appdata)
            .join("OpenLess")
            .join(LEGACY_CREDS_FILE));
    }
    #[cfg(not(target_os = "windows"))]
    {
        let home = std::env::var("HOME").context("HOME not set")?;
        Ok(PathBuf::from(home)
            .join(LEGACY_CREDS_DIR)
            .join(LEGACY_CREDS_FILE))
    }
}

fn keyring_entry() -> Result<keyring::Entry> {
    keyring_entry_for(KEYRING_CREDENTIALS_ACCOUNT)
}

fn keyring_entry_for(account: &str) -> Result<keyring::Entry> {
    keyring_entry_for_service(CredentialsVault::SERVICE_NAME, account)
}

fn keyring_entry_for_service(service: &str, account: &str) -> Result<keyring::Entry> {
    keyring::Entry::new(service, account).context("open system credential vault")
}

fn clean_credentials(root: &CredsRoot) -> CredsRoot {
    let mut cleaned = sanitize_credentials(root);
    cleaned.providers.asr.retain(|_, v| !v.is_empty());
    cleaned.providers.llm.retain(|_, v| !v.is_empty());
    cleaned
}

fn reset_provider_configuration_root(root: &CredsRoot) -> CredsRoot {
    CredsRoot {
        version: root.version,
        active: CredsActive::default(),
        providers: CredsProviders::default(),
    }
}

fn normalize_active_asr_provider(provider: &str) -> String {
    crate::product::normalize_active_asr_provider_id(provider)
}

fn normalize_active_llm_provider(provider: &str) -> String {
    crate::product::normalize_active_llm_provider_id(provider)
}

fn string_field_is_empty(value: &Option<String>) -> bool {
    value
        .as_ref()
        .map(|value| value.trim().is_empty())
        .unwrap_or(true)
}

fn asr_entry_has_substantive_config(entry: &CredsAsrEntry) -> bool {
    !string_field_is_empty(&entry.apiKey)
        || !string_field_is_empty(&entry.baseURL)
        || !string_field_is_empty(&entry.model)
        || !string_field_is_empty(&entry.appKey)
        || !string_field_is_empty(&entry.accessKey)
        || !string_field_is_empty(&entry.resourceId)
        || !string_field_is_empty(&entry.vocabularyId)
}

fn llm_entry_has_substantive_config(entry: &CredsLlmEntry) -> bool {
    !string_field_is_empty(&entry.apiKey)
        || !string_field_is_empty(&entry.baseURL)
        || !string_field_is_empty(&entry.model)
        || entry.temperature.is_some()
        || entry
            .extraHeaders
            .as_ref()
            .map(|headers| !headers.is_empty())
            .unwrap_or(false)
}

fn copy_missing_string_field(target: &mut Option<String>, source: &Option<String>) {
    if string_field_is_empty(target) && !string_field_is_empty(source) {
        *target = source.clone();
    }
}

fn merge_missing_asr_fields(target: &mut CredsAsrEntry, source: &CredsAsrEntry) {
    copy_missing_string_field(&mut target.apiKey, &source.apiKey);
    copy_missing_string_field(&mut target.baseURL, &source.baseURL);
    copy_missing_string_field(&mut target.model, &source.model);
    copy_missing_string_field(&mut target.appKey, &source.appKey);
    copy_missing_string_field(&mut target.accessKey, &source.accessKey);
    copy_missing_string_field(&mut target.resourceId, &source.resourceId);
    copy_missing_string_field(&mut target.vocabularyId, &source.vocabularyId);
}

fn migrate_active_legacy_asr_bucket(
    providers: &mut HashMap<String, CredsAsrEntry>,
    old_active: &str,
    normalized_active: &str,
) {
    if normalized_active != crate::product::DOUBAO_ASR_PROVIDER_ID
        || old_active == normalized_active
    {
        return;
    }
    let Some(source) = providers.get(old_active).cloned() else {
        return;
    };
    if !asr_entry_has_substantive_config(&source) {
        return;
    }
    let target = providers
        .entry(crate::product::DOUBAO_ASR_PROVIDER_ID.into())
        .or_default();
    merge_missing_asr_fields(target, &source);
}

fn llm_entry_endpoint_is_local(entry: &CredsLlmEntry) -> bool {
    let Some(base_url) = entry.baseURL.as_deref() else {
        return false;
    };
    let Ok(url) = reqwest::Url::parse(base_url.trim()) else {
        return false;
    };
    let Some(host) = url.host_str() else {
        return false;
    };
    host.eq_ignore_ascii_case("localhost") || host == "127.0.0.1"
}

fn llm_entry_is_complete(entry: &CredsLlmEntry) -> bool {
    !string_field_is_empty(&entry.baseURL)
        && !string_field_is_empty(&entry.model)
        && (!string_field_is_empty(&entry.apiKey) || llm_entry_endpoint_is_local(entry))
}

fn should_replace_openai_compatible_llm_bucket(target: Option<&CredsLlmEntry>) -> bool {
    target
        .map(|entry| !llm_entry_is_complete(entry))
        .unwrap_or(true)
}

fn migrate_active_legacy_llm_bucket(
    providers: &mut HashMap<String, CredsLlmEntry>,
    old_active: &str,
    normalized_active: &str,
) {
    if normalized_active != crate::product::OPENAI_COMPATIBLE_PROVIDER_ID
        || old_active == normalized_active
    {
        return;
    }
    let Some(source) = providers.get(old_active).cloned() else {
        return;
    };
    if !llm_entry_has_substantive_config(&source) {
        return;
    }
    if should_replace_openai_compatible_llm_bucket(
        providers.get(crate::product::OPENAI_COMPATIBLE_PROVIDER_ID),
    ) {
        providers.insert(crate::product::OPENAI_COMPATIBLE_PROVIDER_ID.into(), source);
    }
}

fn normalize_qwen_llm_model_selection(providers: &mut HashMap<String, CredsLlmEntry>) {
    let Some(entry) = providers.get_mut(crate::product::QWEN_LLM_PROVIDER_ID) else {
        return;
    };
    if entry.model.as_deref().map(str::trim) == Some("qwen3.6-plus") {
        entry.model = Some(crate::polish::QWEN_LLM_DEFAULT_MODEL.into());
    }
}

fn sanitize_credentials(root: &CredsRoot) -> CredsRoot {
    let mut sanitized = root.clone();
    sanitized.version = CREDS_SCHEMA_VERSION;
    let old_asr = sanitized.active.asr.clone();
    let normalized_asr = normalize_active_asr_provider(&old_asr);
    migrate_active_legacy_asr_bucket(&mut sanitized.providers.asr, &old_asr, &normalized_asr);
    sanitized.active.asr = normalized_asr;
    let old_llm = sanitized.active.llm.clone();
    let normalized_llm = normalize_active_llm_provider(&old_llm);
    migrate_active_legacy_llm_bucket(&mut sanitized.providers.llm, &old_llm, &normalized_llm);
    normalize_qwen_llm_model_selection(&mut sanitized.providers.llm);
    sanitized.active.llm = normalized_llm;
    sanitized
}

fn read_legacy_credentials_file(path: &Path) -> Option<CredsRoot> {
    if !path.exists() {
        return None;
    }
    let bytes = match fs::read(path) {
        Ok(b) => b,
        Err(e) => {
            log::warn!("[vault] read legacy {} failed: {}", path.display(), e);
            return None;
        }
    };
    match serde_json::from_slice::<CredsRoot>(&bytes) {
        Ok(root) => Some(root),
        Err(e) => {
            log::warn!("[vault] parse legacy {} failed: {}", path.display(), e);
            None
        }
    }
}

fn remove_legacy_credentials_file() -> Result<()> {
    let Ok(path) = credentials_path() else {
        return Ok(());
    };
    if path.exists() {
        fs::remove_file(&path)
            .with_context(|| format!("remove legacy credentials file {}", path.display()))?;
    }
    Ok(())
}

fn remove_legacy_credentials_file_best_effort() {
    if let Err(e) = remove_legacy_credentials_file() {
        log::warn!("[vault] remove legacy credentials file failed: {e}");
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct CredsChunkManifest {
    openless_credentials_storage: String,
    version: u32,
    /// v1 早期每次 save 都生成新 UUID 作为 chunk account 命名前缀，
    /// 这让 macOS Keychain 的「始终允许」每次保存后失效 → 反复弹 ACL 弹窗。
    /// 现在 save 在 `stable-a` / `stable-b` 两个固定 generation 间切换：
    /// 先写 inactive slot 的 chunks，再提交 manifest，避免 manifest 写失败时覆盖
    /// active chunks；固定双槽也避免随机 UUID 造成无限 Keychain ACL 名称。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    generation: Option<String>,
    chunks: usize,
}

/// 旧版（generation=None）：`credentials.v1.chunk.{index}`
/// 新版（generation=stable-a/stable-b）：`credentials.v1.chunk.<generation>.{index}`
/// 固定双槽名让 ACL 长期有效，同时保证 save 不覆盖当前 manifest 指向的 active slot。
fn chunk_account(generation: Option<&str>, index: usize) -> String {
    match generation {
        Some(gen) => format!("{KEYRING_CREDENTIALS_CHUNK_PREFIX}{gen}.{index}"),
        None => format!("{KEYRING_CREDENTIALS_CHUNK_PREFIX}{index}"),
    }
}

fn next_stable_chunk_generation(previous: Option<&str>) -> String {
    match previous {
        Some(KEYRING_STABLE_GENERATION_A) => KEYRING_STABLE_GENERATION_B.into(),
        Some(KEYRING_STABLE_GENERATION_B) => KEYRING_STABLE_GENERATION_A.into(),
        _ => KEYRING_STABLE_GENERATION_A.into(),
    }
}

fn chunk_accounts_to_cleanup_after_save(
    previous: Option<&CredsChunkManifest>,
    target_generation: &str,
    new_chunks: usize,
) -> Vec<String> {
    let mut accounts = Vec::new();
    if let Some(previous) = previous {
        for index in 0..previous.chunks {
            accounts.push(chunk_account(previous.generation.as_deref(), index));
        }
        for index in new_chunks..previous.chunks {
            accounts.push(chunk_account(Some(target_generation), index));
        }
    }
    accounts
}

fn stale_target_chunk_accounts_to_cleanup(
    target_generation: &str,
    new_chunks: usize,
) -> Vec<String> {
    (new_chunks..KEYRING_STALE_CHUNK_CLEANUP_LIMIT)
        .map(|index| chunk_account(Some(target_generation), index))
        .collect()
}

fn chunk_json_payload(json: &str) -> Vec<String> {
    let mut chunks = Vec::new();
    let mut current = String::new();
    let mut current_units = 0usize;
    for ch in json.chars() {
        let units = ch.len_utf16();
        if !current.is_empty() && current_units + units > KEYRING_CHUNK_MAX_UTF16_UNITS {
            chunks.push(std::mem::take(&mut current));
            current_units = 0;
        }
        current.push(ch);
        current_units += units;
    }
    if !current.is_empty() || json.is_empty() {
        chunks.push(current);
    }
    chunks
}

fn read_chunk_manifest(json: &str) -> Option<CredsChunkManifest> {
    let manifest = serde_json::from_str::<CredsChunkManifest>(json).ok()?;
    if manifest.openless_credentials_storage == "chunked" && manifest.version == 1 {
        Some(manifest)
    } else {
        None
    }
}

fn previous_manifest_from_value(
    value: Result<Option<String>>,
) -> Result<Option<CredsChunkManifest>> {
    match value? {
        Some(json) => read_chunk_manifest(&json)
            .map(Some)
            .ok_or_else(|| anyhow!("invalid system credential vault manifest")),
        None => Ok(None),
    }
}

fn get_keyring_password(account: &str) -> Result<Option<String>> {
    get_keyring_password_for_service(CredentialsVault::SERVICE_NAME, account)
}

fn get_keyring_password_for_service(service: &str, account: &str) -> Result<Option<String>> {
    match keyring_entry_for_service(service, account)?.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(anyhow!(e))
            .with_context(|| format!("read system credential vault {service}/{account}")),
    }
}

fn delete_keyring_password(account: &str) {
    delete_keyring_password_for_service(CredentialsVault::SERVICE_NAME, account);
}

fn delete_keyring_password_for_service(service: &str, account: &str) {
    match keyring_entry_for_service(service, account).and_then(|entry| {
        entry
            .delete_credential()
            .with_context(|| format!("delete system credential vault {service}/{account}"))
    }) {
        Ok(()) | Err(_) => {}
    }
}

fn load_keyring_credentials() -> Result<Option<CredsRoot>> {
    load_keyring_credentials_for_service(CredentialsVault::SERVICE_NAME)
}

fn load_keyring_credentials_for_service(service: &str) -> Result<Option<CredsRoot>> {
    let Some(json_or_manifest) =
        get_keyring_password_for_service(service, KEYRING_CREDENTIALS_ACCOUNT)?
    else {
        return Ok(None);
    };

    let manifest = read_chunk_manifest(&json_or_manifest)
        .ok_or_else(|| anyhow!("invalid system credential vault manifest"))?;
    let mut json = String::new();
    for index in 0..manifest.chunks {
        let account = chunk_account(manifest.generation.as_deref(), index);
        let chunk = get_keyring_password_for_service(service, &account)?
            .ok_or_else(|| anyhow!("missing system credential vault chunk {index}"))?;
        json.push_str(&chunk);
    }

    serde_json::from_str::<CredsRoot>(&json)
        .map(|root| Some(sanitize_credentials(&root)))
        .context("decode system credential vault payload")
}

fn load_legacy_keyring_credentials() -> CredsRoot {
    match load_legacy_keyring_credentials_for_update() {
        Ok(root) => root,
        Err(e) => {
            log::warn!("[vault] read legacy vault credentials failed: {e}");
            CredsRoot::default()
        }
    }
}

fn load_legacy_keyring_credentials_for_update() -> Result<CredsRoot> {
    if let Some(root) =
        load_keyring_credentials_for_service(crate::product::LEGACY_KEYRING_SERVICE_NAME)?
    {
        return Ok(clean_credentials(&root));
    }

    let mut root = CredsRoot::default();
    root.active.asr = LEGACY_ASR_PROVIDER_ID.into();
    for account in CredentialAccount::all() {
        let legacy_account = account.keyring_account();
        match get_keyring_password_for_service(
            crate::product::LEGACY_KEYRING_SERVICE_NAME,
            legacy_account,
        ) {
            Ok(Some(value)) => write_account(&mut root, *account, Some(value)),
            Ok(None) => {}
            Err(e) => return Err(e.context(format!("read legacy vault {legacy_account}"))),
        }
    }
    Ok(clean_credentials(&root))
}

fn remove_legacy_keyring_credentials() {
    if let Ok(Some(json_or_manifest)) = get_keyring_password_for_service(
        crate::product::LEGACY_KEYRING_SERVICE_NAME,
        KEYRING_CREDENTIALS_ACCOUNT,
    ) {
        if let Some(manifest) = read_chunk_manifest(&json_or_manifest) {
            for index in 0..manifest.chunks {
                delete_keyring_password_for_service(
                    crate::product::LEGACY_KEYRING_SERVICE_NAME,
                    &chunk_account(manifest.generation.as_deref(), index),
                );
            }
        }
    }
    delete_keyring_password_for_service(
        crate::product::LEGACY_KEYRING_SERVICE_NAME,
        KEYRING_CREDENTIALS_ACCOUNT,
    );

    for account in CredentialAccount::all() {
        delete_keyring_password_for_service(
            crate::product::LEGACY_KEYRING_SERVICE_NAME,
            account.keyring_account(),
        );
    }
}

fn load_legacy_credentials() -> Option<CredsRoot> {
    credentials_path()
        .ok()
        .and_then(|p| read_legacy_credentials_file(&p))
        .map(|root| sanitize_credentials(&root))
}

fn legacy_vault_has_credentials(root: &CredsRoot) -> bool {
    !root.providers.asr.is_empty() || !root.providers.llm.is_empty()
}

fn load_legacy_sources_without_migration() -> CredsRoot {
    if let Some(legacy) = load_legacy_credentials() {
        return legacy;
    }

    let legacy_vault = load_legacy_keyring_credentials();
    if legacy_vault_has_credentials(&legacy_vault) {
        return legacy_vault;
    }

    CredsRoot::default()
}

fn migrate_legacy_sources() -> CredsRoot {
    match migrate_legacy_sources_for_update() {
        Ok(root) => root,
        Err(e) => {
            log::warn!("[vault] legacy credential migration failed: {e}");
            load_legacy_sources_without_migration()
        }
    }
}

fn migrate_legacy_sources_for_update() -> Result<CredsRoot> {
    if let Some(legacy) = load_legacy_credentials() {
        save_credentials(&legacy)?;
        remove_legacy_keyring_credentials();
        return Ok(legacy);
    }

    let legacy_vault = load_legacy_keyring_credentials_for_update()?;
    if legacy_vault_has_credentials(&legacy_vault) {
        save_credentials(&legacy_vault)?;
        remove_legacy_keyring_credentials();
        return Ok(legacy_vault);
    }

    Ok(CredsRoot::default())
}

fn load_credentials() -> CredsRoot {
    if let Some(cached) = credentials_cache().lock().as_ref().cloned() {
        return sanitize_credentials(&cached);
    }
    match load_keyring_credentials() {
        Ok(Some(root)) => {
            // 不在这里调 remove_legacy_keyring_credentials() —— 它内部对每个
            // 旧 account 各做一次 keyring delete，每次 delete 在 macOS Keychain
            // 上仍要触发 ACL 检查。第一次成功 load 时 legacy entries 通常已经
            // 被 migrate_legacy_sources_for_update 清理过了；这里若再无脑跑，
            // 只会反复弹「OpenLess 想删除 X」十几次。文件 legacy（plaintext
            // JSON）不需要 ACL，可继续 best-effort 删除。
            remove_legacy_credentials_file_best_effort();
            store_credentials_cache(&root);
            root
        }
        Ok(None) => {
            // 没有现成 chunked manifest —— 走 migrate（如果有 legacy 则写入并返回写后的 root）。
            // migrate_legacy_sources 内部 save_credentials 已经会刷 cache，这里再补一次
            // 是为了「无 legacy 也无 manifest」走默认 root 的路径也能进 cache。
            let root = migrate_legacy_sources();
            store_credentials_cache(&root);
            root
        }
        Err(e) => {
            // **不缓存 keyring 错误路径下的 fallback**。Keychain 可能只是临时不可读
            // （用户尚未在第一次弹窗里点同意 / DataProtection 错误 / login keychain
            // 还没 unlock）；如果在这里把 legacy fallback 写进 cache，等用户授权后
            // 我们就再也不会重读 keyring，整个进程生命周期里都拿 stale 数据。下次
            // 调用让它再尝试一次 keyring。pr_agent feedback on PR #394。
            log::warn!("[vault] system credential read failed: {e}");
            load_legacy_sources_without_migration()
        }
    }
}

fn load_credentials_for_update() -> Result<CredsRoot> {
    if let Some(cached) = credentials_cache().lock().as_ref().cloned() {
        return Ok(sanitize_credentials(&cached));
    }
    match load_keyring_credentials() {
        Ok(Some(root)) => {
            // 同 load_credentials：不再每次 update 都尝试 delete legacy keyring
            // entries，避免反复触发 macOS Keychain ACL 弹窗。
            remove_legacy_credentials_file_best_effort();
            store_credentials_cache(&root);
            Ok(root)
        }
        Ok(None) => {
            // migrate_legacy_sources_for_update 内部如果实际 migrate 会调
            // save_credentials，cache 会被刷新；如果只返回 default root（没 legacy），
            // 我们这里再显式 cache 一次防御性补一下。
            let root = migrate_legacy_sources_for_update()?;
            store_credentials_cache(&root);
            Ok(root)
        }
        // 错误路径不缓存 —— 同 load_credentials 注释；让下次读重试 keyring。
        Err(e) => Err(e),
    }
}

fn save_credentials(root: &CredsRoot) -> Result<()> {
    let cleaned = clean_credentials(root);
    let json = serde_json::to_string(&cleaned).context("encode credentials failed")?;
    let previous_manifest =
        previous_manifest_from_value(get_keyring_password(KEYRING_CREDENTIALS_ACCOUNT))?;
    let chunks = chunk_json_payload(&json);

    let target_generation = next_stable_chunk_generation(
        previous_manifest
            .as_ref()
            .and_then(|m| m.generation.as_deref()),
    );

    for account in stale_target_chunk_accounts_to_cleanup(&target_generation, chunks.len()) {
        delete_keyring_password(&account);
    }

    // 先写 inactive fixed slot 的所有 chunks，再写 manifest —— 保证 chunk 写失败
    // 或 manifest 写失败时，旧 manifest 仍指向旧 chunks，不会读到混合 payload。
    for (index, chunk) in chunks.iter().enumerate() {
        let account = chunk_account(Some(&target_generation), index);
        keyring_entry_for(&account)?
            .set_password(chunk)
            .with_context(|| format!("write system credential vault chunk {index}"))?;
    }

    let manifest = CredsChunkManifest {
        openless_credentials_storage: "chunked".to_string(),
        version: 1,
        generation: Some(target_generation.clone()),
        chunks: chunks.len(),
    };
    let manifest_json =
        serde_json::to_string(&manifest).context("encode credential manifest failed")?;
    keyring_entry()?
        .set_password(&manifest_json)
        .context("write system credential vault manifest")?;

    // Manifest 已提交后再 best-effort 清理旧 active slot 和 target slot 多余 chunks。
    for account in chunk_accounts_to_cleanup_after_save(
        previous_manifest.as_ref(),
        &target_generation,
        chunks.len(),
    ) {
        delete_keyring_password(&account);
    }

    remove_legacy_credentials_file_best_effort();
    // 写完成功后立刻刷新 process cache —— 同进程后续读不再回 Keychain。
    // 见 CREDENTIALS_CACHE 的 doc。
    store_credentials_cache(&cleaned);
    Ok(())
}

fn lookup_account(root: &CredsRoot, account: CredentialAccount) -> Option<String> {
    let asr = root.providers.asr.get(&root.active.asr);
    let llm = root.providers.llm.get(&root.active.llm);
    let pick = |s: &Option<String>| s.as_ref().filter(|v| !v.is_empty()).cloned();
    match account {
        CredentialAccount::VolcengineAppKey => {
            asr.and_then(|e| pick(&e.appKey).or_else(|| pick(&e.apiKey)))
        }
        CredentialAccount::VolcengineAccessKey => asr.and_then(|e| pick(&e.accessKey)),
        CredentialAccount::VolcengineResourceId => asr.and_then(|e| pick(&e.resourceId)),
        CredentialAccount::ArkApiKey => llm.and_then(|e| pick(&e.apiKey)),
        CredentialAccount::ArkModelId => llm.and_then(|e| pick(&e.model)),
        CredentialAccount::ArkEndpoint => llm.and_then(|e| pick(&e.baseURL)),
        CredentialAccount::AsrQwenApiKey => root
            .providers
            .asr
            .get(crate::product::QWEN_REALTIME_ASR_PROVIDER_ID)
            .and_then(|e| pick(&e.apiKey)),
        CredentialAccount::AsrDoubaoApiKey => root
            .providers
            .asr
            .get(crate::product::DOUBAO_ASR_PROVIDER_ID)
            .and_then(|e| pick(&e.apiKey)),
        CredentialAccount::LlmQwenApiKey => root
            .providers
            .llm
            .get(crate::product::QWEN_LLM_PROVIDER_ID)
            .and_then(|e| pick(&e.apiKey)),
        CredentialAccount::LlmGeminiApiKey => root
            .providers
            .llm
            .get(crate::product::GEMINI_PROVIDER_ID)
            .and_then(|e| pick(&e.apiKey)),
        CredentialAccount::AsrApiKey => asr.and_then(|e| pick(&e.apiKey)),
        CredentialAccount::AsrEndpoint => asr.and_then(|e| pick(&e.baseURL)),
        CredentialAccount::AsrModel => asr.and_then(|e| pick(&e.model)),
        CredentialAccount::AsrVocabularyId => asr.and_then(|e| pick(&e.vocabularyId)),
    }
}

fn write_account(root: &mut CredsRoot, account: CredentialAccount, value: Option<String>) {
    let asr_id = root.active.asr.clone();
    let llm_id = root.active.llm.clone();
    let normalized = value.and_then(|v| if v.is_empty() { None } else { Some(v) });
    match account {
        CredentialAccount::VolcengineAppKey => {
            let entry = root.providers.asr.entry(asr_id).or_default();
            entry.appKey = normalized;
        }
        CredentialAccount::VolcengineAccessKey => {
            let entry = root.providers.asr.entry(asr_id).or_default();
            entry.accessKey = normalized;
        }
        CredentialAccount::VolcengineResourceId => {
            let entry = root.providers.asr.entry(asr_id).or_default();
            entry.resourceId = normalized;
        }
        CredentialAccount::ArkApiKey => {
            let entry = root.providers.llm.entry(llm_id).or_default();
            entry.apiKey = normalized;
        }
        CredentialAccount::ArkModelId => {
            let entry = root.providers.llm.entry(llm_id).or_default();
            entry.model = normalized;
        }
        CredentialAccount::ArkEndpoint => {
            let entry = root.providers.llm.entry(llm_id).or_default();
            entry.baseURL = normalized;
        }
        CredentialAccount::AsrQwenApiKey => {
            let entry = root
                .providers
                .asr
                .entry(crate::product::QWEN_REALTIME_ASR_PROVIDER_ID.into())
                .or_default();
            entry.apiKey = normalized;
        }
        CredentialAccount::AsrDoubaoApiKey => {
            let entry = root
                .providers
                .asr
                .entry(crate::product::DOUBAO_ASR_PROVIDER_ID.into())
                .or_default();
            entry.apiKey = normalized;
        }
        CredentialAccount::LlmQwenApiKey => {
            let entry = root
                .providers
                .llm
                .entry(crate::product::QWEN_LLM_PROVIDER_ID.into())
                .or_default();
            entry.apiKey = normalized;
        }
        CredentialAccount::LlmGeminiApiKey => {
            let entry = root
                .providers
                .llm
                .entry(crate::product::GEMINI_PROVIDER_ID.into())
                .or_default();
            entry.apiKey = normalized;
        }
        CredentialAccount::AsrApiKey => {
            let entry = root.providers.asr.entry(asr_id).or_default();
            entry.apiKey = normalized;
        }
        CredentialAccount::AsrEndpoint => {
            let entry = root.providers.asr.entry(asr_id).or_default();
            entry.baseURL = normalized;
        }
        CredentialAccount::AsrModel => {
            let entry = root.providers.asr.entry(asr_id).or_default();
            entry.model = normalized;
        }
        CredentialAccount::AsrVocabularyId => {
            let entry = root.providers.asr.entry(asr_id).or_default();
            entry.vocabularyId = normalized;
        }
    }
}

// ───────────────────────── HistoryStore ─────────────────────────

pub struct HistoryStore {
    path: PathBuf,
    stats_path: PathBuf,
    lock: Mutex<()>,
}

impl HistoryStore {
    pub fn new() -> Result<Self> {
        let dir = data_dir()?;
        ensure_dir(&dir)?;
        Ok(Self {
            path: dir.join(HISTORY_FILE),
            stats_path: dir.join(USAGE_STATS_FILE),
            lock: Mutex::new(()),
        })
    }

    #[cfg(test)]
    pub(crate) fn with_dir_for_tests(dir: PathBuf) -> Self {
        Self {
            path: dir.join(HISTORY_FILE),
            stats_path: dir.join(USAGE_STATS_FILE),
            lock: Mutex::new(()),
        }
    }

    pub fn list(&self) -> Result<Vec<DictationSession>> {
        let _guard = self.lock.lock();
        self.read_locked()
    }

    pub fn usage_stats(&self) -> Result<UsageStats> {
        let _guard = self.lock.lock();
        self.read_or_migrate_usage_stats_locked()
    }

    pub fn append(&self, session: DictationSession) -> Result<()> {
        self.append_with_retention(session, 0)
    }

    /// `retention_days == 0` 跟旧 append 行为一致（不按时间清理）。
    /// `> 0` 时在写入新条目后顺手把超过 N 天的会话裁掉，写入时就完成清理，
    /// 不需要后台轮询。最后再受 200 条硬上限约束（HISTORY_CAP）。
    pub fn append_with_retention(
        &self,
        session: DictationSession,
        retention_days: u32,
    ) -> Result<()> {
        let _guard = self.lock.lock();
        let mut sessions = self.read_locked()?;
        let mut stats = self.read_or_migrate_usage_stats_from_sessions_locked(&sessions)?;
        stats.total_chars = stats
            .total_chars
            .saturating_add(session.final_text.encode_utf16().count() as u64);
        stats.total_duration_ms = stats
            .total_duration_ms
            .saturating_add(session.duration_ms.unwrap_or(0));
        stats.total_segments = stats.total_segments.saturating_add(1);
        // Prepend so the newest session is at index 0, matching the Swift impl.
        sessions.insert(0, session);
        if retention_days > 0 {
            let cutoff = chrono::Utc::now() - chrono::Duration::days(i64::from(retention_days));
            sessions.retain(|s| {
                chrono::DateTime::parse_from_rfc3339(&s.created_at)
                    .map(|t| t.with_timezone(&chrono::Utc) >= cutoff)
                    // 解析失败时保守保留——避免错误的时间戳让用户丢历史。
                    .unwrap_or(true)
            });
        }
        if sessions.len() > HISTORY_CAP {
            sessions.truncate(HISTORY_CAP);
        }
        self.write_usage_stats_locked(&stats)?;
        self.write_locked(&sessions)
    }

    /// 返回最近 N 分钟内的会话（newest-first）。`minutes == 0` → 空 Vec，
    /// 调用方据此跳过对话感知 polish 路径。
    pub fn recent_within_minutes(&self, minutes: u32) -> Result<Vec<DictationSession>> {
        if minutes == 0 {
            return Ok(Vec::new());
        }
        let _guard = self.lock.lock();
        let sessions = self.read_locked()?;
        let cutoff = chrono::Utc::now() - chrono::Duration::minutes(i64::from(minutes));
        // sessions 是 newest-first，超出窗口的会话之后的都更老，take_while 即可。
        let filtered: Vec<DictationSession> = sessions
            .into_iter()
            .take_while(|s| {
                chrono::DateTime::parse_from_rfc3339(&s.created_at)
                    .map(|t| t.with_timezone(&chrono::Utc) >= cutoff)
                    .unwrap_or(false)
            })
            .collect();
        Ok(filtered)
    }

    pub fn delete(&self, id: &str) -> Result<()> {
        let _guard = self.lock.lock();
        let mut sessions = self.read_locked()?;
        let original_len = sessions.len();
        sessions.retain(|s| s.id != id);
        if sessions.len() == original_len {
            return Ok(());
        }
        self.write_locked(&sessions)
    }

    pub fn clear(&self) -> Result<()> {
        let _guard = self.lock.lock();
        self.write_usage_stats_locked(&UsageStats::default())?;
        self.write_locked(&Vec::<DictationSession>::new())
    }

    fn read_locked(&self) -> Result<Vec<DictationSession>> {
        read_or_default::<Vec<DictationSession>>(&self.path)
    }

    fn write_locked(&self, sessions: &[DictationSession]) -> Result<()> {
        let json = serde_json::to_vec_pretty(sessions).context("encode history failed")?;
        atomic_write(&self.path, &json)
    }

    fn read_or_migrate_usage_stats_locked(&self) -> Result<UsageStats> {
        let sessions = self.read_locked()?;
        self.read_or_migrate_usage_stats_from_sessions_locked(&sessions)
    }

    fn read_or_migrate_usage_stats_from_sessions_locked(
        &self,
        sessions: &[DictationSession],
    ) -> Result<UsageStats> {
        if self.stats_path.exists() {
            return read_or_default::<UsageStats>(&self.stats_path);
        }
        let stats = usage_stats_from_sessions(sessions);
        self.write_usage_stats_locked(&stats)?;
        Ok(stats)
    }

    fn write_usage_stats_locked(&self, stats: &UsageStats) -> Result<()> {
        let json = serde_json::to_vec_pretty(stats).context("encode usage stats failed")?;
        atomic_write(&self.stats_path, &json)
    }
}

fn usage_stats_from_sessions(sessions: &[DictationSession]) -> UsageStats {
    sessions
        .iter()
        .fold(UsageStats::default(), |mut stats, session| {
            stats.total_chars = stats
                .total_chars
                .saturating_add(session.final_text.encode_utf16().count() as u64);
            stats.total_duration_ms = stats
                .total_duration_ms
                .saturating_add(session.duration_ms.unwrap_or(0));
            stats.total_segments = stats.total_segments.saturating_add(1);
            stats
        })
}

// ───────────────────────── PreferencesStore ─────────────────────────

pub struct PreferencesStore {
    path: PathBuf,
    state: Mutex<UserPreferences>,
}

impl PreferencesStore {
    pub fn new() -> Result<Self> {
        let dir = data_dir()?;
        ensure_dir(&dir)?;
        migrate_low_risk_openless_data(&dir);
        let path = dir.join(PREFERENCES_FILE);
        let prefs = if path.exists() {
            read_or_default::<UserPreferences>(&path).unwrap_or_else(|e| {
                log::warn!(
                    "[prefs] load {} failed, using defaults: {}",
                    path.display(),
                    e
                );
                UserPreferences::default()
            })
        } else {
            UserPreferences::default()
        }
        .sanitize_product_visibility();
        Ok(Self {
            path,
            state: Mutex::new(prefs),
        })
    }

    pub fn get(&self) -> UserPreferences {
        self.state.lock().clone()
    }

    pub fn set(&self, prefs: UserPreferences) -> Result<()> {
        let prefs = prefs.sanitize_product_visibility();
        let json = serde_json::to_vec_pretty(&prefs).context("encode prefs failed")?;
        atomic_write(&self.path, &json)?;
        let mut guard = self.state.lock();
        *guard = prefs;
        Ok(())
    }
}

// ───────────────────────── DictionaryStore ─────────────────────────

pub struct DictionaryStore {
    path: PathBuf,
    lock: Mutex<()>,
}

impl DictionaryStore {
    pub fn new() -> Result<Self> {
        let dir = data_dir()?;
        ensure_dir(&dir)?;
        Ok(Self {
            path: dir.join(VOCAB_FILE),
            lock: Mutex::new(()),
        })
    }

    #[cfg(test)]
    fn new_for_path(path: PathBuf) -> Self {
        Self {
            path,
            lock: Mutex::new(()),
        }
    }

    pub fn list(&self) -> Result<Vec<DictionaryEntry>> {
        let _guard = self.lock.lock();
        self.read_locked()
    }

    pub fn add(&self, phrase: String, note: Option<String>) -> Result<DictionaryEntry> {
        let _guard = self.lock.lock();
        let mut entries = self.read_locked()?;
        let entry = DictionaryEntry {
            id: Uuid::new_v4().to_string(),
            phrase,
            note,
            enabled: true,
            hits: 0,
            created_at: Utc::now().to_rfc3339(),
        };
        entries.insert(0, entry.clone());
        self.write_locked(&entries)?;
        Ok(entry)
    }

    pub fn remove(&self, id: &str) -> Result<()> {
        let _guard = self.lock.lock();
        let mut entries = self.read_locked()?;
        let before = entries.len();
        entries.retain(|e| e.id != id);
        if entries.len() == before {
            return Ok(());
        }
        self.write_locked(&entries)
    }

    pub fn set_enabled(&self, id: &str, enabled: bool) -> Result<()> {
        let _guard = self.lock.lock();
        let mut entries = self.read_locked()?;
        let mut found = false;
        for entry in entries.iter_mut() {
            if entry.id == id {
                entry.enabled = enabled;
                found = true;
                break;
            }
        }
        if !found {
            return Err(anyhow!("dictionary entry {} not found", id));
        }
        self.write_locked(&entries)
    }

    pub fn clear(&self) -> Result<()> {
        let _guard = self.lock.lock();
        self.write_locked(&[])
    }

    /// 扫描一段最终文本，对每个 enabled 词条按出现次数累加 `hits`。
    ///
    /// 匹配是大小写不敏感的子串扫描：「Hello hello HELLO」算 3 次。
    /// 返回本次累加的总命中数，方便调用方记录到 history.dictionary_entry_count。
    pub fn record_hits(&self, text: &str) -> Result<u64> {
        if text.is_empty() {
            return Ok(0);
        }
        let _guard = self.lock.lock();
        let mut entries = self.read_locked()?;
        if entries.is_empty() {
            return Ok(0);
        }
        let haystack = text.to_lowercase();
        let mut total: u64 = 0;
        let mut changed = false;
        for entry in entries.iter_mut() {
            if !entry.enabled {
                continue;
            }
            let needle = entry.phrase.trim().to_lowercase();
            if needle.is_empty() {
                continue;
            }
            let count = count_occurrences(&haystack, &needle);
            if count > 0 {
                entry.hits = entry.hits.saturating_add(count);
                total = total.saturating_add(count);
                changed = true;
            }
        }
        if changed {
            self.write_locked(&entries)?;
        }
        Ok(total)
    }

    fn read_locked(&self) -> Result<Vec<DictionaryEntry>> {
        read_or_default::<Vec<DictionaryEntry>>(&self.path)
    }

    fn write_locked(&self, entries: &[DictionaryEntry]) -> Result<()> {
        let json = serde_json::to_vec_pretty(entries).context("encode vocab failed")?;
        atomic_write(&self.path, &json)
    }
}

/// 统计 `needle` 在 `haystack` 中的非重叠出现次数。两侧调用前都应已转小写。
fn count_occurrences(haystack: &str, needle: &str) -> u64 {
    if needle.is_empty() || haystack.len() < needle.len() {
        return 0;
    }
    let mut count: u64 = 0;
    let mut start = 0usize;
    while let Some(pos) = haystack[start..].find(needle) {
        count = count.saturating_add(1);
        start = start + pos + needle.len();
        if start >= haystack.len() {
            break;
        }
    }
    count
}

pub fn list_vocab_presets() -> Result<VocabPresetStore> {
    let dir = data_dir()?;
    ensure_dir(&dir)?;
    read_or_default::<VocabPresetStore>(&dir.join(VOCAB_PRESETS_FILE))
}

pub fn save_vocab_presets(store: &VocabPresetStore) -> Result<()> {
    let dir = data_dir()?;
    ensure_dir(&dir)?;
    let path = dir.join(VOCAB_PRESETS_FILE);
    let json = serde_json::to_vec_pretty(store).context("encode vocab presets failed")?;
    atomic_write(&path, &json)
}

// ───────────────────────── CorrectionRuleStore ─────────────────────────

pub struct CorrectionRuleStore {
    path: PathBuf,
    lock: Mutex<()>,
}

impl CorrectionRuleStore {
    pub fn new() -> Result<Self> {
        let dir = data_dir()?;
        ensure_dir(&dir)?;
        Ok(Self {
            path: dir.join(CORRECTION_RULES_FILE),
            lock: Mutex::new(()),
        })
    }

    pub fn list(&self) -> Result<Vec<CorrectionRule>> {
        let _guard = self.lock.lock();
        self.read_locked()
    }

    pub fn add(&self, pattern: String, replacement: String) -> Result<CorrectionRule> {
        let pattern = pattern.trim().to_string();
        let replacement = replacement.trim().to_string();
        validate_correction_rule_syntax(&pattern, &replacement)?;
        let _guard = self.lock.lock();
        let mut rules = self.read_locked()?;
        let rule = CorrectionRule {
            id: Uuid::new_v4().to_string(),
            pattern,
            replacement,
            enabled: true,
            created_at: Utc::now().to_rfc3339(),
        };
        rules.insert(0, rule.clone());
        self.write_locked(&rules)?;
        Ok(rule)
    }

    pub fn remove(&self, id: &str) -> Result<()> {
        let _guard = self.lock.lock();
        let mut rules = self.read_locked()?;
        let before = rules.len();
        rules.retain(|r| r.id != id);
        if rules.len() == before {
            return Ok(());
        }
        self.write_locked(&rules)
    }

    pub fn set_enabled(&self, id: &str, enabled: bool) -> Result<()> {
        let _guard = self.lock.lock();
        let mut rules = self.read_locked()?;
        let mut found = false;
        for rule in rules.iter_mut() {
            if rule.id == id {
                rule.enabled = enabled;
                found = true;
                break;
            }
        }
        if !found {
            return Err(anyhow!("correction rule {} not found", id));
        }
        self.write_locked(&rules)
    }

    fn read_locked(&self) -> Result<Vec<CorrectionRule>> {
        read_or_default::<Vec<CorrectionRule>>(&self.path)
    }

    fn write_locked(&self, rules: &[CorrectionRule]) -> Result<()> {
        let json = serde_json::to_vec_pretty(rules).context("encode correction rules failed")?;
        atomic_write(&self.path, &json)
    }
}

fn validate_correction_rule_syntax(pattern: &str, replacement: &str) -> Result<()> {
    if pattern.is_empty() {
        return Err(anyhow!("correction rule pattern is empty"));
    }
    let pattern_token_count = pattern.matches(CORRECTION_NUM_TOKEN).count();
    if pattern_token_count > 1 {
        return Err(anyhow!("unsupported correction rule syntax"));
    }
    if replacement.contains(CORRECTION_NUM_TOKEN) && pattern_token_count == 0 {
        return Err(anyhow!("unsupported correction rule syntax"));
    }
    if pattern_token_count == 1 {
        let Some((prefix, suffix)) = pattern.split_once(CORRECTION_NUM_TOKEN) else {
            return Err(anyhow!("unsupported correction rule syntax"));
        };
        if prefix.is_empty() && suffix.is_empty() {
            return Err(anyhow!("unsupported correction rule syntax"));
        }
    }
    Ok(())
}

// ───────────────────────── CredentialsVault ─────────────────────────

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum CredentialAccount {
    VolcengineAppKey,
    VolcengineAccessKey,
    VolcengineResourceId,
    ArkApiKey,
    ArkModelId,
    ArkEndpoint,
    /// Qwen realtime ASR API key, independent of the active ASR provider.
    AsrQwenApiKey,
    /// Doubao streaming ASR API key, independent of the active ASR provider.
    AsrDoubaoApiKey,
    /// Qwen LLM API key, independent of the active LLM provider.
    LlmQwenApiKey,
    /// Gemini API key, independent of the active LLM provider.
    LlmGeminiApiKey,
    /// Active ASR provider's API key (used by Whisper-compatible providers).
    AsrApiKey,
    /// Active ASR provider's base URL.
    AsrEndpoint,
    /// Active ASR provider's model name.
    AsrModel,
    /// Active ASR provider's optional hotword vocabulary ID.
    AsrVocabularyId,
}

impl CredentialAccount {
    /// Account names match the Swift `CredentialAccount` constants exactly so
    /// existing Keychain entries written by the macOS Swift app remain
    /// readable after upgrade.
    pub fn as_str(&self) -> &'static str {
        match self {
            CredentialAccount::VolcengineAppKey => "volcengine.app_key",
            CredentialAccount::VolcengineAccessKey => "volcengine.access_key",
            CredentialAccount::VolcengineResourceId => "volcengine.resource_id",
            CredentialAccount::ArkApiKey => "ark.api_key",
            CredentialAccount::ArkModelId => "ark.model_id",
            CredentialAccount::ArkEndpoint => "ark.endpoint",
            CredentialAccount::AsrQwenApiKey => "asr.qwen.api_key",
            CredentialAccount::AsrDoubaoApiKey => "asr.doubao.api_key",
            CredentialAccount::LlmQwenApiKey => "llm.qwen.api_key",
            CredentialAccount::LlmGeminiApiKey => "llm.gemini.api_key",
            CredentialAccount::AsrApiKey => "asr.api_key",
            CredentialAccount::AsrEndpoint => "asr.endpoint",
            CredentialAccount::AsrModel => "asr.model",
            CredentialAccount::AsrVocabularyId => "asr.vocabulary_id",
        }
    }

    pub fn keyring_account(&self) -> &'static str {
        self.as_str()
    }

    pub fn all() -> &'static [CredentialAccount] {
        &[
            CredentialAccount::VolcengineAppKey,
            CredentialAccount::VolcengineAccessKey,
            CredentialAccount::VolcengineResourceId,
            CredentialAccount::ArkApiKey,
            CredentialAccount::ArkModelId,
            CredentialAccount::ArkEndpoint,
            CredentialAccount::AsrQwenApiKey,
            CredentialAccount::AsrDoubaoApiKey,
            CredentialAccount::LlmQwenApiKey,
            CredentialAccount::LlmGeminiApiKey,
            CredentialAccount::AsrApiKey,
            CredentialAccount::AsrEndpoint,
            CredentialAccount::AsrModel,
            CredentialAccount::AsrVocabularyId,
        ]
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CredentialsSnapshot {
    pub volcengine_app_key: Option<String>,
    pub volcengine_access_key: Option<String>,
    pub volcengine_resource_id: Option<String>,
    pub asr_qwen_api_key: Option<String>,
    pub asr_doubao_api_key: Option<String>,
    pub llm_qwen_api_key: Option<String>,
    pub llm_gemini_api_key: Option<String>,
    pub asr_api_key: Option<String>,
    pub asr_endpoint: Option<String>,
    pub asr_model: Option<String>,
    pub ark_api_key: Option<String>,
    pub ark_model_id: Option<String>,
    pub ark_endpoint: Option<String>,
}

/// 凭据存储——系统凭据库；旧 JSON 文件只作为迁移来源。
pub struct CredentialsVault;

impl CredentialsVault {
    /// 系统凭据库 service name；macOS 下对应 Keychain service。
    pub const SERVICE_NAME: &'static str = crate::product::KEYRING_SERVICE_NAME;

    pub fn normalize_active_asr_provider_id(id: &str) -> String {
        normalize_active_asr_provider(id)
    }

    pub fn normalize_active_llm_provider_id(id: &str) -> String {
        normalize_active_llm_provider(id)
    }

    pub fn get(account: CredentialAccount) -> Result<Option<String>> {
        let _guard = credentials_lock().lock();
        Ok(lookup_account(&load_credentials(), account))
    }

    pub fn set(account: CredentialAccount, value: &str) -> Result<()> {
        let _guard = credentials_lock().lock();
        let mut root = load_credentials_for_update()?;
        let v = if value.is_empty() {
            None
        } else {
            Some(value.to_string())
        };
        write_account(&mut root, account, v);
        save_credentials(&root)
    }

    pub fn remove(account: CredentialAccount) -> Result<()> {
        let _guard = credentials_lock().lock();
        let mut root = load_credentials_for_update()?;
        write_account(&mut root, account, None);
        save_credentials(&root)
    }

    pub fn get_active_asr() -> String {
        let _guard = credentials_lock().lock();
        load_credentials().active.asr
    }

    pub fn set_active_asr_provider(id: &str) -> Result<()> {
        let _guard = credentials_lock().lock();
        let mut root = load_credentials_for_update()?;
        root.active.asr = normalize_active_asr_provider(id);
        save_credentials(&root)
    }

    pub fn set_active_llm_provider(id: &str) -> Result<()> {
        let _guard = credentials_lock().lock();
        let mut root = load_credentials_for_update()?;
        root.active.llm = normalize_active_llm_provider(id);
        save_credentials(&root)
    }

    pub fn clear_provider_configuration() -> Result<()> {
        let _guard = credentials_lock().lock();
        let root = load_credentials_for_update()?;
        save_credentials(&reset_provider_configuration_root(&root))
    }

    pub fn get_active_llm() -> String {
        let _guard = credentials_lock().lock();
        load_credentials().active.llm
    }

    pub fn snapshot() -> CredentialsSnapshot {
        let _guard = credentials_lock().lock();
        let root = load_credentials();
        CredentialsSnapshot {
            volcengine_app_key: lookup_account(&root, CredentialAccount::VolcengineAppKey),
            volcengine_access_key: lookup_account(&root, CredentialAccount::VolcengineAccessKey),
            volcengine_resource_id: lookup_account(&root, CredentialAccount::VolcengineResourceId),
            asr_qwen_api_key: lookup_account(&root, CredentialAccount::AsrQwenApiKey),
            asr_doubao_api_key: lookup_account(&root, CredentialAccount::AsrDoubaoApiKey),
            llm_qwen_api_key: lookup_account(&root, CredentialAccount::LlmQwenApiKey),
            llm_gemini_api_key: lookup_account(&root, CredentialAccount::LlmGeminiApiKey),
            asr_api_key: lookup_account(&root, CredentialAccount::AsrApiKey),
            asr_endpoint: lookup_account(&root, CredentialAccount::AsrEndpoint),
            asr_model: lookup_account(&root, CredentialAccount::AsrModel),
            ark_api_key: lookup_account(&root, CredentialAccount::ArkApiKey),
            ark_model_id: lookup_account(&root, CredentialAccount::ArkModelId),
            ark_endpoint: lookup_account(&root, CredentialAccount::ArkEndpoint),
        }
    }

    #[cfg(test)]
    pub(crate) fn get_llm_provider_api_key_for_smoke(provider_id: &str) -> Result<Option<String>> {
        let _guard = credentials_lock().lock();
        let root = load_credentials();
        Ok(root
            .providers
            .llm
            .get(provider_id)
            .and_then(|entry| entry.apiKey.as_ref())
            .filter(|value| !value.trim().is_empty())
            .cloned())
    }
}

#[cfg(test)]
mod tests {
    use super::{
        chunk_json_payload, clean_credentials, list_vocab_presets, normalize_active_llm_provider,
        save_vocab_presets, validate_correction_rule_syntax, write_account, CredentialAccount,
        CredsAsrEntry, CredsChunkManifest, CredsLlmEntry, CredsRoot, DictionaryStore, HistoryStore,
        KEYRING_CHUNK_MAX_UTF16_UNITS, LEGACY_ASR_PROVIDER_ID,
    };
    use crate::types::{
        DictationSession, DictionaryEntry, InsertStatus, PolishMode, VocabPreset, VocabPresetStore,
    };
    use std::fs;
    use std::path::PathBuf;

    #[test]
    fn credentials_root_defaults_to_cloud_first_active_providers() {
        super::reset_credentials_cache_for_tests();
        let root = CredsRoot::default();
        assert_eq!(
            root.active.asr,
            crate::product::QWEN_REALTIME_ASR_PROVIDER_ID
        );
        assert_eq!(root.active.llm, crate::product::QWEN_LLM_PROVIDER_ID);
    }

    #[test]
    fn credential_sanitize_maps_volcengine_active_to_doubao_backup() {
        super::reset_credentials_cache_for_tests();
        let mut root = CredsRoot::default();
        root.active.asr = "volcengine".into();

        let sanitized = super::sanitize_credentials(&root);

        assert_eq!(sanitized.active.asr, crate::product::DOUBAO_ASR_PROVIDER_ID);
    }

    #[test]
    fn clean_credentials_migrates_previous_qwen_default_model_to_flash() {
        let mut root = CredsRoot::default();
        root.version = 1;
        root.providers.llm.insert(
            crate::product::QWEN_LLM_PROVIDER_ID.into(),
            CredsLlmEntry {
                apiKey: Some("key".into()),
                model: Some("qwen3.6-plus".into()),
                ..Default::default()
            },
        );

        let cleaned = clean_credentials(&root);
        let qwen = cleaned
            .providers
            .llm
            .get(crate::product::QWEN_LLM_PROVIDER_ID)
            .expect("qwen llm bucket");

        assert_eq!(qwen.model.as_deref(), Some("qwen3.5-flash"));
    }

    #[test]
    fn clean_credentials_remaps_current_qwen_plus_selection_to_flash() {
        let mut root = CredsRoot::default();
        root.providers.llm.insert(
            crate::product::QWEN_LLM_PROVIDER_ID.into(),
            CredsLlmEntry {
                apiKey: Some("key".into()),
                model: Some("qwen3.6-plus".into()),
                ..Default::default()
            },
        );

        let cleaned = clean_credentials(&root);
        let qwen = cleaned
            .providers
            .llm
            .get(crate::product::QWEN_LLM_PROVIDER_ID)
            .expect("qwen llm bucket");

        assert_eq!(qwen.model.as_deref(), Some("qwen3.5-flash"));
    }

    #[test]
    fn credential_payload_chunks_stay_under_windows_blob_limit() {
        let payload = format!(
            "{}{}{}",
            "a".repeat(KEYRING_CHUNK_MAX_UTF16_UNITS + 25),
            "😀".repeat(20),
            "b".repeat(KEYRING_CHUNK_MAX_UTF16_UNITS + 25)
        );
        let chunks = chunk_json_payload(&payload);
        assert!(chunks.len() > 1);
        assert_eq!(chunks.concat(), payload);
        assert!(chunks
            .iter()
            .all(|chunk| chunk.encode_utf16().count() <= KEYRING_CHUNK_MAX_UTF16_UNITS));
    }

    #[test]
    fn credential_accounts_include_cloud_provider_specific_keys() {
        assert_eq!(
            CredentialAccount::AsrQwenApiKey.as_str(),
            "asr.qwen.api_key"
        );
        assert_eq!(
            CredentialAccount::AsrDoubaoApiKey.as_str(),
            "asr.doubao.api_key"
        );
        assert_eq!(
            CredentialAccount::LlmQwenApiKey.as_str(),
            "llm.qwen.api_key"
        );
        assert_eq!(
            CredentialAccount::LlmGeminiApiKey.as_str(),
            "llm.gemini.api_key"
        );
    }

    #[test]
    fn stable_chunk_generation_alternates_without_overwriting_active_slot() {
        assert_eq!(super::next_stable_chunk_generation(None), "stable-a");
        assert_eq!(
            super::next_stable_chunk_generation(Some("stable-a")),
            "stable-b"
        );
        assert_eq!(
            super::next_stable_chunk_generation(Some("stable-b")),
            "stable-a"
        );
    }

    #[test]
    fn usage_stats_keep_all_time_chars_when_history_is_capped() {
        let dir = std::env::temp_dir().join(format!(
            "whisper-input-history-stats-{}",
            uuid::Uuid::new_v4()
        ));
        fs::create_dir_all(&dir).unwrap();
        let history = HistoryStore::with_dir_for_tests(dir.clone());

        for index in 0..=super::HISTORY_CAP {
            history
                .append_with_retention(test_session(index, "abc"), 0)
                .unwrap();
        }

        assert_eq!(history.list().unwrap().len(), super::HISTORY_CAP);
        assert_eq!(
            history.usage_stats().unwrap().total_chars,
            ((super::HISTORY_CAP + 1) * 3) as u64
        );

        fs::remove_dir_all(dir).ok();
    }

    #[test]
    fn clearing_history_resets_usage_stats() {
        let dir = std::env::temp_dir().join(format!(
            "whisper-input-history-clear-{}",
            uuid::Uuid::new_v4()
        ));
        fs::create_dir_all(&dir).unwrap();
        let history = HistoryStore::with_dir_for_tests(dir.clone());

        history
            .append_with_retention(test_session(1, "abc"), 0)
            .unwrap();
        history.clear().unwrap();

        assert_eq!(history.list().unwrap().len(), 0);
        assert_eq!(history.usage_stats().unwrap().total_chars, 0);

        fs::remove_dir_all(dir).ok();
    }

    fn test_session(index: usize, final_text: &str) -> DictationSession {
        DictationSession {
            id: format!("session-{index}"),
            created_at: format!("2026-06-08T00:{:02}:00Z", index % 60),
            raw_transcript: final_text.to_string(),
            final_text: final_text.to_string(),
            mode: PolishMode::Light,
            app_bundle_id: None,
            app_name: None,
            insert_status: InsertStatus::Inserted,
            error_code: None,
            duration_ms: Some(1000),
            dictionary_entry_count: None,
            asr_provider_id: None,
            llm_provider_id: None,
        }
    }

    #[test]
    fn manifest_read_error_prevents_target_generation_selection() {
        let result = super::previous_manifest_from_value(Err(anyhow::anyhow!("transient")));

        assert!(result.is_err());
    }

    #[test]
    fn invalid_manifest_prevents_target_generation_selection() {
        let result = super::previous_manifest_from_value(Ok(Some("{\"version\":1}".into())));

        assert!(result.is_err());
    }

    #[test]
    fn missing_manifest_allows_first_write() {
        let result = super::previous_manifest_from_value(Ok(None)).expect("missing manifest ok");

        assert!(result.is_none());
    }

    #[test]
    fn stable_chunk_cleanup_removes_old_active_slot_and_target_overflow() {
        let previous = CredsChunkManifest {
            openless_credentials_storage: "chunked".into(),
            version: 1,
            generation: Some("stable-a".into()),
            chunks: 3,
        };
        let cleanup = super::chunk_accounts_to_cleanup_after_save(Some(&previous), "stable-b", 1);

        assert!(cleanup.contains(&super::chunk_account(Some("stable-a"), 0)));
        assert!(cleanup.contains(&super::chunk_account(Some("stable-a"), 2)));
        assert!(cleanup.contains(&super::chunk_account(Some("stable-b"), 1)));
        assert!(cleanup.contains(&super::chunk_account(Some("stable-b"), 2)));
    }

    #[test]
    fn stale_chunk_cleanup_removes_unreferenced_target_slot_without_touching_active_slot() {
        let cleanup = super::stale_target_chunk_accounts_to_cleanup("stable-b", 1);

        assert!(!cleanup.contains(&super::chunk_account(Some("stable-a"), 0)));
        assert!(!cleanup.contains(&super::chunk_account(Some("stable-b"), 0)));
        assert!(cleanup.contains(&super::chunk_account(Some("stable-b"), 1)));
        assert!(cleanup.contains(&super::chunk_account(Some("stable-b"), 63)));
        assert!(!cleanup.contains(&super::chunk_account(Some("stable-b"), 64)));
    }

    #[test]
    fn reset_provider_configuration_root_clears_credentials_and_restores_defaults() {
        let mut root = CredsRoot::default();
        root.active.asr = crate::product::DOUBAO_ASR_PROVIDER_ID.into();
        root.active.llm = crate::product::GEMINI_PROVIDER_ID.into();
        root.providers.asr.insert(
            crate::product::QWEN_REALTIME_ASR_PROVIDER_ID.into(),
            CredsAsrEntry {
                apiKey: Some("asr-key".into()),
                ..Default::default()
            },
        );
        root.providers.llm.insert(
            crate::product::GEMINI_PROVIDER_ID.into(),
            CredsLlmEntry {
                apiKey: Some("llm-key".into()),
                ..Default::default()
            },
        );

        let reset = super::reset_provider_configuration_root(&root);

        assert_eq!(reset.active.asr, crate::product::DEFAULT_ASR_PROVIDER_ID);
        assert_eq!(reset.active.llm, crate::product::DEFAULT_LLM_PROVIDER_ID);
        assert!(reset.providers.asr.is_empty());
        assert!(reset.providers.llm.is_empty());
    }

    #[test]
    fn dictionary_store_clear_removes_all_entries() {
        let path = std::env::temp_dir().join(format!(
            "openless-vocab-clear-{}.json",
            uuid::Uuid::new_v4()
        ));
        fs::write(
            &path,
            serde_json::to_vec(&vec![DictionaryEntry {
                id: "term-1".into(),
                phrase: "轻语输入".into(),
                note: None,
                enabled: true,
                hits: 3,
                created_at: "2026-05-15T00:00:00Z".into(),
            }])
            .expect("encode vocab fixture"),
        )
        .expect("write vocab fixture");
        let store = DictionaryStore::new_for_path(path.clone());

        store.clear().expect("clear vocab");

        assert!(store.list().expect("list vocab").is_empty());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn legacy_per_account_asr_secrets_migrate_to_doubao_bucket() {
        let mut root = CredsRoot::default();
        root.active.asr = LEGACY_ASR_PROVIDER_ID.into();

        write_account(
            &mut root,
            CredentialAccount::VolcengineAppKey,
            Some("app".into()),
        );
        write_account(
            &mut root,
            CredentialAccount::VolcengineAccessKey,
            Some("access".into()),
        );
        write_account(
            &mut root,
            CredentialAccount::VolcengineResourceId,
            Some("resource".into()),
        );
        write_account(&mut root, CredentialAccount::AsrApiKey, Some("key".into()));
        write_account(
            &mut root,
            CredentialAccount::AsrEndpoint,
            Some("https://legacy.example/v1".into()),
        );
        write_account(
            &mut root,
            CredentialAccount::AsrModel,
            Some("legacy-model".into()),
        );

        let cleaned = clean_credentials(&root);

        assert_eq!(
            cleaned.active.asr,
            crate::product::DOUBAO_ASR_PROVIDER_ID.to_string()
        );
        let doubao_asr = cleaned
            .providers
            .asr
            .get(crate::product::DOUBAO_ASR_PROVIDER_ID)
            .expect("doubao ASR bucket");
        assert_eq!(doubao_asr.appKey.as_deref(), Some("app"));
        assert_eq!(doubao_asr.accessKey.as_deref(), Some("access"));
        assert_eq!(doubao_asr.resourceId.as_deref(), Some("resource"));
        assert_eq!(doubao_asr.apiKey.as_deref(), Some("key"));
        assert_eq!(
            doubao_asr.baseURL.as_deref(),
            Some("https://legacy.example/v1")
        );
        assert_eq!(doubao_asr.model.as_deref(), Some("legacy-model"));
        assert_eq!(
            super::lookup_account(&cleaned, CredentialAccount::VolcengineAppKey).as_deref(),
            Some("app")
        );
        assert_eq!(
            super::lookup_account(&cleaned, CredentialAccount::VolcengineAccessKey).as_deref(),
            Some("access")
        );
        assert_eq!(
            super::lookup_account(&cleaned, CredentialAccount::VolcengineResourceId).as_deref(),
            Some("resource")
        );
        assert_eq!(
            super::lookup_account(&cleaned, CredentialAccount::AsrApiKey).as_deref(),
            Some("key")
        );
        assert_eq!(
            super::lookup_account(&cleaned, CredentialAccount::AsrEndpoint).as_deref(),
            Some("https://legacy.example/v1")
        );
        assert_eq!(
            super::lookup_account(&cleaned, CredentialAccount::AsrModel).as_deref(),
            Some("legacy-model")
        );
    }

    #[test]
    fn legacy_per_account_asr_migration_keeps_existing_doubao_fields() {
        let mut root = CredsRoot::default();
        root.active.asr = LEGACY_ASR_PROVIDER_ID.into();
        write_account(
            &mut root,
            CredentialAccount::VolcengineAppKey,
            Some("legacy-app".into()),
        );
        write_account(
            &mut root,
            CredentialAccount::VolcengineAccessKey,
            Some("legacy-access".into()),
        );
        write_account(
            &mut root,
            CredentialAccount::AsrApiKey,
            Some("legacy-key".into()),
        );
        root.providers.asr.insert(
            crate::product::DOUBAO_ASR_PROVIDER_ID.into(),
            super::CredsAsrEntry {
                apiKey: Some("existing-key".into()),
                baseURL: Some("https://existing.example/v1".into()),
                ..Default::default()
            },
        );

        let cleaned = clean_credentials(&root);
        let doubao_asr = cleaned
            .providers
            .asr
            .get(crate::product::DOUBAO_ASR_PROVIDER_ID)
            .expect("doubao ASR bucket");

        assert_eq!(doubao_asr.appKey.as_deref(), Some("legacy-app"));
        assert_eq!(doubao_asr.accessKey.as_deref(), Some("legacy-access"));
        assert_eq!(doubao_asr.apiKey.as_deref(), Some("existing-key"));
        assert_eq!(
            doubao_asr.baseURL.as_deref(),
            Some("https://existing.example/v1")
        );
    }

    #[test]
    fn normalize_active_llm_provider_keeps_gemini_and_collapses_legacy_ids() {
        assert_eq!(
            normalize_active_llm_provider(crate::product::GEMINI_PROVIDER_ID),
            crate::product::GEMINI_PROVIDER_ID
        );
        for id in [
            "ark",
            "deepseek",
            "siliconflow",
            "openai",
            "custom",
            "mimo",
            "cometapi",
            "openrouterFree",
            "alibabaCoding",
            "codingPlanX",
            "codex_oauth",
            "future-provider",
        ] {
            assert_eq!(
                normalize_active_llm_provider(id),
                crate::product::OPENAI_COMPATIBLE_PROVIDER_ID
            );
        }
        assert_eq!(
            normalize_active_llm_provider(""),
            crate::product::QWEN_LLM_PROVIDER_ID
        );
    }

    #[test]
    fn clean_credentials_migrates_active_legacy_llm_bucket_to_openai_compatible() {
        let mut root = CredsRoot::default();
        root.active.llm = "deepseek".into();
        root.providers.llm.insert(
            "deepseek".into(),
            CredsLlmEntry {
                apiKey: Some("legacy-key".into()),
                baseURL: Some("https://api.deepseek.com/v1".into()),
                model: Some("deepseek-chat".into()),
                ..Default::default()
            },
        );
        root.providers.llm.insert(
            crate::product::OPENAI_COMPATIBLE_PROVIDER_ID.into(),
            CredsLlmEntry {
                apiKey: Some("existing-key".into()),
                ..Default::default()
            },
        );
        root.providers.llm.insert(
            crate::product::GEMINI_PROVIDER_ID.into(),
            CredsLlmEntry {
                apiKey: Some("gemini-key".into()),
                baseURL: Some("https://generativelanguage.googleapis.com/v1beta".into()),
                model: Some("gemini-2.5-flash".into()),
                ..Default::default()
            },
        );

        let cleaned = clean_credentials(&root);

        assert_eq!(
            cleaned.active.llm,
            crate::product::OPENAI_COMPATIBLE_PROVIDER_ID
        );
        let openai_compatible = cleaned
            .providers
            .llm
            .get(crate::product::OPENAI_COMPATIBLE_PROVIDER_ID)
            .expect("openai-compatible bucket");
        assert_eq!(openai_compatible.apiKey.as_deref(), Some("legacy-key"));
        assert_eq!(
            openai_compatible.baseURL.as_deref(),
            Some("https://api.deepseek.com/v1")
        );
        assert_eq!(openai_compatible.model.as_deref(), Some("deepseek-chat"));
        assert!(cleaned.providers.llm.contains_key("deepseek"));
        assert_eq!(
            cleaned
                .providers
                .llm
                .get(crate::product::GEMINI_PROVIDER_ID)
                .and_then(|entry| entry.apiKey.as_deref()),
            Some("gemini-key")
        );
    }

    #[test]
    fn clean_credentials_preserves_complete_openai_compatible_bucket_during_legacy_migration() {
        let mut root = CredsRoot::default();
        root.active.llm = "deepseek".into();
        root.providers.llm.insert(
            "deepseek".into(),
            CredsLlmEntry {
                apiKey: Some("legacy-key".into()),
                baseURL: Some("https://api.deepseek.com/v1".into()),
                model: Some("deepseek-chat".into()),
                ..Default::default()
            },
        );
        root.providers.llm.insert(
            crate::product::OPENAI_COMPATIBLE_PROVIDER_ID.into(),
            CredsLlmEntry {
                apiKey: Some("target-key".into()),
                baseURL: Some("https://api.openai.com/v1".into()),
                model: Some("gpt-4o-mini".into()),
                ..Default::default()
            },
        );

        let cleaned = clean_credentials(&root);
        let openai_compatible = cleaned
            .providers
            .llm
            .get(crate::product::OPENAI_COMPATIBLE_PROVIDER_ID)
            .expect("openai-compatible bucket");

        assert_eq!(openai_compatible.apiKey.as_deref(), Some("target-key"));
        assert_eq!(
            openai_compatible.baseURL.as_deref(),
            Some("https://api.openai.com/v1")
        );
        assert_eq!(openai_compatible.model.as_deref(), Some("gpt-4o-mini"));
        assert!(cleaned.providers.llm.contains_key("deepseek"));
    }

    #[test]
    fn vocab_presets_roundtrip_json_file() {
        let tmp: PathBuf =
            std::env::temp_dir().join(format!("openless-test-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&tmp).expect("create temp dir");
        // Linux path helper uses XDG_DATA_HOME first.
        unsafe {
            std::env::set_var("XDG_DATA_HOME", &tmp);
        }
        let store = VocabPresetStore {
            custom: vec![VocabPreset {
                id: "test".into(),
                name: "测试".into(),
                phrases: vec!["PR".into(), "CI".into()],
            }],
            overrides: vec![],
            disabled_builtin_preset_ids: vec!["chef".into()],
        };
        save_vocab_presets(&store).expect("save presets");
        let loaded = list_vocab_presets().expect("list presets");
        assert_eq!(loaded.custom.len(), 1);
        assert_eq!(loaded.custom[0].id, "test");
        assert_eq!(
            loaded.custom[0].phrases,
            vec!["PR".to_string(), "CI".to_string()]
        );
        assert_eq!(loaded.disabled_builtin_preset_ids, vec!["chef".to_string()]);
        let _ = fs::remove_dir_all(&tmp);
    }

    #[test]
    fn correction_rule_syntax_rejects_silent_noops() {
        assert!(validate_correction_rule_syntax("{num}粒", "{num}例").is_ok());
        assert!(validate_correction_rule_syntax("几粒", "几例").is_ok());
        assert!(validate_correction_rule_syntax("", "几例").is_err());
        assert!(validate_correction_rule_syntax("{num}", "{num}例").is_err());
        assert!(validate_correction_rule_syntax("{num}到{num}粒", "{num}例").is_err());
        assert!(validate_correction_rule_syntax("几粒", "{num}例").is_err());
    }
}
