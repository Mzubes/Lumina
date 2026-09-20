# Document engine — phased plan

Replacing Lumina's template design and rendering stack so it can produce
marketing-quality documents from a visual canvas.

Status: **plan only.** Nothing below is built. Written after proving the two
load-bearing technical claims in this repo's own environment (see
[Evidence](#evidence-already-gathered)).

---

## What's settled

| Decision | Made |
|---|---|
| Lumina reports and displays **finalized** warehouse data (Snowflake) | confirmed |
| It **calculates nothing** — no accounting, performance or attribution | confirmed |
| Reconciliation happens **upstream**; Lumina gates publishing on the attestation | confirmed |
| The deliverable is a **marketing-quality document** | confirmed |
| Template authoring must be a **visual canvas**, not a form | confirmed |
| Layout supports **both** absolute placement and flowing bands | confirmed |
| **PPTX stays in scope** as a second renderer | confirmed |
| Template authors are ops, working from approved blocks; **marketing sets guidelines and retrieves content** | confirmed |
| Data model v2 (24 tables: entities + `Dataset`/`DisplaySpec` + `DataLoad` + `ReportSnapshot` + `BrandKit`) | designed, tested, not wired in |

---

## The gap, stated plainly

| | Today | Needed |
|---|---|---|
| Template editor | Vertical stack of collapsible cards. dnd-kit reorder only. **No x/y, no page, no free placement.** | Page-geometry canvas with select / drag / resize / snap / align |
| Renderer | `fpdf2` — imperative cursor writer. Core fonts **latin-1 only**; `pdf_renderer.py` carries a substitution table that silently turns em-dashes into hyphens | CSS Paged Media: running headers, page counters, controlled breaks, repeating table headers, real webfonts |
| Charts in PDF | matplotlib raster, bolted in per component | Vector SVG from the same components the app already renders |
| Template model | Flat ordered list of components | Sections (bands) bound to a dataset, containing positioned elements |
| Report reproducibility | PDF frozen at `file_path`, but export/preview **re-resolve live** — they disagree after any restatement | Frozen `ReportSnapshot` at approval; every format renders from it |

---

## Sequencing principle

**Renderer before canvas.**

The renderer is what makes marketing quality possible at all, and it can be
proven against the *existing* component model with no UI change — every
template in the system gets better the day it ships. Build the canvas first
and you are designing against a renderer that cannot honour what you draw.

The registry at `backend/renderers/__init__.py` is already the seam:

```python
RENDERERS = {'pdf': render_pdf, 'pptx': render_pptx, 'xlsx': render_xlsx, 'raw': render_raw}
```

Swapping the PDF entry is one line plus one new module. Everything upstream
of it — `resolve_report_content()` and its payload contract — is untouched.

---

## Phases

Each ships independently and is reversible. Sizes are rough engineering
estimates, not commitments.

### A · WeasyPrint renderer behind the existing model · ~1 week

**Goal:** every existing template renders dramatically better, with zero UI
change and zero data-model change.

- New `renderers/html_pdf_renderer.py`: resolved payload → Jinja HTML → WeasyPrint
- Component templates for the types already in `report_content.py`
  (`holdings_table`, `performance`, `text_block`, `data_table`, `people_grid`,
  `report_reference`, disclosures)
- `@page` rules from `ReportTemplate.header_config` / `footer_config`:
  running header, running footer, `counter(page)`/`counter(pages)`
- `theme_config` → CSS custom properties, so existing themed templates carry over
- Keep `fpdf2` registered as `pdf_legacy` for one release, for side-by-side

**Verification:** render the seeded Pzena factsheet both ways, diff visually,
and assert the Unicode that fpdf2 currently mangles survives intact.

**Risk:** low. Additive; old path stays until the new one is signed off.

---

### B · Print-CSS discipline · ~2–3 days · **SHIPPED**

**Goal:** stop the silent-failure class found in testing.

Probing 18 CSS features against the real engine found **two** silent
failures, not one:

| Feature | Result |
|---|---|
| `color-mix()` | draws nothing — `styles.css` uses it 48 times |
| `aspect-ratio` | draws nothing — a natural reach for a chart container |

Everything else tried renders correctly, **CSS grid and flexbox included**,
which is what makes a real layout engine viable here at all. The full
matrix is `tests/test_print_css_support.py`, and it is pinned in both
directions: a WeasyPrint upgrade that *starts* supporting one of the two
fails the suite, so the allow-list widens deliberately rather than by
accident.

- `tests/test_print_css_lint.py` scans every print-path source for a banned
  feature and reports file and line. The banned list is derived from the
  support matrix rather than restated, so there is no second list to forget.
  Commentary is stripped first — the template's own warning about
  `color-mix()` must stay writable.
- `tests/test_golden_documents.py` renders three fixtures (a factsheet, a
  60-row table that spans pages, and an edge-case document), rasterises
  every page, and compares against committed references.

Comparison runs on a **downsampled fingerprint**, not raw pixels: the same
document rasterised on two machines differs in thousands of glyph-edge
pixels without one visible change, so an exact-match test would be either
permanently red or uselessly loose. Measured separation on the factsheet:

| Change | Difference |
|---|---|
| none | 0.00% |
| one table row dropped | 3.9% |
| theme colour changed | 9.5% |
| chart removed | 100% |
| footer wording changed | 0.06% |

The 1% threshold sits cleanly between. The last row is the honest limit: a
coarse fingerprint cannot see a reworded footer, which is why the running
header and footer keep their own assertions in `test_html_pdf_renderer.py`.

A committed canary (`tests/golden/_environment.png`) renders text through
the engine but **not** through the report template. If it mismatches, the
machine lays out text differently and the golden tests **skip with that
reason** instead of failing — a red build for a reason nobody can act on is
worse than a gap you can read. CI installs `poppler-utils` and
`fonts-dejavu-core` so the tests actually run there rather than skipping.

**Verified:** raising the table font size 8.5pt → 10.5pt fails the golden
tests (4.2% and 14.3%) while leaving the canary matched — proving the guard
discriminates between "the document changed" and "this machine is
different". The lint catches a synthetic `color-mix` and ignores it in
comments. Also fixed in this phase: `pypdf`, imported by the Phase A tests,
was a dependency of nothing — CI would have failed on import.

---

### C · Server-side chart pipeline · ~1 week

**Goal:** vector charts in print, from one definition.

Three tiers, in order of preference:

1. **Existing components, as markup.** `BarChart` and `CompositionBar` are
   pure HTML/CSS (zero SVG elements); `AreaChart` and `DonutChart` are static
   SVG. All four render in WeasyPrint natively. Port their markup+CSS into
   the Jinja component templates — no library.
2. **Vega-Lite via `vl-convert-python`** for anything needing computed axes,
   scales or legends. Pure Rust, no Node, no browser. A spec is JSON, so a
   chart definition is a value a `DisplaySpec` can hold.
3. matplotlib (already a dependency) as the escape hatch.

- Chart colours resolve from `BrandKit.colors.chart_series`, not per-template
- Re-run the dataviz palette validator against the print ground

**Verification:** each chart type rendered at 300dpi and inspected; series
colours match the brand kit; no raster artefacts.

---

### D · Template model v2 — sections and elements · ~1.5 weeks

**Goal:** the Coric-shaped model, expressed in the schema.

```
ReportTemplate
  └─ TemplateSection    layout_mode: 'flow' | 'fixed'
  │                     flow  -> stacks, may iterate a Dataset, breaks across pages
  │                     fixed -> anchored at page coordinates, does not flow
  │                     + page-break rules, orientation, repeat-on-every-page
  └─ TemplateElement    x, y, w, h, z, type, binding, style
                        absolutely positioned WITHIN its section
                        text | field | table | chart | image | line | box | page_number
```

**Both layout modes, per the decision above.** A "free placement per page"
design is a `fixed` section covering the page; a flowing factsheet body is a
`flow` section. One model, both behaviours, and a template mixes them —
a fixed masthead and footer with a flowing body between them.

**The element model stays renderer-agnostic.** Because PPTX is in scope
(Phase G), no element may encode HTML-specific semantics. Position, size,
type, binding and style are abstract; each renderer maps them. A `style`
value names a brand-kit token, never a CSS declaration. This is now a hard
constraint rather than good practice — two renderers consume this tree.

- Both scoped by `firm_id`, both additive to schema_v2
- `TemplateElement.binding` references a `DatasetField` or a `DisplaySpec`
- Migration from today's flat component list: each component becomes a
  section with one full-width element, so nothing breaks
- Renderer reads sections/elements; absolute positioning inside a band,
  bands flow down the page

**Verification:** migrate the seeded Pzena template, render, confirm
byte-comparable output to Phase A.

---

### E · The canvas · ~3–4 weeks

**Goal:** the visual designer. Largest phase; sub-phases ship in order.

**Reframed by the authoring decision.** This is not a freeform design tool.
Templates are built by client-reporting ops from **approved building blocks**,
inside guardrails marketing sets:

- Colour and type are chosen from `BrandKit` **tokens**, never a free colour
  picker or font dropdown. Off-brand output should be unreachable, not
  discouraged.
- New sections start from the preset library (`templateLibrary.js` already
  holds the right catalogue — Fund Facts, Sector Weights, Region
  Concentration and the rest). A blank page is available but is not the
  default path.
- Free placement is real, but snapped to the brand grid and margin guides.
- Marketing's role here is **governance, not authoring**: they own the brand
  kit, the approved block catalogue and the disclosure rules. They are not
  expected to open the canvas.

| | Sub-phase | Delivers |
|---|---|---|
| E1 | Page surface + element model | A4/Letter, portrait/landscape, margins, rulers, grid, zoom. Elements as absolutely-positioned DOM. |
| E2 | Direct manipulation | Select, multi-select, drag, resize handles, snap-to-grid, snap-to-element, alignment guides, z-order, keyboard nudge, undo/redo. Via `interact.js` or `moveable` on DOM. |
| E3 | Properties inspector | Right panel: position, size, typography, colour from the brand kit, borders, padding — the Coric Properties pane. |
| E4 | Data binding | Bind an element to a `DatasetField` or `DisplaySpec`. Field picker driven by the dataset's own metadata. Live sample values on the canvas. |
| E5 | Sections + outline | Left/right outline of sections and pages, matching Coric's Sections pane. Band properties: data source, break behaviour, orientation. |
| E6 | Live preview | Render to PDF server-side, show beside the canvas. Same HTML both sides, so drift is structural zero. |

**Explicitly not Fabric.js or Konva.** Those draw to a bitmap canvas —
elements become canvas objects, which means reimplementing text layout, line
breaking, kerning and table flow, and then writing a second renderer for PDF.
Two layout engines that drift. A report is mostly text in tables; the browser
already does that perfectly.

**Verification:** rebuild the seeded Pzena factsheet from scratch on the
canvas, with no code, and render it.

---

### F · Snapshot freezing · ~3–4 days

**Goal:** close a defect that is live today.

`Report.file_path` holds a frozen PDF, but `routes/reports.py`'s export and
preview paths call `resolve_report_content()` again, live. After any upstream
restatement the PDF a client holds and the preview beside it disagree, and
nothing says so.

- Freeze the resolved payload into `ReportSnapshot` at approval, with a
  content hash
- Bind every `DataLoad` it drew on via `ReportDataBinding`
- Check `DataLoad.is_publishable` across the whole bound set before freezing
- All formats render from the snapshot thereafter
- A reissue is a new `version`, never an overwrite

**Independent of everything else** — could run in parallel from day one.

---

### G · PPTX as a second renderer · ~1–1.5 weeks

**Goal:** deck-shaped output, where clients want the editable file.

Proven working in this environment: branded `.pptx` → `python-pptx` injection
→ LibreOffice headless → PDF. Designer's fonts, colours and positions
preserved; table rows cloned with their formatting; native charts re-pointed
via `replace_data()` keeping series colours and legend.

**Two things found in testing that must be designed around:**

1. PowerPoint has **no flow layout**. An expanded table silently covered a
   text box beneath it — verified by z-order.
2. **The engine cannot know rendered height.** `python-pptx` reports the
   *authored* height (1.00") regardless of row count. Only the renderer knows
   the truth. Overflow detection therefore needs a probe render, or fixed
   whitespace budgets with a hard row cap.

Scope this to `pitchbook` / `meeting_pack` / `marketing` report types only.
Factsheets and statements stay on the HTML path, which has flow layout.

Confirmed in scope, so Phase D's element model must stay renderer-agnostic
from the start — retrofitting that later means rewriting every template.

Requires `libreoffice-impress` in the container — **not** installed by
default; `libreoffice-core` alone has no PPTX filter.

---

### H · Content retrieval for marketing · ~1–1.5 weeks · NEW

**Goal:** serve the persona the rest of this plan does not.

Marketing sets the guidelines and then **comes to the system to retrieve
content** — the latest approved factsheet for a fund, a sector chart to drop
into a pitch deck, an approved commentary paragraph to reuse. None of that is
template authoring, and none of it exists today.

- A content library over distributed reports and their frozen
  `ReportSnapshot`s: browse by fund / strategy / client / period, filtered to
  **approved and current only**
- Download a document in any registered format, or export a single component
  — a chart as SVG/PNG, a table as XLSX — without opening the report
- Reusable text blocks (commentary, disclosures) with their approval state
  visible, so nobody pastes a superseded paragraph into a new deck
- A "what changed" view: which packs moved since a given date

This is much of what Seismic actually sells, and it is closer to revenue than
the canvas is. It depends only on Phase F (snapshot freezing), not on the
canvas — so it can run in parallel with D and E.

---

## Evidence already gathered

Everything below was run in this repo's environment, not assumed.

| Claim | Evidence |
|---|---|
| WeasyPrint does real paged media | 3-page render with running header + footer, `Page 1 of 3`, forced break, table header repeating on page 2, full Unicode (Ørsted, em-dash, curly quotes), absolute positioning |
| Existing chart components are print-ready | `BarChart`/`CompositionBar` have 0 SVG elements (pure CSS); `AreaChart`/`DonutChart` are static SVG. All rendered in a WeasyPrint PDF at 150dpi |
| Vega-Lite renders server-side with no Node | `vl-convert-python`, 20KB SVG, computed axes/scale/legend |
| `color-mix()` fails silently in WeasyPrint | Isolated probe: hex ✓, gradient ✓, color-mix ✗ (renders nothing) |
| PPTX template injection works | Branded template → filled deck → PDF, with styling, cloned table rows and native chart preserved |
| PowerPoint has no flow layout | Expanded table covered the commentary box; z-order and declared-vs-rendered height confirmed |

---

## Risks

| Risk | Mitigation |
|---|---|
| Print CSS regressions are invisible until a client sees them | Golden-render tests (Phase B) are non-negotiable, not nice-to-have |
| Canvas scope creep — a layout designer is a genuinely large surface | E1–E6 ship in order; E1–E3 alone already beat today's editor |
| WeasyPrint CSS gaps beyond `color-mix` | Build a support-matrix fixture page early in Phase B and render it; find the gaps before the templates do |
| Brand fonts unlicensed for server embedding | Check licences before Phase C; `BrandKit.font_asset_uris` exists to hold them |
| Two renderers (HTML + PPTX) drift | They share the resolved payload and the brand kit; only chrome differs. Golden tests on both. |

---

## Open decisions

All three opening questions are now answered and folded into the phases
above. What remains open:

1. **Does marketing need to edit the approved block catalogue themselves, or
   does ops curate it on their behalf?** Changes whether Phase H ships a
   governance UI or just a read surface.
2. **Which brand fonts, and are they licensed for server-side embedding?**
   Blocks Phase C. `BrandKit.font_asset_uris` exists to hold them, but the
   licence question is commercial, not technical.
3. **What is the real page-count ceiling for a pack?** Drives whether
   rendering is synchronous or goes to a job queue. A 4-page factsheet is
   sub-second; a 200-page consolidated statement is not.

---

## Suggested order of attack

**A → B → F in parallel → C → D → E**, with H alongside D/E once F lands, and
G after E1–E3 prove the canvas direction.

Phase A alone makes every existing document markedly better and takes about a
week. It is the highest ratio of visible improvement to risk in the whole
plan, and it needs no decisions from the list above.
