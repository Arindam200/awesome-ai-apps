use std::collections::{HashMap, HashSet};
use std::fs::{self, File};
use std::io::{BufReader, Read};
use std::path::{Component, Path, PathBuf};
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use bzip2::read::BzDecoder;
use futures_util::StreamExt;
use reqwest::Url;
use sha2::{Digest, Sha256};
use tokio::io::AsyncWriteExt;

use super::paths;
use super::types::{
    ModelDownloadSource, ModelManifest, ModelManifestFile, MODEL_ID, VAD_FILE_NAME,
};

const DEFAULT_SOURCE_ID: &str = "github-release";
const MAX_MODEL_ARCHIVE_BYTES: u64 = 2 * 1024 * 1024 * 1024;
const VAD_DOWNLOAD_EXTRA_BYTES: u64 = 1024 * 1024;
const MANIFEST_JSON: &str =
    include_str!("../../../resources/asr-models/fire-red-asr2-ctc-zh-en-int8.json");
static DOWNLOAD_INSTALL_LOCK: OnceLock<tokio::sync::Mutex<()>> = OnceLock::new();

pub fn bundled_manifest() -> Result<ModelManifest> {
    serde_json::from_str(MANIFEST_JSON).context("parse bundled Qingyu ASR model manifest")
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn validate_file_bytes(file: &ModelManifestFile, bytes: &[u8]) -> Result<()> {
    let actual_size = bytes.len() as u64;
    if actual_size != file.size {
        anyhow::bail!(
            "{} size mismatch: expected {}, got {}",
            file.path,
            file.size,
            actual_size
        );
    }

    let actual_hash = sha256_hex(bytes);
    if !actual_hash.eq_ignore_ascii_case(&file.sha256) {
        anyhow::bail!(
            "{} sha256 mismatch: expected {}, got {}",
            file.path,
            file.sha256,
            actual_hash
        );
    }

    Ok(())
}

pub fn source_by_id(
    manifest: &ModelManifest,
    source_id: Option<&str>,
    custom_base_url: Option<&str>,
) -> Result<ModelDownloadSource> {
    if let Some(base_url) = custom_base_url {
        return Ok(ModelDownloadSource {
            id: "custom".into(),
            label: "自定义源".into(),
            base_url: normalize_base_url(base_url)?,
        });
    }

    let id = source_id
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or(DEFAULT_SOURCE_ID);
    let source = manifest
        .sources
        .iter()
        .find(|source| source.id == id)
        .cloned()
        .with_context(|| format!("download source not found: {id}"))?;
    Ok(ModelDownloadSource {
        base_url: normalize_base_url(&source.base_url)?,
        ..source
    })
}

fn normalize_base_url(base_url: &str) -> Result<String> {
    let trimmed = base_url.trim();
    if trimmed.is_empty() {
        anyhow::bail!("download source base URL is empty");
    }

    let mut url =
        Url::parse(trimmed).with_context(|| format!("invalid download source URL: {trimmed}"))?;
    match url.scheme() {
        "http" | "https" => {}
        scheme => anyhow::bail!("download source URL scheme is not allowed: {scheme}"),
    }
    if url.host_str().is_none() {
        anyhow::bail!("download source URL must include a host");
    }
    if url.query().is_some() {
        anyhow::bail!("download source URL must not include query parameters");
    }
    if url.fragment().is_some() {
        anyhow::bail!("download source URL must not include a fragment");
    }
    url.set_query(None);
    url.set_fragment(None);
    Ok(url.as_str().trim_end_matches('/').to_string())
}

pub async fn download_and_install(source: ModelDownloadSource) -> Result<()> {
    let _guard = download_install_mutex().lock().await;
    download_and_install_locked(source).await
}

pub async fn delete_installed_model() -> Result<()> {
    let _guard = download_install_mutex().lock().await;
    let root = paths::production_model_root()?;
    tokio::task::spawn_blocking(move || match fs::remove_dir_all(&root) {
        Ok(()) => Ok(()),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(err) => Err(err).with_context(|| {
            format!(
                "delete Qingyu ASR model directory failed: {}",
                root.display()
            )
        }),
    })
    .await
    .context("delete Qingyu ASR model task failed")?
}

fn download_install_mutex() -> &'static tokio::sync::Mutex<()> {
    DOWNLOAD_INSTALL_LOCK.get_or_init(|| tokio::sync::Mutex::new(()))
}

