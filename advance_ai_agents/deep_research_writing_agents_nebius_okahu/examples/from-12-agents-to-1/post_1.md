We planned 12 AI agents. We shipped 1. It worked better.

Sounds crazy, right? But it's a common story.

A client wanted an AI chatbot for marketing content: emails, SMS, promos. Their initial design had dozens of specialized agents: orchestrator, analyzers, validators, spam prevention.

In practice? A single agent with tools won. Its tasks were tightly coupled and sequential. Splitting it created information silos and handoff errors. One brain maintained context, made decisions. Tools were still specialized.

This is the core mistake. People jump to complex multi-agent setups too fast.

Think of AI system design as a spectrum:
*   Workflows: You control every step.
*   Single Agent + Tools: Model decides the flow.
*   Multi-Agent: Multiple decision-makers coordinate.

**Stay as far left as possible.** Move right only when forced. Each step right increases cost, latency, debugging, and failure points. More LLM calls mean more tokens, more traces.

A single agent with tools works for most cases. But it has limits. Too many tools? You hit "context rot." Past ~10-20 tools, LLMs degrade at tool selection. They get overwhelmed. Information gets lost in the middle.

So, when do you actually need multi-agent?
Only 4 valid reasons:
1.  True Parallelism: Tasks are genuinely independent.
2.  Context Overload: Single agent context is too packed.
3.  Modularity: You need reusable or third-party agent systems.
4.  Security Boundaries: Strict data isolation or compliance.

We built an article generator. We started with one agent for research and writing. It broke. Research is exploratory. Writing is constrained. We needed two agents with a clear handoff. Each had its own lean, focused context.

**The simplest system that reliably solves the problem is always the best system.**

Don't overengineer your AI agents. Build simple first.

What's the most complex agent architecture you've simplified? Tell me below.