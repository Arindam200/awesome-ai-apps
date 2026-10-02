"""
Auth0-inspired secure agent control workflow.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class User:
    user_id: str
    roles: set[str]
    permissions: set[str]


@dataclass
class AuditEvent:
    user_id: str
    action: str
    allowed: bool
    reason: str
    timestamp: str


AUDIT_LOG: list[AuditEvent] = []


def audit(
    user_id: str,
    action: str,
    allowed: bool,
    reason: str,
) -> None:
    AUDIT_LOG.append(
        AuditEvent(
            user_id=user_id,
            action=action,
            allowed=allowed,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    )


def authorize(
    user: User,
    action: str,
    required_permission: str,
) -> bool:
    if required_permission not in user.permissions:
        audit(
            user.user_id,
            action,
            False,
            f"Missing permission: {required_permission}",
        )
        return False

    audit(user.user_id, action, True, "Permission granted")
    return True


def execute_tool(
    user: User,
    action: str,
    required_permission: str,
    sensitive: bool = False,
    approved: bool = False,
) -> dict[str, Any]:
    if not authorize(user, action, required_permission):
        return {
            "status": "denied",
            "message": "Authorization failed",
        }

    if sensitive and not approved:
        audit(
            user.user_id,
            action,
            False,
            "Explicit approval required",
        )
        return {
            "status": "approval_required",
            "message": "This sensitive action requires approval",
        }

    return {
        "status": "allowed",
        "message": f"Executed action: {action}",
    }


def main() -> None:
    analyst = User(
        user_id="user-001",
        roles={"analyst"},
        permissions={"reports:read", "reports:export"},
    )

    print(
        execute_tool(
            analyst,
            "read_report",
            "reports:read",
        )
    )

    print(
        execute_tool(
            analyst,
            "delete_report",
            "reports:delete",
            sensitive=True,
        )
    )

    print(
        execute_tool(
            analyst,
            "export_report",
            "reports:export",
            sensitive=True,
        )
    )

    print("\nAudit log:")
    for event in AUDIT_LOG:
        print(event)


if __name__ == "__main__":
    main()