async fn download_and_install_locked(source: ModelDownloadSource) -> Result<()> {
    let manifest = bundled_manifest()?;
    let root = paths::production_model_root()?;
    fs::create_dir_all(&root)
        .with_context(|| format!("create ASR model root failed: {}", root.display()))?;
    let staging = tempfile::Builder::new()
        .prefix(".qingyu-asr-staging-")
        .tempdir_in(&root)
        .with_context(|| format!("create ASR model staging dir failed: {}", root.display()))?;

    let client = build_client()?;
    let archive_name = format!("{MODEL_ID}.tar.bz2");
    let archive_url = artifact_url(&source, &archive_name);
    let archive_path = staging.path().join(&archive_name);
    download_to_file(
        &client,
        &archive_url,
        &archive_path,
        MAX_MODEL_ARCHIVE_BYTES,
        "model archive",
    )
    .await
    .with_context(|| format!("download model archive failed: {archive_url}"))?;
    let archive_path_for_extract = archive_path.clone();
    let staging_path_for_extract = staging.path().to_path_buf();
    let manifest_for_extract = manifest.clone();
    tokio::task::spawn_blocking(move || {
        extract_tar_bz2(
            &archive_path_for_extract,
            &staging_path_for_extract,
            &manifest_for_extract,
        )
    })
    .await
    .context("extract model archive task failed")?
    .context("extract model archive failed")?;

    let vad_file = manifest
        .files
        .iter()
        .find(|file| file.path == VAD_FILE_NAME)
        .context("bundled manifest missing VAD file entry")?;
    let vad_url = artifact_url(&source, VAD_FILE_NAME);
    let vad_limit = vad_file.size.saturating_add(VAD_DOWNLOAD_EXTRA_BYTES);
    let vad_bytes = download_bytes(&client, &vad_url, vad_limit, "VAD model")
        .await
        .with_context(|| format!("download VAD failed: {vad_url}"))?;
    validate_file_bytes(vad_file, &vad_bytes)?;
    fs::write(staging.path().join(VAD_FILE_NAME), vad_bytes)
        .with_context(|| format!("write staged VAD failed: {}", VAD_FILE_NAME))?;

    let staging_path_for_install = staging.path().to_path_buf();
    let root_for_install = root.clone();
    let manifest_for_install = manifest.clone();
    tokio::task::spawn_blocking(move || {
        validate_manifest_files(&manifest_for_install, &staging_path_for_install)?;
        install_staged_files(&staging_path_for_install, &root_for_install)
    })
    .await
    .context("install model task failed")?
}

fn build_client() -> Result<reqwest::Client> {
    reqwest::Client::builder()
        .user_agent(concat!("OpenLess/", env!("CARGO_PKG_VERSION")))
        .connect_timeout(std::time::Duration::from_secs(30))
        .build()
        .context("build model download HTTP client failed")
}

fn artifact_url(source: &ModelDownloadSource, file_name: &str) -> String {
    format!("{}/{}", source.base_url.trim_end_matches('/'), file_name)
}

async fn download_to_file(
    client: &reqwest::Client,
    url: &str,
    path: &Path,
    max_bytes: u64,
    label: &str,
) -> Result<()> {
    let response = client
        .get(url)
        .send()
        .await
        .with_context(|| format!("HTTP GET failed: {url}"))?;
    if !response.status().is_success() {
        anyhow::bail!("HTTP {} for {url}", response.status());
    }
    reject_oversized_content_length(response.content_length(), max_bytes, label, url)?;

    let mut file = tokio::fs::File::create(path)
        .await
        .with_context(|| format!("create download file failed: {}", path.display()))?;
    let mut stream = response.bytes_stream();
    let mut downloaded = 0u64;
    while let Some(chunk) = stream.next().await {
        let chunk = chunk.context("read download stream chunk failed")?;
        downloaded = downloaded
            .checked_add(chunk.len() as u64)
            .context("download byte count overflow")?;
        if downloaded > max_bytes {
            anyhow::bail!(
                "{label} download exceeded size limit: limit {} bytes, got at least {} bytes ({url})",
                max_bytes,
                downloaded
            );
        }
        file.write_all(&chunk)
            .await
            .with_context(|| format!("write download file failed: {}", path.display()))?;
    }
    file.flush().await.ok();
    Ok(())
}

