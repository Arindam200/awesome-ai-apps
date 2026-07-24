//! Coordinator 的纯状态转移层。
//!
//! 这里不依赖 Tauri / 音频 / 系统剪贴板，只描述 dictation session 的 Rust
//! 状态机。这样 Windows CI 可以在不启动完整 Tauri test harness 的情况下实际运行
//! 后端单测。

use std::time::Instant;

use uuid::Uuid;

pub type SessionId = Uuid;

pub fn new_session_id() -> SessionId {
    Uuid::new_v4()
}

pub fn initial_session_id() -> SessionId {
    Uuid::nil()
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum SessionPhase {
    Idle,
    Starting,
    Listening,
    Processing,
    /// 已经过了最后一次 cancel 检查、即将 / 正在调用 inserter.insert 的窗口。
    /// cancel_session 在此阶段拒绝介入：Cmd+V 模拟点击已开始或已发出，
    /// 无法撤销，硬把 cancelled=true 也救不回来，只会让 UI 出现 cancelled
    /// 但实际还是插入了的诡异状态。详见 PR 修 Codex audit HIGH #2。
    Inserting,
}

pub(crate) struct SessionState {
    pub(crate) phase: SessionPhase,
    pub(crate) started_at: Instant,
    /// Starting 阶段（ASR 握手中）按下 stop 边沿（toggle 第二次按 / hold 松开）→
    /// 等握手完成 phase=Listening 后立刻 end_session，不丢边沿。issue #51。
    pub(crate) pending_stop: bool,
    /// 用户在 Processing 阶段按 Esc 取消：end_session 在 polish/insert 检查点跳过插入 +
    /// 跳过 history.append。issue #52。
    pub(crate) cancelled: bool,
    pub(crate) focus_target: Option<usize>,
    /// 每次 begin_session 生成新的 UUID session id。
    /// recorder error monitor 持有 captured id，处理时若与当前不等说明
    /// 是上一 session 的迟到错误，必须 drop，不要 abort 当前 active session。
    pub(crate) session_id: SessionId,
    /// 用户开始 dictation 时所处的前台 app 标签（"Mail (com.apple.mail)" / Windows 窗口标题）。
    /// 用作 LLM polish/translate 的上下文前提，让模型按 app 调风格。详见 issue #116。
    pub(crate) front_app: Option<String>,
}

impl Default for SessionState {
    fn default() -> Self {
        Self {
            phase: SessionPhase::Idle,
            started_at: Instant::now(),
            pending_stop: false,
            cancelled: false,
            focus_target: None,
            session_id: initial_session_id(),
            front_app: None,
        }
    }
}

/// begin_session 的锁内转移：只有 Idle 能进入 Starting，并生成新 session id。
pub(crate) fn begin_session_state(
    state: &mut SessionState,
    focus_target: Option<usize>,
    front_app: Option<String>,
) -> Option<SessionId> {
    if state.phase != SessionPhase::Idle {
        return None;
    }
    state.phase = SessionPhase::Starting;
    state.started_at = Instant::now();
    state.pending_stop = false;
    state.cancelled = false;
    state.focus_target = focus_target;
    state.session_id = new_session_id();
    state.front_app = front_app;
    Some(state.session_id)
}

/// stop_dictation / hold release 在 Starting 阶段只记录 pending_stop，等待启动完成后处理。
pub(crate) fn request_stop_during_starting_state(state: &mut SessionState) -> bool {
    if state.phase != SessionPhase::Starting {
        return false;
    }
    state.pending_stop = true;
    true
}

/// begin_session 中各 await 之间的 cancel race 检查结果。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum BeginOutcome {
    /// 启动 continuation 属于旧 session；不能改动当前 session 状态。
    StaleContinuation,
    /// 正常进入 Listening。
    Started,
    /// Starting 阶段积累了 pending_stop 边沿，应立即 end_session（hold 快速松开 / toggle 快速双击）。
    PendingStop,
    /// 期间 cancel_session 触发（cancelled=true 或 phase 被外部改回 Idle）。
    /// 必须回滚 recorder + ASR 资源，不进 Listening。
    CancelRaced,
}

