// Page geometry for the template canvas.
//
// The canvas and the PDF renderer must agree about size, or a template
// designed here prints somewhere else. They agree by using the SAME UNIT:
// every position and size below is millimetres, and the canvas lays
// elements out with CSS `mm` exactly as renderers/templates/report.html
// does. There is no conversion in the layout path and therefore nothing to
// get wrong -- which is the whole reason the plan rules out a bitmap canvas
// (Fabric, Konva), where positions become pixels and a second layout engine
// starts drifting from the first.
//
// MM_TO_PX exists only for the ruler and grid, which have to be drawn in
// device pixels. CSS defines 1mm as exactly 96/25.4 px, so this constant is
// the spec's, not a guess.

export const MM_TO_PX = 96 / 25.4;

// Matches schema_v2/templates.py PAGE_SIZES. Dimensions are the portrait
// short and long edges in millimetres.
export const PAGE_SIZES = {
  a4: { label: 'A4', width: 210, height: 297 },
  letter: { label: 'Letter', width: 215.9, height: 279.4 },
  legal: { label: 'Legal', width: 215.9, height: 355.6 },
  a3: { label: 'A3', width: 297, height: 420 },
};

export const ORIENTATIONS = ['portrait', 'landscape'];

// The template defaults in schema_v2, repeated here so a new template on
// the canvas starts where a new template in the database starts.
export const DEFAULT_MARGINS_MM = { top: 26, bottom: 20, left: 16, right: 16 };

export const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];

export const mmToPx = (mm, zoom = 1) => mm * MM_TO_PX * zoom;
export const pxToMm = (px, zoom = 1) => px / (MM_TO_PX * zoom);

// Rounding a dragged position to the model's own precision. The schema
// stores three decimals; keeping the canvas to the same precision means a
// position survives a round trip unchanged instead of drifting a hair each
// time it is saved.
export const roundMm = (mm) => Math.round(mm * 1000) / 1000;

export const pageSize = (size = 'a4', orientation = 'portrait') => {
  const base = PAGE_SIZES[size] || PAGE_SIZES.a4;
  return orientation === 'landscape'
    ? { width: base.height, height: base.width }
    : { width: base.width, height: base.height };
};

// The area a section may occupy: the sheet less its margins. Everything an
// author places is positioned relative to this box, not to the sheet, which
// is why a template with wider margins does not need its elements moved.
export const contentBox = (page) => {
  const { width, height } = pageSize(page.size, page.orientation);
  const margins = { ...DEFAULT_MARGINS_MM, ...(page.margins || {}) };
  return {
    x: margins.left,
    y: margins.top,
    width: width - margins.left - margins.right,
    height: height - margins.top - margins.bottom,
  };
};

// Ruler ticks, in millimetres from the sheet edge. The interval widens as
// the page shrinks so the ticks never collide: at 50% an A4 width would
// otherwise carry 210 labels in 400px.
export const rulerTicks = (lengthMm, zoom = 1) => {
  const minLabelGapPx = 44;
  const interval = [5, 10, 20, 25, 50, 100]
    .find(step => mmToPx(step, zoom) >= minLabelGapPx) || 100;
  const ticks = [];
  for (let mm = 0; mm <= lengthMm + 0.001; mm += interval) {
    ticks.push(roundMm(mm));
  }
  return { interval, ticks };
};

// Grid spacing in millimetres. A 5mm grid is the usual typographic step
// here; below 75% it doubles rather than rendering as grey mush.
export const gridStepMm = (zoom = 1, baseMm = 5) => (zoom < 0.75 ? baseMm * 2 : baseMm);

export const snapMm = (mm, stepMm) => (stepMm > 0 ? roundMm(Math.round(mm / stepMm) * stepMm) : roundMm(mm));

// Keeps a box inside the content area. An element dragged past the edge is
// a template that prints off the page, so the canvas does not allow it.
export const clampToBox = (box, bounds) => {
  const width = Math.min(box.w_mm, bounds.width);
  const height = Math.min(box.h_mm, bounds.height);
  return {
    x_mm: roundMm(Math.min(Math.max(box.x_mm, 0), bounds.width - width)),
    y_mm: roundMm(Math.min(Math.max(box.y_mm, 0), bounds.height - height)),
    w_mm: roundMm(width),
    h_mm: roundMm(height),
  };
};
