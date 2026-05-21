# Vélib Wizard — Storytelling Website Design

**Date:** 2026-05-21
**Author:** Paolo Lancellotti (with Claude)
**Status:** Approved, awaiting implementation plan

## Goal

Add a public-facing storytelling website to the existing Vélib Wizard project. The site narrates, in a personal "DIY zine" tone, the problem the Wizard solves and how it works. The existing interactive dashboard becomes a separate page reachable from the new landing.

The site must do two things at once:

1. **Entertain.** Heavy, satisfying animations that make a visitor want to scroll back up just to watch them again.
2. **Explain the tech honestly.** The Wizard is a real ML forecaster — the site must convey that truthfully (in plain language, without hype) without losing the playful tone.

## Audience and tone

- **Audience:** primarily portfolio reviewers (recruiters, hiring managers, fellow developers), but the site is friendly to any casual visitor.
- **Tone:** first-person, slightly self-deprecating, hand-made vibe. Bottom-of-the-page-zine voice, not corporate marketing.
- **Language:** entire site copy in **English**. The hand-drawn nature of the type and the French city naturally allows a few French phrases (e.g. *"...mais où le garer?"*) for flavor.

## Narrative arc

A single linear story: *I love Vélib → but there's this one problem that drives me mad → so I built the Wizard*. The narrative carries through nine sections; the user scrolls and the story unfolds.

## Architecture and routing

The site lives inside the existing Next.js 16 app at `web/`. **No new project, no new deploy target.** One Vercel deploy serves everything.

### Route changes

| Path | Current | After |
|---|---|---|
| `/` | `<MapView />` (the dashboard) | Storytelling landing page |
| `/dashboard` | does not exist | `<MapView />` (moved from `/`) |
| `/network`, `/station/[id]`, `/status` | as-is | as-is |

### Shared navigation

A new `<Navbar />` component is added to `src/app/layout.tsx`. It is:

- **Logo on the left** (`/logo-mark.png`, links to `/`).
- **Links on the right:** `Story` (`/`), `Network` (`/network`), and a primary CTA **`Dashboard →`** styled as a green accent button.
- On `/` (story) it starts transparent and solidifies into white on scroll.
- On all other pages it is solid white from the start.

### File layout

```
web/src/app/
  page.tsx                  # Story page (new)
  dashboard/page.tsx        # MapView wrapper (new, moved from root)
  layout.tsx                # Adds <Navbar />
  network/page.tsx          # unchanged
  station/[id]/...          # unchanged
  status/page.tsx           # unchanged
  _story/                   # Private folder (underscore prefix, not routed)
    sections/
      Hero.tsx
      Love.tsx
      TheRide.tsx           # the horizontal-scroll showcase
      Problem.tsx
      Stakes.tsx
      Idea.tsx
      HowItWorks.tsx
      SeeItLive.tsx
      Footer.tsx
    components/
      Navbar.tsx
      Path.tsx              # animated SVG path
      Monument.tsx          # collage-cutout monument component
      Underline.tsx         # hand-drawn underline SVG
      CountUp.tsx           # number animation
    lib/
      gsap.ts               # GSAP init + ScrollTrigger plugin registration

web/public/story/           # Optimized site assets (new)
  velib-bike.webp
  eiffel.webp
  louvre.webp
  sacre-coeur.webp
  notre-dame.webp
  (any additional collage pieces)
```

Source PNGs in `website/velib.artwork/` are preprocessed (watermark removal where needed, compression, WebP conversion) into `web/public/story/`. The `website/` folder remains as the asset workshop.

## Tech stack additions

Added to `web/package.json`:

| Package | Version target | Purpose |
|---|---|---|
| `gsap` | ^3.13 | Animation engine + `ScrollTrigger` plugin. GSAP and all official plugins became free for all use after Webflow's acquisition of GreenSock (2024). |
| `motion` | ^11 | Component-level React animations (the modern, lighter rename of `framer-motion`). |
| `clsx` | ^2 | Conditional className helper. |

Fonts loaded via `next/font/google` (zero runtime overhead):

- **Display (hand-drawn):** `Caveat` — used for headings, big numbers, pull quotes.
- **Body (clean):** `Inter` — paragraphs, navbar, technical copy.

Final font choice between `Caveat` and `Patrick Hand` may be revisited during implementation by running both side-by-side; we ship one.

### Color palette extension

Existing palette in `web/src/app/globals.css`:
- Vélib light blue `#5fbcd2`
- Vélib dark blue `#0e5e7a`
- White

