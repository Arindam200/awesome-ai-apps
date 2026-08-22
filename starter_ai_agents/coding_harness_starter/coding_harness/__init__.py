"""A minimal, approval-gated coding harness starter."""

from .approval import ApprovalGate, request_approval
from .models import (
    FileOperation,
    ImplementationPlan,
    PatchProposal,
    RunSummary,
    TestRunRecord,
)
from .patching import apply_prepared_patch, prepare_patch, render_unified_diff
from .workspace import Workspace, WorkspaceError

__all__ = [
    "ApprovalGate",
    "FileOperation",
    "ImplementationPlan",
    "PatchProposal",
    "RunSummary",
    "TestRunRecord",
    "Workspace",
    "WorkspaceError",
    "apply_prepared_patch",
    "prepare_patch",
    "render_unified_diff",
    "request_approval",
]
