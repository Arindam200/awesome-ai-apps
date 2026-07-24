#[cfg(target_os = "windows")]
#[allow(dead_code)]
mod imp {
    use std::path::{Path, PathBuf};
    use std::sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    };

    use anyhow::{Context, Result};
    use foundry_local_sdk::{FoundryLocalConfig, FoundryLocalManager, Model};
    use parking_lot::Mutex;
    use tokio::sync::Mutex as AsyncMutex;

    use crate::asr::local::foundry::{
        FoundryCatalogModel, FoundryPrepareProgressPayload, FoundryRuntimeStatus, MODELS,
        PROVIDER_ID,
    };
    use crate::asr::local::foundry_native::{self, RuntimeSource};

    type FoundryPrepareProgressCallback =
        Arc<dyn Fn(FoundryPrepareProgressPayload) + Send + Sync + 'static>;

    #[derive(Clone)]
    struct LoadedModel {
        alias: String,
        model_id: String,
        model: Arc<Model>,
    }

    #[derive(Default)]
    struct RuntimeState {
        manager: Option<&'static FoundryLocalManager>,
        loaded: Option<LoadedModel>,
    }

    pub struct FoundryLocalRuntime {
        lifecycle: AsyncMutex<()>,
        cancel_prepare: AtomicBool,
        state: Mutex<RuntimeState>,
    }

    impl Default for FoundryLocalRuntime {
        fn default() -> Self {
            Self::new()
        }
    }

    impl FoundryLocalRuntime {
        pub fn new() -> Self {
            Self {
                lifecycle: AsyncMutex::new(()),
                cancel_prepare: AtomicBool::new(false),
                state: Mutex::new(RuntimeState::default()),
            }
        }

        pub async fn status_snapshot(
            &self,
            active_model: &str,
            runtime_source: &str,
        ) -> FoundryRuntimeStatus {
            let loaded_model_id = self
                .state
                .lock()
                .loaded
                .as_ref()
                .map(|loaded| loaded.model_id.clone());
            let native_ready = foundry_native::runtime_ready();
            FoundryRuntimeStatus {
                provider_id: PROVIDER_ID.into(),
                available: true,
                runtime_ready: native_ready,
                runtime_source: foundry_native::normalize_runtime_source_str(runtime_source),
                active_model: active_model.to_string(),
                loaded_model_id,
                endpoint: None,
                error: None,
            }
        }

        pub async fn ensure_loaded(&self, alias: &str, runtime_source: &str) -> Result<String> {
            self.ensure_loaded_with_progress(alias, runtime_source, |_| {})
                .await
        }

        pub async fn ensure_loaded_with_progress<F>(
            &self,
            alias: &str,
            runtime_source: &str,
            progress: F,
        ) -> Result<String>
        where
            F: Fn(FoundryPrepareProgressPayload) + Send + Sync + 'static,
        {
            let _lifecycle = self.lifecycle.lock().await;
            self.cancel_prepare.store(false, Ordering::SeqCst);
            let progress: FoundryPrepareProgressCallback = Arc::new(progress);
            let runtime_source = foundry_native::normalize_runtime_source(runtime_source);
            Ok(self
                .ensure_loaded_locked(alias, runtime_source, progress)
                .await?
                .model_id)
        }

        pub fn request_cancel_prepare(&self) {
            self.cancel_prepare.store(true, Ordering::SeqCst);
        }

        #[cfg(test)]
        pub(crate) fn cancel_prepare_requested_for_tests(&self) -> bool {
            self.cancel_prepare.load(Ordering::SeqCst)
        }

        pub async fn catalog_snapshot(&self) -> Result<Vec<FoundryCatalogModel>> {
            let _lifecycle = self.lifecycle.lock().await;
            if !foundry_native::runtime_ready() {
                return Ok(crate::asr::local::foundry::static_catalog_models());
            }
            let manager = self.manager()?;
            let mut catalog = Vec::with_capacity(MODELS.len());
            for known in MODELS {
                let model = manager
                    .catalog()
                    .get_model(known.alias)
                    .await
                    .with_context(|| format!("get Foundry catalog model {}", known.alias))?;
                let info = model.info();
                let cached = model.is_cached().await.unwrap_or(info.cached);
                catalog.push(FoundryCatalogModel {
                    alias: known.alias.to_string(),
                    display_name: info
                        .display_name
                        .clone()
                        .unwrap_or_else(|| known.display_name.to_string()),
                    cached,
                    file_size_mb: info.file_size_mb,
                });
            }
            Ok(catalog)
        }

        pub async fn transcribe_audio_file(
            &self,
            alias: &str,
            runtime_source: &str,
            language_hint: Option<&str>,
            audio_path: &Path,
            audio_timeout: std::time::Duration,
        ) -> Result<String> {
            let _lifecycle = self.lifecycle.lock().await;
            self.cancel_prepare.store(false, Ordering::SeqCst);
            let runtime_source = foundry_native::normalize_runtime_source(runtime_source);
            let model = self
                .ensure_loaded_locked(alias, runtime_source, Arc::new(|_| {}))
                .await?
                .model;
            let mut client = model.create_audio_client();
            if let Some(language_hint) = normalized_language_hint(language_hint) {
                client = client.language(language_hint);
            }
            let result = tokio::time::timeout(audio_timeout, client.transcribe(audio_path))
                .await
                .with_context(|| {
                    format!(
                        "transcribe audio with Foundry model {alias} timed out after {} seconds",
                        audio_timeout.as_secs()
                    )
                })?
                .with_context(|| format!("transcribe audio with Foundry model {alias}"))?;
            Ok(result.text)
        }

        pub async fn release_now(&self) -> Result<()> {
            let _lifecycle = self.lifecycle.lock().await;
            self.release_now_locked().await
        }

        async fn ensure_loaded_locked(
            &self,
            alias: &str,
            runtime_source: RuntimeSource,
            progress: FoundryPrepareProgressCallback,
        ) -> Result<LoadedModel> {
            if let Some(loaded) = self.cached_loaded_model(alias) {
                progress.as_ref()(FoundryPrepareProgressPayload::finished(
                    alias,
                    "Foundry model already loaded",
                ));
                return Ok(loaded);
            }

            let previous_loaded = self.loaded_for_different_alias(alias);

            self.check_prepare_cancelled()?;
            foundry_native::ensure_runtime(runtime_source, {
                let progress = Arc::clone(&progress);
                let alias = alias.to_string();
                move |label, percent| {
                    progress.as_ref()(FoundryPrepareProgressPayload::runtime(
                        alias.clone(),
                        label.to_string(),
                        percent,
                    ));
                }
            })
            .await
            .context("download Foundry Local native runtime")?;
            self.check_prepare_cancelled()?;
            let manager = self.manager()?;
            progress.as_ref()(FoundryPrepareProgressPayload::runtime(
                alias,
                "Foundry Local runtime components",
                0.0,
            ));
            let runtime_progress = Arc::clone(&progress);
            let runtime_alias = alias.to_string();
            manager
                .download_and_register_eps_with_progress(
                    None,
                    move |ep_name: &str, percent: f64| {
                        let label = if ep_name.trim().is_empty() {
                            "Foundry Local runtime components".to_string()
                        } else {
                            format!("Foundry Local runtime component: {ep_name}")
                        };
                        runtime_progress.as_ref()(FoundryPrepareProgressPayload::runtime(
                            runtime_alias.clone(),
                            label,
                            percent,
                        ));
                    },
                )
                .await
                .context("download/register Foundry execution providers")?;
            progress.as_ref()(FoundryPrepareProgressPayload::runtime(
                alias,
                "Foundry Local runtime components",
                100.0,
            ));
            self.check_prepare_cancelled()?;

            let model = manager
                .catalog()
                .get_model(alias)
                .await
                .with_context(|| format!("get Foundry model {alias}"))?;

            let model_label = model_display_label(alias);
            if !model
                .is_cached()
                .await
                .context("check Foundry model cache")?
            {
                progress.as_ref()(FoundryPrepareProgressPayload::model(
                    alias,
                    model_label.clone(),
                    0.0,
                ));
                let model_progress = Arc::clone(&progress);
                let model_alias = alias.to_string();
                let model_label_for_progress = model_label.clone();
                model
                    .download(Some(move |percent: f64| {
                        model_progress.as_ref()(FoundryPrepareProgressPayload::model(
                            model_alias.clone(),
                            model_label_for_progress.clone(),
                            percent,
                        ));
                    }))
                    .await
                    .with_context(|| format!("download Foundry model {alias}"))?;
                progress.as_ref()(FoundryPrepareProgressPayload::model(
                    alias,
                    model_label.clone(),
                    100.0,
                ));
            } else {
                progress.as_ref()(FoundryPrepareProgressPayload::model(
                    alias,
                    format!("{model_label} already downloaded"),
                    100.0,
                ));
            }

            self.check_prepare_cancelled()?;
            progress.as_ref()(FoundryPrepareProgressPayload::load(
                alias,
                model_label.clone(),
                0.0,
            ));
            let model_id = model.id().to_string();
            if previous_loaded
                .as_ref()
                .is_some_and(|previous| previous.model_id == model_id)
            {
                progress.as_ref()(FoundryPrepareProgressPayload::load(
                    alias,
                    model_label.clone(),
                    100.0,
                ));
                let loaded = LoadedModel {
                    alias: alias.to_string(),
                    model_id,
                    model,
                };
                *self.state.lock() = RuntimeState {
                    manager: Some(manager),
                    loaded: Some(loaded.clone()),
                };
                progress.as_ref()(FoundryPrepareProgressPayload::finished(
                    alias,
                    format!("{model_label} ready"),
                ));
                return Ok(loaded);
            }

            let unloaded_previous = if let Some(previous) = previous_loaded.as_ref() {
                Self::unload_model(previous).await?;
                self.clear_loaded_if_model_id(&previous.model_id);
                Some(previous.clone())
            } else {
                None
            };
            if let Err(error) = self.check_prepare_cancelled() {
                self.rollback_prepare_error(manager, unloaded_previous.as_ref(), alias, error)
                    .await?;
            }
            if let Err(error) = model
                .load()
                .await
                .with_context(|| format!("load Foundry model {alias}"))
            {
                self.rollback_prepare_error(manager, unloaded_previous.as_ref(), alias, error)
                    .await?;
            }
            if self.cancel_prepare.load(Ordering::SeqCst) {
                if let Err(error) = model
                    .unload()
                    .await
                    .with_context(|| format!("unload cancelled Foundry model {alias}"))
                {
                    self.rollback_prepare_error(manager, unloaded_previous.as_ref(), alias, error)
                        .await?;
                }
                self.rollback_prepare_error(
                    manager,
                    unloaded_previous.as_ref(),
                    alias,
                    anyhow::anyhow!("Foundry Local Whisper prepare cancelled"),
                )
                .await?;
            }
            progress.as_ref()(FoundryPrepareProgressPayload::load(
                alias,
                model_label.clone(),
                100.0,
            ));

            let loaded = LoadedModel {
                alias: alias.to_string(),
                model_id,
                model,
            };
            *self.state.lock() = RuntimeState {
                manager: Some(manager),
                loaded: Some(loaded.clone()),
            };
            progress.as_ref()(FoundryPrepareProgressPayload::finished(
                alias,
                format!("{model_label} ready"),
            ));
            Ok(loaded)
        }

        async fn release_now_locked(&self) -> Result<()> {
            if let Some(loaded) = self.loaded_model_snapshot() {
                Self::unload_model(&loaded).await?;
                self.clear_loaded_if_model_id(&loaded.model_id);
            }
            Ok(())
        }

        async fn restore_loaded_model(
            &self,
            manager: &'static FoundryLocalManager,
            loaded: &LoadedModel,
        ) -> Result<()> {
            loaded
                .model
                .load()
                .await
                .with_context(|| format!("restore Foundry model {}", loaded.model_id))?;
            *self.state.lock() = RuntimeState {
                manager: Some(manager),
                loaded: Some(loaded.clone()),
            };
            Ok(())
        }

        async fn rollback_prepare_error(
            &self,
            manager: &'static FoundryLocalManager,
            previous: Option<&LoadedModel>,
            alias: &str,
            error: anyhow::Error,
        ) -> Result<()> {
            if let Some(previous) = previous {
                if let Err(restore_error) = self.restore_loaded_model(manager, previous).await {
                    return Err(error).with_context(|| {
                        format!(
                            "prepare Foundry model {alias} failed; also failed to restore previous Foundry model {}: {restore_error:#}",
                            previous.model_id
                        )
                    });
                }
            }
            Err(error)
        }

        fn cached_loaded_model(&self, alias: &str) -> Option<LoadedModel> {
            self.state
                .lock()
                .loaded
                .as_ref()
                .filter(|loaded| loaded.alias == alias)
                .cloned()
        }

        fn manager(&self) -> Result<&'static FoundryLocalManager> {
            if let Some(manager) = self.state.lock().manager {
                return Ok(manager);
            }

            let manager = FoundryLocalManager::create(self.manager_config())
                .context("initialize Foundry Local manager")?;
            self.state.lock().manager = Some(manager);
            Ok(manager)
        }

        fn manager_config(&self) -> FoundryLocalConfig {
            // OpenLess owns Windows App Runtime installation; keep the SDK bootstrapper non-interactive.
            let mut config =
                FoundryLocalConfig::new("openless").additional_setting("Bootstrap", "false");
            if let Ok(dir) = crate::persistence::foundry_app_data_root() {
                config = config.app_data_dir(dir.to_string_lossy().to_string());
            }
            if let Ok(dir) = crate::persistence::foundry_model_cache_root() {
                config = config.model_cache_dir(dir.to_string_lossy().to_string());
            }
            if let Ok(dir) = crate::persistence::foundry_logs_root() {
                config = config.logs_dir(dir.to_string_lossy().to_string());
            }
            let runtime_dir = foundry_native::runtime_dir().ok();
            let candidates = foundry_native_dir_candidates(runtime_dir.as_deref());
            if let Some(native_dir) = select_foundry_native_dir(candidates) {
                config = config.library_path(native_dir.to_string_lossy().to_string());
            }
            config
        }

        fn loaded_model_snapshot(&self) -> Option<LoadedModel> {
            self.state.lock().loaded.clone()
        }

        fn loaded_for_different_alias(&self, alias: &str) -> Option<LoadedModel> {
            self.state
                .lock()
                .loaded
                .as_ref()
                .filter(|loaded| loaded.alias != alias)
                .cloned()
        }

        fn clear_loaded_if_model_id(&self, model_id: &str) {
            let mut state = self.state.lock();
            if state
                .loaded
                .as_ref()
                .is_some_and(|loaded| loaded.model_id == model_id)
            {
                state.loaded.take();
            }
        }

        async fn unload_model(loaded: &LoadedModel) -> Result<()> {
            loaded
                .model
                .unload()
                .await
                .with_context(|| format!("unload Foundry model {}", loaded.model_id))?;
            Ok(())
        }

        fn check_prepare_cancelled(&self) -> Result<()> {
            if self.cancel_prepare.load(Ordering::SeqCst) {
                anyhow::bail!("Foundry Local Whisper prepare cancelled");
            }
            Ok(())
        }
    }

    fn model_display_label(alias: &str) -> String {
        MODELS
            .iter()
            .find(|model| model.alias == alias)
            .map(|model| model.display_name.to_string())
            .unwrap_or_else(|| alias.to_string())
    }

    fn normalized_language_hint(language_hint: Option<&str>) -> Option<String> {
        language_hint
            .map(str::trim)
            .filter(|hint| !hint.is_empty())
            .map(str::to_string)
    }

    fn foundry_native_dir_candidates(runtime_dir: Option<&Path>) -> Vec<PathBuf> {
        let mut candidates = Vec::new();

        if let Some(runtime_dir) = runtime_dir {
            candidates.push(runtime_dir.to_path_buf());
        }

        candidates
    }

    fn select_foundry_native_dir(candidates: Vec<PathBuf>) -> Option<PathBuf> {
        candidates
            .into_iter()
            .find(|dir| dir.join("Microsoft.AI.Foundry.Local.Core.dll").exists())
    }

    #[cfg(test)]
    mod lifecycle_tests {
        use super::{
            foundry_native_dir_candidates, normalized_language_hint, select_foundry_native_dir,
            FoundryLocalRuntime,
        };
        use std::fs;

        #[test]
        fn runtime_has_async_lifecycle_gate() {
            let runtime = FoundryLocalRuntime::new();

            assert!(runtime.lifecycle.try_lock().is_ok());
        }

        #[test]
        fn runtime_normalizes_language_hint_before_audio_client() {
            assert_eq!(
                normalized_language_hint(Some(" zh ")),
                Some("zh".to_string())
            );
            assert_eq!(normalized_language_hint(Some("")), None);
            assert_eq!(normalized_language_hint(None), None);
        }

        #[test]
        fn runtime_finds_downloaded_foundry_native_runtime_dir() {
            let root = std::env::temp_dir().join(format!(
                "openless-foundry-native-test-{}",
                uuid::Uuid::new_v4()
            ));
            let native_dir = root.join("runtime");
            fs::create_dir_all(&native_dir).unwrap();
            fs::write(
                native_dir.join("Microsoft.AI.Foundry.Local.Core.dll"),
                b"placeholder",
            )
            .unwrap();

            let candidates = foundry_native_dir_candidates(Some(native_dir.as_path()));

            assert_eq!(select_foundry_native_dir(candidates).unwrap(), native_dir);

            fs::remove_dir_all(root).unwrap();
        }
    }
}

