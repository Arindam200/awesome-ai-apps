use std::path::{Path, PathBuf};

use anyhow::{Context, Result};

use super::types::{QingyuAsrModelSource, MODEL_ID, VAD_FILE_NAME};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PreferredModelLocation {
    pub model_dir: PathBuf,
    pub source: QingyuAsrModelSource,
}

pub fn dev_model_root() -> Option<PathBuf> {
    dev_model_root_from_anchors(runtime_anchors())
}

fn runtime_anchors() -> Vec<PathBuf> {
    let mut anchors = Vec::new();
    if let Ok(current_dir) = std::env::current_dir() {
        anchors.push(current_dir);
    }
    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(exe_dir) = current_exe.parent() {
            anchors.push(exe_dir.to_path_buf());
        }
    }
    anchors
}

pub(crate) fn dev_model_root_from_anchors<I, P>(anchors: I) -> Option<PathBuf>
where
    I: IntoIterator<Item = P>,
    P: AsRef<Path>,
{
    anchors
        .into_iter()
        .flat_map(|anchor| {
            anchor
                .as_ref()
                .ancestors()
                .map(Path::to_path_buf)
                .collect::<Vec<_>>()
        })
        .find_map(|ancestor| {
            if !is_development_checkout_root(&ancestor) {
                return None;
            }
            let candidate = ancestor.join("openless-asr");
            if development_model_is_complete(&candidate) {
                Some(candidate)
            } else {
                None
            }
        })
}

fn is_development_checkout_root(root: &Path) -> bool {
    root.join("openless-all")
        .join("app")
        .join("src-tauri")
        .join("Cargo.toml")
        .is_file()
}

fn development_model_is_complete(root: &Path) -> bool {
    let model_dir = model_dir_from_root(root);
    model_dir.join("model.int8.onnx").is_file() && model_dir.join("tokens.txt").is_file()
}

pub fn production_model_root() -> Result<PathBuf> {
    Ok(production_data_dir()?.join("models").join("asr"))
}

#[cfg(target_os = "windows")]
fn production_data_dir() -> Result<PathBuf> {
    production_data_dir_from_appdata(Some(std::env::var("APPDATA").context("APPDATA not set")?))
}

#[cfg(target_os = "windows")]
fn production_data_dir_from_appdata(appdata: Option<String>) -> Result<PathBuf> {
    let appdata = appdata.context("APPDATA not set")?;
    Ok(PathBuf::from(appdata).join(crate::product::DATA_DIR_NAME))
}

#[cfg(target_os = "macos")]
fn production_data_dir() -> Result<PathBuf> {
    production_data_dir_from_home(Some(std::env::var("HOME").context("HOME not set")?))
}

#[cfg(target_os = "macos")]
fn production_data_dir_from_home(home: Option<String>) -> Result<PathBuf> {
    let home = home.context("HOME not set")?;
    Ok(PathBuf::from(home)
        .join("Library")
        .join("Application Support")
        .join(crate::product::DATA_DIR_NAME))
}

#[cfg(all(unix, not(target_os = "macos")))]
fn production_data_dir() -> Result<PathBuf> {
    let xdg_data_home = std::env::var("XDG_DATA_HOME").ok();
    let home = if xdg_data_home
        .as_deref()
        .map(|xdg| !xdg.is_empty())
        .unwrap_or(false)
    {
        None
    } else {
        Some(std::env::var("HOME").context("HOME not set")?)
    };
    production_data_dir_from_unix_env(xdg_data_home, home)
}

#[cfg(all(unix, not(target_os = "macos")))]
fn production_data_dir_from_unix_env(
    xdg_data_home: Option<String>,
    home: Option<String>,
) -> Result<PathBuf> {
    if let Some(xdg_data_home) = xdg_data_home.filter(|value| !value.is_empty()) {
        return Ok(PathBuf::from(xdg_data_home).join(crate::product::DATA_DIR_NAME));
    }

    let home = home.context("HOME not set")?;
    Ok(PathBuf::from(home)
        .join(".local")
        .join("share")
        .join(crate::product::DATA_DIR_NAME))
}

#[cfg(test)]
mod tests {
    use super::{model_dir_from_root, preferred_model_location_from_parts, MODEL_ID};
    use crate::asr::qingyu::types::QingyuAsrModelSource;

    #[cfg(target_os = "windows")]
    use super::production_data_dir_from_appdata;
    #[cfg(target_os = "macos")]
    use super::production_data_dir_from_home;
    #[cfg(all(unix, not(target_os = "macos")))]
    use super::production_data_dir_from_unix_env;

