# AI Shark Tank Practice Ground Plan

## Product Goal

AI Shark Tank should be a clean investor-practice room for founders at different stages:

- idea stage founders who need to turn a messy concept into a fundable pitch
- early operators with first revenue, customers, or pilots
- scaling founders who need sharper unit economics, growth strategy, and deal terms

The product should feel like entering a live investor room, not filling out a busy SaaS dashboard.

## Current Agentic Core

The backend now uses Mastra with:

- `pitch-duel-workflow`: deterministic 10-round Shark Tank simulation flow
- `minimax-founder-agent`: operational, numbers-heavy founder strategy
- `deepseek-founder-agent`: strategic, market-positioning founder strategy
- `investor-judge-agent`: extracts facts, asks questions, scores rounds, negotiates terms, and writes the report

Nebius remains the model provider through Mastra's OpenAI-compatible model config.

## Best Next UX Shape

Keep the first screen simple:

1. Studio background stays visible.
2. User writes one natural-language business prompt in the bottom dock.
3. A compact mode selector can sit near the prompt:
   - `Idea`
   - `Early Traction`
   - `Scaling`
   - `Fundraising`
4. A compact objective selector can sit near the prompt:
   - `Pitch Clarity`
   - `Growth Plan`
   - `Unit Economics`
   - `Investor Deal`

These options should not create a large form. They should simply guide the judge's questions and the founders' answer style.

## Better Simulation Flow

The app should show progress in a way that feels alive:

1. Judge extracts business facts and stage.
2. Judge reveals all 10 questions as a small timeline.
3. Each round streams in this order:
   - judge question
   - MiniMax Founder answer
   - DeepSeek Founder answer
   - judge score and round winner
4. After round 10:
   - judge negotiates final terms
   - final winner appears
   - report modal becomes available

No local fake fallback. If a model fails, show the real setup/model error.

## Practice Value

The report should become more useful than a transcript:

- investor readiness score
- top 3 pitch weaknesses
- top 3 strongest investor hooks
- rewritten 60-second pitch
- investor objections to rehearse
- suggested next data to collect
- recommended ask and milestone framing

## Clean Dashboard Later

A dashboard can exist, but should be secondary:

- saved pitch reports
- compare previous attempts
- stage filter
- score trend
- replay button

It should open from a small top button and never cover the core studio experience by default.

## Implementation Order

1. Add compact practice mode and objective controls.
2. Pass mode/objective into the Mastra workflow.
3. Make the judge adapt questions by founder stage.
4. Upgrade the report modal with readiness score and rewritten pitch.
5. Add a clean saved-reports dashboard modal.
6. Add a critic retry pass only when answers are vague or miss user facts.
