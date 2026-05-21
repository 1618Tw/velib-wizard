# Vélib Wizard Storytelling Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public-facing nine-section storytelling site at `/` of the existing `web/` Next.js app, animated with GSAP ScrollTrigger and `motion`, and move the existing interactive map to `/dashboard` accessible from a shared navbar.

**Architecture:** All work is inside `web/` (the existing Next.js 16 app). New private `_story/` folder holds sections, components, and lib. Existing `/` (MapView) moves to `/dashboard`. A shared `<Navbar />` lives in `app/layout.tsx` and is scroll-aware on the story page. No new deploy targets — site ships on Vercel with the rest of the web app.

**Tech Stack:**
- Next.js 16 (App Router), React 19, TypeScript
- Tailwind CSS v4 (`@theme inline`)
- `gsap` ^3.13 + ScrollTrigger plugin
- `motion` ^11 (component-level animations)
- `clsx` ^2 (conditional classnames)
- `next/font/google` for Caveat + Inter fonts
- WebP-optimized monument illustrations served via `next/image`

**Spec reference:** `docs/superpowers/specs/2026-05-21-velib-wizard-storytelling-website-design.md`

---

## File map

### Files created

| Path | Responsibility |
|---|---|
| `web/src/app/dashboard/page.tsx` | Server component wrapping `MapView` (moved from `/`) |
| `web/src/app/_story/sections/Hero.tsx` | Section 1: full-height intro with bike + headline |
| `web/src/app/_story/sections/Love.tsx` | Section 2: stats row, count-up |
| `web/src/app/_story/sections/TheRide.tsx` | Section 3: horizontal pinned scroll |
| `web/src/app/_story/sections/Problem.tsx` | Section 4: station fills up |
| `web/src/app/_story/sections/Stakes.tsx` | Section 5: giant "31" number |
| `web/src/app/_story/sections/Idea.tsx` | Section 6: lightbulb / transition |
| `web/src/app/_story/sections/HowItWorks.tsx` | Section 7: three-step technical explainer |
| `web/src/app/_story/sections/SeeItLive.tsx` | Section 8: map + CTA to /dashboard |
| `web/src/app/_story/sections/Footer.tsx` | Section 9: credits and links |
| `web/src/app/_story/components/Navbar.tsx` | Scroll-aware shared navbar (client) |
| `web/src/app/_story/components/Underline.tsx` | Hand-drawn SVG underline (animatable) |
| `web/src/app/_story/components/CountUp.tsx` | Number that animates from 0 to target on enter |
| `web/src/app/_story/components/Monument.tsx` | Collage-cutout monument image with parallax |
| `web/src/app/_story/components/Path.tsx` | Animated SVG path for THE RIDE |
| `web/src/app/_story/lib/gsap.ts` | GSAP registration helper (client-only) |
| `web/public/story/velib-bike.webp` | Optimized bike asset |
| `web/public/story/eiffel.webp` | Optimized monument |
| `web/public/story/louvre.webp` | Optimized monument |
| `web/public/story/sacre-coeur.webp` | Optimized monument |
| `web/public/story/notre-dame.webp` | Optimized monument |

### Files modified

| Path | Change |
|---|---|
| `web/package.json` | Add `gsap`, `motion`, `clsx` deps |
| `web/src/app/page.tsx` | Replace `<MapView />` with story page composition |
| `web/src/app/layout.tsx` | Replace inline header markup with `<Navbar />` component |
| `web/src/app/globals.css` | Add `--color-accent-green`, `--color-paper`, Caveat font variable |

---

## Pre-flight

- [ ] **Verify branch is clean and we're on `main` (or a feature branch)**

```bash
cd /Users/paololancellotti/Velib_wizard
git status
git branch --show-current
```

Expected: working tree has the spec already committed (commit `0827396`), no other uncommitted changes that don't belong to this work.

If dirty, stash or commit before proceeding.

---

## Task 1: Consult Next.js 16 docs for any breaking changes that affect this work

**Files:**
- Read only: `web/node_modules/next/dist/docs/**`

The project's `web/AGENTS.md` mandates reading the in-tree Next.js docs before writing code, because Next 16 has API changes that diverge from common training data.

- [ ] **Step 1: Locate the docs**

```bash
ls /Users/paololancellotti/Velib_wizard/web/node_modules/next/dist/docs/
```

Expected: a folder of docs (markdown or html).

- [ ] **Step 2: Skim relevant pages**

For this work, the relevant areas are:
- App Router routing and layouts
- `next/font/google` usage
- `next/image` and remote/local asset patterns
- Client components (`"use client"` directive)
- Any deprecation notices for the above

Run something like:
```bash
ls /Users/paololancellotti/Velib_wizard/web/node_modules/next/dist/docs/ | head -40
```
Then read the files matching `app-router`, `fonts`, `image`, `client-components`.

- [ ] **Step 3: Note any divergences from prior knowledge**

If anything in this plan's code samples uses an API that the docs flag as deprecated or different in Next 16, adjust the code in that task before writing it. Document the divergence in the commit message of the relevant task.

- [ ] **Step 4: No code change in this task — proceed to Task 2**

No commit needed. This is a reading task.

---

## Task 2: Install runtime dependencies

**Files:**
- Modify: `web/package.json`
- Modify: `web/package-lock.json`

- [ ] **Step 1: Install dependencies**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm install gsap@^3.13 motion@^11 clsx@^2
```

Expected: dependencies added; `package-lock.json` updated.

- [ ] **Step 2: Verify they appear in `package.json`**

```bash
grep -E '"(gsap|motion|clsx)"' /Users/paololancellotti/Velib_wizard/web/package.json
```

Expected:
```
    "clsx": "^2...",
    "gsap": "^3.13...",
    "motion": "^11...",
```

- [ ] **Step 3: Confirm typecheck still passes**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/package.json web/package-lock.json
git commit -m "feat(web): add gsap, motion, clsx for storytelling site"
```

---

## Task 3: Extend the design tokens (colors + paper background + font variable slot)

**Files:**
- Modify: `web/src/app/globals.css`

- [ ] **Step 1: Update `globals.css`**

Open `/Users/paololancellotti/Velib_wizard/web/src/app/globals.css` and replace its full content with:

```css
@import "tailwindcss";

:root {
  color-scheme: light;

  --background: #ffffff;
  --foreground: #0e5e7a;

  /* Vélib brand palette */
  --color-brand:        #5fbcd2;
  --color-brand-hover:  #4ba9c0;
  --color-brand-dark:   #0e5e7a;
  --color-brand-darker: #083f55;
  --color-brand-tint:   #e8f4f8;
  --color-brand-border: #cfe6ee;

  /* Story site extensions */
  --color-accent-green: #a3d63a;       /* Smoove green; CTAs only */
  --color-accent-green-hover: #8fc228;
  --color-paper:        #fafaf7;       /* off-white zine paper */
  --color-ink:          #1a1a1a;       /* hand-drawn marks */
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-brand:        var(--color-brand);
  --color-brand-hover:  var(--color-brand-hover);
  --color-brand-dark:   var(--color-brand-dark);
  --color-brand-darker: var(--color-brand-darker);
  --color-brand-tint:   var(--color-brand-tint);
  --color-brand-border: var(--color-brand-border);
  --color-accent-green: var(--color-accent-green);
  --color-accent-green-hover: var(--color-accent-green-hover);
  --color-paper:        var(--color-paper);
  --color-ink:          var(--color-ink);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
  --font-display: var(--font-caveat);
  --font-body: var(--font-inter);
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-geist-sans), -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
}
```

