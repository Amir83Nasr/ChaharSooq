# ADR 007 — Desktop sidebar/theme motion performance (keep glass + grid)

Date: 2026-11-05 · Status: accepted

## Context

On desktop, collapsing/expanding the sidebar stuttered visibly, and the
theme toggle felt delayed (click → visible change lag). Both ship with the
shadcn `offcanvas` + `inset` sidebar, a glass (`backdrop-blur`) sticky
header, and a square grid background — glass and grid are design
requirements and must stay.

## Root causes

1. The grid (`.bg-grid-pattern`, two 48px `linear-gradient`s) was painted
   directly on `SidebarInset` — the box whose margin animates on every
   sidebar toggle and which contains the scroll area. Every animation frame
   and every scroll frame repainted the full-viewport grid.
2. The sticky glass header (`bg-background/50 backdrop-blur-lg`) sat above
   that repainting surface without its own stacking context, so each frame
   also re-rasterized the backdrop blur over new pixels.
3. The shared motion was 350ms of layout-driven transitions (gap `width`,
   inset `margin/margin-inline-start`), maximizing the frames where (1)+(2)
   compounded. The sliding panel additionally tracked `width` (static in
   the offcanvas variant) and carried a permanent `will-change`, pinning
   compositor layers for the page lifetime.
4. `transition-all` on theme icons, buttons, badges, tabs, and the sidebar
   rail forced the browser to track every property through the theme class
   flip, on top of the oklch `color-mix` style recalc the flip already costs.

## Decision

Optimize around glass + grid, never remove them:

- Grid lives on one dedicated absolute, non-scrolling layer inside
  `SidebarInset` (`apps/web/app/(dashboard)/layout.tsx`); never on an
  animating or scrolling container.
- Glass header keeps translucency + blur + the pull-under offset, with
  `isolate` (own stacking context) and `backdrop-blur-md` max radius
  (`apps/web/components/layout/dashboard-header.tsx`).
- One shared 220ms duration/easing (`--sidebar-transition-duration`); panel
  transitions only `transform`; no permanent `will-change` anywhere.
- Staged choreography: labels/icons (`.sidebar-collapse-label`,
  `.sidebar-collapse-icon`, `.sidebar-collapse-fade`) fade out fast with no
  delay on close and fade in delayed (~80ms) on open, via
  direction-dependent transition params (see the STAGED CHOREOGRAPHY comment
  in `globals.css`). Slide/push itself is never delayed; total stays ~220ms.
- No `transition-all`: list only animated props. Keep
  `disableTransitionOnChange` on the next-themes provider. Never
  `background-attachment: fixed` on these surfaces.

## Alternatives

- Removing glass/grid: rejected — required by design (user-confirmed).
- Overlay (non-push) sidebar to dodge layout animation: rejected — changes
  the push UX; the layered-paint fix made the push smooth enough.
- Longer duration to "smooth" the motion: rejected — more frames of joint
  blur+grid repaint reads as more lag, not less.

## Consequences

- Enforced by `AGENTS.md` §10 (Motion performance); this ADR is the
  root-cause record. Any change to header blur, grid placement, sidebar
  duration, or global transitions must re-check this ADR first.
