In the early days of LLMs, "context" just meant plugging a few docs into RAG.

Now, you need a context optimization strategy.

Why? Agents juggle multiple data sources, tools, and memory types.

If you don't have a context optimization strategy, your agents will become slow, expensive, and increasingly unreliable.

So here are 5 key strategies to manage your LLM context window effectively:

𝟭/ 𝗦𝗲𝗹𝗲𝗰𝘁𝗶𝗻𝗴 𝘁𝗵𝗲 𝗿𝗶𝗴𝗵𝘁 𝗰𝗼𝗻𝘁𝗲𝘅𝘁

Don’t pass everything.
Use RAG + reranking to retrieve only the most relevant facts.

Structured outputs help the LLM break responses into logical parts, so only essential info flows downstream.

→ The goal: maximize information density per token.

𝟮/ 𝗖𝗼𝗻𝘁𝗲𝘅𝘁 𝗰𝗼𝗺𝗽𝗿𝗲𝘀𝘀𝗶𝗼𝗻

Long-running conversations overflow fast.

Summarize old messages, move key facts into long-term memory (e.g. mem0), and deduplicate redundant content with methods like MinHash.

Think of it as memory management for your agent (or garbage collection for context).

𝟯/ 𝗖𝗼𝗻𝘁𝗲𝘅𝘁 𝗼𝗿𝗱𝗲𝗿𝗶𝗻𝗴

LLMs remember the 𝘀𝘁𝗮𝗿𝘁 and 𝗲𝗻𝗱 of a prompt best.
They tend to forget what’s in the middle (the “lost-in-the-middle” effect).

So place critical instructions at the top.
Put recent or time-sensitive info at the bottom.

Everything else? Compress or skip it.

𝟰/ 𝗜𝘀𝗼𝗹𝗮𝘁𝗶𝗻𝗴 𝗰𝗼𝗻𝘁𝗲𝘅𝘁

Split complex tasks across specialized agents.

Each maintains its own focused context window, reducing interference and improving reasoning.

Think of it like classic separation of concerns applied to AI systems.

𝟱/ 𝗙𝗼𝗿𝗺𝗮𝘁 𝗼𝗽𝘁𝗶𝗺𝗶𝘇𝗮𝘁𝗶𝗼𝗻

Structure matters.
Use YAML or XML to clearly separate instruction types.

This helps the model reason more reliably.

Pro tip: YAML is ~66% more token-efficient than JSON.

𝗛𝗲𝗿𝗲'𝘀 𝘁𝗵𝗲 𝗺𝗮𝗶𝗻 𝗴𝗶𝘀𝘁:

Context engineering isn’t about giving LLMs more information.

It’s about giving them the right information, at the right time, in the right format.

I covered these strategies in my article about Context Engineering in Decoding AI Magazine.

Check it out here: https://lnkd.in/dTYs6ezm

Image credit: Thread on X by @lenadroid
