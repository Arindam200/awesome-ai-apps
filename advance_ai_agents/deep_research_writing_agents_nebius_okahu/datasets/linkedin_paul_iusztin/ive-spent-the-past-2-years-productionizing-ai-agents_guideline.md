# LinkedIn Post Guideline

## Topic
This post should argue for the critical importance of durable workflow orchestration tools over AI-specific frameworks when building and deploying AI agents in production.

## Angle
The post should present an "unpopular opinion" or contrarian viewpoint, challenging the common focus on AI frameworks by highlighting a more foundational, often overlooked aspect: durability and resilience. It should demonstrate the hidden costs of lacking durability with quantified examples and provide a clear hierarchy of priorities for building robust AI systems.

## Target Audience
This post is for ML engineers, software architects, and technical leaders involved in designing, building, or scaling AI agents for production environments. They are concerned with system reliability, efficiency, and cost-effectiveness.

## Key Points to Cover
*   AI frameworks primarily solve the "reasoning" layer (making agents smart), but not the "durability" layer (handling failures, retries, state management).
*   Lack of durable execution leads to significant hidden costs in production (e.g., wasted tokens, duplicated writes, debugging time), which scale rapidly.
*   Traditional workflow orchestrators may not suit the dynamic nature of AI agent decision-making, emphasizing the need for tools that integrate with normal Python control flow.
*   Prioritize establishing a robust and durable infrastructure layer for AI agents first, as it's foundational and harder to swap than reasoning layers.
*   AI frameworks are optional and can be integrated later if truly needed, whereas durability is non-negotiable for production systems.

## Tone
The tone should be authoritative, experienced, and opinionated, yet educational and data-driven. It should be confident in its contrarian stance, backing it with practical examples and cost implications, without being overly dismissive of AI frameworks.