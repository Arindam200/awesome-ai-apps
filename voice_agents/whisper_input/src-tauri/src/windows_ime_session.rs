use crate::types::InsertStatus;
use crate::windows_ime_ipc::{ImeSubmitRequest, WindowsImeIpcServer};
use crate::windows_ime_profile::{
    restore_decision, ImeProfileSnapshot, ProfileRestoreDecision, WindowsImeProfileManager,
};
use crate::windows_ime_protocol::ImeSubmitStatus;

#[derive(Debug)]
pub enum WindowsImeSessionError {
    Profile(String),
    Ipc(String),
}

impl std::fmt::Display for WindowsImeSessionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Profile(message) | Self::Ipc(message) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for WindowsImeSessionError {}

pub fn map_ime_status_to_insert_status(status: ImeSubmitStatus) -> InsertStatus {
    match status {
        ImeSubmitStatus::Committed => InsertStatus::Inserted,
        ImeSubmitStatus::Rejected | ImeSubmitStatus::Failed => InsertStatus::CopiedFallback,
    }
}

pub fn should_fallback_after_ime_result(status: ImeSubmitStatus) -> bool {
    !matches!(status, ImeSubmitStatus::Committed)
}

#[derive(Debug)]
pub struct PreparedWindowsImeSession {
    saved_profile: Option<ImeProfileSnapshot>,
    openless_activated: bool,
}

impl PreparedWindowsImeSession {
    pub fn unavailable() -> Self {
        Self {
            saved_profile: None,
            openless_activated: false,
        }
    }

    pub fn activation_failed(saved_profile: ImeProfileSnapshot) -> Self {
        Self {
            saved_profile: Some(saved_profile),
            openless_activated: false,
        }
    }

    pub fn is_ready_for_tsf_submit(&self) -> bool {
        self.has_saved_profile() && self.openless_was_activated()
    }

    pub fn has_saved_profile(&self) -> bool {
        self.saved_profile.is_some()
    }

    pub fn openless_was_activated(&self) -> bool {
        self.openless_activated
    }

    pub fn should_restore_when_active_profile_check_fails(&self) -> bool {
        self.has_saved_profile()
    }

    pub fn activation_failed_with_saved_profile(&self) -> bool {
        self.has_saved_profile() && !self.openless_was_activated()
    }
}

pub struct WindowsImeSessionController {
    profile_manager: WindowsImeProfileManager,
    ipc: WindowsImeIpcServer,
}

impl WindowsImeSessionController {
    pub fn new() -> Self {
        Self {
            profile_manager: WindowsImeProfileManager::new(),
            ipc: WindowsImeIpcServer::new(),
        }
    }

    pub fn prepare_session(&self) -> PreparedWindowsImeSession {
        #[cfg(target_os = "windows")]
        {
            let saved_profile = match self.profile_manager.capture_active_profile() {
                Ok(snapshot) => snapshot,
                Err(error) => {
                    let error = WindowsImeSessionError::Profile(error.to_string());
                    log::warn!("[windows-ime] capture active profile failed: {error}");
                    return PreparedWindowsImeSession::unavailable();
                }
            };

            match self.profile_manager.activate_openless_profile() {
                Ok(()) => PreparedWindowsImeSession {
                    saved_profile: Some(saved_profile),
                    openless_activated: true,
                },
                Err(error) => {
                    let error = WindowsImeSessionError::Profile(error.to_string());
                    log::warn!("[windows-ime] activate OpenLess profile failed: {error}");
                    PreparedWindowsImeSession::activation_failed(saved_profile)
                }
            }
        }

        #[cfg(not(target_os = "windows"))]
        {
            PreparedWindowsImeSession::unavailable()
        }
    }