#[cfg(target_os = "windows")]
pub use imp::FoundryLocalRuntime;

#[cfg(not(target_os = "windows"))]
pub struct FoundryLocalRuntime;

#[cfg(not(target_os = "windows"))]
impl Default for FoundryLocalRuntime {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(not(target_os = "windows"))]
impl FoundryLocalRuntime {
    pub fn new() -> Self {
        Self
    }

    pub async fn status_snapshot(
        &self,
        active_model: &str,
        runtime_source: &str,
    ) -> super::foundry::FoundryRuntimeStatus {
        let mut status = super::foundry::FoundryRuntimeStatus::unavailable(
            active_model.to_string(),
            "Foundry Local Whisper is only available on Windows",
        );
        status.runtime_source = super::foundry_native::normalize_runtime_source_str(runtime_source);
        status
    }

    pub async fn ensure_loaded(
        &self,
        alias: &str,
        _runtime_source: &str,
    ) -> anyhow::Result<String> {
        anyhow::bail!("Foundry Local Whisper is only available on Windows: {alias}");
    }

    pub async fn ensure_loaded_with_progress<F>(
        &self,
        alias: &str,
        _runtime_source: &str,
        _progress: F,
    ) -> anyhow::Result<String>
    where
        F: Fn(super::foundry::FoundryPrepareProgressPayload) + Send + Sync + 'static,
    {
        anyhow::bail!("Foundry Local Whisper is only available on Windows: {alias}");
    }

