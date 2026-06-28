"""Chat parsing and follow-up helpers."""

from __future__ import annotations

import re

from models import AgentRunResult, CompanyContext


FIELD_ALIASES = {
    "company": "company_name",
    "company name": "company_name",
    "product": "product",
    "category": "product",
    "product/category": "product",
    "audience": "audience",
    "target audience": "audience",
    "keywords": "seed_keywords",
    "seed keywords": "seed_keywords",
    "competitors": "competitors",
    "existing topics": "existing_topics",
    "existing content": "existing_topics",
}


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def apply_prompt_context(prompt: str, context: dict) -> bool:
    """Parse structured or natural chat context into the mutable Streamlit context dict."""
    changed = False
    for raw_line in prompt.replace(";", "\n").splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        field = FIELD_ALIASES.get(key.strip().lower())
        if not field or not value.strip():
            continue
        if field in {"seed_keywords", "competitors", "existing_topics"}:
            context[field] = split_csv(value)
        else:
            context[field] = value.strip()
        changed = True
    changed = _apply_natural_context(prompt, context) or changed
    return changed


def _apply_natural_context(prompt: str, context: dict) -> bool:
    changed = False
    normalized = " ".join(prompt.split())

    if not context["company_name"].strip():
        company = _first_match(
            normalized,
            [
                r"\b(?:built|created|launched)\s+([A-Za-z0-9-]+\.[A-Za-z]{2,})(?:,|\.)",
                r"\b(?:I\s+)?(?:run|own|manage|founded?)\s+([A-Za-z0-9-]+\.[A-Za-z]{2,})(?:,|\.|\s|$)",
                r"\b(?:for|about|around)\s+([A-Za-z0-9-]+\.[A-Za-z]{2,})(?:,|\.|\s|$)",
                r"(?:devrel|developer relations)\s+for\s+([A-Za-z][A-Za-z0-9 .&-]{1,40}?)(?:,|\.|\s+a\s)",
                r"\b(?:built|created|launched)\s+([A-Za-z][A-Za-z0-9 .&-]{1,40}?)(?:,|\.)",
                r"(?:leading|run|own|manage)\s+content\s+for\s+([A-Za-z][A-Za-z0-9 .&-]{1,40}?)(?:,|\sand\s|\.)",
                r"(?:company|startup|team)\s+(?:is|called)\s+([A-Za-z][A-Za-z0-9 .&-]{1,40}?)(?:,|\.|\sand\s)",
                r"\bfor\s+([A-Z][A-Za-z0-9 .&-]{1,40}?)(?:,?\s+and\s+I\s+want|,?\s+we\s+want)",
            ],
        )
        if company:
            context["company_name"] = _clean_phrase(company)
            changed = True

    if not context["product"].strip():
        product = _first_match(
            normalized,
            [
                r"(?:built|created|launched|run|own|manage|founded?)\s+[A-Za-z][A-Za-z0-9 .&-]{1,40}?,\s+(?:a|an|the)\s+(.+?)(?:\.|\s+for\s+)",
                r"(?:devrel|developer relations)\s+for\s+[A-Za-z][A-Za-z0-9 .&-]{1,40}?,\s+(?:a|an|the)\s+(.+?)(?:\.|\s+Our\s+audience\s+)",
                r"opportunities\s+for\s+our\s+(.+?)(?:\.|\s+Our\s+audience\s+is)",
                r"(?:product|category)\s+(?:is|=)\s+(.+?)(?:\.|,|\s+and\s)",
                r"(?:it'?s\s+a|its\s+a|it\s+is\s+a)\s+(.+?(?:tool|platform|framework|sdk|api|system|service|app))(?:\.|,|\s|$)",
                r"building\s+(?:a|an|the|our)?\s*(.+?(?:framework|platform|tool|sdk|api|system|product))(?:\.|,|\s+for\s)",
            ],
        )
        if product:
            context["product"] = _clean_phrase(product)
            changed = True

    if not context["audience"].strip():
        audience = _first_match(
            normalized,
            [
                r"(?:my|our)\s+audience\s+is\s+(.+?)(?:\.|\s+They\s+care\s+about)",
                r"(?:our\s+)?audience\s+is\s+(.+?)(?:\.|\s+They\s+care\s+about)",
                r"\bhelp\s+(.+?)\s+understand\b",
                r"(?:for|targeting)\s+((?:senior\s+)?(?:AI|ML|software|platform|engineering|backend|frontend|devops)[^.]{10,140}?)(?:\.|\s+who\s+care)",
            ],
        )
        if audience:
            context["audience"] = _clean_phrase(audience)
            changed = True

    if not context["competitors"]:
        competitors = _first_match(
            normalized,
            [
                r"(?:competitors|adjacent tools|alternatives)[^.]{0,40}\s+include\s+(.+?)(?:\.|$)",
                r"(?:against|versus|vs\.?)\s+(.+?)(?:\.|$)",
            ],
        )
        if competitors:
            context["competitors"] = _split_natural_list(competitors)
            changed = bool(context["competitors"]) or changed

    if not context["seed_keywords"]:
        keyword_chunks: list[str] = []
        cares = _first_match(normalized, [r"care\s+about\s+(.+?)(?:\.|$)"])
        interested = _first_match(normalized, [r"interested\s+in\s+topics\s+that\s+could\s+become\s+(.+?)(?:\.|$)"])
        if cares:
            keyword_chunks.extend(_split_natural_list(cares))
        if interested:
            keyword_chunks.extend(_split_natural_list(interested))
        around = _first_match(normalized, [r"\baround\s+(.+?)(?:\.|$)"])
        if around:
            keyword_chunks.extend(_split_natural_list(around))
        if context["product"]:
            keyword_chunks.extend(_product_keywords(context["product"]))
        context["seed_keywords"] = list(dict.fromkeys(item for item in keyword_chunks if len(item) > 2))[:10]
        changed = bool(context["seed_keywords"]) or changed

    return changed


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _clean_phrase(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .,")
    value = re.sub(r"^(?:a|an|the|our)\s+", "", value, flags=re.IGNORECASE)
    return value


def _split_natural_list(value: str) -> list[str]:
    value = value.replace(" and ", ", ")
    value = value.replace(" or ", ", ")
    return [
        _clean_phrase(item)
        for item in value.split(",")
        if _clean_phrase(item)
    ]


def _product_keywords(product: str) -> list[str]:
    words = [word.strip(".,").lower() for word in product.split()]
    pairs = [" ".join(words[index : index + 2]) for index in range(max(0, len(words) - 1))]
    return [_clean_phrase(product), *pairs]


def missing_fields(context: dict) -> list[str]:
    missing = []
    if not context["company_name"].strip() and not context["product"].strip():
        missing.append("company or product/category")
    elif not context["product"].strip():
        context["product"] = context["company_name"].strip()
    if not context["audience"].strip():
        missing.append("target audience")
    return missing


def has_required_context(context: dict) -> bool:
    return not missing_fields(context)


def wants_brief_run(prompt: str, context: dict | None = None) -> bool:
    lowered = prompt.lower()
    if wants_explicit_research_run(prompt):
        return True
    if wants_memory_lookup(prompt) or wants_current_report_followup(prompt):
        return False

    run_phrases = (
        "run the brief",
        "run trend digest",
        "run the trend digest",
        "trend digest",
        "talk ideas",
        "blog ideas",
        "devrel ideas",
        "research trends",
        "run gap analysis",
        "generate the report",
        "create the report",
        "generate the brief",
        "create the brief",
        "start the brief",
        "run research",
        "start research",
        "generate it",
        "run it",
    )
    if any(phrase in lowered for phrase in run_phrases):
        return True

    action_terms = (
        "find",
        "search",
        "research",
        "look for",
        "recommend",
        "suggest",
        "analyze",
        "analyse",
        "discover",
        "identify",
        "give me",
        "show me",
        "what should",
        "help me",
    )
    publishing_terms = (
        "content idea",
        "content ideas",
        "topic",
        "topics",
        "article",
        "articles",
        "blog",
        "blogs",
        "talk",
        "talks",
        "tutorial",
        "tutorials",
        "devrel",
        "trend",
        "trends",
        "publish",
        "publishing",
        "opportunit",
        "what to write",
        "write about",
    )
    has_action = any(action in lowered for action in action_terms)
    has_publishing_term = any(
        term in lowered for term in publishing_terms
    )
    if has_action and has_publishing_term:
        return True

    generic_idea_terms = (
        "idea",
        "ideas",
        "suggestion",
        "suggestions",
        "recommendation",
        "recommendations",
    )
    generic_run_terms = (
        "suggest some",
        "suggest ideas",
        "some ideas",
        "content ideas",
        "please search",
        "search for me",
        "research for me",
        "look for ideas",
        "find and analyze",
        "find and analyse",
        "analyze for me",
        "analyse for me",
        "do it",
        "go ahead",
    )
    if context and has_required_context(context):
        return any(term in lowered for term in generic_run_terms) or (
            has_action and any(term in lowered for term in generic_idea_terms)
        )

    return False


def wants_explicit_research_run(prompt: str) -> bool:
    lowered = prompt.lower()
    old_session_terms = ("before", "past", "previous", "previously", "history", "memory")
    if any(term in lowered for term in old_session_terms):
        return False

    explicit_research_terms = (
        "research developer conversations",
        "research what developers",
        "research recent",
        "research trends",
        "run research",
        "start research",
        "check dev.to",
        "dev.to saturation",
        "article saturation",
        "hacker news demand",
        "hn demand",
        "recommend technical blog",
        "recommend technical blogs",
        "recommend talk",
        "recommend talks",
        "publish next",
        "what should we publish",
    )
    if any(term in lowered for term in explicit_research_terms):
        return True

    action_terms = ("find", "search", "research", "analyze", "analyse", "recommend", "suggest")
    source_terms = ("hn", "hacker news", "dev.to", "devto", "developer conversations", "article saturation")
    output_terms = ("ideas", "topics", "blog", "blogs", "talk", "talks", "trend", "trends", "publish")
    return (
        any(term in lowered for term in action_terms)
        and any(term in lowered for term in source_terms)
        and any(term in lowered for term in output_terms)
    )


def wants_current_report_followup(prompt: str) -> bool:
    lowered = prompt.lower()
    old_session_terms = ("before", "past", "previous", "previously", "history", "memory")
    if any(term in lowered for term in old_session_terms):
        return False

    report_terms = (
        "latest",
        "current",
        "this report",
        "the report",
        "the digest",
        "this digest",
        "idea",
        "ideas",
        "topic",
        "topics",
        "trend",
        "trends",
        "evidence",
        "source",
        "sources",
        "what did we find",
        "what we found",
        "what did you find",
        "what did we get",
        "what was suggested",
        "what topics were suggested",
        "what ideas were suggested",
        "make these",
        "make it",
        "more technical",
        "comparison",
        "vs",
    )
    question_or_refinement = (
        "?" in prompt
        or any(term in lowered for term in ("show", "explain", "summarize", "recap", "make", "turn", "focus"))
    )
    return question_or_refinement and any(term in lowered for term in report_terms)


def render_context_summary(context: dict) -> str:
    company_context = CompanyContext(**context)
    lines = ["Got it. I'll treat this as the DevRel research context:"]
    lines.append(f"- {company_context.company_name or 'Missing company'} is the company.")
    lines.append(f"- The product/category is {company_context.product or 'missing'}." )
    lines.append(f"- The audience is {company_context.audience or 'missing'}." )
    if company_context.seed_keywords:
        lines.append(f"- I’ll start from these signals: {', '.join(company_context.seed_keywords)}." )
    else:
        lines.append("- I’ll derive HN and DEV search angles from the product and audience.")
    if company_context.competitors:
        lines.append(f"- I’ll keep these alternatives in view: {', '.join(company_context.competitors)}.")
    if company_context.existing_topics:
        lines.append(f"- Existing topics to account for: {', '.join(company_context.existing_topics)}.")
    return "\n".join(lines)


def conversational_response(
    prompt: str,
    context: dict,
    result: AgentRunResult | None,
) -> str | None:
    lowered = prompt.lower().strip()
    missing = missing_fields(context)

    if any(term in lowered for term in ("what can you do", "how does this work", "what do you do")):
        return (
            "I help turn developer demand into a trend digest and DevRel talk/blog ideas. Once you give me "
            "enough context, I run an Agno multi-agent team that checks HN demand, DEV.to supply, and "
            "Engram memory in parallel. For normal follow-up questions like this, I won't call HN or DEV."
        )

    if any(term in lowered for term in ("do you call hn", "call dev", "hacker news every time", "dev every time")):
        return (
            "No. I only call Hacker News and DEV.to when you ask me to find, recommend, or analyze talk/blog ideas or trends. "
            "Regular chat follow-ups use the current session context, the latest generated report, or Engram chat storage."
        )

    if any(term in lowered for term in ("what context", "what do you know", "current context", "what have you got")):
        return render_context_summary(context)

    summary_triggers = (
        "summary", "recap", "what did we find", "what we found",
        "what we researched", "what did we research", "what have we",
        "what we got", "what did we get", "what did you find",
        "what was researched", "researched about",
    )
    if result is not None and any(term in lowered for term in summary_triggers):
        ideas = result.report.content_ideas[:3]
        trends = result.report.trend_digest[:3]
        if not ideas and not trends:
            return result.report.summary
        lines = [result.report.summary, ""]
        if trends:
            lines.append("Top trends from the latest report:")
            lines.extend(
                f"{index}. {trend.topic} - intensity {trend.intensity_score}"
                for index, trend in enumerate(trends, 1)
            )
            lines.append("")
        if ideas:
            lines.append("Top talk/blog ideas from the latest report:")
            lines.extend(
                f"{index}. {idea.title} ({idea.format}) - score {idea.score}"
                for index, idea in enumerate(ideas, 1)
            )
        return "\n".join(lines)

    if result is not None and any(term in lowered for term in ("why", "explain", "tell me more")):
        topic_number = _first_number(lowered)
        if topic_number is not None and 0 < topic_number <= len(result.report.content_ideas):
            idea = result.report.content_ideas[topic_number - 1]
            return (
                f"Idea {topic_number}, **{idea.title}**, is interesting because {idea.angle}\n\n"
                f"The gap I'd lean into: {idea.dev_gap}\n\n"
                f"Format: {idea.format} | Confidence: {idea.confidence}"
            )

    if wants_brief_run(prompt, context) and missing:
        return (
            "I can do that, but I still need "
            + (missing[0] if len(missing) == 1 else ", ".join(missing[:-1]) + f", and {missing[-1]}")
            + ". You can say it naturally; no labels required."
        )

    if "?" in prompt:
        if missing:
            return (
                "Yep. I can answer questions here without calling HN or DEV. "
                "For the research report itself, I still need "
                + (missing[0] if len(missing) == 1 else ", ".join(missing[:-1]) + f", and {missing[-1]}")
                + "."
            )
        return (
            "Yes. I have enough context for the report, and I'll only call HN and DEV.to when you ask me to find, recommend, or analyze trends and talk/blog ideas. "
            "Until then, I can refine the angle, audience, competitors, or keywords conversationally."
        )

    return None


def wants_memory_lookup(prompt: str) -> bool:
    lowered = prompt.lower()
    if wants_explicit_research_run(prompt):
        return False
    historical_research_phrases = (
        "our research",
        "research we have done",
        "research we've done",
        "research we did",
        "we researched",
        "we have researched",
        "we've researched",
        "done so far",
        "so far",
        "last few products",
        "last few topics",
        "last few ideas",
        "last products",
        "last topics",
        "last ideas",
    )
    historical_subject_terms = (
        "product",
        "products",
        "topic",
        "topics",
        "idea",
        "ideas",
        "article",
        "articles",
        "blog",
        "blogs",
        "talk",
        "talks",
        "publish",
        "work on",
    )
    if any(phrase in lowered for phrase in historical_research_phrases) and any(
        term in lowered for term in historical_subject_terms
    ):
        return True
    memory_terms = (
        "before",
        "past",
        "previous",
        "previously",
        "recent",
        "recently",
        "lately",
        "already",
        "history",
        "memory",
        "discussed",
        "researched",
        "generated",
        "suggested",
        "recommend",
        "recommended",
        "found",
        "so far",
    )
    subject_terms = (
        "product",
        "products",
        "topic",
        "topics",
        "idea",
        "ideas",
        "article",
        "articles",
        "blog",
        "blogs",
        "talk",
        "talks",
        "brief",
        "briefs",
        "report",
        "reports",
        "about",
        "result",
        "results",
        "suggestion",
        "suggestions",
        "recommendation",
        "recommendations",
    )
    return any(term in lowered for term in memory_terms) and any(
        term in lowered for term in subject_terms
    )


def followup_response(prompt: str, result: AgentRunResult | None) -> str | None:
    if result is None:
        return None

    lowered = prompt.lower()
    summary_terms = (
        "what topics",
        "what ideas",
        "what trends",
        "what did we find",
        "what we found",
        "what did you find",
        "what was suggested",
        "what were suggested",
        "topics were suggested",
        "ideas were suggested",
        "suggested recently",
        "summary",
        "recap",
    )
    if any(term in lowered for term in summary_terms):
        lines = [result.report.summary.strip() or f"Here are the latest ideas for {result.report.company}."]
        if result.report.trend_digest:
            lines.append("")
            lines.append("Top trends from the latest report:")
            for index, trend in enumerate(result.report.trend_digest[:5], 1):
                lines.append(f"{index}. **{trend.topic}** — intensity {trend.intensity_score}")
        if result.report.content_ideas:
            lines.append("")
            lines.append("Top talk/blog ideas from the latest report:")
            for index, idea in enumerate(result.report.content_ideas[:5], 1):
                lines.append(f"{index}. **{idea.title}** ({idea.format}, score {idea.score})")
        return "\n".join(lines)

    if "evidence" in lowered and any(term in lowered for term in ("topic", "brief", "idea", "opportunity", "trend")):
        topic_number = _first_number(lowered)
        if topic_number is None:
            return "Tell me which idea number you want evidence for."
        index = topic_number - 1
        if index < 0 or index >= len(result.report.content_ideas):
            return f"I only have {len(result.report.content_ideas)} ideas in the latest report."
        idea = result.report.content_ideas[index]
        hn_links = "\n".join(f"- {url}" for url in idea.hn_evidence) or "- No strong HN evidence found in this run."
        dev_links = "\n".join(f"- {url}" for url in idea.dev_links) or "- No specific DEV.to article matched this idea closely."
        return (
            f"### Evidence for idea {topic_number}: {idea.title}\n\n"
            f"HN evidence:\n{hn_links}\n\n"
            f"DEV supply links:\n{dev_links}\n\n"
            f"DEV supply gap: {idea.dev_gap}"
        )

    if "more technical" in lowered or "technical" in lowered:
        lines = ["### More technical angles"]
        for index, idea in enumerate(result.report.content_ideas, 1):
            outline = "; ".join(idea.outline[:3]) if idea.outline else "Add a runnable implementation demo."
            lines.append(f"{index}. {idea.title}: {outline}")
        return "\n".join(lines)

    if "comparison" in lowered or "vs" in lowered:
        lines = ["### Comparison reframing"]
        for index, idea in enumerate(result.report.content_ideas, 1):
            lines.append(
                f"{index}. Reframe '{idea.title}' as evaluation criteria, tradeoffs, and migration risks."
            )
        return "\n".join(lines)

    return None


def _first_number(text: str) -> int | None:
    for token in text.replace("#", " ").split():
        if token.isdigit():
            return int(token)
    return None