Added:
- `--accent-green` `#a3d63a` — the Smoove green from the bike PNGs. **Reserved for primary CTAs and small decorative highlights only** (Dashboard button, "See it live" CTA, occasional underlines).
- `--paper` `#fafaf7` — off-white background for sections that need a "zine paper" feel (STAKES, HOW IT WORKS).

## The nine sections

Each section is its own React component in `_story/sections/`. The page composes them in order in `page.tsx`. Copy below is a **draft** to be refined during implementation; numbers and exact phrasing may change.

### 1. HERO

- Full-height, sticky transparent navbar.
- **Headline:** *"The Vélib Wizard"* (Caveat display, with hand-drawn zigzag underline).
- **Subhead:** *"I built a model that tells you if your station will be full in 2 hours. Because Paris."*
- **Visual:** the bike rolls in from the left and parks at the center-bottom; small pulsing "See the wizard ↓" indicator below.
- **Animation:** headline writes letter-by-letter (stagger); bike enters with rotating wheels.

### 2. LOVE

- White section, text-and-stats hybrid.
- **Copy:** *"Everybody loves the Vélib. Locals, tourists, food delivery riders, dads with kids. It's the cheapest way to feel Parisian for 5 minutes."*
- **Visual:** three stat counters side-by-side — `~20,000 bikes` · `~1,400 stations` · `~150K trips/day`.
- **Animation:** count-up on enter; hand-drawn underlines appear under selected keywords (e.g. *Parisian*).

### 3. THE RIDE — horizontal scroll showcase

The heart of the entertainment. See "THE RIDE in detail" below.

### 4. PROBLEM

- Full-bleed Vélib-blue (`#5fbcd2`) section.
- **Copy:** *"But there's one thing that drives me mad. You arrive. The station is full. Every slot has a bike. Now what?"*
- **Visual:** a hand-drawn station rack with ~10 slots is shown empty at top; slots fill with red bikes one-by-one on scroll. A stick-figure rider arrives at the bottom with a question mark over their head.
- **Animation:** slot fill sequenced on scroll progress; rider enters last.

### 5. STAKES

- `--paper` background.
- **Copy:** *"Sometimes you ride 15 more minutes just looking for a free slot."*
- **Visual:** giant `31` numeral (Caveat, ~280pt), with caption: *"the % of stations completely full at 8:45am in central Paris."* A hand-drawn stopwatch spins next to it.
- **Animation:** the `31` writes itself in; stopwatch rotates.
- **Note:** the exact number is computed from the live database during implementation. If the real number is undramatic, the framing changes (e.g. *"minutes lost per week"* or *"hours saved per year"*). We do not invent numbers.

### 6. IDEA

- Transition section, white background fading toward Vélib blue.
- **Copy:** *"So I built a Wizard that tells you in advance."*
- **Visual:** a lightbulb illuminates over the stick figure; bike emoji transforms into 🧙.
- **Animation:** lightbulb on, SVG sparkles, background gradient transitions on scroll.

### 7. HOW IT WORKS — the honest technical section

Full-height, `--paper` background. Three steps stacked vertically, connected by hand-drawn arrows. See "HOW IT WORKS in detail" below.

### 8. SEE IT LIVE

- Vélib-dark-blue (`#0e5e7a`) section.
- **Copy:** *"Want to see it on your station? Pick a station. See the next 10 hours."*
- **Visual:** simplified Paris map (Seine + ~4 districts) with red/yellow/green pins pulsing. Large `--accent-green` CTA button: **"Try the Wizard →"** linking to `/dashboard`.
- **Animation:** pins pulse; CTA has hover micro-interaction (scale 1.05 + growing shadow).

### 9. FOOTER

- Compact dark-blue section.
- **Copy:** *"Built solo by Paolo Lancellotti as a portfolio project · 2026"* with GitHub / Portfolio / Email links and a monospaced stack line: *"Data: Vélib' Métropole GBFS · Model: LightGBM · Hosted on Vercel + Render free tier"*.
- **Visual:** a small bike pedals slowly left-to-right on infinite loop — "the journey continues".

## THE RIDE in detail

The signature animation. Built with GSAP `ScrollTrigger`.

### Mechanics

```
Pin the section when its top edge reaches the top of the viewport.
The inner track is ~400vw wide (four horizontal panels worth).
As the user scrolls vertically, the inner track translates x from 0 to -300vw.
At -300vw, unpin and continue normal vertical scroll.
Total pin scroll distance: ~3 × window height (~3000px).
```

