import {
  HANDLES, MIN_SIZE_MM, clamp, moveBox, nudge, reorder, resizeBox, snapLines,
} from './canvasGeometry';

const BOUNDS = { width: 178, height: 251 };
const box = (over = {}) => ({ x_mm: 20, y_mm: 20, w_mm: 40, h_mm: 10, ...over });

describe('moving', () => {
  test('a drag moves the box by the millimetres it was given', () => {
    const { box: moved } = moveBox(box(), 10, 5, { bounds: BOUNDS, snap: false });
    expect(moved).toMatchObject({ x_mm: 30, y_mm: 25, w_mm: 40, h_mm: 10 });
  });

  test('with no neighbour nearby it falls to the grid', () => {
    const { box: moved } = moveBox(box(), 2.4, 0, { bounds: BOUNDS, gridMm: 5, others: [] });
    expect(moved.x_mm).toBe(20);      // 22.4 -> nearest 5mm
  });

  test('it snaps to another element rather than to the grid', () => {
    // A neighbour's left edge at 23mm is closer than the 25mm gridline, so
    // the two line up exactly -- which is the whole point of the feature.
    const neighbour = box({ x_mm: 23, y_mm: 80 });
    const { box: moved, guides } = moveBox(box(), 3.6, 0,
      { bounds: BOUNDS, gridMm: 5, others: [neighbour] });
    expect(moved.x_mm).toBe(23);
    expect(guides.x).toBe(23);
  });

  test('centres align too, not just edges', () => {
    const neighbour = box({ x_mm: 100, w_mm: 40, y_mm: 80 });   // centre 120
    const { box: moved } = moveBox(box({ w_mm: 20 }), 90, 0,
      { bounds: BOUNDS, gridMm: 0, others: [neighbour] });
    expect(moved.x_mm + moved.w_mm / 2).toBe(120);
  });

  test('a box cannot be dragged off the page', () => {
    const { box: moved } = moveBox(box(), -500, -500, { bounds: BOUNDS, snap: false });
    expect(moved).toMatchObject({ x_mm: 0, y_mm: 0 });
    const { box: far } = moveBox(box(), 500, 500, { bounds: BOUNDS, snap: false });
    expect(far.x_mm + far.w_mm).toBe(BOUNDS.width);
    expect(far.y_mm + far.h_mm).toBe(BOUNDS.height);
  });

  test('the content box edges and centre are snap targets', () => {
    const lines = snapLines(BOUNDS, []);
    expect(lines.x).toEqual(expect.arrayContaining([0, 89, 178]));
    expect(lines.y).toEqual(expect.arrayContaining([0, 125.5, 251]));
  });
});

describe('resizing', () => {
  test('dragging the south-east handle changes size only', () => {
    const resized = resizeBox(box(), 'se', 10, 5, { bounds: BOUNDS, snap: false });
    expect(resized).toMatchObject({ x_mm: 20, y_mm: 20, w_mm: 50, h_mm: 15 });
  });

  test('dragging the north-west handle moves the origin and shrinks the box', () => {
    const resized = resizeBox(box(), 'nw', 5, 5, { bounds: BOUNDS, snap: false });
    expect(resized).toMatchObject({ x_mm: 25, y_mm: 25, w_mm: 35, h_mm: 5 });
  });

  test('resizing from the right does not move the left edge', () => {
    // The bug this guards: snapping the origin instead of the dragged edge
    // slides the whole box while the author is only widening it.
    const resized = resizeBox(box(), 'e', 3.7, 0, { bounds: BOUNDS, gridMm: 5 });
    expect(resized.x_mm).toBe(20);
    expect(resized.x_mm + resized.w_mm).toBe(65);   // snapped to the grid
  });

  test('a box dragged through itself stops instead of inverting', () => {
    const resized = resizeBox(box(), 'e', -500, 0, { bounds: BOUNDS, snap: false });
    expect(resized.w_mm).toBe(MIN_SIZE_MM);
    expect(resized.x_mm).toBe(20);
  });

  test('dragging a west handle past the east edge keeps the east edge put', () => {
    const resized = resizeBox(box(), 'w', 500, 0, { bounds: BOUNDS, snap: false });
    expect(resized.x_mm + resized.w_mm).toBe(60);   // the original right edge
    expect(resized.w_mm).toBe(MIN_SIZE_MM);
  });

  test.each(HANDLES)('handle %s produces a valid box', (handle) => {
    const resized = resizeBox(box(), handle, 7, 7, { bounds: BOUNDS });
    expect(resized.w_mm).toBeGreaterThanOrEqual(MIN_SIZE_MM);
    expect(resized.h_mm).toBeGreaterThanOrEqual(MIN_SIZE_MM);
    expect(resized.x_mm).toBeGreaterThanOrEqual(0);
    expect(resized.x_mm + resized.w_mm).toBeLessThanOrEqual(BOUNDS.width + 0.001);
  });

  test('an unknown handle is a programming error, not a silent no-op', () => {
    expect(() => resizeBox(box(), 'middle', 1, 1, { bounds: BOUNDS })).toThrow('middle');
  });
});

describe('keyboard', () => {
  test('an arrow key moves one grid step', () => {
    expect(nudge(box(), 'ArrowRight', { bounds: BOUNDS, gridMm: 5 }).x_mm).toBe(25);
  });

  test('the fine modifier moves one millimetre', () => {
    expect(nudge(box(), 'ArrowRight', { bounds: BOUNDS, gridMm: 5, fine: true }).x_mm).toBe(21);
  });

  test('a nudge respects the page edge', () => {
    expect(nudge(box({ x_mm: 0 }), 'ArrowLeft', { bounds: BOUNDS }).x_mm).toBe(0);
  });

  test('a key that is not an arrow leaves the box alone', () => {
    expect(nudge(box(), 'Enter', { bounds: BOUNDS })).toEqual(box());
  });
});

describe('z-order', () => {
  const siblings = [{ z_index: 0 }, { z_index: 3 }, { z_index: 1 }];

  test('bring to front clears every sibling', () => {
    expect(reorder({ z_index: 1 }, siblings, 'front')).toBe(4);
  });

  test('send to back clears every sibling the other way', () => {
    expect(reorder({ z_index: 1 }, siblings, 'back')).toBe(-1);
  });
});

describe('clamping', () => {
  test('an element larger than the page is shrunk, not pushed off it', () => {
    expect(clamp({ x_mm: 0, y_mm: 0, w_mm: 400, h_mm: 400 }, BOUNDS))
      .toEqual({ x_mm: 0, y_mm: 0, w_mm: 178, h_mm: 251 });
  });

  test('an element smaller than the minimum is grown to it', () => {
    expect(clamp({ x_mm: 0, y_mm: 0, w_mm: 0.2, h_mm: 0.2 }, BOUNDS).w_mm).toBe(MIN_SIZE_MM);
  });
});
