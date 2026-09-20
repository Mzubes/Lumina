import {
  DEFAULT_MARGINS_MM, MM_TO_PX, clampToBox, contentBox, gridStepMm, mmToPx,
  pageSize, pxToMm, roundMm, rulerTicks, snapMm,
} from './paper';

describe('the unit the canvas and the renderer share', () => {
  test('a millimetre is the CSS millimetre, exactly', () => {
    // CSS defines 1mm as 96/25.4 px. If this drifts, a template designed
    // on the canvas prints at a different size -- the exact failure the
    // plan rules out a bitmap canvas to avoid.
    expect(MM_TO_PX).toBeCloseTo(3.7795275590551185, 12);
    expect(mmToPx(25.4)).toBeCloseTo(96, 10);
  });

  test('converting back and forth loses nothing that matters', () => {
    for (const mm of [0, 1, 16, 178, 210, 297]) {
      expect(pxToMm(mmToPx(mm))).toBeCloseTo(mm, 10);
      expect(pxToMm(mmToPx(mm, 1.5), 1.5)).toBeCloseTo(mm, 10);
    }
  });

  test('rounding matches the three decimals the schema stores', () => {
    // So a position survives a save/load round trip instead of drifting a
    // hair every time.
    expect(roundMm(10.50049)).toBe(10.5);
    expect(roundMm(10.5005)).toBe(10.501);
  });
});

describe('page geometry', () => {
  test('A4 and Letter are the real sizes', () => {
    expect(pageSize('a4')).toEqual({ width: 210, height: 297 });
    expect(pageSize('letter')).toEqual({ width: 215.9, height: 279.4 });
  });

  test('landscape swaps the edges', () => {
    expect(pageSize('a4', 'landscape')).toEqual({ width: 297, height: 210 });
  });

  test('an unknown size falls back rather than rendering a zero-sized page', () => {
    expect(pageSize('tabloid')).toEqual(pageSize('a4'));
  });

  test('the content box is the sheet less its margins', () => {
    const box = contentBox({ size: 'a4', orientation: 'portrait' });
    expect(box).toEqual({ x: 16, y: 26, width: 178, height: 251 });
    // 178mm is the width the print stylesheet lays out against, so the two
    // genuinely agree rather than happening to look similar.
  });

  test('custom margins move the content box', () => {
    const box = contentBox({ size: 'a4', margins: { ...DEFAULT_MARGINS_MM, left: 30 } });
    expect(box.x).toBe(30);
    expect(box.width).toBe(210 - 30 - 16);
  });
});

describe('rulers and grid', () => {
  test('tick spacing widens as the page shrinks', () => {
    // At 50% a 5mm interval would put 42 labels in ~400px.
    expect(rulerTicks(210, 0.5).interval).toBeGreaterThan(rulerTicks(210, 2).interval);
  });

  test('every tick interval leaves room for its label', () => {
    for (const zoom of [0.5, 0.75, 1, 1.25, 1.5, 2]) {
      expect(mmToPx(rulerTicks(210, zoom).interval, zoom)).toBeGreaterThanOrEqual(44);
    }
  });

  test('ticks start at the sheet edge and reach the far one', () => {
    const { ticks, interval } = rulerTicks(210, 1);
    expect(ticks[0]).toBe(0);
    expect(ticks[ticks.length - 1]).toBeGreaterThan(210 - interval);
  });

  test('the grid coarsens rather than turning to mush when zoomed out', () => {
    expect(gridStepMm(1)).toBe(5);
    expect(gridStepMm(0.5)).toBe(10);
  });
});

describe('snapping and clamping', () => {
  test('snap lands on the grid', () => {
    expect(snapMm(12.4, 5)).toBe(10);
    expect(snapMm(13.1, 5)).toBe(15);
  });

  test('a zero step means no snapping, not a division by zero', () => {
    expect(snapMm(12.4, 0)).toBe(12.4);
  });

  test('an element cannot be dragged off the page', () => {
    const bounds = { width: 178, height: 251 };
    expect(clampToBox({ x_mm: -20, y_mm: -5, w_mm: 40, h_mm: 10 }, bounds))
      .toEqual({ x_mm: 0, y_mm: 0, w_mm: 40, h_mm: 10 });
    expect(clampToBox({ x_mm: 200, y_mm: 300, w_mm: 40, h_mm: 10 }, bounds))
      .toEqual({ x_mm: 138, y_mm: 241, w_mm: 40, h_mm: 10 });
  });

  test('an element wider than the page is shrunk to fit, not pushed off it', () => {
    expect(clampToBox({ x_mm: 0, y_mm: 0, w_mm: 400, h_mm: 500 }, { width: 178, height: 251 }))
      .toEqual({ x_mm: 0, y_mm: 0, w_mm: 178, h_mm: 251 });
  });
});
