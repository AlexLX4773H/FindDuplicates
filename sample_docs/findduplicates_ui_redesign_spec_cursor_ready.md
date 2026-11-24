# FindDuplicates Dashboard — UI/UX Redesign Specification (Obsidian & Gold)

> **Instructions for Cursor AI:** Use this document as the authoritative design and refactoring blueprint for the FindDuplicates web frontend. Before modifying files, inspect the existing repository structure, templates, stylesheets, and JavaScript/framework state handlers. **Do not remove, break, or stub out any existing functionality, API calls, modal dialogs, or Docker/CasaOS runtime behaviors.**

---

## 1. Clutter Audit: What Is Making the Current UI Feel Crowded & Generic

Based on an audit of the current dashboard layout, five core structural and visual issues create friction:

1. **5 Stacked Horizontal Bars ("Chrome Bloat"):**
   Currently, nearly 35–40% of vertical screen height is consumed before the first duplicate card appears:
   - Row 1: Top navbar (brand, subtitle, 3 stat pills, 6 action buttons)
   - Row 2: Full-width Read-Only Guarantee banner + Active View label
   - Row 3: Active Report filename + HTML/CSV/JSON export buttons + Discard + Saved Reports button
   - Row 4: Main navigation tabs + Run Scan button
   - Row 5: Filter pills + Keep All / Pre-Select Best + Search input
2. **Triplicated & Duplicated Controls:**
   - **Saved Reports** appears in **3 different places** (Top bar, Report bar, Main Tabs).
   - **Scan Jobs** appears in **2 different places** (Top bar, Main Tabs).
   - **Quick Scan** and **Run Scan** compete as two bright blue primary actions in two different bars.
   - **Duplicate counts** appear both as top-bar stat pills (`Manga Dupes 3`, `Doujinshi Dupes 0`) and as filter pills (`Manga 3`, `Doujinshi 0`).
3. **Generic "Neon Rainbow on Slate" Theme:**
   - Deep navy-slate (`#0f172a`) combined with neon purple tabs, cyan scan buttons, orange-red removal buttons, bright blue info banners, and saturated green/brown row washes produces high visual fatigue and looks like a generic boilerplate dark theme.
   - Too many saturated accents compete at equal visual weight, destroying hierarchy.
4. **Heavy Visual Noise Inside Duplicate Cards:**
   - Full-row background tints (muddy green and muddy brown) make scanning long lists tiring.
   - Long file paths (`/DATA/SharedSgb/...`) run at full width directly under titles, visually drowning out the key decision-making metrics (`Group`, `Pages`, `Volume`).
   - Raw snake_case reason tags (`alternative_translation`, `version_upgrade`, `exact_duplicate`) and bracketed technical strings (`[Visual Verification: Visual match verified (Hamming distance: 2)]`) sit inline inside loud blue boxes.

---

## 2. Zero-Functionality-Loss Consolidation Map

Every single control, indicator, and workflow from the current UI is preserved and relocated to a logical, de-duplicated home:

