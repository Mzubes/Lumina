import fs from 'fs';
import path from 'path';

import {
  ALIGNMENTS, BORDERS, BREAK_RULES, CHART_KINDS, COLOR_ROLES, FILLS,
  LAYOUT_MODES, REPEAT_MODES, STYLE_TOKENS, VALIGNMENTS, controlsFor,
  elementClasses,
} from './elementStyles';

// The backend is the authority. This reads it rather than restating it:
// a copied vocabulary that drifts gives the author controls the API
// refuses, and the failure shows up as a save that silently 400s.
const SCHEMA = path.resolve(__dirname, '../../backend/schema_v2');
const STYLING_PY = path.join(SCHEMA, 'styling.py');
const TEMPLATES_PY = path.join(SCHEMA, 'templates.py');

const pythonTuple = (source, name) => {
  const match = source.match(new RegExp(`^${name} = \\(([\\s\\S]*?)\\)$`, 'm'));
  if (!match) throw new Error(`${name} not found in styling.py`);
  return [...match[1].matchAll(/'([^']+)'/g)].map(m => m[1]);
};

describe('the style vocabulary matches the backend', () => {
  const source = fs.readFileSync(STYLING_PY, 'utf8');

  test('style tokens', () => {
    // STYLE_TOKENS there is (token, label) pairs; take every other string.
    const pairs = pythonTuple(source, 'STYLE_TOKENS');
    const tokens = pairs.filter((_, index) => index % 2 === 0);
    expect(STYLE_TOKENS.map(t => t.value)).toEqual(tokens);
  });

  test.each([
    ['COLOR_ROLES', COLOR_ROLES],
    ['ALIGNMENTS', ALIGNMENTS],
    ['VALIGNMENTS', VALIGNMENTS],
    ['BORDERS', BORDERS],
    ['FILLS', FILLS],
    ['CHART_KINDS', CHART_KINDS],
  ])('%s', (name, ours) => {
    expect(ours).toEqual(pythonTuple(source, name));
  });
});

describe('the band vocabulary matches the backend', () => {
  const source = fs.readFileSync(TEMPLATES_PY, 'utf8');

  test.each([
    ['LAYOUT_MODES', LAYOUT_MODES],
    ['REPEAT_MODES', REPEAT_MODES],
    ['BREAK_RULES', BREAK_RULES],
  ])('%s', (name, ours) => {
    expect(ours).toEqual(pythonTuple(source, name));
  });
});

describe('elementClasses', () => {
  test('resolves a token and every option', () => {
    expect(elementClasses({
      style_token: 'heading-1',
      options: { align: 'right', valign: 'middle', color: 'accent', border: 'bottom', fill: 'tint' },
    })).toEqual(['st-heading-1', 'align-right', 'va-middle', 'color-accent',
      'border-bottom', 'fill-tint']);
  });

  test('drops anything outside the vocabulary', () => {
    // Same rule as the renderer: an unknown name draws nothing rather than
    // emitting a class the stylesheet has never heard of.
    expect(elementClasses({ style_token: 'heading-9', options: { align: 'sideways' } }))
      .toEqual([]);
  });

  test('an element with no styling carries no classes', () => {
    expect(elementClasses({ element_type: 'text' })).toEqual([]);
  });
});

describe('controlsFor', () => {
  test('a rule has colour but no typography', () => {
    const line = controlsFor('line');
    expect(line.color).toBe(true);
    expect(line.style).toBe(false);
    expect(line.align).toBe(false);
  });

  test('only a text element edits its own words', () => {
    expect(controlsFor('text').staticText).toBe(true);
    expect(controlsFor('field').staticText).toBe(false);
  });

  test('a chart picks its kind, an image its source', () => {
    expect(controlsFor('chart').chartKind).toBe(true);
    expect(controlsFor('image').src).toBe(true);
    expect(controlsFor('chart').src).toBe(false);
  });
});
