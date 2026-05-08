99% of engineers skip the most important part of building agents:

Which pattern to use and why?

Agentic systems are not one thing...

They sit on a spectrum of control, flexibility, cost, and debuggability.

At a high level:

• Workflows execute a predefined sequence of steps. They are fast, testable, and cost-efficient.
• Agents decide what to do next. They handle ambiguity well, but introduce latency, variability, and harder debugging.
• Semi-workflows combine both. A deterministic backbone, with agentic branches only where interpretation or judgment is required.

The hybrid approach is where most production systems end up.

But let’s look at 5 core agentic patterns and how they apply to a real system:

𝟭/ 𝗥𝗲𝗔𝗰𝘁
The classic loop: reason, act, observe, repeat.

Useful when:

• The path forward is unclear
• Multiple tools must be selected dynamically
• The agent must adapt mid-execution

Trade-off:

• High flexibility
• Higher latency and cost
• More complex traces

𝟮/ 𝗦𝗲𝗹𝗳-𝗥𝗲𝗳𝗹𝗲𝗰𝘁𝗶𝘃𝗲 𝗔𝗴𝗲𝗻𝘁
A controlled quality loop.

Flow:

1. Prepare context deterministically
2. Draft an initial response
3. Reflect against a rubric
4. Revise for a limited number of cycles
5. Deliver the final output

Why it works:

• Significant quality gains for a small token increase
• Predictable behavior
• Easy to audit and reason about

This pattern is ideal when consistency and tone matter more than raw speed.

𝟯/ 𝗡𝗲𝘁𝘄𝗼𝗿𝗸 𝗼𝗳 𝗔𝗴𝗲𝗻𝘁𝘀 (𝗦𝘄𝗮𝗿𝗺)
Multiple agents collaborate on the same problem.

Useful when:

• Tasks can run in parallel
• Domains are clearly separable
• Context would overload a single agent

Risk:

• Coordination overhead
• Context silos
• Difficult debugging if roles are not sharply defined

𝟰/ 𝗦𝘂𝗽𝗲𝗿𝘃𝗶𝘀𝗼𝗿 𝗣𝗮𝘁𝘁𝗲𝗿𝗻
A coordinator agent delegates tasks to specialized workers.

The supervisor:

• Plans
• Assigns subtasks
• Aggregates results

This works well when responsibilities are clear and outputs are structured.

𝟱/ 𝗛𝘆𝗯𝗿𝗶𝗱 𝗪𝗼𝗿𝗸𝗳𝗹𝗼𝘄 (𝗦𝗲𝗺𝗶-𝘄𝗼𝗿𝗸𝗳𝗹𝗼𝘄)
A deterministic pipeline with agentic branches.

This is the most common production pattern.

Why:

• Deterministic steps handle data fetching, validation, and side effects
• Agents are reserved for interpretation and judgment
• Control flow stays understandable and testable

Any agent framework you encounter maps back to one of these 5.

Here's the core gist:

Agentic design is about choosing the simplest pattern that solves the problem.

• Use workflows when the path is known
• Use agents when ambiguity exists
• Combine them when reality demands both

This breakdown comes from Lesson 3 of the open-source course Designing Enterprise MCP Systems, published in Decoding AI Magazine.

Want to read?

Check it out here: https://lnkd.in/eP28fW4d

P.S. Huge thanks to Anca Ioana Muscalagiu for writing this lesson and articulating these patterns so clearly.