### Layout (inside the pinned section)

```
┌──────────────────────────────────────────────────────────────────┐
│   vw 0%        100%         200%          300%        400%      │
│   EIFFEL       LOUVRE       SACRÉ-CŒUR   NOTRE-DAME   transition│
│   ──path──────────────────────────────────────────────────────  │
│   🚲 →         🚲 →          🚲 →          🚲 →         🚲 ⤵    │
└──────────────────────────────────────────────────────────────────┘
```

### Choreography

Three parallax layers move at different speeds:
- **Sky layer** (clouds, distant silhouettes): 50% speed of scroll
- **Middle layer** (distant buildings): 80%
- **Foreground monuments**: 100%

The bike does not move horizontally relative to the viewport; the world scrolls past it. The bike animates only its own wheels (CSS keyframes) and a slight vertical bob along the path.

Each monument enters from the right with `opacity 0 → 1` + `translateY 40 → 0` and exits to the left with the inverse. When the bike's horizontal position aligns with a monument, the panel does a micro-bounce (`scale 1 → 1.02 → 1` in 200ms) as a satisfying feedback beat.

### DIY-zine touches

- Scribble-style cloud sketches drift right-to-left in the background at semi-random delays.
- A small hand-drawn label appears above each monument as it enters: *"Eiffel Tower (yes, that one)"*, *"Louvre — closed mondays"*, *"Sacré-Cœur (the climb is brutal)"*, *"Notre-Dame (under repair since 2019)"*. Personality, not just decoration.

### The bridge panel (vw 300-400%)

All monuments are now scaled small with opacity 0.25, scattered in the background. The bike, slightly desaturated (CSS `filter: grayscale(0.3)`), arrives in front of a full station rack. Copy *"...mais où le garer?"* writes itself on top. The very last beat before unpin: one slot turns red. This is the literal handoff to the PROBLEM section.

### Storyboard reference

Visual mockup created in Pencil at `/new` (5-frame storyboard, see brainstorming session). The implementation matches the staging of those frames.

## HOW IT WORKS in detail

Three steps in a vertical stack, connected by hand-drawn SVG arrows that auto-draw on scroll. Off-white paper background.

### Step 1 — LISTEN

Card content:
> Every 5 minutes I check every station. The dataset grows.

Animation: card fades and slides up; a bar mini-chart count-ups from 0 to ~5000 data points; a hand-drawn annotation reads *"~288 snapshots/day"*.

### Arrow 1 → 2

SVG path with `stroke-dasharray` write-on as Step 2 enters viewport. Pencil-stroke style.

### Step 2 — LEARN

Card content:
> A model studies the patterns. It's called **gradient boosting**: it builds many small decision trees, each fixing the previous one's mistakes.

Animation: central "MODEL" box pulses (scale 1 ↔ 1.03 every 2s). Four feature icons (☀️ weather, 📅 weekday, ⏰ hour, 📍 lat/lon) enter from the left and fall into the box in stagger. An arrow exits the box labeled *"forecast"*.

A `<details>` disclosure reveals a "for nerds" explanation: *"Why LightGBM and not deep learning?"* — small dataset, tabular features, training in seconds on a laptop.

### Step 3 — PREDICT

Card content:
> For any station, any time in the next 10 hours, it gives a number: *"70% full at 18:30."* MAE ~1.2 bikes.

Animation: mini sparkline auto-draws showing an example forecast curve over 10 hours; the MAE figure appears with a soft glow.

A small inline tooltip explains MAE: *"Mean Absolute Error — on average the wizard's guess is off by about 1.2 bikes."*

### Honest caveat

A small note at the section footer reads:
> *The wizard learns from ~1 week of data. Accuracy will improve as the dataset grows. The model is retrained nightly.*

This is consistent with the project's stated discipline: be precise about what the model is and isn't.

## Mobile, performance, accessibility

### Mobile (≤ 768px)

| Section | Desktop | Mobile |
|---|---|---|
| HERO, LOVE, IDEA, FOOTER | as designed | proportionally scaled |
| **THE RIDE** | **horizontal-pinned scrub** | **horizontal touch-swipe with snap** (attempted first, see fallback below) |
| PROBLEM, STAKES | as designed | compacted |
| HOW IT WORKS | already vertical | unchanged |
| SEE IT LIVE | map + CTA side-by-side | CTA-prominent, map shrinks below |