async fn download_bytes(
    client: &reqwest::Client,
    url: &str,
    max_bytes: u64,
    label: &str,
) -> Result<Vec<u8>> {
    let response = client
        .get(url)
        .send()
        .await
        .with_context(|| format!("HTTP GET failed: {url}"))?;
    if !response.status().is_success() {
        anyhow::bail!("HTTP {} for {url}", response.status());
    }
    reject_oversized_content_length(response.content_length(), max_bytes, label, url)?;

    let mut bytes = Vec::new();
    let mut stream = response.bytes_stream();
    let mut downloaded = 0u64;
    while let Some(chunk) = stream.next().await {
        let chunk = chunk.context("read download stream chunk failed")?;
        downloaded = downloaded
            .checked_add(chunk.len() as u64)
            .context("download byte count overflow")?;
        if downloaded > max_bytes {
            anyhow::bail!(
                "{label} download exceeded size limit: limit {} bytes, got at least {} bytes ({url})",
                max_bytes,
                downloaded
            );
        }
        bytes.extend_from_slice(&chunk);
    }
    Ok(bytes)
}

fn reject_oversized_content_length(
    content_length: Option<u64>,
    max_bytes: u64,
    label: &str,
    url: &str,
) -> Result<()> {
    if let Some(content_length) = content_length {
        if content_length > max_bytes {
            anyhow::bail!(
                "{label} content length exceeds size limit: limit {} bytes, content-length {} bytes ({url})",
                max_bytes,
                content_length
            );
        }
    }
    Ok(())
}

fn extract_tar_bz2(archive_path: &Path, dest: &Path, manifest: &ModelManifest) -> Result<()> {
    let file = File::open(archive_path)
        .with_context(|| format!("open archive failed: {}", archive_path.display()))?;
    let decoder = BzDecoder::new(file);
    extract_model_files_from_tar_reader(decoder, dest, manifest)
}

fn extract_model_files_from_tar_reader<R: Read>(
    reader: R,
    dest: &Path,
    manifest: &ModelManifest,
) -> Result<()> {
    let model_files: HashMap<String, &ModelManifestFile> = manifest
        .files
        .iter()
        .filter(|file| file.path != VAD_FILE_NAME)
        .map(|file| (file.path.clone(), file))
        .collect();
    let max_extract_bytes = model_files
        .values()
        .try_fold(0u64, |sum, file| sum.checked_add(file.size))
        .context("manifest model size overflow")?;

    let mut archive = tar::Archive::new(reader);
    let mut extracted = HashSet::new();
    let mut extracted_bytes = 0u64;

    for entry in archive.entries().context("read archive entries failed")? {
        let mut entry = entry.context("read archive entry failed")?;
        let entry_path = archive_entry_path(&entry)?;
        ensure_relative_safe_path(&entry_path)?;
        let entry_type = entry.header().entry_type();

        if entry_type.is_dir() {
            continue;
        }
        if !entry_type.is_file() {
            anyhow::bail!(
                "unsupported archive entry type for {}: {:?}",
                entry_path,
                entry_type
            );
        }

        let Some(manifest_file) = model_files.get(&entry_path) else {
            continue;
        };
        if !extracted.insert(entry_path.clone()) {
            anyhow::bail!("duplicate archive entry for manifest file: {entry_path}");
        }

        let header_size = entry
            .header()
            .size()
            .with_context(|| format!("read archive header size failed: {entry_path}"))?;
        if header_size != manifest_file.size {
            anyhow::bail!(
                "{} archive size mismatch: manifest {}, header {}",
                entry_path,
                manifest_file.size,
                header_size
            );
        }
        extracted_bytes = extracted_bytes
            .checked_add(header_size)
            .context("archive extracted byte count overflow")?;
        if extracted_bytes > max_extract_bytes {
            anyhow::bail!(
                "archive extracted bytes exceeded manifest limit: limit {}, got {}",
                max_extract_bytes,
                extracted_bytes
            );
        }

        let output_path = manifest_file_path(dest, manifest_file)?;
        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent).with_context(|| {
                format!("create model file parent failed: {}", parent.display())
            })?;
        }
        let mut output = File::create(&output_path)
            .with_context(|| format!("create model file failed: {}", output_path.display()))?;
        let copied = std::io::copy(&mut entry, &mut output)
            .with_context(|| format!("write model file failed: {}", output_path.display()))?;
        if copied != manifest_file.size {
            anyhow::bail!(
                "{} extracted size mismatch: expected {}, got {}",
                entry_path,
                manifest_file.size,
                copied
            );
        }
    }

    for path in model_files.keys() {
        if !extracted.contains(path) {
            anyhow::bail!("archive missing manifest file: {path}");
        }
    }

    Ok(())
}

