#[cfg(target_os = "windows")]
mod imp {
    use std::fs;
    use std::io::{self, Read};
    use std::os::windows::process::CommandExt;
    use std::path::{Path, PathBuf};
    use std::process::Command;
    use std::time::Duration;

    use anyhow::{Context, Result};
    use serde_json::Value;
    use tokio::task;

    const NUGET_FEED_INDEX: &str = "https://api.nuget.org/v3/index.json";
    const ORT_NIGHTLY_FEED_INDEX: &str =
        "https://pkgs.dev.azure.com/aiinfra/PublicPackages/_packaging/ORT-Nightly/nuget/v3/index.json";
    const TARGET_RID_NATIVE_PREFIX: &str = "runtimes/win-x64/native/";
    const CORE_DLL: &str = "Microsoft.AI.Foundry.Local.Core.dll";
    const REQUIRED_DLLS: &[&str] = &[CORE_DLL, "onnxruntime.dll", "onnxruntime-genai.dll"];
    const WINDOWS_APP_RUNTIME_INSTALLER_URL: &str =
        "https://aka.ms/windowsappsdk/1.8/1.8.260416003/windowsappruntimeinstall-x64.exe";
    const WINDOWS_APP_RUNTIME_INSTALLER_FILE: &str = "WindowsAppRuntimeInstall-x64.exe";
    const WINDOWS_APP_RUNTIME_MANUAL_STEPS: &str =
        "Install Windows App SDK Runtime 1.8 x64 manually from https://aka.ms/windowsappsdk/1.8/1.8.260416003/windowsappruntimeinstall-x64.exe. On x64 Windows it must register x86+x64 Framework/DDLM packages and x64 Main/Singleton packages for the current user. If this PC is managed by an organization, enable MSIX/sideloading policy or ask IT to provision the runtime.";
    const WINDOWS_APP_RUNTIME_PROGRESS_START: f64 = 0.0;
    const WINDOWS_APP_RUNTIME_PROGRESS_END: f64 = 20.0;
    const NATIVE_RUNTIME_PROGRESS_START: f64 = WINDOWS_APP_RUNTIME_PROGRESS_END;
    const NATIVE_RUNTIME_PROGRESS_END: f64 = 98.0;
    const CREATE_NO_WINDOW: u32 = 0x08000000;

    #[derive(Debug)]
    struct CommandCapture {
        status_code: Option<i32>,
        stdout: String,
        stderr: String,
    }

    impl CommandCapture {
        fn success(&self) -> bool {
            self.status_code == Some(0)
        }
    }

    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum RuntimeSource {
        Auto,
        Nuget,
        OrtNightly,
    }