    #[cfg(target_os = "windows")]
    #[test]
    fn production_model_root_requires_platform_data_env() {
        assert!(production_data_dir_from_appdata(None).is_err());
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn production_model_root_requires_platform_data_env() {
        assert!(production_data_dir_from_home(None).is_err());
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    #[test]
    fn production_model_root_requires_platform_data_env() {
        assert!(production_data_dir_from_unix_env(None, None).is_err());
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn macos_data_dir_uses_application_support() {
        let dir = production_data_dir_from_home(Some("/Users/example".into())).unwrap();

        assert_eq!(
            dir,
            std::path::PathBuf::from("/Users/example")
                .join("Library")
                .join("Application Support")
                .join(crate::product::DATA_DIR_NAME)
        );
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    #[test]
    fn unix_data_dir_prefers_xdg_data_home() {
        let dir =
            production_data_dir_from_unix_env(Some("/xdg/data".into()), Some("/home/me".into()))
                .unwrap();

        assert_eq!(
            dir,
            std::path::PathBuf::from("/xdg/data").join(crate::product::DATA_DIR_NAME)
        );
    }

    #[test]
    fn preferred_model_location_uses_repo_development_model_when_available() {
        let temp = tempfile::tempdir().unwrap();
        let repo = temp.path().join("repo");
        let anchor = repo
            .join("openless-all")
            .join("app")
            .join(".artifacts")
            .join("windows-msvc")
            .join("portable");
        std::fs::create_dir_all(repo.join("openless-all").join("app").join("src-tauri")).unwrap();
        std::fs::write(
            repo.join("openless-all")
                .join("app")
                .join("src-tauri")
                .join("Cargo.toml"),
            b"[package]\n",
        )
        .unwrap();
        std::fs::create_dir_all(&anchor).unwrap();

        let dev_root = repo.join("openless-asr");
        let dev_model_dir = model_dir_from_root(&dev_root);
        std::fs::create_dir_all(&dev_model_dir).unwrap();
        std::fs::write(dev_model_dir.join("model.int8.onnx"), b"model").unwrap();
        std::fs::write(dev_model_dir.join("tokens.txt"), b"tokens").unwrap();
        let production_root = temp.path().join("appdata").join("models").join("asr");

        let location = preferred_model_location_from_parts([anchor], production_root);

        assert_eq!(location.model_dir, dev_model_dir);
        assert_eq!(location.source, QingyuAsrModelSource::Development);
    }

    #[test]
    fn preferred_model_location_uses_production_when_development_model_is_incomplete() {
        let temp = tempfile::tempdir().unwrap();
        let repo = temp.path().join("repo");
        let anchor = repo.join("openless-all").join("app");
        std::fs::create_dir_all(repo.join("openless-all").join("app").join("src-tauri")).unwrap();
        std::fs::write(
            repo.join("openless-all")
                .join("app")
                .join("src-tauri")
                .join("Cargo.toml"),
            b"[package]\n",
        )
        .unwrap();
        std::fs::create_dir_all(model_dir_from_root(repo.join("openless-asr"))).unwrap();
        let production_root = temp.path().join("appdata").join("models").join("asr");

        let location = preferred_model_location_from_parts([anchor], production_root.clone());

        assert_eq!(
            location.model_dir,
            production_root.join(MODEL_ID).join(MODEL_ID)
        );
        assert_eq!(location.source, QingyuAsrModelSource::Production);
    }
}

pub fn model_dir_from_root(root: impl AsRef<Path>) -> PathBuf {
    root.as_ref().join(MODEL_ID).join(MODEL_ID)
}

pub fn model_root_from_model_dir(model_dir: impl AsRef<Path>) -> Option<PathBuf> {
    model_dir.as_ref().parent()?.parent().map(Path::to_path_buf)
}

pub fn vad_path_from_model_dir(model_dir: impl AsRef<Path>) -> Option<PathBuf> {
    model_root_from_model_dir(model_dir).map(|root| root.join(VAD_FILE_NAME))
}

pub fn preferred_model_dir() -> Result<PathBuf> {
    Ok(preferred_model_location()?.model_dir)
}

pub fn preferred_model_location() -> Result<PreferredModelLocation> {
    if let Some(dev_root) = dev_model_root() {
        return Ok(PreferredModelLocation {
            model_dir: model_dir_from_root(dev_root),
            source: QingyuAsrModelSource::Development,
        });
    }

    Ok(PreferredModelLocation {
        model_dir: model_dir_from_root(production_model_root()?),
        source: QingyuAsrModelSource::Production,
    })
}

pub(crate) fn preferred_model_location_from_parts<I, P>(
    anchors: I,
    production_root: PathBuf,
) -> PreferredModelLocation
where
    I: IntoIterator<Item = P>,
    P: AsRef<Path>,
{
    if let Some(dev_root) = dev_model_root_from_anchors(anchors) {
        return PreferredModelLocation {
            model_dir: model_dir_from_root(dev_root),
            source: QingyuAsrModelSource::Development,
        };
    }

    PreferredModelLocation {
        model_dir: model_dir_from_root(production_root),
        source: QingyuAsrModelSource::Production,
    }
}