fn archive_entry_path<R: Read>(entry: &tar::Entry<'_, R>) -> Result<String> {
    let path = entry.path().context("read archive entry path failed")?;
    let path = path
        .to_str()
        .with_context(|| format!("archive entry path is not UTF-8: {}", path.display()))?;
    if path.contains('\\') {
        anyhow::bail!("archive entry path contains backslash: {path}");
    }
    Ok(path.trim_end_matches('/').to_string())
}

fn validate_manifest_files(manifest: &ModelManifest, root: &Path) -> Result<()> {
    for file in &manifest.files {
        let path = manifest_file_path(root, file)?;
        validate_file_on_disk(file, &path)?;
    }
    Ok(())
}

fn manifest_file_path(root: &Path, file: &ModelManifestFile) -> Result<PathBuf> {
    ensure_relative_safe_path(&file.path)?;
    Ok(root.join(Path::new(&file.path)))
}

fn ensure_relative_safe_path(path: &str) -> Result<()> {
    let relative_path = Path::new(path);
    if path.trim().is_empty()
        || path.contains(':')
        || path.contains('\\')
        || relative_path.is_absolute()
        || relative_path
            .components()
            .any(|component| matches!(component, Component::ParentDir | Component::Prefix(_)))
    {
        anyhow::bail!("path must be relative and stay within model root: {path}");
    }
    Ok(())
}

fn validate_file_on_disk(file: &ModelManifestFile, path: &Path) -> Result<()> {
    let metadata = fs::metadata(path)
        .with_context(|| format!("manifest file missing: {} ({})", file.path, path.display()))?;
    if !metadata.is_file() {
        anyhow::bail!("manifest entry is not a file: {}", file.path);
    }
    if metadata.len() != file.size {
        anyhow::bail!(
            "{} size mismatch: expected {}, got {}",
            file.path,
            file.size,
            metadata.len()
        );
    }

    let actual_hash = sha256_file(path)?;
    if !actual_hash.eq_ignore_ascii_case(&file.sha256) {
        anyhow::bail!(
            "{} sha256 mismatch: expected {}, got {}",
            file.path,
            file.sha256,
            actual_hash
        );
    }

    Ok(())
}

fn sha256_file(path: &Path) -> Result<String> {
    let file =
        File::open(path).with_context(|| format!("open file for sha256: {}", path.display()))?;
    let mut reader = BufReader::new(file);
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 1024 * 1024];
    loop {
        let read = reader
            .read(&mut buffer)
            .with_context(|| format!("read file for sha256: {}", path.display()))?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn install_staged_files(staging_root: &Path, root: &Path) -> Result<()> {
    let staged_model_dir = staging_root.join(MODEL_ID);
    let staged_vad = staging_root.join(VAD_FILE_NAME);
    if !staged_model_dir.is_dir() {
        anyhow::bail!(
            "staged model directory missing: {}",
            staged_model_dir.display()
        );
    }
    if !staged_vad.is_file() {
        anyhow::bail!("staged VAD file missing: {}", staged_vad.display());
    }

    let dest_model_dir = root.join(MODEL_ID);
    let dest_vad = root.join(VAD_FILE_NAME);
    let backup_suffix = backup_suffix();
    let backup_model_dir = root.join(format!("{MODEL_ID}{backup_suffix}"));
    let backup_vad = root.join(format!("{VAD_FILE_NAME}{backup_suffix}"));

    let mut backups: Vec<(PathBuf, PathBuf)> = Vec::new();
    let mut installed_model = false;
    let mut installed_vad = false;

    let install_result = (|| -> Result<()> {
        if move_existing(&dest_model_dir, &backup_model_dir)? {
            backups.push((backup_model_dir.clone(), dest_model_dir.clone()));
        }
        if move_existing(&dest_vad, &backup_vad)? {
            backups.push((backup_vad.clone(), dest_vad.clone()));
        }
        fs::rename(&staged_model_dir, &dest_model_dir).with_context(|| {
            format!(
                "install model directory failed: {} -> {}",
                staged_model_dir.display(),
                dest_model_dir.display()
            )
        })?;
        installed_model = true;
        fs::rename(&staged_vad, &dest_vad).with_context(|| {
            format!(
                "install VAD file failed: {} -> {}",
                staged_vad.display(),
                dest_vad.display()
            )
        })?;
        installed_vad = true;
        Ok(())
    })();

    if let Err(error) = install_result {
        if installed_model {
            let _ = remove_path_if_exists(&dest_model_dir);
        }
        if installed_vad {
            let _ = remove_path_if_exists(&dest_vad);
        }
        for (backup, dest) in backups.iter().rev() {
            let _ = restore_backup(backup, dest);
        }
        return Err(error);
    }

    for (backup, _) in backups {
        let _ = remove_path_if_exists(&backup);
    }
    Ok(())
}

fn backup_suffix() -> String {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0);
    format!(".backup-{}-{millis}", std::process::id())
}