| Existing Element | Current Location(s) | New Location | Improvement |
| :--- | :--- | :--- | :--- |
| Brand Logo & Title | Top bar left | Sidebar top header | Clean obsidian monogram + refined typography |
| `Report`, `Scan Jobs`, `Saved Reports`, `Offline Tree Dumps` | Duplicated across Row 1, Row 3, Row 4 | **Left Sidebar Primary Nav** (Single source of truth) | Eliminates 5 redundant buttons across 3 bars |
| `Quick Scan` & `Run Scan` | Separate blue buttons in Row 1 & Row 4 | **Left Sidebar Primary Split/Dual Action** (`Quick Scan` + `Custom Scan` trigger) | Unifies scanning actions in one predictable spot |
| `Scanned`, `Manga Dupes`, `Doujinshi Dupes` | 3 pills crammed in Row 1 | **Left Sidebar Compact Telemetry Card** (3-column mini grid) | Scannable at a glance without cluttering header |
| `Scan Logs (0)` & `CasaOS Guide` | Crowded into Row 1 | **Left Sidebar Bottom Utilities** | Keeps infrequent utility modals accessible but quiet |
| `READ-ONLY GUARANTEE` Banner | Full-width Row 2 strip | **Left Sidebar Footer Safe-Mode Badge** (with hover/click popover showing full text) | Reclaims 48px of vertical viewport while remaining permanently visible |
| Active Report Filename (`*.json`) | Row 3 left | **Sticky Top Bar Left** (context pill) | Always visible while scrolling through duplicates |
| `HTML Report`, `CSV`, `JSON` Exports | 3 separate buttons in Row 3 | **Sticky Top Bar `Export ▾` Dropdown Menu** | Collapses 3 buttons into 1 sleek dropdown |
| `Discard Report` | Bright red button in Row 3 | **Sticky Top Bar subtle ghost icon/button** next to active report pill (turns crimson on hover) | Reduces accidental clicks & visual noise |
| `Review & Confirm Removal (N)` | Orange-red button in Row 1 | **Sticky Top Bar Right — Signature Gold Primary CTA** | Clear #1 focal point on the entire page |
| `All Duplicates`, `Manga`, `Doujinshi`, `Partials / Splits` | Row 5 left | **Workspace Filter Bar Left** (sleek underline/pill segmented tabs) | Cleaner hierarchy directly above the list |
| `Keep All`, `Pre-Select Best`, Search Input | Row 5 right | **Workspace Filter Bar Right** | Compact inline toolbar with subtle styling |
| `Keep Both` + Category Tag (`alternative_translation`) | Card header right | **Card Header** (formatted human-readable badge + subtle `Keep Both` ghost button) | Better readability (`Alternative Translation`, `Version Upgrade`, `Exact Duplicate`) |
| Recommendation + `[Visual Verification...]` | Loud blue full box | **Slim Gold-Left-Border Insight Strip** + dedicated **Visual Match / Hamming Pill** in card header | Separates human guidance from machine verification telemetry |
| Candidate Row (`Keep` / `Archive` / `Delete`, `RECOMMENDED BEST`, `HQ`, Path, Group/Pages/Vol) | Muddy green/brown full-row fills | **Crisp Dark Row with `3px` Semantic Left Edge Bar**, inline Gold `★ Best Match` badge, structured monospace metadata chips, truncated path with click-to-copy, and refined 3-way segmented control | Effortless side-by-side comparison with dramatically lower eye strain |

---

## 3. Design System: "Obsidian & Burnished Gold"

The new aesthetic draws from **precision archival instruments and luxury dark interfaces**: deep obsidian blacks for effortless focus, hairline structural dividers, warm champagne/burnished gold for primary focus and recommendations, and restrained semantic tones for file actions.

### 3.1 Color Palette (CSS Custom Properties)

```css
:root {
  /* --- Obsidian Surfaces --- */
  --bg-canvas: #050505;            /* True obsidian pure-black page backdrop */
  --bg-sidebar: #0A0A0C;           /* Subtle elevated sidebar surface */
  --bg-surface: #0E0E11;           /* Primary card / panel surface */
  --bg-surface-elevated: #141418;  /* Hover states, dropdowns, inputs */
  --bg-surface-subtle: #1A1A20;    /* Active neutral pills, segmented tracks */

  /* --- Structural Borders --- */
  --border-subtle: rgba(255, 255, 255, 0.07);
  --border-default: rgba(255, 255, 255, 0.12);
  --border-gold-subtle: rgba(212, 175, 55, 0.24);
  --border-gold-strong: rgba(212, 175, 55, 0.55);

  /* --- Gold Accent Hierarchy --- */
  --gold-primary: #D4AF37;         /* Burnished gold — primary accents & CTA */
  --gold-bright: #EED278;          /* Champagne highlight — text on dark & hover */
  --gold-muted: #9E8028;           /* Muted antique gold — icons, dividers */
  --gold-tint: rgba(212, 175, 55, 0.10);
  --gold-glow: rgba(212, 175, 55, 0.18);

  /* --- Typography Colors --- */
  --text-primary: #F4F4F6;         /* High-contrast crisp off-white */
  --text-secondary: #A1A1AA;       /* Metadata, labels, secondary descriptions */
  --text-muted: #666670;           /* Paths, timestamps, inactive icons */
  --text-on-gold: #090805;         /* Deep onyx text placed on solid gold buttons */

  /* --- Restrained Semantic Status Colors --- */
  /* Keep = Muted Emerald */
  --status-keep: #34D399;
  --status-keep-bg: rgba(52, 211, 153, 0.10);
  --status-keep-border: rgba(52, 211, 153, 0.35);

  /* Archive = Warm Amber Gold */
  --status-archive: #E5A93C;
  --status-archive-bg: rgba(229, 169, 60, 0.12);
  --status-archive-border: rgba(229, 169, 60, 0.40);

  /* Delete = Controlled Crimson */
  --status-delete: #F87171;
  --status-delete-bg: rgba(248, 113, 113, 0.10);
  --status-delete-border: rgba(248, 113, 113, 0.38);
}
```

### 3.2 Typography

