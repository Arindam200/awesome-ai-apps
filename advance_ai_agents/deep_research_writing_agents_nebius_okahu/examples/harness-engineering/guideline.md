# LinkedIn Post Guideline

## Topic
What is harness engineering and why it matters for AI engineers

## Angle
Explain harness engineering as the discipline of building reliable systems around AI agents — not just prompting them. Draw heavily from the video's framework: prompt engineering = what to ask, context engineering = what to send, harness engineering = how the whole thing operates. Use the car analogy (model = engine, context = fuel, harness = the rest of the car). Show why this shift happened (agents got good enough to be useful but not reliable enough to trust alone) and what it means for how software gets built.

## Target Audience
AI engineers, ML engineers, software engineers building with or interested in AI agents

## Key Points to Cover
- The progression: prompt engineering → context engineering → harness engineering
- Why it emerged: agents got good enough to be useful AND dangerous
- The car analogy: model is the engine, context is fuel/oil, harness is steering/brakes/lane boundaries
- What a harness includes: tools, permissions, state, tests, logs, retries, checkpoints, guardrails, evals
- Real examples: Anthropic's long-running agents, OpenAI's million-line zero-manual-code product, Stripe's 1000+ merged PRs/week, LangChain moving from outside top 30 to top 5 by changing only the harness
- The mindset shift: stop hoping the model does better, engineer the environment so it can't make the same mistake again
- End with CTA linking to the full video: https://youtu.be/zYerCzIexCg

## Tone
Clear, direct, educational. Conversational but authoritative. The reader should walk away understanding what harness engineering is and why it's the direction AI is heading.
