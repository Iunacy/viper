---
name: "VIPER"
description: "A graphite robotics interface for real recorded motion and inspectable evidence."
colors:
  ice: "#b4ddf8"
  ice-hover: "#d7edfc"
  graphite: "#101214"
  panel: "#16191c"
  toolbar: "#131619"
  control: "#191e22"
  control-hover: "#252d34"
  divider: "#30373d"
  control-hover-border: "#778b9b"
  foreground: "#edf0f2"
  muted: "#a1abb4"
  prose: "#b7c0c7"
  status-border: "#3d515e"
  experimental: "#e8c895"
  experimental-border: "#62523b"
  planned: "#b5bdc5"
  planned-border: "#45515b"
  chart-cursor: "#f0c87d"
typography:
  display:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "clamp(64px, 7.8vw, 112px)"
    fontWeight: 600
    lineHeight: 0.93
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "clamp(44px, 6.2vw, 86px)"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Barlow, sans-serif"
    fontSize: "30px"
    fontWeight: 500
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Barlow, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "10px"
    fontWeight: 400
    letterSpacing: "0.035em"
  measurement:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "17px"
    fontWeight: 400
  action:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "11px"
    fontWeight: 400
    letterSpacing: "0.06em"
rounded:
  square: "0"
  control: "2px"
spacing:
  control-inline: "12px"
  panel-inline: "20px"
  workspace-inline: "25px"
  navigation-gap: "30px"
components:
  button-primary:
    backgroundColor: "{colors.ice}"
    textColor: "{colors.graphite}"
    typography: "{typography.action}"
    padding: "17px 21px"
  button-primary-hover:
    backgroundColor: "{colors.ice-hover}"
    textColor: "{colors.graphite}"
  button-control:
    backgroundColor: "{colors.control}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  button-control-hover:
    backgroundColor: "{colors.control-hover}"
  button-control-selected:
    backgroundColor: "{colors.ice}"
    textColor: "{colors.graphite}"
  select-control:
    backgroundColor: "{colors.control}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  navigation:
    textColor: "{colors.foreground}"
  status:
    textColor: "{colors.ice}"
    padding: "7px 9px"
  status-experimental:
    textColor: "{colors.experimental}"
  status-planned:
    textColor: "{colors.planned}"
  inspector:
    backgroundColor: "{colors.panel}"
    width: "305px"
  inspector-content:
    padding: "22px 20px"
  timeline:
    height: "18px"
    width: "100%"
  tab:
    textColor: "{colors.muted}"
    rounded: "{rounded.square}"
    padding: "18px 0"
  tab-selected:
    textColor: "{colors.ice}"
---

# Design System: VIPER

## Overview

**Creative North Star: "Graphite robotics laboratory"**

A graphite exhibition space opens into a precise, inspectable robotics workstation. Near-black graphite and deep charcoal establish the ground; soft white, cool gray and restrained ice blue keep the interface technical and calm. Real robot geometry supplies the cinematic focal material.

Use technical sans typography for hierarchy and reading, and monospaced values for measurements and recording identity. Thin dividers and tonal surfaces organize dense controls. Motion stays subtle and respects reduced-motion preferences.

**Key Characteristics:**

- Near-black graphite and deep charcoal surfaces.
- Soft white and cool gray with restrained ice blue.
- Technical sans typography and monospaced measurements.
- Real robot geometry, inspectable evidence and subtle motion.

## Colors

The palette combines graphite and cool metallic neutrals with a restrained ice-blue primary accent. The frontmatter is the normative source for values; names below describe their use.

### Primary

- **Ice** (`ice`): primary actions, selected controls, navigation state, source links and measured-data traces.
- **Ice hover** (`ice-hover`): the primary action's lighter hover surface.

### Neutral

- **Graphite** (`graphite`): page and renderer ground; dark foreground on ice controls.
- **Deep charcoal** (`panel`, `toolbar`): inspector and anchored workspace bands.
- **Control charcoal** (`control`, `control-hover`): native controls at rest and on hover.
- **Cool dividers** (`divider`, `control-hover-border`): thin structural separators and interactive hover borders.
- **Soft white** (`foreground`): main interface text.
- **Cool gray** (`muted`, `prose`): subordinate labels and readable explanatory copy.

Semantic exceptions remain narrow: `experimental` and its border mark experimental evidence; `planned` and its border mark planned work. `status-border` supports the ice status badge. `chart-cursor` marks playback position in the chart. These are functional states, not additional brand accents.

**The Evidence Status Rule.** Pair every evidence status color with a readable status label.

## Typography

**Display Font:** Barlow Condensed, sans-serif fallback.

**Body Font:** Barlow, sans-serif fallback.

**Label/Mono Font:** IBM Plex Mono, monospace fallback.

Fonts are self-hosted. Condensed headlines give compact statements presence, while the interface and research prose remain direct and readable. Monospaced text distinguishes technical identity and measured values.

### Hierarchy

