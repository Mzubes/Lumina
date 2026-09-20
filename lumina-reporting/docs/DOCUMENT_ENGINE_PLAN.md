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

### B · Print-CSS discipline · ~2–3 days

**Goal:** stop the silent-failure class found in testing.

- **`color-mix()` renders nothing in WeasyPrint.** Verified: plain hex ✓,
  `linear-gradient` ✓, `color-mix` ✗ — and it fails **silently**.
  `styles.css` has **48 uses**.
- Precompute every derived colour into a literal token. The screen stylesheet
  may keep `color-mix`; the print stylesheet may not.
- Add a lint rule failing any `color-mix` in print CSS
- Golden-render tests: render N fixture documents to PNG, compare against
  committed references with a pixel tolerance. This is the only way a CSS
  regression in a PDF gets caught before a client sees it.

**Verification:** the lint rule fails on a deliberately reintroduced
`color-mix`; a deliberate 2px padding change fails the golden test.

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

### D · Template model v2 — sections and elements · ~1 week

**Goal:** the Coric-shaped model, expressed in the schema.

```
ReportTemplate
  └─ TemplateSection    band: bound to Dataset + DisplaySpec, iterates,
  │                     page-break rules, orientation, repeat-on-every-page
  └─ TemplateElement    x, y, w, h, z, type, binding, style
                        text | field | table | chart | image | line | box | page_number
```

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

### G · PPTX as a second renderer · ~1–1.5 weeks · optional

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

Requires `libreoffice-impress` in the container — **not** installed by
default; `libreoffice-core` alone has no PPTX filter.

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

1. **Absolute positioning inside bands, or full free placement per page?**
   Coric does both — absolute inside a band, bands flow. That is my
   recommendation, but it changes the element model, so it should be settled
   before Phase D.
2. **Is PPTX (Phase G) in or out?** It is genuinely optional. It buys the
   editable-deck use case and costs a second renderer to maintain.
3. **Who authors templates?** If marketing designers do, the canvas needs to
   feel like a design tool. If client-reporting ops do, it can lean more on
   presets and structure. This changes E2/E3 materially.

---

## Suggested order of attack

**A → B → F in parallel → C → D → E**, with G deferred until after E1–E3 prove
the canvas direction.

Phase A alone makes every existing document markedly better and takes about a
week. It is the highest ratio of visible improvement to risk in the whole
plan, and it needs no decisions from the list above.
