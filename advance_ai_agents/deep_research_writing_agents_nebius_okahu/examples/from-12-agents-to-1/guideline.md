# LinkedIn Post Guideline

## Topic
Why most AI teams should use 1 agent instead of 12 — a decision framework for choosing the right AI agent architecture.

## Angle
Open with the counterintuitive insight that a team replaced 12 planned agents with 1 and got better results. Use this as a hook to introduce the complexity spectrum (workflows → single agent → multi-agent) and the principle that simpler systems win. End with a clear mental model readers can apply immediately.

## Target Audience
AI engineers, ML engineers, and technical leads who are building or planning LLM-powered applications and are tempted to jump straight to multi-agent architectures.

## Key Points to Cover
* The hook: a team planned 12 agents but shipped 1 — and it worked better because tasks were tightly coupled and sequential.
* The complexity spectrum: workflows (you control steps) → single agent + tools (model controls flow) → multi-agent (multiple decision-makers). Move right only when forced.
* The "context rot" problem: past ~10-20 tools, LLMs degrade at tool selection due to "loss in the middle" attention patterns.
* The only 4 valid reasons for multi-agent: true parallelism, context overload, third-party modularity, hard security boundaries.
* The takeaway: "The simplest system that reliably solves the problem is always the best system."

## Tone
Direct, opinionated, and practical. No fluff. Speak engineer-to-engineer. Use short punchy sentences. The post should feel like hard-won advice from someone who has seen teams waste months overengineering.

## Constraints
* Target ~1200 characters for the final post.

## Resources

- [Stop Overengineering: Workflows vs AI Agents Explained](https://www.youtube.com/watch?v=_rO2fv6tSsQ)
