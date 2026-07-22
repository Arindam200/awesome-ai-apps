//! Temporary system-output mute while recording.

pub struct AudioMuteGuard {
    inner: Option<platform::PlatformMuteGuard>,
}

impl AudioMuteGuard {
    pub fn activate() -> Result<Self, String> {
        Ok(Self {
            inner: Some(platform::activate()?),
        })
    }
}

impl Drop for AudioMuteGuard {
    fn drop(&mut self) {
        if let Some(inner) = self.inner.take() {
            inner.restore();
        }
    }
}

#[cfg(target_os = "windows")]
mod platform {
    use windows::Win32::Foundation::{BOOL, RPC_E_CHANGED_MODE};
    use windows::Win32::Media::Audio::Endpoints::IAudioEndpointVolume;
    use windows::Win32::Media::Audio::{
        eConsole, eRender, IMMDeviceEnumerator, MMDeviceEnumerator,
    };
    use windows::Win32::System::Com::{
        CoCreateInstance, CoInitializeEx, CoUninitialize, CLSCTX_ALL, COINIT_APARTMENTTHREADED,
    };

    pub struct PlatformMuteGuard {
        was_muted: bool,
    }

    pub fn activate() -> Result<PlatformMuteGuard, String> {
        let was_muted = endpoint_muted()?;
        if !was_muted {
            set_endpoint_muted(true)?;
        }
        Ok(PlatformMuteGuard { was_muted })
    }

    impl PlatformMuteGuard {
        pub fn restore(self) {
            if let Err(err) = set_endpoint_muted(self.was_muted) {
                log::warn!("[audio-mute] restore endpoint mute failed: {err}");
            }
        }
    }

    fn endpoint_muted() -> Result<bool, String> {
        with_endpoint_volume(|endpoint| unsafe {
            let muted = endpoint
                .GetMute()
                .map_err(|e| format!("read endpoint mute state failed: {e}"))?;
            Ok(muted.as_bool())
        })
    }

    fn set_endpoint_muted(muted: bool) -> Result<(), String> {
        with_endpoint_volume(|endpoint| unsafe {
            endpoint
                .SetMute(BOOL(muted as i32), std::ptr::null())
                .map_err(|e| format!("set endpoint mute failed: {e}"))
        })
    }

    fn with_endpoint_volume<T>(
        f: impl FnOnce(&IAudioEndpointVolume) -> Result<T, String>,
    ) -> Result<T, String> {
        unsafe {
            let hr = CoInitializeEx(None, COINIT_APARTMENTTHREADED);
            let uninit_com = hr.is_ok();
            if !hr.is_ok() && hr != RPC_E_CHANGED_MODE {
                return Err(format!("CoInitializeEx failed: {hr:?}"));
            }

            let result = (|| {
                let enumerator: IMMDeviceEnumerator =
                    CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL)
                        .map_err(|e| format!("create audio device enumerator failed: {e}"))?;
                let device = enumerator
                    .GetDefaultAudioEndpoint(eRender, eConsole)
                    .map_err(|e| format!("get default render endpoint failed: {e}"))?;
                let endpoint: IAudioEndpointVolume = device
                    .Activate(CLSCTX_ALL, None)
                    .map_err(|e| format!("activate endpoint volume failed: {e}"))?;
                f(&endpoint)
            })();

            if uninit_com {
                CoUninitialize();
            }
            result
        }
    }
}

#[cfg(target_os = "macos")]
mod platform {
    use std::process::Command;

    pub struct PlatformMuteGuard {
        was_muted: bool,
    }

    pub fn activate() -> Result<PlatformMuteGuard, String> {
        let was_muted = output_muted()?;
        if !was_muted {
            set_output_muted(true)?;
        }
        Ok(PlatformMuteGuard { was_muted })
    }

    impl PlatformMuteGuard {
        pub fn restore(self) {
            if let Err(err) = set_output_muted(self.was_muted) {
                log::warn!("[audio-mute] restore output mute failed: {err}");
            }
        }
    }

