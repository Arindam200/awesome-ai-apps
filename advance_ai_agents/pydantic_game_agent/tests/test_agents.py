from app.agents import needs_repair, normalize_review
from app.models import GameReview


def test_review_storage_persistence_issue_is_ignored() -> None:
    review = GameReview(
        approved=False,
        issues=["High score is not persisted to localStorage as specified."],
        fix_instructions="Use localStorage for the best score.",
    )

    normalized = normalize_review(review, safety_issues=[])

    assert normalized.approved is True
    assert normalized.issues == []
    assert not needs_repair(normalized, [])


def test_review_real_issue_still_requires_repair() -> None:
    review = GameReview(approved=False, issues=["Restart button is missing."])

    normalized = normalize_review(review, safety_issues=[])

    assert normalized.approved is False
    assert normalized.issues == ["Restart button is missing."]
    assert needs_repair(normalized, [])
