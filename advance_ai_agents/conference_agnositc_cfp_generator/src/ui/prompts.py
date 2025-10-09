"""
Prompt templates for the Conference Talk RAG System
Contains all structured prompts for generating talk proposals
"""

from typing import List, Dict, Any
def create_talk_proposal_prompt(
    query: str,
    conference_info: Dict[str, Any],
    similar_talks: List[Dict[str, Any]],
    adk_research: str
) -> str:
    """
    Create the structured prompt for generating talk proposals

    Args:
        query: User's talk idea
        conference_info: Conference metadata (name, year, platform, etc.)
        similar_talks: List of similar talks from the database
        adk_research: Real-time research context

    Returns:
        Formatted prompt string for the LLM
    """

    # Prepare historical context in the structured format
    if similar_talks:
        historical_context = "\n\n".join([
            f"Title: {talk.get('title', 'N/A')}\n"
            f"Description: {talk.get('description', 'N/A')}\n"
            f"Category: {talk.get('category', 'N/A')}\n"
            f"Speaker: {talk.get('speaker', 'N/A')}\n"
            f"Relevance Score: {talk.get('score', 0):.3f}"
            for talk in similar_talks
        ])
    else:
        historical_context = f"No similar historical talks were found in the {conference_info.get('name', 'conference')} database."

    # Prepare research context
    research_context = adk_research if adk_research and adk_research != "Research unavailable" else \
                      "Real-time research context unavailable."

    # Create the enhanced structured prompt based on the original approach
    prompt = f"""You are an expert conference program advisor for {conference_info.get('name', 'technical conferences')}.
Your mission is to create a compelling, unique, and timely talk proposal.

**User's Core Idea:** "{query}"

To assist you, here is a two-part analysis:

---
**PART 1: HISTORICAL CONTEXT (FROM CONFERENCE DATABASE)**
These are similar talks that have been given at {conference_info.get('name', 'this conference')} in the past. Your proposal MUST offer a fresh perspective or build upon these in a novel way. Do not simply repeat these topics.

{historical_context}
---
**PART 2: REAL-TIME WEB ANALYSIS (FROM RESEARCH AGENT)**
This is a fresh analysis of what's currently happening on the web regarding this topic (latest discussions, emerging tech, community sentiment). This provides the "zeitgeist" and reveals current gaps.

{research_context}
---

**YOUR TASK:**
Synthesize the information from ALL parts above (user idea, historical context, and real-time analysis). Create a complete talk proposal that is timely, avoids repetition, and addresses a genuine gap or novel angle.

**REQUIRED OUTPUT FORMAT:**

**Title:**
*A compelling, modern title that captures the essence of your unique angle.*

**Abstract:**
*A detailed 2-3 paragraph summary. It should briefly acknowledge the existing landscape and then clearly explain what new insights, techniques, or case studies this talk will present.
   1. Focuses on end-user/practitioner perspective
   2. Builds upon existing concepts rather than repeating them
   3. Follows a similar structure to successful conference talks
   4. Addresses current trends and gaps in the topic area*
   **Note:** Maintain word limit should be 200-250 words

**Key Learning Objectives:**
*Provide 3-4 bullet points of what an attendee will learn.*

**Target Audience:**
*Specify the ideal audience (e.g., Beginner DevOps Engineers, Expert SREs, Platform Architects, etc.).*

**Why This Talk is Timely:**
*Explain why this topic is important RIGHT NOW, referencing current trends identified in the real-time analysis.*

**Why This Talk is Unique:**
*A crucial section explaining precisely how this talk differs from past talks shown in the historical context and aligns with the current trends identified in the real-time analysis.*

**Benefits to the Ecosystem:**
*An important section explaining how this talk will benefit general ecosystem of that conference (refer it from the conference context) and audience attending it. Give 3-5 bullet point based answer*"""

    return prompt


def get_system_message() -> str:
    """
    Get the system message for the LLM

    Returns:
        System message string
    """
    return "You are a world-class conference program advisor with deep expertise in technical conferences and emerging technology trends."


# Additional prompt templates can be added here as needed
def create_research_analysis_prompt(topic: str) -> str:
    """
    Create prompt for analyzing research results

    Args:
        topic: The research topic

    Returns:
        Formatted prompt for research analysis
    """
    return f"""You are a meticulous research analyst using advanced AI capabilities.
Analyze the provided search results and create a comprehensive research summary for the topic: "{topic}".

Focus on extracting:
1. **Latest Developments**: What's new in the field?
2. **Community Insights**: What are developers/practitioners discussing?
3. **Technical Gaps**: What problems need solving?
4. **Emerging Trends**: What's gaining momentum?

Use clear markdown formatting and be comprehensive yet concise.
Ignore any search errors and focus on successful results."""