    pub fn request_cancel_prepare(&self) {}

    pub async fn catalog_snapshot(
        &self,
    ) -> anyhow::Result<Vec<super::foundry::FoundryCatalogModel>> {
        Ok(super::foundry::static_catalog_models())
    }

    pub async fn transcribe_audio_file(
        &self,
        alias: &str,
        _runtime_source: &str,
        _language_hint: Option<&str>,
        _audio_path: &std::path::Path,
        _audio_timeout: std::time::Duration,
    ) -> anyhow::Result<String> {
        anyhow::bail!("Foundry Local Whisper is only available on Windows: {alias}");
    }

    pub async fn release_now(&self) -> anyhow::Result<()> {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::FoundryLocalRuntime;

    #[tokio::test]
    async fn new_runtime_reports_native_audio_status_shape() {
        let runtime = FoundryLocalRuntime::new();
        let status = runtime.status_snapshot("whisper-small", "auto").await;

        assert_eq!(status.provider_id, crate::asr::local::foundry::PROVIDER_ID);
        assert_eq!(status.active_model, "whisper-small");
        assert_eq!(status.loaded_model_id, None);
        assert_eq!(status.endpoint, None);
        if status.available {
            assert_eq!(status.error, None);
        } else {
            assert!(status.error.is_some());
        }
    }

    #[tokio::test]
    async fn new_runtime_release_now_has_real_async_unload_contract() {
        let runtime = FoundryLocalRuntime::new();

        runtime.release_now().await.unwrap();

        let status = runtime.status_snapshot("whisper-small", "auto").await;
        assert_eq!(status.loaded_model_id, None);
    }
}