- **Display:** the `display` role is the desktop hero scale, with responsive overrides in Layout.
- **Headline:** the `headline` role establishes the research introduction.
- **Title:** the `title` role introduces research sections.
- **Body:** the `body` role supports research prose, limited to (73ch). Hero copy uses (17px) at a line height of (1.5) and a width of (320px).
- **Label:** the `label` role is the shared technical base; contextual labels range from (6px) footer notes on compact screens to (12px) transport values.
- **Measurement:** the `measurement` role presents coordinates; the prominent current-error value uses (29px). Tables and transport use tabular numerals.
- **Action:** the `action` role supports the primary entry link.

**The Measurement Type Rule.** Use mono for measured values and recording identity, and sans for reading and interface hierarchy.

## Layout

The shared header is (76px) high with horizontal padding of (3.4vw). Navigation uses the `navigation-gap` spacing token. At widths up to (700px), the header becomes (64px) high with (20px) side padding; the narrowest breakpoint tightens the header further.

The homepage is a single-viewport composition beneath the header. Robot geometry occupies the right field on desktop and the upper field on mobile; compact copy and the primary entry link retain a clear reading area. The lab fills the viewport beneath the header, with a toolbar, flexible stage area, optional inspector and anchored transport. Its minimum height is (540px) on desktop and (650px) on mobile, allowing scrolling when necessary. Research uses a centered maximum width of (1440px), desktop side padding of (7vw), and (24px) mobile side padding. Results tables scroll horizontally.

The inspector is (305px) wide by default, (340px) from (1600px), and (270px) at widths up to (1050px). At widths up to (700px), it overlays the stage at a width of `min(280px, 78%)` and starts closed. Comparison stages stack at widths up to (1050px). The research pipeline changes from four columns to two on mobile; roadmap entries change from three columns to two at the intermediate breakpoint.

Display type becomes (128px) from (1600px), (82px) up to (1050px), and `clamp(51px, 12vw, 76px)` up to (700px). Compact-height screens have dedicated overrides at a maximum height of (720px); inspect the stylesheet before adding further competing overrides.

## Elevation & Depth

Use tonal layering, thin dividers and the rendered robot's lighting for depth. Controls and desktop panels have no ornamental shadow or glow. The mobile inspector has one structural shadow (`-18px 0 40px #0006`) to separate the overlay from the stage. Translucent stage captions and camera-control backgrounds maintain legibility over the renderer.

**The Structural Depth Rule.** Reserve interface shadows for the mobile inspector overlay; use surfaces and separators for ordinary grouping.

## Shapes

Controls use the `control` radius, while primary entry links, tabs, evidence badges and workspace panels remain square. Thin (1px) dividers define regions. Tabs use a (2px) selected underline. The small recording marker is circular; it is an indicator, not a general corner treatment.

## Components

### Buttons

Primary entry links use ice with graphite text, the `action` typography, generous inline spacing and a minimum desktop height of (48px). On mobile they use padding of (12px 15px), a minimum height of (43px), and (9px) type. Hover lightens the surface and translates the action upward by (2px).

Secondary controls use charcoal, a thin divider border and the `control` radius. Hover changes both border and background. Pressed toggles use ice with graphite text. Disabled buttons have opacity (0.45) and a wait cursor. Do not enable scene camera actions before the renderer is ready.

All interactive elements retain an ice focus outline of (2px) with an offset of (4px). Selection uses ice with graphite text.

### Inputs / Fields

Native selects share the secondary-control treatment. The experiment selector is a compact, transparent, borderless variant. Playback uses a full-width range input with ice accent and a height of (18px). Keep native keyboard operation and accessible labels.

### Navigation

Main navigation uses sans type at (14px), with ice for the current page and hover. Mobile navigation uses (12px), tightened to (11px) at the narrowest breakpoint. Inspector tabs use muted labels, ice selected text and an ice underline; the tab panel is scrollable.

### Evidence Status

Square outlined badges use mono labels at (8px) with padding of (7px 9px). Verified evidence uses ice, experimental evidence uses the restrained warm status color, and planned work uses neutral gray. Preserve the written qualifier in every variant.

### Workspace Containers

The inspector uses the panel surface and a left divider; content uses padding of (22px 20px). Toolbar and transport use the darker toolbar surface. Research groups use ruled sections and editorial spacing rather than a generic card grid.

### Motion and Recorded Scenes

Hero copy enters over (0.85s) with `cubic-bezier(0.16, 1, 0.3, 1)` and a short vertical displacement. Primary hover uses a (0.2s) background transition and a (0.3s) transform transition. View transitions fade the old route over (0.16s) and introduce the new route over (0.35s). Camera orbit damping is (0.09), independent of the recording clock.

Reduced motion removes CSS entrance and state transitions, uses automatic scrolling, disables route animation and leaves the hero paused initially. Playback remains a deliberate user action. Loading and graphics failure states use readable status text over the scene; they must remain truthful about available interaction.

## Do's and Don'ts

### Do:

- **Do** use real robot geometry and measured recording values.
- **Do** reserve ice blue for emphasis, selected controls, links and data traces.
- **Do** pair evidence status color with explicit text.
- **Do** retain visible keyboard focus and reduced-motion behavior.
- **Do** keep physical units, provenance and recording identity legible.

### Don't:

- **Don't** introduce a generic dashboard card grid as the visual identity.
- **Don't** fabricate telemetry or decorate the interface with invented signals.
- **Don't** add ornamental glow, heavy shadows or competing accent palettes.
- **Don't** use motion as the only way to communicate state.