fn move_existing(path: &Path, backup: &Path) -> Result<bool> {
    if path.exists() {
        fs::rename(path, backup).with_context(|| {
            format!(
                "backup existing install failed: {} -> {}",
                path.display(),
                backup.display()
            )
        })?;
        return Ok(true);
    }
    Ok(false)
}

fn restore_backup(backup: &Path, dest: &Path) -> Result<()> {
    if backup.exists() {
        fs::rename(backup, dest).with_context(|| {
            format!(
                "restore install backup failed: {} -> {}",
                backup.display(),
                dest.display()
            )
        })?;
    }
    Ok(())
}

fn remove_path_if_exists(path: &Path) -> std::io::Result<()> {
    if !path.exists() {
        return Ok(());
    }
    if path.is_dir() {
        fs::remove_dir_all(path)
    } else {
        fs::remove_file(path)
    }
}

#[cfg(test)]
mod tests {
    use super::{
        bundled_manifest, extract_model_files_from_tar_reader, normalize_base_url, sha256_hex,
        source_by_id, validate_file_bytes,
    };
    use crate::asr::qingyu::types::{
        ModelDownloadSource, ModelManifest, ModelManifestFile, MODEL_ID,
    };
    use std::io::Cursor;

    #[test]
    fn bundled_manifest_has_sources_and_files() {
        let manifest = bundled_manifest().expect("bundled manifest parses");

        assert_eq!(manifest.model_id, MODEL_ID);
        assert_eq!(manifest.version, "2026-02-25");
        assert_eq!(manifest.files.len(), 3);
        assert!(manifest.files.iter().any(|file| {
            file.path.ends_with("model.int8.onnx")
                && file.size == 775_861_420
                && file.sha256 == "ca3dbabd82170110cc0b343c2890866d449984bc9cd92b9a18371ff80a81bb99"
        }));
        assert!(manifest.files.iter().any(|file| {
            file.path.ends_with("tokens.txt")
                && file.size == 79_172
                && file.sha256 == "1bc613de2112d257e61a349c3e72d1b1a9cf19c33d3ca954197ad2171e5ea07b"
        }));
        assert!(manifest.files.iter().any(|file| {
            file.path == "silero_vad.onnx"
                && file.size == 643_854
                && file.sha256 == "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6"
        }));
        assert!(manifest
            .sources
            .iter()
            .any(|source| source.id == "github-release"));
    }

    #[test]
    fn custom_source_overrides_manifest_source() {
        let manifest = manifest_with_source();

        let source = source_by_id(
            &manifest,
            Some("github-release"),
            Some(" https://mirror.example/asr/ "),
        )
        .expect("custom source selected");

        assert_eq!(source.id, "custom");
        assert_eq!(source.label, "自定义源");
        assert_eq!(source.base_url, "https://mirror.example/asr");
    }