- **Primary UI Font:** `'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif`
- **Monospace Font (filenames, paths, JSON report names, page counts, Hamming distance):** `'JetBrains Mono', ui-monospace, SFMono-Regular, monospace`
- **Numeric Alignment:** Always apply `font-variant-numeric: tabular-nums;` to counters, badges, page counts, and Hamming distances.

| Role | Size | Weight | Tracking / Notes |
| :--- | :--- | :--- | :--- |
| App Brand | `15px` | `700` | `-0.02em`, crisp white + gold dot/icon |
| Group Card Title | `15px` | `600` | `-0.01em`, `#F4F4F6`, chapter number in `#A1A1AA` |
| Candidate Filename | `13.5px` | `600` | `#F4F4F6`, subtle hover highlight |
| Recommendation Text | `12.5px` | `400` | `#C8C8D0`, line-height `1.5` |
| Metadata Chips | `11.5px` | `500` | Monospace, `#A1A1AA` labels + `#E4E4E8` values |
| File Path | `11px` | `400` | Monospace, `#666670`, `text-overflow: ellipsis` |
| Micro Badges | `10px` | `600` | Uppercase, `+0.06em` letter spacing |

### 3.3 Elevation, Borders & Radii

- **No heavy drop shadows** on black backgrounds (they turn muddy). Rely on **surface luminance stepping** (`#050505` -> `#0E0E11` -> `#141418`) and **`1px` crisp borders**.
- **Gold subtle glow** (`0 0 24px rgba(212, 175, 55, 0.16)`) reserved *exclusively* for the primary `Review & Confirm Removal` CTA button and active modal overlays.
- **Border Radius:**
  - Cards & Modals: `12px`
  - Inputs, Buttons, Segmented Tracks: `8px`
  - Micro-tags & Status Badges: `6px` (avoid overly bubbly full pill spam except for small numeric counters)

---

## 4. Layout & Component Architecture

### 4.1 Overall Shell Layout

```text
+-----------------------+---------------------------------------------------------------------+
|  SIDEBAR (252px)      |  STICKY TOP BAR (60px)                                              |
|  -------------------  |  [Report: full_exe_...json] [Export v] [Trash]   [Review & Confirm 3]|
|  [FD] FindDuplicates  +---------------------------------------------------------------------+
|                       |  WORKSPACE CONTAINER (max-width: 1140px, centered, padding: 28px)   |
|  [⚡ Quick Scan] [⚙]  |                                                                     |
|                       |  FILTER BAR:                                                        |
|  NAVIGATION           |  [All 3] [Manga 3] [Doujinshi 0] [Partials 0]                       |
|  > Resolution Report 3|                          [Search...] [Keep All] [✨ Pre-Select Best]|
|    Scan Jobs         4|                                                                     |
|    Saved Reports     4|  +---------------------------------------------------------------+  |
|    Offline Tree Dumps |  | MANGA  Flag Capture in the First Move · Ch. 1                 |  |
|                       |  |        [Alternative Translation] [✓ Visual · H:2] [Keep Both] |  |
|  CURRENT SCAN         |  |---------------------------------------------------------------|  |
|  Scanned | Manga | Dj |  | ┃ Recommendation: Multiple scanlation groups found...         |  |
|     3    |   3   |  0 |  |---------------------------------------------------------------|  |
|                       |  | ┃ Fuyuking_Ch.1 - Honest-Considerate MC...                    |  |
|  -------------------  |  | ┃ Group: Fuyuking · 4 Pages · Vol: Aaa     [Keep|Archive|Del] |  |
|  UTILITIES            |  | ┃ .../Manga_1/Aaa/Flag Capture.../Fuyuking_Ch.1... [copy]     |  |
|  • Scan Logs         0|  |---------------------------------------------------------------|  |
|  ? CasaOS Guide       |  | ┃ RingMeigh_Ch.1 - Kind and good-hearing... [★ Best Match]    |  |
|                       |  | ┃ Group: RingMeigh · 5 Pages · Vol: Aaa    [Keep|Archive|Del] |  |
|  [🛡 Read-Only Safe]  |  | ┃ .../Manga_1/Aaa/Flag Capture.../RingMeigh_Ch.1... [copy]    |  |
+-----------------------+  +---------------------------------------------------------------+  |
```

### 4.2 Detailed Component Specifications

#### A. Left Sidebar (`252px` fixed on desktop, slide-over drawer `< 1024px`)
- **Header:** Custom minimalist geometric monogram in gold (`#D4AF37`) + `FindDuplicates` wordmark.
- **Scan Control Group:**
  - Full-width split row: Primary dark-gold-bordered button `⚡ Quick Scan` (`flex: 1`) paired with an icon button (`Sliders` / `Play`) for `Run Custom Scan` (opens the full scan configuration modal).
