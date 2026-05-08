Harness engineering isn't just a new term for prompt engineering. It's where AI is heading.

Agents got useful enough for code and tools, but they weren't reliable. They'd repeat mistakes. The bottleneck shifted from code generation to consistent, reliable behavior in real systems.

Think of it this way: prompt engineering is what to ask. Context engineering is what to send the model. Harness engineering is **how the whole thing operates**. It's the environment *around* the model, beyond just tokens.

Car analogy: the model is the engine. Context is the fuel. **The harness is the rest of the car**: steering, brakes, lane boundaries. It prevents crashes.

A harness includes tools, permissions, state, tests, logs, retries, checkpoints, guardrails, and evals.

Stop hoping the model improves. Engineer its environment. The burden shifts to us, the builders, to prevent repeat mistakes.

I use self-reflection in my Claude Code setup. The agent learns what I liked, saving tokens and time.

Real companies are already doing this. Anthropic's long-running agents externalize memory into artifacts. OpenAI built a 1M-line product with zero manual code using structured docs and agent-to-agent reviews. Stripe agents merge 1K+ PRs weekly within isolated environments. LangChain moved a coding agent from outside the top 30 to top 5 on Terminal Bench 2.0 by changing *only* the harness. Same model, better system.

This isn't just for coding agents. This is the new way software gets built.

The programmer's job is shifting: less writing code, more designing habitats for agents to work without issues. Think machine-readable docs, evals, sandboxes, permission boundaries, and structural tests.

Reliability is the real work. Not just prompting.

LLMs are heading into systems, workflows, harnesses. Value comes from orchestration, constraints, feedback loops—not just a single prompt. The future isn't one genius model. It's models in well-engineered environments.

That's why **harness engineering** matters. It's what happens when you stop demoing intelligence and start shipping it.

Want to learn more? I explain it all in my latest video: https://youtu.be/zYerCzIexCg What's your biggest challenge building reliable agent systems right now?