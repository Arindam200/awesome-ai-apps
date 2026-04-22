import os
from crewai import Agent, Crew, LLM, Process, Task


def build_llm(model_id: str) -> LLM:
    return LLM(
        model=f"nebius/{model_id}",
        api_key=os.getenv("NEBIUS_API_KEY"),
    )


CLAUSE_TYPES = [
    "Parties & Effective Date",
    "Term & Termination",
    "Payment & Fees",
    "Confidentiality / NDA",
    "Intellectual Property",
    "Representations & Warranties",
    "Limitation of Liability",
    "Indemnification",
    "Non-Compete / Non-Solicit",
    "Governing Law & Jurisdiction",
    "Dispute Resolution / Arbitration",
    "Assignment & Change of Control",
    "Data Protection / Privacy",
    "Force Majeure",
    "Miscellaneous (notices, severability, entire agreement)",
]


def build_crew(model_id: str, contract_text: str, party_perspective: str) -> Crew:
    llm = build_llm(model_id)

    extractor = Agent(
        role="Contract Clause Extractor",
        goal=(
            "Identify, label, and quote every material clause from the "
            "provided contract with precise references."
        ),
        backstory=(
            "You are a meticulous paralegal who has read thousands of "
            "commercial contracts. You never paraphrase clauses when a "
            "direct quote will do, and you never invent text that is not "
            "in the document."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    risk_analyst = Agent(
        role="Legal Risk Analyst",
        goal=(
            f"Score each extracted clause for risk from the perspective "
            f"of {party_perspective}, using Low / Medium / High with a "
            f"short rationale."
        ),
        backstory=(
            "You are a senior contracts attorney who specializes in "
            "protecting your client from one-sided terms, unbounded "
            "liability, and hidden operational obligations."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    reviewer = Agent(
        role="Senior Paralegal Reviewer",
        goal=(
            "Produce a final contract review memo summarizing clauses, "
            "risks, and redline recommendations."
        ),
        backstory=(
            "You consolidate the work of the extractor and risk analyst "
            "into a clean, executive-ready memo with clear next steps."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    extract_task = Task(
        description=(
            "You will receive the full text of a contract below. Extract "
            "every material clause and map it to one of these categories:\n"
            f"{chr(10).join('- ' + c for c in CLAUSE_TYPES)}\n\n"
            "For EACH clause produce:\n"
            "1. Category (from the list above, or 'Other')\n"
            "2. Section / heading reference as it appears in the contract\n"
            "3. A verbatim quote (<= 400 chars; truncate with ... if longer)\n"
            "4. A one-sentence plain-English summary\n\n"
            "Return the result as a Markdown table with columns: "
            "Category | Section | Quote | Summary.\n\n"
            "CONTRACT TEXT:\n"
            f"\"\"\"\n{contract_text}\n\"\"\""
        ),
        expected_output=(
            "A Markdown table with one row per material clause."
        ),
        agent=extractor,
    )

    risk_task = Task(
        description=(
            "Using the extracted clauses from the previous task, score "
            f"each one for risk from the perspective of {party_perspective}. "
            "Output a Markdown table with columns: "
            "Category | Risk (Low/Medium/High) | Why it matters | "
            "Suggested redline.\n\n"
            "Scoring guidance:\n"
            "- High: uncapped/broad liability, one-sided indemnity, "
            "auto-renewal without notice, IP assignment giveaways, "
            "unilateral termination rights against our client, "
            "unfavorable governing law, broad non-competes.\n"
            "- Medium: vague SLAs, ambiguous payment terms, "
            "confidentiality carve-outs, assignment without consent.\n"
            "- Low: standard boilerplate with balanced terms.\n"
            "Finish with a single 'Overall Contract Risk' line: "
            "Low / Medium / High, plus a 2-sentence justification."
        ),
        expected_output=(
            "A Markdown risk table followed by an overall risk rating."
        ),
        agent=risk_analyst,
        context=[extract_task],
    )

    review_task = Task(
        description=(
            "Write the final Contract Review Memo in Markdown with these "
            "sections:\n"
            "1. **Executive Summary** (3-5 bullets: what this contract is, "
            "key commercial terms, overall risk verdict).\n"
            "2. **Key Clauses** (table from the extractor, trimmed to the "
            "most material rows).\n"
            "3. **Risk Assessment** (table from the risk analyst).\n"
            "4. **Recommended Redlines** (numbered list of the top 5-8 "
            "changes to request, each with a one-line rationale).\n"
            "5. **Open Questions for Counsel** (bullets: anything you "
            "cannot determine from the document alone).\n\n"
            f"Client perspective: {party_perspective}.\n"
            "Never invent clauses that were not identified by the "
            "extractor. Close the memo with a disclaimer that this is "
            "an AI-generated review and not legal advice."
        ),
        expected_output="A complete Markdown review memo.",
        agent=reviewer,
        context=[extract_task, risk_task],
    )

    return Crew(
        agents=[extractor, risk_analyst, reviewer],
        tasks=[extract_task, risk_task, review_task],
        process=Process.sequential,
        verbose=True,
    )


def run_review(model_id: str, contract_text: str, party_perspective: str) -> str:
    crew = build_crew(model_id, contract_text, party_perspective)
    result = crew.kickoff()
    return getattr(result, "raw", str(result))