- **Navigation List:**
  - Active item uses `--gold-tint` background, `--border-gold-subtle` border, `2px` gold left accent bar, `--gold-bright` icon, and crisp white text.
  - Inactive items use transparent background, `--text-secondary` text, subtle hover to `--bg-surface-elevated`.
  - Numeric badges sit flush right in monospace.
- **Compact Telemetry Widget:**
  - Single bordered box (`--bg-surface`) divided into 3 equal columns: `Scanned`, `Manga`, `Doujinshi`.
- **Footer Utilities:**
  - `Scan Logs` (with subtle emerald/muted live dot + log count badge).
  - `CasaOS Guide` (opens guide modal).
  - **Read-Only Guarantee Pill:** Subtle bordered pill with gold shield icon `Read-Only Safe Mode`. Hovering or clicking reveals a crisp popover with the exact guarantee copy: *"Scans only generate reports. No files are ever moved or deleted automatically. All changes require explicit manual confirmation."*

#### B. Sticky Top Bar (`60px` height, `backdrop-filter: blur(12px)`, `rgba(5, 5, 5, 0.85)`)
- **Left Group (Active Report Context):**
  - Subtle status indicator dot (gold when loaded) + monospace report name (`full_exe_20261123_203315_report.json`) inside a dark pill.
  - **`Export ▾` Dropdown Button:** Clicking opens a crisp obsidian menu listing `HTML Report`, `CSV`, and `JSON`.
  - **`Discard Report` Icon Button:** Ghost trash/close icon with tooltip `"Discard Active Report"`. Turns muted crimson on hover.
- **Right Group (Primary Action):**
  - **`Review & Confirm Removal` Button:** Solid burnished gold gradient (`linear-gradient(135deg, #E5C158 0%, #C59B27 100%)`), dark onyx bold text (`#090805`), and an embedded dark pill counter badge (e.g., `3`) showing total items staged for Archive/Delete. Disabled/dimmed gracefully when `0` actions are pending.

#### C. Workspace Filter & Batch Action Bar
- Placed inside the main scroll area (or optionally sticky below top bar) with generous spacing (`margin-bottom: 20px`).
- **Left:** Clean segmented filter tabs (`All Duplicates`, `Manga`, `Doujinshi`, `Partials / Splits`) with muted numeric counters. Active filter has a subtle gold bottom border or gold-tinted obsidian pill.
- **Right:**
  - Compact search input (`width: 220px`, dark `--bg-surface`, gold border on focus) with magnifying glass icon.
  - `Keep All` ghost button (emerald dot/icon on hover).
  - `Pre-Select Best` gold-outlined ghost button (`✨` / sparkle icon in gold).

#### D. Duplicate Group Card
- Container: `--bg-surface` (`#0E0E11`), `1px solid var(--border-subtle)`, `border-radius: 12px`, `overflow: hidden`, `margin-bottom: 20px`.
- **1. Card Header (`padding: 14px 20px`, `border-bottom: 1px solid var(--border-subtle)`):**
  - Left:
    - Media type micro-badge (`MANGA` in `--gold-tint` with `--gold-bright` text; `DOUJINSHI` in subtle zinc/rose tint).
    - Title: `Flag Capture in the First Move` + muted separator `·` + `Chapter 1`.
  - Right:
    - Formatted match-reason tag (`Alternative Translation`, `Version Upgrade`, `Exact Duplicate`) in neutral elevated chip.
    - Visual Verification chip (parsed cleanly from the data): `✓ Visual Match · Hamming 2` in subtle monospace pill.
    - `Keep Both` button: Compact secondary button (`shield/check` icon) that sets all candidates in this group to `Keep`.
- **2. Recommendation Strip (`padding: 10px 20px`, `background: rgba(212, 175, 55, 0.04)`, `border-bottom: 1px solid var(--border-subtle)`):**
  - Thin `2px` vertical gold bar on the left edge (`box-shadow: inset 2px 0 0 var(--gold-primary)`).
  - Gold sparkle/info icon + concise recommendation text (strip redundant `[Visual Verification...]` suffix if displayed in the header pill, or style it neatly as a secondary muted tag).