- [ ] **Step 2: Confirm there are no syntax errors**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npx tsc --noEmit
```

Expected: zero errors (CSS is not typechecked but make sure nothing else regressed).

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/globals.css
git commit -m "feat(web): add accent-green and paper design tokens for story site"
```

---

## Task 4: Load Caveat and Inter fonts in the root layout

**Files:**
- Modify: `web/src/app/layout.tsx`

Adds the two new fonts as CSS variables; later Tailwind classes (`font-display`, `font-body`) will reference them through the `@theme inline` aliases set in Task 3.

- [ ] **Step 1: Update `layout.tsx`**

Open `/Users/paololancellotti/Velib_wizard/web/src/app/layout.tsx` and modify the imports and font instantiation. The full new file content (we'll fully replace it in Task 6 when introducing the Navbar; for now just add the fonts and the variable wires):

Replace the existing font imports block:
```ts
import { Geist, Geist_Mono } from "next/font/google";
```
with:
```ts
import { Geist, Geist_Mono, Caveat, Inter } from "next/font/google";
```

Then add below the existing `Geist_Mono` constant:

```ts
const caveat = Caveat({
  variable: "--font-caveat",
  subsets: ["latin"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});
```

Then update the `<html className=...>` to include the new variables:

```tsx
className={`${geistSans.variable} ${geistMono.variable} ${caveat.variable} ${inter.variable} h-full antialiased`}
```

- [ ] **Step 2: Run the dev server and confirm the site still loads**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

In another terminal or browser, open http://localhost:3000 and confirm the existing MapView still renders. (We haven't moved it yet — it's at `/`.)

Kill the dev server (Ctrl+C) after confirming.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/layout.tsx
git commit -m "feat(web): load Caveat and Inter fonts for story site"
```

---

## Task 5: Move the MapView from `/` to `/dashboard`

**Files:**
- Create: `web/src/app/dashboard/page.tsx`
- (page.tsx at root will be left untouched in this task; Task 9 replaces it with the story page)

We create the dashboard route first, then later swap the root page so there's never a moment where the MapView is unreachable.

- [ ] **Step 1: Create the dashboard route file**

Create `/Users/paololancellotti/Velib_wizard/web/src/app/dashboard/page.tsx` with this exact content:

```tsx
import MapView from "@/components/MapView";

export default function DashboardPage() {
  return <MapView />;
}
```

- [ ] **Step 2: Verify the route resolves**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Visit http://localhost:3000/dashboard. The MapView should render. Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/dashboard/page.tsx
git commit -m "feat(web): expose interactive map at /dashboard"
```

---

## Task 6: Replace the inline navbar with a scroll-aware `<Navbar />` client component

**Files:**
- Create: `web/src/app/_story/components/Navbar.tsx`
- Modify: `web/src/app/layout.tsx`

The existing header markup is in `layout.tsx`. We extract it into a client component that becomes transparent at the top of the story page (`/`) and solidifies on scroll. On any other route the navbar is solid from the start.

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /Users/paololancellotti/Velib_wizard/web/src/app/_story/components
```

- [ ] **Step 2: Create `Navbar.tsx`**

Create `/Users/paololancellotti/Velib_wizard/web/src/app/_story/components/Navbar.tsx`:

```tsx
"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";

export default function Navbar() {
  const pathname = usePathname();
  const isStory = pathname === "/";
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    if (!isStory) return;
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [isStory]);

  const transparent = isStory && !scrolled;

  return (
    <header
      className={clsx(
        "fixed top-0 left-0 right-0 z-50 transition-colors duration-300",
        transparent
          ? "bg-transparent"
          : "bg-white/85 backdrop-blur border-b border-[var(--color-brand-border)]"
      )}
    >
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" aria-label="The Velib Wizard — home" className="flex items-center">
          <Image
            src="/logo-mark.png"
            alt="The Velib Wizard"
            width={482}
            height={512}
            priority
            className="h-9 w-auto"
          />
        </Link>
        <nav className="flex items-center gap-6 text-sm">
          <Link
            href="/"
            className={clsx(
              "transition-colors hover:opacity-100",
              transparent ? "text-white/90 hover:text-white" : "text-[var(--color-brand-dark)]/70 hover:text-[var(--color-brand-dark)]"
            )}
          >
            Story
          </Link>
          <Link
            href="/network"
            className={clsx(
              "transition-colors hover:opacity-100",
              transparent ? "text-white/90 hover:text-white" : "text-[var(--color-brand-dark)]/70 hover:text-[var(--color-brand-dark)]"
            )}
          >
            Network
          </Link>
          <Link
            href="/dashboard"
            className="px-3 py-1.5 rounded-md font-semibold text-[var(--color-brand-darker)] bg-[var(--color-accent-green)] hover:bg-[var(--color-accent-green-hover)] transition-colors"
          >
            Dashboard →
          </Link>
        </nav>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Update `layout.tsx` to use the Navbar**

Open `/Users/paololancellotti/Velib_wizard/web/src/app/layout.tsx` and:

1. Remove the `Image` and `Link` imports (now unused at this level).
2. Add the Navbar import:
   ```ts
   import Navbar from "./_story/components/Navbar";
   ```
3. Replace the inline `<header>...</header>` markup with `<Navbar />`.
4. Add `pt-14` to the `<main>` so content isn't hidden under the fixed navbar.

The new `RootLayout` body section should look like:

```tsx
<body className="min-h-full flex flex-col bg-white text-[var(--color-brand-dark)]">
  <Providers>
    <Navbar />
    <main className="flex-1 flex flex-col min-h-0 pt-14">{children}</main>
  </Providers>
</body>
```

- [ ] **Step 4: Verify navbar renders on every route**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Visit http://localhost:3000/dashboard, /network, /status. The new fixed navbar should be visible at top with logo, Story link, Network link, and a green `Dashboard →` button. On `/` (still MapView for now), the navbar is solid (not transparent — we haven't styled the story background dark yet, that comes in Task 9).

Kill the server.

- [ ] **Step 5: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/components/Navbar.tsx web/src/app/layout.tsx
git commit -m "feat(web): scroll-aware navbar shared across all routes"
```

---

## Task 7: Preprocess artwork PNGs into optimized WebP under `public/story/`

**Files:**
- Create: `web/public/story/velib-bike.webp`
- Create: `web/public/story/eiffel.webp`
- Create: `web/public/story/louvre.webp`
- Create: `web/public/story/sacre-coeur.webp`
- Create: `web/public/story/notre-dame.webp`

Source PNGs live in `/Users/paololancellotti/Velib_wizard/website/velib.artwork/`. We compress and convert them. The Eiffel pngtree image has watermarks; we use the cleaner `Untitled-1.png` as the Eiffel source.

- [ ] **Step 1: Confirm `cwebp` is available (Homebrew has it via `webp`)**

```bash
which cwebp || brew list webp >/dev/null 2>&1 || echo "Need to install: brew install webp"
```

If missing: `brew install webp`.

- [ ] **Step 2: Make the destination folder**

```bash
mkdir -p /Users/paololancellotti/Velib_wizard/web/public/story
```

- [ ] **Step 3: Convert each asset**

Run these one by one (so a failure on one doesn't block the others):

```bash
cd /Users/paololancellotti/Velib_wizard/website/velib.artwork

cwebp -q 82 -m 6 velib.png -o /Users/paololancellotti/Velib_wizard/web/public/story/velib-bike.webp
cwebp -q 82 -m 6 Untitled-1.png -o /Users/paololancellotti/Velib_wizard/web/public/story/eiffel.webp
cwebp -q 82 -m 6 louvre.png -o /Users/paololancellotti/Velib_wizard/web/public/story/louvre.webp
cwebp -q 82 -m 6 monument-5185359_1280.png -o /Users/paololancellotti/Velib_wizard/web/public/story/sacre-coeur.webp
cwebp -q 82 -m 6 "png-clipart-musxe9e-du-louvre-eiffel-tower-les-invalides-seine-hotel-france-louvre-france-louvre-view-quadruple-building-museum.png" -o /Users/paololancellotti/Velib_wizard/web/public/story/notre-dame.webp
```

Note on Notre-Dame: the file naming in `velib.artwork/` is messy. If `notre-dame.webp` isn't actually Notre-Dame after conversion (could be a generic monument), we fall back to building it as an SVG silhouette in Task 14 (THE RIDE). The Step 4 verification will tell us.

- [ ] **Step 4: Verify file sizes are reasonable**

```bash
ls -lh /Users/paololancellotti/Velib_wizard/web/public/story/
```

Expected: each `.webp` between 20 KB and 80 KB. If any file is over 200 KB, lower quality and re-run:

```bash
cwebp -q 70 -m 6 SOURCE -o DEST
```

- [ ] **Step 5: Spot-check one image visually**

Open `web/public/story/eiffel.webp` in Preview (`open /Users/paololancellotti/Velib_wizard/web/public/story/eiffel.webp`). Confirm:
- No diagonal pngtree watermarks
- Background is transparent (or near-transparent)
- The monument is recognizable

If watermarks are still visible, replace with `pngtree-eiffel-tower-png-clipart-paris-famous-architecture-png-image_20953701.png` source and re-test, or note as a follow-up to address in Task 14.

- [ ] **Step 6: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/public/story/
git commit -m "feat(web): optimized monument illustrations for story site"
```

---

## Task 8: Create the GSAP init helper

**Files:**
- Create: `web/src/app/_story/lib/gsap.ts`

A small module that registers the `ScrollTrigger` plugin exactly once, client-side. Components import `useIsomorphicGsap()` to safely run GSAP code in React effects without SSR errors.

- [ ] **Step 1: Make the lib folder**

```bash
mkdir -p /Users/paololancellotti/Velib_wizard/web/src/app/_story/lib
```

- [ ] **Step 2: Create `gsap.ts`**

Create `/Users/paololancellotti/Velib_wizard/web/src/app/_story/lib/gsap.ts`:

```ts
"use client";

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

let registered = false;

export function ensureGsap() {
  if (registered) return { gsap, ScrollTrigger };
  if (typeof window !== "undefined") {
    gsap.registerPlugin(ScrollTrigger);
    registered = true;
  }
  return { gsap, ScrollTrigger };
}

export { gsap, ScrollTrigger };
```

- [ ] **Step 3: Typecheck**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/lib/gsap.ts
git commit -m "feat(web): gsap registration helper for story animations"
```

---

## Task 9: Replace `/` with a minimal story page skeleton

**Files:**
- Modify: `web/src/app/page.tsx`

We swap the root from MapView to an empty story page composition. From this point onward, `/` is the story (still mostly empty) and `/dashboard` serves the map.

- [ ] **Step 1: Replace `page.tsx`**

Open `/Users/paololancellotti/Velib_wizard/web/src/app/page.tsx` and replace its content with:

```tsx
import Hero from "./_story/sections/Hero";
import Love from "./_story/sections/Love";
import TheRide from "./_story/sections/TheRide";
import Problem from "./_story/sections/Problem";
import Stakes from "./_story/sections/Stakes";
import Idea from "./_story/sections/Idea";
import HowItWorks from "./_story/sections/HowItWorks";
import SeeItLive from "./_story/sections/SeeItLive";
import Footer from "./_story/sections/Footer";

export default function StoryPage() {
  return (
    <>
      <Hero />
      <Love />
      <TheRide />
      <Problem />
      <Stakes />
      <Idea />
      <HowItWorks />
      <SeeItLive />
      <Footer />
    </>
  );
}
```

- [ ] **Step 2: Create stub files for every section so the page compiles**

The page won't compile until each imported file exists. Create skeletons (we'll fill them in subsequent tasks):

```bash
mkdir -p /Users/paololancellotti/Velib_wizard/web/src/app/_story/sections
```

Then create each file with this exact stub pattern (replace `SectionName` and `slug`):

`web/src/app/_story/sections/Hero.tsx`:
```tsx
export default function Hero() {
  return (
    <section id="hero" aria-label="Hero" className="min-h-screen flex items-center justify-center bg-[var(--color-brand)]">
      <h1 className="text-white text-4xl">Hero (TBD)</h1>
    </section>
  );
}
```

Repeat the same pattern for the others, changing `id`, `aria-label`, `className` background and label:

- `Love.tsx` → `bg-white`, "Love (TBD)"
- `TheRide.tsx` → `bg-[var(--color-brand)]`, "The Ride (TBD)"
- `Problem.tsx` → `bg-[var(--color-brand)]`, "Problem (TBD)"
- `Stakes.tsx` → `bg-[var(--color-paper)]`, "Stakes (TBD)"
- `Idea.tsx` → `bg-white`, "Idea (TBD)"
- `HowItWorks.tsx` → `bg-[var(--color-paper)]`, "How It Works (TBD)"
- `SeeItLive.tsx` → `bg-[var(--color-brand-dark)]`, "See it Live (TBD)" with white text
- `Footer.tsx` → `bg-[var(--color-brand-dark)] min-h-[200px]`, "Footer (TBD)" with white text

Example for SeeItLive:
```tsx
export default function SeeItLive() {
  return (
    <section id="see-it-live" aria-label="See it Live" className="min-h-screen flex items-center justify-center bg-[var(--color-brand-dark)]">
      <h1 className="text-white text-4xl">See it Live (TBD)</h1>
    </section>
  );
}
```

These TBD labels are temporary scaffolding — every one is replaced by a real section in Tasks 10–18.

- [ ] **Step 3: Run the dev server and scroll through all 9 sections**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Open http://localhost:3000 and scroll. You should see 9 distinct full-height bands with the TBD labels. Confirm `/dashboard` still works.

Kill the server.

- [ ] **Step 4: Update the existing `metadata.title` to reflect the new home**

In `web/src/app/layout.tsx` adjust the `metadata` constant:

```ts
export const metadata: Metadata = {
  title: "The Vélib Wizard — A bike-share forecaster for Paris",
  description: "Built solo as a portfolio project. Tells you if your Vélib station will be full in 2 hours.",
};
```

- [ ] **Step 5: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/page.tsx web/src/app/_story/sections/ web/src/app/layout.tsx
git commit -m "feat(web): scaffold nine-section story page, MapView now /dashboard only"
```

---

## Task 10: Build reusable `<Underline />` and `<CountUp />` components

**Files:**
- Create: `web/src/app/_story/components/Underline.tsx`
- Create: `web/src/app/_story/components/CountUp.tsx`

Small visual primitives reused across multiple sections.

- [ ] **Step 1: Create `Underline.tsx`**

Create `/Users/paololancellotti/Velib_wizard/web/src/app/_story/components/Underline.tsx`:

```tsx
"use client";

import { motion } from "motion/react";

type Props = {
  color?: string;
  className?: string;
};

export default function Underline({
  color = "var(--color-accent-green)",
  className,
}: Props) {
  return (
    <svg
      viewBox="0 0 200 12"
      className={className}
      preserveAspectRatio="none"
      aria-hidden
    >
      <motion.path
        d="M 4 8 Q 50 1, 100 6 T 196 4"
        fill="none"
        stroke={color}
        strokeWidth={4}
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        whileInView={{ pathLength: 1 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        viewport={{ once: true, margin: "-10%" }}
      />
    </svg>
  );
}
```

- [ ] **Step 2: Create `CountUp.tsx`**

Create `/Users/paololancellotti/Velib_wizard/web/src/app/_story/components/CountUp.tsx`:

```tsx
"use client";

import { animate, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

type Props = {
  to: number;
  duration?: number;
  formatter?: (n: number) => string;
  className?: string;
};

export default function CountUp({
  to,
  duration = 1.6,
  formatter = (n) => Math.round(n).toLocaleString("en-US"),
  className,
}: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-10%" });
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const controls = animate(0, to, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => setValue(v),
    });
    return () => controls.stop();
  }, [inView, to, duration]);

  return (
    <span ref={ref} className={className}>
      {formatter(value)}
    </span>
  );
}
```

- [ ] **Step 3: Typecheck**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npx tsc --noEmit
```

Expected: zero errors. If `motion/react` import path errors, the project's installed `motion` version may use a different entry; try `from "motion"` instead and re-run.

- [ ] **Step 4: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/components/Underline.tsx web/src/app/_story/components/CountUp.tsx
git commit -m "feat(web): reusable Underline and CountUp story primitives"
```

---

## Task 11: Implement the HERO section

**Files:**
- Modify: `web/src/app/_story/sections/Hero.tsx`

- [ ] **Step 1: Replace the stub with the real Hero**

Open `/Users/paololancellotti/Velib_wizard/web/src/app/_story/sections/Hero.tsx` and replace with:

```tsx
"use client";

import Image from "next/image";
import { motion } from "motion/react";
import Underline from "../components/Underline";

const TITLE = "The Vélib Wizard";

export default function Hero() {
  return (
    <section
      id="hero"
      aria-label="Hero"
      className="relative min-h-screen flex flex-col items-center justify-center bg-[var(--color-brand)] overflow-hidden"
    >
      <div className="relative z-10 px-6 text-center text-white">
        <h1 className="font-[var(--font-display)] font-bold leading-none">
          {TITLE.split("").map((char, i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i, duration: 0.4, ease: "easeOut" }}
              className="inline-block text-7xl md:text-9xl"
            >
              {char === " " ? " " : char}
            </motion.span>
          ))}
        </h1>
        <div className="mx-auto mt-2 w-72 md:w-[28rem]">
          <Underline color="#ffffff" className="w-full h-3" />
        </div>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9, duration: 0.6 }}
          className="mt-8 max-w-2xl mx-auto text-lg md:text-xl font-[var(--font-body)]"
        >
          I built a model that tells you if your bike station will be full in
          2 hours. Because Paris.
        </motion.p>
      </div>

      <motion.div
        initial={{ x: -240, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ delay: 1.1, duration: 1.0, ease: "easeOut" }}
        className="relative z-10 mt-10 md:mt-12"
      >
        <Image
          src="/story/velib-bike.webp"
          alt="A Vélib electric bike illustration"
          width={520}
          height={350}
          priority
          className="w-[280px] md:w-[420px] h-auto"
        />
      </motion.div>

      <motion.a
        href="#love"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.6, duration: 0.6 }}
        className="absolute bottom-8 text-white/90 text-sm font-[var(--font-body)]"
      >
        <span className="inline-block animate-pulse">↓ See the wizard</span>
      </motion.a>
    </section>
  );
}
```

- [ ] **Step 2: Visual check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Open http://localhost:3000. Expected:
- Title appears letter-by-letter with a slight bounce
- A green underline draws below the title
- Subhead fades in
- Bike rolls in from the left
- Bottom shows "↓ See the wizard" pulsing
- Background is full Vélib blue (#5fbcd2)
- Navbar at top is transparent over the blue background, links visible in white

Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/Hero.tsx
git commit -m "feat(web): hero section with letter-stagger title and bike entrance"
```

---

## Task 12: Implement the LOVE section

**Files:**
- Modify: `web/src/app/_story/sections/Love.tsx`

- [ ] **Step 1: Replace the stub**

Open `/Users/paololancellotti/Velib_wizard/web/src/app/_story/sections/Love.tsx`:

```tsx
"use client";

import { motion } from "motion/react";
import CountUp from "../components/CountUp";
import Underline from "../components/Underline";

const STATS = [
  { value: 20000, suffix: " bikes" },
  { value: 1400, suffix: " stations" },
  { value: 150000, suffix: " trips/day" },
] as const;

export default function Love() {
  return (
    <section
      id="love"
      aria-label="Everybody loves the Vélib"
      className="min-h-screen flex flex-col items-center justify-center bg-white px-6 py-24"
    >
      <div className="max-w-3xl text-center">
        <h2 className="text-4xl md:text-6xl font-[var(--font-display)] font-bold text-[var(--color-brand-dark)] leading-tight">
          Everybody loves the
          <span className="relative inline-block ml-3">
            Vélib
            <span className="absolute left-0 -bottom-2 w-full h-3 pointer-events-none">
              <Underline className="w-full h-full" />
            </span>
          </span>
          .
        </h2>
        <p className="mt-8 text-lg md:text-xl text-[var(--color-brand-dark)]/80 font-[var(--font-body)] leading-relaxed">
          Locals, tourists, food delivery riders, dads with kids. It's the
          cheapest way to feel Parisian for 5 minutes.
        </p>
      </div>

      <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-24 text-center">
        {STATS.map((s, i) => (
          <motion.div
            key={s.suffix}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-10%" }}
            transition={{ delay: i * 0.1, duration: 0.5 }}
          >
            <div className="text-5xl md:text-7xl font-[var(--font-display)] font-bold text-[var(--color-brand)]">
              ~<CountUp to={s.value} />
            </div>
            <div className="mt-2 text-sm md:text-base text-[var(--color-brand-dark)]/70 uppercase tracking-wider font-[var(--font-body)]">
              {s.suffix.trim()}
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Visual check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Visit http://localhost:3000 and scroll to LOVE. Expected:
- Heading "Everybody loves the Vélib" with hand-drawn underline below "Vélib"
- 3 stats below count up from 0 to their target when in view
- Numbers formatted with thousands separators (e.g. "20,000")

Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/Love.tsx
git commit -m "feat(web): love section with count-up stats"
```

---

## Task 13: Build `<Monument />` and `<Path />` components for THE RIDE

**Files:**
- Create: `web/src/app/_story/components/Monument.tsx`
- Create: `web/src/app/_story/components/Path.tsx`

Two small primitives used inside THE RIDE.

- [ ] **Step 1: Create `Monument.tsx`**

Create `/Users/paololancellotti/Velib_wizard/web/src/app/_story/components/Monument.tsx`:

```tsx
import Image from "next/image";
import clsx from "clsx";

type Props = {
  src: string;
  alt: string;
  label: string;
  className?: string;
  width: number;
  height: number;
};

export default function Monument({
  src,
  alt,
  label,
  className,
  width,
  height,
}: Props) {
  return (
    <div className={clsx("relative flex flex-col items-center", className)}>
      <Image
        src={src}
        alt={alt}
        width={width}
        height={height}
        className="object-contain drop-shadow-[0_4px_18px_rgba(0,0,0,0.18)]"
      />
      <span
        className="mt-3 font-[var(--font-display)] text-white/90 text-xl rotate-[-3deg] inline-block"
        style={{ textShadow: "0 1px 0 rgba(0,0,0,0.15)" }}
      >
        {label}
      </span>
    </div>
  );
}
```

- [ ] **Step 2: Create `Path.tsx`**

Create `/Users/paololancellotti/Velib_wizard/web/src/app/_story/components/Path.tsx`:

```tsx
type Props = {
  className?: string;
};

export default function Path({ className }: Props) {
  return (
    <svg
      viewBox="0 0 4000 200"
      preserveAspectRatio="none"
      className={className}
      aria-hidden
    >
      <path
        d="M 0 140 Q 500 60, 1000 130 T 2000 130 T 3000 130 T 4000 130"
        fill="none"
        stroke="rgba(255,255,255,0.65)"
        strokeWidth={4}
        strokeDasharray="14 10"
        strokeLinecap="round"
      />
    </svg>
  );
}
```

- [ ] **Step 3: Typecheck**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/components/Monument.tsx web/src/app/_story/components/Path.tsx
git commit -m "feat(web): Monument and Path primitives for THE RIDE"
```

---

## Task 14: Implement THE RIDE — horizontal pinned scroll (desktop)

**Files:**
- Modify: `web/src/app/_story/sections/TheRide.tsx`

This is the centerpiece. We pin the section, the inner track translates `x` from `0` to `-300vw` as the user scrolls vertically. Mobile fallback (touch-swipe with snap) is done in Task 15.

- [ ] **Step 1: Replace the stub**

Open `/Users/paololancellotti/Velib_wizard/web/src/app/_story/sections/TheRide.tsx`:

```tsx
"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";
import { ensureGsap } from "../lib/gsap";
import Monument from "../components/Monument";
import Path from "../components/Path";

const PANELS = [
  {
    src: "/story/eiffel.webp",
    alt: "Eiffel Tower",
    label: "Eiffel Tower (yes, that one)",
    width: 200,
    height: 360,
  },
  {
    src: "/story/louvre.webp",
    alt: "Louvre",
    label: "Louvre — closed mondays",
    width: 320,
    height: 220,
  },
  {
    src: "/story/sacre-coeur.webp",
    alt: "Sacré-Cœur",
    label: "Sacré-Cœur (the climb is brutal)",
    width: 240,
    height: 280,
  },
  {
    src: "/story/notre-dame.webp",
    alt: "Notre-Dame",
    label: "Notre-Dame (under repair since 2019)",
    width: 280,
    height: 240,
  },
];

export default function TheRide() {
  const sectionRef = useRef<HTMLElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const bikeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(max-width: 767px)").matches) return; // mobile uses separate behavior, Task 15

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const { gsap, ScrollTrigger } = ensureGsap();
    const section = sectionRef.current;
    const track = trackRef.current;
    const bike = bikeRef.current;
    if (!section || !track || !bike) return;

    const ctx = gsap.context(() => {
      const totalPanels = PANELS.length + 1; // +1 for bridge panel
      const distance = (totalPanels - 1) * window.innerWidth;

      gsap.to(track, {
        x: -distance,
        ease: "none",
        scrollTrigger: {
          trigger: section,
          start: "top top",
          end: () => `+=${distance}`,
          pin: true,
          scrub: 0.5,
          invalidateOnRefresh: true,
        },
      });

      gsap.to(bike, {
        y: -8,
        repeat: -1,
        yoyo: true,
        duration: 0.6,
        ease: "sine.inOut",
      });
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="the-ride"
      aria-label="The ride through Paris"
      className="relative h-screen overflow-hidden bg-[var(--color-brand)]"
    >
      <div
        ref={trackRef}
        className="absolute inset-0 flex"
        style={{ width: `${(PANELS.length + 1) * 100}vw` }}
      >
        {PANELS.map((p, i) => (
          <div
            key={p.alt}
            className="relative shrink-0 h-full flex items-end justify-center pb-32"
            style={{ width: "100vw" }}
          >
            <Monument
              src={p.src}
              alt={p.alt}
              label={p.label}
              width={p.width}
              height={p.height}
            />
            <span className="absolute top-12 left-12 text-white/70 font-[var(--font-display)] text-2xl">
              {String(i + 1).padStart(2, "0")}
            </span>
          </div>
        ))}

        {/* Bridge panel */}
        <div
          key="bridge"
          className="relative shrink-0 h-full flex flex-col items-center justify-center"
          style={{ width: "100vw" }}
        >
          <h3 className="font-[var(--font-display)] text-white text-6xl md:text-8xl italic text-center px-6 max-w-3xl">
            ...mais où le garer ?
          </h3>
          <p className="mt-4 text-white/80 text-sm font-[var(--font-body)]">
            Scroll on.
          </p>
        </div>
      </div>

      {/* Path */}
      <Path className="absolute left-0 right-0 bottom-28 h-12" />

      {/* Bike — fixed in viewport while world scrolls */}
      <div
        ref={bikeRef}
        className="absolute left-1/2 -translate-x-1/2 bottom-20 z-10 pointer-events-none"
      >
        <Image
          src="/story/velib-bike.webp"
          alt=""
          width={200}
          height={140}
          className="w-[140px] md:w-[180px] h-auto"
        />
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Visual check (desktop only)**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Open http://localhost:3000 on desktop browser. Scroll down to THE RIDE. Expected:
- Section pins (page stops scrolling vertically)
- Inner track translates horizontally as you continue scrolling
- 4 monuments pass behind the bike (which stays centered, gently bobbing up/down)
- After last monument, a bridge panel with "...mais où le garer ?" appears
- After bridge panel, unpins and PROBLEM section becomes visible
- Total pin distance ≈ 4× viewport width of scroll

Kill the server.

If horizontal scroll is jerky: increase `scrub` to `1.0`. If it's too sluggish: lower to `0.3`. Pick what feels right.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/TheRide.tsx
git commit -m "feat(web): THE RIDE horizontal pinned scroll on desktop"
```

---

## Task 15: Add mobile + reduced-motion fallback to THE RIDE

**Files:**
- Modify: `web/src/app/_story/sections/TheRide.tsx`

The desktop horizontal scroll doesn't work on touch. We add a touch-swipe snap-scroll variant for mobile, with an automatic fallback to a vertical card stack if the user has `prefers-reduced-motion`.

- [ ] **Step 1: Add the mobile/reduced JSX**

Edit `TheRide.tsx`. Below the existing `useEffect`, add a small helper to detect mode. Then conditionally render. The cleanest approach: render two trees, hide one via CSS.

Replace the entire `return (...)` block with:

```tsx
return (
  <>
    {/* Desktop: pinned horizontal scroll */}
    <section
      ref={sectionRef}
      id="the-ride"
      aria-label="The ride through Paris"
      className="relative h-screen overflow-hidden bg-[var(--color-brand)] hidden md:block motion-reduce:hidden"
    >
      <div
        ref={trackRef}
        className="absolute inset-0 flex"
        style={{ width: `${(PANELS.length + 1) * 100}vw` }}
      >
        {PANELS.map((p, i) => (
          <div
            key={p.alt}
            className="relative shrink-0 h-full flex items-end justify-center pb-32"
            style={{ width: "100vw" }}
          >
            <Monument
              src={p.src}
              alt={p.alt}
              label={p.label}
              width={p.width}
              height={p.height}
            />
            <span className="absolute top-12 left-12 text-white/70 font-[var(--font-display)] text-2xl">
              {String(i + 1).padStart(2, "0")}
            </span>
          </div>
        ))}
        <div
          key="bridge"
          className="relative shrink-0 h-full flex flex-col items-center justify-center"
          style={{ width: "100vw" }}
        >
          <h3 className="font-[var(--font-display)] text-white text-6xl md:text-8xl italic text-center px-6 max-w-3xl">
            ...mais où le garer ?
          </h3>
          <p className="mt-4 text-white/80 text-sm font-[var(--font-body)]">
            Scroll on.
          </p>
        </div>
      </div>
      <Path className="absolute left-0 right-0 bottom-28 h-12" />
      <div
        ref={bikeRef}
        className="absolute left-1/2 -translate-x-1/2 bottom-20 z-10 pointer-events-none"
      >
        <Image
          src="/story/velib-bike.webp"
          alt=""
          width={200}
          height={140}
          className="w-[140px] md:w-[180px] h-auto"
        />
      </div>
    </section>

    {/* Mobile + reduced motion: horizontal touch-swipe with snap */}
    <section
      id="the-ride-mobile"
      aria-label="The ride through Paris"
      className="relative bg-[var(--color-brand)] md:hidden motion-reduce:block motion-reduce:md:block"
    >
      <div className="overflow-x-auto snap-x snap-mandatory flex">
        {PANELS.map((p, i) => (
          <div
            key={p.alt}
            className="relative shrink-0 w-screen h-screen snap-center flex items-end justify-center pb-32"
          >
            <Monument
              src={p.src}
              alt={p.alt}
              label={p.label}
              width={p.width}
              height={p.height}
            />
            <span className="absolute top-12 left-8 text-white/70 font-[var(--font-display)] text-2xl">
              {String(i + 1).padStart(2, "0")}
            </span>
          </div>
        ))}
        <div className="relative shrink-0 w-screen h-screen snap-center flex flex-col items-center justify-center px-6">
          <h3 className="font-[var(--font-display)] text-white text-5xl italic text-center max-w-md">
            ...mais où le garer ?
          </h3>
          <p className="mt-4 text-white/80 text-sm font-[var(--font-body)]">
            Swipe up.
          </p>
        </div>
      </div>
      <p className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/80 text-xs font-[var(--font-body)] pointer-events-none">
        ← swipe →
      </p>
    </section>
  </>
);
```

- [ ] **Step 2: Visual check on mobile viewport**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Open http://localhost:3000 and use Chrome DevTools → Toggle device toolbar → pick an iPhone preset. Scroll to THE RIDE. Expected:
- Section is a horizontal touch-swipe carousel
- Each monument is one full screen, snap-centers
- "← swipe →" hint visible at bottom

Then toggle `prefers-reduced-motion: reduce` (DevTools → Rendering → Emulate CSS media feature) and reload. On desktop with reduced motion, the desktop pinned version should hide and the mobile version should display.

Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/TheRide.tsx
git commit -m "feat(web): mobile and reduced-motion fallback for THE RIDE"
```

---

## Task 16: Implement PROBLEM section

**Files:**
- Modify: `web/src/app/_story/sections/Problem.tsx`

A station rack fills with bikes one-by-one as the user scrolls; a stick figure arrives at the bottom with a question mark.

- [ ] **Step 1: Replace the stub**

```tsx
"use client";

import { motion } from "motion/react";

const SLOTS = Array.from({ length: 10 }, (_, i) => i);

export default function Problem() {
  return (
    <section
      id="problem"
      aria-label="The problem"
      className="min-h-screen flex flex-col items-center justify-center bg-[var(--color-brand)] text-white px-6 py-24"
    >
      <h2 className="font-[var(--font-display)] text-4xl md:text-6xl font-bold text-center max-w-3xl leading-tight">
        But there's one thing that drives me mad.
      </h2>

      <p className="mt-6 max-w-2xl text-center text-lg md:text-xl font-[var(--font-body)] text-white/90">
        You arrive. The station is full. Every slot has a bike. Now what?
      </p>

      {/* Station rack */}
      <div className="mt-16 grid grid-cols-5 md:grid-cols-10 gap-3 max-w-3xl">
        {SLOTS.map((i) => (
          <motion.div
            key={i}
            initial={{ scale: 0, opacity: 0 }}
            whileInView={{ scale: 1, opacity: 1 }}
            viewport={{ once: true, margin: "-15%" }}
            transition={{ delay: i * 0.08, duration: 0.25, ease: "easeOut" }}
            className="w-12 h-16 md:w-16 md:h-20 bg-red-500 rounded-sm border-2 border-white/60 flex items-center justify-center text-white text-xs font-[var(--font-body)]"
            aria-label={`Slot ${i + 1} — occupied`}
          >
            🚲
          </motion.div>
        ))}
      </div>

      {/* Rider with question mark */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-15%" }}
        transition={{ delay: 1.0, duration: 0.5 }}
        className="mt-12 flex flex-col items-center"
      >
        <span className="text-5xl">🤔</span>
        <span className="mt-2 font-[var(--font-display)] text-2xl text-white/90">
          (you, with a bike)
        </span>
      </motion.div>
    </section>
  );
}
```

- [ ] **Step 2: Visual check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Scroll to PROBLEM. Expected: heading + subtitle + a 10-slot rack that fills slot-by-slot with red rectangles each containing a bike emoji, then the 🤔 rider appears below.

Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/Problem.tsx
git commit -m "feat(web): problem section with sequential rack fill"
```

---

## Task 17: Implement STAKES section

**Files:**
- Modify: `web/src/app/_story/sections/Stakes.tsx`

A giant "31" with explanatory caption. The number is hardcoded for now; the spec notes it should be computed from the DB if real data dictates a different framing — that is a follow-up after the site is wired up.

- [ ] **Step 1: Replace the stub**

```tsx
"use client";

import { motion } from "motion/react";

const NUMBER = 31;

export default function Stakes() {
  return (
    <section
      id="stakes"
      aria-label="The stakes"
      className="min-h-screen flex flex-col items-center justify-center bg-[var(--color-paper)] text-[var(--color-brand-darker)] px-6 py-24"
    >
      <p className="font-[var(--font-display)] text-2xl md:text-3xl max-w-2xl text-center text-[var(--color-brand-dark)]/80">
        Sometimes you ride 15 more minutes just looking for a free slot.
      </p>

      <motion.div
        initial={{ scale: 0.6, opacity: 0 }}
        whileInView={{ scale: 1, opacity: 1 }}
        viewport={{ once: true, margin: "-15%" }}
        transition={{ duration: 0.7, ease: "easeOut" }}
        className="mt-8 font-[var(--font-display)] font-bold leading-none"
        style={{ fontSize: "clamp(180px, 32vw, 360px)" }}
      >
        {NUMBER}
        <span className="text-[0.3em] align-top ml-2">%</span>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: "-15%" }}
        transition={{ delay: 0.4, duration: 0.6 }}
        className="mt-4 max-w-xl text-center text-base md:text-lg font-[var(--font-body)] text-[var(--color-brand-dark)]/80"
      >
        of stations are completely full at 8:45 a.m. in central Paris.
        <span className="block mt-1 text-sm text-[var(--color-brand-dark)]/50 italic">
          (approximate — recomputed from live data)
        </span>
      </motion.p>
    </section>
  );
}
```

- [ ] **Step 2: Visual check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Scroll to STAKES. Expected: subhead + a massive "31%" + caption below.

Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/Stakes.tsx
git commit -m "feat(web): stakes section with giant 31% headline"
```

---

## Task 18: Implement IDEA section

**Files:**
- Modify: `web/src/app/_story/sections/Idea.tsx`

- [ ] **Step 1: Replace the stub**

```tsx
"use client";

import { motion } from "motion/react";

export default function Idea() {
  return (
    <section
      id="idea"
      aria-label="The idea"
      className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-white to-[var(--color-brand-tint)] px-6 py-24"
    >
      <motion.div
        initial={{ scale: 0, rotate: -20, opacity: 0 }}
        whileInView={{ scale: 1, rotate: 0, opacity: 1 }}
        viewport={{ once: true, margin: "-20%" }}
        transition={{ duration: 0.6, ease: "backOut" }}
        className="text-8xl"
      >
        💡
      </motion.div>

      <motion.h2
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-20%" }}
        transition={{ delay: 0.3, duration: 0.5 }}
        className="mt-8 font-[var(--font-display)] text-4xl md:text-6xl font-bold text-[var(--color-brand-darker)] text-center max-w-3xl"
      >
        So I built a Wizard that tells you in advance.
      </motion.h2>

      <motion.div
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: "-20%" }}
        transition={{ delay: 0.7, duration: 0.5 }}
        className="mt-8 text-5xl"
      >
        🧙
      </motion.div>
    </section>
  );
}
```

- [ ] **Step 2: Visual check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Scroll to IDEA. Expected: 💡 pops in with a small back-out animation, heading fades, 🧙 appears below.

Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/Idea.tsx
git commit -m "feat(web): idea section transition with lightbulb and wizard"
```

---

## Task 19: Implement HOW IT WORKS section

**Files:**
- Modify: `web/src/app/_story/sections/HowItWorks.tsx`

- [ ] **Step 1: Replace the stub**

```tsx
"use client";

import { motion } from "motion/react";

const STEPS = [
  {
    n: "1",
    title: "LISTEN",
    body: "Every 5 minutes I check every station. The dataset grows.",
    annotation: "~288 snapshots per day",
  },
  {
    n: "2",
    title: "LEARN",
    body: "A model studies the patterns. It's called gradient boosting: it builds many small decision trees, each fixing the previous one's mistakes.",
    annotation: "LightGBM — small, fast, tabular-friendly",
  },
  {
    n: "3",
    title: "PREDICT",
    body: "For any station, any time in the next 10 hours, it gives a number: \"70% full at 18:30.\"",
    annotation: "MAE ≈ 1.2 bikes (typical error)",
  },
];

export default function HowItWorks() {
  return (
    <section
      id="how-it-works"
      aria-label="How the wizard works"
      className="min-h-screen bg-[var(--color-paper)] text-[var(--color-brand-darker)] px-6 py-24"
    >
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="font-[var(--font-display)] text-4xl md:text-6xl font-bold">
          How does the wizard see the future?
        </h2>
        <p className="mt-4 text-lg font-[var(--font-body)] text-[var(--color-brand-dark)]/80">
          Three steps, one model, zero magic.
        </p>
      </div>

      <div className="mt-20 max-w-2xl mx-auto flex flex-col gap-12">
        {STEPS.map((s, i) => (
          <motion.div
            key={s.n}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-15%" }}
            transition={{ duration: 0.5, delay: i * 0.15 }}
            className="relative bg-white rounded-lg border-2 border-[var(--color-brand-darker)]/15 p-6 md:p-8 shadow-[6px_6px_0_0_var(--color-brand-darker)]"
          >
            <div className="flex items-start gap-4">
              <span className="font-[var(--font-display)] text-5xl font-bold text-[var(--color-brand)] leading-none">
                {s.n}
              </span>
              <div className="flex-1">
                <h3 className="font-[var(--font-body)] font-bold uppercase tracking-widest text-sm text-[var(--color-brand-darker)]">
                  {s.title}
                </h3>
                <p className="mt-3 text-base md:text-lg font-[var(--font-body)] leading-relaxed">
                  {s.body}
                </p>
                <p className="mt-3 font-[var(--font-display)] text-lg text-[var(--color-brand-dark)]/70 rotate-[-1deg] inline-block">
                  ↳ {s.annotation}
                </p>
              </div>
            </div>
          </motion.div>
        ))}

        <details className="mt-4 text-sm font-[var(--font-body)] text-[var(--color-brand-dark)]/80">
          <summary className="cursor-pointer underline decoration-dotted">
            Why LightGBM and not deep learning?
          </summary>
          <p className="mt-3 leading-relaxed pl-4 border-l-2 border-[var(--color-brand-darker)]/15">
            Tabular features, ~1 week of data, trains in seconds on a laptop. Deep
            learning would be overkill (and probably worse) at this dataset size.
          </p>
        </details>

        <p className="mt-6 text-xs italic text-[var(--color-brand-dark)]/60 font-[var(--font-body)] text-center">
          The wizard learns from ~1 week of data. Accuracy will improve as the
          dataset grows. The model is retrained nightly.
        </p>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Visual check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Scroll to HOW IT WORKS. Expected: 3 cards stacked with chunky offset shadows, each enters on scroll; expandable "Why LightGBM" disclosure; honest caveat at the bottom.

Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/HowItWorks.tsx
git commit -m "feat(web): how-it-works section explaining the LightGBM forecaster"
```

---

## Task 20: Implement SEE IT LIVE section

**Files:**
- Modify: `web/src/app/_story/sections/SeeItLive.tsx`

- [ ] **Step 1: Replace the stub**

```tsx
"use client";

import Link from "next/link";
import { motion } from "motion/react";

const PINS = [
  { x: 30, y: 40, status: "green" },
  { x: 55, y: 30, status: "yellow" },
  { x: 70, y: 55, status: "red" },
  { x: 45, y: 65, status: "green" },
  { x: 60, y: 75, status: "yellow" },
  { x: 25, y: 60, status: "red" },
];

const STATUS_COLOR: Record<string, string> = {
  green: "#22c55e",
  yellow: "#facc15",
  red: "#ef4444",
};

export default function SeeItLive() {
  return (
    <section
      id="see-it-live"
      aria-label="See it live"
      className="min-h-screen flex flex-col items-center justify-center bg-[var(--color-brand-dark)] text-white px-6 py-24"
    >
      <h2 className="font-[var(--font-display)] text-4xl md:text-6xl font-bold text-center max-w-3xl">
        Want to see it on your station?
      </h2>
      <p className="mt-4 text-lg md:text-xl font-[var(--font-body)] text-white/80 text-center max-w-xl">
        Pick a station. See the next 10 hours.
      </p>

      <div className="relative mt-12 w-full max-w-md aspect-[4/3] bg-[var(--color-brand-darker)] rounded-lg border border-white/10 overflow-hidden">
        {/* Stylized Seine curve */}
        <svg
          viewBox="0 0 100 75"
          preserveAspectRatio="none"
          className="absolute inset-0 w-full h-full"
          aria-hidden
        >
          <path
            d="M 0 38 Q 25 22, 50 36 T 100 32"
            stroke="rgba(95,188,210,0.45)"
            strokeWidth={3}
            fill="none"
          />
        </svg>
        {PINS.map((p, i) => (
          <motion.span
            key={i}
            className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full"
            style={{
              left: `${p.x}%`,
              top: `${p.y}%`,
              width: 12,
              height: 12,
              background: STATUS_COLOR[p.status],
              boxShadow: `0 0 0 4px ${STATUS_COLOR[p.status]}33`,
            }}
            animate={{ scale: [1, 1.25, 1] }}
            transition={{
              duration: 1.6,
              repeat: Infinity,
              delay: i * 0.2,
              ease: "easeInOut",
            }}
            aria-hidden
          />
        ))}
      </div>

      <Link
        href="/dashboard"
        className="mt-12 inline-flex items-center gap-2 px-6 py-3 rounded-md bg-[var(--color-accent-green)] hover:bg-[var(--color-accent-green-hover)] text-[var(--color-brand-darker)] font-bold text-lg font-[var(--font-body)] shadow-[0_6px_0_0_rgba(0,0,0,0.25)] hover:shadow-[0_3px_0_0_rgba(0,0,0,0.25)] hover:translate-y-[3px] transition-all"
      >
        Try the Wizard →
      </Link>
    </section>
  );
}
```

- [ ] **Step 2: Visual check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Scroll to SEE IT LIVE. Expected: dark blue section with a stylized map, pulsing colored pins, and a big green "Try the Wizard →" button. Clicking the button navigates to `/dashboard`.

Kill the server.

- [ ] **Step 3: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/SeeItLive.tsx
git commit -m "feat(web): see-it-live section with stylized map and dashboard CTA"
```

---

## Task 21: Implement FOOTER section

**Files:**
- Modify: `web/src/app/_story/sections/Footer.tsx`

- [ ] **Step 1: Replace the stub**

```tsx
"use client";

import Image from "next/image";
import { motion } from "motion/react";

export default function Footer() {
  return (
    <footer
      id="footer"
      aria-label="Footer"
      className="relative bg-[var(--color-brand-darker)] text-white/90 px-6 py-12 overflow-hidden"
    >
      <div className="max-w-3xl mx-auto flex flex-col items-center gap-4 text-center">
        <p className="font-[var(--font-body)] text-base">
          Built solo by{" "}
          <span className="font-bold">Paolo Lancellotti</span> as a portfolio
          project · 2026
        </p>
        <ul className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm">
          <li>
            <a
              href="https://github.com/"
              className="underline decoration-dotted hover:text-white"
            >
              GitHub
            </a>
          </li>
          <li>
            <a
              href="mailto:paolo.lancellotti02@gmail.com"
              className="underline decoration-dotted hover:text-white"
            >
              Email
            </a>
          </li>
        </ul>
        <p className="mt-4 font-mono text-xs text-white/60">
          Data: Vélib' Métropole GBFS · Model: LightGBM · Hosted on Vercel +
          Render free tier
        </p>
      </div>

      <motion.div
        className="absolute bottom-2 left-0 pointer-events-none"
        initial={{ x: "-20%" }}
        animate={{ x: "110%" }}
        transition={{ duration: 24, repeat: Infinity, ease: "linear" }}
      >
        <Image
          src="/story/velib-bike.webp"
          alt=""
          width={80}
          height={56}
          className="opacity-50"
        />
      </motion.div>
    </footer>
  );
}
```

- [ ] **Step 2: Update GitHub URL placeholder**

If you have a public GitHub repo URL for this project, replace `https://github.com/` with the real link. If not, leave it for the user to fill in post-launch.

- [ ] **Step 3: Visual check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Scroll to the bottom. Expected: dark blue footer with credit + links + a tiny bike pedaling slowly across.

Kill the server.

- [ ] **Step 4: Commit**

```bash
cd /Users/paololancellotti/Velib_wizard
git add web/src/app/_story/sections/Footer.tsx
git commit -m "feat(web): footer with credits and infinite-loop bike animation"
```

---

## Task 22: End-to-end verification (build, lint, browser walk-through)

**Files:**
- No file changes — verification only.

- [ ] **Step 1: Production build**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run build
```

Expected: build completes with zero errors. Note bundle sizes. If the story page bundle exceeds 350 KB gzipped, investigate which library is bloating.

- [ ] **Step 2: TypeScript final check**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Manual walkthrough on desktop**

```bash
cd /Users/paololancellotti/Velib_wizard/web
npm run dev
```

Open http://localhost:3000 in Chrome. Scroll from top to bottom. Verify every section animates as the spec describes:

1. HERO — title staggers in, bike rolls in
2. LOVE — stats count up
3. THE RIDE — pins, horizontal scroll past 4 monuments + bridge, unpins
4. PROBLEM — rack fills slot-by-slot, rider appears
5. STAKES — "31%" grows in
6. IDEA — lightbulb pops, heading fades, wizard emoji
7. HOW IT WORKS — 3 cards enter, disclosure expands when clicked
8. SEE IT LIVE — map with pulsing pins, CTA button visible
9. FOOTER — credits + slow-moving bike

Click "Dashboard →" in the navbar. Confirm MapView loads at `/dashboard`. Click logo to return to `/`. Confirm.

- [ ] **Step 4: Mobile walkthrough**

In DevTools, switch to iPhone 14 Pro preset. Reload http://localhost:3000. Scroll through. Verify:
- THE RIDE is now a horizontal touch-swipe carousel (swipe with click+drag in DevTools)
- All other sections look reasonable at mobile width

- [ ] **Step 5: Reduced motion check**

In DevTools → Rendering → Emulate CSS media feature → `prefers-reduced-motion: reduce`. Reload. Verify:
- THE RIDE no longer has the pinned scroll; the horizontal-swipe variant shows instead
- Other section animations should not be removed entirely; they're already light

- [ ] **Step 6: Lighthouse**

In DevTools → Lighthouse → run a mobile audit and a desktop audit on http://localhost:3000.

Record both scores. Target:
- Performance ≥ 85 on desktop, ≥ 70 on mobile
- Accessibility ≥ 95 both

If accessibility is < 95, the most common causes are color contrast and missing alt text — fix in this same task.

- [ ] **Step 7: Commit any final tweaks**

If you made any tweaks during verification:

```bash
cd /Users/paololancellotti/Velib_wizard
git add -p web/
git commit -m "chore(web): polish after end-to-end verification"
```

- [ ] **Step 8: Final status check**

```bash
cd /Users/paololancellotti/Velib_wizard
git log --oneline -25
git status
```

Expected: 21+ new commits on top of the spec commit `0827396`, working tree clean.

---

## Done

The storytelling site is live at `/` and the interactive dashboard at `/dashboard`. Nine sections render with the staged animations. Mobile and reduced-motion fallbacks are in place. Final Lighthouse scores recorded.

Open questions explicitly deferred (handle as separate follow-up tasks, not in this plan):
- Compute the real `31%` value (or another framing) from the live database and update STAKES.
- Clean up the Eiffel asset if the cwebp output still shows pngtree watermarks (re-source or hand-build an SVG).
- Replace `https://github.com/` with the real repo URL in FOOTER once it's public.
- Decide whether to add Vercel Analytics.