**Mobile fallback for THE RIDE:** the initial mobile implementation attempts a horizontal touch-swipe with snap-to-panel. If real-device testing shows the gesture is uncomfortable or conflicts with the page's vertical scroll, we degrade to a vertical stack of five cards, each animating on enter.

### Performance targets

- All monument PNGs converted to WebP, target 30-50 KB each (down from ~300 KB originals).
- Images served through `next/image` for automatic lazy-loading and responsive sources.
- GSAP (~30 KB gz) + ScrollTrigger (~12 KB gz) is acceptable budget.
- `motion` used selectively; no layout animations.
- Lighthouse targets: Performance ≥ 85, Accessibility ≥ 95, on both desktop and mobile.
- Site is statically served by Vercel — no Render dependency for the story page itself.

### Accessibility

- `prefers-reduced-motion: reduce` collapses every animation to a basic fade-in. THE RIDE becomes a vertical stack even on desktop. No scrub, no parallax.
- Every illustrative image has a descriptive `alt` attribute.
- Semantic HTML throughout: `<nav>`, `<section>`, `<h1>`-`<h6>` in correct hierarchy.
- Full keyboard navigability; the CTA is a real `<a href>`.
- Color contrast: white text on `#5fbcd2` and `#0e5e7a` is checked to pass WCAG AA (≥ 4.5:1).

## Out of scope (explicit)

We are NOT building:
- Internationalization. Site is English-only.
- Analytics (Vercel Analytics may be added later, not part of this spec).
- Contact form. Email link in footer suffices.
- CMS. Copy is hardcoded in React components.
- A/B testing.
- Three.js, Rive, or any 3D rendering.

## Verification (during implementation)

- `npm run dev` and view each section in the browser; confirm every animation does what the design says.
- Manual cross-browser sanity: Chrome desktop + Safari iPhone (Responsive Design Mode + a real device when available).
- DevTools `prefers-reduced-motion: reduce` toggle: verify graceful degradation.
- `npm run build`: confirm zero TypeScript / build errors and acceptable bundle size.
- Lighthouse mobile + desktop, report numbers in the implementation summary.
- No unit tests for animations (poor cost/benefit for visual logic).

## Risks and open questions

### Technical risks

1. **GSAP ScrollTrigger + Next.js App Router.** GSAP is client-only, requires `"use client"` and dynamic import to avoid SSR errors. Standard integration hurdle.
2. **Next.js 16 breaking changes.** The project's `AGENTS.md` warns about this. `node_modules/next/dist/docs/` should be consulted before writing any route handlers or using advanced features. Pure client components are unaffected.
3. **Mobile horizontal scroll** may need to fall back to the vertical-stack variant if touch UX feels off. Decision deferred to implementation.
4. **PNG watermark on Eiffel tower asset.** The `pngtree-eiffel-tower-...png` has diagonal watermarks. Resolution at implementation time: either find a clean variant in the artwork folder, or hand-build an SVG silhouette.

### Open questions, deferred to implementation

- Exact final copy per section (drafts here, polished while building).
- Real value of the `31` in STAKES — computed from the DB during implementation; framing adjusts if needed.
- Final display font (Caveat vs Patrick Hand) — quick A/B at build time.
- Exact wording of the four monument labels in THE RIDE.

## Roadmap (high-level effort)

| Step | Scope | Estimate |
|---|---|---|
| 1 | Restructure routing (`/` ↔ `/dashboard`), add `<Navbar />` | 0.5d |
| 2 | Install deps, set up fonts and colors, scaffold `_story/` | 0.25d |
| 3 | Preprocess PNGs → WebP into `public/story/` | 0.25d |
| 4 | HERO + LOVE | 0.5d |
| 5 | **THE RIDE** | 1.5d |
| 6 | PROBLEM + STAKES + IDEA | 0.75d |
| 7 | HOW IT WORKS | 0.75d |
| 8 | SEE IT LIVE + FOOTER + polish | 0.5d |
| 9 | Mobile sweep, reduced-motion, Lighthouse | 0.5d |

**Total: ~5.5 working days.** Calendar time will vary.

## Deliverable

- A deployable Vélib Wizard site where `/` is the storytelling experience and `/dashboard` is the existing interactive map, navigable from a shared navbar.
- Nine sections built, animated, responsive.
- Performance and accessibility within target.
- A final implementation report including screenshots of every section, Lighthouse scores, and any compromises taken.
