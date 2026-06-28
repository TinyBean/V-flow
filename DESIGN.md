# Design

The visual system for V-flow's redesigned surfaces (`templates/index.html`, `templates/player.html`). Register: **product**. Mood: **restrained editorial, dark, image-forward**. Color strategy: **Restrained** — near-monochrome surfaces, one warm accent reserved for state.

## Scene (why dark)

A single user, at a desktop, in a dim room, watching local video. Dark surfaces are chosen for that physical scene — never as a default. The browser page is dark so the eye is already adapted when a video opens; the player page is dark so the frame is the only light source.

## Color

OKLCH throughout. A near-neutral, barely-warm dark ramp so the surface reads as ink/cinema rather than cold "tool grey," paired with a single warm-gold accent used only for state (active, current, focus, the play affordance, the speed badge). The thumbnails and video are the only saturated color on the page.

```
/* surface ramp — faint warm-neutral dark */
--bg:        oklch(0.165 0.006 75);   /* page */
--surface:   oklch(0.205 0.006 75);   /* raised: top bar */
--surface-2: oklch(0.250 0.007 75);   /* hover / pressed */
--line:      oklch(0.96 0.004 90 / 0.10);  /* hairline rules, from ink alpha */
--line-2:    oklch(0.96 0.004 90 / 0.06);  /* quieter hairline */

/* ink ramp — contrast-verified on --bg */
--ink:       oklch(0.96 0.004 90);    /* primary text        ≈ 16:1 */
--ink-2:     oklch(0.78 0.006 80);    /* readable secondary  ≈ 7:1  */
--ink-3:     oklch(0.60 0.006 80);    /* decorative / hint   — borders & dim UI only */

/* accent — warm gold, state only */
--accent:    oklch(0.84 0.13 70);     /* current / focus / play */
--accent-ink:oklch(0.20 0.02 70);     /* text on accent fill */

/* state */
--error:     oklch(0.72 0.16 25);     /* warm red, used only for errors */
```

Contrast: `--ink` and `--ink-2` clear AA (≥4.5:1) on `--bg` for all text including file-size meta. `--ink-3` is reserved for non-text chrome (separators, inactive glyphs); where it appears as text it sits on a darker scrim that still clears AA. Gray-on-warm-bg drift is avoided by pulling the whole ramp from the same warm hue family, never a cool neutral grey.

## Typography

One family — a tuned system sans — carries everything (wordmark, titles, labels, data, player chrome). No display face, no pairing. Editorial restraint comes from weight, spacing, and rhythm, not from a special font.

```
--font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
```

Fixed rem scale (not fluid — product UI viewed at consistent DPI), ratio ~1.2:

| Role          | Size   | Weight | Tracking    | LH   |
|---------------|--------|--------|-------------|------|
| Wordmark      | 0.95rem| 600    | -0.01em     | 1    |
| Folder name   | 0.95rem| 500    | 0           | 1.4  |
| Video title   | 0.875rem| 500   | 0           | 1.35 |
| Body / count  | 0.875rem| 400   | 0           | 1.5  |
| Meta (size)   | 0.75rem| 400    | 0           | 1.4  |
| Micro label   | 0.6875rem| 600  | +0.06em     | 1    |

Micro labels are **lowercase** with slight positive tracking — they replace the old uppercase tracked eyebrows. Used at most once or twice per view, never as a reflex above every section.

`text-wrap: balance` on headings/titles; `pretty` on any prose.

## Layout

- **Container**: generous, clamped side padding `clamp(16px, 4vw, 48px)`; content max-width ~1600px so huge grids still breathe.
- **Rhythm**: a 4px-base spacing scale (`4 8 12 16 20 24 32 48 64 96`). Section gaps vary (not uniform).
- **Top bar**: hairline-bottom, near-opaque dark + 12px blur. Wordmark left, search center, count right. No gradient, no logo mark.
- **Breadcrumbs**: hairline `/` separators; current crumb in accent. Disappears at root.
- **Folders**: a quiet inline list of chips, not cards — folder glyph (SVG) + name + (count). Borderless at rest, hairline + lift on hover.
- **Video grid**: `grid-template-columns: repeat(auto-fill, minmax(260px, 1fr))`. Thumbnail is the element (16:9, fills the cell); a slim info bar below carries title + size. Hover = subtle brightness + a hairline frame + the play glyph — **no** drop-shadow glow, **no** big lift.
- **Pagination**: prev / `page x of y` / next, inline, hairline buttons.
- **z-index scale**: `--z-sticky: 100; --z-overlay: 200; --z-badge: 300;`.

## Components

Shared, consistent vocabulary across both pages. Every interactive element has default / hover / focus-visible / active / disabled.

- **Search field**: hairline pill, ink text, `--ink-2` placeholder at AA contrast (not the dim-grey default), accent ring on focus.
- **Buttons**: hairline, transparent fill, ink label; hover `--surface-2`; focus-visible accent ring; disabled at 0.4 opacity.
- **Folder chip / video cell / breadcrumb / page button**: same hairline + hover + focus vocabulary.
- **Thumbnail**: lazy-loaded from `/api/thumb/...`, graceful fade-in; on error a quiet monogram placeholder (initial + ext), never a broken-image icon.
- **States**: skeleton shimmer for loading (not a centered spinner over content); empty state that names the situation in one quiet line; error as a hairline-bordered inline note.
- **Icons**: 1.5px-stroke inline SVG, `currentColor`. Search, folder, play, chevron, close. Never emoji.

## Motion

150–200ms, ease-out-quart, on opacity / border / filter / transform only. Hover on a cell brightens the thumbnail and draws a hairline frame. Thumbnails crossfade in on load. No orchestrated page-load sequence, no bounce/elastic. Every motion has a `prefers-reduced-motion` fallback (instant or crossfade).

## Iconography set

Inline SVG, 16–20px, stroke `currentColor` `stroke-width="1.5"`, `fill="none"`: `search`, `folder`, `play` (solid triangle only inside the hover affordance), `chevron-left/right`, `chevron-down`, `close`, `film` (wordmark option). One weight, one style, everywhere.
