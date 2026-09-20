import {
  CATEGORICAL_COLORS, MAX_SERIES, OTHER_COLOR, assignSeriesColors, colorForLabel,
} from './categoricalPalette';

const rows = (count) => Array.from({ length: count },
  (_, index) => ({ label: `Series ${index + 1}`, value: index + 1 }));

describe('assignSeriesColors', () => {
  test('assigns slots in fixed order', () => {
    expect(assignSeriesColors(rows(3)).map(row => row.color))
      .toEqual(CATEGORICAL_COLORS.slice(0, 3));
  });

  test('a filter that drops a series does not repaint the survivors', () => {
    // Colour follows the entity, not its rank in the current view -- the
    // first slot is the first slot whether three teams are showing or eight.
    const all = assignSeriesColors(rows(8));
    const fewer = assignSeriesColors(rows(3));
    expect(fewer.map(row => row.color)).toEqual(all.slice(0, 3).map(row => row.color));
  });

  test('folds past the palette instead of cycling back to slot one', () => {
    // The bug this module was extracted to fix: CATEGORICAL_COLORS[index %
    // length] gave the ninth series the first one's hue, so two different
    // teams read as one team.
    const folded = assignSeriesColors(rows(12));
    expect(folded).toHaveLength(MAX_SERIES);
    expect(folded[folded.length - 1]).toMatchObject({ label: 'Other', color: OTHER_COLOR });
    expect(new Set(folded.map(row => row.color)).size).toBe(folded.length);
  });

  test('folding keeps the total, so a part-to-whole bar still sums right', () => {
    const source = rows(12);
    const total = source.reduce((sum, row) => sum + row.value, 0);
    const folded = assignSeriesColors(source);
    expect(folded.reduce((sum, row) => sum + row.value, 0)).toBe(total);
  });

  test('a remainder label never takes a categorical slot', () => {
    const withUnassigned = [...rows(2), { label: 'Unassigned', value: 5 }];
    const assigned = assignSeriesColors(withUnassigned);
    expect(assigned.find(row => row.label === 'Unassigned').color).toBe(OTHER_COLOR);
    expect(assigned.filter(row => row.color !== OTHER_COLOR).map(row => row.color))
      .toEqual(CATEGORICAL_COLORS.slice(0, 2));
  });

  test('extra keys on a row survive', () => {
    const [first] = assignSeriesColors([{ label: 'A', value: 1, valueLabel: '1h' }]);
    expect(first.valueLabel).toBe('1h');
  });

  test.each([null, undefined, []])('empty input is empty output (%p)', (input) => {
    expect(assignSeriesColors(input)).toEqual([]);
  });
});

describe('colorForLabel', () => {
  test('is stable for the same label', () => {
    expect(colorForLabel('Client Reporting')).toBe(colorForLabel('Client Reporting'));
  });

  test('only ever returns a palette slot', () => {
    for (const label of ['', 'a', 'Compliance', 'Ünïcødé', 'a'.repeat(200)]) {
      expect(CATEGORICAL_COLORS).toContain(colorForLabel(label));
    }
  });
});
