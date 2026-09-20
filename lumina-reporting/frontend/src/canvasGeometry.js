// Drag, resize, snap and align — as arithmetic, separate from the pointer
// events that drive it.
//
// It lives apart from the React component for one reason: this is where a
// bug produces an element a millimetre off where the author put it, and
// that is far easier to catch in a test than by dragging a box and
// squinting. The component's job is only to turn pointer deltas into
// millimetres and hand them here.
//
// Everything below is millimetres. Zoom never appears: the caller divides
// the pixel delta by the scale before calling in, so this module cannot be
// wrong about zoom because it never sees it.

import { roundMm } from './paper';

export const HANDLES = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];

// Smallest element the canvas will make. Below this a box is unclickable
// and, at 8pt, could not hold a character anyway.
export const MIN_SIZE_MM = 4;

// How close an edge has to be before it snaps. In millimetres, so the
// behaviour is the same at every zoom -- a tolerance in pixels would snap
// hard when zoomed out and barely at all when zoomed in.
export const SNAP_TOLERANCE_MM = 1.5;

const edges = (box) => ({
  start: box.x_mm,
  centre: box.x_mm + box.w_mm / 2,
  end: box.x_mm + box.w_mm,
});

const verticalEdges = (box) => ({
  start: box.y_mm,
  centre: box.y_mm + box.h_mm / 2,
  end: box.y_mm + box.h_mm,
});

// The lines an element can snap to: the content box's own edges and
// centre, plus every edge and centre of the other elements. This is what
// makes two elements line up exactly rather than approximately.
export const snapLines = (bounds, others) => {
  const x = [0, bounds.width / 2, bounds.width];
  const y = [0, bounds.height / 2, bounds.height];
  for (const box of others) {
    const horizontal = edges(box);
    const vertical = verticalEdges(box);
    x.push(horizontal.start, horizontal.centre, horizontal.end);
    y.push(vertical.start, vertical.centre, vertical.end);
  }
  return { x, y };
};

// Snap one of a box's three horizontal positions (left, centre, right) to
// the nearest line, and report which line so the canvas can draw it.
const snapAxis = (positions, lines, gridMm, tolerance) => {
  let best = null;
  for (const [role, value] of Object.entries(positions)) {
    for (const line of lines) {
      const distance = Math.abs(value - line);
      if (distance <= tolerance && (best === null || distance < best.distance)) {
        best = { distance, delta: line - value, line, role };
      }
    }
  }
  if (best) return { delta: best.delta, guide: best.line };
  if (gridMm > 0) {
    // No neighbour to align with, so fall back to the grid -- applied to
    // the leading edge, which is the one the author is watching.
    const snapped = Math.round(positions.start / gridMm) * gridMm;
    return { delta: snapped - positions.start, guide: null };
  }
  return { delta: 0, guide: null };
};

export const clamp = (box, bounds) => {
  const w = Math.min(Math.max(box.w_mm, MIN_SIZE_MM), bounds.width);
  const h = Math.min(Math.max(box.h_mm, MIN_SIZE_MM), bounds.height);
  return {
    x_mm: roundMm(Math.min(Math.max(box.x_mm, 0), bounds.width - w)),
    y_mm: roundMm(Math.min(Math.max(box.y_mm, 0), bounds.height - h)),
    w_mm: roundMm(w),
    h_mm: roundMm(h),
  };
};

// Move a box by a millimetre delta, snapping and clamping.
export const moveBox = (box, dxMm, dyMm, options = {}) => {
  const { bounds, others = [], gridMm = 5, tolerance = SNAP_TOLERANCE_MM, snap = true } = options;
  let moved = { ...box, x_mm: box.x_mm + dxMm, y_mm: box.y_mm + dyMm };
  const guides = { x: null, y: null };

  if (snap) {
    const lines = snapLines(bounds, others);
    const x = snapAxis(edges(moved), lines.x, gridMm, tolerance);
    const y = snapAxis(verticalEdges(moved), lines.y, gridMm, tolerance);
    moved = { ...moved, x_mm: moved.x_mm + x.delta, y_mm: moved.y_mm + y.delta };
    guides.x = x.guide;
    guides.y = y.guide;
  }
  return { box: clamp(moved, bounds), guides };
};