    fn output_muted() -> Result<bool, String> {
        let output = Command::new("osascript")
            .args(["-e", "output muted of (get volume settings)"])
            .output()
            .map_err(|e| format!("query output mute failed: {e}"))?;
        if !output.status.success() {
            return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
        }
        Ok(String::from_utf8_lossy(&output.stdout).trim() == "true")
    }

    fn set_output_muted(muted: bool) -> Result<(), String> {
        let script = if muted {
            "set volume output muted true"
        } else {
            "set volume output muted false"
        };
        let output = Command::new("osascript")
            .args(["-e", script])
            .output()
            .map_err(|e| format!("set output mute failed: {e}"))?;
        if output.status.success() {
            Ok(())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).trim().to_string())
        }
    }
}

#[cfg(target_os = "linux")]
mod platform {
    use std::process::Command;

    enum Backend {
        Wpctl,
        Pactl,
    }

    pub struct PlatformMuteGuard {
        backend: Backend,
        was_muted: bool,
    }

    pub fn activate() -> Result<PlatformMuteGuard, String> {
        if let Ok(was_muted) = wpctl_output_muted() {
            if !was_muted {
                wpctl_set_output_muted(true)?;
            }
            return Ok(PlatformMuteGuard {
                backend: Backend::Wpctl,
                was_muted,
            });
        }

        let was_muted = pactl_output_muted()?;
        if !was_muted {
            pactl_set_output_muted(true)?;
        }
        Ok(PlatformMuteGuard {
            backend: Backend::Pactl,
            was_muted,
        })
    }

    impl PlatformMuteGuard {
        pub fn restore(self) {
            let result = match self.backend {
                Backend::Wpctl => wpctl_set_output_muted(self.was_muted),
                Backend::Pactl => pactl_set_output_muted(self.was_muted),
            };
            if let Err(err) = result {
                log::warn!("[audio-mute] restore output mute failed: {err}");
            }
        }
    }

    fn wpctl_output_muted() -> Result<bool, String> {
        let output = Command::new("wpctl")
            .args(["get-volume", "@DEFAULT_AUDIO_SINK@"])
            .output()
            .map_err(|e| format!("wpctl get-volume failed: {e}"))?;
        if !output.status.success() {
            return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
        }
        Ok(String::from_utf8_lossy(&output.stdout).contains("[MUTED]"))
    }

    fn wpctl_set_output_muted(muted: bool) -> Result<(), String> {
        let value = if muted { "1" } else { "0" };
        let output = Command::new("wpctl")
            .args(["set-mute", "@DEFAULT_AUDIO_SINK@", value])
            .output()
            .map_err(|e| format!("wpctl set-mute failed: {e}"))?;
        if output.status.success() {
            Ok(())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).trim().to_string())
        }
    }

    fn pactl_output_muted() -> Result<bool, String> {
        let output = Command::new("pactl")
            .args(["get-sink-mute", "@DEFAULT_SINK@"])
            .output()
            .map_err(|e| format!("pactl get-sink-mute failed: {e}"))?;
        if !output.status.success() {
            return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
        }
        let stdout = String::from_utf8_lossy(&output.stdout).to_ascii_lowercase();
        Ok(stdout.contains("yes") || stdout.contains("是"))
    }

    fn pactl_set_output_muted(muted: bool) -> Result<(), String> {
        let value = if muted { "1" } else { "0" };
        let output = Command::new("pactl")
            .args(["set-sink-mute", "@DEFAULT_SINK@", value])
            .output()
            .map_err(|e| format!("pactl set-sink-mute failed: {e}"))?;
        if output.status.success() {
            Ok(())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).trim().to_string())
        }
    }
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
mod platform {
    pub struct PlatformMuteGuard;

    pub fn activate() -> Result<PlatformMuteGuard, String> {
        Err("output mute is not supported on this platform".to_string())
    }

    impl PlatformMuteGuard {
        pub fn restore(self) {}
    }
}
