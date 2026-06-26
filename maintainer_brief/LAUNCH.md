# Launch Kit

## The post (X / LinkedIn)

> Never thought I'd say this, but this might be my favorite email ever.
>
> Every Monday at 8am, my agent sends me an intelligence brief about my open source project.
>
> It tells me:
>
> - Which feature requests are actually gaining momentum (clustered across GitHub, HN, Reddit)
> - Which conference talks and industry reports mention my project
> - What competitors announced — pulled from their slide decks
> - Which security advisories touch my dependency chain
> - Five concrete actions to take this week
>
> The interesting part: the best signals don't live in any API.
>
> They live in KubeCon schedule PDFs. Speaker decks. CNCF survey reports. RFCs. Advisory PDFs. The stuff nobody has time to read.
>
> Unsiloed converts those documents into structured JSON — feature requests with urgency, competitor launches, ecosystem mentions — each field with a confidence score and a word-level bounding-box citation. Every claim in my newsletter links to a viewer that highlights the exact sentence on the exact slide it came from.
>
> My agent doesn't just read 40 documents for me. It shows me its receipts.
>
> Maintainers, this is the new standard. Stop building roadmaps from whoever shouts loudest.
>
> Open source, link below. 👇

## Demo video beats (60–90s)

1. **The inbox.** Open Gmail, show the brief. Scroll the six sections. (3–5s per section.)
2. **The receipt.** Click "View source ↗" on a feature-request insight → citation viewer
   opens → highlight rectangle pulses on the KubeCon deck page. *This is the money shot.*
3. **The other receipt.** One more click-through — ideally a bbox on a *chart* in the
   CNCF survey PDF (visually striking).
4. **Live run.** Upload a fresh deck on the Documents page → "Run brief now" → stage
   ticker: ingesting → extracting with Unsiloed → writing the brief. (Pre-warm the rest
   of the corpus the day before — caching means only the new deck extracts live.)
5. **The config.** Flash `projects/meshery.yaml` — "point it at your own project."

## Demo data seeding checklist

Add to `projects/meshery.yaml` → `documents.urls` (or upload via dashboard):

- [ ] KubeCon + CloudNativeCon schedule PDF (Sched printable export)
- [ ] CNCF Annual Survey report PDF (cncf.io/reports) — charts make great bbox shots
- [ ] 1–2 CNCF TAG whitepapers mentioning service mesh (github.com/cncf/tag-network)
- [ ] 2–3 speaker decks as PDF exports (Speaker Deck / Sched attachments)
- [ ] A Meshery design doc / roadmap exported to PDF
- [ ] One security advisory saved as PDF (exercises the security schema)

**Pre-warm trick:** run the pipeline on the full corpus the day before recording.
Content-hash caching means the live "Run brief now" only extracts the freshly
uploaded deck — fast and dramatic — while the brief draws on everything.

## Pre-flight checklist

- [ ] `scripts/calibrate_bbox.py` run; correct bbox space set in CitationViewer
- [ ] Real email delivered to your inbox; renders in Gmail; deep links work
- [ ] Brief has ≥1 insight per section (tune document corpus if a section is empty)
- [ ] Dashboard screenshots at 1280px+ width, light room, no devtools open
- [ ] Repo public, README screenshot added, link in post