- **3. Candidate File Rows:**
  - Separated by `1px solid var(--border-subtle)`.
  - **CRITICAL ANTI-CLUTTER RULE:** Do **NOT** flood the entire row background with opaque green or brown. Instead:
    - Base row background stays clean `--bg-surface` (`#0E0E11`), with an ultra-subtle `2–3%` tint at most on hover.
    - Apply a **`3px` solid left-edge indicator bar** (`border-left: 3px solid ...`) matching the candidate's current action state:
      - `Keep`: `--status-keep` (`#34D399`)
      - `Archive`: `--status-archive` (`#E5A93C`)
      - `Delete`: `--status-delete` (`#F87171`)
  - **Row Left Content:**
    - **Title Line:** Crisp filename + optional badges:
      - `★ Best Match` (replaces `RECOMMENDED BEST`) styled in `--gold-tint` with `--gold-bright` text and `--border-gold-subtle`.
      - `HQ` badge styled in crisp white/gold micro-chip.
    - **Metadata Line:** Structured horizontal chips with crisp contrast:
      - `Group: RingMeigh` · `Pages: 5` · `Vol: Aaa` (highlight higher page counts or HQ naturally via crisp white values).
    - **Path Line:** Single-line truncated monospace path (`direction` or smart middle/end ellipsis) with full path in `title` tooltip and a subtle `Copy` icon button that appears on row hover.
  - **Row Right Control (3-Way Segmented Toggle):**
    - Track: `--bg-canvas` (`#050505`) with `1px solid var(--border-subtle)`, `padding: 3px`, `border-radius: 8px`.
    - Three compact buttons: `Keep`, `Archive`, `Delete`.
    - Inactive buttons: transparent, `--text-muted`, hover to `--text-primary`.
    - Active button: subtle tinted fill + matching border + crisp colored text:
      - Active `Keep`: `--status-keep-bg`, `--status-keep-border`, `--status-keep`
      - Active `Archive`: `--status-archive-bg`, `--status-archive-border`, `--status-archive`
      - Active `Delete`: `--status-delete-bg`, `--status-delete-border`, `--status-delete`

---

## 5. Implementation Rules & Refactor Checklist for Cursor

When applying this redesign to the `FindDuplicates` codebase, follow this exact execution plan:

1. **Audit Existing Bindings First:**
   - Locate all HTML templates, CSS files, and JS modules (or React/Vue/Alpine/Vanilla scripts).
   - Map every `id`, `data-*` attribute, `onclick` / event listener, WebSocket/polling hook, and API endpoint (e.g., `/api/scan`, `/api/reports`, `/api/export`, `/api/confirm`).
   - Preserve every modal (`Review & Confirm Removal`, `Scan Logs`, `CasaOS Guide`, `Run Scan` options) and restyle them using the exact same Obsidian & Gold tokens (`--bg-surface`, `--border-gold-subtle`, `--gold-primary` confirm buttons, `--status-delete` destructive confirmations).
2. **Replace Stylesheet / Theme Tokens:**
   - Remove generic slate/purple/neon-blue utility classes or CSS variables.
   - Load `Plus Jakarta Sans` and `JetBrains Mono` (either via Google Fonts with clean system fallbacks so offline Docker/LAN environments like CasaOS still render crisply!).
   - Define the Section 3.1 CSS custom properties at `:root`.
3. **Refactor Shell into Sidebar + Sticky Topbar:**
   - Move duplicated navigation buttons into the single Left Sidebar.
   - Ensure switching between `Resolution Report`, `Scan Jobs`, `Saved Reports`, and `Offline Tree Dumps` calls the exact same view-switching logic as before.
   - Consolidate `HTML Report`, `CSV`, and `JSON` buttons into the topbar `Export ▾` dropdown while preserving their exact download URLs / handlers.
4. **Upgrade Duplicate Cards & Candidate Rows:**
   - Format reason codes cleanly in the UI display layer (`alternative_translation` -> `Alternative Translation`) without altering underlying JSON data values.
   - Extract `[Visual Verification: ...]` via regex in the render helper to populate the header verification badge when present, gracefully falling back to inline display if the format differs.
   - Replace full-row color washes with the `3px` semantic left border and refined 3-way segmented control.
5. **Verify Offline / CasaOS LAN Compatibility:**
   - Since this runs as a self-hosted Docker app on local IPs (e.g., `192.168.x.x:8765`), ensure all icons are inline SVGs (zero external icon-font dependencies required to function) and fonts gracefully fall back to system sans/mono if offline.
6. **Verify Responsive Behavior:**
   - Desktop (`>= 1024px`): Fixed `252px` sidebar + fluid workspace.
   - Tablet/Mobile (`< 1024px`): Sidebar collapses into a hamburger toggle drawer in the top bar; candidate rows stack action controls cleanly below metadata.