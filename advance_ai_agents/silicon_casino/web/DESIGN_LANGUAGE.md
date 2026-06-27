# Silicon Casino Spectator UI — Design Language

This document captures the current visual system and interaction language used in the spectator frontend.

## 1) Design Principles
- **Cyberpunk Pixel**: Mix retro pixel-culture with modern neon gradients and CRT artifacts.
- **High-contrast Legibility**: Dark canvas, luminous accents, and monospace typography for clarity.
- **System-as-theater**: Every panel feels like a console screen in an arena control room.
- **Motion as meaning**: Animation is used to explain game state (burn, chips, showdown), not as decoration.

## 2) Typography
- **Display / Brand**: `Press Start 2P`
  - Used in the brand title and main hero heading.
  - Intentionally pixelated to set the retro/cyber tone.
- **UI / Body**: `Share Tech Mono`
  - Used for all UI copy, labels, and data readouts.
  - Ensures consistent numeric alignment and terminal-style feel.

## 3) Color System

### Base
- **Background**: deep midnight gradient
  - `#070a12` → `#0a0f1c` → `#1a2340`
- **Panel**: `#0f1629`
- **Panel Border**: `#243b6b`
- **Muted Text**: `#7b8bb7`
- **Primary Text**: `#e6f1ff`

### Neon Accents
- **Neon Cyan**: `#7dd3fc`
- **Neon Pink**: `#f472b6`
- **Neon Green**: `#34d399`
- **Neon Amber**: `#fbbf24`

### Status Colors
- **Connected**: `#86efac`
- **Connecting/Reconnecting**: `#93c5fd`
- **Error**: `#fecaca`
- **Disconnected**: `#fca5a5`
- **Demo**: `#fde68a`

## 4) Layout & Spacing
- **Page padding**: `32px`
- **Grid gaps**: `16–24px`
- **Panels**: 1px neon border, translucent interior
- **Cards**: 12–16px padding
- **Rounded corners**: subtle (6–10px) on elements, 24–28px on the Pixi table

## 5) Core Components (Visual Rules)

### Navigation
- Sticky-looking top bar with blur (`backdrop-filter: blur(6px)`).
- Brand title in pixel font.
- Active link uses neon cyan underline.
- CTA button uses gradient from blue to teal.

### Panels
- **Background**: `var(--panel)`
- **Border**: `var(--panel-border)`
- **Title**: neon cyan, small caps feel

### Buttons
- **Primary**: gradient fill, dark text, bold.
- **Ghost**: transparent with cyan border.
- **Hover**: slight lift with shadow.

### Metrics / Stats
- Large numeric emphasis, muted labels.
- Should be readable at a glance from distance.

### Logs
- Monospace alignment.
- Dashed separators.
- Thought logs accent in neon green.

## 6) Visual Effects

### CRT/Scanline Overlay
- Global `::before` overlay on `.app-root`.
- Animated opacity (“flicker”) to simulate CRT artifact.

### Table FX (Pixi)
- **Burn Rate**: upward drifting particles in pink.
- **Chip Move**: small amber discs animating to pot center.
- **Showdown Flash**: cyan screen wash for 600ms.
- **Thought Bubbles**: text above seats for 6 seconds.

## 7) Information Hierarchy
- **Hero**: pixel font, big size, short lines.
- **Panels**: micro-headers + short data lines.
- **Game State**: Table HUD uses compact key/value lines.
- **Action Logs**: time → action → thought snippet.

## 8) Accessibility & Readability
- Avoid pure neon text on pure black.
- Use muted text for secondary labels.
- Keep line height ~1.6 on long text blocks.

## 9) Current CSS Variables
Located in `web/src/styles.css`:
- `--neon-cyan`
- `--neon-pink`
- `--neon-green`
- `--neon-amber`
- `--panel`
- `--panel-border`
- `--muted`

## 10) Future Extensions (Planned)
- Add iconography set (pixel/CRT style).
- Define motion timing tokens.
- Introduce theme variants (darker arena vs. broadcast overlay).

---

If you want a more formal design system spec (tokens, scales, component anatomy), say the word and I’ll expand this into a full system guide.
