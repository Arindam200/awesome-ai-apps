# Whisper Input Product Context

## Product Register

- Register: Product UI
- Platform: Windows desktop application built with Tauri and React
- Primary users: Chinese-speaking workplace users who use voice input for daily writing and question answering
- Core purpose: turn speech into text, optionally polish or structure it with a configured LLM, and insert the result into the active application

## Design Direction

- Personality: quiet, trustworthy, efficient, and familiar
- Density: compact enough for a 1240 x 800 desktop window without sacrificing readable type or 40 px control targets
- Hierarchy: use spacing, alignment, typography, and lightweight separators before borders or shadows
- Component language: preserve the existing sidebar, settings tabs, cards, buttons, toggles, icon system, tokens, and Chinese/English localization
- Motion: restrained and functional; respect reduced-motion preferences

## Current Iteration

- Scope: Settings > Privacy & Data only
- Selected reference: the third generated layout shown on 2026-07-11
- Goal: make all privacy explanations and five existing controls visible in the standard desktop viewport
- Functional constraint: do not change copy, handlers, confirmation dialogs, persistence, API keys, provider configuration behavior, or diagnostic export behavior
- Responsive constraint: preserve the compact desktop composition and fall back to a single column when the content area becomes narrow

## Anti-References

- Avoid one oversized vertical list with large empty areas
- Avoid nested cards, heavy borders, decorative shadows, loud danger styling, and unnecessary new labels
- Avoid new icons, features, routes, buttons, or rewritten explanatory text
