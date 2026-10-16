
import pytest

from citations import (
    Citation,
    build_citations,
    format_answer_with_citations,
    format_citations,
)


def test_builds_page_level_citation():
    evidence = [
        {
            "page_number": 3,
            "text": "Revenue increased by 20%.",
            "source": "report.pdf",
        }
    ]

    citations = build_citations(evidence)

    assert len(citations) == 1
    assert citations[0].page_number == 3
    assert citations[0].excerpt == "Revenue increased by 20%."
    assert citations[0].source == "report.pdf"


def test_page_numbers_are_one_based():
    with pytest.raises(ValueError):
        Citation(page_number=0, excerpt="Some evidence")

    with pytest.raises(ValueError):
        build_citations(
            [{"page_number": -1, "text": "Evidence"}]
        )


def test_rejects_non_integer_page_number():
    with pytest.raises(ValueError):
        build_citations(
            [{"page_number": "2", "text": "Evidence"}]
        )


@pytest.mark.parametrize("page_number", [True, False, 2.5, "2"])
def test_direct_citation_rejects_non_integer_page_number(page_number):
    with pytest.raises(ValueError):
        Citation(page_number=page_number, excerpt="Evidence")


@pytest.mark.parametrize("excerpt", [None, 123])
def test_direct_citation_rejects_non_string_excerpt(excerpt):
    with pytest.raises(ValueError):
        Citation(page_number=1, excerpt=excerpt)


@pytest.mark.parametrize("source", [None, 123])
def test_direct_citation_rejects_non_string_source(source):
    with pytest.raises(ValueError):
        Citation(page_number=1, excerpt="Evidence", source=source)


def test_deduplicates_identical_citations():
    evidence = [
        {"page_number": 2, "text": "Sales grew."},
        {"page_number": 2, "text": "Sales grew."},
    ]

    citations = build_citations(evidence)

    assert len(citations) == 1


def test_preserves_different_evidence_on_same_page():
    evidence = [
        {"page_number": 2, "text": "Sales grew."},
        {"page_number": 2, "text": "Costs declined."},
    ]

    citations = build_citations(evidence)

    assert len(citations) == 2
    assert all(c.page_number == 2 for c in citations)


def test_skips_empty_evidence():
    citations = build_citations(
        [
            {"page_number": 1, "text": ""},
            {"page_number": 2, "text": "   "},
        ]
    )

    assert citations == []


def test_formats_citation_with_page_number():
    citation = Citation(
        page_number=4,
        excerpt="The chart shows quarterly growth.",
        source="report.pdf",
    )

    formatted = format_citations([citation])

    assert "[Page 4]" in formatted
    assert "quarterly growth" in formatted
    assert "report.pdf" in formatted


def test_formats_answer_with_citations():
    citations = build_citations(
        [{"page_number": 5, "text": "Profit increased."}]
    )

    result = format_answer_with_citations(
        "Profit increased during the period.",
        citations,
    )

    assert "Profit increased during the period." in result
    assert "Sources:" in result
    assert "[Page 5]" in result


def test_handles_missing_citations():
    result = format_answer_with_citations("An answer.", [])

    assert "No supporting citations were retrieved." in result


def test_rejects_empty_answer():
    with pytest.raises(ValueError):
        format_answer_with_citations("  ", [])