    pub async fn submit_prepared(
        &self,
        prepared: &PreparedWindowsImeSession,
        request: ImeSubmitRequest,
    ) -> Result<InsertStatus, WindowsImeSessionError> {
        if !prepared.is_ready_for_tsf_submit() {
            return Err(WindowsImeSessionError::Ipc(
                "OpenLess IME session is not active".to_string(),
            ));
        }

        let status = self
            .ipc
            .submit_text(request)
            .await
            .map_err(|error| WindowsImeSessionError::Ipc(error.to_string()))?;
        if should_fallback_after_ime_result(status) {
            log::warn!(
                "[windows-ime] TSF submit returned {status:?}; falling back to non-TSF insertion"
            );
        }
        Ok(map_ime_status_to_insert_status(status))
    }

    pub fn restore_session(&self, prepared: PreparedWindowsImeSession) {
        let should_restore = match self.profile_manager.is_openless_profile_active() {
            Ok(openless_active) => restore_decision(
                prepared.saved_profile.as_ref(),
                openless_active,
                prepared.activation_failed_with_saved_profile(),
            ),
            Err(error) => {
                if prepared.should_restore_when_active_profile_check_fails() {
                    log::warn!(
                        "[windows-ime] check active profile before restore failed: {error}; attempting restore"
                    );
                    ProfileRestoreDecision::RestoreSavedProfile
                } else {
                    log::warn!("[windows-ime] check active profile before restore failed: {error}");
                    ProfileRestoreDecision::KeepCurrentProfile
                }
            }
        };

        if should_restore != ProfileRestoreDecision::RestoreSavedProfile {
            return;
        }

        let Some(saved_profile) = prepared.saved_profile.as_ref() else {
            return;
        };

        if let Err(error) = self.profile_manager.restore_profile(saved_profile) {
            log::warn!("[windows-ime] restore saved profile failed: {error}");
        }
    }
}

impl Default for WindowsImeSessionController {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn committed_ime_result_maps_to_inserted() {
        assert_eq!(
            map_ime_status_to_insert_status(ImeSubmitStatus::Committed),
            InsertStatus::Inserted
        );
    }

    #[test]
    fn rejected_ime_result_requests_fallback() {
        assert!(should_fallback_after_ime_result(ImeSubmitStatus::Rejected));
        assert!(should_fallback_after_ime_result(ImeSubmitStatus::Failed));
        assert!(!should_fallback_after_ime_result(
            ImeSubmitStatus::Committed
        ));
    }

    #[tokio::test]
    async fn submit_prepared_reports_unavailable_session() {
        let controller = WindowsImeSessionController::new();
        let result = controller
            .submit_prepared(
                &PreparedWindowsImeSession::unavailable(),
                ImeSubmitRequest {
                    session_id: "session-1".to_string(),
                    text: "hello".to_string(),
                    created_at: "2026-05-01T12:00:00Z".to_string(),
                    target: None,
                },
            )
            .await;

        assert!(
            matches!(result, Err(WindowsImeSessionError::Ipc(message)) if message == "OpenLess IME session is not active")
        );
    }

    #[test]
    fn active_profile_check_failure_restores_any_session_with_saved_profile() {
        let prepared = PreparedWindowsImeSession {
            saved_profile: Some(ImeProfileSnapshot::keyboard_layout(0x0409, 0x0409_0409)),
            openless_activated: true,
        };
        let activation_failed = PreparedWindowsImeSession::activation_failed(
            ImeProfileSnapshot::keyboard_layout(0x0409, 0x0409_0409),
        );

        assert!(prepared.should_restore_when_active_profile_check_fails());
        assert!(activation_failed.should_restore_when_active_profile_check_fails());
        assert!(!PreparedWindowsImeSession::unavailable()
            .should_restore_when_active_profile_check_fails());
    }

    #[test]
    fn activation_failed_session_keeps_snapshot_but_cannot_submit() {
        let prepared = PreparedWindowsImeSession::activation_failed(
            ImeProfileSnapshot::keyboard_layout(0x0409, 0x0409_0409),
        );

        assert!(prepared.has_saved_profile());
        assert!(!prepared.openless_was_activated());
        assert!(!prepared.is_ready_for_tsf_submit());
        assert!(prepared.activation_failed_with_saved_profile());
    }
}
