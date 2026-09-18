from main import AUDIT_LOG, User, execute_tool


def setup_function():
    AUDIT_LOG.clear()


def test_allowed_action():
    user = User(
        user_id="test-user",
        roles={"analyst"},
        permissions={"reports:read"},
    )

    result = execute_tool(
        user,
        "read_report",
        "reports:read",
    )

    assert result["status"] == "allowed"


def test_denied_action():
    user = User(
        user_id="test-user",
        roles={"analyst"},
        permissions={"reports:read"},
    )

    result = execute_tool(
        user,
        "delete_report",
        "reports:delete",
    )

    assert result["status"] == "denied"


def test_sensitive_action_requires_approval():
    user = User(
        user_id="test-user",
        roles={"analyst"},
        permissions={"reports:export"},
    )

    result = execute_tool(
        user,
        "export_report",
        "reports:export",
        sensitive=True,
    )

    assert result["status"] == "approval_required"


def test_audit_log_created():
    user = User(
        user_id="test-user",
        roles={"analyst"},
        permissions={"reports:read"},
    )

    execute_tool(user, "read_report", "reports:read")

    assert len(AUDIT_LOG) == 1
    assert AUDIT_LOG[0].allowed is True
