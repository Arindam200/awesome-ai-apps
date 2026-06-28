# Maintainer Brief — UI Redesign Plan

Migrate from the current **editorial / cream-paper "neo-totalism"** theme to a
**modern technical light theme** in the spirit of the Formaly + Supermemory
references: light-grey canvas, white panels, hairline borders, sharp edges,
mono micro-labels, corner-bracket framing, and a confident blue accent.

The good news: the whole app is driven by **8 tokens in one `@theme` block**, so
the bulk of the migration is a token swap + a component-by-component restyle.
No data, API, or routing changes.

---

## 1. The shift (old → new design language)

| Aspect | Current | New |
|---|---|---|
| Canvas | Cream paper `#f5f4f0` | Light grey `#F6F7F9` |
| Accent | Copper `#b3502d` | Blue `#3553FF` (hover `#2840D6`) |
| Headlines | Georgia **serif italic** | Tight grotesque **sans** (Inter Tight) |
| Micro-labels | Bold uppercase sans | **Mono** uppercase, letter-spaced, with `[01/06]` indices |
| Edges | Soft, warm | **Sharp** (≤6px radius), crisp hairlines |
| Framing | Plain borders | **Corner-bracket frames**, full-width hairline dividers |
| Feel | Magazine / print | Product / engineering, "classy lines" |

---

## 2. Color system (new `@theme` block)

Replace the `@theme` block in `app/globals.css`:

```css
@theme {
  /* surfaces */
  --color-bg:          #F6F7F9;  /* page (light grey) */
  --color-surface:     #FFFFFF;  /* cards / panels */
  --color-surface-2:   #F0F2F5;  /* inset / hover fill */
  --color-line:        #E5E7EB;  /* hairline border */
  --color-line-strong: #D4D7DD;  /* emphasized divider */

  /* text */
  --color-ink:    #2B2926;  /* primary text */
  --color-muted:  #6B6F76;  /* secondary text */
  --color-faint:  #9AA0A6;  /* mono labels / tertiary */

  /* brand blue */
  --color-primary:       #3553FF;
  --color-primary-hover: #2840D6;
  --color-primary-soft:  #EEF1FF;  /* blue chip / badge bg */

  /* gold accent (secondary) */
  --color-gold:      #B8870F;
  --color-gold-soft: #FBF3E0;

  /* status (added as needed, palette-friendly) */
  --color-danger:      #B42318;
  --color-danger-soft: #FCEBEA;
  --color-success:     #1E7A4C;

  /* type */
  --font-sans:    "Inter", system-ui, sans-serif;
  --font-display: "Inter Tight", "Inter", sans-serif;  /* tight headlines */
  --font-mono:    "Geist Mono", "SF Mono", ui-monospace, monospace;

  --radius: 6px;  /* sharp-ish; chips/buttons 6px, frames 2–4px */
}
```

**Mechanical class map** (find/replace across `app/` + `components/`):

| Old | New |
|---|---|
| `bg-paper` | `bg-bg` |
| `bg-card` | `bg-surface` |
| `text-accent` / `bg-accent` | `text-primary` / `bg-primary` |
| `bg-accent-soft` | `bg-primary-soft` |
| `border-accent` | `border-primary` |
| `font-serif` (+ remove `italic`) | `font-display` |
| `text-ink`, `text-muted`, `border-line` | unchanged (values change in `@theme`) |

> Doing this find/replace first gives a safe checkpoint where the app already
> reads blue + light-grey with zero layout changes, before per-component polish.

---

## 3. Typography