    #[test]
    fn normalize_base_url_rejects_unsafe_or_non_base_urls() {
        assert_eq!(
            normalize_base_url(" https://mirror.example/asr/ ").unwrap(),
            "https://mirror.example/asr"
        );
        assert!(normalize_base_url("").is_err());
        assert!(normalize_base_url("file:///tmp/asr").is_err());
        assert!(normalize_base_url("https://mirror.example/asr?token=1").is_err());
        assert!(normalize_base_url("https://mirror.example/asr#models").is_err());

        let manifest = manifest_with_source();
        assert!(source_by_id(&manifest, Some("github-release"), Some("  ")).is_err());
    }

    #[test]
    fn extract_model_files_from_tar_reader_skips_non_manifest_regular_files() {
        let manifest = manifest_with_files(vec![ModelManifestFile {
            path: "model-dir/model.int8.onnx".into(),
            size: 5,
            sha256: sha256_hex(b"model"),
        }]);
        let tar_bytes = tar_with_files(&[
            ("model-dir/model.int8.onnx", b"model".as_slice()),
            ("model-dir/README.md", b"skip".as_slice()),
        ]);
        let dir = tempfile::tempdir().unwrap();

        extract_model_files_from_tar_reader(Cursor::new(tar_bytes), dir.path(), &manifest)
            .expect("safe archive extracts");

        assert_eq!(
            std::fs::read(dir.path().join("model-dir/model.int8.onnx")).unwrap(),
            b"model"
        );
        assert!(!dir.path().join("model-dir/README.md").exists());
    }

    #[test]
    fn extract_model_files_from_tar_reader_rejects_symlinks() {
        let manifest = manifest_with_files(vec![ModelManifestFile {
            path: "model-dir/model.int8.onnx".into(),
            size: 5,
            sha256: sha256_hex(b"model"),
        }]);
        let tar_bytes = tar_with_symlink("model-dir/model.int8.onnx", "outside");
        let dir = tempfile::tempdir().unwrap();

        let error =
            extract_model_files_from_tar_reader(Cursor::new(tar_bytes), dir.path(), &manifest)
                .expect_err("symlink rejected");

        assert!(error.to_string().contains("unsupported archive entry"));
    }

    #[test]
    fn validate_file_bytes_rejects_size_mismatch() {
        let file = ModelManifestFile {
            path: "tiny.bin".into(),
            size: 3,
            sha256: "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824".into(),
        };

        let error = validate_file_bytes(&file, b"hello").expect_err("size mismatch rejected");

        assert!(error.to_string().contains("size mismatch"));
    }

    #[test]
    fn validate_file_bytes_rejects_hash_mismatch() {
        let file = ModelManifestFile {
            path: "hello.txt".into(),
            size: 5,
            sha256: "0000000000000000000000000000000000000000000000000000000000000000".into(),
        };

        let error = validate_file_bytes(&file, b"hello").expect_err("hash mismatch rejected");

        assert!(error.to_string().contains("sha256 mismatch"));
    }

    fn manifest_with_source() -> ModelManifest {
        ModelManifest {
            model_id: MODEL_ID.into(),
            version: "test".into(),
            files: Vec::new(),
            sources: vec![ModelDownloadSource {
                id: "github-release".into(),
                label: "官方 GitHub 源".into(),
                base_url: "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"
                    .into(),
            }],
        }
    }

    fn manifest_with_files(files: Vec<ModelManifestFile>) -> ModelManifest {
        ModelManifest {
            model_id: MODEL_ID.into(),
            version: "test".into(),
            files,
            sources: Vec::new(),
        }
    }

    fn tar_with_files(files: &[(&str, &[u8])]) -> Vec<u8> {
        let mut builder = tar::Builder::new(Vec::new());
        for (path, bytes) in files {
            let mut header = tar::Header::new_gnu();
            header.set_size(bytes.len() as u64);
            header.set_mode(0o644);
            header.set_cksum();
            builder
                .append_data(&mut header, *path, Cursor::new(*bytes))
                .unwrap();
        }
        builder.finish().unwrap();
        builder.into_inner().unwrap()
    }

    fn tar_with_symlink(path: &str, target: &str) -> Vec<u8> {
        let mut builder = tar::Builder::new(Vec::new());
        let mut header = tar::Header::new_gnu();
        header.set_entry_type(tar::EntryType::Symlink);
        header.set_size(0);
        header.set_mode(0o777);
        header.set_cksum();
        builder.append_link(&mut header, path, target).unwrap();
        builder.finish().unwrap();
        builder.into_inner().unwrap()
    }
}