pub(crate) fn finish_starting_session_state(
    state: &mut SessionState,
    session_id: SessionId,
) -> BeginOutcome {
    if state.session_id != session_id {
        BeginOutcome::StaleContinuation
    } else if state.cancelled || state.phase != SessionPhase::Starting {
        BeginOutcome::CancelRaced
    } else {
        state.phase = SessionPhase::Listening;
        let pending = std::mem::replace(&mut state.pending_stop, false);
        if pending {
            BeginOutcome::PendingStop
        } else {
            BeginOutcome::Started
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum StartupRaceStatus {
    ActiveStarting,
    CancelRaced,
    StaleContinuation,
}

pub(crate) fn startup_race_status(
    state: &SessionState,
    captured_session_id: SessionId,
) -> StartupRaceStatus {
    if state.session_id != captured_session_id {
        StartupRaceStatus::StaleContinuation
    } else if state.cancelled || state.phase != SessionPhase::Starting {
        StartupRaceStatus::CancelRaced
    } else {
        StartupRaceStatus::ActiveStarting
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct CancelDecision {
    pub(crate) phase: SessionPhase,
    pub(crate) session_id: SessionId,
}

/// cancel_session 的锁内前半段。Idle / Inserting 不可取消；其他阶段设置 cancelled。
pub(crate) fn begin_cancel_session_state(state: &mut SessionState) -> Option<CancelDecision> {
    let phase = state.phase;
    if matches!(phase, SessionPhase::Idle | SessionPhase::Inserting) {
        return None;
    }
    state.cancelled = true;
    Some(CancelDecision {
        phase,
        session_id: state.session_id,
    })
}

/// cancel_session 外部资源清理后的锁内收尾。Processing 阶段把 phase 留给 end_session
/// 自己收尾（防止与 polish/insert 路径竞争），但 focus_target 是当前 session 的窗口
/// 资源句柄，cancel 之后无论处于哪个 phase 都应当释放，避免下一个 session 之前的
/// 空档期被旧值污染。详见 audit 3.3.5。
pub(crate) fn finish_cancel_session_state(state: &mut SessionState, decision: CancelDecision) {
    state.focus_target = None;
    if decision.phase != SessionPhase::Processing {
        state.phase = SessionPhase::Idle;
    }
}

pub(crate) fn start_processing_if_listening(state: &mut SessionState) -> Option<SessionId> {
    if state.phase != SessionPhase::Listening {
        return None;
    }
    state.phase = SessionPhase::Processing;
    Some(state.session_id)
}

pub(crate) struct RecordingAbort {
    pub(crate) elapsed: u64,
    pub(crate) session_id: SessionId,
}

pub(crate) fn begin_recording_abort_before_restore(
    state: &mut SessionState,
) -> Option<RecordingAbort> {
    if state.cancelled
        || !matches!(
            state.phase,
            SessionPhase::Starting | SessionPhase::Listening
        )
    {
        return None;
    }
    state.cancelled = true;
    Some(RecordingAbort {
        elapsed: state.started_at.elapsed().as_millis() as u64,
        session_id: state.session_id,
    })
}

pub(crate) fn publish_abort_idle_after_restore(state: &mut SessionState, session_id: SessionId) {
    if state.session_id == session_id {
        state.phase = SessionPhase::Idle;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn session_id(n: u128) -> SessionId {
        Uuid::from_u128(n)
    }

    #[test]
    fn begin_session_enters_starting_and_clears_stale_edges() {
        let mut state = SessionState {
            pending_stop: true,
            cancelled: true,
            ..Default::default()
        };

        let id = begin_session_state(
            &mut state,
            Some(7),
            Some("Terminal (com.apple.Terminal)".into()),
        )
        .unwrap();

        assert_eq!(state.phase, SessionPhase::Starting);
        assert!(!state.pending_stop);
        assert!(!state.cancelled);
        assert_eq!(state.focus_target, Some(7));
        assert_eq!(
            state.front_app.as_deref(),
            Some("Terminal (com.apple.Terminal)")
        );
        assert_eq!(state.session_id, id);
        assert_ne!(id, initial_session_id());
    }

    #[test]
    fn begin_session_ignores_non_idle_phase() {
        let mut state = SessionState {
            phase: SessionPhase::Processing,
            session_id: session_id(99),
            ..Default::default()
        };

        assert!(begin_session_state(&mut state, Some(1), Some("Mail".into())).is_none());

        assert_eq!(state.phase, SessionPhase::Processing);
        assert_eq!(state.session_id, session_id(99));
        assert!(state.focus_target.is_none());
        assert!(state.front_app.is_none());
    }

    #[test]
    fn stop_during_starting_sets_pending_stop_only_for_starting() {
        let mut state = SessionState {
            phase: SessionPhase::Starting,
            ..Default::default()
        };

        assert!(request_stop_during_starting_state(&mut state));
        assert!(state.pending_stop);

        state.phase = SessionPhase::Listening;
        state.pending_stop = false;
        assert!(!request_stop_during_starting_state(&mut state));
        assert!(!state.pending_stop);
    }

    #[test]
    fn finish_starting_is_table_driven_for_pending_cancel_and_stale_edges() {
        let cases = [
            (
                SessionPhase::Starting,
                false,
                false,
                session_id(7),
                BeginOutcome::Started,
                SessionPhase::Listening,
            ),
            (
                SessionPhase::Starting,
                false,
                true,
                session_id(7),
                BeginOutcome::PendingStop,
                SessionPhase::Listening,
            ),
            (
                SessionPhase::Starting,
                true,
                false,
                session_id(7),
                BeginOutcome::CancelRaced,
                SessionPhase::Starting,
            ),
            (
                SessionPhase::Idle,
                false,
                false,
                session_id(7),
                BeginOutcome::CancelRaced,
                SessionPhase::Idle,
            ),
            (
                SessionPhase::Starting,
                false,
                false,
                session_id(8),
                BeginOutcome::StaleContinuation,
                SessionPhase::Starting,
            ),
        ];

        for (phase, cancelled, pending_stop, actual_id, expected, expected_phase) in cases {
            let mut state = SessionState {
                phase,
                cancelled,
                pending_stop,
                session_id: actual_id,
                ..Default::default()
            };

            assert_eq!(
                finish_starting_session_state(&mut state, session_id(7)),
                expected,
                "phase={phase:?} cancelled={cancelled} pending_stop={pending_stop} actual_id={actual_id}"
            );
            assert_eq!(state.phase, expected_phase);
            if expected == BeginOutcome::PendingStop {
                assert!(!state.pending_stop);
            }
        }
    }

    #[test]
    fn cancel_session_state_machine_is_table_driven() {
        let cases = [
            (SessionPhase::Idle, SessionPhase::Idle, false),
            (SessionPhase::Starting, SessionPhase::Idle, true),
            (SessionPhase::Listening, SessionPhase::Idle, true),
            (SessionPhase::Processing, SessionPhase::Processing, true),
            (SessionPhase::Inserting, SessionPhase::Inserting, false),
        ];

        for (initial, expected_phase, expected_cancelled) in cases {
            let mut state = SessionState {
                phase: initial,
                cancelled: false,
                focus_target: Some(1),
                session_id: session_id(42),
                ..Default::default()
            };

            if let Some(decision) = begin_cancel_session_state(&mut state) {
                finish_cancel_session_state(&mut state, decision);
            }

            assert_eq!(state.phase, expected_phase, "initial={initial:?}");
            assert_eq!(state.cancelled, expected_cancelled, "initial={initial:?}");
            // 任何被 begin_cancel_session_state 接受的 phase（即非 Idle/Inserting）
            // 都应当清掉 focus_target，包括 Processing —— 这是 audit 3.3.5 的回归卡。
            if expected_cancelled {
                assert!(
                    state.focus_target.is_none(),
                    "focus_target should clear after cancel, initial={initial:?}"
                );
            } else {
                assert_eq!(
                    state.focus_target,
                    Some(1),
                    "rejected cancel must not touch focus_target, initial={initial:?}"
                );
            }
        }
    }

    #[test]
    fn stop_dictation_from_listening_enters_processing_once() {
        let mut state = SessionState {
            phase: SessionPhase::Listening,
            session_id: session_id(123),
            ..Default::default()
        };

        assert_eq!(
            start_processing_if_listening(&mut state),
            Some(session_id(123))
        );
        assert_eq!(state.phase, SessionPhase::Processing);
        assert_eq!(start_processing_if_listening(&mut state), None);
        assert_eq!(state.phase, SessionPhase::Processing);
    }

    #[test]
    fn startup_race_check_is_table_driven_for_begin_session_edges() {
        let cases = [
            (
                SessionPhase::Starting,
                false,
                session_id(7),
                StartupRaceStatus::ActiveStarting,
            ),
            (
                SessionPhase::Starting,
                true,
                session_id(7),
                StartupRaceStatus::CancelRaced,
            ),
            (
                SessionPhase::Idle,
                false,
                session_id(7),
                StartupRaceStatus::CancelRaced,
            ),
            (
                SessionPhase::Listening,
                false,
                session_id(7),
                StartupRaceStatus::CancelRaced,
            ),
            (
                SessionPhase::Starting,
                false,
                session_id(8),
                StartupRaceStatus::StaleContinuation,
            ),
        ];

        for (phase, cancelled, actual_session_id, expected) in cases {
            let state = SessionState {
                phase,
                cancelled,
                session_id: actual_session_id,
                ..Default::default()
            };

            assert_eq!(
                startup_race_status(&state, session_id(7)),
                expected,
                "phase={phase:?} cancelled={cancelled} actual_session={actual_session_id}"
            );
        }
    }

    #[test]
    fn recording_abort_keeps_session_non_idle_until_restore_can_run() {
        let mut state = SessionState {
            phase: SessionPhase::Listening,
            cancelled: false,
            session_id: session_id(7),
            ..Default::default()
        };

        let abort = begin_recording_abort_before_restore(&mut state).unwrap();

        assert_eq!(abort.session_id, session_id(7));
        assert!(state.cancelled);
        assert_eq!(state.phase, SessionPhase::Listening);

        publish_abort_idle_after_restore(&mut state, abort.session_id);

        assert_eq!(state.phase, SessionPhase::Idle);
    }

    #[test]
    fn recording_abort_is_noop_after_prior_cancel_or_idle() {
        let cases = [
            (SessionPhase::Idle, false),
            (SessionPhase::Processing, false),
            (SessionPhase::Listening, true),
        ];

        for (phase, cancelled) in cases {
            let mut state = SessionState {
                phase,
                cancelled,
                ..Default::default()
            };

            assert!(begin_recording_abort_before_restore(&mut state).is_none());
            assert_eq!(state.phase, phase);
            assert_eq!(state.cancelled, cancelled);
        }
    }
}
