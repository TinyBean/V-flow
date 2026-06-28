# Product

## Register

product

## Users

One person, on their own computer, browsing their own local video library in a desktop browser — usually in a dim room, often in the middle of watching something. The job: get from "I have hundreds of files in nested folders" to "this one is playing, now" with as little friction as possible. Occasional secondary use is a phone over LAN (so the result must stay responsive), but desktop is primary. The user is the owner and only audience — there is nothing to sell and nobody to impress; the interface only needs to earn trust from someone fluent in good tools.

## Product Purpose

V-flow is a tiny local video browser: point it at a folder, browse the tree, see thumbnails, search within a folder, and play any file in a clean standalone tab. Success is measured in seconds-to-play, not in delight or feature count. It exists because the OS file explorer is a poor place to look at a video library and a full media server (Plex/Jellyfin) is overkill.

## Brand Personality

Restrained. Editorial. Quiet. Three words: *calm, precise, image-forward*. The video frames are the only color that matters; the chrome stays out of the way. Tone is like a well-set cinema room or a quiet film magazine — confident enough to use lots of dark space and small type, never shouting, never decorating. Refined rather than friendly, trustworthy rather than flashy.

## Anti-references

- **The current V-flow design itself** — gradient-text logo, emoji-as-icons (📁🎬🔍▶), uppercase letter-spaced section labels, decorative red glow/shadows. These are the generic "AI dark dashboard" tells and the first thing to leave behind.
- **Plex / Jellyfin busy chrome** — gradients, glossy cards, heavy metadata overlays, branded color blocks. Overkill for a single-user tool.
- **"Cool dark tool" aesthetics** — neon accents, glassmorphism cards, glowing hover states. Decoration posing as design.
- **Marketing landing-page grammar** — hero metrics, tracked eyebrows, numbered sections. This is a tool, not a pitch.

## Design Principles

1. **The content is the design.** Thumbnails and the video itself are the only imagery. Chrome recedes; structure is carried by type, space, and hairline rules — never by cards, shadows, or color fills.
2. **Editorial restraint over decoration.** Hierarchy comes from typography and whitespace. Color is reserved for state (active, focus, current, error) and used as little as possible.
3. **Disappear into the task.** The measure of a session is seconds-to-play. Nothing animates for its own sake; nothing demands attention that isn't the video.
4. **Dark by scene, not by default.** Dark surfaces exist because the user watches video in dim rooms — a real physical scene — not because dark looks "pro."
5. **Earned familiarity.** Standard affordances (search field, breadcrumb, pagination, native video controls) used cleanly and consistently. Don't reinvent controls for flavor.

## Accessibility & Inclusion

- WCAG AA contrast on all text and meaningful UI (≥4.5:1 body / ≥3:1 large), including secondary metadata like file size and counts.
- Full keyboard operability: the player's existing shortcuts (←/→ seek, space pause) and focus-visible states across every interactive element.
- Honor `prefers-reduced-motion`: any motion has an instant/crossfade fallback.
- Thumb-friendly hit targets for the secondary phone-over-LAN use.