- **Body:** Inter (400/500/600).
- **Display/headlines:** Inter Tight (600/700), tight tracking (`-0.02em`),
  large sizes. One word per headline in `text-primary` (the Formaly "highlight
  word" move).
- **Mono labels:** Geist Mono (or SF Mono), uppercase, `tracking-[0.18em]`,
  ~11px, `text-faint`. Used for eyebrows, section indices `[01/06]`, "LIVE
  PREVIEW", status text.

Load via `next/font` in `layout.tsx` (Inter + Inter Tight + Geist Mono → CSS
vars wired to `--font-*`).

---

## 4. Signature motifs (copy-paste building blocks)

**(a) Top accent strip** — a 3px blue bar pinned at the very top of the page
(Formaly has this). `<div className="fixed inset-x-0 top-0 z-[60] h-[3px] bg-primary" />`

**(b) Mono eyebrow / section-label row** — `› WHAT YOU GET ......... [01/06]`:

```tsx
// components/ui/SectionLabel.tsx
export function SectionLabel({ label, index, total }: {label:string; index?:number; total?:number}) {
  return (
    <div className="flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.18em] text-faint">
      <span className="text-primary">›</span>
      <span>{label}</span>
      <span className="h-px flex-1 bg-line" />
      {index && <span>[{String(index).padStart(2,"0")}/{String(total).padStart(2,"0")}]</span>}
    </div>
  );
}
```

**(c) Corner-bracket frame** — the "classy lines / sharp edges" look. A panel
with L-shaped ticks at each corner:

```css
/* globals.css */
.frame { position: relative; border: 1px solid var(--color-line); border-radius: 2px; background: var(--color-surface); }
.frame::before, .frame::after,
.frame > .br::before, .frame > .br::after { content:""; position:absolute; width:10px; height:10px; border-color: var(--color-primary); }
.frame::before { top:-1px; left:-1px; border-top:2px solid; border-left:2px solid; }
.frame::after  { top:-1px; right:-1px; border-top:2px solid; border-right:2px solid; }
.frame > .br::before { bottom:-1px; left:-1px; border-bottom:2px solid; border-left:2px solid; }
.frame > .br::after  { bottom:-1px; right:-1px; border-bottom:2px solid; border-right:2px solid; }
```

**(d) Blue icon chip** — rounded-square blue tile with a white Lucide icon
(feature cards):

```tsx
// components/ui/IconChip.tsx
export function IconChip({ icon: Icon }: { icon: LucideIcon }) {
  return <span className="grid h-10 w-10 place-items-center rounded-[6px] bg-primary text-white"><Icon size={18} strokeWidth={2}/></span>;
}
```

**(e) Buttons:**
- Primary: `bg-primary text-white hover:bg-primary-hover rounded-[6px] px-5 py-2.5 text-sm font-semibold` + optional trailing `arrow-right`.
- Secondary: `bg-surface border border-line hover:bg-surface-2`.
- Mono CTA (editorial): uppercase `font-mono tracking-[0.12em] text-[12px]`.

**(f) Logo mark** — corner-bracket square in blue (matches the references). Copy
as inline SVG into the Header:

```svg
<svg width="22" height="22" viewBox="0 0 24 24" fill="none">
  <path d="M3 8V3h5" stroke="#3553FF" stroke-width="2.5"/>
  <path d="M16 21h5v-5" stroke="#3553FF" stroke-width="2.5"/>
  <rect x="8" y="8" width="8" height="8" rx="1.5" fill="#3553FF"/>
</svg>
```

---

## 5. Icons to copy (Lucide — `npm i lucide-react`)

All from [lucide.dev](https://lucide.dev) (MIT, copy SVG or use `lucide-react`).

| Area | Usage → Lucide name |
|---|---|
| **Shell / nav** | Brief → `newspaper` · Compose → `send` · Signals → `activity` · Documents → `file-text` · Settings → `settings-2` · switcher → `chevron-down` · new → `plus` · CTA → `arrow-right` · external → `arrow-up-right` |
| **Brief sections** | Top Requested Features → `trending-up` · urgency hot → `flame` · Community Health → `heart-pulse` · Ecosystem Mentions → `megaphone` · Competitor Watch → `crosshair` (or `eye`) · Security Alerts → `shield-alert` · Recommended Actions → `list-checks` · citation → `quote` · source link → `external-link` |
| **Create flow** | repo search → `search` · stars → `star` · validated → `check-circle-2` · repo → `github` · keywords/topics → `tag` · remove chip → `x` · cadence → `calendar` |
| **Documents** | dropzone → `upload-cloud` · file → `file-text` · processing → `loader` (spin) · done → `check` · failed → `triangle-alert` |
| **Compose** | send to N → `mail` · test send → `flask-conical` · run now → `play` / `refresh-cw` |
| **Marketing chips** (optional hero grid) | AI → `sparkles` · chat → `message-square` · insights → `line-chart` · fast → `zap` · secure → `shield-check` |

---

## 6. Component primitives to create (`components/ui/`)

Build these once; every page consumes them:
`Button.tsx`, `Card.tsx` (surface + hairline + optional corner brackets + optional
bottom blue sheen), `Badge.tsx` (blue/gold/danger/neutral — drives urgency &
severity), `SectionLabel.tsx`, `Frame.tsx`, `IconChip.tsx`, `Input.tsx` /
`Toggle.tsx` / `SegmentedControl.tsx` (sharp, hairline, blue focus ring).

---

## 7. Step-by-step migration (phased, each phase is shippable)

**Phase 0 — Foundations.** Rewrite `@theme` (section 2), load fonts via
`next/font`, set `body` to `bg-bg/text-ink`, add motif CSS (frame, top strip),
swap citation-pulse color copper→blue. *Accept:* app compiles, canvas is grey.

**Phase 1 — Mechanical token swap.** Find/replace per section 2 map across all
files; delete `italic` on former serif headings. *Accept:* whole app reads
blue + grey, no layout drift. **Safe checkpoint / commit.**

**Phase 2 — Primitives.** Add `lucide-react` + the `components/ui/*` primitives
(section 6). *Accept:* a scratch page renders Button/Badge/Card/SectionLabel/Frame.

**Phase 3 — Shell (`layout.tsx`, `Header.tsx`).** Top accent strip; white header
with hairline; corner-bracket logo mark; nav as small mono-ish labels with blue
active underline; restyled project switcher; primary "＋ New brief". *Accept:*
header matches reference; switcher works.

**Phase 4 — Brief viewer (`app/page.tsx`).**
- *Empty/onboarding hero:* optional pill badge, big Inter-Tight headline with one
  blue highlight word, muted subtitle, primary + secondary buttons, mono
  sub-line (e.g. `WEEKLY · CITED SOURCES`), and a **framed sample-brief preview**
  (Frame + `LIVE PREVIEW` mono label + traffic-light dots).
- *Brief article:* each section header → `SectionLabel` with `[NN/06]` index;
  wrap content in `Card`; urgency/severity → `Badge`; recommendations as numbered
  list with blue index; `SourceLinks` → chips with `quote`/`external-link` icon.

**Phase 5 — Create flow (`app/new/page.tsx`, `ChipsInput.tsx`).** Gallery preset
cards with `IconChip`/emoji + hover lift + hairline; repo validation card (avatar,
`star` count, topic `tag` chips); inputs restyled (sharp, blue focus ring);
cadence as `SegmentedControl`; collapsible Advanced.

**Phase 6 — Compose (`app/compose/page.tsx`).** Two-pane: left controls (modern
`Toggle` switches for the 6 sections, restyled inputs), right preview framed like
an email client (`Frame` + `LIVE PREVIEW` + dots). Primary "Send to N", secondary
"Send test" with `flask-conical`.

**Phase 7 — Signals / Documents / Settings.**
- Signals: list/table with mono column headers + type `Badge`s.
- Documents: dashed-hairline dropzone with `upload-cloud`; doc cards with
  `file-text` + status `Badge`.
- Settings: `SectionLabel` groups, restyled inputs, a clearly separated
  **danger zone** (delete) using `--color-danger`.

**Phase 8 — Citations (`CitationViewer.tsx`, `citations/[signalId]`).** Wrap the
viewer in `Frame`; blue pulse highlight; restyled controls + `external-link`.

**Phase 9 — Email parity (`backend/app/newsletter/templates/brief.html.j2`).**
Update inline styles to the new palette (blue accent, ink text, hairlines, mono
eyebrows) so the delivered email matches the dashboard. *The email is the
product — keep it in sync.* (Email-safe: inline styles, no external fonts, tables.)

**Phase 10 — Polish & QA.** Blue `focus-visible` rings everywhere; hover
transitions; responsive (stack two-pane, collapse nav); `prefers-reduced-motion`;
favicon/logo; final pass via `/browse` or manual screenshots at 1280px+.

---

## 8. Choices I made (flag if you'd change them)

- **Display font = Inter Tight** (free, geometric, tight). Swappable for Space
  Grotesk / General Sans / a licensed grotesque if you have one.
- **Added `danger` + `success`** status colors (red/green) beyond blue+gold —
  needed for security severity and delete actions; kept restrained.
- **Gold `#B8870F`** is used as the *secondary* accent (badges, "high" urgency,
  highlights), not a primary surface — keeps blue dominant like the references.

---

## 9. Effort / sequencing

~10 files of UI + 1 email template. Phases 0–2 (~half a day) unlock everything;
3–8 are independent per-screen passes (parallelizable); 9–10 are finishing. Each
phase compiles and is committable on its own, so we can ship the redesign
incrementally without a long-lived broken branch.
```
```
