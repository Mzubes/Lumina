// The one categorical palette, and the only two ways to draw from it.
//
// Four files used to carry their own copy of this list. Worse, the copies
// were six slots of an eight-hue set in a different order, and that order
// fails: on the white card these charts sit on, --cat-5 magenta and --cat-6
// red were adjacent at OKLab dE 13.2, under the normal-vision floor of 15.
// Every ordering of those six was enumerated against the dataviz skill's
// validator and none clears every gate, so the fix was the two missing
// hues, not a re-order. See styles.css for the validated set.
//
// The print renderer (backend/renderers/chart_palette.py) holds the same
// eight in the same order, for the same reason: a printed chart sits on
// paper white, which is the same ground as the card.

export const CATEGORICAL_COLORS = [
  'var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)',
  'var(--cat-5)', 'var(--cat-6)', 'var(--cat-7)', 'var(--cat-8)',
];

export const OTHER_COLOR = 'var(--cat-other)';
export const OTHER_LABELS = new Set(['Other', 'Unassigned', 'Unclassified']);
export const MAX_SERIES = CATEGORICAL_COLORS.length;

// A stable colour for an open-ended label space -- a firm-custom workflow
// step, a client's initials. Hashing means two labels can collide, which is
// the accepted cost of not having a fixed slot list to assign from; it is
// NOT the same as cycling by rank, which would give the 9th series in a
// known list the 1st one's hue and make two entities look like one.
export const colorForLabel = (label) => {
  let hash = 0;
  for (let index = 0; index < label.length; index += 1) {
    hash = (hash * 31 + label.charCodeAt(index)) >>> 0;
  }
  return CATEGORICAL_COLORS[hash % CATEGORICAL_COLORS.length];
};

// Slot assignment for a known, ordered series list. Past the palette's
// length the tail is SUMMED into "Other" rather than wrapping back to slot
// one: a repeated hue makes two different things look like one thing, which
// is a wrong chart rather than a crowded one.
//
// `rows` are {label, value}; the returned rows carry a colour.
export const assignSeriesColors = (rows) => {
  const named = (rows || []).filter(row => !OTHER_LABELS.has(row.label));
  const reserved = (rows || []).filter(row => OTHER_LABELS.has(row.label))
    .map(row => ({ ...row, color: OTHER_COLOR }));

  if (named.length <= MAX_SERIES) {
    return [...named.map((row, index) => ({ ...row, color: CATEGORICAL_COLORS[index] })),
            ...reserved];
  }

  const kept = named.slice(0, MAX_SERIES - 1)
    .map((row, index) => ({ ...row, color: CATEGORICAL_COLORS[index] }));
  const remainder = named.slice(MAX_SERIES - 1)
    .reduce((sum, row) => sum + (row.value || 0), 0)
    + reserved.reduce((sum, row) => sum + (row.value || 0), 0);
  return [...kept, { label: 'Other', value: remainder, color: OTHER_COLOR }];
};