// Which edges a handle drags. 'nw' moves the origin and shrinks the box;
// 'se' only changes the size. Expressed as coefficients so the arithmetic
// below is one expression rather than eight branches.
const HANDLE_AXES = {
  nw: { x: 1, y: 1, w: -1, h: -1 }, n: { x: 0, y: 1, w: 0, h: -1 },
  ne: { x: 0, y: 1, w: 1, h: -1 }, e: { x: 0, y: 0, w: 1, h: 0 },
  se: { x: 0, y: 0, w: 1, h: 1 }, s: { x: 0, y: 0, w: 0, h: 1 },
  sw: { x: 1, y: 0, w: -1, h: 1 }, w: { x: 1, y: 0, w: -1, h: 0 },
};

export const resizeBox = (box, handle, dxMm, dyMm, options = {}) => {
  const { bounds, gridMm = 5, snap = true } = options;
  const axes = HANDLE_AXES[handle];
  if (!axes) throw new Error(`unknown resize handle ${handle}`);

  let next = {
    x_mm: box.x_mm + axes.x * dxMm,
    y_mm: box.y_mm + axes.y * dyMm,
    w_mm: box.w_mm + axes.w * dxMm,
    h_mm: box.h_mm + axes.h * dyMm,
  };

  if (snap && gridMm > 0) {
    // Snap the edge being dragged, not the origin -- otherwise resizing
    // from the right silently moves the left.
    const snapTo = (value) => Math.round(value / gridMm) * gridMm;
    if (axes.x) { const x = snapTo(next.x_mm); next.w_mm += next.x_mm - x; next.x_mm = x; }
    if (axes.y) { const y = snapTo(next.y_mm); next.h_mm += next.y_mm - y; next.y_mm = y; }
    if (axes.w > 0) next.w_mm = snapTo(next.x_mm + next.w_mm) - next.x_mm;
    if (axes.h > 0) next.h_mm = snapTo(next.y_mm + next.h_mm) - next.y_mm;
  }

  // A box dragged through itself keeps its far edge put and stops at the
  // minimum, rather than inverting and jumping across the page.
  if (next.w_mm < MIN_SIZE_MM) {
    if (axes.x) next.x_mm = box.x_mm + box.w_mm - MIN_SIZE_MM;
    next.w_mm = MIN_SIZE_MM;
  }
  if (next.h_mm < MIN_SIZE_MM) {
    if (axes.y) next.y_mm = box.y_mm + box.h_mm - MIN_SIZE_MM;
    next.h_mm = MIN_SIZE_MM;
  }
  return clamp(next, bounds);
};

// Arrow-key nudge. One grid step normally, one millimetre with a
// modifier -- the fine adjustment an author reaches for last.
export const nudge = (box, direction, { bounds, gridMm = 5, fine = false }) => {
  const step = fine ? 1 : gridMm;
  const deltas = {
    ArrowLeft: [-step, 0], ArrowRight: [step, 0],
    ArrowUp: [0, -step], ArrowDown: [0, step],
  };
  const delta = deltas[direction];
  if (!delta) return box;
  return clamp({ ...box, x_mm: box.x_mm + delta[0], y_mm: box.y_mm + delta[1] }, bounds);
};

// Z-order. Returns a new z_index, never reorders the array -- the model
// stores the index, so that is what has to change.
export const reorder = (element, siblings, direction) => {
  const zs = siblings.map(item => item.z_index);
  if (direction === 'front') return Math.max(...zs, element.z_index) + 1;
  if (direction === 'back') return Math.min(...zs, element.z_index) - 1;
  return element.z_index;
};