    impl RuntimeSource {
        pub fn as_str(self) -> &'static str {
            match self {
                RuntimeSource::Auto => "auto",
                RuntimeSource::Nuget => "nuget",
                RuntimeSource::OrtNightly => "ort-nightly",
            }
        }
    }

    struct NativePackage {
        name: &'static str,
        version: &'static str,
        expected_file: &'static str,
    }

    const PACKAGES: &[NativePackage] = &[
        NativePackage {
            name: "Microsoft.AI.Foundry.Local.Core.WinML",
            version: "1.0.0",
            expected_file: CORE_DLL,
        },
        NativePackage {
            name: "Microsoft.ML.OnnxRuntime.Foundry",
            version: "1.23.2.3",
            expected_file: "onnxruntime.dll",
        },
        NativePackage {
            name: "Microsoft.ML.OnnxRuntimeGenAI.Foundry",
            version: "0.13.2",
            expected_file: "onnxruntime-genai.dll",
        },
    ];

    pub fn normalize_runtime_source(value: &str) -> RuntimeSource {
        match value.trim() {
            "nuget" => RuntimeSource::Nuget,
            "ort-nightly" => RuntimeSource::OrtNightly,
            _ => RuntimeSource::Auto,
        }
    }

    pub fn normalize_runtime_source_str(value: &str) -> String {
        normalize_runtime_source(value).as_str().to_string()
    }

    pub fn feed_indexes_for_runtime_source(source: RuntimeSource) -> Vec<&'static str> {
        match source {
            RuntimeSource::Auto => vec![NUGET_FEED_INDEX, ORT_NIGHTLY_FEED_INDEX],
            RuntimeSource::Nuget => vec![NUGET_FEED_INDEX],
            RuntimeSource::OrtNightly => vec![ORT_NIGHTLY_FEED_INDEX],
        }
    }

    pub fn native_package_url(base_address: &str, package_name: &str, version: &str) -> String {
        let base = if base_address.ends_with('/') {
            base_address.to_string()
        } else {
            format!("{base_address}/")
        };
        let lower_name = package_name.to_lowercase();
        let lower_version = version.to_lowercase();
        format!("{base}{lower_name}/{lower_version}/{lower_name}.{lower_version}.nupkg")
    }

    pub fn runtime_dir() -> Result<PathBuf> {
        crate::persistence::foundry_native_runtime_root()
    }

    pub fn runtime_ready() -> bool {
        runtime_dir()
            .map(|dir| required_libraries_present(&dir))
            .unwrap_or(false)
    }

    pub async fn ensure_runtime<F>(source: RuntimeSource, progress: F) -> Result<PathBuf>
    where
        F: Fn(&str, f64),
    {
        let (windows_start, windows_end) = windows_app_runtime_progress_range();
        ensure_windows_app_runtime(&progress, windows_start, windows_end).await?;

        let target_dir = runtime_dir()?;
        if required_libraries_present(&target_dir) {
            progress("Foundry Local 运行组件已下载", 100.0);
            return Ok(target_dir);
        }

        let parent = target_dir
            .parent()
            .context("resolve Foundry native runtime parent")?;
        fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;

        let staging_dir = parent.join(".runtime-download");
        if staging_dir.exists() {
            fs::remove_dir_all(&staging_dir)
                .with_context(|| format!("remove stale {}", staging_dir.display()))?;
        }
        fs::create_dir_all(&staging_dir)
            .with_context(|| format!("create {}", staging_dir.display()))?;

        let client = reqwest::Client::new();
        let (native_start, native_end) = native_runtime_progress_range();
        let native_span = native_end - native_start;
        for (index, package) in PACKAGES.iter().enumerate() {
            let start_percent = native_start + (index as f64 / PACKAGES.len() as f64) * native_span;
            let end_percent =
                native_start + ((index + 1) as f64 / PACKAGES.len() as f64) * native_span;
            let label = format!("下载 Foundry 运行组件：{}", package.name);
            progress(&label, start_percent);

            download_package_with_fallbacks(&client, package, source, &staging_dir).await?;

            if !staging_dir.join(package.expected_file).exists() {
                anyhow::bail!(
                    "Foundry 运行组件缺少 {} from {} {}",
                    package.expected_file,
                    package.name,
                    package.version
                );
            }
            progress(&label, end_percent);
        }

        if !required_libraries_present(&staging_dir) {
            anyhow::bail!("Foundry 运行组件下载不完整");
        }

        if target_dir.exists() {
            fs::remove_dir_all(&target_dir)
                .with_context(|| format!("remove {}", target_dir.display()))?;
        }
        fs::rename(&staging_dir, &target_dir).with_context(|| {
            format!("move {} to {}", staging_dir.display(), target_dir.display())
        })?;
        progress("Foundry Local 运行组件已下载", 100.0);
        Ok(target_dir)
    }

    fn windows_app_runtime_progress_range() -> (f64, f64) {
        (
            WINDOWS_APP_RUNTIME_PROGRESS_START,
            WINDOWS_APP_RUNTIME_PROGRESS_END,
        )
    }

    fn native_runtime_progress_range() -> (f64, f64) {
        (NATIVE_RUNTIME_PROGRESS_START, NATIVE_RUNTIME_PROGRESS_END)
    }

    async fn download_package_with_fallbacks(
        client: &reqwest::Client,
        package: &NativePackage,
        source: RuntimeSource,
        out_dir: &Path,
    ) -> Result<()> {
        let mut last_error: Option<anyhow::Error> = None;
        for feed_index in feed_indexes_for_runtime_source(source) {
            match download_package_from_feed(client, package, feed_index, out_dir).await {
                Ok(()) => return Ok(()),
                Err(error) => {
                    log::warn!(
                        "[foundry-asr] download {} {} from {} failed: {error:#}",
                        package.name,
                        package.version,
                        feed_index
                    );
                    last_error = Some(error);
                }
            }
        }

        match last_error {
            Some(error) => Err(error).with_context(|| {
                format!(
                    "下载 Foundry 运行组件失败：{} {}",
                    package.name, package.version
                )
            }),
            None => anyhow::bail!("没有可用的 Foundry 运行组件下载源"),
        }
    }

    async fn download_package_from_feed(
        client: &reqwest::Client,
        package: &NativePackage,
        feed_index: &str,
        out_dir: &Path,
    ) -> Result<()> {
        let base_address = resolve_package_base_address(client, feed_index).await?;
        let url = native_package_url(&base_address, package.name, package.version);
        let bytes = client
            .get(&url)
            .send()
            .await
            .with_context(|| format!("GET {url}"))?
            .error_for_status()
            .with_context(|| format!("HTTP error for {url}"))?
            .bytes()
            .await
            .with_context(|| format!("read {url}"))?;

        let nupkg_path = out_dir.join(format!(
            "{}-{}.nupkg",
            package.name.to_lowercase(),
            package.version
        ));
        fs::write(&nupkg_path, &bytes)
            .with_context(|| format!("write {}", nupkg_path.display()))?;
        let extracted = extract_native_libraries_from_nupkg(&nupkg_path, out_dir)?;
        fs::remove_file(&nupkg_path).ok();
        if extracted == 0 {
            anyhow::bail!("NuGet 包里没有找到 win-x64 native DLL: {url}");
        }
        Ok(())
    }

    async fn ensure_windows_app_runtime<F>(
        progress: &F,
        start_percent: f64,
        end_percent: f64,
    ) -> Result<()>
    where
        F: Fn(&str, f64),
    {
        let before_probe = run_windows_app_runtime_probe().await;
        if matches!(before_probe.as_ref(), Ok(capture) if capture.success()) {
            return Ok(());
        }
        log_windows_app_runtime_probe("before install", &before_probe);

        progress(
            "下载 Windows App Runtime 1.8（Foundry Local 依赖）",
            start_percent,
        );
        let installer_dir = crate::persistence::foundry_local_root()?.join("windows-app-runtime");
        fs::create_dir_all(&installer_dir)
            .with_context(|| format!("create {}", installer_dir.display()))?;
        let installer_path = installer_dir.join(WINDOWS_APP_RUNTIME_INSTALLER_FILE);

        let bytes = reqwest::Client::new()
            .get(WINDOWS_APP_RUNTIME_INSTALLER_URL)
            .send()
            .await
            .context("download Windows App Runtime installer")?
            .error_for_status()
            .context("download Windows App Runtime installer failed")?
            .bytes()
            .await
            .context("read Windows App Runtime installer")?;
        fs::write(&installer_path, &bytes)
            .with_context(|| format!("write {}", installer_path.display()))?;

        progress(
            "安装 Windows App Runtime 1.8",
            (start_percent + end_percent) / 2.0,
        );
        let install_path = installer_path.clone();
        let install_output = task::spawn_blocking(move || {
            let mut command = Command::new(&install_path);
            command.args(["--quiet", "--force"]);
            command.creation_flags(CREATE_NO_WINDOW);
            command.output()
        })
        .await
        .context("join Windows App Runtime installer task")?
        .with_context(|| format!("run {}", installer_path.display()))?;
        fs::remove_file(&installer_path).ok();

        let install_capture = CommandCapture {
            status_code: install_output.status.code(),
            stdout: decode_command_output(&install_output.stdout),
            stderr: decode_command_output(&install_output.stderr),
        };
        log_command_capture("Windows App Runtime installer", &install_capture);

        if !wait_for_windows_app_runtime_ready().await {
            let after_probe = run_windows_app_runtime_probe().await;
            log_windows_app_runtime_probe("after install", &after_probe);
            if install_capture.success() {
                log::warn!(
                    "[foundry-asr] Windows App Runtime installer exited successfully, but the package probe did not confirm the complete current-user package set. Continuing with the Foundry SDK bootstrapper disabled; if Foundry fails later, use the probe diagnostics in openless.log. {}",
                    WINDOWS_APP_RUNTIME_MANUAL_STEPS
                );
                progress(
                    "Windows App Runtime 1.8 安装器已完成（验证结果见日志）",
                    end_percent,
                );
                return Ok(());
            }
            anyhow::bail!(
                "Windows App Runtime 1.8 is still unavailable after automatic installation. OpenLess stopped before starting Foundry Local to avoid the Windows bootstrapper dialog. Installer exit code: {}. {} See openless.log for installer output, package list, OS build, and elevation diagnostics.",
                format_exit_code(install_capture.status_code),
                WINDOWS_APP_RUNTIME_MANUAL_STEPS
            );
        }
        progress("Windows App Runtime 1.8 已安装", end_percent);
        Ok(())
    }

    async fn wait_for_windows_app_runtime_ready() -> bool {
        for _ in 0..20 {
            if windows_app_runtime_ready().await {
                return true;
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
        }
        false
    }

    fn windows_app_runtime_detection_script() -> &'static str {
        r#"
$min = [version]'1.8.1.0'
$pkgs = @(Get-AppxPackage -Name '*AppRuntime*' -ErrorAction SilentlyContinue)
function Test-Package($NamePattern, $Architecture, $IsFramework) {
    return @($pkgs | Where-Object {
        $_.Name -match $NamePattern `
            -and "$($_.Architecture)" -ieq $Architecture `
            -and [version]$_.Version -ge $min `
            -and "$($_.Status)" -eq 'Ok' `
            -and $_.IsPartiallyStaged -ne $true `
            -and ([bool]$_.IsFramework -eq $IsFramework)
    }).Count -gt 0
}
$checks = [ordered]@{
    frameworkX86 = Test-Package '^Microsoft\.WindowsAppRuntime\.1\.8$' 'X86' $true
    frameworkX64 = Test-Package '^Microsoft\.WindowsAppRuntime\.1\.8$' 'X64' $true
    mainX64 = Test-Package '^MicrosoftCorporationII\.(WinAppRuntime|WindowsAppRuntime)\.Main\.1\.8$' 'X64' $false
    singletonX64 = Test-Package '^(MicrosoftCorporationII\.(WinAppRuntime|WindowsAppRuntime)\.Singleton|Microsoft\.WindowsAppRuntime\.Singleton)$' 'X64' $false
    ddlmX86 = Test-Package '^Microsoft\.WinAppRuntime\.DDLM\..*-x8$' 'X86' $false
    ddlmX64 = Test-Package '^Microsoft\.WinAppRuntime\.DDLM\..*-x6$' 'X64' $false
}
$readyForFoundryX64 = $checks.frameworkX64 -and $checks.mainX64 -and $checks.singletonX64 -and $checks.ddlmX64
$completeX64MachineRuntime = $checks.frameworkX86 -and $readyForFoundryX64 -and $checks.ddlmX86
$isElevated = $false
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]$identity
    $isElevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} catch {}
$allUsersPackages = @()
$allUsersError = $null
try {
    $allUsersPackages = @(Get-AppxPackage -AllUsers -Name '*AppRuntime*' -ErrorAction Stop | Select-Object -First 80 Name, Architecture, Version, PackageFamilyName, PackageFullName, IsFramework, IsPartiallyStaged, SignatureKind, Status)
} catch {
    $allUsersError = $_.Exception.Message
}
$diagnostics = [ordered]@{
    ready = $readyForFoundryX64
    readyForFoundryX64 = $readyForFoundryX64
    completeX64MachineRuntime = $completeX64MachineRuntime
    minMsixPackageVersion = $min.ToString()
    osVersion = [Environment]::OSVersion.Version.ToString()
    is64BitOperatingSystem = [Environment]::Is64BitOperatingSystem
    is64BitProcess = [Environment]::Is64BitProcess
    processArchitecture = $env:PROCESSOR_ARCHITECTURE
    processArchitectureW6432 = $env:PROCESSOR_ARCHITEW6432
    isElevated = $isElevated
    checks = $checks
    currentUserPackages = @($pkgs | Select-Object -First 80 Name, Architecture, Version, PackageFamilyName, PackageFullName, IsFramework, IsPartiallyStaged, SignatureKind, Status)
    allUsersPackages = $allUsersPackages
    allUsersError = $allUsersError
}
$diagnostics | ConvertTo-Json -Compress -Depth 6
if ($readyForFoundryX64) { exit 0 } else { exit 1 }
"#
    }

    pub async fn windows_app_runtime_ready() -> bool {
        run_windows_app_runtime_probe()
            .await
            .map(|capture| capture.success())
            .unwrap_or(false)
    }

    async fn run_windows_app_runtime_probe() -> Result<CommandCapture> {
        run_powershell_script(windows_app_runtime_detection_script()).await
    }

    async fn run_powershell_script(script: &'static str) -> Result<CommandCapture> {
        task::spawn_blocking(move || {
            let mut command = Command::new("powershell.exe");
            command.args([
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ]);
            command.creation_flags(CREATE_NO_WINDOW);
            let output = command.output().context("run powershell.exe")?;
            Ok(CommandCapture {
                status_code: output.status.code(),
                stdout: decode_command_output(&output.stdout),
                stderr: decode_command_output(&output.stderr),
            })
        })
        .await
        .context("join PowerShell task")?
    }

    fn decode_command_output(bytes: &[u8]) -> String {
        String::from_utf8_lossy(bytes).trim().to_string()
    }

    fn log_windows_app_runtime_probe(stage: &str, result: &Result<CommandCapture>) {
        match result {
            Ok(capture) => {
                log_command_capture(&format!("Windows App Runtime probe ({stage})"), capture)
            }
            Err(error) => {
                log::warn!("[foundry-asr] Windows App Runtime probe ({stage}) failed: {error:#}");
            }
        }
    }

    fn log_command_capture(label: &str, capture: &CommandCapture) {
        let level = if capture.success() {
            log::Level::Info
        } else {
            log::Level::Warn
        };
        log::log!(
            level,
            "[foundry-asr] {label} exited code={} stdout={} stderr={}",
            format_exit_code(capture.status_code),
            compact_log_text(&capture.stdout),
            compact_log_text(&capture.stderr)
        );
    }

    fn format_exit_code(code: Option<i32>) -> String {
        match code {
            Some(value) => format!("0x{:08X}", value as u32),
            None => "unknown".to_string(),
        }
    }

    fn compact_log_text(value: &str) -> String {
        const MAX_LOG_CHARS: usize = 6000;
        let compact = value.split_whitespace().collect::<Vec<_>>().join(" ");
        if compact.chars().count() <= MAX_LOG_CHARS {
            compact
        } else {
            let truncated: String = compact.chars().take(MAX_LOG_CHARS).collect();
            format!("{truncated}...(truncated)")
        }
    }

    async fn resolve_package_base_address(
        client: &reqwest::Client,
        feed_index: &str,
    ) -> Result<String> {
        let value: Value = client
            .get(feed_index)
            .send()
            .await
            .with_context(|| format!("GET {feed_index}"))?
            .error_for_status()
            .with_context(|| format!("HTTP error for {feed_index}"))?
            .json()
            .await
            .with_context(|| format!("decode NuGet feed index {feed_index}"))?;

        let resources = value["resources"]
            .as_array()
            .context("NuGet feed index missing resources")?;
        for resource in resources {
            let resource_type = resource["@type"].as_str().unwrap_or("");
            if resource_type == "PackageBaseAddress/3.0.0" {
                if let Some(id) = resource["@id"].as_str() {
                    return Ok(id.to_string());
                }
            }
        }
        anyhow::bail!("NuGet feed index missing PackageBaseAddress: {feed_index}");
    }

    fn required_libraries_present(dir: &Path) -> bool {
        REQUIRED_DLLS.iter().all(|dll| dir.join(dll).exists())
    }

    pub fn extract_native_libraries_from_nupkg(nupkg: &Path, out_dir: &Path) -> Result<usize> {
        let bytes = fs::read(nupkg).with_context(|| format!("read {}", nupkg.display()))?;
        extract_native_libraries(io::Cursor::new(bytes), out_dir)
    }

    fn extract_native_libraries<R: Read + io::Seek>(reader: R, out_dir: &Path) -> Result<usize> {
        let mut archive = zip::ZipArchive::new(reader).context("open nupkg zip")?;
        let mut extracted = 0usize;
        for index in 0..archive.len() {
            let mut file = archive.by_index(index).context("read zip entry")?;
            let name = file.name().to_string();
            if !name.starts_with(TARGET_RID_NATIVE_PREFIX) || !name.ends_with(".dll") {
                continue;
            }
            let Some(file_name) = Path::new(&name).file_name() else {
                continue;
            };
            let dest = out_dir.join(file_name);
            let mut out_file =
                fs::File::create(&dest).with_context(|| format!("create {}", dest.display()))?;
            io::copy(&mut file, &mut out_file)
                .with_context(|| format!("write {}", dest.display()))?;
            extracted += 1;
        }
        Ok(extracted)
    }

    #[cfg(test)]
    mod tests {
        use std::fs;
        use std::io::Write;
        use zip::write::SimpleFileOptions;

        use super::super::{
            extract_native_libraries_from_nupkg, feed_indexes_for_runtime_source,
            native_package_url, normalize_runtime_source, RuntimeSource,
        };

        #[test]
        fn runtime_source_auto_tries_nuget_before_ort_nightly() {
            assert_eq!(normalize_runtime_source(""), RuntimeSource::Auto);
            assert_eq!(normalize_runtime_source("unknown"), RuntimeSource::Auto);

            let feeds = feed_indexes_for_runtime_source(RuntimeSource::Auto);

            assert_eq!(feeds[0], "https://api.nuget.org/v3/index.json");
            assert_eq!(
                feeds[1],
                "https://pkgs.dev.azure.com/aiinfra/PublicPackages/_packaging/ORT-Nightly/nuget/v3/index.json"
            );
        }

        #[test]
        fn native_package_url_uses_lowercase_nuget_id_and_version() {
            let url = native_package_url(
                "https://example.test/packages/",
                "Microsoft.AI.Foundry.Local.Core.WinML",
                "1.0.0",
            );

            assert_eq!(
                url,
                "https://example.test/packages/microsoft.ai.foundry.local.core.winml/1.0.0/microsoft.ai.foundry.local.core.winml.1.0.0.nupkg"
            );
        }

        #[test]
        fn windows_app_runtime_detection_requires_complete_package_set() {
            let script = super::windows_app_runtime_detection_script();

            assert!(script.contains("Microsoft\\.WindowsAppRuntime\\.1\\.8"));
            assert!(script.contains("frameworkX86"));
            assert!(script.contains("frameworkX64"));
            assert!(script.contains("readyForFoundryX64"));
            assert!(script.contains("completeX64MachineRuntime"));
            assert!(script.contains("Main\\.1\\.8"));
            assert!(script.contains("Singleton"));
            assert!(script.contains("ddlmX86"));
            assert!(script.contains("ddlmX64"));
            assert!(script.contains("1.8.1.0"));
            assert!(script.contains("PackageFamilyName"));
            assert!(script.contains("IsFramework"));
        }

        #[test]
        fn runtime_prepare_progress_starts_with_windows_app_runtime() {
            let windows_runtime = super::windows_app_runtime_progress_range();
            let native_runtime = super::native_runtime_progress_range();

            assert_eq!(windows_runtime, (0.0, 20.0));
            assert!(native_runtime.0 >= windows_runtime.1);
            assert_eq!(native_runtime.1, 98.0);
        }

        #[test]
        fn extract_native_libraries_only_keeps_target_rid_dlls() {
            let root = std::env::temp_dir().join(format!(
                "openless-foundry-native-zip-test-{}",
                uuid::Uuid::new_v4()
            ));
            let nupkg = root.join("package.nupkg");
            let out = root.join("out");
            fs::create_dir_all(&root).unwrap();
            fs::create_dir_all(&out).unwrap();

            {
                let file = fs::File::create(&nupkg).unwrap();
                let mut zip = zip::ZipWriter::new(file);
                let options = SimpleFileOptions::default();
                zip.start_file(
                    "runtimes/win-x64/native/Microsoft.AI.Foundry.Local.Core.dll",
                    options,
                )
                .unwrap();
                zip.write_all(b"core").unwrap();
                zip.start_file("runtimes/linux-x64/native/libignored.so", options)
                    .unwrap();
                zip.write_all(b"ignored").unwrap();
                zip.start_file("tools/not-native.dll", options).unwrap();
                zip.write_all(b"ignored").unwrap();
                zip.finish().unwrap();
            }

            let extracted = extract_native_libraries_from_nupkg(&nupkg, &out).unwrap();

            assert_eq!(extracted, 1);
            assert!(out.join("Microsoft.AI.Foundry.Local.Core.dll").exists());
            assert!(!out.join("libignored.so").exists());
            assert!(!out.join("not-native.dll").exists());

            fs::remove_dir_all(root).unwrap();
        }
    }
}

#[cfg(target_os = "windows")]
pub use imp::*;

#[cfg(not(target_os = "windows"))]
pub fn normalize_runtime_source_str(value: &str) -> String {
    match value.trim() {
        "nuget" => "nuget".into(),
        "ort-nightly" => "ort-nightly".into(),
        _ => "auto".into(),
    }
}
